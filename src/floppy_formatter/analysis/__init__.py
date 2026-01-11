"""
Analysis module for USB Floppy Formatter.

This module provides disk scanning, bad sector detection, and reporting
functionality for comprehensive disk analysis and diagnostics.
"""

from floppy_formatter.analysis.scanner import (
    SectorMap,
    TrackInfo,
    ScanStatistics,
    scan_all_sectors,
    scan_track,
    get_track_info,
    get_scan_statistics,
)

from floppy_formatter.analysis.statistics import (
    DiskStatus,
    ComparisonStatistics,
    FormatStatistics,
    ProgressUpdate,
    create_comparison_statistics,
    create_format_statistics,
    create_progress_update,
    format_progress_line,
    generate_history_graph,
)

from floppy_formatter.analysis.reporter import (
    generate_hex_dump,
    generate_track_map,
    generate_bad_sector_list,
    generate_comparison_report,
    generate_format_report,
    generate_progress_display,
    generate_complete_report,
)

__all__ = [
    # Phase 4: Data structures
    "SectorMap",
    "TrackInfo",
    "ScanStatistics",

    # Phase 4: Scanning functions
    "scan_all_sectors",
    "scan_track",
    "get_track_info",
    "get_scan_statistics",

    # Phase 7: Statistical analysis
    "DiskStatus",
    "ComparisonStatistics",
    "FormatStatistics",
    "ProgressUpdate",
    "create_comparison_statistics",
    "create_format_statistics",
    "create_progress_update",
    "format_progress_line",
    "generate_history_graph",

    # Phase 7: Reporting functions
    "generate_hex_dump",
    "generate_track_map",
    "generate_bad_sector_list",
    "generate_comparison_report",
    "generate_format_report",
    "generate_progress_display",
    "generate_complete_report",
]
