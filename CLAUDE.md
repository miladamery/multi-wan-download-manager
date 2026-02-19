# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-WAN Download Manager - A Windows PyQt6 application that downloads files through multiple network interfaces simultaneously by binding each download to a specific source IP address. This allows combining bandwidth from multiple connections (Ethernet, Wi-Fi, Mobile Hotspot) when downloading multi-part files.

## Common Commands

### Running the Application
```bash
python main.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Building Portable Executable
```bash
pyinstaller downloader.spec
```
Creates a standalone `dist/MultiWANDownloader.exe` (~43 MB) that can run without Python installation. The executable is portable - it creates `Downloads` and `.multiwan_downloader` folders next to the exe file.

For development/debugging builds with console output:
```bash
pyinstaller --onefile --console --name MultiWANDownloader main.py
```

### Testing Network Detection
```bash
python network_detector.py
```
Prints all detected network interfaces with their IP addresses, gateways, MAC addresses, and connection status.

### Testing IP Binding Verification
```bash
python download_engine.py
```
Tests that downloads are correctly bound to each detected interface by verifying against httpbin.org/ip.

## Architecture

### Core Components

**Entry Point**
- `main.py` - Simple PyQt6 application launcher that initializes `DownloadManagerApp`

**Network Layer** (`network_detector.py`)
- `get_network_interfaces()` - Returns all interfaces with name, IP, gateway, status, MAC
- `get_connected_interfaces()` - Filters to only connected (isup) interfaces
- `get_interfaces_with_internet()` - Filters out virtual adapters (VMware, VirtualBox, etc.) and tests actual internet connectivity via HTTP request
- Uses `psutil` for interface enumeration and `netifaces` for gateway detection
- Virtual adapter filtering uses pattern blacklist: `vEthernet`, `VMware`, `VMnet`, `VirtualBox`, `Loopback`, `TAP`, `OpenVPN`, `Hyper-V`, `Bluetooth`, `docker`

**Download Engine** (`download_engine.py`)
- `DownloadEngine` class handles HTTP/HTTPS downloads with source IP binding
- Key method: `create_bound_session(source_ip)` - Uses `requests-toolbelt.SourceAddressAdapter` to bind to specific IP
- `download_file()` - Streaming download with progress callbacks, pause/resume support, speed limiting
- Resume support via HTTP Range headers (checks if partial file exists)
- Speed limiting via `time.sleep()` based on chunk size and target MB/s
- `get_download_info()` - HEAD request to get file size, filename from Content-Disposition

**Threading** (`download_thread.py`)
- `DownloadThread` - QThread worker that wraps `DownloadEngine` for non-blocking downloads
- Signals: `progress_updated`, `download_completed`, `download_failed`, `download_paused`
- `DownloadManager` class - Manages multiple download threads, tracks status (queued/downloading/paused/cancelled)
- One download per interface limitation enforced in GUI's `start_all_downloads()`

**GUI** (`download_manager_ui.py`)
- PyQt6 `DownloadManagerApp` main window
- Two tables: `queue_table` (pending downloads) and `active_table` (running downloads)
- Interface selection dropdown auto-populates with internet-connected interfaces
- Auto-starts next queued download for an interface when current download completes/fails (`_start_next_download_for_interface`)
- Progress updates via QTimer every 500ms (configurable)

**State Persistence** (`state_manager.py`)
- Saves application state to state file with auto-backup (keeps last 10 backups)
- Auto-saves on application close
- Restores queued and active downloads on restart (active downloads go back to queue for manual restart)
- Paths are portable-aware: uses exe directory when frozen, user home when running as Python script

### Configuration (`config.py`)

Key settings:
- `PORTABLE_BASE_DIR` - Auto-detected base path (exe dir when frozen, user home otherwise)
- `DEFAULT_DOWNLOAD_DIR` - Default save location (relative to base dir)
- `MAX_CONCURRENT_DOWNLOADS` - Max simultaneous downloads (10)
- `DEFAULT_CHUNK_SIZE` - Streaming chunk size (8KB)
- `REFRESH_INTERVAL` - GUI update frequency (500ms)
- `CONNECTION_TIMEOUT` / `READ_TIMEOUT` - Request timeouts
- `SSL_VERIFY` - Set to `False` by default (disables SSL verification warnings)
- `STATE_DIR` / `STATE_FILE` - State persistence location (relative to base dir)
- `INTERNET_TEST_URL` - URL for connectivity testing (httpbin.org/ip)

**Portable Path Handling:** The `_get_portable_path()` function detects if running as a frozen executable (`sys.frozen`) and adjusts paths accordingly. This allows the app to create `Downloads` and `.multiwan_downloader` folders alongside the exe for true portability.

## IP Binding Implementation Details

The core mechanism for binding to a specific network interface:

```python
from requests_toolbelt.adapters.source import SourceAddressAdapter

session = requests.Session()
adapter = SourceAddressAdapter((source_ip, 0))  # Port 0 = OS chooses
session.mount('http://', adapter)
session.mount('https://', adapter)
```

This ensures all HTTP/HTTPS requests from this session originate from the specified source IP, routing through the corresponding network interface.

## Download Flow

1. User adds URL to queue, selects interface and optional speed limit
2. Click "Start All" - GUI starts max 1 download per interface (rest remain queued)
3. For each download:
   - `DownloadThread` created and started
   - Thread calls `DownloadEngine.download_file()` with bound session
   - Progress emitted via signals every ~1 second
   - GUI updates progress bars via QTimer polling
4. On completion:
   - Download removed from active list
   - Next queued download for same interface auto-started
   - User notified with file path

## Pause/Resume Mechanics

- Pause: Sets `is_paused=True` in engine, download loop sleeps while paused
- Resume: Sets `is_paused=False`, loop continues from same position
- Cancel: Sets `is_running=False`, closes session, removes partial file
- True resume (after app restart) uses HTTP Range headers to continue from partial file

## Testing IP Binding

Use the test in `download_engine.py:394-426`:
```python
verify_source_ip(source_ip)  # Makes request to httpbin.org/ip and checks returned origin
```

This is useful for verifying that the selected interface is actually being used for outbound traffic.

## Building for Distribution

### PyInstaller Configuration

The project uses PyInstaller with a custom spec file (`downloader.spec`) to create a single-file Windows executable.

**Key spec file settings:**
- `--onefile` mode: Single exe that self-extracts to temp dir at runtime
- `--windowed` mode: No console window (set `console=True` in spec for debugging)
- Hidden imports: PyQt6 modules, requests-toolbelt, psutil, netifaces, urllib3

### Build Output Structure

```
Downloader/
├── build/downloader/     # Build artifacts (can be deleted)
├── dist/
│   └── MultiWANDownloader.exe   # <-- The portable executable (~43 MB)
└── downloader.spec       # PyInstaller configuration
```

### Distribution Checklist

When distributing the application:
1. Copy only `dist/MultiWANDownloader.exe`
2. No other files needed - all dependencies bundled
3. Runs on any Windows 10+ machine without Python
4. Creates `Downloads` and `.multiwan_downloader` folders next to exe on first run

### Rebuilding After Code Changes

After modifying Python code:
```bash
cd C:\Users\Milad\Desktop\Downloader
pyinstaller downloader.spec --clean
```

The `--clean` flag forces a full rebuild (useful if changes aren't reflected).
