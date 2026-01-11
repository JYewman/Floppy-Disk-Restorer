"""
Disk geometry detection and validation for Linux/WSL2.

This module provides functions to read disk geometry using Linux ioctl
and validate that disks match expected 1.44MB floppy specifications.
"""

import os
import struct
import fcntl
from dataclasses import dataclass
from typing import Optional


# Linux ioctl constants from linux/hdreg.h
HDIO_GETGEO = 0x0301  # Get drive geometry

# Linux ioctl constants from linux/fs.h
BLKGETSIZE64 = 0x80081272  # Get device size in bytes

# Standard floppy specifications
MEDIA_TYPE_F3_1Pt44_512 = 0x0F
CYLINDERS_1PT44MB = 80
HEADS_PER_CYLINDER_1PT44MB = 2
SECTORS_PER_TRACK_1PT44MB = 18
BYTES_PER_SECTOR = 512
TOTAL_SECTORS_1PT44MB = 2880


# =============================================================================
# Disk Geometry Data Class
# =============================================================================


@dataclass
class DiskGeometry:
    """
    Disk geometry information for a floppy disk.

    This class represents the physical layout of a disk, obtained from
    ioctl(HDIO_GETGEO) on Linux. The geometry is readable even on
    unformatted disks or disks with bad sector 0.

    Attributes:
        media_type: Media type constant (0x0F for 1.44MB)
        cylinders: Number of cylinders/tracks per side (80 for 1.44MB)
        heads: Number of heads/sides (2 for 1.44MB)
        sectors_per_track: Sectors per track (18 for 1.44MB)
        bytes_per_sector: Bytes per sector (512 for standard floppies)

    Calculated Properties:
        total_sectors: Total number of sectors on disk
        total_bytes: Total capacity in bytes

    Example:
        >>> geometry = DiskGeometry(
        ...     media_type=0x0F,
        ...     cylinders=80,
        ...     heads=2,
        ...     sectors_per_track=18,
        ...     bytes_per_sector=512
        ... )
        >>> print(f"Capacity: {geometry.total_bytes / 1024 / 1024:.2f} MB")
        Capacity: 1.44 MB
    """
    media_type: int
    cylinders: int
    heads: int
    sectors_per_track: int
    bytes_per_sector: int

    @property
    def total_sectors(self) -> int:
        """Calculate total number of sectors on disk."""
        return self.cylinders * self.heads * self.sectors_per_track

    @property
    def total_bytes(self) -> int:
        """Calculate total capacity in bytes."""
        return self.total_sectors * self.bytes_per_sector

    @property
    def total_tracks(self) -> int:
        """Calculate total number of tracks (cylinders × heads)."""
        return self.cylinders * self.heads

    def is_1_44mb_floppy(self) -> bool:
        """
        Check if geometry matches 1.44MB floppy disk.

        Returns:
            True if this is a standard 1.44MB floppy

        Example:
            >>> if geometry.is_1_44mb_floppy():
            ...     print("Standard 1.44MB floppy detected")
        """
        return (
            self.cylinders == 80 and
            self.heads == 2 and
            self.sectors_per_track == 18 and
            self.bytes_per_sector == 512
        )

    def is_720kb_floppy(self) -> bool:
        """
        Check if geometry matches 720KB floppy disk.

        Returns:
            True if this is a 720KB floppy

        Example:
            >>> if geometry.is_720kb_floppy():
            ...     print("720KB floppy detected")
        """
        return (
            self.cylinders == 80 and
            self.heads == 2 and
            self.sectors_per_track == 9 and
            self.bytes_per_sector == 512
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        capacity_mb = self.total_bytes / (1024 * 1024)
        return (
            f"DiskGeometry("
            f"media=0x{self.media_type:02X}, "
            f"{self.cylinders}C/{self.heads}H/{self.sectors_per_track}S, "
            f"{self.bytes_per_sector}B/sec, "
            f"{capacity_mb:.2f}MB)"
        )

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"DiskGeometry(media_type=0x{self.media_type:02X}, "
            f"cylinders={self.cylinders}, "
            f"heads={self.heads}, "
            f"sectors_per_track={self.sectors_per_track}, "
            f"bytes_per_sector={self.bytes_per_sector})"
        )


# =============================================================================
# Geometry Reading
# =============================================================================


def get_disk_geometry(fd: int) -> DiskGeometry:
    """
    Read disk geometry using ioctl(HDIO_GETGEO).

    This ioctl works on unformatted disks and disks with bad sector 0,
    making it perfect for our use case. The geometry is read from the
    drive controller, not from the filesystem.

    On Linux, if HDIO_GETGEO fails (common on USB devices), we fall back
    to detecting geometry by device size.

    Args:
        fd: File descriptor from open_device()

    Returns:
        DiskGeometry object with disk layout information

    Raises:
        OSError: If ioctl fails and fallback detection fails

    Example:
        >>> from floppy_formatter.core.device_manager import open_device, close_device
        >>> fd = open_device('/dev/sde', read_only=True)
        >>> geometry = get_disk_geometry(fd)
        >>> print(geometry)
        DiskGeometry(media=0x0F, 80C/2H/18S, 512B/sec, 1.44MB)
        >>> close_device(fd)
    """
    try:
        # Try ioctl(HDIO_GETGEO) first
        # struct hd_geometry { u8 heads, u8 sectors, u16 cylinders, u32 start }
        # Total: 8 bytes
        buf = bytearray(8)
        fcntl.ioctl(fd, HDIO_GETGEO, buf)

        # Parse struct hd_geometry
        heads, sectors, cylinders, start = struct.unpack('BBHI', buf)

        # Validate geometry - many USB floppy drives return garbage from HDIO_GETGEO
        # If the geometry doesn't match any known floppy format, use size-based fallback
        is_valid_1_44mb = (cylinders == 80 and heads == 2 and sectors == 18)
        is_valid_720kb = (cylinders == 80 and heads == 2 and sectors == 9)

        if not (is_valid_1_44mb or is_valid_720kb):
            # HDIO_GETGEO returned invalid geometry (common on USB drives)
            # Raise OSError to trigger fallback to size-based detection
            raise OSError("HDIO_GETGEO returned invalid geometry, using size-based detection")

        # Determine media type based on geometry
        if is_valid_1_44mb:
            media_type = MEDIA_TYPE_F3_1Pt44_512
        elif is_valid_720kb:
            media_type = 0x05  # 720KB
        else:
            media_type = 0x00  # Unknown

        return DiskGeometry(
            media_type=media_type,
            cylinders=cylinders,
            heads=heads,
            sectors_per_track=sectors,
            bytes_per_sector=BYTES_PER_SECTOR
        )

    except OSError:
        # HDIO_GETGEO failed or returned invalid data (common on USB floppy drives)
        # Fall back to detection by device size
        try:
            # Get device size using BLKGETSIZE64
            size_buf = bytearray(8)
            fcntl.ioctl(fd, BLKGETSIZE64, size_buf)
            device_bytes = struct.unpack('Q', size_buf)[0]

            # Check if it's a 1.44MB floppy (1474560 bytes)
            if device_bytes == 1474560:
                return DiskGeometry(
                    media_type=MEDIA_TYPE_F3_1Pt44_512,
                    cylinders=CYLINDERS_1PT44MB,
                    heads=HEADS_PER_CYLINDER_1PT44MB,
                    sectors_per_track=SECTORS_PER_TRACK_1PT44MB,
                    bytes_per_sector=BYTES_PER_SECTOR
                )
            # Check if it's a 720KB floppy (737280 bytes)
            elif device_bytes == 737280:
                return DiskGeometry(
                    media_type=0x05,
                    cylinders=80,
                    heads=2,
                    sectors_per_track=9,
                    bytes_per_sector=BYTES_PER_SECTOR
                )
            else:
                raise OSError(
                    f"Unknown floppy size: {device_bytes} bytes. "
                    f"Expected 1474560 (1.44MB) or 737280 (720KB)."
                )

        except OSError as e:
            raise OSError(
                f"Failed to read disk geometry: {e}. "
                f"Make sure a floppy disk is inserted."
            ) from e


# =============================================================================
# Geometry Validation
# =============================================================================


def validate_floppy_geometry(geometry: DiskGeometry,
                            strict: bool = True) -> tuple[bool, Optional[str]]:
    """
    Validate that geometry matches expected floppy disk specifications.

    Args:
        geometry: DiskGeometry object to validate
        strict: If True, require exact 1.44MB match. If False, accept 720KB too.

    Returns:
        Tuple of (valid: bool, error_message: str or None)

    Example:
        >>> geometry = get_disk_geometry(fd)
        >>> valid, error = validate_floppy_geometry(geometry)
        >>> if not valid:
        ...     print(f"Invalid geometry: {error}")
        >>> else:
        ...     print("Valid 1.44MB floppy")
    """
    # Check for 1.44MB floppy
    if geometry.is_1_44mb_floppy():
        return (True, None)

    # If not strict, accept 720KB too
    if not strict and geometry.is_720kb_floppy():
        return (True, None)

    # Invalid geometry - build error message
    expected = "1.44MB (80/2/18/512)" if strict else "1.44MB or 720KB"
    actual = (
        f"{geometry.cylinders}/{geometry.heads}/"
        f"{geometry.sectors_per_track}/{geometry.bytes_per_sector}"
    )

    error_message = (
        f"Invalid floppy geometry.\n"
        f"Expected: {expected}\n"
        f"Actual: {actual}\n"
        f"This may not be a standard floppy disk."
    )

    return (False, error_message)


def validate_1_44mb_geometry(geometry: DiskGeometry) -> bool:
    """
    Strict validation for 1.44MB floppy geometry.

    Args:
        geometry: DiskGeometry object to validate

    Returns:
        True if geometry is exactly 1.44MB floppy

    Example:
        >>> if validate_1_44mb_geometry(geometry):
        ...     print("Ready for 1.44MB operations")
    """
    return geometry.is_1_44mb_floppy()


# =============================================================================
# Geometry Information
# =============================================================================


def get_geometry_summary(geometry: DiskGeometry) -> str:
    """
    Get a human-readable summary of disk geometry.

    Args:
        geometry: DiskGeometry object

    Returns:
        Multi-line string with geometry details

    Example:
        >>> summary = get_geometry_summary(geometry)
        >>> print(summary)
        Disk Geometry Summary
        =====================
        Media Type: 0x0F (1.44MB Floppy)
        Cylinders: 80
        Heads: 2
        Sectors/Track: 18
        Bytes/Sector: 512
        Total Sectors: 2,880
        Total Capacity: 1.44 MB (1,474,560 bytes)
    """
    # Determine media description
    if geometry.is_1_44mb_floppy():
        media_desc = "0x0F (1.44MB Floppy)"
    elif geometry.is_720kb_floppy():
        media_desc = "0x05 (720KB Floppy)"
    else:
        media_desc = f"0x{geometry.media_type:02X} (Unknown)"

    capacity_mb = geometry.total_bytes / (1024 * 1024)

    return f"""Disk Geometry Summary
=====================
Media Type: {media_desc}
Cylinders: {geometry.cylinders}
Heads: {geometry.heads}
Sectors/Track: {geometry.sectors_per_track}
Bytes/Sector: {geometry.bytes_per_sector}
Total Sectors: {geometry.total_sectors:,}
Total Capacity: {capacity_mb:.2f} MB ({geometry.total_bytes:,} bytes)"""


def compare_geometries(geo1: DiskGeometry, geo2: DiskGeometry) -> dict:
    """
    Compare two disk geometries.

    Args:
        geo1: First geometry
        geo2: Second geometry

    Returns:
        Dictionary with comparison results

    Example:
        >>> before = get_disk_geometry(fd)
        >>> # ... format disk ...
        >>> after = get_disk_geometry(fd)
        >>> diff = compare_geometries(before, after)
        >>> if diff['identical']:
        ...     print("Geometry unchanged")
    """
    return {
        'identical': (
            geo1.media_type == geo2.media_type and
            geo1.cylinders == geo2.cylinders and
            geo1.heads == geo2.heads and
            geo1.sectors_per_track == geo2.sectors_per_track and
            geo1.bytes_per_sector == geo2.bytes_per_sector
        ),
        'media_type_changed': geo1.media_type != geo2.media_type,
        'cylinders_changed': geo1.cylinders != geo2.cylinders,
        'heads_changed': geo1.heads != geo2.heads,
        'sectors_changed': geo1.sectors_per_track != geo2.sectors_per_track,
        'bytes_per_sector_changed': geo1.bytes_per_sector != geo2.bytes_per_sector,
    }


# =============================================================================
# Standard Geometry Constants
# =============================================================================


def get_standard_1_44mb_geometry() -> DiskGeometry:
    """
    Get the standard 1.44MB floppy geometry.

    Returns:
        DiskGeometry object with 1.44MB specifications

    Example:
        >>> standard = get_standard_1_44mb_geometry()
        >>> actual = get_disk_geometry(fd)
        >>> if actual.is_1_44mb_floppy():
        ...     print("Matches standard 1.44MB")
    """
    return DiskGeometry(
        media_type=MEDIA_TYPE_F3_1Pt44_512,
        cylinders=CYLINDERS_1PT44MB,
        heads=HEADS_PER_CYLINDER_1PT44MB,
        sectors_per_track=SECTORS_PER_TRACK_1PT44MB,
        bytes_per_sector=BYTES_PER_SECTOR
    )


def get_standard_720kb_geometry() -> DiskGeometry:
    """
    Get the standard 720KB floppy geometry.

    Returns:
        DiskGeometry object with 720KB specifications

    Example:
        >>> standard_720 = get_standard_720kb_geometry()
    """
    return DiskGeometry(
        media_type=0x05,  # MEDIA_TYPE_F3_720_512
        cylinders=80,
        heads=2,
        sectors_per_track=9,
        bytes_per_sector=512
    )
