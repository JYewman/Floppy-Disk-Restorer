"""
Batch verification worker for verifying multiple floppy disks.

Provides per-disk verification by wrapping the analysis functionality,
returning results in a batch-compatible format.

Part of Phase 11: Batch Operations
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal

from floppy_formatter.gui.workers.base_worker import GreaseweazleWorker
from floppy_formatter.gui.dialogs.batch_verify_config_dialog import (
    FloppyDiskInfo, BatchVerifyConfig
)

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice
    from floppy_formatter.core.geometry import DiskGeometry

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class DiskGrade(Enum):
    """Overall disk grade based on verification results."""
    EXCELLENT = "A"
    GOOD = "B"
    FAIR = "C"
    POOR = "D"
    FAILED = "F"
    SKIPPED = "S"

    @classmethod
    def from_score(cls, score: float) -> 'DiskGrade':
        """
        Get grade from numeric score.

        Args:
            score: Quality score (0-100)

        Returns:
            DiskGrade corresponding to score
        """
        if score >= 90:
            return cls.EXCELLENT
        elif score >= 80:
            return cls.GOOD
        elif score >= 70:
            return cls.FAIR
        elif score >= 60:
            return cls.POOR
        else:
            return cls.FAILED


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SingleDiskResult:
    """
    Verification result for a single disk.

    Attributes:
        disk_info: Information about the disk
        grade: Overall disk grade
        overall_score: Quality score (0-100)
        good_sectors: Number of readable sectors
        bad_sectors: Number of unreadable sectors
        weak_sectors: Number of weak sectors
        total_sectors: Total sectors on disk
        analysis_duration_ms: Time taken in milliseconds
        timestamp: When verification was performed
        encoding_type: Detected encoding (MFM, FM, etc.)
        disk_type: Disk type (HD, DD)
        average_snr_db: Average signal-to-noise ratio
        average_jitter_ns: Average timing jitter
        recommendations: List of recommendations
        skipped: Whether the disk was skipped
        error_message: Error message if verification failed
        full_result: Full analysis result for detailed reporting
    """
    disk_info: FloppyDiskInfo
    grade: DiskGrade = DiskGrade.FAILED
    overall_score: float = 0.0
    good_sectors: int = 0
    bad_sectors: int = 0
    weak_sectors: int = 0
    total_sectors: int = 2880
    analysis_duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    encoding_type: str = "UNKNOWN"
    disk_type: str = "HD"
    average_snr_db: float = 0.0
    average_jitter_ns: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    skipped: bool = False
    error_message: Optional[str] = None
    full_result: Optional[Any] = None

    @property
    def is_passing(self) -> bool:
        """Check if disk passes verification (grade C or better)."""
        return self.grade in (DiskGrade.EXCELLENT, DiskGrade.GOOD, DiskGrade.FAIR)

    @property
    def display_grade(self) -> str:
        """Get display string for grade."""
        if self.skipped:
            return "S"
        return self.grade.value


@dataclass
class BatchVerificationResult:
    """
    Complete batch verification results.

    Attributes:
        config: Batch configuration used
        disk_results: List of individual disk results
        start_time: When batch started
        end_time: When batch completed
        total_duration_ms: Total time in milliseconds
        disks_verified: Number of disks successfully verified
        disks_skipped: Number of disks skipped
        disks_failed: Number of disks that failed verification
        average_score: Average quality score across verified disks
        pass_rate: Percentage of disks with grade C or better
        grade_distribution: Count of each grade
    """
    config: BatchVerifyConfig
    disk_results: List[SingleDiskResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_duration_ms: int = 0
    disks_verified: int = 0
    disks_skipped: int = 0
    disks_failed: int = 0
    average_score: float = 0.0
    pass_rate: float = 0.0
    grade_distribution: Dict[str, int] = field(default_factory=lambda: {
        'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0, 'S': 0
    })

    def finalize(self) -> None:
        """Calculate summary statistics after all disks verified."""
        self.end_time = datetime.now()

        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.total_duration_ms = int(delta.total_seconds() * 1000)

        # Reset counters
        self.disks_verified = 0
        self.disks_skipped = 0
        self.disks_failed = 0
        self.grade_distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0, 'S': 0}

        scores = []
        passing = 0

        for result in self.disk_results:
            grade_key = result.display_grade
            if grade_key in self.grade_distribution:
                self.grade_distribution[grade_key] += 1

            if result.skipped:
                self.disks_skipped += 1
            elif result.error_message:
                self.disks_failed += 1
            else:
                self.disks_verified += 1
                scores.append(result.overall_score)
                if result.is_passing:
                    passing += 1

        if scores:
            self.average_score = sum(scores) / len(scores)

        total_verified = self.disks_verified
        if total_verified > 0:
            self.pass_rate = (passing / total_verified) * 100

    def get_summary(self) -> str:
        """Get a text summary of the batch results."""
        return (
            f"Batch Complete: {self.disks_verified} verified, "
            f"{self.disks_skipped} skipped, {self.disks_failed} failed. "
            f"Pass rate: {self.pass_rate:.1f}%"
        )


# =============================================================================
# Batch Verify Worker
# =============================================================================

class BatchVerifyWorker(GreaseweazleWorker):
    """
    Worker for verifying a single disk in a batch.

    This worker wraps the analysis functionality to verify a single disk,
    returning results in a batch-compatible format. It's instantiated
    once per disk and run sequentially.

    Signals:
        disk_verified(SingleDiskResult): Emitted when disk verification completes
        verification_failed(str): Emitted if verification fails
        track_analyzed(int, int, object): Per-track progress for sector map updates

    Example:
        worker = BatchVerifyWorker(device, geometry, disk_info, "Standard")
        worker.disk_verified.connect(on_disk_verified)
        worker.verification_failed.connect(on_error)
    """

    # Signals
    disk_verified = pyqtSignal(object)      # SingleDiskResult
    verification_failed = pyqtSignal(str)   # Error message
    track_analyzed = pyqtSignal(int, int, object)  # cyl, head, result

    def __init__(
        self,
        device: 'GreaseweazleDevice',
        geometry: 'DiskGeometry',
        disk_info: FloppyDiskInfo,
        analysis_depth: str,
    ):
        """
        Initialize batch verify worker.

        Args:
            device: Connected GreaseweazleDevice instance
            geometry: Disk geometry information
            disk_info: Information about the disk being verified
            analysis_depth: Analysis depth (Quick/Standard/Thorough/Forensic)
        """
        super().__init__(device)
        self._geometry = geometry
        self._disk_info = disk_info
        self._analysis_depth = analysis_depth

        logger.info(
            "BatchVerifyWorker initialized for disk %d (serial=%s, depth=%s)",
            disk_info.index + 1,
            disk_info.serial_number or "N/A",
            analysis_depth
        )

    def run(self) -> None:
        """
        Execute the verification operation for a single disk.

        Runs analysis based on configured depth and returns results
        in batch-compatible format.
        """
        from floppy_formatter.hardware import read_track_flux
        from floppy_formatter.analysis.flux_analyzer import (
            FluxCapture, analyze_flux_timing, detect_encoding_type,
        )
        from floppy_formatter.analysis.signal_quality import grade_track_quality

        start_time = time.time()

        try:
            self._running = True

            # Ensure motor is running
            if not self._device.is_motor_on():
                logger.info("Starting motor for verification...")
                self._device.reinitialize_drive()
            else:
                self._device.motor_on()

            # Wait for motor to stabilize
            time.sleep(0.5)

            # Get tracks to analyze based on depth
            tracks = self._get_tracks_to_analyze()
            total_tracks = len(tracks)

            logger.info("Verifying disk %d: analyzing %d tracks",
                        self._disk_info.index + 1, total_tracks)

            # Accumulate metrics
            quality_scores = []
            snr_values = []
            jitter_values = []
            good_tracks = 0
            bad_tracks = 0
            weak_tracks = 0
            encoding_type = "UNKNOWN"

            for i, (cyl, head) in enumerate(tracks):
                if self._cancelled:
                    logger.info("Verification cancelled")
                    break

                try:
                    # Seek to track
                    self._device.seek(cyl, head)

                    # Capture flux
                    revolutions = self._get_revolutions()
                    flux_data = read_track_flux(
                        self._device, cyl, head, revolutions=revolutions
                    )

                    # Create flux capture for analysis
                    capture = FluxCapture(
                        cylinder=cyl,
                        head=head,
                        flux_data=flux_data,
                        capture_time=datetime.now(),
                    )

                    # Analyze timing
                    timing_stats = analyze_flux_timing(capture)

                    # Detect encoding (use first track's encoding as disk encoding)
                    if i == 0:
                        enc_type, confidence = detect_encoding_type(capture)
                        if confidence > 0.5:
                            encoding_type = enc_type

                    # Grade track quality
                    quality = grade_track_quality(capture, timing_stats)
                    quality_scores.append(quality.score)

                    if quality.snr_db is not None:
                        snr_values.append(quality.snr_db)
                    if quality.jitter_ns is not None:
                        jitter_values.append(quality.jitter_ns)

                    # Count by grade
                    if quality.grade.name in ('A', 'B'):
                        good_tracks += 1
                    elif quality.grade.name in ('D', 'F'):
                        bad_tracks += 1
                    elif quality.grade.name == 'C':
                        weak_tracks += 1

                    # Emit track progress
                    self.track_analyzed.emit(cyl, head, quality)

                    # Update progress
                    progress = int((i + 1) / total_tracks * 100)
                    self.progress.emit(progress)

                except Exception as e:
                    logger.warning("Failed to analyze track %d/%d: %s", cyl, head, e)
                    bad_tracks += 1

            # Calculate overall results
            elapsed_ms = int((time.time() - start_time) * 1000)

            overall_score = 0.0
            if quality_scores:
                overall_score = sum(quality_scores) / len(quality_scores)

            avg_snr = sum(snr_values) / len(snr_values) if snr_values else 0.0
            avg_jitter = sum(jitter_values) / len(jitter_values) if jitter_values else 0.0

            # Estimate sector counts from track quality
            total_sectors = self._geometry.total_sectors
            total_analyzed_tracks = good_tracks + bad_tracks + weak_tracks

            if total_analyzed_tracks > 0:
                good_ratio = good_tracks / total_analyzed_tracks
                bad_ratio = bad_tracks / total_analyzed_tracks
                weak_ratio = weak_tracks / total_analyzed_tracks

                good_sectors = int(total_sectors * good_ratio)
                bad_sectors = int(total_sectors * bad_ratio)
                weak_sectors = int(total_sectors * weak_ratio)
            else:
                good_sectors = 0
                bad_sectors = total_sectors
                weak_sectors = 0

            # Build result
            result = SingleDiskResult(
                disk_info=self._disk_info,
                grade=DiskGrade.from_score(overall_score),
                overall_score=overall_score,
                good_sectors=good_sectors,
                bad_sectors=bad_sectors,
                weak_sectors=weak_sectors,
                total_sectors=total_sectors,
                analysis_duration_ms=elapsed_ms,
                timestamp=datetime.now(),
                encoding_type=encoding_type,
                disk_type="HD" if self._geometry.sectors_per_track >= 18 else "DD",
                average_snr_db=avg_snr,
                average_jitter_ns=avg_jitter,
                recommendations=self._generate_recommendations(overall_score, bad_tracks),
            )

            logger.info(
                "Disk %d verification complete: grade=%s, score=%.1f",
                self._disk_info.index + 1, result.grade.value, overall_score
            )

            self.disk_verified.emit(result)

        except Exception as e:
            logger.error(
                "Verification failed for disk %d: %s",
                self._disk_info.index + 1, e, exc_info=True
            )

            # Return error result
            error_result = SingleDiskResult(
                disk_info=self._disk_info,
                grade=DiskGrade.FAILED,
                error_message=str(e),
                timestamp=datetime.now(),
            )
            self.disk_verified.emit(error_result)
            self.verification_failed.emit(str(e))

        finally:
            self._running = False
            self.finished.emit()

    def _get_tracks_to_analyze(self) -> List[tuple]:
        """
        Get list of (cylinder, head) tuples to analyze based on depth.

        Returns:
            List of (cylinder, head) tuples
        """
        cylinders = self._geometry.cylinders
        heads = self._geometry.heads

        if self._analysis_depth == "Quick":
            # Sample tracks: 0, 20, 40, 60, 79
            sample_cyls = [0, 20, 40, 60, min(79, cylinders - 1)]
            return [(c, h) for c in sample_cyls for h in range(heads)]
        else:
            # All tracks
            return [(c, h) for c in range(cylinders) for h in range(heads)]

    def _get_revolutions(self) -> float:
        """Get number of revolutions based on analysis depth."""
        if self._analysis_depth == "Quick":
            return 1.0
        elif self._analysis_depth == "Standard":
            return 2.0
        elif self._analysis_depth == "Thorough":
            return 3.0
        else:  # Forensic
            return 5.0

    def _generate_recommendations(
        self, score: float, bad_track_count: int
    ) -> List[str]:
        """
        Generate recommendations based on verification results.

        Args:
            score: Overall quality score
            bad_track_count: Number of bad tracks found

        Returns:
            List of recommendation strings
        """
        recs = []

        if score >= 90:
            recs.append("Disk is in excellent condition")
        elif score >= 80:
            recs.append("Disk is in good condition")
        elif score >= 70:
            recs.append("Disk shows some wear, consider backup")
        elif score >= 60:
            recs.append("Disk has significant issues, backup immediately")
        else:
            recs.append("Disk is in poor condition, data recovery recommended")

        if bad_track_count > 10:
            recs.append(f"Multiple bad tracks detected ({bad_track_count})")

        return recs


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'BatchVerifyWorker',
    'SingleDiskResult',
    'BatchVerificationResult',
    'DiskGrade',
]
