"""
PLL-based MFM decoder adapted from Greaseweazle.

This module implements a Phase-Locked Loop (PLL) based decoder for
converting raw flux timing data to MFM-encoded bits, then decoding
to sector data.

The PLL algorithm dynamically adjusts both phase and frequency to
track timing variations in the flux data, providing much more robust
decoding than simple division methods.

Based on Greaseweazle's track.py and codec/ibm/ibm.py
Original code by Keir Fraser, released into public domain.
"""

import logging
import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Try to import bitarray for efficient bit operations
try:
    from bitarray import bitarray
    BITARRAY_AVAILABLE = True
except ImportError:
    BITARRAY_AVAILABLE = False
    bitarray = None

# Try to import crcmod for CRC calculation
try:
    import crcmod.predefined
    crc16 = crcmod.predefined.Crc('crc-ccitt-false')
    CRCMOD_AVAILABLE = True
except ImportError:
    CRCMOD_AVAILABLE = False
    crc16 = None

from . import SectorStatus, SectorData
from .flux_io import FluxData

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# MFM sync patterns (as bytes for bitarray)
# Three A1 sync marks with missing clock: 0x4489 * 3
MFM_SYNC_BYTES = b'\x44\x89' * 3
MFM_IAM_SYNC_BYTES = b'\x52\x24' * 3

# Address marks


class Mark:
    IAM = 0xfc   # Index Address Mark
    IDAM = 0xfe  # ID Address Mark
    DAM = 0xfb   # Data Address Mark
    DDAM = 0xf8  # Deleted Data Address Mark


# =============================================================================
# MFM Decode/Encode Tables
# =============================================================================

# Build decode lookup table: 16-bit MFM -> 8-bit data
_decode_list = bytearray()
for x in range(0x5555 + 1):
    y = 0
    for i in range(16):
        if x & (1 << (i * 2)):
            y |= 1 << i
    _decode_list.append(y)


def mfm_decode(dat: bytes) -> bytes:
    """Decode MFM-encoded bytes to data bytes."""
    out = bytearray()
    for x, y in zip(dat[::2], dat[1::2]):
        out.append(_decode_list[((x << 8) | y) & 0x5555])
    return bytes(out)


# =============================================================================
# CRC Calculation
# =============================================================================

def calculate_crc_ccitt(data: bytes) -> int:
    """Calculate CRC-CCITT (0xFFFF initial, no final XOR)."""
    if CRCMOD_AVAILABLE:
        return crc16.new(data).crcValue
    else:
        # Fallback implementation
        crc = 0xFFFF
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        return crc


# =============================================================================
# PLL-based Flux to Bits Conversion
# =============================================================================

@dataclass
class PLLConfig:
    """Configuration for the PLL decoder."""
    period_adj_pct: float = 5.0    # Clock frequency adjustment rate (%)
    phase_adj_pct: float = 60.0    # Clock phase adjustment rate (%)
    clock_max_adj: float = 0.30    # Maximum clock adjustment (±30%) - matches GW decoder
    lowpass_thresh: Optional[float] = None  # Optional noise filter threshold


class PLLDecoder:
    """
    PLL-based flux-to-bits decoder.

    Uses a Phase-Locked Loop algorithm to convert raw flux timing
    to a bitstream. The PLL dynamically adjusts both phase and frequency
    to track timing variations in the flux data.
    """

    def __init__(self, clock: float, config: Optional[PLLConfig] = None):
        """
        Initialize PLL decoder.

        Args:
            clock: Expected time per bit cell in seconds
            config: PLL configuration parameters
        """
        self.clock = clock
        self.config = config or PLLConfig()

        # Calculate clock limits
        self.clock_min = clock * (1 - self.config.clock_max_adj)
        self.clock_max = clock * (1 + self.config.clock_max_adj)

        # PLL adjustment factors
        self.pll_period_adj = self.config.period_adj_pct / 100
        self.pll_phase_adj = self.config.phase_adj_pct / 100

    def flux_to_bitcells(self, flux_data: FluxData) -> Tuple['bitarray', List[float], List[int]]:
        """
        Convert flux timing data to bitcells using PLL.

        Args:
            flux_data: Raw flux timing data

        Returns:
            Tuple of (bitarray, time_array, revolution_boundaries)
        """
        if not BITARRAY_AVAILABLE:
            raise ImportError("bitarray package required for PLL decoder")

        freq = float(flux_data.sample_freq)
        clock_centre = self.clock
        clock = clock_centre

        # Initialize output arrays
        bit_array = bitarray(endian='big')
        time_array: List[float] = []
        revolutions: List[int] = []

        # Index iterator for revolution detection
        if flux_data.index_positions and len(flux_data.index_positions) >= 2:
            index_times = []
            for i in range(1, len(flux_data.index_positions)):
                idx_samples = flux_data.index_positions[i] - flux_data.index_positions[i-1]
                index_times.append(idx_samples / freq)
            index_iter = iter(index_times + [float('inf')])
        else:
            # No index info, use estimated revolution time
            index_iter = iter([0.2, float('inf')])  # ~200ms per rev at 300 RPM

        # Optional lowpass filtering for noise
        flux_times = flux_data.flux_times
        if self.config.lowpass_thresh is not None:
            flux_times = self._lowpass_filter(flux_times, freq, self.config.lowpass_thresh)

        # Convert flux list to iterator
        flux_iter = iter(flux_times)

        nbits = 0
        ticks = 0.0
        to_index = next(index_iter)

        for x in flux_iter:
            # Gather enough ticks to generate at least one bitcell
            ticks += x / freq
            if ticks < clock / 2:
                continue

            # Clock out zero or more 0s, followed by a 1
            zeros = 0
            while True:
                ticks -= clock
                if ticks < clock / 2:
                    break
                zeros += 1
                bit_array.append(False)
            bit_array.append(True)

            # PLL: Adjust clock window position according to phase mismatch
            new_ticks = ticks * (1 - self.pll_phase_adj)

            # Distribute the clock adjustment across all bits we just emitted
            _clock = clock + (ticks - new_ticks) / (zeros + 1)
            for i in range(zeros + 1):
                # Check if we cross the index mark
                to_index -= _clock
                if to_index < 0:
                    revolutions.append(nbits)
                    nbits = 0
                    to_index += next(index_iter, float('inf'))
                # Emit bit time
                nbits += 1
                time_array.append(_clock)

            # PLL: Adjust clock frequency according to phase mismatch
            if zeros <= 3:
                # In sync: adjust clock by a fraction of the phase mismatch
                clock += ticks * self.pll_period_adj
            else:
                # Out of sync: adjust clock towards centre
                clock += (clock_centre - clock) * self.pll_period_adj

            # Clamp the clock's adjustment range
            clock = min(max(clock, self.clock_min), self.clock_max)

            ticks = new_ticks

        # Add final revolution if we have bits
        if nbits > 0:
            revolutions.append(nbits)

        return bit_array, time_array, revolutions

    def _lowpass_filter(self, flux_times: List[int], freq: float,
                        thresh: float) -> List[int]:
        """Apply lowpass filter to remove short noise pulses."""
        result = []
        flux_iter = iter(flux_times)
        pending = 0

        for x in flux_iter:
            t = x / freq
            if t <= thresh:
                # Short pulse - merge with neighbors
                try:
                    y = next(flux_iter)
                    if y / freq <= t:
                        # y is shorter, merge x+y+next
                        z = next(flux_iter, 0)
                        pending += x + y + z
                    else:
                        # x is shorter, merge pending+x+y to pending
                        pending += x + y
                except StopIteration:
                    pending += x
            else:
                if pending > 0:
                    result.append(pending + x)
                    pending = 0
                else:
                    result.append(x)

        if pending > 0:
            if result:
                result[-1] += pending
            else:
                result.append(pending)

        return result


# =============================================================================
# MFM Sector Decoder
# =============================================================================

@dataclass
class DecodedIDAM:
    """Decoded ID Address Mark."""
    start: int      # Bit position
    end: int        # Bit position
    crc: int        # CRC value (0 = valid)
    c: int          # Cylinder
    h: int          # Head
    r: int          # Sector (record)
    n: int          # Size code


@dataclass
class DecodedDAM:
    """Decoded Data Address Mark."""
    start: int      # Bit position
    end: int        # Bit position
    crc: int        # CRC value (0 = valid)
    mark: int       # Address mark (DAM or DDAM)
    data: bytes     # Sector data


@dataclass
class DecodedSector:
    """Complete decoded sector."""
    idam: DecodedIDAM
    dam: DecodedDAM

    @property
    def crc_valid(self) -> bool:
        return self.idam.crc == 0 and self.dam.crc == 0


class MFMSectorDecoder:
    """
    MFM sector decoder using PLL-decoded bitstream.

    Searches for A1 sync patterns and decodes sector headers and data.
    """

    def __init__(self):
        """Initialize decoder."""
        if not BITARRAY_AVAILABLE:
            raise ImportError("bitarray package required for MFM decoder")

        # Pre-build sync pattern as bitarray
        self.mfm_sync = bitarray(endian='big')
        self.mfm_sync.frombytes(MFM_SYNC_BYTES)

    def decode_track(self, bits: 'bitarray',
                     expected_cyl: int = 0,
                     expected_head: int = 0) -> List[DecodedSector]:
        """
        Decode all sectors from a PLL-decoded bitstream.

        Args:
            bits: Bitarray from PLL decoder
            expected_cyl: Expected cylinder (for logging)
            expected_head: Expected head (for logging)

        Returns:
            List of decoded sectors
        """
        sectors: List[DecodedSector] = []
        idam: Optional[DecodedIDAM] = None

        logger.debug("Searching for MFM sync patterns in %d bits", len(bits))

        # Search for all sync patterns
        sync_positions = list(bits.search(self.mfm_sync))
        logger.debug("Found %d MFM sync patterns", len(sync_positions))

        for offs in sync_positions:
            # Need at least 4*16 bits after sync for address mark
            if len(bits) < offs + 4 * 16:
                continue

            # Decode the address mark (byte after 3 A1 syncs)
            mark_bits = bits[offs + 3 * 16:offs + 4 * 16]
            mark = mfm_decode(mark_bits.tobytes())[0]

            if mark == Mark.IDAM:
                # ID Address Mark - sector header
                s, e = offs, offs + 10 * 16
                if len(bits) < e:
                    continue

                # Decode header bytes: A1 A1 A1 FE C H R N CRC CRC
                header_bits = bits[s:e]
                header = mfm_decode(header_bits.tobytes())
                c, h, r, n = struct.unpack(">4x4B2x", header)

                # Verify CRC
                crc = calculate_crc_ccitt(header)

                # Save previous IDAM if not matched with DAM
                if idam is not None:
                    logger.debug("Orphan IDAM at %d (no DAM found)", idam.start)

                idam = DecodedIDAM(s, e, crc, c, h, r, n)

                if crc == 0:
                    logger.debug("Found valid IDAM: C=%d H=%d R=%d N=%d", c, h, r, n)
                else:
                    logger.debug("Found IDAM with CRC error: C=%d H=%d R=%d N=%d", c, h, r, n)

            elif mark == Mark.DAM or mark == Mark.DDAM:
                # Data Address Mark
                if idam is None or offs - idam.end > 1000:
                    # No matching IDAM or too far away
                    logger.debug("DAM at %d without matching IDAM", offs)
                    continue

                # Calculate sector size from size code
                sz = 128 << idam.n

                # Calculate data field extent
                s, e = offs, offs + (4 + sz + 2) * 16
                if len(bits) < e:
                    logger.debug("Not enough bits for sector data at %d", offs)
                    continue

                # Decode data field
                data_bits = bits[s:e]
                data = mfm_decode(data_bits.tobytes())

                # Verify CRC
                crc = calculate_crc_ccitt(data)

                # Extract sector data (skip A1 A1 A1 DAM, exclude CRC)
                sector_data = data[4:-2]

                dam = DecodedDAM(s, e, crc, mark, sector_data)
                sector = DecodedSector(idam, dam)

                if sector.crc_valid:
                    logger.debug(
                        "Decoded valid sector C=%d H=%d R=%d (%d bytes)",
                        idam.c, idam.h, idam.r, len(sector_data)
                    )
                else:
                    logger.debug(
                        "Decoded sector with CRC error C=%d H=%d R=%d",
                        idam.c, idam.h, idam.r
                    )

                sectors.append(sector)
                idam = None

        logger.info("Decoded %d sectors from track", len(sectors))
        return sectors


# =============================================================================
# High-Level Decoder
# =============================================================================

class PLLMFMDecoder:
    """
    Complete PLL-based MFM decoder.

    Combines PLL flux-to-bits conversion with MFM sector decoding.
    """

    def __init__(self, bit_cell_us: float = 1.0,
                 pll_config: Optional[PLLConfig] = None):
        """
        Initialize decoder.

        Args:
            bit_cell_us: Expected bit cell width in microseconds (1.0 for HD, 2.0 for DD)
            pll_config: Optional PLL configuration
        """
        self.bit_cell_us = bit_cell_us
        self.clock = bit_cell_us / 1_000_000  # Convert to seconds
        self.pll_config = pll_config

    def decode_track(self, flux_data: FluxData) -> List[SectorData]:
        """
        Decode all sectors from flux data.

        Args:
            flux_data: Raw flux capture from a track

        Returns:
            List of SectorData for each decoded sector
        """
        if not BITARRAY_AVAILABLE:
            logger.error("bitarray package not available - cannot use PLL decoder")
            return []

        logger.info(
            "PLL decoding track C%d H%d (%d flux transitions)",
            flux_data.cylinder, flux_data.head, len(flux_data.flux_times)
        )

        # Auto-detect bit cell if possible
        detected_bit_cell = flux_data.estimate_bit_cell_width()
        if detected_bit_cell is not None and 0.5 <= detected_bit_cell <= 4.0:
            clock = detected_bit_cell / 1_000_000
            logger.debug("Using detected bit cell: %.2f µs", detected_bit_cell)
        else:
            clock = self.clock
            logger.debug("Using default bit cell: %.2f µs", self.bit_cell_us)

        # Create PLL decoder and convert flux to bits
        pll = PLLDecoder(clock, self.pll_config)
        try:
            bits, times, revolutions = pll.flux_to_bitcells(flux_data)
        except Exception as e:
            logger.error("PLL conversion failed: %s", e)
            return []

        logger.debug(
            "PLL produced %d bits across %d revolution(s)",
            len(bits), len(revolutions)
        )

        # Decode sectors from bitstream
        sector_decoder = MFMSectorDecoder()
        decoded = sector_decoder.decode_track(bits, flux_data.cylinder, flux_data.head)

        # Convert to SectorData format
        sectors = []
        for d in decoded:
            status = SectorStatus.GOOD if d.crc_valid else SectorStatus.CRC_ERROR
            quality = 1.0 if d.crc_valid else 0.5

            sectors.append(SectorData(
                cylinder=d.idam.c,
                head=d.idam.h,
                sector=d.idam.r,
                data=d.dam.data,
                status=status,
                crc_valid=d.crc_valid,
                signal_quality=quality
            ))

        # Sort by sector number
        sectors.sort(key=lambda s: s.sector)

        return sectors


def decode_flux_with_pll(flux_data: FluxData,
                         bit_cell_us: float = 1.0) -> List[SectorData]:
    """
    High-level function to decode flux data using PLL decoder.

    Args:
        flux_data: Raw flux capture from a track
        bit_cell_us: Expected bit cell width (default 1.0µs for HD, use 2.0 for DD)

    Returns:
        List of SectorData for each decoded sector
    """
    decoder = PLLMFMDecoder(bit_cell_us)
    return decoder.decode_track(flux_data)
