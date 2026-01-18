# Formatting Disks

This guide covers formatting floppy disks with Floppy Workbench.

## Table of Contents

- [What is Formatting?](#what-is-formatting)
- [When to Format](#when-to-format)
- [Format Types](#format-types)
- [Format Configuration](#format-configuration)
- [Running a Format](#running-a-format)
- [Verification](#verification)
- [Format Best Practices](#format-best-practices)

---

## What is Formatting?

Formatting writes a fresh data structure to a floppy disk, including:

- **Track markers** - Synchronization patterns
- **Sector headers** - Address marks (cylinder, head, sector)
- **Data areas** - Initialized with fill pattern
- **CRC values** - Error detection checksums
- **Gap bytes** - Spacing between sectors

### Low-Level vs High-Level Formatting

| Type | What It Does | When to Use |
|------|--------------|-------------|
| **Low-Level** | Writes physical track structure | Repairing damaged disks |
| **High-Level** | Creates filesystem (FAT, directory) | Preparing for use |

Floppy Workbench performs **low-level formatting** at the flux level, which can:
- Repair disks that won't format in an OS
- Refresh weak magnetic signals
- Test drive write capability

---

## When to Format

### Good Reasons to Format

- **Blank disk preparation** - New or recycled disks
- **Signal refresh** - Strengthening weak sectors
- **Recovery prep** - Rewriting bad sectors before recovery
- **Secure erase** - Removing sensitive data
- **Testing** - Verifying drive write capability

### When NOT to Format

- **Data recovery needed** - Format destroys existing data!
- **Unknown disk contents** - Scan first to check
- **Write-protected disk** - Remove write protection first
- **Valuable disk** - Make a backup image first

**Warning**: Formatting permanently erases all data on the disk!

---

## Format Types

### Standard Format

**Purpose**: Normal disk formatting

| Parameter | Value |
|-----------|-------|
| Fill Pattern | 0x4E (standard) |
| Verification | Single pass |
| Interleave | 1:1 |
| Speed | Fast |

**Use for**:
- Preparing blank disks
- Normal use

### Low-Level Refresh

**Purpose**: Strengthen weak magnetic signals

| Parameter | Value |
|-----------|-------|
| Fill Pattern | Varies per pass |
| Passes | Multiple (3-5) |
| Verification | Each pass |
| Speed | Slow |

**Use for**:
- Disks with weak sectors
- Aging media refresh
- Pre-recovery treatment

### Secure Erase

**Purpose**: Remove data securely

| Parameter | Value |
|-----------|-------|
| Fill Patterns | Multiple random/fixed |
| Passes | 3-7 (configurable) |
| Verification | Final pass |
| Speed | Very slow |

**Use for**:
- Sensitive data destruction
- Disk recycling
- Compliance requirements

---

## Format Configuration

### Basic Options

#### Disk Type

| Type | Sectors/Track | Cylinders | Capacity |
|------|---------------|-----------|----------|
| **1.44MB HD** | 18 | 80 | 1,474,560 bytes |
| **720KB DD** | 9 | 80 | 737,280 bytes |
| **1.2MB HD** | 15 | 80 | 1,228,800 bytes |
| **360KB DD** | 9 | 40 | 368,640 bytes |

#### Format Mode

- **Standard**: Normal format with verification
- **Refresh**: Multiple passes for signal strengthening
- **Secure**: Multi-pass overwrite with verification

### Advanced Options

| Option | Description | Default |
|--------|-------------|---------|
| **Verify After Write** | Read back each track | On |
| **Fill Pattern** | Byte value for data areas | 0x4E |
| **Gap Length** | Spacing between sectors | Auto |
| **Interleave** | Sector ordering | 1:1 |
| **Retry Failed** | Retry failed tracks | 3 times |

### Fill Patterns

| Pattern | Value | Purpose |
|---------|-------|---------|
| **Standard** | 0x4E | Normal formatting |
| **Zero** | 0x00 | Clean erase |
| **Ones** | 0xFF | Alternative erase |
| **Random** | Varies | Secure erase |
| **Pattern** | 0xAA/0x55 | Testing |

---

## Running a Format

### Step 1: Confirm Disk Selection

1. Verify correct disk is inserted
2. Check disk isn't write-protected
3. Confirm you want to erase all data

### Step 2: Open Format Dialog

Click **Format** button or press `Ctrl+Shift+F`

### Step 3: Configure Format

1. Select disk type (must match physical disk!)
2. Choose format mode
3. Set verification options
4. Click **Start Format**

### Step 4: Confirmation

A confirmation dialog appears:

```
┌────────────────────────────────────────────────────┐
│              ⚠️ CONFIRM FORMAT                      │
│                                                     │
│  You are about to format this disk.                │
│  ALL DATA WILL BE PERMANENTLY ERASED!              │
│                                                     │
│  Disk Type: 1.44MB HD                              │
│  Format Mode: Standard                              │
│  Total Sectors: 2,880                              │
│                                                     │
│  Type "FORMAT" to confirm:  [          ]           │
│                                                     │
│           [Cancel]        [Format]                 │
└────────────────────────────────────────────────────┘
```

### Step 5: Monitor Progress

```
┌────────────────────────────────────────────────────┐
│  Formatting...                                      │
│  ════════════════════════════════════════          │
│  Track: 45/80  |  Head: 0  |  Progress: 56%        │
│                                                     │
│  Phase: Writing  |  Errors: 0                      │
│  Elapsed: 0:45  |  Remaining: 0:35                 │
│                                                     │
│  [Cancel]                                          │
└────────────────────────────────────────────────────┘
```

### Step 6: Review Results

Format complete dialog shows:

- Tracks written successfully
- Verification results
- Any errors encountered

---

## Verification

### During Format

With **Verify After Write** enabled:

1. Track is written
2. Track is read back
3. Data is compared
4. Errors are reported

### Post-Format Verification

After formatting, run a scan to verify:

1. Click **Scan** (`Ctrl+S`)
2. Use Standard scan mode
3. Check all sectors are GOOD

### Verification Failures

If verification fails:

| Error | Cause | Action |
|-------|-------|--------|
| **Write failed** | Drive or disk issue | Try different disk |
| **Verify mismatch** | Media degradation | Retry or discard disk |
| **Partial failure** | Specific track issue | May be recoverable |

---

## Format Best Practices

### For New Disks

1. Use **Standard** format
2. Enable verification
3. Run a scan after formatting
4. Test with actual data

### For Recycled Disks

1. Scan first to check condition
2. Use **Refresh** format if weak sectors found
3. Verify thoroughly
4. Discard if many bad sectors

### For Sensitive Data

1. Use **Secure Erase** mode
2. Set 3+ passes minimum
3. Use random fill patterns
4. Verify each pass

### For Signal Refresh

1. Scan disk first
2. Note weak sector locations
3. Use **Refresh** format
4. Compare before/after scans

### HD Disks in HD Drives

- Use **1.44MB HD** format
- Never format HD disks as DD (reduces capacity and reliability)

### DD Disks

- Use **720KB DD** format
- DD disks cannot be reliably formatted as HD

---

## Troubleshooting Format Issues

### "Write Protected"

- Check write-protect tab on disk
- For 3.5" disks: close the hole
- For 5.25" disks: cover the notch

### "Format Failed - Track 0"

- Track 0 is critical for disk function
- May indicate:
  - Physical damage
  - Drive alignment issue
  - Worn drive heads
- Try different disk or drive

### "Verification Errors"

- Single track: Retry, may be transient
- Multiple tracks: Disk may be worn
- All tracks: Drive or media issue

### "Format Stalls"

- Check drive is still spinning
- Verify USB connection stable
- Try reducing write speed

### "Wrong Capacity After Format"

- Verify correct disk type selected
- HD disks have HD hole, DD disks don't
- Some drives auto-detect incorrectly

---

## Format Technical Details

### Track Structure (1.44MB HD)

```
┌─────────────────────────────────────────────────────────────────────┐
│ GAP4a │ SYNC │ IAM │ GAP1 │ [Sector 1] │ GAP3 │ [Sector 2] │ ... │ │
└─────────────────────────────────────────────────────────────────────┘

Each sector:
┌─────────────────────────────────────────────────────────────────────┐
│ SYNC │ IDAM │ C │ H │ R │ N │ CRC │ GAP2 │ SYNC │ DAM │ Data │ CRC │
└─────────────────────────────────────────────────────────────────────┘

C = Cylinder, H = Head, R = Record (sector number), N = Size code
```

### Timing Parameters

| Parameter | Value (HD) | Value (DD) |
|-----------|------------|------------|
| Data Rate | 500 Kbps | 250 Kbps |
| Bit Cell | 2.0 µs | 4.0 µs |
| RPM | 300 | 300 |

---

**Next:** [[Recovery Operations]] - Learn about data recovery
