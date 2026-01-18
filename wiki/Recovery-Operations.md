# Recovery Operations

This guide covers advanced data recovery techniques in Floppy Workbench.

## Table of Contents

- [Understanding Recovery](#understanding-recovery)
- [Recovery Levels](#recovery-levels)
- [Recovery Techniques](#recovery-techniques)
- [Recovery Configuration](#recovery-configuration)
- [Running Recovery](#running-recovery)
- [Multi-Capture Recovery](#multi-capture-recovery)
- [PLL Tuning](#pll-tuning)
- [Recovery Best Practices](#recovery-best-practices)
- [When Recovery Fails](#when-recovery-fails)

---

## Understanding Recovery

### What is Recovery?

Recovery is the process of extracting data from damaged or degraded floppy disks. Unlike a simple read, recovery employs multiple techniques to maximize data retrieval:

- **Multiple read passes** - Read same data repeatedly
- **Statistical analysis** - Compare multiple reads to find consensus
- **PLL optimization** - Tune decoder for specific disk
- **Signal processing** - Extract data from weak signals

### Why Disks Need Recovery

| Cause | Effect | Recovery Chance |
|-------|--------|-----------------|
| **Age** | Magnetic decay | Good |
| **Heat/Humidity** | Signal degradation | Good |
| **Physical damage** | Scratches, warping | Moderate |
| **Mold/Contamination** | Surface damage | Moderate |
| **Demagnetization** | Signal loss | Poor |
| **Media breakdown** | Oxide shedding | Poor |

### Recovery vs Formatting

| Approach | Goal | Data Preserved |
|----------|------|----------------|
| **Recovery** | Extract existing data | Yes |
| **Format+Rescan** | Rewrite then read | No |

**Important**: Recovery attempts to read existing data. Formatting destroys it!

---

## Recovery Levels

Floppy Workbench offers three recovery intensity levels:

### Standard Recovery

**Purpose**: Basic multi-pass recovery

| Parameter | Value |
|-----------|-------|
| Read Passes | 5-10 |
| Techniques | Multi-read averaging |
| Time | 2-5 minutes |
| Success Rate | 60-80% of bad sectors |

**Use for**:
- Disks with few bad sectors
- Recent media degradation
- First recovery attempt

### Aggressive Recovery

**Purpose**: Enhanced recovery with PLL tuning

| Parameter | Value |
|-----------|-------|
| Read Passes | 10-25 |
| Techniques | Multi-read + PLL sweep |
| Time | 5-15 minutes |
| Success Rate | 70-90% of bad sectors |

**Use for**:
- Disks with moderate damage
- Older disks
- After Standard fails

### Forensic Recovery

**Purpose**: Maximum effort recovery

| Parameter | Value |
|-----------|-------|
| Read Passes | 25-100+ |
| Techniques | All available |
| Time | 15-60+ minutes |
| Success Rate | 80-95% of bad sectors |

**Use for**:
- Critical data recovery
- Severely damaged disks
- Last resort attempts

---

## Recovery Techniques

### Multi-Read Averaging

Reads the same track multiple times and compares results:

```
Read 1: 1 0 1 1 ? 0 1 0  (? = uncertain bit)
Read 2: 1 0 1 1 0 0 1 0
Read 3: 1 0 1 1 0 0 1 0
Read 4: 1 0 1 1 1 0 1 0
Read 5: 1 0 1 1 0 0 1 0
─────────────────────────
Result: 1 0 1 1 0 0 1 0  (consensus: bit 5 = 0)
```

### Statistical Bit Voting

For each bit position:
1. Count 0s and 1s across all reads
2. Choose the majority value
3. Flag low-confidence bits for extra attention

### PLL Parameter Sweep

The Phase-Locked Loop decoder has adjustable parameters:

| Parameter | Description | Range |
|-----------|-------------|-------|
| **Bit Cell** | Expected bit timing | 1.8-2.2 µs (HD) |
| **Period Adj** | PLL responsiveness | 0.01-0.10 |
| **Phase Adj** | Phase correction rate | 0.3-0.8 |

Recovery tries multiple parameter combinations to find optimal settings.

### Bit-Slip Correction

Detects and corrects synchronization errors:

```
Expected: SYNC SYNC SYNC DATA DATA DATA
Actual:   SYNC SYNC DATA DATA DATA DATA  (slipped 1 bit early)
Fixed:    SYNC SYNC SYNC DATA DATA DATA  (corrected)
```

### Weak Bit Detection

Identifies bits near the detection threshold:

- Strong bits: Clear 0 or 1
- Weak bits: Near threshold, may flip between reads
- Recovery focuses extra attention on weak areas

---

## Recovery Configuration

### Mode Selection

#### Fixed Passes

Run exactly N recovery passes:

```
┌────────────────────────────────────────┐
│  Pass Mode: Fixed                       │
│  Number of Passes: [10    ] ▼          │
│                                         │
│  Estimated Time: ~3 minutes             │
└────────────────────────────────────────┘
```

**Use when**:
- You know how much time you have
- Consistent results needed
- Batch processing

#### Convergence Mode

Run until no more improvement:

```
┌────────────────────────────────────────┐
│  Pass Mode: Convergence                 │
│  Stop after [3] passes with no change  │
│  Maximum passes: [50]                   │
│                                         │
│  Stops automatically when converged     │
└────────────────────────────────────────┘
```

**Use when**:
- Maximum recovery desired
- Time is flexible
- Unknown disk condition

### Advanced Options

| Option | Description | Default |
|--------|-------------|---------|
| **Multi-Capture** | Enable flux-level recovery | On |
| **PLL Tuning** | Sweep PLL parameters | Aggressive+ |
| **Bit-Slip Recovery** | Correct sync errors | On |
| **Quality Threshold** | Minimum signal % | 50% |
| **Prevent Sleep** | Keep system awake | On |

### Sector Selection

| Option | Description |
|--------|-------------|
| **All Bad Sectors** | Recover all failed sectors |
| **Selected Sectors** | Only recover selected |
| **Custom Range** | Specify track/sector range |

---

## Running Recovery

### Step 1: Scan First

Always scan before recovery:
1. Click **Scan** (`Ctrl+S`)
2. Use Standard or Thorough mode
3. Note bad sector locations

### Step 2: Review Bad Sectors

In the Errors tab:
- Review list of bad sectors
- Check error distribution
- Assess recovery viability

### Step 3: Start Recovery

Click **Restore** (`Ctrl+R`) to open recovery dialog.

### Step 4: Configure Recovery

1. Select **Recovery Level** (Standard/Aggressive/Forensic)
2. Choose **Pass Mode** (Fixed or Convergence)
3. Set **Options** (Multi-Capture, PLL Tuning, etc.)
4. Click **Start Recovery**

### Step 5: Monitor Progress

```
┌────────────────────────────────────────────────────────────┐
│  RECOVERY IN PROGRESS                                       │
│  ══════════════════════════════════════════════════════    │
│                                                             │
│  Pass: 7/25  |  Mode: Aggressive                           │
│                                                             │
│  Bad Sectors:     42 → 12  (30 recovered)                  │
│  Recovery Rate:   71.4%                                     │
│                                                             │
│  Current Track: 45  |  Elapsed: 4:32  |  ETA: 2:15         │
│                                                             │
│  [Pause]  [Cancel]                                         │
└────────────────────────────────────────────────────────────┘
```

### Step 6: Review Results

After recovery completes:
- Recovered sectors turn orange on map
- Statistics show recovery rate
- Remaining bad sectors listed

---

## Multi-Capture Recovery

### How It Works

Multi-Capture reads raw flux data multiple times:

1. **Capture**: Read raw flux transitions (not decoded data)
2. **Store**: Save each capture separately
3. **Analyze**: Compare flux patterns across captures
4. **Decode**: Use combined flux data for decoding

### Why It's Better

- Works at magnetic level, before decoding
- Captures timing variations
- Can recover from intermittent read issues
- More data for statistical analysis

### Configuration

```
┌────────────────────────────────────────┐
│  Multi-Capture Settings                 │
├────────────────────────────────────────┤
│  Captures per Track: [5   ] ▼          │
│  Revolutions per Capture: [3]          │
│  Store Raw Flux: [✓]                   │
└────────────────────────────────────────┘
```

### Memory Considerations

Multi-Capture uses significant memory:
- ~500KB per track per revolution
- 5 captures × 3 revolutions × 160 tracks = ~1.2 GB
- Ensure adequate system RAM

---

## PLL Tuning

### Understanding PLL

The Phase-Locked Loop decoder synchronizes to data:

```
Flux transitions:  │ │  │ │  │  │ │  │ │  │
                   ↓ ↓  ↓ ↓  ↓  ↓ ↓  ↓ ↓  ↓
PLL clock:        ─┴─┴──┴─┴──┴──┴─┴──┴─┴──┴─
                   1 0  1 1  0  1 0  1 1  0
```

### PLL Parameters

| Parameter | Effect | Optimal Range |
|-----------|--------|---------------|
| **bit_cell_us** | Expected bit timing | 1.9-2.1 (HD) |
| **pll_period_adj** | How fast PLL adjusts to speed changes | 0.03-0.07 |
| **pll_phase_adj** | How fast PLL adjusts to phase changes | 0.4-0.7 |

### Automatic PLL Sweep

Recovery tries multiple PLL configurations:

```
Trying: bit_cell=2.0, period_adj=0.05, phase_adj=0.6
Result: 35 bad sectors

Trying: bit_cell=1.95, period_adj=0.05, phase_adj=0.6
Result: 28 bad sectors  ← Better!

Trying: bit_cell=1.95, period_adj=0.03, phase_adj=0.5
Result: 22 bad sectors  ← Best so far!
```

### Manual PLL Configuration

For expert users:

```
┌────────────────────────────────────────┐
│  Manual PLL Settings                    │
├────────────────────────────────────────┤
│  Bit Cell (µs):    [1.95  ]            │
│  Period Adjust:    [0.03  ]            │
│  Phase Adjust:     [0.50  ]            │
│                                         │
│  [Test] [Apply to All]                 │
└────────────────────────────────────────┘
```

---

## Recovery Best Practices

### Before Recovery

1. **Scan thoroughly** - Know what you're dealing with
2. **Check drive** - Use a known-good drive
3. **Clean disk** - Gently clean if contaminated
4. **Clean drive** - Clean heads before critical recovery

### During Recovery

1. **Start with Standard** - Don't jump to Forensic immediately
2. **Monitor progress** - Watch for convergence
3. **Don't disturb** - Avoid vibration and movement
4. **Stay patient** - Recovery takes time

### After Recovery

1. **Verify recovered sectors** - Check data makes sense
2. **Export immediately** - Save recovered data
3. **Don't rely on disk** - The disk is damaged
4. **Store carefully** - Keep disk for potential future attempts

### Environmental Factors

| Factor | Recommendation |
|--------|----------------|
| **Temperature** | 20-25°C (68-77°F) |
| **Humidity** | 40-60% |
| **Vibration** | Minimize |
| **Time of day** | When power is stable |

---

## When Recovery Fails

### Partial Recovery

If some sectors won't recover:

1. **Export what you have** - Save recovered data
2. **Try different drive** - Head alignment varies
3. **Try different parameters** - Manual PLL tuning
4. **Professional services** - Data recovery specialists

### Assessing Damage

| Symptom | Likely Cause | Prognosis |
|---------|--------------|-----------|
| Random scattered bad sectors | Media degradation | Good |
| Entire tracks bad | Physical damage | Moderate |
| One side completely bad | Head issue | Try other drive |
| No data at all | Demagnetized/blank | Poor |

### Data Recovery Services

For critical data that can't be recovered:

- Professional data recovery services
- Specialized equipment
- Clean room facilities
- Magnetic force microscopy (extreme cases)

### Accepting Loss

Sometimes data cannot be recovered:
- Physical destruction
- Complete demagnetization
- Severe oxidation
- Fire/water damage

Document what was lost and preserve the disk for potential future technology advances.

---

## Recovery Technical Details

### Signal Quality Metrics

| Metric | Description | Good Value |
|--------|-------------|------------|
| **SNR** | Signal-to-noise ratio | > 20 dB |
| **Jitter** | Timing variation | < 10% |
| **Peak Amplitude** | Signal strength | Consistent |

### Sector Recovery Process

```
1. Identify bad sector (cylinder, head, sector)
2. Seek to track
3. For each pass:
   a. Capture flux data (multiple revolutions)
   b. Decode with current PLL parameters
   c. Check CRC
   d. If good: mark recovered
   e. If bad: store for statistical analysis
4. After all passes:
   a. Combine flux data from all captures
   b. Apply bit voting
   c. Final decode attempt
```

---

**Next:** [[Flux Analysis]] - Understanding flux-level data
