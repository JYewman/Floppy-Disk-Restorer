"""
Flux-level disk image handling for SCP/HFE formats.

This module provides classes for reading, writing, and manipulating
flux-level floppy disk images. Flux images preserve the raw magnetic
transitions on the disk surface, enabling preservation of copy-protected
and non-standard formats.

Supported Formats:
    - SCP: SuperCard Pro flux image format
    - HFE: HxC Floppy Emulator format

Part of Phase 11: Image Import/Export
"""

import logging
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, TYPE_CHECKING

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
    SCP_MAGIC,
    HFE_MAGIC,
)

if TYPE_CHECKING:
    from floppy_formatter.hardware import FluxData, GreaseweazleDevice
    from .sector_image import SectorImage

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# SCP format constants
SCP_HEADER_SIZE = 16
SCP_TRACK_HEADER_SIZE = 4
SCP_VERSION = 0x18  # Version 2.4

# SCP disk types
SCP_DISK_TYPE_C64 = 0x00
SCP_DISK_TYPE_AMIGA = 0x04
SCP_DISK_TYPE_ATARI_ST = 0x08
SCP_DISK_TYPE_ATARI_800 = 0x0C
SCP_DISK_TYPE_APPLE_II = 0x10
SCP_DISK_TYPE_APPLE_II_PRO = 0x14
SCP_DISK_TYPE_APPLE_400K_800K = 0x18
SCP_DISK_TYPE_APPLE_144 = 0x1C
SCP_DISK_TYPE_PC_360K = 0x20
SCP_DISK_TYPE_PC_720K = 0x24
SCP_DISK_TYPE_PC_1200K = 0x28
SCP_DISK_TYPE_PC_1440K = 0x2C
SCP_DISK_TYPE_OTHER = 0x30

# SCP flags
SCP_FLAG_INDEX = 0x01        # Index mark stored
SCP_FLAG_TPI_96 = 0x02       # 96 TPI drive
SCP_FLAG_RPM_360 = 0x04      # 360 RPM drive
SCP_FLAG_NORMALIZED = 0x08   # Flux normalized
SCP_FLAG_READ_WRITE = 0x10   # R/W capable
SCP_FLAG_FOOTER = 0x20       # Has footer

# HFE format constants
HFE_HEADER_SIZE = 512
HFE_TRACK_LUT_SIZE = 512

# HFE encoding types
HFE_ENCODING_ISO_MFM = 0x00
HFE_ENCODING_AMIGA_MFM = 0x01
HFE_ENCODING_ISO_FM = 0x02
HFE_ENCODING_EMU_FM = 0x03
HFE_ENCODING_UNKNOWN = 0xFF

# HFE interface modes
HFE_MODE_IBM_PC_DD = 0x00
HFE_MODE_IBM_PC_HD = 0x01
HFE_MODE_ATARI_ST_DD = 0x02
HFE_MODE_ATARI_ST_HD = 0x03
HFE_MODE_AMIGA_DD = 0x04
HFE_MODE_AMIGA_HD = 0x05
HFE_MODE_CPC_DD = 0x06
HFE_MODE_GENERIC_SHUGART = 0x07
HFE_MODE_IBM_PC_ED = 0x08
HFE_MODE_MSX2_DD = 0x09
HFE_MODE_C64_DD = 0x0A
HFE_MODE_EMU_SHUGART = 0x0B
HFE_MODE_S950_DD = 0x0C
HFE_MODE_S950_HD = 0x0D
HFE_MODE_DISABLE = 0xFE

# Default sample frequency (Greaseweazle F7)
DEFAULT_SAMPLE_FREQ = 72_000_000


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SCPHeader:
    """
    SCP file header structure.

    Attributes:
        version: File format version
        disk_type: Type of disk (PC, Amiga, etc.)
        num_revolutions: Number of revolutions per track
        start_track: First track number
        end_track: Last track number
        flags: Format flags
        bit_cell_width: Bit cell encoding (0=16bit, else 8bit)
        heads: Head configuration (0=both, 1=head0, 2=head1)
        resolution: Time resolution in 25ns units
        checksum: Data checksum
    """
    version: int = SCP_VERSION
    disk_type: int = SCP_DISK_TYPE_PC_1440K
    num_revolutions: int = 2
    start_track: int = 0
    end_track: int = 159  # 80 cyls * 2 heads - 1
    flags: int = SCP_FLAG_INDEX
    bit_cell_width: int = 0  # 16-bit
    heads: int = 0  # Both heads
    resolution: int = 0  # 25ns
    checksum: int = 0


@dataclass
class HFEHeader:
    """
    HFE file header structure.

    Attributes:
        revision: File format revision
        num_tracks: Number of tracks
        num_sides: Number of sides
        track_encoding: Encoding type
        bit_rate: Bit rate in 250bps units
        rpm: Disk RPM (0=300)
        interface_mode: Interface mode
        track_list_offset: Offset to track LUT
    """
    revision: int = 0
    num_tracks: int = 80
    num_sides: int = 2
    track_encoding: int = HFE_ENCODING_ISO_MFM
    bit_rate: int = 1000  # 250000 bps
    rpm: int = 0  # 300 RPM
    interface_mode: int = HFE_MODE_IBM_PC_HD
    track_list_offset: int = 1  # After header


@dataclass
class WriteResult:
    """
    Result of writing an image to disk.

    Attributes:
        success: Overall operation success
        tracks_written: Number of tracks written
        tracks_verified: Number of tracks verified
        failed_tracks: List of (cylinder, head) that failed
        errors: List of error messages
    """
    success: bool = True
    tracks_written: int = 0
    tracks_verified: int = 0
    failed_tracks: List[Tuple[int, int]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# =============================================================================
# FluxImage Abstract Base Class
# =============================================================================

class FluxImage(ABC):
    """
    Abstract base class for flux-level disk images.

    Provides a common interface for SCP and HFE format handling.
    """

    @abstractmethod
    def load(self, filepath: str) -> None:
        """Load image from file."""
        pass

    @abstractmethod
    def save(self, filepath: str) -> None:
        """Save image to file."""
        pass

    @abstractmethod
    def get_track_flux(self, cyl: int, head: int) -> Optional['FluxData']:
        """Get flux data for a track."""
        pass

    @abstractmethod
    def set_track_flux(self, cyl: int, head: int, flux: 'FluxData') -> None:
        """Set flux data for a track."""
        pass

    @abstractmethod
    def get_metadata(self) -> ImageMetadata:
        """Get image metadata."""
        pass

    @property
    @abstractmethod
    def cylinders(self) -> int:
        """Number of cylinders."""
        pass

    @property
    @abstractmethod
    def heads(self) -> int:
        """Number of heads."""
        pass

    @staticmethod
    def open(filepath: str) -> 'FluxImage':
        """
        Open a flux image file, auto-detecting format.

        Args:
            filepath: Path to image file

        Returns:
            SCPImage or HFEImage instance

        Raises:
            ImageFormatError: If format is not a flux format
        """
        format_type = detect_format(filepath)

        if format_type == ImageFormat.SCP:
            image = SCPImage()
            image.load(filepath)
            return image
        elif format_type == ImageFormat.HFE:
            image = HFEImage()
            image.load(filepath)
            return image
        else:
            raise ImageFormatError(
                f"Not a flux image format: {format_type.name}",
                filepath
            )


# =============================================================================
# SCPImage Class
# =============================================================================

class SCPImage(FluxImage):
    """
    SuperCard Pro flux image handler.

    SCP format stores raw flux transition timing data for each track,
    supporting multiple revolutions per track for better data recovery.

    File Structure:
        - 16-byte header
        - Track data offset table (4 bytes per track)
        - Track data blocks (variable size per track)
        - Optional footer

    Example:
        # Load existing image
        scp = SCPImage()
        scp.load("disk.scp")

        # Get flux data for a track
        flux = scp.get_track_flux(0, 0)

        # Modify and save
        scp.save("modified.scp")
    """

    def __init__(self):
        """Initialize SCPImage."""
        self._header: SCPHeader = SCPHeader()
        self._filepath: Optional[str] = None
        self._track_data: Dict[int, List[bytes]] = {}  # track_num -> [rev data]
        self._track_offsets: Dict[int, int] = {}
        self._modified: bool = False

    @property
    def cylinders(self) -> int:
        """Number of cylinders."""
        total_tracks = self._header.end_track - self._header.start_track + 1
        if self._header.heads == 0:  # Both heads
            return (total_tracks + 1) // 2
        return total_tracks

    @property
    def heads(self) -> int:
        """Number of heads."""
        if self._header.heads == 0:
            return 2
        return 1

    @property
    def revolutions(self) -> int:
        """Number of revolutions stored per track."""
        return self._header.num_revolutions

    def load(self, filepath: str) -> None:
        """
        Load SCP image from file.

        Args:
            filepath: Path to SCP file

        Raises:
            ImageReadError: If file cannot be read
            ImageCorruptError: If file format is invalid
        """
        path = Path(filepath)

        if not path.exists():
            raise ImageReadError(f"File does not exist", filepath)

        logger.info("Loading SCP image: %s", filepath)

        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()
        except IOError as e:
            raise ImageReadError(f"Failed to read file: {e}", filepath)

        if len(file_data) < SCP_HEADER_SIZE:
            raise ImageCorruptError("File too small for SCP header", filepath,
                                   expected_size=SCP_HEADER_SIZE,
                                   actual_size=len(file_data))

        # Parse header
        self._parse_header(file_data[:SCP_HEADER_SIZE], filepath)

        # Parse track offset table
        num_tracks = self._header.end_track - self._header.start_track + 1
        offset_table_size = num_tracks * 4
        offset_table_start = SCP_HEADER_SIZE

        if len(file_data) < offset_table_start + offset_table_size:
            raise ImageCorruptError("File too small for track offset table", filepath)

        # Read track offsets
        for i in range(num_tracks):
            track_num = self._header.start_track + i
            offset_pos = offset_table_start + i * 4
            self._track_offsets[track_num] = struct.unpack(
                '<I', file_data[offset_pos:offset_pos + 4]
            )[0]

        # Read track data
        self._track_data = {}
        for track_num, offset in self._track_offsets.items():
            if offset == 0:
                continue  # Empty track

            if offset >= len(file_data):
                logger.warning("Track %d offset %d beyond file size", track_num, offset)
                continue

            # Read track header
            if offset + 4 > len(file_data):
                continue

            track_header = file_data[offset:offset + 4]
            if track_header[:3] != b'TRK':
                logger.warning("Invalid track header at offset %d", offset)
                continue

            stored_track_num = track_header[3]

            # Read revolution data
            rev_data = []
            rev_offset = offset + 4

            for rev in range(self._header.num_revolutions):
                if rev_offset + 12 > len(file_data):
                    break

                # Revolution header: index time (4), track length (4), data offset (4)
                rev_header = file_data[rev_offset:rev_offset + 12]
                index_time = struct.unpack('<I', rev_header[0:4])[0]
                track_length = struct.unpack('<I', rev_header[4:8])[0]
                data_offset_rel = struct.unpack('<I', rev_header[8:12])[0]

                # Calculate absolute data offset
                data_offset = offset + data_offset_rel

                if data_offset + track_length * 2 > len(file_data):
                    logger.warning("Track %d rev %d data truncated", track_num, rev)
                    break

                # Read flux data (16-bit values)
                flux_bytes = file_data[data_offset:data_offset + track_length * 2]
                rev_data.append(flux_bytes)

                rev_offset += 12

            if rev_data:
                self._track_data[track_num] = rev_data

        self._filepath = filepath
        self._modified = False

        logger.info("Loaded SCP: %d tracks, %d revolutions",
                   len(self._track_data), self._header.num_revolutions)

    def _parse_header(self, header: bytes, filepath: str) -> None:
        """Parse SCP header bytes."""
        if header[:3] != SCP_MAGIC:
            raise ImageFormatError("Invalid SCP magic bytes", filepath)

        self._header = SCPHeader(
            version=header[3],
            disk_type=header[4],
            num_revolutions=header[5] if header[5] > 0 else 1,
            start_track=header[6],
            end_track=header[7],
            flags=header[8],
            bit_cell_width=header[9],
            heads=header[10],
            resolution=header[11],
            checksum=struct.unpack('<I', header[12:16])[0],
        )

    def save(self, filepath: str) -> None:
        """
        Save SCP image to file.

        Args:
            filepath: Path to save to

        Raises:
            ImageWriteError: If file cannot be written
        """
        logger.info("Saving SCP image: %s", filepath)

        # Create parent directories
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        output = bytearray()

        # Build header
        header = bytearray(SCP_HEADER_SIZE)
        header[0:3] = SCP_MAGIC
        header[3] = self._header.version
        header[4] = self._header.disk_type
        header[5] = self._header.num_revolutions
        header[6] = self._header.start_track
        header[7] = self._header.end_track
        header[8] = self._header.flags
        header[9] = self._header.bit_cell_width
        header[10] = self._header.heads
        header[11] = self._header.resolution
        # Checksum will be filled in later
        output.extend(header)

        # Build track offset table
        num_tracks = self._header.end_track - self._header.start_track + 1
        offset_table = bytearray(num_tracks * 4)

        # Calculate where track data will start
        track_data_start = SCP_HEADER_SIZE + len(offset_table)

        # Build track data
        track_data = bytearray()
        current_offset = track_data_start

        for i in range(num_tracks):
            track_num = self._header.start_track + i

            if track_num not in self._track_data or not self._track_data[track_num]:
                # No data for this track
                struct.pack_into('<I', offset_table, i * 4, 0)
                continue

            # Store offset
            struct.pack_into('<I', offset_table, i * 4, current_offset)

            # Build track block
            track_block = bytearray()

            # Track header: "TRK" + track number
            track_block.extend(b'TRK')
            track_block.append(track_num)

            # Revolution headers and data
            rev_headers_size = self._header.num_revolutions * 12
            data_start_rel = 4 + rev_headers_size  # After track header + rev headers

            rev_data_offset = data_start_rel
            rev_headers = bytearray()
            rev_datas = bytearray()

            for rev, flux_bytes in enumerate(self._track_data[track_num]):
                # Revolution header
                index_time = 200000000 // DEFAULT_SAMPLE_FREQ  # ~200ms in samples
                track_length = len(flux_bytes) // 2  # Number of 16-bit values

                rev_header = bytearray(12)
                struct.pack_into('<I', rev_header, 0, index_time)
                struct.pack_into('<I', rev_header, 4, track_length)
                struct.pack_into('<I', rev_header, 8, rev_data_offset)
                rev_headers.extend(rev_header)

                rev_datas.extend(flux_bytes)
                rev_data_offset += len(flux_bytes)

            track_block.extend(rev_headers)
            track_block.extend(rev_datas)

            track_data.extend(track_block)
            current_offset += len(track_block)

        output.extend(offset_table)
        output.extend(track_data)

        # Calculate and store checksum
        checksum = sum(output[SCP_HEADER_SIZE:]) & 0xFFFFFFFF
        struct.pack_into('<I', output, 12, checksum)

        # Write file
        try:
            with open(filepath, 'wb') as f:
                f.write(output)
        except IOError as e:
            raise ImageWriteError(f"Failed to write file: {e}", filepath)

        self._filepath = filepath
        self._modified = False

        logger.info("Saved SCP: %d bytes", len(output))

    def get_track_flux(self, cyl: int, head: int) -> Optional['FluxData']:
        """
        Get flux data for a track.

        Args:
            cyl: Cylinder number
            head: Head number

        Returns:
            FluxData or None if track not present
        """
        # Import here to avoid circular imports
        from floppy_formatter.hardware import FluxData

        track_num = cyl * 2 + head

        if track_num not in self._track_data or not self._track_data[track_num]:
            return None

        # Combine all revolutions into one FluxData
        flux_times = []
        index_positions = []
        current_pos = 0

        for rev_bytes in self._track_data[track_num]:
            # Mark index position at start of each revolution
            index_positions.append(current_pos)

            # Parse 16-bit flux values
            for i in range(0, len(rev_bytes), 2):
                if i + 2 <= len(rev_bytes):
                    value = struct.unpack('<H', rev_bytes[i:i + 2])[0]
                    if value > 0:
                        flux_times.append(value)
                        current_pos += value

        return FluxData(
            flux_times=flux_times,
            sample_freq=DEFAULT_SAMPLE_FREQ,
            index_positions=index_positions,
            cylinder=cyl,
            head=head,
            revolutions=len(self._track_data[track_num])
        )

    def get_revolution(self, cyl: int, head: int, rev: int) -> Optional['FluxData']:
        """
        Get flux data for a specific revolution.

        Args:
            cyl: Cylinder number
            head: Head number
            rev: Revolution number (0-based)

        Returns:
            FluxData for single revolution or None
        """
        from floppy_formatter.hardware import FluxData

        track_num = cyl * 2 + head

        if track_num not in self._track_data:
            return None

        revs = self._track_data[track_num]
        if rev >= len(revs):
            return None

        rev_bytes = revs[rev]
        flux_times = []

        for i in range(0, len(rev_bytes), 2):
            if i + 2 <= len(rev_bytes):
                value = struct.unpack('<H', rev_bytes[i:i + 2])[0]
                if value > 0:
                    flux_times.append(value)

        return FluxData(
            flux_times=flux_times,
            sample_freq=DEFAULT_SAMPLE_FREQ,
            index_positions=[0],
            cylinder=cyl,
            head=head,
            revolutions=1
        )

    def set_track_flux(self, cyl: int, head: int, flux: 'FluxData') -> None:
        """
        Set flux data for a track.

        Args:
            cyl: Cylinder number
            head: Head number
            flux: FluxData to store
        """
        track_num = cyl * 2 + head

        # Convert FluxData to 16-bit values
        rev_bytes = bytearray()
        for time_val in flux.flux_times:
            # Clamp to 16-bit range
            clamped = min(65535, max(1, time_val))
            rev_bytes.extend(struct.pack('<H', clamped))

        # Store as single revolution
        self._track_data[track_num] = [bytes(rev_bytes)]
        self._modified = True

        # Update header track range if needed
        if track_num < self._header.start_track:
            self._header.start_track = track_num
        if track_num > self._header.end_track:
            self._header.end_track = track_num

    def create_blank(self, cylinders: int = 80, heads: int = 2,
                     revolutions: int = 2) -> None:
        """
        Create a blank SCP image.

        Args:
            cylinders: Number of cylinders
            heads: Number of heads
            revolutions: Revolutions per track
        """
        self._header = SCPHeader(
            version=SCP_VERSION,
            disk_type=SCP_DISK_TYPE_PC_1440K,
            num_revolutions=revolutions,
            start_track=0,
            end_track=cylinders * heads - 1,
            flags=SCP_FLAG_INDEX,
            heads=0 if heads == 2 else heads,
        )
        self._track_data = {}
        self._track_offsets = {}
        self._filepath = None
        self._modified = True

    @staticmethod
    def from_flux_captures(captures: Dict[Tuple[int, int], 'FluxData']) -> 'SCPImage':
        """
        Create SCP image from flux captures.

        Args:
            captures: Dict mapping (cylinder, head) to FluxData

        Returns:
            New SCPImage instance
        """
        if not captures:
            raise ValueError("No flux captures provided")

        # Determine geometry from captures
        max_cyl = max(cyl for cyl, head in captures.keys())
        max_head = max(head for cyl, head in captures.keys())

        image = SCPImage()
        image.create_blank(max_cyl + 1, max_head + 1, 2)

        for (cyl, head), flux in captures.items():
            image.set_track_flux(cyl, head, flux)

        return image

    def get_metadata(self) -> ImageMetadata:
        """Get image metadata."""
        return ImageMetadata(
            format=ImageFormat.SCP,
            filename=Path(self._filepath).name if self._filepath else "",
            file_size=0,  # Unknown until saved
            cylinders=self.cylinders,
            heads=self.heads,
            sectors_per_track=18,  # Assumed
            sector_size=512,
            is_flux_image=True,
            has_header=True,
            revolutions=self._header.num_revolutions,
            description=f"SCP v{self._header.version}",
        )

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the SCP image.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if self._header.start_track > self._header.end_track:
            errors.append(f"Invalid track range: {self._header.start_track}-{self._header.end_track}")

        if self._header.num_revolutions == 0:
            errors.append("Number of revolutions is zero")

        # Check track data
        for track_num in range(self._header.start_track, self._header.end_track + 1):
            if track_num in self._track_data:
                for rev, data in enumerate(self._track_data[track_num]):
                    if len(data) == 0:
                        errors.append(f"Track {track_num} revolution {rev} is empty")

        return (len(errors) == 0, errors)

    def calculate_checksum(self) -> int:
        """Calculate data checksum."""
        total = 0
        for track_data in self._track_data.values():
            for rev_data in track_data:
                total += sum(rev_data)
        return total & 0xFFFFFFFF


# =============================================================================
# HFEImage Class
# =============================================================================

class HFEImage(FluxImage):
    """
    HxC Floppy Emulator image handler.

    HFE format stores tracks as interleaved bit streams, with both sides
    of a cylinder stored together in 256-byte blocks.

    File Structure:
        - 512-byte header
        - Track lookup table (512 bytes)
        - Track data (variable, interleaved by side)

    Example:
        # Load existing image
        hfe = HFEImage()
        hfe.load("disk.hfe")

        # Get flux data
        flux = hfe.get_track_flux(0, 0)
    """

    def __init__(self):
        """Initialize HFEImage."""
        self._header: HFEHeader = HFEHeader()
        self._filepath: Optional[str] = None
        self._track_data: Dict[Tuple[int, int], bytes] = {}  # (cyl, head) -> data
        self._track_lut: List[Tuple[int, int]] = []  # (offset, length) for each track
        self._modified: bool = False

    @property
    def cylinders(self) -> int:
        """Number of cylinders."""
        return self._header.num_tracks

    @property
    def heads(self) -> int:
        """Number of heads."""
        return self._header.num_sides

    @property
    def bit_rate(self) -> int:
        """Bit rate in bps."""
        return self._header.bit_rate * 250

    def load(self, filepath: str) -> None:
        """
        Load HFE image from file.

        Args:
            filepath: Path to HFE file

        Raises:
            ImageReadError: If file cannot be read
            ImageCorruptError: If file format is invalid
        """
        path = Path(filepath)

        if not path.exists():
            raise ImageReadError(f"File does not exist", filepath)

        logger.info("Loading HFE image: %s", filepath)

        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()
        except IOError as e:
            raise ImageReadError(f"Failed to read file: {e}", filepath)

        if len(file_data) < HFE_HEADER_SIZE:
            raise ImageCorruptError("File too small for HFE header", filepath,
                                   expected_size=HFE_HEADER_SIZE,
                                   actual_size=len(file_data))

        # Parse header
        self._parse_header(file_data[:HFE_HEADER_SIZE], filepath)

        # Read track lookup table
        lut_offset = self._header.track_list_offset * 512
        lut_size = self._header.num_tracks * 4

        if lut_offset + lut_size > len(file_data):
            raise ImageCorruptError("Track LUT extends beyond file", filepath)

        self._track_lut = []
        for i in range(self._header.num_tracks):
            lut_entry_offset = lut_offset + i * 4
            track_offset = struct.unpack('<H', file_data[lut_entry_offset:lut_entry_offset + 2])[0]
            track_length = struct.unpack('<H', file_data[lut_entry_offset + 2:lut_entry_offset + 4])[0]
            self._track_lut.append((track_offset, track_length))

        # Read track data
        self._track_data = {}
        for cyl, (track_offset, track_length) in enumerate(self._track_lut):
            if track_offset == 0 or track_length == 0:
                continue

            data_offset = track_offset * 512
            if data_offset >= len(file_data):
                continue

            # HFE stores both sides interleaved in 256-byte blocks
            # Read full track data
            full_track_data = file_data[data_offset:data_offset + track_length]

            # De-interleave sides
            side0_data = bytearray()
            side1_data = bytearray()

            for block_start in range(0, len(full_track_data), 512):
                block = full_track_data[block_start:block_start + 512]
                if len(block) >= 256:
                    side0_data.extend(block[:256])
                if len(block) >= 512:
                    side1_data.extend(block[256:512])

            self._track_data[(cyl, 0)] = bytes(side0_data)
            if self._header.num_sides >= 2:
                self._track_data[(cyl, 1)] = bytes(side1_data)

        self._filepath = filepath
        self._modified = False

        logger.info("Loaded HFE: %d tracks, %d sides",
                   self._header.num_tracks, self._header.num_sides)

    def _parse_header(self, header: bytes, filepath: str) -> None:
        """Parse HFE header bytes."""
        if header[:8] != HFE_MAGIC:
            raise ImageFormatError("Invalid HFE magic bytes", filepath)

        self._header = HFEHeader(
            revision=header[8],
            num_tracks=header[9],
            num_sides=header[10],
            track_encoding=header[11],
            bit_rate=struct.unpack('<H', header[12:14])[0],
            rpm=struct.unpack('<H', header[14:16])[0],
            interface_mode=header[16],
            track_list_offset=struct.unpack('<H', header[18:20])[0],
        )

    def save(self, filepath: str) -> None:
        """
        Save HFE image to file.

        Args:
            filepath: Path to save to

        Raises:
            ImageWriteError: If file cannot be written
        """
        logger.info("Saving HFE image: %s", filepath)

        # Create parent directories
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        output = bytearray()

        # Build header
        header = bytearray(HFE_HEADER_SIZE)
        header[0:8] = HFE_MAGIC
        header[8] = self._header.revision
        header[9] = self._header.num_tracks
        header[10] = self._header.num_sides
        header[11] = self._header.track_encoding
        struct.pack_into('<H', header, 12, self._header.bit_rate)
        struct.pack_into('<H', header, 14, self._header.rpm)
        header[16] = self._header.interface_mode
        header[17] = 1  # Reserved
        struct.pack_into('<H', header, 18, 1)  # Track list at block 1
        # Write enable flag
        header[20] = 0xFF
        # Single/double step mode
        header[21] = 0xFF

        output.extend(header)

        # Build track lookup table
        lut = bytearray(HFE_TRACK_LUT_SIZE)
        track_data_start = 2  # Start after header and LUT (2 blocks)
        current_block = track_data_start

        # Build interleaved track data
        track_blocks = bytearray()

        for cyl in range(self._header.num_tracks):
            side0_data = self._track_data.get((cyl, 0), b'')
            side1_data = self._track_data.get((cyl, 1), b'') if self._header.num_sides >= 2 else b''

            # Ensure both sides are same length (pad if needed)
            max_len = max(len(side0_data), len(side1_data))
            if max_len == 0:
                # Empty track
                struct.pack_into('<H', lut, cyl * 4, 0)
                struct.pack_into('<H', lut, cyl * 4 + 2, 0)
                continue

            # Pad to 256-byte boundary
            block_count = (max_len + 255) // 256
            padded_len = block_count * 256

            side0_padded = side0_data.ljust(padded_len, b'\x00')
            side1_padded = side1_data.ljust(padded_len, b'\x00')

            # Interleave into 512-byte blocks
            track_interleaved = bytearray()
            for i in range(block_count):
                track_interleaved.extend(side0_padded[i * 256:(i + 1) * 256])
                track_interleaved.extend(side1_padded[i * 256:(i + 1) * 256])

            # Store in LUT
            struct.pack_into('<H', lut, cyl * 4, current_block)
            struct.pack_into('<H', lut, cyl * 4 + 2, len(track_interleaved))

            track_blocks.extend(track_interleaved)
            current_block += len(track_interleaved) // 512

        output.extend(lut)
        output.extend(track_blocks)

        # Write file
        try:
            with open(filepath, 'wb') as f:
                f.write(output)
        except IOError as e:
            raise ImageWriteError(f"Failed to write file: {e}", filepath)

        self._filepath = filepath
        self._modified = False

        logger.info("Saved HFE: %d bytes", len(output))

    def get_track_flux(self, cyl: int, head: int) -> Optional['FluxData']:
        """
        Get flux data for a track.

        Args:
            cyl: Cylinder number
            head: Head number

        Returns:
            FluxData or None if track not present
        """
        from floppy_formatter.hardware import FluxData

        if (cyl, head) not in self._track_data:
            return None

        track_bytes = self._track_data[(cyl, head)]
        if not track_bytes:
            return None

        # Convert HFE bit stream to flux timing
        # HFE stores data as a bit stream where 1s represent flux transitions
        flux_times = self._bits_to_flux(track_bytes)

        return FluxData(
            flux_times=flux_times,
            sample_freq=DEFAULT_SAMPLE_FREQ,
            index_positions=[0],
            cylinder=cyl,
            head=head,
            revolutions=1
        )

    def _bits_to_flux(self, data: bytes) -> List[int]:
        """Convert HFE bit stream to flux timing values."""
        flux_times = []
        count = 0

        # Calculate samples per bit based on bit rate
        # HFE bit rate is in 250bps units, sample freq is typically 72MHz
        bit_time_ns = 1000000000 / (self._header.bit_rate * 250)
        samples_per_bit = int(bit_time_ns * DEFAULT_SAMPLE_FREQ / 1000000000)

        for byte in data:
            for bit in range(8):
                bit_val = (byte >> (7 - bit)) & 1
                count += samples_per_bit
                if bit_val == 1:
                    if count > 0:
                        flux_times.append(count)
                        count = 0

        # Handle trailing count
        if count > 0:
            flux_times.append(count)

        return flux_times

    def _flux_to_bits(self, flux: 'FluxData') -> bytes:
        """Convert flux timing to HFE bit stream."""
        # Calculate samples per bit
        bit_time_ns = 1000000000 / (self._header.bit_rate * 250)
        samples_per_bit = int(bit_time_ns * flux.sample_freq / 1000000000)

        # Generate bit stream
        bits = []
        sample_pos = 0

        for time_val in flux.flux_times:
            # Fill with zeros until transition
            while sample_pos < time_val:
                bits.append(0)
                sample_pos += samples_per_bit
            # Add transition
            bits.append(1)
            sample_pos = 0

        # Convert bits to bytes
        result = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                if i + j < len(bits):
                    byte = (byte << 1) | bits[i + j]
                else:
                    byte = byte << 1
            result.append(byte)

        return bytes(result)

    def set_track_flux(self, cyl: int, head: int, flux: 'FluxData') -> None:
        """
        Set flux data for a track.

        Args:
            cyl: Cylinder number
            head: Head number
            flux: FluxData to store
        """
        track_bytes = self._flux_to_bits(flux)
        self._track_data[(cyl, head)] = track_bytes
        self._modified = True

        # Update header if needed
        if cyl >= self._header.num_tracks:
            self._header.num_tracks = cyl + 1
        if head >= self._header.num_sides:
            self._header.num_sides = head + 1

    def create_blank(self, cylinders: int = 80, heads: int = 2,
                     bit_rate: int = 250000) -> None:
        """
        Create a blank HFE image.

        Args:
            cylinders: Number of cylinders
            heads: Number of heads
            bit_rate: Bit rate in bps
        """
        self._header = HFEHeader(
            revision=0,
            num_tracks=cylinders,
            num_sides=heads,
            track_encoding=HFE_ENCODING_ISO_MFM,
            bit_rate=bit_rate // 250,
            rpm=0,  # 300 RPM
            interface_mode=HFE_MODE_IBM_PC_HD,
            track_list_offset=1,
        )
        self._track_data = {}
        self._track_lut = []
        self._filepath = None
        self._modified = True

    @staticmethod
    def from_flux_captures(captures: Dict[Tuple[int, int], 'FluxData']) -> 'HFEImage':
        """
        Create HFE image from flux captures.

        Args:
            captures: Dict mapping (cylinder, head) to FluxData

        Returns:
            New HFEImage instance
        """
        if not captures:
            raise ValueError("No flux captures provided")

        # Determine geometry from captures
        max_cyl = max(cyl for cyl, head in captures.keys())
        max_head = max(head for cyl, head in captures.keys())

        image = HFEImage()
        image.create_blank(max_cyl + 1, max_head + 1)

        for (cyl, head), flux in captures.items():
            image.set_track_flux(cyl, head, flux)

        return image

    def get_metadata(self) -> ImageMetadata:
        """Get image metadata."""
        encoding_names = {
            HFE_ENCODING_ISO_MFM: "MFM",
            HFE_ENCODING_AMIGA_MFM: "AMIGA_MFM",
            HFE_ENCODING_ISO_FM: "FM",
            HFE_ENCODING_EMU_FM: "EMU_FM",
        }

        return ImageMetadata(
            format=ImageFormat.HFE,
            filename=Path(self._filepath).name if self._filepath else "",
            file_size=0,
            cylinders=self._header.num_tracks,
            heads=self._header.num_sides,
            sectors_per_track=18,
            sector_size=512,
            is_flux_image=True,
            has_header=True,
            bit_rate=self._header.bit_rate * 250,
            encoding=encoding_names.get(self._header.track_encoding, "UNKNOWN"),
        )

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the HFE image.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if self._header.num_tracks == 0:
            errors.append("Number of tracks is zero")

        if self._header.num_sides not in (1, 2):
            errors.append(f"Invalid number of sides: {self._header.num_sides}")

        if self._header.bit_rate == 0:
            errors.append("Bit rate is zero")

        return (len(errors) == 0, errors)


# =============================================================================
# Conversion Functions
# =============================================================================

def convert_sector_to_flux(sector_image: 'SectorImage',
                           sample_freq: int = DEFAULT_SAMPLE_FREQ) -> Dict[Tuple[int, int], 'FluxData']:
    """
    Convert sector image to flux data using MFM encoding.

    Args:
        sector_image: SectorImage to convert
        sample_freq: Sample frequency for flux data

    Returns:
        Dict mapping (cylinder, head) to FluxData
    """
    from floppy_formatter.hardware import SectorData, SectorStatus
    from floppy_formatter.hardware import encode_sectors_to_flux

    captures = {}

    for cyl in range(sector_image.cylinders):
        for head in range(sector_image.heads):
            # Build sector list for this track
            sectors = []
            for sec in range(1, sector_image.sectors_per_track + 1):
                data = sector_image.get_sector(cyl, head, sec)
                sector = SectorData(
                    cylinder=cyl,
                    head=head,
                    sector=sec,
                    data=data,
                    status=SectorStatus.GOOD,
                    crc_valid=True,
                    signal_quality=1.0
                )
                sectors.append(sector)

            # Encode to flux
            flux = encode_sectors_to_flux(cyl, head, sectors, sample_freq)
            captures[(cyl, head)] = flux

    return captures


def convert_flux_to_sector(flux_image: FluxImage) -> 'SectorImage':
    """
    Convert flux image to sector image using MFM decoding.

    Args:
        flux_image: FluxImage to convert

    Returns:
        SectorImage with decoded sector data
    """
    from floppy_formatter.hardware import decode_flux_to_sectors
    from .sector_image import SectorImage

    sector_image = SectorImage()
    sector_image.create_blank(flux_image.cylinders, flux_image.heads)

    for cyl in range(flux_image.cylinders):
        for head in range(flux_image.heads):
            flux = flux_image.get_track_flux(cyl, head)
            if flux is None:
                continue

            # Decode sectors
            sectors = decode_flux_to_sectors(flux)

            for sector in sectors:
                try:
                    if sector.is_good and 1 <= sector.sector <= sector_image.sectors_per_track:
                        sector_image.set_sector(cyl, head, sector.sector, sector.data)
                except (ValueError, IndexError):
                    pass

    return sector_image


def convert_format(input_path: str, output_path: str,
                   output_format: Optional[ImageFormat] = None) -> None:
    """
    Convert between image formats.

    Supports:
    - Sector-to-sector: IMG <-> IMA <-> DSK
    - Flux-to-flux: SCP <-> HFE
    - Cross-type: Sector <-> Flux (requires encoding/decoding)

    Args:
        input_path: Path to input image
        output_path: Path to output image
        output_format: Output format (auto-detect from extension if None)

    Raises:
        ImageFormatError: If conversion is not supported
    """
    from .sector_image import SectorImage

    # Detect formats
    input_format = detect_format(input_path)

    if output_format is None:
        ext = Path(output_path).suffix.lower()
        from .image_formats import get_format_for_extension
        output_format = get_format_for_extension(ext)

    if output_format == ImageFormat.UNKNOWN:
        raise ImageFormatError(f"Cannot determine output format for: {output_path}")

    logger.info("Converting %s (%s) to %s (%s)",
               input_path, input_format.name, output_path, output_format.name)

    # Determine conversion type
    input_is_flux = input_format in (ImageFormat.SCP, ImageFormat.HFE)
    output_is_flux = output_format in (ImageFormat.SCP, ImageFormat.HFE)

    if input_is_flux and output_is_flux:
        # Flux-to-flux conversion
        input_image = FluxImage.open(input_path)

        if output_format == ImageFormat.SCP:
            output_image = SCPImage()
        else:
            output_image = HFEImage()

        output_image.create_blank(input_image.cylinders, input_image.heads)

        for cyl in range(input_image.cylinders):
            for head in range(input_image.heads):
                flux = input_image.get_track_flux(cyl, head)
                if flux:
                    output_image.set_track_flux(cyl, head, flux)

        output_image.save(output_path)

    elif not input_is_flux and not output_is_flux:
        # Sector-to-sector conversion
        input_image = SectorImage(input_path)
        input_image.save(output_path, output_format)

    elif not input_is_flux and output_is_flux:
        # Sector-to-flux conversion
        input_image = SectorImage(input_path)
        captures = convert_sector_to_flux(input_image)

        if output_format == ImageFormat.SCP:
            output_image = SCPImage.from_flux_captures(captures)
        else:
            output_image = HFEImage.from_flux_captures(captures)

        output_image.save(output_path)

    else:
        # Flux-to-sector conversion
        input_image = FluxImage.open(input_path)
        output_image = convert_flux_to_sector(input_image)
        output_image.save(output_path, output_format)


# =============================================================================
# Disk Read/Write Operations
# =============================================================================

def read_disk_to_image(device: 'GreaseweazleDevice',
                       output_path: str,
                       format_type: ImageFormat,
                       progress_callback: Optional[callable] = None) -> ImageMetadata:
    """
    Read entire disk and save to image file.

    Args:
        device: Connected GreaseweazleDevice
        output_path: Path to save image
        format_type: Format to save as
        progress_callback: Optional callback(track, total, status)

    Returns:
        ImageMetadata for saved image

    Raises:
        ImageWriteError: If save fails
    """
    from floppy_formatter.hardware import decode_flux_to_sectors
    from .sector_image import SectorImage

    logger.info("Reading disk to %s (format: %s)", output_path, format_type.name)

    # Get drive info
    drive_info = device.get_drive_info()
    cylinders = drive_info.cylinders
    heads = drive_info.heads
    total_tracks = cylinders * heads

    is_flux_format = format_type in (ImageFormat.SCP, ImageFormat.HFE)

    if is_flux_format:
        # Read flux data
        captures = {}

        for cyl in range(cylinders):
            for head in range(heads):
                track_num = cyl * heads + head

                if progress_callback:
                    progress_callback(track_num, total_tracks, f"Reading C{cyl} H{head}")

                flux = device.read_track(cyl, head, revolutions=2.0)
                captures[(cyl, head)] = flux

        # Save flux image
        if format_type == ImageFormat.SCP:
            image = SCPImage.from_flux_captures(captures)
        else:
            image = HFEImage.from_flux_captures(captures)

        image.save(output_path)
        return image.get_metadata()

    else:
        # Read and decode to sectors
        sector_image = SectorImage()
        sector_image.create_blank(cylinders, heads, drive_info.sectors_per_track)

        for cyl in range(cylinders):
            for head in range(heads):
                track_num = cyl * heads + head

                if progress_callback:
                    progress_callback(track_num, total_tracks, f"Reading C{cyl} H{head}")

                flux = device.read_track(cyl, head)
                sectors = decode_flux_to_sectors(flux)

                for sector in sectors:
                    if sector.is_good and 1 <= sector.sector <= sector_image.sectors_per_track:
                        sector_image.set_sector(cyl, head, sector.sector, sector.data)

        sector_image.save(output_path, format_type)
        return sector_image.get_metadata()


def write_image_to_disk(device: 'GreaseweazleDevice',
                        input_path: str,
                        verify: bool = True,
                        progress_callback: Optional[callable] = None) -> WriteResult:
    """
    Write image file to physical disk.

    Args:
        device: Connected GreaseweazleDevice
        input_path: Path to image file
        verify: Whether to verify after writing
        progress_callback: Optional callback(track, total, status)

    Returns:
        WriteResult with operation details
    """
    from floppy_formatter.hardware import encode_sectors_to_flux, decode_flux_to_sectors
    from .sector_image import SectorImage

    logger.info("Writing %s to disk (verify: %s)", input_path, verify)

    result = WriteResult()
    format_type = detect_format(input_path)

    is_flux_format = format_type in (ImageFormat.SCP, ImageFormat.HFE)

    if is_flux_format:
        image = FluxImage.open(input_path)
        cylinders = image.cylinders
        heads = image.heads
    else:
        image = SectorImage(input_path)
        cylinders = image.cylinders
        heads = image.heads

    total_tracks = cylinders * heads

    # Write tracks
    for cyl in range(cylinders):
        for head in range(heads):
            track_num = cyl * heads + head

            if progress_callback:
                progress_callback(track_num, total_tracks, f"Writing C{cyl} H{head}")

            try:
                if is_flux_format:
                    flux = image.get_track_flux(cyl, head)
                    if flux:
                        device.write_track(cyl, head, flux)
                        result.tracks_written += 1
                else:
                    # Convert sectors to flux
                    from floppy_formatter.hardware import SectorData, SectorStatus
                    sectors = []
                    for sec in range(1, image.sectors_per_track + 1):
                        data = image.get_sector(cyl, head, sec)
                        sectors.append(SectorData(
                            cylinder=cyl,
                            head=head,
                            sector=sec,
                            data=data,
                            status=SectorStatus.GOOD,
                            crc_valid=True,
                            signal_quality=1.0
                        ))
                    flux = encode_sectors_to_flux(cyl, head, sectors)
                    device.write_track(cyl, head, flux)
                    result.tracks_written += 1

            except Exception as e:
                logger.error("Failed to write C%d H%d: %s", cyl, head, e)
                result.failed_tracks.append((cyl, head))
                result.errors.append(f"Write failed C{cyl} H{head}: {e}")

    # Verify if requested
    if verify:
        for cyl in range(cylinders):
            for head in range(heads):
                track_num = cyl * heads + head

                if progress_callback:
                    progress_callback(track_num, total_tracks, f"Verifying C{cyl} H{head}")

                try:
                    read_flux = device.read_track(cyl, head)

                    if is_flux_format:
                        # For flux images, we can't easily verify byte-for-byte
                        # Just check if we can decode sectors
                        sectors = decode_flux_to_sectors(read_flux)
                        if sectors:
                            result.tracks_verified += 1
                    else:
                        # Decode and compare
                        sectors = decode_flux_to_sectors(read_flux)
                        all_match = True
                        for sector in sectors:
                            if sector.is_good and 1 <= sector.sector <= image.sectors_per_track:
                                expected = image.get_sector(cyl, head, sector.sector)
                                if sector.data != expected:
                                    all_match = False
                                    break
                        if all_match:
                            result.tracks_verified += 1
                        else:
                            result.errors.append(f"Verify mismatch C{cyl} H{head}")

                except Exception as e:
                    logger.error("Verify failed C%d H%d: %s", cyl, head, e)
                    result.errors.append(f"Verify failed C{cyl} H{head}: {e}")

    # Determine success
    result.success = (len(result.failed_tracks) == 0 and
                     (not verify or result.tracks_verified == result.tracks_written))

    return result


def compare_image_to_disk(image_path: str,
                          device: 'GreaseweazleDevice',
                          progress_callback: Optional[callable] = None) -> 'ImageComparison':
    """
    Compare image file to physical disk.

    Args:
        image_path: Path to image file
        device: Connected GreaseweazleDevice
        progress_callback: Optional callback(track, total, status)

    Returns:
        ImageComparison with detailed results
    """
    from floppy_formatter.hardware import decode_flux_to_sectors
    from .sector_image import SectorImage, ImageComparison

    logger.info("Comparing %s to disk", image_path)

    format_type = detect_format(image_path)
    is_flux_format = format_type in (ImageFormat.SCP, ImageFormat.HFE)

    # Load image
    if is_flux_format:
        image = FluxImage.open(image_path)
        # Convert to sector image for comparison
        sector_image = convert_flux_to_sector(image)
    else:
        sector_image = SectorImage(image_path)

    result = ImageComparison(
        image1_path=image_path,
        image2_path="(physical disk)",
    )

    total_tracks = sector_image.cylinders * sector_image.heads

    # Read and compare
    for cyl in range(sector_image.cylinders):
        for head in range(sector_image.heads):
            track_num = cyl * sector_image.heads + head

            if progress_callback:
                progress_callback(track_num, total_tracks, f"Comparing C{cyl} H{head}")

            try:
                flux = device.read_track(cyl, head)
                sectors = decode_flux_to_sectors(flux)

                for sec in range(1, sector_image.sectors_per_track + 1):
                    lba = sector_image.chs_to_lba(cyl, head, sec)
                    expected = sector_image.get_sector(cyl, head, sec)

                    # Find matching sector in decoded data
                    found = False
                    for sector in sectors:
                        if sector.sector == sec:
                            found = True
                            if sector.is_good and sector.data == expected:
                                result.identical_sectors += 1
                            else:
                                result.different_sectors += 1
                                result.difference_map[lba] = (expected, sector.data)
                            break

                    if not found:
                        result.missing_in_image2.append(lba)

            except Exception as e:
                logger.error("Compare failed C%d H%d: %s", cyl, head, e)

    result.identical = (result.different_sectors == 0 and
                       len(result.missing_in_image2) == 0)

    if result.identical:
        result.summary = f"Disk matches image ({result.identical_sectors} sectors)"
    else:
        parts = []
        if result.different_sectors > 0:
            parts.append(f"{result.different_sectors} different")
        if result.missing_in_image2:
            parts.append(f"{len(result.missing_in_image2)} missing on disk")
        result.summary = f"Differences found: {', '.join(parts)}"

    return result


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Classes
    'FluxImage',
    'SCPImage',
    'HFEImage',
    # Data classes
    'SCPHeader',
    'HFEHeader',
    'WriteResult',
    # Conversion functions
    'convert_sector_to_flux',
    'convert_flux_to_sector',
    'convert_format',
    # Disk operations
    'read_disk_to_image',
    'write_image_to_disk',
    'compare_image_to_disk',
    # Constants
    'SCP_HEADER_SIZE',
    'HFE_HEADER_SIZE',
    'DEFAULT_SAMPLE_FREQ',
]
