# Exporting Images

This guide covers saving disk contents to image files.

## Table of Contents

- [Image Formats Overview](#image-formats-overview)
- [Sector Images](#sector-images)
- [Flux Images](#flux-images)
- [Export Configuration](#export-configuration)
- [Export Process](#export-process)
- [Format Comparison](#format-comparison)
- [Best Practices](#best-practices)

---

## Image Formats Overview

Floppy Workbench supports two categories of disk images:

### Sector Images

Store decoded sector data:

| Format | Extension | Description |
|--------|-----------|-------------|
| **IMG** | .img | Raw sector dump |
| **IMA** | .ima | Same as IMG |
| **DSK** | .dsk | Common for various platforms |

### Flux Images

Store raw magnetic flux data:

| Format | Extension | Description |
|--------|-----------|-------------|
| **SCP** | .scp | SuperCard Pro format |
| **HFE** | .hfe | HxC Floppy Emulator format |

---

## Sector Images

### What They Contain

Sector images store:
- Raw sector data (512 bytes each)
- Sectors in linear order
- No timing or flux information

### IMG/IMA Format

**Structure**:
```
Offset    Content
0x00000   Sector 1, Track 0, Head 0 (512 bytes)
0x00200   Sector 2, Track 0, Head 0 (512 bytes)
...
0x02400   Sector 1, Track 0, Head 1 (512 bytes)
...
```

**File sizes**:

| Disk Type | Size |
|-----------|------|
| 1.44MB HD | 1,474,560 bytes |
| 720KB DD | 737,280 bytes |
| 1.2MB HD | 1,228,800 bytes |
| 360KB DD | 368,640 bytes |

### When to Use Sector Images

**Good for**:
- Disks that read perfectly
- Use in emulators
- Copying between computers
- Smaller file size

**Not good for**:
- Damaged disks (bad sectors become zeros)
- Copy-protected software
- Archival preservation
- Non-standard formats

---

## Flux Images

### What They Contain

Flux images store:
- Raw flux transition times
- Index pulse positions
- Full magnetic representation
- All timing information

### SCP Format (SuperCard Pro)

**Features**:
- Industry standard for preservation
- Multiple revolutions per track
- High-precision timing
- Widely supported

**Structure**:
```
Header:
  - Signature "SCP"
  - Version, disk type
  - Track count, revolution count

Track Data:
  - Flux times (16/32-bit values)
  - Index positions
  - Per-track headers
```

**File sizes**: 5-50 MB depending on revolutions

### HFE Format (HxC)

**Features**:
- Designed for floppy emulators
- Good compression
- Playback-oriented

**File sizes**: 2-10 MB typical

### When to Use Flux Images

**Good for**:
- Archival preservation
- Damaged disk backup
- Copy-protected software
- Non-standard formats
- Later recovery attempts

**Considerations**:
- Larger file sizes
- Requires compatible software to use
- Contains disk defects as-is

---

## Export Configuration

### Opening Export Dialog

Click **Export** or press `Ctrl+E`

### Export Dialog

```
┌─────────────────────────────────────────────────────────────┐
│                      EXPORT DISK IMAGE                       │
├─────────────────────────────────────────────────────────────┤
│  FORMAT                                                      │
│  ──────                                                      │
│  ○ Sector Image (IMG)                                       │
│    Raw sector data. Best for working disks.                 │
│                                                              │
│  ○ Flux Image (SCP)                                         │
│    Raw flux data in SuperCard Pro format. Best for          │
│    archival and preservation.                               │
│                                                              │
│  ○ Flux Image (HFE)                                         │
│    HxC Floppy Emulator format. Good for emulators.         │
├─────────────────────────────────────────────────────────────┤
│  OPTIONS                                                     │
│  ───────                                                     │
│  Revolutions: [3   ] ▼  (flux images only)                  │
│  Include bad sectors: [✓]                                   │
│  Verify after export: [✓]                                   │
├─────────────────────────────────────────────────────────────┤
│  DESTINATION                                                 │
│  ───────────                                                 │
│  File: [                                        ] [Browse]  │
├─────────────────────────────────────────────────────────────┤
│              [Cancel]                    [Export]           │
└─────────────────────────────────────────────────────────────┘
```

### Format Options

#### Sector Image (IMG)

| Option | Description |
|--------|-------------|
| **Bad sector handling** | Fill with zeros or pattern |
| **Verify** | Read back and compare |

#### Flux Image (SCP)

| Option | Description | Recommended |
|--------|-------------|-------------|
| **Revolutions** | Captures per track | 3-5 |
| **All tracks** | Include empty tracks | Yes for archival |
| **Index aligned** | Align to index pulse | Yes |

#### Flux Image (HFE)

| Option | Description |
|--------|-------------|
| **Encoding** | MFM/FM/Auto |
| **Bit rate** | Data rate setting |

---

## Export Process

### Step 1: Scan the Disk

Before exporting:
1. Perform a complete scan
2. Note any bad sectors
3. Decide on format based on condition

### Step 2: Configure Export

1. Click **Export** (`Ctrl+E`)
2. Select format type
3. Set options
4. Choose destination file

### Step 3: Export Progress

```
┌────────────────────────────────────────────────────┐
│  Exporting...                                       │
│  ════════════════════════════════════════          │
│                                                     │
│  Track: 45/80  |  Head: 0  |  Progress: 56%        │
│  Format: SCP   |  Revolutions: 3                   │
│                                                     │
│  Elapsed: 1:23  |  Size: 12.4 MB                   │
│                                                     │
│  [Cancel]                                          │
└────────────────────────────────────────────────────┘
```

### Step 4: Verification

If verification enabled:
1. File is read back
2. Data compared to original
3. Results reported

### Step 5: Completion

```
┌────────────────────────────────────────────────────┐
│  Export Complete                                    │
│                                                     │
│  File: my_disk.scp                                 │
│  Size: 24.7 MB                                     │
│  Tracks: 160 (80 cylinders × 2 heads)              │
│  Revolutions: 3                                     │
│  Duration: 2:45                                     │
│                                                     │
│  ✓ Verification passed                             │
│                                                     │
│  [Open Folder]  [OK]                               │
└────────────────────────────────────────────────────┘
```

---

## Format Comparison

### Feature Comparison

| Feature | IMG | SCP | HFE |
|---------|-----|-----|-----|
| **Preserves timing** | No | Yes | Partial |
| **Multiple revolutions** | No | Yes | No |
| **Copy protection** | No | Yes | Partial |
| **File size** | Small | Large | Medium |
| **Emulator support** | Wide | Good | Wide |
| **Recovery potential** | None | High | Medium |

### Size Comparison

| Disk Type | IMG | SCP (3 rev) | HFE |
|-----------|-----|-------------|-----|
| 1.44MB HD | 1.4 MB | 15-25 MB | 3-5 MB |
| 720KB DD | 0.7 MB | 10-15 MB | 2-3 MB |

### Quality Comparison

| Scenario | Recommended Format |
|----------|-------------------|
| Working disk, everyday use | IMG |
| Archival preservation | SCP |
| Floppy emulator | HFE |
| Damaged disk backup | SCP |
| Copy-protected software | SCP |
| Minimal storage | IMG |
| Maximum compatibility | IMG |

---

## Best Practices

### For Working Disks

1. Scan to verify all sectors good
2. Export as IMG for convenience
3. Optionally also export SCP for archival

### For Damaged Disks

1. Always export as SCP first
2. This preserves raw data for future recovery
3. Then export IMG if usable

### For Archival

1. Use SCP format
2. Set revolutions to 5
3. Include all tracks
4. Verify after export
5. Store multiple copies

### For Copy-Protected Disks

1. Must use SCP format
2. IMG will not capture protection
3. Maximum revolutions (5+)
4. Note protection type in filename

### Naming Conventions

Suggested filename format:
```
[Name]_[Type]_[Date].[ext]

Examples:
WordPerfect_51_HD_2024-01-15.scp
Games_Disk2_DD_2024-01-15.img
System_Master_Protected_2024-01-15.scp
```

### Storage Recommendations

| Medium | Reliability | Notes |
|--------|-------------|-------|
| SSD/HDD | Good | Multiple locations |
| Cloud storage | Good | Offsite backup |
| Optical (BD-R) | Excellent | Long-term archival |
| M-DISC | Best | 1000+ year lifespan |

---

## Using Exported Images

### With Emulators

| Emulator | IMG | SCP | HFE |
|----------|-----|-----|-----|
| DOSBox | Yes | No | No |
| 86Box | Yes | No | No |
| PCem | Yes | No | No |
| WinUAE | Yes | Yes | Yes |
| FS-UAE | Yes | Yes | Yes |
| HxC | No | Yes | Yes |

### Writing Back to Disk

To write an image to physical disk:
1. Use **Write Image** function
2. Select source image file
3. Configure write options
4. Insert blank disk
5. Start write operation

### Converting Between Formats

**SCP → IMG**:
- Decode flux to sectors
- Export sectors as IMG
- Loses timing data

**IMG → SCP**:
- Encode sectors to flux
- Creates standard MFM timing
- Not original flux

---

## Troubleshooting Export

### "Export failed - read error"

- Disk has bad sectors
- Try enabling "Include bad sectors" (fills with pattern)
- Or recover disk first

### File too small

- Check disk type setting matches physical disk
- Verify scan completed fully

### Verification failed

- Disk may have changed during export
- Try again with disk properly seated
- Check for drive issues

### "No space on device"

- SCP files are large
- Clear space or use different location
- Consider IMG for space savings

---

**Next:** [[Batch Operations]] - Working with multiple disks
