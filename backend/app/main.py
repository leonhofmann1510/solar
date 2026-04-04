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
from sqlalchemy import select, text

from app.config import settings
from app.database import async_session, engine
from app.models import Rule
from app.routers import app_settings, devices, meter, readings, rules
from app.routers.ws import ConnectionManager
from app.routers.ws import router as ws_router
from app.services.device_poller import poll_device_states
from app.services.discovery.mqtt_discovery import (
    DISCOVERY_TOPICS,
    handle_shelly_announce,
    handle_tasmota_discovery,
    handle_z2m_devices,
)
from app.services.discovery.tuya_discovery import cleanup_stale_sessions, tuya_ip_refresh_loop
from app.services.mqtt import MQTTClient
from app.services.poller import poll_loop
from app.services.protocols.mqtt_protocol import build_topic_map, handle_state_message, subscribe_state_topics
from app.state import AppState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
for _noisy in ("tinytuya", "httpcore", "httpx"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
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


def _make_mqtt_message_handler(app_state: AppState):
    """Create an MQTT message callback that routes to discovery and state handlers."""

    def on_message(topic: str, payload: str) -> None:
        loop = asyncio.get_event_loop()

        if topic == "shellies/announce":
            asyncio.run_coroutine_threadsafe(
                handle_shelly_announce(payload, app_state.ws_manager), loop,
            )
        elif topic.startswith("tasmota/discovery/") and topic.endswith("/config"):
            asyncio.run_coroutine_threadsafe(
                handle_tasmota_discovery(topic, payload, app_state.ws_manager), loop,
            )
        elif topic == settings.zigbee2mqtt_bridge_topic:
            asyncio.run_coroutine_threadsafe(
                handle_z2m_devices(payload, app_state.ws_manager), loop,
            )
        else:
            asyncio.run_coroutine_threadsafe(
                handle_state_message(topic, payload, app_state), loop,
            )

    return on_message


async def _run_migrations() -> None:
    """Run Alembic migrations to head on startup."""
    cfg = AlembicConfig("alembic.ini")
    loop = asyncio.get_running_loop()

    async with engine.connect() as conn:
        has_alembic = await conn.scalar(text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version')"
        ))
        if not has_alembic:
            has_tables = await conn.scalar(text(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='inverter_readings')"
            ))
            if has_tables:
                logger.info("Untracked DB detected — stamping at revision 004 before upgrade")
                await loop.run_in_executor(None, partial(alembic_command.stamp, cfg, "004"))

    await loop.run_in_executor(None, partial(alembic_command.upgrade, cfg, "head"))
    logger.info("Database migrations applied")


async def _cleanup_loop() -> None:
    """Periodic cleanup of stale Tuya login sessions."""
    while True:
        try:
            await cleanup_stale_sessions()
        except Exception:
            logger.exception("Error in cleanup loop")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await _run_migrations()
    await _seed_rules_from_file()

    # Central app state
    app_state = AppState(
        mqtt_client=MQTTClient(),
        ws_manager=ConnectionManager(),
    )
    app.state.app_state = app_state

    app_state.mqtt_client.connect()

    # Subscribe to device discovery topics
    for topic in DISCOVERY_TOPICS:
        app_state.mqtt_client.subscribe(topic)
    logger.info("Subscribed to discovery topics: %s", DISCOVERY_TOPICS)

    # Build topic map for confirmed MQTT devices and subscribe
    await build_topic_map(app_state)
    subscribe_state_topics(app_state)

    # Set up the message callback that routes to discovery + state handlers
    app_state.mqtt_client.set_message_callback(_make_mqtt_message_handler(app_state))

    # Start background tasks
    tasks = [
        asyncio.create_task(poll_loop(app_state.mqtt_client, app_state.ws_manager)),
        asyncio.create_task(poll_device_states(app_state.ws_manager)),
        asyncio.create_task(_cleanup_loop()),
        asyncio.create_task(tuya_ip_refresh_loop()),
    ]
    logger.info("Background tasks started (poller=%ds interval)", settings.poll_interval_seconds)

    yield

    # Shutdown — cancel all background tasks
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    app_state.mqtt_client.disconnect()
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(title="Solar", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(readings.router)
app.include_router(rules.router)
app.include_router(devices.router)
app.include_router(meter.router)
app.include_router(app_settings.router)
app.include_router(ws_router)
