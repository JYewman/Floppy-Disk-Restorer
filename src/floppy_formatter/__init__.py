"""
Floppy Workbench - Professional Floppy Disk Analysis & Recovery Tool.

A comprehensive floppy disk analysis and recovery application using
Greaseweazle V4.1 for flux-level disk access. Features include:

- Flux-level disk analysis with waveform and histogram visualization
- Advanced data recovery with multi-capture and PLL tuning
- Head alignment diagnostics
- Convergence-based recovery algorithms
- Multiple image format support (IMG, IMA, SCP, HFE)
- Professional workbench GUI with real-time sector map

Supports Linux and Windows environments with Greaseweazle hardware.
"""

__version__ = "2.0.0"
__author__ = "Joshua Yewman"
__license__ = "MIT"
__app_name__ = "Floppy Workbench"

# Re-export main entry point
from floppy_formatter.main import main

# Re-export geometry utilities
from floppy_formatter.core.geometry import (
    DiskGeometry,
    get_disk_geometry,
    get_greaseweazle_geometry,
    validate_floppy_geometry,
    get_standard_1_44mb_geometry,
    get_standard_720kb_geometry,
)

# Re-export Greaseweazle hardware interface
from floppy_formatter.hardware import (
    GreaseweazleDevice,
    FluxData,
    FluxReader,
    FluxWriter,
    MFMDecoder,
    MFMEncoder,
)

# Re-export admin/platform utilities
from floppy_formatter.utils.admin_check import (
    is_admin,
    is_wsl,
)

__all__ = [
    # Main entry point
    "main",
    "__version__",
    "__app_name__",

    # Greaseweazle hardware
    "GreaseweazleDevice",
    "FluxData",
    "FluxReader",
    "FluxWriter",
    "MFMDecoder",
    "MFMEncoder",

    # Geometry
    "DiskGeometry",
    "get_disk_geometry",
    "get_greaseweazle_geometry",
    "validate_floppy_geometry",
    "get_standard_1_44mb_geometry",
    "get_standard_720kb_geometry",

    # Admin utilities
    "is_admin",
    "is_wsl",
]
