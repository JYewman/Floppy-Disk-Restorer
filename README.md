# Floppy Workbench

**Professional Floppy Disk Analysis & Recovery Tool**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: 2.0.0](https://img.shields.io/badge/version-2.0.0-green.svg)](https://github.com/JYewman/Floppy-Disk-Restorer/releases)

A comprehensive floppy disk analysis and recovery application using **Greaseweazle V4.1** for flux-level disk access. Floppy Workbench provides professional-grade tools for disk preservation, recovery, and analysis.

![Floppy Workbench Screenshot](screenshots/Screenshot_1.png)

## Features

### Flux-Level Analysis

- **Real-time flux waveform visualization** - Oscilloscope-style view of magnetic transitions
- **Pulse width histogram** - Analyze MFM timing distribution
- **Signal quality metrics** - SNR, jitter, and weak bit detection
- **Automatic format detection** - MFM, FM, GCR, and non-standard formats
- **Copy protection detection** - Forensic analysis of protection schemes

### Advanced Data Recovery

- **Multi-capture recovery** - Read same track multiple times for statistical bit voting
- **PLL tuning** - Find optimal decoder parameters for marginal disks
- **Convergence-based recovery** - Automatically stop when no further improvement
- **Bit-slip correction** - Recover from synchronization errors
- **Targeted recovery** - Focus on bad sectors while preserving good data

### Disk Operations

- **Scan** - Full surface analysis with sector-by-sector health mapping
- **Format** - Write fresh formatted disk with verification
- **Restore** - Multi-pass recovery with configurable intensity
- **Write Image** - Write disk images to physical media
- **Batch Verify** - Verify multiple disks in sequence

### Diagnostics

- **Head alignment measurement** - Detect azimuth errors and track centering issues
- **RPM stability monitoring** - Real-time drive speed analysis
- **Drive health assessment** - Comprehensive drive diagnostics

### Professional Workbench GUI

- **Single-page workbench layout** - All controls accessible at once
- **Circular sector map** - Visual disk health with zoom and selection (2,880 sectors)
- **Tabbed analytics panel** - Overview, flux, errors, recovery, diagnostics
- **Keyboard shortcuts** - Fast operation access
- **Dark/Light themes** - Comfortable viewing in any environment
- **Native system sounds** - Audio feedback on Windows, Linux, and macOS

### Supported Disk Formats

#### IBM PC (MFM)

- 360KB 5.25" DD (40 cylinders, 9 sectors/track)
- 720KB 3.5" DD (80 cylinders, 9 sectors/track)
- 1.2MB 5.25" HD (80 cylinders, 15 sectors/track)
- 1.44MB 3.5" HD (80 cylinders, 18 sectors/track)

#### Amiga (Amiga MFM)

- 880KB DD (80 cylinders, 11 sectors/track)
- 1.76MB HD (80 cylinders, 22 sectors/track)

#### Atari ST (MFM)

- 360KB DD (80 cylinders, 9 sectors/track)
- 720KB DD (80 cylinders, 9 sectors/track)

#### BBC Micro

- DFS 100KB/200KB (FM encoding)
- ADFS 640KB/800KB (MFM encoding)

### Import/Export

- **Sector images**: IMG, IMA, DSK formats
- **Flux images**: SCP (SuperCard Pro), HFE (HxC Floppy Emulator)
- **Reports**: PDF and HTML with embedded charts

## Hardware Requirements

### Required

- **Greaseweazle V4.1** (or compatible V4, F7 models)
- **3.5" HD floppy drive** (PC-type, 34-pin interface)
- **USB connection** to host computer

### Where to Get Greaseweazle

- Official project: [Greaseweazle on GitHub](https://github.com/keirf/greaseweazle)
- Pre-built units available from various retro computing vendors

### Supported Drive Types

- 3.5" HD (1.44MB) - Primary support
- 3.5" DD (720KB) - Supported
- 5.25" drives - Experimental support

## Software Requirements

- **Python 3.10** or higher
- **PyQt6** (installed automatically)
- **Greaseweazle library** (installed automatically)
- **Operating System**: Windows, Linux, or macOS

## Installation

### Using pip (Recommended)

```bash
pip install floppy-workbench
```

### Development Installation

```bash
# Clone the repository
git clone https://github.com/JYewman/Floppy-Disk-Restorer.git
cd Floppy-Disk-Restorer

# Install with Poetry
poetry install

# Or with pip in development mode
pip install -e .
```

### Dependencies

The following packages are installed automatically:

- `PyQt6` - GUI framework
- `PyQt6-Charts` - Chart widgets
- `greaseweazle` - Hardware communication
- `numpy` - Numerical operations
- `bitarray` - Efficient bit operations
- `crcmod` - CRC calculations
- `reportlab` - PDF generation
- `pydantic` - Settings validation

## Quick Start

### 1. Connect Hardware

1. Connect your Greaseweazle to a USB port
2. Connect a 3.5" floppy drive to the Greaseweazle
3. Power on the drive (some drives require external power)

### 2. Launch Application

```bash
# Using the installed command
floppy-workbench

# Or using Python module
python -m floppy_formatter
```

### 3. Connect to Device

1. Click **"Connect"** in the Drive Control panel
2. Select drive unit (usually Drive 0)
3. The motor will spin up and RPM will be displayed

### 4. Insert Disk and Scan

1. Insert a floppy disk into the drive
2. Click **"Scan"** or press `Ctrl+S`
3. Watch the sector map fill in with disk health

### 5. Analyze and Recover

- **View flux data**: Switch to the Flux tab in the analytics panel
- **Recover bad sectors**: Click "Restore" and configure recovery options
- **Export disk image**: Click "Export" to save IMG/SCP/HFE files

## Usage Guide

### Scanning Disks

The scan operation reads all sectors and displays their status:

- **Green**: Good sector, data readable
- **Red**: Bad sector, CRC error or unreadable
- **Yellow**: Weak sector, marginal signal
- **Blue**: Currently being read

**Scan modes:**

- **Quick**: Sample tracks (fast overview)
- **Standard**: All sectors, single read
- **Thorough**: Multi-read verification

### Formatting Disks

Format operations write fresh data to the disk:

- **Standard**: Normal format with verification
- **Low-level Refresh**: Rewrite all sectors to refresh magnetic signal
- **Secure Erase**: Multiple overwrite passes

### Recovery Operations

For disks with bad sectors:

1. **Scan first** to identify bad sectors
2. **Select recovery mode**:
   - **Fixed Passes**: Run exactly N format passes (1-100)
   - **Convergence Mode**: Run until bad count stabilizes
3. **Enable Multi-Capture** for statistical recovery
4. **Set recovery level**:
   - **Standard**: Traditional multi-pass recovery
   - **Aggressive**: Adds PLL tuning
   - **Forensic**: Maximum effort, all techniques

### Flux Analysis

The Flux tab provides low-level analysis:

- **Waveform view**: See individual flux transitions
- **Histogram**: Analyze pulse width distribution
- **Quality metrics**: Signal-to-noise ratio, timing jitter

### Exporting Images

Save disk contents to files:

- **IMG/IMA**: Standard sector images (for working disks)
- **SCP**: SuperCard Pro flux format (preserves raw flux)
- **HFE**: HxC Floppy Emulator format

## Configuration

Settings are stored in platform-specific locations:

- **Windows**: `%APPDATA%/FloppyWorkbench/settings.json`
- **Linux**: `~/.config/floppy-workbench/settings.json`
- **macOS**: `~/Library/Application Support/FloppyWorkbench/settings.json`

Example configuration:

```json
{
  "device": {
    "default_drive": 0,
    "motor_timeout": 30,
    "seek_speed": "standard"
  },
  "display": {
    "theme": "dark",
    "color_scheme": "default",
    "animate_operations": true
  },
  "recovery": {
    "default_passes": 5,
    "convergence_threshold": 3,
    "multi_capture_revolutions": 5
  }
}
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Start Scan |
| `Ctrl+Shift+F` | Start Format |
| `Ctrl+R` | Start Recovery |
| `Ctrl+Shift+A` | Start Analysis |
| `Space` | Pause/Resume |
| `Escape` | Cancel Operation |
| `Ctrl+Shift+C` | Connect/Disconnect |
| `Ctrl+M` | Toggle Motor |
| `Ctrl+0` | Seek to Track 0 |

## Troubleshooting

### "No Greaseweazle found"

1. Check USB connection
2. Verify Greaseweazle LED is lit
3. On Linux, ensure user is in `plugdev` group:

   ```bash
   sudo usermod -a -G plugdev $USER
   ```

4. Try running with sudo: `sudo floppy-workbench`

### "No disk detected"

1. Check disk is fully inserted
2. Verify drive is connected to Greaseweazle
3. Check drive power (some drives need external 5V/12V)
4. Try a known-good disk

### "Read errors on all sectors"

1. Clean the drive heads
2. Try a different disk
3. Check for correct drive type (HD vs DD)
4. Inspect disk for visible damage

### WSL2 USB Passthrough

If using Windows Subsystem for Linux:

1. Install [USBIPD-WIN](https://github.com/dorssel/usbipd-win)
2. In PowerShell (Admin):

   ```powershell
   usbipd list
   usbipd bind --busid <BUSID>
   usbipd attach --wsl --busid <BUSID>
   ```

3. Verify in WSL: `lsusb | grep -i greaseweazle`

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

### Development Setup

```bash
# Clone and install in development mode
git clone https://github.com/JYewman/Floppy-Disk-Restorer.git
cd Floppy-Disk-Restorer
poetry install --with dev

# Run tests
poetry run pytest

# Run linting
poetry run flake8 src/ --max-line-length=100
poetry run ruff check src/
poetry run black --check src/
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

- **Greaseweazle** - Keir Fraser's amazing floppy controller project
- **PyQt6** - Riverbank Computing
- **Feather Icons** - Icon set by Cole Bemis
- **Floppy Disk Preservation Community** - For keeping magnetic media alive

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

---

**Made with love for the floppy disk preservation community**
