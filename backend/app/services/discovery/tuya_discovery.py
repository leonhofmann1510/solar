import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models import Device, DeviceCapability

logger = logging.getLogger(__name__)

# HA's registered client_id and schema (public, MIT-licensed, allowlisted by Tuya)
TUYA_CLIENT_ID = "HA_3y9q4ak7g4ephrvke"
TUYA_SCHEMA = "haauthorize"

# In-memory store for active QR login sessions
_active_sessions: dict[str, dict] = {}


async def start_qr_login(user_code: str) -> dict:
    """Start a Tuya QR login session.

    Generates a QR token that the user scans with the Smart Life app.
    Returns { session_id, qr_url } where qr_url is the string to encode
    as a QR image in the frontend.
    """
    from tuya_sharing import LoginControl

    session_id = str(uuid.uuid4())
    login_control = LoginControl()

    response = await asyncio.to_thread(
        login_control.qr_code,
        TUYA_CLIENT_ID,
        TUYA_SCHEMA,
        user_code,
    )

    if not response.get("success"):
        logger.error("Failed to generate Tuya QR code: %s", response)
        raise ValueError(
            f"Tuya QR code generation failed: {response.get('msg', 'unknown error')}"
        )

    qr_token = response["result"]["qrcode"]
    qr_url = f"tuyaSmart--qrLogin?token={qr_token}"

    _active_sessions[session_id] = {
        "login_control": login_control,
        "qr_token": qr_token,
        "user_code": user_code,
        "status": "pending",
        "devices_found": 0,
        "created_at": datetime.utcnow(),
    }

    logger.info("Tuya QR login session started: %s", session_id)
    return {"session_id": session_id, "qr_url": qr_url}


async def poll_login_status(session_id: str) -> dict:
    """Poll whether the user has scanned the QR code and confirmed login.

    Returns { status: "pending" | "success" | "failed", devices_found: int }
    """
    session = _active_sessions.get(session_id)
    if not session:
        return {"status": "failed", "devices_found": 0}

    # Already resolved — return result and clean up
    if session["status"] in ("success", "failed"):
        result = {"status": session["status"], "devices_found": session["devices_found"]}
        _active_sessions.pop(session_id, None)
        return result

    # Still processing (fetch + scan in progress) — tell the frontend to keep polling
    if session["status"] == "processing":
        return {"status": "pending", "devices_found": 0}

    # Timeout after 5 minutes
    if datetime.utcnow() - session["created_at"] > timedelta(minutes=5):
        _active_sessions.pop(session_id, None)
        return {"status": "failed", "devices_found": 0}

    login_control = session["login_control"]

    try:
        success, info = await asyncio.to_thread(
            login_control.login_result,
            session["qr_token"],
            TUYA_CLIENT_ID,
            session["user_code"],
        )
    except Exception:
        logger.exception("Tuya login_result call failed for session %s", session_id)
        _active_sessions.pop(session_id, None)
        return {"status": "failed", "devices_found": 0}

    if not success:
        return {"status": "pending", "devices_found": 0}

    # Login confirmed — mark as processing and start the fetch+scan in the background.
    # We do NOT await it here: the fetch + LAN scan takes 10-20s and holding the HTTP
    # connection that long causes Axios timeouts on the frontend. Subsequent polls will
    # find the session in "processing" state and return "pending" until the task finishes.
    session["status"] = "processing"
    logger.info("Tuya QR login confirmed for session %s — starting background fetch", session_id)
    asyncio.create_task(_run_background_fetch(session_id, session["user_code"], info))
    return {"status": "pending", "devices_found": 0}


async def _run_background_fetch(session_id: str, user_code: str, login_info: dict) -> None:
    """Background task: fetch devices from Tuya cloud and run LAN IP scan.

    Updates the session status when done so the next poll picks up the result.
    """
    try:
        count = await _fetch_and_save_devices(user_code, login_info)
        if session_id in _active_sessions:
            _active_sessions[session_id]["status"] = "success"
            _active_sessions[session_id]["devices_found"] = count
        logger.info("Background fetch complete for session %s: %d device(s)", session_id, count)
    except Exception:
        logger.exception("Background fetch failed for session %s", session_id)
        if session_id in _active_sessions:
            _active_sessions[session_id]["status"] = "failed"


async def _fetch_and_save_devices(user_code: str, login_info: dict) -> int:
    """Create a Manager with the login token, fetch all devices, and upsert into DB.

    login_info is the dict returned by LoginControl.login_result(). It contains:
      - endpoint, terminal_id  (where the Manager must connect)
      - t, uid, expire_time, access_token, refresh_token  (the auth token)
    """
    from tuya_sharing import Manager, SharingTokenListener

    class _TokenListener(SharingTokenListener):
        def update_token(self, token_info):
            pass  # One-time key fetch — no need to persist the refreshed token

    # The endpoint and terminal_id come from the login response, not from our config.
    # Using wrong values here causes the Manager to hit the wrong API host (404).
    endpoint = login_info.get("endpoint") or settings.tuya_endpoint
    terminal_id = login_info.get("terminal_id") or f"solarflow-{uuid.uuid4().hex[:8]}"

    logger.info("Creating Tuya Manager: endpoint=%s terminal_id=%s", endpoint, terminal_id)

    # Manager expects only the auth token fields, not the full login_info dict
    token_info = {
        "t": login_info.get("t"),
        "uid": login_info.get("uid"),
        "expire_time": login_info.get("expire_time"),
        "access_token": login_info.get("access_token"),
        "refresh_token": login_info.get("refresh_token"),
    }

    manager = await asyncio.to_thread(
        Manager,
        TUYA_CLIENT_ID,
        user_code,
        terminal_id,
        endpoint,
        token_info,
        _TokenListener(),
    )

    await asyncio.to_thread(manager.update_device_cache)

    device_map = manager.device_map
    if not device_map:
        logger.info("No devices returned from Tuya after QR login")
        return 0

    count = 0
    async with async_session() as db:
        for dev_id, dev in device_map.items():
            logger.info(
                "Tuya device from SDK: id=%s name=%s category=%s online=%s has_key=%s",
                dev.id, dev.name, dev.category, dev.online, bool(dev.local_key),
            )

            result = await db.execute(
                select(Device).where(Device.raw_id == dev.id, Device.protocol == "tuya")
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update key and IP in case they changed
                existing.tuya_local_key = dev.local_key
                existing.ip_address = dev.ip or existing.ip_address
                existing.last_seen_at = datetime.utcnow()

                # Refresh DP IDs using the SDK's local_strategy so that
                # capabilities created by old flows (without tuya_dp_id) now work
                local_strategy = getattr(dev, "local_strategy", {}) or {}
                if local_strategy:
                    code_to_dp_id = {
                        v.get("status_code"): dp_id
                        for dp_id, v in local_strategy.items()
                        if isinstance(v, dict) and v.get("status_code")
                    }
                    caps_result = await db.execute(
                        select(DeviceCapability).where(
                            DeviceCapability.device_id == existing.id
                        )
                    )
                    for cap in caps_result.scalars().all():
                        dp_id = code_to_dp_id.get(cap.key)
                        if dp_id is not None and cap.tuya_dp_id != dp_id:
                            cap.tuya_dp_id = dp_id

                count += 1
                logger.info("Updated existing Tuya device: %s (%s)", dev.name, dev.id)
                continue

            device = Device(
                name=dev.name,
                protocol="tuya",
                raw_id=dev.id,
                ip_address=dev.ip or None,
                tuya_local_key=dev.local_key,
                confirmed=False,
                meta={
                    "product_id": dev.product_id,
                    "product_name": getattr(dev, "product_name", ""),
                    "category": dev.category,
                    "online": dev.online,
                },
            )
            db.add(device)
            await db.flush()

            caps_added = await _populate_capabilities(db, device, dev)
            count += 1
            logger.info(
                "Tuya discovered: %s (%s) with %d capabilities",
                dev.name, dev.id, caps_added,
            )

        await db.commit()

    # Run a LAN scan immediately so devices have correct IPs before the user sees them
    await scan_and_update_ips()

    return count


async def scan_and_update_ips() -> dict:
    """Scan the LAN for Tuya devices and update their IP addresses in the DB.

    Uses tinytuya's broadcast listener. Returns { scanned, updated }.
    """
    try:
        import tinytuya
    except ImportError:
        logger.error("tinytuya not installed — cannot scan Tuya network")
        return {"scanned": 0, "updated": 0}

    logger.info("Starting Tuya LAN scan...")
    try:
        scan_results: dict = await asyncio.to_thread(
            lambda: tinytuya.deviceScan(verbose=False)
        )
    except Exception:
        logger.exception("Tuya LAN scan failed")
        return {"scanned": 0, "updated": 0}

    if not scan_results:
        logger.info("Tuya LAN scan found no devices")
        return {"scanned": 0, "updated": 0}

    # Build gwId -> {ip, version} from scan results
    id_to_scan: dict[str, dict] = {
        info["gwId"]: {"ip": ip, "version": str(info.get("version", "3.3"))}
        for ip, info in scan_results.items()
        if info.get("gwId")
    }

    updated = 0
    async with async_session() as db:
        result = await db.execute(select(Device).where(Device.protocol == "tuya"))
        devices = result.scalars().all()

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
                    "Updated Tuya device %s (%s) → IP=%s version=%s",
                    device.name, device.raw_id, new_ip, version,
                )

        await db.commit()

    logger.info("Tuya LAN scan complete: %d found, %d updated", len(id_to_scan), updated)
    return {"scanned": len(id_to_scan), "updated": updated}


async def _populate_capabilities(db, device: Device, sdk_device) -> int:
    """Populate device capabilities from the SDK's function and status_range dicts.

    The SDK provides:
      - sdk_device.function: dict[str, DeviceFunction] — writable DPs
      - sdk_device.status_range: dict[str, DeviceStatusRange] — readable DPs
      - sdk_device.local_strategy: dict[int, {"status_code": str, ...}] — maps
        integer DP IDs to their code names, used to populate tuya_dp_id.
    """
    functions = getattr(sdk_device, "function", {}) or {}
    status_range = getattr(sdk_device, "status_range", {}) or {}
    local_strategy = getattr(sdk_device, "local_strategy", {}) or {}

    # Build a reverse map: code_name -> integer dp_id
    code_to_dp_id: dict[str, int] = {
        v.get("status_code"): dp_id
        for dp_id, v in local_strategy.items()
        if isinstance(v, dict) and v.get("status_code")
    }

    # Merge function + status_range — function = writable, status_range = readable
    all_dps: dict[str, dict] = {}

    for code, sr in status_range.items():
        all_dps[code] = {
            "capability_type": "state",
            "data_type": _map_tuya_type(getattr(sr, "type", "String")),
            "values": getattr(sr, "values", ""),
        }

    for code, fn in functions.items():
        if code in all_dps:
            all_dps[code]["capability_type"] = "both"
        else:
            all_dps[code] = {
                "capability_type": "action",
                "data_type": _map_tuya_type(getattr(fn, "type", "String")),
                "values": getattr(fn, "values", ""),
            }
        all_dps[code]["display_name"] = (
            getattr(fn, "name", None) or getattr(fn, "desc", None)
        )

    # If the SDK gave us nothing, fall back to category defaults
    if not all_dps:
        category = getattr(sdk_device, "category", "")
        defaults = _get_default_capabilities(category)
        for cap_data in defaults:
            cap = DeviceCapability(device_id=device.id, **cap_data)
            db.add(cap)
        return len(defaults)

    count = 0
    for code, dp_info in all_dps.items():
        min_val, max_val, unit = _parse_value_range(
            dp_info["values"], dp_info["data_type"]
        )
        display_name = dp_info.get("display_name") or code.replace("_", " ").title()
        tuya_dp_id = code_to_dp_id.get(code)

        cap = DeviceCapability(
            device_id=device.id,
            key=code,
            display_name=display_name,
            capability_type=dp_info["capability_type"],
            data_type=dp_info["data_type"],
            min_value=min_val,
            max_value=max_val,
            unit=unit,
            tuya_dp_id=tuya_dp_id,
        )
        db.add(cap)
        count += 1

    return count


def _map_tuya_type(tuya_type: str) -> str:
    """Map Tuya SDK type names to our data_type values."""
    mapping = {
        "Boolean": "boolean",
        "Integer": "integer",
        "Enum": "string",
        "Json": "string",
        "String": "string",
        "Raw": "string",
    }
    return mapping.get(tuya_type, "string")


def _parse_value_range(
    values_str, data_type: str
) -> tuple[float | None, float | None, str | None]:
    """Extract min, max, unit from a Tuya values range string.

    For Integer types this is often JSON like:
    {"min":0,"max":255,"scale":0,"step":1,"unit":""}
    """
    if not values_str or data_type not in ("integer", "float"):
        return None, None, None

    try:
        vals = json.loads(values_str) if isinstance(values_str, str) else values_str
        if isinstance(vals, dict):
            min_val = vals.get("min")
            max_val = vals.get("max")
            unit = vals.get("unit") or None
            return (
                float(min_val) if min_val is not None else None,
                float(max_val) if max_val is not None else None,
                unit,
            )
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    return None, None, None


def _get_default_capabilities(category: str) -> list[dict]:
    """Get default capabilities for common Tuya device categories."""
    defaults = {
        "cz": [  # Smart Plug
            {"key": "switch_1", "display_name": "Switch", "capability_type": "both", "data_type": "boolean", "tuya_dp_id": 1},
        ],
        "kg": [  # Switch
            {"key": "switch_1", "display_name": "Switch 1", "capability_type": "both", "data_type": "boolean", "tuya_dp_id": 1},
        ],
        "dj": [  # Light
            {"key": "switch_led", "display_name": "Light", "capability_type": "both", "data_type": "boolean", "tuya_dp_id": 1},
            {"key": "work_mode", "display_name": "Brightness", "capability_type": "both", "data_type": "integer", "tuya_dp_id": 2},
        ],
        "dc": [  # Curtain
            {"key": "control", "display_name": "Control", "capability_type": "both", "data_type": "string", "tuya_dp_id": 1},
            {"key": "percent_control", "display_name": "Position", "capability_type": "both", "data_type": "integer", "tuya_dp_id": 2},
        ],
        "qn": [  # Radiator Thermostat
            {"key": "switch", "display_name": "Power", "capability_type": "both", "data_type": "boolean", "tuya_dp_id": 1},
            {"key": "temp_set", "display_name": "Target Temperature", "capability_type": "both", "data_type": "integer", "tuya_dp_id": 2, "unit": "\u00b0C", "min_value": 5.0, "max_value": 35.0},
            {"key": "temp_current", "display_name": "Current Temperature", "capability_type": "sensor", "data_type": "integer", "tuya_dp_id": 3, "unit": "\u00b0C"},
            {"key": "mode", "display_name": "Mode", "capability_type": "both", "data_type": "string", "tuya_dp_id": 4},
        ],
    }

    return defaults.get(category, [
        {"key": "switch", "display_name": "Switch", "capability_type": "both", "data_type": "boolean", "tuya_dp_id": 1},
    ])


async def cleanup_stale_sessions():
    """Remove sessions older than 5 minutes. Call from lifespan or poller."""
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    stale = [sid for sid, s in _active_sessions.items() if s["created_at"] < cutoff]
    for sid in stale:
        del _active_sessions[sid]
    if stale:
        logger.info("Cleaned up %d stale Tuya login session(s)", len(stale))
