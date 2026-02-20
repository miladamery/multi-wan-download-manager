"""
Bandwidth Usage Graph Widget for Multi-WAN Download Manager.

Provides real-time visualization of download speeds with per-interface
breakdown and total aggregated views.
"""

import logging
from collections import deque
from threading import Lock
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QRadioButton,
    QHBoxLayout,
    QGroupBox
)
from PyQt6.QtCore import Qt

import pyqtgraph as pg

# Configure logging
logger = logging.getLogger(__name__)


class BandwidthGraphWidget(QWidget):
    """
    Real-time bandwidth usage graph with per-interface and total views.

    Features:
    - Rolling buffer for 5 minutes of historical data (600 points at 500ms intervals)
    - Toggle between per-interface and total aggregated views
    - Statistics display (Current/Peak/Average speeds)
    - Thread-safe data access
    """

    # Color palette for interface curves
    INTERFACE_COLORS = [
        '#FF6B6B',  # Red
        '#4ECDC4',  # Teal
        '#45B7D1',  # Blue
        '#FFA07A',  # Light Salmon
        '#98D8C8',  # Mint
        '#F7DC6F',  # Yellow
        '#BB8FCE',  # Purple
        '#85C1E2',  # Light Blue
    ]

    def __init__(self, network_interfaces: List[dict], parent: Optional[QWidget] = None):
        """
        Initialize the bandwidth graph widget.

        Args:
            network_interfaces: List of interface dicts with 'name' and 'ip' keys
            parent: Parent widget
        """
        super().__init__(parent)

        self.network_interfaces = network_interfaces
        self.interface_names = {iface['ip']: iface['name'] for iface in network_interfaces}

        # Buffer configuration: 5 minutes at 500ms intervals = 600 data points
        self.buffer_duration_minutes = 5
        self.update_interval_seconds = 0.5  # 500ms
        self.max_data_points = int(self.buffer_duration_minutes * 60 / self.update_interval_seconds)

        # Data storage (rolling buffers)
        self.timestamps: deque = deque(maxlen=self.max_data_points)
        self.per_interface_speeds: Dict[str, deque] = {}  # {ip: deque}
        self.total_speeds: deque = deque(maxlen=self.max_data_points)

        # Thread safety
        self.data_lock = Lock()

        # View mode: 'per_interface' or 'total'
        self.view_mode = 'per_interface'

        # Statistics callback (set by parent)
        self.stats_callback = None

        # Setup UI
        self._setup_ui()

        logger.debug("BandwidthGraphWidget initialized with %d data point buffer", self.max_data_points)

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create PyQtGraph plot widget
        self.plot_widget = pg.PlotWidget()
        self._setup_graph()

        layout.addWidget(self.plot_widget)

    def _setup_graph(self):
        """Configure the PyQtGraph PlotWidget."""
        # Set white background
        self.plot_widget.setBackground('w')

        # Show grid
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # Configure axes
        self.plot_widget.setLabel('left', 'Speed', units='MB/s')
        self.plot_widget.setLabel('bottom', 'Time')
        self.plot_widget.setTitle('Bandwidth Usage')

        # Enable auto-range for y-axis
        self.plot_widget.enableAutoRange(axis='y')

        # Set y-axis to start from 0
        self.plot_widget.setYRange(0, 10)

        # Create legend for per-interface view
        self.legend = self.plot_widget.addLegend(offset=(10, 10))

        # Initialize curve storage
        self.interface_curves = {}  # {ip: PlotDataItem}
        self.total_curve = None  # PlotDataItem for total view

    def add_data_point(self, timestamp: float, interface_speeds: Dict[str, float], total_speed: float):
        """
        Add a new data point to the rolling buffer.

        Thread-safe method called from GUI timer.

        Args:
            timestamp: Unix timestamp
            interface_speeds: Dictionary mapping interface IP to speed in MB/s
            total_speed: Total aggregated speed in MB/s
        """
        with self.data_lock:
            # Add timestamp
            self.timestamps.append(timestamp)

            # Add per-interface speeds (create deques for new interfaces dynamically)
            for ip, speed in interface_speeds.items():
                if ip not in self.per_interface_speeds:
                    self.per_interface_speeds[ip] = deque(maxlen=self.max_data_points)
                self.per_interface_speeds[ip].append(speed)

            # Add total speed
            self.total_speeds.append(total_speed)

        # Update graph display
        self._update_graph()

    def reset_buffers(self):
        """Reset all data buffers. Called when there are no active downloads."""
        with self.data_lock:
            self.timestamps.clear()
            self.per_interface_speeds.clear()
            self.total_speeds.clear()

    def set_view_mode(self, mode: str):
        """
        Set the graph view mode.

        Args:
            mode: 'per_interface' or 'total'
        """
        if mode not in ('per_interface', 'total'):
            logger.warning("Invalid view mode: %s", mode)
            return

        self.view_mode = mode
        logger.debug("View mode changed to: %s", mode)
        self._update_graph()

    def set_stats_callback(self, callback):
        """
        Set the callback function for updating statistics display.

        Args:
            callback: Function that receives statistics dict as argument
        """
        self.stats_callback = callback

    def _update_graph(self):
        """Update the graph display based on current view mode."""
        try:
            if self.view_mode == 'per_interface':
                self._render_per_interface_view()
            else:
                self._render_total_view()

            # Update statistics
            self._update_statistics()

        except Exception as e:
            logger.error("Error updating graph: %s", e)

    def _render_per_interface_view(self):
        """Render per-interface breakdown view."""
        with self.data_lock:
            if not self.timestamps:
                return

            # Get data snapshot
            timestamps = list(self.timestamps)
            active_interfaces = {}

            # Find interfaces with data
            for ip, speeds in self.per_interface_speeds.items():
                if len(speeds) > 0:
                    # Get non-zero speeds only
                    active_interfaces[ip] = list(speeds)

        # Clear existing curves
        self.plot_widget.clear()
        self.legend = self.plot_widget.addLegend(offset=(10, 10))
        self.interface_curves.clear()

        # Create curve for each active interface
        color_idx = 0
        for ip, speeds in active_interfaces.items():
            if not speeds or len(speeds) != len(timestamps):
                continue

            # Get interface name
            interface_name = self.interface_names.get(ip, ip)

            # Create plot curve
            color = self.INTERFACE_COLORS[color_idx % len(self.INTERFACE_COLORS)]
            curve = self.plot_widget.plot(
                timestamps,
                speeds,
                pen=pg.mkPen(color=color, width=2),
                name=f"{interface_name} ({ip})"
            )

            self.interface_curves[ip] = curve
            color_idx += 1

        # Update x-axis to show relative time
        self._update_x_axis()

    def _render_total_view(self):
        """Render total aggregated view."""
        with self.data_lock:
            if not self.timestamps:
                return

            timestamps = list(self.timestamps)
            total_speeds = list(self.total_speeds)

        # Clear existing curves
        self.plot_widget.clear()
        self.interface_curves.clear()

        # Create single curve for total
        if total_speeds and len(total_speeds) == len(timestamps):
            self.total_curve = self.plot_widget.plot(
                timestamps,
                total_speeds,
                pen=pg.mkPen(color='#2E86AB', width=3),
                name='Total Bandwidth'
            )

        # Update x-axis to show relative time
        self._update_x_axis()

    def _update_x_axis(self):
        """Update x-axis to show relative time (minutes ago)."""
        with self.data_lock:
            if not self.timestamps:
                return

            current_time = self.timestamps[-1]

            # Set x-axis range to show 5 minutes window
            # Format as "X:XX" (minutes and seconds ago)
            if len(self.timestamps) > 1:
                self.plot_widget.setXRange(
                    current_time - self.buffer_duration_minutes * 60,
                    current_time
                )

    def _calculate_statistics(self) -> dict:
        """
        Calculate Current/Peak/Average statistics.

        Only uses the last 60 seconds of data and filters outliers.

        Returns:
            Dictionary with statistics based on current view mode
        """
        with self.data_lock:
            # Use only recent data (last 60 seconds = 120 data points at 500ms intervals)
            recent_data_points = 120

            if self.view_mode == 'per_interface':
                stats = {}
                for ip, speeds in self.per_interface_speeds.items():
                    if len(speeds) > 0:
                        # Get only recent data
                        recent_speeds = list(speeds)[-recent_data_points:]

                        # Filter out zeros and unrealistic outliers (>100 MB/s for typical consumer connections)
                        valid_speeds = [s for s in recent_speeds if 0 < s <= 100]

                        if valid_speeds:
                            stats[ip] = {
                                'current': speeds[-1],
                                'peak': max(valid_speeds),
                                'average': sum(valid_speeds) / len(valid_speeds)
                            }
                            # Add interface name for display
                            stats[ip]['name'] = self.interface_names.get(ip, ip)
                return {'per_interface': stats}
            else:
                # Total view
                if len(self.total_speeds) > 0:
                    # Get only recent data
                    recent_speeds = list(self.total_speeds)[-recent_data_points:]

                    # Filter out zeros and unrealistic outliers
                    valid_speeds = [s for s in recent_speeds if 0 < s <= 100]

                    if valid_speeds:
                        return {
                            'total': {
                                'current': self.total_speeds[-1],
                                'peak': max(valid_speeds),
                                'average': sum(valid_speeds) / len(valid_speeds)
                            }
                        }

        return {}

    def _update_statistics(self):
        """Update the statistics display via callback."""
        stats = self._calculate_statistics()

        if self.stats_callback:
            self.stats_callback(stats)
