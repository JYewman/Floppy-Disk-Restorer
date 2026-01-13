# Changelog

All notable changes to Floppy Workbench will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-01-13

### Major Release: Greaseweazle Support & Professional Workbench GUI

This is a complete rewrite of the application, transitioning from USB floppy drive
support to Greaseweazle V4.1 flux-level disk controller, and from a TUI interface
to a professional PyQt6 workbench GUI.

### Breaking Changes

- **Hardware**: Now requires Greaseweazle V4.1 (or compatible) instead of USB floppy drives
- **Interface**: Replaced Textual TUI with PyQt6 workbench GUI
- **Package name**: Changed from `floppy-formatter` to `floppy-workbench`
- **Configuration**: Settings file location and format changed

### Added

#### Hardware Layer (Phase 1)
- `GreaseweazleDevice` class for device connection and motor control
- `FluxIO` module for raw flux read/write operations
- `MFMCodec` for MFM encoding/decoding
- `DriveCalibration` for RPM measurement and timing

#### Flux Analysis (Phase 3)
- `FluxAnalyzer` for timing statistics and histogram generation
- `SignalQuality` for SNR, jitter, and weak bit detection
- `HeadAlignment` for track margin and azimuth measurement
- `Forensics` for copy protection and format detection

#### Advanced Recovery (Phase 4)
- Multi-capture recovery with flux-level bit voting
- PLL parameter tuning for marginal sectors
- Bit-slip recovery for synchronization errors
- Surface treatment with proper DC erase

#### Workbench GUI (Phase 5)
- Single-page workbench layout with three panels
- `DriveControlPanel` with connection status and motor control
- `OperationToolbar` with start/stop/pause controls
- `StatusStrip` with real-time status display

#### Enhanced Sector Map (Phase 6)
- Flux quality overlay mode
- Selection mode for targeted operations
- Zoom controls and export functionality
- `SectorInfoPanel` with detailed sector information

#### Analytics Dashboard (Phase 7)
- Overview tab with health score and recommendations
- Flux tab with waveform and histogram views
- Errors tab with heatmap and pattern detection
- Recovery tab with convergence tracking
- Diagnostics tab with alignment and RPM charts

#### Flux Visualization (Phase 8)
- `FluxWaveformWidget` with oscilloscope-style view
- `FluxHistogramWidget` with Gaussian peak fitting
- `TimingJitterWidget` with scatter plot analysis

#### Operation Dialogs (Phase 10)
- `ScanConfigDialog` with mode selection
- `FormatConfigDialog` with pattern options
- `RestoreConfigDialog` preserving all recovery options
- `AnalyzeConfigDialog` with depth selection
- `ExportDialog` for IMG/SCP/HFE formats

#### Image Support (Phase 11)
- IMG/IMA sector image read/write
- SCP flux image support
- HFE flux image support

#### Reports (Phase 12)
- HTML reports with embedded charts
- PDF export using ReportLab
- Scan, recovery, diagnostic, and comparison templates

#### Settings (Phase 13)
- JSON-based settings persistence
- Device, display, recovery, and export categories
- Window position and panel layout persistence

#### Polish (Phase 14)
- Animation system with fade, slide, scale effects
- Loading skeleton widgets
- Animated buttons with ripple effects
- Drag-and-drop for image files
- Sound notifications
- Splash screen with loading progress
- Professional application icon
- Dark and light theme enhancements
- Comprehensive keyboard shortcuts

### Changed

- Application renamed from "USB Floppy Formatter" to "Floppy Workbench"
- Recovery algorithms now use flux-level operations for better accuracy
- Multi-read recovery replaced with multi-capture flux voting
- Error handling updated for Greaseweazle exceptions
- All USB-specific code paths removed

### Removed

- USB floppy drive support (`device_manager.py`, `sector_io.py`)
- TUI interface (Textual-based terminal UI)
- `MainMenuWidget` and `DriveSelectWidget` screens
- Linux ioctl-based device operations
- udev rule requirements

### Fixed

- Recovery now properly preserves good sectors in targeted mode
- Convergence detection more accurate with flux-level data
- Motor control no longer has firmware timeout issues

### Dependencies

- Added: `greaseweazle ^1.0`
- Added: `numpy ^1.26.0`
- Added: `reportlab ^4.0.0`
- Added: `pyqtgraph ^0.13.0` (optional)
- Removed: `textual`

## [0.2.0] - 2024-12-01

### Added
- Multi-read statistical recovery algorithm
- Convergence-based recovery mode
- Targeted recovery for bad sectors only
- Real-time convergence tracking display
- Comprehensive test suite

### Changed
- Improved error classification
- Better progress reporting
- Enhanced TUI layout

## [0.1.0] - 2024-11-15

### Added
- Initial release
- Basic scan functionality
- Low-level format operations
- TUI interface with Textual
- Support for 1.44MB floppy disks
