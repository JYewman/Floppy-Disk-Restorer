"""
USB Floppy Formatter - Linux/WSL2 floppy disk restoration tool.

A Python-based low-level formatting and recovery tool for USB floppy drives,
specifically designed to handle disks with bad sector 0 and other severe defects
that prevent normal access. Now supports Linux and WSL2 environments.
"""

__version__ = "0.2.0"
__author__ = "Joshua Yewman"
__license__ = "MIT"

# Re-export main entry point
from floppy_formatter.main import main

# Re-export TUI application
from floppy_formatter.tui import FloppyFormatterApp

# Re-export device management and geometry
from floppy_formatter.core.device_manager import (
    find_floppy_devices,
    enumerate_devices,
    open_device,
    close_device,
    get_device_path,
)
from floppy_formatter.core.geometry import (
    DiskGeometry,
    get_disk_geometry,
    validate_floppy_geometry,
)

from floppy_formatter.utils.admin_check import (
    is_admin,
    is_wsl,
)

__all__ = [
    # Main entry point
    "main",
    "__version__",

    # TUI Application
    "FloppyFormatterApp",

    # Device management
    "find_floppy_devices",
    "enumerate_devices",
    "open_device",
    "close_device",
    "get_device_path",

    # Geometry
    "DiskGeometry",
    "get_disk_geometry",
    "validate_floppy_geometry",

    # Admin utilities
    "is_admin",
    "is_wsl",
]
