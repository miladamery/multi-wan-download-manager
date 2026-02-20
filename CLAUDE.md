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
- PyQt6 `DownloadManagerApp` main window with **tabbed interface**: "Downloads" and "History" tabs
- **Downloads Tab**: Contains all download management features
  - Tabbed URL input: "Single URL" and "Batch URLs (Round-Robin)" tabs
  - Two tables: `queue_table` (pending downloads) and `active_table` (running downloads)
- Queue table columns: URL, Interface, Speed Limit, **Size**, Actions
  - Actions: **Move Up (↑)**, **Move Down (↓)**, **Remove**
- Active downloads table columns: Status, File, Interface, **Size**, Progress, Speed|ETA, Actions
  - Downloading: **Pause** button
  - Paused: **Resume** and **To Queue** buttons
- **Resizable columns**: All table columns use `Interactive` mode, allowing users to drag borders to adjust widths
- Interface selection dropdown auto-populates with internet-connected interfaces
- Batch URL import from file with automatic round-robin interface distribution
- File size display via HEAD requests (`DownloadEngine.get_download_info()`)
- Human-readable file size formatting (`_format_file_size()`)
- Auto-starts next queued download for an interface when current download completes/fails (`_start_next_download_for_interface`)
- Progress updates via QTimer every 500ms (configurable)
- **Smart resume**: "Start All" button resumes paused downloads before starting new ones from queue
- **History Tab**: Download history with full details and management features

**State Persistence** (`state_manager.py`)
- Saves application state to state file with auto-backup (keeps last 10 backups)
- Auto-saves on application close
- **Queue restoration**: Queued downloads remain in queue when app is reopened
- **Active downloads restoration**: Active/paused downloads are moved to the **top of the queue** when app is reopened
  - This ensures previously active downloads get priority when user clicks "Start All"
  - Downloads resume from where they left off (supports partial file resume via HTTP Range requests)
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

### Interface Column Display

Both Queue and Active Downloads tables show the interface in the same format: `"InterfaceName (IP)"`

**Queue table** (`update_queue_table()`):
```python
interface_text = f"{download['interface']['name']} ({download['interface']['ip']})"
```

**Active Downloads table** (`update_active_downloads_table()`):
```python
# Look up interface name from source_ip
source_ip = download['source_ip']
interface_name = None
for iface in self.network_interfaces:
    if iface['ip'] == source_ip:
        interface_name = iface['name']
        break

if interface_name:
    interface_text = f"{interface_name} ({source_ip})"
else:
    interface_text = source_ip  # Fallback
```

This consistency makes it easy to identify which interface each download is using.

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
| Actions | 4 | **Move Up (↑)**, **Move Down (↓)**, **Remove** buttons |

**Actions**:
- Move Up (↑): Moves item up in queue (disabled for first row)
- Move Down (↓): Moves item down in queue (disabled for last row)
- Remove: Deletes item from queue

### Active Downloads Table (`active_table`)
| Column | Index | Description |
|--------|-------|-------------|
| Status | 0 | Icon: ↓ (downloading), || (paused), ✓ (completed) |
| File | 1 | Filename extracted from URL |
| Interface | 2 | Network interface name and IP (consistent with queue table) |
| Size | 3 | Total file size in human-readable format |
| Progress | 4 | Progress bar with percentage |
| Speed \| ETA | 5 | Current speed (MB/s) and estimated time remaining |
| Actions | 6 | Pause, Resume, To Queue buttons |

**Actions** (dynamic based on status):
- Downloading: **Pause** button
- Paused: **Resume** and **To Queue** buttons

### History Table (`history_table`)
| Column | Index | Description |
|--------|-------|-------------|
| Date/Time | 0 | Completion date and time (YYYY-MM-DD HH:MM:SS) |
| File | 1 | Downloaded filename |
| Interface | 2 | Network interface name and IP |
| Size | 3 | File size in human-readable format |
| URL | 4 | Full download URL (shown completely, resizable) |
| Actions | 5 | **View**, **Copy URL**, **Re-download** buttons |

**Actions**:
- View: Opens details dialog with full download information
- Copy URL: Copies URL to clipboard
- Re-download: Adds URL back to queue with same settings

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

**Active Downloads Restoration Logic:**
When the application is reopened, active downloads are not restored as active/paused downloads. Instead:
1. They are moved to the **top of the queue** (inserted at position 0 in reverse order)
2. Regular queued downloads are appended after them
3. This ensures previously active downloads get priority when user clicks "Start All"

Example from `_restore_state()`:
```python
# First, restore active downloads to the TOP of the queue
active_downloads_to_queue = []
for dl in state.get("active_downloads", []):
    download_info = {...}
    active_downloads_to_queue.append(download_info)

# Insert at the beginning (in reverse to preserve order)
for download_info in reversed(active_downloads_to_queue):
    self.queued_downloads.insert(0, download_info)

# Then, restore queued downloads (they go after)
for dl in state.get("queued_downloads", []):
    download_info = {...}
    self.queued_downloads.append(download_info)
```

### Column Resizing
All table columns use `Interactive` resize mode to allow user resizing:
```python
header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Interactive)
```

Additionally, initial column widths are set for better defaults:
```python
self.queue_table.setColumnWidth(0, 400)  # URL
self.queue_table.setColumnWidth(1, 150)  # Interface
# etc...
```

The last column stretches to fill remaining space:
```python
header.setStretchLastSection(True)
```

### Resume/Start All Functionality
The `start_all_downloads()` method has been enhanced to:
1. **First**: Resume all paused downloads via `self.download_manager.resume_all()`
2. **Then**: Start new downloads from the queue (existing logic)

This ensures that when user clicks "Start All":
- Any paused downloads are resumed first
- Then new downloads from the queue are started (respecting the 1-download-per-interface limit)

**Important**: The `resume_download()` method in `DownloadManager` now checks if the thread is running:
```python
if not thread.isRunning():
    # Thread hasn't started yet, start it now
    thread.start()
else:
    # Thread is running but paused, just resume
    thread.resume()
```

This fix was necessary because restored downloads were created but threads were never started, causing resume to fail.

## Download History

### Overview
The download history feature tracks all completed downloads, providing a permanent record of download activity. History is stored in the state file and persists across application restarts.

### History Data Structure
Each history entry contains:
```python
{
    'download_id': int,              # Unique download ID
    'url': str,                      # Download URL
    'filename': str,                 # Downloaded filename
    'filepath': str,                 # Full path to downloaded file
    'interface': {
        'name': str,                 # Interface name (e.g., "Ethernet")
        'ip': str                    # Interface IP address
    },
    'file_size': int,                # File size in bytes
    'completion_time': str,          # ISO format timestamp
    'speed_limit': float or None     # Speed limit in MB/s
}
```

### History Table Columns
| Column | Index | Description |
|--------|-------|-------------|
| Date/Time | 0 | Completion date and time (YYYY-MM-DD HH:MM:SS) |
| File | 1 | Downloaded filename |
| Interface | 2 | Network interface name and IP |
| Size | 3 | File size in human-readable format |
| URL | 4 | Full download URL (shown completely) |
| Actions | 5 | View, Copy URL, Re-download buttons |

### History Features

**View Details** (`view_history_details(row)`):
- Opens dialog showing complete download information
- Displays: File, URL, File Path, Interface, Size, Speed Limit, Completion Time
- If file exists: "Open File" and "Open Folder" buttons available
- Uses `os.startfile()` to open files/folders on Windows

**Copy URL** (`copy_url_from_history(row)`):
- Copies full URL to system clipboard
- Shows brief confirmation in status bar
- Useful for sharing or re-downloading in other tools

**Re-download** (`redownload_from_history(row)`):
- Adds URL back to download queue
- Uses same interface and speed limit as original download
- Fetches current file size via HEAD request before adding
- Shows confirmation message with filename

**Clear History** (`clear_download_history()`):
- Removes all history entries with confirmation dialog
- Shows count of entries to be deleted
- Action requires explicit confirmation
- Cannot be undone

**Export History** (`export_download_history()`):
- Exports all history entries to CSV file
- Columns: Date/Time, Filename, URL, Interface, IP, File Size (Bytes), Speed Limit, File Path
- User selects destination via file dialog
- Shows success/error message with entry count

### State Persistence
History is saved in the state file under the `download_history` key:
```python
# Saving (in _get_current_state)
state["download_history"] = []
for entry in self.download_history:
    state["download_history"].append({...})

# Restoring (in _restore_state)
for entry in state.get("download_history", []):
    self.download_history.append({...})
```

**Unlimited Retention**: History is never automatically deleted. Users must manually clear history.

### History Capture Point
History entries are created in `on_download_completed()` **before** showing the completion message:
```python
# Create history entry
history_entry = {
    'download_id': download_id,
    'url': download['url'],
    'filename': os.path.basename(filepath),
    'filepath': filepath,
    'interface': {...},
    'file_size': thread.total_bytes,
    'completion_time': datetime.now().isoformat(),
    'speed_limit': thread.speed_limit
}

# Add to history (newest first)
self.download_history.insert(0, history_entry)
self.update_history_table()
```

## Queue Management

### Queue Reordering

**Purpose**: Allow users to change download priority in the queue by reordering items.

**Implementation**:
- `move_queue_up(row)`: Swaps item with previous position (disabled for row 0)
- `move_queue_down(row)`: Swaps item with next position (disabled for last row)

**Button States**:
- **Move Up (↑)**: Disabled on first row (`row == 0`)
- **Move Down (↓)**: Disabled on last row (`row == len(queued_downloads) - 1`)

**Algorithm**: Simple swap operation:
```python
# Move up
self.queued_downloads[row], self.queued_downloads[row - 1] = \
    self.queued_downloads[row - 1], self.queued_downloads[row]

# Move down
self.queued_downloads[row], self.queued_downloads[row + 1] = \
    self.queued_downloads[row + 1], self.queued_downloads[row]
```

**State Persistence**: Queue order is automatically preserved in the state file since `queued_downloads` is a list. Order is maintained when saving/restoring.

**Impact**: Reordered items start in new order when "Start All" is clicked. This affects which downloads get priority for each interface.

### Move Paused Downloads to Queue

**Purpose**: Allow users to return paused downloads to the queue for re-prioritization or later resumption.

**Implementation** (`move_paused_to_queue(download_id)`):

1. **Capture download info**:
   - URL, interface (name + IP), speed limit
   - Progress info (total bytes, downloaded bytes)
   - File path (for partial file resume)

2. **Cancel the download**:
   - Calls `cancel_download()` to stop the thread
   - **Preserves partial file** on disk for resume

3. **Remove from active**:
   - Deletes from `active_downloads` dictionary

4. **Add to queue**:
   - Appends to `queued_downloads` list
   - Maintains original settings

5. **Update UI**:
   - Refreshes both active downloads and queue tables
   - Updates status bar
   - Shows confirmation message

**Partial File Preservation**: When moved to queue, the partial download file remains on disk. When the download is resumed from the queue, the `DownloadEngine` detects the existing file and uses HTTP Range headers to continue from the saved position.

**Example Flow**:
```python
# User pauses 500MB download at 30%
# User clicks "To Queue"
# Download cancelled, partial file (~150MB) preserved
# User reorders queue to prioritize
# User starts queue
# Download resumes from 30%, not from beginning
```

**Use Cases**:
- Defer a download to process other items first
- Re-prioritize downloads without losing progress
- Pause and move to queue when bandwidth is needed elsewhere
- Recover from network issues by moving to end of queue

