"""
Core functionality for USB Floppy Formatter (Linux/WSL2).

This module provides device management, geometry detection, and low-level
disk operations for floppy disk formatting and recovery on Linux systems.
"""

from floppy_formatter.core.device_manager import (
    find_floppy_devices,
    enumerate_devices,
    get_device_path,
    open_device,
    close_device,
    is_device_accessible,
)

from floppy_formatter.core.geometry import (
    DiskGeometry,
    get_disk_geometry,
    validate_floppy_geometry,
)

from floppy_formatter.core.sector_io import (
    # Reading
    read_sector,
    read_sector_multiread,
    read_sectors_batch,
    read_track,

    # Writing
    write_sector,
    write_sectors_batch,

    # Pattern writing
    write_pattern,
    write_track_pattern,
    write_disk_pattern,
    get_pattern_for_pass,
    get_pattern_name,

    # Pattern constants
    PATTERN_ALTERNATING_LOW,
    PATTERN_ALTERNATING_HIGH,
    PATTERN_ALL_SET,
    PATTERN_ALL_CLEAR,
    PATTERN_SEQUENCE,

    # Error classification
    classify_error,
    is_fatal_error,
    is_data_error,

    # Verification
    verify_sector,
    verify_pattern,
)

from floppy_formatter.core.formatter import (
    # Device detection
    is_usb_floppy,
    get_format_capability,

    # Formatting operations
    format_track,
    format_disk,
    format_tracks_range,

    # Format verification
    verify_format,

    # Utility
    estimate_format_time,
)

from floppy_formatter.core.recovery import (
    # Power management
    prevent_sleep,
    allow_sleep,

    # Recovery operations
    recover_disk,
    recover_bad_sectors_only,
    recover_track,
    retry_bad_sectors,

    # Recovery analysis
    analyze_convergence,
    get_recovery_recommendation,

    # Recovery statistics
    RecoveryStatistics,
)

__all__ = [
    # Device management
    "find_floppy_devices",
    "enumerate_devices",
    "get_device_path",
    "open_device",
    "close_device",
    "is_device_accessible",

    # Geometry
    "DiskGeometry",
    "get_disk_geometry",
    "validate_floppy_geometry",

    # Sector I/O - Reading
    "read_sector",
    "read_sector_multiread",
    "read_sectors_batch",
    "read_track",

    # Sector I/O - Writing
    "write_sector",
    "write_sectors_batch",

    # Pattern writing
    "write_pattern",
    "write_track_pattern",
    "write_disk_pattern",
    "get_pattern_for_pass",
    "get_pattern_name",

    # Pattern constants
    "PATTERN_ALTERNATING_LOW",
    "PATTERN_ALTERNATING_HIGH",
    "PATTERN_ALL_SET",
    "PATTERN_ALL_CLEAR",
    "PATTERN_SEQUENCE",

    # Error classification
    "classify_error",
    "is_fatal_error",
    "is_data_error",

    # Verification
    "verify_sector",
    "verify_pattern",

    # Device detection
    "is_usb_floppy",
    "get_format_capability",

    # Formatting operations
    "format_track",
    "format_disk",
    "format_tracks_range",
    "verify_format",
    "estimate_format_time",

    # Power management
    "prevent_sleep",
    "allow_sleep",

    # Recovery operations
    "recover_disk",
    "recover_bad_sectors_only",
    "recover_track",
    "retry_bad_sectors",

    # Recovery analysis
    "analyze_convergence",
    "get_recovery_recommendation",
    "RecoveryStatistics",
]
