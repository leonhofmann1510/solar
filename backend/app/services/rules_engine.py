import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DeviceState, Rule, RuleEvent
from app.services.device_handler import execute_action
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


def _evaluate_inverter_condition(condition: dict, readings: dict[str, float | None]) -> bool:
    """Evaluate a single inverter condition against the readings dict."""
    field = condition["field"]
    value = readings.get(field)
    if value is None:
        return False
    op_fn = OPERATORS.get(condition["operator"])
    if op_fn is None:
        logger.warning("Unknown operator: %s", condition["operator"])
        return False
    return op_fn(value, condition["value"])


def _evaluate_device_condition(condition: dict, device_states: dict[int, dict[str, Any]]) -> bool:
    """Evaluate a device condition against the device states dict."""
    device_id = condition.get("device_id")
    capability_key = condition.get("capability_key")
    if device_id is None or not capability_key:
        return False

    device_values = device_states.get(device_id, {})
    current_value = device_values.get(capability_key)
    if current_value is None:
        return False

    op_fn = OPERATORS.get(condition["operator"])
    if op_fn is None:
        logger.warning("Unknown operator: %s", condition["operator"])
        return False

    return op_fn(current_value, condition["value"])


def _evaluate_condition(
    condition: dict,
    readings: dict[str, float | None],
    device_states: dict[int, dict[str, Any]],
) -> bool:
    """Evaluate a single condition — dispatches to inverter or device logic."""
    source = condition.get("source", "inverter")
    if source == "device":
        return _evaluate_device_condition(condition, device_states)
    return _evaluate_inverter_condition(condition, readings)


def evaluate_conditions(
    rule: Rule,
    readings: dict[str, float | None],
    device_states: dict[int, dict[str, Any]],
) -> bool:
    """Evaluate all conditions for a rule using AND/OR logic."""
    results = [_evaluate_condition(c, readings, device_states) for c in rule.conditions]
    if rule.condition_logic == "OR":
        return any(results)
    return all(results)


def _reverse_payload(payload: str) -> str:
    return _REVERSE_MAP.get(payload.lower(), payload)


async def _load_device_states(session: AsyncSession) -> dict[int, dict[str, Any]]:
    """Load all device states into a nested dict: {device_id: {capability_key: value}}."""
    result = await session.execute(select(DeviceState))
    states: dict[int, dict[str, Any]] = {}
    for s in result.scalars().all():
        if s.device_id not in states:
            states[s.device_id] = {}
        if s.value_boolean is not None:
            states[s.device_id][s.capability_key] = s.value_boolean
        elif s.value_numeric is not None:
            states[s.device_id][s.capability_key] = s.value_numeric
        elif s.value_string is not None:
            states[s.device_id][s.capability_key] = s.value_string
    return states


async def _fire_action(
    action: dict,
    session: AsyncSession,
    mqtt_client: MQTTClient,
    rule_id: int,
    action_label: str,
) -> None:
    """Fire a single action — supports both MQTT-topic and device-based actions."""
    action_type = action.get("type", "mqtt")  # Default to mqtt for backwards compatibility

    # Device-based action (works with any protocol: Tuya, MQTT devices, etc.)
    if action_type == "device" or ("device_id" in action and "capability_key" in action):
        success = await execute_action(
            session, mqtt_client,
            action["device_id"], action["capability_key"], action["value"],
        )
        if success:
            session.add(RuleEvent(
                rule_id=rule_id,
                action_taken=action_label,
                mqtt_topic=f"device:{action['device_id']}:{action['capability_key']}",
                mqtt_payload=str(action["value"]),
            ))

    # Raw MQTT action
    elif action_type == "mqtt" or "mqtt_topic" in action:
        topic = action.get("mqtt_topic", "")
        if not topic:
            return
        payload = action.get("mqtt_payload", "")
        if action_label == "reverse":
            payload = _reverse_payload(payload)
        mqtt_client.publish(topic, payload)
        session.add(RuleEvent(
            rule_id=rule_id,
            action_taken=action_label,
            mqtt_topic=topic,
            mqtt_payload=payload,
        ))


async def run_engine(
    session: AsyncSession,
    mqtt_client: MQTTClient,
    latest_readings: list[InverterData],
) -> None:
    """Evaluate all enabled rules against the latest inverter readings and device states."""
    # Build a flat readings dict (use inv1 values, inv2 as fallback)
    readings: dict[str, float | None] = {}
    for data in latest_readings:
        for key, val in asdict(data).items():
            if key in ("inverter_id", "timestamp"):
                continue
            # First inverter's values take priority
            if key not in readings or readings[key] is None:
                readings[key] = val

    device_states = await _load_device_states(session)

    result = await session.execute(select(Rule).where(Rule.enabled.is_(True)))
    rules = result.scalars().all()

    now = datetime.now(UTC)

    for rule in rules:
        matched = evaluate_conditions(rule, readings, device_states)

        if matched and rule.state == "idle":
            # Check cooldown
            if rule.cooldown_seconds and rule.last_fired_at:
                elapsed = (now - rule.last_fired_at).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    continue

            # Fire actions
            for action in rule.actions:
                await _fire_action(action, session, mqtt_client, rule.id, "fire")

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
                    if "device_id" in action:
                        # Reverse boolean for device actions
                        reversed_value = not action["value"] if isinstance(action.get("value"), bool) else action.get("value")
                        reversed_action = {**action, "value": reversed_value}
                        await _fire_action(reversed_action, session, mqtt_client, rule.id, "reverse")
                    else:
                        await _fire_action(action, session, mqtt_client, rule.id, "reverse")
            elif rule.on_clear_action == "custom" and rule.on_clear_payload:
                for action in rule.actions:
                    if "mqtt_topic" in action:
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
