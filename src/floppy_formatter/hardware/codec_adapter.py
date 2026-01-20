"""
Unified codec adapter for Greaseweazle disk formats.

This module provides the CodecAdapter class which wraps Greaseweazle's codec
infrastructure to provide a unified interface for encoding and decoding
disk data across ALL supported formats: IBM MFM/FM, Amiga, Mac GCR, C64 GCR,
Apple II GCR, Atari, and many more.

The CodecAdapter is session-aware - it takes a DiskSession from Phase 1 and
uses the session's gw_format to select the appropriate Greaseweazle codec.

Part of Phase 2: Hardware Layer

Example:
    >>> from floppy_formatter.core.session import DiskSession
    >>> from floppy_formatter.hardware.codec_adapter import CodecAdapter
    >>>
    >>> session = DiskSession.from_gw_format('ibm.1440')
    >>> adapter = CodecAdapter(session)
    >>>
    >>> # Decode flux to sectors
    >>> sectors = adapter.decode_track(flux_data, cyl=0, head=0)
    >>>
    >>> # Encode sectors to flux
    >>> flux = adapter.encode_track(sectors, cyl=0, head=0)
"""

from __future__ import annotations

import logging
import sys
import io
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from floppy_formatter.core.session import DiskSession
    from floppy_formatter.hardware.flux_io import FluxData

# Greaseweazle imports
try:
    from greaseweazle.codec.codec import get_diskdef
    from greaseweazle.flux import Flux, WriteoutFlux
    GREASEWEAZLE_CODEC_AVAILABLE = True
except ImportError:
    GREASEWEAZLE_CODEC_AVAILABLE = False
    get_diskdef = None
    Flux = None
    WriteoutFlux = None

from floppy_formatter.hardware import SectorData, SectorStatus
from floppy_formatter.hardware.flux_io import FluxData

logger = logging.getLogger(__name__)


@contextmanager
def _suppress_stdout():
    """
    Context manager to suppress stdout.

    Used to suppress debug print statements from the Greaseweazle library
    (e.g., "Unknown mark xx" messages from ibm.py).
    """
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old_stdout


# =============================================================================
# Track Timing Data Class
# =============================================================================

@dataclass
class TrackTiming:
    """
    Timing parameters for a specific track.

    Different disk formats have different timing requirements. Some formats
    even have variable timing per track (e.g., Mac GCR varies by zone).

    Attributes:
        bit_cell_us: Bit cell time in microseconds
        data_rate_kbps: Data rate in kbit/s
        rpm: Expected disk rotation speed in RPM
        time_per_rev_ms: Expected time per revolution in milliseconds
        clock_ns: Clock period in nanoseconds
        sectors_per_track: Number of sectors on this track
        bytes_per_sector: Bytes per sector for this track
        gap_bytes: Number of gap bytes between sectors
        encoding: Encoding type (mfm, fm, gcr, etc.)
    """
    bit_cell_us: float = 2.0
    data_rate_kbps: int = 500
    rpm: int = 300
    time_per_rev_ms: float = 200.0
    clock_ns: float = 1000.0
    sectors_per_track: int = 18
    bytes_per_sector: int = 512
    gap_bytes: int = 80
    encoding: str = "mfm"


# =============================================================================
# Codec Adapter
# =============================================================================

class CodecAdapter:
    """
    Unified codec interface for Greaseweazle disk formats.

    This adapter bridges the gap between our FluxData/SectorData classes and
    Greaseweazle's codec infrastructure. It provides consistent encode/decode
    operations across ALL supported formats.

    The adapter is initialized with a DiskSession which determines which
    Greaseweazle codec to use. The session's gw_format string (e.g., 'ibm.1440',
    'amiga.amigados', 'mac.800') maps to the appropriate codec.

    Supported format families:
        - IBM PC: MFM formats (160KB to 2.88MB)
        - Amiga: AmigaDOS DD/HD
        - Macintosh: GCR 400KB/800KB (variable speed zones)
        - Apple II: GCR DOS 3.3, ProDOS
        - Commodore: 1541/1571/1581 GCR/MFM
        - Atari ST: MFM formats
        - Many more via Greaseweazle's comprehensive codec library

    Attributes:
        session: The DiskSession defining the disk format
        diskdef: Greaseweazle DiskDef object for the format
        gw_format: Greaseweazle format string

    Example:
        >>> session = DiskSession.from_gw_format('ibm.1440')
        >>> adapter = CodecAdapter(session)
        >>>
        >>> # Decode flux from disk read
        >>> sectors = adapter.decode_track(flux_data, cyl=0, head=0)
        >>> for sec in sectors:
        ...     print(f"Sector {sec.sector}: {sec.status.name}")
        >>>
        >>> # Encode sectors for disk write
        >>> flux = adapter.encode_track(sectors, cyl=0, head=0)
    """

    def __init__(self, session: 'DiskSession'):
        """
        Initialize the codec adapter with a session.

        Args:
            session: DiskSession defining the disk format to use

        Raises:
            ImportError: If Greaseweazle codec library not available
            ValueError: If the session's format is not supported
        """
        if not GREASEWEAZLE_CODEC_AVAILABLE:
            raise ImportError(
                "Greaseweazle codec library not available. "
                "Install with: pip install greaseweazle"
            )

        self._session = session
        self._gw_format = session.gw_format

        # Get the diskdef for this format
        self._diskdef = get_diskdef(self._gw_format)
        if self._diskdef is None:
            raise ValueError(f"Unknown format: {self._gw_format}")

        # Cache track objects for efficiency
        self._track_cache: Dict[tuple, Any] = {}

        logger.info("CodecAdapter initialized for format: %s", self._gw_format)
        logger.debug("  Cylinders: %d, Heads: %d",
                    self._diskdef.cyls, self._diskdef.heads)

    @property
    def session(self) -> 'DiskSession':
        """Get the session this adapter is configured for."""
        return self._session

    @property
    def gw_format(self) -> str:
        """Get the Greaseweazle format string."""
        return self._gw_format

    @property
    def diskdef(self):
        """Get the Greaseweazle DiskDef object."""
        return self._diskdef

    # =========================================================================
    # Track Creation
    # =========================================================================

    def _get_track(self, cyl: int, head: int, use_cache: bool = True):
        """
        Get or create a track object for the specified position.

        Args:
            cyl: Cylinder number
            head: Head number
            use_cache: Whether to use cached track objects

        Returns:
            Greaseweazle track object
        """
        cache_key = (cyl, head)

        if use_cache and cache_key in self._track_cache:
            return self._track_cache[cache_key]

        # Create new track from diskdef
        track = self._diskdef.mk_track(cyl, head)

        if use_cache:
            self._track_cache[cache_key] = track

        return track

    def clear_cache(self) -> None:
        """Clear the track cache."""
        self._track_cache.clear()
        logger.debug("Track cache cleared")

    def debug_decode_raw_flux(self, gw_flux, cyl: int, head: int) -> dict:
        """
        Debug function to decode raw Greaseweazle Flux directly.

        Bypasses our FluxData conversion to test if the issue is in
        our conversion or elsewhere.

        Args:
            gw_flux: Raw Greaseweazle Flux object (not our FluxData)
            cyl: Cylinder number
            head: Head number

        Returns:
            Dict with debug info about decode results
        """
        from greaseweazle.track import PLLTrack

        result = {
            'flux_info': {
                'sample_freq': gw_flux.sample_freq,
                'num_transitions': len(gw_flux.list),
                'index_list': list(gw_flux.index_list) if gw_flux.index_list else [],
                'index_cued': gw_flux.index_cued,
            },
            'pll_info': {},
            'raw_sectors': [],
            'final_sectors': [],
        }

        # Get track timing parameters
        track = self._get_track(cyl, head, use_cache=False)
        track_clock = getattr(track, 'clock', None)
        track_time_per_rev = getattr(track, 'time_per_rev', None)

        result['track_info'] = {
            'clock_us': track_clock * 1e6 if track_clock else None,
            'time_per_rev_ms': track_time_per_rev * 1000 if track_time_per_rev else None,
        }

        # Try PLL decode directly
        try:
            gw_flux.cue_at_index()

            pll_track = PLLTrack(
                time_per_rev=track_time_per_rev,
                clock=track_clock,
                data=gw_flux,
                pll=None
            )

            result['pll_info'] = {
                'num_bits': len(pll_track.bitarray),
                'num_revolutions': len(pll_track.revolutions),
                'bits_per_rev': [r.nr_bits for r in pll_track.revolutions],
            }

            # Now decode the track
            with _suppress_stdout():
                track.decode_flux(gw_flux)

            # Check for raw sectors (IBMTrack_Fixed stores them in .raw)
            if hasattr(track, 'raw') and track.raw is not None:
                for s in track.raw.sectors:
                    result['raw_sectors'].append({
                        'r': getattr(s.idam, 'r', None) if s.idam else None,
                        'crc': s.crc,
                        'idam_crc': getattr(s.idam, 'crc', None) if s.idam else None,
                        'dam_crc': getattr(s.dam, 'crc', None) if s.dam else None,
                        'has_data': s.dam is not None and s.dam.data is not None,
                        'data_len': len(s.dam.data) if s.dam and s.dam.data else 0,
                    })

            # Check final sectors
            for s in track.sectors:
                result['final_sectors'].append({
                    'r': getattr(s.idam, 'r', None) if s.idam else None,
                    'crc': s.crc,
                    'idam_crc': getattr(s.idam, 'crc', None) if s.idam else None,
                    'dam_crc': getattr(s.dam, 'crc', None) if s.dam else None,
                })

        except Exception as e:
            result['error'] = str(e)
            import traceback
            result['traceback'] = traceback.format_exc()

        return result

    # =========================================================================
    # Decoding (Flux → Sectors)
    # =========================================================================

    def decode_track(self, flux_data: 'FluxData', cyl: int, head: int) -> List[SectorData]:
        """
        Decode flux data to sectors using the Greaseweazle codec.

        This method takes raw flux timing data captured from a disk track
        and decodes it into individual sectors using the appropriate codec
        for the session's format.

        Args:
            flux_data: FluxData object containing captured flux transitions
            cyl: Cylinder number the flux was captured from
            head: Head number the flux was captured from

        Returns:
            List of SectorData objects, one per decoded sector.
            Missing or unreadable sectors will have appropriate status set.

        Example:
            >>> flux = device.read_track(0, 0)
            >>> sectors = adapter.decode_track(flux, 0, 0)
            >>> good_count = sum(1 for s in sectors if s.is_good)
            >>> print(f"Decoded {good_count}/{len(sectors)} good sectors")
        """
        # Create a fresh track object for decoding (don't use cache)
        track = self._get_track(cyl, head, use_cache=False)

        # Log track timing parameters for debugging
        track_clock = getattr(track, 'clock', None)
        track_time_per_rev = getattr(track, 'time_per_rev', None)
        logger.debug(
            "C%d:H%d: Track params - clock=%.3fµs, time_per_rev=%.1fms, format=%s",
            cyl, head,
            track_clock * 1e6 if track_clock else 0,
            track_time_per_rev * 1000 if track_time_per_rev else 0,
            self._gw_format
        )

        # Convert our FluxData to Greaseweazle Flux format
        gw_flux = flux_data.to_greaseweazle_flux()

        # Calculate flux time_per_rev for logging
        try:
            flux_ticks_per_rev = sum(gw_flux.index_list) / len(gw_flux.index_list) if gw_flux.index_list else 0
            flux_time_per_rev = flux_ticks_per_rev / gw_flux.sample_freq if flux_ticks_per_rev else 0
        except:
            flux_time_per_rev = 0

        # Log flux data characteristics
        logger.debug(
            "C%d:H%d: Flux data - %d transitions, sample_freq=%.1fMHz, "
            "index_cued=%s, time_per_rev=%.1fms, index_list=%s",
            cyl, head,
            len(gw_flux.list),
            gw_flux.sample_freq / 1e6,
            gw_flux.index_cued,
            flux_time_per_rev * 1000,
            gw_flux.index_list[:3] if gw_flux.index_list else []
        )

        # Verify timing match between track and flux
        if track_time_per_rev and flux_time_per_rev:
            time_diff_pct = abs(track_time_per_rev - flux_time_per_rev) / track_time_per_rev * 100
            if time_diff_pct > 5:  # More than 5% difference
                logger.warning(
                    "C%d:H%d: TIME MISMATCH! Track expects %.1fms, flux is %.1fms (%.1f%% diff)",
                    cyl, head, track_time_per_rev * 1000, flux_time_per_rev * 1000, time_diff_pct
                )

        # Decode the flux into the track
        # Use _suppress_stdout to silence Greaseweazle's "Unknown mark xx" prints
        try:
            with _suppress_stdout():
                track.decode_flux(gw_flux)
        except Exception as e:
            logger.warning("Flux decode error at C%d H%d: %s", cyl, head, e)
            # Fall back to standard decoder for IBM formats
            if self._gw_format.startswith('ibm.'):
                logger.debug("Falling back to standard decoder for IBM format")
                return self._fallback_decode(flux_data, cyl, head)
            # For non-IBM formats, return missing sectors
            return self._create_missing_sectors(cyl, head)

        # Log RAW decode results for IBMTrack_Fixed
        # The predefined sectors start with crc=0xffff and only get updated
        # if the raw decode finds matching sectors with good CRCs
        if hasattr(track, 'raw') and track.raw is not None:
            raw_track = track.raw
            raw_good = sum(1 for s in raw_track.sectors if s.crc == 0)
            raw_bad = sum(1 for s in raw_track.sectors if s.crc != 0)
            logger.info(
                "C%d:H%d: RAW decode found %d sectors: %d good (crc==0), %d bad",
                cyl, head, len(raw_track.sectors), raw_good, raw_bad
            )
            # Log first few raw sector CRCs for debugging
            for i, s in enumerate(raw_track.sectors[:5]):
                idam_crc = getattr(s.idam, 'crc', None) if s.idam else None
                dam_crc = getattr(s.dam, 'crc', None) if s.dam else None
                logger.debug(
                    "  RAW Sector[%d] R=%d: combined=%d, idam=%s, dam=%s",
                    i, getattr(s.idam, 'r', '?') if s.idam else '?',
                    s.crc, idam_crc, dam_crc
                )

        # Convert track sectors to our SectorData format
        return self._extract_sectors(track, cyl, head)

    def _extract_sectors(self, track, cyl: int, head: int) -> List[SectorData]:
        """
        Extract SectorData objects from a decoded track.

        Args:
            track: Greaseweazle track object with decoded data
            cyl: Cylinder number
            head: Head number

        Returns:
            List of SectorData objects
        """
        sectors = []
        expected_sectors = getattr(track, 'nsec', self._session.sectors_per_track)
        bytes_per_sector = self._session.bytes_per_sector

        # Get the full track image data
        try:
            img_data = track.get_img_track()
        except Exception as e:
            logger.warning("Could not get image data from track: %s", e)
            img_data = None

        # Track which sectors we found
        found_sectors: Dict[int, SectorData] = {}

        # Process decoded sectors from track
        if hasattr(track, 'sectors') and track.sectors:
            # Log raw GW sector info for debugging
            gw_good = sum(1 for s in track.sectors if getattr(s, 'crc', -1) == 0)
            logger.debug(
                "C%d:H%d: GW track has %d sectors, %d with crc==0 (good)",
                cyl, head, len(track.sectors), gw_good
            )
            for idx, gw_sec in enumerate(track.sectors):
                # Get sector number from IDAM if available
                sec_num = self._get_sector_number(gw_sec, idx)

                # Determine sector status
                status, crc_valid = self._determine_sector_status(gw_sec)

                # Get sector data
                data = self._get_sector_data(gw_sec, img_data, idx, bytes_per_sector)

                # Calculate signal quality
                signal_quality = self._calculate_signal_quality(gw_sec, status)

                sector = SectorData(
                    cylinder=cyl,
                    head=head,
                    sector=sec_num,
                    data=data,
                    status=status,
                    crc_valid=crc_valid,
                    signal_quality=signal_quality
                )
                found_sectors[sec_num] = sector

        # Build final sector list, filling in missing sectors
        for sec_num in range(1, expected_sectors + 1):
            if sec_num in found_sectors:
                sectors.append(found_sectors[sec_num])
            else:
                # Create missing sector entry
                sectors.append(SectorData(
                    cylinder=cyl,
                    head=head,
                    sector=sec_num,
                    data=bytes(bytes_per_sector),
                    status=SectorStatus.MISSING,
                    crc_valid=False,
                    signal_quality=0.0
                ))

        # Log summary of extracted sectors
        good_count = sum(1 for s in sectors if s.status == SectorStatus.GOOD)
        bad_count = sum(1 for s in sectors if s.status == SectorStatus.CRC_ERROR)
        missing_count = sum(1 for s in sectors if s.status == SectorStatus.MISSING)
        logger.info(
            "C%d:H%d extracted %d sectors: %d good, %d CRC errors, %d missing",
            cyl, head, len(sectors), good_count, bad_count, missing_count
        )

        return sectors

    def _get_sector_number(self, gw_sec, default_idx: int) -> int:
        """
        Get sector number from Greaseweazle sector object.

        Args:
            gw_sec: Greaseweazle sector object
            default_idx: Default index if sector number not found

        Returns:
            Sector number (1-based)
        """
        # Try to get from IDAM (ID Address Mark)
        if hasattr(gw_sec, 'idam') and gw_sec.idam:
            idam = gw_sec.idam
            # IDAM contains: c=cylinder, h=head, r=sector, n=size code
            # The 'r' field is the sector number
            if hasattr(idam, 'r'):
                return idam.r
            # Parse from string representation if needed
            idam_str = str(idam)
            if 'r=' in idam_str:
                try:
                    r_part = idam_str.split('r=')[1].split()[0]
                    return int(r_part)
                except (IndexError, ValueError):
                    pass

        # Default: use index + 1 (1-based sector numbering)
        return default_idx + 1

    def _determine_sector_status(self, gw_sec) -> tuple:
        """
        Determine sector status from Greaseweazle sector object.

        Greaseweazle uses a combined CRC field (idam.crc | dam.crc) where:
        - crc == 0 means BOTH IDAM and DAM CRCs are valid (sector is GOOD)
        - crc != 0 means at least one CRC failed (sector has errors)

        Args:
            gw_sec: Greaseweazle sector object (ibm.Sector)

        Returns:
            Tuple of (SectorStatus, crc_valid)
        """
        # Get combined CRC from sector (idam.crc | dam.crc)
        # In Greaseweazle, crc==0 means the CRC check passed
        crc = getattr(gw_sec, 'crc', None)
        dam = getattr(gw_sec, 'dam', None)
        idam = getattr(gw_sec, 'idam', None)

        # Debug logging to diagnose issues
        if logger.isEnabledFor(logging.DEBUG):
            idam_crc = getattr(idam, 'crc', None) if idam else None
            dam_crc = getattr(dam, 'crc', None) if dam else None
            sec_r = getattr(idam, 'r', '?') if idam else '?'
            logger.debug(
                "Sector R=%s: combined_crc=%s, idam_crc=%s, dam_crc=%s",
                sec_r, crc, idam_crc, dam_crc
            )

        # CRC=0 means good (both IDAM and DAM CRCs valid)
        if crc == 0:
            return SectorStatus.GOOD, True

        # Check if DAM (Data Address Mark) is present
        if dam is None:
            return SectorStatus.NO_DATA, False

        # Check for specific error types
        # If IDAM is valid (crc=0) but DAM is invalid, it's a data CRC error
        if idam is not None:
            idam_crc = getattr(idam, 'crc', None)
            if idam_crc == 0:
                # IDAM valid, DAM must have CRC error
                return SectorStatus.CRC_ERROR, False

        # Both have issues or other problem
        return SectorStatus.CRC_ERROR, False

    def _get_sector_data(self, gw_sec, img_data: Optional[bytes],
                         idx: int, bytes_per_sector: int) -> bytes:
        """
        Get sector data bytes.

        Greaseweazle stores sector data in the DAM (Data Address Mark) object,
        accessed via gw_sec.dam.data.

        Args:
            gw_sec: Greaseweazle sector object (ibm.Sector)
            img_data: Full track image data (if available)
            idx: Sector index in track
            bytes_per_sector: Expected bytes per sector

        Returns:
            Sector data bytes
        """
        # Try to get from DAM (Data Address Mark) - this is where GW stores data
        dam = getattr(gw_sec, 'dam', None)
        if dam is not None:
            dam_data = getattr(dam, 'data', None)
            if dam_data is not None:
                return bytes(dam_data)

        # Try to get from image data (fallback for bulk reads)
        if img_data is not None:
            start = idx * bytes_per_sector
            end = start + bytes_per_sector
            if end <= len(img_data):
                return bytes(img_data[start:end])

        # Return empty sector if no data found
        return bytes(bytes_per_sector)

    def _calculate_signal_quality(self, gw_sec, status: SectorStatus) -> float:
        """
        Calculate signal quality metric for a sector.

        Args:
            gw_sec: Greaseweazle sector object
            status: Determined sector status

        Returns:
            Signal quality from 0.0 to 1.0
        """
        if status == SectorStatus.GOOD:
            return 1.0
        elif status == SectorStatus.CRC_ERROR:
            return 0.5
        elif status == SectorStatus.WEAK:
            return 0.3
        elif status == SectorStatus.NO_DATA:
            return 0.1
        else:  # MISSING
            return 0.0

    def _create_missing_sectors(self, cyl: int, head: int) -> List[SectorData]:
        """
        Create a list of missing sector entries.

        Used when track decoding fails entirely.

        Args:
            cyl: Cylinder number
            head: Head number

        Returns:
            List of SectorData objects all marked as MISSING
        """
        sectors = []
        for sec_num in range(1, self._session.sectors_per_track + 1):
            sectors.append(SectorData(
                cylinder=cyl,
                head=head,
                sector=sec_num,
                data=bytes(self._session.bytes_per_sector),
                status=SectorStatus.MISSING,
                crc_valid=False,
                signal_quality=0.0
            ))
        return sectors

    def _fallback_decode(self, flux_data: 'FluxData', cyl: int, head: int) -> List[SectorData]:
        """
        Fall back to standard decoders when Greaseweazle codec fails.

        Uses the same decoder priority as the scan worker for consistency:
        1. Greaseweazle-compatible MFM codec
        2. PLL decoder
        3. Simple MFM decoder

        Args:
            flux_data: FluxData object containing captured flux transitions
            cyl: Cylinder number
            head: Head number

        Returns:
            List of SectorData objects from fallback decoder
        """
        # Get timing parameters from session
        bit_cell_us = self._session.bit_cell_us
        rpm = self._session.rpm

        # Try Greaseweazle-compatible decoder first
        try:
            from floppy_formatter.hardware.gw_mfm_codec import decode_flux_to_sectors_gw
            sectors = decode_flux_to_sectors_gw(flux_data, bit_cell_us=bit_cell_us)
            if sectors:
                logger.debug("Fallback GW decoder returned %d sectors", len(sectors))
                return sectors
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Fallback GW decoder failed: %s", e)

        # Try PLL decoder
        try:
            from floppy_formatter.hardware.pll_decoder import decode_flux_with_pll
            sectors = decode_flux_with_pll(flux_data, bit_cell_us=bit_cell_us, rpm=rpm)
            if sectors:
                logger.debug("Fallback PLL decoder returned %d sectors", len(sectors))
                return sectors
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Fallback PLL decoder failed: %s", e)

        # Fall back to simple decoder
        try:
            from floppy_formatter.hardware.mfm_codec import decode_flux_to_sectors
            sectors = decode_flux_to_sectors(flux_data, bit_cell_us=bit_cell_us)
            logger.debug("Fallback simple decoder returned %d sectors", len(sectors))
            return sectors
        except Exception as e:
            logger.warning("All fallback decoders failed: %s", e)

        # If all decoders fail, return missing sectors
        return self._create_missing_sectors(cyl, head)

    # =========================================================================
    # Encoding (Sectors → Flux)
    # =========================================================================

    def encode_track(self, sectors: List[SectorData], cyl: int, head: int) -> 'FluxData':
        """
        Encode sectors to flux data using the Greaseweazle codec.

        This method takes sector data and encodes it to flux format suitable
        for writing to a disk track using the appropriate codec for the
        session's format.

        Args:
            sectors: List of SectorData objects to encode
            cyl: Target cylinder number
            head: Target head number

        Returns:
            FluxData object ready for writing to disk

        Raises:
            ValueError: If sector data is invalid or incompatible

        Example:
            >>> # Prepare sector data
            >>> sectors = [SectorData(cyl=0, head=0, sector=i, data=data[i], ...)
            ...            for i in range(18)]
            >>> flux = adapter.encode_track(sectors, 0, 0)
            >>> device.write_track(0, 0, flux)
        """
        # Create track object
        track = self._get_track(cyl, head, use_cache=False)

        # Build track image data from sectors
        img_data = self._build_track_image(sectors, cyl, head)

        # Set the track image data
        try:
            track.set_img_track(img_data)
        except Exception as e:
            logger.error("Failed to set track image at C%d H%d: %s", cyl, head, e)
            raise ValueError(f"Failed to encode track data: {e}") from e

        # Generate master track (encoded format)
        try:
            master = track.master_track()
        except Exception as e:
            logger.error("Failed to create master track at C%d H%d: %s", cyl, head, e)
            raise ValueError(f"Failed to generate master track: {e}") from e

        # Get flux for writing
        try:
            writeout_flux = master.flux_for_writeout(cue_at_index=True)
        except Exception as e:
            logger.error("Failed to generate flux at C%d H%d: %s", cyl, head, e)
            raise ValueError(f"Failed to generate flux data: {e}") from e

        # Convert to our FluxData format
        return self._convert_writeout_flux(writeout_flux, cyl, head)

    def _build_track_image(self, sectors: List[SectorData],
                           cyl: int, head: int) -> bytes:
        """
        Build track image data from sectors.

        Args:
            sectors: List of SectorData objects
            cyl: Cylinder number
            head: Head number

        Returns:
            Bytes containing concatenated sector data
        """
        bytes_per_sector = self._session.bytes_per_sector
        expected_sectors = self._session.sectors_per_track

        # Create sector lookup by sector number
        sector_data_map: Dict[int, bytes] = {}
        for sec in sectors:
            if sec.cylinder == cyl and sec.head == head:
                sector_data_map[sec.sector] = sec.data

        # Build track image in sector order (1 to N)
        img_parts = []
        for sec_num in range(1, expected_sectors + 1):
            if sec_num in sector_data_map:
                data = sector_data_map[sec_num]
                # Ensure correct size
                if len(data) < bytes_per_sector:
                    data = data + bytes(bytes_per_sector - len(data))
                elif len(data) > bytes_per_sector:
                    data = data[:bytes_per_sector]
                img_parts.append(data)
            else:
                # Missing sector - fill with pattern
                img_parts.append(bytes(bytes_per_sector))

        return b''.join(img_parts)

    def _convert_writeout_flux(self, writeout_flux, cyl: int, head: int) -> 'FluxData':
        """
        Convert Greaseweazle WriteoutFlux to our FluxData format.

        Args:
            writeout_flux: Greaseweazle WriteoutFlux object
            cyl: Cylinder number
            head: Head number

        Returns:
            FluxData object
        """
        # WriteoutFlux has a list property with flux times
        flux_times = list(writeout_flux.list)

        # Get sample frequency
        sample_freq = getattr(writeout_flux, 'sample_freq', 72_000_000)

        # Get index positions if available
        index_positions = []
        if hasattr(writeout_flux, 'index_list'):
            index_positions = list(writeout_flux.index_list)

        return FluxData(
            flux_times=flux_times,
            sample_freq=sample_freq,
            index_positions=index_positions,
            cylinder=cyl,
            head=head,
            revolutions=1.0
        )

    # =========================================================================
    # Timing Information
    # =========================================================================

    def get_track_timing(self, cyl: int, head: int) -> TrackTiming:
        """
        Get timing parameters for a specific track.

        Different formats have different timing requirements. Some formats
        like Mac GCR even have variable timing per track (zone-based speed).
        This method returns the correct timing for the specified track.

        Args:
            cyl: Cylinder number
            head: Head number

        Returns:
            TrackTiming object with format-specific timing parameters

        Example:
            >>> timing = adapter.get_track_timing(0, 0)
            >>> print(f"Bit cell: {timing.bit_cell_us}µs")
            >>> print(f"Data rate: {timing.data_rate_kbps} kbps")
        """
        # Get track object to access timing
        track = self._get_track(cyl, head)

        # Extract timing from track
        clock = getattr(track, 'clock', 1e-6)
        time_per_rev = getattr(track, 'time_per_rev', 0.2)
        nsec = getattr(track, 'nsec', self._session.sectors_per_track)

        # Calculate derived values
        bit_cell_us = clock * 1e6
        rpm = int(60.0 / time_per_rev) if time_per_rev > 0 else 300
        time_per_rev_ms = time_per_rev * 1000
        clock_ns = clock * 1e9

        # Calculate data rate (approximate)
        # For MFM: data_rate = 1 / (2 * bit_cell)
        if bit_cell_us > 0:
            data_rate_kbps = int(500 / bit_cell_us)
        else:
            data_rate_kbps = 500

        # Get gap bytes if available
        gap_bytes = getattr(track, 'gap_presync', 80)

        return TrackTiming(
            bit_cell_us=bit_cell_us,
            data_rate_kbps=data_rate_kbps,
            rpm=rpm,
            time_per_rev_ms=time_per_rev_ms,
            clock_ns=clock_ns,
            sectors_per_track=nsec,
            bytes_per_sector=self._session.bytes_per_sector,
            gap_bytes=gap_bytes,
            encoding=self._session.encoding
        )

    # =========================================================================
    # Format Information
    # =========================================================================

    def get_format_info(self) -> Dict[str, Any]:
        """
        Get information about the codec's format.

        Returns:
            Dictionary with format details
        """
        return {
            'gw_format': self._gw_format,
            'platform': self._session.platform,
            'cylinders': self._diskdef.cyls,
            'heads': self._diskdef.heads,
            'encoding': self._session.encoding,
            'disk_size': self._session.disk_size,
            'capacity_kb': self._session.capacity_kb,
        }

    def is_variable_sectors_per_track(self) -> bool:
        """
        Check if format has variable sectors per track.

        Some formats like C64 GCR have different numbers of sectors
        on different tracks (zone-based).

        Returns:
            True if sectors per track varies by cylinder
        """
        # Check a few tracks to see if nsec changes
        if self._diskdef.cyls < 2:
            return False

        track0 = self._get_track(0, 0)
        nsec0 = getattr(track0, 'nsec', 0)

        # Check middle track
        mid_cyl = self._diskdef.cyls // 2
        track_mid = self._diskdef.mk_track(mid_cyl, 0)
        nsec_mid = getattr(track_mid, 'nsec', 0)

        return nsec0 != nsec_mid

    def get_sectors_for_track(self, cyl: int, head: int) -> int:
        """
        Get the number of sectors for a specific track.

        Useful for formats with variable sectors per track.

        Args:
            cyl: Cylinder number
            head: Head number

        Returns:
            Number of sectors on this track
        """
        track = self._get_track(cyl, head)
        return getattr(track, 'nsec', self._session.sectors_per_track)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def validate_session(self) -> tuple:
        """
        Validate that the session is compatible with the codec.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Try to create a track - this validates the format
            track = self._diskdef.mk_track(0, 0)
            if track is None:
                return False, "Could not create track from format"

            # Check basic attributes
            if not hasattr(track, 'decode_flux'):
                return False, "Track does not support flux decoding"

            if not hasattr(track, 'master_track'):
                return False, "Track does not support encoding"

            return True, None

        except Exception as e:
            return False, f"Format validation failed: {e}"

    def __repr__(self) -> str:
        """String representation."""
        return (f"CodecAdapter(format='{self._gw_format}', "
                f"cyls={self._diskdef.cyls}, heads={self._diskdef.heads})")


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'CodecAdapter',
    'TrackTiming',
]
