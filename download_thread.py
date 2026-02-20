"""
Download Thread Module

This module provides a QThread-based worker for handling downloads
in the background without blocking the GUI.
"""
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from typing import Optional
import os
import logging

from download_engine import DownloadEngine
from config import DEFAULT_DOWNLOAD_DIR

logger = logging.getLogger(__name__)


class DownloadSignals(QObject):
    """Signals for download status updates."""
    progress_updated = pyqtSignal(int, int, int, float, str)  # percentage, downloaded, total, speed, eta
    download_completed = pyqtSignal(str)  # filepath
    download_failed = pyqtSignal(str)  # error message
    download_paused = pyqtSignal()


class DownloadThread(QThread):
    """
    Worker thread for handling downloads in the background.

    This thread manages a single download operation and emits signals
    to update the GUI with progress, completion, and error status.
    """

    def __init__(
        self,
        url: str,
        source_ip: str,
        destination: Optional[str] = None,
        filename: Optional[str] = None,
        speed_limit: Optional[float] = None
    ):
        """
        Initialize the download thread.

        Args:
            url: The URL to download from
            source_ip: The source IP address to bind to
            destination: Directory to save the file (defaults to Downloads)
            filename: Custom filename (optional, auto-detected if None)
            speed_limit: Speed limit in MB/s (None for unlimited)
        """
        super().__init__()
        self.url = url
        self.source_ip = source_ip
        self.destination = destination or DEFAULT_DOWNLOAD_DIR
        self.filename = filename
        self.speed_limit = speed_limit

        self.engine = DownloadEngine()
        self.signals = DownloadSignals()

        # Connect engine to thread signals
        self.signals.progress_updated.connect(self._on_progress_updated)

        # Thread state
        self._is_paused = False
        self._is_cancelled = False

        # Download info
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.current_speed = 0.0
        self.current_eta = "00:00"
        self.filepath = ""

    def run(self):
        """Main download loop - runs in a separate thread."""
        try:
            # Ensure destination directory exists
            os.makedirs(self.destination, exist_ok=True)

            # Get download info first
            info = self.engine.get_download_info(self.url, self.source_ip)

            if not info.get('success'):
                self.signals.download_failed.emit(
                    info.get('error', 'Failed to get download info')
                )
                return

            # Determine filename
            if not self.filename:
                self.filename = info.get('filename', 'downloaded_file')

            # Build full file path
            self.filepath = os.path.join(self.destination, self.filename)

            # Get total size
            self.total_bytes = info.get('file_size', 0)

            # Start the download
            result = self.engine.download_file(
                url=self.url,
                source_ip=self.source_ip,
                dest_path=self.filepath,
                progress_callback=self._progress_callback,
                speed_limit_mbps=self.speed_limit
            )

            # Handle result
            if result.get('success'):
                self.signals.download_completed.emit(self.filepath)
            elif result.get('cancelled'):
                # Download was cancelled - partial file may exist
                pass
            else:
                error = result.get('error', 'Download failed')
                downloaded = result.get('downloaded', 0)
                if downloaded > 0:
                    error += f" ({downloaded} bytes downloaded)"
                self.signals.download_failed.emit(error)

        except (OSError, RuntimeError) as e:
            logger.error("Download error: %s", e)
            self.signals.download_failed.emit(f"Unexpected error: {str(e)}")

    def _progress_callback(self, percentage: int, downloaded: int, total: int, speed: float, eta: str):
        """
        Internal callback for progress updates from the engine.

        Args:
            percentage: Download progress percentage (0-100)
            downloaded: Bytes downloaded
            total: Total bytes to download
            speed: Current download speed in MB/s
            eta: Estimated time remaining
        """
        # Update instance variables
        self.downloaded_bytes = downloaded
        self.total_bytes = total
        self.current_speed = speed
        self.current_eta = eta

        # Emit signal to GUI
        self.signals.progress_updated.emit(percentage, downloaded, total, speed, eta)

    def _on_progress_updated(self, percentage: int, downloaded: int, total: int, speed: float, eta: str):
        """
        Slot for progress updates - can be used for additional processing.
        """
        pass  # Signal is already being emitted by _progress_callback

    def pause(self):
        """Pause the download."""
        self._is_paused = True
        if self.engine:
            self.engine.pause()

    def resume(self):
        """Resume a paused download."""
        self._is_paused = False
        if self.engine:
            self.engine.resume()

    def cancel(self):
        """Cancel the download and remove partial file."""
        self._is_cancelled = True
        if self.engine:
            self.engine.cancel()

        # Remove partial file if it exists
        if self.filepath and os.path.exists(self.filepath):
            try:
                os.remove(self.filepath)
            except OSError as e:
                logger.warning("Failed to remove partial file %s: %s", self.filepath, e)

    def get_progress_info(self) -> dict:
        """
        Get current download progress information.

        Returns:
            Dictionary containing:
                - percentage: Progress percentage (0-100)
                - downloaded: Bytes downloaded
                - total: Total bytes
                - speed: Current speed in MB/s
                - eta: Estimated time remaining
        """
        if self.total_bytes > 0:
            percentage = int((self.downloaded_bytes / self.total_bytes) * 100)
        else:
            percentage = 0

        return {
            'percentage': percentage,
            'downloaded': self.downloaded_bytes,
            'total': self.total_bytes,
            'speed': self.current_speed,
            'eta': self.current_eta,
            'filepath': self.filepath
        }

    def is_paused(self) -> bool:
        """Check if download is paused."""
        return self._is_paused

    def is_cancelled(self) -> bool:
        """Check if download is cancelled."""
        return self._is_cancelled


class DownloadManager:
    """
    Manages multiple download threads.

    This class handles the lifecycle of multiple concurrent downloads,
    including starting, pausing, resuming, and cancelling.
    """

    def __init__(self):
        self.active_downloads = {}  # Dictionary mapping ID to DownloadThread
        self.next_id = 1

    def add_download(
        self,
        url: str,
        source_ip: str,
        destination: Optional[str] = None,
        filename: Optional[str] = None,
        speed_limit: Optional[float] = None
    ) -> int:
        """
        Add a new download to the manager.

        Args:
            url: The URL to download
            source_ip: Source IP to bind to
            destination: Save directory
            filename: Custom filename
            speed_limit: Speed limit in MB/s

        Returns:
            Unique download ID
        """
        download_id = self.next_id
        self.next_id += 1

        thread = DownloadThread(
            url=url,
            source_ip=source_ip,
            destination=destination,
            filename=filename,
            speed_limit=speed_limit
        )

        self.active_downloads[download_id] = {
            'thread': thread,
            'url': url,
            'source_ip': source_ip,
            'status': 'queued'
        }

        return download_id

    def start_download(self, download_id: int):
        """Start a specific download."""
        if download_id in self.active_downloads:
            download = self.active_downloads[download_id]
            if download['status'] == 'queued' or download['status'] == 'paused':
                thread = download['thread']
                download['status'] = 'downloading'
                thread.start()

    def pause_download(self, download_id: int):
        """Pause a specific download."""
        if download_id in self.active_downloads:
            download = self.active_downloads[download_id]
            thread = download['thread']
            thread.pause()
            download['status'] = 'paused'

    def resume_download(self, download_id: int):
        """Resume a paused download."""
        if download_id in self.active_downloads:
            download = self.active_downloads[download_id]
            thread = download['thread']

            # Check if thread is already running
            if not thread.isRunning():
                # Thread hasn't started yet, start it now
                download['status'] = 'downloading'
                thread.start()
            else:
                # Thread is running but paused, just resume
                thread.resume()
                download['status'] = 'downloading'

    def cancel_download(self, download_id: int):
        """Cancel and remove a download."""
        if download_id in self.active_downloads:
            download = self.active_downloads[download_id]
            thread = download['thread']
            thread.cancel()
            download['status'] = 'cancelled'

            # Remove from active downloads
            del self.active_downloads[download_id]

    def get_download(self, download_id: int) -> Optional[dict]:
        """Get download information by ID."""
        return self.active_downloads.get(download_id)

    def get_all_downloads(self) -> dict:
        """Get all active downloads."""
        return self.active_downloads.copy()

    def pause_all(self):
        """Pause all active downloads."""
        for download_id, download in self.active_downloads.items():
            if download['status'] == 'downloading':
                self.pause_download(download_id)

    def resume_all(self):
        """Resume all paused downloads."""
        for download_id, download in self.active_downloads.items():
            if download['status'] == 'paused':
                self.resume_download(download_id)

    def cancel_all(self):
        """Cancel all downloads."""
        download_ids = list(self.active_downloads.keys())
        for download_id in download_ids:
            self.cancel_download(download_id)

    def get_active_count(self) -> int:
        """Get count of downloading threads."""
        return sum(1 for d in self.active_downloads.values() if d['status'] == 'downloading')

    def get_total_speed(self) -> float:
        """Get total download speed across all active downloads (MB/s)."""
        total_speed = 0.0
        for download in self.active_downloads.values():
            if download['status'] == 'downloading':
                progress = download['thread'].get_progress_info()
                total_speed += progress.get('speed', 0.0)
        return total_speed

    def is_interface_busy(self, source_ip: str) -> bool:
        """
        Check if an interface currently has an active download.

        Args:
            source_ip: The source IP address of the interface

        Returns:
            True if the interface has a downloading or paused download, False otherwise
        """
        for download in self.active_downloads.values():
            if download['source_ip'] == source_ip and download['status'] in ('downloading', 'paused'):
                return True
        return False
