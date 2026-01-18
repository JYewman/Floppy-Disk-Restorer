"""
Sector-level adapter for Greaseweazle flux operations.

This module provides the adapter layer between sector-level operations
(as used by recovery.py, scanner.py, formatter.py) and flux-level operations
(as provided by the Greaseweazle hardware module).

The adapter translates traditional sector read/write calls into:
1. Seek to the correct track
2. Read raw flux data
3. Decode MFM to extract sectors (for reads)
4. Encode sectors to MFM flux (for writes)
5. Write flux to disk

This preserves all existing recovery algorithms while enabling flux-level
analysis and advanced recovery techniques.
"""

import time
import logging
from typing import Tuple, List, Dict, Optional, Any
from dataclasses import dataclass

from floppy_formatter.hardware import (
    GreaseweazleDevice,
    FluxData,
    SectorData,
    SectorStatus,
    decode_flux_data,
    encode_sectors_to_flux,
    create_formatted_track,
    create_pattern_track,
    read_track_flux,
    write_track_flux,
    erase_track_flux,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (preserved from sector_io.py for backward compatibility)
# =============================================================================

# Standard bytes per sector
BYTES_PER_SECTOR = 512

# Error codes (compatible with existing code)
ERROR_SUCCESS = 0
ERROR_PERMISSION_DENIED = 13  # EACCES
ERROR_NOT_READY = 19          # ENODEV
ERROR_WRITE_PROTECT = 30      # EROFS
ERROR_CRC = 5                 # EIO
ERROR_READ_FAULT = 5          # EIO
ERROR_WRITE_FAULT = 5         # EIO
ERROR_SECTOR_NOT_FOUND = 6    # ENXIO

# Motor and timing constants
_MOTOR_SPINDOWN_TIMEOUT = 30.0
_MOTOR_SPINUP_DELAY = 0.8
_BASE_RECOVERY_DELAY = 0.2
_MOTOR_KEEPALIVE_INTERVAL = 5.0

# Pattern constants (preserved from sector_io.py)
PATTERN_ALTERNATING_LOW = 0x55   # 01010101 - Alternating bits starting low
PATTERN_ALTERNATING_HIGH = 0xAA  # 10101010 - Alternating bits starting high
PATTERN_ALL_SET = 0xFF           # 11111111 - All bits set
PATTERN_ALL_CLEAR = 0x00         # 00000000 - All bits clear

# Pattern rotation sequence for multi-pass recovery
PATTERN_SEQUENCE = [
    PATTERN_ALTERNATING_LOW,   # Pass 0, 4, 8, ...
    PATTERN_ALTERNATING_HIGH,  # Pass 1, 5, 9, ...
    PATTERN_ALL_SET,           # Pass 2, 6, 10, ...
    PATTERN_ALL_CLEAR,         # Pass 3, 7, 11, ...
]

# Track state tracking
_last_activity_time = 0.0
_consecutive_errors = 0
_last_successful_read_time = 0.0


# =============================================================================
# Track Cache for Efficient Operations
# =============================================================================

@dataclass
class TrackCache:
    """
    Cache for decoded track data to avoid redundant flux reads.

    When reading multiple sectors from the same track, we read the flux
    once and decode all sectors, then serve subsequent reads from cache.
    """
    cylinder: int
    head: int
    sectors: Dict[int, SectorData]
    flux_data: Optional[FluxData]
    timestamp: float

    def is_valid(self, max_age: float = 1.0) -> bool:
        """Check if cache is still valid (not too old)."""
        return (time.time() - self.timestamp) < max_age

    def get_sector(self, sector_num: int) -> Optional[SectorData]:
        """Get a sector from cache if available."""
        return self.sectors.get(sector_num)


# Global track cache (one track at a time)
_track_cache: Optional[TrackCache] = None


def invalidate_track_cache() -> None:
    """Invalidate the track cache (call after writes)."""
    global _track_cache
    _track_cache = None


def _cache_track(device: GreaseweazleDevice, cylinder: int, head: int,
                 revolutions: float = 1.2) -> TrackCache:
    """
    Read and cache a track's flux data and decoded sectors.

    Args:
        device: Connected Greaseweazle device
        cylinder: Cylinder number
        head: Head number
        revolutions: Number of revolutions to capture

    Returns:
        TrackCache with decoded sectors
    """
    global _track_cache

    # Check if we already have this track cached
    if (_track_cache is not None
            and _track_cache.cylinder == cylinder
            and _track_cache.head == head
            and _track_cache.is_valid()):
        return _track_cache

    # Read flux data from track
    flux_data = read_track_flux(device, cylinder, head, revolutions)

    # Decode sectors from flux
    decoded_sectors = decode_flux_data(flux_data)

    # Build sector dictionary (sector number -> SectorData)
    sectors_dict = {s.sector: s for s in decoded_sectors}

    # Create and store cache
    _track_cache = TrackCache(
        cylinder=cylinder,
        head=head,
        sectors=sectors_dict,
        flux_data=flux_data,
        timestamp=time.time()
    )

    return _track_cache


# =============================================================================
# Sector Reading Operations
# =============================================================================

def read_sector(device: GreaseweazleDevice, cylinder: int, head: int,
                sector: int, bytes_per_sector: int = BYTES_PER_SECTOR
                ) -> Tuple[bool, Optional[bytes], int]:
    """
    Read a single sector from the disk using flux capture and MFM decoding.

    This function reads the entire track's flux data, decodes all sectors,
    and returns the requested sector. The track is cached for efficiency
    when reading multiple sectors from the same track.

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder number (0-79 for 3.5" HD)
        head: Head number (0 or 1)
        sector: Sector number (1-18 for standard PC format)
        bytes_per_sector: Expected sector size (default 512)

    Returns:
        Tuple of (success, data, error_code):
        - success: True if read succeeded
        - data: Sector data (512 bytes) if successful, None if failed
        - error_code: 0 if successful, error code if failed

    Example:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     success, data, error = read_sector(device, 0, 0, 1)
        ...     if success:
        ...         print(f"Read {len(data)} bytes from sector 1")
    """
    global _consecutive_errors, _last_successful_read_time, _last_activity_time

    logger.debug("read_sector: C%d H%d S%d", cylinder, head, sector)

    try:
        # Cache track data (reads flux if not cached)
        track_cache = _cache_track(device, cylinder, head)

        # Get the requested sector from cache
        sector_data = track_cache.get_sector(sector)

        if sector_data is None:
            # Sector not found in decoded data
            logger.debug("read_sector: sector %d not found in decoded track", sector)
            _consecutive_errors += 1
            return (False, None, ERROR_SECTOR_NOT_FOUND)

        # Check if sector was decoded successfully
        if not sector_data.is_good:
            # Sector has errors (CRC failure, etc.)
            logger.debug(
                "read_sector: sector %d has status %s",
                sector, sector_data.status.name
            )
            _consecutive_errors += 1
            if sector_data.status == SectorStatus.CRC_ERROR:
                return (False, None, ERROR_CRC)
            elif sector_data.status == SectorStatus.MISSING:
                return (False, None, ERROR_SECTOR_NOT_FOUND)
            else:
                return (False, None, ERROR_READ_FAULT)

        # Success
        _consecutive_errors = 0
        _last_successful_read_time = time.time()
        _last_activity_time = time.time()

        return (True, sector_data.data, ERROR_SUCCESS)

    except Exception as e:
        logger.error("read_sector: exception: %s", e)
        _consecutive_errors += 1
        return (False, None, ERROR_READ_FAULT)


def read_sector_by_lba(device: GreaseweazleDevice, lba: int,
                       geometry: Any,
                       bytes_per_sector: int = BYTES_PER_SECTOR
                       ) -> Tuple[bool, Optional[bytes], int]:
    """
    Read a sector by linear block address (LBA).

    Converts LBA to CHS and reads the sector.

    Args:
        device: Connected GreaseweazleDevice instance
        lba: Linear sector number (0-2879 for 1.44MB)
        geometry: DiskGeometry object
        bytes_per_sector: Expected sector size

    Returns:
        Same as read_sector()
    """
    # Convert LBA to CHS
    sectors_per_track = geometry.sectors_per_track
    heads = geometry.heads

    sectors_per_cylinder = sectors_per_track * heads
    cylinder = lba // sectors_per_cylinder
    remainder = lba % sectors_per_cylinder
    head = remainder // sectors_per_track
    sector = (remainder % sectors_per_track) + 1  # Sectors are 1-indexed

    return read_sector(device, cylinder, head, sector, bytes_per_sector)


def read_track(device: GreaseweazleDevice, cylinder: int, head: int,
               geometry: Any) -> Tuple[int, List[Dict]]:
    """
    Read all sectors in a track.

    More efficient than reading sectors individually as it only
    captures flux once and decodes all sectors.

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder number (0-79)
        head: Head number (0 or 1)
        geometry: DiskGeometry object

    Returns:
        Tuple of (success_count, results):
        - success_count: Number of sectors read successfully
        - results: List of dicts with keys:
            - 'sector': Sector number
            - 'success': True if read succeeded
            - 'data': Sector data (bytes) if successful, None if failed
            - 'error': Error code
    """
    results = []
    success_count = 0

    # Read and cache the track
    try:
        track_cache = _cache_track(device, cylinder, head)
    except Exception as e:
        logger.error("read_track: failed to read track: %s", e)
        # Return all sectors as failed
        for sector_num in range(1, geometry.sectors_per_track + 1):
            results.append({
                'sector': sector_num,
                'success': False,
                'data': None,
                'error': ERROR_READ_FAULT
            })
        return (0, results)

    # Extract results for each sector
    for sector_num in range(1, geometry.sectors_per_track + 1):
        sector_data = track_cache.get_sector(sector_num)

        if sector_data is not None and sector_data.is_good:
            results.append({
                'sector': sector_num,
                'success': True,
                'data': sector_data.data,
                'error': ERROR_SUCCESS
            })
            success_count += 1
        elif sector_data is not None:
            # Sector found but has errors
            error = ERROR_CRC if sector_data.status == SectorStatus.CRC_ERROR else ERROR_READ_FAULT
            results.append({
                'sector': sector_num,
                'success': False,
                'data': None,
                'error': error
            })
        else:
            # Sector not found
            results.append({
                'sector': sector_num,
                'success': False,
                'data': None,
                'error': ERROR_SECTOR_NOT_FOUND
            })

    return (success_count, results)


def read_sector_multiread(device: GreaseweazleDevice, cylinder: int, head: int,
                          sector: int, max_attempts: int = 100,
                          bytes_per_sector: int = BYTES_PER_SECTOR
                          ) -> Tuple[bool, Optional[bytes], int, int]:
    """
    Read a sector using multiple flux captures with statistical analysis.

    This function captures multiple revolutions of flux data and uses
    statistical bit voting to reconstruct marginal sector data. This is
    the Greaseweazle-enhanced version of the original read_sector_multiread.

    The algorithm:
    1. Capture multiple revolutions of flux data
    2. Decode each revolution independently
    3. Use majority voting on each byte position across all reads
    4. Return reconstructed data even if no single read was perfect

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder number
        head: Head number
        sector: Sector number
        max_attempts: Number of flux captures/revolutions to analyze
        bytes_per_sector: Expected sector size

    Returns:
        Tuple of (success, data, error_code, successful_reads):
        - success: True if data was reconstructed
        - data: Reconstructed sector data or None
        - error_code: 0 if successful, last error code if failed
        - successful_reads: Number of successful decode attempts
    """
    logger.debug("read_sector_multiread: C%d H%d S%d attempts=%d",
                 cylinder, head, sector, max_attempts)

    # Invalidate cache since we need fresh reads
    invalidate_track_cache()

    successful_reads = []
    last_error = ERROR_CRC

    # Calculate revolutions needed (each revolution is one read attempt)
    # We'll capture in batches to be efficient
    revolutions_per_capture = min(10, max_attempts)
    num_captures = (max_attempts + revolutions_per_capture - 1) // revolutions_per_capture

    for capture_num in range(num_captures):
        try:
            # Capture multiple revolutions at once
            revolutions = min(
                revolutions_per_capture, max_attempts - len(successful_reads)
            )

            flux_data = read_track_flux(
                device, cylinder, head, revolutions=float(revolutions + 0.2)
            )

            # Try to extract sector data from each revolution
            for rev in range(int(revolutions)):
                try:
                    rev_flux = flux_data.get_revolution_data(rev)
                    decoded = decode_flux_data(rev_flux)

                    # Find our target sector
                    for s in decoded:
                        if s.sector == sector:
                            if s.is_good:
                                successful_reads.append(s.data)
                            elif s.data and len(s.data) == bytes_per_sector:
                                # Even bad CRC data is useful for voting
                                successful_reads.append(s.data)
                            break

                except (ValueError, IndexError):
                    # Revolution extraction failed
                    continue

        except Exception as e:
            logger.debug(
                "read_sector_multiread: capture %d failed: %s",
                capture_num, e
            )
            continue

        # Early exit if we have enough good reads
        if len(successful_reads) >= max_attempts:
            break

    # If no successful reads at all, fail
    if len(successful_reads) == 0:
        return (False, None, last_error, 0)

    # If only one read, return it directly
    if len(successful_reads) == 1:
        return (True, successful_reads[0], ERROR_SUCCESS, 1)

    # Statistical reconstruction using majority voting
    reconstructed = bytearray(bytes_per_sector)

    for byte_pos in range(bytes_per_sector):
        byte_votes = {}
        for read_data in successful_reads:
            if byte_pos < len(read_data):
                byte_value = read_data[byte_pos]
                byte_votes[byte_value] = byte_votes.get(byte_value, 0) + 1

        if byte_votes:
            most_common = max(byte_votes.keys(), key=lambda k: byte_votes[k])
            reconstructed[byte_pos] = most_common

    logger.debug("read_sector_multiread: reconstructed from %d reads",
                 len(successful_reads))

    return (True, bytes(reconstructed), ERROR_SUCCESS, len(successful_reads))


# =============================================================================
# Sector Writing Operations
# =============================================================================

def write_sector(device: GreaseweazleDevice, cylinder: int, head: int,
                 sector: int, data: bytes,
                 bytes_per_sector: int = BYTES_PER_SECTOR) -> Tuple[bool, int]:
    """
    Write a single sector to the disk.

    Since MFM encoding requires writing a complete track, this function:
    1. Reads the existing track data
    2. Replaces the target sector
    3. Encodes and writes the complete track

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder number
        head: Head number
        sector: Sector number (1-18)
        data: Sector data to write (must be exactly bytes_per_sector)
        bytes_per_sector: Expected sector size

    Returns:
        Tuple of (success, error_code)

    Raises:
        ValueError: If data is not the correct size
    """
    global _consecutive_errors, _last_activity_time

    if len(data) != bytes_per_sector:
        raise ValueError(f"Data must be {bytes_per_sector} bytes, got {len(data)}")

    logger.debug("write_sector: C%d H%d S%d", cylinder, head, sector)

    try:
        # Read existing track to preserve other sectors
        track_cache = _cache_track(device, cylinder, head)

        # Build sector list for encoding
        sectors = []
        for sector_num in range(1, 19):  # Standard 18 sectors
            if sector_num == sector:
                # Use new data for target sector
                sectors.append(SectorData(
                    cylinder=cylinder,
                    head=head,
                    sector=sector_num,
                    data=data,
                    status=SectorStatus.GOOD,
                    crc_valid=True,
                    signal_quality=1.0
                ))
            else:
                # Use existing data or zeros
                existing = track_cache.get_sector(sector_num)
                if existing and existing.data:
                    sectors.append(existing)
                else:
                    # Fill missing sectors with zeros
                    sectors.append(SectorData(
                        cylinder=cylinder,
                        head=head,
                        sector=sector_num,
                        data=bytes(bytes_per_sector),
                        status=SectorStatus.GOOD,
                        crc_valid=True,
                        signal_quality=1.0
                    ))

        # Encode and write the track
        flux_data = encode_sectors_to_flux(cylinder, head, sectors)
        write_track_flux(device, cylinder, head, flux_data, erase_first=True)

        # Invalidate cache since track was modified
        invalidate_track_cache()

        _consecutive_errors = 0
        _last_activity_time = time.time()

        return (True, ERROR_SUCCESS)

    except Exception as e:
        logger.error("write_sector: exception: %s", e)
        _consecutive_errors += 1
        return (False, ERROR_WRITE_FAULT)


def write_track(device: GreaseweazleDevice, cylinder: int, head: int,
                sector_data_list: List[Tuple[int, bytes]],
                geometry: Any) -> Tuple[int, List[Dict]]:
    """
    Write multiple sectors to a track at once.

    More efficient than writing sectors individually.

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder number
        head: Head number
        sector_data_list: List of (sector_number, data) tuples
        geometry: DiskGeometry object

    Returns:
        Tuple of (success_count, results)
    """
    logger.debug(
        "write_track: C%d H%d %d sectors",
        cylinder, head, len(sector_data_list)
    )

    # Build sector data dictionary
    data_dict = {s[0]: s[1] for s in sector_data_list}

    # Build complete sector list
    sectors = []
    for sector_num in range(1, geometry.sectors_per_track + 1):
        if sector_num in data_dict:
            sectors.append(SectorData(
                cylinder=cylinder,
                head=head,
                sector=sector_num,
                data=data_dict[sector_num],
                status=SectorStatus.GOOD,
                crc_valid=True,
                signal_quality=1.0
            ))
        else:
            # Fill with zeros for sectors not specified
            sectors.append(SectorData(
                cylinder=cylinder,
                head=head,
                sector=sector_num,
                data=bytes(geometry.bytes_per_sector),
                status=SectorStatus.GOOD,
                crc_valid=True,
                signal_quality=1.0
            ))

    try:
        # Encode and write
        flux_data = encode_sectors_to_flux(cylinder, head, sectors)
        write_track_flux(device, cylinder, head, flux_data, erase_first=True)

        # Invalidate cache
        invalidate_track_cache()

        # Build results
        results = []
        for sector_num, data in sector_data_list:
            results.append({
                'sector': sector_num,
                'success': True,
                'error': ERROR_SUCCESS
            })

        return (len(sector_data_list), results)

    except Exception as e:
        logger.error("write_track: exception: %s", e)
        # All sectors failed
        results = []
        for sector_num, data in sector_data_list:
            results.append({
                'sector': sector_num,
                'success': False,
                'error': ERROR_WRITE_FAULT
            })
        return (0, results)


def write_track_pattern(device: GreaseweazleDevice, cylinder: int, head: int,
                        pattern_byte: int, geometry: Any) -> Tuple[int, List[Dict]]:
    """
    Write a magnetic pattern to all sectors in a track.

    Pattern writing "exercises" magnetic domains and is used during
    recovery operations to refresh weak areas of the disk.

    This preserves the pattern rotation behavior from the original
    recovery algorithms (0x00, 0xFF, 0xAA, 0x55).

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder number
        head: Head number
        pattern_byte: Pattern value (0x00-0xFF)
        geometry: DiskGeometry object

    Returns:
        Tuple of (success_count, results)
    """
    logger.debug(
        "write_track_pattern: C%d H%d pattern=0x%02X",
        cylinder, head, pattern_byte
    )

    try:
        # Create pattern-filled sectors using MFM codec helper
        sectors = create_pattern_track(
            cylinder, head,
            pattern=bytes([pattern_byte]),
            sector_count=geometry.sectors_per_track,
            sector_size=geometry.bytes_per_sector
        )

        # Encode and write
        flux_data = encode_sectors_to_flux(cylinder, head, sectors)
        write_track_flux(device, cylinder, head, flux_data, erase_first=True)

        # Invalidate cache
        invalidate_track_cache()

        # Build results
        results = []
        for sector_num in range(1, geometry.sectors_per_track + 1):
            results.append({
                'sector': sector_num,
                'success': True,
                'error': ERROR_SUCCESS
            })

        return (geometry.sectors_per_track, results)

    except Exception as e:
        logger.error("write_track_pattern: exception: %s", e)
        results = []
        for sector_num in range(1, geometry.sectors_per_track + 1):
            results.append({
                'sector': sector_num,
                'success': False,
                'error': ERROR_WRITE_FAULT
            })
        return (0, results)


def format_track_low_level(
    device: GreaseweazleDevice, cylinder: int, head: int,
    geometry: Any, fill_byte: int = 0x00
) -> Tuple[bool, int, List[int], int]:
    """
    Low-level track format using Greaseweazle.

    This replaces the USB floppy's sector-by-sector format with a proper
    track-level format using DC erase followed by MFM encoding.

    Args:
        device: Connected GreaseweazleDevice instance
        cylinder: Cylinder number
        head: Head number
        geometry: DiskGeometry object
        fill_byte: Byte to fill formatted sectors with (default 0x00)

    Returns:
        Tuple of (success, bad_sector_count, bad_sectors, error_code)
    """
    logger.debug(
        "format_track_low_level: C%d H%d fill=0x%02X",
        cylinder, head, fill_byte
    )

    try:
        # Erase the track first (DC erase)
        erase_track_flux(device, cylinder, head)

        # Create freshly formatted sectors
        sectors = create_formatted_track(
            cylinder, head,
            fill_byte=fill_byte,
            sector_count=geometry.sectors_per_track,
            sector_size=geometry.bytes_per_sector
        )

        # Encode and write
        flux_data = encode_sectors_to_flux(cylinder, head, sectors)
        write_track_flux(device, cylinder, head, flux_data, erase_first=False)

        # Invalidate cache
        invalidate_track_cache()

        # Verify by reading back
        # Re-read the track and check for errors
        verify_cache = _cache_track(device, cylinder, head)

        bad_sectors = []
        for sector_num in range(1, geometry.sectors_per_track + 1):
            sector_data = verify_cache.get_sector(sector_num)
            if sector_data is None or not sector_data.is_good:
                bad_sectors.append(sector_num)

        if len(bad_sectors) == 0:
            return (True, 0, [], ERROR_SUCCESS)
        elif len(bad_sectors) < geometry.sectors_per_track:
            return (True, len(bad_sectors), bad_sectors, ERROR_SUCCESS)
        else:
            return (False, len(bad_sectors), bad_sectors, ERROR_WRITE_FAULT)

    except Exception as e:
        logger.error("format_track_low_level: exception: %s", e)
        return (False, geometry.sectors_per_track,
                list(range(1, geometry.sectors_per_track + 1)),
                ERROR_WRITE_FAULT)


# =============================================================================
# Cache and Motor Management
# =============================================================================

def flush_flux_cache(device: GreaseweazleDevice) -> None:
    """
    Flush the internal flux cache and prepare for fresh reads.

    This is the Greaseweazle equivalent of the BLKFLSBUF ioctl used
    with USB floppy drives. It ensures subsequent reads get fresh
    data from the physical disk.

    Unlike USB floppy drives, Greaseweazle doesn't have a kernel buffer
    cache issue, but we do have our internal track cache that needs
    invalidation.

    Args:
        device: Connected GreaseweazleDevice instance (not used, but
                kept for interface compatibility)
    """
    global _track_cache

    logger.debug("flush_flux_cache: invalidating track cache")
    _track_cache = None


def wake_up_device(device: GreaseweazleDevice) -> bool:
    """
    Wake up the floppy drive motor if it may have spun down.

    With Greaseweazle, we have direct motor control, so we can
    simply ensure the motor is on.

    Args:
        device: Connected GreaseweazleDevice instance

    Returns:
        True if device is ready
    """
    global _consecutive_errors

    logger.debug("wake_up_device: ensuring motor is on")

    try:
        if not device.is_motor_on():
            device.motor_on()
            # Wait for motor to spin up
            time.sleep(_MOTOR_SPINUP_DELAY)

        _consecutive_errors = 0
        return True

    except Exception as e:
        logger.error("wake_up_device: exception: %s", e)
        return False


def motor_keepalive(device: GreaseweazleDevice) -> bool:
    """
    Keep the motor running during long operations.

    With Greaseweazle, we have direct motor control (no firmware timeout),
    so this is a no-op. The motor stays on until we explicitly turn it off.

    Args:
        device: Connected GreaseweazleDevice instance

    Returns:
        True (always succeeds with Greaseweazle)
    """
    global _last_activity_time
    _last_activity_time = time.time()
    return True


def reset_error_tracking() -> None:
    """
    Reset the consecutive error counter and last read time.

    Call this when starting a new operation.
    """
    global _consecutive_errors, _last_successful_read_time, _last_activity_time
    _consecutive_errors = 0
    _last_successful_read_time = time.time()
    _last_activity_time = time.time()


def should_attempt_usb_reset() -> bool:
    """
    Check if a USB reset might help (not needed for Greaseweazle).

    Returns:
        False (Greaseweazle doesn't need USB reset recovery)
    """
    return False


# =============================================================================
# Pattern Utilities (preserved from sector_io.py)
# =============================================================================

def get_pattern_for_pass(pass_number: int) -> int:
    """
    Get the magnetic pattern for a specific recovery pass.

    Patterns rotate in sequence: 0x55 -> 0xAA -> 0xFF -> 0x00 -> repeat

    Args:
        pass_number: Pass number (0, 1, 2, ...)

    Returns:
        Pattern byte value for this pass
    """
    return PATTERN_SEQUENCE[pass_number % len(PATTERN_SEQUENCE)]


def get_pattern_name(pattern_byte: int) -> str:
    """
    Get human-readable name for a pattern.

    Args:
        pattern_byte: Pattern value (0x00-0xFF)

    Returns:
        Pattern name string
    """
    pattern_names = {
        PATTERN_ALTERNATING_LOW: "Alternating Low (0x55)",
        PATTERN_ALTERNATING_HIGH: "Alternating High (0xAA)",
        PATTERN_ALL_SET: "All Set (0xFF)",
        PATTERN_ALL_CLEAR: "All Clear (0x00)",
    }
    return pattern_names.get(pattern_byte, f"Custom (0x{pattern_byte:02X})")


# =============================================================================
# Error Classification (preserved from sector_io.py)
# =============================================================================

def classify_error(error_code: int) -> str:
    """
    Classify disk I/O error types into human-readable descriptions.

    Args:
        error_code: Error code from read/write operations

    Returns:
        Human-readable error description
    """
    error_map = {
        ERROR_SUCCESS: "Success",
        ERROR_CRC: "I/O Error",
        ERROR_SECTOR_NOT_FOUND: "Sector Not Found",
        ERROR_NOT_READY: "Drive Not Ready",
        ERROR_WRITE_PROTECT: "Write Protected",
        ERROR_PERMISSION_DENIED: "Permission Denied",
        ERROR_READ_FAULT: "Read Fault",
        ERROR_WRITE_FAULT: "Write Fault",
    }
    return error_map.get(error_code, f"Error {error_code}")


def is_fatal_error(error_code: int) -> bool:
    """
    Determine if an error is fatal (unrecoverable).

    Args:
        error_code: Error code

    Returns:
        True if error is fatal
    """
    fatal_errors = {
        ERROR_WRITE_PROTECT,
        ERROR_PERMISSION_DENIED,
        ERROR_NOT_READY,
    }
    return error_code in fatal_errors


def is_data_error(error_code: int) -> bool:
    """
    Determine if an error is a data/media error.

    Args:
        error_code: Error code

    Returns:
        True if error is data-related
    """
    data_errors = {
        ERROR_CRC,
        ERROR_SECTOR_NOT_FOUND,
        ERROR_READ_FAULT,
        ERROR_WRITE_FAULT,
    }
    return error_code in data_errors
