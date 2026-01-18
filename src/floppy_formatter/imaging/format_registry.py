"""
Disk Format Registry for Write Image feature.

Contains specifications for all supported disk formats across multiple platforms:
- IBM PC (DOS/Windows)
- Amiga
- Macintosh
- Atari ST
- BBC Micro
- Commodore
- Apple II
- MSX
- Amstrad CPC
- Sam Coupé

Part of the Write Image feature for writing blank formatted disk images.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


# =============================================================================
# Enums
# =============================================================================

class Encoding(Enum):
    """Disk encoding types."""
    MFM = "MFM"      # Modified Frequency Modulation (most common)
    FM = "FM"        # Frequency Modulation (older, single density)
    GCR = "GCR"      # Group Coded Recording (Apple, Commodore, Mac)
    AMIGA = "AMIGA"  # Amiga-specific MFM variant


class Density(Enum):
    """Disk density types."""
    SD = "SD"    # Single Density
    DD = "DD"    # Double Density
    HD = "HD"    # High Density
    ED = "ED"    # Extended Density


class Platform(Enum):
    """Supported platforms."""
    IBM_PC = "IBM PC"
    AMIGA = "Amiga"
    MACINTOSH = "Macintosh"
    ATARI_ST = "Atari ST"
    BBC_MICRO = "BBC Micro"
    COMMODORE = "Commodore"
    APPLE_II = "Apple II"
    MSX = "MSX"
    AMSTRAD_CPC = "Amstrad CPC"
    SAM_COUPE = "Sam Coupé"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DiskFormatSpec:
    """
    Specification for a disk format.

    Contains all the technical details needed to write a blank formatted
    disk image to a physical floppy disk.
    """
    # Identification
    platform: Platform
    name: str
    description: str

    # Physical geometry
    cylinders: int
    heads: int
    sectors_per_track: int
    bytes_per_sector: int

    # Encoding parameters
    encoding: Encoding
    density: Density
    data_rate_kbps: int

    # RPM (most are 300, but some older formats use 360)
    rpm: int = 300

    # Sector numbering (most start at 1, but some start at 0)
    first_sector_id: int = 1

    # Gap sizes (bytes) - for MFM/FM encoding
    gap1: int = 50      # Post-index gap
    gap2: int = 22      # Post-ID gap
    gap3: int = 80      # Post-data gap
    gap4: int = 200     # Pre-index gap (fill to track end)

    # Interleave factor (1 = no interleave)
    interleave: int = 1

    # Track skew (sectors to skip between tracks)
    track_skew: int = 0

    # Head skew (sectors to skip between heads)
    head_skew: int = 0

    # File extension for generated image
    file_extension: str = "img"

    # Bundled image filename (relative to data/disk_images/)
    image_filename: str = ""

    # Whether this format is commonly used (for UI sorting)
    common: bool = False

    # Additional notes for UI display
    notes: str = ""

    # Whether a bundled image is available
    has_bundled_image: bool = False

    @property
    def capacity_bytes(self) -> int:
        """Calculate total capacity in bytes."""
        return (self.cylinders * self.heads *
                self.sectors_per_track * self.bytes_per_sector)

    @property
    def capacity_kb(self) -> int:
        """Calculate total capacity in KB."""
        return self.capacity_bytes // 1024

    @property
    def total_tracks(self) -> int:
        """Calculate total number of tracks."""
        return self.cylinders * self.heads

    @property
    def total_sectors(self) -> int:
        """Calculate total number of sectors."""
        return self.total_tracks * self.sectors_per_track

    @property
    def bit_cell_us(self) -> float:
        """Calculate bit cell time in microseconds."""
        if self.density == Density.HD:
            return 1.0  # HD: 1µs bit cell
        elif self.density == Density.DD:
            return 2.0  # DD: 2µs bit cell
        elif self.density == Density.SD:
            return 4.0  # SD: 4µs bit cell (FM)
        else:
            return 2.0  # Default to DD

    @property
    def display_name(self) -> str:
        """Get display name for UI."""
        return f"{self.name} ({self.capacity_kb}KB)"

    @property
    def full_description(self) -> str:
        """Get full description for UI tooltip."""
        return (f"{self.platform.value} {self.name}\n"
                f"Capacity: {self.capacity_kb}KB\n"
                f"Geometry: {self.cylinders}C x {self.heads}H x "
                f"{self.sectors_per_track}S x {self.bytes_per_sector}B\n"
                f"Encoding: {self.encoding.value}, {self.density.value}\n"
                f"Data Rate: {self.data_rate_kbps} kbps")

    def get_sector_ids(self, cylinder: int, head: int) -> List[int]:
        """
        Get the sector IDs for a given track, accounting for interleave.

        Args:
            cylinder: Cylinder number
            head: Head number

        Returns:
            List of sector IDs in the order they appear on the track
        """
        # Calculate starting sector based on skew
        start_offset = (
            cylinder * self.track_skew + head * self.head_skew
        ) % self.sectors_per_track

        # Generate sector order with interleave
        sectors = []
        for i in range(self.sectors_per_track):
            sector_id = (
                (i * self.interleave + start_offset) % self.sectors_per_track
            ) + self.first_sector_id
            sectors.append(sector_id)

        return sectors


# =============================================================================
# Format Registry
# =============================================================================

# IBM PC Formats
IBM_PC_FORMATS = [
    DiskFormatSpec(
        platform=Platform.IBM_PC,
        name="1.44MB HD",
        description="Standard PC 3.5\" High Density",
        cylinders=80,
        heads=2,
        sectors_per_track=18,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.HD,
        data_rate_kbps=500,
        file_extension="img",
        image_filename="ibm_pc/blank_1440.img",
        common=True,
        has_bundled_image=True,
        notes="Most common PC floppy format"
    ),
    DiskFormatSpec(
        platform=Platform.IBM_PC,
        name="720KB DD",
        description="Standard PC 3.5\" Double Density",
        cylinders=80,
        heads=2,
        sectors_per_track=9,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.DD,
        data_rate_kbps=250,
        file_extension="img",
        image_filename="ibm_pc/blank_720.img",
        common=True,
        has_bundled_image=True,
        notes="Common PC DD format"
    ),
    DiskFormatSpec(
        platform=Platform.IBM_PC,
        name="1.2MB HD",
        description="PC 5.25\" High Density",
        cylinders=80,
        heads=2,
        sectors_per_track=15,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.HD,
        data_rate_kbps=500,
        rpm=360,
        file_extension="img",
        image_filename="ibm_pc/blank_1200.img",
        common=True,
        has_bundled_image=True,
        notes="5.25\" HD format"
    ),
    DiskFormatSpec(
        platform=Platform.IBM_PC,
        name="360KB DD",
        description="PC 5.25\" Double Density",
        cylinders=40,
        heads=2,
        sectors_per_track=9,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.DD,
        data_rate_kbps=250,
        rpm=300,
        file_extension="img",
        image_filename="ibm_pc/blank_360.img",
        common=True,
        has_bundled_image=True,
        notes="Original PC floppy format"
    ),
    DiskFormatSpec(
        platform=Platform.IBM_PC,
        name="180KB SS DD",
        description="PC 5.25\" Single-Sided DD",
        cylinders=40,
        heads=1,
        sectors_per_track=9,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.DD,
        data_rate_kbps=250,
        rpm=300,
        file_extension="img",
        image_filename="ibm_pc/blank_180.img",
        has_bundled_image=True,
        notes="Early PC single-sided format"
    ),
    DiskFormatSpec(
        platform=Platform.IBM_PC,
        name="160KB SS DD",
        description="PC 5.25\" Single-Sided DD (8 sectors)",
        cylinders=40,
        heads=1,
        sectors_per_track=8,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.DD,
        data_rate_kbps=250,
        rpm=300,
        file_extension="img",
        image_filename="ibm_pc/blank_160.img",
        has_bundled_image=True,
        notes="Original IBM PC format"
    ),
    DiskFormatSpec(
        platform=Platform.IBM_PC,
        name="320KB DD",
        description="PC 5.25\" Double-Sided DD (8 sectors)",
        cylinders=40,
        heads=2,
        sectors_per_track=8,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.DD,
        data_rate_kbps=250,
        rpm=300,
        file_extension="img",
        image_filename="ibm_pc/blank_320.img",
        has_bundled_image=True,
        notes="Early PC double-sided format"
    ),
    DiskFormatSpec(
        platform=Platform.IBM_PC,
        name="2.88MB ED",
        description="PC 3.5\" Extended Density",
        cylinders=80,
        heads=2,
        sectors_per_track=36,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.ED,
        data_rate_kbps=1000,
        file_extension="img",
        image_filename="ibm_pc/blank_2880.img",
        has_bundled_image=True,
        notes="Rare ED format, requires special drive"
    ),
]

# Amiga Formats
AMIGA_FORMATS = [
    DiskFormatSpec(
        platform=Platform.AMIGA,
        name="880KB DD (OFS)",
        description="Standard Amiga 3.5\" DD (Old File System)",
        cylinders=80,
        heads=2,
        sectors_per_track=11,
        bytes_per_sector=512,
        encoding=Encoding.AMIGA,
        density=Density.DD,
        data_rate_kbps=250,
        first_sector_id=0,
        file_extension="adf",
        image_filename="amiga/Empty-DD-OFS.adf",
        common=True,
        has_bundled_image=True,
        notes="Standard AmigaDOS OFS format"
    ),
    DiskFormatSpec(
        platform=Platform.AMIGA,
        name="880KB DD (FFS)",
        description="Standard Amiga 3.5\" DD (Fast File System)",
        cylinders=80,
        heads=2,
        sectors_per_track=11,
        bytes_per_sector=512,
        encoding=Encoding.AMIGA,
        density=Density.DD,
        data_rate_kbps=250,
        first_sector_id=0,
        file_extension="adf",
        image_filename="amiga/Empty-DD-FFS.adf",
        common=True,
        has_bundled_image=True,
        notes="Standard AmigaDOS FFS format"
    ),
    DiskFormatSpec(
        platform=Platform.AMIGA,
        name="1.76MB HD (FFS)",
        description="Amiga 3.5\" HD (Fast File System)",
        cylinders=80,
        heads=2,
        sectors_per_track=22,
        bytes_per_sector=512,
        encoding=Encoding.AMIGA,
        density=Density.HD,
        data_rate_kbps=500,
        first_sector_id=0,
        file_extension="adf",
        image_filename="amiga/Empty-HD-FFS.adf",
        has_bundled_image=True,
        notes="Amiga HD format, requires HD drive"
    ),
]

# Atari ST Formats
ATARI_ST_FORMATS = [
    DiskFormatSpec(
        platform=Platform.ATARI_ST,
        name="720KB DD",
        description="Standard Atari ST 3.5\" DD",
        cylinders=80,
        heads=2,
        sectors_per_track=9,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.DD,
        data_rate_kbps=250,
        file_extension="st",
        image_filename="atari_st/blank_720k.st",
        common=True,
        has_bundled_image=True,
        notes="Standard Atari ST format, PC compatible"
    ),
    DiskFormatSpec(
        platform=Platform.ATARI_ST,
        name="800KB DD (10 sec)",
        description="Atari ST Extended DD",
        cylinders=80,
        heads=2,
        sectors_per_track=10,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.DD,
        data_rate_kbps=250,
        file_extension="st",
        image_filename="atari_st/blank_800k.st",
        has_bundled_image=True,
        notes="Extended format, not PC compatible"
    ),
]

# BBC Micro Formats
BBC_MICRO_FORMATS = [
    DiskFormatSpec(
        platform=Platform.BBC_MICRO,
        name="DFS 200KB SS",
        description="Acorn DFS Single-Sided",
        cylinders=80,
        heads=1,
        sectors_per_track=10,
        bytes_per_sector=256,
        encoding=Encoding.FM,
        density=Density.SD,
        data_rate_kbps=125,
        first_sector_id=0,
        file_extension="ssd",
        image_filename="bbc_micro/blank_dfs_ss.ssd",
        common=True,
        has_bundled_image=True,
        notes="Standard BBC DFS format"
    ),
    DiskFormatSpec(
        platform=Platform.BBC_MICRO,
        name="DFS 400KB DS",
        description="Acorn DFS Double-Sided",
        cylinders=80,
        heads=2,
        sectors_per_track=10,
        bytes_per_sector=256,
        encoding=Encoding.FM,
        density=Density.SD,
        data_rate_kbps=125,
        first_sector_id=0,
        file_extension="dsd",
        image_filename="bbc_micro/blank_dfs_ds.dsd",
        has_bundled_image=True,
        notes="Double-sided DFS format"
    ),
]

# Commodore Formats
COMMODORE_FORMATS = [
    DiskFormatSpec(
        platform=Platform.COMMODORE,
        name="1541 170KB",
        description="Commodore 64 1541 Drive",
        cylinders=35,
        heads=1,
        sectors_per_track=17,  # Average, varies by zone
        bytes_per_sector=256,
        encoding=Encoding.GCR,
        density=Density.DD,
        data_rate_kbps=250,
        first_sector_id=0,
        rpm=300,
        file_extension="d64",
        image_filename="commodore/blank_1541.d64",
        common=True,
        has_bundled_image=True,
        notes="C64 standard format, variable sectors per track"
    ),
]

# Macintosh Formats
MACINTOSH_FORMATS = [
    DiskFormatSpec(
        platform=Platform.MACINTOSH,
        name="400KB SS HFS",
        description="Original Macintosh 400KB",
        cylinders=80,
        heads=1,
        sectors_per_track=10,  # Average, varies by zone
        bytes_per_sector=512,
        encoding=Encoding.GCR,
        density=Density.DD,
        data_rate_kbps=250,
        first_sector_id=0,
        rpm=300,  # Variable speed
        file_extension="dsk",
        image_filename="macintosh/400K.dsk",
        has_bundled_image=True,
        notes="Classic Mac GCR, variable speed"
    ),
    DiskFormatSpec(
        platform=Platform.MACINTOSH,
        name="800KB DS HFS",
        description="Macintosh 800KB Double-Sided",
        cylinders=80,
        heads=2,
        sectors_per_track=10,  # Average, varies by zone
        bytes_per_sector=512,
        encoding=Encoding.GCR,
        density=Density.DD,
        data_rate_kbps=250,
        first_sector_id=0,
        rpm=300,  # Variable speed
        file_extension="dsk",
        image_filename="macintosh/800K.dsk",
        common=True,
        has_bundled_image=True,
        notes="Classic Mac GCR, variable speed"
    ),
    DiskFormatSpec(
        platform=Platform.MACINTOSH,
        name="1.44MB HD HFS",
        description="Macintosh SuperDrive HD",
        cylinders=80,
        heads=2,
        sectors_per_track=18,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.HD,
        data_rate_kbps=500,
        file_extension="dsk",
        image_filename="macintosh/1440K.dsk",
        common=True,
        has_bundled_image=True,
        notes="PC-compatible HD format"
    ),
]

# Apple II Formats (no bundled images - GCR encoding)
APPLE_II_FORMATS = []

# MSX Formats
MSX_FORMATS = [
    DiskFormatSpec(
        platform=Platform.MSX,
        name="720KB DD",
        description="Standard MSX-DOS",
        cylinders=80,
        heads=2,
        sectors_per_track=9,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.DD,
        data_rate_kbps=250,
        file_extension="dsk",
        image_filename="msx/blank_720k.dsk",
        common=True,
        has_bundled_image=True,
        notes="Standard MSX format, PC compatible"
    ),
]

# Amstrad CPC Formats
AMSTRAD_CPC_FORMATS = [
    DiskFormatSpec(
        platform=Platform.AMSTRAD_CPC,
        name="Data 180KB",
        description="Amstrad CPC Data Format",
        cylinders=40,
        heads=1,
        sectors_per_track=9,
        bytes_per_sector=512,
        encoding=Encoding.MFM,
        density=Density.DD,
        data_rate_kbps=250,
        first_sector_id=0xC1,  # Amstrad uses 0xC1-0xC9
        file_extension="dsk",
        image_filename="amstrad_cpc/blank_data.dsk",
        common=True,
        has_bundled_image=True,
        notes="Standard Amstrad data format"
    ),
]

# Sam Coupé Formats (no bundled images)
SAM_COUPE_FORMATS = []


# =============================================================================
# Format Registry Class
# =============================================================================

class FormatRegistry:
    """
    Registry of all supported disk formats.

    Provides methods to query and retrieve format specifications by
    platform, encoding, density, or other criteria.
    """

    def __init__(self):
        """Initialize the format registry."""
        self._formats: Dict[Platform, List[DiskFormatSpec]] = {
            Platform.IBM_PC: IBM_PC_FORMATS,
            Platform.AMIGA: AMIGA_FORMATS,
            Platform.ATARI_ST: ATARI_ST_FORMATS,
            Platform.BBC_MICRO: BBC_MICRO_FORMATS,
            Platform.COMMODORE: COMMODORE_FORMATS,
            Platform.MACINTOSH: MACINTOSH_FORMATS,
            Platform.APPLE_II: APPLE_II_FORMATS,
            Platform.MSX: MSX_FORMATS,
            Platform.AMSTRAD_CPC: AMSTRAD_CPC_FORMATS,
            Platform.SAM_COUPE: SAM_COUPE_FORMATS,
        }

    def get_platforms(self) -> List[Platform]:
        """
        Get list of all supported platforms.

        Returns:
            List of Platform enum values
        """
        return list(self._formats.keys())

    def get_platform_names(self) -> List[str]:
        """
        Get list of all platform display names.

        Returns:
            List of platform name strings
        """
        return [p.value for p in self._formats.keys()]

    def get_formats_for_platform(self, platform: Platform) -> List[DiskFormatSpec]:
        """
        Get all formats for a specific platform.

        Args:
            platform: Platform enum value

        Returns:
            List of DiskFormatSpec for that platform
        """
        return self._formats.get(platform, [])

    def get_formats_by_platform_name(self, name: str) -> List[DiskFormatSpec]:
        """
        Get formats for a platform by its display name.

        Args:
            name: Platform display name (e.g., "IBM PC")

        Returns:
            List of DiskFormatSpec for that platform
        """
        for platform, formats in self._formats.items():
            if platform.value == name:
                return formats
        return []

    def get_all_formats(self) -> List[DiskFormatSpec]:
        """
        Get all formats across all platforms.

        Returns:
            List of all DiskFormatSpec
        """
        all_formats = []
        for formats in self._formats.values():
            all_formats.extend(formats)
        return all_formats

    def get_common_formats(self) -> List[DiskFormatSpec]:
        """
        Get commonly used formats across all platforms.

        Returns:
            List of DiskFormatSpec marked as common
        """
        return [f for f in self.get_all_formats() if f.common]

    def get_formats_by_encoding(self, encoding: Encoding) -> List[DiskFormatSpec]:
        """
        Get all formats using a specific encoding.

        Args:
            encoding: Encoding type (MFM, FM, GCR, AMIGA)

        Returns:
            List of DiskFormatSpec using that encoding
        """
        return [f for f in self.get_all_formats() if f.encoding == encoding]

    def get_formats_by_density(self, density: Density) -> List[DiskFormatSpec]:
        """
        Get all formats using a specific density.

        Args:
            density: Density type (SD, DD, HD, ED)

        Returns:
            List of DiskFormatSpec using that density
        """
        return [f for f in self.get_all_formats() if f.density == density]

    def get_mfm_formats(self) -> List[DiskFormatSpec]:
        """
        Get all MFM-encoded formats (directly writable with standard encoder).

        Returns:
            List of DiskFormatSpec using MFM encoding
        """
        return self.get_formats_by_encoding(Encoding.MFM)

    def find_format(
        self,
        platform: Platform,
        name: str
    ) -> Optional[DiskFormatSpec]:
        """
        Find a specific format by platform and name.

        Args:
            platform: Platform enum value
            name: Format name

        Returns:
            DiskFormatSpec if found, None otherwise
        """
        for fmt in self.get_formats_for_platform(platform):
            if fmt.name == name:
                return fmt
        return None

    def find_format_by_display_name(
        self,
        platform_name: str,
        format_display_name: str
    ) -> Optional[DiskFormatSpec]:
        """
        Find a format by platform name and format display name.

        Args:
            platform_name: Platform display name
            format_display_name: Format display name (includes capacity)

        Returns:
            DiskFormatSpec if found, None otherwise
        """
        formats = self.get_formats_by_platform_name(platform_name)
        for fmt in formats:
            if fmt.display_name == format_display_name:
                return fmt
        return None

    def is_format_supported(self, format_spec: DiskFormatSpec) -> Tuple[bool, str]:
        """
        Check if a format can be written with current capabilities.

        Args:
            format_spec: Format specification to check

        Returns:
            Tuple of (supported, reason) - reason explains why not supported
        """
        # MFM formats are fully supported
        if format_spec.encoding == Encoding.MFM:
            return True, "MFM encoding supported"

        # FM formats supported via Greaseweazle
        if format_spec.encoding == Encoding.FM:
            return True, "FM encoding supported via Greaseweazle"

        # Amiga formats supported via Greaseweazle
        if format_spec.encoding == Encoding.AMIGA:
            return True, "Amiga encoding supported via Greaseweazle"

        # GCR formats require special handling
        if format_spec.encoding == Encoding.GCR:
            # Commodore GCR is supported via Greaseweazle
            if format_spec.platform == Platform.COMMODORE:
                return True, "Commodore GCR supported via Greaseweazle"
            # Apple GCR is supported via Greaseweazle
            if format_spec.platform == Platform.APPLE_II:
                return True, "Apple GCR supported via Greaseweazle"
            # Mac GCR requires variable speed motor
            if format_spec.platform == Platform.MACINTOSH:
                if format_spec.density == Density.HD:
                    return True, "Mac HD MFM format supported"
                return False, "Mac GCR requires variable speed motor"

        return False, "Unknown encoding type"


# =============================================================================
# Module-level singleton
# =============================================================================

_registry: Optional[FormatRegistry] = None


def get_format_registry() -> FormatRegistry:
    """
    Get the global format registry singleton.

    Returns:
        FormatRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = FormatRegistry()
    return _registry


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'Encoding',
    'Density',
    'Platform',
    'DiskFormatSpec',
    'FormatRegistry',
    'get_format_registry',
    # Format lists for direct access
    'IBM_PC_FORMATS',
    'AMIGA_FORMATS',
    'ATARI_ST_FORMATS',
    'BBC_MICRO_FORMATS',
    'COMMODORE_FORMATS',
    'MACINTOSH_FORMATS',
    'APPLE_II_FORMATS',
    'MSX_FORMATS',
    'AMSTRAD_CPC_FORMATS',
    'SAM_COUPE_FORMATS',
]
