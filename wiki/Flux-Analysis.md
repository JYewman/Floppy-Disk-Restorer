# Flux Analysis

This guide explains flux-level analysis in Floppy Disk Workbench.

## Table of Contents

- [Understanding Flux Data](#understanding-flux-data)
- [Analysis Configuration](#analysis-configuration)
- [The Flux Tab](#the-flux-tab)
- [Waveform Visualization](#waveform-visualization)
- [Pulse Histogram](#pulse-histogram)
- [Signal Quality Metrics](#signal-quality-metrics)
- [Running Analysis](#running-analysis)
- [Interpreting Results](#interpreting-results)
- [Advanced Analysis](#advanced-analysis)

---

## Understanding Flux Data

### What is Flux?

Flux refers to the magnetic field changes recorded on a floppy disk. Instead of reading logical data (0s and 1s), flux-level analysis examines the raw magnetic transitions and their precise timing.

### Why Flux Analysis Matters

Flux analysis provides insights that sector-level reading cannot:

| Benefit | Description |
|---------|-------------|
| **Raw signal visibility** | See actual magnetic data before decoding |
| **Problem diagnosis** | Identify signal degradation and timing issues |
| **Recovery optimization** | Tune PLL parameters based on actual timing |
| **Copy protection detection** | Identify non-standard encodings |
| **Archival preservation** | Capture complete magnetic information |

### MFM Encoding

IBM PC disks use Modified Frequency Modulation (MFM) encoding. Data is encoded as timing between magnetic flux transitions:

| Pulse Type | Bit Cells | HD Timing | DD Timing |
|------------|-----------|-----------|-----------|
| **2T (Short)** | 2 | ~4.0 µs | ~8.0 µs |
| **3T (Medium)** | 3 | ~6.0 µs | ~12.0 µs |
| **4T (Long)** | 4 | ~8.0 µs | ~16.0 µs |

A healthy MFM disk shows three distinct peaks in the pulse width histogram, corresponding to these timing values.

### Encoding Types

Floppy Disk Workbench can detect multiple encoding types:

| Encoding | Used By | Characteristics |
|----------|---------|-----------------|
| **MFM** | IBM PC, Amiga, Atari ST | Three peaks at 2T, 3T, 4T ratios |
| **FM** | Older 8" drives | Two peaks at 1T, 2T ratios |
| **GCR** | Apple, Commodore | Multiple closely-spaced peaks |

---

## Analysis Configuration

Click the **Analyze** button in the Operation Toolbar to open the Analysis Configuration dialog.

![Analysis Configuration Dialog](../screenshots/analyze_config_dialog.png)
*Screenshot: Analysis Configuration dialog showing all analysis options*

### Analysis Depth

Choose the thoroughness of analysis:

| Depth | Description | Tracks Analyzed |
|-------|-------------|-----------------|
| **Quick** | Basic quality check on sample tracks | Tracks 0, 20, 40, 60, 79 (both heads) |
| **Full** | Complete analysis of all tracks | All 160 tracks |
| **Comprehensive** | Full analysis with extended captures | All 160 tracks with extra revolutions |

Quick analysis is useful for initial assessment. Full analysis is recommended for detailed quality grading. Comprehensive analysis provides the most accurate results but takes longer.

### Analysis Components

Select which analysis components to enable:

| Component | Description | Default |
|-----------|-------------|---------|
| **Flux Analysis** | Signal quality, timing jitter, histogram analysis | Enabled |
| **Head Alignment** | Track margin measurement, azimuth detection | Disabled |
| **Forensic Analysis** | Copy protection detection, format analysis, deleted data | Disabled |

Components are auto-selected based on analysis depth but can be manually adjusted. Comprehensive depth enables all components by default.

### Track Range

Configure which tracks to analyze:

| Option | Description |
|--------|-------------|
| **Analyze all tracks** | Analyzes all 80 cylinders (160 tracks total) |
| **Custom range** | Specify start and end cylinders (0-79) |

### Capture Settings

| Setting | Description | Range |
|---------|-------------|-------|
| **Revolutions per track** | Number of disk rotations to capture | 1-20 |

More revolutions provide better quality assessment at the cost of longer analysis time. The default is 3 revolutions. Comprehensive depth uses 5 revolutions for maximum accuracy.

### Report Output

| Option | Description |
|--------|-------------|
| **Save analysis report** | Generate and save a detailed analysis report |
| **Report format** | HTML, PDF, or JSON format |

---

## The Flux Tab

The Flux tab in the Analytics Panel provides real-time flux visualization.

![Flux Tab](../screenshots/flux_tab.png)
*Screenshot: Flux tab showing waveform and histogram displays*

### Track/Sector Selector

| Control | Description |
|---------|-------------|
| **Cylinder** | Select cylinder to analyze (0-79) |
| **Head** | Select side (0 or 1) |
| **Sector** | Select specific sector (1-18) or All |
| **Load Flux** | Load flux data from previous scan or analysis |
| **Capture Live** | Capture new flux directly from the disk |

### Display Layout

The Flux tab is split into two main areas:

- **Top section (70%)**: Waveform display showing flux transitions over time
- **Bottom section (30%)**: Histogram showing pulse width distribution

An info bar at the bottom displays:
- Track position (Cylinder and Head)
- Capture duration in milliseconds
- Total transition count
- Overall quality score

### Export

Click **Export Flux...** to save the currently displayed flux data to a SuperCard Pro (.scp) file for external analysis or archival.

---

## Waveform Visualization

The waveform display shows flux transitions as a square wave pattern over time.

![Flux Waveform](../screenshots/flux_waveform.png)
*Screenshot: Waveform display showing flux transitions with markers*

### Reading the Waveform

| Element | Meaning |
|---------|---------|
| **Transition spacing** | Time between flux changes (encodes data) |
| **Signal height** | Relative signal strength |
| **Color (green)** | Good signal quality (confidence ≥80%) |
| **Color (yellow)** | Weak signal (confidence 50-80%) |
| **Color (red)** | Poor signal (confidence <50%) |

### Markers

The waveform displays visual markers for significant positions:

| Marker Type | Color | Description |
|-------------|-------|-------------|
| **Index** | Purple | Index pulse position (track start) |
| **Sector** | Blue | Sector header positions |
| **Data** | Dark Blue | Data region boundaries |
| **Gap** | Gray | Inter-sector gaps |

### Toolbar Controls

| Button | Function |
|--------|----------|
| **Fit** | Zoom to show entire waveform |
| **+** | Zoom in (show finer detail) |
| **-** | Zoom out (show more time) |

The toolbar also displays:
- Current zoom percentage
- Cursor position in microseconds
- Total transition count

### Mouse Controls

| Action | Function |
|--------|----------|
| **Scroll wheel** | Horizontal scroll |
| **Ctrl+Scroll** | Zoom in/out |
| **Middle button drag** | Pan view |
| **Shift+Click+Drag** | Select region |
| **Hover** | Show transition info tooltip |

### Keyboard Shortcuts

| Key | Function |
|-----|----------|
| `+` or `=` | Zoom in |
| `-` | Zoom out |
| `0` | Zoom to fit |
| `←` `→` | Pan left/right |
| `Home` | Jump to start |
| `End` | Jump to end |
| `Escape` | Clear selection |

---

## Pulse Histogram

The histogram shows the distribution of pulse widths across the captured flux data.

![Flux Histogram](../screenshots/flux_histogram.png)
*Screenshot: Pulse histogram showing MFM peaks with Gaussian fits*

### Display Elements

| Element | Description |
|---------|-------------|
| **Bars (cyan)** | Pulse width counts per bin |
| **Reference lines** | Expected MFM peak positions (2T, 3T, 4T) |
| **Gaussian curves** | Fitted curves overlaid on detected peaks |
| **Quality metrics** | Displayed in upper-right corner |

### MFM Reference Lines

Dashed vertical lines indicate expected MFM peak positions:

| Line | Color | Position (HD) |
|------|-------|---------------|
| **2T** | Blue | 4.0 µs |
| **3T** | Green | 6.0 µs |
| **4T** | Purple | 8.0 µs |

### Interpreting the Histogram

| Pattern | Meaning | Quality |
|---------|---------|---------|
| **Three sharp, separated peaks** | Clean MFM signal | Excellent |
| **Peaks slightly overlapping** | Minor timing jitter | Good |
| **Peaks significantly merged** | Speed or timing issues | Marginal |
| **Extra peaks** | Non-standard encoding | Investigate |
| **No clear peaks** | Severe degradation or no data | Poor |

### Statistics Bar

The statistics bar at the bottom shows:

| Statistic | Description |
|-----------|-------------|
| **Total** | Total pulse count in histogram |
| **2T** | Detected 2T peak position (µs) |
| **3T** | Detected 3T peak position (µs) |
| **4T** | Detected 4T peak position (µs) |
| **Sep** | Average separation between peaks |

### Quality Metrics

Displayed in the upper-right corner of the histogram:

| Metric | Description |
|--------|-------------|
| **Quality** | Overall quality score (0-100%) |
| **Peaks** | Number of detected peaks |
| **Jitter** | Average timing jitter (µs) |

Quality score color coding:
- **Green (≥70%)**: Excellent or good quality
- **Yellow (40-70%)**: Marginal quality
- **Red (<40%)**: Poor quality

---

## Signal Quality Metrics

### Key Metrics

| Metric | Description | Good | Warning | Critical |
|--------|-------------|------|---------|----------|
| **SNR** | Signal-to-Noise Ratio | > 25 dB | 15-25 dB | < 15 dB |
| **Jitter** | Timing variation (RMS) | < 100 ns | 100-200 ns | > 200 ns |
| **Peak Separation** | Distance between histogram peaks | > 1.5 µs | 1-1.5 µs | < 1 µs |
| **Outlier %** | Pulses outside expected range | < 5% | 5-10% | > 10% |

### Quality Grades

Analysis assigns a letter grade to each track and an overall grade:

| Grade | Score | Description |
|-------|-------|-------------|
| **A** | 90-100 | Excellent - archive quality |
| **B** | 75-89 | Good - normal operation |
| **C** | 60-74 | Fair - may have read issues |
| **D** | 40-59 | Poor - recovery needed |
| **F** | 0-39 | Critical - significant data loss |

### Timing Statistics

Full analysis provides comprehensive timing statistics:

| Statistic | Description |
|-----------|-------------|
| **Mean** | Average pulse width |
| **Std Dev** | Standard deviation |
| **Median** | Median pulse width |
| **Mode** | Most common pulse width |
| **Skewness** | Distribution asymmetry |
| **Kurtosis** | Distribution tail weight |
| **Bit Cell** | Estimated bit cell width |

---

## Running Analysis

### Step 1: Configure Analysis

1. Click **Analyze** in the Operation Toolbar
2. Select **Analysis Depth** (Quick/Full/Comprehensive)
3. Enable desired **Analysis Components**
4. Set **Track Range** if needed
5. Configure **Capture Settings**
6. Enable **Report Output** if desired
7. Click **Start Analysis**

### Step 2: Monitor Progress

![Analysis Progress](../screenshots/analyze_progress.png)
*Screenshot: Analysis progress display*

During analysis, the interface shows:
- Current track being analyzed
- Progress percentage
- Per-track quality scores as they complete

The circular sector map updates to show quality grades for each track:
- **Green**: Grade A or B
- **Yellow**: Grade C
- **Red**: Grade D or F

### Step 3: Review Results

When analysis completes:

| Result | Location |
|--------|----------|
| **Overall grade** | Summary panel |
| **Per-track grades** | Sector map (color-coded) |
| **Detailed statistics** | Analytics Panel tabs |
| **Recommendations** | Analysis report |

### Step 4: Use the Flux Tab

After analysis, use the Flux tab to examine individual tracks:

1. Set **Cylinder** and **Head** in the selector
2. Click **Load Flux** to view captured data
3. Examine the waveform for signal quality
4. Check the histogram for timing characteristics
5. Note any problem areas for recovery

---

## Interpreting Results

### Overall Disk Assessment

| Result | Recommended Action |
|--------|-------------------|
| **Grade A** | Standard operations - disk is in excellent condition |
| **Grade B** | Standard operations - minor degradation acceptable |
| **Grade C** | Use multi-read recovery mode |
| **Grade D** | Use aggressive recovery with PLL tuning |
| **Grade F** | Use forensic recovery mode |

### Common Problems

#### Weak Signal

**Symptoms:**
- Low SNR (< 15 dB)
- Histogram peaks are low
- Many weak (yellow) transitions in waveform

**Causes:**
- Media degradation
- Worn drive heads
- Head-to-media spacing issues

**Action:** Try a different drive, clean the disk surface, use multi-capture recovery.

#### High Jitter

**Symptoms:**
- Wide histogram peaks
- Peaks starting to merge
- Jitter > 200 ns

**Causes:**
- Motor speed instability
- Media deterioration
- Temperature effects

**Action:** Check drive mechanics, enable PLL tuning in recovery.

#### Missing or Extra Peaks

**Symptoms:**
- Histogram doesn't show 3 clear peaks
- Extra peaks present
- Encoding detection shows low confidence

**Causes:**
- Copy protection
- Non-IBM format
- Severe degradation

**Action:** Enable forensic analysis, check for copy protection, verify disk format.

### Per-Track Analysis

Examine individual tracks to identify problem areas:

1. Locate tracks with poor grades on the sector map
2. Load flux for those tracks in the Flux tab
3. Examine waveform for:
   - Dropout regions (gaps)
   - Color changes (signal quality issues)
   - Irregular spacing
4. Check histogram for:
   - Peak positions vs expected
   - Peak overlap
   - Quality score

---

## Advanced Analysis

### Forensic Analysis

When **Forensic Analysis** is enabled, analysis includes:

| Feature | Description |
|---------|-------------|
| **Copy protection detection** | Identifies protection schemes (weak bits, long tracks, etc.) |
| **Format analysis** | Determines disk format type |
| **Deleted data detection** | Locates potentially recoverable deleted content |

### Copy Protection Detection

Forensic analysis detects common protection types:

| Protection Type | Detection Method |
|-----------------|------------------|
| **Weak bits** | Intentionally marginal timing |
| **Long tracks** | Extra data beyond standard track length |
| **Missing sectors** | Intentional sector gaps |
| **Non-standard gaps** | Unusual inter-sector timing |
| **Fuzzy bits** | Variable read results |

When protection is detected, the analysis report includes:
- Number of protected tracks
- Protection types found
- Recommendations for preservation

### Head Alignment Analysis

When **Head Alignment** is enabled, analysis includes:

| Measurement | Description |
|-------------|-------------|
| **Track margins** | How well-centered the head is on tracks |
| **Azimuth detection** | Head angle relative to tracks |
| **Cross-talk measurement** | Signal bleed from adjacent tracks |

### Encoding Detection

Analysis automatically detects the encoding type:

| Encoding | Detection Confidence |
|----------|---------------------|
| **MFM** | High if 3 peaks at 2:3:4 ratio |
| **FM** | High if 2 peaks at 1:2 ratio |
| **GCR** | High if 4-5 closely-spaced peaks |
| **Unknown** | If pattern doesn't match known types |

### Exporting Flux Data

To export flux data for external analysis:

1. Load flux for the desired track in the Flux tab
2. Click **Export Flux...**
3. Choose save location and filename
4. File saves in SuperCard Pro (.scp) format

Exported flux can be analyzed with external tools or preserved for archival.

---

**Next:** [[Exporting Images]] - Save disk contents to files
