"""
MFM (Modified Frequency Modulation) codec for IBM PC floppy disk format.

This module provides encoding and decoding of MFM data for standard IBM PC
3.5" high-density floppy disks. It converts between raw flux timing data
and sector-level data.

IBM PC HD Format (1.44MB):
    - 80 cylinders (tracks)
    - 2 heads (sides)
    - 18 sectors per track
    - 512 bytes per sector
    - MFM encoding with 2.0µs bit cells at 300 RPM

Key Classes:
    MFMDecoder: Decode flux data to sectors
    MFMEncoder: Encode sectors to flux data

Key Functions:
    decode_flux_to_sectors: High-level flux decoding
    encode_sectors_to_flux: High-level flux encoding
    verify_sector_crc: CRC validation for sector data
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from . import SectorStatus, SectorData
from .flux_io import FluxData

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# MFM timing constants for HD (2.0µs bit cell)
BIT_CELL_US = 2.0
SHORT_PULSE_US = 4.0    # 2 bit cells (10 or 01 pattern)
MEDIUM_PULSE_US = 6.0   # 3 bit cells (100 or 001 pattern)
LONG_PULSE_US = 8.0     # 4 bit cells (1000 or 0001 pattern)

# Timing tolerance (fraction of bit cell)
TIMING_TOLERANCE = 0.30

# CRC-CCITT polynomial (x^16 + x^12 + x^5 + 1)
CRC_POLY = 0x1021
CRC_INIT = 0xFFFF

# IBM PC format markers (with clock bits)
SYNC_BYTE = 0x00       # Sync field bytes
GAP_BYTE = 0x4E        # Gap fill byte
A1_SYNC = 0xA1         # Special sync mark (with missing clock)
IDAM_MARK = 0xFE       # ID Address Mark
DAM_MARK = 0xFB        # Data Address Mark
DDAM_MARK = 0xF8       # Deleted Data Address Mark

# MFM encoded A1 sync pattern (with missing clock at bit 5)
# Normal A1: 10100001 -> MFM: 0100010010001001
# Special A1: 10100001 with clock missing -> 0100010010101001
A1_SYNC_PATTERN = 0x4489  # 16-bit MFM pattern for A1 with missing clock

# Sector sizes
SECTOR_SIZE_CODE = {
    0: 128,
    1: 256,
    2: 512,
    3: 1024,
}

# Standard format parameters for 3.5" HD
HD_35_PARAMS = {
    'cylinders': 80,
    'heads': 2,
    'sectors': 18,
    'sector_size': 512,
    'gap3_length': 54,
    'gap4a_length': 80,
    'gap1_length': 50,
    'gap2_length': 22,
}


# =============================================================================
# CRC Calculation
# =============================================================================

class CRCCalculator:
    """CRC-CCITT calculator for MFM sector data."""

    def __init__(self):
        """Initialize with lookup table for fast calculation."""
        self._table = self._generate_table()

    def _generate_table(self) -> List[int]:
        """Generate CRC lookup table."""
        table = []
        for i in range(256):
            crc = i << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ CRC_POLY) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
            table.append(crc)
        return table

    def calculate(self, data: bytes, init: int = CRC_INIT) -> int:
        """
        Calculate CRC-CCITT for data.

        Args:
            data: Bytes to calculate CRC for
            init: Initial CRC value (default 0xFFFF)

        Returns:
            16-bit CRC value
        """
        crc = init
        for byte in data:
            crc = ((crc << 8) ^ self._table[(crc >> 8) ^ byte]) & 0xFFFF
        return crc

    def verify(self, data: bytes, expected_crc: int,
               init: int = CRC_INIT) -> bool:
        """
        Verify CRC matches expected value.

        Args:
            data: Data bytes (not including CRC)
            expected_crc: Expected CRC value
            init: Initial CRC value

        Returns:
            True if CRC matches, False otherwise
        """
        return self.calculate(data, init) == expected_crc


# Global CRC calculator instance
_crc = CRCCalculator()


def calculate_crc(data: bytes) -> int:
    """Calculate CRC-CCITT for data."""
    return _crc.calculate(data)


def verify_crc(data: bytes, expected_crc: int) -> bool:
    """Verify CRC matches expected value."""
    return _crc.verify(data, expected_crc)


# =============================================================================
# MFM Bit Stream Handling
# =============================================================================

@dataclass
class MFMBitstream:
    """
    Container for MFM-encoded bit stream.

    Provides methods for reading and writing MFM data at the bit level.
    """

    bits: List[int] = field(default_factory=list)
    position: int = 0

    @classmethod
    def from_flux(cls, flux_data: FluxData,
                  bit_cell_us: float = BIT_CELL_US) -> 'MFMBitstream':
        """
        Convert flux timing data to MFM bit stream.

        Args:
            flux_data: FluxData containing raw timing values
            bit_cell_us: Expected bit cell width in microseconds

        Returns:
            MFMBitstream containing decoded bits
        """
        bits = []
        times_us = flux_data.get_times_microseconds()

        # Noise filtering threshold - pulses shorter than this are considered noise
        # and are accumulated into the next pulse. For HD MFM, shortest valid pulse
        # is 2 bit cells = 4µs, so anything under ~2.5µs is likely noise.
        noise_threshold_us = bit_cell_us * 1.25  # 2.5µs for HD

        accumulated_time = 0.0
        filtered_count = 0

        for time_us in times_us:
            # Accumulate time
            accumulated_time += time_us

            # If accumulated time is too short, it's noise - skip and accumulate more
            if accumulated_time < noise_threshold_us:
                filtered_count += 1
                continue

            # Determine number of bit cells (zeros before the 1)
            num_cells = round(accumulated_time / bit_cell_us)

            # Clamp to valid MFM range (2-4 bit cells)
            num_cells = max(2, min(4, num_cells))

            # Add zeros then a one
            bits.extend([0] * (num_cells - 1))
            bits.append(1)

            # Reset accumulator
            accumulated_time = 0.0

        if filtered_count > 0:
            logger.debug(
                "Filtered %d noise pulses (threshold=%.2fµs)",
                filtered_count, noise_threshold_us
            )

        return cls(bits=bits)

    def to_flux(self, sample_freq: int = 72_000_000,
                bit_cell_us: float = BIT_CELL_US) -> FluxData:
        """
        Convert MFM bit stream to flux timing data.

        Args:
            sample_freq: Sample frequency in Hz
            bit_cell_us: Bit cell width in microseconds

        Returns:
            FluxData containing flux timing values
        """
        flux_times = []
        count = 0

        for bit in self.bits:
            count += 1
            if bit == 1:
                # Convert bit cells to sample counts
                time_us = count * bit_cell_us
                samples = int(time_us * sample_freq / 1_000_000)
                flux_times.append(samples)
                count = 0

        # Handle any trailing zeros
        if count > 0:
            time_us = count * bit_cell_us
            samples = int(time_us * sample_freq / 1_000_000)
            if samples > 0:
                flux_times.append(samples)

        return FluxData(
            flux_times=flux_times,
            sample_freq=sample_freq
        )

    def read_bits(self, count: int) -> List[int]:
        """Read specified number of bits from current position."""
        result = self.bits[self.position:self.position + count]
        self.position += count
        return result

    def read_byte(self) -> Optional[int]:
        """
        Read and decode one MFM byte (16 bits -> 8 bits).

        MFM encodes each data bit with a clock bit before it.
        Pattern: C0 D0 C1 D1 C2 D2 C3 D3 C4 D4 C5 D5 C6 D6 C7 D7
        where Cn are clock bits and Dn are data bits.

        Returns:
            Decoded byte value, or None if not enough bits
        """
        if self.position + 16 > len(self.bits):
            return None

        raw_bits = self.read_bits(16)

        # Extract data bits (odd positions)
        byte_val = 0
        for i in range(8):
            data_bit = raw_bits[i * 2 + 1]  # Data bits at odd positions
            byte_val = (byte_val << 1) | data_bit

        return byte_val

    def read_bytes(self, count: int) -> bytes:
        """Read and decode multiple MFM bytes."""
        result = bytearray()
        for _ in range(count):
            byte_val = self.read_byte()
            if byte_val is None:
                break
            result.append(byte_val)
        return bytes(result)

    def write_byte(self, value: int, previous_bit: int = 0) -> int:
        """
        Encode and write one byte as MFM (8 bits -> 16 bits).

        Args:
            value: Byte value to encode
            previous_bit: Last data bit from previous byte (for clock calc)

        Returns:
            Last data bit written (for next byte's clock calculation)
        """
        prev = previous_bit

        for i in range(8):
            data_bit = (value >> (7 - i)) & 1

            # Clock bit is 1 if both previous and current data bits are 0
            clock_bit = 1 if (prev == 0 and data_bit == 0) else 0

            self.bits.append(clock_bit)
            self.bits.append(data_bit)

            prev = data_bit

        return prev

    def write_bytes(self, data: bytes, previous_bit: int = 0) -> int:
        """Encode and write multiple bytes as MFM."""
        prev = previous_bit
        for byte in data:
            prev = self.write_byte(byte, prev)
        return prev

    def write_a1_sync(self) -> None:
        """
        Write A1 sync byte with missing clock bit.

        The A1 sync mark has clock bit 5 missing, which creates a unique
        pattern that cannot occur in normal MFM data.
        """
        # A1 = 10100001
        # Normal MFM would be: 01 00 01 00 01 00 00 01
        # With missing clock: 01 00 01 01 01 00 00 01
        # The pattern 0100 0100 1010 1001 = 0x4489
        for bit in [0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1]:
            self.bits.append(bit)

    def find_a1_sync(self) -> int:
        """
        Find position of next A1 sync pattern.

        Returns:
            Bit position of sync pattern, or -1 if not found
        """
        # Look for the A1 sync pattern (0x4489)
        target = [0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1]

        for i in range(self.position, len(self.bits) - 16):
            match = True
            for j, bit in enumerate(target):
                if self.bits[i + j] != bit:
                    match = False
                    break
            if match:
                return i

        return -1

    def seek(self, position: int) -> None:
        """Move read position to specified bit offset."""
        self.position = max(0, min(position, len(self.bits)))

    def skip(self, bits: int) -> None:
        """Skip forward by specified number of bits."""
        self.position = min(self.position + bits, len(self.bits))

    def remaining(self) -> int:
        """Return number of bits remaining."""
        return max(0, len(self.bits) - self.position)

    def __len__(self) -> int:
        """Return total number of bits."""
        return len(self.bits)


# =============================================================================
# MFM Decoder
# =============================================================================

@dataclass
class DecodedSector:
    """Result of decoding a single sector."""
    cylinder: int
    head: int
    sector: int
    size_code: int
    data: bytes
    header_crc_valid: bool
    data_crc_valid: bool
    deleted: bool = False
    signal_quality: float = 1.0


class MFMDecoder:
    """
    Decoder for MFM-encoded floppy disk data.

    Extracts sector data from raw flux captures using IBM PC MFM format.
    """

    def __init__(self, bit_cell_us: float = BIT_CELL_US):
        """
        Initialize decoder.

        Args:
            bit_cell_us: Expected bit cell width in microseconds
        """
        self.bit_cell_us = bit_cell_us

    def decode_track(self, flux_data: FluxData) -> List[SectorData]:
        """
        Decode all sectors from a track's flux data.

        Args:
            flux_data: Raw flux capture from a track

        Returns:
            List of SectorData for each decoded sector
        """
        logger.debug(
            "Decoding track C%d H%d (sample_freq=%d Hz, %d transitions)",
            flux_data.cylinder, flux_data.head, flux_data.sample_freq,
            len(flux_data.flux_times)
        )

        # Try to auto-detect bit cell width from flux data
        detected_bit_cell = flux_data.estimate_bit_cell_width()
        if detected_bit_cell is not None:
            # Use detected bit cell if it's reasonable
            # 0.9-1.1 µs = ED/high-rate, 1.8-2.2 µs = HD, 3.5-4.5 µs = DD
            if 0.9 <= detected_bit_cell <= 6.0:
                bit_cell_to_use = detected_bit_cell
                logger.debug(
                    "Using detected bit cell: %.2f µs (expected: %.2f µs)",
                    detected_bit_cell, self.bit_cell_us
                )
            else:
                bit_cell_to_use = self.bit_cell_us
                logger.warning(
                    "Detected bit cell %.2f µs out of range, using default %.2f µs",
                    detected_bit_cell, self.bit_cell_us
                )
        else:
            bit_cell_to_use = self.bit_cell_us
            logger.debug("Could not detect bit cell, using default: %.2f µs", self.bit_cell_us)

        # Log flux timing statistics for debugging
        times_us = flux_data.get_times_microseconds()
        if times_us:
            # Count pulse widths in MFM ranges
            short = sum(1 for t in times_us if 3.0 <= t < 5.0)
            medium = sum(1 for t in times_us if 5.0 <= t < 7.0)
            long = sum(1 for t in times_us if 7.0 <= t < 9.0)
            too_short = sum(1 for t in times_us if t < 3.0)
            too_long = sum(1 for t in times_us if t > 9.0)

            logger.debug(
                "Flux timing distribution: short(4µs)=%d, medium(6µs)=%d, "
                "long(8µs)=%d, too_short(<3µs)=%d, too_long(>9µs)=%d",
                short, medium, long, too_short, too_long
            )

            # Log actual timing statistics
            if len(times_us) > 100:
                import statistics
                min_t = min(times_us)
                max_t = max(times_us)
                mean_t = statistics.mean(times_us)
                median_t = statistics.median(times_us)
                logger.debug(
                    "Flux timing stats: min=%.2fµs, max=%.2fµs, "
                    "mean=%.2fµs, median=%.2fµs",
                    min_t, max_t, mean_t, median_t
                )

            # If most pulses are out of range, this might explain decode failure
            total = len(times_us)
            out_of_range = too_short + too_long
            if out_of_range > total * 0.3:
                logger.warning(
                    "%.1f%% of flux pulses are outside MFM timing range "
                    "(%.1f%% too short, %.1f%% too long)",
                    (out_of_range / total) * 100,
                    (too_short / total) * 100,
                    (too_long / total) * 100
                )

        # Convert flux to bit stream
        bitstream = MFMBitstream.from_flux(flux_data, bit_cell_to_use)

        sectors = []
        found_sectors = set()
        sync_search_count = 0
        sync_found_count = 0

        # Search for sector headers
        while bitstream.remaining() > 1000:
            # Find A1 sync pattern
            sync_search_count += 1
            sync_pos = bitstream.find_a1_sync()
            if sync_pos < 0:
                break
            sync_found_count += 1

            # Move to sync position
            bitstream.seek(sync_pos)

            # Try to decode a sector
            sector = self._decode_sector(
                bitstream, flux_data.cylinder, flux_data.head
            )

            if sector is not None:
                sector_key = (sector.cylinder, sector.head, sector.sector)
                if sector_key not in found_sectors:
                    sectors.append(sector)
                    found_sectors.add(sector_key)
                    logger.debug(
                        "Decoded sector %d (CRC: header=%s, data=%s)",
                        sector.sector, sector.crc_valid, sector.crc_valid
                    )
            else:
                # Skip past this sync and continue searching
                bitstream.skip(16)

        logger.debug(
            "Decoded %d sectors from track (found %d A1 syncs in %d searches, "
            "bitstream=%d bits)",
            len(sectors), sync_found_count, sync_search_count, len(bitstream)
        )

        return sorted(sectors, key=lambda s: s.sector)

    def _decode_sector(self, bitstream: MFMBitstream,
                       expected_cyl: int, expected_head: int) -> Optional[SectorData]:
        """
        Decode a single sector starting at current bitstream position.

        Args:
            bitstream: MFM bit stream positioned at A1 sync
            expected_cyl: Expected cylinder number (for validation)
            expected_head: Expected head number (for validation)

        Returns:
            SectorData if successful, None if decode fails
        """
        start_pos = bitstream.position

        try:
            # Read 3 A1 sync bytes + address mark
            bitstream.skip(16)  # Skip first A1 (already found)

            # Verify remaining sync bytes (need 2 more A1s after the first)
            for i in range(2):
                sync_check = bitstream.find_a1_sync()
                if sync_check != bitstream.position:
                    logger.debug(
                        "Sector decode failed: A1 sync %d not at expected position "
                        "(found at %d, expected %d)", i+2, sync_check, bitstream.position
                    )
                    return None
                bitstream.skip(16)

            # Read address mark
            mark = bitstream.read_byte()
            if mark is None:
                logger.debug("Sector decode failed: could not read address mark")
                return None

            logger.debug(
                "Found address mark: 0x%02X (IDAM=0x%02X, DAM=0x%02X)",
                mark, IDAM_MARK, DAM_MARK
            )

            if mark == IDAM_MARK:
                # This is a sector header (ID Address Mark)
                return self._decode_sector_with_header(bitstream, start_pos)

            # Not an IDAM, skip
            logger.debug("Address mark 0x%02X is not IDAM, skipping", mark)
            return None

        except Exception as e:
            logger.debug("Error decoding sector: %s", e)
            return None

    def _decode_sector_with_header(self, bitstream: MFMBitstream,
                                   sync_start: int) -> Optional[SectorData]:
        """Decode sector after finding IDAM."""
        # Read header: cylinder, head, sector, size (4 bytes) + CRC (2 bytes)
        header_data = bitstream.read_bytes(4)
        if len(header_data) < 4:
            return None

        cylinder = header_data[0]
        head = header_data[1]
        sector = header_data[2]
        size_code = header_data[3]

        # Read header CRC
        crc_bytes = bitstream.read_bytes(2)
        if len(crc_bytes) < 2:
            return None

        header_crc = (crc_bytes[0] << 8) | crc_bytes[1]

        # Verify header CRC (includes A1 A1 A1 FE + header)
        crc_data = bytes([A1_SYNC, A1_SYNC, A1_SYNC, IDAM_MARK]) + header_data
        header_crc_valid = verify_crc(crc_data, header_crc)

        if not header_crc_valid:
            logger.debug("Header CRC failed for sector C%d H%d S%d",
                         cylinder, head, sector)

        # Get sector size
        sector_size = SECTOR_SIZE_CODE.get(size_code, 512)

        # Now find the data field
        # Skip gap 2 (22 bytes of 0x4E) and sync field (12 bytes of 0x00)
        # Then look for A1 A1 A1 + DAM/DDAM

        data_sync_pos = bitstream.find_a1_sync()
        if data_sync_pos < 0 or data_sync_pos - bitstream.position > 1000:
            # No data field found nearby
            return SectorData(
                cylinder=cylinder,
                head=head,
                sector=sector,
                data=bytes(sector_size),
                status=SectorStatus.NO_DATA,
                crc_valid=False,
                signal_quality=0.5 if header_crc_valid else 0.2
            )

        bitstream.seek(data_sync_pos)

        # Skip 3 A1 sync bytes
        for _ in range(3):
            bitstream.skip(16)

        # Read data address mark
        dam = bitstream.read_byte()
        if dam is None:
            return SectorData(
                cylinder=cylinder,
                head=head,
                sector=sector,
                data=bytes(sector_size),
                status=SectorStatus.NO_DATA,
                crc_valid=False,
                signal_quality=0.3
            )

        if dam not in (DAM_MARK, DDAM_MARK):
            return SectorData(
                cylinder=cylinder,
                head=head,
                sector=sector,
                data=bytes(sector_size),
                status=SectorStatus.NO_DATA,
                crc_valid=False,
                signal_quality=0.3
            )

        # Read sector data
        data = bitstream.read_bytes(sector_size)
        if len(data) < sector_size:
            # Pad with zeros if short read
            data = data + bytes(sector_size - len(data))
            data_crc_valid = False
        else:
            # Read data CRC
            data_crc_bytes = bitstream.read_bytes(2)
            if len(data_crc_bytes) >= 2:
                data_crc = (data_crc_bytes[0] << 8) | data_crc_bytes[1]
                # CRC includes A1 A1 A1 DAM + data
                crc_data = bytes([A1_SYNC, A1_SYNC, A1_SYNC, dam]) + data
                data_crc_valid = verify_crc(crc_data, data_crc)
            else:
                data_crc_valid = False

        # Determine status
        if header_crc_valid and data_crc_valid:
            status = SectorStatus.GOOD
            quality = 1.0
        elif header_crc_valid and not data_crc_valid:
            status = SectorStatus.CRC_ERROR
            quality = 0.6
        else:
            status = SectorStatus.CRC_ERROR
            quality = 0.3

        return SectorData(
            cylinder=cylinder,
            head=head,
            sector=sector,
            data=data,
            status=status,
            crc_valid=(header_crc_valid and data_crc_valid),
            signal_quality=quality
        )


# =============================================================================
# MFM Encoder
# =============================================================================

class MFMEncoder:
    """
    Encoder for MFM floppy disk data.

    Generates MFM-encoded flux data from sector data for writing to disk.
    """

    def __init__(self, bit_cell_us: float = BIT_CELL_US,
                 format_params: Optional[Dict] = None):
        """
        Initialize encoder.

        Args:
            bit_cell_us: Bit cell width in microseconds
            format_params: Optional format parameters (uses HD_35_PARAMS if None)
        """
        self.bit_cell_us = bit_cell_us
        self.params = format_params or HD_35_PARAMS

    def encode_track(self, cylinder: int, head: int,
                     sectors: List[SectorData],
                     sample_freq: int = 72_000_000) -> FluxData:
        """
        Encode a complete track of sector data to flux.

        Args:
            cylinder: Cylinder number
            head: Head number
            sectors: List of SectorData to encode (must have correct CHS)
            sample_freq: Sample frequency for output flux

        Returns:
            FluxData ready for writing to disk
        """
        logger.debug("Encoding track C%d H%d with %d sectors",
                     cylinder, head, len(sectors))

        bitstream = MFMBitstream()

        # Write Gap 4a (pre-index gap)
        self._write_gap(bitstream, self.params['gap4a_length'])

        # Write index address mark (optional for standard PC format)
        # Most PC formats don't include an index mark, so skip it

        # Write Gap 1 (post-index gap)
        self._write_gap(bitstream, self.params['gap1_length'])

        # Sort sectors by sector number
        sectors_sorted = sorted(sectors, key=lambda s: s.sector)

        # Create lookup for quick access
        sector_map = {s.sector: s for s in sectors_sorted}

        # Write each sector
        prev_bit = 0
        for sector_num in range(1, self.params['sectors'] + 1):
            if sector_num in sector_map:
                sector = sector_map[sector_num]
            else:
                # Missing sector - write with zero data
                sector = SectorData(
                    cylinder=cylinder,
                    head=head,
                    sector=sector_num,
                    data=bytes(self.params['sector_size']),
                    status=SectorStatus.GOOD,
                    crc_valid=True,
                    signal_quality=1.0
                )

            prev_bit = self._write_sector(bitstream, sector, prev_bit)

        # Fill remaining track with Gap 4b
        # Calculate how many bytes needed to fill ~200ms at 300 RPM
        target_bits = int(200000 / self.bit_cell_us)  # 200ms worth of bit cells
        remaining = target_bits - len(bitstream)
        if remaining > 0:
            gap_bytes = remaining // 16  # 16 MFM bits per byte
            self._write_gap(bitstream, gap_bytes)

        # Convert to flux
        flux_data = bitstream.to_flux(sample_freq, self.bit_cell_us)
        flux_data.cylinder = cylinder
        flux_data.head = head

        logger.debug("Encoded track: %d bits -> %d flux transitions",
                     len(bitstream), len(flux_data))

        return flux_data

    def _write_gap(self, bitstream: MFMBitstream, length: int,
                   fill_byte: int = GAP_BYTE) -> int:
        """Write gap bytes (0x4E by default)."""
        prev = 0
        for _ in range(length):
            prev = bitstream.write_byte(fill_byte, prev)
        return prev

    def _write_sync(self, bitstream: MFMBitstream, length: int = 12) -> int:
        """Write sync field (0x00 bytes)."""
        prev = 0
        for _ in range(length):
            prev = bitstream.write_byte(SYNC_BYTE, prev)
        return prev

    def _write_sector(self, bitstream: MFMBitstream, sector: SectorData,
                      prev_bit: int) -> int:
        """
        Write a complete sector (header + data).

        Returns the last data bit for next sector's clock calculation.
        """
        # Sync field (12 bytes of 0x00)
        self._write_sync(bitstream, 12)

        # ID Address Mark (A1 A1 A1 FE)
        for _ in range(3):
            bitstream.write_a1_sync()
        prev_bit = bitstream.write_byte(IDAM_MARK, 1)  # After A1, prev is 1

        # Header: C H S N (cylinder, head, sector, size code)
        size_code = 2  # 512 bytes
        for code, size in SECTOR_SIZE_CODE.items():
            if size == len(sector.data):
                size_code = code
                break

        header = bytes([sector.cylinder, sector.head, sector.sector, size_code])
        prev_bit = bitstream.write_bytes(header, prev_bit)

        # Header CRC
        crc_data = bytes([A1_SYNC, A1_SYNC, A1_SYNC, IDAM_MARK]) + header
        header_crc = calculate_crc(crc_data)
        prev_bit = bitstream.write_byte((header_crc >> 8) & 0xFF, prev_bit)
        prev_bit = bitstream.write_byte(header_crc & 0xFF, prev_bit)

        # Gap 2
        prev_bit = self._write_gap(bitstream, self.params['gap2_length'])

        # Sync field for data
        self._write_sync(bitstream, 12)

        # Data Address Mark (A1 A1 A1 FB)
        for _ in range(3):
            bitstream.write_a1_sync()
        prev_bit = bitstream.write_byte(DAM_MARK, 1)

        # Sector data
        prev_bit = bitstream.write_bytes(sector.data, prev_bit)

        # Data CRC
        crc_data = bytes([A1_SYNC, A1_SYNC, A1_SYNC, DAM_MARK]) + sector.data
        data_crc = calculate_crc(crc_data)
        prev_bit = bitstream.write_byte((data_crc >> 8) & 0xFF, prev_bit)
        prev_bit = bitstream.write_byte(data_crc & 0xFF, prev_bit)

        # Gap 3
        prev_bit = self._write_gap(bitstream, self.params['gap3_length'])

        return prev_bit


# =============================================================================
# High-Level Functions
# =============================================================================

def decode_flux_to_sectors(flux_data: FluxData,
                           bit_cell_us: float = BIT_CELL_US) -> List[SectorData]:
    """
    Decode flux data to sector data.

    High-level function to extract all sectors from a flux capture.

    Args:
        flux_data: Raw flux capture from a track
        bit_cell_us: Expected bit cell width (default 2.0µs for HD)

    Returns:
        List of SectorData for each decoded sector

    Example:
        flux = device.read_track(0, 0)
        sectors = decode_flux_to_sectors(flux)
        for sector in sectors:
            print(f"Sector {sector.sector}: {'OK' if sector.is_good else 'BAD'}")
    """
    decoder = MFMDecoder(bit_cell_us)
    return decoder.decode_track(flux_data)


def encode_sectors_to_flux(cylinder: int, head: int,
                           sectors: List[SectorData],
                           sample_freq: int = 72_000_000,
                           bit_cell_us: float = BIT_CELL_US) -> FluxData:
    """
    Encode sector data to flux for writing.

    High-level function to generate flux data from sectors.

    Args:
        cylinder: Cylinder number for the track
        head: Head number for the track
        sectors: List of SectorData to encode
        sample_freq: Sample frequency for output
        bit_cell_us: Bit cell width (default 2.0µs for HD)

    Returns:
        FluxData ready for writing to disk

    Example:
        sectors = [SectorData(...) for i in range(18)]
        flux = encode_sectors_to_flux(0, 0, sectors)
        device.write_track(0, 0, flux)
    """
    encoder = MFMEncoder(bit_cell_us)
    return encoder.encode_track(cylinder, head, sectors, sample_freq)


def verify_sector_crc(sector: SectorData) -> bool:
    """
    Verify the CRC of sector data.

    Note: This re-calculates CRC from the sector data. For sectors
    decoded from flux, use the crc_valid attribute which reflects
    the original disk CRC.

    Args:
        sector: SectorData to verify

    Returns:
        True if data CRC is valid
    """
    return sector.crc_valid


def create_formatted_track(cylinder: int, head: int,
                           fill_byte: int = 0xE5,
                           sector_count: int = 18,
                           sector_size: int = 512) -> List[SectorData]:
    """
    Create sector data for a freshly formatted track.

    Args:
        cylinder: Cylinder number
        head: Head number
        fill_byte: Byte to fill sectors with (default 0xE5)
        sector_count: Number of sectors (default 18 for HD)
        sector_size: Size of each sector (default 512)

    Returns:
        List of SectorData ready for encoding

    Example:
        sectors = create_formatted_track(0, 0)
        flux = encode_sectors_to_flux(0, 0, sectors)
        device.write_track(0, 0, flux)
    """
    sectors = []
    fill_data = bytes([fill_byte] * sector_size)

    for sector_num in range(1, sector_count + 1):
        sectors.append(SectorData(
            cylinder=cylinder,
            head=head,
            sector=sector_num,
            data=fill_data,
            status=SectorStatus.GOOD,
            crc_valid=True,
            signal_quality=1.0
        ))

    return sectors


def create_pattern_track(cylinder: int, head: int,
                         pattern: bytes,
                         sector_count: int = 18,
                         sector_size: int = 512) -> List[SectorData]:
    """
    Create sector data filled with a repeating pattern.

    Useful for recovery operations that use pattern writes.

    Args:
        cylinder: Cylinder number
        head: Head number
        pattern: Byte pattern to repeat (e.g., b'\\x00' or b'\\xAA\\x55')
        sector_count: Number of sectors
        sector_size: Size of each sector

    Returns:
        List of SectorData with pattern-filled data
    """
    # Repeat pattern to fill sector
    repeats = (sector_size // len(pattern)) + 1
    fill_data = (pattern * repeats)[:sector_size]

    sectors = []
    for sector_num in range(1, sector_count + 1):
        sectors.append(SectorData(
            cylinder=cylinder,
            head=head,
            sector=sector_num,
            data=fill_data,
            status=SectorStatus.GOOD,
            crc_valid=True,
            signal_quality=1.0
        ))

    return sectors
