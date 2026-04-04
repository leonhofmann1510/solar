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

# Threshold for triggering network rescan
RESCAN_FAILURE_THRESHOLD = 3


async def poll_device_states(ws_manager=None) -> None:
    """Background loop that polls Tuya device states every poll interval."""
    last_rescan_time = None
    
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
                
                # Track if we need a network rescan
                need_rescan = False
                offline_count = 0

                for device in devices:
                    try:
                        logger.debug(
                            "Polling Tuya device %d (%s) at %s",
                            device.id, device.name, device.ip_address
                        )
                        dps = await tuya_protocol.read_state(device)
                    except Exception as e:
                        logger.exception("Failed to read state for Tuya device %d (%s)", device.id, device.name)
                        
                        # Increment failure counter
                        device.consecutive_failures += 1
                        device.last_error = str(e)
                        
                        # Mark device as offline after first failure
                        if device.is_online:
                            logger.warning(
                                "Device %d (%s) at %s is now OFFLINE (failure %d)",
                                device.id, device.name, device.ip_address, device.consecutive_failures
                            )
                            device.is_online = False
                            offline_count += 1
                            
                            # Broadcast offline status
                            if ws_manager:
                                await ws_manager.broadcast({
                                    "event": "device_offline",
                                    "device_id": device.id,
                                    "device_name": device.name,
                                })
                        
                        # Trigger rescan if failures exceed threshold
                        if device.consecutive_failures >= RESCAN_FAILURE_THRESHOLD:
                            logger.warning(
                                "Device %d (%s) has %d consecutive failures, will trigger network rescan",
                                device.id, device.name, device.consecutive_failures
                            )
                            need_rescan = True
                        
                        await session.commit()
                        continue
                        
                    if not dps:
                        # No data but no exception - treat as offline
                        device.consecutive_failures += 1
                        device.last_error = "No data returned"

                        if device.is_online:
                            logger.warning(
                                "Device %d (%s) returned no data, marking OFFLINE",
                                device.id, device.name
                            )
                            device.is_online = False
                            offline_count += 1

                            if ws_manager:
                                await ws_manager.broadcast({
                                    "event": "device_offline",
                                    "device_id": device.id,
                                    "device_name": device.name,
                                })

                        if device.consecutive_failures >= RESCAN_FAILURE_THRESHOLD:
                            logger.warning(
                                "Device %d (%s) has %d consecutive failures, will trigger network rescan",
                                device.id, device.name, device.consecutive_failures
                            )
                            need_rescan = True

                        await session.commit()
                        continue

                    # Success! Device is online
                    was_offline = not device.is_online
                    device.is_online = True
                    device.consecutive_failures = 0
                    device.last_error = None
                    device.last_seen_at = datetime.now(UTC)
                    
                    if was_offline:
                        logger.info(
                            "Device %d (%s) at %s is now ONLINE",
                            device.id, device.name, device.ip_address
                        )
                        if ws_manager:
                            await ws_manager.broadcast({
                                "event": "device_online",
                                "device_id": device.id,
                                "device_name": device.name,
                            })

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

                    await session.commit()
                
                # Trigger network rescan if needed (offline_count check removed — devices
                # already offline have offline_count=0 every subsequent poll)
                if need_rescan:
                    now = datetime.now(UTC)
                    if last_rescan_time is None or (now - last_rescan_time).total_seconds() > 300:
                        last_rescan_time = now
                        logger.info("Triggering network rescan due to offline devices")
                        from app.services.discovery.tuya_discovery import scan_and_update_ips
                        try:
                            result = await scan_and_update_ips()
                            logger.info("Rescan complete: %s", result)
                        except Exception:
                            logger.exception("Network rescan failed")

        except Exception:
            logger.exception("Error in device state poller")

        await asyncio.sleep(settings.poll_interval_seconds)
