# User Interface Overview

This guide provides a complete tour of the Floppy Workbench user interface.

## Table of Contents

- [Main Window Layout](#main-window-layout)
- [Drive Control Panel](#drive-control-panel)
- [Operation Toolbar](#operation-toolbar)
- [Circular Sector Map](#circular-sector-map)
- [Sector Info Panel](#sector-info-panel)
- [Analytics Panel](#analytics-panel)
- [Status Bar](#status-bar)
- [Menus](#menus)
- [Themes](#themes)

---

## Main Window Layout

Floppy Workbench uses a single-page workbench design where all major functions are accessible without navigating between screens.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Menu Bar                                                            │
├─────────────────────────────────────────────────────────────────────┤
│  Drive Control Panel                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ [Connect] [Drive: 0 ▼] [Motor: Off] [Seek: ◄ 0 ►] RPM: 300.0   ││
│  └─────────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────┤
│  Operation Toolbar                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ [Scan] [Analyze] [Format] [Restore] [Write Image] [Export]      ││
│  └─────────────────────────────────────────────────────────────────┘│
├──────────────────────────────────────────┬──────────────────────────┤
│                                          │                          │
│                                          │    Sector Info Panel     │
│                                          │    ──────────────────    │
│        Circular Sector Map               │    Cylinder: 15          │
│                                          │    Head: 0               │
│        ┌────────────────────┐            │    Sector: 7             │
│        │    ████████████    │            │    Status: GOOD          │
│        │  ██            ██  │            │    Signal: 94.2%         │
│        │ ██              ██ │            │    CRC: Valid            │
│        │ ██              ██ │            │                          │
│        │  ██            ██  │            │    Raw Data:             │
│        │    ████████████    │            │    E8 03 00 00 ...       │
│        └────────────────────┘            │                          │
│                                          │                          │
├──────────────────────────────────────────┴──────────────────────────┤
│  Analytics Panel                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ [Overview] [Flux] [Errors] [Diagnostics] [Recovery]             ││
│  ├─────────────────────────────────────────────────────────────────┤│
│  │                                                                  ││
│  │  Tab Content Area                                                ││
│  │                                                                  ││
│  └─────────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────┤
│  Status Bar: Ready | Sectors: 2880 | Good: 2880 | Bad: 0           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Drive Control Panel

The Drive Control Panel provides hardware interaction controls.

### Components

| Control | Purpose | Shortcut |
|---------|---------|----------|
| **Connect/Disconnect** | Connect to Greaseweazle | `Ctrl+Shift+C` |
| **Drive Selector** | Choose drive unit (0 or 1) | - |
| **Motor Toggle** | Turn drive motor on/off | `Ctrl+M` |
| **Seek Controls** | Move head to specific track | `Ctrl+0` (Track 0) |
| **RPM Display** | Shows current drive speed | - |

### Connection States

| State | Button Text | Indicator |
|-------|-------------|-----------|
| Disconnected | "Connect" | Gray |
| Connecting | "Connecting..." | Yellow |
| Connected | "Disconnect" | Green |
| Error | "Connect" | Red |

### Motor States

| State | Display | Notes |
|-------|---------|-------|
| Off | "Motor: Off" | No disk activity |
| Starting | "Motor: Starting" | Spinning up |
| Running | "Motor: On" + RPM | Ready for operations |

### Seek Controls

- **◄ Button**: Move head inward (lower track)
- **► Button**: Move head outward (higher track)
- **Track Display**: Current head position
- **Track 0 Button**: Return to track 0 (`Ctrl+0`)

---

## Operation Toolbar

The Operation Toolbar provides quick access to all major operations.

### Buttons

| Button | Operation | Shortcut | Description |
|--------|-----------|----------|-------------|
| **Scan** | Disk Scan | `Ctrl+S` | Read all sectors and assess health |
| **Analyze** | Deep Analysis | `Ctrl+Shift+A` | Detailed flux analysis |
| **Format** | Format Disk | `Ctrl+Shift+F` | Write fresh format |
| **Restore** | Recovery | `Ctrl+R` | Multi-pass recovery |
| **Write Image** | Write Image | - | Write disk image to physical disk |
| **Export** | Export Image | `Ctrl+E` | Save disk to file |

### Button States

Buttons change appearance based on application state:

| State | Appearance |
|-------|------------|
| Available | Normal color |
| Unavailable | Grayed out |
| Active | Highlighted |
| In Progress | Shows spinner |

### Context Sensitivity

Buttons are enabled/disabled based on context:

- **Scan**: Enabled when connected with motor running
- **Format**: Enabled when connected
- **Restore**: Enabled after scan with bad sectors
- **Export**: Enabled after successful scan

---

## Circular Sector Map

The Circular Sector Map is the central visualization showing disk health.

### Layout

```
                    Track 0 (outermost)
                          ↓
    ┌───────────────────────────────────────┐
    │           ████████████████            │
    │       ████                ████        │
    │     ██                        ██      │
    │   ██    Head 0 (Top Half)       ██    │
    │  ██                              ██   │
    │  ██ ─────────────────────────── ██   │
    │  ██                              ██   │
    │   ██    Head 1 (Bottom Half)    ██    │
    │     ██                        ██      │
    │       ████                ████        │
    │           ████████████████            │
    └───────────────────────────────────────┘
                          ↑
                    Track 79 (innermost)
```

### Color Legend

| Color | Status | Meaning |
|-------|--------|---------|
| **Green** (#00C853) | GOOD | Successfully read, CRC valid |
| **Red** (#FF1744) | BAD | CRC error or unreadable |
| **Yellow** (#FFD600) | WEAK | Read OK but marginal signal |
| **Orange** (#FF9100) | RECOVERED | Previously bad, now recovered |
| **Gray** (#424242) | UNREAD | Not yet scanned |
| **Blue** (#2196F3) | READING | Currently being processed |
| **Purple** (#9C27B0) | MISSING | Sector not found |

### Interaction

**Click a sector:**
- Selects the sector
- Displays details in Sector Info Panel
- Highlights sector on map

**Right-click a sector:**
- Opens context menu
- Options: Read Sector, View Flux, Mark for Recovery

**Scroll wheel:**
- Zoom in/out on the map

**Drag:**
- Pan the view when zoomed

### Toolbar

The sector map has a small toolbar:

| Button | Function |
|--------|----------|
| **Zoom In** | Enlarge view |
| **Zoom Out** | Reduce view |
| **Fit** | Fit entire map in view |
| **Legend** | Toggle color legend |

---

## Sector Info Panel

The Sector Info Panel shows detailed information about the selected sector.

### Displayed Information

```
┌─────────────────────────────┐
│     SECTOR INFORMATION      │
├─────────────────────────────┤
│ Cylinder:     15            │
│ Head:         0             │
│ Sector:       7             │
│ Linear:       277           │
├─────────────────────────────┤
│ Status:       GOOD          │
│ Signal:       94.2%         │
│ CRC:          Valid         │
│ Read Count:   3             │
├─────────────────────────────┤
│ RAW DATA                    │
│ ┌─────────────────────────┐ │
│ │ E8 03 00 00 8B C4 89 46 │ │
│ │ FC 8B 76 FC 81 FE 00 7C │ │
│ │ 74 16 B4 00 CD 16 3C 1B │ │
│ │ ...                     │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘
```

### Fields

| Field | Description |
|-------|-------------|
| **Cylinder** | Track number (0-79) |
| **Head** | Side (0 or 1) |
| **Sector** | Sector number (1-18 for HD) |
| **Linear** | Linear sector number (0-2879) |
| **Status** | Current sector state |
| **Signal** | Signal quality percentage |
| **CRC** | CRC validation result |
| **Read Count** | Number of read attempts |
| **Raw Data** | Hex dump of sector contents |

---

## Analytics Panel

The Analytics Panel provides detailed analysis through tabbed views.

### Overview Tab

Summary statistics and charts:

```
┌────────────────────────────────────────────────────────────┐
│  DISK OVERVIEW                                              │
├────────────────────────────────────────────────────────────┤
│  Total Sectors:    2,880      │  ████████████████████  98% │
│  Good Sectors:     2,823      │  Good                      │
│  Bad Sectors:         42      │  ██                    2%  │
│  Weak Sectors:        15      │  Bad                       │
├────────────────────────────────────────────────────────────┤
│  Disk Health:     98.5%       │                            │
│  Disk Type:       1.44MB HD   │  Scan Time: 45.3s          │
│  Format:          FAT12       │  Read Errors: 42           │
└────────────────────────────────────────────────────────────┘
```

### Flux Tab

Flux-level analysis tools:

- **Waveform View**: Oscilloscope-style flux visualization
- **Histogram**: Pulse width distribution
- **Track Selector**: Choose track to analyze
- **Zoom Controls**: Time scale adjustment

### Errors Tab

Error analysis and statistics:

- **Error List**: Table of all bad sectors
- **Error Distribution**: Heat map by track
- **Error Types**: Breakdown by error category
- **Export Errors**: Save error report

### Diagnostics Tab

Drive diagnostic tools:

- **RPM Graph**: Real-time speed monitoring
- **Head Alignment**: Alignment test results
- **Read Consistency**: Multi-read comparison
- **Drive Info**: Hardware information

### Recovery Tab

Recovery options and progress:

- **Recovery Mode**: Select recovery strategy
- **Pass Counter**: Current/total passes
- **Progress Chart**: Recovery progress over time
- **Recovered Sectors**: List of successfully recovered sectors

---

## Status Bar

The Status Bar shows current application state.

```
┌─────────────────────────────────────────────────────────────────┐
│ Ready | Sectors: 2880 | Good: 2823 | Bad: 42 | Weak: 15 | 98.5% │
└─────────────────────────────────────────────────────────────────┘
```

### Sections

| Section | Content |
|---------|---------|
| **Status** | Current operation or "Ready" |
| **Sectors** | Total sector count |
| **Good** | Good sector count |
| **Bad** | Bad sector count |
| **Weak** | Weak sector count |
| **Health** | Overall health percentage |

### During Operations

```
┌─────────────────────────────────────────────────────────────────┐
│ Scanning... Track 45/80 | ████████████░░░░░░ 56% | ETA: 0:23   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Menus

### File Menu

| Item | Shortcut | Description |
|------|----------|-------------|
| Open Image | `Ctrl+O` | Load disk image file |
| Export Image | `Ctrl+E` | Save disk to image file |
| Export Report | `Ctrl+Shift+R` | Generate PDF/HTML report |
| Settings | `Ctrl+,` | Open settings dialog |
| Exit | `Alt+F4` | Close application |

### Device Menu

| Item | Shortcut | Description |
|------|----------|-------------|
| Connect | `Ctrl+Shift+C` | Connect to Greaseweazle |
| Disconnect | `Ctrl+Shift+C` | Disconnect from device |
| Motor On/Off | `Ctrl+M` | Toggle drive motor |
| Seek Track 0 | `Ctrl+0` | Return head to track 0 |
| Eject | `Ctrl+J` | Eject disk (if supported) |

### Operations Menu

| Item | Shortcut | Description |
|------|----------|-------------|
| Scan | `Ctrl+S` | Start disk scan |
| Analyze | `Ctrl+Shift+A` | Start deep analysis |
| Format | `Ctrl+Shift+F` | Format disk |
| Restore | `Ctrl+R` | Start recovery |
| Batch Verify | `Ctrl+B` | Start batch verification |

### View Menu

| Item | Shortcut | Description |
|------|----------|-------------|
| Zoom In | `Ctrl++` | Zoom sector map in |
| Zoom Out | `Ctrl+-` | Zoom sector map out |
| Fit View | `Ctrl+0` | Fit map to window |
| Dark Theme | - | Switch to dark theme |
| Light Theme | - | Switch to light theme |

### Help Menu

| Item | Shortcut | Description |
|------|----------|-------------|
| Documentation | `F1` | Open wiki |
| About | - | Version and credits |
| Check Updates | - | Check for new version |

---

## Themes

Floppy Workbench supports dark and light themes.

### Dark Theme (Default)

- Dark gray background
- High contrast text
- Reduced eye strain
- Best for low-light environments

### Light Theme

- Light gray/white background
- Standard contrast
- Best for bright environments

### Changing Theme

1. Go to **View** menu
2. Select **Dark Theme** or **Light Theme**

Or:
1. Open **Settings** (`Ctrl+,`)
2. Navigate to **Display** tab
3. Select theme from dropdown

---

**Next:** [[Scanning Disks]] - Learn about scanning operations
