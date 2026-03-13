from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from app.config import settings
from app.database import async_session
from app.models import InverterReading
from app.services.modbus import InverterData, SungrowModbus
from app.services.mqtt import MQTTClient
from app.services.rules_engine import run_engine

if TYPE_CHECKING:
    from app.routers.ws import ConnectionManager

logger = logging.getLogger(__name__)


def _build_inverters() -> list[SungrowModbus]:
    return [
        SungrowModbus(
            ip=settings.modbus_ip_inverter_1,
            port=settings.modbus_port,
            unit_id=settings.modbus_unit_id,
            inverter_id="inv1",
            has_battery=True,
        ),
        SungrowModbus(
            ip=settings.modbus_ip_inverter_2,
            port=settings.modbus_port,
            unit_id=settings.modbus_unit_id,
            inverter_id="inv2",
            has_battery=False,
        ),
    ]


def _to_orm(data: InverterData) -> InverterReading:
    return InverterReading(
        timestamp=data.timestamp,
        inverter_id=data.inverter_id,
        pv_power_w=data.pv_power_w,
        pv_string1_w=data.pv_string1_w,
        pv_string2_w=data.pv_string2_w,
        battery_soc_pct=data.battery_soc_pct,
        battery_power_w=data.battery_power_w,
        grid_power_w=data.grid_power_w,
        house_load_w=data.house_load_w,
        pv_yield_today_kwh=data.pv_yield_today_kwh,
        feed_in_today_kwh=data.feed_in_today_kwh,
        grid_buy_today_kwh=data.grid_buy_today_kwh,
        inverter_temp_c=data.inverter_temp_c,
        grid_frequency_hz=data.grid_frequency_hz,
    )


async def poll_loop(mqtt_client: MQTTClient, ws_manager: ConnectionManager) -> None:
    """Background polling loop — reads inverters, stores data, evaluates rules."""
    inverters = _build_inverters()

    for inv in inverters:
        if inv.connect():
            logger.info("Connected to inverter %s at %s", inv.inverter_id, inv.ip)
        else:
            logger.error("Failed to connect to inverter %s at %s", inv.inverter_id, inv.ip)

    try:
        while True:
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
                    logger.info("Stored %d reading(s)", len(readings))

                    await run_engine(session, mqtt_client, readings)

                for data in readings:
                    await ws_manager.broadcast(asdict(data))

            await asyncio.sleep(settings.poll_interval_seconds)
    finally:
        for inv in inverters:
            inv.close()
