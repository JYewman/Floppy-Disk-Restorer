# Scanning Disks

This guide covers everything about scanning floppy disks with Floppy Workbench.

## Table of Contents

- [What is Scanning?](#what-is-scanning)
- [Before You Scan](#before-you-scan)
- [Scan Modes](#scan-modes)
- [Scan Configuration](#scan-configuration)
- [Running a Scan](#running-a-scan)
- [Understanding Results](#understanding-results)
- [Advanced Scanning](#advanced-scanning)
- [Scan Best Practices](#scan-best-practices)

---

## What is Scanning?

Scanning is the process of reading all sectors on a floppy disk to:

- **Assess disk health** - Identify good, bad, and weak sectors
- **Map the disk surface** - Create a visual representation
- **Prepare for recovery** - Identify sectors needing attention
- **Verify data integrity** - Check CRC values

During a scan, Floppy Workbench:
1. Reads each track sequentially
2. Decodes MFM data to extract sectors
3. Validates CRC checksums
4. Records signal quality metrics
5. Updates the sector map in real-time

---

## Before You Scan

### Prerequisites

- [ ] Greaseweazle connected and recognized
- [ ] Floppy drive connected and powered
- [ ] Motor spinning (RPM displayed)
- [ ] Disk inserted in drive

### Disk Inspection

Before scanning, visually inspect the disk:

- **Mold or debris** - Clean if possible, or use caution
- **Physical damage** - Scratches, warping may cause issues
- **Shutter condition** - Ensure metal shutter moves freely
- **Hub ring** - Check for cracks or damage

### Drive Preparation

For best results:
1. Clean drive heads if not recently done
2. Let the drive warm up for a minute
3. Ensure RPM is stable (around 300 RPM)

---

## Scan Modes

Floppy Workbench offers three scan modes:

### Quick Scan

**Purpose**: Fast overview of disk condition

| Parameter | Value |
|-----------|-------|
| Tracks Scanned | Sample (every 5th track) |
| Reads per Track | 1 |
| Estimated Time | 10-15 seconds |

**Use when**:
- Testing drive operation
- Quick disk assessment
- Sorting large disk collections

### Standard Scan

**Purpose**: Complete disk analysis (Recommended)

| Parameter | Value |
|-----------|-------|
| Tracks Scanned | All (0-79) |
| Reads per Track | 1-2 |
| Estimated Time | 30-60 seconds |

**Use when**:
- Normal disk reading
- Creating disk images
- General assessment

### Thorough Scan

**Purpose**: Maximum accuracy for damaged disks

| Parameter | Value |
|-----------|-------|
| Tracks Scanned | All (0-79) |
| Reads per Track | 3-5 |
| Estimated Time | 2-5 minutes |

**Use when**:
- Disks with known problems
- Archival preservation
- Before recovery operations

---

## Scan Configuration

When you click **Scan**, the configuration dialog appears:

### Disk Type

Select the disk format:

| Type | Capacity | Cylinders | Sectors/Track |
|------|----------|-----------|---------------|
| **1.44MB HD** | 1,474,560 bytes | 80 | 18 |
| **720KB DD** | 737,280 bytes | 80 | 9 |
| **1.2MB HD** | 1,228,800 bytes | 80 | 15 |
| **360KB DD** | 368,640 bytes | 40 | 9 |

### Scan Mode

Choose from Quick, Standard, or Thorough (see above).

### Advanced Options

| Option | Description | Default |
|--------|-------------|---------|
| **Verify Reads** | Read sectors twice to confirm | On |
| **Record Flux** | Save raw flux data | Off |
| **Quality Threshold** | Minimum signal quality % | 70% |
| **Retry Failed** | Retry bad sectors | 3 times |

### Head Selection

| Option | Description |
|--------|-------------|
| **Both Heads** | Scan head 0 and head 1 (normal) |
| **Head 0 Only** | Single-sided scan (top) |
| **Head 1 Only** | Single-sided scan (bottom) |

---

## Running a Scan

### Step 1: Open Scan Dialog

Click **Scan** button or press `Ctrl+S`

### Step 2: Configure Options

1. Select disk type
2. Choose scan mode
3. Adjust advanced options if needed
4. Click **Start Scan**

### Step 3: Monitor Progress

During the scan:

```
┌────────────────────────────────────────────────────┐
│  Scanning...                                        │
│  ════════════════════════════════════════          │
│  Track: 45/80  |  Head: 0  |  Progress: 56%        │
│                                                     │
│  Good: 1,440  |  Bad: 23  |  Weak: 12              │
│  Elapsed: 0:28  |  Remaining: 0:22                 │
│                                                     │
│  [Cancel]                                          │
└────────────────────────────────────────────────────┘
```

### Step 4: Review Results

When complete:
- Completion sound plays
- Summary dialog appears
- Full results in Analytics Panel

### Canceling a Scan

Press **Escape** or click **Cancel** to stop the scan.
Partial results are preserved.

---

## Understanding Results

### Sector Status Types

| Status | Icon | Description | Action |
|--------|------|-------------|--------|
| **GOOD** | Green | Read successfully, CRC valid | None needed |
| **BAD** | Red | CRC error or unreadable | Consider recovery |
| **WEAK** | Yellow | Read OK but marginal signal | May degrade |
| **MISSING** | Purple | Sector not found on track | Formatting issue |
| **NO_DATA** | Gray | No valid data pattern | May be unformatted |
| **RECOVERED** | Orange | Previously bad, now recovered | Monitor |

### Scan Statistics

After a scan, view statistics in the Overview tab:

| Statistic | Description |
|-----------|-------------|
| **Total Sectors** | Number of sectors scanned |
| **Good Sectors** | Successfully read sectors |
| **Bad Sectors** | Failed sectors |
| **Weak Sectors** | Marginal signal sectors |
| **Disk Health** | Percentage of good sectors |
| **Scan Time** | Duration of scan |
| **Read Errors** | Total read error count |

### Signal Quality Metrics

Each sector has a signal quality score (0-100%):

| Range | Quality | Interpretation |
|-------|---------|----------------|
| 90-100% | Excellent | Strong, clear signal |
| 70-89% | Good | Normal condition |
| 50-69% | Fair | Aging or wear |
| 30-49% | Poor | At risk of failure |
| 0-29% | Critical | Likely unrecoverable |

---

## Advanced Scanning

### Multi-Pass Scanning

For damaged disks, multiple read passes improve accuracy:

1. Open Scan Configuration
2. Set **Scan Mode** to Thorough
3. Increase **Reads per Track** (3-10)
4. Enable **Verify Reads**

Multiple passes help because:
- Weak sectors may read correctly on some passes
- Statistical analysis improves reliability
- Different read conditions may yield better results

### Track-Specific Scanning

To scan specific tracks:

1. Use seek controls to position head
2. In scan dialog, enable **Custom Range**
3. Enter start and end tracks
4. Run scan

### Flux Recording During Scan

To capture raw flux data:

1. Enable **Record Flux** in scan options
2. Select flux storage location
3. Run scan

Flux data enables:
- Post-scan analysis
- Different decoding attempts
- Archival preservation

---

## Scan Best Practices

### For Unknown Disks

1. Start with **Quick Scan** to assess condition
2. If mostly good, use **Standard Scan**
3. If many errors, use **Thorough Scan**

### For Damaged Disks

1. Use **Thorough Scan** mode
2. Enable **Record Flux**
3. Set high retry count (5-10)
4. Lower quality threshold to 50%

### For Archival

1. Use **Thorough Scan** mode
2. Enable **Record Flux**
3. Set maximum retries
4. Run scan multiple times
5. Compare results

### For Large Collections

1. Use **Quick Scan** for initial triage
2. Separate good disks from problem disks
3. Use appropriate mode for each category

### Environmental Tips

- **Temperature**: Room temperature is best (20-25°C)
- **Humidity**: Moderate humidity (40-60%)
- **Vibration**: Minimize during scanning
- **Multiple attempts**: Try scanning again if results seem wrong

---

## Interpreting Problem Patterns

### Entire Disk Bad

- **Possible causes**: Wrong disk type selected, drive issue, disk completely damaged
- **Try**: Verify disk type, try different drive, clean drive heads

### Track 0 Bad

- **Possible causes**: Boot sector damage, physical damage to outer edge
- **Impact**: Disk may not be bootable, but data may be recoverable

### Outer Tracks Bad

- **Possible causes**: Physical damage to disk edge, handling damage
- **Impact**: Data on inner tracks may still be good

### Inner Tracks Bad

- **Possible causes**: Hub area damage, age-related degradation
- **Impact**: Earlier data (outer tracks) may be intact

### Scattered Bad Sectors

- **Possible causes**: Media degradation, magnetic wear
- **Impact**: Recovery may be possible for most data

### One Side Completely Bad

- **Possible causes**: Single-sided disk, head alignment issue
- **Impact**: Try head alignment test, verify disk format

---

**Next:** [[Formatting Disks]] - Learn about formatting operations
