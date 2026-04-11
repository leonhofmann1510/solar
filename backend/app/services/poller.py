from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.config import settings
from app.database import async_session
from app.models import InverterDailyStat, MeterReading
from app.services.meter import BitshakeSmartMeter, MeterData
from app.services.modbus import InverterData, SungrowModbus, load_inverter_configs
from app.services.rules_engine import run_engine

if TYPE_CHECKING:
    from app.state import AppState

logger = logging.getLogger(__name__)

# Module-level state for hourly save logic
_last_save_hour: int | None = None
_prev_inverter_readings: list[InverterData] = []
_prev_meter_data: MeterData | None = None


def _build_inverters() -> list[SungrowModbus]:
    configs = load_inverter_configs(settings.inverters_config_path)
    return [SungrowModbus(cfg) for cfg in configs]


async def poll_loop(app_state: AppState) -> None:
    """Background polling loop — reads inverters + smart meter, stores data, evaluates rules."""
    global _last_save_hour, _prev_inverter_readings, _prev_meter_data

    mqtt_client = app_state.mqtt_client
    ws_manager = app_state.ws_manager

    try:
        inverters = _build_inverters()
    except Exception:
        logger.exception("Failed to load inverter config — poller cannot start")
        return

    if not inverters:
        logger.error("No inverters loaded (check INVERTERS_CONFIG_PATH and inverters.yaml) — poller will not poll")
        return

    meter = BitshakeSmartMeter(ip=settings.smart_meter_ip) if settings.smart_meter_enabled else None

    for inv in inverters:
        if inv.connect():
            logger.info("Connected to inverter %s at %s", inv.inverter_id, inv.ip)
        else:
            logger.error("Failed to connect to inverter %s at %s", inv.inverter_id, inv.ip)

    if meter:
        logger.info("Smart meter polling enabled (%s)", settings.smart_meter_ip)

    try:
        while True:
            try:
                readings: list[InverterData] = []

                for inv in inverters:
                    data = inv.read()
                    if data:
                        readings.append(data)

                current_hour = datetime.now(tz=timezone.utc).hour
                hour_changed = _last_save_hour is not None and current_hour != _last_save_hour

                if readings:
                    # Update in-memory latest (no DB write)
                    for data in readings:
                        app_state.latest_readings[data.inverter_id] = data

                    async with async_session() as session:
                        await run_engine(session, mqtt_client, readings)

                    for data in readings:
                        await ws_manager.broadcast(asdict(data))

                # Poll smart meter independently — failures don't affect inverter polling
                meter_data: MeterData | None = None
                if meter:
                    meter_data = await meter.fetch()
                    if meter_data:
                        await ws_manager.broadcast({
                            "event": "meter_reading",
                            "timestamp": meter_data.timestamp.isoformat(),
                            "consumption_kwh": meter_data.consumption_kwh,
                            "feed_in_kwh": meter_data.feed_in_kwh,
                        })

                # Hourly save: persist previous hour's snapshots when the hour rolls over
                if hour_changed:
                    if _prev_meter_data is not None:
                        async with async_session() as session:
                            session.add(MeterReading(
                                timestamp=_prev_meter_data.timestamp,
                                consumption_kwh=_prev_meter_data.consumption_kwh,
                                feed_in_kwh=_prev_meter_data.feed_in_kwh,
                            ))
                            await session.commit()
                        logger.info("Saved hourly meter snapshot for hour %d", _last_save_hour)

                    if _prev_inverter_readings:
                        async with async_session() as session:
                            for data in _prev_inverter_readings:
                                session.add(InverterDailyStat(
                                    timestamp=data.timestamp,
                                    inverter_id=data.inverter_id,
                                    date=data.timestamp.date(),
                                    hour=_last_save_hour,
                                    pv_yield_today_kwh=data.pv_yield_today_kwh,
                                    feed_in_today_kwh=data.feed_in_today_kwh,
                                    grid_buy_today_kwh=data.grid_buy_today_kwh,
                                ))
                            await session.commit()
                        logger.info("Saved hourly inverter stats for hour %d", _last_save_hour)

                # Store current as "previous" for next cycle
                if readings:
                    _prev_inverter_readings = list(readings)
                if meter_data is not None:
                    _prev_meter_data = meter_data
                if _last_save_hour is None or hour_changed:
                    _last_save_hour = current_hour

            except Exception:
                logger.exception("Unhandled error in poll iteration — will retry next cycle")

            await asyncio.sleep(settings.poll_interval_seconds)
    finally:
        for inv in inverters:
            inv.close()
