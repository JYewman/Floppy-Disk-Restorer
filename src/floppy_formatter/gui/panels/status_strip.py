"""
Status strip for Greaseweazle workbench.

This status bar provides four sections:
- Connection: Greaseweazle connection and firmware info
- Drive: Drive type, disk presence, RPM
- Operation: Current operation status and progress
- Health: Color-coded disk health indicator

Part of Phase 5: Workbench GUI - Main Layout
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QFrame,
    QSizePolicy,
)

logger = logging.getLogger(__name__)


class StatusSection(QWidget):
    """
    A section of the status strip with icon and text.
    """

    def __init__(
        self,
        label: str,
        min_width: int = 100,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize status section.

        Args:
            label: Section label/header
            min_width: Minimum width in pixels
            parent: Parent widget
        """
        super().__init__(parent)

        self._label = label

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(3)

        # Label/header
        self._header_label = QLabel(f"{label}:")
        self._header_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.7); font-weight: bold;"
        )
        layout.addWidget(self._header_label)

        # Value
        self._value_label = QLabel("---")
        self._value_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(self._value_label)

        layout.addStretch()

    def set_value(self, value: str, color: Optional[str] = None) -> None:
        """
        Set the value text.

        Args:
            value: Value text to display
            color: Optional color for the value text
        """
        self._value_label.setText(value)
        if color:
            self._value_label.setStyleSheet(f"color: {color};")
        else:
            self._value_label.setStyleSheet("color: #ffffff;")


class HealthIndicator(QWidget):
    """
    Color-coded health indicator with percentage.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize health indicator.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(3)

        # Label
        header_label = QLabel("Health:")
        header_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.7); font-weight: bold;"
        )
        layout.addWidget(header_label)

        # Progress bar - compact
        self._health_bar = QProgressBar()
        self._health_bar.setRange(0, 100)
        self._health_bar.setValue(0)
        self._health_bar.setTextVisible(False)
        self._health_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._health_bar.setMaximumHeight(12)
        layout.addWidget(self._health_bar)

        # Percentage text
        self._percent_label = QLabel("N/A")
        self._percent_label.setStyleSheet("color: #858585;")
        layout.addWidget(self._percent_label)

        # Initial state
        self._set_bar_color("#3a3d41")

    def set_health(self, percentage: int) -> None:
        """
        Set health percentage.

        Args:
            percentage: Health percentage (0-100)
        """
        percentage = max(0, min(100, percentage))
        self._health_bar.setValue(percentage)
        self._percent_label.setText(f"{percentage}%")

        # Color code based on health
        if percentage >= 80:
            color = "#33cc33"  # Green
            text_color = "#33cc33"
        elif percentage >= 50:
            color = "#cccc33"  # Yellow
            text_color = "#cccc33"
        else:
            color = "#cc3333"  # Red
            text_color = "#cc3333"

        self._set_bar_color(color)
        self._percent_label.setStyleSheet(f"color: {text_color};")

    def clear_health(self) -> None:
        """Clear health display."""
        self._health_bar.setValue(0)
        self._percent_label.setText("N/A")
        self._percent_label.setStyleSheet("color: #858585;")
        self._set_bar_color("#3a3d41")

    def _set_bar_color(self, color: str) -> None:
        """Set progress bar color."""
        self._health_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)


class StatusStrip(QWidget):
    """
    Status strip for the workbench GUI.

    Displays connection status, drive information, operation status,
    and disk health in a horizontal bar at the bottom of the window.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize status strip.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Use preferred sizing - don't fix height for DPI independence
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Apply status bar styling
        self.setStyleSheet("""
            StatusStrip {
                background-color: #007acc;
                border-top: 1px solid #005a9e;
            }
        """)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Connection section
        self._connection_section = StatusSection("Connection")
        main_layout.addWidget(self._connection_section)

        # Separator
        separator1 = self._create_separator()
        main_layout.addWidget(separator1)

        # Drive section
        self._drive_section = StatusSection("Drive")
        main_layout.addWidget(self._drive_section)

        # Separator
        separator2 = self._create_separator()
        main_layout.addWidget(separator2)

        # Operation section (expandable)
        self._operation_section = StatusSection("Status")
        self._operation_section.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        main_layout.addWidget(self._operation_section)

        # Separator
        separator3 = self._create_separator()
        main_layout.addWidget(separator3)

        # Health section
        self._health_indicator = HealthIndicator()
        main_layout.addWidget(self._health_indicator)

        # Initial values
        self._connection_section.set_value("Not connected", "#cc3333")
        self._drive_section.set_value("No drive", "#858585")
        self._operation_section.set_value("Idle", "#cccccc")

    def _create_separator(self) -> QFrame:
        """Create a vertical separator."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        separator.setStyleSheet("QFrame { color: rgba(255, 255, 255, 0.3); }")
        separator.setFixedWidth(1)
        return separator

    # =========================================================================
    # Public API
    # =========================================================================

    def set_connection_status(
        self,
        connected: bool,
        device_info: Optional[str] = None
    ) -> None:
        """
        Update connection status display.

        Args:
            connected: Whether device is connected
            device_info: Optional device info string (e.g., "Greaseweazle V4.1")
        """
        if connected:
            text = device_info if device_info else "Connected"
            self._connection_section.set_value(text, "#ffffff")
        else:
            self._connection_section.set_value("Not connected", "#cc3333")

    def set_drive_status(
        self,
        drive_type: Optional[str] = None,
        rpm: Optional[float] = None,
        has_disk: bool = False
    ) -> None:
        """
        Update drive status display.

        Args:
            drive_type: Drive type string (e.g., "3.5\" HD")
            rpm: Current RPM reading
            has_disk: Whether a disk is detected
        """
        if not drive_type:
            self._drive_section.set_value("Drive not selected", "#858585")
        elif not has_disk:
            self._drive_section.set_value("No disk", "#cccc33")
        elif rpm and rpm > 0:
            self._drive_section.set_value(f"{drive_type} @ {rpm:.0f} RPM", "#ffffff")
        else:
            self._drive_section.set_value(drive_type, "#ffffff")

    def set_operation_status(self, status: str, color: Optional[str] = None) -> None:
        """
        Update operation status display.

        Args:
            status: Status message
            color: Optional text color
        """
        self._operation_section.set_value(status, color or "#cccccc")

    def set_idle(self) -> None:
        """Set status to idle."""
        self._operation_section.set_value("Idle", "#cccccc")

    def set_scanning(self, track: int, total_tracks: int) -> None:
        """
        Set status to scanning.

        Args:
            track: Current track number
            total_tracks: Total tracks
        """
        self._operation_section.set_value(
            f"Scanning track {track}/{total_tracks}...",
            "#33cc33"
        )

    def set_formatting(self, track: int, total_tracks: int) -> None:
        """
        Set status to formatting.

        Args:
            track: Current track number
            total_tracks: Total tracks
        """
        self._operation_section.set_value(
            f"Formatting track {track}/{total_tracks}...",
            "#33cc33"
        )

    def set_restoring(
        self,
        pass_num: int,
        total_passes: int,
        sector: int,
        total_sectors: int
    ) -> None:
        """
        Set status to restoring.

        Args:
            pass_num: Current pass number
            total_passes: Total passes
            sector: Current sector
            total_sectors: Total sectors
        """
        self._operation_section.set_value(
            f"Restoring - Pass {pass_num}/{total_passes}, Sector {sector}/{total_sectors}...",
            "#33cc33"
        )

    def set_analyzing(self, description: str = "flux data") -> None:
        """
        Set status to analyzing.

        Args:
            description: What is being analyzed
        """
        self._operation_section.set_value(
            f"Analyzing {description}...",
            "#33cc33"
        )

    def set_health(self, percentage: int) -> None:
        """
        Update disk health display.

        Args:
            percentage: Health percentage (0-100)
        """
        self._health_indicator.set_health(percentage)

    def clear_health(self) -> None:
        """Clear health display (show N/A)."""
        self._health_indicator.clear_health()

    def set_error(self, message: str) -> None:
        """
        Display error status.

        Args:
            message: Error message
        """
        self._operation_section.set_value(message, "#cc3333")

    def set_warning(self, message: str) -> None:
        """
        Display warning status.

        Args:
            message: Warning message
        """
        self._operation_section.set_value(message, "#cccc33")

    def set_success(self, message: str) -> None:
        """
        Display success status.

        Args:
            message: Success message
        """
        self._operation_section.set_value(message, "#33cc33")
