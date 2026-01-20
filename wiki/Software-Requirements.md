# Software Requirements

This page details all software requirements and dependencies for Floppy Disk Workbench.

## Table of Contents

- [Operating Systems](#operating-systems)
- [Python Requirements](#python-requirements)
- [Core Dependencies](#core-dependencies)
- [Optional Dependencies](#optional-dependencies)
- [Development Dependencies](#development-dependencies)

---

## Operating Systems

### Supported Platforms

| Platform | Version | Status |
|----------|---------|--------|
| **Windows** | 10, 11 | Fully Supported |
| **Linux** | Ubuntu 20.04+, Fedora 35+, Arch | Fully Supported |
| **macOS** | 11 (Big Sur)+ | Supported |

### Platform-Specific Notes

#### Windows

- Windows 10 version 1903 or later recommended
- USB drivers typically work out-of-box
- May need Zadig for driver installation in some cases

#### Linux

- X11 or Wayland display server
- USB permissions configuration required (udev rules)
- libxcb packages needed for PyQt6

#### macOS

- Intel and Apple Silicon supported
- USB device access permission required
- May need to allow app in Security & Privacy settings

---

## Python Requirements

### Version

| Requirement | Version |
|-------------|---------|
| **Minimum** | Python 3.10 |
| **Recommended** | Python 3.11 or 3.12 |

### Checking Your Python Version

```bash
python --version
# or
python3 --version
```

### Installing Python

**Windows:**
Download from [python.org](https://www.python.org/downloads/)

**Linux (Ubuntu/Debian):**
```bash
sudo apt install python3 python3-pip python3-venv
```

**Linux (Fedora):**
```bash
sudo dnf install python3 python3-pip
```

**macOS:**
```bash
brew install python
```

---

## Core Dependencies

These packages are installed automatically with Floppy Disk Workbench:

### GUI Framework

| Package | Version | Purpose |
|---------|---------|---------|
| `PyQt6` | 6.6.0+ | Main GUI framework |
| `PyQt6-Charts` | 6.6.0+ | Chart widgets for analytics |

### Hardware Interface

| Package | Version | Purpose |
|---------|---------|---------|
| `greaseweazle` | Latest | Greaseweazle hardware library |

### Data Processing

| Package | Version | Purpose |
|---------|---------|---------|
| `numpy` | 1.26.0+ | Numerical operations, signal processing |
| `bitarray` | 2.8.0+ | Efficient bit-level operations |
| `crcmod` | 1.7+ | CRC calculation for data verification |

### Configuration & Validation

| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic` | 2.0+ | Settings validation and serialization |

### Report Generation

| Package | Version | Purpose |
|---------|---------|---------|
| `reportlab` | 4.0+ | PDF report generation |

---

## Optional Dependencies

These enhance functionality but aren't required:

### Audio Feedback

| Platform | Package/Tool | Purpose |
|----------|--------------|---------|
| Windows | `winsound` (built-in) | System sounds |
| Linux | `paplay` (PulseAudio) | System sounds |
| macOS | `afplay` (built-in) | System sounds |

**Linux audio setup:**
```bash
# Ubuntu/Debian
sudo apt install pulseaudio-utils

# Fedora
sudo dnf install pulseaudio-utils
```

### Enhanced Charts

For advanced charting features:
```bash
pip install matplotlib
```

---

## Development Dependencies

For contributing to Floppy Disk Workbench:

### Testing

| Package | Purpose |
|---------|---------|
| `pytest` | Test framework |
| `pytest-qt` | PyQt testing utilities |
| `pytest-cov` | Coverage reporting |

### Code Quality

| Package | Purpose |
|---------|---------|
| `black` | Code formatting |
| `flake8` | Linting |
| `ruff` | Fast linting |
| `mypy` | Type checking |

### Documentation

| Package | Purpose |
|---------|---------|
| `sphinx` | Documentation generation |
| `sphinx-rtd-theme` | ReadTheDocs theme |

### Installing Development Dependencies

```bash
# Using Poetry
poetry install --with dev

# Using pip
pip install pytest pytest-qt black flake8 ruff mypy
```

---

## Dependency Installation

### Automatic Installation

All core dependencies are installed automatically:

```bash
pip install floppy-workbench
```

### Manual Installation

If you need to install dependencies separately:

```bash
# Core dependencies
pip install PyQt6 PyQt6-Charts
pip install numpy bitarray crcmod
pip install pydantic reportlab
pip install greaseweazle

# Verify installation
python -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')"
python -c "import numpy; print('NumPy OK')"
python -c "import greaseweazle; print('Greaseweazle OK')"
```

---

## Troubleshooting Dependencies

### PyQt6 Issues

**"No module named PyQt6"**
```bash
pip install PyQt6 PyQt6-Charts
```

**Linux: "Could not load the Qt platform plugin"**
```bash
# Ubuntu/Debian
sudo apt install libxcb-xinerama0 libxcb-cursor0

# Or install all xcb libraries
sudo apt install libxcb*
```

### NumPy Issues

**"numpy.core.multiarray failed to import"**
```bash
pip uninstall numpy
pip install numpy
```

### Greaseweazle Issues

**"No module named greaseweazle"**
```bash
pip install greaseweazle
```

**Version mismatch**
```bash
pip install --upgrade greaseweazle
```

---

## Version Compatibility Matrix

| Floppy Disk Workbench | Python | PyQt6 | Greaseweazle |
|------------------|--------|-------|--------------|
| 2.0.x | 3.10-3.12 | 6.6+ | Latest |
| 1.x | 3.9-3.11 | 6.4+ | 1.x |

---

**Next:** [[Getting Started]] - Your first steps with Floppy Disk Workbench
