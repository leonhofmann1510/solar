import asyncio
import logging
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

import yaml
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import async_session, engine
from app.models import Rule
from app.routers import devices, meter, readings, rules
from app.routers.ws import manager as ws_manager
from app.routers.ws import router as ws_router
from app.services.device_poller import poll_device_states
from app.services.discovery.mqtt_discovery import (
    DISCOVERY_TOPICS,
    handle_shelly_announce,
    handle_tasmota_discovery,
    handle_z2m_devices,
)
from app.services.mqtt import MQTTClient
from app.services.poller import poll_loop
from app.services.protocols.mqtt_protocol import build_topic_map, handle_state_message, subscribe_state_topics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


async def _seed_rules_from_file() -> None:
    """Import rules from YAML file if they don't already exist in the DB."""
    path = Path(settings.rules_file_path)
    if not path.exists():
        logger.info("No rules file at %s, skipping seed", path)
        return

    with open(path) as f:
        data = yaml.safe_load(f)

    if not data or "rules" not in data:
        return

    async with async_session() as session:
        for entry in data["rules"]:
            result = await session.execute(
                select(Rule).where(Rule.name == entry["name"])
            )
            if result.scalar_one_or_none():
                continue

            rule = Rule(
                name=entry["name"],
                enabled=entry.get("enabled", True),
                condition_logic=entry.get("condition_logic", "AND"),
                conditions=entry["conditions"],
                actions=entry["actions"],
                on_clear_action=entry.get("on_clear_action", "none"),
                on_clear_payload=entry.get("on_clear_payload"),
                cooldown_seconds=entry.get("cooldown_seconds", 0),
            )
            session.add(rule)
            logger.info("Seeded rule: %s", rule.name)

        await session.commit()


def _make_mqtt_message_handler(mqtt_client: MQTTClient):
    """Create an MQTT message callback that routes to discovery and state handlers."""

    def on_message(topic: str, payload: str) -> None:
        loop = asyncio.get_event_loop()

        if topic == "shellies/announce":
            asyncio.run_coroutine_threadsafe(
                handle_shelly_announce(payload, ws_manager), loop,
            )
        elif topic.startswith("tasmota/discovery/") and topic.endswith("/config"):
            asyncio.run_coroutine_threadsafe(
                handle_tasmota_discovery(topic, payload, ws_manager), loop,
            )
        elif topic == settings.zigbee2mqtt_bridge_topic:
            asyncio.run_coroutine_threadsafe(
                handle_z2m_devices(payload, ws_manager), loop,
            )
        else:
            asyncio.run_coroutine_threadsafe(
                handle_state_message(topic, payload, ws_manager), loop,
            )

    return on_message


async def _run_migrations() -> None:
    """Run Alembic migrations to head on startup (idempotent, safe to run every time)."""
    cfg = AlembicConfig("alembic.ini")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, partial(alembic_command.upgrade, cfg, "head"))
    logger.info("Database migrations applied")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await _run_migrations()

    await _seed_rules_from_file()

    mqtt_client = MQTTClient()
    mqtt_client.connect()

    # Subscribe to device discovery topics
    for topic in DISCOVERY_TOPICS:
        mqtt_client.subscribe(topic)
    logger.info("Subscribed to discovery topics: %s", DISCOVERY_TOPICS)

    # Build topic map for confirmed MQTT devices and subscribe
    await build_topic_map()
    subscribe_state_topics(mqtt_client)

    # Set up the message callback that routes to discovery + state handlers
    mqtt_client.set_message_callback(_make_mqtt_message_handler(mqtt_client))

    # Inject dependencies into the devices router
    devices.set_dependencies(mqtt_client, ws_manager)

    poller_task = asyncio.create_task(poll_loop(mqtt_client, ws_manager))
    logger.info("Poller started (interval=%ds)", settings.poll_interval_seconds)

    device_poller_task = asyncio.create_task(poll_device_states(ws_manager))
    logger.info("Device state poller started")

    yield

    # Shutdown
    poller_task.cancel()
    device_poller_task.cancel()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass
    try:
        await device_poller_task
    except asyncio.CancelledError:
        pass
    mqtt_client.disconnect()
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(title="Solar", version="1.0.0", lifespan=lifespan)

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(readings.router)
app.include_router(rules.router)
app.include_router(devices.router)
app.include_router(meter.router)
app.include_router(ws_router)
