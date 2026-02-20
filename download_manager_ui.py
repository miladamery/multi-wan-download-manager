"""
Download Manager GUI Module

This module provides the PyQt6-based graphical user interface for the
Multi-WAN Download Manager application.
"""
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QProgressBar, QComboBox, QSpinBox, QHeaderView, QGroupBox,
    QFileDialog, QMessageBox, QFrame, QStatusBar, QCheckBox,
    QTabWidget, QTextEdit, QProgressDialog, QDialog
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QIcon, QFont, QColor
from typing import Optional, List, Dict, Any
import os

from network_detector import get_network_interfaces, get_connected_interfaces, get_interfaces_with_internet
from download_thread import DownloadThread, DownloadManager
from download_engine import DownloadEngine
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
        self.download_history = []  # List of completed download entries

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

        # Create main tab widget (Downloads | History)
        main_tab_widget = QTabWidget()

        # Tab 1: Downloads (existing content)
        downloads_tab = QWidget()
        downloads_layout = QVBoxLayout(downloads_tab)
        downloads_layout.addWidget(self.create_tabbed_url_section())
        downloads_layout.addWidget(self.create_queue_section())
        downloads_layout.addWidget(self.create_active_downloads_section())
        downloads_layout.addWidget(self.create_control_buttons())

        # Tab 2: History (new)
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.addWidget(self.create_history_section())

        main_tab_widget.addTab(downloads_tab, "Downloads")
        main_tab_widget.addTab(history_tab, "History")

        main_layout.addWidget(main_tab_widget)

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

    def create_batch_url_section(self) -> QGroupBox:
        """Create the batch URL input section with round-robin distribution."""
        group = QGroupBox("Add Multiple URLs (Round-Robin Distribution)")
        layout = QVBoxLayout()

        # URL text area (multi-line)
        self.batch_url_text = QTextEdit()
        self.batch_url_text.setPlaceholderText(
            "Enter multiple URLs (one per line):\n"
            "https://example.com/file1.zip\n"
            "https://example.com/file2.zip\n"
            "https://example.com/file3.zip"
        )
        self.batch_url_text.setMinimumHeight(120)

        layout.addWidget(QLabel("URLs (one per line):"))
        layout.addWidget(self.batch_url_text)

        # Button row
        button_layout = QHBoxLayout()

        import_btn = QPushButton("Import from File")
        import_btn.clicked.connect(self.import_urls_from_file)

        clear_btn = QPushButton("Clear URLs")
        clear_btn.clicked.connect(self.clear_batch_urls)

        button_layout.addWidget(import_btn)
        button_layout.addWidget(clear_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Speed limit section
        speed_limit_layout = QHBoxLayout()
        self.batch_speed_limit_checkbox = QCheckBox("Enable Speed Limit:")
        self.batch_speed_limit_checkbox.setChecked(False)
        self.batch_speed_limit_checkbox.stateChanged.connect(
            self._on_batch_speed_limit_checkbox_changed
        )
        speed_limit_layout.addWidget(self.batch_speed_limit_checkbox)

        self.batch_speed_limit_spin = QSpinBox()
        self.batch_speed_limit_spin.setRange(1, 1000)
        self.batch_speed_limit_spin.setValue(int(DEFAULT_SPEED_LIMIT))
        self.batch_speed_limit_spin.setSuffix(" MB/s")
        self.batch_speed_limit_spin.setEnabled(False)
        speed_limit_layout.addWidget(self.batch_speed_limit_spin)

        speed_limit_layout.addStretch()
        layout.addLayout(speed_limit_layout)

        # Info label showing available interfaces
        self.interface_info_label = QLabel("Interfaces will be assigned automatically")
        self.interface_info_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")

        # Add All button
        add_all_layout = QHBoxLayout()
        add_all_layout.addWidget(self.interface_info_label)
        add_all_layout.addStretch()

        add_all_btn = QPushButton("Add All to Queue (Round-Robin)")
        add_all_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; }"
        )
        add_all_btn.clicked.connect(self.add_batch_urls_to_queue)
        add_all_layout.addWidget(add_all_btn)

        layout.addLayout(add_all_layout)

        group.setLayout(layout)
        return group

    def create_tabbed_url_section(self) -> QTabWidget:
        """Create tabbed interface for single and batch URL input."""
        tab_widget = QTabWidget()

        # Tab 1: Single URL (existing functionality)
        single_url_widget = QWidget()
        single_layout = QVBoxLayout(single_url_widget)
        single_layout.addWidget(self.create_url_section())

        # Tab 2: Batch URLs (new functionality)
        batch_url_widget = QWidget()
        batch_layout = QVBoxLayout(batch_url_widget)
        batch_layout.addWidget(self.create_batch_url_section())

        tab_widget.addTab(single_url_widget, "Single URL")
        tab_widget.addTab(batch_url_widget, "Batch URLs (Round-Robin)")

        return tab_widget

    def create_queue_section(self) -> QGroupBox:
        """Create the download queue section."""
        group = QGroupBox("Download Queue")
        layout = QVBoxLayout()

        # Queue table
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(5)
        self.queue_table.setHorizontalHeaderLabels(["URL", "Interface", "Speed Limit", "Size", "Actions"])

        # Enable column resizing and set initial widths
        header = self.queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        # Set initial column widths (in pixels)
        self.queue_table.setColumnWidth(0, 400)  # URL
        self.queue_table.setColumnWidth(1, 150)  # Interface
        self.queue_table.setColumnWidth(2, 100)  # Speed Limit
        self.queue_table.setColumnWidth(3, 80)   # Size
        self.queue_table.setColumnWidth(4, 180)   # Actions (wider for Up/Down buttons)
        header.setStretchLastSection(True)  # Stretch last section to fill space

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
        self.active_table.setColumnCount(7)
        self.active_table.setHorizontalHeaderLabels(["Status", "File", "Interface", "Size", "Progress", "Speed | ETA", "Actions"])

        # Enable column resizing and set initial widths
        header = self.active_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        # Set initial column widths (in pixels)
        self.active_table.setColumnWidth(0, 60)   # Status
        self.active_table.setColumnWidth(1, 250)  # File
        self.active_table.setColumnWidth(2, 120)  # Interface
        self.active_table.setColumnWidth(3, 80)   # Size
        self.active_table.setColumnWidth(4, 150)  # Progress
        self.active_table.setColumnWidth(5, 120)  # Speed | ETA
        self.active_table.setColumnWidth(6, 150)  # Actions (wider for additional button)
        header.setStretchLastSection(True)  # Stretch last section to fill space

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

    def create_history_section(self) -> QGroupBox:
        """Create the download history section."""
        group = QGroupBox("Download History")
        layout = QVBoxLayout()

        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Date/Time", "File", "Interface", "Size", "URL", "Actions"
        ])

        # Enable column resizing
        header = self.history_table.horizontalHeader()
        for i in range(6):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        # Set initial column widths
        self.history_table.setColumnWidth(0, 150)  # Date/Time
        self.history_table.setColumnWidth(1, 200)  # File
        self.history_table.setColumnWidth(2, 120)  # Interface
        self.history_table.setColumnWidth(3, 80)   # Size
        self.history_table.setColumnWidth(4, 400)  # URL
        self.history_table.setColumnWidth(5, 200)  # Actions
        header.setStretchLastSection(True)

        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(self.history_table)

        # Control buttons
        button_layout = QHBoxLayout()

        clear_history_btn = QPushButton("Clear History")
        clear_history_btn.clicked.connect(self.clear_download_history)

        export_history_btn = QPushButton("Export History")
        export_history_btn.clicked.connect(self.export_download_history)

        button_layout.addWidget(clear_history_btn)
        button_layout.addWidget(export_history_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group

    def refresh_network_interfaces(self):
        """Refresh the list of available network interfaces with internet access."""
        self.network_interfaces = get_interfaces_with_internet()
        self.interface_combo.clear()

        if not self.network_interfaces:
            self.interface_combo.addItem("No internet-connected interfaces found")

            # Update batch interface info label
            if hasattr(self, 'interface_info_label'):
                self.interface_info_label.setText("No interfaces available")
                self.interface_info_label.setStyleSheet(
                    "QLabel { color: red; font-weight: bold; }"
                )
            return

        for iface in self.network_interfaces:
            display_text = f"{iface['name']} ({iface['ip']})"
            self.interface_combo.addItem(display_text, iface)

        # Update batch interface info label
        if hasattr(self, 'interface_info_label'):
            interface_names = [iface['name'] for iface in self.network_interfaces]
            self.interface_info_label.setText(
                f"Available interfaces ({len(self.network_interfaces)}): "
                f"{', '.join(interface_names)}"
            )
            self.interface_info_label.setStyleSheet(
                "QLabel { color: green; }"
            )

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

    # ============================================================================
    # BATCH URL HELPER METHODS
    # ============================================================================

    def _is_valid_url(self, url: str) -> bool:
        """
        Basic URL validation.

        Args:
            url: URL string to validate

        Returns:
            True if URL appears valid, False otherwise
        """
        if not url:
            return False

        # Check for valid protocol
        valid_protocols = ['http://', 'https://', 'ftp://']
        has_valid_protocol = any(url.lower().startswith(proto) for proto in valid_protocols)

        if not has_valid_protocol:
            return False

        # Basic structure check (must have :// and at least one character after)
        if '://' not in url:
            return False

        parts = url.split('://', 1)
        if len(parts) != 2 or not parts[1]:
            return False

        return True

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "Unknown"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    def _get_distribution_summary(self, urls: List[str], interfaces: List[Dict]) -> str:
        """
        Generate a summary of how URLs are distributed across interfaces.

        Args:
            urls: List of URLs
            interfaces: List of available interface dicts

        Returns:
            Multi-line string showing distribution
        """
        interface_count = len(interfaces)
        url_count = len(urls)

        # Count URLs per interface
        distribution = {}
        for iface in interfaces:
            distribution[iface['name']] = 0

        for index in range(url_count):
            iface_index = index % interface_count
            interface_name = interfaces[iface_index]['name']
            distribution[interface_name] += 1

        # Build summary string
        summary_lines = ["Interface Distribution:"]
        for iface_name, count in distribution.items():
            if count > 0:
                summary_lines.append(f"  - {iface_name}: {count} URL(s)")

        return '\n'.join(summary_lines)

    def _on_batch_speed_limit_checkbox_changed(self, state):
        """Handle batch speed limit checkbox state change."""
        self.batch_speed_limit_spin.setEnabled(state == 2)  # 2 = checked

    def clear_batch_urls(self):
        """Clear all URLs from the batch text area."""
        self.batch_url_text.clear()

    def import_urls_from_file(self):
        """
        Open file dialog and import URLs from a text file.

        Supported formats:
        - Plain text files with one URL per line
        - Files may contain comments (lines starting with #)
        - Empty lines are ignored
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import URLs from File",
            "",  # Start directory (empty = default)
            "Text Files (*.txt);;All Files (*)"
        )

        if not file_path:
            return  # User cancelled

        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Parse URLs (skip empty lines and comments)
            urls = []
            for line in lines:
                url = line.strip()

                # Skip comments and empty lines
                if not url or url.startswith('#'):
                    continue

                # Validate URL
                if self._is_valid_url(url):
                    urls.append(url)

            if not urls:
                QMessageBox.warning(
                    self,
                    "Import Failed",
                    "No valid URLs found in the selected file.\n\n"
                    "File format requirements:\n"
                    "- One URL per line\n"
                    "- Lines starting with # are treated as comments\n"
                    "- URLs must start with http://, https://, or ftp://"
                )
                return

            # Load URLs into text area
            self.batch_url_text.setPlainText('\n'.join(urls))

            # Show success message
            QMessageBox.information(
                self,
                "Import Successful",
                f"Successfully imported {len(urls)} URL(s) from file."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import URLs from file:\n{str(e)}"
            )

    def add_batch_urls_to_queue(self):
        """
        Add multiple URLs to the queue with round-robin interface distribution.

        Round-robin algorithm:
        1. Parse all URLs from text area (one per line)
        2. Validate URLs and filter out empty/invalid entries
        3. Get list of available interfaces with internet access
        4. For each URL, assign next interface in rotation
        5. Apply same speed limit to all downloads
        6. Add all to queued_downloads list
        """
        # Step 1: Get URLs from text area
        raw_text = self.batch_url_text.toPlainText()
        url_lines = raw_text.split('\n')

        # Step 2: Parse and validate URLs
        valid_urls = []
        invalid_urls = []

        for line in url_lines:
            url = line.strip()
            if url:  # Skip empty lines
                if self._is_valid_url(url):
                    valid_urls.append(url)
                else:
                    invalid_urls.append(url)

        if not valid_urls:
            QMessageBox.warning(
                self,
                "Warning",
                "No valid URLs found. Please enter one URL per line.\n\n"
                "URLs must start with http://, https://, or ftp://"
            )
            return

        # Step 3: Get available interfaces
        available_interfaces = self.network_interfaces

        if not available_interfaces:
            QMessageBox.warning(
                self,
                "Warning",
                "No network interfaces with internet access found.\n"
                "Please check your network connections."
            )
            return

        # Step 4: Get speed limit setting
        if self.batch_speed_limit_checkbox.isChecked():
            speed_limit = float(self.batch_speed_limit_spin.value())
        else:
            speed_limit = None

        # Show progress dialog for file size fetching
        progress = QProgressDialog("Fetching file sizes...", "Cancel", 0, len(valid_urls), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setWindowTitle("Processing URLs")
        progress.setMinimumDuration(0)  # Show immediately
        progress.setValue(0)

        # Step 5: Round-robin assignment with progress updates
        interface_count = len(available_interfaces)

        # Create DownloadEngine instance once for efficiency
        download_engine = DownloadEngine()
        added_count = 0

        for index, url in enumerate(valid_urls):
            # Check if user cancelled
            if progress.wasCanceled():
                if added_count > 0:
                    self.update_queue_table()
                    QMessageBox.information(
                        self,
                        "Cancelled",
                        f"Operation cancelled. {added_count} URL(s) added to queue."
                    )
                return

            # Update progress dialog
            progress.setValue(index + 1)
            progress.setLabelText(f"Fetching file size {index + 1}/{len(valid_urls)}")
            QApplication.processEvents()  # Allow UI to update

            # Calculate which interface to use (round-robin)
            interface_index = index % interface_count
            assigned_interface = available_interfaces[interface_index]

            # Fetch file size via HEAD request
            file_size = 0
            try:
                info = download_engine.get_download_info(url, assigned_interface['ip'])
                if info.get('success'):
                    file_size = info.get('file_size', 0)
            except Exception:
                file_size = 0  # Silently fail if size fetch fails

            # Create download info dict
            download_info = {
                'url': url,
                'interface': assigned_interface,
                'speed_limit': speed_limit,
                'file_size': file_size,
                'status': 'queued'
            }

            # Add to queue
            self.queued_downloads.append(download_info)
            added_count += 1

        # Close progress dialog
        progress.close()

        # Step 6: Update UI
        self.update_queue_table()

        # Step 7: Show success message with distribution summary
        interface_summary = self._get_distribution_summary(valid_urls, available_interfaces)
        speed_text = f"{speed_limit} MB/s" if speed_limit else "Unlimited"
        QMessageBox.information(
            self,
            "URLs Added to Queue",
            f"Successfully added {len(valid_urls)} URL(s) to queue.\n\n"
            f"{interface_summary}\n\n"
            f"Speed Limit: {speed_text}"
        )

        # Clear text area for next batch
        self.batch_url_text.clear()

    # ============================================================================
    # SINGLE URL METHODS (existing)
    # ============================================================================

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

        # Fetch file size via HEAD request
        download_engine = DownloadEngine()
        file_size = 0
        try:
            info = download_engine.get_download_info(url, interface_data['ip'])
            if info.get('success'):
                file_size = info.get('file_size', 0)
        except Exception:
            file_size = 0  # Silently fail if size fetch fails

        # Add to queued downloads
        download_info = {
            'url': url,
            'interface': interface_data,
            'speed_limit': speed_limit,
            'file_size': file_size,
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

            # File size (column 3)
            file_size = download.get('file_size', 0)
            size_text = self._format_file_size(file_size)
            size_item = QTableWidgetItem(size_text)
            self.queue_table.setItem(row, 3, size_item)

            # Actions (column 4) - Move Up, Move Down, Remove
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)

            # Move Up button (disable for first row)
            up_btn = QPushButton("↑")
            up_btn.setMaximumWidth(40)
            up_btn.setEnabled(row > 0)  # Disable for first row
            up_btn.clicked.connect(lambda checked, r=row: self.move_queue_up(r))
            actions_layout.addWidget(up_btn)

            # Move Down button (disable for last row)
            down_btn = QPushButton("↓")
            down_btn.setMaximumWidth(40)
            down_btn.setEnabled(row < len(self.queued_downloads) - 1)  # Disable for last row
            down_btn.clicked.connect(lambda checked, r=row: self.move_queue_down(r))
            actions_layout.addWidget(down_btn)

            # Remove button
            remove_btn = QPushButton("Remove")
            remove_btn.setMaximumWidth(60)
            remove_btn.clicked.connect(lambda checked, r=row: self.remove_from_queue(r))
            actions_layout.addWidget(remove_btn)

            actions_layout.addStretch()

            self.queue_table.setCellWidget(row, 4, actions_widget)

    def remove_from_queue(self, row: int):
        """Remove a download from the queue."""
        if 0 <= row < len(self.queued_downloads):
            del self.queued_downloads[row]
            self.update_queue_table()

    def move_queue_up(self, row: int):
        """Move a queue item up by one position."""
        if 0 < row < len(self.queued_downloads):
            # Swap with previous item
            self.queued_downloads[row], self.queued_downloads[row - 1] = \
                self.queued_downloads[row - 1], self.queued_downloads[row]
            self.update_queue_table()

    def move_queue_down(self, row: int):
        """Move a queue item down by one position."""
        if 0 <= row < len(self.queued_downloads) - 1:
            # Swap with next item
            self.queued_downloads[row], self.queued_downloads[row + 1] = \
                self.queued_downloads[row + 1], self.queued_downloads[row]
            self.update_queue_table()

    def start_all_downloads(self):
        """Start all queued downloads and resume paused downloads - max 1 per interface at a time."""

        # First, resume all paused downloads
        self.download_manager.resume_all()

        # Then start new downloads from queue
        if not self.queued_downloads:
            # No new downloads to start, but update table in case we resumed paused ones
            self.update_active_downloads_table()
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

            # Interface - look up name from IP
            source_ip = download['source_ip']
            interface_name = None
            # Find interface name matching this IP
            for iface in self.network_interfaces:
                if iface['ip'] == source_ip:
                    interface_name = iface['name']
                    break

            if interface_name:
                interface_text = f"{interface_name} ({source_ip})"
            else:
                interface_text = source_ip  # Fallback to just IP if not found
            interface_item = QTableWidgetItem(interface_text)
            self.active_table.setItem(row, 2, interface_item)

            # File size (column 3)
            progress_info = download['thread'].get_progress_info()
            total_bytes = progress_info.get('total', 0)
            size_text = self._format_file_size(total_bytes)
            size_item = QTableWidgetItem(size_text)
            self.active_table.setItem(row, 3, size_item)

            # Progress bar (column 4)
            progress_bar = QProgressBar()
            progress_bar.setValue(progress_info['percentage'])
            progress_bar.setFormat(f"{progress_info['percentage']}%")
            self.active_table.setCellWidget(row, 4, progress_bar)

            # Speed and ETA (column 5) - stays as text
            speed_eta_text = f"{progress_info['speed']:.2f} MB/s | ETA: {progress_info['eta']}"
            speed_eta_item = QTableWidgetItem(speed_eta_text)
            self.active_table.setItem(row, 5, speed_eta_item)

            # Actions (column 6)
            if download['status'] == 'downloading':
                pause_btn = QPushButton("Pause")
                pause_btn.clicked.connect(lambda checked, did=download_id: self.pause_download(did))
                self.active_table.setCellWidget(row, 6, pause_btn)
            elif download['status'] == 'paused':
                # Create actions widget with multiple buttons
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(4, 2, 4, 2)

                # Resume button
                resume_btn = QPushButton("Resume")
                resume_btn.setMaximumWidth(60)
                resume_btn.clicked.connect(lambda checked, did=download_id: self.resume_download(did))
                actions_layout.addWidget(resume_btn)

                # Move to Queue button
                move_to_queue_btn = QPushButton("To Queue")
                move_to_queue_btn.setMaximumWidth(70)
                move_to_queue_btn.clicked.connect(lambda checked, did=download_id: self.move_paused_to_queue(did))
                actions_layout.addWidget(move_to_queue_btn)

                actions_layout.addStretch()

                self.active_table.setCellWidget(row, 6, actions_widget)

    def update_history_table(self):
        """Update the history table with download history."""
        self.history_table.setRowCount(len(self.download_history))

        for row, entry in enumerate(self.download_history):
            # Date/Time
            completion_time = entry.get('completion_time', 'Unknown')
            # Parse ISO format and display in readable format
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(completion_time)
                time_text = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                time_text = completion_time

            time_item = QTableWidgetItem(time_text)
            self.history_table.setItem(row, 0, time_item)

            # File
            filename = entry.get('filename', 'Unknown')
            file_item = QTableWidgetItem(filename)
            self.history_table.setItem(row, 1, file_item)

            # Interface
            interface = entry.get('interface', {})
            interface_text = f"{interface.get('name', 'Unknown')} ({interface.get('ip', 'Unknown')})"
            interface_item = QTableWidgetItem(interface_text)
            self.history_table.setItem(row, 2, interface_item)

            # Size
            file_size = entry.get('file_size', 0)
            size_text = self._format_file_size(file_size)
            size_item = QTableWidgetItem(size_text)
            self.history_table.setItem(row, 3, size_item)

            # URL - show full URL
            url = entry.get('url', 'Unknown')
            url_item = QTableWidgetItem(url)
            self.history_table.setItem(row, 4, url_item)

            # Actions (View Details, Copy URL, Re-download)
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)

            view_btn = QPushButton("View")
            view_btn.setMaximumWidth(50)
            view_btn.clicked.connect(lambda checked, r=row: self.view_history_details(r))
            actions_layout.addWidget(view_btn)

            copy_btn = QPushButton("Copy URL")
            copy_btn.setMaximumWidth(70)
            copy_btn.clicked.connect(lambda checked, r=row: self.copy_url_from_history(r))
            actions_layout.addWidget(copy_btn)

            redownload_btn = QPushButton("Re-download")
            redownload_btn.setMaximumWidth(80)
            redownload_btn.clicked.connect(lambda checked, r=row: self.redownload_from_history(r))
            actions_layout.addWidget(redownload_btn)

            actions_layout.addStretch()

            self.history_table.setCellWidget(row, 5, actions_widget)

    def pause_download(self, download_id: int):
        """Pause a specific download."""
        self.download_manager.pause_download(download_id)

    def resume_download(self, download_id: int):
        """Resume a paused download."""
        self.download_manager.resume_download(download_id)

    def move_paused_to_queue(self, download_id: int):
        """Move a paused download back to the queue."""
        # Get the download
        download = self.download_manager.get_download(download_id)
        if not download:
            return

        # Get interface details
        interface_ip = download['source_ip']
        interface_name = None
        for iface in self.network_interfaces:
            if iface['ip'] == interface_ip:
                interface_name = iface['name']
                break

        # Get progress info to preserve partial file info
        progress = download['thread'].get_progress_info()

        # Create download info for queue
        download_info = {
            'url': download['url'],
            'interface': {
                'name': interface_name or interface_ip,
                'ip': interface_ip
            },
            'speed_limit': download['thread'].speed_limit,
            'file_size': progress.get('total', 0),
            'status': 'queued'
        }

        # Cancel the download (keeps partial file for resume)
        self.download_manager.cancel_download(download_id)

        # Remove from active downloads
        if download_id in self.download_manager.active_downloads:
            del self.download_manager.active_downloads[download_id]

        # Add to queue
        self.queued_downloads.append(download_info)

        # Update UI
        self.update_active_downloads_table()
        self.update_queue_table()
        self.update_status_bar()

        # Show confirmation
        QMessageBox.information(
            self,
            "Moved to Queue",
            f"Download moved back to queue:\n{download['url']}\n\n"
            f"Progress will be preserved when resumed."
        )

    def on_download_progress(self, download_id: int, percentage: int, downloaded: int,
                            total: int, speed: float, eta: str):
        """Handle download progress updates."""
        # Progress is updated via timer, so we don't need to do anything here
        pass

    def on_download_completed(self, download_id: int, filepath: str):
        """Handle download completion."""
        from datetime import datetime

        # Get the interface for this download
        download = self.download_manager.get_download(download_id)
        interface_ip = download['source_ip'] if download else None

        # ===== ADD TO HISTORY =====
        if download:
            thread = download['thread']

            # Get interface details
            interface_name = None
            for iface in self.network_interfaces:
                if iface['ip'] == interface_ip:
                    interface_name = iface['name']
                    break

            # Create history entry
            history_entry = {
                'download_id': download_id,
                'url': download['url'],
                'filename': os.path.basename(filepath),
                'filepath': filepath,
                'interface': {
                    'name': interface_name or interface_ip,
                    'ip': interface_ip
                },
                'file_size': thread.total_bytes,
                'completion_time': datetime.now().isoformat(),
                'speed_limit': thread.speed_limit
            }

            # Add to history (newest first)
            self.download_history.insert(0, history_entry)
            self.update_history_table()

        # ===== EXISTING CODE =====
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

    def view_history_details(self, row: int):
        """Show detailed information about a history entry."""
        if 0 <= row < len(self.download_history):
            entry = self.download_history[row]

            details = QDialog(self)
            details.setWindowTitle("Download Details")
            details.setMinimumWidth(500)
            layout = QVBoxLayout(details)

            # Build details text
            info_text = f"""
            <h2>Download Information</h2>
            <table border="0" cellpadding="5">
            <tr><td><b>File:</b></td><td>{entry.get('filename', 'Unknown')}</td></tr>
            <tr><td><b>URL:</b></td><td>{entry.get('url', 'Unknown')}</td></tr>
            <tr><td><b>File Path:</b></td><td>{entry.get('filepath', 'Unknown')}</td></tr>
            <tr><td><b>Interface:</b></td><td>{entry['interface'].get('name', 'Unknown')} ({entry['interface'].get('ip', 'Unknown')})</td></tr>
            <tr><td><b>File Size:</b></td><td>{self._format_file_size(entry.get('file_size', 0))}</td></tr>
            <tr><td><b>Speed Limit:</b></td><td>{entry.get('speed_limit', 'Unlimited') if entry.get('speed_limit') else 'Unlimited'} MB/s</td></tr>
            <tr><td><b>Completed:</b></td><td>{entry.get('completion_time', 'Unknown')}</td></tr>
            </table>
            """

            label = QLabel(info_text)
            label.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(label)

            # Open file location button
            filepath = entry.get('filepath', '')
            if filepath and os.path.exists(filepath):
                btn_layout = QHBoxLayout()

                open_file_btn = QPushButton("Open File")
                open_file_btn.clicked.connect(lambda: os.startfile(filepath))

                open_folder_btn = QPushButton("Open Folder")
                open_folder_btn.clicked.connect(lambda: os.startfile(os.path.dirname(filepath)))

                btn_layout.addWidget(open_file_btn)
                btn_layout.addWidget(open_folder_btn)
                btn_layout.addStretch()
                layout.addLayout(btn_layout)

            # Close button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(details.accept)
            layout.addWidget(close_btn)

            details.exec()

    def copy_url_from_history(self, row: int):
        """Copy the URL from a history entry to clipboard."""
        if 0 <= row < len(self.download_history):
            entry = self.download_history[row]
            url = entry.get('url', '')
            if url:
                clipboard = QApplication.clipboard()
                clipboard.setText(url)
                # Show brief confirmation
                self.status_bar.showMessage(f"URL copied: {url[:50]}...", 3000)

    def redownload_from_history(self, row: int):
        """Re-download a file from history."""
        if 0 <= row < len(self.download_history):
            entry = self.download_history[row]

            url = entry['url']
            interface = entry['interface']
            speed_limit = entry.get('speed_limit')

            # Fetch current file size
            download_engine = DownloadEngine()
            file_size = 0
            try:
                info = download_engine.get_download_info(url, interface['ip'])
                if info.get('success'):
                    file_size = info.get('file_size', 0)
            except Exception:
                file_size = 0

            # Add to queue
            download_info = {
                'url': url,
                'interface': interface,
                'speed_limit': speed_limit,
                'file_size': file_size,
                'status': 'queued'
            }

            self.queued_downloads.append(download_info)
            self.update_queue_table()

            # Show confirmation
            QMessageBox.information(
                self,
                "Added to Queue",
                f"Added to download queue:\n{entry.get('filename', url)}"
            )

    def clear_download_history(self):
        """Clear all download history after confirmation."""
        if not self.download_history:
            QMessageBox.information(self, "Clear History", "History is already empty.")
            return

        reply = QMessageBox.question(
            self,
            "Clear History",
            f"Are you sure you want to clear {len(self.download_history)} history entries?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.download_history.clear()
            self.update_history_table()
            QMessageBox.information(self, "Clear History", "Download history cleared.")

    def export_download_history(self):
        """Export download history to a CSV file."""
        if not self.download_history:
            QMessageBox.information(self, "Export History", "No history to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Download History",
            "download_history.csv",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            import csv
            from datetime import datetime

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Write header
                writer.writerow([
                    "Date/Time", "Filename", "URL", "Interface", "IP Address",
                    "File Size (Bytes)", "Speed Limit (MB/s)", "File Path"
                ])

                # Write entries
                for entry in self.download_history:
                    try:
                        dt = datetime.fromisoformat(entry['completion_time'])
                        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        time_str = entry['completion_time']

                    writer.writerow([
                        time_str,
                        entry.get('filename', ''),
                        entry.get('url', ''),
                        entry['interface'].get('name', ''),
                        entry['interface'].get('ip', ''),
                        entry.get('file_size', 0),
                        entry.get('speed_limit', ''),
                        entry.get('filepath', '')
                    ])

            QMessageBox.information(
                self,
                "Export Successful",
                f"Exported {len(self.download_history)} entries to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export history:\n{str(e)}"
            )

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
                "speed_limit": dl["speed_limit"],
                "file_size": dl.get("file_size", 0)
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

        # Save download history
        state["download_history"] = []
        for entry in self.download_history:
            state["download_history"].append({
                'download_id': entry['download_id'],
                'url': entry['url'],
                'filename': entry['filename'],
                'filepath': entry['filepath'],
                'interface': entry['interface'],
                'file_size': entry['file_size'],
                'completion_time': entry['completion_time'],
                'speed_limit': entry['speed_limit']
            })

        return state

    def _restore_state(self):
        """Restore application state from saved file."""
        state = self.state_manager.load_state()

        if not state:
            return

        # Restore next_id
        self.download_manager.next_id = state.get("next_id", 1)

        # First, restore active downloads to the TOP of the queue (in reverse order to maintain original order)
        active_downloads_to_queue = []
        for dl in state.get("active_downloads", []):
            download_info = {
                "url": dl["url"],
                "interface": dl["interface"],
                "speed_limit": dl.get("speed_limit"),
                "file_size": dl.get("file_size", 0),
                "status": "queued"
            }
            active_downloads_to_queue.append(download_info)

        # Insert at the beginning of the queue (in reverse to preserve order)
        for download_info in reversed(active_downloads_to_queue):
            self.queued_downloads.insert(0, download_info)

        # Then, restore queued downloads (they go after the previously active ones)
        for dl in state.get("queued_downloads", []):
            download_info = {
                "url": dl["url"],
                "interface": dl["interface"],
                "speed_limit": dl.get("speed_limit"),
                "file_size": dl.get("file_size", 0),
                "status": "queued"
            }
            self.queued_downloads.append(download_info)

        # Restore download history
        for entry in state.get("download_history", []):
            self.download_history.append({
                'download_id': entry.get('download_id', 0),
                'url': entry['url'],
                'filename': entry['filename'],
                'filepath': entry['filepath'],
                'interface': entry['interface'],
                'file_size': entry.get('file_size', 0),
                'completion_time': entry['completion_time'],
                'speed_limit': entry.get('speed_limit')
            })

        # Update UI with restored state
        self.update_queue_table()
        self.update_active_downloads_table()
        self.update_history_table()


def main():
    """Main entry point for the application."""
    import sys

    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look

    window = DownloadManagerApp()
    window.show()

    sys.exit(app.exec())
