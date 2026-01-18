"""
Diagnostics tab for Analytics Dashboard.

Provides drive diagnostics including:
- Head alignment visualization
- RPM stability chart
- Drive temperature (if available)
- Self-test results panel
- Drive information display

Part of Phase 7: Analytics Dashboard
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QSizePolicy,
    QGridLayout,
)
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QPainterPath,
    QFont,
    QPaintEvent,
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

COLOR_GOOD = QColor("#4ec9b0")
COLOR_WARNING = QColor("#dcdcaa")
COLOR_BAD = QColor("#f14c4c")
COLOR_INFO = QColor("#569cd6")

# RPM reference
TARGET_RPM = 300.0
RPM_TOLERANCE = 2.0  # ±2 RPM


# =============================================================================
# Data Classes
# =============================================================================

class TestStatus(Enum):
    """Status of a self-test item."""
    PENDING = "Pending"
    RUNNING = "Running"
    PASS = "Pass"
    FAIL = "Fail"
    SKIPPED = "Skipped"


@dataclass
class SelfTestItem:
    """
    Single self-test item result.

    Attributes:
        name: Test name
        status: Test status
        details: Additional details
        duration_ms: Test duration
    """
    name: str
    status: TestStatus = TestStatus.PENDING
    details: str = ""
    duration_ms: float = 0.0


@dataclass
class SelfTestResults:
    """
    Complete self-test results.

    Attributes:
        tests: List of test items
        timestamp: When tests were run
        overall_pass: Whether all tests passed
    """
    tests: List[SelfTestItem] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    overall_pass: bool = False

    def __post_init__(self):
        if not self.tests:
            # Default tests
            self.tests = [
                SelfTestItem("Track 0 seek"),
                SelfTestItem("Full stroke seek"),
                SelfTestItem("RPM stability"),
                SelfTestItem("Index pulse detection"),
                SelfTestItem("Read/write head check"),
            ]


@dataclass
class AlignmentResults:
    """
    Head alignment test results.

    Attributes:
        score: Overall alignment score (0-100)
        status: Text status ("Aligned", "Slightly Off", "Misaligned")
        inner_margin: Inner track margin (microns)
        outer_margin: Outer track margin (microns)
        center_offset: Offset from center (microns)
        cylinders_tested: List of tested cylinders
        per_cylinder_scores: Score for each tested cylinder
    """
    score: float = 0.0
    status: str = "Unknown"
    inner_margin: float = 0.0
    outer_margin: float = 0.0
    center_offset: float = 0.0
    cylinders_tested: List[int] = field(default_factory=list)
    per_cylinder_scores: List[float] = field(default_factory=list)


# =============================================================================
# Alignment Visualization Widget
# =============================================================================

class AlignmentVisualizationWidget(QWidget):
    """
    Visual representation of head alignment.

    Shows:
    - Margin plot with inner/outer margins
    - Center offset indicator
    - Per-cylinder alignment quality
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._results: Optional[AlignmentResults] = None

        self.setMinimumSize(200, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_results(self, results: AlignmentResults) -> None:
        """Set alignment results."""
        self._results = results
        self.update()

    def clear_results(self) -> None:
        """Clear results."""
        self._results = None
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the alignment visualization."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), COLOR_PANEL_BG)

        margin_left = 50
        margin_right = 20
        margin_top = 30
        margin_bottom = 30

        plot_left = margin_left
        plot_right = self.width() - margin_right
        plot_top = margin_top
        plot_bottom = self.height() - margin_bottom
        plot_width = plot_right - plot_left
        plot_height = plot_bottom - plot_top
        center_y = plot_top + plot_height / 2

        # Title
        painter.setPen(QPen(COLOR_TEXT))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(margin_left, 18, "Head Alignment")

        if not self._results or not self._results.cylinders_tested:
            painter.setPen(QPen(COLOR_TEXT_DIM))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(
                int(plot_left + plot_width / 2 - 60),
                int(center_y), "No alignment data"
            )
            return

        # Draw reference line (center/optimal position)
        painter.setPen(QPen(COLOR_INFO, 1, Qt.PenStyle.DashLine))
        painter.drawLine(
            int(plot_left), int(center_y),
            int(plot_right), int(center_y)
        )

        # Draw margin bands
        max_margin = max(self._results.inner_margin, self._results.outer_margin, 50)
        scale = (plot_height / 2) / max_margin

        # Inner margin band (above center)
        inner_height = self._results.inner_margin * scale
        painter.fillRect(
            QRectF(plot_left, center_y - inner_height, plot_width, inner_height),
            QColor(COLOR_GOOD.red(), COLOR_GOOD.green(), COLOR_GOOD.blue(), 50)
        )

        # Outer margin band (below center)
        outer_height = self._results.outer_margin * scale
        painter.fillRect(
            QRectF(plot_left, center_y, plot_width, outer_height),
            QColor(COLOR_GOOD.red(), COLOR_GOOD.green(), COLOR_GOOD.blue(), 50)
        )

        # Draw per-cylinder quality bars
        n_cyls = len(self._results.cylinders_tested)
        if n_cyls > 0:
            bar_width = plot_width / n_cyls - 4

            cyls_scores = zip(
                self._results.cylinders_tested,
                self._results.per_cylinder_scores
            )
            for i, (cyl, score) in enumerate(cyls_scores):
                x = plot_left + i * (plot_width / n_cyls) + 2
                bar_height = (score / 100) * (plot_height / 2 - 10)

                # Color based on score
                if score >= 80:
                    color = COLOR_GOOD
                elif score >= 60:
                    color = COLOR_WARNING
                else:
                    color = COLOR_BAD

                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color.darker(120)))

                # Draw bar from center
                painter.drawRect(QRectF(x, center_y - bar_height, bar_width, bar_height * 2))

                # Cylinder label
                painter.setPen(QPen(COLOR_TEXT_DIM))
                painter.setFont(QFont("Consolas", 7))
                painter.drawText(int(x), int(plot_bottom + 12), str(cyl))

        # Draw center offset indicator
        offset_ratio = self._results.center_offset / max_margin
        offset_x = plot_left + plot_width / 2 + offset_ratio * (plot_width / 4)
        painter.setPen(QPen(COLOR_WARNING, 2))
        painter.drawLine(int(offset_x), int(center_y - 10), int(offset_x), int(center_y + 10))

        # Status text
        painter.setFont(QFont("Segoe UI", 9))

        if self._results.score >= 80:
            status_color = COLOR_GOOD
        elif self._results.score >= 60:
            status_color = COLOR_WARNING
        else:
            status_color = COLOR_BAD

        painter.setPen(QPen(status_color))
        status_text = f"{self._results.status} ({self._results.score:.0f}%)"
        painter.drawText(int(plot_right - 100), 18, status_text)

        # Axis labels
        painter.setPen(QPen(COLOR_TEXT_DIM))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(5, int(center_y - plot_height / 4), f"+{max_margin:.0f}")
        painter.drawText(5, int(center_y), "0")
        painter.drawText(5, int(center_y + plot_height / 4), f"-{max_margin:.0f}")

        # Label
        painter.drawText(5, int(plot_bottom + 12), "µm")


# =============================================================================
# RPM Chart Widget
# =============================================================================

class RPMChartWidget(QWidget):
    """
    Line chart showing RPM measurements over time.

    Features:
    - Reference line at 300 RPM
    - Stability indicator
    - Rolling window of measurements
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._rpm_history: List[float] = []
        self._max_points = 50
        self._target_rpm = TARGET_RPM

        self.setMinimumSize(200, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def add_rpm_measurement(self, rpm: float) -> None:
        """Add an RPM measurement."""
        self._rpm_history.append(rpm)
        if len(self._rpm_history) > self._max_points:
            self._rpm_history = self._rpm_history[-self._max_points:]
        self.update()

    def set_rpm_data(self, rpm_list: List[float]) -> None:
        """Set all RPM data."""
        self._rpm_history = rpm_list[-self._max_points:]
        self.update()

    def clear_rpm_data(self) -> None:
        """Clear RPM data."""
        self._rpm_history.clear()
        self.update()

    def get_stability_status(self) -> str:
        """Get stability status text."""
        if not self._rpm_history:
            return "Unknown"

        avg_rpm = sum(self._rpm_history) / len(self._rpm_history)
        max_deviation = max(abs(rpm - avg_rpm) for rpm in self._rpm_history)

        if max_deviation <= RPM_TOLERANCE / 2:
            return "Stable"
        elif max_deviation <= RPM_TOLERANCE:
            return "Minor variation"
        else:
            return "Unstable"

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the RPM chart."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), COLOR_PANEL_BG)

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

        # Title with status
        painter.setPen(QPen(COLOR_TEXT))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(margin_left, 16, "RPM Stability")

        status = self.get_stability_status()
        if status == "Stable":
            status_color = COLOR_GOOD
        elif status == "Minor variation":
            status_color = COLOR_WARNING
        else:
            status_color = COLOR_BAD

        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QPen(status_color))
        painter.drawText(int(plot_right - 80), 16, status)

        # Draw target line at 300 RPM
        target_y = plot_top + plot_height / 2

        painter.setPen(QPen(COLOR_INFO, 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(plot_left), int(target_y), int(plot_right), int(target_y))

        # RPM range: 290-310
        rpm_min = 290.0
        rpm_max = 310.0
        rpm_range = rpm_max - rpm_min

        # Draw tolerance band
        tolerance_height = (RPM_TOLERANCE * 2 / rpm_range) * plot_height
        painter.fillRect(
            QRectF(plot_left, target_y - tolerance_height / 2, plot_width, tolerance_height),
            QColor(COLOR_GOOD.red(), COLOR_GOOD.green(), COLOR_GOOD.blue(), 30)
        )

        if not self._rpm_history:
            painter.setPen(QPen(COLOR_TEXT_DIM))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(
                int(plot_left + plot_width / 2 - 30), int(target_y), "No data"
            )
            return

        # Draw data line
        path = QPainterPath()
        n = len(self._rpm_history)

        for i, rpm in enumerate(self._rpm_history):
            x = plot_left + (i / (n - 1)) * plot_width if n > 1 else plot_left + plot_width / 2
            y = plot_bottom - ((rpm - rpm_min) / rpm_range) * plot_height

            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        painter.setPen(QPen(COLOR_INFO, 2))
        painter.drawPath(path)

        # Draw current value
        current_rpm = self._rpm_history[-1]
        painter.setFont(QFont("Consolas", 10))
        painter.setPen(QPen(COLOR_TEXT))
        painter.drawText(int(plot_right - 60), int(plot_bottom + 18), f"{current_rpm:.1f}")

        # Y axis labels
        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QPen(COLOR_TEXT_DIM))
        painter.drawText(5, int(plot_top + 4), str(int(rpm_max)))
        painter.drawText(5, int(target_y + 4), str(int(self._target_rpm)))
        painter.drawText(5, int(plot_bottom), str(int(rpm_min)))


# =============================================================================
# Self-Test Results Widget
# =============================================================================

class SelfTestWidget(QFrame):
    """
    Widget showing self-test results with pass/fail status.

    Features:
    - List of tests with status icons
    - Run Self-Test button
    - Last test timestamp
    """

    run_test_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._results: Optional[SelfTestResults] = None
        self._is_running = False

        self.setStyleSheet(f"""
            SelfTestWidget {{
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
        layout.setSpacing(3)

        # Header row
        header = QHBoxLayout()

        title = QLabel("Self-Test")
        title.setStyleSheet("font-weight: bold; font-size: 8pt;")
        header.addWidget(title)

        header.addStretch()

        self._run_btn = QPushButton("Run")
        self._run_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 2px;
                padding: 2px 8px;
                font-size: 7pt;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:disabled {
                background-color: #3c3c3c;
                color: #808080;
            }
        """)
        self._run_btn.clicked.connect(self._on_run_clicked)
        header.addWidget(self._run_btn)

        layout.addLayout(header)

        # Test results container
        self._test_container = QWidget()
        self._test_layout = QVBoxLayout(self._test_container)
        self._test_layout.setContentsMargins(0, 0, 0, 0)
        self._test_layout.setSpacing(2)

        layout.addWidget(self._test_container)

        # Timestamp
        self._timestamp_label = QLabel("Last run: Never")
        self._timestamp_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 7pt;")
        layout.addWidget(self._timestamp_label)

        # Initialize with default tests
        self._results = SelfTestResults()
        self._update_test_display()

    def set_results(self, results: SelfTestResults) -> None:
        """Set test results."""
        self._results = results
        self._update_test_display()

        if results.timestamp:
            ts_str = results.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            self._timestamp_label.setText(f"Last run: {ts_str}")

    def update_test_item(self, test_name: str, status: TestStatus, details: str = "") -> None:
        """Update a single test item."""
        if not self._results:
            return

        for test in self._results.tests:
            if test.name == test_name:
                test.status = status
                test.details = details
                break

        self._update_test_display()

    def set_running(self, running: bool) -> None:
        """Set whether tests are currently running."""
        self._is_running = running
        self._run_btn.setEnabled(not running)
        self._run_btn.setText("..." if running else "Run")

    def _update_test_display(self) -> None:
        """Update the test display."""
        # Clear existing
        while self._test_layout.count():
            item = self._test_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._results:
            return

        for test in self._results.tests:
            row = QHBoxLayout()

            # Status icon
            status_label = QLabel()
            if test.status == TestStatus.PASS:
                status_label.setText("\u2714")  # Checkmark
                status_label.setStyleSheet(f"color: {COLOR_GOOD.name()};")
            elif test.status == TestStatus.FAIL:
                status_label.setText("\u2718")  # X
                status_label.setStyleSheet(f"color: {COLOR_BAD.name()};")
            elif test.status == TestStatus.RUNNING:
                status_label.setText("\u25CF")  # Circle
                status_label.setStyleSheet(f"color: {COLOR_WARNING.name()};")
            elif test.status == TestStatus.SKIPPED:
                status_label.setText("\u2014")  # Dash
                status_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()};")
            else:
                status_label.setText("\u25CB")  # Empty circle
                status_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()};")

            status_label.setFixedWidth(14)
            row.addWidget(status_label)

            # Test name
            name_label = QLabel(test.name)
            name_label.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-size: 7pt;")
            row.addWidget(name_label, 1)

            # Status text
            status_text = QLabel(test.status.value)
            status_text.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 7pt;")
            row.addWidget(status_text)

            row_widget = QWidget()
            row_widget.setLayout(row)
            self._test_layout.addWidget(row_widget)

    def _on_run_clicked(self) -> None:
        """Handle run button click."""
        self.run_test_requested.emit()


# =============================================================================
# Drive Info Widget
# =============================================================================

class DriveInfoWidget(QFrame):
    """
    Widget showing drive information.

    Displays:
    - Greaseweazle firmware version
    - Connected drive type
    - Current disk type
    - Serial number
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setStyleSheet(f"""
            DriveInfoWidget {{
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
        title = QLabel("Drive Information")
        title.setStyleSheet("font-weight: bold; font-size: 8pt;")
        layout.addWidget(title)

        # Info grid
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setColumnMinimumWidth(0, 65)
        grid.setColumnStretch(1, 1)

        self._firmware_label = self._add_info_row(grid, 0, "Firmware:")
        self._drive_type_label = self._add_info_row(grid, 1, "Drive Type:")
        self._disk_type_label = self._add_info_row(grid, 2, "Disk Type:")
        self._serial_label = self._add_info_row(grid, 3, "Serial:")

        layout.addLayout(grid)

    def _add_info_row(self, grid: QGridLayout, row: int, label_text: str) -> QLabel:
        """Add an info row and return the value label."""
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 7pt;")
        label.setFixedWidth(60)
        grid.addWidget(label, row, 0)

        value = QLabel("--")
        value.setStyleSheet("font-size: 7pt;")
        grid.addWidget(value, row, 1)

        return value

    def update_info(
        self,
        firmware: str = "--",
        drive_type: str = "--",
        disk_type: str = "--",
        serial: str = "--"
    ) -> None:
        """Update drive information."""
        self._firmware_label.setText(firmware)
        self._drive_type_label.setText(drive_type)
        self._disk_type_label.setText(disk_type)
        self._serial_label.setText(serial)

    def clear_info(self) -> None:
        """Clear drive information."""
        self._firmware_label.setText("--")
        self._drive_type_label.setText("--")
        self._disk_type_label.setText("--")
        self._serial_label.setText("--")


# =============================================================================
# Temperature Widget
# =============================================================================

class TemperatureWidget(QFrame):
    """
    Widget showing drive temperature (if available).
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._temperature: Optional[float] = None

        self.setStyleSheet(f"""
            TemperatureWidget {{
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
        title = QLabel("Temperature")
        title.setStyleSheet("font-weight: bold; font-size: 8pt;")
        layout.addWidget(title)

        # Temperature display
        self._temp_label = QLabel("N/A")
        self._temp_label.setStyleSheet("font-size: 14pt;")
        self._temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._temp_label)

        # Status
        self._status_label = QLabel("Not available")
        self._status_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 7pt;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

    def set_temperature(self, temp_c: float) -> None:
        """Set temperature in Celsius."""
        self._temperature = temp_c
        self._temp_label.setText(f"{temp_c:.1f}°C")

        if temp_c < 40:
            self._status_label.setText("Normal")
            self._status_label.setStyleSheet(f"color: {COLOR_GOOD.name()}; font-size: 7pt;")
        elif temp_c < 50:
            self._status_label.setText("Warm")
            self._status_label.setStyleSheet(f"color: {COLOR_WARNING.name()}; font-size: 7pt;")
        else:
            self._status_label.setText("Hot - allow cooling")
            self._status_label.setStyleSheet(f"color: {COLOR_BAD.name()}; font-size: 7pt;")

    def set_unavailable(self) -> None:
        """Set temperature as unavailable."""
        self._temperature = None
        self._temp_label.setText("N/A")
        self._status_label.setText("Not available")
        self._status_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 7pt;")


# =============================================================================
# Diagnostics Tab
# =============================================================================

class DiagnosticsTab(QWidget):
    """
    Diagnostics tab with alignment, RPM, and self-test displays.

    Signals:
        run_alignment_requested(): Request to run alignment test
        run_self_test_requested(): Request to run self-test
    """

    run_alignment_requested = pyqtSignal()
    run_self_test_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Left column: alignment + RPM
        left_column = QVBoxLayout()
        left_column.setSpacing(4)

        # Alignment visualization
        alignment_frame = QFrame()
        alignment_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PANEL_BG.name()};
                border: 1px solid {COLOR_BORDER.name()};
                border-radius: 4px;
            }}
        """)
        alignment_layout = QVBoxLayout(alignment_frame)
        alignment_layout.setContentsMargins(4, 4, 4, 4)

        # Alignment header with button
        align_header = QHBoxLayout()
        align_header.addStretch()

        self._run_align_btn = QPushButton("Run Alignment Test")
        self._run_align_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        self._run_align_btn.clicked.connect(self.run_alignment_requested)
        align_header.addWidget(self._run_align_btn)

        alignment_layout.addLayout(align_header)

        self._alignment_widget = AlignmentVisualizationWidget()
        alignment_layout.addWidget(self._alignment_widget, 1)

        left_column.addWidget(alignment_frame, 2)

        # RPM chart
        rpm_frame = QFrame()
        rpm_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PANEL_BG.name()};
                border: 1px solid {COLOR_BORDER.name()};
                border-radius: 4px;
            }}
        """)
        rpm_layout = QVBoxLayout(rpm_frame)
        rpm_layout.setContentsMargins(4, 4, 4, 4)

        self._rpm_chart = RPMChartWidget()
        rpm_layout.addWidget(self._rpm_chart)

        left_column.addWidget(rpm_frame, 1)

        layout.addLayout(left_column, 2)

        # Right column: self-test + drive info + temperature
        right_column = QVBoxLayout()
        right_column.setSpacing(4)

        # Self-test
        self._self_test_widget = SelfTestWidget()
        self._self_test_widget.run_test_requested.connect(self.run_self_test_requested)
        right_column.addWidget(self._self_test_widget, 2)

        # Drive info
        self._drive_info_widget = DriveInfoWidget()
        right_column.addWidget(self._drive_info_widget, 1)

        # Temperature
        self._temp_widget = TemperatureWidget()
        right_column.addWidget(self._temp_widget)

        layout.addLayout(right_column, 1)

    def update_alignment_results(self, results: AlignmentResults) -> None:
        """Update alignment visualization."""
        self._alignment_widget.set_results(results)

    def update_rpm_data(self, rpm_history: List[float]) -> None:
        """Update RPM chart."""
        self._rpm_chart.set_rpm_data(rpm_history)

    def add_rpm_measurement(self, rpm: float) -> None:
        """Add a single RPM measurement."""
        self._rpm_chart.add_rpm_measurement(rpm)

    def update_self_test_results(self, results: SelfTestResults) -> None:
        """Update self-test results."""
        self._self_test_widget.set_results(results)

    def update_test_item(self, test_name: str, status: TestStatus, details: str = "") -> None:
        """Update a single self-test item."""
        self._self_test_widget.update_test_item(test_name, status, details)

    def set_self_test_running(self, running: bool) -> None:
        """Set whether self-test is running."""
        self._self_test_widget.set_running(running)

    def update_drive_info(
        self,
        firmware: str = "--",
        drive_type: str = "--",
        disk_type: str = "--",
        serial: str = "--"
    ) -> None:
        """Update drive information."""
        self._drive_info_widget.update_info(firmware, drive_type, disk_type, serial)

    def update_temperature(self, temp_c: Optional[float]) -> None:
        """Update temperature display."""
        if temp_c is not None:
            self._temp_widget.set_temperature(temp_c)
        else:
            self._temp_widget.set_unavailable()

    def run_diagnostics(self) -> None:
        """Trigger full diagnostic sequence."""
        # Emit both signals
        self.run_alignment_requested.emit()
        self.run_self_test_requested.emit()

    def clear_all(self) -> None:
        """Clear all diagnostic data."""
        self._alignment_widget.clear_results()
        self._rpm_chart.clear_rpm_data()
        self._drive_info_widget.clear_info()
        self._temp_widget.set_unavailable()


__all__ = [
    'DiagnosticsTab',
    'AlignmentResults',
    'SelfTestResults',
    'SelfTestItem',
    'TestStatus',
    'AlignmentVisualizationWidget',
    'RPMChartWidget',
    'SelfTestWidget',
    'DriveInfoWidget',
    'TemperatureWidget',
]
