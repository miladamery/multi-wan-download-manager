# Multi-WAN Download Manager Implementation Plan

## Project Overview
Build a Windows download manager application that can download files through multiple network connections simultaneously by binding each download to a specific network interface/IP address.

**Technology Stack:**
- **Language:** Python 3.9+
- **GUI Framework:** PyQt6 (native Windows look and feel)
- **Network Detection:** psutil + netifaces
- **HTTP Binding:** requests-toolbelt (SourceAddressAdapter)
- **Download Management:** requests library with streaming

---

## Phase 1: Project Setup

### 1.1 Create Project Structure
```
C:\Users\Milad\Desktop\Downloader\
├── main.py                 # Application entry point
├── network_detector.py     # Network interface detection
├── download_engine.py      # Download logic with binding
├── download_manager_ui.py  # PyQt6 GUI
├── download_thread.py      # QThread for downloads
├── config.py               # Configuration and constants
├── requirements.txt        # Dependencies
└── README.md              # Documentation
```

### 1.2 Install Dependencies
```bash
pip install PyQt6 psutil netifaces requests requests-toolbelt
```

### 1.3 Create requirements.txt
```
PyQt6==6.6.1
psutil==5.9.8
netifaces==0.11.0
requests==2.31.0
requests-toolbelt==1.0.0
```

---

## Phase 2: Core Components

### 2.1 Network Interface Detection (`network_detector.py`)

**Purpose:** Detect all available network interfaces and their associated IPs.

**Key Functions:**
- `get_network_interfaces()` - Returns list of interfaces with:
  - Interface name (e.g., "Wi-Fi", "Ethernet", "Mobile Hotspot")
  - IPv4 address
  - Gateway
  - Connection status (connected/disconnected)
  - MAC address

**Implementation:**
- Use `psutil.net_if_addrs()` to get interface addresses
- Use `psutil.net_if_stats()` for connection status
- Use `netifaces.gateways()` for gateway information
- Filter for active interfaces with valid IPv4 addresses

**Example Output:**
```python
[
    {
        'name': 'Ethernet',
        'ip': '192.168.1.100',
        'gateway': '192.168.1.1',
        'status': 'connected',
        'mac': '00:11:22:33:44:55'
    },
    {
        'name': 'Wi-Fi 2',
        'ip': '192.168.1.101',
        'gateway': '192.168.1.1',
        'status': 'connected',
        'mac': '00:11:22:33:44:56'
    }
]
```

---

### 2.2 Download Engine with IP Binding (`download_engine.py`)

**Purpose:** Handle HTTP/HTTPS downloads bound to specific source IPs.

**Key Functions:**
- `create_bound_session(source_ip)` - Create requests Session bound to specific IP
- `download_file(url, source_ip, destination, progress_callback)` - Download with progress
- `get_download_info(url)` - Get file size, filename from URL headers

**Implementation Details:**
- Use `requests-toolbelt.SourceAddressAdapter` for source IP binding
- Support resuming downloads (using Range headers)
- Stream downloads to handle large files
- Calculate speed and ETA
- Support pause/resume/cancel operations

**Code Structure:**
```python
from requests_toolbelt.adapters.source import SourceAddressAdapter
import requests

def create_bound_session(source_ip):
    session = requests.Session()
    adapter = SourceAddressAdapter((source_ip, 0))
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def download_file(url, source_ip, dest_path, progress_callback):
    session = create_bound_session(source_ip)
    response = session.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))

    with open(dest_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if not is_running:
                break
            f.write(chunk)
            progress_callback(downloaded, total_size)
```

---

### 2.3 Download Thread (`download_thread.py`)

**Purpose:** QThread-based worker for handling downloads in background.

**Class: DownloadThread**

**Signals:**
- `progress_updated(int percentage, int downloaded, int total, float speed, str eta)`
- `download_completed(str filepath)`
- `download_failed(str error)`
- `download_paused()`

**Methods:**
- `__init__(url, source_ip, dest_path, speed_limit=None)`
- `run()` - Main download loop
- `pause()` - Pause download
- `resume()` - Resume download
- `cancel()` - Cancel download

**Speed Limiting:**
- Implement token bucket or simple sleep-based rate limiting
- Calculate chunk delay based on speed limit setting

---

### 2.4 GUI Components (`download_manager_ui.py`)

**Main Window Class: `DownloadManagerApp`**

**Layout Structure:**
```
┌─────────────────────────────────────────────────────────┐
│ Multi-WAN Download Manager                    [][_][X]  │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ Add New Download:                                        │
│ ┌─────────────────────────────────────────────────────┐ │
│ URL: [___________________________] [Paste] [Clear]     │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ Download Queue:                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ URL              | Interface   | Speed Limit | Actions│ │
│ │ ───────────────────────────────────────────────────── │ │
│ │ chunk1.rar       | Ethernet    | 2 MB/s     │ [X]    │ │
│ │ chunk2.rar       | Wi-Fi 2     | Unlimited  │ [X]    │ │
│ │ chunk3.rar       | Mobile ISP  | 1 MB/s     │ [X]    │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ Active Downloads:                                        │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Status | File          | Interface  | Progress     │ │
│ │ ───────────────────────────────────────────────────── │ │
│ │ ↓      | chunk1.rar    | Ethernet   | ████████░░ 80%│ │
│ │        |               | 2.1 MB/s   | ETA: 0:05:23  │ │
│ │ ↓      | chunk2.rar    | Wi-Fi 2    | ██████░░░░ 60%│ │
│ │        |               | 1.8 MB/s   | ETA: 0:08:45  │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ Controls:                                                │
│ [Start All] [Pause All] [Clear Completed] [Settings]    │
│                                                           │
│ Total Speed: 3.9 MB/s | Active: 2 | Completed: 5        │
└─────────────────────────────────────────────────────────┘
```

**Key Widgets:**
- `QLineEdit` - URL input
- `QTableWidget` - Download queue (columns: URL, Interface, Speed Limit, Remove button)
- `QTableWidget` - Active downloads (columns: Status, File, Interface, Progress bar, Speed, ETA)
- `QProgressBar` - Individual download progress
- `QComboBox` - Network interface selection per download
- `QSpinBox` - Speed limit control
- `QPushButton` - Start, Pause, Remove, Clear buttons
- `QStatusBar` - Total speed and statistics

---

### 2.5 Main Entry Point (`main.py`)

**Purpose:** Initialize QApplication and launch main window.

```python
import sys
from PyQt6.QtWidgets import QApplication
from download_manager_ui import DownloadManagerApp

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    window = DownloadManagerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
```

---

## Phase 3: Advanced Features

### 3.1 Queue Management
- Add multiple URLs to queue
- Reorder downloads (drag & drop or buttons)
- Auto-start next download when one completes

### 3.2 Speed Limiting
- Per-download speed limit (in MB/s)
- Global speed limit option
- Implement in download thread with throttling

### 3.3 Pause/Resume Support
- Pause individual downloads
- Resume using HTTP Range headers
- Save state to allow resuming after app restart

### 3.4 Connection Assignment Modes
1. **Manual Mode** - User selects interface for each download
2. **Auto Round-Robin** - Automatically distribute downloads across interfaces
3. **Smart Balancing** - Assign based on current load per interface

---

## Phase 4: Configuration (`config.py`)

```python
import os

# Application settings
APP_NAME = "Multi-WAN Download Manager"
APP_VERSION = "1.0.0"

# Download settings
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
MAX_CONCURRENT_DOWNLOADS = 10
DEFAULT_CHUNK_SIZE = 8192  # 8KB

# Speed settings
SPEED_LIMIT_UNLIMITED = 0  # MB/s
DEFAULT_SPEED_LIMIT = 2.0  # MB/s

# UI settings
REFRESH_INTERVAL = 500  # ms (update progress twice per second)
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 600

# Network settings
IP_CHECK_URL = "http://httpbin.org/ip"  # For verifying source IP
CONNECTION_TIMEOUT = 30  # seconds
READ_TIMEOUT = 60  # seconds
```

---

## Phase 5: Testing & Verification

### 5.1 Network Interface Detection Test
- Connect multiple ISPs (Ethernet + 2 mobile hotspots)
- Run application and verify all interfaces detected
- Check that IP addresses and gateways are correct

### 5.2 IP Binding Verification
- Download test files through each interface
- Verify using IP check service (httpbin.org/ip)
- Confirm traffic goes through correct interface

### 5.3 Multi-Download Test
- Add 3-4 download URLs
- Assign each to different interface
- Start all downloads simultaneously
- Verify all progress independently
- Check total speed = sum of individual speeds

### 5.4 Speed Limit Test
- Set speed limit to 1 MB/s
- Verify actual download speed stays near limit
- Test different limits per download

### 5.5 Pause/Resume Test
- Start download, pause at 50%
- Resume and verify continues from 50%
- Cancel and restart to verify clean state

---

## Implementation Order

1. **Setup Phase** (30 minutes)
   - Create project structure
   - Install dependencies
   - Create config.py

2. **Network Detection** (1 hour)
   - Implement network_detector.py
   - Test with multiple interfaces

3. **Download Engine** (2 hours)
   - Implement download_engine.py with IP binding
   - Test binding verification
   - Add progress tracking

4. **Download Thread** (1 hour)
   - Implement download_thread.py
   - Add pause/resume/cancel
   - Add speed limiting

5. **Basic GUI** (3 hours)
   - Implement main window layout
   - Add interface detection display
   - Add URL input and queue table

6. **Download Management** (2 hours)
   - Connect GUI to download threads
   - Display progress updates
   - Handle start/pause/remove actions

7. **Advanced Features** (2 hours)
   - Add speed limit controls
   - Implement queue management
   - Add auto-assignment mode

8. **Polish & Testing** (2 hours)
   - Error handling
   - UI refinements
   - Integration testing

**Total Estimated Time:** 13-15 hours

---

## Critical Files to Create

1. `requirements.txt` - Dependencies
2. `config.py` - Configuration constants
3. `network_detector.py` - Network interface detection
4. `download_engine.py` - Download with IP binding
5. `download_thread.py` - QThread download worker
6. `download_manager_ui.py` - PyQt6 main GUI
7. `main.py` - Application entry point
8. `README.md` - User documentation

---

## Potential Issues & Solutions

### Issue 1: Administrator Privileges
**Problem:** Some network operations require admin rights on Windows
**Solution:** Gracefully handle limited access, add manifest for admin elevation

### Issue 2: Interface Name Clarity
**Problem:** Windows shows interface GUIDs instead of friendly names
**Solution:** Use netsh commands to get friendly names, map to descriptions

### Issue 3: HTTPS Certificate Verification with Binding
**Problem:** Source IP binding may affect SSL verification
**Solution:** Test thoroughly, provide option to disable SSL verify if needed

### Issue 4: Mobile Hotspot Instability
**Problem:** Mobile connections may drop during download
**Solution:** Auto-retry logic, connection status monitoring, pause on disconnect

### Issue 5: Large File Handling
**Problem:** Very large files (50GB+) may cause memory issues
**Solution:** Always stream downloads, never load full file into memory

---

## Verification Checklist

Before considering the project complete:

- [ ] All network interfaces detected with correct IPs
- [ ] Can manually assign downloads to specific interfaces
- [ ] IP binding verified (requests come from correct IP)
- [ ] Multiple downloads run simultaneously
- [ ] Progress bars update accurately
- [ ] Speed limiting works correctly
- [ ] Pause/resume functionality works
- [ ] Cancel removes partial files
- [ ] Application survives interface disconnection
- [ ] Total speed = sum of individual speeds
- [ ] GUI is responsive during downloads
- [ ] Clean shutdown (all threads stopped)

---

## Future Enhancements (Optional)

- Download scheduling (start at specific time)
- Download history/logs
- Export/import download lists
- Bandwidth usage graphs
- Dark mode theme
- Multi-language support
- Portable version (no installation required)
- Command-line interface alternative
