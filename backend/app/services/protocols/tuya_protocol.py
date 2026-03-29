import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import decrypt_value
from app.models import Device, DeviceCapability

logger = logging.getLogger(__name__)


def _get_tuya_device(device: Device):
    """Create a tinytuya device instance for the given device."""
    try:
        import tinytuya
    except ImportError:
        logger.error("tinytuya not installed — cannot control Tuya devices")
        return None

    if not device.ip_address or not device.tuya_local_key:
        logger.warning("Tuya device %d missing ip_address or local_key", device.id)
        return None

    local_key = decrypt_value(device.tuya_local_key)
    if not local_key:
        logger.error("Tuya device %d: failed to decrypt local_key", device.id)
        return None

    # Use actual version from scan results (stored in meta during network scan).
    # Devices running firmware 3.4+ will silently ignore a 3.3 command.
    version = float((device.meta or {}).get("tuya_version", "3.3"))

    d = tinytuya.OutletDevice(
        dev_id=device.raw_id,
        address=device.ip_address,
        local_key=local_key,
        version=version,
    )
    d.set_socketPersistent(False)
    return d


async def read_state(device: Device) -> dict[str, dict]:
    """Read all datapoints from a Tuya device. Returns {dp_id: value}."""
    d = _get_tuya_device(device)
    if not d:
        return {}

    try:
        status = await asyncio.to_thread(d.status)
    except Exception:
        logger.exception("Failed to read Tuya device %d (%s)", device.id, device.raw_id)
        return {}

    if "dps" not in status:
        logger.warning("Tuya device %d returned no dps: %s", device.id, status)
        return {}

    return status["dps"]


async def set_dp(
    session: AsyncSession,
    device: Device,
    capability_key: str,
    value: bool | int | float | str,
) -> bool:
    """Set a datapoint on a Tuya device. Returns True on success."""
    result = await session.execute(
        select(DeviceCapability).where(
            DeviceCapability.device_id == device.id,
            DeviceCapability.key == capability_key,
        )
    )
    cap = result.scalar_one_or_none()
    if not cap or cap.tuya_dp_id is None:
        logger.warning("No Tuya DP ID for device=%d key=%s", device.id, capability_key)
        return False

    # Coerce value to the type Tuya expects — type mismatches are silently ignored by the device
    if cap.data_type == "boolean":
        if isinstance(value, str):
            value = value.lower() in ("true", "1", "on", "yes")
        else:
            value = bool(value)
    elif cap.data_type in ("integer", "float"):
        value = float(value) if cap.data_type == "float" else int(value)

    d = _get_tuya_device(device)
    if not d:
        return False

    try:
        logger.info(
            "Tuya set_value device=%d raw_id=%s dp=%d value=%r version=%s",
            device.id, device.raw_id, cap.tuya_dp_id, value,
            (device.meta or {}).get("tuya_version", "3.3"),
        )
        response = await asyncio.to_thread(d.set_value, cap.tuya_dp_id, value)
        logger.info("Tuya set_value response for device=%d: %s", device.id, response)
        if response and isinstance(response, dict) and response.get("Error"):
            logger.error(
                "Tuya device %d returned error: %s", device.id, response["Error"]
            )
            return False
        return True
    except Exception:
        logger.exception(
            "Failed to set Tuya DP %d=%s on device %d",
            cap.tuya_dp_id, value, device.id,
        )
        return False
