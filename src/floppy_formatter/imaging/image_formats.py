"""
Image format detection and metadata extraction for floppy disk images.

This module provides format detection, metadata reading, and validation
for various floppy disk image formats including sector-level (IMG, IMA, DSK)
and flux-level (SCP, HFE) formats.

Supported Formats:
    - IMG/IMA: Raw sector images (no header)
    - DSK: CPC/Spectrum DSK format with header
    - SCP: SuperCard Pro flux image
    - HFE: HxC Floppy Emulator flux image

Part of Phase 11: Image Import/Export
"""

import logging
import os
import struct
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class ImageError(Exception):
    """Base exception for image-related errors."""

    def __init__(self, message: str, filepath: Optional[str] = None):
        self.message = message
        self.filepath = filepath
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.filepath:
            return f"{self.message} [File: {self.filepath}]"
        return self.message


class ImageFormatError(ImageError):
    """Raised when image format is invalid or unsupported."""

    def __init__(self, message: str, filepath: Optional[str] = None,
                 detected_format: Optional[str] = None):
        self.detected_format = detected_format
        super().__init__(message, filepath)

    def _format_message(self) -> str:
        base = super()._format_message()
        if self.detected_format:
            return f"{base} [Detected: {self.detected_format}]"
        return base


class ImageCorruptError(ImageError):
    """Raised when image file is corrupt or incomplete."""

    def __init__(self, message: str, filepath: Optional[str] = None,
                 expected_size: Optional[int] = None,
                 actual_size: Optional[int] = None):
        self.expected_size = expected_size
        self.actual_size = actual_size
        super().__init__(message, filepath)

    def _format_message(self) -> str:
        base = super()._format_message()
        if self.expected_size is not None and self.actual_size is not None:
            return f"{base} [Expected: {self.expected_size}, Actual: {self.actual_size}]"
        return base


class ImageGeometryError(ImageError):
    """Raised when image geometry is invalid or mismatched."""

    def __init__(self, message: str, filepath: Optional[str] = None,
                 cylinders: Optional[int] = None,
                 heads: Optional[int] = None,
                 sectors: Optional[int] = None):
        self.cylinders = cylinders
        self.heads = heads
        self.sectors = sectors
        super().__init__(message, filepath)

    def _format_message(self) -> str:
        base = super()._format_message()
        if self.cylinders is not None:
            return f"{base} [C:{self.cylinders} H:{self.heads} S:{self.sectors}]"
        return base


class ImageReadError(ImageError):
    """Raised when reading image file fails."""
    pass


class ImageWriteError(ImageError):
    """Raised when writing image file fails."""
    pass


# =============================================================================
# Enums and Constants
# =============================================================================

class ImageFormat(Enum):
    """Supported disk image formats."""
    IMG = auto()      # Raw sector image (no header)
    IMA = auto()      # Raw sector image (same as IMG)
    DSK = auto()      # CPC/Spectrum DSK format with header
    SCP = auto()      # SuperCard Pro flux image
    HFE = auto()      # HxC Floppy Emulator flux image
    UNKNOWN = auto()  # Unrecognized format


# Magic bytes for format detection
SCP_MAGIC = b'SCP'
HFE_MAGIC = b'HXCPICFE'
DSK_MAGIC = b'MV - CPC'  # Extended DSK format
DSK_MAGIC_ALT = b'EXTENDED'  # Alternative DSK header

# Standard floppy geometries (for raw image size detection)
STANDARD_GEOMETRIES = [
    # (cylinders, heads, sectors_per_track, sector_size, name)
    (80, 2, 18, 512, "3.5\" HD (1.44MB)"),      # 1,474,560 bytes
    (80, 2, 9, 512, "3.5\" DD (720KB)"),        # 737,280 bytes
    (80, 2, 15, 512, "5.25\" HD (1.2MB)"),      # 1,228,800 bytes
    (40, 2, 9, 512, "5.25\" DD (360KB)"),       # 368,640 bytes
    (80, 1, 18, 512, "3.5\" HD SS (720KB)"),    # 737,280 bytes
    (80, 1, 9, 512, "3.5\" DD SS (360KB)"),     # 368,640 bytes
    (40, 1, 9, 512, "5.25\" DD SS (180KB)"),    # 184,320 bytes
    (77, 2, 26, 256, "8\" DSDD (500KB)"),       # 512,512 bytes (close)
    (80, 2, 36, 512, "3.5\" ED (2.88MB)"),      # 2,949,120 bytes
]

# File extension mappings
EXTENSION_MAP: Dict[str, ImageFormat] = {
    '.img': ImageFormat.IMG,
    '.ima': ImageFormat.IMA,
    '.bin': ImageFormat.IMG,
    '.raw': ImageFormat.IMG,
    '.dsk': ImageFormat.DSK,
    '.scp': ImageFormat.SCP,
    '.hfe': ImageFormat.HFE,
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ImageMetadata:
    """
    Metadata for a disk image file.

    Attributes:
        format: Detected image format
        filename: Name of the image file
        file_size: Size of the file in bytes
        cylinders: Number of cylinders
        heads: Number of heads (sides)
        sectors_per_track: Sectors per track
        sector_size: Size of each sector in bytes
        total_sectors: Total number of sectors
        is_flux_image: True if flux-level image (SCP, HFE)
        has_header: True if image has a header structure
        creation_date: Creation date if available
        description: Description string if available
        revolutions: Number of revolutions (for flux images)
        bit_rate: Bit rate in Hz (for flux images)
        encoding: Encoding type (MFM, FM, etc.)
    """
    format: ImageFormat
    filename: str
    file_size: int
    cylinders: int = 80
    heads: int = 2
    sectors_per_track: int = 18
    sector_size: int = 512
    total_sectors: int = 0
    is_flux_image: bool = False
    has_header: bool = False
    creation_date: Optional[datetime] = None
    description: str = ""
    revolutions: int = 1
    bit_rate: int = 250000
    encoding: str = "MFM"

    def __post_init__(self):
        """Calculate total sectors if not provided."""
        if self.total_sectors == 0:
            self.total_sectors = self.cylinders * self.heads * self.sectors_per_track

    @property
    def capacity_bytes(self) -> int:
        """Calculate total capacity in bytes."""
        return self.total_sectors * self.sector_size

    @property
    def capacity_kb(self) -> float:
        """Calculate total capacity in kilobytes."""
        return self.capacity_bytes / 1024.0

    @property
    def capacity_mb(self) -> float:
        """Calculate total capacity in megabytes."""
        return self.capacity_bytes / (1024.0 * 1024.0)

    @property
    def geometry_string(self) -> str:
        """Get geometry as a string."""
        return f"{self.cylinders}/{self.heads}/{self.sectors_per_track}"

    @property
    def format_name(self) -> str:
        """Get human-readable format name."""
        names = {
            ImageFormat.IMG: "Raw Sector Image",
            ImageFormat.IMA: "Raw Sector Image",
            ImageFormat.DSK: "CPC DSK Image",
            ImageFormat.SCP: "SuperCard Pro Flux",
            ImageFormat.HFE: "HxC Floppy Emulator",
            ImageFormat.UNKNOWN: "Unknown",
        }
        return names.get(self.format, "Unknown")


# =============================================================================
# Format Detection
# =============================================================================

def detect_format(filepath: str) -> ImageFormat:
    """
    Detect image format by file extension and magic bytes.

    Checks for format-specific magic bytes first, then falls back
    to extension-based detection.

    Args:
        filepath: Path to the image file

    Returns:
        Detected ImageFormat enum value

    Raises:
        ImageReadError: If file cannot be read
    """
    path = Path(filepath)

    if not path.exists():
        raise ImageReadError(f"File does not exist", filepath)

    if not path.is_file():
        raise ImageReadError(f"Path is not a file", filepath)

    logger.debug("Detecting format for: %s", filepath)

    # Try to read magic bytes
    try:
        with open(filepath, 'rb') as f:
            header = f.read(16)
    except IOError as e:
        raise ImageReadError(f"Failed to read file: {e}", filepath)

    if len(header) < 3:
        # File too small for magic detection
        logger.debug("File too small for magic detection, using extension")
        return _detect_by_extension(filepath)

    # Check for SCP magic bytes
    if header[:3] == SCP_MAGIC:
        logger.debug("Detected SCP format by magic bytes")
        return ImageFormat.SCP

    # Check for HFE magic bytes
    if header[:8] == HFE_MAGIC:
        logger.debug("Detected HFE format by magic bytes")
        return ImageFormat.HFE

    # Check for DSK magic bytes
    if header[:8] == DSK_MAGIC or header[:8] == DSK_MAGIC_ALT:
        logger.debug("Detected DSK format by magic bytes")
        return ImageFormat.DSK

    # Check for extended DSK
    if b'MV - CPC' in header or b'EXTENDED' in header:
        logger.debug("Detected DSK format by header content")
        return ImageFormat.DSK

    # Fall back to extension detection
    return _detect_by_extension(filepath)


def _detect_by_extension(filepath: str) -> ImageFormat:
    """Detect format by file extension."""
    ext = Path(filepath).suffix.lower()

    if ext in EXTENSION_MAP:
        logger.debug("Detected format by extension: %s -> %s", ext, EXTENSION_MAP[ext])
        return EXTENSION_MAP[ext]

    logger.debug("Unknown extension: %s", ext)
    return ImageFormat.UNKNOWN


# =============================================================================
# Metadata Reading
# =============================================================================

def read_metadata(filepath: str) -> ImageMetadata:
    """
    Read and parse image file header/structure.

    Extracts geometry and other metadata from the image file
    based on its format.

    Args:
        filepath: Path to the image file

    Returns:
        ImageMetadata with extracted information

    Raises:
        ImageReadError: If file cannot be read
        ImageFormatError: If format is unsupported
    """
    path = Path(filepath)

    if not path.exists():
        raise ImageReadError(f"File does not exist", filepath)

    file_size = path.stat().st_size
    format_type = detect_format(filepath)

    logger.debug("Reading metadata for %s (format: %s, size: %d)",
                 filepath, format_type.name, file_size)

    # Get creation date from file stats
    try:
        stat_info = path.stat()
        creation_date = datetime.fromtimestamp(stat_info.st_ctime)
    except (OSError, ValueError):
        creation_date = None

    # Handle each format type
    if format_type == ImageFormat.SCP:
        return _read_scp_metadata(filepath, file_size, creation_date)
    elif format_type == ImageFormat.HFE:
        return _read_hfe_metadata(filepath, file_size, creation_date)
    elif format_type == ImageFormat.DSK:
        return _read_dsk_metadata(filepath, file_size, creation_date)
    elif format_type in (ImageFormat.IMG, ImageFormat.IMA):
        return _read_raw_metadata(filepath, file_size, format_type, creation_date)
    else:
        # Unknown format - try raw image detection
        return _read_raw_metadata(filepath, file_size, ImageFormat.UNKNOWN, creation_date)


def _read_raw_metadata(filepath: str, file_size: int,
                       format_type: ImageFormat,
                       creation_date: Optional[datetime]) -> ImageMetadata:
    """Read metadata from raw sector image (IMG/IMA)."""
    filename = Path(filepath).name

    # Try to match file size to known geometry
    cylinders, heads, sectors, sector_size = _infer_geometry_from_size(file_size)

    return ImageMetadata(
        format=format_type,
        filename=filename,
        file_size=file_size,
        cylinders=cylinders,
        heads=heads,
        sectors_per_track=sectors,
        sector_size=sector_size,
        total_sectors=cylinders * heads * sectors,
        is_flux_image=False,
        has_header=False,
        creation_date=creation_date,
        description=_get_geometry_description(cylinders, heads, sectors, sector_size),
    )


def _read_scp_metadata(filepath: str, file_size: int,
                       creation_date: Optional[datetime]) -> ImageMetadata:
    """Read metadata from SCP flux image."""
    filename = Path(filepath).name

    try:
        with open(filepath, 'rb') as f:
            header = f.read(16)
    except IOError as e:
        raise ImageReadError(f"Failed to read SCP header: {e}", filepath)

    if len(header) < 16:
        raise ImageCorruptError("SCP header too short", filepath,
                               expected_size=16, actual_size=len(header))

    # SCP header structure (16 bytes):
    # 0-2: "SCP" magic
    # 3: version
    # 4: disk type
    # 5: number of revolutions
    # 6: start track
    # 7: end track
    # 8: flags
    # 9: bit cell width (0 = 16bit, non-zero = 8bit)
    # 10: heads (0=both, 1=side0, 2=side1)
    # 11: resolution (25ns units, 0=25ns)
    # 12-15: checksum

    version = header[3]
    disk_type = header[4]
    revolutions = header[5] if header[5] > 0 else 1
    start_track = header[6]
    end_track = header[7]
    flags = header[8]
    heads_flag = header[10]

    # Calculate geometry from track range
    # Tracks are numbered 0-159 for double-sided (track = cyl*2 + head)
    total_tracks = end_track - start_track + 1

    if heads_flag == 0:  # Both sides
        heads = 2
        cylinders = (total_tracks + 1) // 2
    else:
        heads = 1
        cylinders = total_tracks

    # SCP doesn't store sector info (it's flux-level)
    # Use standard geometry for description
    sectors_per_track = 18  # Assume HD
    sector_size = 512

    description = f"SCP v{version}, {revolutions} rev, tracks {start_track}-{end_track}"

    return ImageMetadata(
        format=ImageFormat.SCP,
        filename=filename,
        file_size=file_size,
        cylinders=cylinders,
        heads=heads,
        sectors_per_track=sectors_per_track,
        sector_size=sector_size,
        total_sectors=cylinders * heads * sectors_per_track,
        is_flux_image=True,
        has_header=True,
        creation_date=creation_date,
        description=description,
        revolutions=revolutions,
        bit_rate=250000,  # Default MFM HD
        encoding="MFM",
    )


def _read_hfe_metadata(filepath: str, file_size: int,
                       creation_date: Optional[datetime]) -> ImageMetadata:
    """Read metadata from HFE flux image."""
    filename = Path(filepath).name

    try:
        with open(filepath, 'rb') as f:
            header = f.read(512)
    except IOError as e:
        raise ImageReadError(f"Failed to read HFE header: {e}", filepath)

    if len(header) < 512:
        raise ImageCorruptError("HFE header too short", filepath,
                               expected_size=512, actual_size=len(header))

    # HFE header structure (512 bytes):
    # 0-7: "HXCPICFE" magic
    # 8: revision (0)
    # 9: number of tracks
    # 10: number of sides
    # 11: track encoding (0=ISO_IBM_MFM, 1=AMIGA_MFM, etc.)
    # 12-13: bit rate (little-endian, in units of 250 bits/s)
    # 14-15: RPM (little-endian, 0=300)
    # 16: interface mode (0=IBM_PC_DD_FLOPY, etc.)
    # 17: reserved (1)
    # 18-19: track list offset (little-endian)

    revision = header[8]
    num_tracks = header[9]
    num_sides = header[10]
    track_encoding = header[11]
    bit_rate_raw = struct.unpack('<H', header[12:14])[0]
    rpm_raw = struct.unpack('<H', header[14:16])[0]
    interface_mode = header[16]
    track_list_offset = struct.unpack('<H', header[18:20])[0]

    # Calculate geometry
    cylinders = num_tracks
    heads = num_sides if num_sides > 0 else 1

    # Bit rate is in units of 250 bits/s
    bit_rate = bit_rate_raw * 250 if bit_rate_raw > 0 else 250000
    rpm = rpm_raw if rpm_raw > 0 else 300

    # Encoding type names
    encoding_names = {
        0: "MFM",
        1: "AMIGA_MFM",
        2: "MFM_HD",
        3: "FM",
        4: "EMU_FM",
        5: "UNKNOWN",
    }
    encoding = encoding_names.get(track_encoding, "UNKNOWN")

    # HFE doesn't store sector info (flux-level)
    sectors_per_track = 18  # Assume HD
    sector_size = 512

    description = f"HFE rev{revision}, {num_tracks} tracks, {encoding} @ {bit_rate}bps"

    return ImageMetadata(
        format=ImageFormat.HFE,
        filename=filename,
        file_size=file_size,
        cylinders=cylinders,
        heads=heads,
        sectors_per_track=sectors_per_track,
        sector_size=sector_size,
        total_sectors=cylinders * heads * sectors_per_track,
        is_flux_image=True,
        has_header=True,
        creation_date=creation_date,
        description=description,
        revolutions=1,
        bit_rate=bit_rate,
        encoding=encoding,
    )


def _read_dsk_metadata(filepath: str, file_size: int,
                       creation_date: Optional[datetime]) -> ImageMetadata:
    """Read metadata from CPC DSK image."""
    filename = Path(filepath).name

    try:
        with open(filepath, 'rb') as f:
            header = f.read(256)
    except IOError as e:
        raise ImageReadError(f"Failed to read DSK header: {e}", filepath)

    if len(header) < 256:
        raise ImageCorruptError("DSK header too short", filepath,
                               expected_size=256, actual_size=len(header))

    # DSK header structure:
    # 0-33: Identifier string
    # 34-47: Creator name
    # 48: Number of tracks
    # 49: Number of sides
    # 50-51: Track size (little-endian) OR size table for extended DSK
    # 52-255: Size table for extended DSK

    # Check if extended DSK
    is_extended = header[:8] == DSK_MAGIC_ALT or b'EXTENDED' in header[:34]

    # Extract info string
    info_string = header[0:34].decode('ascii', errors='replace').strip()
    creator = header[34:48].decode('ascii', errors='replace').strip()

    num_tracks = header[48]
    num_sides = header[49]

    # Calculate geometry
    cylinders = num_tracks
    heads = num_sides if num_sides > 0 else 1

    # DSK format uses variable sectors per track, assume standard
    sectors_per_track = 9  # Typical for CPC
    sector_size = 512

    description = f"{info_string} by {creator}"

    return ImageMetadata(
        format=ImageFormat.DSK,
        filename=filename,
        file_size=file_size,
        cylinders=cylinders,
        heads=heads,
        sectors_per_track=sectors_per_track,
        sector_size=sector_size,
        total_sectors=cylinders * heads * sectors_per_track,
        is_flux_image=False,
        has_header=True,
        creation_date=creation_date,
        description=description,
    )


def _infer_geometry_from_size(file_size: int) -> Tuple[int, int, int, int]:
    """
    Infer disk geometry from raw image file size.

    Args:
        file_size: Size of the image file in bytes

    Returns:
        Tuple of (cylinders, heads, sectors_per_track, sector_size)
    """
    # Try exact matches first
    for cyls, heads, spt, ss, name in STANDARD_GEOMETRIES:
        if cyls * heads * spt * ss == file_size:
            logger.debug("Matched geometry: %s", name)
            return (cyls, heads, spt, ss)

    # Try to find a reasonable match allowing for some extra space
    for cyls, heads, spt, ss, name in STANDARD_GEOMETRIES:
        expected_size = cyls * heads * spt * ss
        if expected_size <= file_size < expected_size * 1.1:  # 10% tolerance
            logger.debug("Close match to geometry: %s", name)
            return (cyls, heads, spt, ss)

    # Default to 3.5" HD if we can't determine
    logger.warning("Could not determine geometry from size %d, defaulting to HD", file_size)
    return (80, 2, 18, 512)


def _get_geometry_description(cylinders: int, heads: int,
                              sectors: int, sector_size: int) -> str:
    """Get human-readable description for a geometry."""
    capacity = cylinders * heads * sectors * sector_size
    capacity_kb = capacity / 1024

    if capacity_kb >= 1024:
        capacity_str = f"{capacity_kb / 1024:.2f}MB"
    else:
        capacity_str = f"{capacity_kb:.0f}KB"

    return f"{cylinders}C/{heads}H/{sectors}S @ {sector_size}B = {capacity_str}"


# =============================================================================
# Validation
# =============================================================================

def validate_image(filepath: str) -> Tuple[bool, List[str]]:
    """
    Validate image file integrity.

    Performs various checks on the image file including:
    - File exists and is readable
    - File size matches expected geometry
    - Header checksums (where applicable)
    - Internal consistency

    Args:
        filepath: Path to the image file

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors: List[str] = []
    path = Path(filepath)

    # Check file exists
    if not path.exists():
        errors.append(f"File does not exist: {filepath}")
        return (False, errors)

    if not path.is_file():
        errors.append(f"Path is not a file: {filepath}")
        return (False, errors)

    # Check file is readable
    if not os.access(filepath, os.R_OK):
        errors.append(f"File is not readable: {filepath}")
        return (False, errors)

    # Get file size
    try:
        file_size = path.stat().st_size
    except OSError as e:
        errors.append(f"Cannot get file size: {e}")
        return (False, errors)

    # Check for empty file
    if file_size == 0:
        errors.append("File is empty")
        return (False, errors)

    # Detect format and validate format-specific requirements
    try:
        format_type = detect_format(filepath)
    except ImageReadError as e:
        errors.append(f"Cannot detect format: {e}")
        return (False, errors)

    if format_type == ImageFormat.UNKNOWN:
        errors.append("Unknown image format")
        return (False, errors)

    # Format-specific validation
    if format_type == ImageFormat.SCP:
        format_errors = _validate_scp(filepath, file_size)
        errors.extend(format_errors)
    elif format_type == ImageFormat.HFE:
        format_errors = _validate_hfe(filepath, file_size)
        errors.extend(format_errors)
    elif format_type == ImageFormat.DSK:
        format_errors = _validate_dsk(filepath, file_size)
        errors.extend(format_errors)
    elif format_type in (ImageFormat.IMG, ImageFormat.IMA):
        format_errors = _validate_raw(filepath, file_size)
        errors.extend(format_errors)

    is_valid = len(errors) == 0
    return (is_valid, errors)


def _validate_scp(filepath: str, file_size: int) -> List[str]:
    """Validate SCP format image."""
    errors: List[str] = []

    try:
        with open(filepath, 'rb') as f:
            header = f.read(16)
    except IOError as e:
        errors.append(f"Cannot read SCP header: {e}")
        return errors

    if len(header) < 16:
        errors.append(f"SCP header truncated: expected 16 bytes, got {len(header)}")
        return errors

    # Verify magic bytes
    if header[:3] != SCP_MAGIC:
        errors.append(f"Invalid SCP magic bytes: {header[:3]!r}")

    # Check version
    version = header[3]
    if version > 4:
        errors.append(f"Unsupported SCP version: {version}")

    # Check track range
    start_track = header[6]
    end_track = header[7]
    if start_track > end_track:
        errors.append(f"Invalid track range: {start_track}-{end_track}")

    # Verify checksum (last 4 bytes of header)
    stored_checksum = struct.unpack('<I', header[12:16])[0]

    # Calculate checksum (sum of all bytes except checksum field)
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except IOError as e:
        errors.append(f"Cannot read file for checksum: {e}")
        return errors

    # SCP checksum is sum of all bytes from offset 16 to end, stored little-endian
    if len(data) > 16:
        calculated_sum = sum(data[16:]) & 0xFFFFFFFF
        if stored_checksum != 0 and stored_checksum != calculated_sum:
            # Note: Many SCP files have checksum = 0, which means "no checksum"
            errors.append(f"SCP checksum mismatch: stored={stored_checksum:08X}, "
                         f"calculated={calculated_sum:08X}")

    return errors


def _validate_hfe(filepath: str, file_size: int) -> List[str]:
    """Validate HFE format image."""
    errors: List[str] = []

    try:
        with open(filepath, 'rb') as f:
            header = f.read(512)
    except IOError as e:
        errors.append(f"Cannot read HFE header: {e}")
        return errors

    if len(header) < 512:
        errors.append(f"HFE header truncated: expected 512 bytes, got {len(header)}")
        return errors

    # Verify magic bytes
    if header[:8] != HFE_MAGIC:
        errors.append(f"Invalid HFE magic bytes: {header[:8]!r}")

    # Check revision
    revision = header[8]
    if revision > 3:
        errors.append(f"Unsupported HFE revision: {revision}")

    # Check number of tracks
    num_tracks = header[9]
    if num_tracks == 0:
        errors.append("HFE has zero tracks")
    elif num_tracks > 86:  # More than typical 80 + some margin
        errors.append(f"Unusual number of tracks: {num_tracks}")

    # Check number of sides
    num_sides = header[10]
    if num_sides not in (1, 2):
        errors.append(f"Invalid number of sides: {num_sides}")

    # Check track list offset
    track_list_offset = struct.unpack('<H', header[18:20])[0]
    if track_list_offset == 0 or track_list_offset >= file_size:
        errors.append(f"Invalid track list offset: {track_list_offset}")

    return errors


def _validate_dsk(filepath: str, file_size: int) -> List[str]:
    """Validate DSK format image."""
    errors: List[str] = []

    try:
        with open(filepath, 'rb') as f:
            header = f.read(256)
    except IOError as e:
        errors.append(f"Cannot read DSK header: {e}")
        return errors

    if len(header) < 256:
        errors.append(f"DSK header truncated: expected 256 bytes, got {len(header)}")
        return errors

    # Check for valid identifier
    if not (b'MV - CPC' in header[:34] or b'EXTENDED' in header[:34] or
            b'MV - CPC' in header[:10] or header[:8] == DSK_MAGIC_ALT):
        errors.append("Invalid DSK identifier string")

    # Check geometry
    num_tracks = header[48]
    num_sides = header[49]

    if num_tracks == 0:
        errors.append("DSK has zero tracks")
    elif num_tracks > 86:
        errors.append(f"Unusual number of tracks: {num_tracks}")

    if num_sides not in (1, 2):
        errors.append(f"Invalid number of sides: {num_sides}")

    return errors


def _validate_raw(filepath: str, file_size: int) -> List[str]:
    """Validate raw sector image (IMG/IMA)."""
    errors: List[str] = []

    # Check for reasonable file size
    if file_size < 512:  # At least one sector
        errors.append(f"File too small: {file_size} bytes")
        return errors

    # Check if size matches known geometries
    matched = False
    for cyls, heads, spt, ss, name in STANDARD_GEOMETRIES:
        if cyls * heads * spt * ss == file_size:
            matched = True
            break

    if not matched:
        # Not an exact match, check if it's close
        close_match = False
        for cyls, heads, spt, ss, name in STANDARD_GEOMETRIES:
            expected = cyls * heads * spt * ss
            if expected <= file_size < expected * 1.1:
                close_match = True
                errors.append(f"File size {file_size} is close to but not exactly "
                             f"{expected} ({name})")
                break

        if not close_match:
            errors.append(f"File size {file_size} does not match any known geometry")

    return errors


# =============================================================================
# Utility Functions
# =============================================================================

def get_supported_extensions() -> Dict[ImageFormat, List[str]]:
    """
    Get mapping of image formats to supported file extensions.

    Returns:
        Dictionary mapping ImageFormat to list of extensions
    """
    result: Dict[ImageFormat, List[str]] = {
        ImageFormat.IMG: ['.img', '.ima', '.bin', '.raw'],
        ImageFormat.IMA: ['.img', '.ima', '.bin', '.raw'],
        ImageFormat.DSK: ['.dsk'],
        ImageFormat.SCP: ['.scp'],
        ImageFormat.HFE: ['.hfe'],
    }
    return result


def get_format_for_extension(extension: str) -> ImageFormat:
    """
    Get the image format for a file extension.

    Args:
        extension: File extension (with or without leading dot)

    Returns:
        ImageFormat enum value
    """
    ext = extension.lower()
    if not ext.startswith('.'):
        ext = '.' + ext

    return EXTENSION_MAP.get(ext, ImageFormat.UNKNOWN)


def is_flux_format(format_type: ImageFormat) -> bool:
    """Check if format is a flux-level format."""
    return format_type in (ImageFormat.SCP, ImageFormat.HFE)


def is_sector_format(format_type: ImageFormat) -> bool:
    """Check if format is a sector-level format."""
    return format_type in (ImageFormat.IMG, ImageFormat.IMA, ImageFormat.DSK)


def get_expected_size(cylinders: int, heads: int,
                      sectors_per_track: int, sector_size: int = 512) -> int:
    """Calculate expected image size for given geometry."""
    return cylinders * heads * sectors_per_track * sector_size


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Exceptions
    'ImageError',
    'ImageFormatError',
    'ImageCorruptError',
    'ImageGeometryError',
    'ImageReadError',
    'ImageWriteError',
    # Enums
    'ImageFormat',
    # Data classes
    'ImageMetadata',
    # Functions
    'detect_format',
    'read_metadata',
    'validate_image',
    'get_supported_extensions',
    'get_format_for_extension',
    'is_flux_format',
    'is_sector_format',
    'get_expected_size',
    # Constants
    'STANDARD_GEOMETRIES',
    'SCP_MAGIC',
    'HFE_MAGIC',
    'DSK_MAGIC',
]
