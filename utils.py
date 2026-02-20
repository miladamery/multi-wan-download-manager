"""
Utility Functions for Multi-WAN Download Manager

This module provides common utility functions used across the application.
"""
from typing import List, Dict, Optional


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB", "500 KB")
    """
    if size_bytes == 0:
        return "Unknown"

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def format_speed(bytes_per_second: float) -> str:
    """
    Format download speed in human-readable format.

    Args:
        bytes_per_second: Speed in bytes per second

    Returns:
        Formatted speed string (e.g., "1.5 MB/s", "500 KB/s")
    """
    if bytes_per_second == 0:
        return "0 B/s"

    for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s']:
        if bytes_per_second < 1024.0:
            return f"{bytes_per_second:.2f} {unit}"
        bytes_per_second /= 1024.0
    return f"{bytes_per_second:.2f} PB/s"


def format_time(seconds: float) -> str:
    """
    Format seconds into HH:MM:SS string.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string (e.g., "01:23:45", "23:45")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def get_interface_name(interfaces: List[Dict], ip: str) -> Optional[str]:
    """
    Find interface name by IP address.

    Args:
        interfaces: List of interface dictionaries
        ip: IP address to search for

    Returns:
        Interface name if found, None otherwise
    """
    for iface in interfaces:
        if iface.get('ip') == ip:
            return iface.get('name')
    return None
