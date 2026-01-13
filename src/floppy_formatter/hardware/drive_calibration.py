"""
Drive calibration and diagnostics for Greaseweazle.

This module provides functions for measuring and calibrating floppy drive
parameters including RPM, bit timing, head alignment, and signal quality.
These diagnostics help ensure accurate read/write operations and can
identify drive problems.

Key Functions:
    calibrate_drive: Full drive calibration sequence
    measure_rpm: Measure drive rotation speed
    measure_bit_timing: Measure actual bit cell width
    check_head_alignment: Assess head positioning accuracy
    get_drive_health: Overall drive health assessment

Key Classes:
    DriveCalibration: Results from calibration procedure
    AlignmentResult: Head alignment measurement results
    DriveHealth: Overall drive health assessment
"""

import logging
import statistics
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Tuple, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .greaseweazle_device import GreaseweazleDevice

from . import (
    GreaseweazleError,
    SeekError,
    DriveType,
    DriveInfo,
    SectorStatus,
)
from .flux_io import FluxData, analyze_flux_quality
from .mfm_codec import decode_flux_to_sectors, BIT_CELL_US

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Expected values for 3.5" HD drive
NOMINAL_RPM = 300.0
RPM_TOLERANCE = 3.0  # Acceptable deviation from 300 RPM

NOMINAL_BIT_CELL_US = 2.0
BIT_CELL_TOLERANCE = 0.1  # +/- 0.1µs

# Calibration test tracks
CAL_TRACK_OUTER = 2      # Track near outer edge
CAL_TRACK_MIDDLE = 40    # Track in middle
CAL_TRACK_INNER = 78     # Track near inner edge

# Health score thresholds
HEALTH_EXCELLENT = 0.9
HEALTH_GOOD = 0.7
HEALTH_FAIR = 0.5
HEALTH_POOR = 0.3


class HealthGrade(IntEnum):
    """Drive health grade enumeration."""
    EXCELLENT = 4    # Grade A - All parameters within spec
    GOOD = 3         # Grade B - Minor deviations
    FAIR = 2         # Grade C - Noticeable issues but usable
    POOR = 1         # Grade D - Significant problems
    FAILING = 0      # Grade F - Drive needs service/replacement


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class RPMMeasurement:
    """Result of RPM measurement."""
    rpm: float
    min_rpm: float
    max_rpm: float
    std_dev: float
    samples: int
    within_spec: bool

    @property
    def deviation(self) -> float:
        """Deviation from nominal RPM."""
        return abs(self.rpm - NOMINAL_RPM)

    @property
    def stability(self) -> float:
        """RPM stability score (0-1, higher is better)."""
        if self.std_dev > 5.0:
            return 0.0
        return max(0, 1 - (self.std_dev / 5.0))


@dataclass
class BitTimingMeasurement:
    """Result of bit timing measurement."""
    bit_cell_us: float
    std_dev_us: float
    short_peak_us: float
    medium_peak_us: float
    long_peak_us: float
    within_spec: bool

    @property
    def timing_accuracy(self) -> float:
        """Timing accuracy score (0-1)."""
        deviation = abs(self.bit_cell_us - NOMINAL_BIT_CELL_US)
        if deviation > 0.5:
            return 0.0
        return max(0, 1 - (deviation / 0.5))


@dataclass
class AlignmentResult:
    """Result of head alignment check."""
    cylinder: int
    signal_strength: float  # 0-1
    error_rate: float       # 0-1 (0 is best)
    sectors_found: int
    sectors_expected: int
    sectors_good: int

    @property
    def alignment_score(self) -> float:
        """Overall alignment score for this track (0-1)."""
        sector_score = self.sectors_good / max(1, self.sectors_expected)
        signal_score = self.signal_strength
        error_score = 1.0 - self.error_rate
        return (sector_score * 0.5 + signal_score * 0.3 + error_score * 0.2)


@dataclass
class DriveHealth:
    """Overall drive health assessment."""
    grade: HealthGrade
    score: float  # 0-1
    rpm_ok: bool
    timing_ok: bool
    alignment_ok: bool
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @property
    def grade_letter(self) -> str:
        """Get letter grade (A-F)."""
        grades = {
            HealthGrade.EXCELLENT: 'A',
            HealthGrade.GOOD: 'B',
            HealthGrade.FAIR: 'C',
            HealthGrade.POOR: 'D',
            HealthGrade.FAILING: 'F',
        }
        return grades.get(self.grade, '?')

    def __str__(self) -> str:
        return f"Drive Health: {self.grade_letter} ({self.score:.0%})"


@dataclass
class DriveCalibration:
    """Complete drive calibration results."""
    timestamp: float
    drive_type: DriveType
    rpm: RPMMeasurement
    bit_timing: BitTimingMeasurement
    alignment: Dict[int, AlignmentResult]  # Track -> result
    health: DriveHealth
    calibration_successful: bool

    @property
    def optimal_bit_cell_us(self) -> float:
        """Get optimal bit cell timing for this drive."""
        return self.bit_timing.bit_cell_us

    @property
    def rpm_correction_factor(self) -> float:
        """Get RPM correction factor for timing calculations."""
        return NOMINAL_RPM / self.rpm.rpm if self.rpm.rpm > 0 else 1.0


# =============================================================================
# Measurement Functions
# =============================================================================

def measure_rpm(device: 'GreaseweazleDevice',
                samples: int = 5) -> RPMMeasurement:
    """
    Measure drive rotation speed.

    Takes multiple samples and calculates statistics for accuracy.
    The motor must be running and a disk must be present.

    Args:
        device: Connected GreaseweazleDevice with motor running
        samples: Number of measurement samples to take

    Returns:
        RPMMeasurement with detailed RPM statistics

    Raises:
        GreaseweazleError: If measurement fails
    """
    logger.info("Measuring drive RPM (%d samples)", samples)

    rpm_values = []

    for i in range(samples):
        try:
            rpm = device.get_rpm()
            rpm_values.append(rpm)
            logger.debug("RPM sample %d: %.1f", i + 1, rpm)
        except GreaseweazleError as e:
            logger.warning("RPM measurement %d failed: %s", i + 1, e)

    if not rpm_values:
        raise GreaseweazleError("Failed to measure RPM - no valid samples")

    avg_rpm = statistics.mean(rpm_values)
    min_rpm = min(rpm_values)
    max_rpm = max(rpm_values)
    std_dev = statistics.stdev(rpm_values) if len(rpm_values) > 1 else 0.0

    within_spec = abs(avg_rpm - NOMINAL_RPM) <= RPM_TOLERANCE

    result = RPMMeasurement(
        rpm=avg_rpm,
        min_rpm=min_rpm,
        max_rpm=max_rpm,
        std_dev=std_dev,
        samples=len(rpm_values),
        within_spec=within_spec
    )

    logger.info("RPM: %.1f (range: %.1f-%.1f, stddev: %.2f) - %s",
                avg_rpm, min_rpm, max_rpm, std_dev,
                "OK" if within_spec else "OUT OF SPEC")

    return result


def measure_bit_timing(device: 'GreaseweazleDevice',
                        track: int = 40) -> BitTimingMeasurement:
    """
    Measure actual bit cell timing from disk.

    Reads a track and analyzes the flux timing to determine the
    actual bit cell width used on the disk.

    Args:
        device: Connected GreaseweazleDevice with motor running
        track: Track to read for measurement (default 40)

    Returns:
        BitTimingMeasurement with timing statistics

    Raises:
        GreaseweazleError: If measurement fails
    """
    logger.info("Measuring bit timing on track %d", track)

    # Read the track
    flux = device.read_track(track, 0, revolutions=2.0)

    # Analyze timing
    analysis = analyze_flux_quality(flux)

    # Get peak positions
    peaks = analysis.get('peak_positions', {})
    short = peaks.get('short', 4.0)
    medium = peaks.get('medium', 6.0)
    long = peaks.get('long', 8.0)

    # Calculate bit cell from peaks
    bit_cell_estimates = []
    if short:
        bit_cell_estimates.append(short / 2.0)  # Short = 2 bit cells
    if medium:
        bit_cell_estimates.append(medium / 3.0)  # Medium = 3 bit cells
    if long:
        bit_cell_estimates.append(long / 4.0)  # Long = 4 bit cells

    if bit_cell_estimates:
        bit_cell = statistics.mean(bit_cell_estimates)
        std_dev = statistics.stdev(bit_cell_estimates) if len(bit_cell_estimates) > 1 else 0.0
    else:
        bit_cell = NOMINAL_BIT_CELL_US
        std_dev = 0.0

    within_spec = abs(bit_cell - NOMINAL_BIT_CELL_US) <= BIT_CELL_TOLERANCE

    result = BitTimingMeasurement(
        bit_cell_us=bit_cell,
        std_dev_us=std_dev,
        short_peak_us=short or 0.0,
        medium_peak_us=medium or 0.0,
        long_peak_us=long or 0.0,
        within_spec=within_spec
    )

    logger.info("Bit cell: %.3fµs (peaks: %.2f/%.2f/%.2fµs) - %s",
                bit_cell, short or 0, medium or 0, long or 0,
                "OK" if within_spec else "OUT OF SPEC")

    return result


def check_track_alignment(device: 'GreaseweazleDevice',
                           cylinder: int,
                           expected_sectors: int = 18) -> AlignmentResult:
    """
    Check head alignment on a specific track.

    Reads the track and counts how many sectors can be successfully
    decoded to assess head positioning accuracy.

    Args:
        device: Connected GreaseweazleDevice with motor running
        cylinder: Cylinder to check
        expected_sectors: Number of sectors expected (default 18)

    Returns:
        AlignmentResult with alignment assessment
    """
    logger.debug("Checking alignment on cylinder %d", cylinder)

    # Read track on head 0
    flux = device.read_track(cylinder, 0, revolutions=2.0)

    # Decode sectors
    sectors = decode_flux_to_sectors(flux)

    # Calculate metrics
    sectors_found = len(sectors)
    sectors_good = sum(1 for s in sectors if s.status == SectorStatus.GOOD)
    error_rate = 1.0 - (sectors_good / expected_sectors) if expected_sectors > 0 else 1.0

    # Signal strength from flux quality
    analysis = analyze_flux_quality(flux)
    signal_strength = analysis.get('quality_score', 0.5)

    result = AlignmentResult(
        cylinder=cylinder,
        signal_strength=signal_strength,
        error_rate=error_rate,
        sectors_found=sectors_found,
        sectors_expected=expected_sectors,
        sectors_good=sectors_good
    )

    logger.debug("Track %d: %d/%d sectors good (signal: %.2f)",
                 cylinder, sectors_good, expected_sectors, signal_strength)

    return result


def check_head_alignment(device: 'GreaseweazleDevice',
                          tracks: Optional[List[int]] = None) -> Dict[int, AlignmentResult]:
    """
    Check head alignment across multiple tracks.

    Tests alignment at outer, middle, and inner tracks to detect
    alignment issues that may vary across the disk.

    Args:
        device: Connected GreaseweazleDevice with motor running
        tracks: List of tracks to test (default: outer, middle, inner)

    Returns:
        Dictionary mapping track number to AlignmentResult
    """
    if tracks is None:
        tracks = [CAL_TRACK_OUTER, CAL_TRACK_MIDDLE, CAL_TRACK_INNER]

    logger.info("Checking head alignment on tracks: %s", tracks)

    results = {}
    for track in tracks:
        try:
            results[track] = check_track_alignment(device, track)
        except (GreaseweazleError, SeekError) as e:
            logger.warning("Failed to check track %d: %s", track, e)
            # Record a failed result
            results[track] = AlignmentResult(
                cylinder=track,
                signal_strength=0.0,
                error_rate=1.0,
                sectors_found=0,
                sectors_expected=18,
                sectors_good=0
            )

    return results


def assess_drive_health(rpm: RPMMeasurement,
                         timing: BitTimingMeasurement,
                         alignment: Dict[int, AlignmentResult]) -> DriveHealth:
    """
    Assess overall drive health from calibration measurements.

    Combines all measurements into an overall health score and grade.

    Args:
        rpm: RPM measurement results
        timing: Bit timing measurement results
        alignment: Head alignment results by track

    Returns:
        DriveHealth with overall assessment
    """
    issues = []
    recommendations = []

    # Check RPM
    rpm_ok = rpm.within_spec
    if not rpm_ok:
        if rpm.rpm < NOMINAL_RPM - RPM_TOLERANCE:
            issues.append(f"RPM too low ({rpm.rpm:.1f} vs {NOMINAL_RPM})")
            recommendations.append("Check motor or belt tension")
        else:
            issues.append(f"RPM too high ({rpm.rpm:.1f} vs {NOMINAL_RPM})")
            recommendations.append("Check motor regulation")

    if rpm.std_dev > 2.0:
        issues.append(f"Unstable RPM (±{rpm.std_dev:.1f})")
        recommendations.append("Check motor bearings and spindle")

    # Check timing
    timing_ok = timing.within_spec
    if not timing_ok:
        issues.append(f"Bit timing off ({timing.bit_cell_us:.3f}µs vs {NOMINAL_BIT_CELL_US}µs)")
        recommendations.append("May need to adjust read timing compensation")

    # Check alignment
    alignment_scores = [r.alignment_score for r in alignment.values()]
    avg_alignment = statistics.mean(alignment_scores) if alignment_scores else 0.0
    alignment_ok = avg_alignment >= HEALTH_GOOD

    if not alignment_ok:
        # Check for specific patterns
        outer = alignment.get(CAL_TRACK_OUTER)
        inner = alignment.get(CAL_TRACK_INNER)

        if outer and inner:
            if outer.alignment_score > inner.alignment_score + 0.2:
                issues.append("Inner track alignment worse than outer")
                recommendations.append("Head may need radial adjustment")
            elif inner.alignment_score > outer.alignment_score + 0.2:
                issues.append("Outer track alignment worse than inner")
                recommendations.append("Head may need radial adjustment")

        # Check for uniform degradation
        all_low = all(r.sectors_good < r.sectors_expected * 0.8 for r in alignment.values())
        if all_low:
            issues.append("Poor read quality across all tracks")
            recommendations.append("Clean heads and check disk media")

    # Calculate overall score
    rpm_score = rpm.stability * (1.0 if rpm_ok else 0.7)
    timing_score = timing.timing_accuracy
    alignment_score = avg_alignment

    # Weighted average (alignment most important for actual use)
    overall_score = (rpm_score * 0.2 + timing_score * 0.2 + alignment_score * 0.6)

    # Determine grade
    if overall_score >= HEALTH_EXCELLENT:
        grade = HealthGrade.EXCELLENT
    elif overall_score >= HEALTH_GOOD:
        grade = HealthGrade.GOOD
    elif overall_score >= HEALTH_FAIR:
        grade = HealthGrade.FAIR
    elif overall_score >= HEALTH_POOR:
        grade = HealthGrade.POOR
    else:
        grade = HealthGrade.FAILING

    if not recommendations and grade == HealthGrade.EXCELLENT:
        recommendations.append("Drive is operating within specifications")

    return DriveHealth(
        grade=grade,
        score=overall_score,
        rpm_ok=rpm_ok,
        timing_ok=timing_ok,
        alignment_ok=alignment_ok,
        issues=issues,
        recommendations=recommendations
    )


# =============================================================================
# Main Calibration Function
# =============================================================================

def calibrate_drive(device: 'GreaseweazleDevice',
                     drive_unit: int = 0,
                     full_calibration: bool = True) -> DriveCalibration:
    """
    Perform full drive calibration sequence.

    Runs all calibration tests and returns comprehensive results
    including health assessment and recommendations.

    Args:
        device: Connected GreaseweazleDevice (will select drive and start motor)
        drive_unit: Drive unit to calibrate (0 or 1)
        full_calibration: If True, run all tests; if False, quick calibration

    Returns:
        DriveCalibration with all results

    Raises:
        GreaseweazleError: If calibration fails

    Example:
        with GreaseweazleDevice() as device:
            cal = calibrate_drive(device, 0)
            print(f"Drive health: {cal.health.grade_letter}")
            print(f"Optimal bit cell: {cal.optimal_bit_cell_us}µs")
    """
    logger.info("Starting drive calibration (unit=%d, full=%s)",
                drive_unit, full_calibration)

    start_time = time.time()

    # Ensure drive is selected and motor running
    if device.selected_drive != drive_unit:
        device.select_drive(drive_unit)
    if not device.is_motor_on():
        device.motor_on()

    # Check for disk presence
    if not device.is_disk_present():
        raise GreaseweazleError(
            "No disk in drive - insert a disk for calibration"
        )

    # Seek to track 0 for reference
    device.seek_track0()

    # Measure RPM
    rpm = measure_rpm(device, samples=5)

    # Measure bit timing
    timing = measure_bit_timing(device, track=CAL_TRACK_MIDDLE)

    # Check head alignment
    if full_calibration:
        alignment_tracks = [CAL_TRACK_OUTER, CAL_TRACK_MIDDLE, CAL_TRACK_INNER]
    else:
        alignment_tracks = [CAL_TRACK_MIDDLE]

    alignment = check_head_alignment(device, alignment_tracks)

    # Assess overall health
    health = assess_drive_health(rpm, timing, alignment)

    # Return to track 0
    device.seek_track0()

    elapsed = time.time() - start_time
    logger.info("Calibration complete in %.1fs - Grade: %s (%.0f%%)",
                elapsed, health.grade_letter, health.score * 100)

    return DriveCalibration(
        timestamp=start_time,
        drive_type=DriveType.HD_35,
        rpm=rpm,
        bit_timing=timing,
        alignment=alignment,
        health=health,
        calibration_successful=True
    )


def quick_calibration(device: 'GreaseweazleDevice',
                       drive_unit: int = 0) -> DriveCalibration:
    """
    Perform quick drive calibration (RPM and middle track only).

    Faster alternative to full calibration for routine checks.

    Args:
        device: Connected GreaseweazleDevice
        drive_unit: Drive unit to calibrate

    Returns:
        DriveCalibration with limited results
    """
    return calibrate_drive(device, drive_unit, full_calibration=False)


# =============================================================================
# Utility Functions
# =============================================================================

def format_calibration_report(cal: DriveCalibration) -> str:
    """
    Format calibration results as a human-readable report.

    Args:
        cal: DriveCalibration results

    Returns:
        Formatted string report
    """
    lines = [
        "=" * 60,
        "DRIVE CALIBRATION REPORT",
        "=" * 60,
        "",
        f"Drive Type: {cal.drive_type.name}",
        f"Health Grade: {cal.health.grade_letter} ({cal.health.score:.0%})",
        "",
        "--- RPM Measurement ---",
        f"  Average RPM: {cal.rpm.rpm:.1f}",
        f"  Range: {cal.rpm.min_rpm:.1f} - {cal.rpm.max_rpm:.1f}",
        f"  Stability: {cal.rpm.stability:.0%}",
        f"  Status: {'OK' if cal.rpm.within_spec else 'OUT OF SPEC'}",
        "",
        "--- Bit Timing ---",
        f"  Bit Cell: {cal.bit_timing.bit_cell_us:.3f}µs",
        f"  Peaks: {cal.bit_timing.short_peak_us:.2f} / {cal.bit_timing.medium_peak_us:.2f} / {cal.bit_timing.long_peak_us:.2f}µs",
        f"  Status: {'OK' if cal.bit_timing.within_spec else 'OUT OF SPEC'}",
        "",
        "--- Head Alignment ---",
    ]

    for track, result in sorted(cal.alignment.items()):
        lines.append(
            f"  Track {track:2d}: {result.sectors_good}/{result.sectors_expected} sectors "
            f"(signal: {result.signal_strength:.0%})"
        )

    lines.extend([
        "",
        "--- Issues ---",
    ])

    if cal.health.issues:
        for issue in cal.health.issues:
            lines.append(f"  - {issue}")
    else:
        lines.append("  None detected")

    lines.extend([
        "",
        "--- Recommendations ---",
    ])

    for rec in cal.health.recommendations:
        lines.append(f"  - {rec}")

    lines.extend([
        "",
        "=" * 60,
    ])

    return "\n".join(lines)
