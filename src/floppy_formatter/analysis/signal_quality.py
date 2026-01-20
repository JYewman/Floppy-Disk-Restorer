"""
Signal quality analysis for Greaseweazle flux captures.

This module provides comprehensive signal quality metrics including
signal-to-noise ratio (SNR), timing jitter analysis, weak bit detection,
and overall track quality grading.

These metrics are essential for:
- Assessing disk health and degradation
- Identifying problematic areas before data loss
- Optimizing recovery parameters
- Quality control for disk archival

Key Classes:
    JitterMetrics: Timing jitter statistics (RMS, peak-to-peak)
    WeakBitPosition: Location and characteristics of weak bits
    TrackQuality: Overall track quality assessment with grade

Key Functions:
    calculate_snr: Compute signal-to-noise ratio in decibels
    measure_jitter: Analyze timing jitter characteristics
    detect_weak_bits: Find unreliable bit positions
    grade_track_quality: Assign A/B/C/D/F quality grade
"""

import math
import statistics
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from floppy_formatter.analysis.flux_analyzer import FluxCapture

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Quality grade thresholds
GRADE_A_THRESHOLD = 90  # Excellent: 90-100
GRADE_B_THRESHOLD = 75  # Good: 75-89
GRADE_C_THRESHOLD = 60  # Fair: 60-74
GRADE_D_THRESHOLD = 40  # Poor: 40-59
# F: Below 40

# SNR thresholds (in dB)
SNR_EXCELLENT = 20.0  # Very clean signal
SNR_GOOD = 15.0       # Good quality
SNR_FAIR = 10.0       # Acceptable
SNR_POOR = 5.0        # Marginal

# Jitter thresholds (in nanoseconds)
JITTER_EXCELLENT_NS = 50    # Very stable timing
JITTER_GOOD_NS = 100        # Good timing
JITTER_FAIR_NS = 200        # Acceptable
JITTER_POOR_NS = 400        # Marginal

# Weak bit detection thresholds
WEAK_BIT_VARIANCE_THRESHOLD = 0.3  # 30% timing variance indicates weak bit
WEAK_BIT_MIN_SAMPLES = 5           # Minimum samples to detect weak bit

# MFM timing constants for HD (500 kbps data rate)
HD_BIT_CELL_US = 1.0    # 1µs bit cell for HD
HD_BIT_CELL_NS = 1000.0  # 1000ns bit cell for HD


# =============================================================================
# Enums
# =============================================================================

class QualityGrade(Enum):
    """Quality grade letter for track or disk."""
    A = auto()  # Excellent (90-100)
    B = auto()  # Good (75-89)
    C = auto()  # Fair (60-74)
    D = auto()  # Poor (40-59)
    F = auto()  # Failing (<40)

    def __str__(self) -> str:
        return self.name

    @property
    def description(self) -> str:
        """Get human-readable description of grade."""
        descriptions = {
            QualityGrade.A: "Excellent - pristine signal quality",
            QualityGrade.B: "Good - minor degradation, fully recoverable",
            QualityGrade.C: "Fair - noticeable degradation, recoverable with effort",
            QualityGrade.D: "Poor - significant degradation, partial recovery possible",
            QualityGrade.F: "Failing - severe degradation, recovery unlikely",
        }
        return descriptions.get(self, "Unknown")


class WeakBitType(Enum):
    """Classification of weak bit cause."""
    MAGNETIC_FADE = auto()      # Signal has weakened over time
    MEDIA_DEFECT = auto()       # Physical defect on disk surface
    WRITE_SPLICE = auto()       # Weak point at write splice location
    INTENTIONAL = auto()        # Deliberately weak (copy protection)
    TIMING_DRIFT = auto()       # PLL timing issue
    UNKNOWN = auto()            # Cause undetermined


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class JitterMetrics:
    """
    Timing jitter statistics for flux analysis.

    Jitter is the variation in timing of flux transitions from their
    ideal positions. Lower jitter indicates better signal quality.

    Attributes:
        rms_ns: Root-mean-square jitter in nanoseconds
        peak_to_peak_ns: Maximum timing deviation (peak-to-peak)
        mean_deviation_ns: Average absolute deviation from ideal
        max_deviation_ns: Maximum single deviation observed
        min_deviation_ns: Minimum deviation (closest to ideal)
        samples_analyzed: Number of timing samples analyzed
        outlier_count: Number of extreme outliers detected
        outlier_percentage: Percentage of samples that are outliers
        per_pulse_jitter: Jitter broken down by pulse type (2T, 3T, 4T)
    """
    rms_ns: float
    peak_to_peak_ns: float
    mean_deviation_ns: float
    max_deviation_ns: float
    min_deviation_ns: float
    samples_analyzed: int
    outlier_count: int
    outlier_percentage: float
    per_pulse_jitter: Dict[str, float] = field(default_factory=dict)

    def get_quality_assessment(self) -> str:
        """
        Get human-readable quality assessment based on RMS jitter.

        Returns:
            Quality description string
        """
        if self.rms_ns < JITTER_EXCELLENT_NS:
            return "Excellent - very stable timing"
        elif self.rms_ns < JITTER_GOOD_NS:
            return "Good - stable timing"
        elif self.rms_ns < JITTER_FAIR_NS:
            return "Fair - moderate timing variation"
        elif self.rms_ns < JITTER_POOR_NS:
            return "Poor - significant timing variation"
        else:
            return "Critical - severe timing instability"

    def to_score(self) -> float:
        """
        Convert jitter metrics to a 0-100 quality score.

        Returns:
            Score from 0 (worst) to 100 (best)
        """
        # RMS jitter of 50ns = 100, 500ns = 0
        rms_score = max(0, 100 - (self.rms_ns - 50) / 4.5)

        # Outlier penalty
        outlier_penalty = min(30, self.outlier_percentage * 3)

        return max(0, rms_score - outlier_penalty)


@dataclass
class WeakBitPosition:
    """
    Location and characteristics of a detected weak bit.

    Weak bits are positions where the magnetic signal is unreliable,
    causing inconsistent reads across multiple captures.

    Attributes:
        flux_index: Index in the flux timing array
        position_us: Position in microseconds from track start
        bit_position: Estimated bit position in the data stream
        variance: Timing variance at this position (0.0-1.0+)
        confidence: Confidence in weak bit detection (0.0-1.0)
        weak_type: Classification of weak bit cause
        timing_spread_ns: Range of observed timings at this position
        sample_count: Number of samples used for detection
        affected_sector: Sector number if determinable, else -1
        cylinder: Cylinder number if known
        head: Head number if known
    """
    flux_index: int
    position_us: float
    bit_position: int
    variance: float
    confidence: float
    weak_type: WeakBitType
    timing_spread_ns: float
    sample_count: int
    affected_sector: int = -1
    cylinder: int = -1
    head: int = -1

    def is_critical(self) -> bool:
        """
        Check if this weak bit is critical (likely to cause data loss).

        Returns:
            True if weak bit is likely to cause read errors
        """
        return self.variance > 0.5 and self.confidence > 0.8

    def get_severity(self) -> str:
        """
        Get severity level of this weak bit.

        Returns:
            Severity string: "critical", "high", "medium", or "low"
        """
        if self.variance > 0.6:
            return "critical"
        elif self.variance > 0.4:
            return "high"
        elif self.variance > 0.25:
            return "medium"
        else:
            return "low"


@dataclass
class SNRResult:
    """
    Signal-to-noise ratio analysis result.

    Attributes:
        snr_db: Overall SNR in decibels
        signal_power: Estimated signal power
        noise_power: Estimated noise power
        noise_floor_us: Estimated noise floor in timing (microseconds)
        per_peak_snr: SNR for each detected MFM peak
        quality_assessment: Human-readable quality description
    """
    snr_db: float
    signal_power: float
    noise_power: float
    noise_floor_us: float
    per_peak_snr: Dict[str, float] = field(default_factory=dict)
    quality_assessment: str = ""

    def __post_init__(self):
        """Set quality assessment if not provided."""
        if not self.quality_assessment:
            if self.snr_db >= SNR_EXCELLENT:
                self.quality_assessment = "Excellent"
            elif self.snr_db >= SNR_GOOD:
                self.quality_assessment = "Good"
            elif self.snr_db >= SNR_FAIR:
                self.quality_assessment = "Fair"
            elif self.snr_db >= SNR_POOR:
                self.quality_assessment = "Poor"
            else:
                self.quality_assessment = "Critical"


@dataclass
class TrackQuality:
    """
    Overall track quality assessment with letter grade.

    Combines multiple metrics into a comprehensive quality
    assessment for a single track.

    Attributes:
        score: Numeric quality score (0-100)
        grade: Letter grade (A/B/C/D/F)
        snr_db: Signal-to-noise ratio
        jitter_rms_ns: RMS timing jitter
        weak_bit_count: Number of weak bits detected
        transition_count: Total flux transitions
        missing_sector_count: Number of unreadable sectors
        crc_error_count: Number of CRC errors
        signal_strength: Relative signal strength (0.0-1.0)
        factors: Breakdown of contributing factors to score
        recommendations: List of improvement recommendations
        cylinder: Cylinder number
        head: Head number
    """
    score: float
    grade: QualityGrade
    snr_db: float
    jitter_rms_ns: float
    weak_bit_count: int
    transition_count: int
    missing_sector_count: int
    crc_error_count: int
    signal_strength: float
    factors: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    cylinder: int = -1
    head: int = -1

    @classmethod
    def from_score(cls, score: float, **kwargs) -> 'TrackQuality':
        """
        Create TrackQuality from a numeric score.

        Args:
            score: Quality score (0-100)
            **kwargs: Additional attributes

        Returns:
            TrackQuality instance with appropriate grade
        """
        if score >= GRADE_A_THRESHOLD:
            grade = QualityGrade.A
        elif score >= GRADE_B_THRESHOLD:
            grade = QualityGrade.B
        elif score >= GRADE_C_THRESHOLD:
            grade = QualityGrade.C
        elif score >= GRADE_D_THRESHOLD:
            grade = QualityGrade.D
        else:
            grade = QualityGrade.F

        return cls(score=score, grade=grade, **kwargs)

    def is_recoverable(self) -> bool:
        """
        Estimate if data on this track is recoverable.

        Returns:
            True if track data is likely recoverable
        """
        return self.score >= GRADE_D_THRESHOLD or self.crc_error_count == 0

    def get_summary(self) -> str:
        """
        Get one-line summary of track quality.

        Returns:
            Summary string
        """
        return (
            f"Grade {self.grade.name} ({self.score:.0f}/100) - "
            f"SNR: {self.snr_db:.1f}dB, "
            f"Jitter: {self.jitter_rms_ns:.0f}ns, "
            f"Weak bits: {self.weak_bit_count}"
        )


# =============================================================================
# Analysis Functions
# =============================================================================

def calculate_snr(flux: 'FluxCapture') -> SNRResult:
    """
    Calculate signal-to-noise ratio from flux capture.

    SNR is estimated by analyzing the pulse width histogram:
    - Signal power: Energy in the expected MFM peak regions
    - Noise power: Energy outside the expected peaks (including
      inter-peak valleys and outliers)

    Uses numpy for fast vectorized operations (~100x faster than pure Python).

    Args:
        flux: FluxCapture to analyze

    Returns:
        SNRResult with SNR in decibels and supporting metrics

    Example:
        >>> result = calculate_snr(capture)
        >>> print(f"SNR: {result.snr_db:.1f} dB ({result.quality_assessment})")
    """
    times_us = flux.get_timings_microseconds()

    if len(times_us) < 100:
        return SNRResult(
            snr_db=0.0,
            signal_power=0.0,
            noise_power=1.0,
            noise_floor_us=float('inf'),
            quality_assessment="Insufficient data"
        )

    # Convert to numpy array for fast vectorized operations
    times_np = np.array(times_us, dtype=np.float64)

    # Determine if HD or DD
    mean_timing = float(np.mean(times_np))
    is_hd = mean_timing < 10.0

    if is_hd:
        expected_peaks = np.array([2.0, 3.0, 4.0])  # 2T, 3T, 4T for HD MFM
        peak_window = 0.5
    else:
        expected_peaks = np.array([4.0, 6.0, 8.0])  # 2T, 3T, 4T for DD MFM
        peak_window = 1.0

    # Use numpy boolean indexing to categorize samples (vectorized, fast)
    peak_names = ['2T', '3T', '4T']
    per_peak_signal = {}
    signal_mask = np.zeros(len(times_np), dtype=bool)

    for i, peak in enumerate(expected_peaks):
        # Find samples within this peak's window
        mask = np.abs(times_np - peak) < peak_window
        per_peak_signal[peak_names[i]] = times_np[mask]
        signal_mask |= mask

    # Noise samples are everything not in a peak
    noise_samples = times_np[~signal_mask]

    # Calculate signal power using numpy
    signal_power = 0.0
    per_peak_snr = {}

    for i, peak_name in enumerate(peak_names):
        samples = per_peak_signal[peak_name]
        if len(samples) > 0:
            expected = expected_peaks[i]
            # Signal power: inverse of variance (tighter clustering = stronger signal)
            deviations_sq = (samples - expected) ** 2
            variance = float(np.mean(deviations_sq))
            signal_power += len(samples) / (variance + 0.01)

            # Per-peak SNR
            if variance > 0:
                peak_snr = 10 * math.log10(expected ** 2 / variance)
                per_peak_snr[peak_name] = max(-10.0, min(40.0, peak_snr))

    # Noise power from outlier samples
    if len(noise_samples) > 1:
        noise_variance = float(np.var(noise_samples, ddof=1))
        noise_power = len(noise_samples) * noise_variance
        noise_floor_us = float(np.std(noise_samples, ddof=1))
    elif len(noise_samples) == 1:
        noise_power = 1.0
        noise_floor_us = 0.5
    else:
        noise_power = 0.1
        noise_floor_us = 0.5

    # SNR in decibels
    if noise_power > 0:
        snr_linear = signal_power / noise_power
        snr_db = 10 * math.log10(max(0.001, snr_linear))
    else:
        snr_db = 30.0

    # Clamp to reasonable range
    snr_db = max(-10.0, min(40.0, snr_db))

    return SNRResult(
        snr_db=snr_db,
        signal_power=signal_power,
        noise_power=noise_power,
        noise_floor_us=noise_floor_us,
        per_peak_snr=per_peak_snr,
    )


def measure_jitter(
    flux: 'FluxCapture',
    reference_captures: Optional[List['FluxCapture']] = None
) -> JitterMetrics:
    """
    Analyze timing jitter characteristics of flux capture.

    Jitter is measured as the deviation of pulse timings from their
    ideal values. If reference captures are provided, jitter is
    measured across multiple reads of the same track.

    Uses numpy for fast vectorized operations (~100x faster than pure Python).

    Args:
        flux: Primary FluxCapture to analyze
        reference_captures: Optional list of additional captures for
                           cross-revolution jitter analysis

    Returns:
        JitterMetrics with comprehensive jitter statistics

    Example:
        >>> jitter = measure_jitter(capture)
        >>> print(f"RMS Jitter: {jitter.rms_ns:.1f} ns")
        >>> print(jitter.get_quality_assessment())
    """
    times_ns = flux.get_timings_nanoseconds()

    if len(times_ns) < 100:
        return JitterMetrics(
            rms_ns=float('inf'),
            peak_to_peak_ns=float('inf'),
            mean_deviation_ns=float('inf'),
            max_deviation_ns=float('inf'),
            min_deviation_ns=float('inf'),
            samples_analyzed=len(times_ns),
            outlier_count=0,
            outlier_percentage=0.0,
        )

    # Convert to numpy array for fast vectorized operations
    times_np = np.array(times_ns, dtype=np.float64)

    # Determine if HD or DD
    mean_timing = float(np.mean(times_np)) / 1000  # Convert to us
    is_hd = mean_timing < 10.0

    if is_hd:
        expected_timings = np.array([2000.0, 3000.0, 4000.0])  # 2T, 3T, 4T in ns
        tolerance_ns = 1000.0
    else:
        expected_timings = np.array([4000.0, 6000.0, 8000.0])  # DD timings
        tolerance_ns = 2000.0

    # Vectorized: compute distance to each expected timing for all samples
    # Shape: (n_samples, 3) - distance to each of the 3 expected timings
    distances = np.abs(times_np[:, np.newaxis] - expected_timings)

    # Find minimum distance and which expected timing it matches
    min_distances = np.min(distances, axis=1)
    best_matches = np.argmin(distances, axis=1)

    # Mask for samples within tolerance (signal) vs outliers (noise)
    in_tolerance = min_distances <= tolerance_ns
    deviations = min_distances[in_tolerance]
    outlier_count = int(np.sum(~in_tolerance))

    if len(deviations) == 0:
        return JitterMetrics(
            rms_ns=float('inf'),
            peak_to_peak_ns=float('inf'),
            mean_deviation_ns=float('inf'),
            max_deviation_ns=float('inf'),
            min_deviation_ns=float('inf'),
            samples_analyzed=len(times_ns),
            outlier_count=outlier_count,
            outlier_percentage=(outlier_count / len(times_ns)) * 100,
        )

    # Calculate jitter statistics using numpy (fast)
    rms_ns = float(np.sqrt(np.mean(deviations ** 2)))
    peak_to_peak_ns = float(np.max(deviations) - np.min(deviations))
    mean_deviation_ns = float(np.mean(deviations))
    max_deviation_ns = float(np.max(deviations))
    min_deviation_ns = float(np.min(deviations))

    # Per-pulse type jitter
    per_pulse_jitter = {}
    pulse_names = ['2T', '3T', '4T']
    for i, pname in enumerate(pulse_names):
        # Get deviations for samples matched to this pulse type
        pulse_mask = (best_matches == i) & in_tolerance
        pulse_devs = min_distances[pulse_mask]
        if len(pulse_devs) > 0:
            per_pulse_jitter[pname] = float(np.sqrt(np.mean(pulse_devs ** 2)))

    # Cross-capture jitter analysis if references provided
    if reference_captures:
        cross_jitter = _analyze_cross_capture_jitter(flux, reference_captures)
        rms_ns = (rms_ns + cross_jitter) / 2

    return JitterMetrics(
        rms_ns=rms_ns,
        peak_to_peak_ns=peak_to_peak_ns,
        mean_deviation_ns=mean_deviation_ns,
        max_deviation_ns=max_deviation_ns,
        min_deviation_ns=min_deviation_ns,
        samples_analyzed=len(times_ns),
        outlier_count=outlier_count,
        outlier_percentage=(outlier_count / len(times_ns)) * 100,
        per_pulse_jitter=per_pulse_jitter,
    )


def detect_weak_bits(
    captures: List['FluxCapture'],
    variance_threshold: float = WEAK_BIT_VARIANCE_THRESHOLD
) -> List[WeakBitPosition]:
    """
    Find unreliable bit positions by comparing multiple flux captures.

    Weak bits are detected by analyzing timing variance across multiple
    captures of the same track. Positions with high variance are flagged
    as potentially unreliable.

    Args:
        captures: List of FluxCapture from multiple reads of same track
        variance_threshold: Minimum variance to flag as weak (0.0-1.0)

    Returns:
        List of WeakBitPosition for each detected weak bit

    Example:
        >>> # Capture same track multiple times
        >>> captures = [read_track(device, cyl, head) for _ in range(10)]
        >>> weak_bits = detect_weak_bits(captures)
        >>> for wb in weak_bits:
        ...     print(f"Weak bit at position {wb.position_us:.1f}us: {wb.get_severity()}")
    """
    if len(captures) < 2:
        logger.warning("Need at least 2 captures for weak bit detection")
        return []

    # Get all timings in microseconds
    all_timings = [c.get_timings_microseconds() for c in captures]

    # Find minimum length for alignment
    min_len = min(len(t) for t in all_timings)
    if min_len < 100:
        return []

    weak_bits = []
    cylinder = captures[0].cylinder
    head = captures[0].head

    # Calculate cumulative positions for bit position estimation
    cumulative_pos = 0.0

    # Analyze each position
    for i in range(min_len):
        # Get timings at this position across all captures
        timings_at_pos = [t[i] for t in all_timings]

        mean_timing = statistics.mean(timings_at_pos)
        cumulative_pos += mean_timing

        # Calculate coefficient of variation (normalized variance)
        if mean_timing > 0:
            std_dev = statistics.stdev(timings_at_pos) if len(timings_at_pos) > 1 else 0
            cv = std_dev / mean_timing
        else:
            cv = 0

        # Check if variance exceeds threshold
        if cv >= variance_threshold:
            # Calculate timing spread
            timing_spread_ns = (max(timings_at_pos) - min(timings_at_pos)) * 1000

            # Classify weak bit type
            weak_type = _classify_weak_bit_type(
                timings_at_pos, mean_timing, cv, i, min_len
            )

            # Estimate bit position (assuming ~2us per bit cell for HD)
            bit_position = int(cumulative_pos / HD_BIT_CELL_US)

            # Estimate affected sector (18 sectors per track, ~12500 bits per sector)
            bits_per_sector = 12500
            affected_sector = (bit_position // bits_per_sector) + 1
            if affected_sector > 18:
                affected_sector = -1  # Unknown

            # Confidence based on number of samples and consistency
            confidence = min(1.0, len(timings_at_pos) / 10) * (1.0 - 1.0 / (1.0 + cv))

            weak_bits.append(WeakBitPosition(
                flux_index=i,
                position_us=cumulative_pos,
                bit_position=bit_position,
                variance=cv,
                confidence=confidence,
                weak_type=weak_type,
                timing_spread_ns=timing_spread_ns,
                sample_count=len(timings_at_pos),
                affected_sector=affected_sector,
                cylinder=cylinder,
                head=head,
            ))

    # Sort by variance (highest first)
    weak_bits.sort(key=lambda wb: wb.variance, reverse=True)

    logger.debug("Detected %d weak bits from %d captures",
                 len(weak_bits), len(captures))

    return weak_bits


def grade_track_quality(
    flux: 'FluxCapture',
    sector_results: Optional[List[Dict]] = None,
    additional_captures: Optional[List['FluxCapture']] = None
) -> TrackQuality:
    """
    Assign overall A/B/C/D/F quality grade to a track.

    Combines multiple quality metrics into a single comprehensive
    assessment including numeric score, letter grade, and
    recommendations for improvement.

    Args:
        flux: Primary FluxCapture to analyze
        sector_results: Optional list of sector decode results with
                       'success' and 'crc_valid' fields
        additional_captures: Optional captures for weak bit analysis

    Returns:
        TrackQuality with grade and supporting metrics

    Example:
        >>> quality = grade_track_quality(capture, sector_results)
        >>> print(f"Track quality: {quality.grade.name} ({quality.score:.0f}/100)")
        >>> for rec in quality.recommendations:
        ...     print(f"  - {rec}")
    """
    factors = {}
    recommendations = []

    # Calculate SNR
    snr_result = calculate_snr(flux)
    snr_db = snr_result.snr_db

    # SNR score (0-25 points)
    if snr_db >= SNR_EXCELLENT:
        snr_score = 25
    elif snr_db >= SNR_GOOD:
        snr_score = 20
    elif snr_db >= SNR_FAIR:
        snr_score = 15
    elif snr_db >= SNR_POOR:
        snr_score = 10
    else:
        snr_score = 5
        recommendations.append("Consider multi-capture recovery for weak signal")
    factors['snr'] = snr_score

    # Calculate jitter
    jitter = measure_jitter(flux)
    jitter_rms_ns = jitter.rms_ns

    # Jitter score (0-25 points)
    if jitter_rms_ns < JITTER_EXCELLENT_NS:
        jitter_score = 25
    elif jitter_rms_ns < JITTER_GOOD_NS:
        jitter_score = 20
    elif jitter_rms_ns < JITTER_FAIR_NS:
        jitter_score = 15
    elif jitter_rms_ns < JITTER_POOR_NS:
        jitter_score = 10
    else:
        jitter_score = 5
        recommendations.append("PLL tuning may improve marginal sectors")
    factors['jitter'] = jitter_score

    # Weak bit analysis (0-25 points)
    weak_bit_count = 0
    if additional_captures:
        all_captures = [flux] + additional_captures
        weak_bits = detect_weak_bits(all_captures)
        weak_bit_count = len(weak_bits)
        critical_weak_bits = sum(1 for wb in weak_bits if wb.is_critical())

        if critical_weak_bits == 0:
            weak_score = 25
        elif critical_weak_bits <= 5:
            weak_score = 20
        elif critical_weak_bits <= 20:
            weak_score = 15
        elif critical_weak_bits <= 50:
            weak_score = 10
        else:
            weak_score = 5
            recommendations.append("Multiple weak bits detected - use statistical recovery")
    else:
        # Estimate from outlier percentage
        weak_score = max(5, 25 - int(jitter.outlier_percentage * 2))
    factors['weak_bits'] = weak_score

    # Sector decode results (0-25 points)
    missing_sectors = 0
    crc_errors = 0

    if sector_results:
        total_sectors = len(sector_results)
        good_sectors = sum(
            1 for s in sector_results
            if s.get('success', False) and s.get('crc_valid', False)
        )
        crc_errors = sum(
            1 for s in sector_results
            if s.get('success', False) and not s.get('crc_valid', True)
        )
        missing_sectors = total_sectors - good_sectors - crc_errors

        if good_sectors == total_sectors:
            sector_score = 25
        elif good_sectors >= total_sectors - 1:
            sector_score = 20
        elif good_sectors >= total_sectors - 3:
            sector_score = 15
            recommendations.append("Some sectors have CRC errors - retry with multi-read")
        elif good_sectors >= total_sectors // 2:
            sector_score = 10
            recommendations.append("Multiple bad sectors - full recovery recommended")
        else:
            sector_score = 5
            recommendations.append("Track severely damaged - forensic recovery may help")
    else:
        # Estimate from signal quality
        sector_score = int((snr_score + jitter_score) / 2)
    factors['sectors'] = sector_score

    # Calculate total score
    total_score = sum(factors.values())

    # Estimate signal strength (0.0-1.0)
    signal_strength = min(1.0, (snr_db + 10) / 30)

    # Determine grade
    if total_score >= GRADE_A_THRESHOLD:
        grade = QualityGrade.A
    elif total_score >= GRADE_B_THRESHOLD:
        grade = QualityGrade.B
    elif total_score >= GRADE_C_THRESHOLD:
        grade = QualityGrade.C
    elif total_score >= GRADE_D_THRESHOLD:
        grade = QualityGrade.D
    else:
        grade = QualityGrade.F

    # Add grade-specific recommendations
    if grade == QualityGrade.A:
        pass  # No recommendations needed
    elif grade == QualityGrade.B:
        if not recommendations:
            recommendations.append("Good quality - standard read should succeed")
    elif grade == QualityGrade.C:
        recommendations.insert(0, "Fair quality - multiple read attempts recommended")
    elif grade == QualityGrade.D:
        recommendations.insert(0, "Poor quality - aggressive recovery settings recommended")
    elif grade == QualityGrade.F:
        recommendations.insert(0, "Critical condition - forensic recovery mode required")

    return TrackQuality(
        score=float(total_score),
        grade=grade,
        snr_db=snr_db,
        jitter_rms_ns=jitter_rms_ns,
        weak_bit_count=weak_bit_count,
        transition_count=flux.transition_count,
        missing_sector_count=missing_sectors,
        crc_error_count=crc_errors,
        signal_strength=signal_strength,
        factors=factors,
        recommendations=recommendations,
        cylinder=flux.cylinder,
        head=flux.head,
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _analyze_cross_capture_jitter(
    primary: 'FluxCapture',
    references: List['FluxCapture']
) -> float:
    """
    Analyze jitter across multiple captures of the same track.

    Returns:
        Cross-capture RMS jitter in nanoseconds
    """
    all_captures = [primary] + references
    all_timings = [c.get_timings_nanoseconds() for c in all_captures]

    min_len = min(len(t) for t in all_timings)
    if min_len < 100:
        return float('inf')

    # Calculate variance at each position
    position_variances = []

    for i in range(min(min_len, 50000)):  # Limit for performance
        timings_at_pos = [t[i] for t in all_timings]
        if len(timings_at_pos) > 1:
            variance = statistics.variance(timings_at_pos)
            position_variances.append(variance)

    if not position_variances:
        return float('inf')

    # RMS of variances gives cross-capture jitter
    rms_variance = math.sqrt(statistics.mean(position_variances))
    return rms_variance


def _classify_weak_bit_type(
    timings: List[float],
    mean_timing: float,
    variance: float,
    position: int,
    total_length: int
) -> WeakBitType:
    """
    Classify the likely cause of a weak bit.

    Returns:
        WeakBitType classification
    """
    # Check for patterns that indicate specific causes

    # Write splice typically at track start/end
    track_position = position / total_length
    if track_position < 0.02 or track_position > 0.98:
        return WeakBitType.WRITE_SPLICE

    # Timing drift shows as consistent bias
    timing_bias = statistics.mean(timings) - mean_timing
    if abs(timing_bias) > mean_timing * 0.15:
        return WeakBitType.TIMING_DRIFT

    # Check for bimodal distribution (intentional weak bit)
    if len(timings) >= 5:
        sorted_timings = sorted(timings)
        lower = sorted_timings[:len(sorted_timings) // 2]
        upper = sorted_timings[len(sorted_timings) // 2:]
        if lower and upper:
            gap = min(upper) - max(lower)
            spread = max(timings) - min(timings)
            if gap > spread * 0.3:
                return WeakBitType.INTENTIONAL

    # High variance with consistent mean suggests magnetic fade
    if variance > 0.4:
        return WeakBitType.MAGNETIC_FADE

    # Very high variance suggests media defect
    if variance > 0.6:
        return WeakBitType.MEDIA_DEFECT

    return WeakBitType.UNKNOWN


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Enums
    'QualityGrade',
    'WeakBitType',
    # Data classes
    'JitterMetrics',
    'WeakBitPosition',
    'SNRResult',
    'TrackQuality',
    # Functions
    'calculate_snr',
    'measure_jitter',
    'detect_weak_bits',
    'grade_track_quality',
    # Constants
    'GRADE_A_THRESHOLD',
    'GRADE_B_THRESHOLD',
    'GRADE_C_THRESHOLD',
    'GRADE_D_THRESHOLD',
    'SNR_EXCELLENT',
    'SNR_GOOD',
    'SNR_FAIR',
    'SNR_POOR',
    'JITTER_EXCELLENT_NS',
    'JITTER_GOOD_NS',
    'JITTER_FAIR_NS',
    'JITTER_POOR_NS',
]
