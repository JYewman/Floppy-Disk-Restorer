"""
MFM Codec using Greaseweazle's proven implementation.

This module provides MFM encoding and decoding by directly leveraging
Greaseweazle's battle-tested code. It serves as an adapter between
the workbench's data structures and Greaseweazle's track handling.

Based on Greaseweazle code by Keir Fraser, released into public domain.
"""

import struct
import logging
from typing import List, Optional
from dataclasses import dataclass

# Import Greaseweazle components
from bitarray import bitarray
import crcmod.predefined

from .flux_io import FluxData
from . import SectorData, SectorStatus

logger = logging.getLogger(__name__)

# CRC calculator
crc16 = crcmod.predefined.Crc('crc-ccitt-false')

# =============================================================================
# Constants from Greaseweazle
# =============================================================================

# MFM sync pattern: 3x A1 with missing clock = 0x4489 * 3
MFM_SYNC_BYTES = b'\x44\x89' * 3

# Address marks


class Mark:
    IAM = 0xfc   # Index Address Mark
    IDAM = 0xfe  # ID Address Mark
    DAM = 0xfb   # Data Address Mark
    DDAM = 0xf8  # Deleted Data Address Mark


# HD 3.5" format parameters
HD_TIME_PER_REV = 0.2  # 200ms at 300 RPM
# HD MFM bit cell is 1µs (500kbps data rate = 1Mbps MFM cell rate)
# Flux transitions occur at 2T, 3T, 4T = 2µs, 3µs, 4µs
HD_CLOCK = 1e-6  # 1µs MFM bit cell for HD

# MFM gaps (bytes)
MFM_GAP1 = 50   # Post-index gap
MFM_GAP2 = 22   # Post-IDAM gap
MFM_GAP3 = 54   # Post-DAM gap (for 512-byte sectors)
MFM_GAP4A = 80  # Pre-index gap
MFM_PRESYNC = 12  # Sync field length (0x00 bytes)
MFM_GAPBYTE = 0x4e  # Gap fill byte

# =============================================================================
# Encoding/Decoding Tables (from Greaseweazle)
# =============================================================================

# Build encode lookup: 8-bit data -> 16-bit MFM (data bits only)
_encode_list: List[int] = []
for x in range(256):
    y = 0
    for i in range(8):
        y <<= 2
        y |= (x >> (7-i)) & 1
    _encode_list.append(y)

# Build decode lookup: 16-bit MFM -> 8-bit data
_decode_list = bytearray()
for x in range(0x5555 + 1):
    y = 0
    for i in range(16):
        if x & (1 << (i * 2)):
            y |= 1 << i
    _decode_list.append(y)


def encode(dat: bytes) -> bytes:
    """Encode data bytes to MFM (data bits only, no clock)."""
    out = bytearray()
    for x in dat:
        out += struct.pack('>H', _encode_list[x])
    return bytes(out)


def decode(dat: bytes) -> bytes:
    """Decode MFM bytes to data bytes."""
    out = bytearray()
    for x, y in zip(dat[::2], dat[1::2]):
        out.append(_decode_list[((x << 8) | y) & 0x5555])
    return bytes(out)


def mfm_encode(dat: bytes) -> bytes:
    """Add clock bits to MFM-encoded data."""
    y = 0
    out = bytearray()
    for x in dat:
        y = (y << 8) | x
        if (x & 0xaa) == 0:
            y |= ~((y >> 1) | (y << 1)) & 0xaaaa
        y &= 255
        out.append(y)
    return bytes(out)


def sync_a1() -> bytes:
    """Get A1 sync byte with missing clock (0x4489 pattern)."""
    # A1 with missing clock at bit 5
    return b'\x44\x89'


# =============================================================================
# Track Encoding (adapted from Greaseweazle IBMTrack.mfm_master_track)
# =============================================================================

def encode_mfm_track(
    cylinder: int,
    head: int,
    sectors: List[SectorData],
    time_per_rev: float = HD_TIME_PER_REV,
    clock: float = HD_CLOCK,
    sample_freq: int = 72_000_000
) -> FluxData:
    """
    Encode sectors to MFM flux data for writing.

    This uses the same algorithm as Greaseweazle's IBMTrack.mfm_master_track()
    to ensure compatibility.

    Args:
        cylinder: Cylinder number
        head: Head number
        sectors: List of SectorData to encode
        time_per_rev: Revolution time in seconds (0.2 for 300 RPM)
        clock: Bit cell time in seconds (2e-6 for HD)
        sample_freq: Sample frequency in Hz

    Returns:
        FluxData ready for writing
    """
    logger.debug("Encoding MFM track C%d H%d with %d sectors",
                 cylinder, head, len(sectors))

    # Sort sectors by sector number
    sectors_sorted = sorted(sectors, key=lambda s: s.sector)

    # Build the track as encoded bytes
    t = bytearray()

    # Gap 4a (pre-index gap)
    t += encode(bytes([MFM_GAPBYTE] * MFM_GAP4A))

    # Gap 1 (post-index gap)
    t += encode(bytes([MFM_GAPBYTE] * MFM_GAP1))

    # Encode each sector
    for sector in sectors_sorted:
        # Pre-sync gap
        t += encode(bytes([MFM_GAPBYTE] * 12))

        # Sync field (12 bytes of 0x00)
        t += encode(bytes([0x00] * MFM_PRESYNC))

        # IDAM: A1 A1 A1 FE C H R N CRC CRC
        t += MFM_SYNC_BYTES  # 3x A1 sync

        idam = bytes([0xa1, 0xa1, 0xa1, Mark.IDAM,
                      cylinder, head, sector.sector, 2])  # N=2 for 512 bytes
        idam_crc = crc16.new(idam).crcValue
        idam += struct.pack('>H', idam_crc)
        t += encode(idam[3:])  # Encode from FE onwards (syncs already added)

        # Gap 2 (post-IDAM)
        t += encode(bytes([MFM_GAPBYTE] * MFM_GAP2))

        # Sync field for data
        t += encode(bytes([0x00] * MFM_PRESYNC))

        # DAM: A1 A1 A1 FB DATA CRC CRC
        t += MFM_SYNC_BYTES  # 3x A1 sync

        data = sector.data if sector.data else bytes(512)
        if len(data) < 512:
            data = data + bytes(512 - len(data))
        elif len(data) > 512:
            data = data[:512]

        dam = bytes([0xa1, 0xa1, 0xa1, Mark.DAM]) + data
        dam_crc = crc16.new(dam).crcValue
        dam += struct.pack('>H', dam_crc)
        t += encode(dam[3:])  # Encode from FB onwards (syncs already added)

        # Gap 3 (post-DAM)
        t += encode(bytes([MFM_GAPBYTE] * MFM_GAP3))

    # Fill remaining track with gap bytes
    # Target track length in bits
    target_bits = int(time_per_rev / clock)
    current_bits = len(t) * 8  # Each byte is 8 bits

    if current_bits < target_bits:
        gap_bytes = (target_bits - current_bits) // 16  # 16 MFM bits per byte
        t += encode(bytes([MFM_GAPBYTE] * gap_bytes))

    # Add clock bits to the encoded data
    t = bytearray(mfm_encode(bytes(t)))

    logger.debug("Encoded track: %d bytes -> %d MFM bits", len(t), len(t) * 8)

    # Convert MFM bits to flux timing
    # Create bitarray from the MFM bytes
    bits = bitarray(endian='big')
    bits.frombytes(bytes(t))

    # Calculate ticks per bit cell
    # At 72MHz sample freq and 2µs bit cell: 2e-6 * 72e6 = 144 ticks per bit
    ticks_per_bit = clock * sample_freq
    logger.debug("Ticks per bit cell: %.1f (%.2f µs)", ticks_per_bit, clock * 1e6)

    # Convert bits to flux timings
    # Each 1 bit is a flux transition, 0 bits just add time between transitions
    flux_list = []
    flux_ticks = 0.0

    for bit in bits:
        flux_ticks += ticks_per_bit
        if bit:
            flux_list.append(int(flux_ticks))
            flux_ticks = 0.0

    # Handle trailing ticks (append to last flux if any)
    if flux_ticks > 0 and flux_list:
        flux_list[-1] += int(flux_ticks)

    logger.info("Encoded track C%d H%d: %d flux transitions, %.1f ms",
                cylinder, head, len(flux_list),
                sum(flux_list) / sample_freq * 1000)

    return FluxData(
        flux_times=flux_list,
        sample_freq=sample_freq,
        cylinder=cylinder,
        head=head
    )


# =============================================================================
# Track Decoding (adapted from Greaseweazle IBMTrack.mfm_decode_raw)
# =============================================================================

@dataclass
class DecodedIDAM:
    """Decoded ID Address Mark."""
    start: int
    end: int
    crc: int
    c: int  # Cylinder
    h: int  # Head
    r: int  # Sector number
    n: int  # Size code


@dataclass
class DecodedDAM:
    """Decoded Data Address Mark."""
    start: int
    end: int
    crc: int
    mark: int
    data: bytes


def decode_mfm_track(flux_data: FluxData) -> List[SectorData]:
    """
    Decode MFM flux data to sectors using PLL.

    This uses the same algorithm as Greaseweazle's IBMTrack.mfm_decode_raw()
    to ensure compatibility.

    Args:
        flux_data: Raw flux capture from a track

    Returns:
        List of decoded SectorData
    """
    logger.info("Decoding MFM track C%d H%d (%d flux transitions)",
                flux_data.cylinder, flux_data.head, len(flux_data.flux_times))

    # Convert flux to bits using PLL
    bits = flux_to_bits_pll(flux_data)

    if len(bits) < 1000:
        logger.warning("Too few bits decoded: %d", len(bits))
        return []

    logger.debug("PLL produced %d bits", len(bits))

    # Create sync pattern for searching
    mfm_sync = bitarray(endian='big')
    mfm_sync.frombytes(MFM_SYNC_BYTES)

    sectors: List[SectorData] = []
    idam: Optional[DecodedIDAM] = None

    # Search for sync patterns
    sync_positions = list(bits.search(mfm_sync))
    logger.debug("Found %d MFM sync patterns", len(sync_positions))

    for offs in sync_positions:
        # Need at least 4*16 bits after sync for address mark
        if len(bits) < offs + 4 * 16:
            continue

        # Decode the address mark (byte after 3 A1 syncs)
        mark_bits = bits[offs + 3 * 16:offs + 4 * 16]
        mark = decode(mark_bits.tobytes())[0]

        if mark == Mark.IDAM:
            # ID Address Mark - sector header
            s, e = offs, offs + 10 * 16
            if len(bits) < e:
                continue

            # Decode header bytes: A1 A1 A1 FE C H R N CRC CRC
            header_bits = bits[s:e]
            header = decode(header_bits.tobytes())
            c, h, r, n = struct.unpack(">4x4B2x", header)

            # Verify CRC
            crc = crc16.new(header).crcValue

            idam = DecodedIDAM(s, e, crc, c, h, r, n)

            if crc == 0:
                logger.debug("Found valid IDAM: C=%d H=%d R=%d N=%d", c, h, r, n)
            else:
                logger.debug("Found IDAM with CRC error: C=%d H=%d R=%d N=%d", c, h, r, n)

        elif mark == Mark.DAM or mark == Mark.DDAM:
            # Data Address Mark
            if idam is None or offs - idam.end > 1000:
                # No matching IDAM or too far away
                continue

            # Calculate sector size from size code
            sz = 128 << idam.n

            # Calculate data field extent
            s, e = offs, offs + (4 + sz + 2) * 16
            if len(bits) < e:
                continue

            # Decode data field
            data_bits = bits[s:e]
            data = decode(data_bits.tobytes())

            # Verify CRC
            crc = crc16.new(data).crcValue

            # Extract sector data (skip A1 A1 A1 DAM, exclude CRC)
            sector_data = data[4:-2]

            # Create SectorData
            crc_valid = (idam.crc == 0 and crc == 0)
            status = SectorStatus.GOOD if crc_valid else SectorStatus.CRC_ERROR

            sectors.append(SectorData(
                cylinder=idam.c,
                head=idam.h,
                sector=idam.r,
                data=sector_data,
                status=status,
                crc_valid=crc_valid,
                signal_quality=1.0 if crc_valid else 0.5
            ))

            if crc_valid:
                logger.debug(
                    "Decoded valid sector C=%d H=%d R=%d (%d bytes)",
                    idam.c, idam.h, idam.r, len(sector_data)
                )
            else:
                logger.debug(
                    "Decoded sector with CRC error C=%d H=%d R=%d",
                    idam.c, idam.h, idam.r
                )

            idam = None

    logger.info("Decoded %d sectors from track", len(sectors))
    return sorted(sectors, key=lambda s: s.sector)


def flux_to_bits_pll(
    flux_data: FluxData,
    clock: float = HD_CLOCK,
    period_adj_pct: int = 5,
    phase_adj_pct: int = 60
) -> bitarray:
    """
    Convert flux timing to bits using PLL algorithm.

    This is adapted from Greaseweazle's PLL implementation.

    Args:
        flux_data: Raw flux capture
        clock: Expected bit cell time in seconds
        period_adj_pct: PLL period adjustment percentage
        phase_adj_pct: PLL phase adjustment percentage

    Returns:
        Decoded bitarray
    """
    freq = float(flux_data.sample_freq)
    clock_centre = clock
    clock_min = clock * 0.7  # Allow 30% deviation
    clock_max = clock * 1.3

    pll_period_adj = period_adj_pct / 100
    pll_phase_adj = phase_adj_pct / 100

    bits = bitarray(endian='big')

    ticks = 0.0

    for x in flux_data.flux_times:
        # Accumulate time
        ticks += x / freq

        if ticks < clock / 2:
            continue

        # Clock out zero or more 0s, followed by a 1
        while ticks >= clock / 2:
            ticks -= clock
            if ticks >= clock / 2:
                bits.append(False)  # 0 bit
            else:
                break
        bits.append(True)  # 1 bit (flux transition)

        # PLL: Adjust phase
        new_ticks = ticks * (1 - pll_phase_adj)

        # PLL: Adjust frequency
        if abs(ticks) < clock * 2:
            # In sync: adjust towards measured period
            clock += ticks * pll_period_adj
        else:
            # Out of sync: adjust towards centre
            clock += (clock_centre - clock) * pll_period_adj

        # Clamp clock
        clock = max(min(clock, clock_max), clock_min)

        ticks = new_ticks

    return bits


# =============================================================================
# High-level functions
# =============================================================================

def encode_sectors_to_flux_gw(
    cylinder: int,
    head: int,
    sectors: List[SectorData],
    sample_freq: int = 72_000_000
) -> FluxData:
    """
    Encode sectors to flux using Greaseweazle-compatible algorithm.

    This is the recommended function for encoding sectors for writing.
    """
    return encode_mfm_track(cylinder, head, sectors, sample_freq=sample_freq)


def decode_flux_to_sectors_gw(flux_data: FluxData) -> List[SectorData]:
    """
    Decode flux to sectors using Greaseweazle-compatible algorithm.

    This is the recommended function for decoding flux after reading.
    """
    return decode_mfm_track(flux_data)


__all__ = [
    'encode_mfm_track',
    'decode_mfm_track',
    'encode_sectors_to_flux_gw',
    'decode_flux_to_sectors_gw',
    'flux_to_bits_pll',
    'encode',
    'decode',
    'mfm_encode',
    'Mark',
]
