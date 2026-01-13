"""
Sector-level disk image handling for IMG/IMA/DSK formats.

This module provides the SectorImage class for reading, writing, and
manipulating sector-level floppy disk images. It supports raw sector
images (IMG/IMA) and CPC DSK format with headers.

Key Features:
    - Load and save IMG/IMA/DSK images
    - Sector-level read/write access (CHS and LBA)
    - Geometry detection and validation
    - Create blank formatted images
    - Image comparison tools

Part of Phase 11: Image Import/Export
"""

import logging
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from .image_formats import (
    ImageFormat,
    ImageMetadata,
    ImageError,
    ImageFormatError,
    ImageCorruptError,
    ImageGeometryError,
    ImageReadError,
    ImageWriteError,
    detect_format,
    read_metadata,
    get_format_for_extension,
    STANDARD_GEOMETRIES,
    DSK_MAGIC,
    DSK_MAGIC_ALT,
)

if TYPE_CHECKING:
    from floppy_formatter.hardware import SectorData, SectorStatus

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default fill byte for formatted sectors
DEFAULT_FILL_BYTE = 0xE5

# DSK format constants
DSK_HEADER_SIZE = 256
DSK_TRACK_HEADER_SIZE = 256
DSK_SECTOR_INFO_SIZE = 8

# Standard geometries for reference
HD_35_GEOMETRY = (80, 2, 18, 512)  # 1.44MB
DD_35_GEOMETRY = (80, 2, 9, 512)   # 720KB
HD_525_GEOMETRY = (80, 2, 15, 512) # 1.2MB
DD_525_GEOMETRY = (40, 2, 9, 512)  # 360KB


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ImageComparison:
    """
    Result of comparing two disk images.

    Attributes:
        image1_path: Path to first image
        image2_path: Path to second image
        identical: True if images are identical
        identical_sectors: Number of identical sectors
        different_sectors: Number of different sectors
        missing_in_image1: LBAs present in image2 but not image1
        missing_in_image2: LBAs present in image1 but not image2
        difference_map: Dict mapping LBA to (data1, data2) tuples
        summary: Human-readable summary
    """
    image1_path: str
    image2_path: str
    identical: bool = True
    identical_sectors: int = 0
    different_sectors: int = 0
    missing_in_image1: List[int] = field(default_factory=list)
    missing_in_image2: List[int] = field(default_factory=list)
    difference_map: Dict[int, Tuple[bytes, bytes]] = field(default_factory=dict)
    summary: str = ""

    @property
    def total_compared(self) -> int:
        """Total sectors compared."""
        return self.identical_sectors + self.different_sectors

    @property
    def match_percentage(self) -> float:
        """Percentage of sectors that match."""
        if self.total_compared == 0:
            return 0.0
        return (self.identical_sectors / self.total_compared) * 100.0


# =============================================================================
# SectorImage Class
# =============================================================================

class SectorImage:
    """
    Sector-level disk image handler.

    Supports reading, writing, and manipulating sector-level floppy disk
    images in IMG, IMA, and DSK formats.

    Attributes:
        cylinders: Number of cylinders
        heads: Number of heads (sides)
        sectors_per_track: Sectors per track
        sector_size: Size of each sector in bytes
        total_sectors: Total number of sectors
        data: Raw sector data

    Example:
        # Load existing image
        image = SectorImage("disk.img")

        # Read a sector
        data = image.get_sector(0, 0, 1)

        # Modify and save
        image.set_sector(0, 0, 1, new_data)
        image.save("modified.img")

        # Create blank image
        blank = SectorImage()
        blank.create_blank(80, 2, 18)
        blank.save("blank.img")
    """

    def __init__(self, filepath: Optional[str] = None):
        """
        Initialize SectorImage.

        Args:
            filepath: Optional path to load image from
        """
        self._cylinders: int = 80
        self._heads: int = 2
        self._sectors_per_track: int = 18
        self._sector_size: int = 512
        self._data: bytearray = bytearray()
        self._filepath: Optional[str] = None
        self._format: ImageFormat = ImageFormat.IMG
        self._modified: bool = False

        if filepath:
            self.load(filepath)

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def cylinders(self) -> int:
        """Number of cylinders."""
        return self._cylinders

    @property
    def heads(self) -> int:
        """Number of heads (sides)."""
        return self._heads

    @property
    def sectors_per_track(self) -> int:
        """Sectors per track."""
        return self._sectors_per_track

    @property
    def sector_size(self) -> int:
        """Size of each sector in bytes."""
        return self._sector_size

    @property
    def total_sectors(self) -> int:
        """Total number of sectors."""
        return self._cylinders * self._heads * self._sectors_per_track

    @property
    def data(self) -> bytes:
        """Raw sector data."""
        return bytes(self._data)

    @property
    def capacity(self) -> int:
        """Total capacity in bytes."""
        return self.total_sectors * self._sector_size

    @property
    def filepath(self) -> Optional[str]:
        """Path to loaded image file."""
        return self._filepath

    @property
    def format(self) -> ImageFormat:
        """Image format."""
        return self._format

    @property
    def is_modified(self) -> bool:
        """Check if image has been modified since load/save."""
        return self._modified

    # =========================================================================
    # Loading
    # =========================================================================

    def load(self, filepath: str) -> None:
        """
        Load image from file.

        Detects format and parses accordingly.

        Args:
            filepath: Path to image file

        Raises:
            ImageReadError: If file cannot be read
            ImageFormatError: If format is unsupported
            ImageCorruptError: If file is corrupt
        """
        path = Path(filepath)

        if not path.exists():
            raise ImageReadError(f"File does not exist", filepath)

        if not path.is_file():
            raise ImageReadError(f"Path is not a file", filepath)

        logger.info("Loading image: %s", filepath)

        # Detect format
        self._format = detect_format(filepath)

        if self._format == ImageFormat.UNKNOWN:
            raise ImageFormatError("Unknown image format", filepath)

        # Load based on format
        if self._format == ImageFormat.DSK:
            self._load_dsk(filepath)
        elif self._format in (ImageFormat.IMG, ImageFormat.IMA):
            self._load_raw(filepath)
        elif self._format in (ImageFormat.SCP, ImageFormat.HFE):
            raise ImageFormatError(
                "Flux images cannot be loaded as sector images. Use FluxImage class.",
                filepath, detected_format=self._format.name
            )
        else:
            # Try as raw image
            self._load_raw(filepath)

        self._filepath = filepath
        self._modified = False

        logger.info("Loaded %d sectors (%d/%d/%d @ %d bytes)",
                   self.total_sectors, self._cylinders, self._heads,
                   self._sectors_per_track, self._sector_size)

    def _load_raw(self, filepath: str) -> None:
        """Load raw sector image (IMG/IMA)."""
        try:
            with open(filepath, 'rb') as f:
                self._data = bytearray(f.read())
        except IOError as e:
            raise ImageReadError(f"Failed to read file: {e}", filepath)

        file_size = len(self._data)

        if file_size == 0:
            raise ImageCorruptError("File is empty", filepath)

        # Infer geometry from size
        self._cylinders, self._heads, self._sectors_per_track, self._sector_size = \
            self._infer_geometry(file_size)

        expected_size = self.capacity
        if file_size < expected_size:
            logger.warning("File size %d is less than expected %d, padding with zeros",
                          file_size, expected_size)
            self._data.extend(bytes(expected_size - file_size))
        elif file_size > expected_size:
            logger.warning("File size %d is greater than expected %d, truncating",
                          file_size, expected_size)
            self._data = self._data[:expected_size]

    def _load_dsk(self, filepath: str) -> None:
        """Load CPC DSK format image."""
        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()
        except IOError as e:
            raise ImageReadError(f"Failed to read file: {e}", filepath)

        if len(file_data) < DSK_HEADER_SIZE:
            raise ImageCorruptError("DSK header too short", filepath,
                                   expected_size=DSK_HEADER_SIZE,
                                   actual_size=len(file_data))

        # Parse header
        header = file_data[:DSK_HEADER_SIZE]

        # Check for extended DSK format
        is_extended = b'EXTENDED' in header[:34]

        num_tracks = header[48]
        num_sides = header[49]

        if num_tracks == 0 or num_sides == 0:
            raise ImageCorruptError("Invalid DSK geometry", filepath)

        self._cylinders = num_tracks
        self._heads = num_sides
        self._sector_size = 512  # Default

        # For standard DSK, track size is fixed
        if not is_extended:
            track_size = struct.unpack('<H', header[50:52])[0]
            self._sectors_per_track = (track_size - DSK_TRACK_HEADER_SIZE) // 512
        else:
            # Extended DSK has variable track sizes
            # Read first track to determine sectors per track
            self._sectors_per_track = 9  # Default for CPC

        # Extract sector data from tracks
        self._data = bytearray(self.capacity)
        offset = DSK_HEADER_SIZE

        for cyl in range(self._cylinders):
            for head in range(self._heads):
                if offset >= len(file_data):
                    break

                # Read track header
                if offset + DSK_TRACK_HEADER_SIZE > len(file_data):
                    break

                track_header = file_data[offset:offset + DSK_TRACK_HEADER_SIZE]

                # Verify track header
                if track_header[:12] != b'Track-Info\r\n':
                    logger.warning("Invalid track header at offset %d", offset)
                    offset += DSK_TRACK_HEADER_SIZE
                    continue

                # Get sector count for this track
                sector_count = track_header[21]
                sector_size_code = track_header[20]
                sector_size = 128 << sector_size_code if sector_size_code < 8 else 512

                # Read sector info table
                sector_infos = []
                for i in range(sector_count):
                    info_offset = 24 + i * DSK_SECTOR_INFO_SIZE
                    if info_offset + DSK_SECTOR_INFO_SIZE <= len(track_header):
                        sector_info = track_header[info_offset:info_offset + DSK_SECTOR_INFO_SIZE]
                        sector_infos.append(sector_info)

                # Read sector data
                data_offset = offset + DSK_TRACK_HEADER_SIZE
                for i, info in enumerate(sector_infos):
                    if len(info) >= 4:
                        sector_cyl = info[0]
                        sector_head = info[1]
                        sector_num = info[2]
                        sector_size_code = info[3]

                        actual_size = 128 << sector_size_code if sector_size_code < 8 else 512

                        if data_offset + actual_size <= len(file_data):
                            sector_data = file_data[data_offset:data_offset + actual_size]

                            # Calculate LBA and store
                            if 1 <= sector_num <= self._sectors_per_track:
                                lba = self.chs_to_lba(cyl, head, sector_num)
                                dest_offset = lba * self._sector_size
                                copy_size = min(len(sector_data), self._sector_size)
                                self._data[dest_offset:dest_offset + copy_size] = \
                                    sector_data[:copy_size]

                            data_offset += actual_size

                # Move to next track
                if is_extended:
                    # Track sizes are in the size table at offset 52
                    track_size_entry = header[52 + cyl * num_sides + head]
                    track_size = track_size_entry * 256
                    offset += track_size if track_size > 0 else DSK_TRACK_HEADER_SIZE
                else:
                    track_size = struct.unpack('<H', header[50:52])[0]
                    offset += track_size

    def _infer_geometry(self, file_size: int) -> Tuple[int, int, int, int]:
        """Infer disk geometry from file size."""
        # Try exact matches first
        for cyls, heads, spt, ss, name in STANDARD_GEOMETRIES:
            if cyls * heads * spt * ss == file_size:
                return (cyls, heads, spt, ss)

        # Try close matches
        for cyls, heads, spt, ss, name in STANDARD_GEOMETRIES:
            expected = cyls * heads * spt * ss
            if expected <= file_size < expected * 1.1:
                return (cyls, heads, spt, ss)

        # Default to 3.5" HD
        return (80, 2, 18, 512)

    # =========================================================================
    # Saving
    # =========================================================================

    def save(self, filepath: str, format_type: Optional[ImageFormat] = None) -> None:
        """
        Save image to file.

        Args:
            filepath: Path to save to
            format_type: Format to save as (auto-detect from extension if None)

        Raises:
            ImageWriteError: If file cannot be written
            ImageFormatError: If format is unsupported for saving
        """
        if format_type is None:
            format_type = get_format_for_extension(Path(filepath).suffix)
            if format_type == ImageFormat.UNKNOWN:
                format_type = ImageFormat.IMG

        logger.info("Saving image to %s (format: %s)", filepath, format_type.name)

        # Create parent directories if needed
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save based on format
        if format_type in (ImageFormat.IMG, ImageFormat.IMA):
            self._save_raw(filepath)
        elif format_type == ImageFormat.DSK:
            self._save_dsk(filepath)
        elif format_type in (ImageFormat.SCP, ImageFormat.HFE):
            raise ImageFormatError(
                "Cannot save sector image as flux format. Use FluxImage class.",
                filepath
            )
        else:
            # Default to raw
            self._save_raw(filepath)

        self._filepath = filepath
        self._format = format_type
        self._modified = False

        logger.info("Saved %d bytes to %s", len(self._data), filepath)

    def _save_raw(self, filepath: str) -> None:
        """Save as raw sector image."""
        try:
            with open(filepath, 'wb') as f:
                f.write(self._data)
        except IOError as e:
            raise ImageWriteError(f"Failed to write file: {e}", filepath)

    def _save_dsk(self, filepath: str) -> None:
        """Save as CPC DSK format."""
        # Build DSK file
        output = bytearray()

        # Create header (256 bytes)
        header = bytearray(DSK_HEADER_SIZE)

        # Identifier
        identifier = b'EXTENDED CPC DSK File\r\nDisk-Info\r\n'
        header[:len(identifier)] = identifier

        # Creator
        creator = b'FloppyWorkbench '
        header[34:34 + len(creator)] = creator

        # Geometry
        header[48] = self._cylinders
        header[49] = self._heads

        # Track sizes (extended format stores size/256 for each track)
        track_data_size = self._sectors_per_track * self._sector_size
        track_total_size = DSK_TRACK_HEADER_SIZE + track_data_size
        track_size_entry = (track_total_size + 255) // 256  # Round up

        for i in range(self._cylinders * self._heads):
            header[52 + i] = track_size_entry

        output.extend(header)

        # Create tracks
        for cyl in range(self._cylinders):
            for head in range(self._heads):
                # Track header
                track_header = bytearray(DSK_TRACK_HEADER_SIZE)
                track_header[:12] = b'Track-Info\r\n'
                track_header[16] = cyl
                track_header[17] = head
                track_header[20] = 2  # Sector size code (2 = 512 bytes)
                track_header[21] = self._sectors_per_track
                track_header[22] = 0x4E  # Gap3 length
                track_header[23] = 0xE5  # Filler byte

                # Sector info table
                for sec in range(self._sectors_per_track):
                    info_offset = 24 + sec * DSK_SECTOR_INFO_SIZE
                    track_header[info_offset] = cyl      # C
                    track_header[info_offset + 1] = head # H
                    track_header[info_offset + 2] = sec + 1  # R (1-based)
                    track_header[info_offset + 3] = 2    # N (size code)
                    track_header[info_offset + 4] = 0    # ST1
                    track_header[info_offset + 5] = 0    # ST2
                    # Bytes 6-7: actual data length (little-endian)
                    struct.pack_into('<H', track_header, info_offset + 6, self._sector_size)

                output.extend(track_header)

                # Sector data
                for sec in range(1, self._sectors_per_track + 1):
                    sector_data = self.get_sector(cyl, head, sec)
                    output.extend(sector_data)

        # Write file
        try:
            with open(filepath, 'wb') as f:
                f.write(output)
        except IOError as e:
            raise ImageWriteError(f"Failed to write DSK file: {e}", filepath)

    # =========================================================================
    # Sector Access
    # =========================================================================

    def get_sector(self, cyl: int, head: int, sector: int) -> bytes:
        """
        Get sector data by CHS address.

        Args:
            cyl: Cylinder number (0-based)
            head: Head number (0 or 1)
            sector: Sector number (1-based)

        Returns:
            Sector data as bytes

        Raises:
            ValueError: If address is out of range
        """
        if not self.is_valid_chs(cyl, head, sector):
            raise ValueError(
                f"Invalid CHS address: {cyl}/{head}/{sector} "
                f"(max: {self._cylinders - 1}/{self._heads - 1}/{self._sectors_per_track})"
            )

        lba = self.chs_to_lba(cyl, head, sector)
        return self.get_sector_by_lba(lba)

    def set_sector(self, cyl: int, head: int, sector: int, data: bytes) -> None:
        """
        Set sector data by CHS address.

        Args:
            cyl: Cylinder number (0-based)
            head: Head number (0 or 1)
            sector: Sector number (1-based)
            data: Sector data (must be sector_size bytes)

        Raises:
            ValueError: If address is out of range or data size is wrong
        """
        if not self.is_valid_chs(cyl, head, sector):
            raise ValueError(
                f"Invalid CHS address: {cyl}/{head}/{sector} "
                f"(max: {self._cylinders - 1}/{self._heads - 1}/{self._sectors_per_track})"
            )

        lba = self.chs_to_lba(cyl, head, sector)
        self.set_sector_by_lba(lba, data)

    def get_sector_by_lba(self, lba: int) -> bytes:
        """
        Get sector data by LBA (Logical Block Address).

        Args:
            lba: Logical block address (0-based)

        Returns:
            Sector data as bytes

        Raises:
            ValueError: If LBA is out of range
        """
        if lba < 0 or lba >= self.total_sectors:
            raise ValueError(f"LBA {lba} out of range (0-{self.total_sectors - 1})")

        offset = lba * self._sector_size
        return bytes(self._data[offset:offset + self._sector_size])

    def set_sector_by_lba(self, lba: int, data: bytes) -> None:
        """
        Set sector data by LBA (Logical Block Address).

        Args:
            lba: Logical block address (0-based)
            data: Sector data

        Raises:
            ValueError: If LBA is out of range or data size is wrong
        """
        if lba < 0 or lba >= self.total_sectors:
            raise ValueError(f"LBA {lba} out of range (0-{self.total_sectors - 1})")

        if len(data) != self._sector_size:
            raise ValueError(
                f"Data size {len(data)} does not match sector size {self._sector_size}"
            )

        offset = lba * self._sector_size
        self._data[offset:offset + self._sector_size] = data
        self._modified = True

    def get_track(self, cyl: int, head: int) -> List[bytes]:
        """
        Get all sectors from a track.

        Args:
            cyl: Cylinder number
            head: Head number

        Returns:
            List of sector data (sectors 1 through sectors_per_track)
        """
        sectors = []
        for sec in range(1, self._sectors_per_track + 1):
            sectors.append(self.get_sector(cyl, head, sec))
        return sectors

    def set_track(self, cyl: int, head: int, sectors: List[bytes]) -> None:
        """
        Set all sectors on a track.

        Args:
            cyl: Cylinder number
            head: Head number
            sectors: List of sector data
        """
        if len(sectors) != self._sectors_per_track:
            raise ValueError(
                f"Expected {self._sectors_per_track} sectors, got {len(sectors)}"
            )

        for i, data in enumerate(sectors):
            self.set_sector(cyl, head, i + 1, data)

    # =========================================================================
    # Geometry Conversion
    # =========================================================================

    def chs_to_lba(self, cyl: int, head: int, sector: int) -> int:
        """
        Convert CHS address to LBA.

        Args:
            cyl: Cylinder number (0-based)
            head: Head number (0 or 1)
            sector: Sector number (1-based)

        Returns:
            LBA (0-based)
        """
        return (cyl * self._heads + head) * self._sectors_per_track + (sector - 1)

    def lba_to_chs(self, lba: int) -> Tuple[int, int, int]:
        """
        Convert LBA to CHS address.

        Args:
            lba: Logical block address (0-based)

        Returns:
            Tuple of (cylinder, head, sector) where sector is 1-based
        """
        sector = (lba % self._sectors_per_track) + 1
        temp = lba // self._sectors_per_track
        head = temp % self._heads
        cyl = temp // self._heads
        return (cyl, head, sector)

    def is_valid_chs(self, cyl: int, head: int, sector: int) -> bool:
        """
        Check if CHS address is valid for this image.

        Args:
            cyl: Cylinder number (0-based)
            head: Head number (0 or 1)
            sector: Sector number (1-based)

        Returns:
            True if address is valid
        """
        return (0 <= cyl < self._cylinders and
                0 <= head < self._heads and
                1 <= sector <= self._sectors_per_track)

    # =========================================================================
    # Creation
    # =========================================================================

    def create_blank(self, cylinders: int = 80, heads: int = 2,
                     sectors_per_track: int = 18, sector_size: int = 512,
                     fill_byte: int = DEFAULT_FILL_BYTE) -> None:
        """
        Create a new blank image with specified geometry.

        Args:
            cylinders: Number of cylinders
            heads: Number of heads
            sectors_per_track: Sectors per track
            sector_size: Size of each sector in bytes
            fill_byte: Byte value to fill sectors with
        """
        logger.info("Creating blank image: %d/%d/%d @ %d bytes, fill=0x%02X",
                   cylinders, heads, sectors_per_track, sector_size, fill_byte)

        self._cylinders = cylinders
        self._heads = heads
        self._sectors_per_track = sectors_per_track
        self._sector_size = sector_size

        total_size = self.capacity
        self._data = bytearray([fill_byte] * total_size)
        self._filepath = None
        self._format = ImageFormat.IMG
        self._modified = True

    @staticmethod
    def create_standard_hd() -> 'SectorImage':
        """Create a standard 3.5" HD (1.44MB) blank image."""
        image = SectorImage()
        image.create_blank(80, 2, 18, 512)
        return image

    @staticmethod
    def create_standard_dd() -> 'SectorImage':
        """Create a standard 3.5" DD (720KB) blank image."""
        image = SectorImage()
        image.create_blank(80, 2, 9, 512)
        return image

    # =========================================================================
    # Conversion from Sector Data
    # =========================================================================

    @staticmethod
    def from_sector_list(sectors: List['SectorData'],
                         cylinders: int = 80,
                         heads: int = 2,
                         sectors_per_track: int = 18,
                         sector_size: int = 512,
                         fill_byte: int = DEFAULT_FILL_BYTE) -> 'SectorImage':
        """
        Create image from list of SectorData objects.

        Args:
            sectors: List of SectorData from MFM decode
            cylinders: Number of cylinders
            heads: Number of heads
            sectors_per_track: Sectors per track
            sector_size: Sector size
            fill_byte: Fill byte for missing sectors

        Returns:
            New SectorImage containing the sector data
        """
        image = SectorImage()
        image.create_blank(cylinders, heads, sectors_per_track, sector_size, fill_byte)

        for sector in sectors:
            try:
                # Ensure sector number is valid
                if 1 <= sector.sector <= sectors_per_track:
                    # Pad or truncate data to sector size
                    data = sector.data
                    if len(data) < sector_size:
                        data = data + bytes([fill_byte] * (sector_size - len(data)))
                    elif len(data) > sector_size:
                        data = data[:sector_size]

                    image.set_sector(sector.cylinder, sector.head, sector.sector, data)
            except (ValueError, IndexError) as e:
                logger.warning("Skipping invalid sector %d/%d/%d: %s",
                              sector.cylinder, sector.head, sector.sector, e)

        return image

    def to_sector_list(self) -> List[dict]:
        """
        Convert image to list of sector dictionaries.

        Returns:
            List of dicts with keys: cylinder, head, sector, data
        """
        result = []
        for cyl in range(self._cylinders):
            for head in range(self._heads):
                for sec in range(1, self._sectors_per_track + 1):
                    result.append({
                        'cylinder': cyl,
                        'head': head,
                        'sector': sec,
                        'data': self.get_sector(cyl, head, sec),
                    })
        return result

    # =========================================================================
    # Comparison
    # =========================================================================

    def compare(self, other: 'SectorImage') -> ImageComparison:
        """
        Compare this image with another.

        Args:
            other: SectorImage to compare with

        Returns:
            ImageComparison with detailed results
        """
        result = ImageComparison(
            image1_path=self._filepath or "(in memory)",
            image2_path=other._filepath or "(in memory)",
        )

        # Compare sector by sector
        max_sectors = max(self.total_sectors, other.total_sectors)

        for lba in range(max_sectors):
            # Check if sector exists in each image
            in_self = lba < self.total_sectors
            in_other = lba < other.total_sectors

            if in_self and not in_other:
                result.missing_in_image2.append(lba)
            elif in_other and not in_self:
                result.missing_in_image1.append(lba)
            elif in_self and in_other:
                data1 = self.get_sector_by_lba(lba)
                data2 = other.get_sector_by_lba(lba)

                if data1 == data2:
                    result.identical_sectors += 1
                else:
                    result.different_sectors += 1
                    result.difference_map[lba] = (data1, data2)

        # Determine overall result
        result.identical = (result.different_sectors == 0 and
                           len(result.missing_in_image1) == 0 and
                           len(result.missing_in_image2) == 0)

        # Generate summary
        if result.identical:
            result.summary = f"Images are identical ({result.identical_sectors} sectors)"
        else:
            parts = []
            if result.different_sectors > 0:
                parts.append(f"{result.different_sectors} different")
            if result.missing_in_image1:
                parts.append(f"{len(result.missing_in_image1)} missing in first")
            if result.missing_in_image2:
                parts.append(f"{len(result.missing_in_image2)} missing in second")
            result.summary = f"Images differ: {', '.join(parts)}"

        return result

    # =========================================================================
    # Metadata
    # =========================================================================

    def get_metadata(self) -> ImageMetadata:
        """Get metadata for this image."""
        return ImageMetadata(
            format=self._format,
            filename=Path(self._filepath).name if self._filepath else "",
            file_size=len(self._data),
            cylinders=self._cylinders,
            heads=self._heads,
            sectors_per_track=self._sectors_per_track,
            sector_size=self._sector_size,
            total_sectors=self.total_sectors,
            is_flux_image=False,
            has_header=(self._format == ImageFormat.DSK),
        )

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def fill_track(self, cyl: int, head: int, pattern: bytes) -> None:
        """
        Fill a track with a repeating pattern.

        Args:
            cyl: Cylinder number
            head: Head number
            pattern: Pattern to repeat
        """
        # Extend pattern to sector size
        repeats = (self._sector_size // len(pattern)) + 1
        fill_data = (pattern * repeats)[:self._sector_size]

        for sec in range(1, self._sectors_per_track + 1):
            self.set_sector(cyl, head, sec, fill_data)

    def clear(self, fill_byte: int = 0x00) -> None:
        """
        Clear all sectors to a fill byte.

        Args:
            fill_byte: Byte value to fill with
        """
        self._data = bytearray([fill_byte] * len(self._data))
        self._modified = True

    def copy(self) -> 'SectorImage':
        """Create a deep copy of this image."""
        new_image = SectorImage()
        new_image._cylinders = self._cylinders
        new_image._heads = self._heads
        new_image._sectors_per_track = self._sectors_per_track
        new_image._sector_size = self._sector_size
        new_image._data = bytearray(self._data)
        new_image._filepath = None
        new_image._format = self._format
        new_image._modified = True
        return new_image

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"SectorImage({self._cylinders}C/{self._heads}H/{self._sectors_per_track}S "
            f"@ {self._sector_size}B = {self.capacity // 1024}KB)"
        )

    def __len__(self) -> int:
        """Return total number of sectors."""
        return self.total_sectors

    def __eq__(self, other: object) -> bool:
        """Check equality with another SectorImage."""
        if not isinstance(other, SectorImage):
            return False
        return (self._data == other._data and
                self._cylinders == other._cylinders and
                self._heads == other._heads and
                self._sectors_per_track == other._sectors_per_track and
                self._sector_size == other._sector_size)


# =============================================================================
# Comparison Functions
# =============================================================================

def compare_images(path1: str, path2: str) -> ImageComparison:
    """
    Compare two image files.

    Args:
        path1: Path to first image
        path2: Path to second image

    Returns:
        ImageComparison with detailed results
    """
    image1 = SectorImage(path1)
    image2 = SectorImage(path2)
    return image1.compare(image2)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'SectorImage',
    'ImageComparison',
    'compare_images',
    'DEFAULT_FILL_BYTE',
    'HD_35_GEOMETRY',
    'DD_35_GEOMETRY',
    'HD_525_GEOMETRY',
    'DD_525_GEOMETRY',
]
