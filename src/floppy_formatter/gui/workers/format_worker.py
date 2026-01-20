"""
Format worker for Greaseweazle floppy disk operations.

Provides track-at-a-time formatting with bulk erase, pattern writes,
and verification. Supports multiple format types for different use cases.

Part of Phase 9: Workers & Background Processing
Updated Phase 3: Session-aware formatting with codec adapter support
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal

from floppy_formatter.gui.workers.base_worker import GreaseweazleWorker

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice, SectorData
    from floppy_formatter.core.geometry import DiskGeometry
    from floppy_formatter.core.session import DiskSession

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def decode_flux_data(flux_data):
    """
    Decode flux data to sectors using the same decoder priority as restore worker.

    This ensures consistency between format verification, restore, and scanning -
    all use the same decoder order to avoid false positives/negatives.

    Args:
        flux_data: FluxData from track read

    Returns:
        List of SectorData objects
    """
    # Use Greaseweazle-compatible decoder first (same as restore_worker)
    try:
        from floppy_formatter.hardware.gw_mfm_codec import decode_flux_to_sectors_gw
        sectors = decode_flux_to_sectors_gw(flux_data)
        if sectors:
            logger.debug("GW decoder returned %d sectors", len(sectors))
            return sectors
        logger.debug("GW decoder returned 0 sectors, trying PLL decoder")
    except ImportError:
        logger.debug("GW decoder not available")
    except Exception as e:
        logger.warning("GW decoder failed: %s", e)

    # Try PLL decoder as fallback
    try:
        from floppy_formatter.hardware.pll_decoder import decode_flux_with_pll
        sectors = decode_flux_with_pll(flux_data)
        if sectors:
            logger.debug("PLL decoder returned %d sectors", len(sectors))
            return sectors
    except ImportError:
        logger.debug("PLL decoder not available")
    except Exception as e:
        logger.warning("PLL decoder failed: %s", e)

    # Fall back to simple decoder
    from floppy_formatter.hardware.mfm_codec import decode_flux_to_sectors
    sectors = decode_flux_to_sectors(flux_data)
    logger.debug("Simple decoder returned %d sectors", len(sectors))
    return sectors


# =============================================================================
# Constants
# =============================================================================

# Standard fill patterns
PATTERN_ZERO = 0x00
PATTERN_ONE = 0xFF
PATTERN_E5 = 0xE5
PATTERN_AA = 0xAA
PATTERN_55 = 0x55

# Secure erase patterns (multiple overwrites)
SECURE_ERASE_PATTERNS = [PATTERN_ZERO, PATTERN_ONE, PATTERN_AA, PATTERN_55, PATTERN_ZERO]


# =============================================================================
# Enums
# =============================================================================

class FormatType(Enum):
    """
    Format type determining the formatting approach.

    STANDARD: Normal format with specified fill pattern
    LOW_LEVEL_REFRESH: Degauss + multiple pattern writes to refresh media
    SECURE_ERASE: Multiple overwrites with different patterns
    """
    STANDARD = auto()
    LOW_LEVEL_REFRESH = auto()
    SECURE_ERASE = auto()


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TrackFormatResult:
    """
    Result of formatting a single track.

    Attributes:
        cylinder: Cylinder number (0-79)
        head: Head number (0-1)
        format_success: True if format succeeded
        verify_success: True if verification passed (None if not verified)
        error_message: Error description if failed
        format_time_ms: Time to format this track in milliseconds
    """
    cylinder: int
    head: int
    format_success: bool
    verify_success: Optional[bool] = None
    error_message: Optional[str] = None
    format_time_ms: float = 0.0

    @property
    def track_number(self) -> int:
        """Linear track number (0-159)."""
        return self.cylinder * 2 + self.head

    @property
    def is_perfect(self) -> bool:
        """True if format and verify (if done) both succeeded."""
        if self.verify_success is None:
            return self.format_success
        return self.format_success and self.verify_success


@dataclass
class FormatResult:
    """
    Complete format result containing all track data.

    Attributes:
        success: True if all operations completed successfully
        total_tracks: Total number of tracks formatted
        tracks_formatted: Number of tracks successfully formatted
        tracks_verified: Number of tracks successfully verified
        tracks_failed: Number of tracks that failed
        bad_sectors: List of bad sector numbers found during verify
        track_results: Per-track results
        format_duration: Total format time in seconds
        format_type: Type of format performed
        fill_pattern: Pattern used for formatting
        verified: Whether verification was performed
        timestamp: When format was performed
    """
    success: bool
    total_tracks: int
    tracks_formatted: int = 0
    tracks_verified: int = 0
    tracks_failed: int = 0
    bad_sectors: List[int] = field(default_factory=list)
    track_results: List[TrackFormatResult] = field(default_factory=list)
    format_duration: float = 0.0
    format_type: FormatType = FormatType.STANDARD
    fill_pattern: int = PATTERN_E5
    verified: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def success_rate(self) -> float:
        """Percentage of tracks successfully formatted."""
        if self.total_tracks == 0:
            return 0.0
        return (self.tracks_formatted / self.total_tracks) * 100.0


# =============================================================================
# Format Worker
# =============================================================================

class FormatWorker(GreaseweazleWorker):
    """
    Worker for formatting floppy disks.

    Performs bulk erase followed by track writing using Greaseweazle.
    Supports multiple format types and optional verification.

    Features:
    - Bulk track erase using DC erase
    - Pattern fill with configurable byte value
    - Optional read-back verification
    - Multiple format types (standard, refresh, secure)
    - Real-time progress reporting
    - Session-aware encoding for non-IBM formats (Phase 3)

    Session Integration (Phase 3):
        When a DiskSession is provided, the worker uses the session's
        CodecAdapter for encoding, enabling proper formatting of ALL
        Greaseweazle-supported formats (IBM, Amiga, Mac, C64, etc.).
        Geometry is derived from the session if not explicitly provided.

    Signals:
        track_formatted(int, int, bool): Per track (cyl, head, success)
        track_verified(int, int, bool): Per track verification (cyl, head, verified_ok)
        format_complete(FormatResult): Final complete format result

    Example:
        # Session-aware formatting (preferred for Phase 3+)
        worker = FormatWorker(device, session=session, fill_pattern=0xE5)

        # Legacy: explicit geometry
        worker = FormatWorker(device, geometry=geometry, verify=True)
    """

    # Signals specific to formatting
    track_formatted = pyqtSignal(int, int, bool)    # cyl, head, success
    track_verified = pyqtSignal(int, int, bool)     # cyl, head, verified_ok
    format_complete = pyqtSignal(object)            # FormatResult

    def __init__(
        self,
        device: 'GreaseweazleDevice',
        geometry: Optional['DiskGeometry'] = None,
        fill_pattern: int = PATTERN_E5,
        verify: bool = True,
        format_type: FormatType = FormatType.STANDARD,
        session: Optional['DiskSession'] = None,
    ):
        """
        Initialize format worker.

        Args:
            device: Connected GreaseweazleDevice instance
            geometry: Disk geometry information. If None and session is provided,
                     geometry is derived from session.to_geometry()
            fill_pattern: Byte value to fill sectors with (default 0xE5)
            verify: Whether to verify after formatting
            format_type: Type of format operation
            session: Optional DiskSession for session-aware operations.
                    When provided, enables proper encoding of non-IBM formats.
        """
        super().__init__(device, session)

        # Get geometry from session if not explicitly provided
        if geometry is not None:
            self._geometry = geometry
        elif session is not None:
            self._geometry = session.to_geometry()
        else:
            raise ValueError("Either geometry or session must be provided")

        self._fill_pattern = fill_pattern
        self._verify = verify
        self._format_type = format_type

        logger.info(
            "FormatWorker initialized: type=%s, pattern=0x%02X, verify=%s, session=%s",
            format_type.name, fill_pattern, verify,
            session.gw_format if session else "None"
        )

    def run(self) -> None:
        """
        Execute the format operation.

        Formats all tracks according to the selected format type,
        optionally verifying each track after writing.
        """
        start_time = time.time()

        # Initialize result
        total_tracks = self._geometry.cylinders * self._geometry.heads
        result = FormatResult(
            success=True,
            total_tracks=total_tracks,
            format_type=self._format_type,
            fill_pattern=self._fill_pattern,
            verified=self._verify,
        )

        # Ensure drive is selected and motor is on
        if self._device.selected_drive is None:
            raise RuntimeError(
                "No drive selected. Please click 'Calibrate' in the Drive Control "
                "panel to initialize the drive before formatting."
            )
        if not self._device.is_motor_on():
            self._device.motor_on()

        # Determine patterns to use based on format type
        patterns = self._get_format_patterns()

        logger.info(
            "Formatting %d tracks, type=%s, %d pattern passes",
            total_tracks, self._format_type.name, len(patterns)
        )

        # Process each track
        track_count = 0
        for cylinder in range(self._geometry.cylinders):
            for head in range(self._geometry.heads):
                # Check for cancellation
                if self._cancelled:
                    logger.info("Format cancelled at track %d/%d", cylinder, head)
                    result.success = False
                    break

                # Format the track
                track_result = self._format_track(
                    cylinder, head, patterns
                )

                # Verify if requested
                if self._verify and track_result.format_success:
                    verify_ok = self._verify_track(cylinder, head)
                    track_result.verify_success = verify_ok
                    self.track_verified.emit(cylinder, head, verify_ok)

                    if verify_ok:
                        result.tracks_verified += 1
                    else:
                        # Find bad sectors from verification
                        bad = self._get_bad_sectors_for_track(cylinder, head)
                        result.bad_sectors.extend(bad)

                result.track_results.append(track_result)

                if track_result.format_success:
                    result.tracks_formatted += 1
                else:
                    result.tracks_failed += 1
                    result.success = False

                self.track_formatted.emit(
                    cylinder, head, track_result.format_success
                )

                # Update progress
                track_count += 1
                progress = int((track_count / total_tracks) * 100)
                self.progress.emit(progress)

            if self._cancelled:
                break

        # Calculate duration
        result.format_duration = time.time() - start_time

        # Emit final result
        logger.info(
            "Format complete: %d/%d tracks OK, %d bad sectors, %.1fs",
            result.tracks_formatted, result.total_tracks,
            len(result.bad_sectors), result.format_duration
        )
        self.format_complete.emit(result)
        self.finished.emit()

    def _get_format_patterns(self) -> List[int]:
        """
        Get list of fill patterns based on format type.

        Returns:
            List of byte patterns to write
        """
        if self._format_type == FormatType.STANDARD:
            return [self._fill_pattern]

        elif self._format_type == FormatType.LOW_LEVEL_REFRESH:
            # Multiple patterns to refresh magnetic domains
            return [
                PATTERN_ZERO, PATTERN_ONE, PATTERN_AA,
                PATTERN_55, self._fill_pattern
            ]

        elif self._format_type == FormatType.SECURE_ERASE:
            return SECURE_ERASE_PATTERNS

        else:
            return [self._fill_pattern]

    def _format_track(
        self,
        cylinder: int,
        head: int,
        patterns: List[int]
    ) -> TrackFormatResult:
        """
        Format a single track with the specified patterns.

        Uses the session's codec adapter for encoding when available (Phase 3),
        otherwise falls back to the default MFM encoder.

        Args:
            cylinder: Cylinder number
            head: Head number
            patterns: List of fill patterns to write

        Returns:
            TrackFormatResult with format data
        """
        from floppy_formatter.hardware import erase_track_flux, write_track_flux
        from floppy_formatter.hardware.mfm_codec import encode_sectors_to_flux

        track_start = time.time()

        # Seek to track
        self._device.seek(cylinder, head)

        result = TrackFormatResult(cylinder=cylinder, head=head, format_success=True)

        try:
            # Step 1: Bulk erase the track (DC erase)
            erase_track_flux(self._device, cylinder, head)

            # Step 2: Write each pattern
            for pattern in patterns:
                # Check for cancellation between patterns
                if self._cancelled:
                    result.format_success = False
                    result.error_message = "Cancelled"
                    break

                # Create sector data with fill pattern
                sector_data = self._create_sector_data(
                    cylinder, head, pattern
                )

                # Encode to flux - use session codec adapter if available (Phase 3)
                if self._codec_adapter is not None:
                    # Session-aware encoding for any Greaseweazle format
                    flux = self._codec_adapter.encode_track(sector_data, cylinder, head)
                    logger.debug(
                        "Track C%d:H%d: codec adapter encoded %d sectors",
                        cylinder, head, len(sector_data)
                    )
                else:
                    # Fall back to default MFM encoder (IBM formats only)
                    # NOTE: Argument order is (cylinder, head, sectors)
                    flux = encode_sectors_to_flux(cylinder, head, sector_data)

                # Write to disk
                write_track_flux(self._device, cylinder, head, flux)

            result.format_time_ms = (time.time() - track_start) * 1000

            logger.debug(
                "Track C%d:H%d formatted in %.1f ms",
                cylinder, head, result.format_time_ms
            )

        except Exception as e:
            result.format_success = False
            result.error_message = str(e)
            logger.warning(
                "Track C%d:H%d format failed: %s",
                cylinder, head, e
            )

        return result

    def _verify_track(self, cylinder: int, head: int) -> bool:
        """
        Verify a track by reading back and checking data.

        Uses the session's codec adapter for decoding when available (Phase 3),
        otherwise falls back to the default decoder chain.

        Args:
            cylinder: Cylinder number
            head: Head number

        Returns:
            True if verification passed
        """
        from floppy_formatter.hardware import read_track_flux

        try:
            # Seek and read
            self._device.seek(cylinder, head)
            flux = read_track_flux(self._device, cylinder, head, revolutions=1.2)

            # Decode sectors - use session codec adapter if available (Phase 3)
            if self._codec_adapter is not None:
                sectors = self._codec_adapter.decode_track(flux, cylinder, head)
            else:
                sectors = decode_flux_data(flux)

            # Get sectors per track - use codec adapter for variable formats (Phase 3)
            if self._codec_adapter is not None:
                sectors_per_track = self._codec_adapter.get_sectors_for_track(cylinder, head)
            else:
                sectors_per_track = self._geometry.sectors_per_track

            # Deduplicate by sector number, keep best result
            best_sectors = {}
            for s in sectors:
                sector_num = s.sector
                if sector_num < 1 or sector_num > sectors_per_track:
                    continue
                if sector_num not in best_sectors:
                    best_sectors[sector_num] = s
                elif s.crc_valid and not best_sectors[sector_num].crc_valid:
                    best_sectors[sector_num] = s

            # Check how many unique sectors are good
            good_count = sum(
                1 for s in best_sectors.values()
                if s.data is not None and s.crc_valid
            )

            expected_sectors = sectors_per_track
            success_rate = good_count / expected_sectors if expected_sectors > 0 else 0.0

            # Allow small margin of error (1 retry might help)
            return success_rate >= 0.95

        except Exception as e:
            logger.warning("Verify failed for C%d:H%d: %s", cylinder, head, e)
            return False

    def _create_sector_data(
        self,
        cylinder: int,
        head: int,
        pattern: int
    ) -> List['SectorData']:
        """
        Create sector data for a track filled with pattern.

        Uses session parameters when available (Phase 3) to correctly
        handle variable sector counts and non-standard sector sizes.

        Args:
            cylinder: Cylinder number
            head: Head number
            pattern: Fill byte value

        Returns:
            List of SectorData objects for all sectors in the track
        """
        from floppy_formatter.hardware import SectorData, SectorStatus

        sector_data = []

        # Get format-specific parameters (Phase 3)
        if self._codec_adapter is not None:
            sectors_per_track = self._codec_adapter.get_sectors_for_track(cylinder, head)
            bytes_per_sector = self._session.bytes_per_sector if self._session else 512
        else:
            sectors_per_track = self._geometry.sectors_per_track
            bytes_per_sector = 512  # Standard sector size

        for sector_num in range(1, sectors_per_track + 1):
            data = bytes([pattern] * bytes_per_sector)
            # Create proper SectorData object as expected by codec adapter
            sector = SectorData(
                cylinder=cylinder,
                head=head,
                sector=sector_num,
                data=data,
                status=SectorStatus.GOOD,
                crc_valid=True,
                signal_quality=1.0
            )
            sector_data.append(sector)

        return sector_data

    def _get_bad_sectors_for_track(
        self,
        cylinder: int,
        head: int
    ) -> List[int]:
        """
        Get list of bad sector numbers for a track that failed verification.

        Uses the session's codec adapter for decoding when available (Phase 3),
        otherwise falls back to the default decoder chain.

        Args:
            cylinder: Cylinder number
            head: Head number

        Returns:
            List of linear sector numbers that are bad
        """
        from floppy_formatter.hardware import read_track_flux

        bad_sectors = []

        # Get sectors per track - use codec adapter for variable formats (Phase 3)
        if self._codec_adapter is not None:
            sectors_per_track = self._codec_adapter.get_sectors_for_track(cylinder, head)
        else:
            sectors_per_track = self._geometry.sectors_per_track
        base_sector = (cylinder * self._geometry.heads + head) * sectors_per_track

        try:
            flux = read_track_flux(self._device, cylinder, head, revolutions=1.2)

            # Decode sectors - use session codec adapter if available (Phase 3)
            if self._codec_adapter is not None:
                sectors = self._codec_adapter.decode_track(flux, cylinder, head)
            else:
                sectors = decode_flux_data(flux)

            # Deduplicate by sector number, keep best result
            best_sectors = {}
            for s in sectors:
                sector_num = s.sector
                if sector_num < 1 or sector_num > sectors_per_track:
                    continue
                if sector_num not in best_sectors:
                    best_sectors[sector_num] = s
                elif s.crc_valid and not best_sectors[sector_num].crc_valid:
                    best_sectors[sector_num] = s

            # Check all expected sectors
            for sector_num in range(1, sectors_per_track + 1):
                linear = base_sector + (sector_num - 1)
                if sector_num in best_sectors:
                    sector = best_sectors[sector_num]
                    if sector.data is None or not sector.crc_valid:
                        bad_sectors.append(linear)
                else:
                    # Sector not found at all
                    bad_sectors.append(linear)

        except Exception:
            # If we can't read at all, mark all sectors as bad
            for i in range(sectors_per_track):
                bad_sectors.append(base_sector + i)

        return bad_sectors

    def get_geometry(self) -> 'DiskGeometry':
        """Get the disk geometry being used."""
        return self._geometry

    def get_format_type(self) -> FormatType:
        """Get the format type."""
        return self._format_type


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'FormatWorker',
    'FormatType',
    'FormatResult',
    'TrackFormatResult',
    'PATTERN_ZERO',
    'PATTERN_ONE',
    'PATTERN_E5',
    'PATTERN_AA',
    'PATTERN_55',
]
