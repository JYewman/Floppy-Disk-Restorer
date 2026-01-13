"""
Core functionality for Floppy Formatter with Greaseweazle support.

This module provides disk geometry, sector operations, formatting,
and recovery functionality using Greaseweazle V4.1 USB controller
for direct flux-level disk access.
"""

from floppy_formatter.core.geometry import (
    DiskGeometry,
    get_disk_geometry,
    get_greaseweazle_geometry,
    validate_floppy_geometry,
    get_standard_1_44mb_geometry,
    get_standard_720kb_geometry,
)

from floppy_formatter.core.sector_adapter import (
    # Reading
    read_sector,
    read_sector_by_lba,
    read_sector_multiread,
    read_track,

    # Writing
    write_sector,
    write_track,

    # Pattern writing
    write_track_pattern,
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
    ERROR_SUCCESS,
    ERROR_CRC,
    ERROR_SECTOR_NOT_FOUND,
    ERROR_NOT_READY,
    ERROR_WRITE_PROTECT,

    # Cache management
    flush_flux_cache,
    invalidate_track_cache,
    wake_up_device,
    reset_error_tracking,

    # Constants
    BYTES_PER_SECTOR,
)

from floppy_formatter.core.formatter import (
    # Formatting operations
    format_track,
    format_disk,
    format_tracks_range,

    # Format verification
    verify_format,

    # Device detection
    is_greaseweazle_device,
    is_usb_floppy,
    get_format_capability,

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

from floppy_formatter.core.settings import (
    # Enums
    SeekSpeed,
    ColorScheme,
    RecoveryLevel,
    ExportFormat,
    ReportFormat,
    Theme,

    # Dataclasses
    SectorMapColors,
    DeviceSettings,
    DisplaySettings,
    RecoverySettings,
    ExportSettings,
    WindowSettings,
    RecentFile,

    # Color schemes
    COLOR_SCHEMES,

    # Signals
    SettingsSignals,

    # Main class
    Settings,

    # Convenience functions
    get_settings,
    get_sector_colors,
    get_settings_dir,
    get_settings_file,
)

__all__ = [
    # Geometry
    "DiskGeometry",
    "get_disk_geometry",
    "get_greaseweazle_geometry",
    "validate_floppy_geometry",
    "get_standard_1_44mb_geometry",
    "get_standard_720kb_geometry",

    # Sector I/O - Reading
    "read_sector",
    "read_sector_by_lba",
    "read_sector_multiread",
    "read_track",

    # Sector I/O - Writing
    "write_sector",
    "write_track",

    # Pattern writing
    "write_track_pattern",
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
    "ERROR_SUCCESS",
    "ERROR_CRC",
    "ERROR_SECTOR_NOT_FOUND",
    "ERROR_NOT_READY",
    "ERROR_WRITE_PROTECT",

    # Cache management
    "flush_flux_cache",
    "invalidate_track_cache",
    "wake_up_device",
    "reset_error_tracking",

    # Constants
    "BYTES_PER_SECTOR",

    # Device detection
    "is_greaseweazle_device",
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

    # Settings - Enums
    "SeekSpeed",
    "ColorScheme",
    "RecoveryLevel",
    "ExportFormat",
    "ReportFormat",
    "Theme",

    # Settings - Dataclasses
    "SectorMapColors",
    "DeviceSettings",
    "DisplaySettings",
    "RecoverySettings",
    "ExportSettings",
    "WindowSettings",
    "RecentFile",

    # Settings - Color schemes
    "COLOR_SCHEMES",

    # Settings - Signals
    "SettingsSignals",

    # Settings - Main class
    "Settings",

    # Settings - Convenience functions
    "get_settings",
    "get_sector_colors",
    "get_settings_dir",
    "get_settings_file",
]
