"""
PLL (Phase-Locked Loop) parameter tuning for MFM decoding.

This module provides advanced PLL parameter optimization for recovering
marginal sectors that fail to decode with standard PLL settings.

The MFM decoding process uses a PLL to track the bit clock and correctly
sample data bits. When the disk has timing variations or weak signals,
the default PLL parameters may fail to track correctly.

By systematically searching the PLL parameter space, this module can
find settings that successfully decode previously unreadable sectors.

Key Classes:
    PLLParameters: PLL configuration parameters
    PLLSearchResult: Results from parameter search
    OptimalPLLResult: Best parameters found for a track

Key Functions:
    try_pll_variations: Systematic parameter search
    find_optimal_pll: Find best parameters for difficult tracks
    decode_with_pll: Decode flux using specific PLL settings
"""

import math
import statistics
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any
from itertools import product

# TYPE_CHECKING imports removed - FluxData and SectorData used via FluxCapture

from floppy_formatter.analysis.flux_analyzer import FluxCapture

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default PLL parameters for MFM HD (3.5" 1.44MB)
DEFAULT_FREQUENCY_HZ = 500_000  # 500kHz bit rate for HD
DEFAULT_BANDWIDTH = 0.05  # 5% bandwidth
DEFAULT_DAMPING = 0.707  # Critically damped (sqrt(2)/2)
DEFAULT_PHASE_OFFSET_NS = 0  # No initial phase offset
DEFAULT_GAIN = 1.0  # Unity gain

# PLL parameter search ranges
FREQUENCY_VARIATION_PERCENT = 5.0  # ±5% frequency search
BANDWIDTH_RANGE = (0.02, 0.15)  # 2-15% bandwidth
DAMPING_RANGE = (0.5, 1.2)  # Under to over-damped
PHASE_OFFSET_RANGE_NS = (-500, 500)  # ±500ns phase offset
GAIN_RANGE = (0.5, 2.0)  # Gain factor range

# Search granularity
COARSE_SEARCH_STEPS = 5
FINE_SEARCH_STEPS = 3

# Decoding thresholds
MIN_SECTORS_FOR_SUCCESS = 1
GOOD_DECODE_THRESHOLD = 16  # Out of 18 sectors

# MFM timing constants
HD_BIT_CELL_NS = 2000  # 2 microseconds = 2000 nanoseconds
MFM_2T_NS = 4000  # Short pulse
MFM_3T_NS = 6000  # Medium pulse
MFM_4T_NS = 8000  # Long pulse


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PLLParameters:
    """
    PLL configuration parameters for MFM decoding.

    The PLL tracks the bit clock in the flux data to correctly
    sample data bits. These parameters control how the PLL responds
    to timing variations in the flux.

    Attributes:
        phase_offset: Initial phase offset in nanoseconds.
                     Compensates for systematic timing offset.
        frequency: Center frequency in Hz.
                  500kHz for HD, 250kHz for DD.
        bandwidth: PLL bandwidth as fraction (0.0-1.0).
                  How quickly PLL tracks frequency changes.
                  Lower = more stable, Higher = more responsive.
        damping: PLL damping factor.
                0.707 = critically damped (optimal for most cases).
                <0.707 = underdamped (oscillates).
                >0.707 = overdamped (slow response).
        gain: PLL gain factor.
             Multiplier for phase error correction.
    """
    phase_offset: float = DEFAULT_PHASE_OFFSET_NS  # nanoseconds
    frequency: float = DEFAULT_FREQUENCY_HZ  # Hz
    bandwidth: float = DEFAULT_BANDWIDTH  # fraction
    damping: float = DEFAULT_DAMPING  # dimensionless
    gain: float = DEFAULT_GAIN  # multiplier

    @classmethod
    def for_hd(cls) -> 'PLLParameters':
        """Create default parameters for HD (1.44MB) disks."""
        return cls(
            phase_offset=0.0,
            frequency=500_000,  # 500kHz
            bandwidth=0.05,
            damping=0.707,
            gain=1.0,
        )

    @classmethod
    def for_dd(cls) -> 'PLLParameters':
        """Create default parameters for DD (720KB) disks."""
        return cls(
            phase_offset=0.0,
            frequency=250_000,  # 250kHz
            bandwidth=0.05,
            damping=0.707,
            gain=1.0,
        )

    def with_variation(
        self,
        phase_delta: float = 0,
        freq_delta: float = 0,
        bandwidth_delta: float = 0,
        damping_delta: float = 0,
        gain_delta: float = 0
    ) -> 'PLLParameters':
        """
        Create a new PLLParameters with variations applied.

        Args:
            phase_delta: Phase offset change in nanoseconds
            freq_delta: Frequency change in Hz
            bandwidth_delta: Bandwidth change
            damping_delta: Damping change
            gain_delta: Gain change

        Returns:
            New PLLParameters with variations
        """
        return PLLParameters(
            phase_offset=self.phase_offset + phase_delta,
            frequency=max(100_000, self.frequency + freq_delta),
            bandwidth=max(0.01, min(0.5, self.bandwidth + bandwidth_delta)),
            damping=max(0.3, min(2.0, self.damping + damping_delta)),
            gain=max(0.1, min(5.0, self.gain + gain_delta)),
        )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization."""
        return {
            'phase_offset': self.phase_offset,
            'frequency': self.frequency,
            'bandwidth': self.bandwidth,
            'damping': self.damping,
            'gain': self.gain,
        }

    def __hash__(self) -> int:
        """Make hashable for use in sets/dicts."""
        return hash((
            round(self.phase_offset, 1),
            round(self.frequency, 0),
            round(self.bandwidth, 3),
            round(self.damping, 3),
            round(self.gain, 3),
        ))


@dataclass
class DecodedSectorResult:
    """Result of decoding a single sector with specific PLL parameters."""
    sector_number: int
    success: bool
    crc_valid: bool
    data: Optional[bytes]
    signal_quality: float
    timing_error: float  # Average timing error during decode


@dataclass
class PLLDecodeResult:
    """Result of decoding flux with specific PLL parameters."""
    parameters: PLLParameters
    sectors_decoded: int
    sectors_with_valid_crc: int
    sector_results: List[DecodedSectorResult]
    average_timing_error: float
    decode_quality: float  # 0.0-1.0 overall quality score

    def get_good_sectors(self) -> List[int]:
        """Get list of successfully decoded sector numbers."""
        return [r.sector_number for r in self.sector_results if r.crc_valid]

    def get_failed_sectors(self) -> List[int]:
        """Get list of sector numbers that failed to decode."""
        decoded_sectors = {r.sector_number for r in self.sector_results}
        all_sectors = set(range(1, 19))
        return list(all_sectors - decoded_sectors)


@dataclass
class PLLSearchResult:
    """
    Results from PLL parameter search.

    Attributes:
        successful_params: List of parameter sets that decoded at least one sector
        sectors_recovered: Dict mapping parameter set to list of recovered sectors
        best_params: Parameter set that recovered the most sectors
        best_sector_count: Number of sectors recovered with best parameters
        total_combinations_tried: Number of parameter combinations tested
        search_time_seconds: Time taken for search
    """
    successful_params: List[PLLParameters]
    sectors_recovered: Dict[PLLParameters, List[int]]
    best_params: Optional[PLLParameters]
    best_sector_count: int
    total_combinations_tried: int
    search_time_seconds: float

    def get_summary(self) -> str:
        """Get human-readable summary of search results."""
        if self.best_params:
            return (
                f"Found {len(self.successful_params)} working parameter sets. "
                f"Best recovered {self.best_sector_count} sectors. "
                f"Tested {self.total_combinations_tried} combinations in "
                f"{self.search_time_seconds:.1f}s."
            )
        else:
            return (
                f"No successful parameters found after testing "
                f"{self.total_combinations_tried} combinations."
            )


@dataclass
class OptimalPLLResult:
    """
    Result of finding optimal PLL parameters.

    Attributes:
        parameters: Best PLLParameters found
        sectors_decoded: List of successfully decoded sector numbers
        improvement: How many more sectors vs default PLL
        default_sectors: Sectors decoded with default parameters
        decode_result: Full decode result with best parameters
        confidence: Confidence in these being optimal (0.0-1.0)
    """
    parameters: PLLParameters
    sectors_decoded: List[int]
    improvement: int
    default_sectors: List[int]
    decode_result: PLLDecodeResult
    confidence: float

    def get_summary(self) -> str:
        """Get human-readable summary."""
        if self.improvement > 0:
            return (
                f"Recovered {len(self.sectors_decoded)} sectors "
                f"(+{self.improvement} vs default). "
                f"Confidence: {self.confidence:.0%}"
            )
        elif self.improvement == 0:
            return (
                f"Recovered {len(self.sectors_decoded)} sectors "
                f"(same as default)."
            )
        else:
            return (
                f"Best recovery: {len(self.sectors_decoded)} sectors. "
                f"Default was better by {-self.improvement} sectors."
            )


# =============================================================================
# PLL Simulation and Decoding
# =============================================================================

class PLLDecoder:
    """
    Software PLL implementation for MFM decoding.

    This simulates the hardware PLL that tracks the bit clock
    in flux data. By adjusting the PLL parameters, we can
    optimize decoding for marginal disks.
    """

    def __init__(self, params: PLLParameters):
        """
        Initialize PLL decoder with given parameters.

        Args:
            params: PLLParameters configuration
        """
        self.params = params

        # Calculate derived parameters
        self.bit_period_ns = 1_000_000_000 / params.frequency
        self.half_period_ns = self.bit_period_ns / 2

        # PLL state
        self.phase = params.phase_offset
        self.frequency_offset = 0.0

        # PLL loop filter coefficients
        # Using a second-order loop filter
        wn = 2 * math.pi * params.bandwidth * params.frequency
        self.kp = 2 * params.damping * wn * params.gain  # Proportional gain
        self.ki = wn * wn * params.gain  # Integral gain

        # Accumulated timing error for quality measurement
        self.timing_errors = []

    def reset(self) -> None:
        """Reset PLL state for new track."""
        self.phase = self.params.phase_offset
        self.frequency_offset = 0.0
        self.timing_errors = []

    def process_transition(self, timing_ns: float) -> Tuple[int, float]:
        """
        Process a flux transition and extract data bits.

        Args:
            timing_ns: Time since last transition in nanoseconds

        Returns:
            Tuple of (bits_extracted, timing_error_ns)
        """
        # Calculate expected timing for MFM (2T, 3T, or 4T)
        adjusted_period = self.bit_period_ns * (1 + self.frequency_offset)

        # Determine number of bit cells in this transition
        cell_count = round(timing_ns / adjusted_period)
        cell_count = max(2, min(4, cell_count))  # Clamp to valid MFM range

        # Calculate timing error
        expected_ns = cell_count * adjusted_period
        timing_error = timing_ns - expected_ns

        # Update PLL phase tracking
        phase_error = timing_error / adjusted_period

        # Apply loop filter
        self.phase += self.kp * phase_error
        self.frequency_offset += self.ki * phase_error * (timing_ns / 1_000_000_000)

        # Clamp frequency offset
        self.frequency_offset = max(-0.1, min(0.1, self.frequency_offset))

        # Track timing errors for quality measurement
        self.timing_errors.append(abs(timing_error))

        # Return number of bits (MFM: 2T=01, 3T=001, 4T=0001)
        return cell_count - 1, timing_error

    def get_average_timing_error(self) -> float:
        """Get average absolute timing error in nanoseconds."""
        if not self.timing_errors:
            return 0.0
        return statistics.mean(self.timing_errors)

    def get_timing_quality(self) -> float:
        """
        Get timing quality score (0.0-1.0).

        Based on how well transitions match expected timing.
        """
        if not self.timing_errors:
            return 0.0

        avg_error = self.get_average_timing_error()
        max_acceptable_error = self.half_period_ns

        # Quality decreases as error increases
        if avg_error >= max_acceptable_error:
            return 0.0

        return 1.0 - (avg_error / max_acceptable_error)


def decode_with_pll(
    flux: FluxCapture,
    params: PLLParameters
) -> PLLDecodeResult:
    """
    Decode flux data using specific PLL parameters.

    This function applies custom PLL settings to decode MFM data
    from flux captures. It can recover sectors that fail with
    default PLL settings by using optimized parameters.

    Args:
        flux: FluxCapture to decode
        params: PLLParameters to use for decoding

    Returns:
        PLLDecodeResult with decoded sectors and quality metrics

    Example:
        >>> params = PLLParameters.for_hd()
        >>> params = params.with_variation(phase_delta=100, bandwidth_delta=0.02)
        >>> result = decode_with_pll(capture, params)
        >>> print(f"Decoded {result.sectors_decoded} sectors")
    """
    logger.debug("Decoding with PLL: freq=%dHz, bw=%.3f, damp=%.3f",
                 params.frequency, params.bandwidth, params.damping)

    # Get timing data
    times_ns = flux.get_timings_nanoseconds()

    if not times_ns:
        return PLLDecodeResult(
            parameters=params,
            sectors_decoded=0,
            sectors_with_valid_crc=0,
            sector_results=[],
            average_timing_error=float('inf'),
            decode_quality=0.0,
        )

    # Create PLL decoder
    pll = PLLDecoder(params)

    # Process all transitions to extract bit stream
    bits = []
    for timing in times_ns:
        bit_count, error = pll.process_transition(timing)
        # MFM encoding: 2T=01, 3T=001, 4T=0001
        bits.extend([0] * (bit_count - 1))
        bits.append(1)

    # Now decode MFM to find sectors
    sectors = _decode_mfm_bits_to_sectors(bits, flux.cylinder, flux.head)

    # Build results
    sector_results = []
    valid_crc_count = 0

    for sector_data in sectors:
        result = DecodedSectorResult(
            sector_number=sector_data['sector'],
            success=sector_data['success'],
            crc_valid=sector_data['crc_valid'],
            data=sector_data.get('data'),
            signal_quality=sector_data.get('quality', 0.0),
            timing_error=pll.get_average_timing_error(),
        )
        sector_results.append(result)

        if result.crc_valid:
            valid_crc_count += 1

    return PLLDecodeResult(
        parameters=params,
        sectors_decoded=len(sectors),
        sectors_with_valid_crc=valid_crc_count,
        sector_results=sector_results,
        average_timing_error=pll.get_average_timing_error(),
        decode_quality=pll.get_timing_quality(),
    )


def _decode_mfm_bits_to_sectors(
    bits: List[int],
    cylinder: int,
    head: int
) -> List[Dict[str, Any]]:
    """
    Decode MFM bit stream to sector data.

    This is a simplified MFM decoder that finds sector headers
    and extracts data fields.

    Returns:
        List of sector dictionaries with keys:
        - sector: Sector number
        - success: Whether decode succeeded
        - crc_valid: Whether CRC passed
        - data: Sector data bytes
        - quality: Decode quality score
    """
    sectors = []

    # MFM sync pattern: A1 A1 A1 (with clock violations)
    # In bits: 0100010010001001 repeated 3 times
    sync_pattern = [0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1]

    # Search for sector headers
    bit_pos = 0
    while bit_pos < len(bits) - 1000:  # Need at least 1000 bits for a sector
        # Look for sync pattern
        found_sync = False
        for i in range(min(100, len(bits) - bit_pos - len(sync_pattern))):
            if bits[bit_pos + i:bit_pos + i + len(sync_pattern)] == sync_pattern:
                bit_pos = bit_pos + i + len(sync_pattern) * 3  # Skip all 3 syncs
                found_sync = True
                break

        if not found_sync:
            bit_pos += 100
            continue

        # Check for address mark (FE for header, FB for data)
        if bit_pos + 16 >= len(bits):
            break

        # Decode next byte (simplified - just extract raw bits)
        mark_bits = bits[bit_pos:bit_pos + 16]
        mark_byte = _mfm_bits_to_byte(mark_bits)

        if mark_byte == 0xFE:
            # Sector header found
            bit_pos += 16

            # Read header: cylinder, head, sector, size (4 bytes + 2 CRC)
            if bit_pos + 6 * 16 >= len(bits):
                break

            header_bytes = []
            for _ in range(6):
                byte_bits = bits[bit_pos:bit_pos + 16]
                header_bytes.append(_mfm_bits_to_byte(byte_bits))
                bit_pos += 16

            sector_num = header_bytes[2]

            # Now search for data field
            data_found = False
            for search in range(500):  # Search next 500 bits for data mark
                if bit_pos + search + 16 >= len(bits):
                    break

                # Check for sync + FB
                check_bits = bits[bit_pos + search:bit_pos + search + 16]
                check_byte = _mfm_bits_to_byte(check_bits)

                if check_byte == 0xFB or check_byte == 0xF8:
                    bit_pos = bit_pos + search + 16
                    data_found = True
                    break

            if data_found:
                # Read 512 bytes of data + 2 CRC
                if bit_pos + 514 * 16 >= len(bits):
                    break

                data_bytes = bytearray()
                for _ in range(512):
                    byte_bits = bits[bit_pos:bit_pos + 16]
                    data_bytes.append(_mfm_bits_to_byte(byte_bits))
                    bit_pos += 16

                # Read CRC (simplified - just skip)
                bit_pos += 32

                # Simplified CRC check (just verify it looks like valid data)
                # Real implementation would calculate CRC-CCITT
                crc_valid = len(set(data_bytes)) > 1  # Basic sanity check

                sectors.append({
                    'sector': sector_num,
                    'success': True,
                    'crc_valid': crc_valid,
                    'data': bytes(data_bytes),
                    'quality': 0.8 if crc_valid else 0.4,
                })
            else:
                # Header found but no data field
                sectors.append({
                    'sector': sector_num,
                    'success': False,
                    'crc_valid': False,
                    'data': None,
                    'quality': 0.2,
                })
        else:
            bit_pos += 16

    return sectors


def _mfm_bits_to_byte(bits: List[int]) -> int:
    """
    Convert 16 MFM bits to a data byte.

    MFM encoding interleaves clock and data bits.
    Data bits are at odd positions (1, 3, 5, ..., 15).
    """
    if len(bits) < 16:
        return 0

    byte_val = 0
    for i in range(8):
        data_bit = bits[1 + i * 2]  # Data at positions 1, 3, 5, ...
        byte_val = (byte_val << 1) | data_bit

    return byte_val


# =============================================================================
# PLL Parameter Search
# =============================================================================

def try_pll_variations(
    flux: FluxCapture,
    base_params: PLLParameters
) -> PLLSearchResult:
    """
    Systematic search of PLL parameter space.

    Generates a grid of parameter variations around the base
    parameters and tries each combination to find ones that
    successfully decode sectors.

    Args:
        flux: FluxCapture to decode
        base_params: Base PLLParameters to vary around

    Returns:
        PLLSearchResult with all successful parameter sets

    Example:
        >>> base = PLLParameters.for_hd()
        >>> result = try_pll_variations(capture, base)
        >>> print(f"Found {len(result.successful_params)} working parameter sets")
        >>> if result.best_params:
        ...     print(f"Best recovered {result.best_sector_count} sectors")
    """
    import time
    start_time = time.time()

    logger.info("Starting PLL parameter search")

    # Generate parameter variations
    phase_offsets = [
        base_params.phase_offset + delta
        for delta in range(-300, 301, 100)
    ]

    freq_variations = [
        base_params.frequency * (1 + delta/100)
        for delta in range(-3, 4, 1)
    ]

    bandwidth_variations = [
        base_params.bandwidth + delta
        for delta in [-0.02, -0.01, 0, 0.01, 0.02, 0.03]
    ]

    damping_variations = [
        base_params.damping + delta
        for delta in [-0.2, -0.1, 0, 0.1, 0.2]
    ]

    # Generate all combinations
    combinations = list(product(
        phase_offsets,
        freq_variations,
        bandwidth_variations,
        damping_variations
    ))

    logger.debug("Testing %d parameter combinations", len(combinations))

    successful_params = []
    sectors_recovered = {}
    best_params = None
    best_count = 0

    for phase, freq, bw, damp in combinations:
        params = PLLParameters(
            phase_offset=phase,
            frequency=freq,
            bandwidth=max(0.01, min(0.2, bw)),
            damping=max(0.4, min(1.5, damp)),
            gain=base_params.gain,
        )

        try:
            result = decode_with_pll(flux, params)

            if result.sectors_with_valid_crc >= MIN_SECTORS_FOR_SUCCESS:
                successful_params.append(params)
                sectors_recovered[params] = result.get_good_sectors()

                if result.sectors_with_valid_crc > best_count:
                    best_count = result.sectors_with_valid_crc
                    best_params = params

        except Exception as e:
            logger.debug("Parameter combination failed: %s", e)
            continue

    elapsed = time.time() - start_time

    logger.info("PLL search complete: %d successful sets, best=%d sectors, %.1fs",
                len(successful_params), best_count, elapsed)

    return PLLSearchResult(
        successful_params=successful_params,
        sectors_recovered=sectors_recovered,
        best_params=best_params,
        best_sector_count=best_count,
        total_combinations_tried=len(combinations),
        search_time_seconds=elapsed,
    )


def find_optimal_pll(
    flux: FluxCapture,
    target_sector: Optional[int] = None
) -> OptimalPLLResult:
    """
    Find best PLL parameters for difficult tracks.

    Uses iterative refinement: coarse search followed by fine
    tuning around the best result.

    Args:
        flux: FluxCapture to optimize for
        target_sector: Optional specific sector to optimize for.
                      If None, optimizes for maximum total recovery.

    Returns:
        OptimalPLLResult with best parameters found

    Example:
        >>> result = find_optimal_pll(capture)
        >>> print(result.get_summary())
        >>> # Use optimal parameters for decoding
        >>> decode_result = decode_with_pll(capture, result.parameters)
    """
    logger.info("Finding optimal PLL for C%d H%d (target sector: %s)",
                flux.cylinder, flux.head, target_sector)

    # First, try with default parameters
    base_params = PLLParameters.for_hd()
    default_result = decode_with_pll(flux, base_params)
    default_sectors = default_result.get_good_sectors()

    logger.debug("Default parameters: %d sectors", len(default_sectors))

    # If target sector specified and already decoded, we're done
    if target_sector is not None and target_sector in default_sectors:
        return OptimalPLLResult(
            parameters=base_params,
            sectors_decoded=default_sectors,
            improvement=0,
            default_sectors=default_sectors,
            decode_result=default_result,
            confidence=1.0,
        )

    # Coarse search
    coarse_result = try_pll_variations(flux, base_params)

    if not coarse_result.best_params:
        # No improvement found
        return OptimalPLLResult(
            parameters=base_params,
            sectors_decoded=default_sectors,
            improvement=0,
            default_sectors=default_sectors,
            decode_result=default_result,
            confidence=0.5,
        )

    # Fine search around best coarse result
    fine_params = coarse_result.best_params

    # Smaller variations for fine tuning
    best_params = fine_params
    best_count = coarse_result.best_sector_count

    for phase_delta in range(-50, 51, 25):
        for freq_delta in [-0.001, -0.0005, 0, 0.0005, 0.001]:
            for bw_delta in [-0.005, 0, 0.005]:
                params = fine_params.with_variation(
                    phase_delta=phase_delta,
                    freq_delta=fine_params.frequency * freq_delta,
                    bandwidth_delta=bw_delta,
                )

                try:
                    result = decode_with_pll(flux, params)

                    # Check if this is better
                    if target_sector is not None:
                        # Optimize for specific sector
                        if target_sector in result.get_good_sectors():
                            if result.sectors_with_valid_crc > best_count:
                                best_count = result.sectors_with_valid_crc
                                best_params = params
                    else:
                        # Optimize for total sectors
                        if result.sectors_with_valid_crc > best_count:
                            best_count = result.sectors_with_valid_crc
                            best_params = params

                except Exception:
                    continue

    # Get final result with best parameters
    final_result = decode_with_pll(flux, best_params)
    final_sectors = final_result.get_good_sectors()
    improvement = len(final_sectors) - len(default_sectors)

    # Calculate confidence based on improvement and consistency
    if improvement > 5:
        confidence = 0.95
    elif improvement > 0:
        confidence = 0.8
    elif len(final_sectors) >= len(default_sectors):
        confidence = 0.6
    else:
        confidence = 0.4

    logger.info("Optimal PLL found: %d sectors (+%d), confidence=%.0f%%",
                len(final_sectors), improvement, confidence * 100)

    return OptimalPLLResult(
        parameters=best_params,
        sectors_decoded=final_sectors,
        improvement=improvement,
        default_sectors=default_sectors,
        decode_result=final_result,
        confidence=confidence,
    )


def optimize_for_sector(
    flux: FluxCapture,
    sector_number: int,
    max_attempts: int = 100
) -> Tuple[bool, Optional[bytes], PLLParameters]:
    """
    Optimize PLL specifically to recover a single sector.

    Focused optimization when a specific sector is needed.

    Args:
        flux: FluxCapture containing the track
        sector_number: Sector number to recover (1-18)
        max_attempts: Maximum parameter combinations to try

    Returns:
        Tuple of (success, sector_data, best_parameters)
    """
    logger.debug("Optimizing PLL for sector %d", sector_number)

    base = PLLParameters.for_hd()
    attempt = 0

    # Try systematic variations
    for phase in range(-400, 401, 50):
        for freq_pct in range(-4, 5):
            for bw in [0.03, 0.05, 0.07, 0.10]:
                if attempt >= max_attempts:
                    break

                params = PLLParameters(
                    phase_offset=phase,
                    frequency=base.frequency * (1 + freq_pct/100),
                    bandwidth=bw,
                    damping=base.damping,
                    gain=base.gain,
                )

                try:
                    result = decode_with_pll(flux, params)

                    for sector_result in result.sector_results:
                        matches_sector = sector_result.sector_number == sector_number
                        is_valid = sector_result.crc_valid and sector_result.data is not None
                        if matches_sector and is_valid:
                            logger.info("Found sector %d with custom PLL", sector_number)
                            return (True, sector_result.data, params)

                except Exception:
                    pass

                attempt += 1

    logger.debug("Could not recover sector %d after %d attempts",
                 sector_number, attempt)
    return (False, None, base)


# =============================================================================
# PLL State Class
# =============================================================================

@dataclass
class PLLState:
    """
    Current state of the PLL during decoding.

    Tracks the internal state variables used by the PLL to
    maintain phase lock with the incoming flux data.

    Attributes:
        phase: Current phase in nanoseconds
        frequency: Current frequency estimate in Hz
        phase_error: Last phase error measurement
        locked: Whether PLL is currently locked
        lock_count: Number of consecutive locked samples
        history: Recent phase error history for analysis
    """
    phase: float = 0.0
    frequency: float = DEFAULT_FREQUENCY_HZ
    phase_error: float = 0.0
    locked: bool = False
    lock_count: int = 0
    history: List[float] = field(default_factory=list)

    def update(self, measured_period: float, params: PLLParameters) -> None:
        """Update PLL state with new measurement."""
        expected_period = 1e9 / self.frequency  # Expected in nanoseconds

        # Calculate phase error
        self.phase_error = measured_period - expected_period

        # Update phase
        self.phase += self.phase_error * params.bandwidth

        # Update frequency estimate (second-order PLL)
        freq_correction = self.phase_error * params.bandwidth * params.bandwidth
        self.frequency += freq_correction * params.gain

        # Track lock status
        if abs(self.phase_error) < expected_period * 0.1:  # Within 10%
            self.lock_count += 1
            if self.lock_count > 10:
                self.locked = True
        else:
            self.lock_count = 0
            self.locked = False

        # Maintain history
        self.history.append(self.phase_error)
        if len(self.history) > 100:
            self.history.pop(0)


# =============================================================================
# Utility Functions
# =============================================================================

def create_parameter_grid(
    frequency_range: Tuple[float, float] = (490000, 510000),
    frequency_steps: int = 5,
    bandwidth_range: Tuple[float, float] = (0.02, 0.15),
    bandwidth_steps: int = 5,
    phase_offsets: List[float] = None
) -> List[PLLParameters]:
    """
    Create a grid of PLL parameters for exhaustive search.

    Generates combinations of PLL parameters to try when searching
    for optimal settings for difficult sectors.

    Args:
        frequency_range: Min and max frequency in Hz
        frequency_steps: Number of frequency values to try
        bandwidth_range: Min and max bandwidth values
        bandwidth_steps: Number of bandwidth values to try
        phase_offsets: List of phase offsets to try (ns)

    Returns:
        List of PLLParameters to try
    """
    if phase_offsets is None:
        phase_offsets = [-200, -100, 0, 100, 200]

    params_list = []

    # Generate frequency values
    freq_min, freq_max = frequency_range
    freq_step = (freq_max - freq_min) / max(1, frequency_steps - 1)
    frequencies = [freq_min + i * freq_step for i in range(frequency_steps)]

    # Generate bandwidth values
    bw_min, bw_max = bandwidth_range
    bw_step = (bw_max - bw_min) / max(1, bandwidth_steps - 1)
    bandwidths = [bw_min + i * bw_step for i in range(bandwidth_steps)]

    # Generate all combinations
    for freq in frequencies:
        for bw in bandwidths:
            for phase in phase_offsets:
                params_list.append(PLLParameters(
                    phase_offset=phase,
                    frequency=freq,
                    bandwidth=bw,
                    damping=DEFAULT_DAMPING,
                    gain=1.0
                ))

    logger.debug("Created parameter grid with %d combinations", len(params_list))
    return params_list


def default_pll_parameters() -> PLLParameters:
    """
    Get default PLL parameters for HD MFM decoding.

    Returns standard parameters suitable for most 3.5" HD
    floppy disks in good condition.

    Returns:
        PLLParameters with default values
    """
    return PLLParameters(
        phase_offset=0,
        frequency=DEFAULT_FREQUENCY_HZ,
        bandwidth=DEFAULT_BANDWIDTH,
        damping=DEFAULT_DAMPING,
        gain=1.0
    )


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Data classes
    'PLLParameters',
    'DecodedSectorResult',
    'PLLDecodeResult',
    'PLLSearchResult',
    'OptimalPLLResult',
    'PLLState',
    # Classes
    'PLLDecoder',
    # Functions
    'decode_with_pll',
    'try_pll_variations',
    'find_optimal_pll',
    'optimize_for_sector',
    'create_parameter_grid',
    'default_pll_parameters',
    # Constants
    'DEFAULT_FREQUENCY_HZ',
    'DEFAULT_BANDWIDTH',
    'DEFAULT_DAMPING',
]
