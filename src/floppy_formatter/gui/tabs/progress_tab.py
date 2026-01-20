"""
Progress tab for Analytics Dashboard.

Provides a live progress view during disk operations including:
- Operation name and status
- Progress bar with percentage
- Estimated time to completion
- Current track, head, and sector information
- Operation-specific details

Part of Phase 7: Analytics Dashboard
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Dict, Any
import time

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QGridLayout,
    QGroupBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

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
COLOR_INFO = QColor("#569cd6")  # Blue


# =============================================================================
# Data Classes
# =============================================================================

class OperationStatus(Enum):
    """Status of the current operation."""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class ProgressData:
    """
    Current progress data for an operation.

    Attributes:
        operation_type: Type of operation (scan, format, restore, analyze)
        status: Current operation status
        progress_percent: Progress percentage (0-100)
        current_track: Current track number being processed
        total_tracks: Total number of tracks
        current_head: Current head (0 or 1)
        current_sector: Current sector being processed
        total_sectors: Total number of sectors
        current_pass: Current pass number (for multi-pass operations)
        total_passes: Total number of passes
        start_time: When the operation started
        elapsed_seconds: Seconds elapsed
        eta_seconds: Estimated seconds remaining
        good_sectors: Number of good sectors found/processed
        bad_sectors: Number of bad sectors found
        recovered_sectors: Number of recovered sectors
        message: Current status message
        details: Additional operation-specific details
    """
    operation_type: str = ""
    status: OperationStatus = OperationStatus.IDLE
    progress_percent: int = 0
    current_track: int = 0
    total_tracks: int = 160
    current_head: int = 0
    current_sector: int = 0
    total_sectors: int = 2880
    current_pass: int = 0
    total_passes: int = 1
    start_time: Optional[datetime] = None
    elapsed_seconds: float = 0.0
    eta_seconds: float = 0.0
    good_sectors: int = 0
    bad_sectors: int = 0
    recovered_sectors: int = 0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Progress Stat Card Widget
# =============================================================================

class ProgressStatCard(QWidget):
    """
    Small card displaying a single statistic with label.
    Uses QWidget instead of QFrame to avoid border styling issues.
    """

    def __init__(
        self,
        label: str,
        value: str = "--",
        color: QColor = COLOR_TEXT,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self._label_text = label
        self._value_text = value
        self._color = color

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        # Label
        self._label = QLabel(self._label_text)
        self._label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT_DIM.name()};
                font-size: 12px;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self._label)

        # Value
        self._value = QLabel(self._value_text)
        self._value.setStyleSheet(f"""
            QLabel {{
                color: {self._color.name()};
                font-size: 20px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self._value)

    def set_value(self, value: str, color: Optional[QColor] = None) -> None:
        """Update the displayed value."""
        self._value.setText(value)
        if color:
            self._color = color
            self._value.setStyleSheet(f"""
                QLabel {{
                    color: {color.name()};
                    font-size: 20px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }}
            """)


# =============================================================================
# Progress Tab Widget
# =============================================================================

class ProgressTab(QWidget):
    """
    Tab displaying live progress of disk operations.

    Shows:
    - Current operation type and status
    - Progress bar with percentage
    - Estimated time remaining
    - Track/head/sector information
    - Operation-specific statistics

    Signals:
        cancel_requested: Emitted when user requests cancellation
    """

    cancel_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._progress_data = ProgressData()
        self._start_time: Optional[float] = None

        # Timer for updating elapsed time
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_elapsed_time)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface with horizontal layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        # =================================================================
        # Header: Operation Name and Status
        # =================================================================
        header_layout = QHBoxLayout()

        self._operation_label = QLabel("No Operation")
        self._operation_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #cccccc;
                background: transparent;
                border: none;
            }
        """)
        header_layout.addWidget(self._operation_label)

        header_layout.addStretch()

        self._status_label = QLabel("Idle")
        self._status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #808080;
                padding: 4px 12px;
                background-color: #2d2d30;
                border-radius: 4px;
            }
        """)
        header_layout.addWidget(self._status_label)

        main_layout.addLayout(header_layout)

        # =================================================================
        # Main Content: Horizontal layout with three columns
        # =================================================================
        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)

        # Common GroupBox style - ensure child widgets don't inherit borders
        groupbox_style = """
            QGroupBox {
                border: 1px solid #3a3d41;
                border-radius: 4px;
                margin-top: 8px;
                font-weight: bold;
                color: #cccccc;
                background-color: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                background-color: #1e1e1e;
                color: #cccccc;
            }
            QGroupBox QLabel {
                background: transparent;
                border: none;
            }
        """

        # -----------------------------------------------------------------
        # LEFT COLUMN: Progress
        # -----------------------------------------------------------------
        progress_group = QGroupBox("Progress")
        progress_group.setStyleSheet(groupbox_style)
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setContentsMargins(10, 14, 10, 8)
        progress_layout.setSpacing(4)

        # Large percentage display
        self._percent_label = QLabel("0%")
        self._percent_label.setStyleSheet("""
            QLabel {
                font-size: 26px;
                font-weight: bold;
                color: #4ec9b0;
                background: transparent;
                border: none;
            }
        """)
        self._percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self._percent_label)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setMinimumHeight(20)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3a3d41;
                border-radius: 4px;
                background-color: #2d2d30;
            }
            QProgressBar::chunk {
                background-color: #0e639c;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self._progress_bar)

        # Time info
        time_layout = QHBoxLayout()
        self._elapsed_label = QLabel("Elapsed: --:--")
        self._elapsed_label.setStyleSheet("""
            QLabel {
                color: #808080;
                font-size: 10px;
                background: transparent;
                border: none;
            }
        """)
        time_layout.addWidget(self._elapsed_label)
        time_layout.addStretch()
        self._eta_label = QLabel("ETA: --:--")
        self._eta_label.setStyleSheet("""
            QLabel {
                color: #569cd6;
                font-size: 10px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        time_layout.addWidget(self._eta_label)
        progress_layout.addLayout(time_layout)

        progress_layout.addStretch()
        content_layout.addWidget(progress_group, 1)

        # -----------------------------------------------------------------
        # MIDDLE COLUMN: Current Position (2x2 grid)
        # -----------------------------------------------------------------
        position_group = QGroupBox("Position")
        position_group.setStyleSheet(groupbox_style)
        position_layout = QGridLayout(position_group)
        position_layout.setContentsMargins(10, 14, 10, 8)
        position_layout.setSpacing(8)

        # Cylinder (top-left)
        self._track_card = ProgressStatCard("Cylinder", "-- / --", COLOR_TEXT)
        position_layout.addWidget(self._track_card, 0, 0)

        # Head (top-right)
        self._head_card = ProgressStatCard("Head", "--", COLOR_TEXT)
        position_layout.addWidget(self._head_card, 0, 1)

        # Sector (bottom-left)
        self._sector_card = ProgressStatCard("Sector", "-- / --", COLOR_TEXT)
        position_layout.addWidget(self._sector_card, 1, 0)

        # Pass (bottom-right)
        self._pass_card = ProgressStatCard("Pass", "-- / --", COLOR_INFO)
        position_layout.addWidget(self._pass_card, 1, 1)

        content_layout.addWidget(position_group, 1)

        main_layout.addLayout(content_layout, 1)

        # =================================================================
        # Bottom: Status Message (full width)
        # =================================================================
        message_group = QGroupBox("Status")
        message_group.setStyleSheet(groupbox_style)
        message_layout = QVBoxLayout(message_group)
        message_layout.setContentsMargins(10, 14, 10, 6)

        self._message_label = QLabel("Ready to start operation")
        self._message_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 11px;
                padding: 6px;
                background-color: #2d2d30;
                border-radius: 4px;
            }
        """)
        self._message_label.setWordWrap(True)
        self._message_label.setMinimumHeight(28)
        message_layout.addWidget(self._message_label)

        main_layout.addWidget(message_group)

    # =========================================================================
    # Timer Methods
    # =========================================================================

    def _update_elapsed_time(self) -> None:
        """Update elapsed time display."""
        if self._start_time is not None:
            elapsed = time.time() - self._start_time
            self._progress_data.elapsed_seconds = elapsed
            self._elapsed_label.setText(f"Elapsed: {self._format_time(elapsed)}")

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS or HH:MM:SS."""
        seconds = int(seconds)
        if seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes:02d}:{secs:02d}"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours:d}:{minutes:02d}:{secs:02d}"

    # =========================================================================
    # Public API - Operation Control
    # =========================================================================

    def start_operation(self, operation_type: str, total_tracks: int = 160,
                        total_sectors: int = 2880, total_passes: int = 1) -> None:
        """
        Start tracking a new operation.

        Args:
            operation_type: Type of operation (scan, format, restore, analyze)
            total_tracks: Total number of tracks to process
            total_sectors: Total number of sectors
            total_passes: Total number of passes (for multi-pass operations)
        """
        self._progress_data = ProgressData(
            operation_type=operation_type,
            status=OperationStatus.RUNNING,
            total_tracks=total_tracks,
            total_sectors=total_sectors,
            total_passes=total_passes,
            start_time=datetime.now(),
        )

        self._start_time = time.time()

        # Update UI
        op_names = {
            "scan": "Scanning Disk",
            "format": "Formatting Disk",
            "restore": "Restoring Disk",
            "analyze": "Analyzing Disk",
            "write_image": "Writing Image",
            "batch_verify": "Batch Verification",
        }
        self._operation_label.setText(op_names.get(operation_type, operation_type.title()))
        self._set_status(OperationStatus.RUNNING)

        # Reset displays
        self._progress_bar.setValue(0)
        self._percent_label.setText("0%")
        self._elapsed_label.setText("Elapsed: 00:00")
        self._eta_label.setText("ETA: Calculating...")

        self._track_card.set_value(f"0 / {total_tracks}")
        self._head_card.set_value("0")
        self._sector_card.set_value(f"0 / {total_sectors}")
        self._pass_card.set_value(f"1 / {total_passes}")

        self._message_label.setText(f"Starting {operation_type}...")

        # Start elapsed time timer
        self._update_timer.start(1000)

    def stop_operation(self, success: bool = True, message: str = "") -> None:
        """
        Stop tracking the current operation.

        Args:
            success: Whether the operation completed successfully
            message: Optional completion message
        """
        self._update_timer.stop()

        if success:
            self._set_status(OperationStatus.COMPLETED)
            self._progress_bar.setValue(100)
            self._percent_label.setText("100%")
            self._eta_label.setText("Complete")
        else:
            self._set_status(OperationStatus.FAILED)
            self._eta_label.setText("Failed")

        if message:
            self._message_label.setText(message)

    def cancel_operation(self) -> None:
        """Mark the operation as cancelled."""
        self._update_timer.stop()
        self._set_status(OperationStatus.CANCELLED)
        self._eta_label.setText("Cancelled")
        self._message_label.setText("Operation cancelled by user")

    def reset(self) -> None:
        """Reset the progress tab to initial state."""
        self._update_timer.stop()
        self._start_time = None
        self._progress_data = ProgressData()

        self._operation_label.setText("No Operation")
        self._set_status(OperationStatus.IDLE)

        self._progress_bar.setValue(0)
        self._percent_label.setText("0%")
        self._elapsed_label.setText("Elapsed: --:--")
        self._eta_label.setText("ETA: --:--")

        self._track_card.set_value("-- / --")
        self._head_card.set_value("--")
        self._sector_card.set_value("-- / --")
        self._pass_card.set_value("-- / --")

        self._message_label.setText("Ready to start operation")

    # =========================================================================
    # Public API - Progress Updates
    # =========================================================================

    def set_progress(self, progress: int, eta_seconds: Optional[float] = None) -> None:
        """
        Update progress percentage.

        Args:
            progress: Progress percentage (0-100)
            eta_seconds: Optional estimated time remaining
        """
        progress = max(0, min(100, progress))
        self._progress_data.progress_percent = progress

        self._progress_bar.setValue(progress)
        self._percent_label.setText(f"{progress}%")

        if eta_seconds is not None:
            self._progress_data.eta_seconds = eta_seconds
            self._eta_label.setText(f"ETA: {self._format_time(eta_seconds)}")
        elif progress > 0 and self._start_time:
            # Calculate ETA based on elapsed time
            elapsed = time.time() - self._start_time
            if progress < 100:
                eta = (elapsed / progress) * (100 - progress)
                self._progress_data.eta_seconds = eta
                self._eta_label.setText(f"ETA: {self._format_time(eta)}")

    def set_track(self, cylinder: int, head: int = 0) -> None:
        """
        Update current cylinder and head position.

        Args:
            cylinder: Current cylinder number (0-79 for HD floppies)
            head: Current head (0 or 1)
        """
        self._progress_data.current_track = cylinder
        self._progress_data.current_head = head

        self._track_card.set_value(f"{cylinder} / {self._progress_data.total_tracks}")
        self._head_card.set_value(str(head))

    def set_sector(self, sector: int) -> None:
        """
        Update current sector.

        Args:
            sector: Current sector number
        """
        self._progress_data.current_sector = sector
        self._sector_card.set_value(f"{sector} / {self._progress_data.total_sectors}")

    def set_pass(self, pass_num: int, total_passes: Optional[int] = None) -> None:
        """
        Update current pass number.

        Args:
            pass_num: Current pass number
            total_passes: Optional total passes (updates stored value)
        """
        self._progress_data.current_pass = pass_num
        if total_passes is not None:
            self._progress_data.total_passes = total_passes

        self._pass_card.set_value(f"{pass_num} / {self._progress_data.total_passes}")

    def set_sector_counts(self, good: int = 0, bad: int = 0, recovered: int = 0) -> None:
        """
        Update sector count statistics (data only, no UI display).

        Args:
            good: Number of good sectors
            bad: Number of bad sectors
            recovered: Number of recovered sectors
        """
        self._progress_data.good_sectors = good
        self._progress_data.bad_sectors = bad
        self._progress_data.recovered_sectors = recovered

    def set_message(self, message: str) -> None:
        """
        Update the status message.

        Args:
            message: Status message to display
        """
        self._progress_data.message = message
        self._message_label.setText(message)

    def increment_good_sectors(self, count: int = 1) -> None:
        """Increment the good sector count (data only)."""
        self._progress_data.good_sectors += count

    def increment_bad_sectors(self, count: int = 1) -> None:
        """Increment the bad sector count (data only)."""
        self._progress_data.bad_sectors += count

    def increment_recovered_sectors(self, count: int = 1) -> None:
        """Increment the recovered sector count (data only)."""
        self._progress_data.recovered_sectors += count

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _set_status(self, status: OperationStatus) -> None:
        """Update the status display."""
        self._progress_data.status = status

        status_styles = {
            OperationStatus.IDLE: ("Idle", "#808080", "#2d2d30"),
            OperationStatus.RUNNING: ("Running", "#4ec9b0", "#1e3a2f"),
            OperationStatus.PAUSED: ("Paused", "#dcdcaa", "#3a3a1e"),
            OperationStatus.COMPLETED: ("Complete", "#4ec9b0", "#1e3a2f"),
            OperationStatus.FAILED: ("Failed", "#f14c4c", "#3a1e1e"),
            OperationStatus.CANCELLED: ("Cancelled", "#dcdcaa", "#3a3a1e"),
        }

        text, color, bg = status_styles.get(status, ("Unknown", "#808080", "#2d2d30"))
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {color};
                padding: 4px 12px;
                background-color: {bg};
                border-radius: 4px;
            }}
        """)

    def get_progress_data(self) -> ProgressData:
        """
        Get the current progress data.

        Returns:
            ProgressData with current state
        """
        return self._progress_data


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'ProgressTab',
    'ProgressData',
    'ProgressStatCard',
    'OperationStatus',
]
