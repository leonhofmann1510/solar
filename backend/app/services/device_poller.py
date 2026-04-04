import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import async_session
from app.models import Device, DeviceCapability, DeviceState
from app.services.protocols import tuya_protocol

logger = logging.getLogger(__name__)


async def poll_device_states(ws_manager=None) -> None:
    """Background loop that polls Tuya device states every poll interval."""
    while True:
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(Device).where(
                        Device.confirmed.is_(True),
                        Device.enabled.is_(True),
                        Device.protocol == "tuya",
                    )
                )
                devices = result.scalars().all()

                for device in devices:
                    try:
                        dps = await tuya_protocol.read_state(device)
                    except Exception:
                        logger.exception("Failed to read state for Tuya device %d (%s)", device.id, device.name)
                        continue
                    if not dps:
                        continue

                    # Look up capabilities to map dp_id -> capability_key
                    cap_result = await session.execute(
                        select(DeviceCapability).where(
                            DeviceCapability.device_id == device.id,
                            DeviceCapability.tuya_dp_id.isnot(None),
                        )
                    )
                    caps = {str(c.tuya_dp_id): c for c in cap_result.scalars().all()}

                    for dp_id_str, value in dps.items():
                        cap = caps.get(str(dp_id_str))
                        if not cap:
                            continue

                        value_boolean = None
                        value_numeric = None
                        value_string = None

                        if isinstance(value, bool):
                            value_boolean = value
                        elif isinstance(value, (int, float)):
                            value_numeric = float(value)
                        else:
                            value_string = str(value)

                        stmt = pg_insert(DeviceState).values(
                            device_id=device.id,
                            capability_key=cap.key,
                            value_boolean=value_boolean,
                            value_numeric=value_numeric,
                            value_string=value_string,
                            updated_at=datetime.now(UTC),
                        ).on_conflict_do_update(
                            constraint="uq_device_state_key",
                            set_={
                                "value_boolean": value_boolean,
                                "value_numeric": value_numeric,
                                "value_string": value_string,
                                "updated_at": datetime.now(UTC),
                            },
                        )
                        await session.execute(stmt)

                        if ws_manager:
                            broadcast_value = value_boolean if value_boolean is not None else (
                                value_numeric if value_numeric is not None else value_string
                            )
                            await ws_manager.broadcast({
                                "event": "device_state_changed",
                                "device_id": device.id,
                                "capability_key": cap.key,
                                "value": broadcast_value,
                            })

                    # Update last_seen_at
                    device.last_seen_at = datetime.now(UTC)
                    await session.commit()

        except Exception:
            logger.exception("Error in device state poller")

        await asyncio.sleep(settings.poll_interval_seconds)
