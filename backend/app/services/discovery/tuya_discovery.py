import logging

from sqlalchemy import select

from app.database import async_session
from app.models import Device, DeviceCapability

logger = logging.getLogger(__name__)


async def fetch_tuya_devices(api_key: str, api_secret: str, region: str) -> int:
    """Fetch all Tuya devices via the cloud API and store them locally.

    Returns the count of newly discovered devices.
    """
    try:
        import tinytuya
    except ImportError:
        logger.error("tinytuya not installed — cannot fetch Tuya devices")
        return 0

    if not api_key or not api_secret:
        logger.error("Tuya API key/secret not configured")
        return 0

    try:
        cloud = tinytuya.Cloud(apiRegion=region, apiKey=api_key, apiSecret=api_secret)
        devices = cloud.getdevices()
    except Exception:
        logger.exception("Failed to fetch Tuya device list from cloud")
        return 0

    if not devices:
        logger.info("No Tuya devices returned from cloud API")
        return 0

    count = 0
    async with async_session() as session:
        for dev in devices:
            device_id = dev.get("id", "")
            name = dev.get("name", device_id)
            local_key = dev.get("key", "")
            ip = dev.get("ip", "")
            category = dev.get("category", "")

            # Log what we actually received for debugging
            logger.info("Tuya device raw data: %s", {
                "id": device_id,
                "name": name,
                "category": category,
                "has_ip": bool(ip),
                "has_key": bool(local_key),
                "keys": list(dev.keys())
            })

            result = await session.execute(
                select(Device).where(Device.raw_id == device_id, Device.protocol == "tuya")
            )
            if result.scalar_one_or_none():
                logger.info("Skipping existing Tuya device: %s", device_id)
                continue

            device = Device(
                name=name,
                protocol="tuya",
                raw_id=device_id,
                ip_address=ip or None,
                tuya_local_key=local_key,
                meta=dev,
                confirmed=False,
            )
            session.add(device)
            await session.flush()

            # Try to get capabilities from multiple sources
            capabilities_added = 0

            # 1. From DPS info if available
            dps = dev.get("dps") or {}
            for dp_id_str, dp_value in dps.items():
                dp_id = int(dp_id_str)
                # Guess data type from value
                data_type = "boolean" if isinstance(dp_value, bool) else (
                    "float" if isinstance(dp_value, (int, float)) else "string"
                )
                cap = DeviceCapability(
                    device_id=device.id,
                    key=f"dp_{dp_id}",
                    display_name=f"DP {dp_id}",
                    capability_type="both",
                    data_type=data_type,
                    tuya_dp_id=dp_id,
                )
                session.add(cap)
                capabilities_added += 1

            # 2. Try to get device status to discover actual DPs
            if capabilities_added == 0:
                try:
                    device_status = cloud.getstatus(device_id)
                    if device_status and "result" in device_status:
                        for dp_data in device_status["result"]:
                            dp_id = dp_data.get("code")  # or "dp_id"
                            dp_value = dp_data.get("value")
                            dp_name = dp_data.get("code", f"dp_{dp_id}")

                            # Guess data type from actual value
                            if isinstance(dp_value, bool):
                                data_type = "boolean"
                            elif isinstance(dp_value, int):
                                data_type = "integer"
                            elif isinstance(dp_value, float):
                                data_type = "float"
                            else:
                                data_type = "string"

                            cap = DeviceCapability(
                                device_id=device.id,
                                key=dp_name,
                                display_name=dp_name.replace("_", " ").title(),
                                capability_type="both",
                                data_type=data_type,
                                tuya_dp_id=dp_data.get("dp_id") if dp_data.get("dp_id") else None,
                            )
                            session.add(cap)
                            capabilities_added += 1
                except Exception:
                    logger.warning("Could not get device status for %s", device_id)

            # 3. Try to get detailed device info with functions
            if capabilities_added == 0:
                try:
                    device_details = cloud.getdevicespec(device_id)
                    if device_details and "functions" in device_details:
                        for func in device_details["functions"]:
                            dp_id = func.get("dp_id")
                            code = func.get("code", f"dp_{dp_id}")
                            name = func.get("name", code)
                            data_type_info = func.get("type", "")

                            # Map Tuya types to our types
                            if data_type_info == "Boolean":
                                data_type = "boolean"
                            elif data_type_info in ["Integer", "Enum"]:
                                data_type = "integer"
                            elif data_type_info == "Json":
                                data_type = "string"
                            else:
                                data_type = "string"

                            cap = DeviceCapability(
                                device_id=device.id,
                                key=code,
                                display_name=name,
                                capability_type="both",
                                data_type=data_type,
                                tuya_dp_id=dp_id,
                            )
                            session.add(cap)
                            capabilities_added += 1
                except Exception:
                    logger.warning("Could not get device functions for %s", device_id)

            # 4. Add default capabilities for common categories if we have none
            if capabilities_added == 0:
                default_caps = _get_default_capabilities(category)
                for cap_data in default_caps:
                    cap = DeviceCapability(device_id=device.id, **cap_data)
                    session.add(cap)
                    capabilities_added += 1

            count += 1
            logger.info("Tuya discovered: %s (%s) with %d capabilities",
                       name, device_id, capabilities_added)

        await session.commit()

    return count


def _get_default_capabilities(category: str) -> list[dict]:
    """Get default capabilities for common Tuya device categories."""
    defaults = {
        "cz": [  # Smart Plug
            {"key": "switch_1", "display_name": "Switch", "capability_type": "both", "data_type": "boolean", "tuya_dp_id": 1},
        ],
        "kg": [  # Switch
            {"key": "switch_1", "display_name": "Switch 1", "capability_type": "both", "data_type": "boolean", "tuya_dp_id": 1},
        ],
        "dj": [  # Light
            {"key": "switch_led", "display_name": "Light", "capability_type": "both", "data_type": "boolean", "tuya_dp_id": 1},
            {"key": "work_mode", "display_name": "Brightness", "capability_type": "both", "data_type": "integer", "tuya_dp_id": 2},
        ],
        "dc": [  # Curtain
            {"key": "control", "display_name": "Control", "capability_type": "both", "data_type": "string", "tuya_dp_id": 1},
            {"key": "percent_control", "display_name": "Position", "capability_type": "both", "data_type": "integer", "tuya_dp_id": 2},
        ],
        "qn": [  # Radiator Thermostat
            {"key": "switch", "display_name": "Power", "capability_type": "both", "data_type": "boolean", "tuya_dp_id": 1},
            {"key": "temp_set", "display_name": "Target Temperature", "capability_type": "both", "data_type": "integer", "tuya_dp_id": 2, "unit": "°C", "min_value": 5.0, "max_value": 35.0},
            {"key": "temp_current", "display_name": "Current Temperature", "capability_type": "sensor", "data_type": "integer", "tuya_dp_id": 3, "unit": "°C"},
            {"key": "mode", "display_name": "Mode", "capability_type": "both", "data_type": "string", "tuya_dp_id": 4},
        ],
    }

    return defaults.get(category, [
        # Generic fallback
        {"key": "switch", "display_name": "Switch", "capability_type": "both", "data_type": "boolean", "tuya_dp_id": 1},
    ])