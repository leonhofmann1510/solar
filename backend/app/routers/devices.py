import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_session
from app.models import Device, DeviceCapability, DeviceState
from app.schemas import (
    DeviceActionRequest,
    DeviceCapabilityOut,
    DeviceCapabilitySchema,
    DeviceConfirm,
    DeviceOut,
    DeviceStateOut,
    DeviceUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["devices"])

# These are injected by main.py at startup
_mqtt_client = None
_ws_manager = None


def set_dependencies(mqtt_client, ws_manager) -> None:
    global _mqtt_client, _ws_manager
    _mqtt_client = mqtt_client
    _ws_manager = ws_manager


# --- Discovery ---


@router.post("/discover/tuya")
async def discover_tuya():
    from app.services.discovery.tuya_discovery import fetch_tuya_devices

    count = await fetch_tuya_devices(
        settings.tuya_api_key, settings.tuya_api_secret, settings.tuya_api_region,
    )
    return {"discovered": count}


@router.post("/scan/tuya")
async def scan_tuya_network(session: AsyncSession = Depends(get_session)):
    """Scan the local network for Tuya devices and update their IP addresses."""
    try:
        import tinytuya
    except ImportError:
        raise HTTPException(500, "tinytuya not installed")

    import asyncio

    # Run the blocking network scan in a thread
    loop = asyncio.get_event_loop()
    try:
        scan_results = await loop.run_in_executor(None, lambda: tinytuya.deviceScan(verbose=False))
    except Exception as e:
        logger.exception("Tuya network scan failed")
        raise HTTPException(500, f"Scan failed: {e}")

    if not scan_results:
        return {"updated": 0, "scanned": 0}

    # Build a map of device_id -> {ip, version} from scan results
    id_to_scan: dict[str, dict] = {}
    for ip, info in scan_results.items():
        gwId = info.get("gwId", "")
        if gwId:
            id_to_scan[gwId] = {"ip": ip, "version": str(info.get("version", "3.3"))}

    # Update matching devices in the database
    result = await session.execute(
        select(Device).where(Device.protocol == "tuya")
    )
    devices = result.scalars().all()

    updated = 0
    for device in devices:
        scan_info = id_to_scan.get(device.raw_id)
        if not scan_info:
            continue
        new_ip = scan_info["ip"]
        version = scan_info["version"]
        if new_ip != device.ip_address or (device.meta or {}).get("tuya_version") != version:
            device.ip_address = new_ip
            device.meta = {**(device.meta or {}), "tuya_version": version}
            updated += 1
            logger.info(
                "Updated Tuya device %s (%s) IP=%s version=%s",
                device.name, device.raw_id, new_ip, version,
            )

    await session.commit()
    return {"updated": updated, "scanned": len(id_to_scan)}


@router.post("/discover/mdns")
async def discover_mdns():
    from app.services.discovery.mdns_discovery import scan_mdns_devices

    count = await scan_mdns_devices()
    return {"discovered": count}


@router.get("/pending", response_model=list[DeviceOut])
async def list_pending(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Device)
        .where(Device.confirmed.is_(False))
        .options(selectinload(Device.capabilities), selectinload(Device.states))
    )
    return result.scalars().all()


# --- Device management ---


@router.get("", response_model=list[DeviceOut])
async def list_devices(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Device)
        .where(Device.confirmed.is_(True))
        .options(selectinload(Device.capabilities), selectinload(Device.states))
    )
    return result.scalars().all()


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(device_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Device)
        .where(Device.id == device_id)
        .options(selectinload(Device.capabilities), selectinload(Device.states))
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(404, "Device not found")
    return device


@router.post("/{device_id}/confirm", response_model=DeviceOut)
async def confirm_device(
    device_id: int,
    body: DeviceConfirm,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Device)
        .where(Device.id == device_id)
        .options(selectinload(Device.capabilities), selectinload(Device.states))
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(404, "Device not found")

    device.confirmed = True
    device.name = body.name
    device.room = body.room
    await session.commit()
    await session.refresh(device)

    # Rebuild MQTT topic map after confirming an MQTT device
    if device.protocol == "mqtt" and _mqtt_client:
        from app.services.protocols.mqtt_protocol import build_topic_map, subscribe_state_topics
        await build_topic_map()
        subscribe_state_topics(_mqtt_client)

    return device


@router.put("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: int,
    body: DeviceUpdate,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Device)
        .where(Device.id == device_id)
        .options(selectinload(Device.capabilities), selectinload(Device.states))
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(404, "Device not found")

    if body.name is not None:
        device.name = body.name
    if body.room is not None:
        device.room = body.room
    if body.enabled is not None:
        device.enabled = body.enabled

    await session.commit()
    await session.refresh(device)
    return device


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(404, "Device not found")

    await session.delete(device)
    await session.commit()


# --- Capabilities ---


@router.get("/{device_id}/capabilities", response_model=list[DeviceCapabilityOut])
async def list_capabilities(device_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DeviceCapability).where(DeviceCapability.device_id == device_id)
    )
    return result.scalars().all()


@router.post("/{device_id}/capabilities", response_model=DeviceCapabilityOut, status_code=201)
async def add_capability(
    device_id: int,
    body: DeviceCapabilitySchema,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Device).where(Device.id == device_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Device not found")

    cap = DeviceCapability(device_id=device_id, **body.model_dump())
    session.add(cap)
    await session.commit()
    await session.refresh(cap)
    return cap


@router.put("/{device_id}/capabilities/{key}", response_model=DeviceCapabilityOut)
async def update_capability(
    device_id: int,
    key: str,
    body: DeviceCapabilitySchema,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DeviceCapability).where(
            DeviceCapability.device_id == device_id,
            DeviceCapability.key == key,
        )
    )
    cap = result.scalar_one_or_none()
    if not cap:
        raise HTTPException(404, "Capability not found")

    for field, value in body.model_dump().items():
        setattr(cap, field, value)

    await session.commit()
    await session.refresh(cap)
    return cap


@router.delete("/{device_id}/capabilities/{key}", status_code=204)
async def delete_capability(
    device_id: int,
    key: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DeviceCapability).where(
            DeviceCapability.device_id == device_id,
            DeviceCapability.key == key,
        )
    )
    cap = result.scalar_one_or_none()
    if not cap:
        raise HTTPException(404, "Capability not found")

    await session.delete(cap)
    await session.commit()


# --- State ---


@router.get("/{device_id}/state", response_model=list[DeviceStateOut])
async def get_device_state(device_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DeviceState).where(DeviceState.device_id == device_id)
    )
    return result.scalars().all()


@router.post("/{device_id}/read")
async def read_device_state(device_id: int, session: AsyncSession = Depends(get_session)):
    """Poll the device locally and return raw DPS. Useful for debugging DP mappings."""
    result = await session.execute(
        select(Device).where(Device.id == device_id)
        .options(selectinload(Device.capabilities))
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(404, "Device not found")
    if device.protocol != "tuya":
        raise HTTPException(400, "Only supported for Tuya devices")

    from app.services.protocols.tuya_protocol import read_state
    dps = await read_state(device)
    if not dps:
        raise HTTPException(502, "No response from device — check IP and local key")

    return {"device_id": device_id, "raw_dps": dps}


# --- Action (test endpoint) ---


@router.post("/{device_id}/action")
async def device_action(
    device_id: int,
    body: DeviceActionRequest,
    session: AsyncSession = Depends(get_session),
):
    if not _mqtt_client:
        raise HTTPException(503, "MQTT client not available")

    from app.services.device_handler import execute_action

    success = await execute_action(
        session, _mqtt_client, device_id, body.capability_key, body.value,
    )
    if not success:
        raise HTTPException(400, "Action failed — check device protocol, local key, or capability config")

    return {"ok": True, "device_id": device_id, "capability_key": body.capability_key, "value": body.value}
