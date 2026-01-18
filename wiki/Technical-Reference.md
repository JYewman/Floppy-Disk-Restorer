# Technical Reference

Detailed technical information for advanced users and developers.

## Table of Contents

- [MFM Encoding](#mfm-encoding)
- [Flux Timing](#flux-timing)
- [Track Structure](#track-structure)
- [CRC Calculation](#crc-calculation)
- [PLL Parameters](#pll-parameters)
- [Signal Quality Metrics](#signal-quality-metrics)
- [Data Structures](#data-structures)
- [File Formats](#file-formats)

---

## MFM Encoding

### Encoding Rules

Modified Frequency Modulation (MFM) encoding:

```
Data bit:     0                    1
              │                    │
MFM pattern:  Clock if prev=0      No clock, Data pulse
              No data pulse        │
              │                    │
              ▼                    ▼
Prev=0:      10                   01
Prev=1:      00                   01
```

### Encoding Table

| Previous Bit | Current Bit | MFM Output |
|--------------|-------------|------------|
| 0 | 0 | 10 |
| 0 | 1 | 01 |
| 1 | 0 | 00 |
| 1 | 1 | 01 |

### Pulse Types

| Name | MFM Pattern | Time (HD) | Time (DD) |
|------|-------------|-----------|-----------|
| **2T (Short)** | 10 or 01 | 4 µs | 8 µs |
| **3T (Medium)** | 100 or 001 | 6 µs | 12 µs |
| **4T (Long)** | 1000 or 0001 | 8 µs | 16 µs |

### Example Encoding

```
Data:        1  0  1  1  0  0  1  0
             │  │  │  │  │  │  │  │
MFM bits:   01 00 01 01 10 10 01 00
             │  │  │  │  │  │  │  │
Pulses:     T    T  T  T     T    T
            2T  2T 2T 2T 4T  2T 3T
```

---

## Flux Timing

### Greaseweazle Specifications

| Parameter | Value |
|-----------|-------|
| **Sample Clock** | 72 MHz |
| **Sample Period** | 13.89 ns |
| **Timer Resolution** | 16-bit or 32-bit |
| **Max Flux Time** | ~0.9 ms (16-bit) or ~59 s (32-bit) |

### Converting Flux Times

```python
# Flux time to microseconds
time_us = flux_ticks * (1_000_000 / sample_freq)

# Example: 72 MHz sample rate
time_us = flux_ticks * (1_000_000 / 72_000_000)
time_us = flux_ticks / 72

# For a 2T pulse (HD): ~4µs = ~288 ticks
```

### Timing Tables

#### High Density (HD) - 500 Kbps

| Pulse | Bit Cells | Time (µs) | Ticks (72MHz) |
|-------|-----------|-----------|---------------|
| 2T | 2 | 4.0 | 288 |
| 3T | 3 | 6.0 | 432 |
| 4T | 4 | 8.0 | 576 |

#### Double Density (DD) - 250 Kbps

| Pulse | Bit Cells | Time (µs) | Ticks (72MHz) |
|-------|-----------|-----------|---------------|
| 2T | 2 | 8.0 | 576 |
| 3T | 3 | 12.0 | 864 |
| 4T | 4 | 16.0 | 1152 |

### Bit Cell Calculation

```python
# Bit cell period
bit_cell_us = 1_000_000 / (data_rate_bps * 2)

# HD: 500 Kbps
bit_cell_hd = 1_000_000 / (500_000 * 2) = 1.0 µs

# MFM bit cell (2 clock periods)
mfm_bit_cell_hd = 2.0 µs

# DD: 250 Kbps
mfm_bit_cell_dd = 4.0 µs
```

---

## Track Structure

### IBM MFM Track Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ GAP4a │ SYNC │ IAM │ GAP1 │ Sector 1 │ GAP3 │ ... │ Sector N │ GAP4b │
└──────────────────────────────────────────────────────────────────────┘
```

### Track Components

| Component | Bytes | Content | Purpose |
|-----------|-------|---------|---------|
| **GAP4a** | 80 | 0x4E | Pre-index gap |
| **SYNC** | 12 | 0x00 | Synchronization |
| **IAM** | 4 | 0xC2 C2 C2 FC | Index Address Mark |
| **GAP1** | 50 | 0x4E | Post-index gap |
| **GAP3** | 54-84 | 0x4E | Inter-sector gap |
| **GAP4b** | Variable | 0x4E | Post-data gap |

### Sector Structure

```
┌───────────────────────────────────────────────────────────────────┐
│ SYNC │ IDAM │ C │ H │ R │ N │ CRC │ GAP2 │ SYNC │ DAM │ Data │ CRC │
└───────────────────────────────────────────────────────────────────┘
```

| Field | Bytes | Content | Description |
|-------|-------|---------|-------------|
| **SYNC** | 12 | 0x00 | Synchronization |
| **IDAM** | 4 | 0xA1 A1 A1 FE | ID Address Mark |
| **C** | 1 | 0-255 | Cylinder number |
| **H** | 1 | 0-1 | Head number |
| **R** | 1 | 1-255 | Record (sector) number |
| **N** | 1 | 0-7 | Sector size code |
| **CRC** | 2 | CRC-16 | Header CRC |
| **GAP2** | 22 | 0x4E/0x00 | ID-to-data gap |
| **DAM** | 4 | 0xA1 A1 A1 FB | Data Address Mark |
| **Data** | 128-8192 | User data | Sector data |
| **CRC** | 2 | CRC-16 | Data CRC |

### Sector Size Codes

| N Value | Sector Size (bytes) |
|---------|---------------------|
| 0 | 128 |
| 1 | 256 |
| 2 | 512 |
| 3 | 1024 |
| 4 | 2048 |
| 5 | 4096 |
| 6 | 8192 |

### Address Marks (with MFM clock)

| Mark | Data Pattern | With Missing Clock |
|------|--------------|-------------------|
| **IAM** | C2 C2 C2 FC | A1* A1* A1* FC |
| **IDAM** | A1 A1 A1 FE | A1* A1* A1* FE |
| **DAM** | A1 A1 A1 FB | A1* A1* A1* FB |
| **DDAM** | A1 A1 A1 F8 | A1* A1* A1* F8 |

*A1 with missing clock bit (violation of MFM rules, used for sync)

---

## CRC Calculation

### CRC-16-CCITT

Used for IBM MFM format:

| Parameter | Value |
|-----------|-------|
| **Polynomial** | 0x1021 (x¹⁶ + x¹² + x⁵ + 1) |
| **Initial Value** | 0xFFFF |
| **Final XOR** | 0x0000 |
| **Bit Order** | MSB first |

### CRC Calculation Code

```python
def crc16_ccitt(data: bytes) -> int:
    """Calculate CRC-16-CCITT for IBM MFM format."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc
```

### CRC Coverage

| CRC | Covers |
|-----|--------|
| **Header CRC** | IDAM + C + H + R + N |
| **Data CRC** | DAM + 512 bytes data |

---

## PLL Parameters

### Phase-Locked Loop Decoder

The PLL tracks timing variations to decode flux data.

### Parameters

| Parameter | Symbol | Range | Default | Description |
|-----------|--------|-------|---------|-------------|
| **Bit Cell** | T | 1.5-2.5 µs | 2.0 µs | Expected bit cell period |
| **Period Adj** | α | 0.01-0.15 | 0.05 | Speed tracking rate |
| **Phase Adj** | β | 0.2-0.9 | 0.6 | Phase tracking rate |

### PLL Algorithm

```python
def pll_decode(flux_times, bit_cell_ns, period_adj, phase_adj):
    """
    Phase-Locked Loop decoder for MFM flux data.
    """
    clock = bit_cell_ns  # Current clock period estimate
    phase = 0            # Current phase offset
    bits = []

    for flux_time in flux_times:
        # Calculate time since last clock
        time_since_clock = flux_time - phase

        # Determine number of bit cells
        cells = round(time_since_clock / clock)
        cells = max(2, min(4, cells))  # Clamp to valid range

        # Output bits (MFM decoding)
        bits.extend([0] * (cells - 1) + [1])

        # Update phase (where we think the clock is)
        expected_time = cells * clock
        phase_error = flux_time - (phase + expected_time)
        phase = phase + expected_time + (phase_error * phase_adj)

        # Update clock period estimate
        cell_time = flux_time / cells
        clock_error = cell_time - clock
        clock = clock + (clock_error * period_adj)

    return bits
```

### Tuning Guidelines

| Scenario | Period Adj | Phase Adj |
|----------|------------|-----------|
| **Good disk** | 0.03-0.05 | 0.5-0.6 |
| **Speed variation** | 0.05-0.10 | 0.5-0.6 |
| **Jittery data** | 0.03-0.05 | 0.6-0.8 |
| **Weak signal** | 0.02-0.04 | 0.4-0.5 |

---

## Signal Quality Metrics

### Signal-to-Noise Ratio (SNR)

```python
def calculate_snr(flux_times):
    """
    Calculate SNR from flux timing data.
    """
    # Separate pulse types by timing
    pulses_2t = [t for t in flux_times if 3.5 < t < 4.5]  # HD
    pulses_3t = [t for t in flux_times if 5.5 < t < 6.5]
    pulses_4t = [t for t in flux_times if 7.5 < t < 8.5]

    # Calculate mean and standard deviation
    signal = np.mean([np.std(pulses_2t), np.std(pulses_3t), np.std(pulses_4t)])
    noise = # baseline noise measurement

    snr_db = 20 * np.log10(signal / noise)
    return snr_db
```

### Timing Jitter

```python
def calculate_jitter(flux_times, expected_bit_cell):
    """
    Calculate timing jitter as percentage of bit cell.
    """
    # Normalize to bit cells
    cells = [t / expected_bit_cell for t in flux_times]

    # Calculate deviation from ideal
    ideal_cells = [round(c) for c in cells]
    deviations = [abs(c - i) for c, i in zip(cells, ideal_cells)]

    jitter_percent = (np.std(deviations) / expected_bit_cell) * 100
    return jitter_percent
```

### Quality Score Formula

```python
def calculate_quality_score(snr, jitter, peak_separation):
    """
    Calculate overall quality score (0-100).
    """
    # Normalize metrics
    snr_score = min(100, max(0, (snr - 10) * 5))  # 10-30 dB → 0-100
    jitter_score = min(100, max(0, 100 - jitter * 5))  # 0-20% → 100-0
    sep_score = min(100, max(0, peak_separation * 50))  # 0-2T → 0-100

    # Weighted average
    quality = (snr_score * 0.4 + jitter_score * 0.4 + sep_score * 0.2)
    return quality
```

---

## Data Structures

### SectorData

```python
@dataclass
class SectorData:
    cylinder: int       # 0-79
    head: int           # 0-1
    sector: int         # 1-18 (1-based)
    data: bytes         # Sector data (512 bytes typically)
    status: SectorStatus
    crc_valid: bool
    signal_quality: float  # 0.0-1.0
```

### FluxData

```python
@dataclass
class FluxData:
    flux_times: List[int]   # Flux transition times (sample ticks)
    sample_freq: int        # Sample frequency (72 MHz)
    index_times: List[int]  # Index pulse positions
```

### DiskGeometry

```python
@dataclass
class DiskGeometry:
    cylinders: int          # Number of cylinders (80)
    heads: int              # Number of heads (2)
    sectors_per_track: int  # Sectors per track (18 for HD)
    sector_size: int        # Bytes per sector (512)
    rpm: float              # Rotation speed (300)

    @property
    def total_sectors(self) -> int:
        return self.cylinders * self.heads * self.sectors_per_track
```

---

## File Formats

### SCP (SuperCard Pro)

```
Header (16 bytes):
  Offset  Size  Description
  0x00    3     Signature "SCP"
  0x03    1     Version
  0x04    1     Disk type
  0x05    1     Number of revolutions
  0x06    1     Start track
  0x07    1     End track
  0x08    1     Flags
  0x09    1     Bit cell width
  0x0A    2     Number of heads
  0x0C    4     Checksum

Track Header (per track):
  Offset  Size  Description
  0x00    4     Track data offset

Track Data:
  Duration (4 bytes) + Flux times (variable)
```

### IMG (Raw Sector)

```
Simple concatenation of sector data:

Sector 0: bytes 0-511
Sector 1: bytes 512-1023
...
Sector N: bytes (N*512) to ((N+1)*512-1)

Total size = cylinders × heads × sectors_per_track × 512
```

### HFE (HxC Floppy Emulator)

```
Header (512 bytes):
  Signature "HXCPICFE"
  Format revision
  Number of tracks
  Number of sides
  Track encoding
  Bit rate
  RPM
  Track list offset

Track data:
  Alternating blocks of side 0 and side 1 data
  256 bytes per block per side
```

---

**Next:** [[FAQ]] - Frequently asked questions
