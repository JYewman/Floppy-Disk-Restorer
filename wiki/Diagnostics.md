# Diagnostics

This guide covers drive diagnostics and testing features in Floppy Disk Workbench.

## Table of Contents

- [Diagnostics Overview](#diagnostics-overview)
- [The Diagnostics Tab](#the-diagnostics-tab)
- [RPM Monitoring](#rpm-monitoring)
- [Head Alignment Testing](#head-alignment-testing)
- [Read Consistency Test](#read-consistency-test)
- [Drive Health Assessment](#drive-health-assessment)
- [Interpreting Results](#interpreting-results)
- [Drive Maintenance](#drive-maintenance)

---

## Diagnostics Overview

### Purpose

The Diagnostics features help you:

- Verify drive is functioning correctly
- Detect alignment issues
- Monitor motor stability
- Assess overall drive health
- Troubleshoot read/write problems

### When to Use Diagnostics

| Situation | Recommended Test |
|-----------|-----------------|
| New/unknown drive | Full diagnostic suite |
| Inconsistent reads | Consistency test |
| Specific track problems | Head alignment |
| Speed-related errors | RPM monitoring |
| Before critical recovery | All tests |

---

## The Diagnostics Tab

### Location

Found in the Analytics Panel at the bottom of the main window.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  DIAGNOSTICS                                                     │
├─────────────────────────────────────────────────────────────────┤
│  DRIVE STATUS                    │  RPM MONITOR                 │
│  ────────────                    │  ───────────                 │
│  Device: Greaseweazle V4.1       │       ╭──────────────╮       │
│  Firmware: 1.1                   │  302 ─┤              │       │
│  Drive Unit: 0                   │       │    ████████  │       │
│  Motor: Running                  │  300 ─┤    ████████  │       │
│  Current Track: 40               │       │    ████████  │       │
│                                  │  298 ─┤              │       │
│  QUICK TESTS                     │       ╰──────────────╯       │
│  ───────────                     │  Current: 300.2 RPM          │
│  [RPM Test]                      │  Average: 300.1 RPM          │
│  [Alignment Test]                │  Variation: ±0.3%            │
│  [Consistency Test]              │                              │
│  [Full Diagnostic]               │                              │
├─────────────────────────────────────────────────────────────────┤
│  TEST RESULTS                                                    │
│  ────────────                                                    │
│  Last Test: RPM Stability (2024-01-15 14:32)                    │
│  Result: PASS - Speed within tolerance (300.1 RPM ± 0.3%)       │
└─────────────────────────────────────────────────────────────────┘
```

---

## RPM Monitoring

### What It Measures

Floppy drives must spin at a precise speed:

| Standard | Target RPM | Tolerance |
|----------|------------|-----------|
| Most drives | 300 RPM | ±1.5% (295.5-304.5) |
| 5.25" HD | 360 RPM | ±1.5% |

### Running RPM Test

1. Go to **Diagnostics** tab
2. Click **[RPM Test]**
3. Test runs for 10-30 seconds
4. Results displayed

### Understanding Results

```
RPM Test Results
────────────────
Current Speed:  300.2 RPM
Average Speed:  300.1 RPM
Minimum:        299.5 RPM
Maximum:        300.8 RPM
Variation:      ±0.3%
Status:         PASS ✓
```

### RPM Issues

| Symptom | Possible Cause | Solution |
|---------|---------------|----------|
| Too fast | Belt tension too tight | Adjust/replace belt |
| Too slow | Belt slipping, weak motor | Clean/replace belt, check motor |
| Unstable | Bearing wear, power issue | May need drive replacement |
| Wildly varying | Motor controller fault | Replace drive |

---

## Head Alignment Testing

### What It Measures

Head alignment testing checks if the read/write head is properly positioned over the track center.

### Types of Misalignment

| Type | Description | Effect |
|------|-------------|--------|
| **Radial** | Head offset toward/away from center | Reads adjacent track data |
| **Azimuth** | Head angle not perpendicular | Reduced signal, phase errors |
| **Height** | Head flying too high/low | Weak signal |

### Running Alignment Test

1. Insert an alignment disk or known-good disk
2. Go to **Diagnostics** tab
3. Click **[Alignment Test]**
4. Test reads multiple tracks and compares

### Alignment Results

```
Head Alignment Test
───────────────────
Track 0:   ████████████████████  100%
Track 20:  ███████████████████░   95%
Track 40:  ██████████████████░░   90%
Track 60:  █████████████████░░░   85%
Track 79:  ████████████████░░░░   80%

Overall:   MARGINAL ⚠
Recommendation: Signal degrades toward inner tracks.
                Consider professional alignment or different drive.
```

### Interpreting Alignment

| Signal % | Status | Action |
|----------|--------|--------|
| 90-100% | Good | No action needed |
| 70-89% | Marginal | Monitor, may affect some disks |
| 50-69% | Poor | Significant read issues likely |
| <50% | Failed | Drive needs alignment or replacement |

---

## Read Consistency Test

### What It Measures

Reads the same track multiple times to check consistency:

- Same data each time = Good
- Different data = Possible issues

### Running Consistency Test

1. Insert a disk (preferably known-good)
2. Go to **Diagnostics** tab
3. Click **[Consistency Test]**
4. Test performs 10+ reads per track

### Consistency Results

```
Read Consistency Test
─────────────────────
Track 0:  10/10 consistent reads (100%)
Track 20: 10/10 consistent reads (100%)
Track 40: 9/10 consistent reads (90%)
Track 60: 10/10 consistent reads (100%)
Track 79: 8/10 consistent reads (80%)

Overall Consistency: 94%
Status: GOOD ✓

Note: Track 40, 79 show minor inconsistency.
      May be disk-related rather than drive issue.
```

### Consistency Issues

| Consistency | Status | Possible Cause |
|-------------|--------|----------------|
| 95-100% | Excellent | Normal operation |
| 85-94% | Good | Minor issues, acceptable |
| 70-84% | Fair | Drive or disk problems |
| <70% | Poor | Significant issues |

---

## Drive Health Assessment

### Full Diagnostic Suite

Runs all tests in sequence:

1. **Connection Test** - Device communication
2. **Motor Test** - Spin-up and RPM
3. **Seek Test** - Head movement
4. **Read Test** - Basic reading
5. **Consistency Test** - Read reliability
6. **Alignment Test** - Head positioning

### Running Full Diagnostic

1. Insert a test disk
2. Click **[Full Diagnostic]**
3. Wait for all tests to complete (~2-5 minutes)
4. Review comprehensive report

### Health Report

```
┌─────────────────────────────────────────────────────────────────┐
│                    DRIVE HEALTH REPORT                           │
├─────────────────────────────────────────────────────────────────┤
│  Drive: Greaseweazle V4.1 - Unit 0                              │
│  Date: 2024-01-15 14:45                                          │
├─────────────────────────────────────────────────────────────────┤
│  TEST                 │  RESULT  │  DETAILS                     │
│  ─────────────────────┼──────────┼─────────────────────────     │
│  Connection           │  PASS ✓  │  Device responding           │
│  Motor Spin-up        │  PASS ✓  │  0.8s to stable speed        │
│  RPM Stability        │  PASS ✓  │  300.1 RPM ± 0.3%            │
│  Seek Accuracy        │  PASS ✓  │  All tracks accessible       │
│  Read Capability      │  PASS ✓  │  Test sectors readable       │
│  Read Consistency     │  PASS ✓  │  94% consistent              │
│  Head Alignment       │  WARN ⚠  │  80% on inner tracks         │
├─────────────────────────────────────────────────────────────────┤
│  OVERALL STATUS: GOOD (with notes)                              │
│                                                                  │
│  Recommendations:                                                │
│  • Drive is functional for most operations                      │
│  • Inner track alignment is marginal                            │
│  • Consider backup drive for critical recovery                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Interpreting Results

### Status Levels

| Status | Symbol | Meaning |
|--------|--------|---------|
| **PASS** | ✓ | Within specification |
| **WARN** | ⚠ | Marginal, may cause issues |
| **FAIL** | ✗ | Out of specification |

### Common Patterns

| Pattern | Likely Cause |
|---------|--------------|
| All tests pass | Drive is healthy |
| RPM fails, others pass | Motor/belt issue |
| Consistency fails | Head or media issue |
| Alignment fails | Mechanical alignment |
| All tests fail | Major drive problem |

### When to Replace a Drive

Consider replacement when:
- Multiple tests fail consistently
- RPM cannot maintain stable speed
- Alignment is severely off
- Read failures are frequent
- Unusual mechanical sounds

---

## Drive Maintenance

### Regular Maintenance

| Task | Frequency | Method |
|------|-----------|--------|
| **Head cleaning** | Every 40-80 hours | Cleaning disk or manual |
| **Dust removal** | Monthly | Compressed air |
| **Belt inspection** | Yearly | Visual check |
| **Lubrication** | Rarely | Only if needed |

### Head Cleaning

**Using a cleaning disk:**
1. Insert cleaning disk
2. Run for 20-30 seconds
3. Remove and let dry

**Manual cleaning (advanced):**
1. Power off and open drive
2. Use isopropyl alcohol (90%+)
3. Gently clean head with lint-free swab
4. Let dry completely before use

### When NOT to Clean

- Avoid over-cleaning (causes wear)
- Don't clean if no improvement expected
- Don't use harsh chemicals
- Never touch head surface directly

### Drive Storage

If storing a drive:
- Clean heads first
- Store in anti-static bag
- Keep in cool, dry place
- Avoid temperature extremes

---

## Diagnostics Best Practices

### Before Important Work

1. Run RPM test
2. Test with known-good disk
3. Verify at least 90% consistency

### After Drive Issues

1. Run full diagnostic suite
2. Compare to previous results
3. Clean heads if appropriate
4. Try different disk

### Periodic Testing

- Test drives monthly if used regularly
- Test after long storage
- Test after moving equipment

---

**Next:** [[Troubleshooting]] - Common problems and solutions
