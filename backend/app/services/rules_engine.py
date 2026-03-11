import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rule, RuleEvent
from app.services.modbus import InverterData
from app.services.mqtt import MQTTClient

logger = logging.getLogger(__name__)

OPERATORS: dict[str, Any] = {
    "gt": lambda a, b: a > b,
    "lt": lambda a, b: a < b,
    "gte": lambda a, b: a >= b,
    "lte": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
    "neq": lambda a, b: a != b,
}

# Payload inversion for the "reverse" on_clear_action
_REVERSE_MAP = {"on": "off", "off": "on", "1": "0", "0": "1"}


def _evaluate_condition(condition: dict, readings: dict[str, float | None]) -> bool:
    """Evaluate a single condition against the readings dict."""
    field = condition["field"]
    value = readings.get(field)
    if value is None:
        return False
    op_fn = OPERATORS.get(condition["operator"])
    if op_fn is None:
        logger.warning("Unknown operator: %s", condition["operator"])
        return False
    return op_fn(value, condition["value"])


def evaluate_conditions(rule: Rule, readings: dict[str, float | None]) -> bool:
    """Evaluate all conditions for a rule using AND/OR logic."""
    results = [_evaluate_condition(c, readings) for c in rule.conditions]
    if rule.condition_logic == "OR":
        return any(results)
    return all(results)


def _reverse_payload(payload: str) -> str:
    return _REVERSE_MAP.get(payload.lower(), payload)


async def run_engine(
    session: AsyncSession,
    mqtt_client: MQTTClient,
    latest_readings: list[InverterData],
) -> None:
    """Evaluate all enabled rules against the latest inverter readings."""
    # Build a flat readings dict (use inv1 values, inv2 as fallback)
    readings: dict[str, float | None] = {}
    for data in latest_readings:
        for key, val in asdict(data).items():
            if key in ("inverter_id", "timestamp"):
                continue
            # First inverter's values take priority
            if key not in readings or readings[key] is None:
                readings[key] = val

    result = await session.execute(select(Rule).where(Rule.enabled.is_(True)))
    rules = result.scalars().all()

    now = datetime.now(UTC)

    for rule in rules:
        matched = evaluate_conditions(rule, readings)

        if matched and rule.state == "idle":
            # Check cooldown
            if rule.cooldown_seconds and rule.last_fired_at:
                elapsed = (now - rule.last_fired_at).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    continue

            # Fire actions
            for action in rule.actions:
                mqtt_client.publish(action["mqtt_topic"], action["mqtt_payload"])
                session.add(RuleEvent(
                    rule_id=rule.id,
                    action_taken="fire",
                    mqtt_topic=action["mqtt_topic"],
                    mqtt_payload=action["mqtt_payload"],
                ))

            await session.execute(
                update(Rule)
                .where(Rule.id == rule.id)
                .values(state="active", last_fired_at=now)
            )
            logger.info("Rule fired: %s", rule.name)

        elif not matched and rule.state == "active":
            # Handle clear action
            if rule.on_clear_action == "reverse":
                for action in rule.actions:
                    reversed_payload = _reverse_payload(action["mqtt_payload"])
                    mqtt_client.publish(action["mqtt_topic"], reversed_payload)
                    session.add(RuleEvent(
                        rule_id=rule.id,
                        action_taken="reverse",
                        mqtt_topic=action["mqtt_topic"],
                        mqtt_payload=reversed_payload,
                    ))
            elif rule.on_clear_action == "custom" and rule.on_clear_payload:
                for action in rule.actions:
                    mqtt_client.publish(action["mqtt_topic"], rule.on_clear_payload)
                    session.add(RuleEvent(
                        rule_id=rule.id,
                        action_taken="clear_custom",
                        mqtt_topic=action["mqtt_topic"],
                        mqtt_payload=rule.on_clear_payload,
                    ))

            await session.execute(
                update(Rule).where(Rule.id == rule.id).values(state="idle")
            )
            logger.info("Rule cleared: %s", rule.name)

    await session.commit()
