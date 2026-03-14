import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import Device, DeviceCapability, DeviceState
from app.services.mqtt import MQTTClient

logger = logging.getLogger(__name__)

# topic -> (device_id, capability_key, data_type)
_topic_map: dict[str, tuple[int, str, str]] = {}


async def build_topic_map() -> dict[str, tuple[int, str, str]]:
    """Load all MQTT state topics from confirmed devices into a lookup dict."""
    global _topic_map
    _topic_map = {}

    async with async_session() as session:
        result = await session.execute(
            select(DeviceCapability)
            .join(Device)
            .where(
                Device.confirmed.is_(True),
                Device.protocol == "mqtt",
                DeviceCapability.mqtt_state_topic.isnot(None),
            )
        )
        for cap in result.scalars().all():
            _topic_map[cap.mqtt_state_topic] = (cap.device_id, cap.key, cap.data_type)

    logger.info("MQTT topic map built: %d topics", len(_topic_map))
    return _topic_map


def subscribe_state_topics(mqtt_client: MQTTClient) -> None:
    """Subscribe to all known MQTT state topics."""
    for topic in _topic_map:
        mqtt_client.subscribe(topic)
    logger.info("Subscribed to %d MQTT state topics", len(_topic_map))


async def handle_state_message(topic: str, payload: str, ws_manager: object | None = None) -> None:
    """Called when an MQTT message arrives on a subscribed state topic."""
    entry = _topic_map.get(topic)
    if not entry:
        return

    device_id, capability_key, data_type = entry

    value_boolean = None
    value_numeric = None
    value_string = None

    if data_type == "boolean":
        value_boolean = payload.lower() in ("on", "1", "true")
    elif data_type in ("integer", "float"):
        try:
            value_numeric = float(payload)
        except ValueError:
            logger.warning("Cannot parse numeric value from %s: %s", topic, payload)
            return
    else:
        value_string = payload

    async with async_session() as session:
        stmt = pg_insert(DeviceState).values(
            device_id=device_id,
            capability_key=capability_key,
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
        await session.commit()

    if ws_manager:
        value = value_boolean if value_boolean is not None else (value_numeric if value_numeric is not None else value_string)
        await ws_manager.broadcast({
            "event": "device_state_changed",
            "device_id": device_id,
            "capability_key": capability_key,
            "value": value,
        })


async def publish_command(
    mqtt_client: MQTTClient,
    session: AsyncSession,
    device_id: int,
    capability_key: str,
    value: bool | int | float | str,
) -> bool:
    """Publish a command to a device via MQTT. Returns True on success."""
    result = await session.execute(
        select(DeviceCapability).where(
            DeviceCapability.device_id == device_id,
            DeviceCapability.key == capability_key,
        )
    )
    cap = result.scalar_one_or_none()
    if not cap or not cap.mqtt_command_topic:
        logger.warning("No MQTT command topic for device=%d key=%s", device_id, capability_key)
        return False

    if isinstance(value, bool):
        payload = "on" if value else "off"
    else:
        payload = str(value)

    mqtt_client.publish(cap.mqtt_command_topic, payload)
    return True
