import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import Device, DeviceCapability, DeviceState
from app.state import AppState, TopicMapEntry

logger = logging.getLogger(__name__)


async def build_topic_map(state: AppState) -> None:
    """Load all MQTT state topics from confirmed devices into the app state."""
    state.topic_map.clear()

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
            state.topic_map[cap.mqtt_state_topic] = TopicMapEntry(
                device_id=cap.device_id,
                capability_key=cap.key,
                data_type=cap.data_type,
            )

    logger.info("MQTT topic map built: %d topics", len(state.topic_map))


def subscribe_state_topics(state: AppState) -> None:
    """Subscribe to all known MQTT state topics."""
    if not state.mqtt_client:
        return
    for topic in state.topic_map:
        state.mqtt_client.subscribe(topic)
    logger.info("Subscribed to %d MQTT state topics", len(state.topic_map))


async def handle_state_message(topic: str, payload: str, state: AppState) -> None:
    """Called when an MQTT message arrives on a subscribed state topic."""
    entry = state.topic_map.get(topic)
    if not entry:
        return

    value_boolean = None
    value_numeric = None
    value_string = None

    if entry.data_type == "boolean":
        value_boolean = payload.lower() in ("on", "1", "true")
    elif entry.data_type in ("integer", "float"):
        try:
            value_numeric = float(payload)
        except ValueError:
            logger.warning("Cannot parse numeric value from %s: %s", topic, payload)
            return
    else:
        value_string = payload

    async with async_session() as session:
        stmt = pg_insert(DeviceState).values(
            device_id=entry.device_id,
            capability_key=entry.capability_key,
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

    if state.ws_manager:
        value = value_boolean if value_boolean is not None else (value_numeric if value_numeric is not None else value_string)
        await state.ws_manager.broadcast({
            "event": "device_state_changed",
            "device_id": entry.device_id,
            "capability_key": entry.capability_key,
            "value": value,
        })


async def publish_command(
    mqtt_client: object,
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
