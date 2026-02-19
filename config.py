"""
Configuration settings for Multi-WAN Download Manager
"""
import os
import sys


# ============================================================================
# PORTABLE PATH DETECTION
# ============================================================================
def _get_portable_path():
    """
    Get base path for portable application.

    When running as a frozen executable (PyInstaller), use the directory
    containing the exe. When running as a Python script, use user's home dir.

    Returns:
        str: Base directory for downloads and state files
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled exe - use exe directory for truly portable build
        return os.path.dirname(sys.executable)
    else:
        # Running as Python script - use user home
        return os.path.expanduser("~")


PORTABLE_BASE_DIR = _get_portable_path()


# ============================================================================
# APPLICATION SETTINGS
# ============================================================================
APP_NAME = "Multi-WAN Download Manager"
APP_VERSION = "1.0.0"


# ============================================================================
# DOWNLOAD SETTINGS
# ============================================================================
DEFAULT_DOWNLOAD_DIR = os.path.join(PORTABLE_BASE_DIR, "Downloads")
MAX_CONCURRENT_DOWNLOADS = 10
DEFAULT_CHUNK_SIZE = 8192  # 8KB - size of chunks for streaming downloads


# ============================================================================
# SPEED SETTINGS
# ============================================================================
SPEED_LIMIT_UNLIMITED = 0  # MB/s (0 means unlimited)
DEFAULT_SPEED_LIMIT = 2.0  # MB/s - default per-download speed limit


# ============================================================================
# UI SETTINGS
# ============================================================================
REFRESH_INTERVAL = 500  # ms - GUI update frequency (twice per second)
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 600
WINDOW_TITLE = f"{APP_NAME} v{APP_VERSION}"


# ============================================================================
# NETWORK SETTINGS
# ============================================================================
# URL to verify which IP address is being used for requests
IP_CHECK_URL = "http://httpbin.org/ip"

CONNECTION_TIMEOUT = 30  # seconds - timeout for establishing connection
READ_TIMEOUT = 60  # seconds - timeout for reading data

# SSL certificate verification
# Set to False to bypass SSL certificate verification errors
# WARNING: Disabling SSL verification is less secure, but needed for some servers
SSL_VERIFY = False

# Internet connectivity testing
# Used to filter interfaces that have actual internet access
INTERNET_TEST_URL = "http://httpbin.org/ip"
INTERNET_TEST_TIMEOUT = 3  # seconds - timeout for connectivity test


# ============================================================================
# DOWNLOAD RETRY SETTINGS
# ============================================================================
MAX_RETRY_ATTEMPTS = 3  # Number of times to retry failed downloads
RETRY_DELAY = 5  # seconds - wait between retry attempts


# ============================================================================
# THREAD SETTINGS
# ============================================================================
THREAD_SLEEP_INTERVAL = 0.1  # seconds - how often to check for pause/cancel


# ============================================================================
# STATE PERSISTENCE SETTINGS
# ============================================================================
STATE_DIR = os.path.join(PORTABLE_BASE_DIR, ".multiwan_downloader")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
BACKUP_DIR = os.path.join(STATE_DIR, "backups")
AUTO_SAVE_INTERVAL = 30  # seconds - periodic auto-save interval
