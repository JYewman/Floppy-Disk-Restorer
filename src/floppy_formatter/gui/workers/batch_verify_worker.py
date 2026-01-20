"""
Batch verification worker for verifying multiple floppy disks.

Uses scan-style sector decoding for accurate verification results.
Returns per-track and per-sector results in a batch-compatible format.

Part of Phase 11: Batch Operations
Updated: Now uses CodecAdapter for fast, accurate sector decoding
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
    from floppy_formatter.core.session import DiskSession

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
        if score >= 95:
            return cls.EXCELLENT
        elif score >= 85:
            return cls.GOOD
        elif score >= 70:
            return cls.FAIR
        elif score >= 50:
            return cls.POOR
        else:
            return cls.FAILED


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TrackVerifyResult:
    """
    Verification result for a single track.

    Attributes:
        cylinder: Cylinder number
        head: Head number
        good_sectors: Number of sectors with good CRC
        bad_sectors: Number of sectors with CRC errors
        missing_sectors: Number of sectors not found
        weak_sectors: Number of weak/marginal sectors
        total_expected: Expected number of sectors
        sector_errors: Dict mapping sector number to error description
        verify_time_ms: Time taken to verify this track
    """
    cylinder: int
    head: int
    good_sectors: int = 0
    bad_sectors: int = 0
    missing_sectors: int = 0
    weak_sectors: int = 0
    total_expected: int = 18
    sector_errors: Dict[int, str] = field(default_factory=dict)
    verify_time_ms: int = 0

    @property
    def is_perfect(self) -> bool:
        """Check if all sectors are good."""
        return self.good_sectors == self.total_expected and self.bad_sectors == 0

    @property
    def has_errors(self) -> bool:
        """Check if any sectors have errors."""
        return self.bad_sectors > 0 or self.missing_sectors > 0


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
        missing_sectors: Number of missing sectors
        total_sectors: Total sectors on disk
        analysis_duration_ms: Time taken in milliseconds
        timestamp: When verification was performed
        encoding_type: Detected encoding (MFM, FM, etc.)
        disk_type: Disk type (HD, DD)
        track_results: List of per-track results
        recommendations: List of recommendations
        skipped: Whether the disk was skipped
        error_message: Error message if verification failed
    """
    disk_info: FloppyDiskInfo
    grade: DiskGrade = DiskGrade.FAILED
    overall_score: float = 0.0
    good_sectors: int = 0
    bad_sectors: int = 0
    weak_sectors: int = 0
    missing_sectors: int = 0
    total_sectors: int = 2880
    analysis_duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    encoding_type: str = "MFM"
    disk_type: str = "HD"
    track_results: List[TrackVerifyResult] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    skipped: bool = False
    error_message: Optional[str] = None

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

    @property
    def bad_track_count(self) -> int:
        """Number of tracks with at least one error."""
        return sum(1 for t in self.track_results if t.has_errors)


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

    Uses scan-style sector decoding via CodecAdapter for accurate results.
    Decodes actual sector data and validates CRCs rather than using
    flux quality estimates.

    Signals:
        disk_verified(SingleDiskResult): Emitted when disk verification completes
        verification_failed(str): Emitted if verification fails
        track_verified(int, int, TrackVerifyResult): Per-track progress
        sector_status(int, int, int, bool, str): Per-sector status
            (cyl, head, sector, is_good, error_type)

    Example:
        worker = BatchVerifyWorker(device, geometry, disk_info, "Standard")
        worker.disk_verified.connect(on_disk_verified)
        worker.verification_failed.connect(on_error)
    """

    # Signals
    disk_verified = pyqtSignal(object)       # SingleDiskResult
    verification_failed = pyqtSignal(str)    # Error message
    track_verified = pyqtSignal(int, int, object)  # cyl, head, TrackVerifyResult
    sector_status = pyqtSignal(int, int, int, bool, str)  # cyl, head, sector, is_good, error

    def __init__(
        self,
        device: 'GreaseweazleDevice',
        geometry: 'DiskGeometry',
        disk_info: FloppyDiskInfo,
        analysis_depth: str,
        session: Optional['DiskSession'] = None,
    ):
        """
        Initialize batch verify worker.

        Args:
            device: Connected GreaseweazleDevice instance
            geometry: Disk geometry information. If None and session is provided,
                     geometry is derived from session.to_geometry()
            disk_info: Information about the disk being verified
            analysis_depth: Analysis depth (Quick/Standard/Thorough/Forensic)
            session: Optional DiskSession for session-aware operations.
                    When provided, uses session parameters for accurate verification.
        """
        super().__init__(device, session)

        # Get geometry from session if not explicitly provided
        if geometry is not None:
            self._geometry = geometry
        elif session is not None:
            self._geometry = session.to_geometry()
        else:
            raise ValueError("Either geometry or session must be provided")

        self._disk_info = disk_info
        self._analysis_depth = analysis_depth

        logger.info(
            "BatchVerifyWorker initialized for disk %d (serial=%s, depth=%s, session=%s)",
            disk_info.index + 1,
            disk_info.serial_number or "N/A",
            analysis_depth,
            session.gw_format if session else "None"
        )

    def run(self) -> None:
        """
        Execute the verification operation for a single disk.

        Uses scan-style sector decoding for accurate results.
        """
        from floppy_formatter.hardware.flux_io import read_track_flux

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

            # Get tracks to verify based on depth
            tracks = self._get_tracks_to_verify()
            total_tracks = len(tracks)

            logger.info("Verifying disk %d: scanning %d tracks with sector decoding",
                        self._disk_info.index + 1, total_tracks)

            # Accumulate results
            track_results: List[TrackVerifyResult] = []
            total_good = 0
            total_bad = 0
            total_weak = 0
            total_missing = 0

            sectors_per_track = self._geometry.sectors_per_track

            for i, (cyl, head) in enumerate(tracks):
                if self._cancelled:
                    logger.info("Verification cancelled")
                    break

                track_start = time.time()

                try:
                    # Determine revolutions based on depth
                    revolutions = self._get_revolutions()

                    # Read flux data
                    flux_data = read_track_flux(
                        self._device, cyl, head, revolutions=revolutions
                    )

                    # Decode sectors using CodecAdapter if available, else fallback
                    sectors = self._decode_track(flux_data, cyl, head)

                    # Process decoded sectors
                    track_result = self._process_decoded_sectors(
                        cyl, head, sectors, sectors_per_track
                    )
                    track_result.verify_time_ms = int((time.time() - track_start) * 1000)

                    # Accumulate totals
                    total_good += track_result.good_sectors
                    total_bad += track_result.bad_sectors
                    total_weak += track_result.weak_sectors
                    total_missing += track_result.missing_sectors

                    track_results.append(track_result)

                    # Emit track progress
                    self.track_verified.emit(cyl, head, track_result)

                    # Log progress
                    logger.debug(
                        "Track C%d:H%d verified: %d good, %d bad, %d missing (%.0fms)",
                        cyl, head,
                        track_result.good_sectors,
                        track_result.bad_sectors,
                        track_result.missing_sectors,
                        track_result.verify_time_ms
                    )

                except Exception as e:
                    logger.warning("Failed to verify track C%d:H%d: %s", cyl, head, e)

                    # Record as all missing
                    track_result = TrackVerifyResult(
                        cylinder=cyl,
                        head=head,
                        missing_sectors=sectors_per_track,
                        total_expected=sectors_per_track,
                        sector_errors={s: str(e) for s in range(1, sectors_per_track + 1)},
                        verify_time_ms=int((time.time() - track_start) * 1000)
                    )
                    total_missing += sectors_per_track
                    track_results.append(track_result)
                    self.track_verified.emit(cyl, head, track_result)

                # Update progress
                progress = int((i + 1) / total_tracks * 100)
                self.progress.emit(progress)

            # Calculate final results
            elapsed_ms = int((time.time() - start_time) * 1000)
            total_sectors = self._geometry.total_sectors

            # Calculate score based on actual sector results
            if total_sectors > 0:
                # Perfect = 100, each bad sector reduces score
                good_ratio = total_good / total_sectors
                overall_score = good_ratio * 100
            else:
                overall_score = 0.0

            # Determine disk type and encoding
            disk_type = "HD" if sectors_per_track >= 15 else "DD"
            encoding = "MFM"
            if self._session is not None:
                encoding = getattr(self._session, 'encoding', 'MFM')

            # Build result
            result = SingleDiskResult(
                disk_info=self._disk_info,
                grade=DiskGrade.from_score(overall_score),
                overall_score=overall_score,
                good_sectors=total_good,
                bad_sectors=total_bad,
                weak_sectors=total_weak,
                missing_sectors=total_missing,
                total_sectors=total_sectors,
                analysis_duration_ms=elapsed_ms,
                timestamp=datetime.now(),
                encoding_type=encoding,
                disk_type=disk_type,
                track_results=track_results,
                recommendations=self._generate_recommendations(
                    overall_score, total_bad, total_missing, track_results
                ),
            )

            logger.info(
                "Disk %d verification complete: grade=%s, score=%.1f%%, "
                "good=%d, bad=%d, missing=%d, time=%.1fs",
                self._disk_info.index + 1,
                result.grade.value,
                overall_score,
                total_good,
                total_bad,
                total_missing,
                elapsed_ms / 1000
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

    def _decode_track(self, flux_data, cyl: int, head: int) -> list:
        """
        Decode sectors from flux data.

        Uses CodecAdapter if session is available (fast, accurate),
        otherwise falls back to standard decoders.

        Args:
            flux_data: FluxData from track read
            cyl: Cylinder number
            head: Head number

        Returns:
            List of SectorData objects
        """
        # Try CodecAdapter first (fast, session-aware)
        if self._codec_adapter is not None:
            try:
                sectors = self._codec_adapter.decode_track(flux_data, cyl, head)
                if sectors:
                    logger.debug(
                        "C%d:H%d: CodecAdapter decoded %d sectors",
                        cyl, head, len(sectors)
                    )
                    return sectors
            except Exception as e:
                logger.debug("CodecAdapter failed for C%d:H%d: %s", cyl, head, e)

        # Fallback to Greaseweazle MFM codec
        try:
            from floppy_formatter.hardware.gw_mfm_codec import decode_flux_to_sectors_gw
            sectors = decode_flux_to_sectors_gw(flux_data, cyl, head)
            if sectors:
                logger.debug(
                    "C%d:H%d: GW codec decoded %d sectors",
                    cyl, head, len(sectors)
                )
                return sectors
        except Exception as e:
            logger.debug("GW codec failed for C%d:H%d: %s", cyl, head, e)

        # Last resort: simple MFM decoder
        try:
            from floppy_formatter.hardware.mfm_codec import decode_flux_to_sectors
            sectors = decode_flux_to_sectors(flux_data)
            logger.debug(
                "C%d:H%d: Simple codec decoded %d sectors",
                cyl, head, len(sectors)
            )
            return sectors
        except Exception as e:
            logger.warning("All decoders failed for C%d:H%d: %s", cyl, head, e)
            return []

    def _process_decoded_sectors(
        self,
        cyl: int,
        head: int,
        sectors: list,
        expected_count: int
    ) -> TrackVerifyResult:
        """
        Process decoded sectors into a track result.

        Deduplicates sectors (keeping best result for each sector number)
        and categorizes them by status.

        Args:
            cyl: Cylinder number
            head: Head number
            sectors: List of decoded SectorData
            expected_count: Expected number of sectors per track

        Returns:
            TrackVerifyResult with categorized results
        """
        from floppy_formatter.hardware import SectorStatus

        # Deduplicate sectors - keep best result for each sector number
        best_sectors: Dict[int, Any] = {}

        for sector in sectors:
            sector_num = sector.sector
            if sector_num < 1 or sector_num > expected_count:
                # Invalid sector number (corrupt header?)
                continue

            if sector_num not in best_sectors:
                best_sectors[sector_num] = sector
            else:
                existing = best_sectors[sector_num]
                # Prefer good CRC over bad CRC
                if sector.crc_valid and not existing.crc_valid:
                    best_sectors[sector_num] = sector
                elif sector.crc_valid == existing.crc_valid:
                    # Both same CRC status, prefer better signal quality
                    if hasattr(sector, 'signal_quality') and hasattr(existing, 'signal_quality'):
                        if sector.signal_quality > existing.signal_quality:
                            best_sectors[sector_num] = sector

        # Categorize sectors
        good_count = 0
        bad_count = 0
        weak_count = 0
        missing_count = 0
        sector_errors: Dict[int, str] = {}

        for sector_num in range(1, expected_count + 1):
            if sector_num not in best_sectors:
                # Sector not found
                missing_count += 1
                sector_errors[sector_num] = "Missing"
                self.sector_status.emit(cyl, head, sector_num, False, "Missing")
            else:
                sector = best_sectors[sector_num]

                # Check CRC status
                if sector.crc_valid:
                    # Check for weak/marginal quality
                    quality = getattr(sector, 'signal_quality', 1.0)
                    if quality < 0.7:
                        weak_count += 1
                        self.sector_status.emit(cyl, head, sector_num, True, "Weak")
                    else:
                        good_count += 1
                        self.sector_status.emit(cyl, head, sector_num, True, "")
                else:
                    bad_count += 1
                    error_type = "CRC error"

                    # Check for specific status
                    status = getattr(sector, 'status', None)
                    if status == SectorStatus.NO_DATA:
                        error_type = "No data"
                    elif status == SectorStatus.MISSING:
                        error_type = "Missing data"

                    sector_errors[sector_num] = error_type
                    self.sector_status.emit(cyl, head, sector_num, False, error_type)

        return TrackVerifyResult(
            cylinder=cyl,
            head=head,
            good_sectors=good_count,
            bad_sectors=bad_count,
            weak_sectors=weak_count,
            missing_sectors=missing_count,
            total_expected=expected_count,
            sector_errors=sector_errors,
        )

    def _get_tracks_to_verify(self) -> List[tuple]:
        """
        Get list of (cylinder, head) tuples to verify based on depth.

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
            # All tracks for Standard/Thorough/Forensic
            return [(c, h) for c in range(cylinders) for h in range(heads)]

    def _get_revolutions(self) -> float:
        """Get number of revolutions based on analysis depth."""
        if self._analysis_depth == "Quick":
            return 1.2
        elif self._analysis_depth == "Standard":
            return 2.0
        elif self._analysis_depth == "Thorough":
            return 3.0
        else:  # Forensic
            return 5.0

    def _generate_recommendations(
        self,
        score: float,
        bad_count: int,
        missing_count: int,
        track_results: List[TrackVerifyResult]
    ) -> List[str]:
        """
        Generate recommendations based on verification results.

        Args:
            score: Overall quality score
            bad_count: Total bad sectors
            missing_count: Total missing sectors
            track_results: List of track results

        Returns:
            List of recommendation strings
        """
        recs = []

        # Overall assessment
        if score >= 95:
            recs.append("Disk is in excellent condition - all sectors readable")
        elif score >= 85:
            recs.append("Disk is in good condition with minor issues")
        elif score >= 70:
            recs.append("Disk shows wear - backup recommended")
        elif score >= 50:
            recs.append("Disk has significant issues - backup immediately")
        else:
            recs.append("Disk is in poor condition - data recovery recommended")

        # Specific issues
        if bad_count > 0:
            recs.append(f"Found {bad_count} sectors with CRC errors")

        if missing_count > 0:
            recs.append(f"Found {missing_count} unreadable/missing sectors")

        # Track-specific issues
        bad_tracks = [t for t in track_results if t.has_errors]
        if len(bad_tracks) > 10:
            recs.append(f"Multiple tracks affected ({len(bad_tracks)} tracks with errors)")
        elif bad_tracks:
            # List specific bad tracks
            track_list = ", ".join(
                f"C{t.cylinder}:H{t.head}" for t in bad_tracks[:5]
            )
            if len(bad_tracks) > 5:
                track_list += f" (+{len(bad_tracks) - 5} more)"
            recs.append(f"Errors on tracks: {track_list}")

        # Check for patterns
        if bad_tracks:
            # Check if errors are concentrated on one head
            head0_errors = sum(1 for t in bad_tracks if t.head == 0)
            head1_errors = sum(1 for t in bad_tracks if t.head == 1)

            if head0_errors > 0 and head1_errors == 0:
                recs.append("All errors on head 0 - possible head alignment issue")
            elif head1_errors > 0 and head0_errors == 0:
                recs.append("All errors on head 1 - possible head alignment issue")

            # Check for consecutive track errors (possible media damage)
            consecutive = 0
            max_consecutive = 0
            prev_cyl = -2
            for t in sorted(bad_tracks, key=lambda x: (x.cylinder, x.head)):
                if t.cylinder == prev_cyl + 1 or t.cylinder == prev_cyl:
                    consecutive += 1
                    max_consecutive = max(max_consecutive, consecutive)
                else:
                    consecutive = 1
                prev_cyl = t.cylinder

            if max_consecutive >= 5:
                recs.append(f"Found {max_consecutive} consecutive bad tracks - possible media damage")

        return recs


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'BatchVerifyWorker',
    'SingleDiskResult',
    'BatchVerificationResult',
    'TrackVerifyResult',
    'DiskGrade',
]
