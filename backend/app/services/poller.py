from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from app.config import settings
from app.database import async_session
from app.models import InverterReading, MeterReading
from app.services.meter import BitshakeSmartMeter, MeterData
from app.services.modbus import InverterData, SungrowModbus, load_inverter_configs
from app.services.mqtt import MQTTClient
from app.services.rules_engine import run_engine

if TYPE_CHECKING:
    from app.routers.ws import ConnectionManager

logger = logging.getLogger(__name__)


def _build_inverters() -> list[SungrowModbus]:
    configs = load_inverter_configs(settings.inverters_config_path)
    return [SungrowModbus(cfg) for cfg in configs]


def _meter_to_orm(data: MeterData) -> MeterReading:
    return MeterReading(
        timestamp=data.timestamp,
        consumption_kwh=data.consumption_kwh,
        feed_in_kwh=data.feed_in_kwh,
    )


def _to_orm(data: InverterData) -> InverterReading:
    return InverterReading(
        timestamp=data.timestamp,
        inverter_id=data.inverter_id,
        pv_power_w=data.pv_power_w,
        pv_string1_w=data.pv_string1_w,
        pv_string2_w=data.pv_string2_w,
        battery_soc_pct=data.battery_soc_pct,
        battery_power_w=data.battery_power_w,
        battery_running_state=data.battery_running_state,
        grid_power_w=data.grid_power_w,
        pv_yield_today_kwh=data.pv_yield_today_kwh,
        feed_in_today_kwh=data.feed_in_today_kwh,
        grid_buy_today_kwh=data.grid_buy_today_kwh,
        inverter_temp_c=data.inverter_temp_c,
        grid_frequency_hz=data.grid_frequency_hz,
    )


async def poll_loop(mqtt_client: MQTTClient, ws_manager: ConnectionManager) -> None:
    """Background polling loop — reads inverters + smart meter, stores data, evaluates rules."""
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

                if readings:
                    async with async_session() as session:
                        for data in readings:
                            session.add(_to_orm(data))
                        await session.commit()
                        logger.info("Stored %d inverter reading(s)", len(readings))

                        await run_engine(session, mqtt_client, readings)

                    for data in readings:
                        await ws_manager.broadcast(asdict(data))

                # Poll smart meter independently — failures don't affect inverter polling
                if meter:
                    meter_data = await meter.fetch()
                    if meter_data:
                        async with async_session() as session:
                            session.add(_meter_to_orm(meter_data))
                            await session.commit()
                        await ws_manager.broadcast({
                            "event": "meter_reading",
                            "timestamp": meter_data.timestamp.isoformat(),
                            "consumption_kwh": meter_data.consumption_kwh,
                            "feed_in_kwh": meter_data.feed_in_kwh,
                        })

            except Exception:
                logger.exception("Unhandled error in poll iteration — will retry next cycle")

            await asyncio.sleep(settings.poll_interval_seconds)
    finally:
        for inv in inverters:
            inv.close()
