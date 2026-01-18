"""
Thermal printer support for Star TSP100 and compatible printers.

This module provides functionality to print disk analysis reports
on 80mm thermal receipt printers using the Windows printing API.

Features:
    - Formats reports for 80mm thermal paper
    - Graphical logo, bar charts, and sector map visualization
    - Auto-cut support for Star TSP100 printers
    - ESC/POS command support for direct printing
    - Image printing for better visual quality

Part of Phase 15: Thermal Printer Support
"""

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

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

    # Image printing (ESC/POS raster bit image)
    RASTER_IMAGE = b'\x1d\x76\x30'         # GS v 0 - Print raster bit image


# Thermal paper dimensions (in pixels at 203 DPI - standard for thermal printers)
THERMAL_DPI = 203
PAPER_WIDTH_PX = {
    58: 384,   # 58mm paper (~48mm printable)
    80: 576,   # 80mm paper (~72mm printable)
}


class ThermalImageGenerator:
    """
    Generates graphical images for thermal printing.

    Creates logo, bar charts, and sector maps as images
    for better visual quality than ASCII art.
    """

    def __init__(self, paper_width_mm: int = 80):
        """
        Initialize image generator.

        Args:
            paper_width_mm: Paper width in mm (58 or 80)
        """
        self.paper_width_mm = paper_width_mm
        self.width_px = PAPER_WIDTH_PX.get(paper_width_mm, 576)
        self._pil_available = self._check_pil()

    def _check_pil(self) -> bool:
        """Check if PIL/Pillow is available."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            return True
        except ImportError:
            logger.warning("Pillow not available - falling back to text-only printing")
            return False

    @property
    def is_available(self) -> bool:
        """Check if image generation is available."""
        return self._pil_available

    def create_logo(self, height: int = 80) -> Optional["PILImage"]:
        """
        Create the Floppy Workbench logo image.

        Args:
            height: Logo height in pixels

        Returns:
            PIL Image or None if PIL not available
        """
        if not self._pil_available:
            return None

        try:
            from PIL import Image, ImageDraw, ImageFont

            # Try to load the actual logo first
            logo_path = Path(__file__).parent.parent / "gui" / "resources" / "icons" / "app_logo.png"
            if logo_path.exists():
                logo = Image.open(logo_path).convert('L')  # Grayscale
                # Resize to fit width while maintaining aspect ratio
                aspect = logo.width / logo.height
                new_width = min(self.width_px - 40, int(height * aspect))
                new_height = int(new_width / aspect)
                logo = logo.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Create centered image
                img = Image.new('L', (self.width_px, new_height + 20), 255)
                x_offset = (self.width_px - new_width) // 2
                img.paste(logo, (x_offset, 10))

                # Convert to 1-bit for thermal printing (dithered)
                return img.convert('1')

            # Fallback: Create text-based logo
            img = Image.new('1', (self.width_px, height), 1)  # White background
            draw = ImageDraw.Draw(img)

            # Try to use a nice font, fallback to default
            try:
                font_large = ImageFont.truetype("arial.ttf", 24)
                font_small = ImageFont.truetype("arial.ttf", 14)
            except Exception:
                font_large = ImageFont.load_default()
                font_small = font_large

            # Draw title
            title = "FLOPPY WORKBENCH"
            bbox = draw.textbbox((0, 0), title, font=font_large)
            text_width = bbox[2] - bbox[0]
            x = (self.width_px - text_width) // 2
            draw.text((x, 15), title, font=font_large, fill=0)

            # Draw subtitle
            subtitle = "Disk Analysis Tool"
            bbox = draw.textbbox((0, 0), subtitle, font=font_small)
            text_width = bbox[2] - bbox[0]
            x = (self.width_px - text_width) // 2
            draw.text((x, 50), subtitle, font=font_small, fill=0)

            return img

        except Exception as e:
            logger.error(f"Failed to create logo image: {e}")
            return None

    def create_bar_chart(
        self,
        values: List[Tuple[str, float, str]],
        height_per_bar: int = 30,
        show_percentage: bool = True
    ) -> Optional["PILImage"]:
        """
        Create a horizontal bar chart image.

        Args:
            values: List of (label, value 0-1, color_hint) tuples
            height_per_bar: Height of each bar in pixels
            show_percentage: Show percentage labels

        Returns:
            PIL Image or None if PIL not available
        """
        if not self._pil_available:
            return None

        try:
            from PIL import Image, ImageDraw, ImageFont

            # Calculate dimensions
            margin = 10
            label_width = 100
            bar_width = self.width_px - label_width - margin * 3 - 50  # Space for %
            total_height = len(values) * height_per_bar + margin * 2

            # Create image
            img = Image.new('1', (self.width_px, total_height), 1)
            draw = ImageDraw.Draw(img)

            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except Exception:
                font = ImageFont.load_default()

            y = margin
            for label, value, color_hint in values:
                # Draw label
                draw.text((margin, y + 5), label, font=font, fill=0)

                # Draw bar background (outline)
                bar_x = label_width + margin
                draw.rectangle(
                    [bar_x, y + 2, bar_x + bar_width, y + height_per_bar - 4],
                    outline=0,
                    fill=1
                )

                # Draw filled portion
                filled_width = int(bar_width * min(value, 1.0))
                if filled_width > 0:
                    # Use different fill patterns based on color hint
                    if color_hint == "bad":
                        # Crosshatch pattern for bad
                        for i in range(bar_x, bar_x + filled_width, 4):
                            draw.line([(i, y + 2), (i, y + height_per_bar - 4)], fill=0)
                    elif color_hint == "weak":
                        # Dotted pattern for weak
                        for i in range(bar_x, bar_x + filled_width, 3):
                            for j in range(y + 2, y + height_per_bar - 4, 3):
                                draw.point((i, j), fill=0)
                    else:
                        # Solid fill for good
                        draw.rectangle(
                            [bar_x, y + 2, bar_x + filled_width, y + height_per_bar - 4],
                            fill=0
                        )

                # Draw percentage
                if show_percentage:
                    pct_text = f"{value * 100:.1f}%"
                    draw.text(
                        (bar_x + bar_width + 5, y + 5),
                        pct_text,
                        font=font,
                        fill=0
                    )

                y += height_per_bar

            return img

        except Exception as e:
            logger.error(f"Failed to create bar chart: {e}")
            return None

    def create_sector_map(
        self,
        sector_map: Dict[int, Dict[int, List[str]]],
        cylinders: int,
        heads: int,
        sectors_per_track: int
    ) -> Optional["PILImage"]:
        """
        Create a graphical sector map visualization.

        Maps for each head are placed side-by-side to save paper length.

        Args:
            sector_map: Dict of cylinder -> head -> list of sector statuses
            cylinders: Total number of cylinders
            heads: Number of heads (sides)
            sectors_per_track: Sectors per track

        Returns:
            PIL Image or None if PIL not available
        """
        if not self._pil_available:
            return None

        try:
            from PIL import Image, ImageDraw, ImageFont

            margin = 10
            label_height = 20
            legend_height = 25
            head_label_width = 20  # Width for "H0", "H1" labels
            gap_between_heads = 8  # Gap between the two head maps

            # Calculate width available for each head's map (side by side)
            available_width = self.width_px - margin * 2 - head_label_width * heads - gap_between_heads
            single_map_width = available_width // heads

            # Calculate cell sizes
            cyl_width = max(2, single_map_width // cylinders)
            sector_height = max(2, min(4, 200 // sectors_per_track))

            # Total height for the map area
            head_map_height = sectors_per_track * sector_height
            total_height = (
                label_height +  # "SECTOR MAP" title
                15 +  # Head labels row
                head_map_height +  # Single map height (both heads same row)
                legend_height + margin * 2
            )

            # Create image
            img = Image.new('1', (self.width_px, total_height), 1)
            draw = ImageDraw.Draw(img)

            try:
                font = ImageFont.truetype("arial.ttf", 10)
                font_title = ImageFont.truetype("arial.ttf", 12)
            except Exception:
                font = ImageFont.load_default()
                font_title = font

            y = margin

            # Title
            title = "SECTOR MAP"
            bbox = draw.textbbox((0, 0), title, font=font_title)
            text_width = bbox[2] - bbox[0]
            draw.text(((self.width_px - text_width) // 2, y), title, font=font_title, fill=0)
            y += label_height

            # Draw both head maps side by side
            for head in range(heads):
                # Calculate X offset for this head's map
                head_offset = margin + head * (head_label_width + single_map_width + gap_between_heads // 2)
                map_x = head_offset + head_label_width

                # Head label
                draw.text((head_offset, y), f"H{head}", font=font, fill=0)

            y += 12  # Move past head labels

            map_y = y  # Starting Y for the actual maps

            for head in range(heads):
                head_offset = margin + head * (head_label_width + single_map_width + gap_between_heads // 2)
                map_x = head_offset + head_label_width

                # Draw sector map grid
                for sector in range(sectors_per_track):
                    for cyl in range(cylinders):
                        x = map_x + cyl * cyl_width
                        cell_y = map_y + sector * sector_height

                        # Get sector status
                        status = "unknown"
                        if sector_map and cyl in sector_map:
                            if head in sector_map[cyl]:
                                statuses = sector_map[cyl][head]
                                if sector < len(statuses):
                                    status = statuses[sector]

                        # Draw cell based on status
                        if status == "good":
                            # White (paper color) - good
                            pass
                        elif status == "bad":
                            # Solid black - bad
                            draw.rectangle(
                                [x, cell_y, x + cyl_width - 1, cell_y + sector_height - 1],
                                fill=0
                            )
                        elif status == "weak":
                            # Gray pattern - weak
                            for px in range(x, x + cyl_width, 2):
                                for py in range(cell_y, cell_y + sector_height, 2):
                                    draw.point((px, py), fill=0)
                        else:
                            # Light gray - unknown
                            if (cyl + sector) % 3 == 0:
                                draw.point((x + cyl_width // 2, cell_y + sector_height // 2), fill=0)

                # Draw grid border
                draw.rectangle(
                    [map_x, map_y, map_x + cylinders * cyl_width, map_y + head_map_height],
                    outline=0
                )

            y = map_y + head_map_height + 10

            # Legend
            legend_items = [
                ("Good", 1),      # White
                ("Bad", 0),       # Black
                ("Weak", "gray")  # Gray pattern
            ]

            legend_x = margin
            for label, fill in legend_items:
                # Draw sample box
                if fill == "gray":
                    draw.rectangle([legend_x, y, legend_x + 12, y + 12], outline=0)
                    for px in range(legend_x, legend_x + 12, 2):
                        for py in range(y, y + 12, 2):
                            draw.point((px, py), fill=0)
                else:
                    draw.rectangle([legend_x, y, legend_x + 12, y + 12], outline=0, fill=fill)

                draw.text((legend_x + 16, y), label, font=font, fill=0)
                legend_x += 70

            return img

        except Exception as e:
            logger.error(f"Failed to create sector map: {e}")
            return None

    def create_header_image(self, title: str, subtitle: str = "") -> Optional["PILImage"]:
        """
        Create a styled header image.

        Args:
            title: Main title text
            subtitle: Optional subtitle

        Returns:
            PIL Image or None
        """
        if not self._pil_available:
            return None

        try:
            from PIL import Image, ImageDraw, ImageFont

            height = 60 if subtitle else 40
            img = Image.new('1', (self.width_px, height), 1)
            draw = ImageDraw.Draw(img)

            try:
                font_title = ImageFont.truetype("arialbd.ttf", 18)
                font_sub = ImageFont.truetype("arial.ttf", 12)
            except Exception:
                font_title = ImageFont.load_default()
                font_sub = font_title

            # Draw decorative line
            draw.line([(10, 5), (self.width_px - 10, 5)], fill=0, width=2)

            # Draw title centered
            bbox = draw.textbbox((0, 0), title, font=font_title)
            text_width = bbox[2] - bbox[0]
            draw.text(((self.width_px - text_width) // 2, 12), title, font=font_title, fill=0)

            if subtitle:
                bbox = draw.textbbox((0, 0), subtitle, font=font_sub)
                text_width = bbox[2] - bbox[0]
                draw.text(((self.width_px - text_width) // 2, 38), subtitle, font=font_sub, fill=0)

            # Draw decorative line
            draw.line([(10, height - 5), (self.width_px - 10, height - 5)], fill=0, width=2)

            return img

        except Exception as e:
            logger.error(f"Failed to create header image: {e}")
            return None


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
        """Add text-based logo header (fallback when graphics unavailable)."""
        self.lines.append(self._center("* * * * * * * * * * * * * * * *"))
        self.lines.append(self._center("FLOPPY WORKBENCH"))
        self.lines.append(self._center("Disk Analysis Tool"))
        self.lines.append(self._center("* * * * * * * * * * * * * * * *"))
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
    via the Windows printing API. Can print both text and
    graphical images for better visual quality.
    """

    def __init__(
        self,
        printer_name: str = "",
        auto_cut: bool = True,
        paper_width_mm: int = 80
    ):
        """
        Initialize thermal printer.

        Args:
            printer_name: OS printer name (empty for default)
            auto_cut: Whether to auto-cut paper after printing
            paper_width_mm: Paper width in mm (58 or 80)
        """
        self.printer_name = printer_name
        self.auto_cut = auto_cut
        self.paper_width_mm = paper_width_mm
        self._is_available = False

        # Image generator for graphical printing
        self._image_generator = ThermalImageGenerator(paper_width_mm)

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

    def print_report(
        self,
        data: ThermalReportData,
        include_sector_map: bool = True,
        include_logo: bool = True,
        char_width: int = 48,
        use_graphics: bool = True
    ) -> bool:
        """
        Format and print a disk analysis report.

        Args:
            data: Report data
            include_sector_map: Include sector map visualization
            include_logo: Include application logo
            char_width: Characters per line (for text fallback)
            use_graphics: Use graphical images instead of ASCII art

        Returns:
            True if printing succeeded
        """
        # Try graphical printing if available and requested
        if use_graphics and self._image_generator.is_available:
            return self._print_graphical_report(data, include_sector_map, include_logo)

        # Fall back to text-only printing
        formatter = ThermalReportFormatter(char_width)
        report_text = formatter.format_report(
            data,
            include_sector_map=include_sector_map,
            include_logo=include_logo
        )
        return self.print_text(report_text)

    def _print_graphical_report(
        self,
        data: ThermalReportData,
        include_sector_map: bool = True,
        include_logo: bool = True
    ) -> bool:
        """
        Print report with graphical images.

        Uses PIL to generate images for logo, bar charts, and sector map,
        then prints them using Qt's printing system.

        Args:
            data: Report data
            include_sector_map: Include graphical sector map
            include_logo: Include application logo image

        Returns:
            True if printing succeeded
        """
        if not self._is_available:
            logger.error("Printer not available")
            return False

        try:
            from PIL import Image
            from PyQt6.QtGui import QImage, QPainter, QFont, QFontMetrics
            from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
            from PyQt6.QtCore import QMarginsF, QSizeF, Qt

            # Set up printer
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)

            for info in QPrinterInfo.availablePrinters():
                if info.printerName() == self.printer_name:
                    printer.setPrinterName(self.printer_name)
                    break
            else:
                printer.setPrinterName(QPrinterInfo.defaultPrinter().printerName())

            # Set page size for thermal paper
            page_size = QSizeF(self.paper_width_mm, 500)  # Long page for receipts
            printer.setPageSize(page_size)
            printer.setPageMargins(QMarginsF(2, 2, 2, 2))

            # Create painter
            painter = QPainter()
            if not painter.begin(printer):
                logger.error("Could not start printer")
                return False

            try:
                # Printer resolution and scaling
                dpi = printer.resolution()
                scale = dpi / THERMAL_DPI  # Scale from 203 DPI to printer DPI

                y_pos = 10  # Current Y position
                margin = 10

                # Set up text font
                font = QFont("Arial", 10)
                font_bold = QFont("Arial", 10, QFont.Weight.Bold)
                font_small = QFont("Arial", 8)
                painter.setFont(font)
                metrics = QFontMetrics(font)
                line_height = metrics.height() + 2

                # Helper to draw PIL image
                def draw_pil_image(pil_img, y: int) -> int:
                    """Draw PIL image and return new Y position."""
                    # Convert PIL image to QImage
                    if pil_img.mode == '1':
                        # 1-bit image - convert to RGB for Qt
                        pil_img = pil_img.convert('RGB')

                    img_data = pil_img.tobytes('raw', 'RGB')
                    qimg = QImage(
                        img_data,
                        pil_img.width,
                        pil_img.height,
                        pil_img.width * 3,
                        QImage.Format.Format_RGB888
                    )

                    # Scale to printer resolution
                    scaled_width = int(pil_img.width * scale)
                    scaled_height = int(pil_img.height * scale)

                    # Draw centered
                    x = margin
                    painter.drawImage(x, y, qimg.scaled(
                        scaled_width, scaled_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    ))

                    return y + scaled_height + 10

                # Helper to draw text line
                def draw_text(text: str, y: int, centered: bool = False, bold: bool = False) -> int:
                    painter.setFont(font_bold if bold else font)
                    if centered:
                        text_width = QFontMetrics(painter.font()).horizontalAdvance(text)
                        page_width = int(printer.pageRect(QPrinter.Unit.DevicePixel).width())
                        x = (page_width - text_width) // 2
                    else:
                        x = margin
                    painter.drawText(x, y + metrics.ascent(), text)
                    return y + line_height

                # Helper to draw two-column text
                def draw_two_col(left: str, right: str, y: int) -> int:
                    painter.setFont(font)
                    page_width = int(printer.pageRect(QPrinter.Unit.DevicePixel).width())
                    painter.drawText(margin, y + metrics.ascent(), left)
                    right_width = metrics.horizontalAdvance(right)
                    painter.drawText(page_width - margin - right_width, y + metrics.ascent(), right)
                    return y + line_height

                # Helper to draw separator line
                def draw_separator(y: int, char: str = "-") -> int:
                    page_width = int(printer.pageRect(QPrinter.Unit.DevicePixel).width())
                    painter.drawLine(margin, y + 5, page_width - margin, y + 5)
                    return y + 12

                # === PRINT LOGO ===
                if include_logo:
                    logo_img = self._image_generator.create_logo(height=80)
                    if logo_img:
                        y_pos = draw_pil_image(logo_img, y_pos)

                # === HEADER ===
                y_pos = draw_separator(y_pos, "=")
                y_pos = draw_text(data.title, y_pos, centered=True, bold=True)
                y_pos = draw_separator(y_pos, "=")
                y_pos += 5

                # Timestamp
                y_pos = draw_text(
                    data.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    y_pos,
                    centered=True
                )
                if data.disk_label:
                    y_pos = draw_text(f"Label: {data.disk_label}", y_pos, centered=True)
                y_pos += 10

                # === DISK INFORMATION ===
                y_pos = draw_separator(y_pos)
                y_pos = draw_text("DISK INFORMATION", y_pos, centered=True, bold=True)
                y_pos = draw_separator(y_pos)

                y_pos = draw_two_col("Format:", data.format_type, y_pos)
                y_pos = draw_two_col("Cylinders:", str(data.cylinders), y_pos)
                y_pos = draw_two_col("Heads:", str(data.heads), y_pos)
                y_pos = draw_two_col("Sectors/Track:", str(data.sectors_per_track), y_pos)
                y_pos = draw_two_col("Total Sectors:", str(data.total_sectors), y_pos)
                y_pos += 10

                # === RESULTS with BAR CHART ===
                y_pos = draw_separator(y_pos)
                y_pos = draw_text(f"{data.operation_type.upper()} RESULTS", y_pos, centered=True, bold=True)
                y_pos = draw_separator(y_pos)

                # Create bar chart image
                good_pct = data.good_sectors / max(data.total_sectors, 1)
                bad_pct = data.bad_sectors / max(data.total_sectors, 1)
                weak_pct = data.weak_sectors / max(data.total_sectors, 1)

                bar_values = [
                    (f"Good ({data.good_sectors})", good_pct, "good"),
                    (f"Bad ({data.bad_sectors})", bad_pct, "bad"),
                    (f"Weak ({data.weak_sectors})", weak_pct, "weak"),
                ]
                bar_chart = self._image_generator.create_bar_chart(bar_values)
                if bar_chart:
                    y_pos = draw_pil_image(bar_chart, y_pos)
                else:
                    # Fallback to text
                    y_pos = draw_two_col(f"Good: {data.good_sectors}", f"{good_pct*100:.1f}%", y_pos)
                    y_pos = draw_two_col(f"Bad: {data.bad_sectors}", f"{bad_pct*100:.1f}%", y_pos)
                    y_pos = draw_two_col(f"Weak: {data.weak_sectors}", f"{weak_pct*100:.1f}%", y_pos)

                y_pos += 5

                # === QUALITY METRICS ===
                y_pos = draw_separator(y_pos)
                y_pos = draw_text("QUALITY METRICS", y_pos, centered=True, bold=True)
                y_pos = draw_separator(y_pos)

                # Quality bar chart
                quality_values = [
                    ("Signal Quality", data.signal_quality / 100, "good"),
                    ("Read Success", data.read_success_rate / 100, "good"),
                ]
                quality_chart = self._image_generator.create_bar_chart(quality_values)
                if quality_chart:
                    y_pos = draw_pil_image(quality_chart, y_pos)
                else:
                    y_pos = draw_two_col("Signal Quality:", f"{data.signal_quality:.1f}%", y_pos)
                    y_pos = draw_two_col("Read Success:", f"{data.read_success_rate:.1f}%", y_pos)

                # Duration
                mins = int(data.duration_seconds // 60)
                secs = int(data.duration_seconds % 60)
                y_pos = draw_two_col("Duration:", f"{mins}m {secs}s", y_pos)
                y_pos += 10

                # === SECTOR MAP ===
                if include_sector_map and data.sector_map:
                    sector_map_img = self._image_generator.create_sector_map(
                        data.sector_map,
                        data.cylinders,
                        data.heads,
                        data.sectors_per_track
                    )
                    if sector_map_img:
                        y_pos = draw_pil_image(sector_map_img, y_pos)

                # === FOOTER ===
                y_pos += 10
                y_pos = draw_separator(y_pos, "=")
                y_pos = draw_text("Floppy Workbench v2.0", y_pos, centered=True)
                painter.setFont(font_small)
                y_pos = draw_text("github.com/JYewman", y_pos, centered=True)
                y_pos = draw_separator(y_pos, "=")

            finally:
                painter.end()

            logger.info(f"Printed graphical report to {self.printer_name}")
            return True

        except ImportError as e:
            logger.warning(f"Graphical printing not available: {e}")
            # Fall back to text printing
            formatter = ThermalReportFormatter(PAPER_WIDTHS.get(self.paper_width_mm, 48))
            report_text = formatter.format_report(data, include_sector_map, include_logo)
            return self.print_text(report_text)

        except Exception as e:
            logger.error(f"Graphical printing failed: {e}", exc_info=True)
            return False


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
    'ThermalImageGenerator',
    'ThermalReportData',
    'ThermalReportFormatter',
    'ThermalPrinter',
    'print_scan_report',
    'PAPER_WIDTHS',
    'PAPER_WIDTH_PX',
    'THERMAL_DPI',
]
