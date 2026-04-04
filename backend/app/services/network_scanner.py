"""Network scanner for discovering Tuya devices on the local network."""
import asyncio
import logging
import socket
from typing import Optional

logger = logging.getLogger(__name__)


async def scan_for_tuya_device(ip: str, port: int = 6668, timeout: float = 0.5) -> bool:
    """Check if a Tuya device is reachable at the given IP address.

    Args:
        ip: IP address to check
        port: Port to check (default 6668 for Tuya)
        timeout: Connection timeout in seconds

    Returns:
        True if device responds on the port, False otherwise
    """
    def _check():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0

    try:
        return await asyncio.to_thread(_check)
    except Exception:
        return False


async def scan_network_for_tuya_devices(
    base_ip: str = "192.168.178",
    start: int = 1,
    end: int = 254,
    port: int = 6668,
    timeout: float = 0.5,
    max_concurrent: int = 50
) -> list[str]:
    """Scan a network range for Tuya devices.
    
    Args:
        base_ip: Base IP address (e.g., "192.168.178")
        start: Start of IP range (default 1)
        end: End of IP range (default 254)
        port: Port to scan (default 6668)
        timeout: Connection timeout per IP
        max_concurrent: Maximum concurrent scans
        
    Returns:
        List of IP addresses where Tuya devices were found
    """
    logger.info(f"Scanning {base_ip}.{start}-{end} for Tuya devices on port {port}...")
    
    found_devices = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def check_ip(ip: str):
        async with semaphore:
            if await scan_for_tuya_device(ip, port, timeout):
                logger.info(f"Found Tuya device at {ip}")
                found_devices.append(ip)
    
    # Create tasks for all IPs in range
    tasks = [check_ip(f"{base_ip}.{i}") for i in range(start, end + 1)]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info(f"Network scan complete. Found {len(found_devices)} Tuya device(s)")
    return found_devices


async def find_tuya_device_by_id(
    device_id: str,
    local_key: str,
    current_ip: Optional[str] = None,
    base_ip: str = "192.168.178",
    version: float = 3.3
) -> Optional[str]:
    """Try to find a Tuya device's current IP address.
    
    First tries the current known IP, then scans the network and tests each IP.
    
    Args:
        device_id: Tuya device ID (raw_id)
        local_key: Decrypted local key for the device
        current_ip: Currently known IP address (if any)
        base_ip: Base IP to scan if device not at current_ip
        version: Tuya protocol version (default 3.3)
        
    Returns:
        IP address where device was found, or None
    """
    import tinytuya
    
    # First, try current IP if we have one
    if current_ip:
        logger.debug(f"Checking if Tuya device {device_id} is still at {current_ip}")
        if await scan_for_tuya_device(current_ip):
            # Port is open, try to connect and verify it's the right device
            try:
                d = tinytuya.OutletDevice(
                    dev_id=device_id,
                    address=current_ip,
                    local_key=local_key,
                    version=version,
                )
                d.set_socketPersistent(False)
                status = await asyncio.to_thread(d.status)
                if status and "dps" in status:
                    logger.debug(f"Device {device_id} confirmed at {current_ip}")
                    return current_ip
            except Exception:
                pass
        logger.warning(f"Device {device_id} not found at previous IP {current_ip}")
    
    # If not found at current IP, scan the network
    logger.info(f"Scanning network to locate Tuya device {device_id}")
    found_ips = await scan_network_for_tuya_devices(base_ip=base_ip)
    
    if not found_ips:
        logger.warning(f"No Tuya devices found on network during scan for {device_id}")
        return None
    
    # Try to connect to each found IP and check if it's our device
    logger.info(f"Testing {len(found_ips)} found IP(s) to identify device {device_id}")
    
    for ip in found_ips:
        try:
            d = tinytuya.OutletDevice(
                dev_id=device_id,
                address=ip,
                local_key=local_key,
                version=version,
            )
            d.set_socketPersistent(False)
            status = await asyncio.to_thread(d.status)
            
            if status and "dps" in status and status.get("dps"):
                # Device responded with valid data - this is our device!
                logger.info(f"✅ Found device {device_id} at NEW IP: {ip}")
                return ip
        except Exception as e:
            # This IP wasn't the right device, continue
            logger.debug(f"IP {ip} is not device {device_id}: {e}")
            continue
    
    logger.warning(f"Device {device_id} not found among {len(found_ips)} scanned Tuya device(s)")
    return None
