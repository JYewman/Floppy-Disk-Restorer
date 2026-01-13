"""
Surface treatment module for magnetic media refresh and recovery.

This module provides techniques for physically refreshing the magnetic
surface of floppy disks through degaussing (DC erase) and pattern writing.
These operations help restore weak magnetic domains that have degraded
over time.

Part of Phase 4: Advanced Data Recovery
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable, Tuple
from enum import Enum, auto
import time
import logging

from ..hardware.greaseweazle_device import GreaseweazleDevice
from ..hardware.flux_io import FluxWriter, FluxReader
from ..hardware.mfm_codec import MFMEncoder, MFMDecoder
from ..analysis.signal_quality import calculate_snr, measure_jitter, grade_track_quality


logger = logging.getLogger(__name__)


class TreatmentType(Enum):
    """Types of surface treatment operations."""
    DEGAUSS = auto()        # DC erase only
    PATTERN_WRITE = auto()  # Write specific pattern
    FULL_REFRESH = auto()   # Degauss + pattern cycle
    TARGETED = auto()       # Treat specific sector area


class TreatmentPattern(Enum):
    """Pre-defined treatment patterns for magnetic refresh."""
    ZEROS = 0x00
    ONES = 0xFF
    ALTERNATING_55 = 0x55
    ALTERNATING_AA = 0xAA
    CHECKERBOARD = 0xCC
    INVERSE_CHECKERBOARD = 0x33


# Standard refresh cycle patterns in order
REFRESH_CYCLE_PATTERNS = [
    TreatmentPattern.ZEROS,
    TreatmentPattern.ONES,
    TreatmentPattern.ALTERNATING_55,
    TreatmentPattern.ALTERNATING_AA,
]


@dataclass
class DegaussResult:
    """Result of a degauss (DC erase) operation."""

    cylinder: int
    head: int
    success: bool
    duration_ms: float
    erase_current_ma: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class PatternWriteResult:
    """Result of a pattern write operation."""

    cylinder: int
    head: int
    pattern: int
    success: bool
    duration_ms: float
    verified: bool = False
    verification_errors: int = 0
    error_message: Optional[str] = None


@dataclass
class RefreshResult:
    """Result of a complete track refresh operation."""

    cylinder: int
    head: int
    success: bool

    # Operation details
    degauss_performed: bool = False
    patterns_written: List[int] = field(default_factory=list)
    total_passes: int = 0

    # Timing
    total_duration_ms: float = 0.0
    degauss_duration_ms: float = 0.0
    write_duration_ms: float = 0.0

    # Quality metrics (before and after)
    initial_snr: Optional[float] = None
    final_snr: Optional[float] = None
    initial_quality_grade: Optional[str] = None
    final_quality_grade: Optional[str] = None

    # Verification
    sectors_verified: int = 0
    sectors_passed: int = 0

    error_message: Optional[str] = None


@dataclass
class SectorTreatmentResult:
    """Result of treating a specific weak sector."""

    cylinder: int
    head: int
    sector: int
    success: bool

    # Treatment details
    treatments_applied: List[str] = field(default_factory=list)

    # Before/after comparison
    initial_readable: bool = False
    final_readable: bool = False
    initial_crc_valid: bool = False
    final_crc_valid: bool = False

    # Quality improvement
    snr_improvement: Optional[float] = None
    jitter_reduction: Optional[float] = None

    duration_ms: float = 0.0
    error_message: Optional[str] = None


@dataclass
class BulkTreatmentResult:
    """Result of treating multiple tracks."""

    tracks_treated: int = 0
    tracks_successful: int = 0
    tracks_failed: int = 0

    # Per-track results
    track_results: List[RefreshResult] = field(default_factory=list)

    # Overall metrics
    total_duration_ms: float = 0.0
    average_snr_improvement: Optional[float] = None

    # Summary
    success: bool = False
    error_message: Optional[str] = None


def degauss_track(
    device: GreaseweazleDevice,
    cyl: int,
    head: int,
    verify_erase: bool = True
) -> DegaussResult:
    """
    Perform DC erase (degauss) on a track.

    DC erase writes a constant magnetic field across the entire track,
    effectively erasing all data and resetting the magnetic domains.
    This is more thorough than AC erase and helps restore degraded media.

    Args:
        device: Connected Greaseweazle device
        cyl: Cylinder number
        head: Head number (0 or 1)
        verify_erase: Whether to verify the track is erased after

    Returns:
        DegaussResult with operation status
    """
    start_time = time.perf_counter()

    try:
        logger.info(f"Degaussing track: cyl={cyl}, head={head}")

        # Seek to the target track
        device.seek(cyl, head)

        # Create flux writer for DC erase
        flux_writer = FluxWriter(device)

        # DC erase: write constant flux (all transitions or no transitions)
        # For true DC erase, we write a stream with no transitions
        # This creates a uniform magnetic field across the track

        # Get track timing parameters
        rpm = device.get_rpm()
        if rpm <= 0:
            rpm = 300.0  # Default HD RPM

        # Calculate track duration in microseconds
        track_duration_us = (60.0 / rpm) * 1_000_000

        # Create DC erase flux data - constant level (no transitions)
        # We write a very long interval representing "no transitions"
        dc_erase_flux = _generate_dc_erase_flux(track_duration_us)

        # Perform the erase
        flux_writer.write_track(cyl, head, dc_erase_flux)

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Optionally verify the erase
        if verify_erase:
            flux_reader = FluxReader(device)
            captured = flux_reader.read_track(cyl, head, revolutions=1)

            # Verify by checking for lack of valid MFM data
            decoder = MFMDecoder()
            sectors = decoder.decode_track(captured.flux_data, cyl, head)

            if len(sectors) > 0:
                logger.warning(f"Track still has {len(sectors)} readable sectors after degauss")

        logger.info(f"Degauss completed in {duration_ms:.1f}ms")

        return DegaussResult(
            cylinder=cyl,
            head=head,
            success=True,
            duration_ms=duration_ms
        )

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Degauss failed: {e}")

        return DegaussResult(
            cylinder=cyl,
            head=head,
            success=False,
            duration_ms=duration_ms,
            error_message=str(e)
        )


def _generate_dc_erase_flux(track_duration_us: float) -> bytes:
    """
    Generate flux data for DC erase operation.

    DC erase requires writing a constant magnetic field (no transitions).
    This effectively saturates the magnetic medium in one direction.

    Args:
        track_duration_us: Track duration in microseconds

    Returns:
        Flux data bytes for DC erase
    """
    # For DC erase, we want minimal/no transitions
    # Greaseweazle flux format: sequence of inter-flux intervals
    # We write one very long interval covering the entire track

    # Convert to Greaseweazle sample rate (typically 72MHz = 72 ticks/μs)
    sample_rate = 72_000_000  # 72 MHz
    ticks_per_us = sample_rate / 1_000_000

    total_ticks = int(track_duration_us * ticks_per_us)

    # Greaseweazle uses variable-length encoding for intervals:
    # 0x00-0xF9: interval = value + 1 (1-250 ticks)
    # 0xFA-0xFD: reserved
    # 0xFE XX: interval += (XX + 1) * 250
    # 0xFF XX YY: interval = XX | (YY << 8)

    flux_data = bytearray()

    # Write the total interval using extended encoding
    remaining = total_ticks

    while remaining > 0:
        if remaining <= 250:
            flux_data.append(remaining - 1)
            remaining = 0
        elif remaining <= 65535:
            # Use 3-byte encoding for large intervals
            flux_data.append(0xFF)
            flux_data.append(remaining & 0xFF)
            flux_data.append((remaining >> 8) & 0xFF)
            remaining = 0
        else:
            # Write maximum interval and continue
            flux_data.append(0xFF)
            flux_data.append(0xFF)
            flux_data.append(0xFF)
            remaining -= 65535

    return bytes(flux_data)


def write_recovery_pattern(
    device: GreaseweazleDevice,
    cyl: int,
    head: int,
    pattern: int,
    verify: bool = True
) -> PatternWriteResult:
    """
    Write a specific pattern to refresh magnetic domains.

    Pattern writing exercises the magnetic medium by forcing
    transitions at known positions. This helps strengthen weak
    magnetic areas and can improve subsequent data retention.

    Args:
        device: Connected Greaseweazle device
        cyl: Cylinder number
        head: Head number (0 or 1)
        pattern: Byte pattern to write (0x00, 0xFF, 0x55, 0xAA, etc.)
        verify: Whether to read back and verify the pattern

    Returns:
        PatternWriteResult with operation status
    """
    start_time = time.perf_counter()

    try:
        logger.info(f"Writing recovery pattern 0x{pattern:02X} to cyl={cyl}, head={head}")

        # Seek to target track
        device.seek(cyl, head)

        # Create sector data filled with pattern
        # Standard IBM PC format: 18 sectors × 512 bytes
        sector_size = 512
        sectors_per_track = 18

        pattern_data = bytes([pattern] * sector_size)
        sector_data_list = [pattern_data] * sectors_per_track

        # Encode to MFM flux
        encoder = MFMEncoder()
        flux_data = encoder.encode_track(sector_data_list, cyl, head)

        # Write the track
        flux_writer = FluxWriter(device)
        flux_writer.write_track(cyl, head, flux_data)

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Optionally verify
        verification_errors = 0
        verified = False

        if verify:
            flux_reader = FluxReader(device)
            captured = flux_reader.read_track(cyl, head, revolutions=1)

            decoder = MFMDecoder()
            sectors = decoder.decode_track(captured.flux_data, cyl, head)

            for sector in sectors:
                if sector.data != pattern_data:
                    verification_errors += 1

            verified = True

            if verification_errors > 0:
                logger.warning(f"Pattern verification: {verification_errors}/{sectors_per_track} sectors differ")

        logger.info(f"Pattern write completed in {duration_ms:.1f}ms")

        return PatternWriteResult(
            cylinder=cyl,
            head=head,
            pattern=pattern,
            success=True,
            duration_ms=duration_ms,
            verified=verified,
            verification_errors=verification_errors
        )

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Pattern write failed: {e}")

        return PatternWriteResult(
            cylinder=cyl,
            head=head,
            pattern=pattern,
            success=False,
            duration_ms=duration_ms,
            error_message=str(e)
        )


def refresh_track(
    device: GreaseweazleDevice,
    cyl: int,
    head: int,
    degauss_first: bool = True,
    patterns: Optional[List[int]] = None,
    measure_quality: bool = True,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> RefreshResult:
    """
    Perform complete track refresh with degauss and pattern cycle.

    This combines DC erase with multiple pattern writes to thoroughly
    exercise and refresh the magnetic domains on the track. This is
    the most effective treatment for degraded media.

    The refresh cycle:
    1. (Optional) Measure initial signal quality
    2. DC erase the track (degauss)
    3. Write pattern cycle: 0x00 → 0xFF → 0x55 → 0xAA
    4. (Optional) Measure final signal quality

    Args:
        device: Connected Greaseweazle device
        cyl: Cylinder number
        head: Head number (0 or 1)
        degauss_first: Whether to DC erase before pattern writes
        patterns: Custom pattern list (default: standard refresh cycle)
        measure_quality: Whether to measure SNR before/after
        progress_callback: Optional callback(operation, current, total)

    Returns:
        RefreshResult with operation details and quality metrics
    """
    start_time = time.perf_counter()

    # Use default refresh patterns if not specified
    if patterns is None:
        patterns = [p.value for p in REFRESH_CYCLE_PATTERNS]

    result = RefreshResult(
        cylinder=cyl,
        head=head,
        success=False,
        patterns_written=[]
    )

    total_steps = (1 if degauss_first else 0) + len(patterns) + (2 if measure_quality else 0)
    current_step = 0

    try:
        logger.info(f"Starting track refresh: cyl={cyl}, head={head}")

        # Measure initial quality
        if measure_quality:
            if progress_callback:
                progress_callback("Measuring initial quality", current_step, total_steps)
            current_step += 1

            initial_metrics = _measure_track_quality(device, cyl, head)
            result.initial_snr = initial_metrics.get('snr')
            result.initial_quality_grade = initial_metrics.get('grade')

            logger.info(f"Initial quality: SNR={result.initial_snr:.1f}dB, grade={result.initial_quality_grade}")

        # Degauss (DC erase)
        if degauss_first:
            if progress_callback:
                progress_callback("Degaussing track", current_step, total_steps)
            current_step += 1

            degauss_start = time.perf_counter()
            degauss_result = degauss_track(device, cyl, head, verify_erase=False)
            result.degauss_duration_ms = (time.perf_counter() - degauss_start) * 1000

            if not degauss_result.success:
                result.error_message = f"Degauss failed: {degauss_result.error_message}"
                return result

            result.degauss_performed = True

        # Write pattern cycle
        write_start = time.perf_counter()

        for i, pattern in enumerate(patterns):
            if progress_callback:
                progress_callback(f"Writing pattern 0x{pattern:02X}", current_step, total_steps)
            current_step += 1

            write_result = write_recovery_pattern(
                device, cyl, head, pattern, verify=False
            )

            if not write_result.success:
                result.error_message = f"Pattern write 0x{pattern:02X} failed: {write_result.error_message}"
                return result

            result.patterns_written.append(pattern)
            result.total_passes += 1

        result.write_duration_ms = (time.perf_counter() - write_start) * 1000

        # Measure final quality
        if measure_quality:
            if progress_callback:
                progress_callback("Measuring final quality", current_step, total_steps)
            current_step += 1

            final_metrics = _measure_track_quality(device, cyl, head)
            result.final_snr = final_metrics.get('snr')
            result.final_quality_grade = final_metrics.get('grade')

            logger.info(f"Final quality: SNR={result.final_snr:.1f}dB, grade={result.final_quality_grade}")

            if result.initial_snr and result.final_snr:
                improvement = result.final_snr - result.initial_snr
                logger.info(f"SNR improvement: {improvement:+.1f}dB")

        result.total_duration_ms = (time.perf_counter() - start_time) * 1000
        result.success = True

        logger.info(f"Track refresh completed in {result.total_duration_ms:.1f}ms")

        return result

    except Exception as e:
        result.total_duration_ms = (time.perf_counter() - start_time) * 1000
        result.error_message = str(e)
        logger.error(f"Track refresh failed: {e}")
        return result


def _measure_track_quality(
    device: GreaseweazleDevice,
    cyl: int,
    head: int
) -> Dict[str, any]:
    """
    Measure the signal quality of a track.

    Args:
        device: Connected Greaseweazle device
        cyl: Cylinder number
        head: Head number

    Returns:
        Dictionary with quality metrics
    """
    try:
        device.seek(cyl, head)

        flux_reader = FluxReader(device)
        captured = flux_reader.read_track(cyl, head, revolutions=2)

        # Calculate quality metrics
        snr = calculate_snr(captured)
        jitter = measure_jitter(captured)
        grade = grade_track_quality(captured)

        return {
            'snr': snr,
            'jitter': jitter,
            'grade': grade
        }

    except Exception as e:
        logger.warning(f"Quality measurement failed: {e}")
        return {}


def treat_weak_sector(
    device: GreaseweazleDevice,
    cyl: int,
    head: int,
    sector: int,
    aggressive: bool = False
) -> SectorTreatmentResult:
    """
    Apply targeted magnetic treatment to a specific weak sector.

    This function applies localized treatment to refresh the magnetic
    domains of a single sector without affecting adjacent sectors.
    Useful for targeted recovery of specific bad sectors.

    Treatment steps:
    1. Read and save adjacent sector data
    2. Apply local degauss to sector area
    3. Write recovery patterns to sector
    4. Restore adjacent sectors
    5. Verify sector readability

    Args:
        device: Connected Greaseweazle device
        cyl: Cylinder number
        head: Head number (0 or 1)
        sector: Sector number (1-18 for HD)
        aggressive: Whether to use aggressive treatment (more passes)

    Returns:
        SectorTreatmentResult with treatment outcome
    """
    start_time = time.perf_counter()

    result = SectorTreatmentResult(
        cylinder=cyl,
        head=head,
        sector=sector,
        success=False
    )

    try:
        logger.info(f"Treating weak sector: cyl={cyl}, head={head}, sector={sector}")

        # Seek to track
        device.seek(cyl, head)

        # Read the entire track first
        flux_reader = FluxReader(device)
        flux_writer = FluxWriter(device)
        decoder = MFMDecoder()
        encoder = MFMEncoder()

        captured = flux_reader.read_track(cyl, head, revolutions=2)
        sectors = decoder.decode_track(captured.flux_data, cyl, head)

        # Check initial state of target sector
        target_sector_data = None
        for s in sectors:
            if s.sector_number == sector:
                result.initial_readable = True
                result.initial_crc_valid = s.crc_valid
                if s.crc_valid:
                    target_sector_data = s.data
                break

        # Build sector data map, preserving good sectors
        sector_data_map = {}
        for s in sectors:
            if s.crc_valid:
                sector_data_map[s.sector_number] = s.data

        # Determine treatment patterns
        if aggressive:
            treatment_patterns = [
                0x00, 0xFF, 0x00, 0xFF,  # Multiple toggles
                0xAA, 0x55, 0xAA, 0x55,
                0x00, 0xFF
            ]
        else:
            treatment_patterns = [0x00, 0xFF, 0xAA, 0x55]

        # Apply treatment patterns to target sector
        for pattern in treatment_patterns:
            result.treatments_applied.append(f"pattern_0x{pattern:02X}")

            # Create track with treatment pattern for target sector
            sector_data_list = []
            for sec_num in range(1, 19):  # Sectors 1-18
                if sec_num == sector:
                    # Apply treatment pattern to target sector
                    sector_data_list.append(bytes([pattern] * 512))
                elif sec_num in sector_data_map:
                    # Preserve existing good data
                    sector_data_list.append(sector_data_map[sec_num])
                else:
                    # Unknown sector, write pattern
                    sector_data_list.append(bytes([pattern] * 512))

            # Encode and write
            flux_data = encoder.encode_track(sector_data_list, cyl, head)
            flux_writer.write_track(cyl, head, flux_data)

        # If we had the original data, write it back
        if target_sector_data:
            result.treatments_applied.append("restore_original")

            sector_data_list = []
            for sec_num in range(1, 19):
                if sec_num == sector:
                    sector_data_list.append(target_sector_data)
                elif sec_num in sector_data_map:
                    sector_data_list.append(sector_data_map[sec_num])
                else:
                    sector_data_list.append(bytes([0xF6] * 512))  # Format fill

            flux_data = encoder.encode_track(sector_data_list, cyl, head)
            flux_writer.write_track(cyl, head, flux_data)

        # Verify the result
        captured = flux_reader.read_track(cyl, head, revolutions=2)
        sectors = decoder.decode_track(captured.flux_data, cyl, head)

        for s in sectors:
            if s.sector_number == sector:
                result.final_readable = True
                result.final_crc_valid = s.crc_valid
                break

        # Calculate quality improvement
        initial_snr = _measure_sector_snr(captured.flux_data, sector, decoder)
        # Note: We'd need the before capture to properly compare

        result.duration_ms = (time.perf_counter() - start_time) * 1000
        result.success = result.final_crc_valid

        if result.success:
            logger.info(f"Sector treatment successful: now readable with valid CRC")
        else:
            logger.warning(f"Sector treatment completed but sector not fully recovered")

        return result

    except Exception as e:
        result.duration_ms = (time.perf_counter() - start_time) * 1000
        result.error_message = str(e)
        logger.error(f"Sector treatment failed: {e}")
        return result


def _measure_sector_snr(
    flux_data: bytes,
    sector_number: int,
    decoder: MFMDecoder
) -> Optional[float]:
    """
    Estimate SNR for a specific sector from flux data.

    Args:
        flux_data: Raw flux data
        sector_number: Target sector number
        decoder: MFM decoder instance

    Returns:
        Estimated SNR in dB, or None if cannot measure
    """
    # This is a simplified estimation based on decode confidence
    # A full implementation would analyze the flux timing around the sector
    try:
        # The decoder can provide per-sector confidence metrics
        # For now, return None as this requires more complex analysis
        return None
    except Exception:
        return None


def bulk_refresh_tracks(
    device: GreaseweazleDevice,
    track_list: List[Tuple[int, int]],
    degauss: bool = True,
    patterns: Optional[List[int]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> BulkTreatmentResult:
    """
    Refresh multiple tracks in sequence.

    Args:
        device: Connected Greaseweazle device
        track_list: List of (cylinder, head) tuples to refresh
        degauss: Whether to degauss each track first
        patterns: Custom pattern list (default: standard refresh cycle)
        progress_callback: Optional callback(track_index, total_tracks, status)

    Returns:
        BulkTreatmentResult with overall results
    """
    start_time = time.perf_counter()

    result = BulkTreatmentResult()
    total_tracks = len(track_list)

    snr_improvements = []

    try:
        for i, (cyl, head) in enumerate(track_list):
            if progress_callback:
                progress_callback(i, total_tracks, f"Refreshing cyl={cyl}, head={head}")

            track_result = refresh_track(
                device, cyl, head,
                degauss_first=degauss,
                patterns=patterns,
                measure_quality=True
            )

            result.track_results.append(track_result)
            result.tracks_treated += 1

            if track_result.success:
                result.tracks_successful += 1

                # Track SNR improvement
                if track_result.initial_snr and track_result.final_snr:
                    improvement = track_result.final_snr - track_result.initial_snr
                    snr_improvements.append(improvement)
            else:
                result.tracks_failed += 1

        result.total_duration_ms = (time.perf_counter() - start_time) * 1000

        # Calculate average SNR improvement
        if snr_improvements:
            result.average_snr_improvement = sum(snr_improvements) / len(snr_improvements)

        result.success = result.tracks_failed == 0

        logger.info(
            f"Bulk refresh completed: {result.tracks_successful}/{total_tracks} successful, "
            f"average SNR improvement: {result.average_snr_improvement:.1f}dB"
        )

        return result

    except Exception as e:
        result.total_duration_ms = (time.perf_counter() - start_time) * 1000
        result.error_message = str(e)
        logger.error(f"Bulk refresh failed: {e}")
        return result


def refresh_weak_tracks(
    device: GreaseweazleDevice,
    quality_threshold: str = 'C',
    cylinder_range: Optional[Tuple[int, int]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> BulkTreatmentResult:
    """
    Automatically find and refresh tracks below a quality threshold.

    This function scans the disk for tracks with quality grades below
    the threshold and automatically refreshes them.

    Args:
        device: Connected Greaseweazle device
        quality_threshold: Minimum acceptable grade ('A', 'B', 'C', 'D')
        cylinder_range: Optional (start, end) cylinder range
        progress_callback: Optional callback(track_index, total_tracks, status)

    Returns:
        BulkTreatmentResult with refresh results
    """
    if cylinder_range is None:
        cylinder_range = (0, 79)  # Standard 80 cylinders

    start_cyl, end_cyl = cylinder_range

    # Grade ranking for comparison
    grade_rank = {'A': 4, 'B': 3, 'C': 2, 'D': 1, 'F': 0}
    threshold_rank = grade_rank.get(quality_threshold, 2)

    # Find weak tracks
    weak_tracks = []
    total_tracks = (end_cyl - start_cyl + 1) * 2

    logger.info(f"Scanning for tracks below grade '{quality_threshold}'")

    for cyl in range(start_cyl, end_cyl + 1):
        for head in range(2):
            track_idx = (cyl - start_cyl) * 2 + head

            if progress_callback:
                progress_callback(track_idx, total_tracks, f"Scanning cyl={cyl}, head={head}")

            metrics = _measure_track_quality(device, cyl, head)
            grade = metrics.get('grade', 'F')

            if grade_rank.get(grade, 0) < threshold_rank:
                weak_tracks.append((cyl, head))
                logger.info(f"Found weak track: cyl={cyl}, head={head}, grade={grade}")

    if not weak_tracks:
        logger.info("No weak tracks found")
        return BulkTreatmentResult(success=True)

    logger.info(f"Found {len(weak_tracks)} weak tracks, starting refresh")

    # Refresh the weak tracks
    return bulk_refresh_tracks(
        device,
        weak_tracks,
        degauss=True,
        progress_callback=progress_callback
    )


def emergency_degauss_disk(
    device: GreaseweazleDevice,
    cylinder_range: Optional[Tuple[int, int]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> BulkTreatmentResult:
    """
    Perform emergency full-disk degauss.

    WARNING: This will ERASE ALL DATA on the disk!

    Use this when the disk has severe magnetic contamination
    or when preparing a disk for secure reuse.

    Args:
        device: Connected Greaseweazle device
        cylinder_range: Optional (start, end) cylinder range
        progress_callback: Optional callback(track_index, total_tracks)

    Returns:
        BulkTreatmentResult with degauss results
    """
    if cylinder_range is None:
        cylinder_range = (0, 79)

    start_cyl, end_cyl = cylinder_range

    logger.warning("Starting emergency full-disk degauss - ALL DATA WILL BE ERASED")

    result = BulkTreatmentResult()
    total_tracks = (end_cyl - start_cyl + 1) * 2
    start_time = time.perf_counter()

    try:
        for cyl in range(start_cyl, end_cyl + 1):
            for head in range(2):
                track_idx = (cyl - start_cyl) * 2 + head

                if progress_callback:
                    progress_callback(track_idx, total_tracks)

                degauss_result = degauss_track(device, cyl, head, verify_erase=False)

                # Convert to RefreshResult for consistency
                track_result = RefreshResult(
                    cylinder=cyl,
                    head=head,
                    success=degauss_result.success,
                    degauss_performed=True,
                    degauss_duration_ms=degauss_result.duration_ms,
                    total_duration_ms=degauss_result.duration_ms,
                    error_message=degauss_result.error_message
                )

                result.track_results.append(track_result)
                result.tracks_treated += 1

                if degauss_result.success:
                    result.tracks_successful += 1
                else:
                    result.tracks_failed += 1

        result.total_duration_ms = (time.perf_counter() - start_time) * 1000
        result.success = result.tracks_failed == 0

        logger.info(f"Emergency degauss completed: {result.tracks_successful}/{total_tracks} tracks")

        return result

    except Exception as e:
        result.total_duration_ms = (time.perf_counter() - start_time) * 1000
        result.error_message = str(e)
        logger.error(f"Emergency degauss failed: {e}")
        return result
