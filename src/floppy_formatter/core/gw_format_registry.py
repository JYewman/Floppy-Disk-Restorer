"""
Greaseweazle format registry for Floppy Workbench.

This module provides the GWFormatRegistry class that discovers and provides
access to ALL Greaseweazle disk formats. It dynamically parses format
definitions from the Greaseweazle library to ensure complete platform coverage.

Supported platforms include (but are not limited to):
- IBM PC (160KB through 2.88MB)
- Amiga (880KB DD, 1.76MB HD)
- Macintosh (400KB, 800KB GCR)
- Apple II (DOS 3.3, ProDOS)
- Commodore (1541, 1571, 1581)
- Atari ST
- Acorn/BBC Micro
- ZX Spectrum
- And many more...

Part of Phase 1: Core Data Model
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Platform Metadata
# =============================================================================

@dataclass
class PlatformInfo:
    """Information about a disk platform."""
    id: str                    # Internal ID (e.g., 'ibm')
    display_name: str          # Human-readable name (e.g., 'IBM PC')
    description: str           # Brief description
    default_encoding: str      # Default encoding type
    default_bus_type: int      # Default bus type (1=IBMPC, 2=Shugart)
    primary_disk_size: str     # Primary disk size ('3.5"', '5.25"', '8"')
    manufacturer: str          # Original manufacturer
    era: str                   # Era of use (e.g., '1980s-1990s')


# Platform metadata dictionary
# This provides human-readable names and additional context for each platform
PLATFORM_METADATA: Dict[str, PlatformInfo] = {
    'ibm': PlatformInfo(
        id='ibm',
        display_name='IBM PC',
        description='IBM PC and compatible formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='IBM',
        era='1981-present',
    ),
    'amiga': PlatformInfo(
        id='amiga',
        display_name='Amiga',
        description='Commodore Amiga formats',
        default_encoding='amiga',
        default_bus_type=2,
        primary_disk_size='3.5"',
        manufacturer='Commodore',
        era='1985-1996',
    ),
    'mac': PlatformInfo(
        id='mac',
        display_name='Macintosh',
        description='Apple Macintosh GCR formats',
        default_encoding='mac_gcr',
        default_bus_type=2,
        primary_disk_size='3.5"',
        manufacturer='Apple',
        era='1984-1998',
    ),
    'apple2': PlatformInfo(
        id='apple2',
        display_name='Apple II',
        description='Apple II GCR formats',
        default_encoding='apple_gcr',
        default_bus_type=2,
        primary_disk_size='5.25"',
        manufacturer='Apple',
        era='1977-1993',
    ),
    'commodore': PlatformInfo(
        id='commodore',
        display_name='Commodore 64/128',
        description='Commodore 64, 128, and CMD drive formats',
        default_encoding='c64_gcr',
        default_bus_type=2,
        primary_disk_size='5.25"',
        manufacturer='Commodore',
        era='1982-1994',
    ),
    'atarist': PlatformInfo(
        id='atarist',
        display_name='Atari ST',
        description='Atari ST MFM formats',
        default_encoding='mfm',
        default_bus_type=2,
        primary_disk_size='3.5"',
        manufacturer='Atari',
        era='1985-1993',
    ),
    'atari': PlatformInfo(
        id='atari',
        display_name='Atari 8-bit',
        description='Atari 8-bit computer formats',
        default_encoding='mfm',
        default_bus_type=2,
        primary_disk_size='5.25"',
        manufacturer='Atari',
        era='1979-1992',
    ),
    'acorn': PlatformInfo(
        id='acorn',
        display_name='Acorn/BBC Micro',
        description='Acorn computers including BBC Micro',
        default_encoding='fm',
        default_bus_type=1,
        primary_disk_size='5.25"',
        manufacturer='Acorn',
        era='1981-1994',
    ),
    'zx': PlatformInfo(
        id='zx',
        display_name='ZX Spectrum',
        description='Sinclair ZX Spectrum disk interfaces',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='Sinclair/Various',
        era='1982-1992',
    ),
    'msx': PlatformInfo(
        id='msx',
        display_name='MSX',
        description='MSX computer formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='Various',
        era='1983-1995',
    ),
    'coco': PlatformInfo(
        id='coco',
        display_name='TRS-80 CoCo',
        description='Tandy Color Computer formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='5.25"',
        manufacturer='Tandy/Radio Shack',
        era='1980-1991',
    ),
    'dragon': PlatformInfo(
        id='dragon',
        display_name='Dragon 32/64',
        description='Dragon Data computer formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='5.25"',
        manufacturer='Dragon Data',
        era='1982-1984',
    ),
    'hp': PlatformInfo(
        id='hp',
        display_name='HP',
        description='Hewlett-Packard MMFM formats',
        default_encoding='mmfm',
        default_bus_type=1,
        primary_disk_size='5.25"',
        manufacturer='Hewlett-Packard',
        era='1980s',
    ),
    'dec': PlatformInfo(
        id='dec',
        display_name='DEC',
        description='Digital Equipment Corporation formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='8"',
        manufacturer='DEC',
        era='1970s-1980s',
    ),
    'pc98': PlatformInfo(
        id='pc98',
        display_name='NEC PC-98',
        description='NEC PC-98 Japanese computer formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='NEC',
        era='1982-2000',
    ),
    'micropolis': PlatformInfo(
        id='micropolis',
        display_name='Micropolis',
        description='Micropolis hard-sectored formats',
        default_encoding='micropolis',
        default_bus_type=1,
        primary_disk_size='5.25"',
        manufacturer='Micropolis',
        era='1970s-1980s',
    ),
    'northstar': PlatformInfo(
        id='northstar',
        display_name='North Star',
        description='North Star hard-sectored formats',
        default_encoding='northstar',
        default_bus_type=1,
        primary_disk_size='5.25"',
        manufacturer='North Star',
        era='1977-1984',
    ),
    'sega': PlatformInfo(
        id='sega',
        display_name='Sega',
        description='Sega SF-7000 format',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='Sega',
        era='1983-1985',
    ),
    'ensoniq': PlatformInfo(
        id='ensoniq',
        display_name='Ensoniq',
        description='Ensoniq sampler formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='Ensoniq',
        era='1984-1998',
    ),
    'akai': PlatformInfo(
        id='akai',
        display_name='Akai',
        description='Akai sampler formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='Akai',
        era='1986-2000s',
    ),
    'thomson': PlatformInfo(
        id='thomson',
        display_name='Thomson',
        description='Thomson TO/MO computer formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='Thomson',
        era='1982-1989',
    ),
    'olivetti': PlatformInfo(
        id='olivetti',
        display_name='Olivetti',
        description='Olivetti computer formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='5.25"',
        manufacturer='Olivetti',
        era='1980s',
    ),
    'gem': PlatformInfo(
        id='gem',
        display_name='GEM',
        description='General Electric formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='General Electric',
        era='1980s',
    ),
    'occ1': PlatformInfo(
        id='occ1',
        display_name='OCC',
        description='OCC format',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='OCC',
        era='1980s',
    ),
    'sci': PlatformInfo(
        id='sci',
        display_name='SCI',
        description='Sequential Circuits Prophet formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='Sequential Circuits',
        era='1980s',
    ),
    'tsc': PlatformInfo(
        id='tsc',
        display_name='TSC',
        description='Technical Systems Consultants FLEX formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='5.25"',
        manufacturer='TSC',
        era='1970s-1980s',
    ),
    'epson': PlatformInfo(
        id='epson',
        display_name='Epson',
        description='Epson QX-10 formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='5.25"',
        manufacturer='Epson',
        era='1983-1985',
    ),
    'mm1': PlatformInfo(
        id='mm1',
        display_name='MM/1',
        description='MM/1 OS-9 formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='Various',
        era='1990s',
    ),
    'raw': PlatformInfo(
        id='raw',
        display_name='Raw',
        description='Raw flux data formats',
        default_encoding='mfm',
        default_bus_type=1,
        primary_disk_size='3.5"',
        manufacturer='N/A',
        era='N/A',
    ),
}


# =============================================================================
# Format Info Dataclass
# =============================================================================

@dataclass
class FormatInfo:
    """Information about a specific disk format."""
    gw_format: str             # Greaseweazle format string (e.g., 'ibm.1440')
    platform: str              # Platform ID (e.g., 'ibm')
    format_name: str           # Format name within platform (e.g., '1440')
    display_name: str          # Human-readable name
    description: str           # Brief description
    disk_size: str             # Physical disk size
    cylinders: int             # Number of cylinders
    heads: int                 # Number of heads
    sectors_per_track: int     # Sectors per track
    bytes_per_sector: int      # Bytes per sector
    encoding: str              # Encoding type
    capacity_kb: int           # Capacity in KB
    data_rate_kbps: int        # Data rate in kbps
    rpm: int                   # RPM
    bit_cell_us: float         # Bit cell time in microseconds


# =============================================================================
# Greaseweazle Format Registry
# =============================================================================

class GWFormatRegistry:
    """
    Registry that discovers and provides access to ALL Greaseweazle disk formats.

    This class dynamically discovers all formats supported by the installed
    Greaseweazle library, organizes them by platform, and provides methods
    to query and create sessions from them.

    The registry is designed to be a singleton for efficiency, as format
    discovery only needs to happen once.

    Example:
        >>> registry = GWFormatRegistry()
        >>> platforms = registry.get_all_platforms()
        >>> print(len(platforms))
        29
        >>> ibm_formats = registry.get_formats_for_platform('ibm')
        >>> print([f['gw_format'] for f in ibm_formats])
        ['ibm.160', 'ibm.180', 'ibm.320', ...]
    """

    _instance: Optional['GWFormatRegistry'] = None
    _initialized: bool = False

    def __new__(cls) -> 'GWFormatRegistry':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the format registry."""
        if self._initialized:
            return

        self._initialized = True

        # Storage
        self._platforms: Dict[str, PlatformInfo] = {}
        self._formats: Dict[str, FormatInfo] = {}
        self._formats_by_platform: Dict[str, List[str]] = {}

        # Discover all formats
        self._discover_all_formats()

        logger.info(f"Format registry initialized: {len(self._platforms)} platforms, "
                    f"{len(self._formats)} formats")

    @classmethod
    def instance(cls) -> 'GWFormatRegistry':
        """Get the singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None
        cls._initialized = False

    # =========================================================================
    # Format Discovery
    # =========================================================================

    def _discover_all_formats(self) -> None:
        """
        Discover all formats from the Greaseweazle library.

        This method queries the Greaseweazle library to get all available
        formats and extracts their properties.
        """
        try:
            from greaseweazle.codec.codec import print_formats, get_diskdef
        except ImportError:
            logger.error("Greaseweazle library not installed")
            return

        # Get all format names
        format_list_str = print_formats()
        format_names = format_list_str.split()

        logger.debug(f"Discovered {len(format_names)} formats from Greaseweazle")

        # Process each format
        skipped_formats = []
        for gw_format in format_names:
            try:
                self._process_format(gw_format, get_diskdef)
            except Exception as e:
                # Log at debug level - these are usually Greaseweazle diskdef config issues
                # that we can't fix (e.g., zx.rocky.ss40 has "cylinder out of range")
                logger.debug(f"Skipping format {gw_format}: {e}")
                skipped_formats.append(gw_format)

        if skipped_formats:
            logger.debug(f"Skipped {len(skipped_formats)} formats due to diskdef errors: {skipped_formats}")

    def _process_format(self, gw_format: str, get_diskdef) -> None:
        """
        Process a single format and add it to the registry.

        Args:
            gw_format: Greaseweazle format string
            get_diskdef: Function to get disk definition
        """
        # Parse platform and format name
        if '.' in gw_format:
            parts = gw_format.split('.', 1)
            platform = parts[0]
            format_name = parts[1]
        else:
            platform = gw_format
            format_name = gw_format

        # Ensure platform exists
        if platform not in self._platforms:
            self._add_platform(platform)

        if platform not in self._formats_by_platform:
            self._formats_by_platform[platform] = []

        # Get disk definition
        diskdef = get_diskdef(gw_format)
        if diskdef is None:
            logger.debug(f"Could not get diskdef for {gw_format}")
            return

        # Create a track to get detailed info
        try:
            track = diskdef.mk_track(0, 0)
        except Exception as e:
            logger.debug(f"Could not create track for {gw_format}: {e}")
            return

        # Extract properties
        cylinders = diskdef.cyls
        heads = diskdef.heads

        # Get track properties with fallbacks
        clock_us = track.clock * 1e6 if hasattr(track, 'clock') else 2.0
        time_per_rev = getattr(track, 'time_per_rev', 0.2)
        rpm = int(60 / time_per_rev) if time_per_rev > 0 else 300
        nsec = getattr(track, 'nsec', 18)

        # Determine encoding
        track_type = type(track).__name__
        mode = getattr(track, 'mode', track_type)
        # Convert mode to string if it's an Enum
        mode_str = str(mode) if mode is not None else track_type
        encoding = self._determine_encoding(mode_str, track_type, platform)

        # Determine bytes per sector
        bytes_per_sector = self._determine_bytes_per_sector(track, platform)

        # Calculate data rate
        data_rate_kbps = int(500 / clock_us) if clock_us > 0 else 500

        # Calculate capacity
        capacity_kb = (cylinders * heads * nsec * bytes_per_sector) // 1024

        # Determine disk size
        disk_size = self._determine_disk_size(platform, format_name, cylinders)

        # Generate display name
        display_name = self._generate_display_name(platform, format_name,
                                                    capacity_kb, encoding)

        # Create format info
        format_info = FormatInfo(
            gw_format=gw_format,
            platform=platform,
            format_name=format_name,
            display_name=display_name,
            description=f"{display_name} format",
            disk_size=disk_size,
            cylinders=cylinders,
            heads=heads,
            sectors_per_track=nsec,
            bytes_per_sector=bytes_per_sector,
            encoding=encoding,
            capacity_kb=capacity_kb,
            data_rate_kbps=data_rate_kbps,
            rpm=rpm,
            bit_cell_us=clock_us,
        )

        # Store format info
        self._formats[gw_format] = format_info
        self._formats_by_platform[platform].append(gw_format)

    def _add_platform(self, platform: str) -> None:
        """Add a platform to the registry."""
        if platform in PLATFORM_METADATA:
            self._platforms[platform] = PLATFORM_METADATA[platform]
        else:
            # Create a generic platform info for unknown platforms
            self._platforms[platform] = PlatformInfo(
                id=platform,
                display_name=platform.title(),
                description=f'{platform.title()} disk formats',
                default_encoding='mfm',
                default_bus_type=1,
                primary_disk_size='3.5"',
                manufacturer='Unknown',
                era='Unknown',
            )

    def _determine_encoding(self, mode: str, track_type: str, platform: str) -> str:
        """Determine encoding type from mode string and track type."""
        mode_lower = mode.lower()
        track_lower = track_type.lower()

        if 'fm' in mode_lower and 'mfm' not in mode_lower and 'mmfm' not in mode_lower:
            return 'fm'
        elif 'mmfm' in mode_lower or platform == 'hp':
            return 'mmfm'
        elif 'mfm' in mode_lower or 'mfm' in track_lower:
            return 'mfm'
        elif 'amiga' in track_lower:
            return 'amiga'
        elif 'macgcr' in track_lower or platform == 'mac':
            return 'mac_gcr'
        elif 'c64gcr' in track_lower or platform == 'commodore':
            return 'c64_gcr'
        elif 'apple' in platform or 'apple' in track_lower:
            return 'apple_gcr'
        elif 'micropolis' in track_lower or platform == 'micropolis':
            return 'micropolis'
        elif 'northstar' in track_lower or platform == 'northstar':
            return 'northstar'
        elif 'gcr' in mode_lower or 'gcr' in track_lower:
            return 'gcr'
        else:
            return 'mfm'

    def _determine_bytes_per_sector(self, track: Any, platform: str) -> int:
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
            return 256
        else:
            return 512

    def _determine_disk_size(self, platform: str, format_name: str, cylinders: int) -> str:
        """Determine physical disk size from format info."""
        format_lower = format_name.lower()

        # 8" formats
        if 'rx' in format_lower or platform == 'dec':
            return '8"'

        # 5.25" formats
        five_quarter_platforms = ('apple2', 'commodore', 'atari', 'coco', 'dragon',
                                  'northstar', 'micropolis', 'olivetti', 'tsc')
        five_quarter_keywords = ('1200', '360', '1541', '1571', '40t', '40ds', '40ss',
                                '48tpi', 'booter')

        if platform in five_quarter_platforms:
            return '5.25"'
        if any(kw in format_lower for kw in five_quarter_keywords):
            return '5.25"'
        if cylinders <= 42 and platform not in ('zx',):
            return '5.25"'

        # Default to 3.5"
        return '3.5"'

    def _generate_display_name(self, platform: str, format_name: str,
                                capacity_kb: int, encoding: str) -> str:
        """Generate a human-readable display name for a format."""
        # Get platform display name
        platform_info = self._platforms.get(platform)
        platform_display = platform_info.display_name if platform_info else platform.title()

        # Format capacity
        if capacity_kb >= 1024:
            capacity_str = f"{capacity_kb / 1024:.2f}MB".rstrip('0').rstrip('.')
        else:
            capacity_str = f"{capacity_kb}KB"

        # Clean up format name for display
        format_display = format_name.replace('.', ' ').replace('_', ' ').title()

        return f"{platform_display} {format_display} ({capacity_str})"

    # =========================================================================
    # Public Query Methods
    # =========================================================================

    def get_all_platforms(self) -> List[Dict[str, Any]]:
        """
        Get all available platforms with their metadata.

        Returns:
            List of platform dictionaries with id, display_name, description,
            format_count, etc.

        Example:
            >>> registry = GWFormatRegistry()
            >>> platforms = registry.get_all_platforms()
            >>> for p in platforms[:3]:
            ...     print(f"{p['display_name']}: {p['format_count']} formats")
            IBM PC: 12 formats
            Amiga: 2 formats
            Macintosh: 2 formats
        """
        platforms = []
        for platform_id, info in sorted(self._platforms.items(),
                                         key=lambda x: x[1].display_name):
            format_count = len(self._formats_by_platform.get(platform_id, []))
            platforms.append({
                'id': info.id,
                'display_name': info.display_name,
                'description': info.description,
                'default_encoding': info.default_encoding,
                'default_bus_type': info.default_bus_type,
                'primary_disk_size': info.primary_disk_size,
                'manufacturer': info.manufacturer,
                'era': info.era,
                'format_count': format_count,
            })
        return platforms

    def get_formats_for_platform(self, platform: str) -> List[Dict[str, Any]]:
        """
        Get all formats for a specific platform.

        Args:
            platform: Platform ID (e.g., 'ibm', 'amiga')

        Returns:
            List of format dictionaries with gw_format, display_name, etc.

        Example:
            >>> registry = GWFormatRegistry()
            >>> ibm_formats = registry.get_formats_for_platform('ibm')
            >>> for f in ibm_formats[:3]:
            ...     print(f"{f['gw_format']}: {f['capacity_kb']}KB")
            ibm.160: 160KB
            ibm.180: 180KB
            ibm.320: 320KB
        """
        format_names = self._formats_by_platform.get(platform, [])
        formats = []
        for gw_format in sorted(format_names):
            info = self._formats.get(gw_format)
            if info:
                formats.append({
                    'gw_format': info.gw_format,
                    'platform': info.platform,
                    'format_name': info.format_name,
                    'display_name': info.display_name,
                    'description': info.description,
                    'disk_size': info.disk_size,
                    'cylinders': info.cylinders,
                    'heads': info.heads,
                    'sectors_per_track': info.sectors_per_track,
                    'bytes_per_sector': info.bytes_per_sector,
                    'encoding': info.encoding,
                    'capacity_kb': info.capacity_kb,
                    'data_rate_kbps': info.data_rate_kbps,
                    'rpm': info.rpm,
                    'bit_cell_us': info.bit_cell_us,
                })
        return formats

    def get_formats_by_disk_size(self, disk_size: str) -> List[Dict[str, Any]]:
        """
        Get all formats for a specific disk size.

        Args:
            disk_size: Disk size ('3.5"', '5.25"', '8"')

        Returns:
            List of format dictionaries

        Example:
            >>> registry = GWFormatRegistry()
            >>> formats_35 = registry.get_formats_by_disk_size('3.5"')
            >>> print(len(formats_35))
            50
        """
        formats = []
        for gw_format, info in self._formats.items():
            if info.disk_size == disk_size:
                formats.append({
                    'gw_format': info.gw_format,
                    'platform': info.platform,
                    'format_name': info.format_name,
                    'display_name': info.display_name,
                    'description': info.description,
                    'disk_size': info.disk_size,
                    'cylinders': info.cylinders,
                    'heads': info.heads,
                    'sectors_per_track': info.sectors_per_track,
                    'bytes_per_sector': info.bytes_per_sector,
                    'encoding': info.encoding,
                    'capacity_kb': info.capacity_kb,
                    'data_rate_kbps': info.data_rate_kbps,
                    'rpm': info.rpm,
                    'bit_cell_us': info.bit_cell_us,
                })
        return sorted(formats, key=lambda x: (x['platform'], x['capacity_kb']))

    def get_format_info(self, gw_format: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific format.

        Args:
            gw_format: Greaseweazle format string (e.g., 'ibm.1440')

        Returns:
            Format dictionary or None if not found

        Example:
            >>> registry = GWFormatRegistry()
            >>> info = registry.get_format_info('ibm.1440')
            >>> print(info['capacity_kb'])
            1440
        """
        info = self._formats.get(gw_format)
        if info is None:
            return None

        return {
            'gw_format': info.gw_format,
            'platform': info.platform,
            'format_name': info.format_name,
            'display_name': info.display_name,
            'description': info.description,
            'disk_size': info.disk_size,
            'cylinders': info.cylinders,
            'heads': info.heads,
            'sectors_per_track': info.sectors_per_track,
            'bytes_per_sector': info.bytes_per_sector,
            'encoding': info.encoding,
            'capacity_kb': info.capacity_kb,
            'data_rate_kbps': info.data_rate_kbps,
            'rpm': info.rpm,
            'bit_cell_us': info.bit_cell_us,
        }

    def get_diskdef(self, gw_format: str) -> Optional[Any]:
        """
        Get the Greaseweazle DiskDef object for a format.

        Args:
            gw_format: Greaseweazle format string

        Returns:
            DiskDef object or None if not found

        Example:
            >>> registry = GWFormatRegistry()
            >>> diskdef = registry.get_diskdef('ibm.1440')
            >>> print(diskdef.cyls, diskdef.heads)
            80 2
        """
        try:
            from greaseweazle.codec.codec import get_diskdef
            return get_diskdef(gw_format)
        except ImportError:
            logger.error("Greaseweazle library not installed")
            return None
        except Exception as e:
            logger.error(f"Error getting diskdef for {gw_format}: {e}")
            return None

    def session_from_format(self, gw_format: str,
                            name: Optional[str] = None) -> 'DiskSession':
        """
        Create a DiskSession from a Greaseweazle format string.

        Args:
            gw_format: Greaseweazle format string
            name: Optional custom name for the session

        Returns:
            New DiskSession instance

        Raises:
            ValueError: If format is not found

        Example:
            >>> registry = GWFormatRegistry()
            >>> session = registry.session_from_format('ibm.1440')
            >>> print(session.cylinders, session.heads)
            80 2
        """
        # Import here to avoid circular imports
        from floppy_formatter.core.session import DiskSession

        # Use format info if available for faster creation
        info = self._formats.get(gw_format)
        if info:
            return DiskSession(
                name=name or info.display_name,
                platform=info.platform,
                format_name=info.format_name,
                gw_format=info.gw_format,
                disk_size=info.disk_size,
                cylinders=info.cylinders,
                heads=info.heads,
                sectors_per_track=info.sectors_per_track,
                bytes_per_sector=info.bytes_per_sector,
                encoding=info.encoding,
                data_rate_kbps=info.data_rate_kbps,
                rpm=info.rpm,
                bit_cell_us=info.bit_cell_us,
                bus_type=self._get_bus_type_for_platform(info.platform),
            )

        # Fall back to creating from Greaseweazle directly
        return DiskSession.from_gw_format(gw_format, name)

    def _get_bus_type_for_platform(self, platform: str) -> int:
        """Get the bus type for a platform."""
        info = self._platforms.get(platform)
        if info:
            return info.default_bus_type
        return 1  # Default to IBMPC

    # =========================================================================
    # Platform Query Methods
    # =========================================================================

    def get_platform_info(self, platform: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific platform.

        Args:
            platform: Platform ID

        Returns:
            Platform dictionary or None
        """
        info = self._platforms.get(platform)
        if info is None:
            return None

        return {
            'id': info.id,
            'display_name': info.display_name,
            'description': info.description,
            'default_encoding': info.default_encoding,
            'default_bus_type': info.default_bus_type,
            'primary_disk_size': info.primary_disk_size,
            'manufacturer': info.manufacturer,
            'era': info.era,
            'format_count': len(self._formats_by_platform.get(platform, [])),
        }

    def search_formats(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for formats by name or description.

        Args:
            query: Search query string

        Returns:
            List of matching format dictionaries

        Example:
            >>> registry = GWFormatRegistry()
            >>> results = registry.search_formats('1440')
            >>> print(len(results))
            1
        """
        query_lower = query.lower()
        results = []

        for gw_format, info in self._formats.items():
            if (query_lower in gw_format.lower() or
                query_lower in info.display_name.lower() or
                query_lower in info.description.lower()):
                results.append({
                    'gw_format': info.gw_format,
                    'platform': info.platform,
                    'format_name': info.format_name,
                    'display_name': info.display_name,
                    'description': info.description,
                    'disk_size': info.disk_size,
                    'capacity_kb': info.capacity_kb,
                })

        return sorted(results, key=lambda x: x['gw_format'])

    # =========================================================================
    # Statistics
    # =========================================================================

    @property
    def platform_count(self) -> int:
        """Get the number of platforms."""
        return len(self._platforms)

    @property
    def format_count(self) -> int:
        """Get the total number of formats."""
        return len(self._formats)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the format registry.

        Returns:
            Dictionary with registry statistics
        """
        disk_sizes = {}
        encodings = {}

        for info in self._formats.values():
            # Count by disk size
            disk_sizes[info.disk_size] = disk_sizes.get(info.disk_size, 0) + 1
            # Count by encoding
            encodings[info.encoding] = encodings.get(info.encoding, 0) + 1

        return {
            'platform_count': len(self._platforms),
            'format_count': len(self._formats),
            'disk_sizes': disk_sizes,
            'encodings': encodings,
            'platforms': list(self._platforms.keys()),
        }


# =============================================================================
# Module-Level Convenience Functions
# =============================================================================

def get_format_registry() -> GWFormatRegistry:
    """
    Get the global format registry instance.

    Returns:
        The singleton GWFormatRegistry instance
    """
    return GWFormatRegistry.instance()


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'GWFormatRegistry',
    'PlatformInfo',
    'FormatInfo',
    'PLATFORM_METADATA',
    'get_format_registry',
]
