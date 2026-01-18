"""
Alignment worker for Greaseweazle head alignment measurement.

Provides comprehensive head alignment diagnostics including track margin
measurement, azimuth error detection, and overall alignment grading.

Part of Phase 9: Workers & Background Processing
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal

from floppy_formatter.gui.workers.base_worker import GreaseweazleWorker

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice
    from floppy_formatter.core.geometry import DiskGeometry
    from floppy_formatter.analysis.head_alignment import (
        MarginMeasurement, AzimuthResult, AlignmentStatus
    )
    # AlignmentReport imported at runtime in run() method

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default test cylinders (outer, middle, inner)
DEFAULT_TEST_CYLINDERS = [0, 40, 79]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AlignmentConfig:
    """
    Configuration for an alignment test operation.

    Attributes:
        test_cylinders: List of cylinders to test (default: 0, 40, 79)
        include_azimuth: Whether to test for azimuth error
        include_both_heads: Whether to test both heads
        extended_margins: Use extended margin offsets for detailed analysis
    """
    test_cylinders: List[int] = field(default_factory=lambda: DEFAULT_TEST_CYLINDERS.copy())
    include_azimuth: bool = True
    include_both_heads: bool = True
    extended_margins: bool = False


@dataclass
class CylinderTestResult:
    """
    Result of alignment test for a single cylinder.

    Attributes:
        cylinder: Cylinder number tested
        head0_margin_um: Head 0 total margin in microns
        head1_margin_um: Head 1 total margin in microns (None if not tested)
        head0_centered: Whether head 0 is well-centered
        head1_centered: Whether head 1 is well-centered (None if not tested)
        head0_quality: Signal quality on head 0 (0.0-1.0)
        head1_quality: Signal quality on head 1 (None if not tested)
        issues: List of issues detected at this cylinder
        test_duration_ms: Time taken to test in milliseconds
    """
    cylinder: int
    head0_margin_um: float
    head1_margin_um: Optional[float] = None
    head0_centered: bool = True
    head1_centered: Optional[bool] = None
    head0_quality: float = 1.0
    head1_quality: Optional[float] = None
    issues: List[str] = field(default_factory=list)
    test_duration_ms: float = 0.0

    @property
    def has_issues(self) -> bool:
        """Check if any issues were detected."""
        return len(self.issues) > 0


# =============================================================================
# Alignment Worker
# =============================================================================

class AlignmentWorker(GreaseweazleWorker):
    """
    Worker for head alignment measurement.

    Performs comprehensive head alignment diagnostics by measuring
    track margins at multiple cylinder positions and optionally
    detecting azimuth error between heads.

    Features:
    - Track margin measurement at configurable positions
    - Azimuth error detection between heads
    - Quality grading with recommendations
    - Real-time progress reporting

    Signals:
        cylinder_tested(int, object): Per cylinder (cyl, CylinderTestResult)
        margin_measured(int, int, float): Margin result (cyl, head, margin_um)
        azimuth_result(object): Azimuth measurement result
        alignment_complete(object): Final AlignmentReport

    Example:
        config = AlignmentConfig(
            test_cylinders=[0, 20, 40, 60, 79],
            include_azimuth=True
        )
        worker = AlignmentWorker(device, geometry, config)
        worker.cylinder_tested.connect(on_cylinder_tested)
        worker.alignment_complete.connect(on_alignment_complete)
    """

    # Signals specific to alignment
    cylinder_tested = pyqtSignal(int, object)    # cylinder, CylinderTestResult
    margin_measured = pyqtSignal(int, int, float)  # cylinder, head, margin_um
    azimuth_result = pyqtSignal(object)          # AzimuthResult
    alignment_complete = pyqtSignal(object)       # AlignmentReport

    def __init__(
        self,
        device: 'GreaseweazleDevice',
        geometry: 'DiskGeometry',
        config: Optional[AlignmentConfig] = None,
    ):
        """
        Initialize alignment worker.

        Args:
            device: Connected GreaseweazleDevice instance
            geometry: Disk geometry information
            config: AlignmentConfig with test settings (uses defaults if None)
        """
        super().__init__(device)
        self._geometry = geometry
        self._config = config or AlignmentConfig()

        logger.info(
            "AlignmentWorker initialized: cylinders=%s, azimuth=%s, both_heads=%s",
            self._config.test_cylinders,
            self._config.include_azimuth,
            self._config.include_both_heads
        )

    def run(self) -> None:
        """
        Execute the alignment measurement operation.

        Tests alignment at configured cylinders and generates
        a comprehensive alignment report.
        """
        from floppy_formatter.analysis.head_alignment import (
            measure_track_margins,
            detect_azimuth_error,
            calculate_alignment_score,
            AlignmentReport,
            CylinderAlignment,
            TRACK_PITCH_UM,
        )

        start_time = time.time()

        # Ensure motor is on
        if not self._device.is_motor_on():
            self._device.motor_on()

        cylinder_results = []
        all_margins = []
        total_steps = len(self._config.test_cylinders)
        if self._config.include_azimuth:
            total_steps += 1

        step_count = 0

        logger.info("Starting alignment test on %d cylinders",
                    len(self._config.test_cylinders))

        # Test each cylinder
        for cylinder in self._config.test_cylinders:
            if self._cancelled:
                logger.info("Alignment test cancelled at cylinder %d", cylinder)
                break

            cyl_start = time.time()

            test_result = CylinderTestResult(cylinder=cylinder)
            issues = []

            # Test head 0
            try:
                h0_margin = measure_track_margins(self._device, cylinder, head=0)
                test_result.head0_margin_um = h0_margin.total_margin_um
                test_result.head0_centered = h0_margin.is_centered()
                test_result.head0_quality = h0_margin.peak_quality
                all_margins.append(h0_margin)

                self.margin_measured.emit(cylinder, 0, h0_margin.total_margin_um)

                # Check for issues
                margin_um = h0_margin.total_margin_um
                if margin_um < TRACK_PITCH_UM * 0.3:
                    issues.append(
                        f"Head 0 margin critically narrow: {margin_um:.1f}um"
                    )
                elif margin_um < TRACK_PITCH_UM * 0.5:
                    issues.append(f"Head 0 margin below optimal: {margin_um:.1f}um")

                if not h0_margin.is_centered():
                    offset = h0_margin.center_offset_um
                    issues.append(f"Head 0 off-center: {offset:.1f}um offset")

            except Exception as e:
                logger.warning("Head 0 margin test failed on cylinder %d: %s", cylinder, e)
                test_result.head0_margin_um = 0.0
                test_result.head0_quality = 0.0
                issues.append(f"Head 0 test failed: {e}")

            # Test head 1 if configured
            if self._config.include_both_heads:
                try:
                    h1_margin = measure_track_margins(self._device, cylinder, head=1)
                    test_result.head1_margin_um = h1_margin.total_margin_um
                    test_result.head1_centered = h1_margin.is_centered()
                    test_result.head1_quality = h1_margin.peak_quality
                    all_margins.append(h1_margin)

                    self.margin_measured.emit(cylinder, 1, h1_margin.total_margin_um)

                    # Check for issues
                    h1_margin_um = h1_margin.total_margin_um
                    if h1_margin_um < TRACK_PITCH_UM * 0.3:
                        issues.append(
                            f"Head 1 margin critically narrow: {h1_margin_um:.1f}um"
                        )
                    elif h1_margin_um < TRACK_PITCH_UM * 0.5:
                        issues.append(
                            f"Head 1 margin below optimal: {h1_margin_um:.1f}um"
                        )

                    if not h1_margin.is_centered():
                        h1_offset = h1_margin.center_offset_um
                        issues.append(f"Head 1 off-center: {h1_offset:.1f}um offset")

                except Exception as e:
                    logger.warning("Head 1 margin test failed on cylinder %d: %s", cylinder, e)
                    test_result.head1_margin_um = 0.0
                    test_result.head1_quality = 0.0
                    issues.append(f"Head 1 test failed: {e}")

            test_result.issues = issues
            test_result.test_duration_ms = (time.time() - cyl_start) * 1000

            # Store result for report generation
            h0_margin_obj = None
            h1_margin_obj = None
            if all_margins:
                # Find the margins we just measured
                for m in all_margins[-2:]:  # Last 1 or 2 margins
                    if m.cylinder == cylinder:
                        if m.head == 0:
                            h0_margin_obj = m
                        else:
                            h1_margin_obj = m

            cylinder_results.append(CylinderAlignment(
                cylinder=cylinder,
                head0_margin=h0_margin_obj,
                head1_margin=h1_margin_obj,
                combined_score=(
                    (test_result.head0_quality + (test_result.head1_quality or 0)) /
                    (2 if self._config.include_both_heads else 1)
                ),
                issues=issues,
            ))

            # Emit cylinder result
            self.cylinder_tested.emit(cylinder, test_result)

            # Update progress
            step_count += 1
            progress = int((step_count / total_steps) * 100)
            self.progress.emit(progress)

            logger.debug(
                "Cylinder %d tested: H0 margin=%.1fum, H1 margin=%s, %.1f ms",
                cylinder,
                test_result.head0_margin_um,
                f"{test_result.head1_margin_um:.1f}um" if test_result.head1_margin_um else "N/A",
                test_result.test_duration_ms
            )

        # Azimuth test if configured
        azimuth = None
        if self._config.include_azimuth and not self._cancelled:
            try:
                # Use middle cylinder for azimuth test
                middle_cyl = self._config.test_cylinders[len(self._config.test_cylinders) // 2]
                azimuth = detect_azimuth_error(self._device, middle_cyl)
                self.azimuth_result.emit(azimuth)

                step_count += 1
                progress = int((step_count / total_steps) * 100)
                self.progress.emit(progress)

                logger.debug(
                    "Azimuth test complete: phase_diff=%.2fus, severity=%s",
                    azimuth.phase_difference_us, azimuth.severity
                )

            except Exception as e:
                logger.warning("Azimuth test failed: %s", e)

        # Calculate overall statistics and generate report
        if all_margins:
            import statistics

            all_total_margins = [m.total_margin_um for m in all_margins]
            average_margin = statistics.mean(all_total_margins)
            if len(all_total_margins) > 1:
                margin_variation = statistics.stdev(all_total_margins)
            else:
                margin_variation = 0.0

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
        score, status = calculate_alignment_score(all_margins, azimuth)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            status, average_margin, margin_variation, azimuth, all_margins
        )

        # Create final report
        report = AlignmentReport(
            status=status,
            score=score,
            cylinder_results=cylinder_results,
            azimuth_result=azimuth,
            average_margin_um=average_margin,
            margin_variation_um=margin_variation,
            worst_cylinder=worst_cylinder,
            best_cylinder=best_cylinder,
            recommendations=recommendations,
            test_timestamp=datetime.now().isoformat(),
        )

        duration = time.time() - start_time

        logger.info(
            "Alignment test complete: status=%s, score=%.1f, avg_margin=%.1fum, %.1fs",
            status.name, score, average_margin, duration
        )

        self.alignment_complete.emit(report)
        self.finished.emit()

    def _generate_recommendations(
        self,
        status: 'AlignmentStatus',
        avg_margin: float,
        margin_var: float,
        azimuth: Optional['AzimuthResult'],
        margins: List['MarginMeasurement']
    ) -> List[str]:
        """Generate recommendations based on alignment results."""
        from floppy_formatter.analysis.head_alignment import (
            AlignmentStatus, TRACK_PITCH_UM
        )

        recommendations = []

        # Status-based recommendations
        if status == AlignmentStatus.EXCELLENT:
            recommendations.append("Alignment is excellent - no action needed")
        elif status == AlignmentStatus.GOOD:
            recommendations.append("Alignment is good - suitable for normal use")
        elif status == AlignmentStatus.FAIR:
            recommendations.append(
                "Alignment is fair - may see occasional read issues with disks "
                "from other drives"
            )
            recommendations.append("Consider professional adjustment if problems persist")
        elif status == AlignmentStatus.POOR:
            recommendations.append(
                "Alignment is poor - reduced read/write compatibility with other drives"
            )
            recommendations.append("Professional adjustment recommended")
        else:  # FAILING
            recommendations.append("Alignment is failing - drive may not be reliable")
            recommendations.append("Professional service or replacement recommended")

        # Azimuth recommendations
        if azimuth and azimuth.has_error:
            recommendations.append(azimuth.recommendation)

        # Margin-specific recommendations
        if avg_margin < TRACK_PITCH_UM * 0.4:
            recommendations.append(
                f"Track margins are narrow ({avg_margin:.1f}um) - "
                "drive may struggle with worn media"
            )

        if margin_var > 10:
            recommendations.append(
                f"Significant margin variation ({margin_var:.1f}um) between cylinders - "
                "stepper motor may need attention"
            )

        # Check for consistent centering issues
        if margins:
            offsets = [abs(m.center_offset_um) for m in margins]
            avg_offset = sum(offsets) / len(offsets)
            if avg_offset > 15:
                recommendations.append(
                    f"Head is consistently off-center ({avg_offset:.1f}um) - "
                    "adjustment recommended"
                )

        return recommendations

    def get_geometry(self) -> 'DiskGeometry':
        """Get the disk geometry being used."""
        return self._geometry

    def get_config(self) -> AlignmentConfig:
        """Get the alignment configuration."""
        return self._config


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'AlignmentWorker',
    'AlignmentConfig',
    'CylinderTestResult',
    'DEFAULT_TEST_CYLINDERS',
]
