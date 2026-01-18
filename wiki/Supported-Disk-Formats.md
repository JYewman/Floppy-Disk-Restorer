# Supported Disk Formats

This page details all disk formats supported by Floppy Workbench.

## Table of Contents

- [Format Overview](#format-overview)
- [IBM PC Formats](#ibm-pc-formats)
- [Amiga Formats](#amiga-formats)
- [Atari ST Formats](#atari-st-formats)
- [BBC Micro Formats](#bbc-micro-formats)
- [Other Formats](#other-formats)
- [Encoding Types](#encoding-types)
- [Format Detection](#format-detection)

---

## Format Overview

### Supported Platforms

| Platform | Encoding | Status |
|----------|----------|--------|
| **IBM PC** | MFM | Full Support |
| **Amiga** | Amiga MFM | Full Support |
| **Atari ST** | MFM | Full Support |
| **BBC Micro** | FM/MFM | Full Support |
| **Macintosh** | GCR | Partial |
| **Apple II** | GCR | Partial |
| **Commodore** | GCR/MFM | Partial |

### Format Categories

| Category | Description |
|----------|-------------|
| **Soft-sectored** | Sectors defined by data markers (most formats) |
| **Hard-sectored** | Physical holes mark sector positions (rare) |
| **Variable geometry** | Different tracks have different sector counts |

---

## IBM PC Formats

### 3.5" High Density (HD)

**Primary format** - Most commonly used

| Parameter | Value |
|-----------|-------|
| **Capacity** | 1,474,560 bytes (1.44 MB) |
| **Cylinders** | 80 |
| **Heads** | 2 |
| **Sectors/Track** | 18 |
| **Bytes/Sector** | 512 |
| **Encoding** | MFM |
| **Data Rate** | 500 Kbps |
| **Bit Cell** | 2.0 µs |
| **RPM** | 300 |

**Track layout**:
```
Sector IDs: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18
```

### 3.5" Double Density (DD)

| Parameter | Value |
|-----------|-------|
| **Capacity** | 737,280 bytes (720 KB) |
| **Cylinders** | 80 |
| **Heads** | 2 |
| **Sectors/Track** | 9 |
| **Bytes/Sector** | 512 |
| **Encoding** | MFM |
| **Data Rate** | 250 Kbps |
| **Bit Cell** | 4.0 µs |
| **RPM** | 300 |

### 5.25" High Density (HD)

| Parameter | Value |
|-----------|-------|
| **Capacity** | 1,228,800 bytes (1.2 MB) |
| **Cylinders** | 80 |
| **Heads** | 2 |
| **Sectors/Track** | 15 |
| **Bytes/Sector** | 512 |
| **Encoding** | MFM |
| **Data Rate** | 500 Kbps |
| **RPM** | 360 |

### 5.25" Double Density (DD)

| Parameter | Value |
|-----------|-------|
| **Capacity** | 368,640 bytes (360 KB) |
| **Cylinders** | 40 |
| **Heads** | 2 |
| **Sectors/Track** | 9 |
| **Bytes/Sector** | 512 |
| **Encoding** | MFM |
| **Data Rate** | 250 Kbps |
| **RPM** | 300 |

### IBM PC Filesystem

Standard PC floppy disks use FAT12 filesystem:

| Component | Location |
|-----------|----------|
| **Boot sector** | Sector 0 |
| **FAT #1** | Following boot sector |
| **FAT #2** | Copy of FAT #1 |
| **Root directory** | After FAT tables |
| **Data area** | Remainder of disk |

---

## Amiga Formats

### 3.5" Double Density (DD)

| Parameter | Value |
|-----------|-------|
| **Capacity** | 901,120 bytes (880 KB) |
| **Cylinders** | 80 |
| **Heads** | 2 |
| **Sectors/Track** | 11 |
| **Bytes/Sector** | 512 |
| **Encoding** | Amiga MFM |
| **Data Rate** | 250 Kbps |
| **RPM** | 300 |

### 3.5" High Density (HD)

| Parameter | Value |
|-----------|-------|
| **Capacity** | 1,802,240 bytes (1.76 MB) |
| **Cylinders** | 80 |
| **Heads** | 2 |
| **Sectors/Track** | 22 |
| **Bytes/Sector** | 512 |
| **Encoding** | Amiga MFM |
| **Data Rate** | 500 Kbps |
| **RPM** | 300 |

### Amiga MFM Differences

Amiga MFM differs from IBM MFM:

| Feature | IBM | Amiga |
|---------|-----|-------|
| **Sector header** | Standard IDAM | Custom format |
| **Data encoding** | Interleaved | Separated odd/even |
| **Checksum** | CRC-16 | Simple checksum |
| **Gap format** | 4E pattern | Custom |

### AmigaDOS Filesystem

| Feature | Value |
|---------|-------|
| **Block size** | 512 bytes |
| **Filesystem** | OFS (Original) or FFS (Fast) |
| **Bootable** | Yes, custom boot block |

---

## Atari ST Formats

### 3.5" Single-Sided DD

| Parameter | Value |
|-----------|-------|
| **Capacity** | 368,640 bytes (360 KB) |
| **Cylinders** | 80 |
| **Heads** | 1 |
| **Sectors/Track** | 9 |
| **Bytes/Sector** | 512 |
| **Encoding** | MFM |

### 3.5" Double-Sided DD

| Parameter | Value |
|-----------|-------|
| **Capacity** | 737,280 bytes (720 KB) |
| **Cylinders** | 80 |
| **Heads** | 2 |
| **Sectors/Track** | 9 |
| **Bytes/Sector** | 512 |
| **Encoding** | MFM |

### Atari ST Extended Formats

Some software used extended formats:

| Format | Sectors/Track | Capacity |
|--------|---------------|----------|
| **10 sector** | 10 | 800 KB |
| **11 sector** | 11 | 880 KB |

**Note**: Extended formats may not read in standard PC drives.

### Atari ST Filesystem

- Uses FAT12, similar to PC
- Generally compatible with PC systems
- Some differences in boot sector

---

## BBC Micro Formats

### DFS (Disc Filing System) - FM Encoding

| Parameter | Value |
|-----------|-------|
| **Capacity** | 100 KB (SS) / 200 KB (DS) |
| **Cylinders** | 40 or 80 |
| **Heads** | 1 or 2 |
| **Sectors/Track** | 10 |
| **Bytes/Sector** | 256 |
| **Encoding** | FM (Single Density) |
| **Data Rate** | 125 Kbps |

### ADFS (Advanced DFS) - MFM Encoding

| Parameter | Value |
|-----------|-------|
| **Capacity** | 640 KB - 800 KB |
| **Cylinders** | 80 |
| **Heads** | 2 |
| **Sectors/Track** | 16 |
| **Bytes/Sector** | 256 |
| **Encoding** | MFM |

### FM vs MFM

| Feature | FM | MFM |
|---------|-----|-----|
| **Clock bits** | Every bit | Only between 0s |
| **Density** | Single | Double |
| **Data rate** | 125 Kbps | 250 Kbps |
| **Capacity** | ~100 KB | ~400+ KB |

---

## Other Formats

### Commodore (Experimental)

| System | Format | Encoding |
|--------|--------|----------|
| **1541** | 170 KB | GCR |
| **1571** | 340 KB | GCR |
| **1581** | 800 KB | MFM |

### Apple (Experimental)

| System | Format | Encoding |
|--------|--------|----------|
| **Apple II** | 140 KB | GCR |
| **Macintosh 400K** | 400 KB | GCR |
| **Macintosh 800K** | 800 KB | GCR |

**Note**: GCR formats require additional codec support.

### MSX (MFM)

| Parameter | Value |
|-----------|-------|
| **Capacity** | 360 KB / 720 KB |
| **Encoding** | MFM (PC-compatible) |

### Amstrad CPC (MFM)

| Format | Capacity | Notes |
|--------|----------|-------|
| **Data** | 180 KB | Single-sided |
| **System** | 180 KB | With boot sector |
| **Extended** | 720 KB | Double-sided |

---

## Encoding Types

### MFM (Modified Frequency Modulation)

Most common encoding for floppy disks:

```
Data:  1  0  0  1  0  0  0  1
       ↓  ↓  ↓  ↓  ↓  ↓  ↓  ↓
MFM:  01 00 10 01 00 10 10 01
      ↑     ↑     ↑  ↑
      Data  Clock Clock Clock
```

**Characteristics**:
- One data bit per clock period
- Clock bits only between consecutive zeros
- 2x density of FM

### FM (Frequency Modulation)

Older, single-density encoding:

```
Data:  1  0  0  1
       ↓  ↓  ↓  ↓
FM:   11 10 10 11
      ↑↑ ↑↑ ↑↑ ↑↑
      C D C D C D C D
      (Clock + Data interleaved)
```

**Characteristics**:
- Clock bit before every data bit
- Lower density than MFM
- Used by early systems

### GCR (Group Coded Recording)

Used by Apple and Commodore:

```
4 data bits → 5 disk bits
```

**Characteristics**:
- Self-clocking (no separate clock)
- Requires specific hardware support
- Variable zones on disk

---

## Format Detection

### Automatic Detection

Floppy Workbench can auto-detect formats:

1. **Read track 0** - Examine structure
2. **Check sector size** - 256, 512, 1024 bytes
3. **Count sectors** - Determine format
4. **Verify encoding** - FM vs MFM

### Detection Hints

| Clue | Indicates |
|------|-----------|
| 18 sectors/track | IBM PC HD |
| 9 sectors/track | IBM PC DD or Atari ST |
| 11 sectors/track | Amiga DD |
| 256-byte sectors | BBC Micro |
| 10 sectors, 256 bytes | BBC DFS |

### Manual Override

If auto-detection fails:

1. Go to scan configuration
2. Select disk type manually
3. Adjust parameters as needed

---

## Format Compatibility

### Cross-Platform Reading

| Format | Read on PC? | Notes |
|--------|-------------|-------|
| IBM PC | Yes | Native |
| Amiga | Partial | Data readable, filesystem needs tools |
| Atari ST | Yes | Compatible FAT12 |
| BBC DFS | No | Requires FM support |
| BBC ADFS | Yes | Different filesystem |

### Physical Media Notes

| Media Type | HD Disk | DD Disk |
|------------|---------|---------|
| **Can format as HD?** | Yes | No (unreliable) |
| **Can format as DD?** | Yes | Yes |
| **Identification** | HD hole present | No HD hole |

---

**Next:** [[Configuration]] - Application settings
