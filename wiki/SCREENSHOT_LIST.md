# Screenshot List for Wiki Documentation

This document lists all screenshots needed for the Floppy Disk Workbench wiki documentation.

## Overview

**Total screenshots needed:** 31

**Storage location:** `screenshots/` folder relative to wiki root

---

## Main Window & Layout

### 1. main_window_layout.png
- **Used in:** User-Interface-Overview.md
- **Description:** Main application window showing the three-panel layout
- **Content:** Drive Control Panel at top, Circular Sector Map on left, Sector Info Panel on right, Analytics Panel at bottom
- **State:** Idle state with no disk operation active, showing default empty sectors

### 2. session_screen.png
- **Used in:** User-Interface-Overview.md
- **Description:** Session selection screen (disk format selection)
- **Content:** Platform list on left, format selection in center, preview panel on right
- **State:** IBM PC selected, showing 1.44MB HD highlighted

---

## Panels & Components

### 3. drive_control_panel.png
- **Used in:** User-Interface-Overview.md
- **Description:** Drive Control Panel at top of main window
- **Content:** Device dropdown, Connect button, drive letter display, motor controls, status indicators
- **State:** Connected to device, motor off

### 4. operation_toolbar.png
- **Used in:** User-Interface-Overview.md
- **Description:** Operation Toolbar showing all operation buttons
- **Content:** Scan, Analyze, Format, Restore, Write Image, Export buttons
- **State:** All buttons enabled (device connected)

### 5. sector_map.png
- **Used in:** User-Interface-Overview.md
- **Description:** Circular Sector Map visualization
- **Content:** Full 2,880 sector disk representation in concentric rings
- **State:** After scan showing mix of good (green), bad (red), and weak (yellow) sectors

### 6. sector_info_panel.png
- **Used in:** User-Interface-Overview.md
- **Description:** Sector Info Panel showing detailed sector information
- **Content:** Sector position, status, CRC result, signal quality, hex dump preview
- **State:** Showing details for a selected sector

### 7. status_strip.png
- **Used in:** User-Interface-Overview.md
- **Description:** Status Strip at bottom of window
- **Content:** Connection status, operation status, disk type, progress indicator
- **State:** During an operation showing progress

---

## Analytics Panel Tabs

### 8. analytics_summary.png
- **Used in:** User-Interface-Overview.md
- **Description:** Summary tab in Analytics Panel
- **Content:** Disk overview statistics, good/bad/weak counts, overall health grade
- **State:** After scan with typical results

### 9. analytics_analysis.png
- **Used in:** User-Interface-Overview.md
- **Description:** Analysis tab showing signal quality metrics
- **Content:** Track-by-track quality view, histograms
- **State:** After analysis operation

### 10. analytics_flux.png
- **Used in:** User-Interface-Overview.md
- **Description:** Flux tab showing flux visualization
- **Content:** Track selector, waveform display, histogram
- **State:** Showing flux for a selected track

### 11. analytics_errors.png
- **Used in:** User-Interface-Overview.md
- **Description:** Errors tab showing error details
- **Content:** List of bad sectors, error types, error distribution
- **State:** Showing errors after scan of damaged disk

### 12. analytics_recovery.png
- **Used in:** User-Interface-Overview.md
- **Description:** Recovery tab showing recovery options
- **Content:** Recovery recommendations, technique options
- **State:** Showing recommendations for disk with errors

### 13. analytics_diagnostics.png
- **Used in:** User-Interface-Overview.md
- **Description:** Diagnostics tab showing drive diagnostics
- **Content:** RPM measurement, head alignment status, drive health
- **State:** After diagnostics run

### 14. analytics_verification.png
- **Used in:** User-Interface-Overview.md
- **Description:** Verification tab showing verification results
- **Content:** Sector verification status, consistency check results
- **State:** After verification operation

---

## Scanning

### 15. scan_progress_tab.png
- **Used in:** Scanning-Disks.md, User-Interface-Overview.md
- **Description:** Progress tab during scan operation
- **Content:** Circular sector map updating in real-time, progress bar, sector counter, good/bad counts, elapsed time, ETA
- **State:** Mid-scan, approximately 50% complete with sectors showing green (good), red (bad), yellow (weak)

---

## Formatting

### 16. format_config_dialog.png
- **Used in:** Formatting-Disks.md
- **Description:** Format Configuration dialog
- **Content:** Format type selection (Standard/Low-Level/Secure), fill pattern dropdown, verify after format checkbox
- **State:** Standard format selected, 0x00 fill pattern

### 17. format_confirm_dialog.png
- **Used in:** Formatting-Disks.md
- **Description:** Format Confirmation dialog (warning before format)
- **Content:** Warning message, format type summary, Cancel and Confirm buttons
- **State:** Showing warning about data destruction

### 18. format_progress.png
- **Used in:** Formatting-Disks.md
- **Description:** Format progress display during formatting
- **Content:** Current phase (erase/write/verify), progress bar, track indicator
- **State:** During format operation

---

## Recovery

### 19. restore_config_dialog.png
- **Used in:** Recovery-Operations.md
- **Description:** Restore Configuration dialog with all recovery options
- **Content:** Recovery mode (Fixed/Convergence), recovery scope, multi-read settings, recovery level dropdown, advanced options checkboxes, report options
- **State:** Convergence mode, Aggressive level selected

### 20. restore_progress.png
- **Used in:** Recovery-Operations.md
- **Description:** Recovery progress screen during restore operation
- **Content:** Current pass, bad sector count (before/after), recovery rate, current technique, sector map with recovered sectors (orange)
- **State:** Mid-recovery showing some sectors recovered

---

## Flux Analysis

### 21. analyze_config_dialog.png
- **Used in:** Flux-Analysis.md
- **Description:** Analysis Configuration dialog
- **Content:** Analysis depth selection (Quick/Full/Comprehensive), component checkboxes, track range, capture settings, report options
- **State:** Full analysis selected with flux analysis enabled

### 22. flux_tab.png
- **Used in:** Flux-Analysis.md
- **Description:** Complete Flux tab in Analytics Panel
- **Content:** Track selector (cylinder/head/sector), Load/Capture buttons, waveform display (top 70%), histogram display (bottom 30%), info bar
- **State:** Showing flux data for a track

### 23. flux_waveform.png
- **Used in:** Flux-Analysis.md
- **Description:** Flux waveform display detail
- **Content:** Square wave pattern, color-coded transitions (green/yellow/red), markers, toolbar with zoom controls
- **State:** Zoomed to show individual transitions with good signal quality

### 24. flux_histogram.png
- **Used in:** Flux-Analysis.md
- **Description:** Pulse width histogram detail
- **Content:** Cyan bars showing distribution, MFM reference lines (2T/3T/4T), Gaussian fit curves, quality metrics in corner
- **State:** Healthy MFM signal with three distinct peaks

### 25. analyze_progress.png
- **Used in:** Flux-Analysis.md
- **Description:** Analysis progress display during analysis
- **Content:** Track progress, per-track grades updating, overall progress
- **State:** Mid-analysis with some tracks graded

---

## Exporting

### 26. export_dialog.png
- **Used in:** Exporting-Images.md
- **Description:** Export Configuration dialog
- **Content:** Export type selection (IMG/SCP/HFE), format-specific options, compression settings, file path with browse button
- **State:** SCP format selected with default options

### 27. export_progress.png
- **Used in:** Exporting-Images.md
- **Description:** Export progress display during export
- **Content:** Progress bar, current track, elapsed time, file size
- **State:** Mid-export

---

## Batch Operations

### 28. batch_verify_config_dialog.png
- **Used in:** Batch-Operations.md
- **Description:** Batch Verification Configuration dialog
- **Content:** Batch name field, brand dropdown, disk count spinner, serial number section, analysis depth radio buttons
- **State:** Default configuration with Standard depth

### 29. batch_verify_progress.png
- **Used in:** Batch-Operations.md
- **Description:** Batch verification in progress
- **Content:** Current disk number, track progress, completed disks list with grades, summary statistics
- **State:** Mid-batch with several disks completed (mix of grades)

---

## Settings

### 30. settings_dialog.png
- **Used in:** Configuration.md
- **Description:** Settings dialog showing configuration categories
- **Content:** Tabbed categories (Device, Display, Operations, Sounds, Advanced) with options panel
- **State:** Showing Device settings tab

---

## Existing Screenshot (Keep)

### 31. Screenshot_1.png
- **Used in:** Home.md
- **Description:** Main application screenshot for homepage
- **Content:** General application overview
- **State:** Already exists, keep as-is

---

## Screenshot Capture Guidelines

### Resolution
- Minimum: 1280x720
- Recommended: 1920x1080
- Format: PNG (lossless)

### Application State
- Use dark theme for consistency
- Ensure UI elements are clearly visible
- Hide any personal/sensitive information

### Content Guidelines
- Show realistic data where possible
- Use example disk names like "DOS622", "Office Backup"
- Demonstrate both successful and error states where appropriate

### Naming Convention
- All lowercase
- Underscores for spaces
- Descriptive names matching wiki references
- .png extension

### Folder Structure
```
screenshots/
├── Screenshot_1.png              # Homepage (existing)
├── main_window_layout.png        # Main window
├── session_screen.png            # Session selection
├── drive_control_panel.png       # Top panel
├── operation_toolbar.png         # Toolbar
├── sector_map.png                # Sector visualization
├── sector_info_panel.png         # Sector details
├── status_strip.png              # Status bar
├── analytics_summary.png         # Analytics - Summary
├── analytics_analysis.png        # Analytics - Analysis
├── analytics_flux.png            # Analytics - Flux
├── analytics_errors.png          # Analytics - Errors
├── analytics_recovery.png        # Analytics - Recovery
├── analytics_diagnostics.png     # Analytics - Diagnostics
├── analytics_verification.png    # Analytics - Verification
├── scan_progress_tab.png         # Scan progress (Progress tab)
├── format_config_dialog.png      # Format dialog
├── format_confirm_dialog.png     # Format confirmation
├── format_progress.png           # Format in progress
├── restore_config_dialog.png     # Restore dialog
├── restore_progress.png          # Restore in progress
├── analyze_config_dialog.png     # Analyze dialog
├── flux_tab.png                  # Flux tab
├── flux_waveform.png             # Waveform detail
├── flux_histogram.png            # Histogram detail
├── analyze_progress.png          # Analysis in progress
├── export_dialog.png             # Export dialog
├── export_progress.png           # Export in progress
├── batch_verify_config_dialog.png # Batch dialog
└── batch_verify_progress.png     # Batch in progress
```
