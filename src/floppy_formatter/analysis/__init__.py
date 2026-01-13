"""
Analysis module for Floppy Workbench.

This module provides disk scanning, bad sector detection, reporting,
flux analysis, signal quality metrics, head alignment diagnostics,
and forensic analysis functionality for comprehensive disk analysis.

Submodules:
    scanner: Disk scanning and bad sector detection
    statistics: Statistical analysis and progress tracking
    reporter: Report generation
    flux_analyzer: Flux timing analysis and encoding detection
    signal_quality: Signal quality metrics (SNR, jitter, weak bits)
    head_alignment: Head alignment diagnostics
    forensics: Copy protection and format forensics
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

# Phase 3: Flux Analysis Engine
from floppy_formatter.analysis.flux_analyzer import (
    # Enums
    EncodingType,
    # Data classes
    FluxCapture,
    TimingStatistics,
    HistogramBin,
    HistogramResult,
    # Functions
    analyze_flux_timing,
    generate_histogram,
    detect_encoding_type,
    measure_bit_cell_width,
    # Constants
    HD_BIT_CELL_US,
    DD_BIT_CELL_US,
    MFM_HD_SHORT_US,
    MFM_HD_MEDIUM_US,
    MFM_HD_LONG_US,
)

from floppy_formatter.analysis.signal_quality import (
    # Enums
    QualityGrade,
    WeakBitType,
    # Data classes
    JitterMetrics,
    WeakBitPosition,
    SNRResult,
    TrackQuality,
    # Functions
    calculate_snr,
    measure_jitter,
    detect_weak_bits,
    grade_track_quality,
    # Constants
    GRADE_A_THRESHOLD,
    GRADE_B_THRESHOLD,
    GRADE_C_THRESHOLD,
    GRADE_D_THRESHOLD,
    SNR_EXCELLENT,
    SNR_GOOD,
    SNR_FAIR,
    SNR_POOR,
    JITTER_EXCELLENT_NS,
    JITTER_GOOD_NS,
    JITTER_FAIR_NS,
    JITTER_POOR_NS,
)

from floppy_formatter.analysis.head_alignment import (
    # Enums
    AlignmentStatus,
    MarginDirection,
    # Data classes
    MarginPoint,
    MarginMeasurement,
    AzimuthResult,
    CylinderAlignment,
    AlignmentReport,
    # Functions
    measure_track_margins,
    calculate_alignment_score,
    detect_azimuth_error,
    generate_alignment_report,
    # Constants
    TRACK_PITCH_UM,
    TEST_CYLINDERS,
    ALIGNMENT_EXCELLENT,
    ALIGNMENT_GOOD,
    ALIGNMENT_FAIR,
    ALIGNMENT_POOR,
)

from floppy_formatter.analysis.forensics import (
    # Enums
    ProtectionType,
    FormatType,
    SectorMarkType,
    # Data classes
    ProtectionSignature,
    CopyProtectionResult,
    SectorInfo,
    FormatAnalysis,
    DeletedSector,
    FluxDifference,
    FluxComparison,
    # Functions
    detect_copy_protection,
    analyze_format_type,
    extract_deleted_data,
    compare_flux_captures,
    # Constants
    STANDARD_TRACK_US,
    PC_HD_SECTORS,
    PC_DD_SECTORS,
    DATA_MARK_NORMAL,
    DATA_MARK_DELETED,
)

__all__ = [
    # =========================================================================
    # Scanner (Phase 4)
    # =========================================================================
    # Data structures
    "SectorMap",
    "TrackInfo",
    "ScanStatistics",
    # Scanning functions
    "scan_all_sectors",
    "scan_track",
    "get_track_info",
    "get_scan_statistics",

    # =========================================================================
    # Statistics (Phase 7)
    # =========================================================================
    "DiskStatus",
    "ComparisonStatistics",
    "FormatStatistics",
    "ProgressUpdate",
    "create_comparison_statistics",
    "create_format_statistics",
    "create_progress_update",
    "format_progress_line",
    "generate_history_graph",

    # =========================================================================
    # Reporter (Phase 7)
    # =========================================================================
    "generate_hex_dump",
    "generate_track_map",
    "generate_bad_sector_list",
    "generate_comparison_report",
    "generate_format_report",
    "generate_progress_display",
    "generate_complete_report",

    # =========================================================================
    # Flux Analyzer (Phase 3)
    # =========================================================================
    # Enums
    "EncodingType",
    # Data classes
    "FluxCapture",
    "TimingStatistics",
    "HistogramBin",
    "HistogramResult",
    # Functions
    "analyze_flux_timing",
    "generate_histogram",
    "detect_encoding_type",
    "measure_bit_cell_width",
    # Constants
    "HD_BIT_CELL_US",
    "DD_BIT_CELL_US",
    "MFM_HD_SHORT_US",
    "MFM_HD_MEDIUM_US",
    "MFM_HD_LONG_US",

    # =========================================================================
    # Signal Quality (Phase 3)
    # =========================================================================
    # Enums
    "QualityGrade",
    "WeakBitType",
    # Data classes
    "JitterMetrics",
    "WeakBitPosition",
    "SNRResult",
    "TrackQuality",
    # Functions
    "calculate_snr",
    "measure_jitter",
    "detect_weak_bits",
    "grade_track_quality",
    # Constants
    "GRADE_A_THRESHOLD",
    "GRADE_B_THRESHOLD",
    "GRADE_C_THRESHOLD",
    "GRADE_D_THRESHOLD",
    "SNR_EXCELLENT",
    "SNR_GOOD",
    "SNR_FAIR",
    "SNR_POOR",
    "JITTER_EXCELLENT_NS",
    "JITTER_GOOD_NS",
    "JITTER_FAIR_NS",
    "JITTER_POOR_NS",

    # =========================================================================
    # Head Alignment (Phase 3)
    # =========================================================================
    # Enums
    "AlignmentStatus",
    "MarginDirection",
    # Data classes
    "MarginPoint",
    "MarginMeasurement",
    "AzimuthResult",
    "CylinderAlignment",
    "AlignmentReport",
    # Functions
    "measure_track_margins",
    "calculate_alignment_score",
    "detect_azimuth_error",
    "generate_alignment_report",
    # Constants
    "TRACK_PITCH_UM",
    "TEST_CYLINDERS",
    "ALIGNMENT_EXCELLENT",
    "ALIGNMENT_GOOD",
    "ALIGNMENT_FAIR",
    "ALIGNMENT_POOR",

    # =========================================================================
    # Forensics (Phase 3)
    # =========================================================================
    # Enums
    "ProtectionType",
    "FormatType",
    "SectorMarkType",
    # Data classes
    "ProtectionSignature",
    "CopyProtectionResult",
    "SectorInfo",
    "FormatAnalysis",
    "DeletedSector",
    "FluxDifference",
    "FluxComparison",
    # Functions
    "detect_copy_protection",
    "analyze_format_type",
    "extract_deleted_data",
    "compare_flux_captures",
    # Constants
    "STANDARD_TRACK_US",
    "PC_HD_SECTORS",
    "PC_DD_SECTORS",
    "DATA_MARK_NORMAL",
    "DATA_MARK_DELETED",
]
