# Recovery Operations

This guide covers data recovery from damaged floppy disks using Floppy Disk Workbench.

## Table of Contents

- [Understanding Recovery](#understanding-recovery)
- [Recovery Levels](#recovery-levels)
- [Recovery Techniques](#recovery-techniques)
- [Recovery Configuration](#recovery-configuration)
- [Running Recovery](#running-recovery)
- [Understanding Results](#understanding-results)
- [Recovery Best Practices](#recovery-best-practices)
- [When Recovery Fails](#when-recovery-fails)

---

## Understanding Recovery

Recovery is the process of extracting data from damaged or degraded floppy disks. Unlike simple reading, recovery uses multiple techniques to maximize data retrieval from marginal sectors.

### Why Disks Need Recovery

| Cause | Effect | Recovery Chance |
|-------|--------|-----------------|
| **Age** | Magnetic signal decay | Good |
| **Heat/Humidity** | Signal degradation | Good |
| **Physical damage** | Scratches, warping | Moderate |
| **Mold/Contamination** | Surface damage | Moderate (after cleaning) |
| **Demagnetization** | Partial or complete signal loss | Poor |
| **Media breakdown** | Oxide shedding from substrate | Poor |

### Recovery vs Formatting

| Approach | Purpose | Existing Data |
|----------|---------|---------------|
| **Recovery** | Extract data from damaged sectors | Preserved |
| **Formatting** | Write fresh track structure | Destroyed |

**Important**: Recovery attempts to read existing data. Formatting destroys it. Always try recovery first.

### The Recovery Process

Floppy Disk Workbench recovery works in phases:

1. **Initial Scan** — Identifies all bad sectors
2. **Recovery Passes** — Applies techniques to recover each bad sector
3. **Final Verification** — Confirms recovered sectors are stable
4. **Retry (if needed)** — Repeats for sectors that failed verification

The recovery worker may perform up to 3 complete recovery attempts if verification fails.

---

## Recovery Levels

Floppy Disk Workbench provides three recovery intensity levels.

### Standard

Basic multi-pass recovery suitable for most situations.

| Characteristic | Value |
|----------------|-------|
| Techniques | Format refresh, multi-capture |
| PLL Tuning | No |
| Bit-Slip Recovery | No |
| Best For | Routine recovery, light degradation |

Standard recovery uses format refresh (rewriting tracks) combined with multi-revolution flux capture. This is sufficient for most disks with minor degradation.

### Aggressive

Enhanced recovery with adaptive decoder tuning.

| Characteristic | Value |
|----------------|-------|
| Techniques | Format refresh, multi-capture, PLL tuning |
| PLL Tuning | Yes (after initial passes) |
| Bit-Slip Recovery | No |
| Best For | Moderate damage, timing issues |

Aggressive recovery adds PLL (Phase-Locked Loop) parameter tuning on later passes. The decoder systematically adjusts timing parameters to find settings that can read marginal sectors.

### Forensic

Maximum effort recovery using all available techniques.

| Characteristic | Value |
|----------------|-------|
| Techniques | All available |
| PLL Tuning | Yes (from start) |
| Bit-Slip Recovery | Yes |
| Surface Treatment | Yes |
| Best For | Critical data, severe damage |

Forensic recovery employs every technique from the beginning, including bit-slip recovery for synchronization errors. Use this level for critical data when time is not a constraint.

---

## Recovery Techniques

### Format Refresh

Rewrites the track structure to refresh weak magnetic signals.

**Process:**
1. DC erase the entire track
2. Write with pattern 0x00
3. Write with pattern 0xFF
4. Write with pattern 0xAA
5. Write with pattern 0x55

This exercises the magnetic domains and can restore signal strength in areas where the existing signal has weakened.

### Multi-Capture

Captures multiple revolutions of flux data for statistical analysis.

**Process:**
1. Read track for multiple disk revolutions
2. Compare flux patterns across revolutions
3. Use bit voting to determine most likely data
4. Decode using combined flux data

Each revolution captures the same data but with slightly different noise. Combining multiple reads improves the signal-to-noise ratio.

### PLL Tuning

Adjusts decoder timing parameters to optimize for specific disk characteristics.

The Phase-Locked Loop decoder has adjustable parameters:

| Parameter | Description | Typical Range |
|-----------|-------------|---------------|
| **Bit Cell** | Expected bit timing | 1.9-2.1 µs (HD) |
| **Period Adjust** | Rate of speed tracking | 0.03-0.07 |
| **Phase Adjust** | Rate of phase correction | 0.4-0.7 |

Recovery systematically tries different parameter combinations to find settings that decode marginal sectors.

### Bit-Slip Recovery

Detects and corrects synchronization errors.

A "bit slip" occurs when the decoder loses sync and shifts by one or more bits, causing all subsequent data to decode incorrectly. Bit-slip recovery:

1. Detects patterns indicating sync loss
2. Identifies likely slip location
3. Attempts re-synchronization at different offsets
4. Validates corrected data with CRC

### Surface Treatment

Combines DC erase with pattern refresh for weak media.

This technique performs a full degauss (DC erase) followed by multiple pattern writes to "exercise" weak magnetic areas. It can restore readability to media with marginal signal levels.

---

## Recovery Configuration

Click the **Restore** button in the Operation Toolbar to open the Restore Configuration dialog.

![Restore Configuration Dialog](../screenshots/restore_config_dialog.png)
*Screenshot: Restore Configuration dialog showing all recovery options*

### Recovery Mode

Choose how many recovery passes to run.

**Fixed Passes:**
- Run exactly N passes
- Set pass count from 1 to 100
- Predictable duration

**Convergence Mode:**
- Run until improvement stops
- Stops after 3 consecutive passes with no new recoveries
- Set maximum passes (5-200) as safety limit
- Recommended for unknown disk condition

### Recovery Scope

Choose which sectors to recover.

**Full Disk Recovery:**
- Scans and recovers entire disk
- Formats and verifies all tracks
- Preserves good sectors while recovering bad ones

**Targeted Recovery:**
- Only recovers sectors identified in previous scan
- Faster when few sectors are bad
- Requires prior scan data

### Multi-Read Recovery

Enable statistical recovery using multiple flux captures.

When enabled:
- Set the number of flux revolutions to capture (10-1000)
- More captures = better accuracy but slower
- Uses bit voting to determine most likely data
- Memory usage increases with capture count

The dialog notes that this now uses "flux-level bit voting" rather than byte-level comparison, providing improved accuracy.

### Recovery Level

Select the overall recovery aggressiveness:

| Level | Description |
|-------|-------------|
| **Standard** | Traditional recovery using format passes and verification |
| **Aggressive** | Adds PLL tuning and multi-capture analysis |
| **Forensic** | All techniques, maximum effort, detailed logging |

The level dropdown automatically adjusts the Advanced Options checkboxes to recommended settings.

### Advanced Options

Fine-tune individual recovery techniques:

| Option | Description |
|--------|-------------|
| **Enable PLL Tuning** | Search for optimal decoder parameters on marginal sectors |
| **Enable Bit-Slip Recovery** | Detect and recover from synchronization errors |
| **Enable Surface Treatment** | DC erase + pattern refresh for weak areas |

These options are auto-enabled based on Recovery Level but can be manually overridden.

### Report Options

Configure recovery reporting:

| Option | Description |
|--------|-------------|
| **Generate detailed report** | Create a recovery report with statistics |
| **Include track maps** | Add visual sector maps to report |
| **Include hex dumps** | Include raw data from recovered/failed sectors |
| **Save report to file** | Automatically save report when complete |

---

## Running Recovery

### Step 1: Scan First

Always scan before recovery to identify bad sectors:

1. Click **Scan** in the Operation Toolbar
2. Use Standard or Thorough mode
3. Review results in the Analytics Panel

### Step 2: Review Bad Sectors

Before starting recovery:

- Check the Errors tab to see the list of bad sectors
- Note any patterns (clustered vs scattered)
- Assess whether recovery is viable

### Step 3: Open Restore Dialog

Click **Restore** in the Operation Toolbar to open the configuration dialog.

### Step 4: Configure Recovery

1. Select **Recovery Mode** (Fixed Passes or Convergence)
2. Choose **Recovery Scope** (Full Disk or Targeted)
3. Enable **Multi-Read Recovery** if desired
4. Select **Recovery Level** (Standard/Aggressive/Forensic)
5. Adjust **Advanced Options** if needed
6. Configure **Report Options**
7. Click **Start Restore**

### Step 5: Monitor Progress

![Recovery Progress Screen](../screenshots/restore_progress.png)
*Screenshot: Recovery progress display showing pass information and sector status*

During recovery, the interface shows:

| Element | Description |
|---------|-------------|
| **Current Pass** | Pass number and total passes |
| **Bad Sectors** | Starting count → current count |
| **Recovery Rate** | Percentage of bad sectors recovered |
| **Current Track** | Cylinder and head being processed |
| **Technique** | Current recovery technique being applied |
| **Elapsed/ETA** | Time tracking |

The circular sector map updates to show:
- Green: Good sectors
- Red: Still bad sectors
- Orange: Recovered sectors

### Step 6: Verification

After recovery passes complete:

1. Automatic verification scan runs
2. All originally-bad sectors are re-checked
3. If verification passes, recovery is complete
4. If verification fails, another recovery attempt begins (up to 3 total)

### Step 7: Review Results

When recovery completes:

- Summary shows total recovered vs remaining bad
- Recovered sectors appear orange on the sector map
- Full statistics available in Analytics Panel
- Report generated if enabled

---

## Understanding Results

### Recovery Statistics

The recovery report includes:

| Statistic | Description |
|-----------|-------------|
| **Initial Bad Sectors** | Count at start of recovery |
| **Final Bad Sectors** | Count after all attempts |
| **Sectors Recovered** | Total successfully recovered |
| **Recovery Rate** | Percentage of bad sectors fixed |
| **Passes Completed** | Number of recovery passes run |
| **Converged** | Whether improvement stopped |
| **Total Time** | Duration of recovery operation |

### Technique Breakdown

The report shows which techniques recovered sectors:

| Technique | Description |
|-----------|-------------|
| **format_refresh** | Recovered by rewriting track |
| **multi_capture** | Recovered by statistical bit voting |
| **pll_tuning** | Recovered by adjusting decoder timing |
| **bit_slip** | Recovered by fixing sync errors |
| **maximum_effort** | Recovered by combined techniques |

### Per-Pass History

Each pass records:

- Bad count before and after
- Sectors recovered during that pass
- Duration

This helps identify when recovery is most effective and when it reaches diminishing returns.

---

## Recovery Best Practices

### Before Recovery

1. **Scan first** — Understand the disk condition
2. **Clean the disk** — Gently clean if contaminated (distilled water or isopropyl alcohol)
3. **Clean drive heads** — Ensure heads are clean for optimal reading
4. **Use a good drive** — Try a known-working drive

### During Recovery

1. **Start with Standard** — Escalate to Aggressive/Forensic only if needed
2. **Enable Convergence Mode** — Let recovery run until improvement stops
3. **Minimize vibration** — Keep the workspace stable
4. **Be patient** — Forensic recovery can take considerable time

### After Recovery

1. **Export immediately** — Save recovered data to an image file
2. **Verify the data** — Check that recovered files are usable
3. **Preserve the disk** — Keep the original in case future techniques improve
4. **Document results** — Save the recovery report

### Environmental Factors

| Factor | Recommendation |
|--------|----------------|
| **Temperature** | Room temperature (20-25°C) |
| **Humidity** | Moderate (40-60%) |
| **Vibration** | Minimize; use stable surface |
| **Power** | Avoid unstable power that could affect timing |

---

## When Recovery Fails

### Partial Recovery

If some sectors cannot be recovered:

1. **Export what you have** — Save the partially recovered image
2. **Try a different drive** — Head alignment varies between drives
3. **Try different PLL settings** — Manual tuning may find better parameters
4. **Consider professional services** — Data recovery specialists have additional tools

### Assessing Unrecoverable Sectors

| Pattern | Likely Cause | Prognosis |
|---------|--------------|-----------|
| Scattered sectors | Media degradation | Often partly recoverable |
| Entire tracks | Physical damage | May need professional help |
| One head entirely bad | Head alignment/drive issue | Try different drive |
| No data readable | Demagnetization | Usually not recoverable |

### Professional Data Recovery

For critical data that cannot be recovered:

- Professional data recovery services have clean room facilities
- Specialized equipment can read weaker signals
- Magnetic force microscopy (extreme cases) can image the surface directly
- Cost varies significantly; get quotes for critical data

### Accepting Loss

Sometimes data cannot be recovered:

- Severe physical damage (scratches through the magnetic layer)
- Complete demagnetization (no signal remaining)
- Fire or water damage
- Oxide separation from substrate

Document what was lost. Preserve the disk—future technology may improve recovery possibilities.

---

**Next:** [[Flux Analysis]] — Understanding flux-level data
