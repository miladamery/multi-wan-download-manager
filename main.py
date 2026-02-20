"""
Multi-WAN Download Manager

A Windows download manager application that can download files through
multiple network connections simultaneously by binding each download
to a specific network interface/IP address.

This is the main entry point for the application.
"""
import sys
import os

# Add the current directory to the path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from download_manager_ui import DownloadManagerApp
import config


def main():
    """
    Main entry point for the Multi-WAN Download Manager application.

    Initializes the Qt application and launches the main window.
    """
    # Setup logging
    config.setup_logging()

    # Create QApplication instance
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')  # Modern, cross-platform look

    # Create and show main window
    window = DownloadManagerApp()
    window.show()

    # Start the event loop
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
