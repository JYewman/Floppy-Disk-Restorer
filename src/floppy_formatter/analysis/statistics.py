"""
Statistical analysis for floppy disk operations.

This module provides comprehensive statistical analysis including:
- Before/after comparison statistics
- Recovery success rate calculations
- Disk usability assessment
- Format operation statistics
- Convergence progress tracking
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, TYPE_CHECKING
from enum import Enum

from floppy_formatter.analysis.scanner import SectorMap

if TYPE_CHECKING:
    from floppy_formatter.core.recovery import RecoveryStatistics


# =============================================================================
# Enums
# =============================================================================


class DiskStatus(Enum):
    """
    Overall disk health status after recovery.
    """
    PERFECT = "Perfect"
    """Zero bad sectors - disk is fully functional."""

    GOOD = "Good"
    """Few bad sectors (<1%) - safe for most uses."""

    DEGRADED = "Degraded"
    """Moderate bad sectors (1-5%) - usable but not for critical data."""

    POOR = "Poor"
    """Many bad sectors (5-20%) - significant reliability concerns."""

    UNUSABLE = "Unusable"
    """Too many bad sectors (>20%) - disk should be replaced."""


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ComparisonStatistics:
    """
    Before/after comparison statistics for recovery operations.

    Attributes:
        initial_bad_sectors: Bad sector count before recovery
        final_bad_sectors: Bad sector count after recovery
        sectors_recovered: Number of sectors successfully recovered
        recovery_rate: Percentage of bad sectors recovered (0-100%)
        total_sectors: Total sectors on disk (usually 2880)
        permanently_bad_sectors: List of sector numbers still bad after recovery
        disk_status: Overall disk health assessment
        usability_message: Human-readable assessment message

    Example:
        >>> initial = scan_all_sectors(handle, geometry)
        >>> stats = recover_disk(handle, geometry, convergence_mode=True)
        >>> final = scan_all_sectors(handle, geometry)
        >>> comparison = create_comparison_statistics(initial, final, stats)
        >>> print(f"Recovery: {comparison.recovery_rate:.1f}%")
        >>> print(f"Status: {comparison.disk_status.value}")
    """
    initial_bad_sectors: int
    final_bad_sectors: int
    sectors_recovered: int
    recovery_rate: float
    total_sectors: int
    permanently_bad_sectors: List[int] = field(default_factory=list)
    disk_status: DiskStatus = DiskStatus.UNUSABLE
    usability_message: str = ""

    def is_fully_recovered(self) -> bool:
        """Check if disk is fully recovered (zero bad sectors)."""
        return self.final_bad_sectors == 0

    def is_usable(self) -> bool:
        """Check if disk is usable (Good or better status)."""
        return self.disk_status in [DiskStatus.PERFECT, DiskStatus.GOOD, DiskStatus.DEGRADED]


@dataclass
class FormatStatistics:
    """
    Statistics from a formatting operation.

    Attributes:
        total_duration: Total time spent formatting (seconds)
        passes_performed: Actual number of passes executed
        passes_requested: Number of passes requested (may differ in convergence mode)
        sectors_processed: Total sectors read/written across all passes
        average_speed: Average sectors per second
        convergence_mode: Whether convergence mode was used
        converged: Whether disk converged (only meaningful in convergence mode)
        convergence_pass: Pass number where convergence occurred (or None)
        bad_sector_history: Bad sector counts after each pass

    Example:
        >>> stats = recover_disk(handle, geometry, convergence_mode=True)
        >>> format_stats = create_format_statistics(stats, geometry)
        >>> print(f"Duration: {format_stats.total_duration:.1f} seconds")
        >>> if format_stats.converged:
        ...     print(f"Converged after {format_stats.passes_performed} passes")
    """
    total_duration: float
    passes_performed: int
    passes_requested: int
    sectors_processed: int
    average_speed: float
    convergence_mode: bool
    converged: bool
    convergence_pass: Optional[int]
    bad_sector_history: List[int] = field(default_factory=list)

    def get_convergence_message(self) -> str:
        """
        Get human-readable convergence status message.

        Returns:
            Descriptive message about convergence status
        """
        if not self.convergence_mode:
            return f"Fixed mode: {self.passes_performed} passes executed"
        elif self.converged:
            return f"Converged after {self.convergence_pass} passes (optimal recovery achieved)"
        else:
            return f"Did not converge after {self.passes_performed} passes (may benefit from more passes)"


# =============================================================================
# Statistics Creation Functions
# =============================================================================


def create_comparison_statistics(
    initial_scan: SectorMap,
    final_scan: SectorMap,
    recovery_stats: Optional["RecoveryStatistics"] = None
) -> ComparisonStatistics:
    """
    Create before/after comparison statistics.

    Args:
        initial_scan: Sector map before recovery
        final_scan: Sector map after recovery
        recovery_stats: Optional recovery statistics for additional context

    Returns:
        ComparisonStatistics with complete analysis

    Example:
        >>> initial = scan_all_sectors(handle, geometry)
        >>> # ... perform recovery ...
        >>> final = scan_all_sectors(handle, geometry)
        >>> comparison = create_comparison_statistics(initial, final)
        >>> print(f"Status: {comparison.disk_status.value}")
        >>> print(comparison.usability_message)
    """
    initial_bad = len(initial_scan.bad_sectors)
    final_bad = len(final_scan.bad_sectors)
    recovered = initial_bad - final_bad

    # Calculate recovery rate
    if initial_bad > 0:
        recovery_rate = (recovered / initial_bad) * 100.0
    else:
        recovery_rate = 100.0  # No bad sectors to begin with

    # Determine disk status
    total_sectors = initial_scan.total_sectors
    final_bad_percentage = (final_bad / total_sectors) * 100.0

    if final_bad == 0:
        status = DiskStatus.PERFECT
        message = "Disk is fully functional with zero bad sectors. Safe for all uses including critical data."
    elif final_bad_percentage < 1.0:
        status = DiskStatus.GOOD
        message = f"Disk has {final_bad} bad sectors ({final_bad_percentage:.2f}%). Safe for most uses."
    elif final_bad_percentage < 5.0:
        status = DiskStatus.DEGRADED
        message = f"Disk has {final_bad} bad sectors ({final_bad_percentage:.2f}%). Usable but avoid critical data."
    elif final_bad_percentage < 20.0:
        status = DiskStatus.POOR
        message = f"Disk has {final_bad} bad sectors ({final_bad_percentage:.1f}%). Significant reliability concerns."
    else:
        status = DiskStatus.UNUSABLE
        message = f"Disk has {final_bad} bad sectors ({final_bad_percentage:.1f}%). Should be replaced."

    return ComparisonStatistics(
        initial_bad_sectors=initial_bad,
        final_bad_sectors=final_bad,
        sectors_recovered=recovered,
        recovery_rate=recovery_rate,
        total_sectors=total_sectors,
        permanently_bad_sectors=final_scan.bad_sectors.copy(),
        disk_status=status,
        usability_message=message
    )


def create_format_statistics(
    recovery_stats: "RecoveryStatistics",
    total_sectors: int = 2880
) -> FormatStatistics:
    """
    Create format operation statistics from recovery stats.

    Args:
        recovery_stats: Statistics from recover_disk()
        total_sectors: Total sectors on disk (default: 2880 for 1.44MB)

    Returns:
        FormatStatistics with complete analysis

    Example:
        >>> recovery = recover_disk(handle, geometry, convergence_mode=True)
        >>> format_stats = create_format_statistics(recovery)
        >>> print(format_stats.get_convergence_message())
    """
    # Calculate sectors processed (scans + format operations)
    # Each pass involves: 1 scan + format of all tracks
    sectors_processed = total_sectors * (recovery_stats.passes_executed + 1)

    # Calculate average speed
    if recovery_stats.recovery_duration > 0:
        average_speed = sectors_processed / recovery_stats.recovery_duration
    else:
        average_speed = 0.0

    return FormatStatistics(
        total_duration=recovery_stats.recovery_duration,
        passes_performed=recovery_stats.passes_executed,
        passes_requested=recovery_stats.passes_executed,  # May differ in convergence mode
        sectors_processed=sectors_processed,
        average_speed=average_speed,
        convergence_mode=recovery_stats.convergence_mode,
        converged=recovery_stats.converged,
        convergence_pass=recovery_stats.convergence_pass,
        bad_sector_history=recovery_stats.bad_sector_history.copy()
    )


# =============================================================================
# Progress Tracking
# =============================================================================


@dataclass
class ProgressUpdate:
    """
    Real-time progress update during recovery.

    Attributes:
        current_pass: Current pass number (0-based)
        total_passes: Expected total passes (may be unknown in convergence mode)
        current_bad_sectors: Bad sector count after current pass
        previous_bad_sectors: Bad sector count after previous pass (or None)
        delta_absolute: Absolute change in bad sectors (negative = improvement)
        delta_percentage: Percentage change (negative = improvement)
        trend_indicator: Visual indicator: ↓ (improvement), → (no change), ↑ (worse)

    Example:
        >>> update = create_progress_update(pass_num=2, current_bad=45, previous_bad=89)
        >>> print(f"Pass {update.current_pass + 1}: {update.current_bad_sectors} bad")
        >>> print(f"  Change: {update.delta_absolute} sectors ({update.delta_percentage:+.1f}%)")
        >>> print(f"  Trend: {update.trend_indicator}")
    """
    current_pass: int
    total_passes: Optional[int]
    current_bad_sectors: int
    previous_bad_sectors: Optional[int]
    delta_absolute: Optional[int]
    delta_percentage: Optional[float]
    trend_indicator: str


def create_progress_update(
    pass_num: int,
    current_bad: int,
    previous_bad: Optional[int] = None,
    total_passes: Optional[int] = None
) -> ProgressUpdate:
    """
    Create a progress update for display.

    Args:
        pass_num: Current pass number (0-based)
        current_bad: Current bad sector count
        previous_bad: Previous bad sector count (or None for first pass)
        total_passes: Total expected passes (or None for convergence mode)

    Returns:
        ProgressUpdate with delta calculations and trend indicator

    Example:
        >>> update = create_progress_update(2, 45, 89)
        >>> print(f"{update.trend_indicator} {update.delta_absolute} sectors")
        ↓ -44 sectors
    """
    # Calculate deltas
    if previous_bad is not None:
        delta_abs = current_bad - previous_bad
        if previous_bad > 0:
            delta_pct = (delta_abs / previous_bad) * 100.0
        else:
            delta_pct = 0.0

        # Determine trend indicator
        if delta_abs < 0:
            indicator = "↓"  # Improvement
        elif delta_abs > 0:
            indicator = "↑"  # Worse
        else:
            indicator = "→"  # No change
    else:
        delta_abs = None
        delta_pct = None
        indicator = "·"  # Initial

    return ProgressUpdate(
        current_pass=pass_num,
        total_passes=total_passes,
        current_bad_sectors=current_bad,
        previous_bad_sectors=previous_bad,
        delta_absolute=delta_abs,
        delta_percentage=delta_pct,
        trend_indicator=indicator
    )


def format_progress_line(update: ProgressUpdate) -> str:
    """
    Format a progress update as a single-line string.

    Args:
        update: Progress update to format

    Returns:
        Formatted string suitable for display

    Example:
        >>> update = create_progress_update(2, 45, 89)
        >>> print(format_progress_line(update))
        Pass 3: 45 bad sectors  (↓ -44, -49.4%)
    """
    line_parts = [f"Pass {update.current_pass + 1}"]

    if update.total_passes is not None:
        line_parts[0] += f"/{update.total_passes}"

    line_parts.append(f": {update.current_bad_sectors} bad sectors")

    if update.delta_absolute is not None:
        line_parts.append(f"  ({update.trend_indicator} {update.delta_absolute:+d}, {update.delta_percentage:+.1f}%)")

    return "".join(line_parts)


# =============================================================================
# History Graph Generation
# =============================================================================


def generate_history_graph(
    bad_sector_history: List[int],
    width: int = 60,
    height: int = 10
) -> str:
    """
    Generate text-based graph showing bad sector progression.

    Creates an ASCII art graph showing how bad sector count changed
    across recovery passes. Useful for visualizing convergence.

    Args:
        bad_sector_history: List of bad sector counts (one per pass)
        width: Graph width in characters (default: 60)
        height: Graph height in lines (default: 10)

    Returns:
        Multi-line string containing the graph

    Example:
        >>> history = [147, 89, 45, 23, 12, 12, 12]
        >>> graph = generate_history_graph(history)
        >>> print(graph)
        [Shows ASCII art graph of convergence]
    """
    if len(bad_sector_history) < 2:
        return "Insufficient data for graph"

    # Find min and max values for scaling
    min_val = min(bad_sector_history)
    max_val = max(bad_sector_history)
    value_range = max_val - min_val

    if value_range == 0:
        # All values are the same
        value_range = 1

    # Create empty graph
    graph = [[' ' for _ in range(width)] for _ in range(height)]

    # Scale data points to graph dimensions
    for i, value in enumerate(bad_sector_history):
        if i >= width:
            break

        # Calculate y position (inverted - 0 is top)
        normalized = (value - min_val) / value_range
        y = height - 1 - int(normalized * (height - 1))

        # Plot point
        graph[y][i] = '█'

        # Connect to previous point
        if i > 0:
            prev_value = bad_sector_history[i - 1]
            prev_normalized = (prev_value - min_val) / value_range
            prev_y = height - 1 - int(prev_normalized * (height - 1))

            # Draw vertical line between points
            if prev_y < y:
                for row in range(prev_y + 1, y):
                    graph[row][i - 1] = '│'
            elif prev_y > y:
                for row in range(y + 1, prev_y):
                    graph[row][i - 1] = '│'

    # Convert graph to string with axis labels
    lines = []
    lines.append(f"Bad Sectors: {max_val} ┐")

    for row in graph:
        line = "".join(row)
        lines.append(f"             │{line}")

    lines.append(f"             {min_val} └" + "─" * width)
    lines.append(f"             Pass: 0{' ' * (width - 10)}{len(bad_sector_history) - 1}")

    return "\n".join(lines)
