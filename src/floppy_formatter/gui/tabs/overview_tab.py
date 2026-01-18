"""
Overview tab for Analytics Dashboard.

Provides a summary view of disk health including:
- Disk health score gauge (0-100 with letter grade)
- Statistics cards (total, good, bad, recovered sectors)
- Bad sector trend chart
- Actionable recommendations list

Part of Phase 7: Analytics Dashboard
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QPainterPath,
    QFont,
    QFontMetrics,
    QPaintEvent,
)

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Colors
COLOR_BACKGROUND = QColor("#1e1e1e")
COLOR_CARD_BG = QColor("#252526")
COLOR_CARD_BORDER = QColor("#3a3d41")
COLOR_TEXT = QColor("#cccccc")
COLOR_TEXT_DIM = QColor("#808080")

COLOR_GOOD = QColor("#4ec9b0")  # Green
COLOR_WARNING = QColor("#dcdcaa")  # Yellow
COLOR_BAD = QColor("#f14c4c")  # Red
COLOR_RECOVERED = QColor("#569cd6")  # Blue

# Health score thresholds
HEALTH_EXCELLENT = 90  # A
HEALTH_GOOD = 80       # B
HEALTH_FAIR = 70       # C
HEALTH_POOR = 60       # D
# Below 60: F


# =============================================================================
# Data Classes
# =============================================================================

class RecommendationSeverity(Enum):
    """Severity levels for recommendations."""
    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()


@dataclass
class Recommendation:
    """
    Actionable recommendation for the user.

    Attributes:
        message: The recommendation text
        severity: Severity level
        action: Optional action identifier for follow-up
    """
    message: str
    severity: RecommendationSeverity = RecommendationSeverity.INFO
    action: str = ""

    def get_icon_color(self) -> QColor:
        """Get icon color based on severity."""
        colors = {
            RecommendationSeverity.INFO: COLOR_GOOD,
            RecommendationSeverity.WARNING: COLOR_WARNING,
            RecommendationSeverity.CRITICAL: COLOR_BAD,
        }
        return colors.get(self.severity, COLOR_TEXT)


@dataclass
class DiskStatistics:
    """
    Summary statistics for a disk.

    Attributes:
        total_sectors: Total number of sectors
        good_sectors: Number of readable sectors
        bad_sectors: Number of unreadable sectors
        recovered_sectors: Number of recovered sectors
        unscanned_sectors: Number of sectors not yet scanned
        health_score: Overall health score (0-100)
    """
    total_sectors: int = 2880
    good_sectors: int = 0
    bad_sectors: int = 0
    recovered_sectors: int = 0
    unscanned_sectors: int = 2880
    health_score: float = 0.0

    @property
    def scanned_sectors(self) -> int:
        """Number of sectors that have been scanned."""
        return self.good_sectors + self.bad_sectors

    @property
    def good_percentage(self) -> float:
        """Percentage of good sectors."""
        if self.scanned_sectors == 0:
            return 0.0
        return self.good_sectors / self.scanned_sectors * 100

    @property
    def bad_percentage(self) -> float:
        """Percentage of bad sectors."""
        if self.scanned_sectors == 0:
            return 0.0
        return self.bad_sectors / self.scanned_sectors * 100


@dataclass
class TrendPoint:
    """
    Single point in the bad sector trend chart.

    Attributes:
        timestamp: When the operation occurred
        operation_num: Sequential operation number
        bad_count: Number of bad sectors
        operation_type: Type of operation (scan, restore, etc.)
    """
    timestamp: datetime
    operation_num: int
    bad_count: int
    operation_type: str = "scan"


# =============================================================================
# Health Gauge Widget
# =============================================================================

class HealthGaugeWidget(QWidget):
    """
    Circular health gauge displaying 0-100 score with letter grade.

    Features:
    - Semi-circular gauge with gradient coloring
    - Large percentage display in center
    - Letter grade overlay (A/B/C/D/F)
    - Color transitions from red to green
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._score: float = 0.0
        self._animated_score: float = 0.0
        self._target_score: float = 0.0

        self.setMinimumSize(180, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Animation timer
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate_step)

    def set_score(self, score: float, animate: bool = True) -> None:
        """
        Set the health score.

        Args:
            score: Score value (0-100)
            animate: Whether to animate the change
        """
        self._target_score = max(0, min(100, score))

        if animate:
            self._animation_timer.start(16)  # ~60 FPS
        else:
            self._animated_score = self._target_score
            self._score = self._target_score
            self.update()

    def get_score(self) -> float:
        """Get the current score."""
        return self._score

    def get_letter_grade(self) -> str:
        """Get letter grade for current score."""
        if self._score >= HEALTH_EXCELLENT:
            return "A"
        elif self._score >= HEALTH_GOOD:
            return "B"
        elif self._score >= HEALTH_FAIR:
            return "C"
        elif self._score >= HEALTH_POOR:
            return "D"
        else:
            return "F"

    def _get_score_color(self, score: float) -> QColor:
        """Get color for a given score."""
        if score >= HEALTH_EXCELLENT:
            return COLOR_GOOD
        elif score >= HEALTH_GOOD:
            # Blend from good to warning
            ratio = (score - HEALTH_GOOD) / (HEALTH_EXCELLENT - HEALTH_GOOD)
            return self._blend_colors(COLOR_WARNING, COLOR_GOOD, ratio)
        elif score >= HEALTH_FAIR:
            return COLOR_WARNING
        elif score >= HEALTH_POOR:
            # Blend from warning to bad
            ratio = (score - HEALTH_POOR) / (HEALTH_FAIR - HEALTH_POOR)
            return self._blend_colors(COLOR_BAD, COLOR_WARNING, ratio)
        else:
            return COLOR_BAD

    def _blend_colors(self, c1: QColor, c2: QColor, ratio: float) -> QColor:
        """Blend two colors."""
        ratio = max(0, min(1, ratio))
        return QColor(
            int(c1.red() + (c2.red() - c1.red()) * ratio),
            int(c1.green() + (c2.green() - c1.green()) * ratio),
            int(c1.blue() + (c2.blue() - c1.blue()) * ratio),
        )

    def _animate_step(self) -> None:
        """Animation step."""
        diff = self._target_score - self._animated_score
        if abs(diff) < 0.5:
            self._animated_score = self._target_score
            self._animation_timer.stop()
        else:
            self._animated_score += diff * 0.1

        self._score = self._animated_score
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the gauge."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate dimensions
        width = self.width()
        height = self.height()
        size = min(width, height - 20)
        cx = width / 2
        cy = height / 2 + 10  # Offset down slightly

        radius = size / 2 - 10
        inner_radius = radius * 0.7

        # Draw background arc
        arc_rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        # Draw background track
        painter.setPen(QPen(COLOR_CARD_BORDER, 15, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(arc_rect, 225 * 16, -270 * 16)

        # Draw score arc
        score_color = self._get_score_color(self._score)
        painter.setPen(QPen(score_color, 15, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))

        # Arc spans from 225° (lower left) counter-clockwise
        # -270° is full arc, so we scale by score
        arc_span = int(-270 * self._score / 100)
        if arc_span != 0:
            painter.drawArc(arc_rect, 225 * 16, arc_span * 16)

        # Draw center circle
        center_rect = QRectF(
            cx - inner_radius, cy - inner_radius,
            inner_radius * 2, inner_radius * 2
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(COLOR_CARD_BG))
        painter.drawEllipse(center_rect)

        # Draw score text (number and % separately for better fit)
        font_score = QFont("Segoe UI", int(size / 5), QFont.Weight.Bold)
        font_pct = QFont("Segoe UI", int(size / 8), QFont.Weight.Bold)  # Smaller % sign

        score_num = f"{int(self._score)}"
        pct_sign = "%"

        fm_score = QFontMetrics(font_score)
        fm_pct = QFontMetrics(font_pct)

        num_width = fm_score.horizontalAdvance(score_num)
        pct_width = fm_pct.horizontalAdvance(pct_sign)
        total_width = num_width + pct_width

        painter.setPen(QPen(score_color))

        # Draw number
        painter.setFont(font_score)
        num_x = int(cx - total_width / 2)
        num_y = int(cy + fm_score.height() / 4)
        painter.drawText(num_x, num_y, score_num)

        # Draw % sign (smaller, aligned to baseline)
        painter.setFont(font_pct)
        pct_x = num_x + num_width
        painter.drawText(pct_x, num_y, pct_sign)

        # Draw letter grade
        font_grade = QFont("Segoe UI", int(size / 10))
        painter.setFont(font_grade)
        painter.setPen(QPen(COLOR_TEXT_DIM))

        grade = self.get_letter_grade()
        fm_grade = QFontMetrics(font_grade)
        grade_width = fm_grade.horizontalAdvance(grade)
        painter.drawText(int(cx - grade_width / 2), int(cy + fm_score.height() / 2 + 15), grade)

        # Draw title
        font_title = QFont("Segoe UI", 10)
        painter.setFont(font_title)
        painter.setPen(QPen(COLOR_TEXT))

        title = "Disk Health"
        fm_title = QFontMetrics(font_title)
        title_width = fm_title.horizontalAdvance(title)
        painter.drawText(int(cx - title_width / 2), 15, title)


# =============================================================================
# Statistics Card Widget
# =============================================================================

class StatisticsCard(QFrame):
    """
    Card widget displaying a single statistic.

    Shows an icon, value, label, and optional percentage.
    """

    def __init__(
        self,
        title: str,
        color: QColor,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self._title = title
        self._color = color
        self._value: int = 0
        self._percentage: Optional[float] = None

        self.setStyleSheet(f"""
            StatisticsCard {{
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 6px;
                border-left: 4px solid {color.name()};
            }}
        """)

        self.setMinimumSize(120, 80)
        self.setMaximumHeight(100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Title
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 11px;")
        layout.addWidget(self._title_label)

        # Value row
        value_layout = QHBoxLayout()
        value_layout.setSpacing(8)

        self._value_label = QLabel("0")
        self._value_label.setStyleSheet(f"""
            color: {color.name()};
            font-size: 24px;
            font-weight: bold;
        """)
        value_layout.addWidget(self._value_label)

        self._pct_label = QLabel("")
        self._pct_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 12px;")
        value_layout.addWidget(self._pct_label)

        value_layout.addStretch()
        layout.addLayout(value_layout)

    def set_value(self, value: int, percentage: Optional[float] = None) -> None:
        """Set the displayed value."""
        self._value = value
        self._percentage = percentage

        self._value_label.setText(f"{value:,}")

        if percentage is not None:
            self._pct_label.setText(f"({percentage:.1f}%)")
        else:
            self._pct_label.setText("")


# =============================================================================
# Trend Chart Widget
# =============================================================================

class TrendChartWidget(QWidget):
    """
    Line chart showing bad sector count trend over operations.

    Displays how the bad sector count has changed over time,
    helping users understand if their disk is degrading.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._data: List[TrendPoint] = []
        self._max_points = 20

        self.setMinimumSize(200, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def add_point(self, bad_count: int, operation_type: str = "scan") -> None:
        """Add a data point to the trend."""
        point = TrendPoint(
            timestamp=datetime.now(),
            operation_num=len(self._data) + 1,
            bad_count=bad_count,
            operation_type=operation_type,
        )
        self._data.append(point)

        # Keep only recent points
        if len(self._data) > self._max_points:
            self._data = self._data[-self._max_points:]

        self.update()

    def set_data(self, points: List[TrendPoint]) -> None:
        """Set all trend data."""
        self._data = points[-self._max_points:] if len(points) > self._max_points else list(points)
        self.update()

    def clear_data(self) -> None:
        """Clear all trend data."""
        self._data.clear()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the trend chart."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), COLOR_CARD_BG)

        margin_left = 40
        margin_right = 10
        margin_top = 25
        margin_bottom = 25

        plot_left = margin_left
        plot_right = self.width() - margin_right
        plot_top = margin_top
        plot_bottom = self.height() - margin_bottom
        plot_width = plot_right - plot_left
        plot_height = plot_bottom - plot_top

        # Draw title
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QPen(COLOR_TEXT))
        painter.drawText(margin_left, 15, "Bad Sector Trend")

        if not self._data:
            # Empty state
            painter.setPen(QPen(COLOR_TEXT_DIM))
            painter.setFont(QFont("Segoe UI", 9))
            text_x = int(plot_left + plot_width / 2 - 40)
            text_y = int(plot_top + plot_height / 2)
            painter.drawText(text_x, text_y, "No data yet")
            return

        # Calculate scale
        max_count = max(p.bad_count for p in self._data)
        max_count = max(10, max_count)  # Minimum scale

        # Draw grid
        painter.setPen(QPen(COLOR_CARD_BORDER, 1, Qt.PenStyle.DotLine))
        for i in range(5):
            y = plot_top + i * plot_height / 4
            painter.drawLine(int(plot_left), int(y), int(plot_right), int(y))

        # Draw axes
        painter.setPen(QPen(COLOR_TEXT_DIM, 1))
        painter.drawLine(
            int(plot_left), int(plot_bottom), int(plot_right), int(plot_bottom)
        )
        painter.drawLine(
            int(plot_left), int(plot_top), int(plot_left), int(plot_bottom)
        )

        # Y axis labels
        painter.setFont(QFont("Consolas", 8))
        for i in range(5):
            value = int(max_count * (4 - i) / 4)
            y = plot_top + i * plot_height / 4
            painter.drawText(5, int(y + 4), str(value))

        # Draw data line
        if len(self._data) >= 2:
            path = QPainterPath()
            n = len(self._data)

            for i, point in enumerate(self._data):
                x = plot_left + (i / (n - 1)) * plot_width if n > 1 else plot_left + plot_width / 2
                y = plot_bottom - (point.bad_count / max_count) * plot_height

                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            # Draw the line
            painter.setPen(QPen(COLOR_BAD, 2))
            painter.drawPath(path)

            # Draw points
            for i, point in enumerate(self._data):
                x = plot_left + (i / (n - 1)) * plot_width if n > 1 else plot_left + plot_width / 2
                y = plot_bottom - (point.bad_count / max_count) * plot_height

                painter.setBrush(QBrush(COLOR_BAD))
                painter.setPen(QPen(COLOR_CARD_BG, 2))
                painter.drawEllipse(QPointF(x, y), 4, 4)
        else:
            # Single point
            point = self._data[0]
            x = plot_left + plot_width / 2
            y = plot_bottom - (point.bad_count / max_count) * plot_height

            painter.setBrush(QBrush(COLOR_BAD))
            painter.setPen(QPen(COLOR_CARD_BG, 2))
            painter.drawEllipse(QPointF(x, y), 5, 5)

        # X axis label
        painter.setPen(QPen(COLOR_TEXT_DIM))
        painter.drawText(int(plot_right - 60), int(plot_bottom + 18), "Operations")


# =============================================================================
# Recommendations Widget
# =============================================================================

class RecommendationsWidget(QFrame):
    """
    List widget showing actionable recommendations.

    Each recommendation has an icon indicating severity and
    descriptive text suggesting what action to take.
    """

    recommendation_clicked = pyqtSignal(str)  # Emits action identifier

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setStyleSheet("""
            RecommendationsWidget {
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Title
        title = QLabel("Recommendations")
        title.setStyleSheet("color: #cccccc; font-size: 12px; font-weight: bold;")
        layout.addWidget(title)

        # List
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #3a3d41;
            }
            QListWidget::item:hover {
                background-color: #2d2d30;
            }
        """)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self._recommendations: List[Recommendation] = []

    def set_recommendations(self, recommendations: List[Recommendation]) -> None:
        """Set the list of recommendations."""
        self._recommendations = recommendations
        self._update_list()

    def add_recommendation(self, rec: Recommendation) -> None:
        """Add a single recommendation."""
        self._recommendations.append(rec)
        self._update_list()

    def clear_recommendations(self) -> None:
        """Clear all recommendations."""
        self._recommendations.clear()
        self._update_list()

    def _update_list(self) -> None:
        """Update the list widget."""
        self._list.clear()

        for rec in self._recommendations:
            item = QListWidgetItem()

            # Set icon based on severity
            icon_char = ""
            if rec.severity == RecommendationSeverity.INFO:
                icon_char = "\u2139"  # Info symbol
            elif rec.severity == RecommendationSeverity.WARNING:
                icon_char = "\u26A0"  # Warning triangle
            else:
                icon_char = "\u2718"  # X mark

            item.setText(f"{icon_char}  {rec.message}")
            item.setForeground(QBrush(rec.get_icon_color()))
            item.setData(Qt.ItemDataRole.UserRole, rec.action)

            self._list.addItem(item)

        if not self._recommendations:
            item = QListWidgetItem()
            item.setText("No recommendations at this time")
            item.setForeground(QBrush(COLOR_TEXT_DIM))
            self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle item click."""
        action = item.data(Qt.ItemDataRole.UserRole)
        if action:
            self.recommendation_clicked.emit(action)


# =============================================================================
# Overview Tab
# =============================================================================

class OverviewTab(QWidget):
    """
    Overview tab showing disk health summary.

    Contains:
    - Health gauge (0-100 score with letter grade)
    - Statistics cards (total, good, bad, recovered)
    - Bad sector trend chart
    - Actionable recommendations

    Signals:
        recommendation_action(str): Emitted when user clicks a recommendation
    """

    recommendation_action = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._statistics = DiskStatistics()
        self._trend_data: List[TrendPoint] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Left column: Health gauge + recommendations
        left_column = QVBoxLayout()
        left_column.setSpacing(8)

        # Health gauge
        self._health_gauge = HealthGaugeWidget()
        left_column.addWidget(self._health_gauge)

        # Recommendations
        self._recommendations = RecommendationsWidget()
        self._recommendations.recommendation_clicked.connect(self.recommendation_action)
        left_column.addWidget(self._recommendations, 1)

        layout.addLayout(left_column)

        # Right column: Stats cards + trend chart
        right_column = QVBoxLayout()
        right_column.setSpacing(8)

        # Statistics cards row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(8)

        self._total_card = StatisticsCard("Total Sectors", COLOR_TEXT)
        cards_layout.addWidget(self._total_card)

        self._good_card = StatisticsCard("Good", COLOR_GOOD)
        cards_layout.addWidget(self._good_card)

        self._bad_card = StatisticsCard("Bad", COLOR_BAD)
        cards_layout.addWidget(self._bad_card)

        self._recovered_card = StatisticsCard("Recovered", COLOR_RECOVERED)
        cards_layout.addWidget(self._recovered_card)

        right_column.addLayout(cards_layout)

        # Trend chart
        self._trend_chart = TrendChartWidget()
        right_column.addWidget(self._trend_chart, 1)

        layout.addLayout(right_column, 1)

    def update_overview(
        self,
        total_sectors: int = 2880,
        good_sectors: int = 0,
        bad_sectors: int = 0,
        recovered_sectors: int = 0,
        health_score: Optional[float] = None
    ) -> None:
        """
        Update overview with scan/recovery results.

        Args:
            total_sectors: Total number of sectors
            good_sectors: Number of good sectors
            bad_sectors: Number of bad sectors
            recovered_sectors: Number of recovered sectors
            health_score: Optional explicit health score (auto-calculated if None)
        """
        self._statistics = DiskStatistics(
            total_sectors=total_sectors,
            good_sectors=good_sectors,
            bad_sectors=bad_sectors,
            recovered_sectors=recovered_sectors,
            unscanned_sectors=total_sectors - good_sectors - bad_sectors,
        )

        # Calculate health score if not provided
        if health_score is None:
            scanned = good_sectors + bad_sectors
            if scanned > 0:
                health_score = (good_sectors / scanned) * 100
            else:
                health_score = 0.0

        self._statistics.health_score = health_score

        # Update UI
        self._health_gauge.set_score(health_score)
        self._total_card.set_value(total_sectors)
        has_scanned = self._statistics.scanned_sectors > 0
        good_pct = self._statistics.good_percentage if has_scanned else None
        bad_pct = self._statistics.bad_percentage if has_scanned else None
        self._good_card.set_value(good_sectors, good_pct)
        self._bad_card.set_value(bad_sectors, bad_pct)
        self._recovered_card.set_value(recovered_sectors)

        # Add trend point
        self._trend_chart.add_point(bad_sectors, "scan")

        # Generate recommendations
        self._update_recommendations()

    def clear_overview(self) -> None:
        """Clear all overview data."""
        self._statistics = DiskStatistics()
        self._health_gauge.set_score(0, animate=False)
        self._total_card.set_value(2880)
        self._good_card.set_value(0)
        self._bad_card.set_value(0)
        self._recovered_card.set_value(0)
        self._trend_chart.clear_data()
        self._recommendations.clear_recommendations()

    def add_trend_point(self, bad_count: int, operation_type: str = "scan") -> None:
        """Add a point to the trend chart."""
        self._trend_chart.add_point(bad_count, operation_type)

    def set_recommendations(self, recommendations: List[Recommendation]) -> None:
        """Set explicit recommendations."""
        self._recommendations.set_recommendations(recommendations)

    def _update_recommendations(self) -> None:
        """Generate recommendations based on current statistics."""
        recs = []

        bad_pct = self._statistics.bad_percentage

        if self._statistics.scanned_sectors == 0:
            recs.append(Recommendation(
                "Run a disk scan to assess disk health",
                RecommendationSeverity.INFO,
                "scan"
            ))
        elif bad_pct >= 10:
            recs.append(Recommendation(
                f"Critical: {bad_pct:.1f}% bad sectors - consider replacing disk",
                RecommendationSeverity.CRITICAL,
                "replace"
            ))
            recs.append(Recommendation(
                "Back up any recoverable data immediately",
                RecommendationSeverity.CRITICAL,
                "backup"
            ))
        elif bad_pct >= 5:
            recs.append(Recommendation(
                f"Warning: {bad_pct:.1f}% bad sectors detected",
                RecommendationSeverity.WARNING,
                ""
            ))
            recs.append(Recommendation(
                "Run restore operation to attempt recovery",
                RecommendationSeverity.WARNING,
                "restore"
            ))
        elif bad_pct >= 1:
            recs.append(Recommendation(
                f"{self._statistics.bad_sectors} marginal sectors detected",
                RecommendationSeverity.INFO,
                ""
            ))
            recs.append(Recommendation(
                "Consider running restore with multi-capture mode",
                RecommendationSeverity.INFO,
                "restore_multi"
            ))
        elif self._statistics.bad_sectors > 0:
            recs.append(Recommendation(
                f"Only {self._statistics.bad_sectors} bad sector(s) - disk is mostly healthy",
                RecommendationSeverity.INFO,
                ""
            ))
        else:
            recs.append(Recommendation(
                "Disk appears to be in good condition",
                RecommendationSeverity.INFO,
                ""
            ))

        # Check trend
        if len(self._trend_data) >= 3:
            recent = [p.bad_count for p in self._trend_data[-3:]]
            if all(recent[i] < recent[i + 1] for i in range(len(recent) - 1)):
                recs.insert(0, Recommendation(
                    "Bad sector count is increasing - disk may be degrading",
                    RecommendationSeverity.WARNING,
                    ""
                ))

        self._recommendations.set_recommendations(recs)

    def get_statistics(self) -> DiskStatistics:
        """Get current statistics."""
        return self._statistics


__all__ = [
    'OverviewTab',
    'HealthGaugeWidget',
    'StatisticsCard',
    'TrendChartWidget',
    'RecommendationsWidget',
    'DiskStatistics',
    'TrendPoint',
    'Recommendation',
    'RecommendationSeverity',
]
