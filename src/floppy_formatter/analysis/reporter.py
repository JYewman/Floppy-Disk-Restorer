"""
Detailed reporting for floppy disk operations.

This module provides comprehensive reporting functionality including:
- Sector-by-sector detailed reports
- Hex dumps of bad sectors
- Visual track maps
- Before/after comparison reports
- Convergence progress displays
"""

from typing import List, Optional
import string

from floppy_formatter.analysis.scanner import (
    SectorMap,
    get_all_tracks,
    format_sector_address,
)
from floppy_formatter.analysis.statistics import (
    ComparisonStatistics,
    FormatStatistics,
    ProgressUpdate,
    format_progress_line,
    generate_history_graph,
)
from floppy_formatter.core.geometry import (
    DiskGeometry,
    CYLINDERS_1PT44MB,
    HEADS_PER_CYLINDER_1PT44MB,
)


# =============================================================================
# Hex Dump Generation
# =============================================================================


def generate_hex_dump(
    sector_data: bytes,
    sector_number: int,
    bytes_per_line: int = 16
) -> str:
    """
    Generate hexadecimal dump of sector data.

    Shows offset, hex bytes, and ASCII representation for each line.
    Highlights error patterns (all 0x00, all 0xFF, etc.).

    Args:
        sector_data: Raw sector data (usually 512 bytes)
        sector_number: Sector number for display
        bytes_per_line: Bytes to show per line (default: 16)

    Returns:
        Multi-line formatted hex dump

    Example:
        >>> data = bytes([0xFF] * 512)
        >>> dump = generate_hex_dump(data, 0)
        >>> print(dump)
        Sector 0 Hex Dump:
        0000: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF  ................
        ...
        [Pattern detected: All 0xFF]
    """
    lines = []
    lines.append(f"Sector {sector_number} Hex Dump:")
    lines.append("=" * 70)

    # Check for patterns
    pattern_type = _detect_pattern(sector_data)
    if pattern_type:
        lines.append(f"[Pattern detected: {pattern_type}]")
        lines.append("")

    # Generate hex dump lines
    for offset in range(0, len(sector_data), bytes_per_line):
        chunk = sector_data[offset:offset + bytes_per_line]

        # Format offset
        offset_str = f"{offset:04X}:"

        # Format hex bytes
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        hex_str = hex_str.ljust(bytes_per_line * 3 - 1)

        # Format ASCII representation
        ascii_str = "".join(
            chr(b) if b in string.printable.encode('ascii') and b >= 32 else '.'
            for b in chunk
        )

        lines.append(f"{offset_str} {hex_str}  {ascii_str}")

    lines.append("=" * 70)
    return "\n".join(lines)


def _detect_pattern(data: bytes) -> Optional[str]:
    """
    Detect common error patterns in sector data.

    Args:
        data: Sector data to analyze

    Returns:
        Pattern description or None if no pattern detected
    """
    if len(data) == 0:
        return "Empty sector"

    unique_bytes = set(data)

    if len(unique_bytes) == 1:
        byte_value = list(unique_bytes)[0]
        if byte_value == 0x00:
            return "All 0x00 (zero-filled)"
        elif byte_value == 0xFF:
            return "All 0xFF (erased/unformatted)"
        elif byte_value == 0x55:
            return "All 0x55 (pattern: 01010101)"
        elif byte_value == 0xAA:
            return "All 0xAA (pattern: 10101010)"
        else:
            return f"All 0x{byte_value:02X} (single byte pattern)"

    return None


# =============================================================================
# Track Map Visualization
# =============================================================================


def generate_track_map(
    sector_map: SectorMap,
    geometry: Optional[DiskGeometry] = None,
    max_cylinders: Optional[int] = None
) -> str:
    """
    Generate visual track map showing sector status.

    Creates a grid showing all tracks with visual indicators:
    - ✓ = Good sector
    - ✗ = Bad sector
    - ? = Unknown/uncertain

    Args:
        sector_map: Complete sector map from scanning
        geometry: Optional disk geometry (uses defaults if not provided)
        max_cylinders: Maximum cylinders to display (None = all)

    Returns:
        Multi-line formatted track map

    Example:
        >>> scan = scan_all_sectors(handle, geometry)
        >>> track_map = generate_track_map(scan)
        >>> print(track_map)
        Track Map (✓ = Good, ✗ = Bad)

        Cyl 00: ✗✗✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓  [Head 0]
                ✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓  [Head 1]
        ...
    """
    # Use provided geometry or defaults
    if geometry is None:
        cylinders = CYLINDERS_1PT44MB
        heads = HEADS_PER_CYLINDER_1PT44MB
    else:
        cylinders = geometry.cylinders
        heads = geometry.heads

    if max_cylinders is not None:
        cylinders = min(cylinders, max_cylinders)

    lines = []
    lines.append("Track Map (✓ = Good, ✗ = Bad)")
    lines.append("")

    # Get all track info
    all_tracks = get_all_tracks(sector_map, geometry)

    for cylinder in range(cylinders):
        for head in range(heads):
            track_idx = cylinder * heads + head
            if track_idx >= len(all_tracks):
                break

            track = all_tracks[track_idx]

            # Format cylinder number (only on first head)
            if head == 0:
                cyl_label = f"Cyl {cylinder:02d}: "
            else:
                cyl_label = " " * 8  # Indent for head 1

            # Generate sector status symbols
            sector_symbols = []
            for sector_num in range(track.start_sector, track.end_sector + 1):
                if sector_map.is_sector_good(sector_num):
                    sector_symbols.append("✓")
                elif sector_map.is_sector_bad(sector_num):
                    sector_symbols.append("✗")
                else:
                    sector_symbols.append("?")

            # Format line
            symbols_str = "".join(sector_symbols)
            head_label = f"[Head {head}]"

            lines.append(f"{cyl_label}{symbols_str}  {head_label}")

    return "\n".join(lines)


# =============================================================================
# Bad Sector List
# =============================================================================


def generate_bad_sector_list(
    sector_map: SectorMap,
    geometry: Optional[DiskGeometry] = None,
    include_error_types: bool = True
) -> str:
    """
    Generate detailed list of bad sectors.

    Lists all bad sectors with cylinder/head/sector coordinates
    and error type classification.

    Args:
        sector_map: Complete sector map from scanning
        geometry: Optional disk geometry (uses defaults if not provided)
        include_error_types: Include error descriptions (default: True)

    Returns:
        Multi-line formatted bad sector list

    Example:
        >>> scan = scan_all_sectors(handle, geometry)
        >>> bad_list = generate_bad_sector_list(scan)
        >>> print(bad_list)
        Bad Sectors (12 total):

        Sector    C/H/S          Error Type
        ------    -----          ----------
        0         C0:H0:S0       CRC Error
        1         C0:H0:S1       CRC Error
        ...
    """
    bad_sectors = sector_map.bad_sectors

    if len(bad_sectors) == 0:
        return "No bad sectors detected!"

    lines = []
    lines.append(f"Bad Sectors ({len(bad_sectors)} total):")
    lines.append("")

    if include_error_types:
        lines.append("Sector    C/H/S          Error Type")
        lines.append("------    -----          ----------")

        for sector_num in sorted(bad_sectors):
            chs = format_sector_address(sector_num, geometry)
            # Extract just C#:H#:S# part
            chs_short = chs.split(" (")[0]

            error_type = sector_map.get_sector_error(sector_num)
            if error_type:
                lines.append(f"{sector_num:6d}    {chs_short:13s}  {error_type}")
            else:
                lines.append(f"{sector_num:6d}    {chs_short:13s}  Unknown")
    else:
        lines.append("Sector    C/H/S")
        lines.append("------    -----")

        for sector_num in sorted(bad_sectors):
            chs = format_sector_address(sector_num, geometry)
            chs_short = chs.split(" (")[0]
            lines.append(f"{sector_num:6d}    {chs_short}")

    return "\n".join(lines)


# =============================================================================
# Comparison Reports
# =============================================================================


def generate_comparison_report(
    comparison: ComparisonStatistics
) -> str:
    """
    Generate before/after comparison report.

    Shows recovery effectiveness with clear metrics.

    Args:
        comparison: Comparison statistics from before/after scans

    Returns:
        Multi-line formatted comparison report

    Example:
        >>> comparison = create_comparison_statistics(initial, final, recovery)
        >>> report = generate_comparison_report(comparison)
        >>> print(report)
        [Shows before/after statistics and recovery metrics]
    """
    lines = []
    lines.append("=" * 70)
    lines.append("RECOVERY RESULTS")
    lines.append("=" * 70)
    lines.append("")

    lines.append("Before Recovery:")
    lines.append(f"  Bad sectors: {comparison.initial_bad_sectors}")
    lines.append("")

    lines.append("After Recovery:")
    lines.append(f"  Bad sectors: {comparison.final_bad_sectors}")
    lines.append("")

    lines.append("Recovery Metrics:")
    lines.append(f"  Sectors recovered: {comparison.sectors_recovered}")
    lines.append(f"  Recovery rate: {comparison.recovery_rate:.1f}%")
    lines.append("")

    lines.append("Disk Status:")
    lines.append(f"  Overall: {comparison.disk_status.value}")
    lines.append(f"  Assessment: {comparison.usability_message}")
    lines.append("")

    if comparison.final_bad_sectors > 0:
        lines.append(f"Permanently bad sectors: {len(comparison.permanently_bad_sectors)}")
        if len(comparison.permanently_bad_sectors) <= 20:
            # List all if not too many
            sector_list = ", ".join(str(s) for s in sorted(comparison.permanently_bad_sectors))
            lines.append(f"  Sectors: {sector_list}")
        else:
            # Show first few and count
            first_few = sorted(comparison.permanently_bad_sectors)[:10]
            sector_list = ", ".join(str(s) for s in first_few)
            remaining = len(comparison.permanently_bad_sectors) - 10
            lines.append(f"  First 10: {sector_list}, ... and {remaining} more")

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_format_report(
    format_stats: FormatStatistics
) -> str:
    """
    Generate format operation report.

    Shows formatting statistics including duration, passes, and
    convergence status.

    Args:
        format_stats: Format statistics from operation

    Returns:
        Multi-line formatted format report

    Example:
        >>> format_stats = create_format_statistics(recovery_stats)
        >>> report = generate_format_report(format_stats)
        >>> print(report)
        [Shows format operation statistics]
    """
    lines = []
    lines.append("=" * 70)
    lines.append("FORMAT STATISTICS")
    lines.append("=" * 70)
    lines.append("")

    # Duration and speed
    duration_minutes = format_stats.total_duration / 60.0
    total_secs = format_stats.total_duration
    lines.append(f"Duration: {duration_minutes:.1f} minutes ({total_secs:.1f} seconds)")
    lines.append(f"Average speed: {format_stats.average_speed:.1f} sectors/second")
    lines.append("")

    # Passes
    lines.append(f"Passes executed: {format_stats.passes_performed}")
    lines.append(f"Sectors processed: {format_stats.sectors_processed:,}")
    lines.append("")

    # Convergence status
    lines.append("Convergence:")
    lines.append(f"  Mode: {'Convergence' if format_stats.convergence_mode else 'Fixed pass'}")
    lines.append(f"  Status: {format_stats.get_convergence_message()}")
    lines.append("")

    # Bad sector history
    if format_stats.bad_sector_history:
        lines.append("Bad Sector History:")
        for i, count in enumerate(format_stats.bad_sector_history):
            if i == 0:
                lines.append(f"  Initial scan: {count} bad sectors")
            else:
                prev_count = format_stats.bad_sector_history[i - 1]
                delta = count - prev_count
                delta_str = f"{delta:+d}" if delta != 0 else "no change"
                lines.append(f"  After pass {i}: {count} bad sectors ({delta_str})")
        lines.append("")

        # Text-based graph if enough data
        if len(format_stats.bad_sector_history) >= 2:
            lines.append("Progress Graph:")
            graph = generate_history_graph(format_stats.bad_sector_history)
            lines.append(graph)

    lines.append("=" * 70)
    return "\n".join(lines)


# =============================================================================
# Progress Display
# =============================================================================


def generate_progress_display(
    progress_updates: List[ProgressUpdate]
) -> str:
    """
    Generate convergence progress display.

    Shows pass-by-pass bad sector counts with delta calculations
    and visual trend indicators.

    Args:
        progress_updates: List of progress updates from each pass

    Returns:
        Multi-line formatted progress display

    Example:
        >>> updates = [
        ...     create_progress_update(0, 147, None),
        ...     create_progress_update(1, 89, 147),
        ...     create_progress_update(2, 45, 89),
        ... ]
        >>> display = generate_progress_display(updates)
        >>> print(display)
        Convergence Progress:

        Pass 1: 147 bad sectors  (· Initial scan)
        Pass 2:  89 bad sectors  (↓ -58, -39.5%)
        Pass 3:  45 bad sectors  (↓ -44, -49.4%)
    """
    if not progress_updates:
        return "No progress data available"

    lines = []
    lines.append("Convergence Progress:")
    lines.append("")

    for update in progress_updates:
        line = format_progress_line(update)
        lines.append(line)

    return "\n".join(lines)


# =============================================================================
# Complete Report Generation
# =============================================================================


def generate_complete_report(
    _initial_scan: SectorMap,
    final_scan: SectorMap,
    comparison: ComparisonStatistics,
    format_stats: FormatStatistics,
    include_track_map: bool = True,
    include_bad_sector_list: bool = True,
    geometry: Optional[DiskGeometry] = None
) -> str:
    """
    Generate comprehensive report with all sections.

    Creates a complete report including:
    - Comparison statistics
    - Format statistics
    - Track map (optional)
    - Bad sector list (optional)

    Args:
        initial_scan: Sector map before recovery
        final_scan: Sector map after recovery
        comparison: Comparison statistics
        format_stats: Format statistics
        include_track_map: Include visual track map (default: True)
        include_bad_sector_list: Include bad sector list (default: True)
        geometry: Optional disk geometry

    Returns:
        Multi-line complete report

    Example:
        >>> report = generate_complete_report(
        ...     initial, final, comparison, format_stats
        ... )
        >>> print(report)
        >>> # or save to file
        >>> with open("recovery_report.txt", "w") as f:
        ...     f.write(report)
    """
    sections = []

    # Comparison report
    sections.append(generate_comparison_report(comparison))
    sections.append("")

    # Format report
    sections.append(generate_format_report(format_stats))
    sections.append("")

    # Track map
    if include_track_map:
        sections.append("=" * 70)
        sections.append("TRACK MAP")
        sections.append("=" * 70)
        sections.append("")
        sections.append(generate_track_map(final_scan, geometry))
        sections.append("")

    # Bad sector list
    if include_bad_sector_list and len(final_scan.bad_sectors) > 0:
        sections.append("=" * 70)
        sections.append("BAD SECTOR DETAILS")
        sections.append("=" * 70)
        sections.append("")
        sections.append(generate_bad_sector_list(final_scan, geometry))
        sections.append("")

    return "\n".join(sections)
