# Multi-WAN Download Manager

A Windows download manager application that can download files through multiple network connections simultaneously by binding each download to a specific network interface/IP address.

## Features

- **Multi-Interface Support**: Download files through different network interfaces (Ethernet, Wi-Fi, Mobile Hotspot) simultaneously
- **IP Binding**: Each download is bound to a specific source IP address
- **Download Queue**: Add multiple URLs to a queue and start them together
- **Progress Tracking**: Real-time progress bars, speed display, and ETA calculation
- **Speed Limiting**: Set per-download speed limits in MB/s
- **Pause/Resume**: Pause and resume individual downloads
- **Network Detection**: Automatically detects all connected network interfaces

## Requirements

- Windows 10 or later
- Python 3.9 or higher
- Multiple network interfaces (e.g., Ethernet + Mobile Hotspot) for full functionality

## Installation

### 1. Clone or Download this Project

```bash
cd C:\Users\Milad\Desktop\Downloader
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

The required packages are:
- PyQt6 - GUI framework
- psutil - System and network information
- netifaces - Network interface detection
- requests - HTTP library
- requests-toolbelt - Source IP binding for HTTP requests

### 3. Run the Application

```bash
python main.py
```

## Usage

### Basic Workflow

1. **Add Download URLs**
   - Enter a URL in the "Add New Download" section
   - Click "Paste" to paste from clipboard
   - Select the network interface to use
   - Optionally set a speed limit
   - Click "Add to Queue"

2. **Start Downloads**
   - Add all your URLs to the queue
   - Click "Start All" to begin downloading

3. **Monitor Progress**
   - View real-time progress in the "Active Downloads" section
   - See current speed and ETA for each download
   - Total speed shown in status bar

4. **Control Downloads**
   - Click "Pause" to pause individual downloads
   - Click "Resume" to continue paused downloads
   - Click "Pause All" to pause all active downloads

### Setting Up Multiple Network Connections

To use multiple network interfaces simultaneously:

1. **Connect Ethernet** - Your primary wired connection
2. **Enable Mobile Hotspot** - Use your phone's mobile data
3. **Connect Wi-Fi** - Connect to a secondary Wi-Fi network

The application will automatically detect all connected interfaces and display them in the interface dropdown.

### Example Use Cases

#### Download File Parts Simultaneously

If you have a large file split into multiple parts (e.g., `chunk1.rar`, `chunk2.rar`, `chunk3.rar`):

1. Add `chunk1.rar` → Select Ethernet
2. Add `chunk2.rar` → Select Wi-Fi
3. Add `chunk3.rar` → Select Mobile Hotspot
4. Click "Start All"

Each part will download through a different connection, effectively combining their speeds.

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

- `DEFAULT_DOWNLOAD_DIR` - Default save location for downloads
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

- [ ] Download scheduling (start at specific time)
- [ ] Download history and logs
- [ ] Export/import download lists
- [ ] Bandwidth usage graphs
- [ ] Dark mode theme
- [ ] Multi-language support
- [ ] Command-line interface alternative
- [ ] Automatic interface selection (round-robin, load balancing)

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
