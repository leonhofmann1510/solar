import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device
from app.services.mqtt import MQTTClient
from app.services.protocols import mqtt_protocol, tuya_protocol

logger = logging.getLogger(__name__)


async def execute_action(
    session: AsyncSession,
    mqtt_client: MQTTClient,
    device_id: int,
    capability_key: str,
    value: bool | int | float | str,
) -> bool:
    """Route an action to the correct protocol handler. Returns True on success."""
    result = await session.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if not device:
        logger.warning("Device %d not found", device_id)
        return False

    if not device.enabled:
        logger.warning("Device %d is disabled, skipping action", device_id)
        return False

    if device.protocol == "mqtt":
        return await mqtt_protocol.publish_command(
            mqtt_client, session, device_id, capability_key, value,
        )

    if device.protocol == "tuya":
        return await tuya_protocol.set_dp(session, device, capability_key, value)

    logger.warning("Unsupported protocol %s for device %d", device.protocol, device_id)
    return False
