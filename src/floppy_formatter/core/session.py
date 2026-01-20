"""
Disk session configuration for Floppy Workbench.

This module provides the DiskSession dataclass that holds all configuration
for a disk format session. Sessions define the complete disk specification
including geometry, timing, encoding, and hardware settings.

Sessions are the foundation of the Universal Floppy Disk Session System,
allowing users to select ANY floppy disk format before performing operations.
The session configuration flows through all operations (scan, format, restore,
analyze, export) ensuring correct timing, encoding, and geometry.

Part of Phase 1: Core Data Model
"""

import uuid
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from floppy_formatter.core.geometry import DiskGeometry

# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Bus Type Constants
# =============================================================================

class BusType:
    """Bus type constants for Greaseweazle hardware."""
    IBMPC = 1      # IBM PC style bus (most common)
    SHUGART = 2    # Shugart bus (older/non-IBM systems)


# =============================================================================
# Encoding Type Constants
# =============================================================================

class EncodingType:
    """Encoding type constants for disk formats."""
    MFM = "mfm"              # Modified Frequency Modulation (IBM PC HD/DD)
    FM = "fm"                # Frequency Modulation (older formats)
    GCR = "gcr"              # Group Code Recording (Apple, C64)
    AMIGA = "amiga"          # Amiga MFM variant
    MAC_GCR = "mac_gcr"      # Macintosh GCR
    C64_GCR = "c64_gcr"      # Commodore 64 GCR
    APPLE_GCR = "apple_gcr"  # Apple II GCR
    MMFM = "mmfm"            # Modified MFM (HP)
    M2FM = "m2fm"            # M2FM (DEC)
    MICROPOLIS = "micropolis"  # Micropolis encoding
    NORTHSTAR = "northstar"    # North Star encoding


# =============================================================================
# Disk Size Constants
# =============================================================================

class DiskSize:
    """Physical disk size constants."""
    THREE_HALF = '3.5"'      # 3.5 inch floppy
    FIVE_QUARTER = '5.25"'   # 5.25 inch floppy
    EIGHT = '8"'             # 8 inch floppy


# =============================================================================
# DiskSession Dataclass
# =============================================================================

@dataclass
class DiskSession:
    """
    Complete disk session configuration.

    A DiskSession holds all parameters needed to work with a specific
    floppy disk format. This includes physical geometry, timing parameters,
    encoding type, and hardware settings.

    The session is created from a Greaseweazle format string (e.g., 'ibm.1440')
    and can be serialized to/from dictionaries for persistence.

    Attributes:
        session_id: Unique identifier for this session
        name: Human-readable session name
        created_at: Timestamp when session was created

        platform: Platform prefix (e.g., 'ibm', 'amiga', 'mac')
        format_name: Format name within platform (e.g., '1440', 'amigados')
        gw_format: Full Greaseweazle format string (e.g., 'ibm.1440')

        disk_size: Physical disk size ('3.5"', '5.25"', '8"')

        cylinders: Number of cylinders/tracks per side
        heads: Number of heads/sides
        sectors_per_track: Sectors per track (may vary by track for some formats)
        bytes_per_sector: Bytes per sector

        encoding: Encoding type (mfm, fm, gcr, etc.)
        data_rate_kbps: Data rate in kbit/s
        rpm: Disk rotation speed in RPM
        bit_cell_us: Bit cell time in microseconds

        bus_type: Hardware bus type (1=IBMPC, 2=Shugart)

    Example:
        >>> session = DiskSession.from_gw_format('ibm.1440')
        >>> print(session.name)
        'IBM PC 1.44MB HD'
        >>> geometry = session.to_geometry()
        >>> print(geometry.total_sectors)
        2880
    """

    # Identification
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Session"
    created_at: datetime = field(default_factory=datetime.now)

    # Platform/Format (maps to Greaseweazle diskdef)
    platform: str = "ibm"
    format_name: str = "1440"
    gw_format: str = "ibm.1440"

    # Physical disk
    disk_size: str = DiskSize.THREE_HALF

    # Geometry
    cylinders: int = 80
    heads: int = 2
    sectors_per_track: int = 18
    bytes_per_sector: int = 512

    # Timing/Encoding
    encoding: str = EncodingType.MFM
    data_rate_kbps: int = 500
    rpm: int = 300
    bit_cell_us: float = 2.0

    # Hardware
    bus_type: int = BusType.IBMPC

    # =========================================================================
    # Geometry Conversion
    # =========================================================================

    def to_geometry(self) -> 'DiskGeometry':
        """
        Convert session to a DiskGeometry object.

        Returns:
            DiskGeometry object with parameters from this session

        Example:
            >>> session = DiskSession.from_gw_format('ibm.1440')
            >>> geometry = session.to_geometry()
            >>> print(geometry.total_sectors)
            2880
        """
        # Import here to avoid circular imports
        from floppy_formatter.core.geometry import DiskGeometry

        # Determine media type based on format
        media_type = self._get_media_type()

        return DiskGeometry(
            media_type=media_type,
            cylinders=self.cylinders,
            heads=self.heads,
            sectors_per_track=self.sectors_per_track,
            bytes_per_sector=self.bytes_per_sector,
        )

    def _get_media_type(self) -> int:
        """
        Get media type constant based on format.

        Returns:
            Media type constant for this format
        """
        # Standard media type constants
        MEDIA_TYPE_F3_1Pt44_512 = 0x0F  # 1.44MB 3.5"
        MEDIA_TYPE_F3_720_512 = 0x05    # 720KB 3.5"
        MEDIA_TYPE_F5_1Pt2_512 = 0x03   # 1.2MB 5.25"
        MEDIA_TYPE_F5_360_512 = 0x01    # 360KB 5.25"
        MEDIA_TYPE_F3_2Pt88_512 = 0x12  # 2.88MB 3.5"

        # Match based on format characteristics
        total_kb = (self.cylinders * self.heads * self.sectors_per_track *
                    self.bytes_per_sector) // 1024

        if self.disk_size == DiskSize.THREE_HALF:
            if total_kb >= 2800:
                return MEDIA_TYPE_F3_2Pt88_512
            elif total_kb >= 1400:
                return MEDIA_TYPE_F3_1Pt44_512
            else:
                return MEDIA_TYPE_F3_720_512
        elif self.disk_size == DiskSize.FIVE_QUARTER:
            if total_kb >= 1000:
                return MEDIA_TYPE_F5_1Pt2_512
            else:
                return MEDIA_TYPE_F5_360_512
        else:
            # 8" or unknown - use generic value
            return 0x00

    # =========================================================================
    # Calculated Properties
    # =========================================================================

    @property
    def total_sectors(self) -> int:
        """Calculate total number of sectors on disk."""
        return self.cylinders * self.heads * self.sectors_per_track

    @property
    def total_bytes(self) -> int:
        """Calculate total capacity in bytes."""
        return self.total_sectors * self.bytes_per_sector

    @property
    def capacity_kb(self) -> int:
        """Calculate capacity in kilobytes."""
        return self.total_bytes // 1024

    @property
    def capacity_mb(self) -> float:
        """Calculate capacity in megabytes."""
        return self.total_bytes / (1024 * 1024)

    @property
    def display_name(self) -> str:
        """
        Get a human-readable display name for the session.

        Returns:
            Display name like 'IBM PC 1.44MB HD (3.5")'
        """
        return f"{self.name} ({self.disk_size})"

    @property
    def short_description(self) -> str:
        """
        Get a short description of the format.

        Returns:
            Short description like '80C/2H/18S MFM'
        """
        return (f"{self.cylinders}C/{self.heads}H/{self.sectors_per_track}S "
                f"{self.encoding.upper()}")

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert session to a dictionary for serialization.

        Returns:
            Dictionary representation of the session

        Example:
            >>> session = DiskSession.from_gw_format('ibm.1440')
            >>> data = session.to_dict()
            >>> restored = DiskSession.from_dict(data)
        """
        return {
            'session_id': self.session_id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'platform': self.platform,
            'format_name': self.format_name,
            'gw_format': self.gw_format,
            'disk_size': self.disk_size,
            'cylinders': self.cylinders,
            'heads': self.heads,
            'sectors_per_track': self.sectors_per_track,
            'bytes_per_sector': self.bytes_per_sector,
            'encoding': self.encoding,
            'data_rate_kbps': self.data_rate_kbps,
            'rpm': self.rpm,
            'bit_cell_us': self.bit_cell_us,
            'bus_type': self.bus_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DiskSession':
        """
        Create a session from a dictionary.

        Args:
            data: Dictionary with session data

        Returns:
            New DiskSession instance

        Example:
            >>> data = {'gw_format': 'ibm.1440', 'name': 'My Session', ...}
            >>> session = DiskSession.from_dict(data)
        """
        # Parse created_at if it's a string
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except (ValueError, TypeError):
                created_at = datetime.now()
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            session_id=data.get('session_id', str(uuid.uuid4())),
            name=data.get('name', 'Untitled Session'),
            created_at=created_at,
            platform=data.get('platform', 'ibm'),
            format_name=data.get('format_name', '1440'),
            gw_format=data.get('gw_format', 'ibm.1440'),
            disk_size=data.get('disk_size', DiskSize.THREE_HALF),
            cylinders=data.get('cylinders', 80),
            heads=data.get('heads', 2),
            sectors_per_track=data.get('sectors_per_track', 18),
            bytes_per_sector=data.get('bytes_per_sector', 512),
            encoding=data.get('encoding', EncodingType.MFM),
            data_rate_kbps=data.get('data_rate_kbps', 500),
            rpm=data.get('rpm', 300),
            bit_cell_us=data.get('bit_cell_us', 2.0),
            bus_type=data.get('bus_type', BusType.IBMPC),
        )

    @classmethod
    def from_gw_format(cls, gw_format: str, name: Optional[str] = None) -> 'DiskSession':
        """
        Create a session from a Greaseweazle format string.

        This method queries the Greaseweazle library to get the disk
        definition and extracts all parameters automatically.

        Args:
            gw_format: Greaseweazle format string (e.g., 'ibm.1440')
            name: Optional custom name for the session

        Returns:
            New DiskSession instance configured for the format

        Raises:
            ValueError: If the format is not found

        Example:
            >>> session = DiskSession.from_gw_format('ibm.1440')
            >>> print(session.cylinders, session.heads, session.sectors_per_track)
            80 2 18
        """
        # Import here to avoid import issues if greaseweazle not installed
        try:
            from greaseweazle.codec.codec import get_diskdef
        except ImportError:
            logger.error("Greaseweazle library not installed")
            raise ValueError("Greaseweazle library not installed")

        # Get the disk definition
        diskdef = get_diskdef(gw_format)
        if diskdef is None:
            raise ValueError(f"Unknown format: {gw_format}")

        # Parse platform and format name from gw_format string
        parts = gw_format.split('.', 1)
        platform = parts[0] if parts else gw_format
        format_name = parts[1] if len(parts) > 1 else gw_format

        # Create a track to get timing and encoding info
        track = diskdef.mk_track(0, 0)

        # Extract timing parameters
        clock_us = track.clock * 1e6 if hasattr(track, 'clock') else 2.0
        time_per_rev = getattr(track, 'time_per_rev', 0.2)
        rpm = int(60 / time_per_rev) if time_per_rev > 0 else 300
        nsec = getattr(track, 'nsec', 18)

        # Determine encoding type from track class name or mode attribute
        track_type = type(track).__name__
        mode = getattr(track, 'mode', track_type)
        # Convert mode to string if it's an Enum
        mode_str = str(mode) if mode is not None else track_type
        encoding = cls._determine_encoding(mode_str, track_type, platform)

        # Determine data rate from clock
        # data_rate_kbps = 1000 / (clock_us * 2) for MFM
        # For MFM: 500kbps -> 2us bit cell, 250kbps -> 4us bit cell
        if clock_us > 0:
            data_rate_kbps = int(500 / clock_us)  # Approximate
        else:
            data_rate_kbps = 500

        # Determine bytes per sector
        bytes_per_sector = cls._determine_bytes_per_sector(track, platform, format_name)

        # Determine disk size based on format
        disk_size = cls._determine_disk_size(platform, format_name, diskdef.cyls)

        # Determine bus type based on platform
        bus_type = cls._determine_bus_type(platform)

        # Generate name if not provided
        if name is None:
            name = cls._generate_format_name(platform, format_name, diskdef.cyls,
                                             diskdef.heads, nsec, bytes_per_sector)

        return cls(
            session_id=str(uuid.uuid4()),
            name=name,
            created_at=datetime.now(),
            platform=platform,
            format_name=format_name,
            gw_format=gw_format,
            disk_size=disk_size,
            cylinders=diskdef.cyls,
            heads=diskdef.heads,
            sectors_per_track=nsec,
            bytes_per_sector=bytes_per_sector,
            encoding=encoding,
            data_rate_kbps=data_rate_kbps,
            rpm=rpm,
            bit_cell_us=clock_us,
            bus_type=bus_type,
        )

    @staticmethod
    def _determine_encoding(mode: str, track_type: str, platform: str) -> str:
        """Determine encoding type from mode string and track type."""
        mode_lower = mode.lower()
        track_lower = track_type.lower()

        if 'fm' in mode_lower and 'mfm' not in mode_lower:
            return EncodingType.FM
        elif 'mfm' in mode_lower or 'mfm' in track_lower:
            return EncodingType.MFM
        elif 'amiga' in track_lower:
            return EncodingType.AMIGA
        elif 'macgcr' in track_lower or 'mac' in platform:
            return EncodingType.MAC_GCR
        elif 'c64gcr' in track_lower or platform == 'commodore':
            return EncodingType.C64_GCR
        elif 'apple' in platform or 'apple' in track_lower:
            return EncodingType.APPLE_GCR
        elif 'mmfm' in mode_lower or platform == 'hp':
            return EncodingType.MMFM
        elif 'm2fm' in mode_lower:
            return EncodingType.M2FM
        elif 'micropolis' in track_lower or platform == 'micropolis':
            return EncodingType.MICROPOLIS
        elif 'northstar' in track_lower or platform == 'northstar':
            return EncodingType.NORTHSTAR
        elif 'gcr' in mode_lower or 'gcr' in track_lower:
            return EncodingType.GCR
        else:
            return EncodingType.MFM  # Default to MFM

    @staticmethod
    def _determine_bytes_per_sector(track: Any, platform: str, format_name: str) -> int:
        """Determine bytes per sector from track info."""
        # Try to get from track attributes
        if hasattr(track, 'img_bps') and track.img_bps:
            return track.img_bps

        # Check for sector data
        if hasattr(track, 'sectors') and track.sectors:
            for sec in track.sectors:
                if hasattr(sec, 'data') and sec.data:
                    return len(sec.data)
                if hasattr(sec, 'size'):
                    return sec.size

        # Default based on platform
        if platform in ('commodore',):
            return 256  # C64 uses 256 byte sectors
        elif platform in ('mac', 'apple2'):
            return 512  # Mac and Apple II typically 512
        else:
            return 512  # Default to 512

    @staticmethod
    def _determine_disk_size(platform: str, format_name: str, cylinders: int) -> str:
        """Determine physical disk size from format info."""
        format_lower = format_name.lower()

        # 8" formats
        if 'rx' in format_lower or platform == 'dec':
            return DiskSize.EIGHT

        # 5.25" formats
        five_quarter_platforms = ('apple2', 'commodore', 'atari', 'coco', 'dragon',
                                  'northstar', 'micropolis')
        five_quarter_formats = ('1200', '360', '1541', '1571', '40t', '40ds', '40ss')

        if platform in five_quarter_platforms:
            return DiskSize.FIVE_QUARTER
        if any(f in format_lower for f in five_quarter_formats):
            return DiskSize.FIVE_QUARTER
        if cylinders <= 42:
            return DiskSize.FIVE_QUARTER

        # Default to 3.5"
        return DiskSize.THREE_HALF

    @staticmethod
    def _determine_bus_type(platform: str) -> int:
        """Determine bus type from platform."""
        # Shugart bus platforms
        shugart_platforms = ('amiga', 'atari', 'atarist', 'commodore', 'apple2',
                            'mac', 'acorn', 'bbc')

        if platform.lower() in shugart_platforms:
            return BusType.SHUGART

        return BusType.IBMPC

    @staticmethod
    def _generate_format_name(platform: str, format_name: str, cylinders: int,
                              heads: int, sectors: int, bytes_per_sector: int) -> str:
        """Generate a human-readable format name."""
        # Calculate capacity
        total_kb = (cylinders * heads * sectors * bytes_per_sector) // 1024

        # Platform display names
        platform_names = {
            'ibm': 'IBM PC',
            'amiga': 'Amiga',
            'mac': 'Macintosh',
            'apple2': 'Apple II',
            'commodore': 'Commodore',
            'atarist': 'Atari ST',
            'atari': 'Atari 8-bit',
            'acorn': 'Acorn/BBC Micro',
            'zx': 'ZX Spectrum',
            'msx': 'MSX',
            'coco': 'TRS-80 CoCo',
            'dragon': 'Dragon 32/64',
            'hp': 'HP',
            'dec': 'DEC',
            'pc98': 'NEC PC-98',
            'micropolis': 'Micropolis',
            'northstar': 'North Star',
            'sega': 'Sega',
            'ensoniq': 'Ensoniq',
            'akai': 'Akai',
            'thomson': 'Thomson',
            'olivetti': 'Olivetti',
            'gem': 'GEM',
            'occ1': 'OCC',
            'sci': 'SCI',
            'tsc': 'TSC',
            'epson': 'Epson',
            'mm1': 'MM/1',
            'raw': 'Raw',
        }

        platform_display = platform_names.get(platform.lower(), platform.title())

        # Capacity display
        if total_kb >= 1024:
            capacity_str = f"{total_kb / 1024:.2f}MB".rstrip('0').rstrip('.')
        else:
            capacity_str = f"{total_kb}KB"

        # Density indicator
        if sectors >= 18 and bytes_per_sector == 512:
            density = "HD"
        elif sectors >= 36:
            density = "ED"
        else:
            density = "DD"

        return f"{platform_display} {capacity_str} {density}"

    # =========================================================================
    # Comparison and Hashing
    # =========================================================================

    def __eq__(self, other: object) -> bool:
        """Check equality based on gw_format."""
        if not isinstance(other, DiskSession):
            return False
        return self.gw_format == other.gw_format

    def __hash__(self) -> int:
        """Hash based on gw_format."""
        return hash(self.gw_format)

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self.name} ({self.gw_format})"

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (f"DiskSession(gw_format='{self.gw_format}', "
                f"cylinders={self.cylinders}, heads={self.heads}, "
                f"sectors_per_track={self.sectors_per_track})")


# =============================================================================
# Default Session Factory
# =============================================================================

def get_default_session() -> DiskSession:
    """
    Get the default session (IBM PC 1.44MB HD 3.5").

    Returns:
        Default DiskSession instance

    Example:
        >>> session = get_default_session()
        >>> print(session.gw_format)
        'ibm.1440'
    """
    try:
        return DiskSession.from_gw_format('ibm.1440', name='IBM PC 1.44MB HD')
    except (ImportError, ValueError) as e:
        logger.warning(f"Could not create session from Greaseweazle: {e}")
        # Return a manually configured default
        return DiskSession(
            name='IBM PC 1.44MB HD',
            platform='ibm',
            format_name='1440',
            gw_format='ibm.1440',
            disk_size=DiskSize.THREE_HALF,
            cylinders=80,
            heads=2,
            sectors_per_track=18,
            bytes_per_sector=512,
            encoding=EncodingType.MFM,
            data_rate_kbps=500,
            rpm=300,
            bit_cell_us=2.0,
            bus_type=BusType.IBMPC,
        )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'DiskSession',
    'BusType',
    'EncodingType',
    'DiskSize',
    'get_default_session',
]
