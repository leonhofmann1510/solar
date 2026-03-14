import asyncio
import logging

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models import Device, DeviceCapability

logger = logging.getLogger(__name__)

MDNS_SERVICES = [
    "_http._tcp.local.",
    "_hap._tcp.local.",
    "_shelly._tcp.local.",
    "_esphome._tcp.local.",
]


async def scan_mdns_devices() -> int:
    """Run an mDNS scan and store discovered devices.

    Returns the count of newly discovered devices.
    """
    try:
        from zeroconf import ServiceBrowser, Zeroconf
    except ImportError:
        logger.error("zeroconf not installed — cannot scan mDNS devices")
        return 0

    discovered: list[dict] = []

    class Listener:
        def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            info = zc.get_service_info(type_, name)
            if not info:
                return
            addresses = info.parsed_addresses()
            ip = addresses[0] if addresses else None
            server = info.server or name
            discovered.append({
                "name": server.rstrip("."),
                "ip": ip,
                "type": type_,
                "raw_id": name,
                "properties": {
                    k.decode() if isinstance(k, bytes) else k:
                    v.decode() if isinstance(v, bytes) else str(v)
                    for k, v in (info.properties or {}).items()
                },
            })

        def remove_service(self, zc, type_, name):
            pass

        def update_service(self, zc, type_, name):
            pass

    loop = asyncio.get_event_loop()
    zc = await loop.run_in_executor(None, Zeroconf)

    listener = Listener()
    browsers = []
    for svc in MDNS_SERVICES:
        browsers.append(ServiceBrowser(zc, svc, listener))

    await asyncio.sleep(settings.mdns_scan_timeout_seconds)

    await loop.run_in_executor(None, zc.close)

    count = 0
    async with async_session() as session:
        for dev in discovered:
            raw_id = dev["raw_id"]
            result = await session.execute(
                select(Device).where(Device.raw_id == raw_id, Device.protocol == "mdns")
            )
            if result.scalar_one_or_none():
                continue

            device = Device(
                name=dev["name"],
                protocol="mdns",
                raw_id=raw_id,
                ip_address=dev["ip"],
                meta=dev,
                confirmed=False,
            )
            session.add(device)
            await session.flush()

            cap = DeviceCapability(
                device_id=device.id,
                key="switch",
                display_name="Switch",
                capability_type="both",
                data_type="boolean",
            )
            session.add(cap)

            count += 1
            logger.info("mDNS discovered: %s (%s)", dev["name"], raw_id)

        await session.commit()

    return count
