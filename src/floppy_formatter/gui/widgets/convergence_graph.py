"""
Convergence graph widget for Floppy Workbench GUI.

Displays a line graph showing bad sector count convergence over recovery passes.
Uses PyQt6-Charts for native Qt integration and consistent styling with the
rest of the application.

Library Decision: PyQt6-Charts was chosen over matplotlib because:
- Native Qt widget integrates seamlessly with the all-PyQt6 application
- Consistent rendering with other Qt widgets (CircularSectorMap, dialogs, etc.)
- For a simple line graph, matplotlib's additional power isn't needed
- One ecosystem, one rendering system throughout the application
"""

from typing import List, Tuple, Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt, QMargins
from PyQt6.QtGui import QPen, QColor, QFont, QPainter

from PyQt6.QtCharts import (
    QChart,
    QChartView,
    QLineSeries,
    QScatterSeries,
    QValueAxis,
)


# Dark theme colors matching application
COLOR_BACKGROUND = "#1e1e1e"
COLOR_SURFACE = "#252526"
COLOR_BORDER = "#3c3c3c"
COLOR_TEXT = "#cccccc"
COLOR_TEXT_DIM = "#858585"
COLOR_PRIMARY = "#0e639c"
COLOR_PRIMARY_LIGHT = "#1177bb"
COLOR_GRID = "#333333"
COLOR_SUCCESS = "#4ec9b0"


class ConvergenceGraphWidget(QWidget):
    """
    Widget displaying a convergence trend graph.

    Shows bad sector count (Y-axis) over recovery passes (X-axis) as a line
    graph with markers at each data point. Styled to match the application's
    dark theme.

    The graph automatically scales axes based on data range, with Y-axis
    minimum always at 0 to show the full context of recovery progress.

    Example:
        graph = ConvergenceGraphWidget()
        graph.add_data_point(1, 100)  # Pass 1: 100 bad sectors
        graph.add_data_point(2, 85)   # Pass 2: 85 bad sectors
        graph.add_data_point(3, 70)   # Pass 3: 70 bad sectors
    """

    def __init__(self, title: str = "Convergence Trend", parent: Optional[QWidget] = None):
        """
        Initialize the convergence graph widget.

        Args:
            title: Title displayed above the graph
            parent: Optional parent widget
        """
        super().__init__(parent)

        self._title = title
        self._data: List[Tuple[int, int]] = []

        # Create and configure chart
        self._chart = QChart()
        self._chart.setTitle(self._title)
        self._chart.setBackgroundBrush(QColor(COLOR_BACKGROUND))
        self._chart.setBackgroundRoundness(0)
        self._chart.setTitleBrush(QColor(COLOR_TEXT))
        self._chart.setTitleFont(QFont("", 10, QFont.Weight.Bold))
        self._chart.legend().hide()
        self._chart.setMargins(QMargins(5, 5, 5, 5))

        # Disable animations for immediate updates
        self._chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)

        # Create line series for the trend line
        self._line_series = QLineSeries()
        self._line_series.setName("Bad Sectors")
        line_pen = QPen(QColor(COLOR_PRIMARY))
        line_pen.setWidth(2)
        self._line_series.setPen(line_pen)

        # Create scatter series for data point markers
        self._scatter_series = QScatterSeries()
        self._scatter_series.setName("Data Points")
        self._scatter_series.setMarkerSize(10)
        self._scatter_series.setColor(QColor(COLOR_PRIMARY_LIGHT))
        self._scatter_series.setBorderColor(QColor(COLOR_PRIMARY))

        # Add series to chart
        self._chart.addSeries(self._line_series)
        self._chart.addSeries(self._scatter_series)

        # Create and configure X-axis (Pass Number)
        self._axis_x = QValueAxis()
        self._axis_x.setTitleText("Pass Number")
        self._axis_x.setTitleBrush(QColor(COLOR_TEXT_DIM))
        self._axis_x.setTitleFont(QFont("", 9))
        self._axis_x.setLabelFormat("%d")
        self._axis_x.setLabelsColor(QColor(COLOR_TEXT))
        self._axis_x.setLabelsFont(QFont("", 8))
        self._axis_x.setGridLineColor(QColor(COLOR_GRID))
        self._axis_x.setGridLineVisible(True)
        self._axis_x.setLinePen(QPen(QColor(COLOR_BORDER)))
        self._axis_x.setTickCount(5)
        self._axis_x.setMinorTickCount(0)
        self._axis_x.setRange(0, 10)

        # Create and configure Y-axis (Bad Sectors)
        self._axis_y = QValueAxis()
        self._axis_y.setTitleText("Bad Sectors")
        self._axis_y.setTitleBrush(QColor(COLOR_TEXT_DIM))
        self._axis_y.setTitleFont(QFont("", 9))
        self._axis_y.setLabelFormat("%d")
        self._axis_y.setLabelsColor(QColor(COLOR_TEXT))
        self._axis_y.setLabelsFont(QFont("", 8))
        self._axis_y.setGridLineColor(QColor(COLOR_GRID))
        self._axis_y.setGridLineVisible(True)
        self._axis_y.setLinePen(QPen(QColor(COLOR_BORDER)))
        self._axis_y.setTickCount(5)
        self._axis_y.setMinorTickCount(0)
        self._axis_y.setMin(0)
        self._axis_y.setMax(100)

        # Add axes to chart
        self._chart.addAxis(self._axis_x, Qt.AlignmentFlag.AlignBottom)
        self._chart.addAxis(self._axis_y, Qt.AlignmentFlag.AlignLeft)

        # Attach series to axes
        self._line_series.attachAxis(self._axis_x)
        self._line_series.attachAxis(self._axis_y)
        self._scatter_series.attachAxis(self._axis_x)
        self._scatter_series.attachAxis(self._axis_y)

        # Create chart view with anti-aliasing
        self._chart_view = QChartView(self._chart)
        self._chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._chart_view.setBackgroundBrush(QColor(COLOR_BACKGROUND))

        # Set up layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._chart_view)

        # Size policy - expand to fill available space
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.setMinimumSize(300, 180)

    def add_data_point(self, pass_num: int, bad_sectors: int) -> None:
        """
        Add a single data point to the graph.

        The graph automatically updates axes to accommodate new data.

        Args:
            pass_num: Recovery pass number (X-axis value)
            bad_sectors: Bad sector count after this pass (Y-axis value)
        """
        self._data.append((pass_num, bad_sectors))

        # Add to both series
        self._line_series.append(float(pass_num), float(bad_sectors))
        self._scatter_series.append(float(pass_num), float(bad_sectors))

        # Update axis ranges
        self._update_axes()

    def set_data(self, data: List[Tuple[int, int]]) -> None:
        """
        Set the complete graph data, replacing any existing data.

        Args:
            data: List of (pass_num, bad_sectors) tuples
        """
        # Store data
        self._data = list(data)

        # Clear existing series data
        self._line_series.clear()
        self._scatter_series.clear()

        # Add all data points
        for pass_num, bad_sectors in self._data:
            self._line_series.append(float(pass_num), float(bad_sectors))
            self._scatter_series.append(float(pass_num), float(bad_sectors))

        # Update axis ranges
        self._update_axes()

    def clear(self) -> None:
        """Clear all data from the graph and reset to default state."""
        self._data = []
        self._line_series.clear()
        self._scatter_series.clear()

        # Reset axes to defaults
        self._axis_x.setRange(0, 10)
        self._axis_y.setRange(0, 100)

    def _update_axes(self) -> None:
        """Update axis ranges based on current data."""
        if not self._data:
            self._axis_x.setRange(0, 10)
            self._axis_y.setRange(0, 100)
            return

        x_vals = [d[0] for d in self._data]
        y_vals = [d[1] for d in self._data]

        # X-axis: show all pass numbers with padding
        min_x = max(0, min(x_vals) - 0.5)
        max_x = max(x_vals) + 0.5

        # Ensure reasonable range
        if max_x - min_x < 2:
            max_x = min_x + 2

        self._axis_x.setRange(min_x, max_x)

        # Calculate appropriate tick count for X-axis
        x_range = int(max_x - min_x)
        if x_range <= 5:
            self._axis_x.setTickCount(x_range + 1)
        elif x_range <= 10:
            self._axis_x.setTickCount(x_range + 1)
        else:
            # For larger ranges, use fewer ticks
            self._axis_x.setTickCount(min(10, x_range // 2 + 1))

        # Y-axis: always start at 0, extend to max with 10% padding
        max_y = max(y_vals) if y_vals else 100

        if max_y == 0:
            # Handle case where all bad sectors are recovered
            self._axis_y.setRange(0, 10)
        else:
            # Add 10% padding above max value
            padded_max = max_y * 1.1
            # Round up to nice number
            if padded_max <= 20:
                padded_max = ((int(padded_max) // 5) + 1) * 5
            elif padded_max <= 100:
                padded_max = ((int(padded_max) // 10) + 1) * 10
            else:
                padded_max = ((int(padded_max) // 50) + 1) * 50

            self._axis_y.setRange(0, padded_max)

    def set_title(self, title: str) -> None:
        """
        Set the graph title.

        Args:
            title: New title text
        """
        self._title = title
        self._chart.setTitle(title)

    def get_data(self) -> List[Tuple[int, int]]:
        """
        Get the current graph data.

        Returns:
            List of (pass_num, bad_sectors) tuples
        """
        return self._data.copy()

    def get_data_point_count(self) -> int:
        """
        Get the number of data points in the graph.

        Returns:
            Number of data points
        """
        return len(self._data)

    def set_line_color(self, color: str) -> None:
        """
        Set the line color.

        Args:
            color: Color string (e.g., "#0e639c")
        """
        pen = QPen(QColor(color))
        pen.setWidth(2)
        self._line_series.setPen(pen)
        self._scatter_series.setBorderColor(QColor(color))

    def set_marker_color(self, color: str) -> None:
        """
        Set the marker fill color.

        Args:
            color: Color string (e.g., "#1177bb")
        """
        self._scatter_series.setColor(QColor(color))

    def highlight_convergence(self, converged: bool = True) -> None:
        """
        Visually indicate convergence state.

        Changes the line color to success green when converged.

        Args:
            converged: Whether convergence has been achieved
        """
        if converged:
            pen = QPen(QColor(COLOR_SUCCESS))
            pen.setWidth(2)
            self._line_series.setPen(pen)
            self._scatter_series.setColor(QColor(COLOR_SUCCESS))
            self._scatter_series.setBorderColor(QColor(COLOR_SUCCESS))
        else:
            pen = QPen(QColor(COLOR_PRIMARY))
            pen.setWidth(2)
            self._line_series.setPen(pen)
            self._scatter_series.setColor(QColor(COLOR_PRIMARY_LIGHT))
            self._scatter_series.setBorderColor(QColor(COLOR_PRIMARY))
