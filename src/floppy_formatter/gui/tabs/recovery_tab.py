"""
Recovery tab for Analytics Dashboard.

Provides recovery monitoring and analysis including:
- Real-time convergence line chart
- Pass-by-pass comparison table
- Recovered sectors timeline
- Recovery success prediction

Part of Phase 7: Analytics Dashboard
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
import math

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QGroupBox,
    QSizePolicy,
    QScrollArea,
    QProgressBar,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QPainterPath,
    QFont,
    QPaintEvent,
    QLinearGradient,
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

COLOR_LINE = QColor("#569cd6")  # Blue
COLOR_GOOD = QColor("#4ec9b0")  # Green
COLOR_WARNING = QColor("#dcdcaa")  # Yellow
COLOR_BAD = QColor("#f14c4c")  # Red
COLOR_RECOVERED = QColor("#569cd6")  # Blue
COLOR_GOAL = QColor("#4ec9b0")  # Green - target line


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PassStats:
    """
    Statistics for a single recovery pass.

    Attributes:
        pass_num: Pass number (1-based)
        bad_sectors: Number of bad sectors at end of pass
        recovered: Number of sectors recovered this pass
        failed: Number of sectors that failed recovery this pass
        delta: Change from previous pass (negative = improvement)
        duration_seconds: Duration of this pass
        technique: Recovery technique used
    """
    pass_num: int
    bad_sectors: int
    recovered: int = 0
    failed: int = 0
    delta: int = 0
    duration_seconds: float = 0.0
    technique: str = "standard"


@dataclass
class RecoveryStats:
    """
    Overall recovery statistics.

    Attributes:
        initial_bad_sectors: Count at start
        final_bad_sectors: Count at end
        sectors_recovered: Total sectors recovered
        passes_completed: Number of passes completed
        converged: Did recovery converge
        convergence_pass: Pass number where convergence occurred
        elapsed_time: Total time elapsed
        pass_history: List of per-pass statistics
    """
    initial_bad_sectors: int = 0
    final_bad_sectors: int = 0
    sectors_recovered: int = 0
    passes_completed: int = 0
    converged: bool = False
    convergence_pass: int = 0
    elapsed_time: float = 0.0
    pass_history: List[PassStats] = field(default_factory=list)


@dataclass
class RecoveredSector:
    """
    Record of a single recovered sector.

    Attributes:
        sector_num: Sector number (LBA)
        cylinder: Cylinder number
        head: Head number
        sector: Sector number (1-based)
        pass_num: Pass when recovered
        technique: Technique that recovered it
        timestamp: When recovered
    """
    sector_num: int
    cylinder: int
    head: int
    sector: int
    pass_num: int
    technique: str
    timestamp: datetime


# =============================================================================
# Convergence Chart Widget
# =============================================================================

class ConvergenceChartWidget(QWidget):
    """
    Line chart showing bad sector count over recovery passes.

    Features:
    - Real-time updates during recovery
    - Convergence point marker
    - Goal line at zero
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._data: List[int] = []  # Bad count at each pass
        self._convergence_pass: int = 0
        self._target_line = True

        self.setMinimumSize(200, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def add_convergence_point(self, pass_num: int, bad_count: int) -> None:
        """
        Add a data point to the convergence chart.

        Args:
            pass_num: Pass number (0 = initial scan baseline, 1+ = recovery passes)
            bad_count: Number of bad sectors at this point
        """
        # Ensure we have enough entries (pass_num is 0-based index)
        while len(self._data) <= pass_num:
            self._data.append(self._data[-1] if self._data else bad_count)

        # Set the value at the corresponding index
        self._data[pass_num] = bad_count

        self.update()

    def set_convergence_pass(self, pass_num: int) -> None:
        """Mark the convergence point."""
        self._convergence_pass = pass_num
        self.update()

    def clear_data(self) -> None:
        """Clear all data."""
        self._data.clear()
        self._convergence_pass = 0
        self.update()

    def set_data(self, bad_counts: List[int]) -> None:
        """Set all data at once."""
        self._data = list(bad_counts)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the chart."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), COLOR_PANEL_BG)

        margin_left = 50
        margin_right = 20
        margin_top = 30
        margin_bottom = 35

        plot_left = margin_left
        plot_right = self.width() - margin_right
        plot_top = margin_top
        plot_bottom = self.height() - margin_bottom
        plot_width = plot_right - plot_left
        plot_height = plot_bottom - plot_top

        # Title
        painter.setPen(QPen(COLOR_TEXT))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(margin_left, 18, "Recovery Convergence")

        if not self._data:
            painter.setPen(QPen(COLOR_TEXT_DIM))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(int(plot_left + plot_width / 2 - 40),
                           int(plot_top + plot_height / 2), "No data yet")
            return

        # Calculate scale
        max_count = max(max(self._data), 1)
        n_passes = len(self._data)

        # Draw grid
        painter.setPen(QPen(COLOR_BORDER, 1, Qt.PenStyle.DotLine))
        for i in range(5):
            y = plot_top + i * plot_height / 4
            painter.drawLine(int(plot_left), int(y), int(plot_right), int(y))

        # Draw goal line at 0
        if self._target_line:
            painter.setPen(QPen(COLOR_GOAL, 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(plot_left), int(plot_bottom),
                           int(plot_right), int(plot_bottom))

        # Draw axes
        painter.setPen(QPen(COLOR_TEXT_DIM, 1))
        painter.drawLine(int(plot_left), int(plot_bottom),
                        int(plot_right), int(plot_bottom))
        painter.drawLine(int(plot_left), int(plot_top),
                        int(plot_left), int(plot_bottom))

        # Y axis labels
        painter.setFont(QFont("Consolas", 8))
        for i in range(5):
            value = int(max_count * (4 - i) / 4)
            y = plot_top + i * plot_height / 4
            painter.drawText(5, int(y + 4), str(value))

        # X axis labels (pass 0 = initial/baseline, 1+ = recovery passes)
        step = max(1, n_passes // 10)
        for i in range(0, n_passes, step):
            x = plot_left + (i / (n_passes - 1)) * plot_width if n_passes > 1 else plot_left
            painter.drawText(int(x - 5), int(plot_bottom + 15), str(i))

        # Axis titles
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(int(plot_left + plot_width / 2 - 20),
                        int(self.height() - 5), "Pass")

        painter.save()
        painter.translate(12, int(plot_top + plot_height / 2))
        painter.rotate(-90)
        painter.drawText(0, 0, "Bad Sectors")
        painter.restore()

        # Draw data line
        if len(self._data) >= 2:
            path = QPainterPath()

            for i, count in enumerate(self._data):
                x = plot_left + (i / (n_passes - 1)) * plot_width if n_passes > 1 else plot_left
                y = plot_bottom - (count / max_count) * plot_height

                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            # Create gradient for line
            gradient = QLinearGradient(0, plot_top, 0, plot_bottom)
            gradient.setColorAt(0, COLOR_BAD)
            gradient.setColorAt(1, COLOR_GOOD)

            painter.setPen(QPen(QBrush(gradient), 2))
            painter.drawPath(path)

            # Draw points
            for i, count in enumerate(self._data):
                x = plot_left + (i / (n_passes - 1)) * plot_width if n_passes > 1 else plot_left
                y = plot_bottom - (count / max_count) * plot_height

                # Color based on position in gradient
                ratio = 1 - (count / max_count) if max_count > 0 else 0
                point_color = COLOR_GOOD if ratio > 0.7 else COLOR_WARNING if ratio > 0.3 else COLOR_BAD

                painter.setBrush(QBrush(point_color))
                painter.setPen(QPen(COLOR_PANEL_BG, 2))
                painter.drawEllipse(QPointF(x, y), 4, 4)

            # Mark convergence point (pass_num is the direct array index)
            if self._convergence_pass > 0 and self._convergence_pass < len(self._data):
                i = self._convergence_pass
                x = plot_left + (i / (n_passes - 1)) * plot_width if n_passes > 1 else plot_left
                y = plot_bottom - (self._data[i] / max_count) * plot_height

                # Draw marker
                painter.setPen(QPen(COLOR_GOOD, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(x, y), 8, 8)

                # Label
                painter.setFont(QFont("Consolas", 8))
                painter.setPen(QPen(COLOR_GOOD))
                painter.drawText(int(x + 10), int(y - 5), "Converged")

        else:
            # Single point
            count = self._data[0]
            x = plot_left + plot_width / 2
            y = plot_bottom - (count / max_count) * plot_height

            painter.setBrush(QBrush(COLOR_LINE))
            painter.setPen(QPen(COLOR_PANEL_BG, 2))
            painter.drawEllipse(QPointF(x, y), 5, 5)


# =============================================================================
# Pass Comparison Table
# =============================================================================

class PassComparisonTable(QTableWidget):
    """
    Table showing pass-by-pass comparison.

    Columns: Pass #, Bad Sectors, Recovered, Failed, Delta, Duration
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._pass_stats: List[PassStats] = []

        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(["Pass", "Bad", "Recovered", "Failed", "Delta", "Duration"])

        self.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #cccccc;
                gridline-color: #3a3d41;
                border: none;
                font-size: 7pt;
            }
            QTableWidget::item {
                padding: 1px 2px;
            }
            QTableWidget::item:selected {
                background-color: #264f78;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 2px;
                border: none;
                border-right: 1px solid #3a3d41;
                border-bottom: 1px solid #3a3d41;
                font-size: 7pt;
            }
        """)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(18)
        self.setMaximumHeight(120)

    def add_pass(self, stats: PassStats) -> None:
        """Add a pass to the table."""
        self._pass_stats.append(stats)
        self._update_table()

    def clear_passes(self) -> None:
        """Clear all passes."""
        self._pass_stats.clear()
        self.setRowCount(0)

    def set_passes(self, stats_list: List[PassStats]) -> None:
        """Set all pass stats."""
        self._pass_stats = list(stats_list)
        self._update_table()

    def _update_table(self) -> None:
        """Update table contents."""
        self.setRowCount(len(self._pass_stats) + 1)  # +1 for totals row

        total_recovered = 0
        total_failed = 0
        total_duration = 0.0

        for row, stats in enumerate(self._pass_stats):
            # Pass number
            pass_item = QTableWidgetItem(str(stats.pass_num))
            pass_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 0, pass_item)

            # Bad sectors
            bad_item = QTableWidgetItem(str(stats.bad_sectors))
            bad_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 1, bad_item)

            # Recovered
            rec_item = QTableWidgetItem(str(stats.recovered))
            rec_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if stats.recovered > 0:
                rec_item.setForeground(QBrush(COLOR_GOOD))
            self.setItem(row, 2, rec_item)

            # Failed
            fail_item = QTableWidgetItem(str(stats.failed))
            fail_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if stats.failed > 0:
                fail_item.setForeground(QBrush(COLOR_BAD))
            self.setItem(row, 3, fail_item)

            # Delta
            delta_item = QTableWidgetItem()
            delta_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if stats.delta < 0:
                delta_item.setText(f"\u2193 {abs(stats.delta)}")
                delta_item.setForeground(QBrush(COLOR_GOOD))
            elif stats.delta > 0:
                delta_item.setText(f"\u2191 {stats.delta}")
                delta_item.setForeground(QBrush(COLOR_BAD))
            else:
                delta_item.setText("\u2194 0")
                delta_item.setForeground(QBrush(COLOR_WARNING))
            self.setItem(row, 4, delta_item)

            # Duration
            duration_item = QTableWidgetItem(f"{stats.duration_seconds:.1f}s")
            duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 5, duration_item)

            total_recovered += stats.recovered
            total_failed += stats.failed
            total_duration += stats.duration_seconds

        # Totals row
        total_row = len(self._pass_stats)

        totals_label = QTableWidgetItem("Total")
        totals_label.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        totals_label.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.setItem(total_row, 0, totals_label)

        # Empty cell for bad
        self.setItem(total_row, 1, QTableWidgetItem(""))

        # Total recovered
        total_rec_item = QTableWidgetItem(str(total_recovered))
        total_rec_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        total_rec_item.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        total_rec_item.setForeground(QBrush(COLOR_GOOD))
        self.setItem(total_row, 2, total_rec_item)

        # Total failed
        total_fail_item = QTableWidgetItem(str(total_failed))
        total_fail_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        total_fail_item.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        if total_failed > 0:
            total_fail_item.setForeground(QBrush(COLOR_BAD))
        self.setItem(total_row, 3, total_fail_item)

        # Empty delta
        self.setItem(total_row, 4, QTableWidgetItem(""))

        # Total duration
        total_dur_item = QTableWidgetItem(f"{total_duration:.1f}s")
        total_dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        total_dur_item.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.setItem(total_row, 5, total_dur_item)


# =============================================================================
# Recovery Timeline Widget
# =============================================================================

class RecoveryTimelineWidget(QWidget):
    """
    Horizontal timeline showing recovered sectors.

    Color coded by recovery technique.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._recovered: List[RecoveredSector] = []
        self._max_sectors = 50  # Maximum displayed

        self.setMinimumHeight(40)
        self.setMaximumHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def add_recovered_sector(self, sector: RecoveredSector) -> None:
        """Add a recovered sector."""
        self._recovered.append(sector)
        if len(self._recovered) > self._max_sectors:
            self._recovered = self._recovered[-self._max_sectors:]
        self.update()

    def clear_timeline(self) -> None:
        """Clear the timeline."""
        self._recovered.clear()
        self.update()

    def set_recovered_sectors(self, sectors: List[RecoveredSector]) -> None:
        """Set all recovered sectors."""
        self._recovered = sectors[-self._max_sectors:] if len(sectors) > self._max_sectors else list(sectors)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the timeline."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), COLOR_PANEL_BG)

        margin_left = 6
        margin_right = 6
        margin_top = 14
        height = self.height() - margin_top - 6

        # Title
        painter.setPen(QPen(COLOR_TEXT))
        painter.setFont(QFont("Segoe UI", 7))
        painter.drawText(margin_left, 10, f"Recovered ({len(self._recovered)})")

        if not self._recovered:
            painter.setPen(QPen(COLOR_TEXT_DIM))
            painter.setFont(QFont("Segoe UI", 7))
            painter.drawText(margin_left, margin_top + height // 2 + 3, "No sectors recovered yet")
            return

        # Calculate item width
        available_width = self.width() - margin_left - margin_right
        n = len(self._recovered)
        item_width = min(12, available_width / n - 1)

        # Color by technique
        technique_colors = {
            "standard": COLOR_GOOD,
            "aggressive": COLOR_WARNING,
            "forensic": COLOR_RECOVERED,
        }

        for i, sector in enumerate(self._recovered):
            x = margin_left + i * (item_width + 1)
            y = margin_top

            color = technique_colors.get(sector.technique, COLOR_GOOD)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(120)))
            painter.drawRect(QRectF(x, y, item_width, height))

            # Tooltip on hover could be added
            self.setToolTip(f"Sector {sector.sector_num} (Pass {sector.pass_num}, {sector.technique})")


# =============================================================================
# Prediction Widget
# =============================================================================

class RecoveryPredictionWidget(QFrame):
    """
    Widget showing recovery prediction and progress.

    Displays:
    - Estimated passes remaining
    - Confidence percentage
    - Progress bar
    - Recommendations
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setStyleSheet(f"""
            RecoveryPredictionWidget {{
                background-color: {COLOR_PANEL_BG.name()};
                border: 1px solid {COLOR_BORDER.name()};
                border-radius: 3px;
            }}
            QLabel {{
                color: {COLOR_TEXT.name()};
                font-size: 8pt;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Title
        title = QLabel("Recovery Prediction")
        title.setStyleSheet("font-weight: bold; font-size: 8pt;")
        layout.addWidget(title)

        # Estimated passes
        self._passes_label = QLabel("Estimated passes remaining: --")
        self._passes_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 7pt;")
        layout.addWidget(self._passes_label)

        # Confidence
        self._confidence_label = QLabel("Confidence: --")
        self._confidence_label.setStyleSheet("font-size: 7pt;")
        layout.addWidget(self._confidence_label)

        # Progress
        self._progress = QProgressBar()
        self._progress.setStyleSheet("""
            QProgressBar {
                background-color: #3c3c3c;
                border: none;
                border-radius: 2px;
                height: 12px;
                text-align: center;
                color: white;
                font-size: 7pt;
            }
            QProgressBar::chunk {
                background-color: #4ec9b0;
                border-radius: 2px;
            }
        """)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setMaximumHeight(14)
        layout.addWidget(self._progress)

        # Recommendation (hidden by default to save space)
        self._rec_label = QLabel("")
        self._rec_label.setWordWrap(True)
        self._rec_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 7pt;")
        self._rec_label.setVisible(False)
        layout.addWidget(self._rec_label)

    def update_prediction(
        self,
        current_bad: int,
        initial_bad: int,
        pass_history: List[int],
        max_passes: int = 100
    ) -> None:
        """
        Update prediction based on recovery progress.

        Args:
            current_bad: Current bad sector count
            initial_bad: Initial bad sector count
            pass_history: List of bad counts per pass
            max_passes: Maximum allowed passes
        """
        if initial_bad == 0:
            self._passes_label.setText("No bad sectors to recover")
            self._confidence_label.setText("Confidence: N/A")
            self._progress.setValue(100)
            self._rec_label.setText("Disk is healthy!")
            return

        # Calculate progress
        recovered = initial_bad - current_bad
        progress = int(recovered / initial_bad * 100) if initial_bad > 0 else 0
        self._progress.setValue(progress)

        # Estimate remaining passes based on trend
        if len(pass_history) >= 3:
            # Calculate recovery rate
            recent = pass_history[-3:]
            if all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1)):
                # Still improving
                avg_recovery = (recent[0] - recent[-1]) / len(recent)
                if avg_recovery > 0:
                    est_passes = math.ceil(current_bad / avg_recovery)
                    confidence = min(90, 50 + len(pass_history) * 5)

                    self._passes_label.setText(f"Estimated {est_passes} more pass(es)")
                    self._confidence_label.setText(f"Confidence: {confidence}%")

                    if est_passes <= 3:
                        self._rec_label.setText("Recovery progressing well - continue current approach")
                    elif est_passes <= 10:
                        self._rec_label.setText("Consider switching to aggressive mode for faster recovery")
                    else:
                        self._rec_label.setText("Recovery may take a while - consider forensic mode")
                else:
                    # No improvement
                    self._passes_label.setText("Recovery has converged")
                    self._confidence_label.setText("Confidence: High")
                    self._rec_label.setText("Diminishing returns - consider stopping recovery")
            else:
                # Oscillating
                self._passes_label.setText("Unpredictable progress")
                self._confidence_label.setText("Confidence: Low")
                self._rec_label.setText("Recovery unstable - some sectors may be unrecoverable")
        elif len(pass_history) >= 1:
            # Not enough data yet
            self._passes_label.setText("Analyzing recovery trend...")
            self._confidence_label.setText("Confidence: --")
            self._rec_label.setText("Need more passes for accurate prediction")
        else:
            self._passes_label.setText("Starting recovery...")
            self._confidence_label.setText("Confidence: --")
            self._rec_label.setText("")

    def clear_prediction(self) -> None:
        """Clear prediction display."""
        self._passes_label.setText("Estimated passes remaining: --")
        self._confidence_label.setText("Confidence: --")
        self._progress.setValue(0)
        self._rec_label.setText("")


# =============================================================================
# Statistics Summary Widget
# =============================================================================

class RecoveryStatsWidget(QFrame):
    """
    Widget showing recovery statistics summary.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setStyleSheet(f"""
            RecoveryStatsWidget {{
                background-color: {COLOR_PANEL_BG.name()};
                border: 1px solid {COLOR_BORDER.name()};
                border-radius: 3px;
            }}
            QLabel {{
                color: {COLOR_TEXT.name()};
                font-size: 7pt;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)

        # Title
        title = QLabel("Statistics")
        title.setStyleSheet("font-weight: bold; font-size: 8pt;")
        layout.addWidget(title)

        # Stats labels - more compact
        self._total_recovered_label = QLabel("Total recovered: 0")
        layout.addWidget(self._total_recovered_label)

        self._recovery_rate_label = QLabel("Recovery rate: 0%")
        layout.addWidget(self._recovery_rate_label)

        self._avg_passes_label = QLabel("Avg passes/sector: --")
        layout.addWidget(self._avg_passes_label)

        self._technique_label = QLabel("Primary technique: --")
        layout.addWidget(self._technique_label)

    def update_stats(self, stats: RecoveryStats) -> None:
        """Update statistics display."""
        self._total_recovered_label.setText(f"Total recovered: {stats.sectors_recovered}")

        if stats.initial_bad_sectors > 0:
            rate = stats.sectors_recovered / stats.initial_bad_sectors * 100
            self._recovery_rate_label.setText(f"Recovery rate: {rate:.1f}%")
        else:
            self._recovery_rate_label.setText("Recovery rate: N/A")

        if stats.sectors_recovered > 0 and stats.passes_completed > 0:
            avg = stats.passes_completed / stats.sectors_recovered
            self._avg_passes_label.setText(f"Avg passes/sector: {avg:.1f}")
        else:
            self._avg_passes_label.setText("Avg passes/sector: --")

        # Determine primary technique
        if stats.pass_history:
            techniques = [p.technique for p in stats.pass_history]
            primary = max(set(techniques), key=techniques.count)
            self._technique_label.setText(f"Primary technique: {primary}")
        else:
            self._technique_label.setText("Primary technique: --")

    def clear_stats(self) -> None:
        """Clear statistics."""
        self._total_recovered_label.setText("Total recovered: 0")
        self._recovery_rate_label.setText("Recovery rate: 0%")
        self._avg_passes_label.setText("Avg passes/sector: --")
        self._technique_label.setText("Primary technique: --")


# =============================================================================
# Recovery Tab
# =============================================================================

class RecoveryTab(QWidget):
    """
    Recovery monitoring tab with convergence graph and pass comparison.

    Signals:
        None - this is primarily a display tab
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._stats = RecoveryStats()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Left column: convergence chart + timeline
        left_column = QVBoxLayout()
        left_column.setSpacing(4)

        # Convergence chart
        chart_frame = QFrame()
        chart_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PANEL_BG.name()};
                border: 1px solid {COLOR_BORDER.name()};
                border-radius: 4px;
            }}
        """)
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(4, 4, 4, 4)

        self._convergence_chart = ConvergenceChartWidget()
        chart_layout.addWidget(self._convergence_chart)

        left_column.addWidget(chart_frame, 2)

        # Recovery timeline
        self._timeline = RecoveryTimelineWidget()
        left_column.addWidget(self._timeline)

        layout.addLayout(left_column, 2)

        # Right column: table + prediction + stats
        right_column = QVBoxLayout()
        right_column.setSpacing(4)

        # Pass comparison table
        table_frame = QFrame()
        table_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PANEL_BG.name()};
                border: 1px solid {COLOR_BORDER.name()};
                border-radius: 4px;
            }}
        """)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(2, 2, 2, 2)
        table_layout.setSpacing(2)

        table_title = QLabel("Pass History")
        table_title.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-weight: bold; font-size: 8pt; padding: 2px;")
        table_layout.addWidget(table_title)

        self._pass_table = PassComparisonTable()
        table_layout.addWidget(self._pass_table)

        right_column.addWidget(table_frame, 2)

        # Prediction widget
        self._prediction = RecoveryPredictionWidget()
        self._prediction.setMaximumHeight(80)
        right_column.addWidget(self._prediction)

        # Stats widget
        self._stats_widget = RecoveryStatsWidget()
        self._stats_widget.setMaximumHeight(80)
        right_column.addWidget(self._stats_widget)

        layout.addLayout(right_column, 1)

    def update_recovery_progress(self, pass_num: int, stats: PassStats) -> None:
        """
        Update with progress from a recovery pass.

        Args:
            pass_num: Current pass number
            stats: Statistics for this pass
        """
        # Add to chart
        self._convergence_chart.add_convergence_point(pass_num, stats.bad_sectors)

        # Add to table
        self._pass_table.add_pass(stats)

        # Update prediction
        pass_history = [s.bad_sectors for s in self._stats.pass_history]
        pass_history.append(stats.bad_sectors)
        self._prediction.update_prediction(
            stats.bad_sectors,
            self._stats.initial_bad_sectors,
            pass_history
        )

        # Update internal stats
        self._stats.pass_history.append(stats)
        self._stats.passes_completed = pass_num
        self._stats.final_bad_sectors = stats.bad_sectors
        self._stats.sectors_recovered += stats.recovered

        self._stats_widget.update_stats(self._stats)

    def set_recovery_complete(self, final_stats: RecoveryStats) -> None:
        """Set recovery as complete with final statistics."""
        self._stats = final_stats

        # Update chart with convergence mark
        if final_stats.converged:
            self._convergence_chart.set_convergence_pass(final_stats.convergence_pass)

        # Update all displays
        self._pass_table.set_passes(final_stats.pass_history)
        self._stats_widget.update_stats(final_stats)

        # Final prediction
        self._prediction.update_prediction(
            final_stats.final_bad_sectors,
            final_stats.initial_bad_sectors,
            [s.bad_sectors for s in final_stats.pass_history]
        )

    def clear_recovery_data(self) -> None:
        """Clear all recovery data."""
        self._stats = RecoveryStats()
        self._convergence_chart.clear_data()
        self._pass_table.clear_passes()
        self._timeline.clear_timeline()
        self._prediction.clear_prediction()
        self._stats_widget.clear_stats()

    def add_convergence_point(self, pass_num: int, bad_count: int) -> None:
        """Add a single convergence point."""
        self._convergence_chart.add_convergence_point(pass_num, bad_count)

    def set_initial_bad_sectors(self, count: int) -> None:
        """Set the initial bad sector count for prediction."""
        self._stats.initial_bad_sectors = count

    def add_recovered_sector(self, sector: RecoveredSector) -> None:
        """Add a recovered sector to the timeline."""
        self._timeline.add_recovered_sector(sector)


__all__ = [
    'RecoveryTab',
    'PassStats',
    'RecoveryStats',
    'RecoveredSector',
    'ConvergenceChartWidget',
    'PassComparisonTable',
    'RecoveryTimelineWidget',
    'RecoveryPredictionWidget',
    'RecoveryStatsWidget',
]
