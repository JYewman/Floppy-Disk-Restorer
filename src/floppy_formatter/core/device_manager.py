"""
Device management for USB floppy drives on Linux/WSL2.

This module handles block device detection, opening, and handle management
for Linux environments. It implements functionality to access USB floppy
drives using /dev/sdX device paths with raw sector access.
"""

import os
import errno
import logging
from typing import Optional, List
from dataclasses import dataclass


# =============================================================================
# Linux Device Detection
# =============================================================================


def find_floppy_devices() -> List[str]:
    """
    Find all USB floppy drives by scanning /sys/block.

    This function identifies USB floppy drives by checking:
    - Device is removable (/sys/block/sdX/removable == 1)
    - Device size is 1.44MB (2880 sectors of 512 bytes)

    Returns:
        List of device names (e.g., ['sdb', 'sde'])

    Raises:
        IOError: If no floppy drives are found

    Example:
        >>> devices = find_floppy_devices()
        >>> print(f"Found floppy drives: {devices}")
        Found floppy drives: ['sde']
    """
    floppy_devices = []
    sys_block_path = '/sys/block'

    if not os.path.exists(sys_block_path):
        raise IOError(f"Cannot access {sys_block_path}. Are you running on Linux?")

    # Scan all block devices
    try:
        block_devices = os.listdir(sys_block_path)
    except OSError as e:
        raise IOError(f"Cannot list block devices: {e}")

    for device in block_devices:
        # Check if device is removable
        removable_path = os.path.join(sys_block_path, device, 'removable')
        size_path = os.path.join(sys_block_path, device, 'size')

        try:
            # Read removable status
            with open(removable_path, 'r') as f:
                removable = f.read().strip()

            if removable != '1':
                continue  # Not removable, skip

            # Read device size (in 512-byte sectors)
            with open(size_path, 'r') as f:
                size_sectors = int(f.read().strip())

            # 1.44MB floppy = 2880 sectors of 512 bytes
            if size_sectors == 2880:
                floppy_devices.append(device)

        except (OSError, ValueError):
            # Skip devices we can't read or parse
            continue

    if not floppy_devices:
        raise IOError(
            f"No USB floppy drives found.\n"
            f"Scanned {sys_block_path} for removable 1.44MB devices.\n"
            f"\nPossible causes:\n"
            f"  - No floppy drive connected\n"
            f"  - USB cable disconnected\n"
            f"  - No disk inserted\n"
            f"  - Device not attached to WSL (use 'usbipd attach --wsl --busid X-Y')\n"
            f"  - Root privileges required (use sudo)"
        )

    return floppy_devices


def get_device_path(device_name: str) -> str:
    """
    Convert device name to full /dev path.

    Args:
        device_name: Device name (e.g., 'sde')

    Returns:
        Full device path (e.g., '/dev/sde')

    Example:
        >>> path = get_device_path('sde')
        >>> print(path)
        /dev/sde
    """
    return f'/dev/{device_name}'


# =============================================================================
# Device Opening
# =============================================================================


def open_device(device_path: str, read_only: bool = False) -> int:
    """
    Open block device for raw sector access.

    This function opens a block device with the correct flags for
    low-level disk operations:
    - O_DIRECT: Bypass kernel page cache for direct disk access
    - O_SYNC: Write immediately, don't buffer in memory
    - O_RDONLY or O_RDWR: Read-only or read-write access

    IMPORTANT: Requires root privileges (sudo)!

    Args:
        device_path: Full device path (e.g., '/dev/sde')
        read_only: If True, open with read-only access (default: False)

    Returns:
        File descriptor (integer)

    Raises:
        OSError: If device cannot be opened
        - EACCES (13): Permission denied - need root (sudo)
        - ENOENT (2): Device doesn't exist
        - ENODEV (19): No disk inserted

    Example:
        >>> # Read-only access for detection
        >>> fd = open_device('/dev/sde', read_only=True)
        >>> # ... perform operations ...
        >>> close_device(fd)

        >>> # Read-write access for formatting
        >>> fd = open_device('/dev/sde', read_only=False)
        >>> # ... perform operations ...
        >>> close_device(fd)
    """
    # Determine access flags
    if read_only:
        flags = os.O_RDONLY
    else:
        flags = os.O_RDWR

    # For WSL2 and USB devices, O_DIRECT often doesn't work
    # Use regular buffered I/O with O_SYNC for write safety
    try:
        # Open with just O_SYNC for synchronous writes
        # O_DIRECT causes EINVAL on many WSL2/USB setups
        flags |= os.O_SYNC
        fd = os.open(device_path, flags)
        logging.info(f"Opened {device_path} with buffered I/O")
        return fd

    except OSError as e:
        # Enhance error message with context
        error_code = e.errno
        error_msg = os.strerror(error_code)

        if error_code == errno.EACCES:
            raise OSError(
                error_code,
                f"Permission denied: {device_path}\n"
                f"Root privileges required. Run with: sudo python -m floppy_formatter"
            ) from e
        elif error_code == errno.ENOENT:
            raise OSError(
                error_code,
                f"Device not found: {device_path}\n"
                f"Make sure the USB floppy is attached to WSL.\n"
                f"Use: usbipd list\n"
                f"     usbipd attach --wsl --busid X-Y"
            ) from e
        elif error_code == errno.ENODEV:
            raise OSError(
                error_code,
                f"Device not ready: {device_path}\n"
                f"Make sure a floppy disk is inserted."
            ) from e
        else:
            raise OSError(
                error_code,
                f"Failed to open {device_path}: {error_msg}"
            ) from e


# =============================================================================
# Handle Management
# =============================================================================


def close_device(fd: int) -> None:
    """
    Safely close a device file descriptor.

    Args:
        fd: File descriptor to close

    Example:
        >>> fd = open_device('/dev/sde')
        >>> try:
        ...     # Do operations
        ...     pass
        ... finally:
        ...     close_device(fd)
    """
    if fd is not None and fd >= 0:
        try:
            os.close(fd)
        except OSError:
            # Ignore errors on close
            pass


def flush_device(fd: int) -> None:
    """
    Flush device buffers to ensure all writes are committed.

    This performs both filesystem sync and block device buffer flush.

    Args:
        fd: File descriptor to flush

    Example:
        >>> fd = open_device('/dev/sde', read_only=False)
        >>> # ... write operations ...
        >>> flush_device(fd)
        >>> close_device(fd)
    """
    try:
        # Sync file descriptor
        os.fsync(fd)

        # Flush block device buffers using ioctl BLKFLSBUF
        import fcntl
        BLKFLSBUF = 0x1261  # From linux/fs.h
        fcntl.ioctl(fd, BLKFLSBUF, 0)

    except OSError:
        # Ignore flush errors
        pass


# =============================================================================
# Context Manager for Safe Device Management
# =============================================================================


class DeviceContext:
    """
    Context manager for safe device access.

    Automatically opens and closes the device file descriptor,
    ensuring proper cleanup even if errors occur.

    Args:
        device_path: Full device path (e.g., '/dev/sde')
        read_only: If True, open read-only (default: False)

    Example:
        >>> with DeviceContext('/dev/sde', read_only=True) as fd:
        ...     # Read geometry or perform operations
        ...     pass

        >>> # File descriptor is automatically closed on exit

        >>> with DeviceContext('/dev/sde', read_only=False) as fd:
        ...     # Write operations
        ...     pass
        ...     # Automatically flushed and closed on exit
    """

    def __init__(self, device_path: str, read_only: bool = False):
        """Initialize context manager."""
        self.device_path = device_path
        self.read_only = read_only
        self.fd = None

    def __enter__(self):
        """Open the device."""
        self.fd = open_device(self.device_path, self.read_only)
        return self.fd

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the device, flushing buffers if write mode."""
        if self.fd is not None:
            try:
                # Flush any pending writes
                if not self.read_only:
                    flush_device(self.fd)
            except Exception:
                pass  # Ignore flush errors

            # Close the file descriptor
            close_device(self.fd)

        # Don't suppress exceptions
        return False


# =============================================================================
# Utility Functions
# =============================================================================


def is_device_accessible(device_path: str) -> bool:
    """
    Check if a device exists and is accessible.

    Args:
        device_path: Full device path (e.g., '/dev/sde')

    Returns:
        True if device can be opened, False otherwise

    Example:
        >>> if is_device_accessible('/dev/sde'):
        ...     print("Device is accessible")
    """
    try:
        fd = open_device(device_path, read_only=True)
        close_device(fd)
        return True
    except OSError:
        return False


def enumerate_devices() -> List[str]:
    """
    Enumerate all accessible floppy devices.

    Returns:
        List of accessible device paths (e.g., ['/dev/sde', '/dev/sdf'])

    Example:
        >>> devices = enumerate_devices()
        >>> print(f"Found {len(devices)} floppy drives: {devices}")
        Found 1 floppy drives: ['/dev/sde']
    """
    device_names = find_floppy_devices()
    device_paths = [get_device_path(name) for name in device_names]
    return device_paths


def get_device_description(device_path: str) -> str:
    """
    Get a human-readable description of a device.

    Args:
        device_path: Full device path (e.g., '/dev/sde')

    Returns:
        Description string with geometry information

    Example:
        >>> desc = get_device_description('/dev/sde')
        >>> print(desc)
        /dev/sde: 1.44 MB Floppy (80 cyl, 2 heads, 18 sec/track)
    """
    try:
        from floppy_formatter.core.geometry import get_disk_geometry

        with DeviceContext(device_path, read_only=True) as fd:
            geometry = get_disk_geometry(fd)

            # Calculate capacity
            total_sectors = (geometry.cylinders *
                           geometry.heads *
                           geometry.sectors_per_track)
            capacity_bytes = total_sectors * geometry.bytes_per_sector
            capacity_mb = capacity_bytes / (1024 * 1024)

            # Determine drive type
            if (geometry.cylinders == 80 and geometry.heads == 2 and
                geometry.sectors_per_track == 18):
                drive_type = "1.44 MB Floppy"
            elif (geometry.cylinders == 80 and geometry.heads == 2 and
                  geometry.sectors_per_track == 9):
                drive_type = "720 KB Floppy"
            else:
                drive_type = f"{capacity_mb:.2f} MB Drive"

            return (
                f"{device_path}: {drive_type} "
                f"({geometry.cylinders} cyl, {geometry.heads} heads, "
                f"{geometry.sectors_per_track} sec/track)"
            )

    except Exception as e:
        return f"{device_path}: Error - {e}"


# =============================================================================
# Backward Compatibility Helpers
# =============================================================================


def find_floppy_physical_drive(drive_letter: str = 'A') -> str:
    """
    Find floppy device (backward compatibility wrapper).

    On Linux, drive letters don't exist. This function finds the first
    available floppy device.

    Args:
        drive_letter: Ignored on Linux (for API compatibility)

    Returns:
        Device name (e.g., 'sde')

    Raises:
        IOError: If no floppy drives found

    Example:
        >>> device = find_floppy_physical_drive()
        >>> print(f"Found floppy: {device}")
        Found floppy: sde
    """
    devices = find_floppy_devices()
    if devices:
        return devices[0]  # Return first device
    else:
        raise IOError("No floppy drives found")
