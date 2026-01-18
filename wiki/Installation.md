# Installation Guide

This guide covers all methods of installing Floppy Workbench on your system.

## Table of Contents

- [System Requirements](#system-requirements)
- [Quick Install (pip)](#quick-install-pip)
- [Development Installation](#development-installation)
- [Windows Installation](#windows-installation)
- [Linux Installation](#linux-installation)
- [macOS Installation](#macos-installation)
- [Verifying Installation](#verifying-installation)
- [Updating](#updating)
- [Uninstalling](#uninstalling)

---

## System Requirements

Before installing, ensure your system meets these requirements:

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **Operating System** | Windows 10, Linux (Ubuntu 20.04+), macOS 11+ | Windows 11, Ubuntu 22.04+, macOS 13+ |
| **Python** | 3.10 | 3.11 or 3.12 |
| **RAM** | 4 GB | 8 GB |
| **Disk Space** | 500 MB | 1 GB |
| **Display** | 1280x720 | 1920x1080 |

---

## Quick Install (pip)

The easiest way to install Floppy Workbench is via pip:

```bash
pip install floppy-workbench
```

This will install the application and all dependencies automatically.

### Virtual Environment (Recommended)

It's recommended to use a virtual environment:

```bash
# Create virtual environment
python -m venv floppy-env

# Activate it
# On Windows:
floppy-env\Scripts\activate
# On Linux/macOS:
source floppy-env/bin/activate

# Install
pip install floppy-workbench
```

---

## Development Installation

For development or to get the latest features:

### Using Poetry (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/JYewman/Floppy-Disk-Restorer.git
cd Floppy-Disk-Restorer

# Install Poetry if you don't have it
pip install poetry

# Install dependencies
poetry install

# Run the application
poetry run floppy-workbench
```

### Using pip in Editable Mode

```bash
# Clone the repository
git clone https://github.com/JYewman/Floppy-Disk-Restorer.git
cd Floppy-Disk-Restorer

# Install in editable mode
pip install -e .

# Run the application
floppy-workbench
```

---

## Windows Installation

### Step 1: Install Python

1. Download Python 3.10+ from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **Important**: Check "Add Python to PATH" during installation
4. Click "Install Now"

Verify installation:
```cmd
python --version
```

### Step 2: Install Floppy Workbench

Open Command Prompt or PowerShell:

```cmd
pip install floppy-workbench
```

### Step 3: Install USB Drivers

Greaseweazle usually works without additional drivers on Windows 10/11. If your device isn't recognized:

1. Download [Zadig](https://zadig.akeo.ie/)
2. Connect your Greaseweazle
3. Run Zadig
4. Select "Greaseweazle" from the device list
5. Select "WinUSB" driver
6. Click "Replace Driver"

### Step 4: Run the Application

```cmd
floppy-workbench
```

Or from the Start Menu search for "Floppy Workbench".

---

## Linux Installation

### Ubuntu/Debian

```bash
# Update package list
sudo apt update

# Install Python and pip
sudo apt install python3 python3-pip python3-venv

# Install system dependencies for PyQt6
sudo apt install libxcb-xinerama0 libxcb-cursor0

# Install Floppy Workbench
pip install floppy-workbench
```

### Fedora/RHEL

```bash
# Install Python
sudo dnf install python3 python3-pip

# Install Floppy Workbench
pip install floppy-workbench
```

### Arch Linux

```bash
# Install Python
sudo pacman -S python python-pip

# Install Floppy Workbench
pip install floppy-workbench
```

### USB Permissions

On Linux, you need permission to access USB devices:

```bash
# Add your user to the plugdev group
sudo usermod -a -G plugdev $USER

# Create udev rule for Greaseweazle
sudo tee /etc/udev/rules.d/60-greaseweazle.rules << 'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="1209", ATTR{idProduct}=="4d69", MODE="0666", GROUP="plugdev"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Log out and log back in for group changes to take effect
```

---

## macOS Installation

### Step 1: Install Python

Using Homebrew (recommended):
```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python
```

Or download from [python.org](https://www.python.org/downloads/macos/).

### Step 2: Install Floppy Workbench

```bash
pip3 install floppy-workbench
```

### Step 3: Run the Application

```bash
floppy-workbench
```

**Note**: On first run, macOS may ask for permission to access USB devices. Click "Allow".

---

## Verifying Installation

After installation, verify everything is working:

### 1. Check the Application Starts

```bash
floppy-workbench --version
```

Should output:
```
Floppy Workbench v2.0.0
```

### 2. Launch the GUI

```bash
floppy-workbench
```

The application window should open.

### 3. Check Dependencies

```bash
python -c "import floppy_formatter; print('OK')"
```

Should output:
```
OK
```

---

## Updating

### Update via pip

```bash
pip install --upgrade floppy-workbench
```

### Update Development Installation

```bash
cd Floppy-Disk-Restorer
git pull
poetry install  # or pip install -e .
```

---

## Uninstalling

### Remove via pip

```bash
pip uninstall floppy-workbench
```

### Remove Configuration Files

Configuration files are stored in platform-specific locations:

**Windows:**
```cmd
rmdir /s "%APPDATA%\FloppyWorkbench"
```

**Linux:**
```bash
rm -rf ~/.config/floppy-workbench
```

**macOS:**
```bash
rm -rf ~/Library/Application\ Support/FloppyWorkbench
```

---

## Troubleshooting Installation

### "pip: command not found"

Ensure Python is in your PATH. On Windows, reinstall Python with "Add to PATH" checked.

### "No module named PyQt6"

Install PyQt6 manually:
```bash
pip install PyQt6 PyQt6-Charts
```

### Permission Denied on Linux

Run with sudo or fix USB permissions (see Linux section above).

### SSL Certificate Errors

Update pip and certificates:
```bash
pip install --upgrade pip certifi
```

---

**Next:** [[Hardware Requirements]] - Learn about the required hardware
