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
- Tabbed URL input: "Single URL" and "Batch URLs (Round-Robin)" tabs
- Two tables: `queue_table` (pending downloads) and `active_table` (running downloads)
- Queue table columns: URL, Interface, Speed Limit, **Size**, Actions
- Active downloads table columns: Status, File, Interface, **Size**, Progress, Speed|ETA, Actions
- Interface selection dropdown auto-populates with internet-connected interfaces
- Batch URL import from file with automatic round-robin interface distribution
- File size display via HEAD requests (`DownloadEngine.get_download_info()`)
- Human-readable file size formatting (`_format_file_size()`)
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

### Single URL Downloads
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

### Batch URL Downloads (Round-Robin)
1. User imports multiple URLs (text area or file import)
2. `add_batch_urls_to_queue()` distributes URLs across interfaces:
   - For each URL: `interface_index = url_index % interface_count`
   - Creates `DownloadEngine` instance to fetch file sizes via HEAD requests
   - Stores `file_size` in download_info dict
3. Click "Start All" - Same flow as single URL downloads
4. Queue table displays: URL, Interface, Speed Limit, Size (human-readable format)
5. Active downloads table displays: Status, File, Interface, Size, Progress, Speed|ETA, Actions

## Pause/Resume Mechanics

- Pause: Sets `is_paused=True` in engine, download loop sleeps while paused
- Resume: Sets `is_paused=False`, loop continues from same position
- Cancel: Sets `is_running=False`, closes session, removes partial file
- True resume (after app restart) uses HTTP Range headers to continue from partial file

## Round-Robin URL Distribution

### Algorithm
The round-robin distribution in `add_batch_urls_to_queue()`:

```python
available_interfaces = self.network_interfaces  # List of interface dicts
interface_count = len(available_interfaces)

for index, url in enumerate(valid_urls):
    interface_index = index % interface_count  # Modulo for cycling
    assigned_interface = available_interfaces[interface_index]
    # Create download_info and add to queue
```

### Example Distribution
With 3 interfaces (Ethernet, Wi-Fi, Mobile) and 6 URLs:
- URL 0 (index 0) → 0 % 3 = 0 → Ethernet
- URL 1 (index 1) → 1 % 3 = 1 → Wi-Fi
- URL 2 (index 2) → 2 % 3 = 2 → Mobile
- URL 3 (index 3) → 3 % 3 = 0 → Ethernet (wraps)
- URL 4 (index 4) → 4 % 3 = 1 → Wi-Fi
- URL 5 (index 5) → 5 % 3 = 2 → Mobile

### Batch Import Features
- **File Import**: `import_urls_from_file()` reads URLs from text files
- **Comment Support**: Lines starting with `#` are treated as comments
- **Validation**: Each URL is validated before adding to queue
- **Error Handling**: Gracefully handles invalid URLs and network errors
- **File Size Fetching**: Uses HEAD requests to get file sizes before adding to queue

## File Size Handling

### Fetching File Sizes
`DownloadEngine.get_download_info()` uses HTTP HEAD requests:
```python
response = session.head(url, timeout=30, allow_redirects=True)
file_size = int(response.headers.get('content-length', 0))
```

### Display Formatting
`_format_file_size()` converts bytes to human-readable format:
```python
def _format_file_size(self, size_bytes: int) -> str:
    if size_bytes == 0:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"
```

Examples:
- 500 bytes → "500.0 B"
- 2,048 bytes → "2.0 KB"
- 2,097,152 bytes → "2.0 MB"
- 2,147,483,648 bytes → "2.0 GB"

### Storage
- File sizes are stored in `download_info['file_size']` (in bytes)
- Persisted to state file for queue restoration
- Displayed in both Queue table and Active Downloads table

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

## Table Structures

### Queue Table (`queue_table`)
| Column | Index | Description |
|--------|-------|-------------|
| URL | 0 | Download URL |
| Interface | 1 | Network interface name and IP |
| Speed Limit | 2 | Per-download speed limit (MB/s) or "Unlimited" |
| Size | 3 | File size in human-readable format (B/KB/MB/GB/TB) |
| Actions | 4 | Remove button |

### Active Downloads Table (`active_table`)
| Column | Index | Description |
|--------|-------|-------------|
| Status | 0 | Icon: ↓ (downloading), || (paused), ✓ (completed) |
| File | 1 | Filename extracted from URL |
| Interface | 2 | Source IP address |
| Size | 3 | Total file size in human-readable format |
| Progress | 4 | Progress bar with percentage |
| Speed \| ETA | 5 | Current speed (MB/s) and estimated time remaining |
| Actions | 6 | Pause/Resume/Remove buttons |

## Important Implementation Notes

### Lambda Closure Bug Fix
When connecting signals in loops, always capture loop variables by value using default arguments:

```python
# WRONG - All buttons will use the last download_id
button.clicked.connect(lambda: self.pause_download(download_id))

# CORRECT - Each button captures its own download_id
button.clicked.connect(lambda checked, did=download_id: self.pause_download(did))
```

This is critical for the Pause/Resume buttons in the Active Downloads table. The `checked` parameter is required because `QPushButton.clicked()` signal sends it.

### State Persistence
File sizes are persisted to state files:
```python
# Saving
"file_size": dl.get("file_size", 0)

# Restoring (defaults to 0 for backward compatibility)
"file_size": dl.get("file_size", 0)
```
