"""
Timing jitter visualization widget for Floppy Workbench.

Displays timing deviation as a scatter plot with:
- X-axis: Bit position within track
- Y-axis: Timing deviation from ideal in nanoseconds
- Color coding by deviation magnitude
- Trend line showing systematic drift
- Outlier highlighting
- Sector boundary markers

Part of Phase 8: Flux Visualization Widgets
"""

import math
import statistics
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QSizePolicy,
    QToolTip,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QPainterPath,
    QFont,
    QFontMetrics,
    QPaintEvent,
    QMouseEvent,
    QWheelEvent,
)

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Display colors
COLOR_BACKGROUND = QColor("#1e1e1e")
COLOR_GRID = QColor("#3a3d41")
COLOR_AXIS = QColor("#808080")
COLOR_POINT_GOOD = QColor("#4ec9b0")      # Green - within ±100ns
COLOR_POINT_MARGINAL = QColor("#dcdcaa")  # Yellow - ±100-300ns
COLOR_POINT_POOR = QColor("#f14c4c")      # Red - >±300ns
COLOR_TREND_LINE = QColor("#569cd6")      # Blue
COLOR_SECTOR_LINE = QColor("#3a3d41")     # Gray
COLOR_OUTLIER = QColor("#c586c0")         # Purple
COLOR_ZERO_LINE = QColor("#505050")       # Dark gray
COLOR_TEXT = QColor("#cccccc")

# Jitter thresholds (nanoseconds)
THRESHOLD_GOOD = 100.0
THRESHOLD_MARGINAL = 300.0

# Display settings
MARGIN_LEFT = 70
MARGIN_RIGHT = 20
MARGIN_TOP = 30
MARGIN_BOTTOM = 50
POINT_RADIUS = 2
OUTLIER_RADIUS = 4


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class JitterPoint:
    """
    Single timing jitter measurement.

    Attributes:
        bit_position: Position within track (0 to ~50,000 for HD)
        deviation_ns: Timing deviation in nanoseconds (can be negative)
        is_outlier: Whether this point is a statistical outlier
        sector_num: Which sector this point belongs to (optional)
    """
    bit_position: int
    deviation_ns: float
    is_outlier: bool = False
    sector_num: int = -1


@dataclass
class JitterStatistics:
    """
    Computed jitter statistics.

    Attributes:
        rms_ns: Root mean square jitter in nanoseconds
        peak_to_peak_ns: Peak-to-peak jitter (max - min)
        mean_deviation_ns: Mean deviation
        outlier_count: Number of statistical outliers
        drift_rate_ns_per_bit: Rate of timing drift
        std_deviation_ns: Standard deviation
        point_count: Total number of data points
    """
    rms_ns: float
    peak_to_peak_ns: float
    mean_deviation_ns: float
    outlier_count: int
    drift_rate_ns_per_bit: float
    std_deviation_ns: float = 0.0
    point_count: int = 0

    @property
    def drift_rate_ns_per_sector(self) -> float:
        """Drift rate in ns per sector (assuming ~2800 bits/sector)."""
        return self.drift_rate_ns_per_bit * 2800


@dataclass
class TrendLine:
    """
    Linear trend line parameters (y = slope * x + intercept).

    Attributes:
        slope: Slope (ns per bit)
        intercept: Y-intercept (ns)
        r_squared: Coefficient of determination
    """
    slope: float
    intercept: float
    r_squared: float = 0.0

    def evaluate(self, x: float) -> float:
        """Evaluate trend line at position x."""
        return self.slope * x + self.intercept


# =============================================================================
# Main Jitter Widget
# =============================================================================

class TimingJitterWidget(QWidget):
    """
    Timing jitter scatter plot visualization.

    Displays timing deviation vs bit position with:
    - Color-coded points by deviation magnitude
    - Linear regression trend line
    - Statistical outlier highlighting
    - Sector boundary markers
    - Zoom and pan support

    Signals:
        point_clicked(int, float): Emitted when point is clicked (bit_pos, deviation_ns)
        outlier_selected(int): Emitted when outlier is selected (bit_pos)
        region_selected(int, int): Emitted when region is selected (start_bit, end_bit)
    """

    point_clicked = pyqtSignal(int, float)
    outlier_selected = pyqtSignal(int)
    region_selected = pyqtSignal(int, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Widget settings
        self.setMinimumSize(400, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

        # Data
        self._points: List[JitterPoint] = []
        self._sector_boundaries: List[int] = []
        self._trend_line: Optional[TrendLine] = None
        self._statistics: Optional[JitterStatistics] = None

        # View state
        self._view_start_bit: int = 0
        self._view_end_bit: int = 50000
        self._y_range_ns: float = 500.0  # ±500ns default

        # Interaction state
        self._hover_point_idx: int = -1
        self._selected_region_start: Optional[int] = None
        self._is_selecting = False

        # Display settings
        self._show_trend_line = True
        self._show_sector_boundaries = True
        self._highlight_outliers = True
        self._outlier_threshold_sigma = 3.0

        # Fonts
        self._font_label = QFont("Consolas", 9)
        self._font_title = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self._font_small = QFont("Consolas", 8)

    # =========================================================================
    # Public API
    # =========================================================================

    def set_jitter_data(self, deviations: List[Tuple[int, float]]) -> None:
        """
        Set jitter data from bit position and deviation pairs.

        Args:
            deviations: List of (bit_position, deviation_ns) tuples
        """
        self._points.clear()

        if not deviations:
            self._trend_line = None
            self._statistics = None
            self.update()
            return

        # Create points
        for bit_pos, deviation in deviations:
            self._points.append(JitterPoint(
                bit_position=bit_pos,
                deviation_ns=deviation,
            ))

        # Calculate statistics and detect outliers
        self._calculate_statistics()
        self._detect_outliers()
        self._calculate_trend_line()

        # Set view range to fit data
        if self._points:
            self._view_start_bit = 0
            self._view_end_bit = max(p.bit_position for p in self._points)

            # Set Y range to fit data with margin
            max_dev = max(abs(p.deviation_ns) for p in self._points)
            self._y_range_ns = max(100.0, max_dev * 1.2)

        self.update()

    def set_sector_boundaries(self, boundaries: List[int]) -> None:
        """
        Set sector boundary positions.

        Args:
            boundaries: List of bit positions where sectors start
        """
        self._sector_boundaries = sorted(boundaries)
        self.update()

    def set_sector_count(self, num_sectors: int) -> None:
        """
        Set sector boundaries assuming equal spacing.

        Args:
            num_sectors: Number of sectors per track (e.g., 18 for HD)
        """
        if not self._points:
            return

        max_bit = max(p.bit_position for p in self._points)
        bits_per_sector = max_bit // num_sectors

        self._sector_boundaries = [i * bits_per_sector for i in range(num_sectors + 1)]
        self.update()

    def highlight_outliers(self, threshold_ns: float) -> None:
        """
        Highlight points exceeding threshold deviation.

        Args:
            threshold_ns: Deviation threshold in nanoseconds
        """
        for point in self._points:
            point.is_outlier = abs(point.deviation_ns) > threshold_ns
        self.update()

    def get_statistics(self) -> Optional[JitterStatistics]:
        """Get computed jitter statistics."""
        return self._statistics

    def get_trend_line(self) -> Optional[TrendLine]:
        """Get the computed trend line."""
        return self._trend_line

    def zoom_to_sector(self, sector_num: int) -> None:
        """
        Zoom to show specific sector.

        Args:
            sector_num: Sector number (0-based)
        """
        if sector_num < 0 or sector_num >= len(self._sector_boundaries) - 1:
            return

        self._view_start_bit = self._sector_boundaries[sector_num]
        self._view_end_bit = self._sector_boundaries[sector_num + 1]
        self.update()

    def zoom_to_fit(self) -> None:
        """Zoom to show all data."""
        if not self._points:
            return

        self._view_start_bit = 0
        self._view_end_bit = max(p.bit_position for p in self._points)

        max_dev = max(abs(p.deviation_ns) for p in self._points) if self._points else 500
        self._y_range_ns = max(100.0, max_dev * 1.2)

        self.update()

    def set_y_range(self, range_ns: float) -> None:
        """
        Set Y-axis range.

        Args:
            range_ns: Range in nanoseconds (displays ±range_ns)
        """
        self._y_range_ns = max(50.0, range_ns)
        self.update()

    def set_show_trend_line(self, show: bool) -> None:
        """Enable or disable trend line display."""
        self._show_trend_line = show
        self.update()

    def set_show_sector_boundaries(self, show: bool) -> None:
        """Enable or disable sector boundary markers."""
        self._show_sector_boundaries = show
        self.update()

    def clear(self) -> None:
        """Clear all jitter data."""
        self._points.clear()
        self._sector_boundaries.clear()
        self._trend_line = None
        self._statistics = None
        self._view_start_bit = 0
        self._view_end_bit = 50000
        self._y_range_ns = 500.0
        self.update()

    # =========================================================================
    # Internal Calculations
    # =========================================================================

    def _calculate_statistics(self) -> None:
        """Calculate jitter statistics from data points."""
        if not self._points:
            self._statistics = None
            return

        deviations = [p.deviation_ns for p in self._points]

        # RMS
        rms = math.sqrt(sum(d * d for d in deviations) / len(deviations))

        # Peak-to-peak
        p2p = max(deviations) - min(deviations)

        # Mean
        mean_dev = statistics.mean(deviations)

        # Standard deviation
        std_dev = statistics.stdev(deviations) if len(deviations) > 1 else 0.0

        # Outlier count (will be updated after detection)
        outlier_count = 0

        # Drift rate (from trend line, calculated later)
        drift_rate = 0.0

        self._statistics = JitterStatistics(
            rms_ns=rms,
            peak_to_peak_ns=p2p,
            mean_deviation_ns=mean_dev,
            outlier_count=outlier_count,
            drift_rate_ns_per_bit=drift_rate,
            std_deviation_ns=std_dev,
            point_count=len(deviations),
        )

    def _detect_outliers(self) -> None:
        """Detect statistical outliers using sigma threshold."""
        if not self._points or not self._statistics:
            return

        mean = self._statistics.mean_deviation_ns
        std = self._statistics.std_deviation_ns

        if std == 0:
            return

        threshold = self._outlier_threshold_sigma * std
        outlier_count = 0

        for point in self._points:
            if abs(point.deviation_ns - mean) > threshold:
                point.is_outlier = True
                outlier_count += 1
            else:
                point.is_outlier = False

        # Update statistics
        if self._statistics:
            self._statistics.outlier_count = outlier_count

    def _calculate_trend_line(self) -> None:
        """Calculate linear regression trend line."""
        if len(self._points) < 2:
            self._trend_line = None
            return

        # Linear regression using least squares
        n = len(self._points)
        sum_x = sum(p.bit_position for p in self._points)
        sum_y = sum(p.deviation_ns for p in self._points)
        sum_xy = sum(p.bit_position * p.deviation_ns for p in self._points)
        sum_xx = sum(p.bit_position * p.bit_position for p in self._points)

        denominator = n * sum_xx - sum_x * sum_x

        if abs(denominator) < 1e-10:
            self._trend_line = None
            return

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n

        # Calculate R-squared
        mean_y = sum_y / n
        ss_tot = sum((p.deviation_ns - mean_y) ** 2 for p in self._points)
        ss_res = sum((p.deviation_ns - (slope * p.bit_position + intercept)) ** 2 for p in self._points)

        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        self._trend_line = TrendLine(
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
        )

        # Update drift rate in statistics
        if self._statistics:
            self._statistics.drift_rate_ns_per_bit = slope

    # =========================================================================
    # Coordinate Conversion
    # =========================================================================

    def _bit_to_x(self, bit_pos: int) -> float:
        """Convert bit position to X pixel coordinate."""
        plot_left = MARGIN_LEFT
        plot_width = self.width() - MARGIN_LEFT - MARGIN_RIGHT

        bit_range = self._view_end_bit - self._view_start_bit
        if bit_range == 0:
            return plot_left

        return plot_left + (bit_pos - self._view_start_bit) / bit_range * plot_width

    def _x_to_bit(self, x: float) -> int:
        """Convert X pixel coordinate to bit position."""
        plot_left = MARGIN_LEFT
        plot_width = self.width() - MARGIN_LEFT - MARGIN_RIGHT

        if plot_width == 0:
            return self._view_start_bit

        bit_range = self._view_end_bit - self._view_start_bit
        return int(self._view_start_bit + (x - plot_left) / plot_width * bit_range)

    def _ns_to_y(self, deviation_ns: float) -> float:
        """Convert deviation (ns) to Y pixel coordinate."""
        plot_top = MARGIN_TOP
        plot_height = self.height() - MARGIN_TOP - MARGIN_BOTTOM
        plot_center = plot_top + plot_height / 2

        # Map [-y_range, +y_range] to [bottom, top]
        normalized = deviation_ns / self._y_range_ns
        return plot_center - normalized * (plot_height / 2)

    def _y_to_ns(self, y: float) -> float:
        """Convert Y pixel coordinate to deviation (ns)."""
        plot_top = MARGIN_TOP
        plot_height = self.height() - MARGIN_TOP - MARGIN_BOTTOM
        plot_center = plot_top + plot_height / 2

        normalized = (plot_center - y) / (plot_height / 2)
        return normalized * self._y_range_ns

    def _get_point_color(self, point: JitterPoint) -> QColor:
        """Get color for a jitter point based on deviation."""
        if point.is_outlier and self._highlight_outliers:
            return COLOR_OUTLIER

        abs_dev = abs(point.deviation_ns)

        if abs_dev <= THRESHOLD_GOOD:
            return COLOR_POINT_GOOD
        elif abs_dev <= THRESHOLD_MARGINAL:
            return COLOR_POINT_MARGINAL
        else:
            return COLOR_POINT_POOR

    # =========================================================================
    # Paint Event
    # =========================================================================

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the jitter scatter plot."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), COLOR_BACKGROUND)

        if not self._points:
            self._draw_empty_state(painter)
            return

        # Draw components
        self._draw_grid(painter)
        self._draw_sector_boundaries(painter)
        self._draw_zero_line(painter)
        self._draw_trend_line(painter)
        self._draw_points(painter)
        self._draw_axes(painter)
        self._draw_statistics(painter)

    def _draw_empty_state(self, painter: QPainter) -> None:
        """Draw empty state message."""
        painter.setFont(self._font_title)
        painter.setPen(QPen(COLOR_AXIS))

        text = "No jitter data loaded"
        fm = QFontMetrics(self._font_title)
        text_rect = fm.boundingRect(text)

        x = (self.width() - text_rect.width()) / 2
        y = (self.height() + text_rect.height()) / 2

        painter.drawText(int(x), int(y), text)

    def _draw_grid(self, painter: QPainter) -> None:
        """Draw background grid."""
        pen = QPen(COLOR_GRID, 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)

        plot_left = MARGIN_LEFT
        plot_right = self.width() - MARGIN_RIGHT
        plot_top = MARGIN_TOP
        plot_bottom = self.height() - MARGIN_BOTTOM

        # Horizontal grid lines
        y_steps = [-400, -200, 0, 200, 400]
        for ns in y_steps:
            if abs(ns) <= self._y_range_ns:
                y = self._ns_to_y(ns)
                painter.drawLine(int(plot_left), int(y), int(plot_right), int(y))

        # Vertical grid lines (5 divisions)
        bit_range = self._view_end_bit - self._view_start_bit
        for i in range(1, 5):
            bit_pos = self._view_start_bit + i * bit_range // 5
            x = self._bit_to_x(bit_pos)
            painter.drawLine(int(x), int(plot_top), int(x), int(plot_bottom))

    def _draw_sector_boundaries(self, painter: QPainter) -> None:
        """Draw sector boundary markers."""
        if not self._show_sector_boundaries or not self._sector_boundaries:
            return

        plot_top = MARGIN_TOP
        plot_bottom = self.height() - MARGIN_BOTTOM

        pen = QPen(COLOR_SECTOR_LINE, 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setFont(self._font_small)

        for i, boundary in enumerate(self._sector_boundaries):
            if self._view_start_bit <= boundary <= self._view_end_bit:
                x = self._bit_to_x(boundary)
                painter.drawLine(int(x), int(plot_top), int(x), int(plot_bottom))

                # Draw sector number label
                if i < len(self._sector_boundaries) - 1:
                    painter.setPen(QPen(COLOR_TEXT))
                    painter.drawText(int(x + 2), int(plot_top + 12), f"S{i}")
                    painter.setPen(pen)

    def _draw_zero_line(self, painter: QPainter) -> None:
        """Draw the zero deviation reference line."""
        plot_left = MARGIN_LEFT
        plot_right = self.width() - MARGIN_RIGHT

        pen = QPen(COLOR_ZERO_LINE, 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        y = self._ns_to_y(0)
        painter.drawLine(int(plot_left), int(y), int(plot_right), int(y))

    def _draw_trend_line(self, painter: QPainter) -> None:
        """Draw the linear regression trend line."""
        if not self._show_trend_line or not self._trend_line:
            return

        plot_left = MARGIN_LEFT
        plot_right = self.width() - MARGIN_RIGHT

        pen = QPen(COLOR_TREND_LINE, 2)
        painter.setPen(pen)

        # Draw line from view start to view end
        y1 = self._ns_to_y(self._trend_line.evaluate(self._view_start_bit))
        y2 = self._ns_to_y(self._trend_line.evaluate(self._view_end_bit))

        # Clip to plot area
        plot_top = MARGIN_TOP
        plot_bottom = self.height() - MARGIN_BOTTOM

        painter.drawLine(int(plot_left), int(max(plot_top, min(plot_bottom, y1))),
                        int(plot_right), int(max(plot_top, min(plot_bottom, y2))))

    def _draw_points(self, painter: QPainter) -> None:
        """Draw scatter plot points."""
        plot_left = MARGIN_LEFT
        plot_right = self.width() - MARGIN_RIGHT
        plot_top = MARGIN_TOP
        plot_bottom = self.height() - MARGIN_BOTTOM

        for i, point in enumerate(self._points):
            # Skip points outside view
            if point.bit_position < self._view_start_bit or point.bit_position > self._view_end_bit:
                continue

            x = self._bit_to_x(point.bit_position)
            y = self._ns_to_y(point.deviation_ns)

            # Skip if outside plot area
            if y < plot_top or y > plot_bottom:
                continue

            # Get color
            color = self._get_point_color(point)

            # Determine radius (larger for outliers and hover)
            radius = OUTLIER_RADIUS if point.is_outlier else POINT_RADIUS
            if i == self._hover_point_idx:
                radius += 2

            # Draw point
            painter.setPen(QPen(color.darker(120), 1))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(x, y), radius, radius)

    def _draw_axes(self, painter: QPainter) -> None:
        """Draw axes and labels."""
        pen = QPen(COLOR_AXIS, 1)
        painter.setPen(pen)
        painter.setFont(self._font_label)

        plot_left = MARGIN_LEFT
        plot_right = self.width() - MARGIN_RIGHT
        plot_top = MARGIN_TOP
        plot_bottom = self.height() - MARGIN_BOTTOM

        # X axis
        painter.drawLine(int(plot_left), int(plot_bottom),
                        int(plot_right), int(plot_bottom))

        # Y axis
        painter.drawLine(int(plot_left), int(plot_top),
                        int(plot_left), int(plot_bottom))

        # X axis labels
        bit_range = self._view_end_bit - self._view_start_bit
        for i in range(5):
            bit_pos = self._view_start_bit + i * bit_range // 4
            x = self._bit_to_x(bit_pos)

            if bit_pos >= 1000:
                label = f"{bit_pos // 1000}k"
            else:
                label = str(bit_pos)

            painter.drawText(int(x - 15), int(plot_bottom + 15), label)

        # X axis title
        painter.drawText(int((plot_left + plot_right) / 2 - 30),
                        int(self.height() - 5), "Bit Position")

        # Y axis labels
        for ns in [-400, -200, 0, 200, 400]:
            if abs(ns) <= self._y_range_ns:
                y = self._ns_to_y(ns)
                label = f"{ns:+d}" if ns != 0 else "0"
                painter.drawText(int(plot_left - 45), int(y + 5), label)

        # Y axis title (rotated)
        painter.save()
        painter.translate(15, (plot_top + plot_bottom) / 2)
        painter.rotate(-90)
        painter.drawText(0, 0, "Deviation (ns)")
        painter.restore()

    def _draw_statistics(self, painter: QPainter) -> None:
        """Draw statistics panel."""
        if not self._statistics:
            return

        painter.setFont(self._font_small)
        painter.setPen(QPen(COLOR_TEXT))

        x = self.width() - MARGIN_RIGHT - 120
        y = MARGIN_TOP + 15

        # RMS with color
        rms = self._statistics.rms_ns
        rms_color = COLOR_POINT_GOOD if rms < 100 else \
                   COLOR_POINT_MARGINAL if rms < 300 else COLOR_POINT_POOR

        painter.setPen(QPen(rms_color))
        painter.drawText(int(x), int(y), f"RMS: {rms:.1f} ns")

        painter.setPen(QPen(COLOR_TEXT))
        painter.drawText(int(x), int(y + 15), f"P-P: {self._statistics.peak_to_peak_ns:.1f} ns")
        painter.drawText(int(x), int(y + 30), f"Mean: {self._statistics.mean_deviation_ns:+.1f} ns")
        painter.drawText(int(x), int(y + 45), f"Outliers: {self._statistics.outlier_count}")

        if self._trend_line:
            drift_per_sector = self._statistics.drift_rate_ns_per_sector
            painter.drawText(int(x), int(y + 60), f"Drift: {drift_per_sector:+.1f} ns/sector")

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for hover effects."""
        pos = event.position()
        bit_pos = self._x_to_bit(pos.x())
        dev_ns = self._y_to_ns(pos.y())

        # Find nearest point
        old_hover = self._hover_point_idx
        self._hover_point_idx = -1
        min_dist = float('inf')

        for i, point in enumerate(self._points):
            if abs(point.bit_position - bit_pos) > (self._view_end_bit - self._view_start_bit) / 50:
                continue

            x = self._bit_to_x(point.bit_position)
            y = self._ns_to_y(point.deviation_ns)
            dist = math.sqrt((pos.x() - x) ** 2 + (pos.y() - y) ** 2)

            if dist < min_dist and dist < 15:
                min_dist = dist
                self._hover_point_idx = i

        if self._hover_point_idx != old_hover:
            self.update()

        # Show tooltip
        if self._hover_point_idx >= 0:
            point = self._points[self._hover_point_idx]
            sector_str = f"Sector {point.sector_num}" if point.sector_num >= 0 else "Unknown sector"

            tip = (f"Bit: {point.bit_position:,}\n"
                   f"Deviation: {point.deviation_ns:+.1f} ns\n"
                   f"{sector_str}")

            if point.is_outlier:
                tip += "\n[OUTLIER]"

            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
        else:
            self.setToolTip("")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._hover_point_idx >= 0:
                point = self._points[self._hover_point_idx]
                self.point_clicked.emit(point.bit_position, point.deviation_ns)

                if point.is_outlier:
                    self.outlier_selected.emit(point.bit_position)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for Y-axis zoom."""
        delta = event.angleDelta().y()

        if delta > 0:
            self._y_range_ns = max(50.0, self._y_range_ns * 0.8)
        else:
            self._y_range_ns = min(2000.0, self._y_range_ns * 1.25)

        self.update()
        event.accept()

    def leaveEvent(self, event) -> None:
        """Handle mouse leave."""
        self._hover_point_idx = -1
        self.update()


# =============================================================================
# Jitter Panel with Statistics Bar
# =============================================================================

class TimingJitterPanel(QWidget):
    """
    Timing jitter widget with statistics bar.

    Combines the scatter plot with a statistics display bar.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Jitter widget
        self._jitter = TimingJitterWidget()
        layout.addWidget(self._jitter, 1)

        # Statistics bar
        stats_bar = QFrame()
        stats_bar.setStyleSheet("""
            QFrame {
                background-color: #2d2d30;
                border-top: 1px solid #3a3d41;
            }
            QLabel {
                color: #cccccc;
                padding: 2px 4px;
            }
        """)
        stats_layout = QHBoxLayout(stats_bar)
        stats_layout.setContentsMargins(8, 4, 8, 4)
        stats_layout.setSpacing(16)

        self._points_label = QLabel("Points: --")
        stats_layout.addWidget(self._points_label)

        self._rms_label = QLabel("RMS: --")
        stats_layout.addWidget(self._rms_label)

        self._p2p_label = QLabel("P-P: --")
        stats_layout.addWidget(self._p2p_label)

        self._outliers_label = QLabel("Outliers: --")
        self._outliers_label.setStyleSheet("color: #c586c0;")
        stats_layout.addWidget(self._outliers_label)

        stats_layout.addStretch()

        self._drift_label = QLabel("Drift: --")
        stats_layout.addWidget(self._drift_label)

        layout.addWidget(stats_bar)

        # Connect for updates
        # Note: Would need to add a signal to TimingJitterWidget for data changes
        # For now, update stats when setting data

    def get_jitter_widget(self) -> TimingJitterWidget:
        """Get the jitter widget."""
        return self._jitter

    def set_jitter_data(self, deviations: List[Tuple[int, float]]) -> None:
        """Set jitter data and update statistics display."""
        self._jitter.set_jitter_data(deviations)
        self._update_stats()

    def set_sector_boundaries(self, boundaries: List[int]) -> None:
        """Set sector boundaries."""
        self._jitter.set_sector_boundaries(boundaries)

    def clear(self) -> None:
        """Clear jitter data and statistics."""
        self._jitter.clear()
        self._points_label.setText("Points: --")
        self._rms_label.setText("RMS: --")
        self._p2p_label.setText("P-P: --")
        self._outliers_label.setText("Outliers: --")
        self._drift_label.setText("Drift: --")

    def _update_stats(self) -> None:
        """Update statistics labels from widget data."""
        stats = self._jitter.get_statistics()
        if not stats:
            return

        self._points_label.setText(f"Points: {stats.point_count:,}")
        self._rms_label.setText(f"RMS: {stats.rms_ns:.1f} ns")
        self._p2p_label.setText(f"P-P: {stats.peak_to_peak_ns:.1f} ns")
        self._outliers_label.setText(f"Outliers: {stats.outlier_count}")

        if stats.drift_rate_ns_per_bit != 0:
            self._drift_label.setText(f"Drift: {stats.drift_rate_ns_per_sector:+.1f} ns/sector")
        else:
            self._drift_label.setText("Drift: --")


__all__ = [
    'TimingJitterWidget',
    'TimingJitterPanel',
    'JitterPoint',
    'JitterStatistics',
    'TrendLine',
]
