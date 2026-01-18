# Getting Started

This guide walks you through your first disk scan with Floppy Workbench.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Hardware Setup](#hardware-setup)
- [Launching the Application](#launching-the-application)
- [Connecting to the Device](#connecting-to-the-device)
- [Your First Disk Scan](#your-first-disk-scan)
- [Understanding the Results](#understanding-the-results)
- [Next Steps](#next-steps)

---

## Prerequisites

Before starting, ensure you have:

- [ ] Floppy Workbench installed ([[Installation]])
- [ ] Greaseweazle connected via USB
- [ ] Floppy drive connected to Greaseweazle
- [ ] Power connected to drive (if needed)
- [ ] A floppy disk to test

---

## Hardware Setup

### Step 1: Connect the Greaseweazle

1. Plug the Greaseweazle into a USB port on your computer
2. The LED on the Greaseweazle should illuminate
3. Wait a few seconds for the device to initialize

### Step 2: Connect the Floppy Drive

1. Connect the 34-pin ribbon cable from Greaseweazle to your floppy drive
2. Ensure pin 1 is aligned (usually marked with a red stripe on the cable)
3. Use the connector **after** the twist in the cable for Drive 0

### Step 3: Power the Drive

If your drive needs external power:
1. Connect the 4-pin Berg power connector
2. Ensure +5V (red) and +12V (yellow) if required
3. Some drives only need +5V

### Step 4: Verify Connections

Before continuing:
- Greaseweazle LED is on
- All cables are secure
- Power supply is on (if using external)

---

## Launching the Application

### From Command Line

```bash
floppy-workbench
```

### From Python

```bash
python -m floppy_formatter
```

### What You'll See

When Floppy Workbench starts, you'll see the main workbench interface:

```
┌─────────────────────────────────────────────────────────┐
│  Drive Control Panel                                     │
│  [Connect] [Drive: 0 ▼] [Motor: Off] RPM: ---           │
├─────────────────────────────────────────────────────────┤
│  Operation Toolbar                                       │
│  [Scan] [Analyze] [Format] [Restore] [Write Image]      │
├────────────────────────────────┬────────────────────────┤
│                                │                        │
│     Circular Sector Map        │    Sector Info Panel   │
│                                │                        │
│         (Empty until          │    Cylinder: --        │
│          connected)           │    Head: --            │
│                                │    Sector: --          │
│                                │    Status: --          │
├────────────────────────────────┴────────────────────────┤
│  Analytics Panel                                         │
│  [Overview] [Flux] [Errors] [Diagnostics] [Recovery]    │
└─────────────────────────────────────────────────────────┘
```

---

## Connecting to the Device

### Step 1: Click Connect

1. Look at the **Drive Control Panel** at the top
2. Click the **"Connect"** button
3. Wait for the connection process

### Step 2: Verify Connection

When connected successfully:
- The Connect button changes to "Disconnect"
- The Motor button becomes active
- The status bar shows "Connected to Greaseweazle"

### Step 3: Turn On the Motor

1. Click the **"Motor"** button (or press `Ctrl+M`)
2. Listen for the drive motor spinning up
3. The RPM display should show approximately **300 RPM**

### Troubleshooting Connection

**"No Greaseweazle found"**
- Check USB connection
- Verify Greaseweazle LED is on
- On Linux, check USB permissions
- Try a different USB port

**"Device busy"**
- Close other applications using the device
- Unplug and replug the Greaseweazle

---

## Your First Disk Scan

### Step 1: Insert a Disk

1. Insert a floppy disk into the drive
2. Wait a moment for the disk to settle

**Tip**: Start with a known-good disk for your first test.

### Step 2: Start the Scan

1. Click **"Scan"** in the Operation Toolbar (or press `Ctrl+S`)
2. The Scan Configuration dialog appears

### Step 3: Configure the Scan

For your first scan, use these settings:

| Setting | Recommended Value |
|---------|-------------------|
| **Scan Mode** | Standard |
| **Disk Type** | 1.44MB HD (or 720KB DD for DD disks) |
| **Verify Reads** | Enabled |

Click **"Start Scan"** to begin.

### Step 4: Watch the Progress

During the scan:
- The circular sector map fills in with colored sectors
- The progress bar shows completion percentage
- The status bar shows current track being read

### Step 5: Scan Complete

When the scan finishes:
- A completion sound plays (if enabled)
- The sector map shows final results
- Summary statistics appear in the Overview tab

---

## Understanding the Results

### Sector Map Colors

The circular sector map uses colors to indicate sector health:

| Color | Status | Meaning |
|-------|--------|---------|
| **Green** | GOOD | Sector read successfully, CRC valid |
| **Red** | BAD | CRC error or unreadable |
| **Yellow** | WEAK | Read successfully but marginal signal |
| **Orange** | RECOVERED | Previously bad, now recovered |
| **Gray** | UNREAD | Not yet scanned |
| **Blue** | READING | Currently being read |

### Reading the Sector Map

```
        Track 0 (outer edge)
              ↓
    ┌─────────────────────┐
    │    ████████████     │
    │  ██            ██   │
    │ ██    Sector    ██  │
    │ ██     Map      ██  │
    │  ██            ██   │
    │    ████████████     │
    └─────────────────────┘
              ↑
        Track 79 (inner)
```

- **Outer ring**: Track 0
- **Inner rings**: Higher track numbers
- **Each segment**: One sector (18 per track for HD disks)
- **Two sides**: Head 0 (top) and Head 1 (bottom)

### Statistics Panel

The Overview tab shows:

| Statistic | Description |
|-----------|-------------|
| **Total Sectors** | Number of sectors on disk (2,880 for 1.44MB) |
| **Good Sectors** | Successfully read sectors |
| **Bad Sectors** | Failed sectors (CRC errors) |
| **Weak Sectors** | Marginal signal quality |
| **Disk Health** | Percentage of good sectors |

### Sector Info Panel

Click any sector on the map to see:

- **Cylinder**: Track number (0-79)
- **Head**: Side (0 or 1)
- **Sector**: Sector number (1-18)
- **Status**: Current sector state
- **Signal Quality**: 0-100% quality metric
- **CRC**: Valid or error

---

## Next Steps

Now that you've completed your first scan, explore these features:

### For Good Disks

- [[Exporting Images]] - Save disk contents to a file
- [[Flux Analysis]] - Examine magnetic signal quality

### For Damaged Disks

- [[Recovery Operations]] - Attempt to recover bad sectors
- [[Diagnostics]] - Check drive alignment

### For Blank Disks

- [[Formatting Disks]] - Write a fresh format

### Learn More

- [[User Interface Overview]] - Full GUI documentation
- [[Scanning Disks]] - Advanced scanning options
- [[Keyboard Shortcuts]] - Speed up your workflow

---

## Quick Reference

| Task | Action |
|------|--------|
| Connect to device | Click "Connect" |
| Start motor | Click "Motor" or `Ctrl+M` |
| Scan disk | Click "Scan" or `Ctrl+S` |
| Cancel operation | Press `Escape` |
| View sector details | Click sector on map |
| Switch tabs | Click tab name |

---

**Congratulations!** You've completed your first disk scan with Floppy Workbench.

---

**Next:** [[User Interface Overview]] - Learn the complete interface
