"""
Sector info panel for Floppy Workbench GUI.

A collapsible sidebar that displays detailed information about
a hovered or selected sector, including:
- Address information (Sector, CHS, LBA, byte offset)
- Current status with colored indicator
- Status history over time
- Raw hex dump preview (first 64 bytes)
- Flux quality metrics

Part of Phase 6: Enhanced Sector Map Visualization
"""

import logging
from datetime import datetime
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QGroupBox,
    QScrollArea,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette

from floppy_formatter.gui.widgets.circular_sector_map import (
    CircularSectorMap,
    SectorMetadata,
    SectorStatus,
    FluxQualityMetrics,
    HistoryEntry,
)

logger = logging.getLogger(__name__)


class StatusIndicator(QWidget):
    """
    A small colored indicator showing sector status.
    """

    # Status colors
    STATUS_COLORS = {
        SectorStatus.UNSCANNED: "#505050",
        SectorStatus.GOOD: "#00c800",
        SectorStatus.BAD: "#c83232",
        SectorStatus.RECOVERING: "#ffb400",
        SectorStatus.READING: "#3278dc",
        SectorStatus.WRITING: "#9632c8",
        SectorStatus.VERIFYING: "#ff8c32",
    }

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize status indicator."""
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._status = SectorStatus.UNSCANNED
        self._update_style()

    def set_status(self, status: SectorStatus) -> None:
        """Set the status to display."""
        self._status = status
        self._update_style()

    def _update_style(self) -> None:
        """Update the indicator style based on current status."""
        color = self.STATUS_COLORS.get(self._status, "#505050")
        self.setStyleSheet(f"""
            StatusIndicator {{
                background-color: {color};
                border-radius: 8px;
                border: 1px solid #3a3d41;
            }}
        """)


class CollapsibleSection(QWidget):
    """
    A collapsible section with a header and content area.
    """

    def __init__(
        self,
        title: str,
        parent: Optional[QWidget] = None,
        initially_expanded: bool = True
    ):
        """
        Initialize collapsible section.

        Args:
            title: Section title
            parent: Parent widget
            initially_expanded: Whether section starts expanded
        """
        super().__init__(parent)

        self._is_expanded = initially_expanded

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button
        self._header_button = QPushButton(f"{'▼' if initially_expanded else '▶'} {title}")
        self._header_button.setFlat(True)
        self._header_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d30;
                color: #cccccc;
                border: none;
                padding: 6px 8px;
                text-align: left;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #3a3d41;
            }
        """)
        self._header_button.clicked.connect(self._toggle)
        layout.addWidget(self._header_button)

        # Content container
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(8, 4, 8, 8)
        self._content_layout.setSpacing(4)

        self._content_widget.setVisible(initially_expanded)
        layout.addWidget(self._content_widget)

        self._title = title

    def _toggle(self) -> None:
        """Toggle section expansion."""
        self._is_expanded = not self._is_expanded
        self._content_widget.setVisible(self._is_expanded)
        arrow = "▼" if self._is_expanded else "▶"
        self._header_button.setText(f"{arrow} {self._title}")

    def add_widget(self, widget: QWidget) -> None:
        """Add a widget to the content area."""
        self._content_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        """Add a layout to the content area."""
        self._content_layout.addLayout(layout)

    def is_expanded(self) -> bool:
        """Check if section is expanded."""
        return self._is_expanded

    def set_expanded(self, expanded: bool) -> None:
        """Set expansion state."""
        if self._is_expanded != expanded:
            self._toggle()


class HexDumpWidget(QPlainTextEdit):
    """
    A widget for displaying hex dump of sector data.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize hex dump widget."""
        super().__init__(parent)

        # Set up font
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        if not font.exactMatch():
            font = QFont("monospace", 9)
        self.setFont(font)

        # Read-only
        self.setReadOnly(True)

        # Styling
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #dcdcdc;
                border: 1px solid #3a3d41;
                border-radius: 3px;
            }
        """)

        # Size
        self.setMinimumHeight(120)
        self.setMaximumHeight(180)

        # Initial state
        self.setPlainText("No data available")

    def set_data(self, data: Optional[bytes]) -> None:
        """
        Set the data to display as hex dump.

        Args:
            data: Bytes to display (first 64 bytes shown)
        """
        if not data:
            self.setPlainText("No data available")
            return

        # Limit to 64 bytes
        data = data[:64]

        lines = []
        for offset in range(0, len(data), 16):
            # Get 16 bytes for this line
            chunk = data[offset:offset + 16]

            # Format offset
            offset_str = f"{offset:04X}"

            # Format hex bytes
            hex_parts = []
            for i, byte in enumerate(chunk):
                hex_parts.append(f"{byte:02X}")
                if i == 7:
                    hex_parts.append(" ")  # Extra space in middle
            hex_str = " ".join(hex_parts)

            # Pad hex string if less than 16 bytes
            hex_str = hex_str.ljust(49)  # 16 * 3 - 1 + 2 (extra space in middle)

            # Format ASCII
            ascii_parts = []
            for byte in chunk:
                if 32 <= byte <= 126:
                    ascii_parts.append(chr(byte))
                else:
                    ascii_parts.append(".")
            ascii_str = "".join(ascii_parts)

            lines.append(f"{offset_str}  {hex_str}  {ascii_str}")

        self.setPlainText("\n".join(lines))


class QualityMetricsWidget(QWidget):
    """
    Widget for displaying flux quality metrics.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize quality metrics widget."""
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Signal strength row
        strength_layout = QHBoxLayout()
        strength_label = QLabel("Signal:")
        strength_label.setStyleSheet("color: #858585; font-size: 9pt;")
        strength_label.setFixedWidth(60)
        strength_layout.addWidget(strength_label)

        self._strength_bar = QProgressBar()
        self._strength_bar.setRange(0, 100)
        self._strength_bar.setValue(0)
        self._strength_bar.setTextVisible(True)
        self._strength_bar.setMaximumHeight(16)
        self._strength_bar.setStyleSheet("""
            QProgressBar {
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 3px;
                text-align: center;
                color: #cccccc;
                font-size: 8pt;
            }
            QProgressBar::chunk {
                background-color: #33cc33;
                border-radius: 2px;
            }
        """)
        strength_layout.addWidget(self._strength_bar)
        layout.addLayout(strength_layout)

        # Jitter row
        jitter_layout = QHBoxLayout()
        jitter_label = QLabel("Jitter:")
        jitter_label.setStyleSheet("color: #858585; font-size: 9pt;")
        jitter_label.setFixedWidth(60)
        jitter_layout.addWidget(jitter_label)

        self._jitter_value = QLabel("N/A")
        self._jitter_value.setStyleSheet("color: #cccccc; font-size: 9pt;")
        jitter_layout.addWidget(self._jitter_value)
        jitter_layout.addStretch()
        layout.addLayout(jitter_layout)

        # SNR row
        snr_layout = QHBoxLayout()
        snr_label = QLabel("SNR:")
        snr_label.setStyleSheet("color: #858585; font-size: 9pt;")
        snr_label.setFixedWidth(60)
        snr_layout.addWidget(snr_label)

        self._snr_value = QLabel("N/A")
        self._snr_value.setStyleSheet("color: #cccccc; font-size: 9pt;")
        snr_layout.addWidget(self._snr_value)
        snr_layout.addStretch()
        layout.addLayout(snr_layout)

        # Grade row
        grade_layout = QHBoxLayout()
        grade_label = QLabel("Grade:")
        grade_label.setStyleSheet("color: #858585; font-size: 9pt;")
        grade_label.setFixedWidth(60)
        grade_layout.addWidget(grade_label)

        self._grade_value = QLabel("?")
        self._grade_value.setStyleSheet("""
            color: #858585;
            font-size: 14pt;
            font-weight: bold;
        """)
        grade_layout.addWidget(self._grade_value)
        grade_layout.addStretch()
        layout.addLayout(grade_layout)

    def set_metrics(self, metrics: Optional[FluxQualityMetrics]) -> None:
        """
        Set flux quality metrics to display.

        Args:
            metrics: FluxQualityMetrics or None to clear
        """
        if not metrics:
            self._strength_bar.setValue(0)
            self._jitter_value.setText("N/A")
            self._snr_value.setText("N/A")
            self._grade_value.setText("?")
            self._grade_value.setStyleSheet("color: #858585; font-size: 14pt; font-weight: bold;")
            return

        # Signal strength
        strength_percent = int(metrics.signal_strength * 100)
        self._strength_bar.setValue(strength_percent)

        # Update bar color based on strength
        if strength_percent >= 80:
            bar_color = "#33cc33"  # Green
        elif strength_percent >= 50:
            bar_color = "#cccc33"  # Yellow
        else:
            bar_color = "#cc3333"  # Red

        self._strength_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 3px;
                text-align: center;
                color: #cccccc;
                font-size: 8pt;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 2px;
            }}
        """)

        # Jitter
        self._jitter_value.setText(f"{metrics.jitter:.2f} us")

        # SNR
        self._snr_value.setText(f"{metrics.snr:.1f} dB")

        # Grade with color
        grade = metrics.quality_grade
        grade_colors = {
            "A": "#33cc33",
            "B": "#88cc33",
            "C": "#cccc33",
            "D": "#cc8833",
            "F": "#cc3333",
        }
        grade_color = grade_colors.get(grade, "#858585")
        self._grade_value.setText(grade)
        self._grade_value.setStyleSheet(f"""
            color: {grade_color};
            font-size: 14pt;
            font-weight: bold;
        """)


class SectorInfoPanel(QWidget):
    """
    Collapsible sidebar panel showing detailed sector information.

    Displays:
    - Address information (Sector number, CHS, LBA, byte offset)
    - Current status with colored indicator
    - Status history (scan results over time)
    - Raw hex dump preview (first 64 bytes)
    - Flux quality metrics

    Connects to CircularSectorMap to update when sectors are hovered or selected.
    """

    # Minimum and maximum widths
    MIN_WIDTH = 250
    MAX_WIDTH = 400
    DEFAULT_WIDTH = 280

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize sector info panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Reference to sector map
        self._sector_map: Optional[CircularSectorMap] = None

        # Currently displayed sector
        self._current_sector: Optional[int] = None

        # Collapsed state
        self._is_collapsed = False

        # Build UI
        self._setup_ui()

        # Initial state
        self.clear_display()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setMaximumWidth(self.MAX_WIDTH)

        # Apply panel styling
        self.setStyleSheet("""
            SectorInfoPanel {
                background-color: #252526;
                border-left: 1px solid #3a3d41;
            }
        """)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header_widget = QWidget()
        header_widget.setStyleSheet("background-color: #2d2d30;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(8, 6, 8, 6)

        header_label = QLabel("Sector Info")
        header_label.setStyleSheet("color: #ffffff; font-size: 11pt; font-weight: bold;")
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        # Collapse button
        self._collapse_btn = QPushButton("◀")
        self._collapse_btn.setFixedSize(24, 24)
        self._collapse_btn.setToolTip("Collapse panel")
        self._collapse_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #858585;
                border: none;
                font-size: 12pt;
            }
            QPushButton:hover {
                color: #ffffff;
            }
        """)
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        header_layout.addWidget(self._collapse_btn)

        main_layout.addWidget(header_widget)

        # Scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #252526;
            }
            QScrollBar:vertical {
                background-color: #252526;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background-color: #3a3d41;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4a4d51;
            }
        """)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 4, 0, 8)
        content_layout.setSpacing(0)

        # Address section
        self._address_section = self._create_address_section()
        content_layout.addWidget(self._address_section)

        # Status section
        self._status_section = self._create_status_section()
        content_layout.addWidget(self._status_section)

        # History section
        self._history_section = self._create_history_section()
        content_layout.addWidget(self._history_section)

        # Hex dump section
        self._hex_section = self._create_hex_section()
        content_layout.addWidget(self._hex_section)

        # Flux quality section
        self._quality_section = self._create_quality_section()
        content_layout.addWidget(self._quality_section)

        # Stretch at bottom
        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

    def _create_address_section(self) -> CollapsibleSection:
        """Create the address information section."""
        section = CollapsibleSection("Address", initially_expanded=True)

        # Sector number
        sector_layout = QHBoxLayout()
        sector_label = QLabel("Sector:")
        sector_label.setStyleSheet("color: #858585; font-size: 10pt;")
        sector_label.setFixedWidth(70)
        sector_layout.addWidget(sector_label)

        self._sector_value = QLabel("---")
        self._sector_value.setStyleSheet("color: #ffffff; font-size: 10pt;")
        sector_layout.addWidget(self._sector_value)
        sector_layout.addStretch()
        section.add_layout(sector_layout)

        # CHS address
        chs_layout = QHBoxLayout()
        chs_label = QLabel("CHS:")
        chs_label.setStyleSheet("color: #858585; font-size: 10pt;")
        chs_label.setFixedWidth(70)
        chs_layout.addWidget(chs_label)

        self._chs_value = QLabel("---/---/---")
        self._chs_value.setStyleSheet("color: #ffffff; font-size: 10pt;")
        chs_layout.addWidget(self._chs_value)
        chs_layout.addStretch()
        section.add_layout(chs_layout)

        # LBA
        lba_layout = QHBoxLayout()
        lba_label = QLabel("LBA:")
        lba_label.setStyleSheet("color: #858585; font-size: 10pt;")
        lba_label.setFixedWidth(70)
        lba_layout.addWidget(lba_label)

        self._lba_value = QLabel("---")
        self._lba_value.setStyleSheet("color: #ffffff; font-size: 10pt;")
        lba_layout.addWidget(self._lba_value)
        lba_layout.addStretch()
        section.add_layout(lba_layout)

        # Byte offset
        offset_layout = QHBoxLayout()
        offset_label = QLabel("Offset:")
        offset_label.setStyleSheet("color: #858585; font-size: 10pt;")
        offset_label.setFixedWidth(70)
        offset_layout.addWidget(offset_label)

        self._offset_value = QLabel("---")
        self._offset_value.setStyleSheet("color: #ffffff; font-size: 10pt;")
        offset_layout.addWidget(self._offset_value)
        offset_layout.addStretch()
        section.add_layout(offset_layout)

        return section

    def _create_status_section(self) -> CollapsibleSection:
        """Create the status information section."""
        section = CollapsibleSection("Status", initially_expanded=True)

        # Current status with indicator
        status_layout = QHBoxLayout()
        status_label = QLabel("Current:")
        status_label.setStyleSheet("color: #858585; font-size: 10pt;")
        status_label.setFixedWidth(70)
        status_layout.addWidget(status_label)

        self._status_indicator = StatusIndicator()
        status_layout.addWidget(self._status_indicator)

        self._status_text = QLabel("Unscanned")
        self._status_text.setStyleSheet("color: #ffffff; font-size: 10pt;")
        status_layout.addWidget(self._status_text)
        status_layout.addStretch()
        section.add_layout(status_layout)

        # Last operation
        op_layout = QHBoxLayout()
        op_label = QLabel("Last Op:")
        op_label.setStyleSheet("color: #858585; font-size: 10pt;")
        op_label.setFixedWidth(70)
        op_layout.addWidget(op_label)

        self._last_op_value = QLabel("None")
        self._last_op_value.setStyleSheet("color: #cccccc; font-size: 10pt;")
        op_layout.addWidget(self._last_op_value)
        op_layout.addStretch()
        section.add_layout(op_layout)

        # Last access time
        time_layout = QHBoxLayout()
        time_label = QLabel("Last Access:")
        time_label.setStyleSheet("color: #858585; font-size: 10pt;")
        time_label.setFixedWidth(70)
        time_layout.addWidget(time_label)

        self._last_access_value = QLabel("Never")
        self._last_access_value.setStyleSheet("color: #cccccc; font-size: 10pt;")
        time_layout.addWidget(self._last_access_value)
        time_layout.addStretch()
        section.add_layout(time_layout)

        return section

    def _create_history_section(self) -> CollapsibleSection:
        """Create the status history section."""
        section = CollapsibleSection("History", initially_expanded=True)

        # History table
        self._history_table = QTableWidget()
        self._history_table.setColumnCount(3)
        self._history_table.setHorizontalHeaderLabels(["Time", "Operation", "Result"])
        self._history_table.setMinimumHeight(100)
        self._history_table.setMaximumHeight(150)

        # Configure table
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.verticalHeader().setVisible(False)

        # Column sizing
        header = self._history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._history_table.setColumnWidth(0, 60)
        self._history_table.setColumnWidth(2, 60)

        # Styling
        self._history_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 3px;
                gridline-color: #3a3d41;
                font-size: 9pt;
            }
            QTableWidget::item {
                padding: 2px 4px;
            }
            QTableWidget::item:alternate {
                background-color: #252526;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                border: none;
                border-bottom: 1px solid #3a3d41;
                padding: 4px;
                font-size: 9pt;
            }
        """)

        section.add_widget(self._history_table)
        return section

    def _create_hex_section(self) -> CollapsibleSection:
        """Create the hex dump section."""
        section = CollapsibleSection("Data Preview", initially_expanded=True)

        self._hex_dump = HexDumpWidget()
        section.add_widget(self._hex_dump)

        return section

    def _create_quality_section(self) -> CollapsibleSection:
        """Create the flux quality metrics section."""
        section = CollapsibleSection("Flux Quality", initially_expanded=True)

        self._quality_widget = QualityMetricsWidget()
        section.add_widget(self._quality_widget)

        return section

    def _toggle_collapse(self) -> None:
        """Toggle panel collapse state."""
        self._is_collapsed = not self._is_collapsed

        if self._is_collapsed:
            self._collapse_btn.setText("▶")
            self._collapse_btn.setToolTip("Expand panel")
            self.setMaximumWidth(40)
            self.setMinimumWidth(40)
        else:
            self._collapse_btn.setText("◀")
            self._collapse_btn.setToolTip("Collapse panel")
            self.setMaximumWidth(self.MAX_WIDTH)
            self.setMinimumWidth(self.MIN_WIDTH)

    # =========================================================================
    # Public API
    # =========================================================================

    def connect_to_sector_map(self, sector_map: CircularSectorMap) -> None:
        """
        Connect this panel to a CircularSectorMap instance.

        Args:
            sector_map: The sector map to connect to
        """
        self._sector_map = sector_map

        # Connect signals
        sector_map.sector_hovered.connect(self.update_for_sector)
        sector_map.sector_clicked.connect(self.update_for_sector)

    def disconnect_from_sector_map(self) -> None:
        """Disconnect from the current sector map."""
        if self._sector_map:
            try:
                self._sector_map.sector_hovered.disconnect(self.update_for_sector)
                self._sector_map.sector_clicked.disconnect(self.update_for_sector)
            except Exception:
                pass
            self._sector_map = None

    def update_for_sector(self, sector_num: int) -> None:
        """
        Update the display for a specific sector.

        Args:
            sector_num: Sector number to display
        """
        self._current_sector = sector_num

        # Get metadata from sector map cache
        metadata: Optional[SectorMetadata] = None
        if self._sector_map:
            cache = self._sector_map.get_data_cache()
            metadata = cache.get_metadata(sector_num)

        if metadata:
            self._display_metadata(metadata)
        else:
            self._display_basic_info(sector_num)

    def _display_metadata(self, metadata: SectorMetadata) -> None:
        """Display full metadata for a sector."""
        # Address section
        self._sector_value.setText(str(metadata.sector_num))
        self._chs_value.setText(f"{metadata.cylinder}/{metadata.head}/{metadata.sector_offset + 1}")
        self._lba_value.setText(str(metadata.get_lba()))
        self._offset_value.setText(f"{metadata.get_byte_offset():,}")

        # Status section
        self._status_indicator.set_status(metadata.status)
        self._status_text.setText(metadata.status.name.capitalize())

        # Set status text color
        status_colors = {
            SectorStatus.GOOD: "#33cc33",
            SectorStatus.BAD: "#cc3333",
            SectorStatus.RECOVERING: "#ffb400",
            SectorStatus.READING: "#3278dc",
            SectorStatus.WRITING: "#9632c8",
            SectorStatus.VERIFYING: "#ff8c32",
        }
        color = status_colors.get(metadata.status, "#858585")
        self._status_text.setStyleSheet(f"color: {color}; font-size: 10pt;")

        # Last operation from history
        if metadata.history:
            last_entry = metadata.history[-1]
            self._last_op_value.setText(last_entry.operation.capitalize())
        else:
            self._last_op_value.setText("None")

        # Last access time
        if metadata.last_read_time:
            self._last_access_value.setText(
                metadata.last_read_time.strftime("%H:%M:%S")
            )
        else:
            self._last_access_value.setText("Never")

        # History table
        self._update_history_table(metadata.history)

        # Hex dump
        self._hex_dump.set_data(metadata.data)

        # Flux quality
        self._quality_widget.set_metrics(metadata.flux_quality)

    def _display_basic_info(self, sector_num: int) -> None:
        """Display basic info for a sector without full metadata."""
        # Calculate geometry
        cylinder = sector_num // (18 * 2)
        head = (sector_num // 18) % 2
        sector_offset = sector_num % 18

        # Address section
        self._sector_value.setText(str(sector_num))
        self._chs_value.setText(f"{cylinder}/{head}/{sector_offset + 1}")
        self._lba_value.setText(str(sector_num))
        self._offset_value.setText(f"{sector_num * 512:,}")

        # Status section - default unscanned
        self._status_indicator.set_status(SectorStatus.UNSCANNED)
        self._status_text.setText("Unscanned")
        self._status_text.setStyleSheet("color: #858585; font-size: 10pt;")

        self._last_op_value.setText("None")
        self._last_access_value.setText("Never")

        # Clear history
        self._history_table.setRowCount(0)

        # Clear hex dump
        self._hex_dump.set_data(None)

        # Clear quality
        self._quality_widget.set_metrics(None)

    def _update_history_table(self, history: List[HistoryEntry]) -> None:
        """Update the history table with entries."""
        self._history_table.setRowCount(len(history))

        # Show most recent first
        for row, entry in enumerate(reversed(history)):
            # Time
            time_item = QTableWidgetItem(entry.format_time())
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._history_table.setItem(row, 0, time_item)

            # Operation
            op_item = QTableWidgetItem(entry.operation.capitalize())
            self._history_table.setItem(row, 1, op_item)

            # Result with color
            result_item = QTableWidgetItem(entry.result.capitalize())
            result_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if entry.result.lower() in ["success", "good", "ok"]:
                result_item.setForeground(QColor("#33cc33"))
            elif entry.result.lower() in ["error", "fail", "bad", "crc_error"]:
                result_item.setForeground(QColor("#cc3333"))
            else:
                result_item.setForeground(QColor("#cccc33"))

            self._history_table.setItem(row, 2, result_item)

    def clear_display(self) -> None:
        """Clear all displayed information."""
        self._current_sector = None

        # Address section
        self._sector_value.setText("---")
        self._chs_value.setText("---/---/---")
        self._lba_value.setText("---")
        self._offset_value.setText("---")

        # Status section
        self._status_indicator.set_status(SectorStatus.UNSCANNED)
        self._status_text.setText("---")
        self._status_text.setStyleSheet("color: #858585; font-size: 10pt;")
        self._last_op_value.setText("---")
        self._last_access_value.setText("---")

        # History
        self._history_table.setRowCount(0)

        # Hex dump
        self._hex_dump.set_data(None)

        # Quality
        self._quality_widget.set_metrics(None)

    def get_current_sector(self) -> Optional[int]:
        """Get the currently displayed sector number."""
        return self._current_sector

    def is_collapsed(self) -> bool:
        """Check if the panel is collapsed."""
        return self._is_collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        """Set the collapsed state."""
        if self._is_collapsed != collapsed:
            self._toggle_collapse()
