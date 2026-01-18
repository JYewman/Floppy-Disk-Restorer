# Flux Analysis

This guide explains flux-level analysis in Floppy Workbench.

## Table of Contents

- [Understanding Flux Data](#understanding-flux-data)
- [The Flux Tab](#the-flux-tab)
- [Waveform Visualization](#waveform-visualization)
- [Pulse Histogram](#pulse-histogram)
- [Signal Quality Metrics](#signal-quality-metrics)
- [Analyzing Problems](#analyzing-problems)
- [Advanced Analysis](#advanced-analysis)

---

## Understanding Flux Data

### What is Flux?

Flux refers to the magnetic field changes recorded on a floppy disk. Instead of reading logical data (0s and 1s), flux-level analysis examines the raw magnetic transitions.

### Physical Recording

```
Magnetic domains on disk:

    N  S  N  S     N  S  N     S  N  S
   ─┬──┴──┬──┴─────┬──┴──┬─────┴──┬──┴─
    │     │        │     │        │
    ▼     ▼        ▼     ▼        ▼
   Flux transitions (timing matters!)
```

### MFM Encoding

Data is encoded using Modified Frequency Modulation (MFM):

| Data | MFM Pattern | Pulse Spacing |
|------|-------------|---------------|
| 1 | ...01... | Clock only |
| 01 | ...1001... | 2T (short) |
| 001 | ...10001... | 3T (medium) |
| 0001 | ...100001... | 4T (long) |

The timing between flux transitions encodes the data.

### Why Flux Analysis Matters

- **See actual magnetic data** - Not just decoded results
- **Diagnose problems** - Identify signal issues
- **Optimize recovery** - Tune PLL parameters
- **Detect copy protection** - Non-standard encodings
- **Archival preservation** - Capture everything

---

## The Flux Tab

The Flux tab in the Analytics Panel provides flux visualization tools.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Flux Analysis                                                   │
├─────────────────────────────────────────────────────────────────┤
│  Track: [15 ▼]  Head: [0 ▼]  [Load] [Capture]                  │
├───────────────────────────────────┬─────────────────────────────┤
│                                   │  STATISTICS                 │
│     WAVEFORM VIEW                 │  ────────────────           │
│                                   │  Flux Count: 102,456        │
│  ╭─╮   ╭─╮ ╭──╮  ╭─╮  ╭──╮      │  Index Pulses: 3            │
│  │ │   │ │ │  │  │ │  │  │      │  Track Length: 200.12 ms    │
│  │ ╰───╯ ╰─╯  ╰──╯ ╰──╯  │      │  Data Rate: 512.3 Kbps      │
│  │                       │      │                              │
│  ╰───────────────────────╯      │  Peak: 2.1 µs               │
│                                   │  Jitter: 8.2%               │
│  Time: 0.00 µs - 500.00 µs       │  SNR: 24.3 dB               │
├───────────────────────────────────┴─────────────────────────────┤
│                    HISTOGRAM                                     │
│                                                                  │
│       ▓▓                                                         │
│      ▓▓▓▓         ▓▓▓                                           │
│     ▓▓▓▓▓▓       ▓▓▓▓▓         ▓▓                               │
│    ▓▓▓▓▓▓▓▓     ▓▓▓▓▓▓▓      ▓▓▓▓▓                             │
│  ──┴───┴───┴───┴───┴───┴───┴───┴───┴───                         │
│    2T   3T   4T   5T   (pulse widths in bit cells)              │
└─────────────────────────────────────────────────────────────────┘
```

### Controls

| Control | Function |
|---------|----------|
| **Track** | Select cylinder to analyze |
| **Head** | Select side (0 or 1) |
| **Load** | Load previously captured flux |
| **Capture** | Capture new flux from disk |

---

## Waveform Visualization

### Reading the Waveform

The waveform shows flux transitions over time:

```
Amplitude
   ▲
   │  ╭─╮       ╭──╮     ╭─╮
   │  │ │       │  │     │ │
 0 ┼──┼─┼───────┼──┼─────┼─┼─────► Time
   │  │ │       │  │     │ │
   │  ╰─╯       ╰──╯     ╰─╯
   │
   │  │←2T→│    │←3T→│   │←2T→│
```

| Measurement | Meaning |
|-------------|---------|
| **Pulse height** | Signal strength |
| **Pulse spacing** | Encoded data (2T, 3T, 4T) |
| **Pulse width** | Signal quality |

### Waveform Controls

| Action | Function |
|--------|----------|
| **Scroll** | Pan through time |
| **Zoom +/-** | Adjust time scale |
| **Click** | Position cursor |
| **Drag** | Select region |

### Time Scale

| Zoom Level | View |
|------------|------|
| **Full Track** | Entire rotation (~200ms) |
| **Sector** | ~5-10 ms |
| **Byte** | ~50-100 µs |
| **Bit** | ~2-8 µs |

### Measurement Tools

| Tool | Function |
|------|----------|
| **Cursor** | Show time/amplitude at point |
| **Markers** | Mark positions for reference |
| **Delta** | Measure time between points |

---

## Pulse Histogram

### Understanding the Histogram

The histogram shows distribution of pulse widths:

```
Count
  ▲
  │      ▓▓▓▓
  │     ▓▓▓▓▓▓          ▓▓▓▓
  │    ▓▓▓▓▓▓▓▓        ▓▓▓▓▓▓        ▓▓
  │   ▓▓▓▓▓▓▓▓▓▓      ▓▓▓▓▓▓▓▓     ▓▓▓▓▓
  │  ▓▓▓▓▓▓▓▓▓▓▓▓    ▓▓▓▓▓▓▓▓▓▓   ▓▓▓▓▓▓▓
  └──┴───────┴────────┴────────┴──────┴───► Time
       2T (4µs)       3T (6µs)     4T (8µs)
```

### Ideal Distribution

For MFM data, you should see three distinct peaks:

| Peak | Timing (HD) | Timing (DD) | Represents |
|------|-------------|-------------|------------|
| **2T** | ~4 µs | ~8 µs | Short pulse |
| **3T** | ~6 µs | ~12 µs | Medium pulse |
| **4T** | ~8 µs | ~16 µs | Long pulse |

### Reading the Histogram

| Pattern | Meaning | Quality |
|---------|---------|---------|
| **Three sharp peaks** | Clean MFM signal | Excellent |
| **Overlapping peaks** | Timing jitter | Moderate |
| **Merged peaks** | Severe jitter/speed issue | Poor |
| **Extra peaks** | Non-standard encoding | Investigate |
| **Flat/no peaks** | No valid data | Critical |

### Histogram Analysis

```
Good Signal:              Poor Signal:

    ▓▓▓    ▓▓▓    ▓▓          ▓▓▓▓▓▓▓▓▓▓▓▓▓▓
   ▓▓▓▓▓  ▓▓▓▓▓  ▓▓▓▓       ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓     ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
  ───┴────┴────┴────       ─────────────────────
    2T    3T    4T            (peaks merged)
```

---

## Signal Quality Metrics

### Key Metrics

| Metric | Description | Good | Warning | Critical |
|--------|-------------|------|---------|----------|
| **SNR** | Signal-to-Noise Ratio | > 25 dB | 15-25 dB | < 15 dB |
| **Jitter** | Timing variation | < 8% | 8-15% | > 15% |
| **Peak Separation** | Distance between histogram peaks | > 1.5T | 1-1.5T | < 1T |
| **Consistency** | Variation across track | < 5% | 5-10% | > 10% |

### Signal-to-Noise Ratio (SNR)

Measures signal strength vs background noise:

```
SNR = 20 × log₁₀(Signal / Noise)

High SNR (30 dB):  Clear signal, low noise
                   ─╮  ╭─     Signal peaks
                    │  │
              ~~~~──┴──┴──~~~~  Noise floor (low)

Low SNR (10 dB):   Signal hidden in noise
                   ─╮  ╭─
             ~~~~~~┴~~┴~~~~~~  Noise floor (high)
```

### Timing Jitter

Variation in pulse timing:

```
Ideal (low jitter):
  │ │ │ │ │ │ │ │ │ │  (consistent spacing)

High jitter:
  │  ││ │  │││ │  ││   (inconsistent spacing)
```

**Causes of jitter**:
- Media degradation
- Speed variation
- Motor issues
- Temperature effects

### Calculating Quality Score

```
Quality Score = f(SNR, Jitter, PeakSeparation, Consistency)

90-100%: Excellent - Archive quality
70-89%:  Good - Normal operation
50-69%:  Fair - May have read issues
30-49%:  Poor - Recovery likely needed
0-29%:   Critical - Significant data loss possible
```

---

## Analyzing Problems

### Weak Signal

**Symptoms**:
- Low amplitude in waveform
- Low SNR metric
- Histogram peaks are small

**Causes**:
- Media degradation
- Worn drive heads
- Distance between head and media

**Action**: Try different drive, consider recovery mode

### High Jitter

**Symptoms**:
- Wide histogram peaks
- Peaks starting to merge
- High jitter percentage

**Causes**:
- Motor speed instability
- Media deterioration
- Temperature effects

**Action**: Check drive speed, try multiple captures

### Missing Pulses

**Symptoms**:
- Gaps in waveform
- Missing sectors
- Histogram shows unusual distribution

**Causes**:
- Physical damage
- Oxide loss
- Severe demagnetization

**Action**: Visual inspection, gentle cleaning, recovery mode

### Non-Standard Patterns

**Symptoms**:
- Extra histogram peaks
- Unusual pulse timings
- Valid data but strange flux

**Causes**:
- Copy protection
- Non-IBM format
- Custom encoding

**Action**: Check format, research protection schemes

### Speed Variation

**Symptoms**:
- Histogram peaks shift across track
- Jitter increases at certain positions
- RPM display unstable

**Causes**:
- Motor bearing wear
- Belt slippage
- Power supply issues

**Action**: Check drive mechanics, try different drive

---

## Advanced Analysis

### Track Timing Analysis

Measure track characteristics:

| Measurement | How to Check | Normal Value |
|-------------|--------------|--------------|
| **Track length** | Index to index | 200.00 ms (±0.5%) |
| **Sector timing** | Sector marks | 11.11 ms (HD) |
| **RPM** | 60000 / track_ms | 300.0 (±1.5%) |

### Sector-by-Sector Analysis

For each sector, examine:

1. **Address mark** - Sync and header
2. **Header CRC** - Address validation
3. **Data mark** - Data sync
4. **Data CRC** - Data validation
5. **Gap bytes** - Inter-sector spacing

### Copy Protection Detection

Look for non-standard patterns:

| Protection | Flux Signature |
|------------|----------------|
| **Weak bits** | Intentionally marginal bits |
| **Long tracks** | Extra data beyond normal |
| **Missing sectors** | Intentional sector gaps |
| **Fuzzy bits** | Variable read results |
| **Non-standard gaps** | Unusual timing |

### Raw Flux Export

Export flux data for external analysis:

1. Capture flux with **Capture** button
2. Go to File → Export Flux
3. Choose format (SCP, HFE, RAW)
4. Use external tools for analysis

---

## Flux Tab Reference

### Statistics Panel

| Field | Description |
|-------|-------------|
| **Flux Count** | Total flux transitions |
| **Index Pulses** | Number of index marks |
| **Track Length** | Time for one rotation |
| **Data Rate** | Bits per second |
| **Peak** | Most common pulse width |
| **Jitter** | Timing variation percentage |
| **SNR** | Signal-to-noise ratio |

### Keyboard Shortcuts (Flux Tab)

| Key | Function |
|-----|----------|
| `+` | Zoom in |
| `-` | Zoom out |
| `←` `→` | Pan view |
| `Home` | Go to start |
| `End` | Go to end |
| `Space` | Toggle play/pause (if animated) |

---

**Next:** [[Exporting Images]] - Save disk contents to files
