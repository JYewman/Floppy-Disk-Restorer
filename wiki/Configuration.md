# Configuration

This guide covers all configuration options in Floppy Workbench.

## Table of Contents

- [Settings Overview](#settings-overview)
- [Opening Settings](#opening-settings)
- [Device Settings](#device-settings)
- [Display Settings](#display-settings)
- [Operation Settings](#operation-settings)
- [Sound Settings](#sound-settings)
- [Advanced Settings](#advanced-settings)
- [Configuration File](#configuration-file)

---

## Settings Overview

Floppy Workbench stores settings in a JSON configuration file that persists between sessions.

### Settings Categories

| Category | Description |
|----------|-------------|
| **Device** | Hardware and connection settings |
| **Display** | Theme, colors, animations |
| **Operations** | Scan, format, recovery defaults |
| **Sounds** | Audio feedback preferences |
| **Advanced** | Expert options |

---

## Opening Settings

### Via Menu

**File → Settings** or press `Ctrl+,`

### Settings Dialog

```
┌─────────────────────────────────────────────────────────────────┐
│                         SETTINGS                                 │
├───────────┬─────────────────────────────────────────────────────┤
│           │                                                      │
│  Device   │  DEVICE SETTINGS                                    │
│           │  ────────────────                                    │
│  Display  │                                                      │
│           │  Default Drive Unit:  [0 ▼]                         │
│  Operations│                                                      │
│           │  Motor Timeout (sec): [30    ]                      │
│  Sounds   │                                                      │
│           │  Auto-connect on start: [✓]                         │
│  Advanced │                                                      │
│           │  Seek Speed:           [Standard ▼]                 │
│           │                                                      │
│           │                                                      │
├───────────┴─────────────────────────────────────────────────────┤
│                    [Restore Defaults]  [Cancel]  [Save]         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Device Settings

### Default Drive Unit

| Option | Description |
|--------|-------------|
| **0** | First drive (after cable twist) |
| **1** | Second drive (before cable twist) |

Most setups use Drive 0.

### Motor Timeout

How long the motor stays on after operations:

| Value | Effect |
|-------|--------|
| **0** | Motor stays on until manually stopped |
| **10-30** | Recommended for most use |
| **60+** | For extended sessions |

### Auto-Connect on Start

When enabled:
- Automatically connects to Greaseweazle on startup
- Saves time for frequent users
- Shows error if device not found

### Seek Speed

| Speed | Description | Use Case |
|-------|-------------|----------|
| **Fast** | Maximum speed | Modern drives |
| **Standard** | Normal speed | Most drives |
| **Slow** | Reduced speed | Old/worn drives |

Slower speeds may improve reliability with older drives.

---

## Display Settings

### Theme

| Theme | Description |
|-------|-------------|
| **Dark** | Dark gray background, light text |
| **Light** | Light/white background, dark text |

### Color Scheme

Sector map color options:

| Scheme | Description |
|--------|-------------|
| **Default** | Standard green/red/yellow |
| **High Contrast** | Enhanced visibility |
| **Colorblind** | Patterns + colors |

### Animation Settings

| Option | Description |
|--------|-------------|
| **Animate Operations** | Smooth sector map updates |
| **Show Tooltips** | Hover help text |
| **Status Animations** | Progress indicators |

### Font Size

| Size | Use Case |
|------|----------|
| **Small** | High-resolution displays |
| **Medium** | Standard (default) |
| **Large** | Accessibility |

---

## Operation Settings

### Scan Defaults

| Setting | Description | Default |
|---------|-------------|---------|
| **Default Disk Type** | Pre-selected format | 1.44MB HD |
| **Default Scan Mode** | Quick/Standard/Thorough | Standard |
| **Verify Reads** | Double-read verification | On |
| **Quality Threshold** | Minimum signal % | 70% |

### Format Defaults

| Setting | Description | Default |
|---------|-------------|---------|
| **Verify After Format** | Read-back verification | On |
| **Default Fill Pattern** | Byte pattern for format | 0x4E |
| **Retry Count** | Failed track retries | 3 |

### Recovery Defaults

| Setting | Description | Default |
|---------|-------------|---------|
| **Default Recovery Level** | Standard/Aggressive/Forensic | Standard |
| **Default Pass Count** | Number of passes | 10 |
| **Enable Multi-Capture** | Flux-level recovery | On |
| **Convergence Threshold** | Passes without improvement | 3 |

### Export Defaults

| Setting | Description | Default |
|---------|-------------|---------|
| **Default Format** | IMG/SCP/HFE | SCP |
| **Default Revolutions** | For flux images | 3 |
| **Verify After Export** | Read-back check | On |
| **Default Location** | Save directory | Last used |

---

## Sound Settings

### Enable Sounds

Master toggle for all audio feedback.

### Sound Events

| Event | Description | Default |
|-------|-------------|---------|
| **Operation Complete** | Scan/format finished | On |
| **Error** | Operation failed | On |
| **Warning** | Non-critical issue | On |
| **Disk Insert** | Disk detected | Off |

### Sound Source

Floppy Workbench uses native system sounds:

| Platform | Sound System |
|----------|--------------|
| **Windows** | winsound.MessageBeep() |
| **Linux** | paplay (freedesktop sounds) |
| **macOS** | afplay (system sounds) |

### Volume

Sound volume follows system settings.

---

## Advanced Settings

### PLL Parameters

Expert settings for flux decoding:

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Bit Cell (HD)** | Expected bit timing | 2.0 µs |
| **Bit Cell (DD)** | Expected bit timing | 4.0 µs |
| **Period Adjust** | PLL responsiveness | 0.05 |
| **Phase Adjust** | Phase correction rate | 0.6 |

### Buffer Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Track Buffer Size** | Memory per track | Auto |
| **Flux Buffer** | Raw flux storage | 5 MB |

### Debug Options

| Option | Description | Default |
|--------|-------------|---------|
| **Enable Logging** | Write to log file | On |
| **Log Level** | Verbosity | INFO |
| **Log Location** | File path | App directory |

### Power Management

| Option | Description | Default |
|--------|-------------|---------|
| **Prevent Sleep** | During long operations | On |

---

## Configuration File

### File Location

Settings are stored in:

| Platform | Path |
|----------|------|
| **Windows** | `%APPDATA%\FloppyWorkbench\settings.json` |
| **Linux** | `~/.config/floppy-workbench/settings.json` |
| **macOS** | `~/Library/Application Support/FloppyWorkbench/settings.json` |

### File Format

```json
{
  "device": {
    "default_drive": 0,
    "motor_timeout": 30,
    "auto_connect": true,
    "seek_speed": "standard"
  },
  "display": {
    "theme": "dark",
    "color_scheme": "default",
    "animate_operations": true,
    "show_tooltips": true,
    "font_size": "medium"
  },
  "operations": {
    "scan": {
      "default_disk_type": "1.44MB HD",
      "default_mode": "standard",
      "verify_reads": true,
      "quality_threshold": 70
    },
    "format": {
      "verify_after": true,
      "fill_pattern": "0x4E",
      "retry_count": 3
    },
    "recovery": {
      "default_level": "standard",
      "default_passes": 10,
      "multi_capture": true,
      "convergence_threshold": 3
    },
    "export": {
      "default_format": "scp",
      "default_revolutions": 3,
      "verify_after": true
    }
  },
  "sounds": {
    "enabled": true,
    "on_complete": true,
    "on_error": true,
    "on_warning": true
  },
  "advanced": {
    "pll": {
      "bit_cell_hd": 2.0,
      "bit_cell_dd": 4.0,
      "period_adjust": 0.05,
      "phase_adjust": 0.6
    },
    "debug": {
      "logging": true,
      "log_level": "INFO"
    },
    "power": {
      "prevent_sleep": true
    }
  }
}
```

### Manual Editing

You can edit the configuration file directly:

1. Close Floppy Workbench
2. Open the settings file in a text editor
3. Make changes (maintain valid JSON)
4. Save and restart application

### Resetting Settings

To reset to defaults:

1. Open Settings dialog
2. Click **Restore Defaults**
3. Click **Save**

Or delete the settings file - it will be recreated on next launch.

### Backing Up Settings

To preserve your configuration:

```bash
# Windows
copy "%APPDATA%\FloppyWorkbench\settings.json" settings_backup.json

# Linux
cp ~/.config/floppy-workbench/settings.json settings_backup.json

# macOS
cp ~/Library/Application\ Support/FloppyWorkbench/settings.json settings_backup.json
```

---

**Next:** [[Keyboard Shortcuts]] - Quick reference
