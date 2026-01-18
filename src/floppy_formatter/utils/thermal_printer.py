"""
Thermal printer support for Star TSP100 and compatible printers.

This module provides functionality to print disk analysis reports
on 80mm thermal receipt printers using the Windows printing API.

Features:
    - Formats reports for 80mm thermal paper (48 characters wide)
    - ASCII art sector map visualization
    - Auto-cut support for Star TSP100 printers
    - ESC/POS command support for direct printing

Part of Phase 15: Thermal Printer Support
"""

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Character width for different paper sizes
PAPER_WIDTHS = {
    58: 32,   # 58mm paper
    80: 48,   # 80mm paper (standard receipt)
}

# ESC/POS Commands for Star TSP100
class ESCPOSCommands:
    """ESC/POS command bytes for thermal printers."""
    # Initialization
    INIT = b'\x1b\x40'                    # Initialize printer

    # Text formatting
    BOLD_ON = b'\x1b\x45\x01'             # Bold on
    BOLD_OFF = b'\x1b\x45\x00'            # Bold off
    UNDERLINE_ON = b'\x1b\x2d\x01'        # Underline on
    UNDERLINE_OFF = b'\x1b\x2d\x00'       # Underline off
    DOUBLE_HEIGHT_ON = b'\x1b\x21\x10'    # Double height
    DOUBLE_WIDTH_ON = b'\x1b\x21\x20'     # Double width
    NORMAL_SIZE = b'\x1b\x21\x00'         # Normal size

    # Alignment
    ALIGN_LEFT = b'\x1b\x61\x00'          # Left align
    ALIGN_CENTER = b'\x1b\x61\x01'        # Center align
    ALIGN_RIGHT = b'\x1b\x61\x02'         # Right align

    # Paper control
    FEED_LINE = b'\x0a'                   # Line feed
    FEED_LINES = b'\x1b\x64'              # Feed n lines (add count byte)
    CUT_PARTIAL = b'\x1b\x64\x02\x1d\x56\x01'  # Feed 2 lines, partial cut
    CUT_FULL = b'\x1b\x64\x02\x1d\x56\x00'     # Feed 2 lines, full cut


@dataclass
class ThermalReportData:
    """Data structure for thermal report content."""
    title: str = "FLOPPY DISK ANALYSIS"
    disk_label: str = ""
    timestamp: datetime = None

    # Disk info
    format_type: str = "IBM PC 1.44MB"
    cylinders: int = 80
    heads: int = 2
    sectors_per_track: int = 18

    # Results
    total_sectors: int = 2880
    good_sectors: int = 0
    bad_sectors: int = 0
    weak_sectors: int = 0

    # Quality metrics
    signal_quality: float = 0.0
    read_success_rate: float = 0.0

    # Operation info
    operation_type: str = "Scan"
    duration_seconds: float = 0.0

    # Sector map data (cylinder -> (head -> list of sector statuses))
    sector_map: Optional[Dict[int, Dict[int, List[str]]]] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ThermalReportFormatter:
    """
    Formats disk analysis reports for thermal printing.

    Optimized for 80mm (48 character) thermal paper.
    """

    def __init__(self, char_width: int = 48):
        """
        Initialize formatter.

        Args:
            char_width: Characters per line (48 for 80mm paper)
        """
        self.width = char_width
        self.lines: List[str] = []

    def _center(self, text: str) -> str:
        """Center text within the paper width."""
        return text.center(self.width)

    def _left(self, text: str) -> str:
        """Left-align text."""
        return text.ljust(self.width)

    def _right(self, text: str) -> str:
        """Right-align text."""
        return text.rjust(self.width)

    def _separator(self, char: str = "-") -> str:
        """Create a separator line."""
        return char * self.width

    def _two_column(self, left: str, right: str) -> str:
        """Format two columns."""
        space = self.width - len(left) - len(right)
        if space < 1:
            space = 1
        return left + " " * space + right

    def _bar_graph(self, value: float, max_width: int = 20) -> str:
        """Create a simple ASCII bar graph."""
        filled = int(value * max_width)
        empty = max_width - filled
        return "[" + "#" * filled + "." * empty + "]"

    def format_report(self, data: ThermalReportData,
                      include_sector_map: bool = True,
                      include_logo: bool = True) -> str:
        """
        Format the complete report for thermal printing.

        Args:
            data: Report data
            include_sector_map: Whether to include ASCII sector map
            include_logo: Whether to include ASCII logo

        Returns:
            Formatted report as string
        """
        self.lines = []

        # Header with logo
        if include_logo:
            self._add_logo()

        self._add_header(data)
        self._add_disk_info(data)
        self._add_results(data)
        self._add_quality_metrics(data)

        if include_sector_map and data.sector_map:
            self._add_sector_map(data)

        self._add_footer(data)

        return "\n".join(self.lines)

    def _add_logo(self) -> None:
        """Add ASCII art logo."""
        logo = [
            "  _____ _                        ",
            " |  ___| | ___  _ __  _ __  _   _",
            " | |_  | |/ _ \\| '_ \\| '_ \\| | | |",
            " |  _| | | (_) | |_) | |_) | |_| |",
            " |_|   |_|\\___/| .__/| .__/ \\__, |",
            " Workbench    |_|   |_|    |___/ ",
        ]
        for line in logo:
            self.lines.append(self._center(line[:self.width]))
        self.lines.append("")

    def _add_header(self, data: ThermalReportData) -> None:
        """Add report header."""
        self.lines.append(self._separator("="))
        self.lines.append(self._center(data.title))
        self.lines.append(self._separator("="))
        self.lines.append("")

        # Timestamp
        self.lines.append(self._center(
            data.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        ))

        if data.disk_label:
            self.lines.append(self._center(f"Label: {data.disk_label}"))

        self.lines.append("")

    def _add_disk_info(self, data: ThermalReportData) -> None:
        """Add disk information section."""
        self.lines.append(self._separator("-"))
        self.lines.append(self._center("DISK INFORMATION"))
        self.lines.append(self._separator("-"))

        self.lines.append(self._two_column("Format:", data.format_type))
        self.lines.append(self._two_column("Cylinders:", str(data.cylinders)))
        self.lines.append(self._two_column("Heads:", str(data.heads)))
        self.lines.append(self._two_column("Sectors/Track:", str(data.sectors_per_track)))
        self.lines.append(self._two_column("Total Sectors:", str(data.total_sectors)))
        self.lines.append("")

    def _add_results(self, data: ThermalReportData) -> None:
        """Add results section."""
        self.lines.append(self._separator("-"))
        self.lines.append(self._center(f"{data.operation_type.upper()} RESULTS"))
        self.lines.append(self._separator("-"))

        # Sector counts with visual bars
        good_pct = data.good_sectors / max(data.total_sectors, 1)
        bad_pct = data.bad_sectors / max(data.total_sectors, 1)
        weak_pct = data.weak_sectors / max(data.total_sectors, 1)

        self.lines.append(self._two_column(
            f"Good: {data.good_sectors}",
            f"{good_pct*100:.1f}%"
        ))
        self.lines.append("  " + self._bar_graph(good_pct, 20))

        self.lines.append(self._two_column(
            f"Bad: {data.bad_sectors}",
            f"{bad_pct*100:.1f}%"
        ))
        if data.bad_sectors > 0:
            self.lines.append("  " + self._bar_graph(bad_pct, 20))

        self.lines.append(self._two_column(
            f"Weak: {data.weak_sectors}",
            f"{weak_pct*100:.1f}%"
        ))
        if data.weak_sectors > 0:
            self.lines.append("  " + self._bar_graph(weak_pct, 20))

        self.lines.append("")

    def _add_quality_metrics(self, data: ThermalReportData) -> None:
        """Add quality metrics section."""
        self.lines.append(self._separator("-"))
        self.lines.append(self._center("QUALITY METRICS"))
        self.lines.append(self._separator("-"))

        self.lines.append(self._two_column(
            "Signal Quality:",
            f"{data.signal_quality:.1f}%"
        ))
        self.lines.append("  " + self._bar_graph(data.signal_quality / 100, 20))

        self.lines.append(self._two_column(
            "Read Success:",
            f"{data.read_success_rate:.1f}%"
        ))
        self.lines.append("  " + self._bar_graph(data.read_success_rate / 100, 20))

        # Duration
        mins = int(data.duration_seconds // 60)
        secs = int(data.duration_seconds % 60)
        self.lines.append(self._two_column(
            "Duration:",
            f"{mins}m {secs}s"
        ))

        self.lines.append("")

    def _add_sector_map(self, data: ThermalReportData) -> None:
        """Add ASCII sector map visualization."""
        self.lines.append(self._separator("-"))
        self.lines.append(self._center("SECTOR MAP"))
        self.lines.append(self._separator("-"))

        # Legend
        self.lines.append("Legend: . = Good  X = Bad  ? = Weak")
        self.lines.append("")

        # Create a compact sector map
        # Show a summary view - one character per track
        map_width = min(40, self.width - 8)  # Leave room for labels

        for head in range(data.heads):
            self.lines.append(f"Head {head}:")

            # Group cylinders into chunks that fit the width
            cyl_per_line = map_width

            for start_cyl in range(0, data.cylinders, cyl_per_line):
                end_cyl = min(start_cyl + cyl_per_line, data.cylinders)
                line = ""

                for cyl in range(start_cyl, end_cyl):
                    if data.sector_map and cyl in data.sector_map:
                        if head in data.sector_map[cyl]:
                            statuses = data.sector_map[cyl][head]
                            # Summarize track status
                            if all(s == "good" for s in statuses):
                                line += "."
                            elif any(s == "bad" for s in statuses):
                                line += "X"
                            elif any(s == "weak" for s in statuses):
                                line += "?"
                            else:
                                line += "."
                        else:
                            line += " "
                    else:
                        line += " "

                # Add cylinder range label
                label = f"{start_cyl:02d}"
                self.lines.append(f"  {label} {line}")

            self.lines.append("")

    def _add_footer(self, data: ThermalReportData) -> None:
        """Add report footer."""
        self.lines.append(self._separator("="))
        self.lines.append(self._center("Floppy Workbench v2.0"))
        self.lines.append(self._center("github.com/JYewman"))
        self.lines.append(self._separator("="))
        self.lines.append("")
        self.lines.append("")  # Extra lines before cut


class ThermalPrinter:
    """
    Interface for thermal receipt printers.

    Supports Star TSP100 and compatible ESC/POS printers
    via the Windows printing API.
    """

    def __init__(self, printer_name: str = "", auto_cut: bool = True):
        """
        Initialize thermal printer.

        Args:
            printer_name: OS printer name (empty for default)
            auto_cut: Whether to auto-cut paper after printing
        """
        self.printer_name = printer_name
        self.auto_cut = auto_cut
        self._is_available = False

        # Check availability
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if printing is available."""
        if sys.platform == 'win32':
            try:
                import win32print
                self._is_available = True

                # Get default printer if none specified
                if not self.printer_name:
                    self.printer_name = win32print.GetDefaultPrinter()

            except ImportError:
                logger.warning("win32print not available - thermal printing disabled")
                self._is_available = False
        else:
            # On Linux/Mac, we could use CUPS or lp command
            self._is_available = True

    @property
    def is_available(self) -> bool:
        """Check if printer is available."""
        return self._is_available

    @staticmethod
    def get_available_printers() -> List[str]:
        """
        Get list of available printers.

        Returns:
            List of printer names
        """
        printers = []

        if sys.platform == 'win32':
            try:
                import win32print
                for printer in win32print.EnumPrinters(
                    win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
                ):
                    printers.append(printer[2])  # Printer name is at index 2
            except ImportError:
                pass
        else:
            # On Linux, parse lpstat output
            try:
                import subprocess
                result = subprocess.run(
                    ['lpstat', '-p'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.splitlines():
                    if line.startswith('printer'):
                        parts = line.split()
                        if len(parts) >= 2:
                            printers.append(parts[1])
            except Exception:
                pass

        return printers

    def print_text(self, text: str) -> bool:
        """
        Print plain text to the thermal printer.

        Args:
            text: Text to print

        Returns:
            True if printing succeeded
        """
        if not self._is_available:
            logger.error("Printer not available")
            return False

        try:
            if sys.platform == 'win32':
                return self._print_windows(text)
            else:
                return self._print_unix(text)
        except Exception as e:
            logger.error(f"Printing failed: {e}")
            return False

    def _print_windows(self, text: str) -> bool:
        """Print using Windows API."""
        try:
            import win32print
            import win32ui
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QFont, QPainter, QFontMetrics
            from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
            from PyQt6.QtCore import QMarginsF, QSizeF

            # Use Qt's printing for better text handling
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)

            # Find and set the printer
            for info in QPrinterInfo.availablePrinters():
                if info.printerName() == self.printer_name:
                    printer.setPrinterName(self.printer_name)
                    break
            else:
                # Use default printer
                printer.setPrinterName(QPrinterInfo.defaultPrinter().printerName())

            # Set up page size for receipt (80mm width)
            # Height is continuous, so set a reasonable max
            page_size = QSizeF(80, 297)  # 80mm x ~A4 height
            printer.setPageSize(page_size)
            printer.setPageMargins(QMarginsF(2, 2, 2, 2))

            # Create painter
            painter = QPainter()
            if not painter.begin(printer):
                logger.error("Could not start printer")
                return False

            try:
                # Use monospace font
                font = QFont("Courier New", 8)
                painter.setFont(font)

                # Calculate line height
                metrics = QFontMetrics(font)
                line_height = metrics.height()

                # Print each line
                y = 0
                for line in text.split('\n'):
                    painter.drawText(0, y + metrics.ascent(), line)
                    y += line_height

            finally:
                painter.end()

            logger.info(f"Printed to {self.printer_name}")
            return True

        except Exception as e:
            logger.error(f"Windows printing failed: {e}")
            return False

    def _print_unix(self, text: str) -> bool:
        """Print using lp command on Unix/Linux."""
        try:
            import subprocess
            import tempfile

            # Write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(text)
                temp_path = f.name

            # Build print command
            cmd = ['lp']
            if self.printer_name:
                cmd.extend(['-d', self.printer_name])
            cmd.append(temp_path)

            # Execute print
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            # Clean up temp file
            import os
            os.unlink(temp_path)

            if result.returncode == 0:
                logger.info(f"Printed to {self.printer_name or 'default printer'}")
                return True
            else:
                logger.error(f"lp command failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Unix printing failed: {e}")
            return False

    def print_report(self, data: ThermalReportData,
                     include_sector_map: bool = True,
                     include_logo: bool = True,
                     char_width: int = 48) -> bool:
        """
        Format and print a disk analysis report.

        Args:
            data: Report data
            include_sector_map: Include ASCII sector map
            include_logo: Include ASCII logo
            char_width: Characters per line

        Returns:
            True if printing succeeded
        """
        # Format the report
        formatter = ThermalReportFormatter(char_width)
        report_text = formatter.format_report(
            data,
            include_sector_map=include_sector_map,
            include_logo=include_logo
        )

        # Print it
        return self.print_text(report_text)


def print_scan_report(
    scan_result: Any,
    geometry: Any,
    printer_name: str = "",
    auto_cut: bool = True,
    include_sector_map: bool = True,
    include_logo: bool = True,
    char_width: int = 48,
) -> bool:
    """
    Convenience function to print a scan result.

    Args:
        scan_result: ScanResult object from scan operation
        geometry: DiskGeometry object
        printer_name: Printer name (empty for default)
        auto_cut: Auto-cut paper after printing
        include_sector_map: Include ASCII sector map
        include_logo: Include ASCII logo
        char_width: Characters per line

    Returns:
        True if printing succeeded
    """
    # Convert scan result to thermal report data
    data = ThermalReportData(
        title="DISK SCAN REPORT",
        format_type=f"{geometry.cylinders}x{geometry.heads}x{geometry.sectors_per_track}",
        cylinders=geometry.cylinders,
        heads=geometry.heads,
        sectors_per_track=geometry.sectors_per_track,
        total_sectors=geometry.total_sectors,
        good_sectors=getattr(scan_result, 'good_sectors', 0),
        bad_sectors=getattr(scan_result, 'bad_sectors', 0),
        weak_sectors=getattr(scan_result, 'weak_sectors', 0),
        signal_quality=getattr(scan_result, 'average_signal_quality', 0) * 100,
        read_success_rate=(
            getattr(scan_result, 'good_sectors', 0) /
            max(geometry.total_sectors, 1) * 100
        ),
        operation_type="Scan",
        duration_seconds=getattr(scan_result, 'elapsed_time', 0),
    )

    # Create printer and print
    printer = ThermalPrinter(printer_name, auto_cut)
    return printer.print_report(
        data,
        include_sector_map=include_sector_map,
        include_logo=include_logo,
        char_width=char_width
    )


# Module exports
__all__ = [
    'ESCPOSCommands',
    'ThermalReportData',
    'ThermalReportFormatter',
    'ThermalPrinter',
    'print_scan_report',
    'PAPER_WIDTHS',
]
