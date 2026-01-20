# Frequently Asked Questions

Common questions about Floppy Disk Workbench.

## Table of Contents

- [General Questions](#general-questions)
- [Hardware Questions](#hardware-questions)
- [Software Questions](#software-questions)
- [Disk Format Questions](#disk-format-questions)
- [Recovery Questions](#recovery-questions)
- [Technical Questions](#technical-questions)

---

## General Questions

### What is Floppy Disk Workbench?

Floppy Disk Workbench is a professional-grade application for reading, writing, and recovering floppy disks. It uses the Greaseweazle USB controller to access disks at the magnetic flux level, enabling advanced recovery techniques not possible with standard floppy controllers.

### Why use Floppy Disk Workbench instead of just copying files?

Standard file copying:
- Fails completely on any read error
- Cannot access damaged disks
- Misses data in non-standard formats

Floppy Disk Workbench:
- Recovers data from damaged disks
- Reads any disk format
- Preserves complete disk images
- Provides detailed analysis

### Is Floppy Disk Workbench free?

Yes, Floppy Disk Workbench is open-source software released under the MIT license. You can use, modify, and distribute it freely.

### What platforms are supported?

- Windows 10/11
- Linux (Ubuntu, Fedora, Arch, etc.)
- macOS 11+

---

## Hardware Questions

### What hardware do I need?

**Required:**
- Greaseweazle V4 or V4.1 USB controller
- 3.5" floppy drive (PC-compatible)
- USB cable
- 34-pin floppy cable

**Optional:**
- External power supply for drive
- Multiple drives for comparison

### Where can I get a Greaseweazle?

- eBay, Etsy (search "Greaseweazle")
- Retro computing vendors
- Build your own from official design files

### Can I use any floppy drive?

Most PC-compatible 3.5" drives work well. Recommended:
- Sony MPF920
- Panasonic JU-257
- TEAC FD-235HF

Avoid laptop drives or non-standard interfaces.

### Do I need to power the floppy drive separately?

It depends on your setup:
- Some drives work with USB power only (Greaseweazle V4.1 with power jumper)
- Most vintage drives need external 5V and/or 12V
- 5.25" drives always need external power

### Can I use 5.25" drives?

Yes, with limitations:
- Experimental support
- Requires appropriate power supply
- Some formats may not be fully supported

---

## Software Questions

### How do I install Floppy Disk Workbench?

```bash
pip install floppy-workbench
```

See [[Installation]] for detailed instructions.

### What Python version do I need?

Python 3.10 or higher is required. Python 3.11 or 3.12 is recommended.

### The application won't start. What do I do?

1. Check Python version: `python --version`
2. Reinstall: `pip install --force-reinstall floppy-workbench`
3. Run from command line to see errors
4. Check [[Troubleshooting]] for specific errors

### How do I update to the latest version?

```bash
pip install --upgrade floppy-workbench
```

### Can I run Floppy Disk Workbench without a GUI?

The current version requires a GUI. Command-line operation may be added in future versions. For scripting, you can use the Greaseweazle command-line tools directly.

---

## Disk Format Questions

### What disk formats are supported?

**Full support:**
- IBM PC (360KB, 720KB, 1.2MB, 1.44MB)
- Amiga (880KB, 1.76MB)
- Atari ST (360KB, 720KB)
- BBC Micro (DFS, ADFS)

**Partial support:**
- Macintosh (GCR)
- Commodore (GCR/MFM)
- Apple II (GCR)

### How do I know what format my disk is?

1. **Physical inspection:**
   - 3.5" HD disks have a density hole (top-left)
   - 3.5" DD disks have no density hole
   - Labels may indicate format

2. **Auto-detection:**
   - Floppy Disk Workbench attempts to detect format
   - Check sector count and layout

3. **Platform clues:**
   - PC disks: 9 or 18 sectors/track
   - Amiga: 11 or 22 sectors/track

### Can I read Macintosh disks?

Macintosh 400K/800K disks use GCR encoding, which requires special codec support. This is partially implemented. Recent Mac disks (1.44MB) use standard MFM and are fully supported.

### Can I read copy-protected disks?

Floppy Disk Workbench can capture the flux data from copy-protected disks. Whether the protection can be bypassed depends on the specific protection scheme. Flux-level capture preserves the protection for later analysis.

### What's the difference between HD and DD disks?

| Feature | HD (High Density) | DD (Double Density) |
|---------|-------------------|---------------------|
| Capacity | 1.44 MB | 720 KB |
| Sectors/track | 18 | 9 |
| Data rate | 500 Kbps | 250 Kbps |
| Bit cell | 2 µs | 4 µs |
| Density hole | Yes | No |

---

## Recovery Questions

### Can Floppy Disk Workbench recover my damaged disk?

It depends on the damage:
- **Likely recoverable:** Age-related degradation, weak signal, minor scratches
- **Possibly recoverable:** Mold (after cleaning), moderate damage
- **Unlikely recoverable:** Severe physical damage, demagnetization

### How long does recovery take?

| Recovery Level | Time per disk |
|----------------|---------------|
| Standard | 2-5 minutes |
| Aggressive | 5-15 minutes |
| Forensic | 15-60+ minutes |

### What recovery level should I use?

1. **Start with Standard** - Works for most disks
2. **Try Aggressive** - If Standard doesn't recover all sectors
3. **Use Forensic** - For critical data, as a last resort

### Why do some sectors never recover?

Possible reasons:
- Complete magnetic signal loss
- Physical damage (scratches, holes)
- Media breakdown (oxide shedding)
- Head crash damage

### Should I clean my disk before recovery?

**Yes, if:**
- Visible mold or contamination
- Sticky or residue present

**No, if:**
- Disk appears clean
- Cleaning might cause more damage

**How to clean:**
- Use distilled water or isopropyl alcohol
- Soft, lint-free cloth
- Gentle wiping from center to edge
- Let dry completely

---

## Technical Questions

### What is flux data?

Flux data is the raw magnetic signal recorded on the disk. Instead of decoded bytes (0s and 1s), flux captures the precise timing of magnetic transitions. This allows:
- Recovery of marginal data
- Preservation of all disk information
- Analysis of encoding and protection

### What's the difference between IMG and SCP files?

| Feature | IMG | SCP |
|---------|-----|-----|
| Contains | Decoded sectors | Raw flux |
| Size | Small (1.44 MB) | Large (10-25 MB) |
| Preserves timing | No | Yes |
| Recovery potential | None | High |
| Copy protection | Lost | Preserved |

### What is PLL and why does it matter?

PLL (Phase-Locked Loop) is the algorithm that decodes flux data into bits. It tracks timing variations to correctly identify data. Tuning PLL parameters can recover data from disks with:
- Speed variations
- Timing jitter
- Weak or noisy signals

### What sample rate does Greaseweazle use?

Greaseweazle samples at 72 MHz, giving:
- Resolution: ~14 nanoseconds
- Precision: Excellent for MFM decoding
- Bandwidth: Sufficient for all standard formats

### Why does the sector map show sectors in a circle?

The circular display represents the physical disk layout:
- Outer ring = Track 0 (outer edge)
- Inner ring = Track 79 (inner edge)
- Each segment = One sector
- Color = Sector status

This visualization shows patterns that might indicate:
- Physical damage (radial scratches)
- Head alignment issues (one side bad)
- Age-related degradation patterns

### How accurate is the signal quality percentage?

Signal quality is calculated from:
- Signal-to-noise ratio
- Timing jitter
- Pulse consistency

It's a relative measure:
- 90-100%: Excellent, archive quality
- 70-89%: Good, normal use
- 50-69%: Fair, may have issues
- Below 50%: Poor, needs recovery

---

## Still Have Questions?

If your question isn't answered here:

1. Check other wiki pages for detailed information
2. Search [GitHub Issues](https://github.com/JYewman/Floppy-Disk-Restorer/issues)
3. Open a new issue with your question

---

**Back to:** [[Home]] - Wiki home page
