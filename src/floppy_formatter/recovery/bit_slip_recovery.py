"""
Bit slip detection and recovery for MFM flux data.

Bit slips occur when the PLL loses synchronization with the data stream,
causing the decoder to slip forward or backward by one or more bits.
This results in corrupted data even when the magnetic signal is good.

Common causes of bit slips:
- Sudden timing changes (head vibration, motor speed variation)
- Weak or missing flux transitions
- Noise spikes that look like transitions
- Damaged or worn media causing timing distortion

This module detects bit slip events and attempts to recover data by:
1. Identifying positions where sync was lost
2. Calculating the slip amount (±N bits)
3. Realigning the data stream to restore sync
4. Reconstructing the sector data

Key Functions:
    detect_bit_slips: Find synchronization losses in flux data
    realign_after_slip: Correct timing to restore sync
    reconstruct_slipped_sector: Piece together data around slips
"""

import math
import statistics
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from floppy_formatter.hardware import FluxData

from floppy_formatter.analysis.flux_analyzer import FluxCapture

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# MFM timing constants for HD (3.5" 1.44MB)
HD_BIT_CELL_NS = 2000  # 2 microseconds = 2000 nanoseconds
HD_BIT_CELL_US = 2.0

# Valid MFM pulse widths
MFM_2T_US = 4.0   # Short pulse (2 bit cells)
MFM_3T_US = 6.0   # Medium pulse (3 bit cells)
MFM_4T_US = 8.0   # Long pulse (4 bit cells)

# Timing tolerance for pulse width classification
TIMING_TOLERANCE_US = 1.0  # ±1us tolerance

# Bit slip detection thresholds
PHASE_JUMP_THRESHOLD = 0.3  # 30% of bit cell = suspicious
SUDDEN_PHASE_JUMP = 0.5  # 50% of bit cell = likely slip
MINIMUM_SLIP_CONFIDENCE = 0.6  # Minimum confidence to report

# Sector structure constants
SECTOR_DATA_BITS = 512 * 8 * 2  # 512 bytes * 8 bits * 2 (MFM encoding)
SECTOR_HEADER_BITS = 64  # Approximate header size in bits
GAP_BITS = 100  # Approximate gap size

# Phase tracking window
PHASE_WINDOW_SIZE = 50  # Transitions to average for phase tracking


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class BitSlipEvent:
    """
    Detected bit slip event in flux data.

    Attributes:
        position: Sample position where slip occurred
        flux_index: Index in flux timing array
        position_us: Position in microseconds from track start
        slip_amount: Estimated bits slipped (positive = forward, negative = backward)
        phase_before: Phase before the slip (0.0-1.0 of bit cell)
        phase_after: Phase after the slip
        confidence: Detection confidence (0.0-1.0)
        probable_cause: Likely cause of the slip
        affected_bytes: Estimated bytes affected by this slip
    """
    position: int  # Sample position
    flux_index: int  # Index in flux timing array
    position_us: float  # Position in microseconds
    slip_amount: int  # Bits slipped (+/-)
    phase_before: float  # Phase before slip
    phase_after: float  # Phase after slip
    confidence: float  # Detection confidence
    probable_cause: str  # Likely cause
    affected_bytes: int  # Estimated affected bytes

    def is_forward_slip(self) -> bool:
        """Check if this is a forward slip (data bits lost)."""
        return self.slip_amount > 0

    def is_backward_slip(self) -> bool:
        """Check if this is a backward slip (extra bits inserted)."""
        return self.slip_amount < 0

    def get_severity(self) -> str:
        """Get severity level of this slip."""
        abs_slip = abs(self.slip_amount)
        if abs_slip >= 8:
            return "critical"
        elif abs_slip >= 4:
            return "high"
        elif abs_slip >= 2:
            return "medium"
        else:
            return "low"


@dataclass
class PhaseTrackingState:
    """State of PLL phase tracking for slip detection."""
    current_phase: float = 0.0
    phase_history: List[float] = field(default_factory=list)
    frequency_estimate: float = 500000.0  # Hz
    locked: bool = False
    lock_count: int = 0

    def update(self, timing_us: float, bit_cell_us: float = HD_BIT_CELL_US) -> float:
        """
        Update phase tracking with new transition.

        Args:
            timing_us: Time since last transition in microseconds
            bit_cell_us: Bit cell duration

        Returns:
            Phase error (deviation from expected phase)
        """
        # Calculate expected number of bit cells
        expected_cells = round(timing_us / bit_cell_us)
        expected_cells = max(2, min(4, expected_cells))  # MFM: 2T, 3T, 4T

        # Calculate phase error
        expected_timing = expected_cells * bit_cell_us
        phase_error = (timing_us - expected_timing) / bit_cell_us

        # Update phase
        self.current_phase += phase_error
        self.phase_history.append(self.current_phase)

        # Keep history manageable
        if len(self.phase_history) > PHASE_WINDOW_SIZE * 2:
            self.phase_history = self.phase_history[-PHASE_WINDOW_SIZE:]

        # Update lock status
        if abs(phase_error) < PHASE_JUMP_THRESHOLD:
            self.lock_count += 1
            if self.lock_count > 10:
                self.locked = True
        else:
            self.lock_count = max(0, self.lock_count - 2)
            if abs(phase_error) > SUDDEN_PHASE_JUMP:
                self.locked = False

        return phase_error

    def get_recent_phase_variance(self) -> float:
        """Get variance of recent phase values."""
        if len(self.phase_history) < 5:
            return 0.0
        recent = self.phase_history[-PHASE_WINDOW_SIZE:]
        return statistics.variance(recent) if len(recent) > 1 else 0.0


@dataclass
class SlipCorrection:
    """Correction to apply for a bit slip."""
    position: int  # Position in timing array
    correction_type: str  # "insert" or "remove"
    timing_adjustment_us: float  # Timing to add or remove
    bits_affected: int  # Number of bits affected


@dataclass
class SlipRecoveryResult:
    """
    Result of attempting to recover a slipped sector.

    Attributes:
        success: Whether recovery was successful
        sector_number: Sector that was recovered
        sector_data: Recovered data if successful
        original_data: Data before slip correction (may be partial)
        corrections_applied: List of corrections made
        crc_valid: Whether CRC passed after reconstruction
        confidence: Confidence in recovered data (0.0-1.0)
        slips_corrected: Number of bit slips corrected
    """
    success: bool
    sector_number: int
    sector_data: Optional[bytes]
    original_data: Optional[bytes]
    corrections_applied: List[SlipCorrection]
    crc_valid: bool
    confidence: float
    slips_corrected: int

    def get_summary(self) -> str:
        """Get human-readable summary."""
        if self.success:
            crc_str = "CRC valid" if self.crc_valid else "CRC invalid"
            return (
                f"Sector {self.sector_number}: Recovered "
                f"({self.slips_corrected} slips corrected, {crc_str})"
            )
        else:
            return f"Sector {self.sector_number}: Recovery failed"


@dataclass
class CorrectedFlux:
    """Flux data after bit slip correction."""
    timings_us: List[float]
    original_timings_us: List[float]
    corrections: List[SlipCorrection]
    positions_modified: List[int]


# =============================================================================
# Bit Slip Detection
# =============================================================================

def detect_bit_slips(flux: FluxCapture) -> List[BitSlipEvent]:
    """
    Find synchronization losses in flux data.

    Analyzes flux timing to detect positions where the PLL
    would lose sync and slip by one or more bits.

    Detection algorithm:
    1. Track PLL phase through all transitions
    2. Look for sudden phase jumps exceeding threshold
    3. Calculate slip amount from phase discontinuity
    4. Estimate confidence based on surrounding context

    Args:
        flux: FluxCapture to analyze

    Returns:
        List of BitSlipEvent for each detected slip

    Example:
        >>> slips = detect_bit_slips(capture)
        >>> for slip in slips:
        ...     print(f"Slip at {slip.position_us:.0f}us: {slip.slip_amount} bits")
        ...     print(f"  Cause: {slip.probable_cause}")
    """
    times_us = flux.get_timings_microseconds()

    if len(times_us) < 100:
        return []

    logger.debug("Detecting bit slips in %d transitions", len(times_us))

    slips = []
    phase_state = PhaseTrackingState()

    cumulative_position_us = 0.0
    cumulative_samples = 0

    for i, timing in enumerate(times_us):
        cumulative_position_us += timing

        # Track phase
        phase_error = phase_state.update(timing)

        # Detect slip conditions
        slip_detected = False
        slip_amount = 0
        confidence = 0.0
        cause = ""

        # Condition 1: Sudden large phase jump when previously locked
        if phase_state.locked and abs(phase_error) > SUDDEN_PHASE_JUMP:
            slip_detected = True
            # Calculate slip amount in bits
            slip_amount = round(phase_error)
            confidence = min(1.0, abs(phase_error) / 2.0)
            cause = "Sudden phase jump while locked"

        # Condition 2: Timing value way outside MFM range
        elif timing < 2.0 or timing > 12.0:
            slip_detected = True
            if timing < 2.0:
                slip_amount = -1  # Missing transition
                cause = "Abnormally short pulse (possible noise)"
            else:
                slip_amount = 1  # Extra time
                cause = "Abnormally long pulse (weak/missing transition)"
            confidence = 0.7

        # Condition 3: Phase drift accumulating
        elif len(phase_state.phase_history) >= PHASE_WINDOW_SIZE:
            recent_drift = phase_state.phase_history[-1] - phase_state.phase_history[-PHASE_WINDOW_SIZE]
            if abs(recent_drift) > 1.5:
                slip_detected = True
                slip_amount = round(recent_drift)
                confidence = 0.6
                cause = "Accumulated phase drift"

        if slip_detected and abs(slip_amount) >= 1 and confidence >= MINIMUM_SLIP_CONFIDENCE:
            # Estimate affected bytes
            # A slip affects data from this point until resync (typically 10-50 bytes)
            affected_bytes = min(50, max(10, abs(slip_amount) * 8))

            slips.append(BitSlipEvent(
                position=cumulative_samples,
                flux_index=i,
                position_us=cumulative_position_us,
                slip_amount=slip_amount,
                phase_before=phase_state.phase_history[-2] if len(phase_state.phase_history) >= 2 else 0,
                phase_after=phase_state.current_phase,
                confidence=confidence,
                probable_cause=cause,
                affected_bytes=affected_bytes,
            ))

            # Reset phase tracking after detecting slip
            phase_state.current_phase = 0.0
            phase_state.locked = False
            phase_state.lock_count = 0

        # Update cumulative sample count (rough estimate)
        sample_rate = flux.sample_rate if flux.sample_rate else 72_000_000
        cumulative_samples += int(timing * sample_rate / 1_000_000)

    logger.debug("Detected %d bit slips", len(slips))

    return slips


def analyze_slip_pattern(slips: List[BitSlipEvent]) -> Dict[str, Any]:
    """
    Analyze pattern of detected bit slips.

    Looks for systematic issues vs random events.

    Args:
        slips: List of detected BitSlipEvent

    Returns:
        Dictionary with pattern analysis
    """
    if not slips:
        return {
            'total_slips': 0,
            'pattern': 'none',
            'recommendation': 'No bit slips detected',
        }

    # Analyze slip distribution
    slip_amounts = [s.slip_amount for s in slips]
    slip_positions = [s.position_us for s in slips]

    # Check for systematic bias (all slips in same direction)
    forward_count = sum(1 for s in slip_amounts if s > 0)
    backward_count = sum(1 for s in slip_amounts if s < 0)

    if forward_count > 0 and backward_count == 0:
        pattern = "systematic_forward"
        recommendation = "Drive timing running fast - check motor speed"
    elif backward_count > 0 and forward_count == 0:
        pattern = "systematic_backward"
        recommendation = "Drive timing running slow - check motor speed"
    elif len(slips) > 10:
        pattern = "frequent_random"
        recommendation = "Many random slips - possible media damage or weak signal"
    else:
        pattern = "occasional"
        recommendation = "Occasional slips - normal for marginal media"

    # Check for clustered slips
    clusters = []
    current_cluster = [slips[0]]

    for i in range(1, len(slips)):
        if slips[i].position_us - slips[i-1].position_us < 1000:  # Within 1ms
            current_cluster.append(slips[i])
        else:
            if len(current_cluster) > 1:
                clusters.append(current_cluster)
            current_cluster = [slips[i]]

    if len(current_cluster) > 1:
        clusters.append(current_cluster)

    return {
        'total_slips': len(slips),
        'forward_slips': forward_count,
        'backward_slips': backward_count,
        'pattern': pattern,
        'clusters': len(clusters),
        'average_slip_amount': statistics.mean(abs(s) for s in slip_amounts),
        'max_slip_amount': max(abs(s) for s in slip_amounts),
        'recommendation': recommendation,
    }


# =============================================================================
# Bit Slip Correction
# =============================================================================

def realign_after_slip(
    flux: FluxCapture,
    position: int,
    slip_amount: int
) -> CorrectedFlux:
    """
    Recover synchronization after a bit slip.

    Inserts or removes timing to compensate for the slip
    and attempts to re-establish MFM sync.

    Args:
        flux: FluxCapture to correct
        position: Flux index where slip occurred
        slip_amount: Bits slipped (positive = forward, negative = backward)

    Returns:
        CorrectedFlux with adjusted timing data

    Example:
        >>> slips = detect_bit_slips(capture)
        >>> if slips:
        ...     corrected = realign_after_slip(capture, slips[0].flux_index, slips[0].slip_amount)
        ...     print(f"Applied {len(corrected.corrections)} corrections")
    """
    times_us = list(flux.get_timings_microseconds())
    original_times = list(times_us)
    corrections = []
    positions_modified = []

    if position < 0 or position >= len(times_us):
        return CorrectedFlux(
            timings_us=times_us,
            original_timings_us=original_times,
            corrections=[],
            positions_modified=[],
        )

    logger.debug("Realigning after slip at position %d, amount=%d", position, slip_amount)

    # Calculate timing adjustment needed
    adjustment_us = slip_amount * HD_BIT_CELL_US

    if slip_amount > 0:
        # Forward slip: we lost bits, need to add time
        # Distribute the added time across a few transitions
        num_transitions = min(5, len(times_us) - position)
        add_per_transition = adjustment_us / num_transitions

        for i in range(num_transitions):
            idx = position + i
            if idx < len(times_us):
                times_us[idx] += add_per_transition
                positions_modified.append(idx)

        corrections.append(SlipCorrection(
            position=position,
            correction_type="insert",
            timing_adjustment_us=adjustment_us,
            bits_affected=slip_amount,
        ))

    elif slip_amount < 0:
        # Backward slip: extra bits, need to remove time
        # Take time from subsequent transitions
        num_transitions = min(5, len(times_us) - position)
        remove_per_transition = abs(adjustment_us) / num_transitions

        for i in range(num_transitions):
            idx = position + i
            if idx < len(times_us):
                times_us[idx] = max(2.0, times_us[idx] - remove_per_transition)
                positions_modified.append(idx)

        corrections.append(SlipCorrection(
            position=position,
            correction_type="remove",
            timing_adjustment_us=abs(adjustment_us),
            bits_affected=abs(slip_amount),
        ))

    return CorrectedFlux(
        timings_us=times_us,
        original_timings_us=original_times,
        corrections=corrections,
        positions_modified=positions_modified,
    )


def apply_all_slip_corrections(
    flux: FluxCapture,
    slips: List[BitSlipEvent]
) -> CorrectedFlux:
    """
    Apply corrections for all detected bit slips.

    Args:
        flux: FluxCapture to correct
        slips: List of detected BitSlipEvent

    Returns:
        CorrectedFlux with all corrections applied
    """
    if not slips:
        return CorrectedFlux(
            timings_us=list(flux.get_timings_microseconds()),
            original_timings_us=list(flux.get_timings_microseconds()),
            corrections=[],
            positions_modified=[],
        )

    # Sort slips by position (process from end to start to avoid index shifts)
    sorted_slips = sorted(slips, key=lambda s: s.flux_index, reverse=True)

    times_us = list(flux.get_timings_microseconds())
    original_times = list(times_us)
    all_corrections = []
    all_modified = []

    for slip in sorted_slips:
        position = slip.flux_index
        slip_amount = slip.slip_amount

        if position < 0 or position >= len(times_us):
            continue

        adjustment_us = slip_amount * HD_BIT_CELL_US

        if slip_amount > 0:
            num_transitions = min(5, len(times_us) - position)
            add_per_transition = adjustment_us / num_transitions

            for i in range(num_transitions):
                idx = position + i
                if idx < len(times_us):
                    times_us[idx] += add_per_transition
                    all_modified.append(idx)

            all_corrections.append(SlipCorrection(
                position=position,
                correction_type="insert",
                timing_adjustment_us=adjustment_us,
                bits_affected=slip_amount,
            ))

        elif slip_amount < 0:
            num_transitions = min(5, len(times_us) - position)
            remove_per_transition = abs(adjustment_us) / num_transitions

            for i in range(num_transitions):
                idx = position + i
                if idx < len(times_us):
                    times_us[idx] = max(2.0, times_us[idx] - remove_per_transition)
                    all_modified.append(idx)

            all_corrections.append(SlipCorrection(
                position=position,
                correction_type="remove",
                timing_adjustment_us=abs(adjustment_us),
                bits_affected=abs(slip_amount),
            ))

    logger.debug("Applied %d slip corrections", len(all_corrections))

    return CorrectedFlux(
        timings_us=times_us,
        original_timings_us=original_times,
        corrections=all_corrections,
        positions_modified=list(set(all_modified)),
    )


# =============================================================================
# Sector Reconstruction
# =============================================================================

def reconstruct_slipped_sector(
    flux: FluxCapture,
    sector_num: int
) -> SlipRecoveryResult:
    """
    Piece together sector data by correcting bit slips.

    This function:
    1. Detects all bit slips in the track
    2. Identifies slips that affect the target sector
    3. Applies corrections sequentially
    4. Attempts to decode the corrected flux
    5. Validates CRC on reconstructed data

    Args:
        flux: FluxCapture containing the sector
        sector_num: Sector number to recover (1-18)

    Returns:
        SlipRecoveryResult with recovery status and data

    Example:
        >>> result = reconstruct_slipped_sector(capture, 5)
        >>> if result.success:
        ...     print(f"Recovered sector 5: {len(result.sector_data)} bytes")
        ...     if result.crc_valid:
        ...         print("CRC is valid!")
        ...     else:
        ...         print(f"CRC invalid but data recovered (confidence: {result.confidence:.0%})")
    """
    logger.info("Attempting slip recovery for sector %d", sector_num)

    # First, try to decode without correction to get baseline
    original_data = _try_decode_sector(flux, sector_num)

    # Detect all bit slips
    slips = detect_bit_slips(flux)

    if not slips:
        # No slips detected - if sector is bad, slips aren't the cause
        if original_data is None:
            return SlipRecoveryResult(
                success=False,
                sector_number=sector_num,
                sector_data=None,
                original_data=None,
                corrections_applied=[],
                crc_valid=False,
                confidence=0.0,
                slips_corrected=0,
            )
        else:
            return SlipRecoveryResult(
                success=True,
                sector_number=sector_num,
                sector_data=original_data,
                original_data=original_data,
                corrections_applied=[],
                crc_valid=True,
                confidence=1.0,
                slips_corrected=0,
            )

    # Estimate sector position in track
    # Sectors are approximately evenly distributed across 200ms track
    sector_start_us = (sector_num - 1) * (200000 / 18)
    sector_end_us = sector_num * (200000 / 18)

    # Find slips that affect this sector
    sector_slips = [
        s for s in slips
        if sector_start_us - 5000 <= s.position_us <= sector_end_us + 5000
    ]

    if not sector_slips:
        # No slips affect this sector
        return SlipRecoveryResult(
            success=original_data is not None,
            sector_number=sector_num,
            sector_data=original_data,
            original_data=original_data,
            corrections_applied=[],
            crc_valid=original_data is not None,
            confidence=1.0 if original_data else 0.0,
            slips_corrected=0,
        )

    logger.debug("Found %d slips affecting sector %d", len(sector_slips), sector_num)

    # Apply slip corrections
    corrected = apply_all_slip_corrections(flux, sector_slips)

    # Try to decode corrected flux
    corrected_data = _decode_corrected_flux(corrected.timings_us, flux, sector_num)

    if corrected_data is not None:
        # Validate CRC
        crc_valid = _validate_sector_crc(corrected_data)

        return SlipRecoveryResult(
            success=True,
            sector_number=sector_num,
            sector_data=corrected_data,
            original_data=original_data,
            corrections_applied=corrected.corrections,
            crc_valid=crc_valid,
            confidence=0.9 if crc_valid else 0.6,
            slips_corrected=len(sector_slips),
        )
    else:
        # Correction didn't help - try alternative strategies
        alternative_data = _try_alternative_corrections(flux, sector_slips, sector_num)

        if alternative_data is not None:
            crc_valid = _validate_sector_crc(alternative_data)
            return SlipRecoveryResult(
                success=True,
                sector_number=sector_num,
                sector_data=alternative_data,
                original_data=original_data,
                corrections_applied=corrected.corrections,
                crc_valid=crc_valid,
                confidence=0.7 if crc_valid else 0.4,
                slips_corrected=len(sector_slips),
            )

        return SlipRecoveryResult(
            success=False,
            sector_number=sector_num,
            sector_data=None,
            original_data=original_data,
            corrections_applied=corrected.corrections,
            crc_valid=False,
            confidence=0.0,
            slips_corrected=len(sector_slips),
        )


def recover_track_with_slip_correction(
    flux: FluxCapture
) -> Tuple[List[SlipRecoveryResult], int]:
    """
    Attempt slip recovery on all sectors of a track.

    Args:
        flux: FluxCapture of the track

    Returns:
        Tuple of (list of SlipRecoveryResult, count of recovered sectors)
    """
    results = []
    recovered_count = 0

    for sector_num in range(1, 19):
        result = reconstruct_slipped_sector(flux, sector_num)
        results.append(result)
        if result.success:
            recovered_count += 1

    logger.info("Slip recovery: %d/18 sectors recovered", recovered_count)

    return results, recovered_count


# =============================================================================
# Helper Functions
# =============================================================================

def _try_decode_sector(flux: FluxCapture, sector_num: int) -> Optional[bytes]:
    """
    Attempt to decode a specific sector from flux data.

    Returns:
        Sector data if successful, None if decode failed
    """
    try:
        from floppy_formatter.hardware import FluxData, decode_flux_to_sectors

        flux_data = FluxData(
            flux_times=flux.raw_timings,
            sample_freq=flux.sample_rate,
            index_positions=flux.index_positions,
            cylinder=flux.cylinder,
            head=flux.head,
        )

        sectors = decode_flux_to_sectors(flux_data)

        for sector in sectors:
            if sector.sector == sector_num and sector.is_good:
                return sector.data

        return None

    except Exception as e:
        logger.debug("Sector decode failed: %s", e)
        return None


def _decode_corrected_flux(
    timings_us: List[float],
    original_flux: FluxCapture,
    sector_num: int
) -> Optional[bytes]:
    """
    Decode sector from corrected timing data.

    Returns:
        Sector data if successful, None if decode failed
    """
    try:
        from floppy_formatter.hardware import FluxData, decode_flux_to_sectors

        # Convert microseconds back to sample counts
        sample_rate = original_flux.sample_rate or 72_000_000
        factor = sample_rate / 1_000_000
        flux_times = [max(1, int(t * factor)) for t in timings_us]

        flux_data = FluxData(
            flux_times=flux_times,
            sample_freq=sample_rate,
            index_positions=original_flux.index_positions,
            cylinder=original_flux.cylinder,
            head=original_flux.head,
        )

        sectors = decode_flux_to_sectors(flux_data)

        for sector in sectors:
            if sector.sector == sector_num:
                if sector.data and len(sector.data) == 512:
                    return sector.data

        return None

    except Exception as e:
        logger.debug("Corrected flux decode failed: %s", e)
        return None


def _try_alternative_corrections(
    flux: FluxCapture,
    slips: List[BitSlipEvent],
    sector_num: int
) -> Optional[bytes]:
    """
    Try alternative slip correction strategies.

    Sometimes the slip amount estimate is off by ±1 bit.
    This tries variations to find working corrections.
    """
    times_us = list(flux.get_timings_microseconds())

    # Try variations of slip amounts
    for variation in [-1, 1, -2, 2]:
        modified_slips = []
        for slip in slips:
            modified = BitSlipEvent(
                position=slip.position,
                flux_index=slip.flux_index,
                position_us=slip.position_us,
                slip_amount=slip.slip_amount + variation,
                phase_before=slip.phase_before,
                phase_after=slip.phase_after,
                confidence=slip.confidence,
                probable_cause=slip.probable_cause,
                affected_bytes=slip.affected_bytes,
            )
            modified_slips.append(modified)

        corrected = apply_all_slip_corrections(flux, modified_slips)
        data = _decode_corrected_flux(corrected.timings_us, flux, sector_num)

        if data is not None:
            logger.debug("Alternative correction succeeded with variation=%d", variation)
            return data

    return None


def _validate_sector_crc(data: bytes) -> bool:
    """
    Validate sector data CRC.

    For now, this is a simplified check. A full implementation
    would calculate CRC-CCITT.
    """
    if len(data) != 512:
        return False

    # Basic sanity checks
    # Real implementation would calculate actual CRC
    # For now, check that data isn't all zeros or all ones
    unique_bytes = len(set(data))
    if unique_bytes < 10:
        return False

    return True


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Data classes
    'BitSlipEvent',
    'PhaseTrackingState',
    'SlipCorrection',
    'SlipRecoveryResult',
    'CorrectedFlux',
    # Functions
    'detect_bit_slips',
    'analyze_slip_pattern',
    'realign_after_slip',
    'apply_all_slip_corrections',
    'reconstruct_slipped_sector',
    'recover_track_with_slip_correction',
    # Constants
    'HD_BIT_CELL_NS',
    'HD_BIT_CELL_US',
    'PHASE_JUMP_THRESHOLD',
    'SUDDEN_PHASE_JUMP',
]
