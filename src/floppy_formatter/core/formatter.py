"""
Low-level floppy disk formatting operations using Greaseweazle.

This module provides track and disk formatting functionality using
flux-level writes via Greaseweazle V4.1 USB controller. Unlike USB
floppy drives that use sector-by-sector formatting, Greaseweazle
enables true track-level formatting with:
- DC erase before write (cleaner signal)
- Proper MFM encoding with sync marks
- Full track write in one rotation

This provides better results for degraded or marginal disks compared
to USB floppy drive formatting.
"""

from typing import List, Tuple, Optional, Callable, Union, Any

from floppy_formatter.core.geometry import DiskGeometry
from floppy_formatter.core.sector_adapter import (
    read_track,
    format_track_low_level,
    classify_error,
    invalidate_track_cache,
)
from floppy_formatter.hardware import GreaseweazleDevice


# =============================================================================
# Track Formatting
# =============================================================================


def format_track(
    device: Union[GreaseweazleDevice, Any],
    cylinder: int,
    head: int,
    geometry: DiskGeometry
) -> Tuple[bool, int, List[int], int]:
    """
    Format a single track using Greaseweazle flux-level writes.

    Unlike USB floppy drives that write sector-by-sector, Greaseweazle:
    1. Performs a DC erase of the entire track (clean slate)
    2. Encodes all 18 sectors as a single MFM flux stream
    3. Writes the complete track in one disk rotation
    4. Reads back and verifies all sectors

    This produces cleaner writes with better signal quality compared
    to USB floppy drive formatting.

    Args:
        device: Connected GreaseweazleDevice instance
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
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     geometry = get_greaseweazle_geometry(device)
        ...     success, bad_count, bad_sectors, error = format_track(
        ...         device, 0, 0, geometry
        ...     )
        ...     if success:
        ...         if bad_count > 0:
        ...             print(f"Track formatted with {bad_count} bad sectors")
        ...         else:
        ...             print("Track formatted successfully")
        ...     else:
        ...         print(f"Format failed: {classify_error(error)}")
    """
    # Use the low-level Greaseweazle formatting function
    # This does DC erase + MFM encode + write + verify
    return format_track_low_level(device, cylinder, head, geometry, fill_byte=0x00)


def format_disk(
    device: Union[GreaseweazleDevice, Any],
    geometry: DiskGeometry,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Tuple[bool, int, List[int]]:
    """
    Format entire disk (all 80 cylinders × 2 heads = 160 tracks).

    This function formats the complete floppy disk by iterating through
    all cylinders and heads using Greaseweazle flux-level writes.
    Progress can be reported via callback for real-time UI updates.

    Args:
        device: Connected GreaseweazleDevice instance
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
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     geometry = get_greaseweazle_geometry(device)
        ...     try:
        ...         success, bad_count, bad_sectors = format_disk(
        ...             device, geometry, show_progress
        ...         )
        ...         print(f"Format complete: {bad_count} bad sectors detected")
        ...     except IOError as e:
        ...         print(f"Format failed: {e}")
    """
    total_bad_sectors = 0
    all_bad_sectors = []

    # Calculate total number of tracks
    total_tracks = geometry.cylinders * geometry.heads

    # Invalidate cache before starting
    invalidate_track_cache()

    # Format each track
    for cylinder in range(geometry.cylinders):
        for head in range(geometry.heads):
            # Format this track
            success, bad_count, bad_sectors, error = format_track(
                device, cylinder, head, geometry
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
    device: Union[GreaseweazleDevice, Any],
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
        device: Connected GreaseweazleDevice instance
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
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     geometry = get_greaseweazle_geometry(device)
        ...     success, bad_count, bad_sectors = format_tracks_range(
        ...         device, 0, 9, geometry
        ...     )
        ...     print(f"Formatted 20 tracks: {bad_count} bad sectors")
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

    # Invalidate cache before starting
    invalidate_track_cache()

    # Format each track in range
    for cylinder in range(start_cylinder, end_cylinder + 1):
        for head in range(geometry.heads):
            # Format this track
            success, bad_count, bad_sectors, error = format_track(
                device, cylinder, head, geometry
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
# Device Type Detection (Greaseweazle-specific)
# =============================================================================


def is_greaseweazle_device(device: Union[GreaseweazleDevice, Any]) -> Tuple[bool, str]:
    """
    Check if connected device is a Greaseweazle controller.

    With Greaseweazle, we have direct hardware control rather than
    using USB floppy drives.

    Args:
        device: GreaseweazleDevice instance

    Returns:
        Tuple of (is_greaseweazle: bool, device_name: str)

    Example:
        >>> with GreaseweazleDevice() as device:
        ...     is_gw, name = is_greaseweazle_device(device)
        ...     print(f"Connected: {name}")
    """
    if isinstance(device, GreaseweazleDevice):
        info = device.get_device_info()
        return (True, f"Greaseweazle {info.model} (fw {info.firmware_version})")

    return (False, "Unknown Device")


def is_usb_floppy(device_path: str) -> Tuple[bool, str]:
    """
    Legacy function for backward compatibility.

    With Greaseweazle, this always returns information indicating
    we're using a Greaseweazle controller.

    Args:
        device_path: Device path (ignored for Greaseweazle)

    Returns:
        Tuple of (is_usb: bool, device_name: str)
    """
    return (True, "Greaseweazle V4.1 USB Controller")


def get_format_capability(device_path: str = "") -> Tuple[bool, bool, str]:
    """
    Get format capabilities for Greaseweazle.

    Greaseweazle supports true track-level formatting with:
    - DC erase before write
    - Full MFM encoding
    - Single-rotation writes

    Args:
        device_path: Ignored (kept for backward compatibility)

    Returns:
        Tuple of (supports_flux, supports_standard, message)
        - supports_flux: True (Greaseweazle supports flux-level operations)
        - supports_standard: True (standard formatting available)
        - message: Descriptive message about capabilities

    Example:
        >>> supports_flux, supports_std, msg = get_format_capability()
        >>> print(msg)
        Greaseweazle flux-level formatting (DC erase + MFM encode)
    """
    return (
        True,   # Full flux-level formatting with Greaseweazle
        True,   # Standard sector formatting also available
        "Greaseweazle flux-level formatting (DC erase + MFM encode + verify)"
    )


# =============================================================================
# Format Verification
# =============================================================================


def verify_format(
    device: Union[GreaseweazleDevice, Any],
    geometry: DiskGeometry,
    quick: bool = True
) -> Tuple[bool, int, List[int]]:
    """
    Verify disk format by reading all sectors.

    After formatting, this function verifies that all sectors
    can be read successfully using flux capture and MFM decoding.

    Args:
        device: Connected GreaseweazleDevice instance
        geometry: Disk geometry information
        quick: If True, only read first sector of each track (fast)
               If False, read all sectors (thorough but slower)

    Returns:
        Tuple of (success, bad_sector_count, bad_sectors)
        - success: True if verification passed (no bad sectors)
        - bad_sector_count: Number of bad sectors found
        - bad_sectors: List of bad sector numbers

    Example:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     geometry = get_greaseweazle_geometry(device)
        ...     success, bad_count, bad_sectors = verify_format(device, geometry)
        ...     if success:
        ...         print("Format verification passed!")
        ...     else:
        ...         print(f"Found {bad_count} bad sectors: {bad_sectors}")
    """
    bad_sectors = []

    # Invalidate cache to ensure fresh reads
    invalidate_track_cache()

    if quick:
        # Quick verification: read first sector of each track
        # With Greaseweazle, we still read the whole track but only check sector 1
        for cylinder in range(geometry.cylinders):
            for head in range(geometry.heads):
                # Read the track
                success_count, results = read_track(device, cylinder, head, geometry)

                # Check first sector (sector 1)
                for result in results:
                    if result['sector'] == 1:
                        if not result['success']:
                            track_idx = cylinder * geometry.heads + head
                            linear_sector = track_idx * geometry.sectors_per_track
                            bad_sectors.append(linear_sector)
                        break
    else:
        # Thorough verification: read all sectors
        for cylinder in range(geometry.cylinders):
            for head in range(geometry.heads):
                # Read entire track at once
                success_count, results = read_track(device, cylinder, head, geometry)

                # Check all sectors
                for result in results:
                    if not result['success']:
                        linear_sector = (
                            (cylinder * geometry.heads + head) * geometry.sectors_per_track +
                            (result['sector'] - 1)
                        )
                        bad_sectors.append(linear_sector)

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
