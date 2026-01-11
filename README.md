# USB Floppy Formatter

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](https://www.linux.org/)
[![Tests](https://img.shields.io/badge/tests-124%20passing-brightgreen.svg)](tests/)

> Professional floppy disk recovery and restoration tool with advanced multi-read recovery, convergence detection, and real-time visualization.

A powerful, terminal-based tool for recovering, formatting, and diagnosing 1.44MB floppy disks. Featuring intelligent recovery algorithms and TUI interface built with Textual.

## ✨ Features

### 🔧 **Advanced Recovery Modes**
- **Multi-Read Recovery** - Statistical data recovery using multiple read attempts with majority voting (inspired by SpinRite's DynaStat)
- **Convergence Mode** - Automatically detects optimal recovery point and stops when bad sectors stabilize
- **Targeted Recovery** - Intelligently formats only tracks containing bad sectors, preserving good data
- **Multi-Pass Formatting** - Rotating magnetic patterns (0x55, 0xAA, 0xFF, 0x00) to restore weak magnetic domains

### 📊 **Real-Time Monitoring**
- **Convergence Tracking** - View pass-by-pass statistics with trend indicators (↓ improving, ↑ degrading, → stable)
- **Time Estimates** - Accurate ETA calculations with elapsed/remaining time display
- **Progress Analytics** - Detailed statistics on recovery rates, sector counts, and patterns used

### 🖥️ **Beautiful TUI Interface**
- Modern terminal UI built with [Textual](https://textual.textualize.io/)
- Intuitive menu-driven navigation
- Color-coded sector maps (🟩 Good | 🟥 Bad | ⚫ Unscanned)
- Comprehensive reporting with sector-by-sector details

### 🛠️ **Low-Level Operations**
- Direct block device access for sector-level operations
- Works with severely damaged disks (even when boot sector is unreadable)
- Native Linux device APIs (`/dev/sdX`)
- Full geometry detection and validation

## 📸 Screenshots

_Coming soon - Screenshots of scan visualization, recovery progress, and convergence tracking_

## 🚀 Quick Start

### Requirements

- **Linux** (native or WSL2)
- **Python 3.10+**
- **Root privileges** (required for raw device access)
- **USB floppy drive** with 1.44MB disk
  - Any TEAC USB Floppy Drive should work

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/USB-Floppy-Formatter.git
cd USB-Floppy-Formatter

# Install dependencies
pip install -e .
```

### Basic Usage

```bash
# Launch the TUI (requires sudo)
sudo python -m floppy_formatter

# Or run directly if installed system-wide
sudo floppy-format
```

## 📖 Usage Guide

### 1. Scan Disk

Perform a comprehensive surface scan to identify bad sectors:

```bash
sudo python -m floppy_formatter
# Select: Scan Disk → Choose Device → Start Scan
```

Features:
- Real-time sector map visualization
- Track-by-track progress display
- Detailed error classification
- Comprehensive scan report with statistics

### 2. Format Disk

Low-level format with bad sector detection:

```bash
# From main menu: Format Disk → Choose Device → Configure Options
```

Options:
- **Fixed Passes**: Execute a specific number of formatting passes (1-20)
- **Convergence Mode**: Automatically stop when optimal recovery is achieved
- **Verify After Format**: Confirm all sectors are readable

### 3. Restore Disk (Recovery)

Advanced recovery for degraded disks with intelligent algorithms:

```bash
# From main menu: Restore Disk (Recovery) → Choose Device → Configure Recovery
```

#### Recovery Options:

**Basic Settings:**
- **Fixed Pass Mode**: Execute exactly N passes (predictable duration)
- **Convergence Mode** ⭐: Smart recovery that stops when sectors stabilize (recommended)

**Advanced Recovery:**
- **Targeted Recovery** ⚡: Only format tracks with bad sectors (10-50x faster)
- **Multi-Read Mode** 🔬: Aggressive statistical recovery with majority voting
  - Configurable attempts per sector (10-2000)
  - Uses byte-level statistical analysis
  - Can recover marginally readable sectors

**Report Options:**
- Detailed sector-by-sector analysis
- Track-by-track status maps
- Hex dumps of bad sectors
- Save report to file

## 🔬 Recovery Algorithms

### Multi-Read Recovery

Statistical data recovery that attempts to read bad sectors multiple times:

1. **Multiple Read Attempts**: Reads the same sector 10-2000 times (configurable)
2. **Byte-Level Voting**: Compares results byte-by-byte across all attempts
3. **Statistical Reconstruction**: Uses majority voting to determine most likely correct value
4. **Success Detection**: Returns reconstructed data even if no single read was perfect

Similar to commercial tools like SpinRite's DynaStat technique, but implemented from scratch.

### Convergence Detection

Smart algorithm that automatically detects when recovery has reached optimal point:

**Stops When:**
- Same bad sector count for 3 consecutive passes (converged)
- No improvement in last 5 passes (plateau)
- Maximum passes reached (safety limit: 50)

**Prevents:**
- Unnecessary disk wear from over-formatting
- Wasted time on physically damaged sectors
- Infinite recovery loops

**Displays:**
- Pass-by-pass statistics with delta calculations
- Trend indicators (improving/degrading/stable)
- Recovery rate percentages

### Targeted Recovery

Intelligent recovery that focuses only on problematic areas:

1. **Track Identification**: Identifies which tracks contain bad sectors
2. **Selective Formatting**: Only formats affected tracks (not entire disk)
3. **Data Preservation**: Good tracks remain untouched
4. **Performance**: 10-50x faster than full disk recovery

Example: If only 50 sectors across 3 tracks are bad, formats 3 tracks instead of 160.

## 🛠️ Technical Details

### Device Operations

All operations use native Linux APIs:

| Operation | Method | Details |
|-----------|--------|---------|
| **Device Discovery** | `/sys/block/` scanning | Finds removable 1.44MB devices |
| **Device Open** | `os.open()` | Flags: `O_DIRECT \| O_SYNC` |
| **Sector Read/Write** | `os.lseek()` + `os.read()`/`os.write()` | 512-byte sectors |
| **Geometry Detection** | `ioctl(HDIO_GETGEO)` | Fallback: `BLKGETSIZE64` |
| **Cache Flush** | `fsync()` + `ioctl(BLKFLSBUF)` | Ensures writes are committed |

### Disk Geometry

Standard 1.44MB floppy disk:

```
Cylinders:        80
Heads:            2
Sectors/Track:    18
Bytes/Sector:     512
Total Sectors:    2,880
Total Capacity:   1,440 KB (1.44 MB)
```

### Pattern Writing

Multi-pass recovery uses rotating patterns to restore magnetic domains:

| Pass | Pattern | Binary | Purpose |
|------|---------|--------|---------|
| 0 | `0x55` | `01010101` | Alternating low |
| 1 | `0xAA` | `10101010` | Alternating high |
| 2 | `0xFF` | `11111111` | All bits set |
| 3 | `0x00` | `00000000` | All bits clear |
| 4+ | Sequence | (repeating) | Progressive patterns |

Each pattern exercises different magnetic states to help restore weak domains.

### Error Classification

Intelligent error classification for diagnostic purposes:

```python
FATAL_ERRORS = {
    EACCES,   # Permission denied
    ENODEV,   # No such device
    EROFS,    # Write-protected
    ENXIO,    # Device not configured
}

DATA_ERRORS = {
    EIO,      # Input/output error
    EBADMSG,  # Bad message (CRC)
    ENODATA,  # No data available
}
```

## 🧪 Testing

Comprehensive test suite with 124 tests:

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v           # 77 unit tests
pytest tests/integration/ -v    # 47 integration tests

# Run with coverage
pytest tests/ --cov=floppy_formatter --cov-report=html
```

**Test Coverage:**
- ✅ Geometry calculations and validation
- ✅ Recovery algorithm logic
- ✅ Sector I/O operations
- ✅ Error classification
- ✅ Format/recovery workflows
- ✅ Thread safety and cancellation
- ✅ Progress tracking

## 🐧 Platform Support

### Linux (Native)
✅ **Full Support** - All features work natively
- Direct `/dev/sdX` device access
- No restrictions on low-level operations
- Optimal performance

### WSL2 (Windows Subsystem for Linux)
✅ **Full Support** - Requires USB passthrough
- Install `usbipd-win` on Windows host
- Attach USB device to WSL2
- All features work as on native Linux

#### WSL2 Setup:

```powershell
# Windows side (PowerShell as Administrator)
winget install usbipd
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
```

```bash
# WSL2 side
lsblk  # Verify device appears (e.g., /dev/sdb)
sudo python -m floppy_formatter
```

### Windows (Native)
❌ **Not Supported** - Windows blocks USB writes
- Windows 10/11 restrict raw writes to USB devices at kernel level
- Security feature to prevent boot sector malware
- No workaround available without kernel modifications

**Note:** Internal ISA/FDC floppy controllers work on Windows, but USB floppy drives do not.

## 🐛 Troubleshooting

### Permission Denied
```
Error: Permission denied (errno 13)
```
**Solution**: Run with `sudo`
```bash
sudo python -m floppy_formatter
```

### Device Not Found
```
Error: No floppy drive found
```
**Solutions**:
1. Verify disk is inserted
2. Check device appears: `lsblk`
3. For WSL2: Ensure USB attached with `usbipd attach`

### Write Protected
```
Error: Read-only file system (errno 30)
```
**Solution**: Disable write protection (slide the write-protect tab on disk)

### I/O Errors During Scan
```
Error: Input/output error (errno 5)
```
**Expected Behavior**: This is normal for damaged disks
- Run full scan to identify all bad sectors
- Use **Restore Disk** with **Convergence Mode** to attempt recovery
- Enable **Multi-Read Mode** for aggressive recovery of marginal sectors

### WSL2 USB Device Not Appearing

1. Check Windows side: `usbipd list`
2. Verify device is bound: `usbipd bind --busid <BUSID>`
3. Attach to WSL: `usbipd attach --wsl --busid <BUSID>`
4. Check WSL side: `lsblk` and `dmesg | tail`

## 📚 Python API

### Basic Usage

```python
from floppy_formatter import (
    open_device,
    close_device,
    get_disk_geometry,
    scan_all_sectors,
)

# Open device (requires root)
fd = open_device("/dev/sdb", read_only=True)

try:
    # Get geometry
    geometry = get_disk_geometry(fd)
    print(f"Disk: {geometry.cylinders}C/{geometry.heads}H/{geometry.sectors_per_track}S")

    # Scan disk
    scan_result = scan_all_sectors(fd, geometry)
    print(f"Bad sectors: {len(scan_result.bad_sectors)}")

finally:
    close_device(fd)
```

### Advanced Recovery

```python
from floppy_formatter import (
    open_device,
    close_device,
    get_disk_geometry,
    recover_disk,
)

fd = open_device("/dev/sdb", read_only=False)

try:
    geometry = get_disk_geometry(fd)

    # Convergence mode with multi-read recovery
    stats = recover_disk(
        fd,
        geometry,
        convergence_mode=True,
        max_passes=50,
        multiread_mode=True,
        multiread_attempts=100,
    )

    print(f"Recovery: {stats.sectors_recovered}/{stats.initial_bad_sectors}")
    print(f"Success rate: {stats.get_recovery_rate():.1f}%")
    print(f"Converged after {stats.passes_executed} passes")

finally:
    close_device(fd)
```

## ⚠️ Safety Notes

- ⚠️ **Data Loss Warning**: Formatting operations **WILL ERASE ALL DATA** on the disk
- 🔒 **Root Privileges Required**: Use caution when running as root
- ✅ **Verify Device**: Always double-check you've selected the correct device before formatting
- 💾 **Backup First**: If disk contains important data, attempt recovery before formatting

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the test suite: `pytest tests/ -v`
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/USB-Floppy-Formatter.git
cd USB-Floppy-Formatter

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linters
black src/
flake8 src/
mypy src/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Textual](https://textual.textualize.io/) by Textualize - Modern TUI framework
- Inspired by classic tools like SpinRite and Norton Disk Doctor

## 💬 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/JYewman/USB-Floppy-Formatter/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/JYewman/USB-Floppy-Formatter/discussions)

---

**Made with ❤️ for the floppy disk preservation community**

*Remember: Always backup important data before attempting recovery operations!*
