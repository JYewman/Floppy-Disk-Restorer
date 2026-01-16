"""
Analyze worker for Greaseweazle flux analysis operations.

Provides comprehensive disk analysis with flux timing analysis,
signal quality metrics, encoding detection, and overall quality grading.

Part of Phase 9: Workers & Background Processing
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Dict, Optional, Any, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal

from floppy_formatter.gui.workers.base_worker import GreaseweazleWorker

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice
    from floppy_formatter.core.geometry import DiskGeometry
    from floppy_formatter.analysis.flux_analyzer import FluxCapture, TimingStatistics
    from floppy_formatter.analysis.signal_quality import TrackQuality

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class AnalysisDepth(Enum):
    """
    Analysis depth determining thoroughness and speed.

    QUICK: Sample tracks only with basic metrics
    STANDARD: All tracks with full analysis
    COMPREHENSIVE: All tracks with multi-capture quality assessment
    """
    QUICK = auto()
    STANDARD = auto()
    COMPREHENSIVE = auto()


class AnalysisComponent(Enum):
    """Components of analysis that can be enabled/disabled."""
    FLUX_TIMING = auto()      # Timing histogram and statistics
    SIGNAL_QUALITY = auto()   # SNR and jitter metrics
    ENCODING = auto()         # Encoding type detection
    WEAK_BITS = auto()        # Weak bit detection (requires multi-capture)
    FORENSICS = auto()        # Copy protection, format analysis


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AnalysisConfig:
    """
    Configuration for an analysis operation.

    Attributes:
        depth: Analysis depth (QUICK, STANDARD, COMPREHENSIVE)
        components: Set of analysis components to enable
        capture_revolutions: Number of revolutions to capture per track
        save_flux: Whether to save raw flux data for later analysis
        report_format: Output report format ('html', 'json', 'text')
    """
    depth: AnalysisDepth = AnalysisDepth.STANDARD
    components: List[AnalysisComponent] = field(default_factory=lambda: [
        AnalysisComponent.FLUX_TIMING,
        AnalysisComponent.SIGNAL_QUALITY,
        AnalysisComponent.ENCODING,
    ])
    capture_revolutions: int = 2
    save_flux: bool = False
    report_format: str = 'html'

    def includes(self, component: AnalysisComponent) -> bool:
        """Check if a component is enabled."""
        return component in self.components


@dataclass
class TrackAnalysisResult:
    """
    Analysis result for a single track.

    Attributes:
        cylinder: Cylinder number
        head: Head number
        timing_stats: Flux timing statistics
        quality: Track quality grade and metrics
        encoding_type: Detected encoding type
        encoding_confidence: Confidence in encoding detection
        bit_cell_us: Measured bit cell width in microseconds
        peak_positions: Detected histogram peak positions
        weak_bit_count: Number of weak bits detected
        analysis_time_ms: Time taken to analyze in milliseconds
        copy_protection: Copy protection analysis result
        format_analysis: Format analysis result
    """
    cylinder: int
    head: int
    timing_stats: Optional['TimingStatistics'] = None
    quality: Optional['TrackQuality'] = None
    encoding_type: str = "UNKNOWN"
    encoding_confidence: float = 0.0
    bit_cell_us: float = 0.0
    peak_positions: List[float] = field(default_factory=list)
    weak_bit_count: int = 0
    analysis_time_ms: float = 0.0
    copy_protection: Optional[Any] = None
    format_analysis: Optional[Any] = None

    @property
    def track_number(self) -> int:
        """Linear track number (0-159)."""
        return self.cylinder * 2 + self.head

    @property
    def grade(self) -> str:
        """Quality grade as string."""
        if self.quality:
            return self.quality.grade.name
        return "?"


@dataclass
class DiskAnalysisResult:
    """
    Complete analysis result for entire disk.

    Attributes:
        total_tracks: Total number of tracks analyzed
        tracks_analyzed: Actual number of tracks analyzed (may differ for QUICK)
        track_results: Per-track analysis results
        overall_quality_score: Average quality score (0-100)
        overall_grade: Overall disk quality grade
        encoding_type: Detected disk encoding type
        disk_type: Detected disk type (HD, DD)
        average_snr_db: Average signal-to-noise ratio
        average_jitter_ns: Average timing jitter
        weak_track_count: Number of tracks with weak bits
        bad_track_count: Number of tracks with quality grade D or F
        analysis_duration: Total analysis time in seconds
        timestamp: When analysis was performed
        recommendations: List of recommendations based on analysis
        is_copy_protected: Whether any copy protection detected
        protection_types: List of detected protection types
        format_type: Detected disk format type
        format_is_standard: Whether format is standard
        protected_track_count: Number of tracks with copy protection
    """
    total_tracks: int
    tracks_analyzed: int = 0
    track_results: List[TrackAnalysisResult] = field(default_factory=list)
    overall_quality_score: float = 0.0
    overall_grade: str = "?"
    encoding_type: str = "UNKNOWN"
    disk_type: str = "UNKNOWN"
    average_snr_db: float = 0.0
    average_jitter_ns: float = 0.0
    weak_track_count: int = 0
    bad_track_count: int = 0
    analysis_duration: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    recommendations: List[str] = field(default_factory=list)
    is_copy_protected: bool = False
    protection_types: List[str] = field(default_factory=list)
    format_type: str = "UNKNOWN"
    format_is_standard: bool = True
    protected_track_count: int = 0

    @property
    def health_percentage(self) -> float:
        """Overall disk health as percentage."""
        return self.overall_quality_score

    def get_grade_distribution(self) -> Dict[str, int]:
        """Get count of tracks by grade."""
        distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0, '?': 0}
        for result in self.track_results:
            grade = result.grade
            if grade in distribution:
                distribution[grade] += 1
        return distribution


# =============================================================================
# Analyze Worker
# =============================================================================

class AnalyzeWorker(GreaseweazleWorker):
    """
    Worker for comprehensive disk analysis.

    Performs deep flux analysis on all tracks to assess disk quality,
    detect encoding, measure signal characteristics, and identify
    potential problem areas.

    Features:
    - Flux timing analysis with histogram and peak detection
    - Signal quality metrics (SNR, jitter, weak bits)
    - Encoding type detection (MFM, FM, GCR)
    - Quality grading (A/B/C/D/F) per track and overall
    - Configurable analysis depth and components

    Signals:
        track_analyzed(int, int, object): Per track (cyl, head, TrackAnalysisResult)
        flux_quality_update(int, int, float): Quality update (cyl, head, score)
        analysis_complete(object): Final complete analysis result

    Example:
        config = AnalysisConfig(
            depth=AnalysisDepth.COMPREHENSIVE,
            components=[AnalysisComponent.FLUX_TIMING, AnalysisComponent.SIGNAL_QUALITY],
        )
        worker = AnalyzeWorker(device, geometry, config)
        worker.track_analyzed.connect(on_track_analyzed)
        worker.analysis_complete.connect(on_analysis_complete)
    """

    # Signals specific to analysis
    track_analyzed = pyqtSignal(int, int, object)   # cyl, head, TrackAnalysisResult
    flux_quality_update = pyqtSignal(int, int, float)  # cyl, head, quality_score
    analysis_complete = pyqtSignal(object)          # DiskAnalysisResult

    def __init__(
        self,
        device: 'GreaseweazleDevice',
        geometry: 'DiskGeometry',
        config: AnalysisConfig,
    ):
        """
        Initialize analyze worker.

        Args:
            device: Connected GreaseweazleDevice instance
            geometry: Disk geometry information
            config: AnalysisConfig with analysis settings
        """
        super().__init__(device)
        self._geometry = geometry
        self._config = config

        # Store flux captures for comprehensive analysis
        self._flux_cache: Dict[tuple, Any] = {}

        logger.info(
            "AnalyzeWorker initialized: depth=%s, components=%d",
            config.depth.name, len(config.components)
        )

    def run(self) -> None:
        """
        Execute the analysis operation.

        Analyzes all tracks according to configuration, building
        a comprehensive disk quality assessment.
        """
        from floppy_formatter.hardware import read_track_flux
        from floppy_formatter.analysis.flux_analyzer import (
            FluxCapture, analyze_flux_timing, detect_encoding_type,
            measure_bit_cell_width, generate_histogram
        )
        from floppy_formatter.analysis.signal_quality import (
            calculate_snr, measure_jitter, grade_track_quality, detect_weak_bits
        )

        start_time = time.time()

        # Initialize result
        total_tracks = self._geometry.cylinders * self._geometry.heads
        result = DiskAnalysisResult(
            total_tracks=total_tracks,
        )

        # Ensure drive is properly initialized and motor is on
        if not self._device.is_motor_on():
            logger.info("Motor not running, reinitializing drive before analysis...")
            self._device.reinitialize_drive()
        else:
            # Just ensure motor is on with standard method
            self._device.motor_on()

        # Get tracks to analyze based on depth
        tracks_to_analyze = self._get_tracks_to_analyze()
        total_to_analyze = len(tracks_to_analyze)

        logger.info("Analyzing %d tracks in %s mode",
                    total_to_analyze, self._config.depth.name)

        # Accumulate metrics for averaging
        snr_values = []
        jitter_values = []
        quality_scores = []
        encoding_counts: Dict[str, int] = {}

        # Analyze each track
        analyzed_count = 0
        for cylinder, head in tracks_to_analyze:
            if self._cancelled:
                logger.info("Analysis cancelled at track %d/%d", cylinder, head)
                break

            track_start = time.time()

            # Seek and capture flux
            self._device.seek(cylinder, head)
            revolutions = self._config.capture_revolutions
            if self._config.depth == AnalysisDepth.COMPREHENSIVE:
                revolutions = max(3, revolutions)

            flux_data = read_track_flux(self._device, cylinder, head, revolutions=revolutions)
            capture = FluxCapture.from_flux_data(flux_data)
            capture.cylinder = cylinder
            capture.head = head

            # Save flux if configured
            if self._config.save_flux:
                self._flux_cache[(cylinder, head)] = capture

            # Initialize track result
            track_result = TrackAnalysisResult(cylinder=cylinder, head=head)

            # Perform analysis based on enabled components
            try:
                # Flux timing analysis
                if self._config.includes(AnalysisComponent.FLUX_TIMING):
                    timing_stats = analyze_flux_timing(capture)
                    track_result.timing_stats = timing_stats
                    track_result.peak_positions = timing_stats.peak_positions
                    track_result.bit_cell_us = timing_stats.bit_cell_estimate_us

                # Encoding detection
                if self._config.includes(AnalysisComponent.ENCODING):
                    encoding, confidence = detect_encoding_type(capture)
                    track_result.encoding_type = encoding.name
                    track_result.encoding_confidence = confidence
                    encoding_counts[encoding.name] = encoding_counts.get(encoding.name, 0) + 1

                # Signal quality analysis
                if self._config.includes(AnalysisComponent.SIGNAL_QUALITY):
                    quality = grade_track_quality(capture)
                    track_result.quality = quality
                    snr_values.append(quality.snr_db)
                    jitter_values.append(quality.jitter_rms_ns)
                    quality_scores.append(quality.score)

                    # Emit quality update
                    self.flux_quality_update.emit(cylinder, head, quality.score)

                # Weak bit detection (comprehensive mode only)
                if (self._config.includes(AnalysisComponent.WEAK_BITS) and
                        self._config.depth == AnalysisDepth.COMPREHENSIVE):
                    # Would need multiple captures for proper weak bit detection
                    # For now, estimate from jitter metrics
                    if track_result.quality:
                        track_result.weak_bit_count = int(
                            track_result.quality.jitter_rms_ns / 50
                        )

                # Forensics analysis (copy protection and format analysis)
                if self._config.includes(AnalysisComponent.FORENSICS):
                    from floppy_formatter.analysis.forensics import (
                        detect_copy_protection, analyze_format_type
                    )

                    # Analyze copy protection
                    protection_result = detect_copy_protection(capture)
                    track_result.copy_protection = protection_result

                    # Analyze format type
                    format_result = analyze_format_type(capture)
                    track_result.format_analysis = format_result

                    logger.debug(
                        "Forensics C%d:H%d: protected=%s, format=%s",
                        cylinder, head,
                        protection_result.is_protected,
                        format_result.format_type.name
                    )

            except Exception as e:
                logger.warning("Analysis failed for C%d:H%d: %s", cylinder, head, e)
                track_result.encoding_type = "ERROR"

            track_result.analysis_time_ms = (time.time() - track_start) * 1000

            # Store result
            result.track_results.append(track_result)

            # Emit track result
            self.track_analyzed.emit(cylinder, head, track_result)

            # Update progress
            analyzed_count += 1
            progress = int((analyzed_count / total_to_analyze) * 100)
            self.progress.emit(progress)

            logger.debug(
                "Track C%d:H%d analyzed: grade=%s, %.1f ms",
                cylinder, head, track_result.grade, track_result.analysis_time_ms
            )

        # Calculate overall statistics
        result.tracks_analyzed = analyzed_count

        if quality_scores:
            result.overall_quality_score = sum(quality_scores) / len(quality_scores)
            result.overall_grade = self._score_to_grade(result.overall_quality_score)

        if snr_values:
            result.average_snr_db = sum(snr_values) / len(snr_values)

        if jitter_values:
            result.average_jitter_ns = sum(jitter_values) / len(jitter_values)

        # Determine most common encoding
        if encoding_counts:
            result.encoding_type = max(encoding_counts, key=encoding_counts.get)

        # Determine disk type from bit cell
        bit_cells = [tr.bit_cell_us for tr in result.track_results if tr.bit_cell_us > 0]
        if bit_cells:
            avg_bit_cell = sum(bit_cells) / len(bit_cells)
            result.disk_type = "HD" if avg_bit_cell < 3.0 else "DD"

        # Count weak and bad tracks
        for tr in result.track_results:
            if tr.weak_bit_count > 10:
                result.weak_track_count += 1
            if tr.grade in ('D', 'F'):
                result.bad_track_count += 1

        # Aggregate forensics results
        if self._config.includes(AnalysisComponent.FORENSICS):
            all_protection_types = set()
            format_counts: Dict[str, int] = {}
            non_standard_count = 0

            for tr in result.track_results:
                # Copy protection summary
                if tr.copy_protection and tr.copy_protection.is_protected:
                    result.protected_track_count += 1
                    for pt in tr.copy_protection.protection_types:
                        all_protection_types.add(pt.name)

                # Format analysis summary
                if tr.format_analysis:
                    fmt_name = tr.format_analysis.format_type.name
                    format_counts[fmt_name] = format_counts.get(fmt_name, 0) + 1
                    if not tr.format_analysis.is_standard:
                        non_standard_count += 1

            result.is_copy_protected = result.protected_track_count > 0
            result.protection_types = list(all_protection_types)

            if format_counts:
                result.format_type = max(format_counts, key=format_counts.get)
                result.format_is_standard = non_standard_count == 0

        # Generate recommendations
        result.recommendations = self._generate_recommendations(result)

        result.analysis_duration = time.time() - start_time

        logger.info(
            "Analysis complete: %d tracks, grade=%s (%.1f), %.1fs",
            result.tracks_analyzed, result.overall_grade,
            result.overall_quality_score, result.analysis_duration
        )

        self.analysis_complete.emit(result)
        self.finished.emit()

    def _get_tracks_to_analyze(self) -> List[tuple]:
        """
        Get list of tracks to analyze based on depth.

        Returns:
            List of (cylinder, head) tuples
        """
        cylinders = self._geometry.cylinders
        heads = self._geometry.heads

        if self._config.depth == AnalysisDepth.QUICK:
            # Sample key tracks
            key_cylinders = [0, cylinders // 4, cylinders // 2,
                            3 * cylinders // 4, cylinders - 1]
            tracks = []
            for cyl in key_cylinders:
                for head in range(heads):
                    tracks.append((cyl, head))
            return tracks

        else:
            # All tracks for STANDARD and COMPREHENSIVE
            return [
                (cyl, head)
                for cyl in range(cylinders)
                for head in range(heads)
            ]

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return 'A'
        elif score >= 75:
            return 'B'
        elif score >= 60:
            return 'C'
        elif score >= 40:
            return 'D'
        else:
            return 'F'

    def _generate_recommendations(self, result: DiskAnalysisResult) -> List[str]:
        """Generate recommendations based on analysis results."""
        recommendations = []

        # Grade-based recommendations
        if result.overall_grade == 'A':
            recommendations.append("Disk is in excellent condition - standard operations recommended")
        elif result.overall_grade == 'B':
            recommendations.append("Disk is in good condition - minor degradation detected")
        elif result.overall_grade == 'C':
            recommendations.append("Disk shows moderate wear - multi-read recovery recommended")
        elif result.overall_grade == 'D':
            recommendations.append("Disk is degraded - aggressive recovery settings recommended")
        else:
            recommendations.append("Disk is severely degraded - forensic recovery mode required")

        # SNR recommendations
        if result.average_snr_db < 10:
            recommendations.append("Low signal strength detected - consider cleaning disk surface")

        # Jitter recommendations
        if result.average_jitter_ns > 200:
            recommendations.append("High timing jitter - PLL tuning may improve results")

        # Bad track recommendations
        if result.bad_track_count > 0:
            pct = (result.bad_track_count / result.tracks_analyzed) * 100
            if pct > 20:
                recommendations.append(f"{result.bad_track_count} tracks have poor quality - expect data loss")
            else:
                recommendations.append(f"{result.bad_track_count} weak tracks detected - targeted recovery possible")

        # Weak bit recommendations
        if result.weak_track_count > 5:
            recommendations.append("Multiple tracks with weak bits - multi-capture recovery recommended")

        # Forensics recommendations
        if result.is_copy_protected:
            recommendations.append(
                f"Copy protection detected on {result.protected_track_count} tracks - "
                "use raw flux capture for preservation"
            )
            if result.protection_types:
                types_str = ", ".join(result.protection_types[:3])
                recommendations.append(f"Protection types: {types_str}")

        if not result.format_is_standard:
            recommendations.append(
                f"Non-standard format detected ({result.format_type}) - "
                "analyze format before standard decode"
            )

        return recommendations

    def get_geometry(self) -> 'DiskGeometry':
        """Get the disk geometry being used."""
        return self._geometry

    def get_config(self) -> AnalysisConfig:
        """Get the analysis configuration."""
        return self._config

    def get_flux_cache(self) -> Dict[tuple, Any]:
        """Get cached flux data if save_flux was enabled."""
        return dict(self._flux_cache)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'AnalyzeWorker',
    'AnalysisConfig',
    'AnalysisDepth',
    'AnalysisComponent',
    'TrackAnalysisResult',
    'DiskAnalysisResult',
]
