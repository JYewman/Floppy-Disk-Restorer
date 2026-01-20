# Batch Operations

This guide covers verifying multiple floppy disks efficiently using Floppy Disk Workbench.

## Table of Contents

- [Batch Verification Overview](#batch-verification-overview)
- [Configuration](#configuration)
- [Analysis Depth](#analysis-depth)
- [Running Batch Verification](#running-batch-verification)
- [Understanding Results](#understanding-results)
- [Managing Disk Collections](#managing-disk-collections)
- [Best Practices](#best-practices)

---

## Batch Verification Overview

### What is Batch Verification?

Batch Verification allows you to verify multiple floppy disks in sequence, testing each disk's readability and generating comprehensive reports.

### Use Cases

| Scenario | Benefit |
|----------|---------|
| **Collection triage** | Sort good disks from damaged ones |
| **Pre-imaging check** | Identify problem disks before archival |
| **Archive verification** | Periodic health checks on stored disks |
| **Quality control** | Verify newly formatted or written disks |
| **Media testing** | Compare reliability across brands |

### What You Get

- Per-disk quality grades (A through F)
- Sector-level error reports
- Track-by-track analysis
- Recommendations for each disk
- Summary statistics for the batch
- Exportable reports

---

## Configuration

Click **Batch Verify** in the Operations menu to open the Batch Verification Configuration dialog.

![Batch Verify Configuration Dialog](../screenshots/batch_verify_config_dialog.png)
*Screenshot: Batch Verification Configuration dialog*

### Batch Information

| Setting | Description |
|---------|-------------|
| **Batch Name** | Name or description for the batch (e.g., "Office Disks 2024") |
| **Media Brand** | Default brand for the batch |
| **Number of Disks** | How many disks to verify (1-50) |

### Supported Brands

The media brand field helps track disk quality by manufacturer:

- Sony
- TDK
- Maxell
- Fujifilm
- Memorex
- Imation
- Verbatim
- 3M
- Generic/Unknown
- Other

### Serial Numbers (Optional)

Enable serial number tracking to identify disks during and after verification:

| Option | Description |
|--------|-------------|
| **Use serial numbers** | Enable serial number entry for each disk |
| **Serial input fields** | Enter serial for each disk position (1, 2, 3...) |

When enabled, you can enter the serial number printed on each disk. During verification, prompts will reference the serial number to help identify which disk to insert.

---

## Analysis Depth

Select the thoroughness of verification for each disk.

### Quick

| Characteristic | Value |
|----------------|-------|
| **Tracks analyzed** | Sample only (0, 20, 40, 60, 79) |
| **Revolutions** | 1.2 |
| **Best for** | Initial screening, large collections |

Quick mode reads only five strategic track positions per side, providing a fast assessment suitable for initial triage of large collections.

### Standard

| Characteristic | Value |
|----------------|-------|
| **Tracks analyzed** | All 160 tracks |
| **Revolutions** | 2.0 |
| **Best for** | Normal verification |

Standard mode verifies every track on the disk with two-revolution capture. Recommended for most verification tasks.

### Thorough

| Characteristic | Value |
|----------------|-------|
| **Tracks analyzed** | All 160 tracks |
| **Revolutions** | 3.0 |
| **Best for** | Detailed quality assessment |

Thorough mode uses additional revolutions per track for more accurate detection of weak or marginal sectors.

### Forensic

| Characteristic | Value |
|----------------|-------|
| **Tracks analyzed** | All 160 tracks |
| **Revolutions** | 5.0 |
| **Best for** | Critical verification, copy protection detection |

Forensic mode provides the most detailed analysis with maximum capture revolutions. Use for important disks or when copy protection detection is needed.

---

## Running Batch Verification

### Step 1: Configure Batch

1. Click **Batch Verify** in the Operations menu
2. Enter a **Batch Name**
3. Select **Media Brand** if known
4. Set **Number of Disks**
5. Optionally enable and enter **Serial Numbers**
6. Choose **Analysis Depth**
7. Click **Start Batch**

### Step 2: Insert First Disk

After clicking Start Batch:

1. A prompt appears asking for the first disk
2. Insert the disk into the drive
3. Click **Continue** to begin verification

If serial numbers are enabled, the prompt will display which serial number is expected.

### Step 3: Monitor Progress

![Batch Verify Progress](../screenshots/batch_verify_progress.png)
*Screenshot: Batch verification in progress*

During verification, the interface shows:

| Element | Description |
|---------|-------------|
| **Current disk** | Which disk number is being verified |
| **Track progress** | Current track being read |
| **Sector status** | Live sector map updates |
| **Results list** | Completed disks with grades |

### Step 4: Continue Through Batch

After each disk completes:

1. Results display for the completed disk
2. A prompt appears for the next disk
3. Remove the completed disk (sort into appropriate bin)
4. Insert the next disk
5. Click **Continue**

### Controls During Batch

| Button | Action |
|--------|--------|
| **Skip** | Skip current disk, mark as skipped |
| **Retry** | Re-verify the current disk |
| **Pause** | Pause after current disk completes |
| **Stop** | End batch early, keep completed results |

### Step 5: Review Final Results

When all disks are verified (or batch is stopped):

- Summary statistics display
- Report can be exported
- Detailed results available for each disk

---

## Understanding Results

### Quality Grades

Each disk receives a letter grade based on its overall quality score:

| Grade | Score | Description |
|-------|-------|-------------|
| **A** | ≥95% | Excellent - all sectors readable |
| **B** | ≥85% | Good - minor issues only |
| **C** | ≥70% | Fair - some problems, backup recommended |
| **D** | ≥50% | Poor - significant issues, backup immediately |
| **F** | <50% | Failed - extensive damage, recovery needed |
| **S** | N/A | Skipped - disk was skipped during batch |

### Per-Disk Results

Each verified disk shows:

| Metric | Description |
|--------|-------------|
| **Grade** | Overall letter grade |
| **Score** | Numeric quality percentage |
| **Good sectors** | Sectors with valid CRC |
| **Bad sectors** | Sectors with CRC errors |
| **Weak sectors** | Marginal sectors (low signal quality) |
| **Missing sectors** | Sectors not found |
| **Bad tracks** | Number of tracks with errors |
| **Duration** | Verification time |

### Track-Level Details

For detailed investigation, each track result includes:

| Field | Description |
|-------|-------------|
| **Cylinder/Head** | Track position |
| **Good/Bad/Missing** | Sector counts |
| **Sector errors** | Specific error for each bad sector |

### Recommendations

Each disk receives automated recommendations based on results:

| Condition | Recommendation |
|-----------|---------------|
| Score ≥95% | "Disk is in excellent condition" |
| Score 85-94% | "Disk is in good condition with minor issues" |
| Score 70-84% | "Disk shows wear - backup recommended" |
| Score 50-69% | "Disk has significant issues - backup immediately" |
| Score <50% | "Disk is in poor condition - data recovery recommended" |

Additional recommendations may include:
- CRC error count
- Missing sector count
- Affected track list
- Head alignment concerns
- Media damage patterns

### Batch Summary

After batch completion:

| Statistic | Description |
|-----------|-------------|
| **Disks verified** | Successfully completed verifications |
| **Disks skipped** | Disks marked as skipped |
| **Disks failed** | Verifications that encountered errors |
| **Average score** | Mean quality score across verified disks |
| **Pass rate** | Percentage with grade C or better |
| **Grade distribution** | Count of each grade (A, B, C, D, F, S) |

---

## Managing Disk Collections

### Physical Organization

During batch verification, prepare sorting bins:

| Bin | Contents | Action |
|-----|----------|--------|
| **Excellent/Good (A-B)** | Healthy disks | Ready for imaging or continued use |
| **Fair (C)** | Minor issues | Priority backup, monitor |
| **Poor/Failed (D-F)** | Damaged disks | Queue for recovery |
| **Skipped** | Not verified | Re-verify later |

### Labeling Strategy

Consistent labeling helps track disks through the process:

| Strategy | Example | Best For |
|----------|---------|----------|
| **Sequential** | DISK001, DISK002 | Large anonymous collections |
| **Descriptive** | "Tax 1998", "Games" | Known content |
| **Box-Position** | BOX1-01, BOX1-02 | Physical organization |
| **Date-Serial** | 2024-01-001 | Dated acquisitions |

### Tracking Inventory

Use the serial number feature to maintain inventory:

1. Enable serial numbers in configuration
2. Enter disk serials before starting
3. Serial appears in prompts and results
4. Export results for permanent records

---

## Best Practices

### Before Starting

1. **Test drive** - Verify with a known-good disk first
2. **Organize workspace** - Prepare sorting bins
3. **Plan time** - Allocate sufficient time for the batch size
4. **Clean drive heads** - Ensure optimal read quality

### During Batch

1. **Maintain pace** - Don't rush, errors happen when fatigued
2. **Sort immediately** - Place each disk in appropriate bin
3. **Note anomalies** - Make notes on unusual disks
4. **Take breaks** - Pause every 25-50 disks

### Batch Size Recommendations

| Collection Size | Approach |
|-----------------|----------|
| 1-25 disks | Single session |
| 25-50 disks | One session with breaks |
| 50-100 disks | Split into multiple sessions |
| 100+ disks | Multi-day project, plan accordingly |

### Handling Problem Disks

When a disk shows poor results:

1. **Don't retry immediately** - Continue batch
2. **Note the serial/label** - For later attention
3. **Sort into problem bin** - Handle after batch
4. **Try different drive** - Head alignment varies
5. **Consider recovery** - If data is important

### Quality Assurance

For important collections:

1. **Verify 10% of "good" disks** with Thorough mode
2. **Re-check stiff or tight disks** - Mechanical issues affect reads
3. **Listen for unusual sounds** - Drive issues affect all results
4. **Compare across brands** - Note reliability patterns

### After Batch Completion

1. **Export report** - Save for permanent records
2. **Process problem disks** - Queue for recovery
3. **Image good disks** - Archive while they're working
4. **Store properly** - Vertical, cool, dry, away from magnets

---

## Troubleshooting

### "Verification failed" on multiple disks

**Cause:** Drive issue rather than disk issue.

**Solutions:**
- Clean drive heads
- Test with known-good disk
- Check drive connections
- Try a different drive

### Inconsistent results

**Cause:** Marginal disk or drive alignment issues.

**Solutions:**
- Retry with Thorough mode
- Try same disk in different drive
- Check for physical disk damage

### Batch runs very slowly

**Cause:** Using Forensic mode or drive issues.

**Solutions:**
- Use Standard mode for initial triage
- Reserve Thorough/Forensic for important disks
- Check drive motor speed

### Can't read any disks

**Cause:** Drive not properly connected or configured.

**Solutions:**
- Check Greaseweazle connection
- Verify drive selection
- Test basic scan on single disk first

---

**Next:** [[Supported Disk Formats]] - Formats and compatibility
