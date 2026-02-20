# Multi-WAN Download Manager

A Windows download manager application that can download files through multiple network connections simultaneously by binding each download to a specific network interface/IP address.

## Features

- **Multi-Interface Support**: Download files through different network interfaces (Ethernet, Wi-Fi, Mobile Hotspot) simultaneously
- **IP Binding**: Each download is bound to a specific source IP address
- **Download Queue**: Add multiple URLs to a queue and start them together
- **Batch URL Import**: Import multiple URLs from text file with automatic round-robin interface distribution
- **Progress Tracking**: Real-time progress bars, speed display, and ETA calculation
- **File Size Display**: Shows file sizes in human-readable format (B, KB, MB, GB, TB) for queued and active downloads
- **Speed Limiting**: Set per-download speed limits in MB/s
- **Pause/Resume**: Pause and resume individual downloads or all downloads at once
- **Move Paused to Queue**: Return paused downloads to queue for re-prioritization without losing progress
- **Smart Resume**: "Start All" resumes paused downloads before starting new ones from queue
- **State Persistence**: Application saves queue and active downloads; paused downloads return to top of queue on restart
- **Download History**: View complete download history with details, export to CSV, copy URLs, and re-download
- **Resizable Columns**: Drag column borders to adjust table widths to your preference
- **Network Detection**: Automatically detects all connected network interfaces
- **Real-time Bandwidth Graphs**: Monitor bandwidth usage with per-interface breakdown and total aggregated view
  - 5-minute rolling history with collapsible graph
  - Current/Peak/Average speed statistics
  - Toggle between per-interface and total views
  - Statistics remain visible when graph is collapsed

## Requirements

- Windows 10 or later
- Python 3.9 or higher (if running from source)
- Multiple network interfaces (e.g., Ethernet + Mobile Hotspot) for full functionality

## Installation

### Option 1: Download Pre-Built Executable (Recommended)

1. Go to the [Releases](https://github.com/miladamery/multi-wan-download-manager/releases) page
2. Download the latest `MultiWANDownloader.exe`
3. Run the executable - no Python installation needed!

The executable is portable and creates `Downloads` and `.multiwan_downloader` folders next to the exe file.

### Option 2: Run from Source

#### 1. Clone or Download this Project

```bash
cd C:\Users\Milad\Desktop\Downloader
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

The required packages are:
- PyQt6 - GUI framework
- pyqtgraph - Real-time data visualization and graphing
- psutil - System and network information
- netifaces - Network interface detection
- requests - HTTP library
- requests-toolbelt - Source IP binding for HTTP requests

### 3. Run the Application

```bash
python main.py
```

### Building the Executable

If you want to build the executable yourself:

#### Local Build
```bash
pip install pyinstaller
pyinstaller downloader.spec
```
The executable will be in `dist/MultiWANDownloader.exe`.

#### CI/CD Automatic Builds
This project uses GitHub Actions to automatically build executables:
- Builds are triggered on every push to `main` branch
- Releases are created automatically when you push version tags (e.g., `v1.0.0`)

To create a new release:
```bash
git tag v1.0.0
git push origin v1.0.0
```
The executable will be automatically built and attached to the GitHub Release.

## Usage

### Basic Workflow

#### Single URL Downloads

1. **Add Download URLs**
   - Switch to "Single URL" tab
   - Enter a URL in the "Add New Download" section
   - Click "Paste" to paste from clipboard
   - Select the network interface to use
   - Optionally set a speed limit
   - Click "Add to Queue"

#### Batch URL Downloads (Round-Robin Distribution)

1. **Import Multiple URLs**
   - Switch to "Batch URLs (Round-Robin)" tab
   - Option 1: Paste multiple URLs (one per line) in the text area
   - Option 2: Click "Import from File" to load URLs from a text file
   - Set a speed limit (applies to all URLs in batch)
   - Click "Add All to Queue (Round-Robin)"

2. **Automatic Distribution**
   - URLs are automatically distributed across all available interfaces
   - Uses round-robin algorithm for even distribution
   - Example: With 3 interfaces (Ethernet, Wi-Fi, Mobile) and 6 URLs:
     - URL 1 → Ethernet
     - URL 2 → Wi-Fi
     - URL 3 → Mobile
     - URL 4 → Ethernet (wraps around)
     - URL 5 → Wi-Fi
     - URL 6 → Mobile

2. **Start Downloads**
   - Add all your URLs to the queue
   - Click "Start All" to begin downloading
   - One download per interface starts simultaneously
   - Remaining downloads stay queued and auto-start when interfaces free up

3. **Monitor Progress**
   - View real-time progress in the "Active Downloads" section
   - See file size, progress percentage, speed, and ETA for each download
   - Total speed shown in status bar

4. **Control Downloads**
   - Click "Pause" to pause individual downloads
   - Click "Resume" to continue paused downloads
   - Click "Pause All" to pause all active downloads
   - Click "Start All" to resume paused downloads and start new ones from queue

### Download History

The application maintains a complete history of all completed downloads:

**View History Tab**:
- Switch to the "History" tab to see all completed downloads
- Shows: Date/Time, File name, Interface used, File size, and URL
- Sortable by date (newest first)

**History Actions**:
- **View Details**: Click "View" button to see full download information including file path
- **Copy URL**: Copy download URL to clipboard for sharing
- **Re-download**: Add URL back to queue with same interface and speed settings
- **Clear History**: Remove all history entries (requires confirmation)
- **Export to CSV**: Export entire history to CSV file for record-keeping

**History Features**:
- History persists across application restarts
- Export includes: Date, Filename, URL, Interface, IP, File Size, Speed Limit, File Path
- Re-download fetches current file size before adding to queue
- View Details shows file path with "Open File" and "Open Folder" buttons if file exists

### State Persistence

The application automatically saves your downloads when closed:

- **Queued downloads**: Remain in queue when app is reopened
- **Active/Paused downloads**: Moved to the **top of the queue** when app is reopened
  - This ensures previously active downloads get priority when you click "Start All"
  - Downloads resume from where they left off (supports partial file resume via HTTP Range requests)
- **File sizes**: Preserved across sessions

**Example workflow:**
1. Add 6 downloads, click "Start All" → 2 start (1 per interface), 4 stay queued
2. Click "Pause All" → active downloads pause
3. Close application
4. Reopen application → Queue shows: [2 previously active, 4 queued] in that order
5. Click "Start All" → The 2 previously active downloads start first, then the others follow

### Setting Up Multiple Network Connections

To use multiple network interfaces simultaneously:

1. **Connect Ethernet** - Your primary wired connection
2. **Enable Mobile Hotspot** - Use your phone's mobile data
3. **Connect Wi-Fi** - Connect to a secondary Wi-Fi network

The application will automatically detect all connected interfaces and display them in the interface dropdown.

### Example Use Cases

#### Download File Parts Simultaneously (Manual Interface Selection)

If you have a large file split into multiple parts (e.g., `chunk1.rar`, `chunk2.rar`, `chunk3.rar`):

**Method 1: Manual Interface Selection (Single URL tab)**
1. Add `chunk1.rar` → Select Ethernet
2. Add `chunk2.rar` → Select Wi-Fi
3. Add `chunk3.rar` → Select Mobile Hotspot
4. Click "Start All"

Each part will download through a different connection, effectively combining their speeds.

**Method 2: Round-Robin Distribution (Batch URLs tab)**
1. Create a text file `urls.txt` with:
   ```
   https://example.com/file1.rar
   https://example.com/file2.rar
   https://example.com/file3.rar
   ```
2. Switch to "Batch URLs (Round-Robin)" tab
3. Click "Import from File" and select `urls.txt`
4. Set speed limit (optional)
5. Click "Add All to Queue (Round-Robin)"
6. Click "Start All"

URLs are automatically distributed across all available interfaces in round-robin fashion.

#### Download Multiple Files Efficiently

When downloading multiple files from different sources:
- Use batch URL import to add all URLs at once
- Round-robin distribution ensures even load across interfaces
- File sizes are displayed before downloading (when available from server)
- Monitor all downloads in unified Active Downloads table

#### Verify IP Binding

To verify that downloads are using the correct interface:

```bash
python network_detector.py
```

This will display all detected network interfaces with their IP addresses.

To verify actual IP binding:

```bash
python download_engine.py
```

This will test each interface and confirm that requests originate from the correct IP address.

## Project Structure

```
Downloader/
├── main.py                 # Application entry point
├── network_detector.py     # Network interface detection
├── download_engine.py      # Download logic with IP binding
├── download_thread.py      # QThread for background downloads
├── download_manager_ui.py  # PyQt6 GUI
├── config.py               # Configuration and constants
├── requirements.txt        # Dependencies
├── IMPLEMENTATION_PLAN.md  # Implementation documentation
└── README.md              # This file
```

## Configuration

Edit `config.py` to customize:

- `DEFAULT_DOWNLOAD_DIR` - Default save location for downloads (defaults to Windows Downloads folder: `C:\Users\{Username}\Downloads`)
- `MAX_CONCURRENT_DOWNLOADS` - Maximum simultaneous downloads
- `DEFAULT_CHUNK_SIZE` - Size of download chunks (8KB default)
- `REFRESH_INTERVAL` - GUI update frequency (500ms default)
- `CONNECTION_TIMEOUT` - Request timeout (30 seconds)

## Troubleshooting

### No Network Interfaces Detected

- Make sure you have at least one active network connection
- Run as Administrator if interfaces are not being detected
- Check Windows firewall and network settings

### Downloads Not Using Selected Interface

- Verify IP binding using: `python download_engine.py`
- Some VPN software may interfere with source IP binding
- Check that the interface has a valid IP address assigned

### Download Speed Issues

- Check that the interface actually has bandwidth available
- Try adjusting the speed limit setting
- Verify the server supports multiple connections from different IPs

## Limitations

- **HTTP/HTTPS Only**: FTP and other protocols are not supported
- **Windows Only**: Currently designed for Windows systems
- **Server-Side Limits**: Some servers may limit download speed per connection
- **Resume Support**: Depends on server support for Range requests

## Future Enhancements

Potential features for future versions:

- [x] Automatic interface selection (round-robin) - **IMPLEMENTED**
- [x] Batch URL import from file - **IMPLEMENTED**
- [x] File size display - **IMPLEMENTED**
- [x] Resizable table columns - **IMPLEMENTED**
- [x] Smart state persistence with queue priority - **IMPLEMENTED**
- [x] Resume all downloads functionality - **IMPLEMENTED**
- [x] Download history and logs - **IMPLEMENTED**
- [ ] Download scheduling (start at specific time)
- [ ] Bandwidth usage graphs
- [ ] Dark mode theme
- [ ] Multi-language support
- [ ] Command-line interface alternative
- [ ] Advanced load balancing strategies (weighted by interface speed)

## License

This project is provided as-is for educational and personal use.

## Contributing

Contributions are welcome! Areas for improvement:

- Bug fixes
- Performance optimizations
- UI/UX enhancements
- Additional protocol support
- Cross-platform compatibility (Linux, macOS)

## Support

For issues or questions:

1. Check this README for common solutions
2. Review `IMPLEMENTATION_PLAN.md` for technical details
3. Test network detection: `python network_detector.py`
4. Test IP binding: `python download_engine.py`
