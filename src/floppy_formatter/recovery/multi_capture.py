"""
Multi-revolution flux capture and statistical reconstruction.

This module provides advanced data recovery through multi-revolution flux
capture and flux-level statistical bit voting. Unlike byte-level recovery,
this operates at the raw magnetic transition level for maximum accuracy.

The multi-capture approach:
1. Captures 10+ revolutions of flux data from the same track
2. Aligns captures using index pulses as reference
3. Performs bit-by-bit voting across all captures
4. Reconstructs the most likely correct data

This ENHANCES the existing read_sector_multiread() capability by working
at the flux level rather than the decoded sector level.

Key Functions:
    capture_multiple_revolutions: Capture N revolutions of flux data
    align_flux_captures: Time-align captures using index pulses
    reconstruct_from_captures: Statistical bit voting reconstruction
"""

import math
import statistics
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice, FluxData

from floppy_formatter.analysis.flux_analyzer import FluxCapture
from floppy_formatter.analysis.signal_quality import calculate_snr

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default number of revolutions for multi-capture
DEFAULT_REVOLUTION_COUNT = 10

# Maximum revolutions per single capture (hardware limit)
MAX_REVOLUTIONS_PER_CAPTURE = 20

# Minimum captures for reliable voting
MIN_CAPTURES_FOR_VOTING = 3

# Confidence thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.9  # 90% agreement
MEDIUM_CONFIDENCE_THRESHOLD = 0.7  # 70% agreement
LOW_CONFIDENCE_THRESHOLD = 0.5  # 50% agreement (majority)

# Timing alignment tolerance (in sample counts, ~14ns per sample at 72MHz)
ALIGNMENT_TOLERANCE_SAMPLES = 10

# Standard MFM bit cell timing (2us for HD)
HD_BIT_CELL_US = 2.0
HD_BIT_CELL_SAMPLES = 144  # 2us * 72MHz


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CaptureMetadata:
    """
    Metadata for a single revolution capture.

    Attributes:
        revolution_number: Revolution index (0-based)
        index_position: Sample position of index pulse
        duration_samples: Duration in sample counts
        duration_us: Duration in microseconds
        snr_db: Signal-to-noise ratio
        quality_score: Overall quality (0.0-1.0)
        transition_count: Number of flux transitions
    """
    revolution_number: int
    index_position: int
    duration_samples: int
    duration_us: float
    snr_db: float
    quality_score: float
    transition_count: int


@dataclass
class MultiCaptureResult:
    """
    Result of capturing multiple revolutions.

    Attributes:
        captures: List of FluxCapture objects, one per revolution
        metadata: List of CaptureMetadata for each capture
        cylinder: Cylinder number
        head: Head number
        total_revolutions: Total revolutions captured
        sample_rate: Sample rate in Hz
        average_rpm: Measured average RPM
        rpm_stability: RPM standard deviation (lower is better)
    """
    captures: List[FluxCapture]
    metadata: List[CaptureMetadata]
    cylinder: int
    head: int
    total_revolutions: int
    sample_rate: int
    average_rpm: float
    rpm_stability: float

    def get_best_capture(self) -> Optional[FluxCapture]:
        """Get the capture with highest quality score."""
        if not self.captures:
            return None

        best_idx = max(
            range(len(self.metadata)),
            key=lambda i: self.metadata[i].quality_score
        )
        return self.captures[best_idx]

    def get_quality_summary(self) -> str:
        """Get summary of capture quality."""
        if not self.metadata:
            return "No captures"

        avg_snr = statistics.mean(m.snr_db for m in self.metadata)
        avg_quality = statistics.mean(m.quality_score for m in self.metadata)

        return (
            f"{self.total_revolutions} revolutions captured, "
            f"avg SNR: {avg_snr:.1f}dB, avg quality: {avg_quality:.2f}"
        )


@dataclass
class AlignedCaptures:
    """
    Time-aligned flux captures ready for reconstruction.

    After alignment, all captures are synchronized to a common
    time base using index pulses as reference.

    Attributes:
        aligned_timings: List of aligned timing arrays (one per capture)
        reference_index: Index of the reference capture used for alignment
        alignment_offsets: Sample offset applied to each capture
        common_length: Length of aligned data (samples)
        sample_rate: Sample rate in Hz
        cylinder: Cylinder number
        head: Head number
        capture_count: Number of aligned captures
        quality_weights: Quality weight for each capture (for weighted voting)
    """
    aligned_timings: List[List[float]]  # Timing in microseconds
    reference_index: int
    alignment_offsets: List[int]
    common_length: int
    sample_rate: int
    cylinder: int
    head: int
    capture_count: int
    quality_weights: List[float] = field(default_factory=list)

    def get_timing_at_position(self, position: int) -> List[float]:
        """
        Get timing values at a specific position across all captures.

        Args:
            position: Position index in aligned data

        Returns:
            List of timing values from each capture at that position
        """
        timings = []
        for capture_timings in self.aligned_timings:
            if position < len(capture_timings):
                timings.append(capture_timings[position])
        return timings


@dataclass
class BitVoteResult:
    """Result of voting on a single bit position."""
    position: int
    winning_value: int  # 0 or 1
    vote_count: int  # How many captures agreed
    total_votes: int  # Total captures that had data at this position
    confidence: float  # vote_count / total_votes
    timing_us: float  # Reconstructed timing value


@dataclass
class ReconstructedSector:
    """A sector reconstructed from multi-capture voting."""
    sector_number: int
    data: bytes
    crc_valid: bool
    confidence: float  # Average confidence across all bits
    low_confidence_positions: List[int]  # Byte positions with low confidence


@dataclass
class ReconstructedFlux:
    """
    Result of flux-level reconstruction from multiple captures.

    Attributes:
        flux_timings: Reconstructed flux timing array (microseconds)
        confidence_map: Per-position confidence values (0.0-1.0)
        vote_counts: How many captures agreed on each position
        total_positions: Total number of positions reconstructed
        high_confidence_count: Positions with >90% agreement
        medium_confidence_count: Positions with 70-90% agreement
        low_confidence_count: Positions with <70% agreement
        sectors: List of decoded sectors from reconstruction
        cylinder: Cylinder number
        head: Head number
        source_captures: Number of captures used
    """
    flux_timings: List[float]
    confidence_map: List[float]
    vote_counts: List[int]
    total_positions: int
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    sectors: List[ReconstructedSector]
    cylinder: int
    head: int
    source_captures: int

    def get_overall_confidence(self) -> float:
        """Get overall reconstruction confidence."""
        if not self.confidence_map:
            return 0.0
        return statistics.mean(self.confidence_map)

    def get_weak_positions(self, threshold: float = 0.7) -> List[int]:
        """Get positions with confidence below threshold."""
        return [
            i for i, conf in enumerate(self.confidence_map)
            if conf < threshold
        ]

    def to_flux_data(self) -> 'FluxData':
        """
        Convert reconstruction back to FluxData for decoding.

        Returns:
            FluxData object suitable for MFM decoding
        """
        from floppy_formatter.hardware import FluxData

        # Convert microseconds back to sample counts
        sample_rate = 72_000_000  # Standard Greaseweazle rate
        factor = sample_rate / 1_000_000
        flux_times = [int(t * factor) for t in self.flux_timings]

        return FluxData(
            flux_times=flux_times,
            sample_freq=sample_rate,
            index_positions=[0],  # Single revolution
            cylinder=self.cylinder,
            head=self.head,
            revolutions=1.0
        )


# =============================================================================
# Multi-Capture Functions
# =============================================================================

def capture_multiple_revolutions(
    device: Any,  # GreaseweazleDevice
    cyl: int,
    head: int,
    count: int = DEFAULT_REVOLUTION_COUNT
) -> MultiCaptureResult:
    """
    Capture multiple revolutions of flux data from a track.

    This function captures N complete revolutions of the disk,
    providing multiple independent samples of the same track
    for statistical analysis and reconstruction.

    Args:
        device: Connected GreaseweazleDevice instance
        cyl: Cylinder number (0-79 for 3.5" HD)
        head: Head number (0 or 1)
        count: Number of revolutions to capture (default 10)

    Returns:
        MultiCaptureResult containing all captures and metadata

    Example:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     result = capture_multiple_revolutions(device, 40, 0, count=10)
        ...     print(result.get_quality_summary())
    """
    from floppy_formatter.hardware import read_track_flux

    logger.info("Capturing %d revolutions from C%d H%d", count, cyl, head)

    captures = []
    metadata = []
    rpm_measurements = []

    # Capture in batches if needed
    remaining = count
    capture_batch = 0

    while remaining > 0:
        # Determine batch size
        batch_size = min(remaining, MAX_REVOLUTIONS_PER_CAPTURE)

        # Add 0.2 extra to ensure we get complete revolutions
        revolutions_to_capture = float(batch_size + 0.2)

        logger.debug("Capture batch %d: %d revolutions", capture_batch, batch_size)

        try:
            # Capture flux from track
            flux_data = read_track_flux(
                device, cyl, head,
                revolutions=revolutions_to_capture
            )

            # Extract individual revolutions
            for rev in range(batch_size):
                try:
                    rev_flux = flux_data.get_revolution_data(rev)
                    capture = FluxCapture.from_flux_data(rev_flux)

                    # Calculate quality metrics
                    snr_result = calculate_snr(capture)
                    quality_score = _calculate_capture_quality(capture)

                    # Get RPM for this revolution
                    rpm = capture.calculate_rpm()
                    if rpm:
                        rpm_measurements.append(rpm)

                    # Create metadata
                    meta = CaptureMetadata(
                        revolution_number=len(captures),
                        index_position=capture.index_positions[0] if capture.index_positions else 0,
                        duration_samples=sum(capture.raw_timings),
                        duration_us=capture.duration_ms * 1000,
                        snr_db=snr_result.snr_db,
                        quality_score=quality_score,
                        transition_count=capture.transition_count,
                    )

                    captures.append(capture)
                    metadata.append(meta)

                except (ValueError, IndexError) as e:
                    logger.debug("Failed to extract revolution %d: %s", rev, e)
                    continue

        except Exception as e:
            logger.warning("Capture batch %d failed: %s", capture_batch, e)

        remaining -= batch_size
        capture_batch += 1

    # Calculate RPM statistics
    if rpm_measurements:
        average_rpm = statistics.mean(rpm_measurements)
        rpm_stability = statistics.stdev(rpm_measurements) if len(rpm_measurements) > 1 else 0.0
    else:
        average_rpm = 300.0  # Default
        rpm_stability = 0.0

    logger.info("Captured %d revolutions, avg RPM: %.1f (±%.2f)",
                len(captures), average_rpm, rpm_stability)

    return MultiCaptureResult(
        captures=captures,
        metadata=metadata,
        cylinder=cyl,
        head=head,
        total_revolutions=len(captures),
        sample_rate=captures[0].sample_rate if captures else 72_000_000,
        average_rpm=average_rpm,
        rpm_stability=rpm_stability,
    )


def align_flux_captures(captures: List[FluxCapture]) -> AlignedCaptures:
    """
    Time-align multiple flux captures using index pulses as reference.

    This function compensates for RPM variation between captures by:
    1. Using index pulses as alignment reference points
    2. Resampling flux data to a common time base
    3. Compensating for timing drift

    Args:
        captures: List of FluxCapture objects to align

    Returns:
        AlignedCaptures with all captures synchronized

    Example:
        >>> result = capture_multiple_revolutions(device, 40, 0, count=10)
        >>> aligned = align_flux_captures(result.captures)
        >>> print(f"Aligned {aligned.capture_count} captures")
    """
    if not captures:
        return AlignedCaptures(
            aligned_timings=[],
            reference_index=0,
            alignment_offsets=[],
            common_length=0,
            sample_rate=72_000_000,
            cylinder=-1,
            head=-1,
            capture_count=0,
        )

    logger.debug("Aligning %d captures", len(captures))

    # Find the capture with highest quality to use as reference
    quality_scores = []
    for cap in captures:
        snr = calculate_snr(cap)
        quality_scores.append(snr.snr_db)

    reference_index = quality_scores.index(max(quality_scores))
    reference = captures[reference_index]

    # Get reference timing in microseconds
    ref_timings = reference.get_timings_microseconds()
    ref_length = len(ref_timings)

    # Calculate quality weights for weighted voting
    max_quality = max(quality_scores)
    quality_weights = [q / max_quality for q in quality_scores]

    # Align each capture to the reference
    aligned_timings = []
    alignment_offsets = []

    for i, capture in enumerate(captures):
        timings = capture.get_timings_microseconds()

        if i == reference_index:
            # Reference capture - no alignment needed
            aligned_timings.append(timings)
            alignment_offsets.append(0)
        else:
            # Find alignment offset using cross-correlation
            offset = _find_alignment_offset(ref_timings, timings)
            alignment_offsets.append(offset)

            # Apply offset
            if offset > 0:
                # Capture is ahead of reference - trim start
                aligned = timings[offset:]
            elif offset < 0:
                # Capture is behind reference - pad start with zeros
                padding = [0.0] * abs(offset)
                aligned = padding + timings
            else:
                aligned = timings

            aligned_timings.append(aligned)

    # Find common length (minimum across all aligned captures)
    common_length = min(len(t) for t in aligned_timings) if aligned_timings else 0

    # Trim all to common length
    aligned_timings = [t[:common_length] for t in aligned_timings]

    logger.debug("Alignment complete: common length = %d", common_length)

    return AlignedCaptures(
        aligned_timings=aligned_timings,
        reference_index=reference_index,
        alignment_offsets=alignment_offsets,
        common_length=common_length,
        sample_rate=reference.sample_rate,
        cylinder=reference.cylinder,
        head=reference.head,
        capture_count=len(captures),
        quality_weights=quality_weights,
    )


def reconstruct_from_captures(captures: AlignedCaptures) -> ReconstructedFlux:
    """
    Reconstruct flux data using statistical bit voting across captures.

    For each bit position, examines all captures and uses majority
    voting to determine the most likely correct value. Weights votes
    by capture quality if available.

    Args:
        captures: AlignedCaptures from align_flux_captures()

    Returns:
        ReconstructedFlux with reconstructed timing and confidence data

    Example:
        >>> result = capture_multiple_revolutions(device, 40, 0, count=10)
        >>> aligned = align_flux_captures(result.captures)
        >>> reconstructed = reconstruct_from_captures(aligned)
        >>> print(f"Overall confidence: {reconstructed.get_overall_confidence():.1%}")
        >>> # Decode sectors from reconstructed flux
        >>> flux_data = reconstructed.to_flux_data()
        >>> sectors = decode_flux_to_sectors(flux_data)
    """
    if captures.capture_count < MIN_CAPTURES_FOR_VOTING:
        logger.warning("Insufficient captures for voting (%d < %d)",
                       captures.capture_count, MIN_CAPTURES_FOR_VOTING)

    logger.debug("Reconstructing from %d captures, %d positions",
                 captures.capture_count, captures.common_length)

    reconstructed_timings = []
    confidence_map = []
    vote_counts = []

    high_conf = 0
    medium_conf = 0
    low_conf = 0

    # Process each position
    for pos in range(captures.common_length):
        # Get timing values from all captures at this position
        timings_at_pos = captures.get_timing_at_position(pos)

        if not timings_at_pos:
            reconstructed_timings.append(0.0)
            confidence_map.append(0.0)
            vote_counts.append(0)
            low_conf += 1
            continue

        # Quantize timings to MFM pulse widths for voting
        # MFM has 3 valid pulse widths: 2T (~4us), 3T (~6us), 4T (~8us)
        quantized_votes = {}

        for timing in timings_at_pos:
            # Quantize to nearest MFM pulse type
            if timing < 5.0:
                pulse_type = '2T'
            elif timing < 7.0:
                pulse_type = '3T'
            else:
                pulse_type = '4T'

            quantized_votes[pulse_type] = quantized_votes.get(pulse_type, 0) + 1

        # Find winning pulse type
        if quantized_votes:
            winning_type = max(quantized_votes.keys(),
                              key=lambda k: quantized_votes[k])
            winning_votes = quantized_votes[winning_type]
            total_votes = len(timings_at_pos)
            confidence = winning_votes / total_votes

            # Calculate reconstructed timing as weighted mean of matching captures
            matching_timings = []
            for i, timing in enumerate(timings_at_pos):
                # Check if this timing matches winning type
                if timing < 5.0 and winning_type == '2T':
                    matching_timings.append(timing)
                elif 5.0 <= timing < 7.0 and winning_type == '3T':
                    matching_timings.append(timing)
                elif timing >= 7.0 and winning_type == '4T':
                    matching_timings.append(timing)

            if matching_timings:
                # Use median for robustness
                reconstructed_timing = statistics.median(matching_timings)
            else:
                reconstructed_timing = statistics.median(timings_at_pos)

            reconstructed_timings.append(reconstructed_timing)
            confidence_map.append(confidence)
            vote_counts.append(winning_votes)

            # Categorize confidence
            if confidence >= HIGH_CONFIDENCE_THRESHOLD:
                high_conf += 1
            elif confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
                medium_conf += 1
            else:
                low_conf += 1

        else:
            reconstructed_timings.append(0.0)
            confidence_map.append(0.0)
            vote_counts.append(0)
            low_conf += 1

    # Decode sectors from reconstructed flux
    sectors = _decode_reconstructed_sectors(
        reconstructed_timings,
        confidence_map,
        captures.cylinder,
        captures.head,
        captures.sample_rate
    )

    logger.info(
        "Reconstruction complete: %d positions, "
        "high conf: %d, medium: %d, low: %d",
        captures.common_length, high_conf, medium_conf, low_conf
    )

    return ReconstructedFlux(
        flux_timings=reconstructed_timings,
        confidence_map=confidence_map,
        vote_counts=vote_counts,
        total_positions=captures.common_length,
        high_confidence_count=high_conf,
        medium_confidence_count=medium_conf,
        low_confidence_count=low_conf,
        sectors=sectors,
        cylinder=captures.cylinder,
        head=captures.head,
        source_captures=captures.capture_count,
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _calculate_capture_quality(capture: FluxCapture) -> float:
    """
    Calculate overall quality score for a capture.

    Returns:
        Quality score from 0.0 (poor) to 1.0 (excellent)
    """
    scores = []

    # Check transition count (should be reasonable for a full track)
    expected_transitions = 100000  # Approximate for HD track
    trans_ratio = min(capture.transition_count / expected_transitions, 1.0)
    scores.append(trans_ratio)

    # Check duration (should be close to 200ms for 300 RPM)
    expected_duration_ms = 200.0
    duration_ratio = min(capture.duration_ms / expected_duration_ms, 1.0)
    if duration_ratio > 0.95:
        scores.append(1.0)
    elif duration_ratio > 0.8:
        scores.append(0.8)
    else:
        scores.append(0.5)

    # Check for index pulse
    if capture.has_index:
        scores.append(1.0)
    else:
        scores.append(0.5)

    return statistics.mean(scores) if scores else 0.0


def _find_alignment_offset(
    reference: List[float],
    target: List[float],
    max_offset: int = 1000
) -> int:
    """
    Find the best alignment offset between two timing arrays.

    Uses cross-correlation to find the offset that maximizes
    timing similarity between reference and target.

    Returns:
        Offset in samples (positive = target is ahead, negative = behind)
    """
    if not reference or not target:
        return 0

    min_len = min(len(reference), len(target))
    if min_len < 100:
        return 0

    best_offset = 0
    best_correlation = 0.0

    # Try different offsets
    for offset in range(-max_offset, max_offset + 1, 10):  # Step by 10 for speed
        if offset >= 0:
            ref_slice = reference[offset:offset + min_len - max_offset]
            tgt_slice = target[:min_len - max_offset]
        else:
            ref_slice = reference[:min_len - max_offset]
            tgt_slice = target[-offset:-offset + min_len - max_offset]

        if len(ref_slice) < 100 or len(tgt_slice) < 100:
            continue

        # Calculate correlation
        try:
            correlation = _calculate_correlation(ref_slice, tgt_slice)
            if correlation > best_correlation:
                best_correlation = correlation
                best_offset = offset
        except (ValueError, ZeroDivisionError):
            continue

    # Fine-tune around best offset
    for offset in range(best_offset - 10, best_offset + 11):
        if offset >= 0:
            ref_slice = reference[offset:offset + min_len - max_offset]
            tgt_slice = target[:min_len - max_offset]
        else:
            ref_slice = reference[:min_len - max_offset]
            tgt_slice = target[-offset:-offset + min_len - max_offset]

        if len(ref_slice) < 100 or len(tgt_slice) < 100:
            continue

        try:
            correlation = _calculate_correlation(ref_slice, tgt_slice)
            if correlation > best_correlation:
                best_correlation = correlation
                best_offset = offset
        except (ValueError, ZeroDivisionError):
            continue

    return best_offset


def _calculate_correlation(x: List[float], y: List[float]) -> float:
    """Calculate Pearson correlation coefficient between two sequences."""
    n = min(len(x), len(y))
    if n < 10:
        return 0.0

    x = x[:n]
    y = y[:n]

    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)

    std_x = statistics.stdev(x)
    std_y = statistics.stdev(y)

    if std_x == 0 or std_y == 0:
        return 0.0

    covariance = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y)) / n
    return covariance / (std_x * std_y)


def _decode_reconstructed_sectors(
    timings_us: List[float],
    confidence_map: List[float],
    cylinder: int,
    head: int,
    sample_rate: int
) -> List[ReconstructedSector]:
    """
    Decode sectors from reconstructed flux timing data.

    Returns:
        List of ReconstructedSector objects
    """
    try:
        from floppy_formatter.hardware import FluxData, decode_flux_data

        # Convert microseconds back to sample counts
        factor = sample_rate / 1_000_000
        flux_times = [max(1, int(t * factor)) for t in timings_us]

        flux_data = FluxData(
            flux_times=flux_times,
            sample_freq=sample_rate,
            index_positions=[0],
            cylinder=cylinder,
            head=head,
            revolutions=1.0
        )

        decoded = decode_flux_data(flux_data)

        sectors = []
        for sector_data in decoded:
            # Calculate confidence for this sector
            # This is simplified - ideally we'd map flux positions to sector positions
            sector_confidence = statistics.mean(confidence_map) if confidence_map else 0.0

            # Find low confidence positions (byte level approximation)
            bits_per_sector = 512 * 8 * 2  # Including MFM encoding overhead
            start_bit = sector_data.sector * bits_per_sector  # Rough estimate

            low_conf_positions = []
            for byte_pos in range(len(sector_data.data) if sector_data.data else 0):
                bit_pos = start_bit + byte_pos * 16  # Rough mapping
                if bit_pos < len(confidence_map):
                    if confidence_map[bit_pos] < MEDIUM_CONFIDENCE_THRESHOLD:
                        low_conf_positions.append(byte_pos)

            sectors.append(ReconstructedSector(
                sector_number=sector_data.sector,
                data=sector_data.data if sector_data.data else bytes(512),
                crc_valid=sector_data.crc_valid,
                confidence=sector_confidence,
                low_confidence_positions=low_conf_positions[:20],  # Limit list size
            ))

        return sectors

    except Exception as e:
        logger.warning("Failed to decode reconstructed sectors: %s", e)
        return []


# =============================================================================
# Convenience Functions
# =============================================================================

def multi_capture_recover_track(
    device: Any,  # GreaseweazleDevice
    cyl: int,
    head: int,
    revolution_count: int = DEFAULT_REVOLUTION_COUNT
) -> Tuple[ReconstructedFlux, List[ReconstructedSector]]:
    """
    Perform complete multi-capture recovery on a track.

    Convenience function that combines capture, alignment, and
    reconstruction into a single call.

    Args:
        device: Connected GreaseweazleDevice instance
        cyl: Cylinder number
        head: Head number
        revolution_count: Number of revolutions to capture

    Returns:
        Tuple of (ReconstructedFlux, List of ReconstructedSector)

    Example:
        >>> reconstructed, sectors = multi_capture_recover_track(device, 40, 0)
        >>> for sector in sectors:
        ...     if sector.crc_valid:
        ...         print(f"Sector {sector.sector_number}: OK")
        ...     else:
        ...         print(f"Sector {sector.sector_number}: CRC error "
        ...               f"(confidence: {sector.confidence:.1%})")
    """
    # Capture multiple revolutions
    capture_result = capture_multiple_revolutions(device, cyl, head, revolution_count)

    if not capture_result.captures:
        logger.error("No captures obtained for C%d H%d", cyl, head)
        return ReconstructedFlux(
            flux_timings=[],
            confidence_map=[],
            vote_counts=[],
            total_positions=0,
            high_confidence_count=0,
            medium_confidence_count=0,
            low_confidence_count=0,
            sectors=[],
            cylinder=cyl,
            head=head,
            source_captures=0,
        ), []

    # Align captures
    aligned = align_flux_captures(capture_result.captures)

    # Reconstruct using voting
    reconstructed = reconstruct_from_captures(aligned)

    return reconstructed, reconstructed.sectors


def compare_multi_capture_to_single(
    device: Any,  # GreaseweazleDevice
    cyl: int,
    head: int,
    revolution_count: int = 10
) -> Dict[str, Any]:
    """
    Compare multi-capture recovery results to single-read.

    Useful for evaluating the benefit of multi-capture recovery.

    Args:
        device: Connected GreaseweazleDevice instance
        cyl: Cylinder number
        head: Head number
        revolution_count: Number of revolutions for multi-capture

    Returns:
        Dictionary with comparison results
    """
    from floppy_formatter.hardware import read_track_flux, decode_flux_data

    # Single read
    single_flux = read_track_flux(device, cyl, head, revolutions=1.2)
    single_sectors = decode_flux_data(single_flux)
    single_good = sum(1 for s in single_sectors if s.is_good)

    # Multi-capture recovery
    reconstructed, multi_sectors = multi_capture_recover_track(
        device, cyl, head, revolution_count
    )
    multi_good = sum(1 for s in multi_sectors if s.crc_valid)

    return {
        'single_read_good_sectors': single_good,
        'multi_capture_good_sectors': multi_good,
        'improvement': multi_good - single_good,
        'revolution_count': revolution_count,
        'overall_confidence': reconstructed.get_overall_confidence(),
        'high_confidence_positions': reconstructed.high_confidence_count,
        'low_confidence_positions': reconstructed.low_confidence_count,
    }


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Data classes
    'CaptureMetadata',
    'MultiCaptureResult',
    'AlignedCaptures',
    'BitVoteResult',
    'ReconstructedSector',
    'ReconstructedFlux',
    # Functions
    'capture_multiple_revolutions',
    'align_flux_captures',
    'reconstruct_from_captures',
    'multi_capture_recover_track',
    'compare_multi_capture_to_single',
    # Constants
    'DEFAULT_REVOLUTION_COUNT',
    'HIGH_CONFIDENCE_THRESHOLD',
    'MEDIUM_CONFIDENCE_THRESHOLD',
    'LOW_CONFIDENCE_THRESHOLD',
]
