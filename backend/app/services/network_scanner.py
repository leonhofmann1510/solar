"""Network scanner for discovering Tuya devices on the local network."""
import asyncio
import logging
import socket
from typing import Optional

logger = logging.getLogger(__name__)


async def scan_for_tuya_device(ip: str, port: int = 6668, timeout: float = 0.2) -> bool:
    """Check if a Tuya device is reachable at the given IP address.
    
    Args:
        ip: IP address to check
        port: Port to check (default 6668 for Tuya)
        timeout: Connection timeout in seconds
        
    Returns:
        True if device responds on the port, False otherwise
    """
    try:
        # Use asyncio's wait_for with socket connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False


async def scan_network_for_tuya_devices(
    base_ip: str = "192.168.178",
    start: int = 1,
    end: int = 254,
    port: int = 6668,
    timeout: float = 0.2,
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
    current_ip: Optional[str] = None,
    base_ip: str = "192.168.178"
) -> Optional[str]:
    """Try to find a Tuya device's current IP address.
    
    First tries the current known IP, then scans the network if not found.
    
    Args:
        device_id: Tuya device ID
        current_ip: Currently known IP address (if any)
        base_ip: Base IP to scan if device not at current_ip
        
    Returns:
        IP address where device was found, or None
    """
    # First, try current IP if we have one
    if current_ip:
        logger.debug(f"Checking if Tuya device {device_id} is still at {current_ip}")
        if await scan_for_tuya_device(current_ip):
            logger.debug(f"Device {device_id} confirmed at {current_ip}")
            return current_ip
        logger.warning(f"Device {device_id} not found at previous IP {current_ip}")
    
    # If not found at current IP, scan the network
    logger.info(f"Scanning network to locate Tuya device {device_id}")
    found_ips = await scan_network_for_tuya_devices(base_ip=base_ip)
    
    # We can't identify which specific device without connecting and reading the ID
    # So we return the list of found IPs - caller will need to try each one
    # For now, just return None if we can't verify current IP
    # Full implementation would require connecting to each found IP and reading device ID
    
    if not found_ips:
        logger.warning(f"No Tuya devices found on network during scan for {device_id}")
        return None
    
    logger.info(f"Found {len(found_ips)} Tuya device(s) on network, but cannot auto-match to {device_id}")
    logger.info(f"Manual verification needed. Found devices at: {', '.join(found_ips)}")
    return None
