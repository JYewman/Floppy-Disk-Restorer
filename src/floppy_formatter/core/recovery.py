"""
Multi-pass recovery algorithms for floppy disk restoration.

This module implements sophisticated recovery strategies including:
- Fixed-pass recovery mode (user-specified number of passes)
- Convergence mode (automatic detection of optimal recovery)
- Pattern writing between passes for magnetic domain restoration
- Comprehensive recovery statistics tracking
- Flux-level multi-read statistical recovery (with Greaseweazle)

Recovery Levels (Phase 4 Enhancement):
- STANDARD: Traditional multi-pass recovery (existing algorithms preserved)
- AGGRESSIVE: Multi-capture + PLL tuning before giving up on sectors
- FORENSIC: All techniques including bit-slip recovery, maximum effort

The convergence algorithm automatically determines when a disk has
reached its best possible state without over-formatting.

Updated for Greaseweazle: Uses flux-level operations for more precise
recovery with multi-revolution captures and statistical bit voting.
All original recovery algorithms are preserved - only the I/O layer changed.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Tuple, Union, Any, Dict
from enum import Enum, auto

from floppy_formatter.core.geometry import DiskGeometry
from floppy_formatter.core.formatter import format_track
from floppy_formatter.core.sector_adapter import (
    write_track_pattern,
    read_sector,
    read_sector_by_lba,
    read_sector_multiread,
    get_pattern_for_pass,
    get_pattern_name,
    wake_up_device,
    reset_error_tracking,
    motor_keepalive,
    should_attempt_usb_reset,
    flush_flux_cache,
    invalidate_track_cache,
    ERROR_SUCCESS,
)
from floppy_formatter.analysis.scanner import (
    scan_all_sectors,
    scan_track,
    SectorMap,
)
from floppy_formatter.hardware import GreaseweazleDevice
from floppy_formatter.hardware.flux_io import FluxReader


# =============================================================================
# Recovery Levels (Phase 4)
# =============================================================================


class RecoveryLevel(Enum):
    """
    Recovery aggressiveness levels.

    STANDARD: Traditional multi-pass recovery (existing algorithms preserved)
        - Pattern writing between passes (0x00, 0xFF, 0x55, 0xAA)
        - Optional multi-read statistical recovery
        - Fastest but may leave marginally recoverable sectors

    AGGRESSIVE: Multi-capture + PLL tuning before giving up
        - Everything in STANDARD
        - Multi-revolution flux capture with statistical bit voting
        - PLL parameter optimization for marginal sectors
        - Significantly better recovery rate for degraded disks

    FORENSIC: All techniques, maximum effort, detailed logging
        - Everything in AGGRESSIVE
        - Bit-slip detection and correction
        - Surface treatment (degauss + pattern refresh)
        - Comprehensive logging for analysis
        - Slowest but maximum possible recovery
    """
    STANDARD = auto()
    AGGRESSIVE = auto()
    FORENSIC = auto()


# =============================================================================
# Advanced Recovery Module Imports (Lazy Loading)
# =============================================================================


def _get_multi_capture():
    """Lazy import of multi_capture module."""
    from floppy_formatter.recovery import (
        capture_multiple_revolutions,
        align_flux_captures,
        reconstruct_from_captures,
        multi_capture_recover_sector,
    )
    return {
        'capture_multiple_revolutions': capture_multiple_revolutions,
        'align_flux_captures': align_flux_captures,
        'reconstruct_from_captures': reconstruct_from_captures,
        'multi_capture_recover_sector': multi_capture_recover_sector,
    }


def _get_pll_tuning():
    """Lazy import of pll_tuning module."""
    from floppy_formatter.recovery import (
        find_optimal_pll,
        optimize_for_sector,
        default_pll_parameters,
    )
    return {
        'find_optimal_pll': find_optimal_pll,
        'optimize_for_sector': optimize_for_sector,
        'default_pll_parameters': default_pll_parameters,
    }


def _get_bit_slip_recovery():
    """Lazy import of bit_slip_recovery module."""
    from floppy_formatter.recovery import (
        detect_bit_slips,
        reconstruct_slipped_sector,
    )
    return {
        'detect_bit_slips': detect_bit_slips,
        'reconstruct_slipped_sector': reconstruct_slipped_sector,
    }


def _get_surface_treatment():
    """Lazy import of surface_treatment module."""
    from floppy_formatter.recovery import (
        refresh_track,
        treat_weak_sector,
        degauss_track,
    )
    return {
        'refresh_track': refresh_track,
        'treat_weak_sector': treat_weak_sector,
        'degauss_track': degauss_track,
    }


# =============================================================================
# Cache Management
# =============================================================================


def flush_device_cache(device: Union[GreaseweazleDevice, Any]) -> None:
    """
    Flush internal caches and prepare for fresh disk reads.

    This is CRITICAL for accurate scanning after format passes. Without
    flushing, cached data may be returned instead of reading from the
    physical disk, making bad sectors appear "good".

    With Greaseweazle, this invalidates the internal track cache and
    ensures subsequent flux reads are fresh captures from the disk.

    Args:
        device: Connected GreaseweazleDevice instance
    """
    # Invalidate internal track cache
    flush_flux_cache(device)
    invalidate_track_cache()

    logging.debug("flush_device_cache: caches invalidated")

    # Wake up the device motor if needed
    wake_up_device(device)


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


@dataclass
class RestoreConfig:
    """
    Configuration for disk restoration operations.

    This dataclass preserves all existing recovery options while adding
    new Phase 4 advanced recovery capabilities.

    PRESERVED Fields (from original implementation):
        passes: Number of format passes (fixed mode)
        convergence_mode: Use convergence detection
        max_passes: Maximum passes in convergence mode
        convergence_threshold: Consecutive passes for convergence
        targeted_mode: Only recover bad sectors (preserve good data)
        multiread_mode: Enable multi-read statistical recovery
        multiread_attempts: Number of read attempts (now flux capture count)
        bad_sector_list: Pre-identified sectors to recover (targeted mode)

    NEW Fields (Phase 4):
        recovery_level: STANDARD, AGGRESSIVE, or FORENSIC
        pll_tuning: Enable PLL parameter optimization
        bit_slip_recovery: Enable bit-slip detection and correction
        surface_treatment: Enable degauss + pattern refresh for weak tracks
        detailed_logging: Enable comprehensive recovery logging

    Example:
        >>> config = RestoreConfig(
        ...     convergence_mode=True,
        ...     multiread_mode=True,
        ...     recovery_level=RecoveryLevel.AGGRESSIVE,
        ...     pll_tuning=True
        ... )
        >>> stats = recover_disk_with_config(device, geometry, config)
    """
    # PRESERVED: Original recovery options (all must continue to work)
    passes: int = 5
    convergence_mode: bool = False
    max_passes: int = 50
    convergence_threshold: int = 3
    targeted_mode: bool = False
    multiread_mode: bool = False
    multiread_attempts: int = 100  # Now used as flux capture count
    bad_sector_list: Optional[List[int]] = None

    # NEW: Phase 4 advanced recovery options
    recovery_level: RecoveryLevel = RecoveryLevel.STANDARD
    pll_tuning: bool = False
    bit_slip_recovery: bool = False
    surface_treatment: bool = False
    detailed_logging: bool = False

    def __post_init__(self):
        """Apply recovery level defaults."""
        # Automatically enable features based on recovery level
        if self.recovery_level == RecoveryLevel.AGGRESSIVE:
            # AGGRESSIVE enables multi-capture and PLL tuning by default
            if not self.multiread_mode:
                self.multiread_mode = True
            if not self.pll_tuning:
                self.pll_tuning = True

        elif self.recovery_level == RecoveryLevel.FORENSIC:
            # FORENSIC enables all advanced features
            if not self.multiread_mode:
                self.multiread_mode = True
            if not self.pll_tuning:
                self.pll_tuning = True
            if not self.bit_slip_recovery:
                self.bit_slip_recovery = True
            if not self.surface_treatment:
                self.surface_treatment = True
            if not self.detailed_logging:
                self.detailed_logging = True


@dataclass
class AdvancedRecoveryStats:
    """
    Statistics for Phase 4 advanced recovery techniques.

    Tracks which advanced techniques were used and their effectiveness.
    """
    # Multi-capture statistics
    multi_capture_attempts: int = 0
    multi_capture_successes: int = 0

    # PLL tuning statistics
    pll_tuning_attempts: int = 0
    pll_tuning_successes: int = 0

    # Bit-slip recovery statistics
    bit_slips_detected: int = 0
    bit_slips_corrected: int = 0

    # Surface treatment statistics
    tracks_treated: int = 0
    sectors_refreshed: int = 0

    # Per-technique recovery counts
    recovered_by_standard: int = 0
    recovered_by_multi_capture: int = 0
    recovered_by_pll_tuning: int = 0
    recovered_by_bit_slip: int = 0
    recovered_by_surface_treatment: int = 0

    def get_technique_effectiveness(self) -> Dict[str, float]:
        """Get success rate for each technique."""
        return {
            'multi_capture': (
                self.multi_capture_successes / max(1, self.multi_capture_attempts) * 100
            ),
            'pll_tuning': (
                self.pll_tuning_successes / max(1, self.pll_tuning_attempts) * 100
            ),
            'bit_slip': (
                self.bit_slips_corrected / max(1, self.bit_slips_detected) * 100
            ),
        }


# =============================================================================
# Format Pass Operations
# =============================================================================


def perform_format_pass(
    device: Union[GreaseweazleDevice, Any],
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
    2. Write pattern to each track using flux-level operations
    3. Format each track with DC erase and MFM encoding
    4. Add inter-pass delay for disk settling

    Pattern writing helps restore weak magnetic domains, improving
    sector reliability. Different patterns stress different aspects
    of the magnetic coating.

    Args:
        device: Connected GreaseweazleDevice instance
        geometry: Disk geometry information
        pass_num: Current pass number (0-based)
        total_passes: Total number of passes
        bad_sector_count: Current bad sector count
        converged: Whether convergence detected
        progress_callback: Optional function(pass_num, total_passes, current_sector, total_sectors, bad_sector_count, converged)

    Example:
        >>> # Perform 3 passes manually
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     for pass_num in range(3):
        ...         print(f"Pass {pass_num + 1}/3")
        ...         perform_format_pass(device, geometry, pass_num, 3, 0, False)
        ...         print("Pass complete, scanning...")
        ...         scan = scan_all_sectors(device, geometry)
        ...         print(f"Bad sectors: {len(scan.bad_sectors)}")
    """
    # Select pattern for this pass (rotates through 4 patterns)
    pattern = get_pattern_for_pass(pass_num)

    # Format each track with pattern writing
    total_sectors = geometry.total_sectors
    for cylinder in range(geometry.cylinders):
        for head in range(geometry.heads):
            # Motor keepalive - with Greaseweazle we have direct motor control
            # so this is mainly for tracking activity
            motor_keepalive(device)

            # Write pattern to all sectors in this track
            # This helps restore weak magnetic areas
            write_track_pattern(device, cylinder, head, pattern, geometry)

            # Format the track using flux-level operations
            success, bad_count, bad_tracks, error = format_track(
                device, cylinder, head, geometry
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
                    logging.error(f"Progress callback error: {e}")

    # Inter-pass delay for disk settling
    # Allows magnetic domains to stabilize before next pass
    time.sleep(0.5)


# =============================================================================
# Recovery Algorithms
# =============================================================================


def _lba_to_chs(lba: int, geometry: DiskGeometry) -> Tuple[int, int, int]:
    """Convert LBA to CHS for multiread operations."""
    sectors_per_cylinder = geometry.sectors_per_track * geometry.heads
    cylinder = lba // sectors_per_cylinder
    remainder = lba % sectors_per_cylinder
    head = remainder // geometry.sectors_per_track
    sector = (remainder % geometry.sectors_per_track) + 1  # Sectors are 1-indexed
    return (cylinder, head, sector)


def recover_disk(
    device: Union[GreaseweazleDevice, Any],
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
    - Uses multi-revolution flux capture with statistical bit voting
    - Performs multiple flux captures (default: 100) per bad sector
    - Uses majority voting to reconstruct correct data byte-by-byte
    - After each format pass, attempts aggressive recovery on remaining bad sectors
    - Significantly slower but can recover marginally readable sectors
    - Best for disks with physical damage or weak magnetic domains
    - Enhanced with Greaseweazle: Works at flux level for better accuracy

    Args:
        device: Connected GreaseweazleDevice instance
        geometry: Disk geometry information
        passes: Number of passes in fixed mode (default: 5)
        convergence_mode: Enable convergence detection (default: False)
        max_passes: Maximum passes in convergence mode (default: 50)
        convergence_threshold: Consecutive passes for convergence (default: 3)
        multiread_mode: Enable multi-read recovery (default: False)
        multiread_attempts: Flux capture count in multi-read mode (default: 100)
        progress_callback: Optional function(pass_num, total_passes, current_sector, total_sectors, bad_sector_count, converged)

    Returns:
        RecoveryStatistics with comprehensive recovery information

    Example - Fixed Pass Mode:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     geometry = get_greaseweazle_geometry(device)
        ...     stats = recover_disk(device, geometry, passes=5)
        ...     print(f"Recovery: {stats.get_recovery_rate():.1f}%")
        ...     print(f"Recovered {stats.sectors_recovered} sectors in 5 passes")

    Example - Convergence Mode:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     geometry = get_greaseweazle_geometry(device)
        ...     stats = recover_disk(device, geometry, convergence_mode=True)
        ...     if stats.converged:
        ...         print(f"Converged after {stats.passes_executed} passes")
        ...         print(f"Remaining {stats.final_bad_sectors} bad sectors are physical damage")
        ...     else:
        ...         print("Did not converge - may need more aggressive recovery")
    """
    # Record start time
    start_time = time.time()

    # Reset error tracking and wake up the drive motor
    reset_error_tracking()
    logging.debug("recover_disk: waking up device motor")
    wake_up_device(device)

    # Perform initial scan to establish baseline
    # Create a wrapper callback that reports scan progress as pass -1
    def initial_scan_callback(sector_num, total, is_good, error_type):
        # Log each sector scanned during the initial scan for debugging
        try:
            logging.debug(
                "recover_disk: initial_scan sector=%d/%d is_good=%s error=%s",
                sector_num,
                total,
                is_good,
                error_type,
            )
        except Exception:
            pass

        if progress_callback is not None:
            try:
                # Report as pass -1 to indicate initial scan
                # Extended callback: (pass_num, total_passes, current_sector, total_sectors, bad_sector_count, converged, is_good, error_type)
                try:
                    progress_callback(-1, 1, sector_num, total, 0, False, is_good, error_type)
                except TypeError:
                    # Fall back to original signature
                    progress_callback(-1, 1, sector_num, total, 0, False)
            except:
                pass

    # Flush cache before initial scan to ensure we read from physical disk
    flush_device_cache(device)

    initial_scan = scan_all_sectors(device, geometry, initial_scan_callback)
    initial_bad_count = len(initial_scan.bad_sectors)

    logging.debug("recover_disk: initial scan bad sectors=%d", initial_bad_count)

    # Notify caller of initial scan results (pass_num == -3 indicates initial scan summary)
    if progress_callback is not None:
        try:
            progress_callback(-3, 0, initial_bad_count, geometry.total_sectors, initial_bad_count, False)
        except Exception as e:
            logging.debug("recover_disk: failed to send initial scan summary: %s", e)
            pass

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

    # If there are no bad sectors found during the initial scan, nothing to do
    if initial_bad_count == 0:
        stats.final_bad_sectors = 0
        stats.sectors_recovered = 0
        stats.recovery_duration = time.time() - start_time
        return stats


    if convergence_mode:
        # =====================================================================
        # Convergence Mode: Format until bad sector count stabilizes
        # =====================================================================

        for pass_num in range(max_passes):
            logging.debug("recover_disk: starting pass %d/%d, current_bad=%d",
                         pass_num + 1, max_passes,
                         stats.bad_sector_history[-1] if stats.bad_sector_history else 0)

            # Record pattern used
            pattern = get_pattern_for_pass(pass_num)
            stats.patterns_used.append(pattern)

            # Perform format pass
            current_bad_count = stats.bad_sector_history[-1] if stats.bad_sector_history else 0
            perform_format_pass(device, geometry, pass_num, max_passes,
                              current_bad_count, stats.converged, progress_callback)
            stats.passes_executed += 1

            # CRITICAL: Flush cache before scanning
            flush_device_cache(device)

            # Scan after pass to check progress
            scan_result = scan_all_sectors(device, geometry,
                                          progress_callback=initial_scan_callback)
            bad_count = len(scan_result.bad_sectors)
            logging.debug("recover_disk: after pass %d, bad_count=%d",
                         pass_num + 1, bad_count)

            # Multi-read mode: Attempt aggressive recovery on remaining bad sectors
            if multiread_mode and bad_count > 0:
                multiread_recovered = 0
                for bad_sector in scan_result.bad_sectors:
                    # Convert LBA to CHS for multiread
                    cyl, head, sector = _lba_to_chs(bad_sector, geometry)
                    success, data, error, attempts = read_sector_multiread(
                        device, cyl, head, sector,
                        max_attempts=multiread_attempts,
                        bytes_per_sector=geometry.bytes_per_sector
                    )
                    if success and attempts > 1:
                        multiread_recovered += 1

                # Update bad count after multi-read recovery
                if multiread_recovered > 0:
                    flush_device_cache(device)
                    scan_result = scan_all_sectors(device, geometry)
                    bad_count = len(scan_result.bad_sectors)

            stats.bad_sector_history.append(bad_count)

            # Notify UI of pass completion (pass_num = -2 signals pass complete)
            if progress_callback is not None:
                try:
                    previous_count = stats.bad_sector_history[-2] if len(stats.bad_sector_history) >= 2 else None
                    progress_callback(-2, pass_num, bad_count, previous_count or 0, 0, False)
                except:
                    pass

            # Check for convergence (PRIMARY CONDITION)
            if len(stats.bad_sector_history) >= convergence_threshold + 1:
                last_n = stats.bad_sector_history[-convergence_threshold:]
                if len(set(last_n)) == 1:  # All same value
                    stats.converged = True
                    stats.convergence_pass = pass_num
                    break

            # Check for plateau (SECONDARY CONDITION)
            if len(stats.bad_sector_history) >= 6:
                last_5 = stats.bad_sector_history[-5:]
                if len(set(last_5)) == 1:
                    stats.converged = True
                    stats.convergence_pass = pass_num
                    break

        # Final scan after convergence
        flush_device_cache(device)
        final_scan = scan_all_sectors(device, geometry, progress_callback=initial_scan_callback)

    else:
        # =====================================================================
        # Fixed Pass Mode: Execute exactly N passes
        # =====================================================================

        for pass_num in range(passes):
            logging.debug("recover_disk: fixed pass %d/%d, current_bad=%d",
                         pass_num + 1, passes,
                         stats.bad_sector_history[-1] if stats.bad_sector_history else 0)

            # Record pattern used
            pattern = get_pattern_for_pass(pass_num)
            stats.patterns_used.append(pattern)

            # Perform format pass
            current_bad_count = stats.bad_sector_history[-1] if stats.bad_sector_history else 0
            perform_format_pass(device, geometry, pass_num, passes,
                              current_bad_count, False, progress_callback)
            stats.passes_executed += 1

            # CRITICAL: Flush cache before scanning
            flush_device_cache(device)

            # Scan after pass to track progress
            scan_result = scan_all_sectors(device, geometry,
                                          progress_callback=initial_scan_callback)
            bad_count = len(scan_result.bad_sectors)
            logging.debug("recover_disk: after fixed pass %d, bad_count=%d",
                         pass_num + 1, bad_count)

            # Multi-read mode: Attempt aggressive recovery on remaining bad sectors
            if multiread_mode and bad_count > 0:
                multiread_recovered = 0
                for bad_sector in scan_result.bad_sectors:
                    # Convert LBA to CHS for multiread
                    cyl, head, sector = _lba_to_chs(bad_sector, geometry)
                    success, data, error, attempts = read_sector_multiread(
                        device, cyl, head, sector,
                        max_attempts=multiread_attempts,
                        bytes_per_sector=geometry.bytes_per_sector
                    )
                    if success and attempts > 1:
                        multiread_recovered += 1

                # Update bad count after multi-read recovery
                if multiread_recovered > 0:
                    flush_device_cache(device)
                    scan_result = scan_all_sectors(device, geometry)
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
        flush_device_cache(device)
        final_scan = scan_all_sectors(device, geometry, progress_callback=initial_scan_callback)

    # Update final statistics
    stats.final_bad_sectors = len(final_scan.bad_sectors)
    stats.sectors_recovered = stats.initial_bad_sectors - stats.final_bad_sectors
    stats.recovery_duration = time.time() - start_time

    return stats


def recover_bad_sectors_only(
    device: Union[GreaseweazleDevice, Any],
    geometry: DiskGeometry,
    bad_sector_list: Optional[List[int]] = None,
    passes: int = 5,
    multiread_mode: bool = False,
    multiread_attempts: int = 100,
    progress_callback: Optional[Callable[[int, int, int, int, int, bool], None]] = None
) -> RecoveryStatistics:
    """
    Targeted recovery that focuses ONLY on bad sectors.

    Instead of reformatting the entire disk, this function:
    1. Performs an initial scan to find bad sectors (if none provided)
    2. Identifies which tracks contain bad sectors
    3. Only formats those specific tracks
    4. Optionally applies multi-read recovery to remaining bad sectors

    This is much faster than full disk recovery and preserves data on good tracks.

    Args:
        device: Connected GreaseweazleDevice instance
        geometry: Disk geometry information
        bad_sector_list: Optional list of bad sector numbers to target.
                        If None, performs initial scan to find them.
        passes: Number of recovery passes per track (default: 5)
        multiread_mode: Enable multi-read recovery (default: False)
        multiread_attempts: Flux capture count in multi-read mode (default: 100)
        progress_callback: Optional function(pass_num, total_passes, current_sector, total_sectors, bad_sector_count, converged)
                          Special pass_num values:
                          -1: Initial scan progress (sector being scanned)
                          -3: Initial scan summary (current_sector = bad count)
                          -2: Pass completion

    Returns:
        RecoveryStatistics with recovery information

    Example:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     # Targeted recovery with automatic initial scan
        ...     stats = recover_bad_sectors_only(device, geometry, passes=5)
        ...     print(f"Targeted recovery: {stats.sectors_recovered} sectors recovered")
    """
    start_time = time.time()

    # Reset error tracking and wake up the drive motor
    reset_error_tracking()
    logging.debug("recover_bad_sectors_only: waking up device motor")
    wake_up_device(device)

    # If no bad sector list provided, do an initial scan to find them
    if bad_sector_list is None:
        logging.debug("recover_bad_sectors_only: performing initial scan")

        # Create callback for per-sector updates during initial scan
        total = geometry.total_sectors

        def initial_scan_callback(sector_num: int, total_sectors: int,
                                  is_good: bool, error_type: str) -> None:
            if progress_callback is not None:
                try:
                    progress_callback(-1, 1, sector_num, total, 0, False, is_good, error_type)
                except TypeError:
                    progress_callback(-1, 1, sector_num, total, 0, False)

        # Flush cache before initial scan
        flush_device_cache(device)

        initial_scan = scan_all_sectors(device, geometry, initial_scan_callback)
        bad_sector_list = list(initial_scan.bad_sectors)

        logging.debug("recover_bad_sectors_only: initial scan found %d bad sectors",
                     len(bad_sector_list))

        # Notify caller of initial scan results
        if progress_callback is not None:
            try:
                progress_callback(-3, 0, len(bad_sector_list), 0, len(bad_sector_list), False)
            except Exception:
                pass

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
        logging.debug("recover_bad_sectors_only: no bad sectors found, nothing to recover")
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
    remaining_bad = list(bad_sector_list)

    # Perform recovery passes on affected tracks only
    for pass_num in range(passes):
        pattern = get_pattern_for_pass(pass_num)
        stats.patterns_used.append(pattern)

        track_count = 0
        for cylinder, head in sorted(bad_tracks):
            # Write pattern to track
            write_track_pattern(device, cylinder, head, pattern, geometry)

            # Format the track
            format_track(device, cylinder, head, geometry)

            track_count += 1

            # Report progress
            if progress_callback is not None:
                try:
                    current_sector = track_count * geometry.sectors_per_track
                    total_sectors = total_tracks * geometry.sectors_per_track
                    progress_callback(pass_num, passes, current_sector, total_sectors,
                                    len(bad_sector_list), False)
                except:
                    pass

        stats.passes_executed += 1

        # CRITICAL: Flush cache before scanning
        flush_device_cache(device)

        # Scan only the affected sectors to check progress
        remaining_bad = []
        for sector_num in bad_sector_list:
            cyl, head, sector = _lba_to_chs(sector_num, geometry)
            success, data, error_code = read_sector(device, cyl, head, sector,
                                                   geometry.bytes_per_sector)
            if not success:
                remaining_bad.append(sector_num)

        bad_count = len(remaining_bad)

        # Multi-read mode: Attempt aggressive recovery on remaining bad sectors
        if multiread_mode and bad_count > 0:
            multiread_recovered = 0
            for bad_sector in remaining_bad[:]:  # Copy list since we'll modify
                cyl, head, sector = _lba_to_chs(bad_sector, geometry)
                success, data, error, attempts = read_sector_multiread(
                    device, cyl, head, sector,
                    max_attempts=multiread_attempts,
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
    device: Union[GreaseweazleDevice, Any],
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
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder number (0-79)
        head: Head number (0-1)
        geometry: Disk geometry information
        passes: Number of recovery passes (default: 5)
        progress_callback: Optional function(current_pass)

    Returns:
        Tuple of (initial_bad_sectors, final_bad_sectors)

    Example:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     # Recover problematic track 15, head 0
        ...     initial, final = recover_track(device, 15, 0, geometry, passes=10)
        ...     print(f"Track recovery: {initial} bad -> {final} bad")
        ...     if final == 0:
        ...         print("Track fully recovered!")
    """
    # Scan track before recovery
    initial_track = scan_track(device, cylinder, head, geometry)
    initial_bad_count = len(initial_track.bad_sectors)

    # Perform recovery passes
    for pass_num in range(passes):
        # Select pattern for this pass
        pattern = get_pattern_for_pass(pass_num)

        # Write pattern to track
        write_track_pattern(device, cylinder, head, pattern, geometry)

        # Format the track
        format_track(device, cylinder, head, geometry)

        # Report progress if callback provided
        if progress_callback is not None:
            progress_callback(pass_num + 1)

        # Small delay between passes
        time.sleep(0.1)

    # Scan track after recovery
    final_track = scan_track(device, cylinder, head, geometry)
    final_bad_count = len(final_track.bad_sectors)

    return (initial_bad_count, final_bad_count)


def retry_bad_sectors(
    device: Union[GreaseweazleDevice, Any],
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
        device: Connected GreaseweazleDevice instance
        bad_sectors: List of bad sector numbers to retry
        geometry: Disk geometry information
        max_retries: Maximum retry attempts per sector (default: 10)
        progress_callback: Optional function(current_sector, total_sectors)

    Returns:
        Tuple of (recovered_sectors, still_bad_sectors)

    Example:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     scan = scan_all_sectors(device, geometry)
        ...     if scan.bad_sectors:
        ...         recovered, still_bad = retry_bad_sectors(
        ...             device, scan.bad_sectors, geometry
        ...         )
        ...         print(f"Retry recovered {len(recovered)} sectors")
        ...         print(f"Still bad: {len(still_bad)} sectors")
    """
    recovered_sectors = []
    still_bad_sectors = []

    for idx, sector_num in enumerate(bad_sectors):
        sector_recovered = False

        # Convert LBA to CHS
        cyl, head, sector = _lba_to_chs(sector_num, geometry)

        # Try reading with increasing delays
        for retry in range(max_retries):
            # Exponential backoff delay (0.1s, 0.2s, 0.4s, 0.8s, ...)
            if retry > 0:
                delay = 0.1 * (2 ** (retry - 1))
                time.sleep(min(delay, 2.0))  # Cap at 2 seconds

            # Invalidate cache to get fresh read
            invalidate_track_cache()

            # Attempt to read sector
            success, data, error = read_sector(
                device, cyl, head, sector, geometry.bytes_per_sector
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
# Advanced Recovery Functions (Phase 4)
# =============================================================================


def _apply_multi_capture_recovery(
    device: GreaseweazleDevice,
    cyl: int,
    head: int,
    sector: int,
    capture_count: int,
    stats: AdvancedRecoveryStats
) -> Tuple[bool, Optional[bytes]]:
    """
    Apply multi-revolution flux capture and statistical bit voting.

    Args:
        device: Connected Greaseweazle device
        cyl: Cylinder number
        head: Head number
        sector: Sector number
        capture_count: Number of flux captures to perform
        stats: Statistics to update

    Returns:
        Tuple of (success, recovered_data)
    """
    try:
        mc = _get_multi_capture()

        stats.multi_capture_attempts += 1

        # Perform multi-revolution capture
        result = mc['multi_capture_recover_sector'](
            device, cyl, head, sector, capture_count
        )

        if result.success and result.data:
            stats.multi_capture_successes += 1
            stats.recovered_by_multi_capture += 1
            logging.info(
                f"Multi-capture recovered sector {cyl}/{head}/{sector} "
                f"with confidence {result.confidence:.1f}%"
            )
            return (True, result.data)

        return (False, None)

    except Exception as e:
        logging.warning(f"Multi-capture recovery failed for {cyl}/{head}/{sector}: {e}")
        return (False, None)


def _apply_pll_tuning_recovery(
    device: GreaseweazleDevice,
    cyl: int,
    head: int,
    sector: int,
    stats: AdvancedRecoveryStats
) -> Tuple[bool, Optional[bytes]]:
    """
    Apply PLL parameter optimization to recover marginal sectors.

    Args:
        device: Connected Greaseweazle device
        cyl: Cylinder number
        head: Head number
        sector: Sector number
        stats: Statistics to update

    Returns:
        Tuple of (success, recovered_data)
    """
    try:
        pll = _get_pll_tuning()

        stats.pll_tuning_attempts += 1

        # Capture flux for PLL analysis
        flux_reader = FluxReader(device)
        device.seek(cyl, head)
        captured = flux_reader.read_track(cyl, head, revolutions=3)

        # Find optimal PLL parameters for this sector
        result = pll['optimize_for_sector'](
            captured.flux_data,
            sector
        )

        if result.success and result.best_data:
            stats.pll_tuning_successes += 1
            stats.recovered_by_pll_tuning += 1
            logging.info(
                f"PLL tuning recovered sector {cyl}/{head}/{sector} "
                f"with params: freq={result.best_params.frequency:.0f}, "
                f"bw={result.best_params.bandwidth:.3f}"
            )
            return (True, result.best_data)

        return (False, None)

    except Exception as e:
        logging.warning(f"PLL tuning recovery failed for {cyl}/{head}/{sector}: {e}")
        return (False, None)


def _apply_bit_slip_recovery(
    device: GreaseweazleDevice,
    cyl: int,
    head: int,
    sector: int,
    stats: AdvancedRecoveryStats
) -> Tuple[bool, Optional[bytes]]:
    """
    Apply bit-slip detection and correction to recover sectors.

    Args:
        device: Connected Greaseweazle device
        cyl: Cylinder number
        head: Head number
        sector: Sector number
        stats: Statistics to update

    Returns:
        Tuple of (success, recovered_data)
    """
    try:
        bsr = _get_bit_slip_recovery()

        # Capture flux
        flux_reader = FluxReader(device)
        device.seek(cyl, head)
        captured = flux_reader.read_track(cyl, head, revolutions=2)

        # Detect bit slips
        slips = bsr['detect_bit_slips'](captured.flux_data)

        if slips:
            stats.bit_slips_detected += len(slips)

            # Attempt to reconstruct the slipped sector
            result = bsr['reconstruct_slipped_sector'](
                captured.flux_data,
                sector
            )

            if result.success and result.data:
                stats.bit_slips_corrected += 1
                stats.recovered_by_bit_slip += 1
                logging.info(
                    f"Bit-slip recovery recovered sector {cyl}/{head}/{sector} "
                    f"({len(slips)} slips corrected)"
                )
                return (True, result.data)

        return (False, None)

    except Exception as e:
        logging.warning(f"Bit-slip recovery failed for {cyl}/{head}/{sector}: {e}")
        return (False, None)


def _apply_surface_treatment(
    device: GreaseweazleDevice,
    cyl: int,
    head: int,
    sector: int,
    geometry: DiskGeometry,
    stats: AdvancedRecoveryStats
) -> bool:
    """
    Apply surface treatment (degauss + pattern refresh) to a weak sector.

    Args:
        device: Connected Greaseweazle device
        cyl: Cylinder number
        head: Head number
        sector: Sector number
        geometry: Disk geometry
        stats: Statistics to update

    Returns:
        True if treatment was applied successfully
    """
    try:
        st = _get_surface_treatment()

        # Apply targeted treatment to the weak sector
        result = st['treat_weak_sector'](device, cyl, head, sector)

        stats.sectors_refreshed += 1

        if result.success and result.final_crc_valid:
            stats.recovered_by_surface_treatment += 1
            logging.info(
                f"Surface treatment recovered sector {cyl}/{head}/{sector}"
            )
            return True

        return False

    except Exception as e:
        logging.warning(f"Surface treatment failed for {cyl}/{head}/{sector}: {e}")
        return False


def _apply_advanced_recovery_to_sector(
    device: GreaseweazleDevice,
    cyl: int,
    head: int,
    sector: int,
    geometry: DiskGeometry,
    config: RestoreConfig,
    stats: AdvancedRecoveryStats
) -> Tuple[bool, Optional[bytes]]:
    """
    Apply advanced recovery techniques to a single bad sector.

    Techniques are applied in order of increasing aggressiveness:
    1. Multi-capture (if multiread_mode or AGGRESSIVE/FORENSIC)
    2. PLL tuning (if pll_tuning or AGGRESSIVE/FORENSIC)
    3. Bit-slip recovery (if bit_slip_recovery or FORENSIC)
    4. Surface treatment (if surface_treatment or FORENSIC)

    Args:
        device: Connected Greaseweazle device
        cyl: Cylinder number
        head: Head number
        sector: Sector number
        geometry: Disk geometry
        config: Recovery configuration
        stats: Statistics to update

    Returns:
        Tuple of (success, recovered_data)
    """
    # Try multi-capture first (fastest advanced technique)
    if config.multiread_mode:
        success, data = _apply_multi_capture_recovery(
            device, cyl, head, sector,
            config.multiread_attempts,
            stats
        )
        if success:
            return (True, data)

    # Try PLL tuning (more computationally intensive)
    if config.pll_tuning:
        success, data = _apply_pll_tuning_recovery(
            device, cyl, head, sector, stats
        )
        if success:
            return (True, data)

    # Try bit-slip recovery (FORENSIC level)
    if config.bit_slip_recovery:
        success, data = _apply_bit_slip_recovery(
            device, cyl, head, sector, stats
        )
        if success:
            return (True, data)

    # Try surface treatment as last resort (physically refreshes media)
    if config.surface_treatment:
        success = _apply_surface_treatment(
            device, cyl, head, sector, geometry, stats
        )
        if success:
            # Re-read the sector after treatment
            success, data, error = read_sector(
                device, cyl, head, sector, geometry.bytes_per_sector
            )
            if success:
                return (True, data)

    return (False, None)


def recover_disk_with_config(
    device: Union[GreaseweazleDevice, Any],
    geometry: DiskGeometry,
    config: RestoreConfig,
    progress_callback: Optional[Callable[[int, int, int, int, int, bool], None]] = None
) -> Tuple[RecoveryStatistics, AdvancedRecoveryStats]:
    """
    Recover a disk using the specified configuration.

    This function provides a unified interface for all recovery modes,
    including the new Phase 4 advanced recovery techniques.

    Args:
        device: Connected Greaseweazle device
        geometry: Disk geometry information
        config: RestoreConfig with recovery options
        progress_callback: Optional progress callback

    Returns:
        Tuple of (RecoveryStatistics, AdvancedRecoveryStats)

    Example - Standard Recovery:
        >>> config = RestoreConfig(passes=5)
        >>> stats, advanced = recover_disk_with_config(device, geometry, config)

    Example - Aggressive Recovery:
        >>> config = RestoreConfig(
        ...     convergence_mode=True,
        ...     recovery_level=RecoveryLevel.AGGRESSIVE
        ... )
        >>> stats, advanced = recover_disk_with_config(device, geometry, config)

    Example - Forensic Recovery:
        >>> config = RestoreConfig(
        ...     convergence_mode=True,
        ...     recovery_level=RecoveryLevel.FORENSIC
        ... )
        >>> stats, advanced = recover_disk_with_config(device, geometry, config)
    """
    advanced_stats = AdvancedRecoveryStats()

    # Enable detailed logging if requested
    if config.detailed_logging:
        logging.getLogger('floppy_formatter').setLevel(logging.DEBUG)

    # Use targeted or full disk recovery based on config
    if config.targeted_mode:
        basic_stats = recover_bad_sectors_only(
            device=device,
            geometry=geometry,
            bad_sector_list=config.bad_sector_list,
            passes=config.passes,
            multiread_mode=False,  # We'll handle advanced recovery separately
            multiread_attempts=config.multiread_attempts,
            progress_callback=progress_callback
        )
    else:
        basic_stats = recover_disk(
            device=device,
            geometry=geometry,
            passes=config.passes,
            convergence_mode=config.convergence_mode,
            max_passes=config.max_passes,
            convergence_threshold=config.convergence_threshold,
            multiread_mode=False,  # We'll handle advanced recovery separately
            multiread_attempts=config.multiread_attempts,
            progress_callback=progress_callback
        )

    # Record sectors recovered by standard methods
    advanced_stats.recovered_by_standard = basic_stats.sectors_recovered

    # If we still have bad sectors and advanced recovery is enabled, try advanced techniques
    if basic_stats.final_bad_sectors > 0 and config.recovery_level != RecoveryLevel.STANDARD:
        logging.info(
            f"Starting advanced recovery for {basic_stats.final_bad_sectors} "
            f"remaining bad sectors (level: {config.recovery_level.name})"
        )

        # Perform a final scan to get current bad sectors
        flush_device_cache(device)
        final_scan = scan_all_sectors(device, geometry)
        remaining_bad = list(final_scan.bad_sectors)

        # Apply advanced recovery to each remaining bad sector
        still_bad = []
        for sector_num in remaining_bad:
            cyl, head, sector = _lba_to_chs(sector_num, geometry)

            success, data = _apply_advanced_recovery_to_sector(
                device, cyl, head, sector, geometry, config, advanced_stats
            )

            if not success:
                still_bad.append(sector_num)

        # Update final statistics
        advanced_recovered = len(remaining_bad) - len(still_bad)
        basic_stats.final_bad_sectors = len(still_bad)
        basic_stats.sectors_recovered += advanced_recovered

        logging.info(
            f"Advanced recovery complete: {advanced_recovered} additional sectors recovered"
        )

    return (basic_stats, advanced_stats)


def aggressive_sector_recovery(
    device: GreaseweazleDevice,
    cyl: int,
    head: int,
    sector: int,
    geometry: DiskGeometry,
    capture_count: int = 50
) -> Tuple[bool, Optional[bytes], str]:
    """
    Apply all available techniques to recover a single sector.

    This function applies techniques in order of complexity:
    1. Multi-capture with statistical bit voting
    2. PLL parameter optimization
    3. Bit-slip detection and correction
    4. Surface treatment (degauss + refresh)

    Args:
        device: Connected Greaseweazle device
        cyl: Cylinder number
        head: Head number
        sector: Sector number
        geometry: Disk geometry
        capture_count: Number of flux captures for multi-capture

    Returns:
        Tuple of (success, data, technique_used)

    Example:
        >>> success, data, technique = aggressive_sector_recovery(
        ...     device, 15, 0, 7, geometry
        ... )
        >>> if success:
        ...     print(f"Recovered using {technique}")
    """
    stats = AdvancedRecoveryStats()

    config = RestoreConfig(
        multiread_mode=True,
        multiread_attempts=capture_count,
        pll_tuning=True,
        bit_slip_recovery=True,
        surface_treatment=True,
        recovery_level=RecoveryLevel.FORENSIC
    )

    success, data = _apply_advanced_recovery_to_sector(
        device, cyl, head, sector, geometry, config, stats
    )

    # Determine which technique succeeded
    technique = "none"
    if stats.recovered_by_multi_capture > 0:
        technique = "multi_capture"
    elif stats.recovered_by_pll_tuning > 0:
        technique = "pll_tuning"
    elif stats.recovered_by_bit_slip > 0:
        technique = "bit_slip"
    elif stats.recovered_by_surface_treatment > 0:
        technique = "surface_treatment"

    return (success, data, technique)


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
