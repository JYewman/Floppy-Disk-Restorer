# Exporting Images

This guide covers saving disk contents to image files using Floppy Disk Workbench.

## Table of Contents

- [Image Formats Overview](#image-formats-overview)
- [Export Configuration](#export-configuration)
- [Export Options](#export-options)
- [Export Process](#export-process)
- [Format Details](#format-details)
- [Format Comparison](#format-comparison)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Image Formats Overview

Floppy Disk Workbench supports two categories of disk images:

### Sector Images

Store decoded sector data with no timing information:

| Format | Extension | Description |
|--------|-----------|-------------|
| **IMG/IMA** | .img, .ima | Raw sector dump (no header) |
| **DSK** | .dsk | CPC/Spectrum format with header |

### Flux Images

Store raw magnetic flux transition data:

| Format | Extension | Description |
|--------|-----------|-------------|
| **SCP** | .scp | SuperCard Pro flux format |
| **HFE** | .hfe | HxC Floppy Emulator format |

### Choosing a Format

| Scenario | Recommended Format |
|----------|-------------------|
| **Working disk for emulators** | IMG |
| **Archival preservation** | SCP |
| **Copy-protected software** | SCP |
| **Damaged disk backup** | SCP |
| **Gotek or HxC device** | HFE |
| **Minimal storage** | IMG |

---

## Export Configuration

Click the **Export** button in the Operation Toolbar or press `Ctrl+E` to open the Export Configuration dialog.

![Export Dialog](../screenshots/export_dialog.png)
*Screenshot: Export Configuration dialog showing format selection and options*

### Export Type

Select the image format to export:

| Type | Description |
|------|-------------|
| **Sector Image (IMG/IMA)** | Standard sector image, compatible with emulators and disk utilities |
| **Flux Image (SCP)** | Raw flux data in SuperCard Pro format, best for archival and preservation |
| **Flux Image (HFE)** | Flux image for HxC Floppy Emulator hardware and Gotek drives |

The dialog displays a brief description for each format type to help with selection.

---

## Export Options

### Sector Image Options

When exporting to IMG/IMA format:

| Option | Description |
|--------|-------------|
| **Include bad sectors as zeros** | Fill unreadable sectors with zero bytes |
| **Pad to standard size (1.44MB)** | Ensure image is exactly 1,474,560 bytes |

Padding ensures compatibility with emulators that expect standard-size images.

### Flux Image Options

When exporting to SCP or HFE format:

| Option | Description | Range |
|--------|-------------|-------|
| **Revolutions to capture** | Number of disk rotations per track | 1-10 |
| **Normalize flux timing** | Adjust timing for consistency across captures | On/Off |

More revolutions provide better data for recovery but increase file size. The default is 2 revolutions. For archival preservation, use 3-5 revolutions.

### Compression

| Option | Description |
|--------|-------------|
| **Compress output** | Apply compression to the output file |
| **Compression type** | None, ZIP, or GZIP |

Compression reduces file size but may affect compatibility with some tools.

### File Destination

| Field | Description |
|-------|-------------|
| **File path** | Full path for the output file |
| **Browse** | Opens file dialog to select save location |

The file extension updates automatically based on the selected format type.

---

## Export Process

### Step 1: Scan First

Before exporting:

1. Perform a complete scan to identify disk condition
2. Note any bad sectors
3. Decide on format based on disk health

For damaged disks, SCP format preserves raw data for future recovery attempts.

### Step 2: Configure Export

1. Click **Export** in the Operation Toolbar
2. Select the format type (IMG, SCP, or HFE)
3. Configure format-specific options
4. Enable compression if desired
5. Choose the output file location
6. Click **Export**

### Step 3: Monitor Progress

![Export Progress](../screenshots/export_progress.png)
*Screenshot: Export progress display*

During export, the interface shows:

| Element | Description |
|---------|-------------|
| **Progress bar** | Percentage complete |
| **Current track** | Cylinder and head being processed |
| **Elapsed time** | Time since export started |
| **File size** | Current size of the output file |

### Step 4: Completion

When export completes:

- A completion message appears
- The exported file is ready for use
- The summary shows file location and size

---

## Format Details

### IMG/IMA Format

The simplest disk image format containing raw sector data.

**Structure:**
- No header
- Sectors stored sequentially
- Sector order: Track 0 Head 0, Track 0 Head 1, Track 1 Head 0, etc.

**File Sizes:**

| Disk Type | Size | Geometry |
|-----------|------|----------|
| 3.5" HD (1.44MB) | 1,474,560 bytes | 80/2/18 |
| 3.5" DD (720KB) | 737,280 bytes | 80/2/9 |
| 5.25" HD (1.2MB) | 1,228,800 bytes | 80/2/15 |
| 5.25" DD (360KB) | 368,640 bytes | 40/2/9 |
| 3.5" ED (2.88MB) | 2,949,120 bytes | 80/2/36 |

**Compatibility:** Nearly all emulators and disk utilities.

### SCP Format (SuperCard Pro)

Industry-standard flux image format for disk preservation.

**Header Structure:**
- "SCP" signature
- Version and disk type
- Track range and revolution count
- Flags and resolution settings
- Data checksum

**Features:**
- Multiple revolutions per track (1-10)
- High-precision timing (25ns resolution)
- Preserves all magnetic data
- Full copy protection support

**File Sizes:** 5-50 MB depending on revolutions and track count.

**Compatibility:** Greaseweazle, SuperCard Pro, Kryoflux, various analysis tools.

### HFE Format (HxC Floppy Emulator)

Flux image format designed for floppy emulation hardware.

**Header Structure:**
- "HXCPICFE" signature
- Track and side count
- Encoding type and bit rate
- Track data offset table

**Encoding Types:**
- MFM (IBM PC)
- AMIGA_MFM
- FM (older formats)

**Features:**
- Good compression
- Playback-oriented design
- Wide hardware support

**File Sizes:** 2-10 MB typical.

**Compatibility:** Gotek drives, HxC floppy emulators, some PC emulators.

---

## Format Comparison

### Feature Comparison

| Feature | IMG | SCP | HFE |
|---------|-----|-----|-----|
| **Preserves timing** | No | Yes | Partial |
| **Multiple revolutions** | No | Yes | No |
| **Copy protection** | No | Yes | Partial |
| **Header information** | No | Yes | Yes |
| **Emulator support** | Wide | Limited | Good |
| **Recovery potential** | None | High | Medium |
| **File validation** | N/A | Checksum | Basic |

### Size Comparison

| Disk Type | IMG | SCP (2 rev) | SCP (5 rev) | HFE |
|-----------|-----|-------------|-------------|-----|
| 1.44MB HD | 1.4 MB | 10-15 MB | 20-30 MB | 3-5 MB |
| 720KB DD | 0.7 MB | 8-12 MB | 15-25 MB | 2-3 MB |

### Use Case Recommendations

| Use Case | Format | Notes |
|----------|--------|-------|
| **Daily use with emulators** | IMG | Maximum compatibility |
| **Long-term preservation** | SCP | Full magnetic capture |
| **Copy-protected games** | SCP | Only option for protection |
| **Damaged disk backup** | SCP | Preserves weak areas |
| **Gotek/FlashFloppy** | HFE | Native support |
| **Share with others** | IMG | Universal format |
| **Storage-constrained** | IMG | Smallest size |

---

## Best Practices

### For Working Disks

1. Scan to verify all sectors are good
2. Export as IMG for convenience
3. Optionally create SCP backup for archival

### For Damaged Disks

1. Always export as SCP first to preserve raw data
2. Use multiple revolutions (3-5) for better recovery chances
3. Then attempt recovery and export usable IMG

### For Archival Preservation

1. Use SCP format with 5 revolutions
2. Enable all tracks (even empty ones)
3. Store multiple copies in different locations
4. Document disk information in filename

### Naming Conventions

Suggested filename format:
```
[Label]_[Type]_[Date].[ext]

Examples:
DOS622_Disk1_HD_2024-01-15.scp
WordPerfect51_DD_2024-01-15.img
Protected_Game_Master_2024-01-15.scp
```

### Storage Recommendations

| Medium | Notes |
|--------|-------|
| **SSD/HDD** | Multiple locations recommended |
| **Cloud storage** | Good for offsite backup |
| **Optical (BD-R)** | Good for long-term archival |
| **M-DISC** | Best for permanent preservation |

---

## Troubleshooting

### "Export failed - read error"

**Cause:** Disk has unreadable sectors.

**Solutions:**
- Enable "Include bad sectors as zeros" for IMG export
- Export as SCP to preserve raw data
- Run recovery first, then export

### File Size Incorrect

**Cause:** Disk type setting may not match physical disk.

**Solutions:**
- Verify disk type in scan results
- Check "Pad to standard size" option for IMG
- Ensure full disk was scanned before export

### Verification Failed

**Cause:** Disk changed during export or drive issues.

**Solutions:**
- Ensure disk is properly seated
- Check drive heads are clean
- Try export again
- Check drive motor stability

### "No space on device"

**Cause:** Insufficient disk space for output file.

**Solutions:**
- SCP files can be large (20-50 MB)
- Clear space or use different location
- Use IMG format for smaller file size
- Enable compression

### Exported File Won't Open

**Cause:** Tool doesn't support the format.

**Solutions:**
- Verify the tool supports the exported format
- IMG has widest compatibility
- HFE for floppy emulator hardware
- SCP for flux analysis tools

### Export Takes Too Long

**Cause:** Multiple revolutions increase time.

**Solutions:**
- Reduce revolutions (1-2 for quick exports)
- Use IMG format (sector-level is faster)
- Check drive is functioning properly

---

## Using Exported Images

### With Emulators

| Emulator | IMG | SCP | HFE |
|----------|-----|-----|-----|
| **DOSBox** | Yes | No | No |
| **86Box** | Yes | No | No |
| **PCem** | Yes | No | No |
| **WinUAE** | Yes | Yes | Yes |
| **FS-UAE** | Yes | Yes | Yes |
| **MAME** | Yes | Some | Some |

### Writing Back to Disk

To write an exported image to a physical disk:

1. Click **Write Image** in the Operation Toolbar
2. Select the source image file
3. Insert a blank or sacrificial disk
4. Configure write options
5. Start write operation

See [[Write Image]] for details.

### Converting Between Formats

**SCP to IMG:**
- Requires decoding flux to sectors
- Use Scan operation on SCP file
- Export result as IMG
- Note: Loses timing data

**IMG to SCP:**
- Not recommended for archival
- Creates synthetic flux from sector data
- Not same as original flux capture

---

**Next:** [[Batch Operations]] - Working with multiple disks
