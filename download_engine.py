"""
Download Engine with IP Binding Support

This module handles HTTP/HTTPS downloads bound to specific source IPs,
allowing downloads through multiple network interfaces simultaneously.
"""
import os
import time
import logging
import requests
from requests_toolbelt.adapters.source import SourceAddressAdapter
from typing import Callable, Optional, Dict, Any
from urllib.parse import unquote
import socket

import config
from utils import format_time

logger = logging.getLogger(__name__)

# Disable SSL warnings if verification is disabled
if not config.SSL_VERIFY:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class DownloadEngine:
    """Engine for downloading files with source IP binding."""

    def __init__(self):
        self.session = None
        self.source_ip = None
        self.is_running = False
        self.is_paused = False
        self.downloaded_bytes = 0
        self.total_size = 0
        self.start_time = None
        self.last_progress_time = None
        self.last_progress_bytes = 0

    def create_bound_session(self, source_ip: str) -> requests.Session:
        """
        Create a requests Session bound to a specific source IP address.

        Args:
            source_ip: The source IP address to bind to

        Returns:
            Configured requests Session object
        """
        session = requests.Session()

        # Create adapter that binds to the specific source IP
        # The port is set to 0, which means the OS will choose an available port
        adapter = SourceAddressAdapter((source_ip, 0))

        # Mount the adapter for both http and https
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        return session

    def get_download_info(self, url: str, source_ip: str) -> Dict[str, Any]:
        """
        Get information about a download without actually downloading it.

        Args:
            url: The URL to check
            source_ip: The source IP to bind to

        Returns:
            Dictionary containing:
                - file_size: Total size in bytes
                - filename: Suggested filename
                - supports_resume: Whether server supports Range requests
                - content_type: MIME type
        """
        try:
            session = self.create_bound_session(source_ip)

            # Use HEAD request to get metadata without downloading
            response = session.head(
                url,
                timeout=config.CONNECTION_TIMEOUT,
                allow_redirects=True,
                verify=config.SSL_VERIFY
            )
            response.raise_for_status()

            # Get file size from Content-Length header
            file_size = int(response.headers.get('content-length', 0))

            # Get filename from Content-Disposition header
            filename = self._extract_filename(url, response.headers)

            # Check if server supports Range requests (for resume functionality)
            supports_resume = 'accept-ranges' in response.headers or \
                            response.headers.get('accept-ranges') == 'bytes'

            content_type = response.headers.get('content-type', 'application/octet-stream')

            return {
                'file_size': file_size,
                'filename': filename,
                'supports_resume': supports_resume,
                'content_type': content_type,
                'success': True
            }

        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _extract_filename(self, url: str, headers: dict) -> str:
        """
        Extract filename from URL or Content-Disposition header.

        Args:
            url: The download URL
            headers: Response headers

        Returns:
            Extracted filename
        """
        # Try Content-Disposition header first
        content_disp = headers.get('content-disposition', '')
        if content_disp:
            try:
                # Parse filename from Content-Disposition
                if 'filename=' in content_disp:
                    filename = content_disp.split('filename=')[-1].strip('"\'')
                    return unquote(filename)
            except (ValueError, KeyError):
                pass

        # Fallback to URL path
        try:
            path = url.split('?')[0]  # Remove query parameters
            filename = path.split('/')[-1]
            if filename:
                return unquote(filename)
        except ValueError:
            pass

        # Default fallback
        return 'downloaded_file'

    def download_file(
        self,
        url: str,
        source_ip: str,
        dest_path: str,
        progress_callback: Callable[[int, int, int, float, str], None],
        speed_limit_mbps: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Download a file bound to a specific source IP.

        Args:
            url: The URL to download from
            source_ip: The source IP to bind to
            dest_path: Full path where file should be saved
            progress_callback: Function called with progress updates:
                (percentage, downloaded_bytes, total_bytes, speed_mbps, eta)
            speed_limit_mbps: Optional speed limit in MB/s (0 = unlimited)

        Returns:
            Dictionary with download result
        """
        self.source_ip = source_ip
        self.session = self.create_bound_session(source_ip)
        self.is_running = True
        self.is_paused = False
        self.start_time = time.time()
        self.last_progress_time = self.start_time
        self.last_progress_bytes = 0

        resume_position = 0

        # Check if we're resuming a partial download
        if os.path.exists(dest_path):
            resume_position = os.path.getsize(dest_path)
            self.downloaded_bytes = resume_position

        headers = {}
        if resume_position > 0:
            headers['Range'] = f'bytes={resume_position}-'

        try:
            # Start the download with streaming
            response = self.session.get(
                url,
                headers=headers,
                stream=True,
                timeout=(config.CONNECTION_TIMEOUT, config.READ_TIMEOUT),
                allow_redirects=True,
                verify=config.SSL_VERIFY
            )
            response.raise_for_status()

            # Get total file size
            if resume_position > 0 and response.status_code == 206:  # Partial Content
                # Server accepted range request
                content_range = response.headers.get('content-range', '')
                if content_range:
                    total_size = int(content_range.split('/')[-1])
                else:
                    total_size = int(response.headers.get('content-length', 0)) + resume_position
            else:
                # Server doesn't support resume or new download
                total_size = int(response.headers.get('content-length', 0))
                resume_position = 0  # Start from beginning

            self.total_size = total_size

            # Determine write mode (append for resume, write for new)
            mode = 'ab' if resume_position > 0 else 'wb'

            with open(dest_path, mode) as f:
                for chunk in response.iter_content(chunk_size=config.DEFAULT_CHUNK_SIZE):
                    # Check if we should stop
                    if not self.is_running:
                        f.close()
                        return {
                            'success': False,
                            'cancelled': True,
                            'downloaded': self.downloaded_bytes
                        }

                    # Handle pause
                    while self.is_paused:
                        time.sleep(config.THREAD_SLEEP_INTERVAL)
                        if not self.is_running:
                            f.close()
                            return {
                                'success': False,
                                'cancelled': True,
                                'downloaded': self.downloaded_bytes
                            }

                    if chunk:  # Filter out keep-alive chunks
                        f.write(chunk)
                        self.downloaded_bytes += len(chunk)

                        # Apply speed limiting if set
                        if speed_limit_mbps and speed_limit_mbps > 0:
                            self._apply_speed_limit(speed_limit_mbps, len(chunk))

                        # Update progress
                        self._update_progress(progress_callback)

            # Download completed successfully
            return {
                'success': True,
                'filepath': dest_path,
                'file_size': self.downloaded_bytes
            }

        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'downloaded': self.downloaded_bytes
            }
        except IOError as e:
            return {
                'success': False,
                'error': f"File I/O error: {str(e)}",
                'downloaded': self.downloaded_bytes
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'downloaded': self.downloaded_bytes
            }
        finally:
            self.is_running = False
            if self.session:
                self.session.close()

    def _apply_speed_limit(self, speed_limit_mbps: float, chunk_size: int):
        """
        Apply speed limiting by calculating delay based on desired speed.

        Args:
            speed_limit_mbps: Speed limit in MB/s
            chunk_size: Size of the chunk just downloaded
        """
        # Convert MB/s to bytes/second
        target_bytes_per_second = speed_limit_mbps * 1024 * 1024

        # Calculate expected time for this chunk
        expected_time = chunk_size / target_bytes_per_second

        # Calculate actual time taken
        # We'll use a simple approach: sleep to match the target rate
        time.sleep(expected_time)

    def _update_progress(self, progress_callback):
        """
        Calculate and report progress.

        Args:
            progress_callback: Callback function for progress updates
        """
        current_time = time.time()

        # Calculate percentage
        if self.total_size > 0:
            percentage = int((self.downloaded_bytes / self.total_size) * 100)
        else:
            percentage = 0

        # Calculate download speed
        time_elapsed = current_time - self.last_progress_time
        if time_elapsed >= 1.0:  # Update speed calculation every second
            bytes_downloaded = self.downloaded_bytes - self.last_progress_bytes
            speed_mbps = (bytes_downloaded / time_elapsed) / (1024 * 1024)

            self.last_progress_time = current_time
            self.last_progress_bytes = self.downloaded_bytes

            # Calculate ETA
            if speed_mbps > 0:
                remaining_bytes = self.total_size - self.downloaded_bytes
                eta_seconds = remaining_bytes / (speed_mbps * 1024 * 1024)
                eta = format_time(eta_seconds)
            else:
                eta = "Calculating..."

            # Call the progress callback
            progress_callback(percentage, self.downloaded_bytes, self.total_size, speed_mbps, eta)

    def pause(self):
        """Pause the download."""
        self.is_paused = True

    def resume(self):
        """Resume the download."""
        self.is_paused = False

    def cancel(self):
        """Cancel the download."""
        self.is_running = False


def verify_source_ip(source_ip: str) -> bool:
    """
    Verify that requests are actually coming from the specified source IP.

    Args:
        source_ip: The expected source IP address

    Returns:
        True if the IP matches, False otherwise
    """
    try:
        session = requests.Session()
        adapter = SourceAddressAdapter((source_ip, 0))
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        response = session.get(config.IP_CHECK_URL, timeout=10)
        response.raise_for_status()

        data = response.json()
        returned_ip = data.get('origin', '').split(',')[0].strip()

        return returned_ip == source_ip

    except (requests.exceptions.RequestException, ValueError, KeyError) as e:
        logger.error("Error verifying source IP: %s", e)
        return False


if __name__ == "__main__":
    # Test the download engine
    import sys
    from network_detector import get_connected_interfaces

    print("Testing Download Engine")
    print("=" * 70)

    # Get available network interfaces
    interfaces = get_connected_interfaces()

    if not interfaces:
        print("No connected network interfaces found!")
        sys.exit(1)

    print("\nAvailable Network Interfaces:")
    for i, iface in enumerate(interfaces, 1):
        print(f"{i}. {iface['name']} - {iface['ip']}")

    # Test IP verification
    print("\n" + "=" * 70)
    print("Testing Source IP Verification:")
    print("=" * 70)

    for iface in interfaces:
        print(f"\nVerifying {iface['name']} ({iface['ip']}):")
        result = verify_source_ip(iface['ip'])
        print(f"  Result: {'PASS' if result else 'FAIL'}")
        if result:
            print(f"  Requests correctly bound to {iface['ip']}")
        else:
            print(f"  WARNING: Requests NOT using {iface['ip']}")
