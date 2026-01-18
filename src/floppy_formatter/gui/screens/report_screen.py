"""
Report screen for Floppy Workbench GUI.

Provides HTML-based report viewing with export functionality for scan,
format, restore, diagnostic, and comparison operation results. Includes
embedded circular sector map visualization, flux quality metrics, and
export to PDF, TXT, and HTML formats.

Enhanced for Phase 12: Reports & Documentation
- Integration with new report templates
- Support for diagnostic and comparison reports
- Flux quality metrics display
- Enhanced tooltips and help system
- "What's This?" mode for detailed help
"""

import base64
from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QFileDialog,
    QMessageBox,
    QSizePolicy,
    QFrame,
    QToolButton,
    QWhatsThis,
)
from PyQt6.QtCore import Qt, pyqtSignal, QBuffer
from PyQt6.QtGui import QFont, QPixmap, QPainter

from floppy_formatter.gui.widgets.circular_sector_map import CircularSectorMap
from floppy_formatter.core.geometry import DiskGeometry

# Import the new report generation system
try:
    from floppy_formatter.reports import (
        generate_scan_report,
        generate_recovery_report,
        generate_diagnostic_report,
        generate_comparison_report,
    )
    REPORTS_AVAILABLE = True
except ImportError:
    REPORTS_AVAILABLE = False


# Dark theme colors for HTML reports
COLOR_BACKGROUND = "#1e1e1e"
COLOR_SURFACE = "#252526"
COLOR_BORDER = "#3c3c3c"
COLOR_TEXT = "#cccccc"
COLOR_TEXT_DIM = "#858585"
COLOR_TEXT_BRIGHT = "#ffffff"
COLOR_PRIMARY = "#0e639c"
COLOR_SUCCESS = "#4ec9b0"
COLOR_WARNING = "#f0a030"
COLOR_ERROR = "#f14c4c"
COLOR_TABLE_HEADER = "#2d2d30"
COLOR_TABLE_ROW_ALT = "#2a2a2a"


# =============================================================================
# Tooltip and Help Text Constants
# =============================================================================

TOOLTIPS = {
    "export_pdf": "Export the current report as a PDF document for printing or archiving",
    "export_txt": "Export the current report as a plain text file for easy sharing",
    "export_html": "Export the current report as an HTML file for web viewing",
    "done_button": "Close this report and return to the previous screen",
    "whats_this": "Click then click any element to see detailed help",
    "report_type": "Select a different report type to view",
}

WHATS_THIS_HELP = {
    "export_pdf": """
        <b>Export as PDF</b><br><br>
        Exports the current report as a PDF document. PDFs maintain
        formatting and are ideal for printing or archiving.<br><br>
        The PDF will include all charts, sector maps, and tables
        visible in the current report.
    """,
    "export_txt": """
        <b>Export as Text</b><br><br>
        Exports the current report as a plain text file. Text files
        are lightweight and can be easily shared or included in logs.<br><br>
        Note: Charts and images are not included in text exports.
    """,
    "export_html": """
        <b>Export as HTML</b><br><br>
        Exports the current report as an HTML file. HTML files can be
        viewed in any web browser and maintain full formatting.<br><br>
        Charts and images are embedded as base64 data, so the HTML
        file is completely self-contained.
    """,
    "report_browser": """
        <b>Report Content</b><br><br>
        This area displays the full report content including:<br>
        - Summary statistics<br>
        - Sector map visualization<br>
        - Detailed tables and charts<br>
        - Error information<br><br>
        Scroll to view all content. Links within the report are clickable.
    """,
}


class ReportWidget(QWidget):
    """
    Report viewer widget with export functionality.

    Displays formatted HTML reports for scan, format, restore, diagnostic,
    and comparison operations. Provides export to PDF, TXT, and HTML formats.

    Signals:
        back_requested(): Emitted when user clicks Back/Done button

    Layout:
        ┌──────────────────────────────────────────┐
        │               Report Title               │
        ├──────────────────────────────────────────┤
        │                                          │
        │           QTextBrowser                   │
        │         (HTML Report Content)            │
        │                                          │
        ├──────────────────────────────────────────┤
        │  [Export PDF] [Export TXT] [Export HTML] │
        │                         [?] [Done]       │
        └──────────────────────────────────────────┘

    Features:
        - Multiple report types (scan, format, restore, diagnostic, comparison)
        - Embedded sector map visualization
        - Flux quality metrics display
        - PDF/TXT/HTML export
        - "What's This?" help mode
        - Detailed tooltips
    """

    # Signals
    back_requested = pyqtSignal()

    # Report types (extended for new types)
    REPORT_NONE = "none"
    REPORT_SCAN = "scan"
    REPORT_FORMAT = "format"
    REPORT_RESTORE = "restore"
    REPORT_DIAGNOSTIC = "diagnostic"
    REPORT_COMPARISON = "comparison"
    REPORT_ANALYSIS = "analysis"

    def __init__(self, parent=None):
        """
        Initialize report widget.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)

        # Report data
        self._report_type = self.REPORT_NONE
        self._report_data: Dict[str, Any] = {}
        self._html_content = ""
        self._timestamp = datetime.now()

        # Device info
        self._device_path: Optional[str] = None
        self._geometry: Optional[DiskGeometry] = None

        # Set up UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)

        # Title
        self._title_label = QLabel("Report")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(f"color: {COLOR_TEXT_BRIGHT};")
        layout.addWidget(self._title_label)

        # Subtitle
        self._subtitle_label = QLabel("Operation results and statistics")
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 10pt;")
        layout.addWidget(self._subtitle_label)

        # Report content browser
        self._text_browser = QTextBrowser()
        self._text_browser.setOpenExternalLinks(True)
        self._text_browser.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self._text_browser.setStyleSheet(self._get_text_browser_style())
        self._text_browser.setWhatsThis(WHATS_THIS_HELP.get("report_browser", ""))
        layout.addWidget(self._text_browser, stretch=1)

        # Button container
        button_frame = QFrame()
        button_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(10, 8, 10, 8)
        button_layout.setSpacing(12)

        # Export buttons
        export_label = QLabel("Export:")
        export_label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 10pt;")
        button_layout.addWidget(export_label)

        self._pdf_button = QPushButton("PDF")
        self._pdf_button.setMinimumWidth(80)
        self._pdf_button.setMinimumHeight(36)
        self._pdf_button.setStyleSheet(self._get_button_style())
        self._pdf_button.setToolTip(TOOLTIPS.get("export_pdf", ""))
        self._pdf_button.setWhatsThis(WHATS_THIS_HELP.get("export_pdf", ""))
        self._pdf_button.clicked.connect(self._on_export_pdf)
        button_layout.addWidget(self._pdf_button)

        self._txt_button = QPushButton("TXT")
        self._txt_button.setMinimumWidth(80)
        self._txt_button.setMinimumHeight(36)
        self._txt_button.setStyleSheet(self._get_button_style())
        self._txt_button.setToolTip(TOOLTIPS.get("export_txt", ""))
        self._txt_button.setWhatsThis(WHATS_THIS_HELP.get("export_txt", ""))
        self._txt_button.clicked.connect(self._on_export_txt)
        button_layout.addWidget(self._txt_button)

        self._html_button = QPushButton("HTML")
        self._html_button.setMinimumWidth(80)
        self._html_button.setMinimumHeight(36)
        self._html_button.setStyleSheet(self._get_button_style())
        self._html_button.setToolTip(TOOLTIPS.get("export_html", ""))
        self._html_button.setWhatsThis(WHATS_THIS_HELP.get("export_html", ""))
        self._html_button.clicked.connect(self._on_export_html)
        button_layout.addWidget(self._html_button)

        button_layout.addStretch()

        # What's This button
        self._whats_this_button = QToolButton()
        self._whats_this_button.setText("?")
        self._whats_this_button.setMinimumWidth(36)
        self._whats_this_button.setMinimumHeight(36)
        self._whats_this_button.setStyleSheet(self._get_help_button_style())
        self._whats_this_button.setToolTip(TOOLTIPS.get("whats_this", ""))
        self._whats_this_button.clicked.connect(self._on_whats_this_clicked)
        button_layout.addWidget(self._whats_this_button)

        # Done button
        self._done_button = QPushButton("Done")
        self._done_button.setMinimumWidth(100)
        self._done_button.setMinimumHeight(36)
        self._done_button.setStyleSheet(self._get_primary_button_style())
        self._done_button.setToolTip(TOOLTIPS.get("done_button", ""))
        self._done_button.clicked.connect(self._on_done_clicked)
        button_layout.addWidget(self._done_button)

        layout.addWidget(button_frame)

        # Show placeholder initially
        self._show_placeholder()

    def _get_text_browser_style(self) -> str:
        """Get stylesheet for text browser."""
        return f"""
            QTextBrowser {{
                background-color: {COLOR_BACKGROUND};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
                padding: 10px;
                font-family: 'Segoe UI', 'Ubuntu', sans-serif;
                font-size: 10pt;
            }}
            QScrollBar:vertical {{
                background-color: {COLOR_BACKGROUND};
                width: 12px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: #4e5157;
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #5a5d61;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar:horizontal {{
                background-color: {COLOR_BACKGROUND};
                height: 12px;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background-color: #4e5157;
                border-radius: 4px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: #5a5d61;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
        """

    def _get_button_style(self) -> str:
        """Get stylesheet for standard buttons."""
        return f"""
            QPushButton {{
                background-color: #3a3d41;
                color: {COLOR_TEXT_BRIGHT};
                border: 1px solid #6c6c6c;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: #4e5157;
                border-color: #858585;
            }}
            QPushButton:pressed {{
                background-color: #2d2d30;
            }}
            QPushButton:disabled {{
                background-color: #2d2d30;
                color: #6c6c6c;
                border-color: #3c3c3c;
            }}
        """

    def _get_primary_button_style(self) -> str:
        """Get stylesheet for primary action buttons."""
        return f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: {COLOR_TEXT_BRIGHT};
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 10pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #1177bb;
            }}
            QPushButton:pressed {{
                background-color: #094771;
            }}
        """

    def _get_help_button_style(self) -> str:
        """Get stylesheet for help button."""
        return f"""
            QToolButton {{
                background-color: transparent;
                color: {COLOR_TEXT_DIM};
                border: 1px solid {COLOR_BORDER};
                border-radius: 18px;
                font-size: 12pt;
                font-weight: bold;
            }}
            QToolButton:hover {{
                background-color: {COLOR_SURFACE};
                color: {COLOR_TEXT_BRIGHT};
                border-color: {COLOR_PRIMARY};
            }}
            QToolButton:pressed {{
                background-color: {COLOR_PRIMARY};
            }}
        """

    def _show_placeholder(self) -> None:
        """Show placeholder message when no report data is available."""
        self._title_label.setText("Report")
        self._subtitle_label.setText("No report data available")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
                    background-color: {COLOR_BACKGROUND};
                    color: {COLOR_TEXT};
                    padding: 40px;
                    text-align: center;
                }}
                .placeholder {{
                    color: {COLOR_TEXT_DIM};
                    font-size: 14pt;
                    margin-top: 100px;
                }}
                .hint {{
                    color: {COLOR_TEXT_DIM};
                    font-size: 10pt;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <p class="placeholder">No report data available</p>
            <p class="hint">Complete a scan, format, restore, or diagnostic
            operation to view its report.</p>
        </body>
        </html>
        """
        self._html_content = html
        self._text_browser.setHtml(html)

        # Disable export buttons
        self._pdf_button.setEnabled(False)
        self._txt_button.setEnabled(False)
        self._html_button.setEnabled(False)

    def set_device_info(self, device_path: str, geometry: DiskGeometry) -> None:
        """
        Set device information for the report.

        Args:
            device_path: Device path (e.g., '/dev/sde')
            geometry: Disk geometry information
        """
        self._device_path = device_path
        self._geometry = geometry

    def set_scan_report(
        self,
        sector_map,
        statistics: Dict[str, Any],
        bad_sectors: Optional[List[Dict[str, Any]]] = None,
        flux_quality: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Set scan operation report data.

        Args:
            sector_map: SectorMap from scan operation
            statistics: Dictionary with scan statistics
            bad_sectors: Optional list of bad sector details
            flux_quality: Optional flux quality metrics
        """
        self._report_type = self.REPORT_SCAN
        self._timestamp = datetime.now()
        self._report_data = {
            "sector_map": sector_map,
            "statistics": statistics,
            "bad_sectors": bad_sectors or [],
            "flux_quality": flux_quality,
        }

        self._generate_scan_report()

    def set_format_report(
        self,
        format_result,
        statistics: Dict[str, Any],
        bad_tracks: Optional[List[int]] = None
    ) -> None:
        """
        Set format operation report data.

        Args:
            format_result: Result from format operation
            statistics: Dictionary with format statistics
            bad_tracks: Optional list of bad track numbers
        """
        self._report_type = self.REPORT_FORMAT
        self._timestamp = datetime.now()
        self._report_data = {
            "format_result": format_result,
            "statistics": statistics,
            "bad_tracks": bad_tracks or [],
        }

        self._generate_format_report()

    def set_restore_report(
        self,
        recovery_stats,
        statistics: Dict[str, Any],
        convergence_history: Optional[List[Dict[str, Any]]] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Set restore operation report data.

        Args:
            recovery_stats: RecoveryStatistics from restore operation
            statistics: Dictionary with restore statistics
            convergence_history: Optional list of convergence history entries
            settings: Optional restore settings used
        """
        self._report_type = self.REPORT_RESTORE
        self._timestamp = datetime.now()
        self._report_data = {
            "recovery_stats": recovery_stats,
            "statistics": statistics,
            "convergence_history": convergence_history or [],
            "settings": settings or {},
        }

        self._generate_restore_report()

    def set_diagnostic_report(
        self,
        diagnostic_data: Dict[str, Any]
    ) -> None:
        """
        Set diagnostic operation report data.

        Args:
            diagnostic_data: Dictionary with diagnostic results including:
                - drive_info: Drive information
                - alignment: Head alignment data
                - rpm: RPM stability data
                - flux_quality: Flux quality metrics
                - health_score: Overall health score (0-100)
                - health_grade: Letter grade (A-F)
                - recommendations: List of recommendations
        """
        self._report_type = self.REPORT_DIAGNOSTIC
        self._timestamp = datetime.now()
        self._report_data = diagnostic_data

        self._generate_diagnostic_report()

    def set_comparison_report(
        self,
        comparison_data: Dict[str, Any]
    ) -> None:
        """
        Set comparison operation report data.

        Args:
            comparison_data: Dictionary with comparison results including:
                - source: Source image/disk info
                - target: Target image/disk info
                - result: Comparison results
                - differences: List of differences
        """
        self._report_type = self.REPORT_COMPARISON
        self._timestamp = datetime.now()
        self._report_data = comparison_data

        self._generate_comparison_report()

    def _get_html_header(self, title: str) -> str:
        """
        Get HTML document header with styles.

        Args:
            title: Document title

        Returns:
            HTML header string
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{title}</title>
            <style>
                body {{
                    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
                    background-color: {COLOR_BACKGROUND};
                    color: {COLOR_TEXT};
                    padding: 20px;
                    line-height: 1.6;
                }}
                h1 {{
                    color: {COLOR_TEXT_BRIGHT};
                    font-size: 24pt;
                    margin-bottom: 5px;
                    text-align: center;
                }}
                h2 {{
                    color: {COLOR_TEXT_BRIGHT};
                    font-size: 14pt;
                    margin-top: 25px;
                    margin-bottom: 10px;
                    padding-bottom: 5px;
                    border-bottom: 1px solid {COLOR_BORDER};
                }}
                h3 {{
                    color: {COLOR_TEXT};
                    font-size: 12pt;
                    margin-top: 15px;
                    margin-bottom: 8px;
                }}
                .timestamp {{
                    color: {COLOR_TEXT_DIM};
                    font-size: 10pt;
                    text-align: center;
                    margin-bottom: 20px;
                }}
                .device-info {{
                    background-color: {COLOR_SURFACE};
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 6px;
                    padding: 15px;
                    margin-bottom: 20px;
                }}
                .summary {{
                    background-color: {COLOR_SURFACE};
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 6px;
                    padding: 15px;
                    margin-bottom: 20px;
                }}
                .summary-item {{
                    display: flex;
                    margin-bottom: 8px;
                }}
                .summary-label {{
                    color: {COLOR_TEXT_DIM};
                    min-width: 150px;
                }}
                .summary-value {{
                    color: {COLOR_TEXT_BRIGHT};
                    font-weight: bold;
                }}
                .good {{
                    color: {COLOR_SUCCESS};
                }}
                .bad {{
                    color: {COLOR_ERROR};
                }}
                .warning {{
                    color: {COLOR_WARNING};
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                    background-color: {COLOR_SURFACE};
                }}
                th {{
                    background-color: {COLOR_TABLE_HEADER};
                    color: {COLOR_TEXT_BRIGHT};
                    padding: 10px 12px;
                    text-align: left;
                    font-weight: bold;
                    border: 1px solid {COLOR_BORDER};
                }}
                td {{
                    padding: 8px 12px;
                    border: 1px solid {COLOR_BORDER};
                }}
                tr:nth-child(even) {{
                    background-color: {COLOR_TABLE_ROW_ALT};
                }}
                tr:hover {{
                    background-color: #333333;
                }}
                .sector-map-container {{
                    text-align: center;
                    margin: 20px 0;
                }}
                .sector-map-container img {{
                    max-width: 100%;
                    height: auto;
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 6px;
                }}
                .status-success {{
                    background-color: #1a3d1a;
                    border: 1px solid {COLOR_SUCCESS};
                    color: {COLOR_SUCCESS};
                    padding: 15px;
                    border-radius: 6px;
                    text-align: center;
                    margin: 20px 0;
                    font-weight: bold;
                }}
                .status-warning {{
                    background-color: #3d3d1a;
                    border: 1px solid {COLOR_WARNING};
                    color: {COLOR_WARNING};
                    padding: 15px;
                    border-radius: 6px;
                    text-align: center;
                    margin: 20px 0;
                    font-weight: bold;
                }}
                .status-error {{
                    background-color: #3d1a1a;
                    border: 1px solid {COLOR_ERROR};
                    color: {COLOR_ERROR};
                    padding: 15px;
                    border-radius: 6px;
                    text-align: center;
                    margin: 20px 0;
                    font-weight: bold;
                }}
                .delta-improved {{
                    color: {COLOR_SUCCESS};
                }}
                .delta-unchanged {{
                    color: {COLOR_WARNING};
                }}
                .delta-worsened {{
                    color: {COLOR_ERROR};
                }}
                .metric-card {{
                    display: inline-block;
                    background-color: {COLOR_SURFACE};
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 8px;
                    padding: 15px 25px;
                    margin: 10px;
                    text-align: center;
                    min-width: 100px;
                }}
                .metric-value {{
                    font-size: 20pt;
                    font-weight: bold;
                    color: {COLOR_TEXT_BRIGHT};
                }}
                .metric-label {{
                    font-size: 9pt;
                    color: {COLOR_TEXT_DIM};
                    margin-top: 5px;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 15px;
                    border-top: 1px solid {COLOR_BORDER};
                    color: {COLOR_TEXT_DIM};
                    font-size: 9pt;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
        """

    def _get_html_footer(self) -> str:
        """Get HTML document footer."""
        return """
            <div class="footer">
                Generated by Floppy Workbench - Greaseweazle Edition<br>
                https://github.com/JYewman/Floppy-Disk-Restorer
            </div>
        </body>
        </html>
        """

    def _sector_to_chs(self, sector_num: int) -> tuple:
        """
        Convert absolute sector number to CHS coordinates.

        Args:
            sector_num: Absolute sector number (0-2879)

        Returns:
            Tuple of (cylinder, head, sector)
        """
        sectors_per_track = 18
        heads = 2

        cylinder = sector_num // (sectors_per_track * heads)
        head = (sector_num // sectors_per_track) % heads
        sector = (sector_num % sectors_per_track) + 1  # Sectors are 1-indexed

        return (cylinder, head, sector)

    def _render_sector_map_to_base64(self, sector_data: Optional[Dict[int, bool]] = None) -> str:
        """
        Render circular sector map to base64-encoded PNG.

        Args:
            sector_data: Optional dict mapping sector numbers to good/bad status

        Returns:
            Base64-encoded PNG image data URL
        """
        # Create offscreen sector map widget
        sector_map = CircularSectorMap()
        sector_map.setFixedSize(600, 600)

        # Populate with sector data if provided
        if sector_data:
            for sector_num, is_good in sector_data.items():
                if 0 <= sector_num < 2880:
                    sector_map.update_sector(sector_num, is_good, animate=False)

        # Render to pixmap using QPainter
        pixmap = QPixmap(sector_map.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        sector_map.render(painter)
        painter.end()

        # Convert to base64
        buffer = QBuffer()
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        buffer.close()

        image_data = base64.b64encode(buffer.data().data()).decode('utf-8')
        return f"data:image/png;base64,{image_data}"

    def _generate_scan_report(self) -> None:
        """Generate HTML report for scan operation."""
        self._title_label.setText("Disk Scan Report")
        self._subtitle_label.setText(f"Scanned: {self._device_path or 'Unknown device'}")

        # Try to use new report system if available
        if REPORTS_AVAILABLE:
            try:
                stats = self._report_data.get("statistics", {})
                bad_sectors = self._report_data.get("bad_sectors", [])
                flux_quality = self._report_data.get("flux_quality")

                # Build sector data for map
                total_sectors = stats.get("total", 2880)
                sector_data = {}
                for i in range(total_sectors):
                    sector_data[i] = True

                for bad_sector in bad_sectors:
                    if isinstance(bad_sector, dict):
                        sector_num = bad_sector.get("sector", 0)
                    else:
                        sector_num = bad_sector
                    if 0 <= sector_num < total_sectors:
                        sector_data[sector_num] = False

                sector_map_image = self._render_sector_map_to_base64(sector_data)

                # Prepare data for template
                report_data = {
                    "total_sectors": stats.get("total", 2880),
                    "good_sectors": stats.get("good_count", 0),
                    "bad_sectors": stats.get("bad_count", 0),
                    "bad_sector_list": bad_sectors,
                    "elapsed_ms": stats.get("elapsed_ms", 0),
                    "sector_map_image": sector_map_image,
                    "flux_quality": flux_quality,
                }

                html = generate_scan_report(
                    report_data,
                    device_path=self._device_path or "Unknown",
                    geometry=str(self._geometry) if self._geometry else "Unknown"
                )

                self._html_content = html
                self._text_browser.setHtml(html)
                self._enable_export_buttons()
                return

            except Exception:
                # Fall back to legacy generation
                pass

        # Legacy report generation
        self._generate_scan_report_legacy()

    def _generate_scan_report_legacy(self) -> None:
        """Legacy scan report generation (fallback)."""
        stats = self._report_data.get("statistics", {})
        bad_sectors = self._report_data.get("bad_sectors", [])

        total_sectors = stats.get("total", 2880)
        good_count = stats.get("good_count", 0)
        bad_count = stats.get("bad_count", 0)
        elapsed_ms = stats.get("elapsed_ms", 0)

        elapsed_secs = elapsed_ms // 1000
        minutes = elapsed_secs // 60
        seconds = elapsed_secs % 60

        good_percent = (good_count / total_sectors * 100) if total_sectors > 0 else 0
        bad_percent = (bad_count / total_sectors * 100) if total_sectors > 0 else 0
        bad_class = 'bad' if bad_count > 0 else 'good'

        # Build HTML
        html = self._get_html_header("Disk Scan Report")

        html += f"""
        <h1>Disk Scan Report</h1>
        <p class="timestamp">Generated: {self._timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="device-info">
            <h3>Device Information</h3>
            <div class="summary-item">
                <span class="summary-label">Device Path:</span>
                <span class="summary-value">{self._device_path or 'Unknown'}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Geometry:</span>
                <span class="summary-value">{self._geometry or 'Unknown'}</span>
            </div>
        </div>

        <h2>Scan Summary</h2>
        <div class="summary">
            <div class="summary-item">
                <span class="summary-label">Total Sectors:</span>
                <span class="summary-value">{total_sectors}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Good Sectors:</span>
                <span class="summary-value good">{good_count} ({good_percent:.1f}%)</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Bad Sectors:</span>
                <span class="summary-value {bad_class}">{bad_count} ({bad_percent:.1f}%)</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Scan Duration:</span>
                <span class="summary-value">{minutes:02d}:{seconds:02d}</span>
            </div>
        </div>
        """

        # Status assessment
        if bad_count == 0:
            html += """
            <div class="status-success">
                Scan Complete - No Bad Sectors Found
            </div>
            """
        else:
            html += f"""
            <div class="status-warning">
                Scan Complete - {bad_count} Bad Sector(s) Found
            </div>
            """

        # Sector map visualization
        sector_data = {}
        for i in range(total_sectors):
            sector_data[i] = True
        for bad_sector in bad_sectors:
            if isinstance(bad_sector, dict):
                sector_num = bad_sector.get("sector", 0)
            else:
                sector_num = bad_sector
            if 0 <= sector_num < total_sectors:
                sector_data[sector_num] = False

        sector_map_image = self._render_sector_map_to_base64(sector_data)

        html += f"""
        <h2>Sector Map</h2>
        <div class="sector-map-container">
            <img src="{sector_map_image}" alt="Sector Map">
        </div>
        """

        # Bad sector details
        if bad_count > 0:
            html += """
            <h2>Bad Sector Details</h2>
            <table>
                <tr>
                    <th>Sector #</th>
                    <th>Cylinder</th>
                    <th>Head</th>
                    <th>Sector</th>
                    <th>Error Type</th>
                </tr>
            """

            for bad_sector in bad_sectors[:100]:
                if isinstance(bad_sector, dict):
                    sector_num = bad_sector.get("sector", 0)
                    error_type = bad_sector.get("error_type", "Unknown")
                else:
                    sector_num = bad_sector
                    error_type = "Read Error"

                cyl, head, sect = self._sector_to_chs(sector_num)

                html += f"""
                <tr>
                    <td>{sector_num}</td>
                    <td>{cyl}</td>
                    <td>{head}</td>
                    <td>{sect}</td>
                    <td class="bad">{error_type}</td>
                </tr>
                """

            html += "</table>"
        else:
            html += """
            <h2>Bad Sector Details</h2>
            <p class="good">No bad sectors found.</p>
            """

        html += self._get_html_footer()

        self._html_content = html
        self._text_browser.setHtml(html)
        self._enable_export_buttons()

    def _generate_format_report(self) -> None:
        """Generate HTML report for format operation."""
        self._title_label.setText("Disk Format Report")
        self._subtitle_label.setText(f"Formatted: {self._device_path or 'Unknown device'}")

        stats = self._report_data.get("statistics", {})
        bad_tracks = self._report_data.get("bad_tracks", [])

        total_tracks = stats.get("total_tracks", 160)
        bad_sectors = stats.get("bad_sectors", 0)
        elapsed_ms = stats.get("elapsed_ms", 0)

        elapsed_secs = elapsed_ms // 1000
        minutes = elapsed_secs // 60
        seconds = elapsed_secs % 60

        bad_track_count = len(bad_tracks)
        successful_tracks = total_tracks - bad_track_count
        bad_tracks_class = 'bad' if bad_track_count > 0 else 'good'
        bad_sectors_class = 'bad' if bad_sectors > 0 else 'good'

        # Build HTML
        html = self._get_html_header("Disk Format Report")

        html += f"""
        <h1>Disk Format Report</h1>
        <p class="timestamp">Generated: {self._timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="device-info">
            <h3>Device Information</h3>
            <div class="summary-item">
                <span class="summary-label">Device Path:</span>
                <span class="summary-value">{self._device_path or 'Unknown'}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Geometry:</span>
                <span class="summary-value">{self._geometry or 'Unknown'}</span>
            </div>
        </div>

        <h2>Format Summary</h2>
        <div class="summary">
            <div class="summary-item">
                <span class="summary-label">Total Tracks:</span>
                <span class="summary-value">{total_tracks}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Successful Tracks:</span>
                <span class="summary-value good">{successful_tracks}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Bad Tracks:</span>
                <span class="summary-value {bad_tracks_class}">{bad_track_count}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Bad Sectors:</span>
                <span class="summary-value {bad_sectors_class}">{bad_sectors}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Format Duration:</span>
                <span class="summary-value">{minutes:02d}:{seconds:02d}</span>
            </div>
        </div>
        """

        # Status assessment
        if bad_sectors == 0 and bad_track_count == 0:
            html += """
            <div class="status-success">
                Format Successful - Disk is Ready for Use
            </div>
            """
        else:
            html += f"""
            <div class="status-warning">
                Format Completed with Errors - {bad_sectors} Bad Sector(s) Found
            </div>
            """

        html += self._get_html_footer()

        self._html_content = html
        self._text_browser.setHtml(html)
        self._enable_export_buttons()

    def _generate_restore_report(self) -> None:
        """Generate HTML report for restore operation."""
        self._title_label.setText("Disk Restore Report")
        self._subtitle_label.setText(f"Restored: {self._device_path or 'Unknown device'}")

        # Try to use new report system
        if REPORTS_AVAILABLE:
            try:
                stats = self._report_data.get("statistics", {})
                settings = self._report_data.get("settings", {})
                convergence_history = self._report_data.get("convergence_history", [])
                recovery_stats = self._report_data.get("recovery_stats")

                initial_bad = stats.get("initial_bad_count", 0)
                final_bad = stats.get("final_bad_count", 0)

                if recovery_stats:
                    initial_bad = getattr(recovery_stats, 'initial_bad_sector_count', initial_bad)
                    final_bad = getattr(recovery_stats, 'final_bad_sector_count', final_bad)

                report_data = {
                    "initial_bad": initial_bad,
                    "final_bad": final_bad,
                    "passes_executed": stats.get("passes_executed", 0),
                    "convergence_history": convergence_history,
                    "elapsed_ms": stats.get("elapsed_ms", 0),
                    "settings": settings,
                }

                html = generate_recovery_report(
                    report_data,
                    device_path=self._device_path or "Unknown",
                    geometry=str(self._geometry) if self._geometry else "Unknown"
                )

                self._html_content = html
                self._text_browser.setHtml(html)
                self._enable_export_buttons()
                return

            except Exception:
                pass

        # Legacy restore report generation
        self._generate_restore_report_legacy()

    def _generate_restore_report_legacy(self) -> None:
        """Legacy restore report generation (fallback)."""
        stats = self._report_data.get("statistics", {})
        recovery_stats = self._report_data.get("recovery_stats")

        initial_bad = stats.get("initial_bad_count", 0)
        final_bad = stats.get("final_bad_count", 0)
        passes_executed = stats.get("passes_executed", 0)
        elapsed_ms = stats.get("elapsed_ms", 0)

        if recovery_stats:
            initial_bad = getattr(recovery_stats, 'initial_bad_sector_count', initial_bad)
            final_bad = getattr(recovery_stats, 'final_bad_sector_count', final_bad)

        recovered = initial_bad - final_bad if initial_bad > 0 else 0
        recovery_rate = (recovered / initial_bad * 100) if initial_bad > 0 else 0
        final_bad_class = 'good' if final_bad == 0 else 'bad'
        recovered_class = 'good' if recovered > 0 else ''

        elapsed_secs = elapsed_ms // 1000
        minutes = elapsed_secs // 60
        seconds = elapsed_secs % 60

        # Build HTML
        html = self._get_html_header("Disk Restore Report")

        html += f"""
        <h1>Disk Restore Report</h1>
        <p class="timestamp">Generated: {self._timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="device-info">
            <h3>Device Information</h3>
            <div class="summary-item">
                <span class="summary-label">Device Path:</span>
                <span class="summary-value">{self._device_path or 'Unknown'}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Geometry:</span>
                <span class="summary-value">{self._geometry or 'Unknown'}</span>
            </div>
        </div>

        <h2>Results Summary</h2>
        <div class="summary">
            <div class="summary-item">
                <span class="summary-label">Passes Executed:</span>
                <span class="summary-value">{passes_executed}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Initial Bad Sectors:</span>
                <span class="summary-value bad">{initial_bad}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Final Bad Sectors:</span>
                <span class="summary-value {final_bad_class}">{final_bad}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Sectors Recovered:</span>
                <span class="summary-value {recovered_class}">{recovered}
                ({recovery_rate:.1f}%)</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Recovery Duration:</span>
                <span class="summary-value">{minutes:02d}:{seconds:02d}</span>
            </div>
        </div>
        """

        # Status assessment
        if final_bad == 0:
            html += """
            <div class="status-success">
                Restore Complete - All Sectors Recovered Successfully
            </div>
            """
        elif recovered > 0:
            html += f"""
            <div class="status-warning">
                Restore Complete - {recovered} Sector(s) Recovered, {final_bad} Remaining
            </div>
            """
        else:
            html += f"""
            <div class="status-error">
                Restore Complete - {final_bad} Sector(s) Could Not Be Recovered
            </div>
            """

        html += self._get_html_footer()

        self._html_content = html
        self._text_browser.setHtml(html)
        self._enable_export_buttons()

    def _generate_diagnostic_report(self) -> None:
        """Generate HTML report for diagnostic operation."""
        self._title_label.setText("Drive Diagnostic Report")
        self._subtitle_label.setText(f"Diagnosed: {self._device_path or 'Unknown device'}")

        if REPORTS_AVAILABLE:
            try:
                html = generate_diagnostic_report(
                    self._report_data,
                    device_path=self._device_path or "Unknown"
                )

                self._html_content = html
                self._text_browser.setHtml(html)
                self._enable_export_buttons()
                return

            except Exception:
                pass

        # Fallback - simple diagnostic report
        html = self._get_html_header("Drive Diagnostic Report")
        html += f"""
        <h1>Drive Diagnostic Report</h1>
        <p class="timestamp">Generated: {self._timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Diagnostic data not available.</p>
        """
        html += self._get_html_footer()

        self._html_content = html
        self._text_browser.setHtml(html)
        self._enable_export_buttons()

    def _generate_comparison_report(self) -> None:
        """Generate HTML report for comparison operation."""
        self._title_label.setText("Image Comparison Report")
        self._subtitle_label.setText("Comparison results")

        if REPORTS_AVAILABLE:
            try:
                html = generate_comparison_report(self._report_data)

                self._html_content = html
                self._text_browser.setHtml(html)
                self._enable_export_buttons()
                return

            except Exception:
                pass

        # Fallback - simple comparison report
        html = self._get_html_header("Image Comparison Report")
        html += f"""
        <h1>Image Comparison Report</h1>
        <p class="timestamp">Generated: {self._timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Comparison data not available.</p>
        """
        html += self._get_html_footer()

        self._html_content = html
        self._text_browser.setHtml(html)
        self._enable_export_buttons()

    def _enable_export_buttons(self) -> None:
        """Enable all export buttons."""
        self._pdf_button.setEnabled(True)
        self._txt_button.setEnabled(True)
        self._html_button.setEnabled(True)

    def _get_default_filename(self, extension: str) -> str:
        """
        Get default filename for export.

        Args:
            extension: File extension (pdf, txt, html)

        Returns:
            Default filename string
        """
        date_str = self._timestamp.strftime('%Y-%m-%d_%H%M%S')
        return f"{self._report_type}_report_{date_str}.{extension}"

    def _on_export_pdf(self) -> None:
        """Handle PDF export button click."""
        default_name = self._get_default_filename("pdf")

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report as PDF",
            default_name,
            "PDF Files (*.pdf)"
        )

        if not file_path:
            return  # Cancelled

        try:
            from PyQt6.QtPrintSupport import QPrinter

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)
            printer.setPageMargins(15, 15, 15, 15, QPrinter.Unit.Millimeter)

            self._text_browser.document().print(printer)

            QMessageBox.information(
                self,
                "Export Successful",
                f"Report exported successfully to:\n\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export PDF:\n\n{str(e)}"
            )

    def _on_export_txt(self) -> None:
        """Handle TXT export button click."""
        default_name = self._get_default_filename("txt")

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report as Text",
            default_name,
            "Text Files (*.txt)"
        )

        if not file_path:
            return  # Cancelled

        try:
            txt_content = self._generate_plain_text_report()

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(txt_content)

            QMessageBox.information(
                self,
                "Export Successful",
                f"Report exported successfully to:\n\n{file_path}"
            )

        except PermissionError:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Permission denied. Cannot write to:\n\n{file_path}\n\n"
                "Please choose a different location."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export text file:\n\n{str(e)}"
            )

    def _on_export_html(self) -> None:
        """Handle HTML export button click."""
        default_name = self._get_default_filename("html")

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report as HTML",
            default_name,
            "HTML Files (*.html)"
        )

        if not file_path:
            return  # Cancelled

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self._html_content)

            QMessageBox.information(
                self,
                "Export Successful",
                f"Report exported successfully to:\n\n{file_path}"
            )

        except PermissionError:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Permission denied. Cannot write to:\n\n{file_path}\n\n"
                "Please choose a different location."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export HTML file:\n\n{str(e)}"
            )

    def _generate_plain_text_report(self) -> str:
        """
        Generate plain text version of the report.

        Returns:
            Plain text report string
        """
        lines = []
        border = "=" * 70

        if self._report_type == self.REPORT_SCAN:
            lines.append(border)
            lines.append("                      DISK SCAN REPORT")
            lines.append(border)
            lines.append(f"Generated: {self._timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")

            stats = self._report_data.get("statistics", {})
            bad_sectors = self._report_data.get("bad_sectors", [])

            lines.append("DEVICE INFORMATION")
            lines.append("-" * 40)
            lines.append(f"Device Path:  {self._device_path or 'Unknown'}")
            lines.append(f"Geometry:     {self._geometry or 'Unknown'}")
            lines.append("")

            lines.append("SCAN SUMMARY")
            lines.append("-" * 40)

            total = stats.get("total", 2880)
            good = stats.get("good_count", 0)
            bad = stats.get("bad_count", 0)
            elapsed_ms = stats.get("elapsed_ms", 0)
            elapsed_secs = elapsed_ms // 1000

            lines.append(f"Total Sectors:   {total}")
            lines.append(f"Good Sectors:    {good} ({good/total*100:.1f}%)")
            lines.append(f"Bad Sectors:     {bad} ({bad/total*100:.1f}%)")
            lines.append(f"Scan Duration:   {elapsed_secs // 60:02d}:{elapsed_secs % 60:02d}")
            lines.append("")

            if bad == 0:
                lines.append("[OK] Scan Complete - No Bad Sectors Found")
            else:
                lines.append(f"[!] Scan Complete - {bad} Bad Sector(s) Found")
            lines.append("")

            if bad > 0:
                lines.append("BAD SECTOR DETAILS")
                lines.append("-" * 40)
                header = f"{'Sector':>8} {'Cylinder':>10} {'Head':>6} {'Sector':>8} {'Error':>12}"
                lines.append(header)
                lines.append("-" * 48)

                for bad_sector in bad_sectors[:50]:
                    if isinstance(bad_sector, dict):
                        sector_num = bad_sector.get("sector", 0)
                        error_type = bad_sector.get("error_type", "Unknown")
                    else:
                        sector_num = bad_sector
                        error_type = "Read Error"

                    cyl, head, sect = self._sector_to_chs(sector_num)
                    lines.append(f"{sector_num:>8} {cyl:>10} {head:>6} {sect:>8} {error_type:>12}")

        elif self._report_type == self.REPORT_RESTORE:
            lines.append(border)
            lines.append("                     DISK RESTORE REPORT")
            lines.append(border)
            lines.append(f"Generated: {self._timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")

            stats = self._report_data.get("statistics", {})

            initial_bad = stats.get("initial_bad_count", 0)
            final_bad = stats.get("final_bad_count", 0)
            passes_executed = stats.get("passes_executed", 0)

            lines.append("DEVICE INFORMATION")
            lines.append("-" * 40)
            lines.append(f"Device Path:  {self._device_path or 'Unknown'}")
            lines.append(f"Geometry:     {self._geometry or 'Unknown'}")
            lines.append("")

            lines.append("RESULTS SUMMARY")
            lines.append("-" * 40)
            lines.append(f"Passes Executed:    {passes_executed}")
            lines.append(f"Initial Bad:        {initial_bad}")
            lines.append(f"Final Bad:          {final_bad}")

            recovered = initial_bad - final_bad
            rate = (recovered / initial_bad * 100) if initial_bad > 0 else 0
            lines.append(f"Sectors Recovered:  {recovered} ({rate:.1f}%)")

        else:
            lines.append(border)
            lines.append(f"                     {self._report_type.upper()} REPORT")
            lines.append(border)
            lines.append(f"Generated: {self._timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        lines.append("")
        lines.append(border)
        lines.append("Generated by Floppy Workbench - Greaseweazle Edition")
        lines.append("https://github.com/JYewman/Floppy-Disk-Restorer")
        lines.append(border)

        return "\n".join(lines)

    def _on_whats_this_clicked(self) -> None:
        """Handle What's This button click."""
        QWhatsThis.enterWhatsThisMode()

    def _on_done_clicked(self) -> None:
        """Handle Done button click."""
        self.back_requested.emit()

    def clear_report(self) -> None:
        """Clear the current report and show placeholder."""
        self._report_type = self.REPORT_NONE
        self._report_data = {}
        self._html_content = ""
        self._show_placeholder()

    def get_report_type(self) -> str:
        """
        Get the current report type.

        Returns:
            Report type string
        """
        return self._report_type

    def has_report(self) -> bool:
        """
        Check if a report is currently loaded.

        Returns:
            True if a report is available
        """
        return self._report_type != self.REPORT_NONE
