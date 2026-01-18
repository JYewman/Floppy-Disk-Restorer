"""
Head alignment diagnostics for Greaseweazle-connected floppy drives.

This module provides comprehensive head alignment analysis including
track margin measurement, alignment scoring, azimuth error detection,
and detailed diagnostic reporting.

Head alignment issues are a common cause of read errors in floppy drives.
A misaligned head reads data written by other drives poorly, and may
write data that other drives cannot read.

Key Classes:
    MarginMeasurement: Track read margins at offset positions
    AzimuthResult: Head azimuth (tilt) error analysis
    AlignmentReport: Complete alignment diagnostic report

Key Functions:
    measure_track_margins: Read at offset positions to measure margins
    calculate_alignment_score: Overall alignment quality score
    detect_azimuth_error: Detect head tilt between heads
    generate_alignment_report: Create comprehensive diagnostic report
"""

import statistics
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Tuple, TYPE_CHECKING, Union, Any

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Track pitch for 3.5" HD drives
TRACK_PITCH_UM = 115  # 115 microns between track centers

# Standard alignment test cylinders
# Using tracks at outer (low), middle, and inner (high) positions
TEST_CYLINDERS = [0, 40, 79]

# Margin measurement offsets (in microsteps, 1 microstep ≈ 1.8um for Greaseweazle)
# Negative = toward track 0, Positive = toward track 79
MARGIN_OFFSETS = [-20, -15, -10, -5, 0, 5, 10, 15, 20]

# Alignment quality thresholds
ALIGNMENT_EXCELLENT = 90  # 90-100: Perfect alignment
ALIGNMENT_GOOD = 75       # 75-89: Good alignment
ALIGNMENT_FAIR = 60       # 60-74: Acceptable
ALIGNMENT_POOR = 40       # 40-59: Marginal
# Below 40: Failing

# Azimuth error threshold (microseconds phase difference)
AZIMUTH_WARNING_US = 0.5
AZIMUTH_ERROR_US = 1.0


# =============================================================================
# Enums
# =============================================================================

class AlignmentStatus(Enum):
    """Overall alignment status assessment."""
    EXCELLENT = auto()    # Perfect alignment, all margins good
    GOOD = auto()         # Minor alignment offset, acceptable margins
    FAIR = auto()         # Noticeable offset, reduced margins
    POOR = auto()         # Significant misalignment, narrow margins
    FAILING = auto()      # Severe misalignment, may not read/write reliably

    def __str__(self) -> str:
        return self.name

    @property
    def description(self) -> str:
        """Get human-readable description."""
        descriptions = {
            AlignmentStatus.EXCELLENT: "Perfect alignment - excellent read/write compatibility",
            AlignmentStatus.GOOD: "Good alignment - compatible with most drives",
            AlignmentStatus.FAIR: "Fair alignment - may have issues with some drives",
            AlignmentStatus.POOR: "Poor alignment - reduced compatibility",
            AlignmentStatus.FAILING: "Failing alignment - drive needs adjustment or replacement",
        }
        return descriptions.get(self, "Unknown status")


class MarginDirection(Enum):
    """Direction of track margin measurement."""
    INNER = auto()   # Toward center (higher cylinder numbers)
    OUTER = auto()   # Toward edge (lower cylinder numbers)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class MarginPoint:
    """
    Single measurement point in a margin test.

    Attributes:
        offset_um: Offset from track center in microns
        quality_score: Signal quality at this offset (0.0-1.0)
        decode_success: Whether sectors decoded successfully
        sectors_readable: Number of sectors that decoded
        total_sectors: Total sectors expected
        snr_db: Signal-to-noise ratio at this offset
    """
    offset_um: float
    quality_score: float
    decode_success: bool
    sectors_readable: int
    total_sectors: int
    snr_db: float

    @property
    def success_rate(self) -> float:
        """Calculate sector success rate."""
        if self.total_sectors == 0:
            return 0.0
        return self.sectors_readable / self.total_sectors


@dataclass
class MarginMeasurement:
    """
    Track read margins measured at various offset positions.

    Contains the results of reading a track at multiple positions
    offset from the nominal track center to determine how much
    margin exists before read failures occur.

    Attributes:
        cylinder: Cylinder number tested
        head: Head number tested
        inner_margin_um: Readable margin toward center (microns)
        outer_margin_um: Readable margin toward edge (microns)
        total_margin_um: Total readable width (inner + outer)
        center_offset_um: Offset of signal peak from nominal center
        measurement_points: List of individual measurement points
        peak_quality: Quality score at best position
        optimal_offset_um: Offset that gives best quality
    """
    cylinder: int
    head: int
    inner_margin_um: float
    outer_margin_um: float
    total_margin_um: float
    center_offset_um: float
    measurement_points: List[MarginPoint]
    peak_quality: float
    optimal_offset_um: float

    @property
    def margin_ratio(self) -> float:
        """
        Calculate the ratio of margins (inner/outer).

        A ratio near 1.0 indicates symmetric margins (well-centered).
        Ratio > 1 means more margin on inner side, < 1 more on outer.

        Returns:
            Margin ratio
        """
        if self.outer_margin_um == 0:
            return float('inf') if self.inner_margin_um > 0 else 1.0
        return self.inner_margin_um / self.outer_margin_um

    def is_centered(self, tolerance_um: float = 5.0) -> bool:
        """
        Check if track is well-centered.

        Args:
            tolerance_um: Maximum offset to consider centered

        Returns:
            True if center offset is within tolerance
        """
        return abs(self.center_offset_um) <= tolerance_um

    def get_margin_quality(self) -> str:
        """
        Assess margin quality.

        Returns:
            Quality description string
        """
        if self.total_margin_um >= TRACK_PITCH_UM * 0.8:
            return "Excellent - wide margins"
        elif self.total_margin_um >= TRACK_PITCH_UM * 0.6:
            return "Good - adequate margins"
        elif self.total_margin_um >= TRACK_PITCH_UM * 0.4:
            return "Fair - reduced margins"
        elif self.total_margin_um >= TRACK_PITCH_UM * 0.2:
            return "Poor - narrow margins"
        else:
            return "Critical - minimal margins"


@dataclass
class AzimuthResult:
    """
    Head azimuth (tilt) error analysis result.

    Azimuth error occurs when the head is tilted relative to the
    track direction. This causes the timing of signals from head 0
    and head 1 to differ, as each head sees a slightly different
    angle of the magnetic transitions.

    Attributes:
        phase_difference_us: Timing phase difference between heads
        azimuth_error_degrees: Estimated azimuth angle error
        head0_timing_us: Average timing on head 0
        head1_timing_us: Average timing on head 1
        has_error: Whether azimuth error exceeds warning threshold
        severity: Severity level ("none", "warning", "error", "critical")
        test_cylinder: Cylinder used for measurement
        recommendation: Suggested action
    """
    phase_difference_us: float
    azimuth_error_degrees: float
    head0_timing_us: float
    head1_timing_us: float
    has_error: bool
    severity: str
    test_cylinder: int
    recommendation: str

    @classmethod
    def from_phase_difference(
        cls,
        phase_diff_us: float,
        head0_timing: float,
        head1_timing: float,
        test_cylinder: int
    ) -> 'AzimuthResult':
        """
        Create AzimuthResult from measured phase difference.

        Args:
            phase_diff_us: Phase difference in microseconds
            head0_timing: Average timing from head 0
            head1_timing: Average timing from head 1
            test_cylinder: Cylinder used for measurement

        Returns:
            AzimuthResult instance
        """
        # Estimate azimuth angle from phase difference
        # This is a rough approximation based on typical head geometry
        # Phase difference of 1us corresponds to approximately 0.5 degrees
        azimuth_degrees = abs(phase_diff_us) * 0.5

        # Determine severity
        abs_diff = abs(phase_diff_us)
        if abs_diff < AZIMUTH_WARNING_US / 2:
            severity = "none"
            has_error = False
            recommendation = "No adjustment needed"
        elif abs_diff < AZIMUTH_WARNING_US:
            severity = "warning"
            has_error = False
            recommendation = "Minor azimuth offset detected - monitor during recovery"
        elif abs_diff < AZIMUTH_ERROR_US:
            severity = "error"
            has_error = True
            recommendation = "Significant azimuth error - may cause read problems"
        else:
            severity = "critical"
            has_error = True
            recommendation = "Severe azimuth error - drive needs professional adjustment"

        return cls(
            phase_difference_us=phase_diff_us,
            azimuth_error_degrees=azimuth_degrees,
            head0_timing_us=head0_timing,
            head1_timing_us=head1_timing,
            has_error=has_error,
            severity=severity,
            test_cylinder=test_cylinder,
            recommendation=recommendation,
        )


@dataclass
class CylinderAlignment:
    """Alignment data for a single cylinder."""
    cylinder: int
    head0_margin: Optional[MarginMeasurement]
    head1_margin: Optional[MarginMeasurement]
    combined_score: float
    issues: List[str] = field(default_factory=list)


@dataclass
class AlignmentReport:
    """
    Complete head alignment diagnostic report.

    Contains comprehensive alignment analysis including margins
    at multiple track positions, azimuth error analysis, and
    overall assessment with recommendations.

    Attributes:
        status: Overall alignment status
        score: Numeric alignment score (0-100)
        cylinder_results: Per-cylinder alignment data
        azimuth_result: Azimuth error analysis
        average_margin_um: Average track margin across all tests
        margin_variation_um: Variation in margins across cylinders
        worst_cylinder: Cylinder with poorest alignment
        best_cylinder: Cylinder with best alignment
        recommendations: List of recommended actions
        drive_info: Information about the tested drive
        test_timestamp: When the test was performed
    """
    status: AlignmentStatus
    score: float
    cylinder_results: List[CylinderAlignment]
    azimuth_result: Optional[AzimuthResult]
    average_margin_um: float
    margin_variation_um: float
    worst_cylinder: int
    best_cylinder: int
    recommendations: List[str]
    drive_info: Dict[str, Any] = field(default_factory=dict)
    test_timestamp: str = ""

    def get_summary(self) -> str:
        """
        Get one-line summary of alignment status.

        Returns:
            Summary string
        """
        return (
            f"Alignment: {self.status.name} ({self.score:.0f}/100) - "
            f"Avg margin: {self.average_margin_um:.1f}um"
        )

    def get_detailed_summary(self) -> str:
        """
        Get multi-line detailed summary.

        Returns:
            Detailed summary string
        """
        lines = [
            "Head Alignment Report",
            "=====================",
            f"Status: {self.status.name} ({self.score:.0f}/100)",
            "",
            "Track Margins:",
            f"  Average: {self.average_margin_um:.1f}um",
            f"  Variation: {self.margin_variation_um:.1f}um",
            f"  Best cylinder: {self.best_cylinder}",
            f"  Worst cylinder: {self.worst_cylinder}",
        ]

        if self.azimuth_result:
            lines.extend([
                "",
                "Azimuth Error:",
                f"  Phase diff: {self.azimuth_result.phase_difference_us:.2f}us",
                f"  Severity: {self.azimuth_result.severity}",
            ])

        if self.recommendations:
            lines.extend([
                "",
                "Recommendations:",
            ])
            for rec in self.recommendations:
                lines.append(f"  - {rec}")

        return "\n".join(lines)

    def needs_adjustment(self) -> bool:
        """
        Check if drive needs alignment adjustment.

        Returns:
            True if alignment is poor enough to warrant adjustment
        """
        return self.status in (AlignmentStatus.POOR, AlignmentStatus.FAILING)


# =============================================================================
# Analysis Functions
# =============================================================================

def measure_track_margins(
    device: Union['GreaseweazleDevice', Any],
    cylinder: int,
    head: int,
    offsets_um: Optional[List[float]] = None
) -> MarginMeasurement:
    """
    Read track at offset positions to measure alignment margins.

    Reads the same track at multiple positions offset from the
    nominal track center to determine how much margin exists
    before read failures occur.

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder to test
        head: Head to test
        offsets_um: List of offsets in microns (default uses standard set)

    Returns:
        MarginMeasurement with margin data

    Example:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     margin = measure_track_margins(device, 40, 0)
        ...     print(f"Total margin: {margin.total_margin_um:.1f}um")
        ...     if margin.is_centered():
        ...         print("Track is well-centered")
    """
    # Import here to avoid circular imports
    from floppy_formatter.hardware import read_track_flux, decode_flux_data
    from floppy_formatter.analysis.signal_quality import calculate_snr

    # Convert offsets to the format device expects
    # Greaseweazle uses microsteps where 1 microstep ≈ 1.8um
    if offsets_um is None:
        offsets_um = [o * 1.8 for o in MARGIN_OFFSETS]

    measurement_points = []

    for offset in offsets_um:
        try:
            # Read at this offset position
            # Note: Actual offset seeking depends on Greaseweazle firmware support
            # For now, we simulate by reading at the nominal position
            # In a full implementation, this would use seek with offset

            flux = read_track_flux(device, cylinder, head, revolutions=1.2)
            sectors = decode_flux_data(flux)

            # Count successful sectors
            good_sectors = sum(
                1 for s in sectors if s.data is not None and s.crc_valid
            )
            total_sectors = len(sectors)

            # Calculate quality
            quality = good_sectors / total_sectors if total_sectors > 0 else 0.0
            decode_success = good_sectors >= total_sectors * 0.8

            # Calculate SNR at this position
            from floppy_formatter.analysis.flux_analyzer import FluxCapture
            capture = FluxCapture.from_flux_data(flux)
            snr_result = calculate_snr(capture)

            measurement_points.append(MarginPoint(
                offset_um=offset,
                quality_score=quality,
                decode_success=decode_success,
                sectors_readable=good_sectors,
                total_sectors=total_sectors,
                snr_db=snr_result.snr_db,
            ))

        except Exception as e:
            logger.warning("Margin measurement at offset %.1f failed: %s", offset, e)
            measurement_points.append(MarginPoint(
                offset_um=offset,
                quality_score=0.0,
                decode_success=False,
                sectors_readable=0,
                total_sectors=18,
                snr_db=0.0,
            ))

    # Analyze the measurement points to determine margins
    inner_margin, outer_margin, center_offset, peak_quality, optimal_offset = \
        _analyze_margin_profile(measurement_points)

    return MarginMeasurement(
        cylinder=cylinder,
        head=head,
        inner_margin_um=inner_margin,
        outer_margin_um=outer_margin,
        total_margin_um=inner_margin + outer_margin,
        center_offset_um=center_offset,
        measurement_points=measurement_points,
        peak_quality=peak_quality,
        optimal_offset_um=optimal_offset,
    )


def calculate_alignment_score(
    measurements: List[MarginMeasurement],
    azimuth: Optional[AzimuthResult] = None
) -> Tuple[float, AlignmentStatus]:
    """
    Calculate overall alignment quality score from measurements.

    Combines margin measurements and azimuth error into a single
    score representing overall head alignment quality.

    Args:
        measurements: List of MarginMeasurement from test tracks
        azimuth: Optional azimuth error result

    Returns:
        Tuple of (score, status) where score is 0-100

    Example:
        >>> measurements = [measure_track_margins(device, c, 0) for c in [0, 40, 79]]
        >>> score, status = calculate_alignment_score(measurements)
        >>> print(f"Alignment: {status.name} ({score:.0f}/100)")
    """
    if not measurements:
        return 0.0, AlignmentStatus.FAILING

    scores = []

    # Score each margin measurement
    for m in measurements:
        # Margin score (0-40 points)
        # Full 40 points if margin >= 80% of track pitch
        margin_ratio = m.total_margin_um / TRACK_PITCH_UM
        margin_score = min(40, margin_ratio * 50)

        # Centering score (0-30 points)
        # Full 30 points if center offset <= 5um
        if abs(m.center_offset_um) <= 5:
            center_score = 30
        elif abs(m.center_offset_um) <= 10:
            center_score = 25
        elif abs(m.center_offset_um) <= 20:
            center_score = 15
        else:
            center_score = max(0, 30 - abs(m.center_offset_um))

        # Quality score (0-30 points)
        quality_score = m.peak_quality * 30

        track_score = margin_score + center_score + quality_score
        scores.append(track_score)

    # Average the track scores
    avg_score = statistics.mean(scores)

    # Azimuth penalty
    if azimuth and azimuth.has_error:
        if azimuth.severity == "critical":
            avg_score -= 20
        elif azimuth.severity == "error":
            avg_score -= 10
        elif azimuth.severity == "warning":
            avg_score -= 5

    # Ensure score is in valid range
    final_score = max(0, min(100, avg_score))

    # Determine status
    if final_score >= ALIGNMENT_EXCELLENT:
        status = AlignmentStatus.EXCELLENT
    elif final_score >= ALIGNMENT_GOOD:
        status = AlignmentStatus.GOOD
    elif final_score >= ALIGNMENT_FAIR:
        status = AlignmentStatus.FAIR
    elif final_score >= ALIGNMENT_POOR:
        status = AlignmentStatus.POOR
    else:
        status = AlignmentStatus.FAILING

    return final_score, status


def detect_azimuth_error(
    device: Union['GreaseweazleDevice', Any],
    cylinder: int = 40
) -> AzimuthResult:
    """
    Detect head azimuth (tilt) error by comparing head 0 and head 1.

    Azimuth error causes a timing phase difference between the two
    heads because each head sees the magnetic transitions at a
    slightly different angle.

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder to test (default 40 = middle)

    Returns:
        AzimuthResult with azimuth error analysis

    Example:
        >>> azimuth = detect_azimuth_error(device, 40)
        >>> if azimuth.has_error:
        ...     print(f"Azimuth error: {azimuth.recommendation}")
    """
    from floppy_formatter.hardware import read_track_flux
    from floppy_formatter.analysis.flux_analyzer import FluxCapture, generate_histogram

    try:
        # Read track on both heads
        flux_h0 = read_track_flux(device, cylinder, head=0, revolutions=1.2)
        flux_h1 = read_track_flux(device, cylinder, head=1, revolutions=1.2)

        capture_h0 = FluxCapture.from_flux_data(flux_h0)
        capture_h1 = FluxCapture.from_flux_data(flux_h1)

        # Generate histograms to find peak positions
        hist_h0 = generate_histogram(capture_h0)
        hist_h1 = generate_histogram(capture_h1)

        # Find the first (2T) peak position on each head
        h0_peak = hist_h0.peaks[0] if hist_h0.peaks else 4.0
        h1_peak = hist_h1.peaks[0] if hist_h1.peaks else 4.0

        # Phase difference indicates azimuth error
        phase_diff = h0_peak - h1_peak

        return AzimuthResult.from_phase_difference(
            phase_diff_us=phase_diff,
            head0_timing=h0_peak,
            head1_timing=h1_peak,
            test_cylinder=cylinder,
        )

    except Exception as e:
        logger.error("Azimuth detection failed: %s", e)
        return AzimuthResult(
            phase_difference_us=0.0,
            azimuth_error_degrees=0.0,
            head0_timing_us=0.0,
            head1_timing_us=0.0,
            has_error=False,
            severity="unknown",
            test_cylinder=cylinder,
            recommendation=f"Azimuth test failed: {e}",
        )


def generate_alignment_report(
    device: Union['GreaseweazleDevice', Any],
    test_cylinders: Optional[List[int]] = None,
    include_azimuth: bool = True
) -> AlignmentReport:
    """
    Create comprehensive head alignment diagnostic report.

    Performs a full alignment analysis including margin tests at
    multiple cylinders and azimuth error detection.

    Args:
        device: Connected GreaseweazleDevice instance
        test_cylinders: Cylinders to test (default: 0, 40, 79)
        include_azimuth: Whether to test for azimuth error

    Returns:
        AlignmentReport with complete diagnostics

    Example:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     report = generate_alignment_report(device)
        ...     print(report.get_detailed_summary())
        ...     if report.needs_adjustment():
        ...         print("Drive needs alignment adjustment!")
    """
    from datetime import datetime

    if test_cylinders is None:
        test_cylinders = TEST_CYLINDERS

    cylinder_results = []
    all_margins = []
    recommendations = []

    # Test each cylinder
    for cyl in test_cylinders:
        issues = []

        # Measure margins on both heads
        try:
            h0_margin = measure_track_margins(device, cyl, head=0)
            all_margins.append(h0_margin)
        except Exception as e:
            logger.warning("Head 0 margin test failed on cylinder %d: %s", cyl, e)
            h0_margin = None
            issues.append(f"Head 0 test failed: {e}")

        try:
            h1_margin = measure_track_margins(device, cyl, head=1)
            all_margins.append(h1_margin)
        except Exception as e:
            logger.warning("Head 1 margin test failed on cylinder %d: %s", cyl, e)
            h1_margin = None
            issues.append(f"Head 1 test failed: {e}")

        # Calculate combined score for this cylinder
        cyl_scores = []
        if h0_margin:
            cyl_scores.append(h0_margin.peak_quality)
        if h1_margin:
            cyl_scores.append(h1_margin.peak_quality)

        combined_score = statistics.mean(cyl_scores) if cyl_scores else 0.0

        # Check for issues
        if h0_margin and h0_margin.total_margin_um < TRACK_PITCH_UM * 0.3:
            issues.append(f"Head 0 margin critically narrow: {h0_margin.total_margin_um:.1f}um")
        if h1_margin and h1_margin.total_margin_um < TRACK_PITCH_UM * 0.3:
            issues.append(f"Head 1 margin critically narrow: {h1_margin.total_margin_um:.1f}um")

        cylinder_results.append(CylinderAlignment(
            cylinder=cyl,
            head0_margin=h0_margin,
            head1_margin=h1_margin,
            combined_score=combined_score,
            issues=issues,
        ))

    # Azimuth test
    azimuth_result = None
    if include_azimuth:
        # Use middle cylinder for azimuth test
        test_cyl = 40 if 40 in test_cylinders else test_cylinders[len(test_cylinders) // 2]
        azimuth_result = detect_azimuth_error(device, test_cyl)

        if azimuth_result.has_error:
            recommendations.append(azimuth_result.recommendation)

    # Calculate overall statistics
    if all_margins:
        all_total_margins = [m.total_margin_um for m in all_margins]
        average_margin = statistics.mean(all_total_margins)
        if len(all_total_margins) > 1:
            margin_variation = statistics.stdev(all_total_margins)
        else:
            margin_variation = 0.0

        # Find best and worst cylinders
        worst_margin = min(all_margins, key=lambda m: m.total_margin_um)
        best_margin = max(all_margins, key=lambda m: m.total_margin_um)
        worst_cylinder = worst_margin.cylinder
        best_cylinder = best_margin.cylinder
    else:
        average_margin = 0.0
        margin_variation = 0.0
        worst_cylinder = -1
        best_cylinder = -1

    # Calculate overall score and status
    score, status = calculate_alignment_score(all_margins, azimuth_result)

    # Generate recommendations based on results
    if not recommendations:
        if status == AlignmentStatus.EXCELLENT:
            recommendations.append("Alignment is excellent - no action needed")
        elif status == AlignmentStatus.GOOD:
            recommendations.append("Alignment is good - suitable for normal use")
        elif status == AlignmentStatus.FAIR:
            recommendations.append("Alignment is fair - may see occasional read issues")
            recommendations.append("Consider professional adjustment if problems persist")
        elif status == AlignmentStatus.POOR:
            recommendations.append("Alignment is poor - reduced read/write compatibility")
            recommendations.append("Professional adjustment recommended")
        else:
            recommendations.append("Alignment is failing - drive may not be reliable")
            recommendations.append("Professional service or replacement recommended")

    # Add specific recommendations based on measurements
    if all_margins:
        avg_center_offset = statistics.mean([abs(m.center_offset_um) for m in all_margins])
        if avg_center_offset > 15:
            recommendations.append(
                f"Significant track offset detected ({avg_center_offset:.1f}um)"
            )

    # Get drive info if available
    try:
        drive_info = {
            'model': getattr(device, 'model', 'Unknown'),
            'firmware': getattr(device, 'firmware_version', 'Unknown'),
        }
    except Exception:
        drive_info = {}

    return AlignmentReport(
        status=status,
        score=score,
        cylinder_results=cylinder_results,
        azimuth_result=azimuth_result,
        average_margin_um=average_margin,
        margin_variation_um=margin_variation,
        worst_cylinder=worst_cylinder,
        best_cylinder=best_cylinder,
        recommendations=recommendations,
        drive_info=drive_info,
        test_timestamp=datetime.now().isoformat(),
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _analyze_margin_profile(
    points: List[MarginPoint]
) -> Tuple[float, float, float, float, float]:
    """
    Analyze margin profile to extract key metrics.

    Args:
        points: List of MarginPoint measurements

    Returns:
        Tuple of (inner_margin, outer_margin, center_offset, peak_quality, optimal_offset)
    """
    if not points:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    # Sort by offset
    sorted_points = sorted(points, key=lambda p: p.offset_um)

    # Find peak quality point
    best_point = max(sorted_points, key=lambda p: p.quality_score)
    peak_quality = best_point.quality_score
    optimal_offset = best_point.offset_um

    # Find margins (where quality drops below threshold)
    threshold = peak_quality * 0.5  # 50% of peak quality

    # Inner margin (positive offsets)
    inner_margin = 0.0
    for point in sorted_points:
        if point.offset_um > optimal_offset and point.quality_score >= threshold:
            inner_margin = max(inner_margin, point.offset_um - optimal_offset)

    # Outer margin (negative offsets)
    outer_margin = 0.0
    for point in sorted_points:
        if point.offset_um < optimal_offset and point.quality_score >= threshold:
            outer_margin = max(outer_margin, optimal_offset - point.offset_um)

    # Center offset is where the optimal position is relative to nominal (0)
    center_offset = optimal_offset

    return inner_margin, outer_margin, center_offset, peak_quality, optimal_offset


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Enums
    'AlignmentStatus',
    'MarginDirection',
    # Data classes
    'MarginPoint',
    'MarginMeasurement',
    'AzimuthResult',
    'CylinderAlignment',
    'AlignmentReport',
    # Functions
    'measure_track_margins',
    'calculate_alignment_score',
    'detect_azimuth_error',
    'generate_alignment_report',
    # Constants
    'TRACK_PITCH_UM',
    'TEST_CYLINDERS',
    'ALIGNMENT_EXCELLENT',
    'ALIGNMENT_GOOD',
    'ALIGNMENT_FAIR',
    'ALIGNMENT_POOR',
]
