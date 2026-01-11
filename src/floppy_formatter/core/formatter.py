"""
Low-level floppy disk formatting operations for Linux/WSL2.

This module provides track and disk formatting functionality using
sector-level writes. Linux does not have native track formatting IOCTLs,
so we implement formatting by writing zeros to all sectors and verifying
the writes.

CRITICAL: Linux formatting uses sector-level operations rather than
track-level operations. This is functionally equivalent and works
reliably on USB floppy drives.
"""

from typing import List, Tuple, Optional, Callable

from floppy_formatter.core.device_manager import open_device, close_device
from floppy_formatter.core.geometry import DiskGeometry
from floppy_formatter.core.sector_io import (
    write_sector,
    read_sector,
    classify_error,
    ERROR_SUCCESS
)


# =============================================================================
# Track Formatting
# =============================================================================


def format_track(
    fd: int,
    cylinder: int,
    head: int,
    geometry: DiskGeometry
) -> Tuple[bool, int, List[int], int]:
    """
    Format a single track using sector-level writes.

    On Linux, there is no native track formatting ioctl. Instead, we:
    1. Calculate which sectors belong to this track
    2. Write zeros to each sector
    3. Read back to verify
    4. Track any sectors that fail to write or verify

    Args:
        fd: File descriptor from open_device()
        cylinder: Cylinder number (0-79 for 1.44MB)
        head: Head number (0-1 for 1.44MB)
        geometry: Disk geometry information

    Returns:
        Tuple of (success, bad_sector_count, bad_sectors, error_code)
        - success: True if format succeeded, False otherwise
        - bad_sector_count: Number of bad sectors detected
        - bad_sectors: List of bad sector numbers
        - error_code: Error code (ERROR_SUCCESS if successful)

    Raises:
        None - all errors returned via tuple

    Example:
        >>> from floppy_formatter.core.device_manager import open_device, close_device
        >>> from floppy_formatter.core.geometry import get_disk_geometry
        >>> fd = open_device('/dev/sde', read_only=False)
        >>> geometry = get_disk_geometry(fd)
        >>> success, bad_count, bad_sectors, error = format_track(fd, 0, 0, geometry)
        >>> if success:
        ...     if bad_count > 0:
        ...         print(f"Track formatted with {bad_count} bad sectors")
        ...     else:
        ...         print("Track formatted successfully")
        ... else:
        ...     print(f"Format failed: {classify_error(error)}")
        >>> close_device(fd)
    """
    # Calculate starting sector for this track
    sectors_per_track = geometry.sectors_per_track
    start_sector = (cylinder * geometry.heads + head) * sectors_per_track

    # Prepare zero-filled sector data
    zero_sector = bytes([0] * geometry.bytes_per_sector)

    bad_sectors = []
    last_error = ERROR_SUCCESS

    # Write zeros to all sectors in this track
    for offset in range(sectors_per_track):
        sector_num = start_sector + offset

        # Write zero sector
        success, error = write_sector(fd, sector_num, zero_sector, geometry.bytes_per_sector)

        if not success:
            bad_sectors.append(sector_num)
            last_error = error
            continue

        # Verify the write by reading back
        success, data, error = read_sector(fd, sector_num, geometry.bytes_per_sector)

        if not success or data != zero_sector:
            bad_sectors.append(sector_num)
            if not success:
                last_error = error

    # Determine overall success
    if len(bad_sectors) == 0:
        return (True, 0, [], ERROR_SUCCESS)
    elif len(bad_sectors) < sectors_per_track:
        # Partial success - some bad sectors but track is usable
        return (True, len(bad_sectors), bad_sectors, ERROR_SUCCESS)
    else:
        # Complete failure - all sectors bad
        return (False, len(bad_sectors), bad_sectors, last_error)


def format_disk(
    fd: int,
    geometry: DiskGeometry,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Tuple[bool, int, List[int]]:
    """
    Format entire disk (all 80 cylinders × 2 heads = 160 tracks).

    This function formats the complete floppy disk by iterating through
    all cylinders and heads. Progress can be reported via callback for
    real-time UI updates.

    Args:
        fd: File descriptor from open_device()
        geometry: Disk geometry information
        progress_callback: Optional function(current_track, total_tracks)
                          for progress updates

    Returns:
        Tuple of (success, total_bad_sectors, bad_sector_list)
        - success: True if all tracks formatted successfully
        - total_bad_sectors: Total number of bad sectors detected
        - bad_sector_list: List of all bad sector numbers

    Raises:
        IOError: If any track fails completely

    Example:
        >>> def show_progress(current, total):
        ...     percent = (current / total) * 100
        ...     print(f"Formatting: {percent:.1f}% ({current}/{total} tracks)")
        >>>
        >>> from floppy_formatter.core.device_manager import open_device, close_device
        >>> from floppy_formatter.core.geometry import get_disk_geometry
        >>> fd = open_device('/dev/sde', read_only=False)
        >>> geometry = get_disk_geometry(fd)
        >>> try:
        ...     success, bad_count, bad_sectors = format_disk(
        ...         fd, geometry, show_progress
        ...     )
        ...     print(f"Format complete: {bad_count} bad sectors detected")
        ... except IOError as e:
        ...     print(f"Format failed: {e}")
        ... finally:
        ...     close_device(fd)
    """
    total_bad_sectors = 0
    all_bad_sectors = []

    # Calculate total number of tracks
    total_tracks = geometry.cylinders * geometry.heads

    # Format each track
    for cylinder in range(geometry.cylinders):
        for head in range(geometry.heads):
            # Format this track
            success, bad_count, bad_sectors, error = format_track(
                fd, cylinder, head, geometry
            )

            if not success:
                # Format failed - raise error
                error_msg = classify_error(error)
                raise IOError(
                    f"Failed to format track C{cylinder}:H{head} "
                    f"(Track {cylinder * geometry.heads + head}): {error_msg}"
                )

            # Accumulate bad sector information
            total_bad_sectors += bad_count
            all_bad_sectors.extend(bad_sectors)

            # Report progress if callback provided
            if progress_callback is not None:
                current_track = cylinder * geometry.heads + head + 1
                progress_callback(current_track, total_tracks)

    return (True, total_bad_sectors, all_bad_sectors)


def format_tracks_range(
    fd: int,
    start_cylinder: int,
    end_cylinder: int,
    geometry: DiskGeometry,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Tuple[bool, int, List[int]]:
    """
    Format a range of cylinders (both heads on each cylinder).

    This function formats a subset of the disk, useful for
    targeted recovery operations or testing.

    Args:
        fd: File descriptor from open_device()
        start_cylinder: First cylinder to format (inclusive)
        end_cylinder: Last cylinder to format (inclusive)
        geometry: Disk geometry information
        progress_callback: Optional function(current, total) for progress

    Returns:
        Tuple of (success, total_bad_sectors, bad_sector_list)

    Raises:
        IOError: If any track fails to format
        ValueError: If cylinder range is invalid

    Example:
        >>> # Format only cylinders 0-9 (first 20 tracks)
        >>> from floppy_formatter.core.device_manager import open_device, close_device
        >>> from floppy_formatter.core.geometry import get_disk_geometry
        >>> fd = open_device('/dev/sde', read_only=False)
        >>> geometry = get_disk_geometry(fd)
        >>> success, bad_count, bad_sectors = format_tracks_range(
        ...     fd, 0, 9, geometry
        ... )
        >>> print(f"Formatted 20 tracks: {bad_count} bad sectors")
        >>> close_device(fd)
    """
    # Validate cylinder range
    if start_cylinder < 0 or end_cylinder >= geometry.cylinders:
        raise ValueError(
            f"Invalid cylinder range: {start_cylinder}-{end_cylinder} "
            f"(valid: 0-{geometry.cylinders-1})"
        )
    if start_cylinder > end_cylinder:
        raise ValueError(
            f"Start cylinder ({start_cylinder}) must be <= "
            f"end cylinder ({end_cylinder})"
        )

    total_bad_sectors = 0
    all_bad_sectors = []

    # Calculate total number of tracks in range
    cylinder_count = end_cylinder - start_cylinder + 1
    total_tracks = cylinder_count * geometry.heads

    track_counter = 0

    # Format each track in range
    for cylinder in range(start_cylinder, end_cylinder + 1):
        for head in range(geometry.heads):
            # Format this track
            success, bad_count, bad_sectors, error = format_track(
                fd, cylinder, head, geometry
            )

            if not success:
                # Format failed - raise error
                error_msg = classify_error(error)
                raise IOError(
                    f"Failed to format track C{cylinder}:H{head}: {error_msg}"
                )

            # Accumulate bad sector information
            total_bad_sectors += bad_count
            all_bad_sectors.extend(bad_sectors)

            # Report progress if callback provided
            if progress_callback is not None:
                track_counter += 1
                progress_callback(track_counter, total_tracks)

    return (True, total_bad_sectors, all_bad_sectors)


# =============================================================================
# Device Type Detection (Linux-specific)
# =============================================================================


def is_usb_floppy(device_path: str) -> Tuple[bool, str]:
    """
    Detect if floppy drive is USB or internal.

    On Linux, USB devices typically appear as /dev/sdX, while internal
    floppy controllers use /dev/fd0.

    Args:
        device_path: Device path (e.g., '/dev/sde' or '/dev/fd0')

    Returns:
        Tuple of (is_usb: bool, device_name: str)
        - is_usb: True if USB floppy, False if internal
        - device_name: Human-readable device type

    Example:
        >>> is_usb, name = is_usb_floppy('/dev/sde')
        >>> if is_usb:
        ...     print(f"Detected {name} - sector-level formatting")
        ... else:
        ...     print(f"Detected {name} - sector-level formatting")
    """
    import os

    device_name = os.path.basename(device_path)

    # Internal floppy controller uses /dev/fd0 or /dev/fd1
    if device_name.startswith('fd'):
        return (False, "Internal Floppy Controller")

    # USB devices use /dev/sdX naming
    if device_name.startswith('sd'):
        return (True, "USB Floppy Drive")

    # Unknown device type
    return (True, f"Unknown Device ({device_name})")


def get_format_capability(device_path: str) -> Tuple[bool, bool, str]:
    """
    Detect format capabilities (Linux always uses sector-level formatting).

    On Linux, we always use sector-level formatting regardless of device type.

    Args:
        device_path: Device path (e.g., '/dev/sde')

    Returns:
        Tuple of (supports_ex, supports_standard, message)
        - supports_ex: Always False on Linux (no native format ioctl)
        - supports_standard: Always True (sector-level formatting)
        - message: Descriptive message about capabilities

    Example:
        >>> supports_ex, supports_std, msg = get_format_capability('/dev/sde')
        >>> print(msg)
        Linux sector-level formatting (write + verify)
    """
    is_usb, device_type = is_usb_floppy(device_path)

    return (
        False,  # No native track formatting on Linux
        True,   # Sector-level formatting always available
        f"Linux sector-level formatting (write + verify) - Device: {device_type}"
    )


# =============================================================================
# Format Verification
# =============================================================================


def verify_format(
    fd: int,
    geometry: DiskGeometry,
    quick: bool = True
) -> Tuple[bool, int, List[int]]:
    """
    Verify disk format by reading all sectors.

    After formatting, this function verifies that all sectors
    can be read successfully.

    Args:
        fd: File descriptor from open_device()
        geometry: Disk geometry information
        quick: If True, only read sector 0 of each track (fast)
               If False, read all sectors (thorough but slow)

    Returns:
        Tuple of (success, bad_sector_count, bad_sectors)
        - success: True if verification passed (no bad sectors)
        - bad_sector_count: Number of bad sectors found
        - bad_sectors: List of bad sector numbers

    Example:
        >>> # After formatting
        >>> from floppy_formatter.core.device_manager import open_device
        >>> from floppy_formatter.core.geometry import get_disk_geometry
        >>> fd = open_device('/dev/sde', read_only=True)
        >>> geometry = get_disk_geometry(fd)
        >>> success, bad_count, bad_sectors = verify_format(fd, geometry)
        >>> if success:
        ...     print("Format verification passed!")
        ... else:
        ...     print(f"Found {bad_count} bad sectors: {bad_sectors}")
    """
    bad_sectors = []

    if quick:
        # Quick verification: read first sector of each track
        for cylinder in range(geometry.cylinders):
            for head in range(geometry.heads):
                # Calculate first sector of this track
                sector_num = (cylinder * geometry.heads + head) * geometry.sectors_per_track

                # Try to read the sector
                success, data, error = read_sector(
                    fd, sector_num, geometry.bytes_per_sector
                )

                if not success:
                    bad_sectors.append(sector_num)
    else:
        # Thorough verification: read all sectors
        for sector_num in range(geometry.total_sectors):
            success, data, error = read_sector(
                fd, sector_num, geometry.bytes_per_sector
            )

            if not success:
                bad_sectors.append(sector_num)

    return (len(bad_sectors) == 0, len(bad_sectors), bad_sectors)


# =============================================================================
# Utility Functions
# =============================================================================


def estimate_format_time(geometry: DiskGeometry, usb_speed: str = "2.0") -> float:
    """
    Estimate formatting time in seconds.

    Linux sector-level formatting provides a rough estimate for user expectations.

    Args:
        geometry: Disk geometry information
        usb_speed: USB version ("2.0" or "3.0")

    Returns:
        Estimated time in seconds

    Example:
        >>> from floppy_formatter.core.geometry import get_standard_1_44mb_geometry
        >>> geometry = get_standard_1_44mb_geometry()
        >>> seconds = estimate_format_time(geometry)
        >>> print(f"Estimated format time: {seconds/60:.1f} minutes")
        Estimated format time: 5.0 minutes
    """
    # Each sector: write (10ms) + read (10ms) = 20ms
    # 2880 sectors = ~60 seconds
    # Add overhead for seeks and verification
    total_sectors = geometry.total_sectors
    time_per_sector = 0.02  # 20ms per sector

    if usb_speed == "3.0":
        time_per_sector *= 0.8  # Slight improvement on USB 3.0

    estimated_seconds = total_sectors * time_per_sector * 1.5  # 50% overhead
    return estimated_seconds
