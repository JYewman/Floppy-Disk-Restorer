"""
Errors tab for Analytics Dashboard.

Provides detailed error analysis including:
- Error heatmap (cylinder vs sector)
- Error type pie chart breakdown
- Error log table with filtering
- Pattern detection analysis

Part of Phase 7: Analytics Dashboard
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Tuple

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QPushButton,
    QFileDialog,
    QAbstractItemView,
    QSizePolicy,
    QTextEdit,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QFont,
    QPaintEvent,
    QMouseEvent,
)

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

COLOR_BACKGROUND = QColor("#1e1e1e")
COLOR_PANEL_BG = QColor("#252526")
COLOR_BORDER = QColor("#3a3d41")
COLOR_TEXT = QColor("#cccccc")
COLOR_TEXT_DIM = QColor("#808080")

# Error type colors
ERROR_COLORS = {
    "CRC": QColor("#f14c4c"),         # Red
    "Missing": QColor("#ff8c00"),      # Orange
    "Weak": QColor("#dcdcaa"),         # Yellow
    "No Address": QColor("#c586c0"),   # Purple
    "Header CRC": QColor("#ce9178"),   # Brown
    "Deleted": QColor("#569cd6"),      # Blue
    "Other": QColor("#808080"),        # Gray
}


# =============================================================================
# Data Classes
# =============================================================================

class ErrorType(Enum):
    """Types of sector errors."""
    CRC = "CRC"
    MISSING = "Missing"
    WEAK = "Weak"
    NO_ADDRESS = "No Address"
    HEADER_CRC = "Header CRC"
    DELETED = "Deleted"
    OTHER = "Other"


@dataclass
class SectorError:
    """
    Single sector error entry.

    Attributes:
        timestamp: When the error was detected
        cylinder: Cylinder number
        head: Head number
        sector: Sector number (1-based)
        error_type: Type of error
        details: Additional error details
        lba: Logical block address
    """
    timestamp: datetime
    cylinder: int
    head: int
    sector: int
    error_type: ErrorType
    details: str = ""
    lba: int = 0

    @classmethod
    def from_chs(cls, cyl: int, head: int, sector: int, error_type: ErrorType,
                 details: str = "", sectors_per_track: int = 18) -> 'SectorError':
        """Create error from CHS address."""
        lba = (cyl * 2 + head) * sectors_per_track + (sector - 1)
        return cls(
            timestamp=datetime.now(),
            cylinder=cyl,
            head=head,
            sector=sector,
            error_type=error_type,
            details=details,
            lba=lba,
        )


# =============================================================================
# Error Heatmap Widget
# =============================================================================

class ErrorHeatmapWidget(QWidget):
    """
    2D heatmap showing error distribution across cylinder and sector positions.

    X-axis: Sector position (0-17)
    Y-axis: Cylinder (0-79)
    Color intensity indicates error frequency.

    Signals:
        cell_clicked(int, int): Emitted when user clicks a cell (cylinder, sector)
    """

    cell_clicked = pyqtSignal(int, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._cylinders = 80
        self._sectors = 18
        self._head = -1  # -1 = both heads combined

        # Error counts: [cylinder][sector] -> count
        self._error_counts: Dict[Tuple[int, int], int] = {}
        self._max_count = 0

        self._hover_cell: Optional[Tuple[int, int]] = None

        self.setMinimumSize(200, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

    def set_errors(self, errors: List[SectorError], head: int = -1) -> None:
        """
        Set error data.

        Args:
            errors: List of sector errors
            head: Head to display (-1 for both)
        """
        self._head = head
        self._error_counts.clear()

        for error in errors:
            if head >= 0 and error.head != head:
                continue

            key = (error.cylinder, error.sector - 1)  # Convert to 0-based
            self._error_counts[key] = self._error_counts.get(key, 0) + 1

        self._max_count = max(self._error_counts.values()) if self._error_counts else 0
        self.update()

    def clear_errors(self) -> None:
        """Clear all error data."""
        self._error_counts.clear()
        self._max_count = 0
        self.update()

    def _cell_at_pos(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        """Get cell (cylinder, sector) at pixel position."""
        margin_left = 40
        margin_right = 10
        margin_top = 20
        margin_bottom = 30

        plot_left = margin_left
        plot_right = self.width() - margin_right
        plot_top = margin_top
        plot_bottom = self.height() - margin_bottom

        if not (plot_left <= x <= plot_right and plot_top <= y <= plot_bottom):
            return None

        cell_width = (plot_right - plot_left) / self._sectors
        cell_height = (plot_bottom - plot_top) / self._cylinders

        sector = int((x - plot_left) / cell_width)
        cylinder = int((y - plot_top) / cell_height)

        if 0 <= sector < self._sectors and 0 <= cylinder < self._cylinders:
            return (cylinder, sector)

        return None

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the heatmap."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), COLOR_PANEL_BG)

        margin_left = 40
        margin_right = 10
        margin_top = 20
        margin_bottom = 30

        plot_left = margin_left
        plot_right = self.width() - margin_right
        plot_top = margin_top
        plot_bottom = self.height() - margin_bottom
        plot_width = plot_right - plot_left
        plot_height = plot_bottom - plot_top

        cell_width = plot_width / self._sectors
        cell_height = plot_height / self._cylinders

        # Draw cells
        for cyl in range(self._cylinders):
            for sec in range(self._sectors):
                count = self._error_counts.get((cyl, sec), 0)

                x = plot_left + sec * cell_width
                y = plot_top + cyl * cell_height

                if count > 0:
                    # Color based on count
                    intensity = count / self._max_count if self._max_count > 0 else 0
                    color = self._get_heat_color(intensity)
                    painter.fillRect(QRectF(x, y, cell_width - 0.5, cell_height - 0.5), color)
                else:
                    # Empty cell
                    empty_rect = QRectF(x, y, cell_width - 0.5, cell_height - 0.5)
                    painter.fillRect(empty_rect, QColor("#2d2d30"))

        # Draw hover highlight
        if self._hover_cell:
            cyl, sec = self._hover_cell
            x = plot_left + sec * cell_width
            y = plot_top + cyl * cell_height
            painter.setPen(QPen(QColor("#007acc"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(x, y, cell_width - 0.5, cell_height - 0.5))

        # Draw border
        painter.setPen(QPen(COLOR_BORDER))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(plot_left, plot_top, plot_width, plot_height))

        # Draw axis labels
        painter.setPen(QPen(COLOR_TEXT_DIM))
        painter.setFont(QFont("Segoe UI", 9))

        # X axis (sectors)
        for sec in range(0, self._sectors, 3):
            x = plot_left + (sec + 0.5) * cell_width
            painter.drawText(int(x - 5), int(plot_bottom + 16), str(sec + 1))

        # Y axis (cylinders)
        for cyl in range(0, self._cylinders, 10):
            y = plot_top + (cyl + 0.5) * cell_height
            painter.drawText(8, int(y + 4), str(cyl))

        # Axis titles
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(int(plot_left + plot_width / 2 - 20), int(self.height() - 5), "Sector")

        painter.save()
        painter.translate(14, int(plot_top + plot_height / 2))
        painter.rotate(-90)
        painter.drawText(0, 0, "Cyl")
        painter.restore()

        # Title
        painter.setPen(QPen(COLOR_TEXT))
        painter.setFont(QFont("Segoe UI", 11))
        head_text = f"Head {self._head}" if self._head >= 0 else "Both Heads"
        painter.drawText(int(plot_left), 14, f"Error Heatmap ({head_text})")

    def _get_heat_color(self, intensity: float) -> QColor:
        """Get heatmap color for intensity (0-1)."""
        # Gradient from dark red to bright red
        r = int(80 + 175 * intensity)
        g = int(20 * (1 - intensity))
        b = int(20 * (1 - intensity))
        return QColor(r, g, b)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for hover effects."""
        cell = self._cell_at_pos(event.position().x(), event.position().y())

        if cell != self._hover_cell:
            self._hover_cell = cell
            self.update()

            if cell:
                cyl, sec = cell
                count = self._error_counts.get(cell, 0)
                self.setToolTip(f"C{cyl} S{sec + 1}\nErrors: {count}")
            else:
                self.setToolTip("")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse click."""
        if event.button() == Qt.MouseButton.LeftButton:
            cell = self._cell_at_pos(event.position().x(), event.position().y())
            if cell:
                self.cell_clicked.emit(cell[0], cell[1] + 1)  # Convert to 1-based sector

    def leaveEvent(self, event) -> None:
        """Handle mouse leave."""
        self._hover_cell = None
        self.update()


# =============================================================================
# Error Pie Chart Widget
# =============================================================================

class ErrorPieChartWidget(QWidget):
    """
    Pie chart showing error type breakdown.

    Displays the distribution of error types with a legend
    showing counts for each type.

    Signals:
        slice_clicked(str): Emitted when user clicks a slice (error type)
    """

    slice_clicked = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._error_counts: Dict[str, int] = {}
        self._total_errors = 0
        self._hover_slice: Optional[str] = None

        self.setMinimumSize(200, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

    def set_errors(self, errors: List[SectorError]) -> None:
        """Set error data."""
        self._error_counts.clear()

        for error in errors:
            error_type = error.error_type.value
            self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1

        self._total_errors = sum(self._error_counts.values())
        self.update()

    def clear_errors(self) -> None:
        """Clear error data."""
        self._error_counts.clear()
        self._total_errors = 0
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the pie chart."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), COLOR_PANEL_BG)

        if self._total_errors == 0:
            painter.setPen(QPen(COLOR_TEXT_DIM))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(int(self.width() / 2 - 40), int(self.height() / 2), "No errors")
            return

        # Calculate pie dimensions
        margin = 15
        legend_width = 120
        pie_size = min(self.width() - legend_width - margin * 2, self.height() - margin * 2)
        pie_size = max(60, pie_size)

        cx = margin + pie_size / 2
        cy = margin + pie_size / 2

        # Draw pie slices
        start_angle = 90 * 16  # Start from top
        radius = pie_size / 2

        sorted_types = sorted(self._error_counts.items(), key=lambda x: -x[1])

        self._slice_angles: Dict[str, Tuple[int, int]] = {}

        for error_type, count in sorted_types:
            span_angle = int(count / self._total_errors * 360 * 16)

            color = ERROR_COLORS.get(error_type, COLOR_TEXT_DIM)
            if self._hover_slice == error_type:
                color = color.lighter(130)

            painter.setBrush(QBrush(color))
            painter.setPen(QPen(COLOR_PANEL_BG, 1))

            rect = QRectF(cx - radius, cy - radius, pie_size, pie_size)
            painter.drawPie(rect, start_angle, span_angle)

            self._slice_angles[error_type] = (start_angle, span_angle)
            start_angle -= span_angle

        # Draw legend
        legend_x = cx + radius + 15
        legend_y = margin + 10

        painter.setFont(QFont("Segoe UI", 11))

        for i, (error_type, count) in enumerate(sorted_types):
            y = legend_y + i * 24

            # Color box
            color = ERROR_COLORS.get(error_type, COLOR_TEXT_DIM)
            painter.fillRect(QRectF(legend_x, y - 8, 14, 14), color)

            # Label
            pct = count / self._total_errors * 100
            painter.setPen(QPen(COLOR_TEXT))
            painter.drawText(int(legend_x + 20), int(y + 4), f"{error_type}: {count} ({pct:.0f}%)")

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for hover effects."""
        # Simplified hit testing - just update on move
        old_hover = self._hover_slice
        self._hover_slice = None  # Could implement proper hit testing

        if self._hover_slice != old_hover:
            self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse click."""
        # Could implement proper hit testing to emit slice_clicked
        pass


# =============================================================================
# Error Log Table Widget
# =============================================================================

class ErrorLogTable(QTableWidget):
    """
    Table showing error log with sortable columns.

    Columns: Time, Cylinder, Head, Sector, Type, Details
    """

    row_double_clicked = pyqtSignal(int, int, int)  # cylinder, head, sector

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._errors: List[SectorError] = []
        self._filter_type: Optional[str] = None

        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(["Time", "Cyl", "Head", "Sector", "Type", "Details"])

        self.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #cccccc;
                gridline-color: #3a3d41;
                border: none;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #264f78;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 6px;
                border: none;
                border-right: 1px solid #3a3d41;
                border-bottom: 1px solid #3a3d41;
            }
        """)

        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSortingEnabled(True)

        self.doubleClicked.connect(self._on_double_clicked)

    def set_errors(self, errors: List[SectorError]) -> None:
        """Set error list."""
        self._errors = list(errors)
        self._update_table()

    def add_error(self, error: SectorError) -> None:
        """Add a single error."""
        self._errors.append(error)
        self._update_table()

    def clear_errors(self) -> None:
        """Clear all errors."""
        self._errors.clear()
        self.setRowCount(0)

    def set_filter(self, error_type: Optional[str]) -> None:
        """Filter by error type."""
        self._filter_type = error_type
        self._update_table()

    def export_to_csv(self, file_path: str) -> bool:
        """Export errors to CSV file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # Header
                f.write("Time,Cylinder,Head,Sector,Type,Details\n")

                # Data
                for error in self._errors:
                    if self._filter_type and error.error_type.value != self._filter_type:
                        continue

                    line = (
                        f"{error.timestamp.isoformat()},"
                        f"{error.cylinder},{error.head},{error.sector},"
                        f"{error.error_type.value},\"{error.details}\"\n"
                    )
                    f.write(line)

            return True
        except Exception as e:
            logger.error("Failed to export errors: %s", e)
            return False

    def _update_table(self) -> None:
        """Update table contents."""
        self.setSortingEnabled(False)
        self.setRowCount(0)

        filtered = self._errors
        if self._filter_type:
            filtered = [e for e in self._errors if e.error_type.value == self._filter_type]

        self.setRowCount(len(filtered))

        for row, error in enumerate(filtered):
            # Time
            time_item = QTableWidgetItem(error.timestamp.strftime("%H:%M:%S"))
            self.setItem(row, 0, time_item)

            # Cylinder
            cyl_item = QTableWidgetItem(str(error.cylinder))
            cyl_item.setData(Qt.ItemDataRole.UserRole, error.cylinder)
            self.setItem(row, 1, cyl_item)

            # Head
            head_item = QTableWidgetItem(str(error.head))
            self.setItem(row, 2, head_item)

            # Sector
            sec_item = QTableWidgetItem(str(error.sector))
            self.setItem(row, 3, sec_item)

            # Type
            type_item = QTableWidgetItem(error.error_type.value)
            type_color = ERROR_COLORS.get(error.error_type.value, COLOR_TEXT)
            type_item.setForeground(QBrush(type_color))
            self.setItem(row, 4, type_item)

            # Details
            details_item = QTableWidgetItem(error.details)
            self.setItem(row, 5, details_item)

        self.setSortingEnabled(True)

    def _on_double_clicked(self, index) -> None:
        """Handle double-click on row."""
        row = index.row()
        if 0 <= row < len(self._errors):
            error = self._errors[row]
            self.row_double_clicked.emit(error.cylinder, error.head, error.sector)


# =============================================================================
# Pattern Detection Widget
# =============================================================================

class PatternDetectionWidget(QFrame):
    """
    Widget showing detected error patterns.

    Analyzes errors to identify patterns like:
    - Clustered errors on specific cylinders
    - Random distribution (media degradation)
    - Track-specific issues (head alignment)
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setObjectName("patternWidget")
        self.setStyleSheet(f"""
            QFrame#patternWidget {{
                background-color: {COLOR_PANEL_BG.name()};
                border: 1px solid {COLOR_BORDER.name()};
                border-radius: 6px;
            }}
            QFrame#patternWidget QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Pattern Detection")
        title.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-weight: bold; font-size: 13px; border: none;")
        layout.addWidget(title)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                color: {COLOR_TEXT.name()};
                border: none;
                font-size: 12px;
                line-height: 1.4;
            }}
        """)
        layout.addWidget(self._text)

    def analyze_errors(self, errors: List[SectorError]) -> None:
        """Analyze errors and display detected patterns."""
        if not errors:
            self._text.setText("No errors to analyze.")
            return

        analysis_lines = []

        # Group by cylinder
        by_cylinder: Dict[int, int] = {}
        for error in errors:
            by_cylinder[error.cylinder] = by_cylinder.get(error.cylinder, 0) + 1

        # Detect clusters
        if by_cylinder:
            cylinders = sorted(by_cylinder.keys())

            # Find consecutive cylinder ranges
            clusters = []
            start = cylinders[0]
            end = cylinders[0]

            for cyl in cylinders[1:]:
                if cyl == end + 1:
                    end = cyl
                else:
                    if end - start >= 2:
                        clusters.append((start, end))
                    start = cyl
                    end = cyl

            if end - start >= 2:
                clusters.append((start, end))

            # Report clusters
            if clusters:
                analysis_lines.append("CLUSTERED ERRORS DETECTED:")
                for start, end in clusters:
                    count = sum(by_cylinder.get(c, 0) for c in range(start, end + 1))
                    analysis_lines.append(f"  - Cylinders {start}-{end}: {count} errors")
                analysis_lines.append("")
                analysis_lines.append("Possible causes:")
                analysis_lines.append("  - Physical damage to disk surface")
                analysis_lines.append("  - Head alignment issues")
                analysis_lines.append("")

        # Check for random distribution
        if len(by_cylinder) > 5:
            # Calculate variance
            counts = list(by_cylinder.values())
            avg = sum(counts) / len(counts)
            variance = sum((c - avg) ** 2 for c in counts) / len(counts)

            if variance < avg * 2:  # Relatively uniform
                analysis_lines.append("RANDOM DISTRIBUTION DETECTED:")
                analysis_lines.append(f"  - Errors spread across {len(by_cylinder)} cylinders")
                analysis_lines.append("")
                analysis_lines.append("Possible causes:")
                analysis_lines.append("  - General media degradation")
                analysis_lines.append("  - Magnetic coating deterioration")
                analysis_lines.append("")

        # Check for head-specific issues
        head0_count = sum(1 for e in errors if e.head == 0)
        head1_count = sum(1 for e in errors if e.head == 1)

        if head0_count > 0 and head1_count > 0:
            ratio = max(head0_count, head1_count) / min(head0_count, head1_count)
            if ratio > 3:
                worse_head = 0 if head0_count > head1_count else 1
                analysis_lines.append("HEAD-SPECIFIC ISSUES:")
                analysis_lines.append(f"  - Head {worse_head} has {ratio:.1f}x more errors")
                analysis_lines.append("")
                analysis_lines.append("Possible causes:")
                analysis_lines.append(f"  - Head {worse_head} may be dirty or damaged")
                analysis_lines.append("  - Disk may have been written with misaligned drive")
                analysis_lines.append("")

        # Check for sector-specific issues
        by_sector: Dict[int, int] = {}
        for error in errors:
            by_sector[error.sector] = by_sector.get(error.sector, 0) + 1

        if by_sector:
            max_sector_errors = max(by_sector.values())
            avg_sector_errors = len(errors) / 18

            if max_sector_errors > avg_sector_errors * 3:
                worst_sectors = [s for s, c in by_sector.items() if c == max_sector_errors]
                analysis_lines.append("SECTOR-SPECIFIC ISSUES:")
                analysis_lines.append(f"  - Sector(s) {worst_sectors} have unusual error rates")
                analysis_lines.append("")

        # Summary
        if not analysis_lines:
            analysis_lines.append("No significant patterns detected.")
            analysis_lines.append("")
            analysis_lines.append(f"Total errors: {len(errors)}")
            analysis_lines.append(f"Affected cylinders: {len(by_cylinder)}")

        self._text.setText("\n".join(analysis_lines))

    def clear_analysis(self) -> None:
        """Clear analysis text."""
        self._text.setText("No errors to analyze.")


# =============================================================================
# Errors Tab
# =============================================================================

class ErrorsTab(QWidget):
    """
    Errors tab with heatmap, pie chart, log table, and pattern detection.

    Signals:
        sector_selected(int, int, int): Emitted when user selects an error (cyl, head, sector)
    """

    sector_selected = pyqtSignal(int, int, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._errors: List[SectorError] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(16)

        # === Top Section: Heatmap and Error Types side by side ===
        top_frame = QFrame()
        top_frame.setObjectName("errorsTopFrame")
        top_frame.setStyleSheet(f"""
            QFrame#errorsTopFrame {{
                background-color: {COLOR_PANEL_BG.name()};
                border: 1px solid {COLOR_BORDER.name()};
                border-radius: 6px;
            }}
            QFrame#errorsTopFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        top_frame.setMinimumHeight(220)
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(16, 12, 16, 12)
        top_layout.setSpacing(20)

        # Left side: Heatmap
        heatmap_container = QVBoxLayout()
        heatmap_container.setSpacing(8)

        # Head selector row
        head_row = QHBoxLayout()
        head_label = QLabel("Show:")
        head_label.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-size: 12px;")
        head_row.addWidget(head_label)

        self._head_combo = QComboBox()
        self._head_combo.addItems(["Both Heads", "Head 0", "Head 1"])
        self._head_combo.currentIndexChanged.connect(self._on_head_changed)
        self._head_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #3c3c3c;
                color: {COLOR_TEXT.name()};
                border: 1px solid {COLOR_BORDER.name()};
                padding: 6px 12px;
                font-size: 12px;
                min-width: 120px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
        """)
        head_row.addWidget(self._head_combo)
        head_row.addStretch()
        heatmap_container.addLayout(head_row)

        self._heatmap = ErrorHeatmapWidget()
        self._heatmap.setMinimumSize(300, 180)
        self._heatmap.cell_clicked.connect(self._on_cell_clicked)
        heatmap_container.addWidget(self._heatmap, 1)

        top_layout.addLayout(heatmap_container, 2)

        # Right side: Error Types (Pie Chart)
        pie_container = QVBoxLayout()
        pie_container.setSpacing(8)

        pie_title = QLabel("Error Types")
        pie_title.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-size: 13px; font-weight: bold;")
        pie_container.addWidget(pie_title)

        self._pie_chart = ErrorPieChartWidget()
        self._pie_chart.setMinimumSize(200, 160)
        pie_container.addWidget(self._pie_chart, 1)

        top_layout.addLayout(pie_container, 1)

        content_layout.addWidget(top_frame)

        # === Bottom Section: Error Log and Pattern Detection ===
        bottom_frame = QFrame()
        bottom_frame.setObjectName("errorsBottomFrame")
        bottom_frame.setStyleSheet(f"""
            QFrame#errorsBottomFrame {{
                background-color: {COLOR_PANEL_BG.name()};
                border: 1px solid {COLOR_BORDER.name()};
                border-radius: 6px;
            }}
            QFrame#errorsBottomFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(16, 12, 16, 12)
        bottom_layout.setSpacing(20)

        # Left side: Error Log Table
        table_container = QVBoxLayout()
        table_container.setSpacing(10)

        # Table toolbar
        table_toolbar = QHBoxLayout()
        table_toolbar.setSpacing(12)

        table_title = QLabel("Error Log")
        table_title.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-size: 13px; font-weight: bold;")
        table_toolbar.addWidget(table_title)
        table_toolbar.addStretch()

        # Filter dropdown
        self._filter_combo = QComboBox()
        self._filter_combo.addItem("All Types")
        for error_type in ErrorType:
            self._filter_combo.addItem(error_type.value)
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        self._filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #3c3c3c;
                color: {COLOR_TEXT.name()};
                border: 1px solid {COLOR_BORDER.name()};
                padding: 6px 12px;
                font-size: 12px;
                min-width: 100px;
            }}
        """)
        table_toolbar.addWidget(self._filter_combo)

        # Export button
        self._export_btn = QPushButton("Export CSV")
        self._export_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #3a3d41;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
        """)
        self._export_btn.clicked.connect(self._on_export_clicked)
        table_toolbar.addWidget(self._export_btn)

        table_container.addLayout(table_toolbar)

        self._error_table = ErrorLogTable()
        self._error_table.setMinimumHeight(180)
        self._error_table.row_double_clicked.connect(self._on_row_double_clicked)
        table_container.addWidget(self._error_table, 1)

        bottom_layout.addLayout(table_container, 2)

        # Right side: Pattern Detection
        pattern_container = QVBoxLayout()
        pattern_container.setSpacing(8)

        self._pattern_widget = PatternDetectionWidget()
        self._pattern_widget.setMinimumWidth(200)
        self._pattern_widget.setMinimumHeight(180)
        pattern_container.addWidget(self._pattern_widget, 1)

        bottom_layout.addLayout(pattern_container, 1)

        content_layout.addWidget(bottom_frame, 1)

        # Set content to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

    def update_errors(self, errors: List[SectorError]) -> None:
        """Update with new error list."""
        self._errors = list(errors)
        self._refresh_all()

    def add_error(self, error: SectorError) -> None:
        """Add a single error."""
        self._errors.append(error)
        self._refresh_all()

    def clear_errors(self) -> None:
        """Clear all errors."""
        self._errors.clear()
        self._heatmap.clear_errors()
        self._pie_chart.clear_errors()
        self._error_table.clear_errors()
        self._pattern_widget.clear_analysis()

    def _refresh_all(self) -> None:
        """Refresh all displays."""
        head = self._head_combo.currentIndex() - 1  # -1 = both
        self._heatmap.set_errors(self._errors, head)
        self._pie_chart.set_errors(self._errors)
        self._error_table.set_errors(self._errors)
        self._pattern_widget.analyze_errors(self._errors)

    def _on_head_changed(self, index: int) -> None:
        """Handle head selector change."""
        head = index - 1  # 0 = both, 1 = head 0, 2 = head 1
        self._heatmap.set_errors(self._errors, head)

    def _on_filter_changed(self, text: str) -> None:
        """Handle filter change."""
        if text == "All Types":
            self._error_table.set_filter(None)
        else:
            self._error_table.set_filter(text)

    def _on_cell_clicked(self, cylinder: int, sector: int) -> None:
        """Handle heatmap cell click."""
        # Find errors at this position
        for error in self._errors:
            if error.cylinder == cylinder and error.sector == sector:
                self.sector_selected.emit(cylinder, error.head, sector)
                break

    def _on_row_double_clicked(self, cylinder: int, head: int, sector: int) -> None:
        """Handle table row double-click."""
        self.sector_selected.emit(cylinder, head, sector)

    def _on_export_clicked(self) -> None:
        """Handle export button click."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Error Log",
            "error_log.csv",
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            if self._error_table.export_to_csv(file_path):
                logger.info("Exported errors to %s", file_path)
            else:
                logger.error("Failed to export errors")


__all__ = [
    'ErrorsTab',
    'SectorError',
    'ErrorType',
    'ErrorHeatmapWidget',
    'ErrorPieChartWidget',
    'ErrorLogTable',
    'PatternDetectionWidget',
]
