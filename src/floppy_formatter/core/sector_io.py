"""
Sector I/O operations for floppy disk reading and writing on Linux/WSL2.

This module provides low-level sector read/write operations with proper
512-byte alignment, error handling, and pattern writing support for
magnetic domain restoration.
"""

import os
import errno
from typing import Tuple, List, Dict, Optional

# Standard bytes per sector
BYTES_PER_SECTOR = 512

# Linux errno values for disk errors
ERROR_SUCCESS = 0
ERROR_PERMISSION_DENIED = errno.EACCES  # 13
ERROR_NOT_READY = errno.ENODEV  # 19
ERROR_WRITE_PROTECT = errno.EROFS  # 30
ERROR_CRC = errno.EIO  # 5 (I/O error)
ERROR_READ_FAULT = errno.EIO  # 5
ERROR_WRITE_FAULT = errno.EIO  # 5
ERROR_SECTOR_NOT_FOUND = errno.ENXIO  # 6


# =============================================================================
# Sector Reading
# =============================================================================


def read_sector(fd: int, sector_number: int,
                bytes_per_sector: int = BYTES_PER_SECTOR) -> Tuple[bool, Optional[bytes], int]:
    """
    Read a single sector from the disk.

    Uses lseek for precise 512-byte aligned positioning and read
    for the actual read operation. This works even on disks with bad sectors,
    returning error information instead of crashing.

    Args:
        fd: File descriptor from open_device()
        sector_number: Physical sector number (0-2879 for 1.44MB)
        bytes_per_sector: Bytes per sector (default: 512)

    Returns:
        Tuple of (success: bool, data: bytes or None, error_code: int)
        - success: True if read succeeded, False otherwise
        - data: Sector data (512 bytes) if successful, None if failed
        - error_code: 0 if successful, errno value if failed

    Common Error Codes:
        EIO (5): I/O error, bad sector, CRC error
        ENXIO (6): Sector not found, severe damage
        ENODEV (19): No disk inserted
        EACCES (13): Permission denied

    Example:
        >>> fd = open_device('/dev/sde', read_only=True)
        >>> success, data, error = read_sector(fd, 0)
        >>> if success:
        ...     print(f"Read {len(data)} bytes from sector 0")
        ... else:
        ...     print(f"Error reading sector 0: {classify_error(error)}")
        >>> close_device(fd)
    """
    try:
        # Calculate byte offset (must be 512-byte aligned)
        offset = sector_number * bytes_per_sector

        # Seek to the sector position
        os.lseek(fd, offset, os.SEEK_SET)

        # Read the sector
        data = os.read(fd, bytes_per_sector)

        # Check if we got the full sector
        if len(data) != bytes_per_sector:
            # Partial read indicates end of device or error
            return (False, None, ERROR_CRC)

        return (True, data, ERROR_SUCCESS)

    except OSError as e:
        # Linux error occurred during read
        return (False, None, e.errno)


def read_sector_multiread(
    fd: int,
    sector_number: int,
    max_attempts: int = 100,
    bytes_per_sector: int = BYTES_PER_SECTOR
) -> Tuple[bool, Optional[bytes], int, int]:
    """
    Read a sector using multiple read attempts with statistical analysis.

    This function attempts to read a problematic sector multiple times,
    performing bit-level statistical analysis to reconstruct the most likely
    correct data. Uses statistical reconstruction similar to commercial recovery tools.

    The algorithm:
    1. Attempts multiple reads of the same sector
    2. Compares results byte-by-byte across all attempts
    3. Uses majority voting to determine the most likely correct value for each byte
    4. Returns reconstructed data even if no single read succeeded perfectly

    Args:
        fd: File descriptor from open_device()
        sector_number: Physical sector number (0-2879 for 1.44MB)
        max_attempts: Maximum read attempts (default: 100, can be increased up to 2000)
        bytes_per_sector: Bytes per sector (default: 512)

    Returns:
        Tuple of (success: bool, data: bytes or None, error_code: int, successful_reads: int)
        - success: True if data was successfully reconstructed
        - data: Reconstructed sector data or None if complete failure
        - error_code: 0 if successful, last error code if failed
        - successful_reads: Number of successful read attempts

    Example:
        >>> fd = open_device('/dev/sde', read_only=True)
        >>> success, data, error, attempts = read_sector_multiread(fd, 150, max_attempts=100)
        >>> if success:
        ...     print(f"Recovered sector 150 after {attempts} successful reads")
        ... else:
        ...     print(f"Failed to recover sector 150 ({attempts} reads succeeded)")
        >>> close_device(fd)
    """
    import time

    successful_reads = []
    last_error = ERROR_CRC

    # Attempt multiple reads
    for attempt in range(max_attempts):
        success, data, error_code = read_sector(fd, sector_number, bytes_per_sector)

        if success:
            successful_reads.append(data)
        else:
            last_error = error_code

        # Small delay between attempts to allow drive to stabilize
        if attempt < max_attempts - 1:
            time.sleep(0.001)  # 1ms delay

    # If we got no successful reads at all, fail
    if len(successful_reads) == 0:
        return (False, None, last_error, 0)

    # If we only got one successful read, return it
    if len(successful_reads) == 1:
        return (True, successful_reads[0], ERROR_SUCCESS, 1)

    # Statistical reconstruction using majority voting
    # For each byte position, find the most common value across all successful reads
    reconstructed = bytearray(bytes_per_sector)

    for byte_pos in range(bytes_per_sector):
        # Collect all values at this byte position
        byte_votes = {}
        for read_data in successful_reads:
            byte_value = read_data[byte_pos]
            byte_votes[byte_value] = byte_votes.get(byte_value, 0) + 1

        # Find the most common value (majority voting)
        most_common_value = max(byte_votes.keys(), key=lambda k: byte_votes[k])
        reconstructed[byte_pos] = most_common_value

    return (True, bytes(reconstructed), ERROR_SUCCESS, len(successful_reads))


def read_sectors_batch(fd: int, start_sector: int, count: int,
                       bytes_per_sector: int = BYTES_PER_SECTOR) -> Tuple[int, List[Dict]]:
    """
    Read multiple consecutive sectors with per-sector error tracking.

    This function reads sectors one at a time, tracking the success/failure
    of each individual sector. This is critical for identifying bad sectors
    during scanning operations.

    Args:
        fd: File descriptor from open_device()
        start_sector: First sector to read
        count: Number of sectors to read
        bytes_per_sector: Bytes per sector (default: 512)

    Returns:
        Tuple of (success_count: int, results: List[Dict])
        - success_count: Number of sectors read successfully
        - results: List of dicts with keys:
            - 'sector': Sector number
            - 'success': True if read succeeded
            - 'data': Sector data (bytes) if successful, None if failed
            - 'error': Error code (0 if successful)

    Example:
        >>> fd = open_device('/dev/sde', read_only=True)
        >>> success_count, results = read_sectors_batch(fd, 0, 18)
        >>> print(f"Read {success_count}/18 sectors successfully")
        >>> for result in results:
        ...     if not result['success']:
        ...         print(f"Sector {result['sector']}: {classify_error(result['error'])}")
        >>> close_device(fd)
    """
    results = []

    for sector in range(start_sector, start_sector + count):
        success, data, error = read_sector(fd, sector, bytes_per_sector)
        results.append({
            'sector': sector,
            'success': success,
            'data': data,
            'error': error
        })

    success_count = sum(1 for r in results if r['success'])
    return (success_count, results)


def read_track(fd: int, cylinder: int, head: int,
               geometry) -> Tuple[int, List[Dict]]:
    """
    Read all sectors in a track.

    Convenience function to read an entire track (cylinder/head combination)
    at once. For 1.44MB floppies, this reads 18 sectors.

    Args:
        fd: File descriptor from open_device()
        cylinder: Cylinder number (0-79)
        head: Head number (0-1)
        geometry: DiskGeometry object with disk layout

    Returns:
        Tuple of (success_count: int, results: List[Dict])
        Same format as read_sectors_batch()

    Example:
        >>> from floppy_formatter.core.geometry import get_disk_geometry
        >>> fd = open_device('/dev/sde', read_only=True)
        >>> geometry = get_disk_geometry(fd)
        >>> success_count, results = read_track(fd, 0, 0, geometry)
        >>> print(f"Track 0/0: {success_count}/18 sectors OK")
        >>> close_device(fd)
    """
    # Calculate starting sector for this track
    sectors_per_track = geometry.sectors_per_track
    start_sector = (cylinder * geometry.heads + head) * sectors_per_track

    return read_sectors_batch(
        fd, start_sector, sectors_per_track, geometry.bytes_per_sector
    )


# =============================================================================
# Sector Writing
# =============================================================================


def write_sector(
    fd: int, sector_number: int, data: bytes, bytes_per_sector: int = BYTES_PER_SECTOR
) -> Tuple[bool, int]:
    """
    Write a single sector to the disk.

    Uses lseek for precise 512-byte aligned positioning and write
    for the actual write operation. The data must be exactly 512 bytes.

    IMPORTANT: Device must be opened with read-write access (not read_only=True)

    Args:
        fd: File descriptor from open_device()
        sector_number: Physical sector number (0-2879 for 1.44MB)
        data: Sector data to write (must be exactly 512 bytes)
        bytes_per_sector: Bytes per sector (default: 512)

    Returns:
        Tuple of (success: bool, error_code: int)
        - success: True if write succeeded, False otherwise
        - error_code: 0 if successful, errno value if failed

    Raises:
        ValueError: If data is not exactly bytes_per_sector bytes

    Common Error Codes:
        EROFS (30): Disk is write-protected
        EACCES (13): Permission denied (not root)
        ENODEV (19): No disk inserted
        EIO (5): Write operation failed

    Example:
        >>> fd = open_device('/dev/sde', read_only=False)
        >>> data = b'\\x00' * 512  # Zero-filled sector
        >>> success, error = write_sector(fd, 0, data)
        >>> if success:
        ...     print("Wrote sector 0 successfully")
        ... else:
        ...     print(f"Error writing: {classify_error(error)}")
        >>> close_device(fd)
    """
    # Validate data length
    if len(data) != bytes_per_sector:
        raise ValueError(
            f"Data must be exactly {bytes_per_sector} bytes, got {len(data)} bytes"
        )

    try:
        # Calculate byte offset (must be 512-byte aligned)
        offset = sector_number * bytes_per_sector

        # Seek to the sector position
        os.lseek(fd, offset, os.SEEK_SET)

        # Write the sector
        bytes_written = os.write(fd, data)

        # Check if full sector was written
        if bytes_written != bytes_per_sector:
            return (False, ERROR_WRITE_FAULT)

        # Write succeeded
        return (True, ERROR_SUCCESS)

    except OSError as e:
        # Linux error occurred during write
        return (False, e.errno)


def write_sectors_batch(
    fd: int, start_sector: int, data_list: List[bytes],
    bytes_per_sector: int = BYTES_PER_SECTOR
) -> Tuple[int, List[Dict]]:
    """
    Write multiple consecutive sectors with per-sector error tracking.

    Args:
        fd: File descriptor from open_device()
        start_sector: First sector to write
        data_list: List of sector data (each must be 512 bytes)
        bytes_per_sector: Bytes per sector (default: 512)

    Returns:
        Tuple of (success_count: int, results: List[Dict])
        - success_count: Number of sectors written successfully
        - results: List of dicts with keys:
            - 'sector': Sector number
            - 'success': True if write succeeded
            - 'error': Error code (0 if successful)

    Example:
        >>> fd = open_device('/dev/sde', read_only=False)
        >>> sectors = [b'\\x00' * 512 for _ in range(18)]  # 18 zero-filled sectors
        >>> success_count, results = write_sectors_batch(fd, 0, sectors)
        >>> print(f"Wrote {success_count}/18 sectors successfully")
        >>> close_device(fd)
    """
    results = []

    for i, data in enumerate(data_list):
        sector = start_sector + i
        success, error = write_sector(fd, sector, data, bytes_per_sector)
        results.append({
            'sector': sector,
            'success': success,
            'error': error
        })

    success_count = sum(1 for r in results if r['success'])
    return (success_count, results)


# =============================================================================
# Pattern Writing
# =============================================================================


def write_pattern(
    fd: int, sector_number: int, pattern_byte: int, bytes_per_sector: int = BYTES_PER_SECTOR
) -> Tuple[bool, int]:
    """
    Write a magnetic pattern to a sector.

    Pattern writing "exercises" the magnetic domains on the disk surface,
    which can help restore weak or marginal sectors. Common patterns:
    - 0x55 (01010101): Alternating bits
    - 0xAA (10101010): Opposite alternating bits
    - 0xFF (11111111): All bits set
    - 0x00 (00000000): All bits clear

    Args:
        fd: File descriptor from open_device()
        sector_number: Physical sector number (0-2879 for 1.44MB)
        pattern_byte: Pattern value (0x00-0xFF)
        bytes_per_sector: Bytes per sector (default: 512)

    Returns:
        Tuple of (success: bool, error_code: int)
        Same as write_sector()

    Example:
        >>> fd = open_device('/dev/sde', read_only=False)
        >>> # Write alternating bit pattern to sector 0
        >>> success, error = write_pattern(fd, 0, 0x55)
        >>> if success:
        ...     print("Wrote 0x55 pattern to sector 0")
        >>> close_device(fd)
    """
    # Create pattern data (full sector filled with pattern_byte)
    pattern_data = bytes([pattern_byte] * bytes_per_sector)

    return write_sector(fd, sector_number, pattern_data, bytes_per_sector)


def write_track_pattern(
    fd: int, cylinder: int, head: int, pattern_byte: int, geometry
) -> Tuple[int, List[Dict]]:
    """
    Write a magnetic pattern to all sectors in a track.

    This is used during multi-pass recovery to "exercise" the magnetic
    domains across an entire track before reformatting.

    Args:
        fd: File descriptor from open_device()
        cylinder: Cylinder number (0-79)
        head: Head number (0-1)
        pattern_byte: Pattern value (0x00-0xFF)
        geometry: DiskGeometry object with disk layout

    Returns:
        Tuple of (success_count: int, results: List[Dict])
        - success_count: Number of sectors written successfully
        - results: List of dicts with per-sector results

    Example:
        >>> from floppy_formatter.core.geometry import get_disk_geometry
        >>> fd = open_device('/dev/sde', read_only=False)
        >>> geometry = get_disk_geometry(fd)
        >>> # Write 0xAA pattern to entire track 0/0
        >>> success_count, results = write_track_pattern(fd, 0, 0, 0xAA, geometry)
        >>> print(f"Wrote pattern to {success_count}/18 sectors")
        >>> close_device(fd)
    """
    results = []
    sectors_per_track = geometry.sectors_per_track
    start_sector = (cylinder * geometry.heads + head) * sectors_per_track

    for sector_offset in range(sectors_per_track):
        sector_num = start_sector + sector_offset
        success, error = write_pattern(
            fd, sector_num, pattern_byte, geometry.bytes_per_sector
        )
        results.append({
            'sector': sector_num,
            'success': success,
            'error': error
        })

    success_count = sum(1 for r in results if r['success'])
    return (success_count, results)


def write_disk_pattern(fd: int, pattern_byte: int, geometry) -> Tuple[int, int]:
    """
    Write a magnetic pattern to the entire disk.

    Writes the pattern to all 2,880 sectors on a 1.44MB floppy.
    This is useful for bulk pattern writing operations.

    Args:
        fd: File descriptor from open_device()
        pattern_byte: Pattern value (0x00-0xFF)
        geometry: DiskGeometry object with disk layout

    Returns:
        Tuple of (success_count: int, total_sectors: int)

    Example:
        >>> from floppy_formatter.core.geometry import get_disk_geometry
        >>> fd = open_device('/dev/sde', read_only=False)
        >>> geometry = get_disk_geometry(fd)
        >>> success, total = write_disk_pattern(fd, 0x00, geometry)
        >>> print(f"Wrote pattern to {success}/{total} sectors")
        >>> close_device(fd)
    """
    total_success = 0
    total_sectors = geometry.total_sectors

    for cylinder in range(geometry.cylinders):
        for head in range(geometry.heads):
            success_count, _ = write_track_pattern(fd, cylinder, head,
                                                   pattern_byte, geometry)
            total_success += success_count

    return (total_success, total_sectors)


# =============================================================================
# Pattern Constants
# =============================================================================


# Standard magnetic patterns for disk restoration
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


def get_pattern_for_pass(pass_number: int) -> int:
    """
    Get the magnetic pattern for a specific recovery pass.

    Patterns rotate in sequence: 0x55 → 0xAA → 0xFF → 0x00 → repeat

    Args:
        pass_number: Pass number (0, 1, 2, ...)

    Returns:
        Pattern byte value for this pass

    Example:
        >>> for i in range(8):
        ...     pattern = get_pattern_for_pass(i)
        ...     print(f"Pass {i}: 0x{pattern:02X}")
        Pass 0: 0x55
        Pass 1: 0xAA
        Pass 2: 0xFF
        Pass 3: 0x00
        Pass 4: 0x55
        ...
    """
    return PATTERN_SEQUENCE[pass_number % len(PATTERN_SEQUENCE)]


def get_pattern_name(pattern_byte: int) -> str:
    """
    Get human-readable name for a pattern.

    Args:
        pattern_byte: Pattern value (0x00-0xFF)

    Returns:
        Pattern name string

    Example:
        >>> print(get_pattern_name(0x55))
        Alternating Low (0x55)
    """
    pattern_names = {
        PATTERN_ALTERNATING_LOW: "Alternating Low (0x55)",
        PATTERN_ALTERNATING_HIGH: "Alternating High (0xAA)",
        PATTERN_ALL_SET: "All Set (0xFF)",
        PATTERN_ALL_CLEAR: "All Clear (0x00)",
    }
    return pattern_names.get(pattern_byte, f"Custom (0x{pattern_byte:02X})")


# =============================================================================
# Error Classification
# =============================================================================


def classify_error(error_code: int) -> str:
    """
    Classify disk I/O error types into human-readable descriptions.

    Maps Linux errno values to short, descriptive error names suitable
    for display in reports and logs.

    Args:
        error_code: Linux errno value from read/write operations

    Returns:
        Human-readable error description

    Example:
        >>> success, data, error = read_sector(fd, 100)
        >>> if not success:
        ...     error_type = classify_error(error)
        ...     print(f"Sector 100: {error_type}")
        Sector 100: I/O Error
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
    return error_map.get(error_code, f"Error {error_code} ({os.strerror(error_code)})")


def is_fatal_error(error_code: int) -> bool:
    """
    Determine if an error is fatal (unrecoverable).

    Fatal errors indicate conditions that cannot be fixed by retrying
    or reformatting, such as write protection or permission denied.

    Args:
        error_code: Linux errno value

    Returns:
        True if error is fatal, False if potentially recoverable

    Example:
        >>> success, data, error = read_sector(fd, 100)
        >>> if not success:
        ...     if is_fatal_error(error):
        ...         print("Fatal error - cannot continue")
        ...     else:
        ...         print("Recoverable error - will retry")
    """
    fatal_errors = {
        ERROR_WRITE_PROTECT,        # Physical tab on disk
        ERROR_PERMISSION_DENIED,    # Permission issue (not root)
        ERROR_NOT_READY,            # No disk or disconnected
    }
    return error_code in fatal_errors


def is_data_error(error_code: int) -> bool:
    """
    Determine if an error is a data/media error.

    Data errors indicate bad sectors or media degradation that may
    be recoverable through reformatting or pattern writing.

    Args:
        error_code: Linux errno value

    Returns:
        True if error is data-related

    Example:
        >>> if is_data_error(error):
        ...     print("Bad sector detected - attempting recovery")
    """
    data_errors = {
        ERROR_CRC,  # Bad sector / I/O error
        ERROR_SECTOR_NOT_FOUND,  # Missing sector
        ERROR_READ_FAULT,  # Read failure
        ERROR_WRITE_FAULT,  # Write failure
    }
    return error_code in data_errors


# =============================================================================
# Sector Verification
# =============================================================================


def verify_sector(
    fd: int, sector_number: int, expected_data: bytes,
    bytes_per_sector: int = BYTES_PER_SECTOR
) -> Tuple[bool, int]:
    """
    Verify that a sector contains expected data.

    Reads a sector and compares it byte-for-byte with expected data.
    Used after writing to verify the write was successful.

    Args:
        fd: File descriptor from open_device()
        sector_number: Physical sector number
        expected_data: Data to compare against (must be 512 bytes)
        bytes_per_sector: Bytes per sector (default: 512)

    Returns:
        Tuple of (matches: bool, error_code: int)
        - matches: True if data matches, False otherwise
        - error_code: 0 if read succeeded, error code if read failed

    Example:
        >>> # Write pattern and verify
        >>> success, error = write_pattern(fd, 0, 0x55)
        >>> if success:
        ...     expected = bytes([0x55] * 512)
        ...     matches, error = verify_sector(fd, 0, expected)
        ...     if matches:
        ...         print("Verification passed")
    """
    success, data, error = read_sector(fd, sector_number, bytes_per_sector)

    if not success:
        # Read failed - return error
        return (False, error)

    # Compare data
    matches = (data == expected_data)
    return (matches, ERROR_SUCCESS)


def verify_pattern(
    fd: int, sector_number: int, pattern_byte: int, bytes_per_sector: int = BYTES_PER_SECTOR
) -> Tuple[bool, int]:
    """
    Verify that a sector contains a specific pattern.

    Convenience function to verify pattern writes.

    Args:
        fd: File descriptor from open_device()
        sector_number: Physical sector number
        pattern_byte: Expected pattern value
        bytes_per_sector: Bytes per sector (default: 512)

    Returns:
        Tuple of (matches: bool, error_code: int)

    Example:
        >>> write_pattern(fd, 0, 0xAA)
        >>> matches, error = verify_pattern(fd, 0, 0xAA)
        >>> if matches:
        ...     print("Pattern verified")
    """
    expected_data = bytes([pattern_byte] * bytes_per_sector)
    return verify_sector(fd, sector_number, expected_data, bytes_per_sector)
