"""
Operation toolbar for Greaseweazle workbench.

This toolbar provides:
- Large icon buttons for main operations (Scan, Format, Restore, Analyze)
- Operation mode selector (Quick/Standard/Thorough/Forensic)
- Start/Stop/Pause controls
- Progress indicator with ETA

Part of Phase 5: Workbench GUI - Main Layout
"""

import logging
from typing import Optional
from enum import Enum, auto

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QProgressBar,
    QFrame,
    QSizePolicy,
    QToolButton,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QIcon

from floppy_formatter.gui.resources import get_icon

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Available operation types."""
    SCAN = "scan"
    FORMAT = "format"
    RESTORE = "restore"
    ANALYZE = "analyze"


class OperationMode(Enum):
    """Operation execution modes."""
    QUICK = "Quick"
    STANDARD = "Standard"
    THOROUGH = "Thorough"
    FORENSIC = "Forensic"


class OperationState(Enum):
    """Current operation state."""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()


class LargeOperationButton(QToolButton):
    """
    Large button for main operations with icon above text.

    Displays a large icon (48x48) with operation name below.
    """

    def __init__(
        self,
        text: str,
        icon_name: str,
        tooltip: str,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize large operation button.

        Args:
            text: Button text
            icon_name: Name of icon from resources
            tooltip: Tooltip text
            parent: Parent widget
        """
        super().__init__(parent)

        self.setText(text)
        self.setToolTip(tooltip)
        # Use text beside icon for horizontal layout (not under)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(16, 16))

        # Try to load icon
        icon = get_icon(icon_name)
        if not icon.isNull():
            self.setIcon(icon)

        # Fixed minimum width to ensure text fits
        self.setMinimumWidth(70)

        # Apply custom styling - compact for smaller UI
        self.setStyleSheet("""
            QToolButton {
                background-color: #2d2d30;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QToolButton:hover {
                background-color: #3a3d41;
                border-color: #007acc;
            }
            QToolButton:pressed {
                background-color: #094771;
            }
            QToolButton:disabled {
                color: #6c6c6c;
                background-color: #252526;
            }
            QToolButton:checked {
                background-color: #094771;
                border-color: #007acc;
            }
        """)


class OperationToolbar(QWidget):
    """
    Operation toolbar for the workbench GUI.

    Provides main operation buttons, mode selection, and control buttons
    for starting, stopping, and pausing operations.

    Signals:
        operation_requested: Emitted when operation button clicked (str: operation_type)
        mode_changed: Emitted when mode selection changes (str: mode_name)
        start_clicked: Emitted when start button clicked
        stop_clicked: Emitted when stop button clicked
        pause_clicked: Emitted when pause button clicked
    """

    operation_requested = pyqtSignal(str)
    mode_changed = pyqtSignal(str)
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize operation toolbar.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # State tracking
        self._state = OperationState.IDLE
        self._selected_operation: Optional[OperationType] = None
        self._progress = 0
        self._eta_seconds = 0
        self._is_enabled = False

        # ETA update timer
        self._eta_timer = QTimer(self)
        self._eta_timer.timeout.connect(self._update_eta)

        # Build UI
        self._setup_ui()

        # Initial state
        self._update_control_states()

    def _setup_ui(self) -> None:
        """Set up the user interface - single horizontal row."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(6)

        # Operation buttons - compact
        self._scan_button = LargeOperationButton(
            "Scan", "search", "Scan disk for errors"
        )
        self._scan_button.setCheckable(True)
        self._scan_button.clicked.connect(lambda: self._on_operation_clicked(OperationType.SCAN))
        main_layout.addWidget(self._scan_button)

        self._format_button = LargeOperationButton(
            "Format", "hard-drive", "Format disk"
        )
        self._format_button.setCheckable(True)
        self._format_button.clicked.connect(lambda: self._on_operation_clicked(OperationType.FORMAT))
        main_layout.addWidget(self._format_button)

        self._restore_button = LargeOperationButton(
            "Restore", "refresh-cw", "Restore/recover disk"
        )
        self._restore_button.setCheckable(True)
        self._restore_button.clicked.connect(lambda: self._on_operation_clicked(OperationType.RESTORE))
        main_layout.addWidget(self._restore_button)

        self._analyze_button = LargeOperationButton(
            "Analyze", "activity", "Analyze flux data"
        )
        self._analyze_button.setCheckable(True)
        self._analyze_button.clicked.connect(lambda: self._on_operation_clicked(OperationType.ANALYZE))
        main_layout.addWidget(self._analyze_button)

        self._operation_buttons = [
            self._scan_button,
            self._format_button,
            self._restore_button,
            self._analyze_button,
        ]

        # Separator
        main_layout.addWidget(self._create_separator())

        # Mode selector - horizontal
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("color: #cccccc;")
        main_layout.addWidget(mode_label)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems([m.value for m in OperationMode])
        self._mode_combo.setCurrentText(OperationMode.STANDARD.value)
        self._mode_combo.setFixedWidth(100)
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        main_layout.addWidget(self._mode_combo)

        # Separator
        main_layout.addWidget(self._create_separator())

        # Control buttons - horizontal
        self._start_button = QPushButton("Start")
        self._start_button.setProperty("variant", "success")
        self._start_button.setFixedWidth(55)
        self._start_button.clicked.connect(self._on_start_clicked)
        main_layout.addWidget(self._start_button)

        self._pause_button = QPushButton("Pause")
        self._pause_button.setToolTip("Pause operation")
        self._pause_button.setFixedWidth(55)
        self._pause_button.clicked.connect(self._on_pause_clicked)
        main_layout.addWidget(self._pause_button)

        self._stop_button = QPushButton("Stop")
        self._stop_button.setToolTip("Stop operation")
        self._stop_button.setProperty("variant", "error")
        self._stop_button.setFixedWidth(50)
        self._stop_button.clicked.connect(self._on_stop_clicked)
        main_layout.addWidget(self._stop_button)

        # Separator
        main_layout.addWidget(self._create_separator())

        # Progress section - horizontal
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedWidth(150)
        main_layout.addWidget(self._progress_bar)

        self._eta_label = QLabel("Ready")
        self._eta_label.setStyleSheet("color: #858585;")
        self._eta_label.setFixedWidth(70)
        main_layout.addWidget(self._eta_label)

        # Add stretch
        main_layout.addStretch(1)

    def _create_separator(self) -> QFrame:
        """Create a vertical separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { color: #3a3d41; }")
        return separator

    def _on_operation_clicked(self, operation: OperationType) -> None:
        """Handle operation button click."""
        # Uncheck other buttons
        for btn in self._operation_buttons:
            if btn != self._get_button_for_operation(operation):
                btn.setChecked(False)

        button = self._get_button_for_operation(operation)
        if button.isChecked():
            self._selected_operation = operation
            logger.debug("Operation selected: %s", operation.value)
            self.operation_requested.emit(operation.value)
        else:
            self._selected_operation = None

    def _get_button_for_operation(self, operation: OperationType) -> LargeOperationButton:
        """Get button widget for operation type."""
        mapping = {
            OperationType.SCAN: self._scan_button,
            OperationType.FORMAT: self._format_button,
            OperationType.RESTORE: self._restore_button,
            OperationType.ANALYZE: self._analyze_button,
        }
        return mapping[operation]

    def _on_mode_changed(self, mode_text: str) -> None:
        """Handle mode selection change."""
        logger.debug("Mode changed: %s", mode_text)
        self.mode_changed.emit(mode_text)

    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        if self._state == OperationState.IDLE:
            logger.debug("Start clicked")
            self.start_clicked.emit()
        elif self._state == OperationState.PAUSED:
            # Resume from pause
            logger.debug("Resume clicked")
            self._state = OperationState.RUNNING
            self._update_control_states()
            self.start_clicked.emit()

    def _on_pause_clicked(self) -> None:
        """Handle pause button click."""
        if self._state == OperationState.RUNNING:
            logger.debug("Pause clicked")
            self._state = OperationState.PAUSED
            self._update_control_states()
            self.pause_clicked.emit()

    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        if self._state in (OperationState.RUNNING, OperationState.PAUSED):
            logger.debug("Stop clicked")
            self._state = OperationState.STOPPING
            self._update_control_states()
            self.stop_clicked.emit()

    def _update_control_states(self) -> None:
        """Update enabled/disabled states based on current state."""
        is_idle = self._state == OperationState.IDLE
        is_running = self._state == OperationState.RUNNING
        is_paused = self._state == OperationState.PAUSED

        # Operation buttons - only enabled when idle and connected
        for btn in self._operation_buttons:
            btn.setEnabled(is_idle and self._is_enabled)

        # Mode selector - only enabled when idle
        self._mode_combo.setEnabled(is_idle and self._is_enabled)

        # Start button
        self._start_button.setEnabled(
            (is_idle and self._selected_operation is not None and self._is_enabled) or
            is_paused
        )
        if is_paused:
            self._start_button.setText("Resume")
        else:
            self._start_button.setText("Start")

        # Pause button - only enabled when running
        self._pause_button.setEnabled(is_running)

        # Stop button - enabled when running or paused
        self._stop_button.setEnabled(is_running or is_paused)

        # Progress bar
        if is_idle:
            self._progress_bar.setValue(0)
            self._eta_label.setText("Ready")

    def _update_eta(self) -> None:
        """Update ETA countdown."""
        if self._eta_seconds > 0:
            self._eta_seconds -= 1
            minutes = self._eta_seconds // 60
            seconds = self._eta_seconds % 60
            self._eta_label.setText(f"ETA: {minutes}:{seconds:02d}")
        else:
            self._eta_label.setText("Completing...")

    # =========================================================================
    # Public API
    # =========================================================================

    def set_enabled(self, enabled: bool) -> None:
        """
        Enable or disable the toolbar.

        Used to disable when not connected to device.

        Args:
            enabled: True to enable, False to disable
        """
        self._is_enabled = enabled
        self._update_control_states()

    def get_selected_operation(self) -> Optional[str]:
        """
        Get the currently selected operation.

        Returns:
            Operation type string or None
        """
        if self._selected_operation:
            return self._selected_operation.value
        return None

    def get_selected_mode(self) -> str:
        """
        Get the currently selected operation mode.

        Returns:
            Mode name string
        """
        return self._mode_combo.currentText()

    def set_operation(self, operation: str) -> None:
        """
        Programmatically select an operation.

        Args:
            operation: Operation type ("scan", "format", "restore", "analyze")
        """
        try:
            op_type = OperationType(operation)
            button = self._get_button_for_operation(op_type)

            # Uncheck all buttons
            for btn in self._operation_buttons:
                btn.setChecked(False)

            # Check the selected button
            button.setChecked(True)
            self._selected_operation = op_type

        except ValueError:
            logger.warning("Unknown operation type: %s", operation)

    def clear_selection(self) -> None:
        """Clear operation selection."""
        for btn in self._operation_buttons:
            btn.setChecked(False)
        self._selected_operation = None

    def start_operation(self) -> None:
        """
        Called when operation starts.

        Updates UI to running state.
        """
        self._state = OperationState.RUNNING
        self._progress = 0
        self._progress_bar.setValue(0)
        self._eta_label.setText("Calculating...")
        self._update_control_states()

    def stop_operation(self) -> None:
        """
        Called when operation stops (completed, cancelled, or error).

        Updates UI to idle state.
        """
        self._state = OperationState.IDLE
        self._eta_timer.stop()
        self._update_control_states()

    def set_progress(self, progress: int, eta_seconds: Optional[int] = None) -> None:
        """
        Update progress display.

        Args:
            progress: Progress percentage (0-100)
            eta_seconds: Optional estimated time remaining in seconds
        """
        self._progress = max(0, min(100, progress))
        self._progress_bar.setValue(self._progress)

        if eta_seconds is not None:
            self._eta_seconds = eta_seconds
            if not self._eta_timer.isActive():
                self._eta_timer.start(1000)  # Update every second
            self._update_eta()
        elif progress >= 100:
            self._eta_timer.stop()
            self._eta_label.setText("Complete")

    def is_operation_running(self) -> bool:
        """
        Check if an operation is currently running.

        Returns:
            True if running or paused
        """
        return self._state in (OperationState.RUNNING, OperationState.PAUSED)

    def get_state(self) -> OperationState:
        """
        Get current operation state.

        Returns:
            Current OperationState
        """
        return self._state
