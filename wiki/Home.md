# Floppy Disk Workbench Wiki

Welcome to the **Floppy Disk Workbench** documentation. This wiki covers installation, operation, and troubleshooting for Floppy Disk Workbench—a tool for floppy disk analysis, recovery, and preservation.

![Floppy Disk Workbench](../screenshots/Screenshot_1.png)

## What is Floppy Disk Workbench?

Floppy Disk Workbench reads and writes floppy disks at the magnetic flux level using a **Greaseweazle** USB controller. This approach allows recovery of damaged disks that standard floppy controllers cannot read.

**Main features:**

- **Disk Analysis** – Sector-by-sector health assessment with signal quality metrics
- **Data Recovery** – Multi-pass algorithms with statistical bit voting for damaged disks
- **Flux Analysis** – Raw magnetic signal visualization, histograms, and timing analysis
- **Disk Imaging** – Export to IMG, SCP, and HFE formats for archival or emulator use
- **Drive Diagnostics** – RPM monitoring, head alignment testing, and read consistency checks

## Quick Navigation

### Getting Started

- [[Installation]] - How to install Floppy Disk Workbench
- [[Hardware Requirements]] - Required hardware and where to get it
- [[Software Requirements]] - Operating system and dependencies
- [[Getting Started]] - Your first steps with Floppy Disk Workbench

### Using the Application

- [[User Interface Overview]] - Understanding the workbench layout
- [[Scanning Disks]] - Reading and analyzing disk contents
- [[Formatting Disks]] - Writing fresh formats to disks
- [[Recovery Operations]] - Recovering data from damaged disks
- [[Flux Analysis]] - Understanding and using flux data
- [[Exporting Images]] - Saving disk images to files
- [[Batch Operations]] - Working with multiple disks

### Reference

- [[Supported Disk Formats]] - IBM PC, Amiga, Atari ST, BBC Micro
- [[Configuration]] - Application settings
- [[Keyboard Shortcuts]] - Quick reference for shortcuts
- [[Diagnostics]] - Drive testing and calibration
- [[Troubleshooting]] - Common problems and solutions
- [[Technical Reference]] - MFM timing, signal quality metrics
- [[FAQ]] - Frequently asked questions

## Version Information

- **Current Version**: 2.0.0
- **Python**: 3.10+
- **License**: MIT

## Support

If you run into problems:

1. Check the [[Troubleshooting]] guide
2. Review the [[FAQ]]
3. [Open an issue on GitHub](https://github.com/JYewman/Floppy-Disk-Restorer/issues)

## Contributing

Floppy Disk Workbench is open source. Contributions are welcome—see the [Contributing Guide](https://github.com/JYewman/Floppy-Disk-Restorer/blob/main/CONTRIBUTING.md) for details.
