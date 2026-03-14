import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models import Device, DeviceCapability

logger = logging.getLogger(__name__)

DISCOVERY_TOPICS = [
    "shellies/announce",
    "tasmota/discovery/+/config",
    settings.zigbee2mqtt_bridge_topic,
]

# Known Shelly model -> capability definitions
SHELLY_CAPABILITIES: dict[str, list[dict]] = {
    "shellyplug-s": [
        {"key": "switch", "display_name": "Switch", "capability_type": "both", "data_type": "boolean",
         "topic_suffix_cmd": "/relay/0/command", "topic_suffix_state": "/relay/0"},
        {"key": "power_w", "display_name": "Power (W)", "capability_type": "state", "data_type": "float",
         "unit": "W", "topic_suffix_state": "/relay/0/power"},
        {"key": "energy_wm", "display_name": "Energy (Wm)", "capability_type": "state", "data_type": "float",
         "unit": "Wm", "topic_suffix_state": "/relay/0/energy"},
    ],
    "shellyplug": [
        {"key": "switch", "display_name": "Switch", "capability_type": "both", "data_type": "boolean",
         "topic_suffix_cmd": "/relay/0/command", "topic_suffix_state": "/relay/0"},
    ],
    "shelly1": [
        {"key": "switch", "display_name": "Switch", "capability_type": "both", "data_type": "boolean",
         "topic_suffix_cmd": "/relay/0/command", "topic_suffix_state": "/relay/0"},
    ],
    "shelly1pm": [
        {"key": "switch", "display_name": "Switch", "capability_type": "both", "data_type": "boolean",
         "topic_suffix_cmd": "/relay/0/command", "topic_suffix_state": "/relay/0"},
        {"key": "power_w", "display_name": "Power (W)", "capability_type": "state", "data_type": "float",
         "unit": "W", "topic_suffix_state": "/relay/0/power"},
    ],
    "shelly25": [
        {"key": "switch_0", "display_name": "Switch 0", "capability_type": "both", "data_type": "boolean",
         "topic_suffix_cmd": "/relay/0/command", "topic_suffix_state": "/relay/0"},
        {"key": "switch_1", "display_name": "Switch 1", "capability_type": "both", "data_type": "boolean",
         "topic_suffix_cmd": "/relay/1/command", "topic_suffix_state": "/relay/1"},
    ],
}


async def _upsert_device(
    session: AsyncSession,
    raw_id: str,
    protocol: str,
    name: str,
    ip_address: str | None,
    mqtt_base_topic: str | None,
    meta: dict | None,
    capabilities: list[dict] | None,
) -> Device | None:
    """Upsert a discovered device. Returns the Device if newly created."""
    result = await session.execute(
        select(Device).where(Device.raw_id == raw_id, Device.protocol == protocol)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.last_seen_at = datetime.now(UTC)
        if ip_address:
            existing.ip_address = ip_address
        await session.commit()
        return None

    device = Device(
        name=name,
        protocol=protocol,
        raw_id=raw_id,
        ip_address=ip_address,
        mqtt_base_topic=mqtt_base_topic,
        meta=meta,
        confirmed=False,
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    session.add(device)
    await session.flush()

    if capabilities:
        for cap_def in capabilities:
            base = mqtt_base_topic or ""
            cap = DeviceCapability(
                device_id=device.id,
                key=cap_def["key"],
                display_name=cap_def["display_name"],
                capability_type=cap_def["capability_type"],
                data_type=cap_def["data_type"],
                unit=cap_def.get("unit"),
                min_value=cap_def.get("min_value"),
                max_value=cap_def.get("max_value"),
                mqtt_command_topic=f"{base}{cap_def['topic_suffix_cmd']}" if cap_def.get("topic_suffix_cmd") else None,
                mqtt_state_topic=f"{base}{cap_def['topic_suffix_state']}" if cap_def.get("topic_suffix_state") else None,
            )
            session.add(cap)

    await session.commit()
    logger.info("Discovered new device: %s (%s)", name, raw_id)
    return device


async def handle_shelly_announce(payload_str: str, ws_manager=None) -> None:
    """Handle a message on shellies/announce."""
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON on shellies/announce: %s", payload_str)
        return

    raw_id = payload.get("id", "")
    ip = payload.get("ip")
    model = payload.get("model", "")
    base_topic = f"shellies/{raw_id}"

    caps = SHELLY_CAPABILITIES.get(model)

    async with async_session() as session:
        device = await _upsert_device(
            session,
            raw_id=raw_id,
            protocol="mqtt",
            name=raw_id,
            ip_address=ip,
            mqtt_base_topic=base_topic,
            meta=payload,
            capabilities=caps,
        )

    if device and ws_manager:
        await ws_manager.broadcast({
            "event": "device_discovered",
            "device": {"id": device.id, "raw_id": raw_id, "protocol": "mqtt"},
        })


async def handle_tasmota_discovery(topic: str, payload_str: str, ws_manager=None) -> None:
    """Handle a message on tasmota/discovery/+/config."""
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        return

    raw_id = payload.get("mac", payload.get("hn", ""))
    if not raw_id:
        return

    ip = payload.get("ip")
    name = payload.get("dn", raw_id)
    base_topic = payload.get("t", f"tasmota/{raw_id}")

    caps = [
        {"key": "switch", "display_name": "Switch", "capability_type": "both",
         "data_type": "boolean", "topic_suffix_cmd": "/cmnd/POWER",
         "topic_suffix_state": "/stat/POWER"},
    ]

    async with async_session() as session:
        device = await _upsert_device(
            session,
            raw_id=raw_id,
            protocol="mqtt",
            name=name,
            ip_address=ip,
            mqtt_base_topic=base_topic,
            meta=payload,
            capabilities=caps,
        )

    if device and ws_manager:
        await ws_manager.broadcast({
            "event": "device_discovered",
            "device": {"id": device.id, "raw_id": raw_id, "protocol": "mqtt"},
        })


def _z2m_expose_to_capability(expose: dict, base_topic: str, friendly_name: str) -> dict | None:
    """Convert a Z2M expose entry to a capability dict."""
    feature_type = expose.get("type")
    name = expose.get("name") or expose.get("property", "")

    if not name:
        if feature_type == "light" and "features" in expose:
            return None
        return None

    data_type = "string"
    cap_type = "state"
    unit = expose.get("unit")
    min_val = expose.get("value_min")
    max_val = expose.get("value_max")

    if feature_type == "binary":
        data_type = "boolean"
        access = expose.get("access", 1)
        cap_type = "both" if access & 2 else "state"
    elif feature_type == "numeric":
        data_type = "float"
        access = expose.get("access", 1)
        cap_type = "both" if access & 2 else "state"
    elif feature_type == "enum":
        data_type = "string"
        access = expose.get("access", 1)
        cap_type = "both" if access & 2 else "state"

    state_topic = f"{base_topic}/{friendly_name}"
    cmd_topic = f"{base_topic}/{friendly_name}/set" if cap_type in ("both", "action") else None

    return {
        "key": name,
        "display_name": name.replace("_", " ").title(),
        "capability_type": cap_type,
        "data_type": data_type,
        "unit": unit,
        "min_value": min_val,
        "max_value": max_val,
        "topic_suffix_cmd": None,
        "topic_suffix_state": None,
        "mqtt_command_topic": cmd_topic,
        "mqtt_state_topic": state_topic,
    }


async def handle_z2m_devices(payload_str: str, ws_manager=None) -> None:
    """Handle the zigbee2mqtt/bridge/devices message — full device list."""
    try:
        devices_list = json.loads(payload_str)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON on Z2M bridge/devices")
        return

    if not isinstance(devices_list, list):
        return

    z2m_base = settings.zigbee2mqtt_bridge_topic.rsplit("/", 2)[0]

    for dev in devices_list:
        if dev.get("type") == "Coordinator":
            continue

        ieee = dev.get("ieee_address", "")
        friendly_name = dev.get("friendly_name", ieee)
        model = dev.get("definition", {}).get("model", "")

        caps = []
        definition = dev.get("definition") or {}
        exposes = definition.get("exposes", [])

        for expose in exposes:
            if "features" in expose:
                for feature in expose["features"]:
                    cap = _z2m_expose_to_capability(feature, z2m_base, friendly_name)
                    if cap:
                        caps.append(cap)
            else:
                cap = _z2m_expose_to_capability(expose, z2m_base, friendly_name)
                if cap:
                    caps.append(cap)

        async with async_session() as session:
            result = await session.execute(
                select(Device).where(Device.raw_id == ieee, Device.protocol == "mqtt")
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.last_seen_at = datetime.now(UTC)
                await session.commit()
                continue

            device = Device(
                name=friendly_name,
                protocol="mqtt",
                raw_id=ieee,
                mqtt_base_topic=f"{z2m_base}/{friendly_name}",
                meta=dev,
                confirmed=False,
                first_seen_at=datetime.now(UTC),
                last_seen_at=datetime.now(UTC),
            )
            session.add(device)
            await session.flush()

            for cap_def in caps:
                cap = DeviceCapability(
                    device_id=device.id,
                    key=cap_def["key"],
                    display_name=cap_def["display_name"],
                    capability_type=cap_def["capability_type"],
                    data_type=cap_def["data_type"],
                    unit=cap_def.get("unit"),
                    min_value=cap_def.get("min_value"),
                    max_value=cap_def.get("max_value"),
                    mqtt_command_topic=cap_def.get("mqtt_command_topic"),
                    mqtt_state_topic=cap_def.get("mqtt_state_topic"),
                )
                session.add(cap)

            await session.commit()

        if ws_manager:
            await ws_manager.broadcast({
                "event": "device_discovered",
                "device": {"id": device.id, "raw_id": ieee, "protocol": "mqtt"},
            })

        logger.info("Z2M discovered: %s (%s, model=%s)", friendly_name, ieee, model)
