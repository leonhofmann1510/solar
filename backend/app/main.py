import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI
from sqlalchemy import select

from app.config import settings
from app.database import async_session, engine
from app.models import Base, Rule
from app.routers import readings, rules
from app.services.mqtt import MQTTClient
from app.services.poller import poll_loop

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")

    await _seed_rules_from_file()

    mqtt_client = MQTTClient()
    mqtt_client.connect()

    poller_task = asyncio.create_task(poll_loop(mqtt_client))
    logger.info("Poller started (interval=%ds)", settings.poll_interval_seconds)

    yield

    # Shutdown
    poller_task.cancel()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass
    mqtt_client.disconnect()
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(title="Solar", version="1.0.0", lifespan=lifespan)
app.include_router(readings.router)
app.include_router(rules.router)
