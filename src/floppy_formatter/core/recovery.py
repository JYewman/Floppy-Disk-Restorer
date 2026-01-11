"""
Multi-pass recovery algorithms for floppy disk restoration.

This module implements sophisticated recovery strategies including:
- Fixed-pass recovery mode (user-specified number of passes)
- Convergence mode (automatic detection of optimal recovery)
- Pattern writing between passes for magnetic domain restoration
- Comprehensive recovery statistics tracking

The convergence algorithm automatically determines when a disk has
reached its best possible state without over-formatting.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Tuple

from floppy_formatter.core.device_manager import close_device
from floppy_formatter.core.geometry import DiskGeometry
from floppy_formatter.core.formatter import format_track
from floppy_formatter.core.sector_io import (
    write_track_pattern,
    read_sector,
    read_sector_multiread,
    get_pattern_for_pass,
    get_pattern_name,
)
from floppy_formatter.analysis.scanner import (
    scan_all_sectors,
    scan_track,
    SectorMap,
)


# =============================================================================
# Power Management (Linux)
# =============================================================================


def prevent_sleep() -> None:
    """
    Prevent system from entering sleep during long operations.

    On Linux, this is typically handled by systemd-inhibit or by the
    desktop environment. For now, this is a no-op placeholder.

    Users can manually prevent sleep using:
        systemd-inhibit --what=sleep --why="Floppy formatting" python -m floppy_formatter

    Example:
        >>> prevent_sleep()
        >>> try:
        ...     # Perform long-running disk operation
        ...     recover_disk(fd, geometry, convergence_mode=True)
        ... finally:
        ...     allow_sleep()
    """
    # Linux: No-op for now
    # Could potentially use systemd-inhibit or dbus calls
    pass


def allow_sleep() -> None:
    """
    Re-enable normal sleep behavior.

    On Linux, this restores normal power management if prevent_sleep()
    had any effect. Currently a no-op.

    Example:
        >>> prevent_sleep()
        >>> try:
        ...     recover_disk(fd, geometry)
        ... finally:
        ...     allow_sleep()  # Always restore in finally block
    """
    # Linux: No-op for now
    pass


# =============================================================================
# Recovery Statistics
# =============================================================================


@dataclass
class RecoveryStatistics:
    """
    Comprehensive statistics from a recovery operation.

    Attributes:
        initial_bad_sectors: Bad sector count before recovery
        final_bad_sectors: Bad sector count after recovery
        sectors_recovered: Number of sectors successfully recovered
        passes_executed: Number of format passes performed
        convergence_mode: Whether convergence mode was used
        converged: Whether disk converged (stable bad sector count)
        convergence_pass: Pass number where convergence occurred (or None)
        bad_sector_history: List of bad sector counts after each pass
        recovery_duration: Total time spent on recovery (seconds)
        patterns_used: List of patterns written during recovery

    Example:
        >>> stats = recover_disk(fd, geometry, convergence_mode=True)
        >>> print(f"Recovered: {stats.sectors_recovered} sectors")
        >>> if stats.converged:
        ...     print(f"Converged after {stats.passes_executed} passes")
        >>> else:
        ...     print("Did not converge - physical damage likely")
    """
    initial_bad_sectors: int
    final_bad_sectors: int
    sectors_recovered: int
    passes_executed: int
    convergence_mode: bool
    converged: bool
    convergence_pass: Optional[int]
    bad_sector_history: List[int] = field(default_factory=list)
    recovery_duration: float = 0.0
    patterns_used: List[int] = field(default_factory=list)

    def get_recovery_rate(self) -> float:
        """
        Get recovery success rate as percentage.

        Returns:
            Percentage of bad sectors recovered (0.0 to 100.0)
        """
        if self.initial_bad_sectors == 0:
            return 0.0
        return (self.sectors_recovered / self.initial_bad_sectors) * 100.0

    def get_improvement_per_pass(self) -> float:
        """
        Get average sectors recovered per pass.

        Returns:
            Average number of sectors recovered per pass
        """
        if self.passes_executed == 0:
            return 0.0
        return self.sectors_recovered / self.passes_executed

    def was_successful(self) -> bool:
        """
        Determine if recovery was successful.

        Recovery is considered successful if:
        - At least 70% of bad sectors were recovered, OR
        - Disk converged (indicating remaining bad sectors are physical damage)

        Returns:
            True if recovery was successful
        """
        recovery_rate = self.get_recovery_rate()
        return recovery_rate >= 70.0 or self.converged


# =============================================================================
# Format Pass Operations
# =============================================================================


def perform_format_pass(
    fd,
    geometry: DiskGeometry,
    pass_num: int,
    total_passes: int,
    bad_sector_count: int,
    converged: bool,
    progress_callback: Optional[Callable[[int, int, int, int, int, bool], None]] = None
) -> None:
    """
    Perform a single format pass with pattern writing.

    This function executes one complete format pass:
    1. Select pattern based on pass number (rotates through 0x55, 0xAA, 0xFF, 0x00)
    2. Write pattern to each track
    3. Format each track
    4. Add inter-pass delay for disk settling

    Pattern writing helps restore weak magnetic domains, improving
    sector reliability. Different patterns stress different aspects
    of the magnetic coating.

    Args:
        fd: File descriptor to physical drive
        geometry: Disk geometry information
        pass_num: Current pass number (0-based)
        total_passes: Total number of passes
        bad_sector_count: Current bad sector count
        converged: Whether convergence detected
        progress_callback: Optional function(pass_num, total_passes, current_sector, total_sectors, bad_sector_count, converged)

    Example:
        >>> # Perform 3 passes manually
        >>> for pass_num in range(3):
        ...     print(f"Pass {pass_num + 1}/3")
        ...     perform_format_pass(fd, geometry, pass_num)
        ...     print("Pass complete, scanning...")
        ...     scan = scan_all_sectors(fd, geometry)
        ...     print(f"Bad sectors: {len(scan.bad_sectors)}")
    """
    # Select pattern for this pass (rotates through 4 patterns)
    pattern = get_pattern_for_pass(pass_num)

    # Format each track with pattern writing
    total_sectors = geometry.total_sectors
    for cylinder in range(geometry.cylinders):
        for head in range(geometry.heads):
            # Write pattern to all sectors in this track
            # This helps restore weak magnetic areas
            write_track_pattern(fd, cylinder, head, pattern, geometry)

            # Format the track
            success, bad_count, bad_tracks, error = format_track(
                fd, cylinder, head, geometry
            )

            # Note: We don't raise errors here - let the scan after pass
            # detect any issues. Some tracks may fail but others succeed.

            # Calculate current sector number (track number * sectors per track)
            current_track = cylinder * geometry.heads + head
            current_sector = (current_track + 1) * geometry.sectors_per_track

            # Report progress if callback provided
            if progress_callback is not None:
                try:
                    progress_callback(
                        pass_num,
                        total_passes,
                        current_sector,
                        total_sectors,
                        bad_sector_count,
                        converged
                    )
                except Exception as e:
                    import logging
                    logging.error(f"Progress callback error: {e}")

    # Inter-pass delay for disk settling
    # Allows magnetic domains to stabilize before next pass
    time.sleep(0.5)


# =============================================================================
# Recovery Algorithms
# =============================================================================


def recover_disk(
    fd,
    geometry: DiskGeometry,
    passes: int = 5,
    convergence_mode: bool = False,
    max_passes: int = 50,
    convergence_threshold: int = 3,
    multiread_mode: bool = False,
    multiread_attempts: int = 100,
    progress_callback: Optional[Callable[[int, int, int, int, int, bool], None]] = None
) -> RecoveryStatistics:
    """
    Recover a degraded floppy disk using multi-pass formatting.

    This function implements three recovery modes:

    **Fixed Pass Mode** (convergence_mode=False, multiread_mode=False):
    - Execute exactly N passes as specified by `passes` parameter
    - Predictable duration and disk wear
    - Use when you know how many passes are needed

    **Convergence Mode** (convergence_mode=True):
    - Continue formatting until bad sector count stabilizes
    - Automatic detection of optimal recovery point
    - Prevents over-formatting (unnecessary disk wear)
    - Stops when:
      * Same bad sector count for 3 consecutive passes (converged), OR
      * No improvement in last 5 passes (plateau), OR
      * Maximum passes reached (safety limit)

    **Multi-Read Mode** (multiread_mode=True):
    - Uses multi-read statistical data recovery on bad sectors
    - Performs multiple read attempts (default: 100) on each bad sector
    - Uses majority voting to reconstruct correct data byte-by-byte
    - After each format pass, attempts aggressive recovery on remaining bad sectors
    - Significantly slower but can recover marginally readable sectors
    - Best for disks with physical damage or weak magnetic domains

    Args:
        fd: File descriptor to physical drive
        geometry: Disk geometry information
        passes: Number of passes in fixed mode (default: 5)
        convergence_mode: Enable convergence detection (default: False)
        max_passes: Maximum passes in convergence mode (default: 50)
        convergence_threshold: Consecutive passes for convergence (default: 3)
        multiread_mode: Enable multi-read recovery (default: False)
        multiread_attempts: Read attempts per bad sector in multi-read mode (default: 100)
        progress_callback: Optional function(pass_num, total_passes, current_sector, total_sectors, bad_sector_count, converged)

    Returns:
        RecoveryStatistics with comprehensive recovery information

    Example - Fixed Pass Mode:
        >>> fd = open_device(drive_num)
        >>> geometry = get_disk_geometry(fd)
        >>> stats = recover_disk(fd, geometry, passes=5)
        >>> print(f"Recovery: {stats.get_recovery_rate():.1f}%")
        >>> print(f"Recovered {stats.sectors_recovered} sectors in 5 passes")
        >>> close_device(fd)

    Example - Convergence Mode:
        >>> def show_progress(cyl, head, pass_num):
        ...     track = cyl * 2 + head
        ...     print(f"Pass {pass_num + 1}, Track {track}/160")
        >>>
        >>> fd = open_device(drive_num)
        >>> geometry = get_disk_geometry(fd)
        >>> stats = recover_disk(
        ...     fd, geometry, convergence_mode=True,
        ...     progress_callback=show_progress
        ... )
        >>> if stats.converged:
        ...     print(f"Converged after {stats.passes_executed} passes")
        ...     print(f"Remaining {stats.final_bad_sectors} bad sectors are physical damage")
        >>> else:
        ...     print("Did not converge - may need more aggressive recovery")
        >>> close_device(fd)
    """
    # Record start time
    start_time = time.time()

    # Perform initial scan to establish baseline
    # Create a wrapper callback that reports scan progress as pass -1
    def initial_scan_callback(sector_num, total, is_good, error_type):
        if progress_callback is not None:
            try:
                # Report as pass -1 to indicate initial scan
                # Pass sector-level information as extra parameters
                # Extended callback: (pass_num, total_passes, current_sector, total_sectors, bad_sector_count, converged, is_good, error_type)
                # For backward compatibility, we try calling with extended parameters first
                try:
                    progress_callback(-1, 1, sector_num, total, 0, False, is_good, error_type)
                except TypeError:
                    # Fall back to original signature if callback doesn't support extended parameters
                    progress_callback(-1, 1, sector_num, total, 0, False)
            except:
                pass

    initial_scan = scan_all_sectors(fd, geometry, initial_scan_callback)
    initial_bad_count = len(initial_scan.bad_sectors)

    # Initialize recovery statistics
    stats = RecoveryStatistics(
        initial_bad_sectors=initial_bad_count,
        final_bad_sectors=initial_bad_count,  # Will be updated
        sectors_recovered=0,  # Will be updated
        passes_executed=0,
        convergence_mode=convergence_mode,
        converged=False,
        convergence_pass=None,
        bad_sector_history=[initial_bad_count],
    )

    if convergence_mode:
        # =====================================================================
        # Convergence Mode: Format until bad sector count stabilizes
        # =====================================================================

        for pass_num in range(max_passes):
            # Record pattern used
            pattern = get_pattern_for_pass(pass_num)
            stats.patterns_used.append(pattern)

            # Perform format pass
            current_bad_count = stats.bad_sector_history[-1] if stats.bad_sector_history else 0
            perform_format_pass(fd, geometry, pass_num, max_passes, current_bad_count, stats.converged, progress_callback)
            stats.passes_executed += 1

            # Scan after pass to check progress
            scan_result = scan_all_sectors(fd, geometry)
            bad_count = len(scan_result.bad_sectors)

            # Multi-read mode: Attempt aggressive recovery on remaining bad sectors
            if multiread_mode and bad_count > 0:
                multiread_recovered = 0
                for bad_sector in scan_result.bad_sectors:
                    success, data, error, attempts = read_sector_multiread(
                        fd, bad_sector, max_attempts=multiread_attempts,
                        bytes_per_sector=geometry.bytes_per_sector
                    )
                    if success and attempts > 1:
                        # Successfully recovered via statistical analysis
                        multiread_recovered += 1

                # Update bad count after multi-read recovery
                if multiread_recovered > 0:
                    # Re-scan to get actual bad count
                    scan_result = scan_all_sectors(fd, geometry)
                    bad_count = len(scan_result.bad_sectors)

            stats.bad_sector_history.append(bad_count)

            # Notify UI of pass completion (pass_num = -2 signals pass complete)
            if progress_callback is not None:
                try:
                    previous_count = stats.bad_sector_history[-2] if len(stats.bad_sector_history) >= 2 else None
                    # Call with pass_num=-2, pass number in total_passes, bad count in current_sector, previous in total_sectors
                    progress_callback(-2, pass_num, bad_count, previous_count or 0, 0, False)
                except:
                    pass

            # Check for convergence (PRIMARY CONDITION)
            # Same bad sector count for N consecutive passes
            if len(stats.bad_sector_history) >= convergence_threshold + 1:
                last_n = stats.bad_sector_history[-convergence_threshold:]
                if len(set(last_n)) == 1:  # All same value
                    # Converged - bad sectors are physically damaged
                    stats.converged = True
                    stats.convergence_pass = pass_num
                    break

            # Check for plateau (SECONDARY CONDITION)
            # No improvement in last 5 passes
            if len(stats.bad_sector_history) >= 6:
                last_5 = stats.bad_sector_history[-5:]
                if len(set(last_5)) == 1:  # All same value
                    # Plateaued - further passes unlikely to help
                    stats.converged = True
                    stats.convergence_pass = pass_num
                    break

        # Final scan after convergence
        final_scan = scan_all_sectors(fd, geometry)

    else:
        # =====================================================================
        # Fixed Pass Mode: Execute exactly N passes
        # =====================================================================

        for pass_num in range(passes):
            # Record pattern used
            pattern = get_pattern_for_pass(pass_num)
            stats.patterns_used.append(pattern)

            # Perform format pass
            current_bad_count = stats.bad_sector_history[-1] if stats.bad_sector_history else 0
            perform_format_pass(fd, geometry, pass_num, passes, current_bad_count, False, progress_callback)
            stats.passes_executed += 1

            # Scan after pass to track progress
            scan_result = scan_all_sectors(fd, geometry)
            bad_count = len(scan_result.bad_sectors)

            # Multi-read mode: Attempt aggressive recovery on remaining bad sectors
            if multiread_mode and bad_count > 0:
                multiread_recovered = 0
                for bad_sector in scan_result.bad_sectors:
                    success, data, error, attempts = read_sector_multiread(
                        fd, bad_sector, max_attempts=multiread_attempts,
                        bytes_per_sector=geometry.bytes_per_sector
                    )
                    if success and attempts > 1:
                        # Successfully recovered via statistical analysis
                        multiread_recovered += 1

                # Update bad count after multi-read recovery
                if multiread_recovered > 0:
                    # Re-scan to get actual bad count
                    scan_result = scan_all_sectors(fd, geometry)
                    bad_count = len(scan_result.bad_sectors)

            stats.bad_sector_history.append(bad_count)

            # Notify UI of pass completion
            if progress_callback is not None:
                try:
                    previous_count = stats.bad_sector_history[-2] if len(stats.bad_sector_history) >= 2 else None
                    progress_callback(-2, pass_num, bad_count, previous_count or 0, 0, False)
                except:
                    pass

        # Final scan
        final_scan = scan_all_sectors(fd, geometry)

    # Update final statistics
    stats.final_bad_sectors = len(final_scan.bad_sectors)
    stats.sectors_recovered = stats.initial_bad_sectors - stats.final_bad_sectors
    stats.recovery_duration = time.time() - start_time

    return stats


def recover_bad_sectors_only(
    fd,
    geometry: DiskGeometry,
    bad_sector_list: List[int],
    passes: int = 5,
    multiread_mode: bool = False,
    multiread_attempts: int = 100,
    progress_callback: Optional[Callable[[int, int, int, int, int, bool], None]] = None
) -> RecoveryStatistics:
    """
    Targeted recovery that focuses ONLY on known bad sectors.

    Instead of reformatting the entire disk, this function:
    1. Identifies which tracks contain bad sectors
    2. Only formats those specific tracks
    3. Optionally applies multi-read recovery to remaining bad sectors

    This is much faster than full disk recovery and preserves data on good tracks.

    Args:
        fd: File descriptor to physical drive
        geometry: Disk geometry information
        bad_sector_list: List of bad sector numbers to target
        passes: Number of recovery passes per track (default: 5)
        multiread_mode: Enable multi-read recovery (default: False)
        multiread_attempts: Read attempts per bad sector in multi-read mode (default: 100)
        progress_callback: Optional function(pass_num, total_passes, current_sector, total_sectors, bad_sector_count, converged)

    Returns:
        RecoveryStatistics with recovery information

    Example:
        >>> # Initial scan finds 50 bad sectors
        >>> initial_scan = scan_all_sectors(fd, geometry)
        >>> bad_sectors = initial_scan.bad_sectors
        >>>
        >>> # Targeted recovery - only fix those 50 sectors
        >>> stats = recover_bad_sectors_only(fd, geometry, bad_sectors, passes=5)
        >>> print(f"Targeted recovery: {stats.sectors_recovered} sectors recovered")
        >>> print(f"Only formatted {len(set(bad_sectors) // 18)} tracks instead of 160!")
    """
    start_time = time.time()

    # Initialize statistics
    initial_bad_count = len(bad_sector_list)
    stats = RecoveryStatistics(
        initial_bad_sectors=initial_bad_count,
        final_bad_sectors=initial_bad_count,
        sectors_recovered=0,
        passes_executed=0,
        convergence_mode=False,
        converged=False,
        convergence_pass=None,
        bad_sector_history=[initial_bad_count],
        recovery_duration=0.0,
        patterns_used=[]
    )

    if initial_bad_count == 0:
        # No bad sectors to recover
        stats.recovery_duration = time.time() - start_time
        return stats

    # Identify unique tracks that contain bad sectors
    bad_tracks = set()
    for sector_num in bad_sector_list:
        track_num = sector_num // geometry.sectors_per_track
        cylinder = track_num // geometry.heads
        head = track_num % geometry.heads
        bad_tracks.add((cylinder, head))

    total_tracks = len(bad_tracks)

    # Perform recovery passes on affected tracks only
    for pass_num in range(passes):
        pattern = get_pattern_for_pass(pass_num)
        stats.patterns_used.append(pattern)

        track_count = 0
        for cylinder, head in sorted(bad_tracks):
            # Write pattern to track
            write_track_pattern(fd, cylinder, head, pattern, geometry)

            # Format the track
            format_track(fd, cylinder, head, geometry)

            track_count += 1

            # Report progress
            if progress_callback is not None:
                try:
                    # Calculate approximate sector progress
                    current_sector = track_count * geometry.sectors_per_track
                    total_sectors = total_tracks * geometry.sectors_per_track
                    progress_callback(pass_num, passes, current_sector, total_sectors, len(bad_sector_list), False)
                except:
                    pass

        stats.passes_executed += 1

        # Scan only the affected tracks to check progress
        remaining_bad = []
        for sector_num in bad_sector_list:
            success, data, error_code = read_sector(fd, sector_num, geometry.bytes_per_sector)
            if not success:
                remaining_bad.append(sector_num)

        bad_count = len(remaining_bad)

        # Multi-read mode: Attempt aggressive recovery on remaining bad sectors
        if multiread_mode and bad_count > 0:
            multiread_recovered = 0
            for bad_sector in remaining_bad[:]:  # Copy list since we'll modify
                success, data, error, attempts = read_sector_multiread(
                    fd, bad_sector, max_attempts=multiread_attempts,
                    bytes_per_sector=geometry.bytes_per_sector
                )
                if success and attempts > 1:
                    multiread_recovered += 1
                    remaining_bad.remove(bad_sector)

            bad_count = len(remaining_bad)

        stats.bad_sector_history.append(bad_count)

        # Notify UI of pass completion
        if progress_callback is not None:
            try:
                previous_count = stats.bad_sector_history[-2] if len(stats.bad_sector_history) >= 2 else None
                progress_callback(-2, pass_num, bad_count, previous_count or 0, 0, False)
            except:
                pass

        # Update bad sector list for next pass
        bad_sector_list = remaining_bad

        # If all sectors recovered, we're done
        if bad_count == 0:
            break

    # Update final statistics
    stats.final_bad_sectors = len(remaining_bad)
    stats.sectors_recovered = stats.initial_bad_sectors - stats.final_bad_sectors
    stats.recovery_duration = time.time() - start_time

    return stats


def recover_track(
    fd,
    cylinder: int,
    head: int,
    geometry: DiskGeometry,
    passes: int = 5,
    progress_callback: Optional[Callable[[int], None]] = None
) -> Tuple[int, int]:
    """
    Recover a single track using multi-pass pattern writing.

    This function focuses recovery efforts on a specific track,
    useful for targeted recovery of problem areas.

    Args:
        fd: File descriptor to physical drive
        cylinder: Cylinder number (0-79)
        head: Head number (0-1)
        geometry: Disk geometry information
        passes: Number of recovery passes (default: 5)
        progress_callback: Optional function(current_pass)

    Returns:
        Tuple of (initial_bad_sectors, final_bad_sectors)

    Example:
        >>> # Recover problematic track 15, head 0
        >>> fd = open_device(drive_num)
        >>> geometry = get_disk_geometry(fd)
        >>> initial, final = recover_track(fd, 15, 0, geometry, passes=10)
        >>> print(f"Track recovery: {initial} bad → {final} bad")
        >>> if final == 0:
        ...     print("Track fully recovered!")
        >>> close_device(fd)
    """
    # Scan track before recovery
    initial_track = scan_track(fd, cylinder, head, geometry)
    initial_bad_count = len(initial_track.bad_sectors)

    # Perform recovery passes
    for pass_num in range(passes):
        # Select pattern for this pass
        pattern = get_pattern_for_pass(pass_num)

        # Write pattern to track
        write_track_pattern(fd, cylinder, head, pattern, geometry)

        # Format the track
        format_track(fd, cylinder, head, geometry)

        # Report progress if callback provided
        if progress_callback is not None:
            progress_callback(pass_num + 1)

        # Small delay between passes
        time.sleep(0.1)

    # Scan track after recovery
    final_track = scan_track(fd, cylinder, head, geometry)
    final_bad_count = len(final_track.bad_sectors)

    return (initial_bad_count, final_bad_count)


def retry_bad_sectors(
    fd,
    bad_sectors: List[int],
    geometry: DiskGeometry,
    max_retries: int = 10,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Tuple[List[int], List[int]]:
    """
    Retry reading bad sectors with exponential backoff delays.

    Some sectors may be temporarily unreadable due to timing issues.
    This function attempts multiple reads with increasing delays to
    give the drive more time to stabilize.

    Args:
        fd: File descriptor to physical drive
        bad_sectors: List of bad sector numbers to retry
        geometry: Disk geometry information
        max_retries: Maximum retry attempts per sector (default: 10)
        progress_callback: Optional function(current_sector, total_sectors)

    Returns:
        Tuple of (recovered_sectors, still_bad_sectors)

    Example:
        >>> # After initial scan shows bad sectors
        >>> scan = scan_all_sectors(fd, geometry)
        >>> if scan.bad_sectors:
        ...     recovered, still_bad = retry_bad_sectors(
        ...         fd, scan.bad_sectors, geometry
        ...     )
        ...     print(f"Retry recovered {len(recovered)} sectors")
        ...     print(f"Still bad: {len(still_bad)} sectors")
    """
    recovered_sectors = []
    still_bad_sectors = []

    for idx, sector_num in enumerate(bad_sectors):
        sector_recovered = False

        # Try reading with increasing delays
        for retry in range(max_retries):
            # Exponential backoff delay (0.1s, 0.2s, 0.4s, 0.8s, ...)
            if retry > 0:
                delay = 0.1 * (2 ** (retry - 1))
                time.sleep(min(delay, 2.0))  # Cap at 2 seconds

            # Attempt to read sector
            success, data, error = read_sector(
                fd, sector_num, geometry.bytes_per_sector
            )

            if success:
                # Sector read successfully
                recovered_sectors.append(sector_num)
                sector_recovered = True
                break

        if not sector_recovered:
            # Sector still bad after all retries
            still_bad_sectors.append(sector_num)

        # Report progress if callback provided
        if progress_callback is not None:
            progress_callback(idx + 1, len(bad_sectors))

    return (recovered_sectors, still_bad_sectors)


# =============================================================================
# Recovery Analysis
# =============================================================================


def analyze_convergence(bad_sector_history: List[int]) -> Tuple[bool, Optional[int], str]:
    """
    Analyze bad sector history to determine if/when convergence occurred.

    Args:
        bad_sector_history: List of bad sector counts after each pass

    Returns:
        Tuple of (converged, convergence_pass, analysis_message)

    Example:
        >>> history = [147, 89, 45, 23, 12, 12, 12]
        >>> converged, pass_num, msg = analyze_convergence(history)
        >>> print(msg)
        Converged after pass 4 (12 bad sectors stable for 3 passes)
    """
    if len(bad_sector_history) < 2:
        return (False, None, "Insufficient data for convergence analysis")

    # Check for convergence (3 consecutive same values)
    convergence_threshold = 3
    for i in range(len(bad_sector_history) - convergence_threshold + 1):
        window = bad_sector_history[i:i + convergence_threshold]
        if len(set(window)) == 1:  # All same value
            converged_value = window[0]
            convergence_pass = i + convergence_threshold - 1
            return (
                True,
                convergence_pass,
                f"Converged after pass {convergence_pass} "
                f"({converged_value} bad sectors stable for {convergence_threshold} passes)"
            )

    # Check for plateau (no improvement in last 5 passes)
    if len(bad_sector_history) >= 6:
        last_5 = bad_sector_history[-5:]
        if len(set(last_5)) == 1:
            plateau_value = last_5[0]
            return (
                True,
                len(bad_sector_history) - 1,
                f"Plateaued at {plateau_value} bad sectors (no improvement in last 5 passes)"
            )

    return (False, None, "No convergence detected - recovery still progressing")


def get_recovery_recommendation(stats: RecoveryStatistics) -> str:
    """
    Get recommendation based on recovery results.

    Args:
        stats: Recovery statistics from recover_disk()

    Returns:
        Human-readable recommendation string

    Example:
        >>> stats = recover_disk(fd, geometry, convergence_mode=True)
        >>> recommendation = get_recovery_recommendation(stats)
        >>> print(recommendation)
    """
    recovery_rate = stats.get_recovery_rate()

    if stats.final_bad_sectors == 0:
        return (
            "✓ Perfect recovery! Disk is fully functional with no bad sectors. "
            "Safe for critical data storage."
        )
    elif recovery_rate >= 90.0 and stats.converged:
        return (
            f"✓ Excellent recovery ({recovery_rate:.1f}%). "
            f"Remaining {stats.final_bad_sectors} bad sectors are physical damage. "
            "Disk is usable for non-critical data."
        )
    elif recovery_rate >= 70.0 and stats.converged:
        return (
            f"✓ Good recovery ({recovery_rate:.1f}%). "
            f"Remaining {stats.final_bad_sectors} bad sectors are physical damage. "
            "Disk is degraded but usable. Avoid storing critical data."
        )
    elif recovery_rate >= 70.0 and not stats.converged:
        return (
            f"⚠ Moderate recovery ({recovery_rate:.1f}%) but did not converge. "
            "Try additional recovery passes or more aggressive recovery methods."
        )
    elif stats.converged:
        return (
            f"⚠ Limited recovery ({recovery_rate:.1f}%). "
            f"{stats.final_bad_sectors} bad sectors are physical damage. "
            "Disk has significant physical damage. Consider replacement."
        )
    else:
        return (
            f"✗ Poor recovery ({recovery_rate:.1f}%) and did not converge. "
            "Disk may have severe physical damage. Consider professional data recovery "
            "or disk replacement."
        )
