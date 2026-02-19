"""
Download Manager GUI Module

This module provides the PyQt6-based graphical user interface for the
Multi-WAN Download Manager application.
"""
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QProgressBar, QComboBox, QSpinBox, QHeaderView, QGroupBox,
    QFileDialog, QMessageBox, QFrame, QStatusBar, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QIcon, QFont, QColor
from typing import Optional, List, Dict, Any
import os

from network_detector import get_network_interfaces, get_connected_interfaces, get_interfaces_with_internet
from download_thread import DownloadThread, DownloadManager
from state_manager import StateManager
from config import (
    WINDOW_TITLE, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    REFRESH_INTERVAL, DEFAULT_SPEED_LIMIT, SPEED_LIMIT_UNLIMITED,
    DEFAULT_DOWNLOAD_DIR
)


class DownloadManagerApp(QMainWindow):
    """
    Main application window for the Multi-WAN Download Manager.
    """

    def __init__(self):
        super().__init__()

        # Download management
        self.download_manager = DownloadManager()
        self.network_interfaces = []
        self.queued_downloads = []  # List of queued download info

        # State management
        self.state_manager = StateManager()

        # Setup UI
        self.init_ui()
        self.refresh_network_interfaces()

        # Setup update timer for progress
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_all_progress)
        self.update_timer.start(REFRESH_INTERVAL)

        # Restore saved state
        self._restore_state()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Add URL input section
        main_layout.addWidget(self.create_url_section())

        # Add download queue section
        main_layout.addWidget(self.create_queue_section())

        # Add active downloads section
        main_layout.addWidget(self.create_active_downloads_section())

        # Add control buttons
        main_layout.addWidget(self.create_control_buttons())

        # Add status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status_bar()

    def create_url_section(self) -> QGroupBox:
        """Create the URL input section."""
        group = QGroupBox("Add New Download")
        layout = QVBoxLayout()

        # URL input row
        url_layout = QHBoxLayout()

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter download URL (e.g., https://example.com/file.zip)")

        url_layout.addWidget(QLabel("URL:"))
        url_layout.addWidget(self.url_input, 1)

        # Buttons
        paste_btn = QPushButton("Paste")
        paste_btn.clicked.connect(self.paste_url)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_url)

        add_btn = QPushButton("Add to Queue")
        add_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        add_btn.clicked.connect(self.add_to_queue)

        url_layout.addWidget(paste_btn)
        url_layout.addWidget(clear_btn)
        url_layout.addWidget(add_btn)

        layout.addLayout(url_layout)

        # Network interface and speed limit row
        options_layout = QHBoxLayout()

        options_layout.addWidget(QLabel("Interface:"))
        self.interface_combo = QComboBox()
        self.interface_combo.setMinimumWidth(200)
        options_layout.addWidget(self.interface_combo)

        # Speed limit checkbox and spinbox
        self.speed_limit_checkbox = QCheckBox("Enable Speed Limit:")
        self.speed_limit_checkbox.setChecked(False)
        self.speed_limit_checkbox.stateChanged.connect(self._on_speed_limit_checkbox_changed)
        options_layout.addWidget(self.speed_limit_checkbox)

        self.speed_limit_spin = QSpinBox()
        self.speed_limit_spin.setRange(1, 1000)
        self.speed_limit_spin.setValue(int(DEFAULT_SPEED_LIMIT))
        self.speed_limit_spin.setSuffix(" MB/s")
        self.speed_limit_spin.setEnabled(False)  # Disabled by default
        options_layout.addWidget(self.speed_limit_spin)

        options_layout.addStretch()

        layout.addLayout(options_layout)

        group.setLayout(layout)
        return group

    def create_queue_section(self) -> QGroupBox:
        """Create the download queue section."""
        group = QGroupBox("Download Queue")
        layout = QVBoxLayout()

        # Queue table
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(4)
        self.queue_table.setHorizontalHeaderLabels(["URL", "Interface", "Speed Limit", "Actions"])

        # Set column widths
        header = self.queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(self.queue_table)
        group.setLayout(layout)
        return group

    def create_active_downloads_section(self) -> QGroupBox:
        """Create the active downloads section."""
        group = QGroupBox("Active Downloads")
        layout = QVBoxLayout()

        # Active downloads table
        self.active_table = QTableWidget()
        self.active_table.setColumnCount(5)
        self.active_table.setHorizontalHeaderLabels(["Status", "File", "Interface", "Progress", "Speed | ETA"])

        # Set column widths
        header = self.active_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.active_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.active_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(self.active_table)
        group.setLayout(layout)
        return group

    def create_control_buttons(self) -> QWidget:
        """Create the control button row."""
        widget = QWidget()
        layout = QHBoxLayout()

        self.start_all_btn = QPushButton("Start All")
        self.start_all_btn.clicked.connect(self.start_all_downloads)

        self.pause_all_btn = QPushButton("Pause All")
        self.pause_all_btn.clicked.connect(self.pause_all_downloads)

        self.clear_completed_btn = QPushButton("Clear Completed")
        self.clear_completed_btn.clicked.connect(self.clear_completed)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.open_settings)

        layout.addWidget(self.start_all_btn)
        layout.addWidget(self.pause_all_btn)
        layout.addWidget(self.clear_completed_btn)
        layout.addWidget(self.settings_btn)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def refresh_network_interfaces(self):
        """Refresh the list of available network interfaces with internet access."""
        self.network_interfaces = get_interfaces_with_internet()
        self.interface_combo.clear()

        if not self.network_interfaces:
            self.interface_combo.addItem("No internet-connected interfaces found")
            return

        for iface in self.network_interfaces:
            display_text = f"{iface['name']} ({iface['ip']})"
            self.interface_combo.addItem(display_text, iface)

    def paste_url(self):
        """Paste URL from clipboard."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.url_input.setText(text)

    def clear_url(self):
        """Clear the URL input field."""
        self.url_input.clear()

    def _on_speed_limit_checkbox_changed(self, state):
        """Handle speed limit checkbox state change."""
        self.speed_limit_spin.setEnabled(state == 2)  # 2 = checked

    def add_to_queue(self):
        """Add the current URL to the download queue."""
        url = self.url_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a URL.")
            return

        # Get selected interface
        if self.interface_combo.count() == 0:
            QMessageBox.warning(self, "Warning", "No network interfaces available.")
            return

        interface_data = self.interface_combo.currentData()
        if not interface_data or isinstance(interface_data, str):
            QMessageBox.warning(self, "Warning", "Please select a valid network interface.")
            return

        # Get speed limit (only if checkbox is checked)
        if self.speed_limit_checkbox.isChecked():
            speed_limit = float(self.speed_limit_spin.value())
        else:
            speed_limit = None  # Unlimited

        # Add to queued downloads
        download_info = {
            'url': url,
            'interface': interface_data,
            'speed_limit': speed_limit,
            'status': 'queued'
        }

        self.queued_downloads.append(download_info)
        self.update_queue_table()

        # Clear URL input for next download
        self.url_input.clear()

    def update_queue_table(self):
        """Update the queue table with current queued downloads."""
        self.queue_table.setRowCount(len(self.queued_downloads))

        for row, download in enumerate(self.queued_downloads):
            # URL
            url_item = QTableWidgetItem(download['url'])
            self.queue_table.setItem(row, 0, url_item)

            # Interface
            interface_text = f"{download['interface']['name']} ({download['interface']['ip']})"
            interface_item = QTableWidgetItem(interface_text)
            self.queue_table.setItem(row, 1, interface_item)

            # Speed limit
            if download['speed_limit']:
                speed_text = f"{download['speed_limit']} MB/s"
            else:
                speed_text = "Unlimited"
            speed_item = QTableWidgetItem(speed_text)
            self.queue_table.setItem(row, 2, speed_item)

            # Actions
            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(lambda checked, r=row: self.remove_from_queue(r))
            self.queue_table.setCellWidget(row, 3, remove_btn)

    def remove_from_queue(self, row: int):
        """Remove a download from the queue."""
        if 0 <= row < len(self.queued_downloads):
            del self.queued_downloads[row]
            self.update_queue_table()

    def start_all_downloads(self):
        """Start all queued downloads - max 1 per interface at a time."""
        if not self.queued_downloads:
            QMessageBox.information(self, "Info", "No downloads in queue.")
            return

        # Track which interfaces we've started a download for
        started_interfaces = set()
        downloads_to_remove = []

        # Start 1 download per interface, keep rest in queue
        for i, download_info in enumerate(self.queued_downloads):
            interface_ip = download_info['interface']['ip']

            # Skip if we already started a download for this interface
            if interface_ip in started_interfaces:
                continue

            # Check if interface is already busy (has existing download)
            if self.download_manager.is_interface_busy(interface_ip):
                continue

            # Start this download
            download_id = self.download_manager.add_download(
                url=download_info['url'],
                source_ip=interface_ip,
                speed_limit=download_info['speed_limit']
            )

            # Get the download thread and connect signals
            download = self.download_manager.get_download(download_id)
            if download:
                thread = download['thread']

                # Connect signals
                thread.signals.progress_updated.connect(
                    lambda p, d, t, s, e, did=download_id: self.on_download_progress(did, p, d, t, s, e)
                )
                thread.signals.download_completed.connect(
                    lambda fp, did=download_id: self.on_download_completed(did, fp)
                )
                thread.signals.download_failed.connect(
                    lambda err, did=download_id: self.on_download_failed(did, err)
                )

                # Start the download
                self.download_manager.start_download(download_id)

            # Mark this interface as having a started download
            started_interfaces.add(interface_ip)
            # Mark for removal from queue (will be removed after loop)
            downloads_to_remove.append(i)

        # Remove started downloads from queue (in reverse order to maintain indices)
        for i in sorted(downloads_to_remove, reverse=True):
            del self.queued_downloads[i]

        self.update_queue_table()
        self.update_active_downloads_table()

    def pause_all_downloads(self):
        """Pause all active downloads."""
        self.download_manager.pause_all()
        self.update_active_downloads_table()

    def clear_completed(self):
        """Clear completed downloads from the active list."""
        # Note: This is a simplified version
        # In a full implementation, you'd track completed downloads separately
        self.update_active_downloads_table()

    def open_settings(self):
        """Open settings dialog."""
        QMessageBox.information(self, "Settings", "Settings dialog not yet implemented.")

    def update_all_progress(self):
        """Update progress for all active downloads."""
        self.update_active_downloads_table()
        self.update_status_bar()

    def update_active_downloads_table(self):
        """Update the active downloads table."""
        downloads = self.download_manager.get_all_downloads()
        self.active_table.setRowCount(len(downloads))

        for row, (download_id, download) in enumerate(downloads.items()):
            # Status
            status_item = QTableWidgetItem()
            if download['status'] == 'downloading':
                status_item.setText("↓")
                status_item.setForeground(QColor(0, 128, 0))  # Green
            elif download['status'] == 'paused':
                status_item.setText("||")
                status_item.setForeground(QColor(255, 165, 0))  # Orange
            elif download['status'] == 'completed':
                status_item.setText("✓")
                status_item.setForeground(QColor(0, 0, 255))  # Blue
            else:
                status_item.setText(download['status'])
            self.active_table.setItem(row, 0, status_item)

            # File (extract from URL)
            url = download['url']
            filename = url.split('/')[-1].split('?')[0] or 'file'
            file_item = QTableWidgetItem(filename)
            self.active_table.setItem(row, 1, file_item)

            # Interface
            interface_text = download['source_ip']
            interface_item = QTableWidgetItem(interface_text)
            self.active_table.setItem(row, 2, interface_item)

            # Progress bar
            progress_info = download['thread'].get_progress_info()
            progress_bar = QProgressBar()
            progress_bar.setValue(progress_info['percentage'])
            progress_bar.setFormat(f"{progress_info['percentage']}%")
            self.active_table.setCellWidget(row, 3, progress_bar)

            # Speed and ETA
            speed_eta_text = f"{progress_info['speed']:.2f} MB/s | ETA: {progress_info['eta']}"
            speed_eta_item = QTableWidgetItem(speed_eta_text)
            self.active_table.setItem(row, 4, speed_eta_item)

            # Add control buttons in the last row
            if download['status'] == 'downloading':
                pause_btn = QPushButton("Pause")
                pause_btn.clicked.connect(lambda: self.pause_download(download_id))
                self.active_table.setCellWidget(row, 4, pause_btn)
            elif download['status'] == 'paused':
                resume_btn = QPushButton("Resume")
                resume_btn.clicked.connect(lambda: self.resume_download(download_id))
                self.active_table.setCellWidget(row, 4, resume_btn)

    def pause_download(self, download_id: int):
        """Pause a specific download."""
        self.download_manager.pause_download(download_id)

    def resume_download(self, download_id: int):
        """Resume a paused download."""
        self.download_manager.resume_download(download_id)

    def on_download_progress(self, download_id: int, percentage: int, downloaded: int,
                            total: int, speed: float, eta: str):
        """Handle download progress updates."""
        # Progress is updated via timer, so we don't need to do anything here
        pass

    def on_download_completed(self, download_id: int, filepath: str):
        """Handle download completion."""
        # Get the interface for this download
        download = self.download_manager.get_download(download_id)
        interface_ip = download['source_ip'] if download else None

        self.update_status_bar()
        QMessageBox.information(self, "Download Complete",
                               f"Download saved to:\n{filepath}")

        # Remove completed download from manager
        if download_id in self.download_manager.active_downloads:
            del self.download_manager.active_downloads[download_id]

        # Auto-start next download for this interface
        if interface_ip:
            self._start_next_download_for_interface(interface_ip)

        self.update_active_downloads_table()

    def on_download_failed(self, download_id: int, error: str):
        """Handle download failure."""
        # Get the interface for this download
        download = self.download_manager.get_download(download_id)
        interface_ip = download['source_ip'] if download else None

        self.update_status_bar()
        QMessageBox.critical(self, "Download Failed", error)

        # Remove failed download from manager
        if download_id in self.download_manager.active_downloads:
            del self.download_manager.active_downloads[download_id]

        # Auto-start next download for this interface
        if interface_ip:
            self._start_next_download_for_interface(interface_ip)

        self.update_active_downloads_table()

    def _start_next_download_for_interface(self, interface_ip: str):
        """
        Start the next queued download for a specific interface.

        Args:
            interface_ip: The IP address of the interface to start download for
        """
        # Find first queued download for this interface
        for i, download_info in enumerate(self.queued_downloads):
            if download_info['interface']['ip'] == interface_ip:
                # Start this download
                download_id = self.download_manager.add_download(
                    url=download_info['url'],
                    source_ip=interface_ip,
                    speed_limit=download_info['speed_limit']
                )

                # Get the download thread and connect signals
                download = self.download_manager.get_download(download_id)
                if download:
                    thread = download['thread']

                    # Connect signals
                    thread.signals.progress_updated.connect(
                        lambda p, d, t, s, e, did=download_id: self.on_download_progress(did, p, d, t, s, e)
                    )
                    thread.signals.download_completed.connect(
                        lambda fp, did=download_id: self.on_download_completed(did, fp)
                    )
                    thread.signals.download_failed.connect(
                        lambda err, did=download_id: self.on_download_failed(did, err)
                    )

                    # Start the download
                    self.download_manager.start_download(download_id)

                # Remove from queue
                del self.queued_downloads[i]
                self.update_queue_table()
                break  # Only start one download per call

    def update_status_bar(self):
        """Update the status bar with current statistics."""
        active_count = self.download_manager.get_active_count()
        total_speed = self.download_manager.get_total_speed()
        total_count = len(self.download_manager.get_all_downloads())

        status_text = f"Active: {active_count} | Total Speed: {total_speed:.2f} MB/s | Total Downloads: {total_count}"
        self.status_bar.showMessage(status_text)

    def closeEvent(self, event):
        """Handle application close - save state before exiting."""
        # Save current state
        state = self._get_current_state()
        self.state_manager.save_state(state)

        # Stop all downloads
        self.download_manager.cancel_all()

        event.accept()

    def _get_current_state(self) -> Dict[str, Any]:
        """Gather current application state for saving."""
        import config

        state = {
            "version": "1.0",
            "next_id": self.download_manager.next_id,
            "queued_downloads": [],
            "active_downloads": [],
            "completed_downloads": [],
            "settings": {
                "default_download_dir": config.DEFAULT_DOWNLOAD_DIR,
                "default_speed_limit": config.DEFAULT_SPEED_LIMIT
            }
        }

        # Save queued downloads
        for dl in self.queued_downloads:
            state["queued_downloads"].append({
                "url": dl["url"],
                "interface": dl["interface"],
                "speed_limit": dl["speed_limit"]
            })

        # Save active downloads
        for dl_id, dl in self.download_manager.get_all_downloads().items():
            progress = dl["thread"].get_progress_info()
            state["active_downloads"].append({
                "id": dl_id,
                "url": dl["url"],
                "interface": {"name": dl["source_ip"], "ip": dl["source_ip"]},
                "speed_limit": dl["thread"].speed_limit,
                "status": dl["status"],
                "filepath": progress.get("filepath"),
                "downloaded_bytes": progress.get("downloaded", 0),
                "total_bytes": progress.get("total", 0),
                "progress_percentage": progress.get("percentage", 0)
            })

        return state

    def _restore_state(self):
        """Restore application state from saved file."""
        state = self.state_manager.load_state()

        if not state:
            return

        # Restore next_id
        self.download_manager.next_id = state.get("next_id", 1)

        # Restore queued downloads
        for dl in state.get("queued_downloads", []):
            download_info = {
                "url": dl["url"],
                "interface": dl["interface"],
                "speed_limit": dl.get("speed_limit"),
                "status": "queued"
            }
            self.queued_downloads.append(download_info)

        # Restore active downloads - add them to queue so they can be restarted
        # The download_engine will automatically resume from partial files
        for dl in state.get("active_downloads", []):
            download_info = {
                "url": dl["url"],
                "interface": dl["interface"],
                "speed_limit": dl.get("speed_limit"),
                "status": "queued"
            }
            self.queued_downloads.append(download_info)

        # Update UI with restored state
        self.update_queue_table()
        self.update_active_downloads_table()


def main():
    """Main entry point for the application."""
    import sys

    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look

    window = DownloadManagerApp()
    window.show()

    sys.exit(app.exec())
