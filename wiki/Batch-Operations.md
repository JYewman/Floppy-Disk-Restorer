# Batch Operations

This guide covers processing multiple disks efficiently with Floppy Workbench.

## Table of Contents

- [Batch Verification](#batch-verification)
- [Setting Up Batch Verify](#setting-up-batch-verify)
- [Running Batch Operations](#running-batch-operations)
- [Managing Disk Collections](#managing-disk-collections)
- [Batch Results](#batch-results)
- [Workflow Tips](#workflow-tips)

---

## Batch Verification

### What is Batch Verification?

Batch Verification allows you to verify multiple floppy disks in sequence:

- Test each disk's readability
- Generate reports for collections
- Sort disks by condition
- Prepare for imaging or archival

### Use Cases

| Scenario | Benefit |
|----------|---------|
| **Disk collection triage** | Sort good from bad disks |
| **Pre-imaging check** | Identify problem disks before imaging |
| **Archive verification** | Check stored disks periodically |
| **Quality control** | Verify newly formatted disks |

---

## Setting Up Batch Verify

### Opening Batch Verify

Click **Batch Verify** in the Operations menu or press `Ctrl+B`

### Configuration Dialog

```
┌─────────────────────────────────────────────────────────────────┐
│                    BATCH VERIFY CONFIGURATION                    │
├─────────────────────────────────────────────────────────────────┤
│  DISK SETTINGS                                                   │
│  ─────────────                                                   │
│  Disk Type:        [1.44MB HD    ▼]                             │
│  Expected Disks:   [25           ]                              │
│                                                                  │
│  VERIFICATION OPTIONS                                            │
│  ────────────────────                                            │
│  Scan Mode:        [Standard     ▼]                             │
│  Verify Reads:     [✓]                                          │
│  Auto-advance:     [✓] Prompt for next disk                     │
│                                                                  │
│  OUTPUT                                                          │
│  ──────                                                          │
│  Generate Report:  [✓]                                          │
│  Report File:      [batch_report.html        ] [Browse]         │
│                                                                  │
│  DISK LABELS                                                     │
│  ───────────                                                     │
│  [✓] Prompt for label on each disk                              │
│  [ ] Use sequential numbers                                      │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│              [Cancel]                    [Start Batch]          │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration Options

| Option | Description |
|--------|-------------|
| **Disk Type** | Format of disks being verified |
| **Expected Disks** | Approximate count (for progress) |
| **Scan Mode** | Quick, Standard, or Thorough |
| **Verify Reads** | Double-read for accuracy |
| **Auto-advance** | Automatic prompt for next disk |
| **Generate Report** | Create summary report |
| **Disk Labels** | How to identify each disk |

---

## Running Batch Operations

### Batch Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                     BATCH VERIFICATION                           │
├─────────────────────────────────────────────────────────────────┤
│  Progress: Disk 7 of ~25                                         │
│  ═════════════════════════════════════════════                   │
│                                                                  │
│  CURRENT DISK                                                    │
│  ────────────                                                    │
│  Label: "Accounting Backup 1998"                                 │
│  Status: Scanning... Track 45/80                                 │
│                                                                  │
│  RESULTS SO FAR                                                  │
│  ──────────────                                                  │
│  ✓ Disk 1: "Reports Q1" - 100% Good                             │
│  ✓ Disk 2: "Reports Q2" - 100% Good                             │
│  ⚠ Disk 3: "Reports Q3" - 97.5% (72 weak)                       │
│  ✗ Disk 4: "Archives" - 89.2% (312 bad)                         │
│  ✓ Disk 5: "System Backup" - 100% Good                          │
│  ✓ Disk 6: "Data Files" - 99.8% (6 weak)                        │
│                                                                  │
│  Summary: 6 verified | 4 good | 1 fair | 1 bad                  │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  [Skip Disk]  [Pause]  [Stop Batch]                             │
└─────────────────────────────────────────────────────────────────┘
```

### Between Disks

After each disk completes:

```
┌────────────────────────────────────────────────────┐
│  DISK COMPLETE                                      │
│                                                     │
│  Results for "Reports Q3":                          │
│  Total Sectors: 2,880                              │
│  Good: 2,808 (97.5%)                               │
│  Weak: 72 (2.5%)                                   │
│  Bad: 0                                            │
│                                                     │
│  INSERT NEXT DISK                                   │
│                                                     │
│  Enter label (optional):                           │
│  [Archives 1999                    ]               │
│                                                     │
│  [Skip] [Retry This Disk] [Continue]              │
└────────────────────────────────────────────────────┘
```

### Pausing and Resuming

- Click **Pause** to halt after current disk
- Click **Resume** to continue
- Progress is preserved during pause

### Stopping Batch

- Click **Stop Batch** to end early
- Results for completed disks are saved
- Report includes partial results

---

## Managing Disk Collections

### Labeling Strategy

Consistent labeling helps track disks:

| Strategy | Example | Best For |
|----------|---------|----------|
| **Sequential** | DISK001, DISK002 | Large anonymous collections |
| **Descriptive** | "Tax 1998", "Games" | Organized archives |
| **Box-Disk** | BOX1-01, BOX1-02 | Physical organization |
| **Date-based** | 2024-01-15-001 | Dated acquisitions |

### Physical Organization

During batch verification:

1. **Prepare sorted bins**:
   - Good disks
   - Needs attention
   - Failed/bad disks

2. **Sort as you go**:
   - Move each verified disk to appropriate bin
   - Mark problem disks for recovery

3. **Document**:
   - Note disk labels
   - Record any observations

### Tracking Inventory

For large collections:

```
Disk ID     | Label              | Status  | Bad% | Notes
──────────────────────────────────────────────────────────
BOX1-001    | System Disk        | Good    | 0%   |
BOX1-002    | Word Processing    | Good    | 0%   |
BOX1-003    | Data Backup        | Fair    | 2.5% | Track 40 weak
BOX1-004    | Archive 1997       | Bad     | 15%  | Needs recovery
```

---

## Batch Results

### Summary Report

After batch completion:

```
┌─────────────────────────────────────────────────────────────────┐
│                    BATCH VERIFICATION REPORT                     │
├─────────────────────────────────────────────────────────────────┤
│  Date: 2024-01-15 14:32                                          │
│  Duration: 45 minutes                                            │
│  Disks Verified: 25                                              │
│                                                                  │
│  SUMMARY                                                         │
│  ───────                                                         │
│  ✓ Excellent (100%):     18 disks                               │
│  ✓ Good (95-99%):         4 disks                               │
│  ⚠ Fair (80-94%):         2 disks                               │
│  ✗ Poor (<80%):           1 disk                                │
│                                                                  │
│  DISKS NEEDING ATTENTION                                         │
│  ───────────────────────                                         │
│  • Archive 1997 (BOX1-004): 15% bad - RECOVERY NEEDED           │
│  • Data Backup (BOX1-003): 2.5% weak - MONITOR                  │
│  • Tax Files (BOX2-012): 6% weak - MONITOR                      │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  [Export CSV]  [Export HTML]  [Print]  [Close]                  │
└─────────────────────────────────────────────────────────────────┘
```

### Export Options

| Format | Description |
|--------|-------------|
| **HTML Report** | Formatted report with charts |
| **CSV** | Spreadsheet-compatible data |
| **PDF** | Printable document |

### Report Contents

Full reports include:

1. **Summary statistics**
2. **Per-disk details**
3. **Error distribution charts**
4. **Recommendations**
5. **Disk condition ranking**

---

## Workflow Tips

### Efficient Processing

1. **Pre-sort by type** - Group HD and DD disks separately
2. **Check drive first** - Verify with known-good disk
3. **Prepare workspace** - Have bins and labels ready
4. **Take breaks** - Don't rush, errors happen when tired

### For Large Collections

| Collection Size | Approach |
|-----------------|----------|
| 1-25 disks | Single session |
| 25-100 disks | Multiple sessions, 25-50 per session |
| 100+ disks | Plan multi-day project |

### Quality Assurance

- Verify ~10% of "good" disks with Thorough scan
- Re-check any disks that feel stiff or tight
- Listen for unusual drive sounds

### Problem Disk Handling

When a disk fails:

1. **Don't immediately retry** - Note and continue
2. **Batch problem disks** - Handle together later
3. **Try different drive** - Alignment may help
4. **Consider recovery** - If data is important

### Maintaining Flow

For maximum efficiency:

1. **Have disks ready** - Stack next to drive
2. **Label quickly** - Use shorthand, expand later
3. **Skip detailed analysis** - Save for later
4. **Focus on throughput** - Details after batch

---

## Batch Operation Best Practices

### Pre-Batch Checklist

- [ ] Drive tested with known-good disk
- [ ] Workspace organized
- [ ] Sorting bins labeled
- [ ] Report file location set
- [ ] Adequate time allocated

### During Batch

- [ ] Keep consistent pace
- [ ] Sort disks as verified
- [ ] Note any anomalies
- [ ] Take breaks every 25-50 disks

### Post-Batch

- [ ] Review summary report
- [ ] Plan recovery for bad disks
- [ ] Archive good disk images
- [ ] Store physical disks properly

---

**Next:** [[Supported Disk Formats]] - Formats and compatibility
