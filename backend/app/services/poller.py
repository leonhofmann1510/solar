from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select, text

from app.config import settings
from app.database import async_session
from app.models import DeviceState, EVSession, InverterDailyStat, MeterReading, SelfSufficiencyHistory
from app.services import app_settings as app_svc
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

# EV charging state
_ev_active_session_id: int | None = None
_ev_was_charging: bool = False
_ev_session_solar_seconds: int = 0
_ev_session_grid_seconds: int = 0
_ev_session_start: datetime | None = None


def _build_inverters() -> list[SungrowModbus]:
    configs = load_inverter_configs(settings.inverters_config_path)
    return [SungrowModbus(cfg) for cfg in configs]


async def poll_loop(app_state: AppState) -> None:
    """Background polling loop — reads inverters + smart meter, stores data, evaluates rules."""
    global _last_save_hour, _prev_inverter_readings, _prev_meter_data
    global _ev_active_session_id, _ev_was_charging, _ev_session_solar_seconds, _ev_session_grid_seconds, _ev_session_start

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

                # EV charging state machine
                if settings.ev_charging_enabled:
                    try:
                        ev_cfg = app_svc.get_all()
                        wallbox_device_id = ev_cfg.get("ev_wallbox_device_id")
                        capability_key = ev_cfg.get("ev_charging_capability_key", "")
                        charging_value = ev_cfg.get("ev_charging_value", "charging")
                        charging_power_kw = float(ev_cfg.get("ev_charging_power_kw", 11.0))
                        battery_threshold = float(ev_cfg.get("ev_battery_threshold_pct", 15.0))
                        efficiency = float(ev_cfg.get("ev_efficiency_km_per_kwh", 6.0))
                        cost_solar = float(ev_cfg.get("ev_cost_per_100km_solar_eur", 0.5))
                        cost_grid = float(ev_cfg.get("ev_cost_per_100km_grid_eur", 4.5))
                        cost_gas = float(ev_cfg.get("ev_cost_per_100km_gas_eur", 10.0))

                        is_charging = False
                        if wallbox_device_id and capability_key:
                            async with async_session() as db:
                                ds_result = await db.execute(
                                    select(DeviceState).where(
                                        DeviceState.device_id == wallbox_device_id,
                                        DeviceState.capability_key == capability_key,
                                    )
                                )
                                ds = ds_result.scalar_one_or_none()
                                if ds is not None:
                                    is_charging = (ds.value_string == charging_value)
                                    logger.debug(
                                        "EV poll: device=%s key=%r stored_value=%r match_value=%r → is_charging=%s",
                                        wallbox_device_id, capability_key, ds.value_string, charging_value, is_charging,
                                    )
                                else:
                                    logger.debug(
                                        "EV poll: device=%s key=%r → no row in device_states (device not yet polled or wrong key)",
                                        wallbox_device_id, capability_key,
                                    )
                        else:
                            logger.debug("EV poll: skipped — wallbox_device_id=%s capability_key=%r", wallbox_device_id, capability_key)

                        # Determine solar vs grid
                        battery_soc: float | None = None
                        if readings:
                            battery_soc = readings[0].battery_soc_pct
                        is_solar = battery_soc is not None and battery_soc > battery_threshold

                        now_ts = datetime.now(tz=timezone.utc)

                        if is_charging and not _ev_was_charging:
                            # SESSION START
                            _ev_session_solar_seconds = 0
                            _ev_session_grid_seconds = 0
                            _ev_session_start = now_ts
                            async with async_session() as db:
                                session_row = EVSession(
                                    started_at=now_ts,
                                    charging_power_kw=charging_power_kw,
                                    efficiency_km_per_kwh=efficiency,
                                    cost_per_100km_solar_eur=cost_solar,
                                    cost_per_100km_grid_eur=cost_grid,
                                    cost_per_100km_gas_eur=cost_gas,
                                )
                                db.add(session_row)
                                await db.commit()
                                await db.refresh(session_row)
                                _ev_active_session_id = session_row.id
                            logger.info("EV session started (id=%d)", _ev_active_session_id)

                        elif is_charging and _ev_was_charging:
                            # ONGOING — accumulate time
                            interval = settings.poll_interval_seconds
                            if is_solar:
                                _ev_session_solar_seconds += interval
                            else:
                                _ev_session_grid_seconds += interval
                            logger.info(
                                "EV ongoing: session=%s solar=%ds grid=%ds (is_solar=%s)",
                                _ev_active_session_id, _ev_session_solar_seconds, _ev_session_grid_seconds, is_solar,
                            )

                        elif not is_charging and _ev_was_charging:
                            # SESSION END
                            if _ev_active_session_id is not None:
                                total_seconds = _ev_session_solar_seconds + _ev_session_grid_seconds
                                if total_seconds > 0:
                                    duration_hours = total_seconds / 3600
                                    kwh_total = charging_power_kw * duration_hours
                                    kwh_solar = kwh_total * (_ev_session_solar_seconds / total_seconds)
                                    kwh_grid = kwh_total * (_ev_session_grid_seconds / total_seconds)
                                    km_solar = kwh_solar * efficiency
                                    km_grid = kwh_grid * efficiency
                                    km_total = kwh_total * efficiency
                                    cost_eur = (km_solar / 100 * cost_solar) + (km_grid / 100 * cost_grid)
                                    gas_cost = km_total / 100 * cost_gas
                                    savings = gas_cost - cost_eur
                                else:
                                    kwh_total = kwh_solar = kwh_grid = km_solar = km_grid = km_total = 0.0
                                    cost_eur = savings = 0.0

                                async with async_session() as db:
                                    result = await db.execute(
                                        select(EVSession).where(EVSession.id == _ev_active_session_id)
                                    )
                                    session_row = result.scalar_one_or_none()
                                    if session_row:
                                        session_row.ended_at = now_ts
                                        session_row.kwh_total = round(kwh_total, 3)
                                        session_row.kwh_solar = round(kwh_solar, 3)
                                        session_row.kwh_grid = round(kwh_grid, 3)
                                        session_row.duration_solar_seconds = _ev_session_solar_seconds
                                        session_row.duration_grid_seconds = _ev_session_grid_seconds
                                        session_row.cost_eur = round(cost_eur, 2)
                                        session_row.savings_vs_gas_eur = round(savings, 2)
                                        await db.commit()

                                await ws_manager.broadcast({
                                    "event": "ev_session_ended",
                                    "session_id": _ev_active_session_id,
                                })
                                logger.info("EV session ended (id=%d, %.3f kWh)", _ev_active_session_id, kwh_total)

                            _ev_active_session_id = None
                            _ev_session_solar_seconds = 0
                            _ev_session_grid_seconds = 0
                            _ev_session_start = None

                        # Broadcast current EV status on every cycle while charging
                        if is_charging:
                            await ws_manager.broadcast({
                                "event": "ev_status",
                                "is_charging": True,
                                "session_id": _ev_active_session_id,
                                "duration_solar_seconds": _ev_session_solar_seconds,
                                "duration_grid_seconds": _ev_session_grid_seconds,
                            })

                        _ev_was_charging = is_charging

                    except Exception:
                        logger.exception("Error in EV state machine")

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

                    # Compute and save self-sufficiency rate snapshot
                    try:
                        since_365: date = (datetime.now(tz=timezone.utc) - timedelta(days=365)).date()
                        rate_query = text("""
                            SELECT
                                COALESCE(SUM(sc), 0) AS total_self_consumption,
                                COALESCE(SUM(sc) + SUM(gb), 0) AS total_consumption
                            FROM (
                                SELECT
                                    GREATEST(0, SUM(max_yield) - MAX(max_feed_in)) AS sc,
                                    COALESCE(MAX(max_grid_buy), 0) AS gb
                                FROM (
                                    SELECT date, inverter_id,
                                        MAX(pv_yield_today_kwh) AS max_yield,
                                        MAX(feed_in_today_kwh)  AS max_feed_in,
                                        MAX(grid_buy_today_kwh) AS max_grid_buy
                                    FROM inverter_daily_stats
                                    WHERE date >= :since
                                    GROUP BY date, inverter_id
                                ) per_inv
                                GROUP BY date
                            ) per_day
                        """)
                        async with async_session() as session:
                            result = await session.execute(rate_query, {"since": since_365})
                            row = result.fetchone()
                            total_sc = float(row.total_self_consumption or 0.0)
                            total_consumption = float(row.total_consumption or 0.0)
                            rate_pct = round((total_sc / total_consumption * 100) if total_consumption > 0 else 0.0, 1)
                            session.add(SelfSufficiencyHistory(
                                timestamp=datetime.now(tz=timezone.utc),
                                rate_pct=rate_pct,
                            ))
                            await session.commit()
                        logger.info("Saved self-sufficiency snapshot: %.1f%%", rate_pct)
                    except Exception:
                        logger.exception("Failed to save self-sufficiency snapshot")

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
