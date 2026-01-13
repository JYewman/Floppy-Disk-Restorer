"""
Flux-level I/O operations for Greaseweazle.

This module provides the FluxData dataclass for storing raw flux captures
and high-level functions for reading, writing, and analyzing flux data
from floppy disks.

Flux data represents the raw magnetic transitions on the disk surface,
captured as timing values between each transition. This low-level data
can be decoded into sector data using the MFM codec.

Key Classes:
    FluxData: Container for raw flux timing data with analysis methods

Key Functions:
    read_track_flux: Capture flux from a track
    write_track_flux: Write flux to a track
    erase_track_flux: Bulk erase a track
    analyze_flux_quality: Calculate signal quality metrics
"""

import logging
import math
import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Iterator

# Greaseweazle imports
try:
    from greaseweazle.flux import Flux
    GREASEWEAZLE_AVAILABLE = True
except ImportError:
    GREASEWEAZLE_AVAILABLE = False
    Flux = None

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Standard MFM timing values for 3.5" HD at 300 RPM
# Bit cell is 2.0 microseconds for HD
HD_BIT_CELL_US = 2.0

# MFM pulse widths in microseconds (for HD)
MFM_SHORT_US = 4.0    # 1-0 or 0-1 transition (2 bit cells)
MFM_MEDIUM_US = 6.0   # 1-00 or 0-01 transition (3 bit cells)
MFM_LONG_US = 8.0     # 1-000 or 0-001 transition (4 bit cells)

# Timing tolerance (percentage of bit cell)
TIMING_TOLERANCE = 0.30  # 30% tolerance

# Sample rate defaults (Greaseweazle F7 uses 72MHz or 84MHz)
DEFAULT_SAMPLE_FREQ = 72_000_000  # 72 MHz

# Index pulse timing
INDEX_PULSE_MIN_SAMPLES = 1000  # Minimum samples between valid indices


@dataclass
class FluxData:
    """
    Container for raw flux timing data from a floppy disk track.

    Flux data represents magnetic transitions on the disk surface as
    timing values. Each value in flux_times represents the time (in
    sample counts) since the previous transition.

    Attributes:
        flux_times: List of timing values between flux transitions
        sample_freq: Sample frequency in Hz (typically 72MHz for Greaseweazle)
        index_positions: Sample positions of index pulses
        cylinder: Cylinder number this flux was captured from
        head: Head number this flux was captured from
        revolutions: Number of revolutions captured

    Example:
        # Create from captured data
        flux = FluxData(
            flux_times=[288, 432, 288, 576, ...],
            sample_freq=72_000_000,
            index_positions=[0, 14400000],
            cylinder=0,
            head=0
        )

        # Get timing in microseconds
        times_us = flux.get_times_microseconds()

        # Analyze quality
        quality = flux.calculate_quality_score()
    """

    flux_times: List[int] = field(default_factory=list)
    sample_freq: int = DEFAULT_SAMPLE_FREQ
    index_positions: List[int] = field(default_factory=list)
    cylinder: int = 0
    head: int = 0
    revolutions: float = 1.0

    @classmethod
    def from_greaseweazle_flux(cls, gw_flux: 'Flux', cylinder: int = 0,
                                head: int = 0) -> 'FluxData':
        """
        Create FluxData from a Greaseweazle Flux object.

        Args:
            gw_flux: Greaseweazle Flux object from read_track()
            cylinder: Cylinder number this flux was captured from
            head: Head number this flux was captured from

        Returns:
            FluxData instance containing the flux data
        """
        # Extract the timing data from Greaseweazle's format
        # gw_flux.list contains the raw timing values
        flux_times = list(gw_flux.list)

        # Get index positions
        index_positions = list(gw_flux.index_list) if gw_flux.index_list else []

        # Calculate revolutions from index positions
        revolutions = len(index_positions) - 1 if len(index_positions) > 1 else 1.0

        return cls(
            flux_times=flux_times,
            sample_freq=gw_flux.sample_freq,
            index_positions=index_positions,
            cylinder=cylinder,
            head=head,
            revolutions=revolutions
        )

    def to_greaseweazle_flux(self) -> 'Flux':
        """
        Convert to Greaseweazle Flux object for writing.

        Returns:
            Greaseweazle Flux object suitable for write_track()
        """
        if not GREASEWEAZLE_AVAILABLE:
            raise ImportError("greaseweazle package not installed")

        # Create Flux object with our data
        return Flux(
            index_list=self.index_positions,
            flux_list=[self.flux_times],
            sample_freq=self.sample_freq
        )

    @property
    def total_samples(self) -> int:
        """Get total number of samples in the flux capture."""
        return sum(self.flux_times)

    @property
    def duration_seconds(self) -> float:
        """Get duration of flux capture in seconds."""
        return self.total_samples / self.sample_freq

    @property
    def duration_milliseconds(self) -> float:
        """Get duration of flux capture in milliseconds."""
        return self.duration_seconds * 1000.0

    @property
    def transition_count(self) -> int:
        """Get number of flux transitions."""
        return len(self.flux_times)

    @property
    def index_count(self) -> int:
        """Get number of index pulses detected."""
        return len(self.index_positions)

    def get_times_microseconds(self) -> List[float]:
        """
        Convert flux times to microseconds.

        Returns:
            List of timing values in microseconds
        """
        factor = 1_000_000 / self.sample_freq
        return [t * factor for t in self.flux_times]

    def get_times_nanoseconds(self) -> List[float]:
        """
        Convert flux times to nanoseconds.

        Returns:
            List of timing values in nanoseconds
        """
        factor = 1_000_000_000 / self.sample_freq
        return [t * factor for t in self.flux_times]

    def get_revolution_data(self, revolution: int = 0) -> 'FluxData':
        """
        Extract flux data for a single revolution.

        Args:
            revolution: Revolution number (0-based)

        Returns:
            FluxData containing only the specified revolution

        Raises:
            ValueError: If revolution number is out of range
        """
        if len(self.index_positions) < 2:
            # No index information, return all data
            return FluxData(
                flux_times=self.flux_times.copy(),
                sample_freq=self.sample_freq,
                index_positions=[],
                cylinder=self.cylinder,
                head=self.head,
                revolutions=1.0
            )

        if revolution >= len(self.index_positions) - 1:
            raise ValueError(
                f"Revolution {revolution} out of range "
                f"(have {len(self.index_positions) - 1} revolutions)"
            )

        # Find start and end positions in flux_times
        start_pos = self.index_positions[revolution]
        end_pos = self.index_positions[revolution + 1]

        # Extract the flux times for this revolution
        cumulative = 0
        start_idx = 0
        end_idx = len(self.flux_times)

        for i, t in enumerate(self.flux_times):
            if cumulative < start_pos:
                start_idx = i
            cumulative += t
            if cumulative >= end_pos:
                end_idx = i + 1
                break

        return FluxData(
            flux_times=self.flux_times[start_idx:end_idx],
            sample_freq=self.sample_freq,
            index_positions=[0, end_pos - start_pos],
            cylinder=self.cylinder,
            head=self.head,
            revolutions=1.0
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
            if samples > INDEX_PULSE_MIN_SAMPLES:  # Filter out noise
                time_seconds = samples / self.sample_freq
                times.append(time_seconds)

        if not times:
            return None

        avg_time = statistics.mean(times)
        return 60.0 / avg_time

    def calculate_quality_score(self) -> float:
        """
        Calculate an overall quality score for the flux data.

        The score is based on:
        - Timing consistency (low jitter)
        - Proper MFM pulse widths
        - Signal-to-noise ratio estimation

        Returns:
            Quality score from 0.0 (poor) to 1.0 (excellent)
        """
        if not self.flux_times:
            return 0.0

        times_us = self.get_times_microseconds()

        # Calculate timing statistics
        scores = []

        # 1. Check for reasonable timing values (MFM range)
        in_range = sum(1 for t in times_us
                       if MFM_SHORT_US * 0.7 <= t <= MFM_LONG_US * 1.3)
        range_score = in_range / len(times_us) if times_us else 0
        scores.append(range_score)

        # 2. Calculate jitter score (lower is better)
        if len(times_us) > 10:
            # Group by expected MFM values and measure variance
            short = [t for t in times_us if 3.0 <= t < 5.0]
            medium = [t for t in times_us if 5.0 <= t < 7.0]
            long = [t for t in times_us if 7.0 <= t < 9.0]

            jitter_scores = []
            for group, expected in [(short, MFM_SHORT_US),
                                     (medium, MFM_MEDIUM_US),
                                     (long, MFM_LONG_US)]:
                if len(group) > 5:
                    std_dev = statistics.stdev(group)
                    # Lower standard deviation is better
                    # Score of 1.0 if std_dev < 0.2us, 0.0 if > 1.0us
                    jitter_score = max(0, 1 - (std_dev - 0.2) / 0.8)
                    jitter_scores.append(jitter_score)

            if jitter_scores:
                scores.append(statistics.mean(jitter_scores))

        # 3. Check for index pulse (indicates disk is rotating properly)
        if self.index_count >= 1:
            scores.append(1.0)
        else:
            scores.append(0.5)

        return statistics.mean(scores) if scores else 0.0

    def get_pulse_histogram(self, bins: int = 50,
                             min_us: float = 2.0,
                             max_us: float = 10.0) -> Tuple[List[float], List[int]]:
        """
        Generate a histogram of pulse widths.

        Args:
            bins: Number of histogram bins
            min_us: Minimum pulse width in microseconds
            max_us: Maximum pulse width in microseconds

        Returns:
            Tuple of (bin_centers, counts)
        """
        times_us = self.get_times_microseconds()

        # Filter to range
        filtered = [t for t in times_us if min_us <= t <= max_us]

        if not filtered:
            return [], []

        # Create histogram
        bin_width = (max_us - min_us) / bins
        counts = [0] * bins
        bin_centers = [min_us + (i + 0.5) * bin_width for i in range(bins)]

        for t in filtered:
            bin_idx = int((t - min_us) / bin_width)
            if 0 <= bin_idx < bins:
                counts[bin_idx] += 1

        return bin_centers, counts

    def detect_mfm_peaks(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Detect the three MFM peak positions from the flux histogram.

        For properly encoded MFM data, there should be peaks at
        approximately 4us, 6us, and 8us (for HD).

        Returns:
            Tuple of (short_peak, medium_peak, long_peak) in microseconds,
            or None for any peak not detected
        """
        bin_centers, counts = self.get_pulse_histogram(bins=100, min_us=2.0, max_us=10.0)

        if not counts:
            return None, None, None

        # Find local maxima in expected regions
        def find_peak(center: float, width: float) -> Optional[float]:
            """Find highest peak within width of center."""
            best_count = 0
            best_pos = None
            for i, (pos, count) in enumerate(zip(bin_centers, counts)):
                if center - width <= pos <= center + width:
                    if count > best_count:
                        best_count = count
                        best_pos = pos
            return best_pos if best_count > max(counts) * 0.1 else None

        short_peak = find_peak(MFM_SHORT_US, 1.0)
        medium_peak = find_peak(MFM_MEDIUM_US, 1.0)
        long_peak = find_peak(MFM_LONG_US, 1.0)

        return short_peak, medium_peak, long_peak

    def estimate_bit_cell_width(self) -> Optional[float]:
        """
        Estimate the bit cell width from detected MFM peaks.

        Returns:
            Estimated bit cell width in microseconds, or None if detection fails
        """
        short, medium, long = self.detect_mfm_peaks()

        estimates = []
        if short is not None:
            estimates.append(short / 2.0)  # Short = 2 bit cells
        if medium is not None:
            estimates.append(medium / 3.0)  # Medium = 3 bit cells
        if long is not None:
            estimates.append(long / 4.0)  # Long = 4 bit cells

        if estimates:
            return statistics.mean(estimates)
        return None

    def __len__(self) -> int:
        """Return number of flux transitions."""
        return len(self.flux_times)

    def __iter__(self) -> Iterator[int]:
        """Iterate over flux times."""
        return iter(self.flux_times)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"FluxData(C{self.cylinder}H{self.head}, "
            f"{self.transition_count} transitions, "
            f"{self.duration_milliseconds:.1f}ms, "
            f"{self.index_count} indices)"
        )


# =============================================================================
# Flux I/O Wrapper Classes
# =============================================================================


class FluxReader:
    """
    High-level flux reading interface.

    Provides an object-oriented wrapper around the flux reading functions.
    Maintains a reference to the device for convenient repeated reads.

    Example:
        reader = FluxReader(device)
        flux = reader.read_track(0, 0, revolutions=2.0)
        quality = reader.analyze_track_quality(0, 0)
    """

    def __init__(self, device: 'GreaseweazleDevice'):
        """
        Initialize FluxReader with a device.

        Args:
            device: Connected GreaseweazleDevice instance
        """
        self._device = device

    def read_track(self, cylinder: int, head: int,
                   revolutions: float = 1.2) -> FluxData:
        """
        Read raw flux data from a track.

        Args:
            cylinder: Cylinder number to read
            head: Head number (0 or 1)
            revolutions: Number of revolutions to capture

        Returns:
            FluxData containing captured flux timing data
        """
        return read_track_flux(self._device, cylinder, head, revolutions)

    def analyze_track_quality(self, cylinder: int, head: int,
                              revolutions: float = 1.5) -> dict:
        """
        Read and analyze flux quality for a track.

        Args:
            cylinder: Cylinder number to read
            head: Head number (0 or 1)
            revolutions: Number of revolutions to capture

        Returns:
            Quality analysis dictionary
        """
        flux = self.read_track(cylinder, head, revolutions)
        return analyze_flux_quality(flux)


class FluxWriter:
    """
    High-level flux writing interface.

    Provides an object-oriented wrapper around the flux writing functions.
    Maintains a reference to the device for convenient repeated writes.

    Example:
        writer = FluxWriter(device)
        writer.write_track(0, 0, flux_data)
        writer.erase_track(0, 1)
    """

    def __init__(self, device: 'GreaseweazleDevice'):
        """
        Initialize FluxWriter with a device.

        Args:
            device: Connected GreaseweazleDevice instance
        """
        self._device = device

    def write_track(self, cylinder: int, head: int, flux_data: FluxData,
                    erase_first: bool = True) -> None:
        """
        Write raw flux data to a track.

        Args:
            cylinder: Cylinder number to write
            head: Head number (0 or 1)
            flux_data: FluxData to write
            erase_first: Whether to erase before writing
        """
        write_track_flux(self._device, cylinder, head, flux_data, erase_first)

    def erase_track(self, cylinder: int, head: int) -> None:
        """
        Erase a track (DC erase).

        Args:
            cylinder: Cylinder number to erase
            head: Head number (0 or 1)
        """
        erase_track_flux(self._device, cylinder, head)

    def write_dc_erase(self, cylinder: int, head: int) -> None:
        """
        Alias for erase_track for surface treatment compatibility.

        Args:
            cylinder: Cylinder number to erase
            head: Head number (0 or 1)
        """
        self.erase_track(cylinder, head)


# =============================================================================
# Flux I/O Functions
# =============================================================================

def read_track_flux(device: 'GreaseweazleDevice', cylinder: int, head: int,
                    revolutions: float = 1.2) -> FluxData:
    """
    Read raw flux data from a track.

    High-level function to capture flux from a floppy disk track.
    The device must be connected with drive selected and motor running.

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder number to read (0-79 for 3.5" HD)
        head: Head number (0 or 1)
        revolutions: Number of revolutions to capture (default 1.2)

    Returns:
        FluxData containing the captured flux timing data

    Raises:
        GreaseweazleError: If device not ready
        FluxError: If read operation fails

    Example:
        with GreaseweazleDevice() as device:
            device.select_drive(0)
            device.motor_on()
            flux = read_track_flux(device, 0, 0, revolutions=2.0)
            print(f"Captured {len(flux)} transitions")
    """
    logger.debug("Reading flux from C%d H%d (%.1f revolutions)",
                 cylinder, head, revolutions)

    flux_data = device.read_track(cylinder, head, revolutions)

    logger.debug("Read %d flux transitions, quality=%.2f",
                 len(flux_data), flux_data.calculate_quality_score())

    return flux_data


def write_track_flux(device: 'GreaseweazleDevice', cylinder: int, head: int,
                     flux_data: FluxData, erase_first: bool = True) -> None:
    """
    Write raw flux data to a track.

    High-level function to write pre-encoded flux data to a floppy disk track.
    Optionally erases the track first for cleaner writes.

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder number to write (0-79 for 3.5" HD)
        head: Head number (0 or 1)
        flux_data: FluxData to write
        erase_first: Whether to erase track before writing (default True)

    Raises:
        GreaseweazleError: If device not ready
        FluxError: If write operation fails

    Example:
        with GreaseweazleDevice() as device:
            device.select_drive(0)
            device.motor_on()
            # flux_data from encode_sectors_to_flux()
            write_track_flux(device, 0, 0, flux_data)
    """
    logger.info("Writing flux to C%d H%d (%d transitions)",
                cylinder, head, len(flux_data))

    if erase_first:
        logger.debug("Erasing track before write")
        device.erase_track(cylinder, head)

    device.write_track(cylinder, head, flux_data)

    logger.debug("Write complete")


def erase_track_flux(device: 'GreaseweazleDevice', cylinder: int, head: int) -> None:
    """
    Erase a track (DC erase).

    Performs a bulk erase of the specified track. This writes a constant
    magnetic field across the entire track, effectively erasing all data.

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder number to erase (0-79 for 3.5" HD)
        head: Head number (0 or 1)

    Raises:
        GreaseweazleError: If device not ready
        FluxError: If erase operation fails
    """
    logger.info("Erasing track C%d H%d", cylinder, head)
    device.erase_track(cylinder, head)
    logger.debug("Erase complete")


# =============================================================================
# Flux Analysis Functions
# =============================================================================

def analyze_flux_quality(flux_data: FluxData) -> dict:
    """
    Perform comprehensive flux quality analysis.

    Analyzes the flux data for various quality metrics including
    timing jitter, peak detection, and signal characteristics.

    Args:
        flux_data: FluxData to analyze

    Returns:
        Dictionary containing:
            - quality_score: Overall quality (0.0-1.0)
            - rpm: Detected RPM (or None)
            - bit_cell_us: Estimated bit cell width
            - peak_positions: Detected MFM peak positions
            - transition_count: Number of flux transitions
            - jitter_metrics: Timing jitter statistics
    """
    logger.debug("Analyzing flux quality for C%d H%d",
                 flux_data.cylinder, flux_data.head)

    # Basic metrics
    quality_score = flux_data.calculate_quality_score()
    rpm = flux_data.calculate_rpm()
    bit_cell = flux_data.estimate_bit_cell_width()
    short_peak, medium_peak, long_peak = flux_data.detect_mfm_peaks()

    # Calculate jitter metrics
    times_us = flux_data.get_times_microseconds()
    jitter_metrics = {}

    if times_us:
        # Group by MFM pulse type
        groups = {
            'short': [t for t in times_us if 3.0 <= t < 5.0],
            'medium': [t for t in times_us if 5.0 <= t < 7.0],
            'long': [t for t in times_us if 7.0 <= t < 9.0],
        }

        for name, group in groups.items():
            if len(group) > 5:
                jitter_metrics[name] = {
                    'count': len(group),
                    'mean': statistics.mean(group),
                    'std_dev': statistics.stdev(group),
                    'min': min(group),
                    'max': max(group),
                }

    result = {
        'quality_score': quality_score,
        'rpm': rpm,
        'bit_cell_us': bit_cell,
        'peak_positions': {
            'short': short_peak,
            'medium': medium_peak,
            'long': long_peak,
        },
        'transition_count': flux_data.transition_count,
        'duration_ms': flux_data.duration_milliseconds,
        'index_count': flux_data.index_count,
        'jitter_metrics': jitter_metrics,
    }

    logger.debug("Flux analysis complete: quality=%.2f, rpm=%s",
                 quality_score, rpm)

    return result


def compare_flux_captures(flux1: FluxData, flux2: FluxData,
                           tolerance_us: float = 0.5) -> dict:
    """
    Compare two flux captures of the same track.

    Useful for verifying write operations or detecting disk degradation
    over time.

    Args:
        flux1: First flux capture
        flux2: Second flux capture
        tolerance_us: Timing tolerance in microseconds

    Returns:
        Dictionary containing comparison metrics:
            - match_ratio: Fraction of matching transitions
            - length_diff: Difference in transition counts
            - timing_diff_mean: Average timing difference
            - timing_diff_max: Maximum timing difference
    """
    times1 = flux1.get_times_microseconds()
    times2 = flux2.get_times_microseconds()

    # Compare lengths
    length_diff = abs(len(times1) - len(times2))
    min_len = min(len(times1), len(times2))

    if min_len == 0:
        return {
            'match_ratio': 0.0,
            'length_diff': length_diff,
            'timing_diff_mean': float('inf'),
            'timing_diff_max': float('inf'),
        }

    # Compare timing values
    differences = []
    matches = 0

    for t1, t2 in zip(times1[:min_len], times2[:min_len]):
        diff = abs(t1 - t2)
        differences.append(diff)
        if diff <= tolerance_us:
            matches += 1

    return {
        'match_ratio': matches / min_len,
        'length_diff': length_diff,
        'timing_diff_mean': statistics.mean(differences),
        'timing_diff_max': max(differences),
        'timing_diff_std': statistics.stdev(differences) if len(differences) > 1 else 0,
    }


def merge_flux_captures(captures: List[FluxData]) -> FluxData:
    """
    Merge multiple flux captures using statistical averaging.

    This is useful for recovering marginal data by reading multiple
    times and averaging the timing values.

    Args:
        captures: List of FluxData from multiple reads of same track

    Returns:
        FluxData with statistically merged timing values

    Note:
        All captures must be from the same track (same cylinder/head).
    """
    if not captures:
        raise ValueError("No captures to merge")

    if len(captures) == 1:
        return captures[0]

    # Use the first capture as reference
    ref = captures[0]
    cylinder = ref.cylinder
    head = ref.head
    sample_freq = ref.sample_freq

    # Convert all to microseconds for comparison
    all_times = [c.get_times_microseconds() for c in captures]

    # Find minimum length (align by length)
    min_len = min(len(t) for t in all_times)

    # Average the timing values
    merged_times_us = []
    for i in range(min_len):
        values = [t[i] for t in all_times]
        # Use median to reduce outlier impact
        merged_times_us.append(statistics.median(values))

    # Convert back to sample counts
    factor = sample_freq / 1_000_000
    merged_times = [int(t * factor) for t in merged_times_us]

    # Use index positions from first capture
    return FluxData(
        flux_times=merged_times,
        sample_freq=sample_freq,
        index_positions=ref.index_positions.copy() if ref.index_positions else [],
        cylinder=cylinder,
        head=head,
        revolutions=ref.revolutions
    )
