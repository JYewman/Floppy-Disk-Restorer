# Formatting Disks

This guide covers low-level formatting of floppy disks with Floppy Disk Workbench.

## Table of Contents

- [What is Formatting?](#what-is-formatting)
- [When to Format](#when-to-format)
- [Format Types](#format-types)
- [Format Configuration](#format-configuration)
- [Running a Format](#running-a-format)
- [Verification](#verification)
- [Troubleshooting Format Issues](#troubleshooting-format-issues)

---

## What is Formatting?

Formatting writes a fresh data structure to a floppy disk at the magnetic level. This includes:

- **Track markers** — Synchronization patterns that allow the drive to find data
- **Sector headers** — Address marks containing cylinder, head, and sector numbers
- **Data areas** — Filled with a specified byte pattern
- **CRC values** — Checksums for error detection
- **Gap bytes** — Spacing between sectors

### Low-Level vs High-Level Formatting

| Type | What It Does | When to Use |
|------|--------------|-------------|
| **Low-Level** | Writes physical track structure using flux | Floppy Disk Workbench |
| **High-Level** | Creates filesystem (FAT, directory entries) | Operating system |

Floppy Disk Workbench performs **low-level formatting** at the flux level, which can:

- Repair disks that cannot be formatted by an operating system
- Refresh weak magnetic signals on aging media
- Prepare disks for use with non-standard formats
- Test drive write capability

After low-level formatting, you may need to perform a high-level format in your operating system to create a usable filesystem.

---

## When to Format

### Reasons to Format

- **Blank disk preparation** — Initialize new or recycled disks
- **Signal refresh** — Strengthen weak magnetic signals on aging media
- **Media testing** — Verify disks can be reliably written
- **Secure erasure** — Remove data by overwriting with multiple patterns
- **Format conversion** — Change disk format (e.g., PC to Amiga)

### When NOT to Format

- **Data recovery needed** — Formatting destroys all existing data
- **Unknown disk contents** — Scan first to assess what is on the disk
- **Write-protected disk** — Remove write protection first
- **Valuable data** — Create a disk image backup first

**Warning**: Formatting permanently erases all data on the disk. This cannot be undone.

---

## Format Types

Floppy Disk Workbench provides three format types, each suited for different purposes.

### Standard Format

Performs a normal format operation with a single pattern write.

| Characteristic | Value |
|----------------|-------|
| Erase Method | DC erase per track |
| Write Passes | 1 |
| Fill Pattern | User-selected (default 0xE5) |
| Speed | Fast |

The standard format erases each track using a DC erase pulse, then writes the track structure with the selected fill pattern. This is the recommended option for routine formatting.

### Low-Level Refresh

Performs DC erase followed by multiple pattern writes to refresh magnetic domains.

| Characteristic | Value |
|----------------|-------|
| Erase Method | DC erase per track |
| Write Passes | 5 |
| Patterns | 0x00, 0xFF, 0xAA, 0x55, then selected pattern |
| Speed | Slow |

Low-level refresh is designed to strengthen weak magnetic areas on aging media. Writing multiple different patterns exercises the magnetic domains more thoroughly than a single write.

**Use when:**

- Disks show weak sectors after scanning
- Media is several years old
- Previous format attempts showed marginal results

### Secure Erase

Performs multiple overwrite passes with different patterns for data destruction.

| Characteristic | Value |
|----------------|-------|
| Erase Method | DC erase per track |
| Write Passes | 5 |
| Patterns | 0x00, 0xFF, 0xAA, 0x55, 0x00 |
| Speed | Slow |

Secure erase overwrites data multiple times with different patterns, making recovery of previous data difficult. Note that for truly sensitive data, physical destruction of the media is more certain.

**Use when:**

- Disposing of disks that contained sensitive information
- Recycling disks that held confidential data
- Compliance requirements mandate secure erasure

---

## Format Configuration

Click the **Format** button in the Operation Toolbar to open the Format Configuration dialog.

![Format Configuration Dialog](../screenshots/format_config_dialog.png)
*Screenshot: Format Configuration dialog showing format type and fill pattern options*

### Format Type Selection

Select the format type using the radio buttons:

| Option | Description |
|--------|-------------|
| **Standard Format** | Normal format with specified fill pattern |
| **Low-Level Refresh** | DC erase plus multiple pattern writes to refresh media |
| **Secure Erase** | Multiple overwrites for data destruction |

### Fill Pattern

Select the byte value used to fill data sectors from the dropdown menu:

| Pattern | Value | Description |
|---------|-------|-------------|
| **Zeros** | 0x00 | All bits zero |
| **Ones** | 0xFF | All bits one |
| **Standard** | 0xE5 | DOS/CP-M default fill pattern |
| **Alternating** | 0xAA | 10101010 binary |
| **Inverse Alt** | 0x55 | 01010101 binary |
| **Custom** | 0x00-0xFF | Enter any hex value |

The Standard (0xE5) pattern is the DOS default and is recommended for general use.

To enter a custom pattern:
1. Select "Custom..." from the dropdown
2. Enter a hex value (00-FF) in the text field
3. The value is validated before formatting begins

### Verification

The **Verify after format** checkbox controls whether each track is read back after writing to confirm the format succeeded.

When enabled:
- Each track is read after writing
- Sectors are decoded and checked
- Any verification failures are reported
- Format takes longer but provides confidence

When disabled:
- Tracks are written without read-back
- Faster completion
- No confirmation that data was written correctly

Verification is recommended and is enabled by default.

---

## Running a Format

### Step 1: Select Disk Format

Before formatting, ensure the correct disk format is selected in the Session screen. The format operation uses the session geometry to determine:

- Number of cylinders to format
- Number of heads
- Sectors per track
- Sector size

### Step 2: Open Format Dialog

Click the **Format** button in the Operation Toolbar.

### Step 3: Configure Options

1. Select the format type (Standard, Low-Level Refresh, or Secure Erase)
2. Choose a fill pattern
3. Enable or disable verification
4. Click **Start Format**

### Step 4: Confirm the Operation

A confirmation dialog appears warning that all data will be erased.

![Format Confirmation Dialog](../screenshots/format_confirm_dialog.png)
*Screenshot: Format confirmation warning dialog*

The dialog shows:
- Warning that all data will be permanently erased
- Details about what the format operation will do
- Cancel (default) and "Yes, Format Disk" buttons

Click **Yes, Format Disk** to proceed, or **Cancel** to abort.

### Step 5: Monitor Progress

During formatting, the interface shows:

![Format Progress](../screenshots/format_progress.png)
*Screenshot: Format progress display with track-by-track status*

| Element | Description |
|---------|-------------|
| **Progress Bar** | Overall completion percentage |
| **Current Track** | Cylinder and head being formatted |
| **Phase** | Current operation (Erasing, Writing, Verifying) |
| **Errors** | Count of tracks that failed |
| **Elapsed Time** | Time since format started |

### Step 6: Review Results

When formatting completes:

- Success or failure notification appears
- Statistics show tracks formatted and any errors
- Results are available in the Analytics Panel

---

## Verification

### During Format

With verification enabled, each track undergoes:

1. **Erase** — DC erase pulse clears the track
2. **Write** — Sector structure written with fill pattern
3. **Read** — Track read back
4. **Decode** — Sectors decoded and CRC checked
5. **Compare** — Results compared against expectations

A track is considered verified if at least 95% of sectors read back correctly.

### Post-Format Verification

For additional confidence, run a scan after formatting:

1. Click **Scan** in the Operation Toolbar
2. Use Standard scan mode
3. Verify all sectors show as Good (green)

Any sectors showing errors after format may indicate:
- Marginal media quality
- Drive alignment issues
- Physical media damage

---

## Troubleshooting Format Issues

### "No drive selected" Error

**Cause:** Drive has not been calibrated.

**Solution:** Click the **Calibrate** button in the Drive Control Panel to initialize the drive before formatting.

### Write Protection Detected

**Cause:** Disk write-protect tab is set.

**Solution:**
- For 3.5" disks: Slide the tab to close the hole
- For 5.25" disks: Cover the notch with tape

### Format Fails on Track 0

**Possible causes:**
- Physical damage to outer edge of disk
- Drive head alignment issue
- Drive motor speed problem

**Solutions:**
- Try a different disk
- Run drive diagnostics
- Try a different drive

### Verification Failures

| Failure Pattern | Likely Cause | Action |
|-----------------|--------------|--------|
| Single track | Transient issue | Retry format |
| Scattered tracks | Worn media | Discard disk |
| All tracks | Drive problem | Check drive |
| One head only | Head alignment | Run diagnostics |

### Format Stalls or Hangs

**Possible causes:**
- USB connection unstable
- Drive stopped spinning
- Power supply issue

**Solutions:**
- Check USB cable connection
- Verify drive motor is running (should hear spinning)
- Try a powered USB hub
- Restart the application

### Wrong Capacity After Format

**Cause:** Incorrect session format selected.

**Solution:**
1. Check the session format matches the physical disk type
2. HD disks (1.44MB) have a density hole; DD disks (720KB) do not
3. Never format DD disks as HD or vice versa

---

## Technical Details

### Track Structure

Each formatted track contains:

```
GAP4a (80 bytes) → SYNC (12 bytes) → IAM → GAP1 (50 bytes) →
[Sector 1] → GAP3 → [Sector 2] → GAP3 → ... → [Sector N] → GAP4b
```

Each sector contains:

```
SYNC (12 bytes) → IDAM (4 bytes) → C H R N → CRC (2 bytes) →
GAP2 (22 bytes) → SYNC → DAM (4 bytes) → Data (512 bytes) → CRC
```

Where:
- **C** = Cylinder number
- **H** = Head number
- **R** = Record (sector) number
- **N** = Size code (2 = 512 bytes)

### Timing Parameters

| Parameter | HD (1.44MB) | DD (720KB) |
|-----------|-------------|------------|
| Data Rate | 500 Kbps | 250 Kbps |
| Bit Cell | 2.0 µs | 4.0 µs |
| RPM | 300 | 300 |

---

**Next:** [[Recovery Operations]] — Learn about data recovery
