"""
Network Interface Detection Module

This module detects all available network interfaces on the system,
including their IP addresses, gateways, MAC addresses, and connection status.
"""
import psutil
import netifaces
import socket
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Import requests for exception handling (imported lazily in test_internet_access)


def get_network_interfaces() -> List[Dict[str, str]]:
    """
    Detect all available network interfaces on the system.

    Returns:
        List of dictionaries containing interface information:
        - name: Interface name (e.g., 'Ethernet', 'Wi-Fi')
        - ip: IPv4 address
        - gateway: Default gateway (if available)
        - status: 'connected' or 'disconnected'
        - mac: MAC address (if available)

    Example:
        [
            {
                'name': 'Ethernet',
                'ip': '192.168.1.100',
                'gateway': '192.168.1.1',
                'status': 'connected',
                'mac': '00:11:22:33:44:55'
            },
            {
                'name': 'Wi-Fi 2',
                'ip': '192.168.1.101',
                'gateway': '192.168.1.1',
                'status': 'connected',
                'mac': '00:11:22:33:44:56'
            }
        ]
    """
    interfaces = []

    try:
        # Get all network interface addresses
        if_addrs = psutil.net_if_addrs()

        # Get interface statistics (for connection status)
        if_stats = psutil.net_if_stats()

        # Get default gateways
        gateways = netifaces.gateways()
        default_gateway = None
        if 'default' in gateways and netifaces.AF_INET in gateways['default']:
            default_gateway = gateways['default'][netifaces.AF_INET][0]

        # Process each interface
        for interface_name, addresses in if_addrs.items():
            interface_info = {
                'name': interface_name,
                'ip': '',
                'gateway': '',
                'status': 'disconnected',
                'mac': ''
            }

            # Extract IPv4 address and MAC address
            for addr in addresses:
                # Check if this is an IPv4 address (family = 2 on all platforms)
                if addr.family == socket.AF_INET:
                    # Check if it looks like an IP address (contains dots)
                    if '.' in addr.address:
                        interface_info['ip'] = addr.address
                    # Check if it looks like a MAC address (contains colons or hyphens)
                    elif ':' in addr.address or '-' in addr.address:
                        interface_info['mac'] = addr.address

            # Skip interfaces without IP address
            if not interface_info['ip']:
                continue

            # Get connection status
            if interface_name in if_stats:
                if if_stats[interface_name].isup:
                    interface_info['status'] = 'connected'

            # Try to get gateway for this specific interface
            # Note: netifaces doesn't easily map gateways to specific interfaces
            # So we use the default gateway for all connected interfaces
            if interface_info['status'] == 'connected' and default_gateway:
                interface_info['gateway'] = default_gateway

            interfaces.append(interface_info)

    except (OSError, psutil.Error) as e:
        logger.error("Error detecting network interfaces: %s", e)
        return []

    return interfaces


def get_interface_by_ip(ip_address: str) -> Optional[Dict[str, str]]:
    """
    Find a network interface by its IP address.

    Args:
        ip_address: The IP address to search for

    Returns:
        Interface information dictionary, or None if not found
    """
    interfaces = get_network_interfaces()
    for interface in interfaces:
        if interface['ip'] == ip_address:
            return interface
    return None


def get_connected_interfaces() -> List[Dict[str, str]]:
    """
    Get only the connected (active) network interfaces.

    Returns:
        List of connected interface dictionaries
    """
    all_interfaces = get_network_interfaces()
    return [iface for iface in all_interfaces if iface['status'] == 'connected']


def test_internet_access(source_ip: str, timeout: Optional[int] = None) -> bool:
    """
    Test if the given source IP has internet access.

    Args:
        source_ip: The source IP address to test
        timeout: Timeout in seconds (defaults to config.INTERNET_TEST_TIMEOUT)

    Returns:
        True if the interface has internet access, False otherwise
    """
    try:
        import config
        import requests.exceptions

        if timeout is None:
            timeout = config.INTERNET_TEST_TIMEOUT

        # Import here to avoid circular dependency
        from download_engine import DownloadEngine

        engine = DownloadEngine()
        session = engine.create_bound_session(source_ip)

        response = session.get(
            config.INTERNET_TEST_URL,
            timeout=timeout,
            verify=config.SSL_VERIFY
        )
        return response.status_code == 200
    except (OSError, requests.exceptions.RequestException):
        return False


def get_interfaces_with_internet() -> List[Dict[str, str]]:
    """
    Get only network interfaces that have actual internet access.

    Filters out virtual adapters (VMware, Hyper-V, etc.) and tests
    internet connectivity for each remaining interface.

    Returns:
        List of interface dictionaries with confirmed internet access
    """
    # Blacklist of virtual adapter name patterns
    VIRTUAL_PATTERNS = [
        'vEthernet', 'VMware', 'VMnet', 'VirtualBox',
        'Loopback', 'TAP', 'OpenVPN', 'Hyper-V',
        'Bluetooth', 'docker'
    ]

    # Get all connected interfaces
    all_interfaces = get_connected_interfaces()

    # Stage 1: Filter out virtual adapters and loopback
    physical_interfaces = []
    for iface in all_interfaces:
        # Skip if name matches virtual pattern
        if any(pattern.lower() in iface['name'].lower() for pattern in VIRTUAL_PATTERNS):
            continue
        # Skip loopback
        if iface['ip'].startswith('127.'):
            continue
        # Skip link-local addresses (169.254.x.x)
        if iface['ip'].startswith('169.254.'):
            continue
        physical_interfaces.append(iface)

    # Stage 2: Test internet connectivity
    interfaces_with_internet = []
    for iface in physical_interfaces:
        if test_internet_access(iface['ip']):
            interfaces_with_internet.append(iface)

    return interfaces_with_internet


def print_network_info():
    """
    Print all network interface information to console.
    Useful for debugging and testing.
    """
    interfaces = get_network_interfaces()

    print("=" * 70)
    print("Network Interfaces Detected:")
    print("=" * 70)

    if not interfaces:
        print("No network interfaces found.")
        return

    for i, iface in enumerate(interfaces, 1):
        print(f"\nInterface {i}:")
        print(f"  Name:    {iface['name']}")
        print(f"  IP:      {iface['ip']}")
        print(f"  Gateway: {iface['gateway'] if iface['gateway'] else 'N/A'}")
        print(f"  Status:  {iface['status']}")
        print(f"  MAC:     {iface['mac'] if iface['mac'] else 'N/A'}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Test the network detector
    print_network_info()
