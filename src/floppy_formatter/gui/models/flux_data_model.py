"""
Flux data model for efficient data handling in Floppy Workbench.

Provides:
- Lazy loading of flux data per track
- LRU cache for recently accessed tracks
- Background processing for analysis
- Device integration for live capture
- Decoded results caching

Part of Phase 8: Flux Visualization Widgets
"""

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional, Dict, Any, Callable, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QWaitCondition

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice
    from floppy_formatter.analysis.flux_analyzer import FluxCapture

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_CACHE_SIZE = 10  # Number of tracks to keep in cache
DEFAULT_ANALYSIS_TIMEOUT_MS = 30000  # 30 seconds


# =============================================================================
# Data Classes
# =============================================================================

class TrackState(Enum):
    """State of a track in the cache."""
    NOT_LOADED = auto()
    LOADING = auto()
    LOADED = auto()
    ANALYZING = auto()
    ANALYZED = auto()
    ERROR = auto()


@dataclass
class SectorData:
    """
    Decoded sector data.

    Attributes:
        sector_num: Sector number (1-based)
        data: Sector data bytes (512 bytes for standard format)
        crc_valid: Whether CRC verification passed
        idam_position_us: Position of ID address mark in microseconds
        dam_position_us: Position of data address mark in microseconds
        quality_score: Signal quality score (0.0-1.0)
    """
    sector_num: int
    data: bytes
    crc_valid: bool = True
    idam_position_us: float = 0.0
    dam_position_us: float = 0.0
    quality_score: float = 1.0


@dataclass
class TrackQuality:
    """
    Track quality metrics.

    Attributes:
        overall_score: Overall quality score (0.0-1.0)
        signal_strength: Average signal strength
        rms_jitter_ns: RMS timing jitter in nanoseconds
        weak_bit_count: Number of weak/uncertain bits
        error_count: Number of decoding errors
        grade: Letter grade (A/B/C/D/F)
    """
    overall_score: float = 0.0
    signal_strength: float = 0.0
    rms_jitter_ns: float = 0.0
    weak_bit_count: int = 0
    error_count: int = 0
    grade: str = "?"

    @classmethod
    def from_score(cls, score: float) -> 'TrackQuality':
        """Create TrackQuality from overall score."""
        if score >= 0.9:
            grade = "A"
        elif score >= 0.8:
            grade = "B"
        elif score >= 0.7:
            grade = "C"
        elif score >= 0.6:
            grade = "D"
        else:
            grade = "F"

        return cls(overall_score=score, grade=grade)


@dataclass
class HistogramResult:
    """
    Cached histogram analysis results.

    Attributes:
        bin_centers: Histogram bin center positions (µs)
        bin_counts: Count in each bin
        bin_width: Width of each bin (µs)
        peak_positions: Detected peak positions (µs)
        peak_sigmas: Peak widths (σ in µs)
        quality_score: Histogram quality score
    """
    bin_centers: List[float] = field(default_factory=list)
    bin_counts: List[int] = field(default_factory=list)
    bin_width: float = 0.1
    peak_positions: List[float] = field(default_factory=list)
    peak_sigmas: List[float] = field(default_factory=list)
    quality_score: float = 0.0


@dataclass
class JitterResult:
    """
    Cached jitter analysis results.

    Attributes:
        bit_positions: Bit positions
        deviations_ns: Timing deviations in nanoseconds
        rms_ns: RMS jitter
        peak_to_peak_ns: Peak-to-peak jitter
        drift_rate: Timing drift rate
        outlier_indices: Indices of outlier points
    """
    bit_positions: List[int] = field(default_factory=list)
    deviations_ns: List[float] = field(default_factory=list)
    rms_ns: float = 0.0
    peak_to_peak_ns: float = 0.0
    drift_rate: float = 0.0
    outlier_indices: List[int] = field(default_factory=list)


@dataclass
class TrackAnalysis:
    """
    Complete track analysis results.

    Attributes:
        cyl: Cylinder number
        head: Head number
        flux_quality: Overall flux quality score
        jitter_stats: Jitter analysis results
        histogram: Histogram analysis results
        sector_quality: Per-sector quality scores
        recommendations: Analysis recommendations
        analysis_time_ms: Time taken for analysis
    """
    cyl: int
    head: int
    flux_quality: float = 0.0
    jitter_stats: Optional[JitterResult] = None
    histogram: Optional[HistogramResult] = None
    sector_quality: Dict[int, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    analysis_time_ms: int = 0


@dataclass
class TrackFluxData:
    """
    Complete flux data for a single track.

    Attributes:
        cyl: Cylinder number
        head: Head number
        raw_flux: Raw FluxCapture object
        decoded_sectors: List of decoded sectors
        histogram_data: Cached histogram analysis
        jitter_data: Cached jitter analysis
        quality_metrics: Track quality metrics
        capture_time: When the data was captured
        analysis_complete: Whether analysis has been performed
        state: Current state of this track data
        error_message: Error message if state is ERROR
    """
    cyl: int
    head: int
    raw_flux: Optional[Any] = None  # FluxCapture
    decoded_sectors: List[SectorData] = field(default_factory=list)
    histogram_data: Optional[HistogramResult] = None
    jitter_data: Optional[JitterResult] = None
    quality_metrics: Optional[TrackQuality] = None
    capture_time: Optional[datetime] = None
    analysis_complete: bool = False
    state: TrackState = TrackState.NOT_LOADED
    error_message: str = ""

    @property
    def track_key(self) -> tuple:
        """Get (cyl, head) tuple as cache key."""
        return (self.cyl, self.head)

    def get_sector(self, sector_num: int) -> Optional[SectorData]:
        """Get decoded sector by number."""
        for sector in self.decoded_sectors:
            if sector.sector_num == sector_num:
                return sector
        return None


# =============================================================================
# LRU Cache Implementation
# =============================================================================

class LRUCache:
    """
    Thread-safe LRU cache for track data.

    Maintains a fixed number of most recently accessed tracks.
    """

    def __init__(self, max_size: int = DEFAULT_CACHE_SIZE):
        self._max_size = max_size
        self._cache: OrderedDict[tuple, TrackFluxData] = OrderedDict()
        self._lock = threading.RLock()

    @property
    def size(self) -> int:
        """Current number of items in cache."""
        with self._lock:
            return len(self._cache)

    @property
    def max_size(self) -> int:
        """Maximum cache size."""
        return self._max_size

    def get(self, cyl: int, head: int) -> Optional[TrackFluxData]:
        """
        Get track data from cache.

        Moves item to end (most recently used) if found.
        """
        key = (cyl, head)
        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, track_data: TrackFluxData) -> Optional[TrackFluxData]:
        """
        Add or update track data in cache.

        Returns evicted item if cache was full, None otherwise.
        """
        key = track_data.track_key
        evicted = None

        with self._lock:
            if key in self._cache:
                # Update existing
                self._cache[key] = track_data
                self._cache.move_to_end(key)
            else:
                # Evict oldest if at capacity
                if len(self._cache) >= self._max_size:
                    # Pop oldest (first) item
                    _, evicted = self._cache.popitem(last=False)

                self._cache[key] = track_data

        return evicted

    def contains(self, cyl: int, head: int) -> bool:
        """Check if track is in cache."""
        with self._lock:
            return (cyl, head) in self._cache

    def remove(self, cyl: int, head: int) -> Optional[TrackFluxData]:
        """Remove track from cache."""
        key = (cyl, head)
        with self._lock:
            return self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached data."""
        with self._lock:
            self._cache.clear()

    def set_max_size(self, new_size: int) -> List[TrackFluxData]:
        """
        Change maximum cache size.

        Returns list of evicted items if shrinking.
        """
        evicted = []
        with self._lock:
            self._max_size = max(1, new_size)

            # Evict excess items
            while len(self._cache) > self._max_size:
                _, item = self._cache.popitem(last=False)
                evicted.append(item)

        return evicted

    def get_all_keys(self) -> List[tuple]:
        """Get all cached track keys."""
        with self._lock:
            return list(self._cache.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'tracks': list(self._cache.keys()),
            }


# =============================================================================
# Background Analysis Worker
# =============================================================================

class AnalysisWorker(QThread):
    """
    Background worker for track analysis.

    Performs analysis operations in a separate thread.
    """

    analysis_complete = pyqtSignal(int, int, object)  # cyl, head, TrackAnalysis
    analysis_progress = pyqtSignal(int)  # percentage
    analysis_error = pyqtSignal(int, int, str)  # cyl, head, error message

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._wait_condition = QWaitCondition()

        self._cyl: int = 0
        self._head: int = 0
        self._track_data: Optional[TrackFluxData] = None
        self._should_stop = False
        self._has_work = False

    def queue_analysis(self, cyl: int, head: int, track_data: TrackFluxData) -> None:
        """Queue a track for analysis."""
        self._mutex.lock()
        self._cyl = cyl
        self._head = head
        self._track_data = track_data
        self._has_work = True
        self._mutex.unlock()
        self._wait_condition.wakeOne()

    def stop(self) -> None:
        """Stop the worker thread."""
        self._mutex.lock()
        self._should_stop = True
        self._has_work = True  # Wake up if waiting
        self._mutex.unlock()
        self._wait_condition.wakeOne()

    def run(self) -> None:
        """Worker thread main loop."""
        while True:
            # Wait for work
            self._mutex.lock()
            while not self._has_work:
                self._wait_condition.wait(self._mutex)

            if self._should_stop:
                self._mutex.unlock()
                break

            cyl = self._cyl
            head = self._head
            track_data = self._track_data
            self._has_work = False
            self._mutex.unlock()

            if track_data is None:
                continue

            # Perform analysis
            try:
                self.analysis_progress.emit(0)
                analysis = self._analyze_track(track_data)
                self.analysis_progress.emit(100)
                self.analysis_complete.emit(cyl, head, analysis)
            except Exception as e:
                logger.error("Analysis error for track %d/%d: %s", cyl, head, e)
                self.analysis_error.emit(cyl, head, str(e))

    def _analyze_track(self, track_data: TrackFluxData) -> TrackAnalysis:
        """Perform track analysis."""
        import time
        start_time = time.time()

        analysis = TrackAnalysis(
            cyl=track_data.cyl,
            head=track_data.head,
        )

        # Analyze histogram if we have flux data
        self.analysis_progress.emit(20)
        if track_data.raw_flux is not None:
            histogram = self._analyze_histogram(track_data)
            analysis.histogram = histogram
            track_data.histogram_data = histogram

        self.analysis_progress.emit(50)

        # Analyze jitter
        if track_data.raw_flux is not None:
            jitter = self._analyze_jitter(track_data)
            analysis.jitter_stats = jitter
            track_data.jitter_data = jitter

        self.analysis_progress.emit(70)

        # Calculate quality
        quality = self._calculate_quality(track_data, analysis)
        analysis.flux_quality = quality.overall_score
        track_data.quality_metrics = quality

        self.analysis_progress.emit(90)

        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(analysis)

        # Per-sector quality
        for sector in track_data.decoded_sectors:
            analysis.sector_quality[sector.sector_num] = sector.quality_score

        analysis.analysis_time_ms = int((time.time() - start_time) * 1000)
        track_data.analysis_complete = True

        return analysis

    def _analyze_histogram(self, track_data: TrackFluxData) -> HistogramResult:
        """Analyze flux histogram."""
        result = HistogramResult()

        if track_data.raw_flux is None:
            return result

        # Get flux timings
        flux = track_data.raw_flux
        if hasattr(flux, 'timings_us') and flux.timings_us:
            timings = flux.timings_us
        elif hasattr(flux, 'get_timings'):
            timings = flux.get_timings()
        else:
            return result

        if not timings:
            return result

        # Build histogram
        min_us, max_us = 2.0, 12.0
        num_bins = 100
        bin_width = (max_us - min_us) / num_bins

        bin_counts = [0] * num_bins
        bin_centers = [min_us + (i + 0.5) * bin_width for i in range(num_bins)]

        for t in timings:
            if min_us <= t <= max_us:
                idx = int((t - min_us) / bin_width)
                if 0 <= idx < num_bins:
                    bin_counts[idx] += 1

        result.bin_centers = bin_centers
        result.bin_counts = bin_counts
        result.bin_width = bin_width

        # Detect peaks (simplified)
        threshold = max(bin_counts) * 0.1 if bin_counts else 0

        peaks = []
        for i in range(1, len(bin_counts) - 1):
            if (bin_counts[i] > threshold and
                bin_counts[i] > bin_counts[i-1] and
                bin_counts[i] > bin_counts[i+1]):
                peaks.append(bin_centers[i])

        result.peak_positions = peaks[:3]  # Keep top 3 peaks

        return result

    def _analyze_jitter(self, track_data: TrackFluxData) -> JitterResult:
        """Analyze timing jitter."""
        result = JitterResult()

        if track_data.raw_flux is None:
            return result

        # Get flux timings
        flux = track_data.raw_flux
        if hasattr(flux, 'timings_us') and flux.timings_us:
            timings = flux.timings_us
        elif hasattr(flux, 'get_timings'):
            timings = flux.get_timings()
        else:
            return result

        if len(timings) < 10:
            return result

        # Calculate expected timing (MFM HD: 2T=4µs, 3T=6µs, 4T=8µs)
        # For each timing, find deviation from nearest expected value
        expected_timings = [4.0, 6.0, 8.0]  # MFM HD

        bit_positions = []
        deviations = []
        current_bit = 0

        for timing in timings:
            # Find nearest expected timing
            nearest = min(expected_timings, key=lambda x: abs(x - timing))
            deviation = (timing - nearest) * 1000  # Convert to nanoseconds

            bit_positions.append(current_bit)
            deviations.append(deviation)

            # Advance bit position (2T = 2 bits, etc.)
            bits = round(timing / 2.0)
            current_bit += max(1, bits)

        result.bit_positions = bit_positions
        result.deviations_ns = deviations

        if deviations:
            import math
            import statistics as stats

            result.rms_ns = math.sqrt(sum(d*d for d in deviations) / len(deviations))
            result.peak_to_peak_ns = max(deviations) - min(deviations)

            # Detect outliers (> 3 sigma)
            if len(deviations) > 2:
                mean = stats.mean(deviations)
                std = stats.stdev(deviations)
                threshold = 3 * std

                result.outlier_indices = [
                    i for i, d in enumerate(deviations)
                    if abs(d - mean) > threshold
                ]

        return result

    def _calculate_quality(self, track_data: TrackFluxData, analysis: TrackAnalysis) -> TrackQuality:
        """Calculate track quality metrics."""
        quality = TrackQuality()

        scores = []

        # Histogram quality (3 distinct peaks = good)
        if analysis.histogram and analysis.histogram.peak_positions:
            num_peaks = len(analysis.histogram.peak_positions)
            if num_peaks == 3:
                scores.append(1.0)
            elif num_peaks == 2:
                scores.append(0.7)
            else:
                scores.append(0.4)

        # Jitter quality (lower RMS = better)
        if analysis.jitter_stats:
            rms = analysis.jitter_stats.rms_ns
            if rms < 100:
                scores.append(1.0)
            elif rms < 200:
                scores.append(0.8)
            elif rms < 400:
                scores.append(0.6)
            else:
                scores.append(0.3)

            quality.rms_jitter_ns = rms

        # Sector decode quality
        if track_data.decoded_sectors:
            good_sectors = sum(1 for s in track_data.decoded_sectors if s.crc_valid)
            total = len(track_data.decoded_sectors)
            scores.append(good_sectors / total if total > 0 else 0)
            quality.error_count = total - good_sectors

        # Calculate overall score
        if scores:
            quality.overall_score = sum(scores) / len(scores)
        else:
            quality.overall_score = 0.5  # Unknown

        # Assign grade
        if quality.overall_score >= 0.9:
            quality.grade = "A"
        elif quality.overall_score >= 0.8:
            quality.grade = "B"
        elif quality.overall_score >= 0.7:
            quality.grade = "C"
        elif quality.overall_score >= 0.6:
            quality.grade = "D"
        else:
            quality.grade = "F"

        return quality

    def _generate_recommendations(self, analysis: TrackAnalysis) -> List[str]:
        """Generate analysis recommendations."""
        recommendations = []

        # Check histogram
        if analysis.histogram:
            num_peaks = len(analysis.histogram.peak_positions)
            if num_peaks < 3:
                recommendations.append(f"Only {num_peaks} peaks detected; expected 3 for MFM")

        # Check jitter
        if analysis.jitter_stats:
            rms = analysis.jitter_stats.rms_ns
            if rms > 300:
                recommendations.append(f"High jitter ({rms:.0f}ns RMS) - may indicate drive speed issues")

            outliers = len(analysis.jitter_stats.outlier_indices)
            if outliers > 10:
                recommendations.append(f"{outliers} timing outliers detected - possible read errors")

        # Check flux quality
        if analysis.flux_quality < 0.6:
            recommendations.append("Low overall flux quality - consider cleaning disk or drive head")

        if not recommendations:
            recommendations.append("Track looks healthy")

        return recommendations


# =============================================================================
# Main Flux Data Model
# =============================================================================

class FluxDataModel(QObject):
    """
    Model for efficient flux data handling.

    Provides:
    - Lazy loading of flux data per track
    - LRU cache for recently accessed tracks
    - Background processing for analysis
    - Device integration for live capture

    Signals:
        track_flux_ready(int, int, TrackFluxData): Track data loaded
        track_analysis_ready(int, int, TrackAnalysis): Analysis complete
        analysis_progress(int): Analysis progress percentage
        capture_complete(int, int, TrackFluxData): Live capture complete
        error_occurred(str): Error message
    """

    track_flux_ready = pyqtSignal(int, int, object)  # cyl, head, TrackFluxData
    track_analysis_ready = pyqtSignal(int, int, object)  # cyl, head, TrackAnalysis
    analysis_progress = pyqtSignal(int)
    capture_complete = pyqtSignal(int, int, object)  # cyl, head, TrackFluxData
    error_occurred = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        # Cache
        self._cache = LRUCache(DEFAULT_CACHE_SIZE)

        # Device reference
        self._device: Optional[Any] = None  # GreaseweazleDevice

        # Background analysis worker
        self._analysis_worker: Optional[AnalysisWorker] = None

        # Pending requests
        self._pending_loads: Dict[tuple, bool] = {}
        self._pending_analyses: Dict[tuple, bool] = {}

        # Lock for thread-safe operations
        self._lock = threading.RLock()

    # =========================================================================
    # Public API - Data Access
    # =========================================================================

    def get_flux_data(self, cyl: int, head: int) -> Optional[TrackFluxData]:
        """
        Get flux data for a track.

        Returns cached data if available, None if not loaded.
        """
        return self._cache.get(cyl, head)

    def get_decoded_sectors(self, cyl: int, head: int) -> Optional[List[SectorData]]:
        """
        Get decoded sectors for a track.

        Returns sector list if available, None if not decoded.
        """
        track_data = self._cache.get(cyl, head)
        if track_data and track_data.decoded_sectors:
            return track_data.decoded_sectors
        return None

    def get_track_analysis(self, cyl: int, head: int) -> Optional[TrackAnalysis]:
        """
        Get analysis results for a track.

        Returns analysis if available, None if not analyzed.
        """
        track_data = self._cache.get(cyl, head)
        if track_data and track_data.analysis_complete:
            return TrackAnalysis(
                cyl=cyl,
                head=head,
                flux_quality=track_data.quality_metrics.overall_score if track_data.quality_metrics else 0,
                jitter_stats=track_data.jitter_data,
                histogram=track_data.histogram_data,
                sector_quality={s.sector_num: s.quality_score for s in track_data.decoded_sectors},
            )
        return None

    def is_track_cached(self, cyl: int, head: int) -> bool:
        """Check if track is in cache."""
        return self._cache.contains(cyl, head)

    def is_track_analyzed(self, cyl: int, head: int) -> bool:
        """Check if track has been analyzed."""
        track_data = self._cache.get(cyl, head)
        return track_data is not None and track_data.analysis_complete

    # =========================================================================
    # Public API - Data Loading
    # =========================================================================

    def request_track_flux(self, cyl: int, head: int) -> None:
        """
        Request flux data for a track.

        If not cached, triggers async load from device.
        Emits track_flux_ready when complete.
        """
        key = (cyl, head)

        # Check cache first
        track_data = self._cache.get(cyl, head)
        if track_data is not None and track_data.state == TrackState.LOADED:
            self.track_flux_ready.emit(cyl, head, track_data)
            return

        # Check if already loading
        with self._lock:
            if key in self._pending_loads:
                return
            self._pending_loads[key] = True

        # Need to load from device
        if self._device is None:
            self.error_occurred.emit("No device connected")
            with self._lock:
                self._pending_loads.pop(key, None)
            return

        # Create placeholder
        track_data = TrackFluxData(cyl=cyl, head=head, state=TrackState.LOADING)
        self._cache.put(track_data)

        # Trigger load (in real implementation, this would be async)
        self._load_track_from_device(cyl, head)

    def load_from_file(self, filepath: str, cyl: int = 0, head: int = 0) -> bool:
        """
        Load flux data from file (SCP, HFE format).

        Args:
            filepath: Path to flux image file
            cyl: Cylinder to load (for multi-track files)
            head: Head to load

        Returns:
            True if successful
        """
        try:
            logger.info("Loading flux from file: %s", filepath)

            # Determine format by extension
            ext = filepath.lower().split('.')[-1]

            raw_flux = None
            flux_transitions = []

            if ext == 'scp':
                # Load SCP format
                from floppy_formatter.imaging.image_formats import load_scp_track
                flux_transitions = load_scp_track(filepath, cyl, head)
                raw_flux = flux_transitions

            elif ext == 'hfe':
                # Load HFE format
                from floppy_formatter.imaging.image_formats import load_hfe_track
                flux_transitions = load_hfe_track(filepath, cyl, head)
                raw_flux = flux_transitions

            elif ext == 'raw':
                # Load raw flux data
                with open(filepath, 'rb') as f:
                    raw_data = f.read()
                # Parse as array of 32-bit transition times
                import struct
                flux_transitions = list(struct.unpack(f'<{len(raw_data)//4}I', raw_data))
                raw_flux = flux_transitions

            else:
                raise ValueError(f"Unsupported flux format: {ext}")

            # Create track data
            track_data = TrackFluxData(
                cyl=cyl,
                head=head,
                state=TrackState.LOADED,
                capture_time=datetime.now(),
                raw_flux=raw_flux,
                flux_transitions=flux_transitions,
            )

            self._cache.put(track_data)
            self.track_flux_ready.emit(cyl, head, track_data)
            return True

        except Exception as e:
            logger.error("Failed to load flux file: %s", e)
            self.error_occurred.emit(f"Failed to load file: {e}")
            return False

    def save_to_file(self, cyl: int, head: int, filepath: str) -> bool:
        """
        Save flux data to file.

        Args:
            cyl: Cylinder number
            head: Head number
            filepath: Target file path

        Returns:
            True if successful
        """
        track_data = self._cache.get(cyl, head)
        if track_data is None or track_data.raw_flux is None:
            self.error_occurred.emit("No flux data to save")
            return False

        try:
            logger.info("Saving flux to file: %s", filepath)

            # Determine format by extension
            ext = filepath.lower().split('.')[-1]

            if ext == 'scp':
                # Save as SCP format
                from floppy_formatter.imaging.image_formats import save_scp_track
                save_scp_track(filepath, cyl, head, track_data.raw_flux)

            elif ext == 'raw':
                # Save as raw flux data
                import struct
                with open(filepath, 'wb') as f:
                    if isinstance(track_data.raw_flux, (list, tuple)):
                        f.write(struct.pack(f'<{len(track_data.raw_flux)}I', *track_data.raw_flux))
                    else:
                        f.write(track_data.raw_flux)

            else:
                raise ValueError(f"Unsupported save format: {ext}")

            logger.info("Flux saved successfully: %s", filepath)
            return True

        except Exception as e:
            logger.error("Failed to save flux file: %s", e)
            self.error_occurred.emit(f"Failed to save file: {e}")
            return False

    # =========================================================================
    # Public API - Analysis
    # =========================================================================

    def analyze_track_async(self, cyl: int, head: int) -> None:
        """
        Start background analysis of a track.

        Emits track_analysis_ready when complete.
        """
        key = (cyl, head)

        # Check if already analyzed
        track_data = self._cache.get(cyl, head)
        if track_data is None:
            self.error_occurred.emit(f"Track {cyl}/{head} not loaded")
            return

        if track_data.analysis_complete:
            analysis = self.get_track_analysis(cyl, head)
            if analysis:
                self.track_analysis_ready.emit(cyl, head, analysis)
            return

        # Check if already analyzing
        with self._lock:
            if key in self._pending_analyses:
                return
            self._pending_analyses[key] = True

        # Start analysis worker
        if self._analysis_worker is None:
            self._analysis_worker = AnalysisWorker(self)
            self._analysis_worker.analysis_complete.connect(self._on_analysis_complete)
            self._analysis_worker.analysis_progress.connect(self.analysis_progress.emit)
            self._analysis_worker.analysis_error.connect(self._on_analysis_error)
            self._analysis_worker.start()

        track_data.state = TrackState.ANALYZING
        self._analysis_worker.queue_analysis(cyl, head, track_data)

    # =========================================================================
    # Public API - Live Capture
    # =========================================================================

    def set_device(self, device: Any) -> None:
        """Set device for live capture."""
        self._device = device

    def capture_track_live(self, cyl: int, head: int, revolutions: int = 3) -> None:
        """
        Capture flux from device.

        Args:
            cyl: Cylinder number
            head: Head number
            revolutions: Number of revolutions to capture

        Emits capture_complete when done.
        """
        if self._device is None:
            self.error_occurred.emit("No device connected")
            return

        logger.info("Capturing flux for track %d/%d (%d revolutions)", cyl, head, revolutions)

        try:
            from floppy_formatter.hardware import read_track_flux
            from floppy_formatter.analysis.flux_analyzer import FluxCapture

            # Ensure motor is on
            if not self._device.is_motor_on():
                self._device.motor_on()

            # Seek to track
            self._device.seek(cyl, head)

            # Capture flux
            flux_data = read_track_flux(self._device, cyl, head, revolutions=revolutions)
            capture = FluxCapture.from_flux_data(flux_data)

            # Extract transition times
            flux_transitions = list(capture.flux_times) if hasattr(capture, 'flux_times') else []

            # Create track data
            track_data = TrackFluxData(
                cyl=cyl,
                head=head,
                state=TrackState.LOADED,
                capture_time=datetime.now(),
                raw_flux=flux_data,
                flux_transitions=flux_transitions,
            )

            self._cache.put(track_data)
            self.capture_complete.emit(cyl, head, track_data)

            logger.info("Flux capture complete for track %d/%d", cyl, head)

        except Exception as e:
            logger.error("Flux capture failed: %s", e)
            self.error_occurred.emit(f"Capture failed: {e}")

    # =========================================================================
    # Public API - Cache Management
    # =========================================================================

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        with self._lock:
            self._pending_loads.clear()
            self._pending_analyses.clear()

    def set_cache_size(self, num_tracks: int) -> None:
        """Change maximum cache size."""
        self._cache.set_max_size(num_tracks)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()

    def invalidate_track(self, cyl: int, head: int) -> None:
        """
        Invalidate cached data for a track.

        Use after new capture to force reload.
        """
        self._cache.remove(cyl, head)
        with self._lock:
            self._pending_loads.pop((cyl, head), None)
            self._pending_analyses.pop((cyl, head), None)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _load_track_from_device(self, cyl: int, head: int) -> None:
        """Load track data from device (internal)."""
        key = (cyl, head)

        try:
            from floppy_formatter.hardware import read_track_flux
            from floppy_formatter.analysis.flux_analyzer import FluxCapture

            logger.info("Loading track %d/%d from device", cyl, head)

            if self._device is None:
                raise RuntimeError("No device connected")

            # Ensure motor is on
            if not self._device.is_motor_on():
                self._device.motor_on()

            # Seek to track
            self._device.seek(cyl, head)

            # Capture flux
            flux_data = read_track_flux(self._device, cyl, head, revolutions=2)
            capture = FluxCapture.from_flux_data(flux_data)

            # Extract transition times
            flux_transitions = list(capture.flux_times) if hasattr(capture, 'flux_times') else []

            # Create track data with actual flux
            track_data = TrackFluxData(
                cyl=cyl,
                head=head,
                state=TrackState.LOADED,
                capture_time=datetime.now(),
                raw_flux=flux_data,
                flux_transitions=flux_transitions,
            )

            self._cache.put(track_data)

            with self._lock:
                self._pending_loads.pop(key, None)

            self.track_flux_ready.emit(cyl, head, track_data)

        except Exception as e:
            logger.error("Failed to load track %d/%d: %s", cyl, head, e)
            self.error_occurred.emit(f"Failed to load track: {e}")

            with self._lock:
                self._pending_loads.pop(key, None)

    def _on_analysis_complete(self, cyl: int, head: int, analysis: TrackAnalysis) -> None:
        """Handle analysis completion."""
        key = (cyl, head)
        with self._lock:
            self._pending_analyses.pop(key, None)

        # Update track data state
        track_data = self._cache.get(cyl, head)
        if track_data:
            track_data.state = TrackState.ANALYZED

        self.track_analysis_ready.emit(cyl, head, analysis)

    def _on_analysis_error(self, cyl: int, head: int, error: str) -> None:
        """Handle analysis error."""
        key = (cyl, head)
        with self._lock:
            self._pending_analyses.pop(key, None)

        track_data = self._cache.get(cyl, head)
        if track_data:
            track_data.state = TrackState.ERROR
            track_data.error_message = error

        self.error_occurred.emit(f"Analysis failed for track {cyl}/{head}: {error}")

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._analysis_worker:
            self._analysis_worker.stop()
            self._analysis_worker.wait()
            self._analysis_worker = None

        self.clear_cache()


__all__ = [
    # Main model
    'FluxDataModel',
    # Data classes
    'TrackFluxData',
    'TrackAnalysis',
    'TrackQuality',
    'SectorData',
    'HistogramResult',
    'JitterResult',
    # Enums
    'TrackState',
    # Cache
    'LRUCache',
    # Worker
    'AnalysisWorker',
]
