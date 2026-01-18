"""
Flux timing analysis for Greaseweazle captures.

This module provides comprehensive analysis of raw flux data captured from
floppy disks, including timing statistics, encoding detection, histogram
generation, and bit cell measurement.

The FluxCapture dataclass extends FluxData with analysis-specific metadata,
while the analysis functions provide deep insights into signal quality
and encoding characteristics.

Key Classes:
    FluxCapture: Extended flux data container with analysis metadata
    TimingStatistics: Comprehensive timing analysis results
    EncodingType: Enum for detected encoding types (MFM, FM, GCR)

Key Functions:
    analyze_flux_timing: Extract detailed timing statistics from flux
    generate_histogram: Create pulse width histogram with peak detection
    detect_encoding_type: Auto-detect disk encoding format
    measure_bit_cell_width: Precisely measure bit cell timing
"""

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional, Tuple, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from floppy_formatter.hardware import FluxData

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# MFM timing constants for 3.5" HD at 300 RPM
# Bit cell is 2.0 microseconds for HD
HD_BIT_CELL_US = 2.0
DD_BIT_CELL_US = 4.0  # Double density

# MFM pulse widths in microseconds (for HD)
MFM_HD_SHORT_US = 4.0     # 2T: 1-0 or 0-1 transition (2 bit cells)
MFM_HD_MEDIUM_US = 6.0    # 3T: 1-00 or 0-01 transition (3 bit cells)
MFM_HD_LONG_US = 8.0      # 4T: 1-000 or 0-001 transition (4 bit cells)

# MFM pulse widths for DD
MFM_DD_SHORT_US = 8.0     # 2T
MFM_DD_MEDIUM_US = 12.0   # 3T
MFM_DD_LONG_US = 16.0     # 4T

# FM timing constants (single density)
FM_SHORT_US = 4.0    # Clock bit
FM_LONG_US = 8.0     # Clock + data bit

# GCR timing (Apple/Commodore formats)
GCR_MIN_US = 3.0
GCR_MAX_US = 5.0

# Analysis thresholds
MIN_TRANSITIONS_FOR_ANALYSIS = 100
PEAK_DETECTION_THRESHOLD = 0.05  # 5% of max count
TIMING_WINDOW_FACTOR = 0.25  # 25% window for peak grouping


# =============================================================================
# Enums
# =============================================================================

class EncodingType(Enum):
    """Detected disk encoding type."""
    MFM = auto()       # Modified Frequency Modulation (PC, Amiga)
    FM = auto()        # Frequency Modulation (older 8" drives)
    GCR = auto()       # Group Coded Recording (Apple, Commodore)
    UNKNOWN = auto()   # Unable to determine encoding


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TimingStatistics:
    """
    Comprehensive timing statistics from flux analysis.

    Contains detailed metrics about pulse timing, distribution,
    and quality indicators for a flux capture.

    Attributes:
        mean_us: Mean pulse width in microseconds
        std_dev_us: Standard deviation of pulse widths
        min_us: Minimum pulse width observed
        max_us: Maximum pulse width observed
        median_us: Median pulse width
        mode_us: Most common pulse width (histogram peak)
        variance_us: Variance of pulse widths
        skewness: Distribution skewness (asymmetry measure)
        kurtosis: Distribution kurtosis (tail weight measure)
        total_transitions: Total number of flux transitions
        short_count: Count of short (2T) pulses
        medium_count: Count of medium (3T) pulses
        long_count: Count of long (4T) pulses
        outlier_count: Count of pulses outside expected MFM range
        outlier_percentage: Percentage of outlier pulses
        peak_positions: Detected histogram peak positions in microseconds
        peak_widths: Width (FWHM) of each detected peak
        bit_cell_estimate_us: Estimated bit cell width
        encoding_confidence: Confidence in encoding detection (0.0-1.0)
    """
    mean_us: float
    std_dev_us: float
    min_us: float
    max_us: float
    median_us: float
    mode_us: float
    variance_us: float
    skewness: float
    kurtosis: float
    total_transitions: int
    short_count: int
    medium_count: int
    long_count: int
    outlier_count: int
    outlier_percentage: float
    peak_positions: List[float]
    peak_widths: List[float]
    bit_cell_estimate_us: float
    encoding_confidence: float

    def get_pulse_distribution(self) -> Dict[str, float]:
        """
        Get the distribution of pulse types as percentages.

        Returns:
            Dictionary with pulse type percentages
        """
        total = self.short_count + self.medium_count + self.long_count
        if total == 0:
            return {'short': 0.0, 'medium': 0.0, 'long': 0.0, 'outlier': 100.0}

        return {
            'short': (self.short_count / self.total_transitions) * 100,
            'medium': (self.medium_count / self.total_transitions) * 100,
            'long': (self.long_count / self.total_transitions) * 100,
            'outlier': self.outlier_percentage,
        }

    def is_valid_mfm(self) -> bool:
        """
        Check if timing statistics are consistent with valid MFM encoding.

        Returns:
            True if data appears to be valid MFM
        """
        # Valid MFM should have:
        # 1. Three distinct peaks
        # 2. Low outlier percentage
        # 3. Reasonable encoding confidence
        return (
            len(self.peak_positions) >= 3 and
            self.outlier_percentage < 10.0 and
            self.encoding_confidence > 0.7
        )


@dataclass
class HistogramBin:
    """Single bin in a pulse width histogram."""
    center_us: float
    count: int
    percentage: float


@dataclass
class HistogramResult:
    """
    Pulse width histogram with peak analysis.

    Contains the histogram data along with detected peaks
    and Gaussian fit parameters for each peak.

    Attributes:
        bins: List of histogram bins
        bin_width_us: Width of each bin in microseconds
        total_count: Total number of samples in histogram
        peaks: Detected peak positions in microseconds
        peak_amplitudes: Height of each peak (count)
        peak_widths: FWHM of each peak (from Gaussian fit)
        peak_areas: Area under each peak
        gaussian_fits: Gaussian fit parameters for each peak
                      Each tuple is (amplitude, center, sigma)
        quality_score: Overall histogram quality (0.0-1.0)
    """
    bins: List[HistogramBin]
    bin_width_us: float
    total_count: int
    peaks: List[float]
    peak_amplitudes: List[int]
    peak_widths: List[float]
    peak_areas: List[float]
    gaussian_fits: List[Tuple[float, float, float]]
    quality_score: float

    def get_bin_centers(self) -> List[float]:
        """Get list of bin center positions."""
        return [b.center_us for b in self.bins]

    def get_bin_counts(self) -> List[int]:
        """Get list of bin counts."""
        return [b.count for b in self.bins]

    def get_peak_separation(self) -> Optional[float]:
        """
        Calculate average separation between peaks.

        Returns:
            Average peak separation in microseconds, or None if < 2 peaks
        """
        if len(self.peaks) < 2:
            return None

        separations = []
        for i in range(1, len(self.peaks)):
            separations.append(self.peaks[i] - self.peaks[i - 1])

        return statistics.mean(separations)


@dataclass
class FluxCapture:
    """
    Extended flux data container with analysis metadata.

    Wraps a FluxData object with additional information useful
    for analysis, including capture timestamp, source information,
    and computed metrics.

    Attributes:
        raw_timings: List of transition times in sample counts
        sample_rate: Clock frequency used for capture (Hz)
        index_positions: List of index pulse positions (sample counts)
        capture_time: Timestamp when capture was taken
        revolutions: Number of complete revolutions captured
        duration_ms: Total capture duration in milliseconds
        metadata: Dictionary for additional capture information
        cylinder: Cylinder number (if known)
        head: Head number (if known)
    """
    raw_timings: List[int]
    sample_rate: int
    index_positions: List[int] = field(default_factory=list)
    capture_time: datetime = field(default_factory=datetime.now)
    revolutions: float = 1.0
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    cylinder: int = -1
    head: int = -1

    def __post_init__(self):
        """Calculate duration if not set."""
        if self.duration_ms == 0.0 and self.raw_timings and self.sample_rate > 0:
            total_samples = sum(self.raw_timings)
            self.duration_ms = (total_samples / self.sample_rate) * 1000.0

    @classmethod
    def from_flux_data(cls, flux_data: 'FluxData',
                       capture_time: Optional[datetime] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> 'FluxCapture':
        """
        Create FluxCapture from a FluxData object.

        Args:
            flux_data: Source FluxData from hardware module
            capture_time: Optional capture timestamp (defaults to now)
            metadata: Optional additional metadata

        Returns:
            FluxCapture instance
        """
        return cls(
            raw_timings=list(flux_data.flux_times),
            sample_rate=flux_data.sample_freq,
            index_positions=list(flux_data.index_positions),
            capture_time=capture_time or datetime.now(),
            revolutions=flux_data.revolutions,
            duration_ms=flux_data.duration_milliseconds,
            metadata=metadata or {},
            cylinder=flux_data.cylinder,
            head=flux_data.head,
        )

    def get_timings_microseconds(self) -> List[float]:
        """
        Convert raw timing values to microseconds.

        Returns:
            List of timing values in microseconds
        """
        if not self.sample_rate:
            return []
        factor = 1_000_000.0 / self.sample_rate
        return [t * factor for t in self.raw_timings]

    def get_timings_nanoseconds(self) -> List[float]:
        """
        Convert raw timing values to nanoseconds.

        Returns:
            List of timing values in nanoseconds
        """
        if not self.sample_rate:
            return []
        factor = 1_000_000_000.0 / self.sample_rate
        return [t * factor for t in self.raw_timings]

    @property
    def transition_count(self) -> int:
        """Get total number of flux transitions."""
        return len(self.raw_timings)

    @property
    def has_index(self) -> bool:
        """Check if capture contains index pulse information."""
        return len(self.index_positions) > 0

    def get_revolution_data(self, revolution: int = 0) -> 'FluxCapture':
        """
        Extract data for a single revolution.

        Args:
            revolution: Revolution number (0-based)

        Returns:
            FluxCapture containing only the specified revolution

        Raises:
            ValueError: If revolution is out of range
        """
        if len(self.index_positions) < 2:
            # No index info, return copy of all data
            return FluxCapture(
                raw_timings=list(self.raw_timings),
                sample_rate=self.sample_rate,
                index_positions=[],
                capture_time=self.capture_time,
                revolutions=1.0,
                metadata=dict(self.metadata),
                cylinder=self.cylinder,
                head=self.head,
            )

        num_revolutions = len(self.index_positions) - 1
        if revolution >= num_revolutions:
            raise ValueError(
                f"Revolution {revolution} out of range (have {num_revolutions})"
            )

        # Find the flux transitions for this revolution
        start_pos = self.index_positions[revolution]
        end_pos = self.index_positions[revolution + 1]

        # Extract transitions
        cumulative = 0
        start_idx = 0
        end_idx = len(self.raw_timings)

        for i, t in enumerate(self.raw_timings):
            if cumulative < start_pos:
                start_idx = i
            cumulative += t
            if cumulative >= end_pos:
                end_idx = i + 1
                break

        return FluxCapture(
            raw_timings=self.raw_timings[start_idx:end_idx],
            sample_rate=self.sample_rate,
            index_positions=[0, end_pos - start_pos],
            capture_time=self.capture_time,
            revolutions=1.0,
            metadata={'source_revolution': revolution, **self.metadata},
            cylinder=self.cylinder,
            head=self.head,
        )

    def calculate_rpm(self) -> Optional[float]:
        """
        Calculate RPM from index pulse timing.

        Returns:
            RPM value, or None if insufficient index data
        """
        if len(self.index_positions) < 2:
            return None

        # Calculate time between consecutive indices
        times = []
        for i in range(1, len(self.index_positions)):
            samples = self.index_positions[i] - self.index_positions[i - 1]
            if samples > 1000:  # Filter noise
                time_seconds = samples / self.sample_rate
                times.append(time_seconds)

        if not times:
            return None

        avg_time = statistics.mean(times)
        return 60.0 / avg_time

    def __repr__(self) -> str:
        """String representation."""
        loc = f"C{self.cylinder}H{self.head}" if self.cylinder >= 0 else "unknown"
        return (
            f"FluxCapture({loc}, {self.transition_count} transitions, "
            f"{self.duration_ms:.1f}ms, {len(self.index_positions)} indices)"
        )


# =============================================================================
# Analysis Functions
# =============================================================================

def analyze_flux_timing(flux: FluxCapture) -> TimingStatistics:
    """
    Extract comprehensive timing statistics from flux data.

    Performs deep analysis of flux timing to characterize the
    recording quality, encoding type, and signal integrity.

    Args:
        flux: FluxCapture to analyze

    Returns:
        TimingStatistics with detailed metrics

    Raises:
        ValueError: If flux has insufficient data for analysis

    Example:
        >>> capture = FluxCapture.from_flux_data(flux_data)
        >>> stats = analyze_flux_timing(capture)
        >>> print(f"Bit cell: {stats.bit_cell_estimate_us:.2f} us")
        >>> if stats.is_valid_mfm():
        ...     print("Valid MFM encoding detected")
    """
    times_us = flux.get_timings_microseconds()

    if len(times_us) < MIN_TRANSITIONS_FOR_ANALYSIS:
        raise ValueError(
            f"Insufficient data for analysis: {len(times_us)} transitions "
            f"(need {MIN_TRANSITIONS_FOR_ANALYSIS})"
        )

    # Basic statistics
    mean_us = statistics.mean(times_us)
    std_dev_us = statistics.stdev(times_us)
    min_us = min(times_us)
    max_us = max(times_us)
    median_us = statistics.median(times_us)
    variance_us = statistics.variance(times_us)

    # Calculate mode (most common value, binned)
    mode_us = _calculate_mode(times_us)

    # Calculate skewness and kurtosis
    skewness = _calculate_skewness(times_us, mean_us, std_dev_us)
    kurtosis = _calculate_kurtosis(times_us, mean_us, std_dev_us)

    # Categorize pulses by expected MFM ranges
    # Determine if HD or DD based on overall timing
    is_hd = mean_us < 10.0  # HD has shorter pulses

    if is_hd:
        short_range = (3.0, 5.0)
        medium_range = (5.0, 7.0)
        long_range = (7.0, 9.0)
        expected_bit_cell = HD_BIT_CELL_US
    else:
        short_range = (6.0, 10.0)
        medium_range = (10.0, 14.0)
        long_range = (14.0, 18.0)
        expected_bit_cell = DD_BIT_CELL_US

    short_count = sum(1 for t in times_us if short_range[0] <= t < short_range[1])
    medium_count = sum(1 for t in times_us if medium_range[0] <= t < medium_range[1])
    long_count = sum(1 for t in times_us if long_range[0] <= t < long_range[1])

    # Outliers are anything outside the expected MFM range
    min_expected = short_range[0] * 0.7
    max_expected = long_range[1] * 1.3
    outlier_count = sum(1 for t in times_us
                        if t < min_expected or t > max_expected)
    outlier_percentage = (outlier_count / len(times_us)) * 100

    # Generate histogram and detect peaks
    histogram = generate_histogram(flux)
    peak_positions = histogram.peaks
    peak_widths = histogram.peak_widths

    # Estimate bit cell width from peaks
    bit_cell_estimate = measure_bit_cell_width(flux)
    if bit_cell_estimate is None:
        bit_cell_estimate = expected_bit_cell

    # Calculate encoding confidence
    encoding_confidence = _calculate_encoding_confidence(
        peak_positions, short_count, medium_count, long_count,
        outlier_percentage, is_hd
    )

    return TimingStatistics(
        mean_us=mean_us,
        std_dev_us=std_dev_us,
        min_us=min_us,
        max_us=max_us,
        median_us=median_us,
        mode_us=mode_us,
        variance_us=variance_us,
        skewness=skewness,
        kurtosis=kurtosis,
        total_transitions=len(times_us),
        short_count=short_count,
        medium_count=medium_count,
        long_count=long_count,
        outlier_count=outlier_count,
        outlier_percentage=outlier_percentage,
        peak_positions=peak_positions,
        peak_widths=peak_widths,
        bit_cell_estimate_us=bit_cell_estimate,
        encoding_confidence=encoding_confidence,
    )


def generate_histogram(
    flux: FluxCapture,
    bins: int = 100,
    min_us: float = 2.0,
    max_us: float = 12.0
) -> HistogramResult:
    """
    Generate pulse width histogram with peak detection and Gaussian fitting.

    Creates a detailed histogram of pulse widths with automatic peak
    detection and Gaussian curve fitting for each detected peak.

    Args:
        flux: FluxCapture to analyze
        bins: Number of histogram bins (default 100)
        min_us: Minimum pulse width to include (microseconds)
        max_us: Maximum pulse width to include (microseconds)

    Returns:
        HistogramResult with bins, peaks, and Gaussian fits

    Example:
        >>> hist = generate_histogram(capture)
        >>> print(f"Detected {len(hist.peaks)} peaks at: {hist.peaks}")
        >>> for center, width in zip(hist.peaks, hist.peak_widths):
        ...     print(f"  Peak at {center:.1f}us, FWHM={width:.2f}us")
    """
    times_us = flux.get_timings_microseconds()

    # Filter to range
    filtered = [t for t in times_us if min_us <= t <= max_us]

    if not filtered:
        return HistogramResult(
            bins=[],
            bin_width_us=(max_us - min_us) / bins,
            total_count=0,
            peaks=[],
            peak_amplitudes=[],
            peak_widths=[],
            peak_areas=[],
            gaussian_fits=[],
            quality_score=0.0,
        )

    # Create histogram bins
    bin_width = (max_us - min_us) / bins
    counts = [0] * bins

    for t in filtered:
        bin_idx = int((t - min_us) / bin_width)
        if 0 <= bin_idx < bins:
            counts[bin_idx] += 1

    # Create bin objects
    histogram_bins = []
    total_count = len(filtered)
    for i in range(bins):
        center = min_us + (i + 0.5) * bin_width
        count = counts[i]
        pct = (count / total_count * 100) if total_count > 0 else 0.0
        histogram_bins.append(HistogramBin(center, count, pct))

    # Detect peaks
    peaks, amplitudes = _detect_peaks(counts, min_us, bin_width)

    # Fit Gaussians to each peak
    gaussian_fits = []
    peak_widths = []
    peak_areas = []

    for peak_pos, amplitude in zip(peaks, amplitudes):
        # Get data around peak for fitting
        peak_bin = int((peak_pos - min_us) / bin_width)
        window = max(5, bins // 20)  # Fit window
        start_bin = max(0, peak_bin - window)
        end_bin = min(bins, peak_bin + window + 1)

        # Fit Gaussian
        fit_centers = [min_us + (i + 0.5) * bin_width
                       for i in range(start_bin, end_bin)]
        fit_counts = counts[start_bin:end_bin]

        amp, center, sigma = _fit_gaussian(fit_centers, fit_counts, peak_pos)
        gaussian_fits.append((amp, center, sigma))

        # FWHM = 2 * sqrt(2 * ln(2)) * sigma ≈ 2.355 * sigma
        fwhm = 2.355 * sigma
        peak_widths.append(fwhm)

        # Area under Gaussian = amp * sigma * sqrt(2*pi)
        area = amp * sigma * math.sqrt(2 * math.pi)
        peak_areas.append(area)

    # Calculate quality score based on:
    # - Number of peaks (3 is optimal for MFM)
    # - Peak sharpness (low FWHM is better)
    # - Peak separation
    quality_score = _calculate_histogram_quality(
        peaks, peak_widths, amplitudes, total_count
    )

    return HistogramResult(
        bins=histogram_bins,
        bin_width_us=bin_width,
        total_count=total_count,
        peaks=peaks,
        peak_amplitudes=amplitudes,
        peak_widths=peak_widths,
        peak_areas=peak_areas,
        gaussian_fits=gaussian_fits,
        quality_score=quality_score,
    )


def detect_encoding_type(flux: FluxCapture) -> Tuple[EncodingType, float]:
    """
    Auto-detect the disk encoding format from flux data.

    Analyzes the pulse width distribution to determine whether
    the data is MFM, FM, GCR, or unknown encoding.

    Args:
        flux: FluxCapture to analyze

    Returns:
        Tuple of (EncodingType, confidence) where confidence is 0.0-1.0

    Example:
        >>> encoding, confidence = detect_encoding_type(capture)
        >>> print(f"Detected: {encoding.name} (confidence: {confidence:.0%})")
    """
    times_us = flux.get_timings_microseconds()

    if len(times_us) < MIN_TRANSITIONS_FOR_ANALYSIS:
        return EncodingType.UNKNOWN, 0.0

    # Generate histogram for analysis
    histogram = generate_histogram(flux, bins=100, min_us=1.0, max_us=20.0)

    if not histogram.peaks:
        return EncodingType.UNKNOWN, 0.0

    # Analyze peak pattern
    peak_positions = sorted(histogram.peaks)

    # MFM characteristics:
    # - 3 distinct peaks at 2T, 3T, 4T ratios
    # - For HD: ~4us, ~6us, ~8us (ratio 2:3:4)
    # - For DD: ~8us, ~12us, ~16us

    # FM characteristics:
    # - 2 peaks at 1T, 2T ratios
    # - ~4us, ~8us for standard FM

    # GCR characteristics:
    # - More complex pattern, typically 4-5 peaks
    # - Narrower pulse width range

    mfm_score = _score_mfm_pattern(peak_positions, histogram.peak_widths)
    fm_score = _score_fm_pattern(peak_positions, histogram.peak_widths)
    gcr_score = _score_gcr_pattern(peak_positions, histogram.peak_widths)

    # Determine encoding by highest score
    scores = [
        (EncodingType.MFM, mfm_score),
        (EncodingType.FM, fm_score),
        (EncodingType.GCR, gcr_score),
    ]

    best_encoding, best_score = max(scores, key=lambda x: x[1])

    # If best score is too low, encoding is unknown
    if best_score < 0.3:
        return EncodingType.UNKNOWN, best_score

    return best_encoding, best_score


def measure_bit_cell_width(flux: FluxCapture) -> Optional[float]:
    """
    Precisely measure the bit cell width from flux data.

    Uses detected MFM peaks to calculate the fundamental bit cell
    timing, which is essential for accurate data recovery.

    Args:
        flux: FluxCapture to analyze

    Returns:
        Bit cell width in microseconds, or None if detection fails

    Example:
        >>> bit_cell = measure_bit_cell_width(capture)
        >>> if bit_cell:
        ...     if bit_cell < 2.5:
        ...         print("High density (HD) disk")
        ...     else:
        ...         print("Double density (DD) disk")
    """
    histogram = generate_histogram(flux, bins=150, min_us=2.0, max_us=18.0)

    if len(histogram.peaks) < 2:
        return None

    peaks = sorted(histogram.peaks)
    estimates = []

    # For MFM, peaks should be at 2T, 3T, 4T
    # So peak separations should be 1T each
    if len(peaks) >= 3:
        # Use ratios to estimate bit cell
        # First peak (2T) / 2 = bit cell
        estimates.append(peaks[0] / 2.0)
        # Second peak (3T) / 3 = bit cell
        estimates.append(peaks[1] / 3.0)
        # Third peak (4T) / 4 = bit cell
        estimates.append(peaks[2] / 4.0)
    elif len(peaks) == 2:
        # Could be FM (1T, 2T) or partial MFM
        ratio = peaks[1] / peaks[0]
        if 1.4 < ratio < 1.7:
            # Looks like 2T, 3T (MFM)
            estimates.append(peaks[0] / 2.0)
            estimates.append(peaks[1] / 3.0)
        elif 1.9 < ratio < 2.1:
            # Looks like 1T, 2T (FM) or 2T, 4T
            estimates.append(peaks[0])
            estimates.append(peaks[1] / 2.0)

    if not estimates:
        return None

    # Use median to reduce outlier impact
    return statistics.median(estimates)


# =============================================================================
# Helper Functions
# =============================================================================

def _calculate_mode(values: List[float], bin_width: float = 0.2) -> float:
    """Calculate mode of a distribution using binning."""
    if not values:
        return 0.0

    # Bin the values
    min_val = min(values)
    bins = {}

    for v in values:
        bin_idx = int((v - min_val) / bin_width)
        bins[bin_idx] = bins.get(bin_idx, 0) + 1

    # Find bin with highest count
    best_bin = max(bins.keys(), key=lambda k: bins[k])
    return min_val + (best_bin + 0.5) * bin_width


def _calculate_skewness(values: List[float], mean: float, std: float) -> float:
    """Calculate skewness (third moment)."""
    if std == 0 or len(values) < 3:
        return 0.0

    n = len(values)
    m3 = sum((x - mean) ** 3 for x in values) / n
    return m3 / (std ** 3)


def _calculate_kurtosis(values: List[float], mean: float, std: float) -> float:
    """Calculate kurtosis (fourth moment, excess kurtosis)."""
    if std == 0 or len(values) < 4:
        return 0.0

    n = len(values)
    m4 = sum((x - mean) ** 4 for x in values) / n
    return (m4 / (std ** 4)) - 3.0  # Excess kurtosis


def _detect_peaks(
    counts: List[int],
    min_us: float,
    bin_width: float
) -> Tuple[List[float], List[int]]:
    """
    Detect peaks in histogram using local maxima detection.

    Returns:
        Tuple of (peak_positions, peak_amplitudes)
    """
    if not counts:
        return [], []

    max_count = max(counts)
    threshold = max_count * PEAK_DETECTION_THRESHOLD

    peaks = []
    amplitudes = []

    # Find local maxima
    for i in range(1, len(counts) - 1):
        if counts[i] > threshold:
            # Check if local maximum
            if counts[i] > counts[i - 1] and counts[i] > counts[i + 1]:
                # Additional check: must be higher than neighbors by margin
                left_min = min(counts[max(0, i - 3):i])
                right_min = min(counts[i + 1:min(len(counts), i + 4)])

                if counts[i] > left_min * 1.2 and counts[i] > right_min * 1.2:
                    pos = min_us + (i + 0.5) * bin_width
                    peaks.append(pos)
                    amplitudes.append(counts[i])

    # Merge peaks that are too close together
    merged_peaks = []
    merged_amplitudes = []
    min_separation = 1.0  # Minimum 1us between peaks

    for pos, amp in zip(peaks, amplitudes):
        if not merged_peaks:
            merged_peaks.append(pos)
            merged_amplitudes.append(amp)
        elif pos - merged_peaks[-1] < min_separation:
            # Merge: keep the higher amplitude peak
            if amp > merged_amplitudes[-1]:
                merged_peaks[-1] = pos
                merged_amplitudes[-1] = amp
        else:
            merged_peaks.append(pos)
            merged_amplitudes.append(amp)

    return merged_peaks, merged_amplitudes


def _fit_gaussian(
    x_data: List[float],
    y_data: List[int],
    initial_center: float
) -> Tuple[float, float, float]:
    """
    Fit a Gaussian curve to the data around a peak.

    Uses simple least-squares approximation.

    Returns:
        Tuple of (amplitude, center, sigma)
    """
    if not x_data or not y_data:
        return 0.0, initial_center, 1.0

    # Find the maximum as amplitude
    max_idx = y_data.index(max(y_data))
    amplitude = float(y_data[max_idx])
    center = x_data[max_idx]

    # Estimate sigma from FWHM
    # Find half-maximum points
    half_max = amplitude / 2

    left_idx = max_idx
    for i in range(max_idx, -1, -1):
        if y_data[i] < half_max:
            left_idx = i
            break

    right_idx = max_idx
    for i in range(max_idx, len(y_data)):
        if y_data[i] < half_max:
            right_idx = i
            break

    # FWHM in x units
    fwhm = x_data[right_idx] - x_data[left_idx] if right_idx > left_idx else 1.0

    # sigma = FWHM / 2.355
    sigma = max(0.1, fwhm / 2.355)

    return amplitude, center, sigma


def _calculate_histogram_quality(
    peaks: List[float],
    widths: List[float],
    amplitudes: List[int],
    total_count: int
) -> float:
    """Calculate quality score for a histogram."""
    if not peaks or total_count == 0:
        return 0.0

    scores = []

    # Score for number of peaks (3 is optimal for MFM)
    num_peaks = len(peaks)
    if num_peaks == 3:
        scores.append(1.0)
    elif num_peaks == 2:
        scores.append(0.7)
    elif num_peaks == 1:
        scores.append(0.4)
    else:
        scores.append(max(0.3, 1.0 - (num_peaks - 3) * 0.1))

    # Score for peak sharpness (lower FWHM is better)
    if widths:
        avg_width = statistics.mean(widths)
        # FWHM < 0.5us is excellent, > 2us is poor
        sharpness_score = max(0, 1.0 - (avg_width - 0.3) / 1.7)
        scores.append(sharpness_score)

    # Score for peak amplitude (higher is better)
    if amplitudes:
        max_amp = max(amplitudes)
        amp_ratio = max_amp / total_count
        # If peak contains >5% of total, good signal
        amp_score = min(1.0, amp_ratio * 20)
        scores.append(amp_score)

    return statistics.mean(scores) if scores else 0.0


def _calculate_encoding_confidence(
    peaks: List[float],
    short_count: int,
    medium_count: int,
    long_count: int,
    outlier_pct: float,
    _is_hd: bool
) -> float:
    """Calculate confidence score for MFM encoding detection."""
    scores = []

    # Peak count score
    if len(peaks) == 3:
        scores.append(1.0)
    elif len(peaks) == 2:
        scores.append(0.6)
    else:
        scores.append(0.3)

    # Distribution balance score
    total = short_count + medium_count + long_count
    if total > 0:
        # Ideal MFM has roughly equal distribution with slight bias toward short
        expected_ratios = [0.4, 0.35, 0.25]  # short, medium, long
        actual_ratios = [
            short_count / total,
            medium_count / total,
            long_count / total
        ]

        # Calculate how close to expected
        diff = sum(abs(e - a) for e, a in zip(expected_ratios, actual_ratios))
        balance_score = max(0, 1.0 - diff)
        scores.append(balance_score)

    # Outlier penalty
    outlier_score = max(0, 1.0 - outlier_pct / 20.0)
    scores.append(outlier_score)

    return statistics.mean(scores) if scores else 0.0


def _score_mfm_pattern(peaks: List[float], widths: List[float]) -> float:
    """Score how well peaks match MFM pattern."""
    if len(peaks) < 2:
        return 0.1

    # MFM should have peaks at 2T, 3T, 4T (ratios 2:3:4)
    # Check if peak ratios match
    peaks = sorted(peaks)

    scores = []

    # Check 3 peaks case
    if len(peaks) >= 3:
        ratio_23 = peaks[1] / peaks[0] if peaks[0] > 0 else 0
        ratio_34 = peaks[2] / peaks[1] if peaks[1] > 0 else 0

        # Expected: 3/2 = 1.5 and 4/3 = 1.33
        score_23 = max(0, 1.0 - abs(ratio_23 - 1.5) * 2)
        score_34 = max(0, 1.0 - abs(ratio_34 - 1.333) * 2)
        scores.extend([score_23, score_34])

    # Check 2 peaks case
    elif len(peaks) == 2:
        ratio = peaks[1] / peaks[0] if peaks[0] > 0 else 0
        # Could be 2T/3T (1.5) or 3T/4T (1.33)
        if 1.4 < ratio < 1.6:
            scores.append(0.8)
        elif 1.25 < ratio < 1.45:
            scores.append(0.7)
        else:
            scores.append(0.3)

    # Peak width score (MFM peaks should be relatively sharp)
    if widths:
        avg_width = statistics.mean(widths)
        width_score = max(0, 1.0 - avg_width / 2.0)
        scores.append(width_score)

    return statistics.mean(scores) if scores else 0.0


def _score_fm_pattern(peaks: List[float], _widths: List[float]) -> float:
    """Score how well peaks match FM pattern."""
    if len(peaks) < 2:
        return 0.1

    peaks = sorted(peaks)

    # FM should have 2 peaks at 1T, 2T (ratio 1:2)
    if len(peaks) == 2:
        ratio = peaks[1] / peaks[0] if peaks[0] > 0 else 0
        if 1.9 < ratio < 2.1:
            return 0.9
        elif 1.7 < ratio < 2.3:
            return 0.6

    # More than 2 peaks is less likely to be FM
    if len(peaks) > 2:
        return 0.2

    return 0.3


def _score_gcr_pattern(peaks: List[float], _widths: List[float]) -> float:
    """Score how well peaks match GCR pattern."""
    if len(peaks) < 3:
        return 0.1

    peaks = sorted(peaks)

    # GCR typically has:
    # - 4-5 closely spaced peaks
    # - Narrower range than MFM
    # - Peak positions don't follow simple integer ratios

    scores = []

    # Check for multiple closely-spaced peaks
    if len(peaks) >= 4:
        scores.append(0.6)
    elif len(peaks) == 3:
        scores.append(0.4)

    # Check peak spacing (GCR has more uniform spacing)
    if len(peaks) >= 3:
        spacings = [peaks[i + 1] - peaks[i] for i in range(len(peaks) - 1)]
        spacing_std = statistics.stdev(spacings) if len(spacings) > 1 else 0
        spacing_mean = statistics.mean(spacings)

        # GCR should have relatively uniform spacing
        cv = spacing_std / spacing_mean if spacing_mean > 0 else 1.0
        uniformity_score = max(0, 1.0 - cv * 2)
        scores.append(uniformity_score)

    # Check range (GCR typically 3-5us range)
    peak_range = peaks[-1] - peaks[0]
    if 2.0 < peak_range < 4.0:
        scores.append(0.7)
    else:
        scores.append(0.3)

    return statistics.mean(scores) if scores else 0.0


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Enums
    'EncodingType',
    # Data classes
    'FluxCapture',
    'TimingStatistics',
    'HistogramBin',
    'HistogramResult',
    # Functions
    'analyze_flux_timing',
    'generate_histogram',
    'detect_encoding_type',
    'measure_bit_cell_width',
    # Constants
    'HD_BIT_CELL_US',
    'DD_BIT_CELL_US',
    'MFM_HD_SHORT_US',
    'MFM_HD_MEDIUM_US',
    'MFM_HD_LONG_US',
]
