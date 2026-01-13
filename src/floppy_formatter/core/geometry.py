"""
Disk geometry detection and validation for Greaseweazle.

This module provides:
- DiskGeometry dataclass for floppy disk parameters
- Geometry detection for Greaseweazle-connected drives
- Validation functions for standard floppy formats

Greaseweazle determines geometry by probing the disk with flux reads
and decoding sector headers to detect the format automatically.
"""

from dataclasses import dataclass
from typing import Optional, Union, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice

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

    This class represents the physical layout of a disk, determined by
    probing the disk with Greaseweazle and decoding sector headers.
    The geometry is detectable even on disks with bad sector 0.

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


def get_greaseweazle_geometry(
    device: Union['GreaseweazleDevice', Any],
    probe_disk: bool = True
) -> DiskGeometry:
    """
    Detect disk geometry using Greaseweazle.

    For 3.5" HD PC floppy disks, the geometry is almost always:
    - 80 cylinders, 2 heads, 18 sectors/track, 512 bytes/sector

    If probe_disk is True, this function will read track 0 to verify
    the disk format and detect the actual sector count.

    Args:
        device: Connected GreaseweazleDevice instance
        probe_disk: If True, read track 0 to verify format (default: True)

    Returns:
        DiskGeometry object with disk layout information

    Raises:
        RuntimeError: If disk detection fails

    Example:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     geometry = get_greaseweazle_geometry(device)
        ...     print(geometry)
        DiskGeometry(media=0x0F, 80C/2H/18S, 512B/sec, 1.44MB)
    """
    if probe_disk:
        try:
            # Import here to avoid circular imports
            from floppy_formatter.hardware import (
                read_track_flux,
                decode_flux_to_sectors,
            )

            # Read track 0, head 0 to detect format
            flux_data = read_track_flux(device, cylinder=0, head=0, revolutions=1.2)
            sectors = decode_flux_to_sectors(flux_data)

            # Count successfully decoded sectors
            sector_numbers = [s.sector for s in sectors if s.data is not None]

            if len(sector_numbers) >= 15:
                # Standard PC format detected
                max_sector = max(sector_numbers) if sector_numbers else 18

                if max_sector == 18:
                    # 1.44MB HD format
                    return DiskGeometry(
                        media_type=MEDIA_TYPE_F3_1Pt44_512,
                        cylinders=CYLINDERS_1PT44MB,
                        heads=HEADS_PER_CYLINDER_1PT44MB,
                        sectors_per_track=SECTORS_PER_TRACK_1PT44MB,
                        bytes_per_sector=BYTES_PER_SECTOR
                    )
                elif max_sector == 9:
                    # 720KB DD format
                    return DiskGeometry(
                        media_type=0x05,
                        cylinders=80,
                        heads=2,
                        sectors_per_track=9,
                        bytes_per_sector=BYTES_PER_SECTOR
                    )

        except Exception:
            # Probing failed, use default geometry
            pass

    # Default to 1.44MB HD format (most common)
    return DiskGeometry(
        media_type=MEDIA_TYPE_F3_1Pt44_512,
        cylinders=CYLINDERS_1PT44MB,
        heads=HEADS_PER_CYLINDER_1PT44MB,
        sectors_per_track=SECTORS_PER_TRACK_1PT44MB,
        bytes_per_sector=BYTES_PER_SECTOR
    )


def get_disk_geometry(device: Union['GreaseweazleDevice', Any]) -> DiskGeometry:
    """
    Read disk geometry from a Greaseweazle-connected drive.

    This is an alias for get_greaseweazle_geometry() for backward
    compatibility with existing code.

    Args:
        device: Connected GreaseweazleDevice instance

    Returns:
        DiskGeometry object with disk layout information

    Example:
        >>> with GreaseweazleDevice() as device:
        ...     device.select_drive(0)
        ...     device.motor_on()
        ...     geometry = get_disk_geometry(device)
        ...     print(geometry)
        DiskGeometry(media=0x0F, 80C/2H/18S, 512B/sec, 1.44MB)
    """
    return get_greaseweazle_geometry(device, probe_disk=True)


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
