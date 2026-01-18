"""
Restore screen for Floppy Workbench GUI.

Provides the disk recovery/restore interface with configuration options,
real-time circular sector map visualization, convergence tracking with
table display, and multi-read statistical recovery support.
"""

from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QFrame,
    QSizePolicy,
    QMessageBox,
    QGroupBox,
    QRadioButton,
    QCheckBox,
    QSpinBox,
    QStackedWidget,
    QButtonGroup,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QElapsedTimer
from PyQt6.QtGui import QFont, QColor, QBrush

from floppy_formatter.gui.widgets.circular_sector_map import CircularSectorMap
from floppy_formatter.gui.widgets.convergence_graph import ConvergenceGraphWidget
from floppy_formatter.gui.workers.restore_worker import RestoreWorker, RestoreConfig
from floppy_formatter.gui.dialogs.confirm_cancel import show_confirm_cancel_dialog
from floppy_formatter.gui.dialogs.confirm_restore import show_confirm_restore_dialog
from floppy_formatter.core.geometry import DiskGeometry
from floppy_formatter.core.device_compat import open_device, close_device


class RestoreWidget(QWidget):
    """
    Disk restore/recovery screen with configuration and visualization.

    Implements a two-phase UI:
    - Phase 1: Options panel for configuring recovery settings
    - Phase 2: Progress view with circular sector map, convergence table,
               and detailed statistics

    Recovery modes supported:
    - Fixed Passes: Execute exactly N recovery passes
    - Convergence Mode: Continue until bad sector count stabilizes
    - Targeted Recovery: Only recover known bad sectors (preserves good data)
    - Multi-Read Mode: Statistical recovery with multiple read attempts

    Signals:
        restore_completed(object): Emitted when restore finishes with RecoveryStatistics
        restore_cancelled(): Emitted when user cancels the restore
        view_report_requested(object): Emitted when user clicks "View Report"
        back_requested(): Emitted when user wants to go back

    Layout (Progress View):
        ┌──────────────────────────────────────────┐
        │         Restoring Disk...                │
        │  Recovery in progress - do not remove    │
        ├──────────────────────────────────────────┤
        │  ┌──────────────┐  ┌─────────────────┐  │
        │  │              │  │ Convergence     │  │
        │  │  Circular    │  │ ┌─────────────┐ │  │
        │  │  Sector Map  │  │ │Pass│Bad│Delta│ │  │
        │  │              │  │ │ 1  │ 50│  -- │ │  │
        │  │              │  │ │ 2  │ 42│ ↓ 8 │ │  │
        │  │              │  │ │ 3  │ 38│ ↓ 4 │ │  │
        │  └──────────────┘  │ └─────────────┘ │  │
        │                    └─────────────────┘  │
        ├──────────────────────────────────────────┤
        │ Progress: [████████████░░░░░░░░] 58%     │
        │ Pass: 3/10 | Sectors: 1672/2880          │
        │ Bad: 38 | Recovered: 12 (24%)            │
        │ Elapsed: 02:45 | ETA: 04:30              │
        │ Status: Pass 3 - Recovering...           │
        │         [Cancel]  [View Report]  [Done]  │
        └──────────────────────────────────────────┘
    """

    # Signals
    restore_completed = pyqtSignal(object)
    restore_cancelled = pyqtSignal()
    view_report_requested = pyqtSignal(object)
    back_requested = pyqtSignal()

    # Constants
    SECTORS_PER_TRACK = 18
    TOTAL_SECTORS = 2880  # Standard 1.44MB floppy

    # Phase indices for stacked widget
    PHASE_OPTIONS = 0
    PHASE_PROGRESS = 1

    # Colors for convergence table
    COLOR_IMPROVED = QColor("#4ec9b0")   # Green/teal - fewer bad sectors
    COLOR_UNCHANGED = QColor("#dcdcaa")  # Yellow - no change
    COLOR_WORSENED = QColor("#f14c4c")   # Red - more bad sectors

    def __init__(self, parent=None):
        """
        Initialize restore widget.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)

        # Device info (set before showing widget)
        self._device_path: Optional[str] = None
        self._geometry: Optional[DiskGeometry] = None
        self._fd: Optional[int] = None

        # Bad sector list from previous scan (for targeted recovery)
        self._known_bad_sectors: List[int] = []

        # Worker and thread
        self._worker: Optional[RestoreWorker] = None
        self._thread: Optional[QThread] = None

        # Restore results
        self._restore_result = None

        # Time tracking
        self._elapsed_timer = QElapsedTimer()
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_elapsed_time)

        # State flags
        self._restore_in_progress = False
        self._restore_completed_flag = False

        # Convergence tracking
        self._convergence_history: List[Dict[str, Any]] = []
        self._current_pass = 0
        self._total_passes = 0
        self._previous_bad_count = 0
        self._initial_bad_count = 0
        self._current_bad_count = 0

        # Progress tracking
        self._current_sector = 0
        self._total_sectors = self.TOTAL_SECTORS

        # Recovery mode tracking
        self._is_convergence_mode = False

        # Set up UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface with stacked widget for phases."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create stacked widget for options and progress phases
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # Phase 1: Options Panel
        self._options_widget = self._create_options_panel()
        self.stacked_widget.addWidget(self._options_widget)

        # Phase 2: Progress View
        self._progress_widget = self._create_progress_view()
        self.stacked_widget.addWidget(self._progress_widget)

        # Start with options panel
        self.stacked_widget.setCurrentIndex(self.PHASE_OPTIONS)

    def _create_options_panel(self) -> QWidget:
        """
        Create the options configuration panel.

        Returns:
            Widget containing all recovery options
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        # Title
        title_label = QLabel("Disk Recovery Options")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(title_label)

        # Subtitle with device info
        self.device_label = QLabel("Configure recovery settings before starting")
        self.device_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device_label.setStyleSheet("color: #858585; font-size: 11pt;")
        layout.addWidget(self.device_label)

        layout.addSpacing(10)

        # Create options groups
        options_container = QWidget()
        options_layout = QHBoxLayout(options_container)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(20)

        # Left column: Recovery Mode and Advanced Recovery
        left_column = QWidget()
        left_column.setMinimumWidth(380)  # Ensure enough width for description text
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        # Recovery Mode group
        recovery_mode_group = self._create_recovery_mode_group()
        left_layout.addWidget(recovery_mode_group)

        # Advanced Recovery group
        advanced_group = self._create_advanced_recovery_group()
        left_layout.addWidget(advanced_group)

        left_layout.addStretch()
        options_layout.addWidget(left_column, stretch=1)

        # Right column: Report Options
        right_column = QWidget()
        right_column.setMinimumWidth(320)  # Ensure enough width for description text
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # Report Options group
        report_group = self._create_report_options_group()
        right_layout.addWidget(report_group)

        right_layout.addStretch()
        options_layout.addWidget(right_column, stretch=1)

        layout.addWidget(options_container, stretch=1)

        # Button container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 20, 0, 0)
        button_layout.setSpacing(15)

        button_layout.addStretch()

        # Cancel button
        self.cancel_options_button = QPushButton("Cancel")
        self.cancel_options_button.setMinimumHeight(50)
        self.cancel_options_button.setMinimumWidth(140)
        self.cancel_options_button.setFont(QFont("", 12))
        self.cancel_options_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3d41;
                color: #ffffff;
                border: 1px solid #6c6c6c;
                border-radius: 6px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #4e5157;
                border-color: #858585;
            }
            QPushButton:pressed {
                background-color: #2d2d30;
            }
        """)
        self.cancel_options_button.clicked.connect(self._on_cancel_options_clicked)
        button_layout.addWidget(self.cancel_options_button)

        # Start Restore button
        self.start_restore_button = QPushButton("Start Restore")
        self.start_restore_button.setMinimumHeight(50)
        self.start_restore_button.setMinimumWidth(160)
        self.start_restore_button.setFont(QFont("", 12))
        self.start_restore_button.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
            QPushButton:disabled {
                background-color: #2d2d30;
                color: #6c6c6c;
            }
        """)
        self.start_restore_button.clicked.connect(self._on_start_restore_clicked)
        button_layout.addWidget(self.start_restore_button)

        button_layout.addStretch()

        layout.addWidget(button_container)

        return panel

    def _create_recovery_mode_group(self) -> QGroupBox:
        """
        Create the Recovery Mode options group.

        Returns:
            QGroupBox with recovery mode controls
        """
        group = QGroupBox("Recovery Mode")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #4ec9b0;
            }
        """)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(15, 20, 15, 15)
        layout.setSpacing(12)

        # Button group for radio buttons
        self.mode_button_group = QButtonGroup(self)

        # Fixed Passes option
        fixed_container = QWidget()
        fixed_layout = QHBoxLayout(fixed_container)
        fixed_layout.setContentsMargins(0, 0, 0, 0)
        fixed_layout.setSpacing(10)

        self.fixed_passes_radio = QRadioButton("Fixed Passes")
        self.fixed_passes_radio.setChecked(True)
        self.fixed_passes_radio.setStyleSheet("""
            QRadioButton {
                color: #ffffff;
                font-size: 10pt;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #5c5c5c;
                border-radius: 9px;
                background-color: #2d2d30;
            }
            QRadioButton::indicator:checked {
                background-color: #0e639c;
                border-color: #0e639c;
            }
            QRadioButton::indicator:checked::after {
                background-color: white;
            }
            QRadioButton::indicator:hover {
                border-color: #858585;
            }
        """)
        self.fixed_passes_radio.toggled.connect(self._on_mode_changed)
        self.mode_button_group.addButton(self.fixed_passes_radio, 0)
        fixed_layout.addWidget(self.fixed_passes_radio)

        self.fixed_passes_spinbox = QSpinBox()
        self.fixed_passes_spinbox.setRange(1, 100)
        self.fixed_passes_spinbox.setValue(5)
        self.fixed_passes_spinbox.setMinimumWidth(100)
        self.fixed_passes_spinbox.setMinimumHeight(40)
        self.fixed_passes_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #5c5c5c;
                border-radius: 4px;
                padding: 6px 8px;
                padding-right: 28px;
                font-size: 10pt;
            }
            QSpinBox:focus {
                border-color: #0e639c;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #4e5157;
                border: none;
                width: 20px;
                subcontrol-origin: border;
            }
            QSpinBox::up-button {
                subcontrol-position: top right;
            }
            QSpinBox::down-button {
                subcontrol-position: bottom right;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #5a5d61;
            }
            QSpinBox::up-arrow {
                width: 8px;
                height: 8px;
            }
            QSpinBox::down-arrow {
                width: 8px;
                height: 8px;
            }
            QSpinBox:disabled {
                background-color: #2d2d30;
                color: #6c6c6c;
                border-color: #3c3c3c;
            }
        """)
        fixed_layout.addWidget(self.fixed_passes_spinbox)

        fixed_layout.addStretch()
        layout.addWidget(fixed_container)

        # Description for fixed passes
        fixed_desc = QLabel("Execute exactly the specified number of recovery passes")
        fixed_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        fixed_desc.setWordWrap(True)
        layout.addWidget(fixed_desc)

        layout.addSpacing(5)

        # Convergence Mode option
        convergence_container = QWidget()
        convergence_layout = QHBoxLayout(convergence_container)
        convergence_layout.setContentsMargins(0, 0, 0, 0)
        convergence_layout.setSpacing(10)

        self.convergence_radio = QRadioButton("Convergence Mode")
        self.convergence_radio.setStyleSheet("""
            QRadioButton {
                color: #ffffff;
                font-size: 10pt;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #5c5c5c;
                border-radius: 9px;
                background-color: #2d2d30;
            }
            QRadioButton::indicator:checked {
                background-color: #0e639c;
                border-color: #0e639c;
            }
            QRadioButton::indicator:hover {
                border-color: #858585;
            }
        """)
        self.convergence_radio.toggled.connect(self._on_mode_changed)
        self.mode_button_group.addButton(self.convergence_radio, 1)
        convergence_layout.addWidget(self.convergence_radio)

        convergence_layout.addStretch()
        layout.addWidget(convergence_container)

        # Max passes for convergence mode
        max_passes_container = QWidget()
        max_passes_layout = QHBoxLayout(max_passes_container)
        max_passes_layout.setContentsMargins(24, 0, 0, 0)
        max_passes_layout.setSpacing(10)

        max_passes_label = QLabel("Max Passes:")
        max_passes_label.setStyleSheet("color: #cccccc; font-size: 10pt;")
        max_passes_layout.addWidget(max_passes_label)

        self.max_passes_spinbox = QSpinBox()
        self.max_passes_spinbox.setRange(5, 200)
        self.max_passes_spinbox.setValue(50)
        self.max_passes_spinbox.setMinimumWidth(100)
        self.max_passes_spinbox.setMinimumHeight(40)
        self.max_passes_spinbox.setEnabled(False)
        self.max_passes_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #5c5c5c;
                border-radius: 4px;
                padding: 6px 8px;
                padding-right: 28px;
                font-size: 10pt;
            }
            QSpinBox:focus {
                border-color: #0e639c;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #4e5157;
                border: none;
                width: 20px;
                subcontrol-origin: border;
            }
            QSpinBox::up-button {
                subcontrol-position: top right;
            }
            QSpinBox::down-button {
                subcontrol-position: bottom right;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #5a5d61;
            }
            QSpinBox::up-arrow {
                width: 8px;
                height: 8px;
            }
            QSpinBox::down-arrow {
                width: 8px;
                height: 8px;
            }
            QSpinBox:disabled {
                background-color: #2d2d30;
                color: #6c6c6c;
                border-color: #3c3c3c;
            }
        """)
        max_passes_layout.addWidget(self.max_passes_spinbox)

        max_passes_layout.addStretch()
        layout.addWidget(max_passes_container)

        # Description for convergence mode
        convergence_desc = QLabel(
            "Continue until bad sector count stabilizes across 3 consecutive passes, "
            "up to the maximum limit"
        )
        convergence_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        convergence_desc.setWordWrap(True)
        convergence_desc.setMinimumHeight(30)  # Ensure space for wrapped text
        layout.addWidget(convergence_desc)

        return group

    def _create_advanced_recovery_group(self) -> QGroupBox:
        """
        Create the Advanced Recovery options group.

        Returns:
            QGroupBox with advanced recovery controls
        """
        group = QGroupBox("Advanced Recovery")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #4ec9b0;
            }
        """)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(15, 20, 15, 15)
        layout.setSpacing(12)

        # Targeted Recovery checkbox
        self.targeted_checkbox = QCheckBox("Targeted Recovery (bad sectors only)")
        self.targeted_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 10pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #5c5c5c;
                border-radius: 3px;
                background-color: #2d2d30;
            }
            QCheckBox::indicator:checked {
                background-color: #0e639c;
                border-color: #0e639c;
            }
            QCheckBox::indicator:hover {
                border-color: #858585;
            }
        """)
        self.targeted_checkbox.toggled.connect(self._on_targeted_toggled)
        layout.addWidget(self.targeted_checkbox)

        # Description for targeted recovery
        targeted_desc = QLabel(
            "Scans first, then ONLY formats tracks with bad sectors. "
            "Faster and preserves data on good tracks."
        )
        targeted_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        targeted_desc.setWordWrap(True)
        targeted_desc.setMinimumHeight(30)  # Ensure space for wrapped text
        layout.addWidget(targeted_desc)

        layout.addSpacing(10)

        # Multi-Read Mode checkbox
        self.multiread_checkbox = QCheckBox("Multi-Read Mode")
        self.multiread_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 10pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #5c5c5c;
                border-radius: 3px;
                background-color: #2d2d30;
            }
            QCheckBox::indicator:checked {
                background-color: #0e639c;
                border-color: #0e639c;
            }
            QCheckBox::indicator:hover {
                border-color: #858585;
            }
        """)
        self.multiread_checkbox.toggled.connect(self._on_multiread_toggled)
        layout.addWidget(self.multiread_checkbox)

        # Multi-read attempts spinbox
        attempts_container = QWidget()
        attempts_layout = QHBoxLayout(attempts_container)
        attempts_layout.setContentsMargins(24, 0, 0, 0)
        attempts_layout.setSpacing(10)

        attempts_label = QLabel("Read Attempts:")
        attempts_label.setStyleSheet("color: #cccccc; font-size: 10pt;")
        attempts_layout.addWidget(attempts_label)

        self.multiread_attempts_spinbox = QSpinBox()
        self.multiread_attempts_spinbox.setRange(10, 1000)
        self.multiread_attempts_spinbox.setValue(100)
        self.multiread_attempts_spinbox.setSingleStep(10)
        self.multiread_attempts_spinbox.setMinimumWidth(110)
        self.multiread_attempts_spinbox.setMinimumHeight(40)
        self.multiread_attempts_spinbox.setEnabled(False)
        self.multiread_attempts_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #5c5c5c;
                border-radius: 4px;
                padding: 6px 8px;
                padding-right: 28px;
                font-size: 10pt;
            }
            QSpinBox:focus {
                border-color: #0e639c;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #4e5157;
                border: none;
                width: 20px;
                subcontrol-origin: border;
            }
            QSpinBox::up-button {
                subcontrol-position: top right;
            }
            QSpinBox::down-button {
                subcontrol-position: bottom right;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #5a5d61;
            }
            QSpinBox::up-arrow {
                width: 8px;
                height: 8px;
            }
            QSpinBox::down-arrow {
                width: 8px;
                height: 8px;
            }
            QSpinBox:disabled {
                background-color: #2d2d30;
                color: #6c6c6c;
                border-color: #3c3c3c;
            }
        """)
        attempts_layout.addWidget(self.multiread_attempts_spinbox)

        attempts_layout.addStretch()
        layout.addWidget(attempts_container)

        # Description for multi-read mode
        multiread_desc = QLabel(
            "Use statistical analysis of multiple reads to recover marginally readable sectors. "
            "Higher attempts increase recovery chance but take longer."
        )
        multiread_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        multiread_desc.setWordWrap(True)
        multiread_desc.setMinimumHeight(40)  # Ensure space for wrapped text
        layout.addWidget(multiread_desc)

        return group

    def _create_report_options_group(self) -> QGroupBox:
        """
        Create the Report Options group.

        Returns:
            QGroupBox with report option controls
        """
        group = QGroupBox("Report Options")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #4ec9b0;
            }
        """)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(15, 20, 15, 15)
        layout.setSpacing(12)

        checkbox_style = """
            QCheckBox {
                color: #ffffff;
                font-size: 10pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #5c5c5c;
                border-radius: 3px;
                background-color: #2d2d30;
            }
            QCheckBox::indicator:checked {
                background-color: #0e639c;
                border-color: #0e639c;
            }
            QCheckBox::indicator:hover {
                border-color: #858585;
            }
        """

        # Detailed Report checkbox
        self.detailed_report_checkbox = QCheckBox("Detailed Report")
        self.detailed_report_checkbox.setChecked(True)
        self.detailed_report_checkbox.setStyleSheet(checkbox_style)
        layout.addWidget(self.detailed_report_checkbox)

        detailed_desc = QLabel("Include per-sector status and error type information")
        detailed_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        detailed_desc.setWordWrap(True)
        layout.addWidget(detailed_desc)

        layout.addSpacing(5)

        # Track Maps checkbox
        self.track_maps_checkbox = QCheckBox("Include Track Maps")
        self.track_maps_checkbox.setStyleSheet(checkbox_style)
        layout.addWidget(self.track_maps_checkbox)

        track_desc = QLabel("Generate ASCII track layout visualizations")
        track_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        track_desc.setWordWrap(True)
        layout.addWidget(track_desc)

        layout.addSpacing(5)

        # Hex Dumps checkbox
        self.hex_dumps_checkbox = QCheckBox("Include Hex Dumps")
        self.hex_dumps_checkbox.setStyleSheet(checkbox_style)
        layout.addWidget(self.hex_dumps_checkbox)

        hex_desc = QLabel("Include hexadecimal dumps of recovered sector data")
        hex_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        hex_desc.setWordWrap(True)
        layout.addWidget(hex_desc)

        layout.addSpacing(5)

        # Save to File checkbox
        self.save_to_file_checkbox = QCheckBox("Save Report to File")
        self.save_to_file_checkbox.setStyleSheet(checkbox_style)
        layout.addWidget(self.save_to_file_checkbox)

        save_desc = QLabel("Automatically save report to disk after completion")
        save_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        save_desc.setWordWrap(True)
        layout.addWidget(save_desc)

        layout.addStretch()

        return group

    def _create_progress_view(self) -> QWidget:
        """
        Create the progress view widget with convergence table.

        Contains circular sector map, convergence history table, progress
        statistics, and control buttons for the restore operation.

        Returns:
            Widget containing progress view elements
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # Title
        self.progress_title_label = QLabel("Restoring Disk")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self.progress_title_label.setFont(title_font)
        self.progress_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_title_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.progress_title_label)

        # Subtitle
        self.progress_subtitle_label = QLabel("Recovery in progress - do not remove the disk")
        self.progress_subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_subtitle_label.setStyleSheet("color: #f0a030; font-size: 10pt;")
        layout.addWidget(self.progress_subtitle_label)

        # Main content area with splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setHandleWidth(8)
        content_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3c3c3c;
            }
            QSplitter::handle:hover {
                background-color: #4e5157;
            }
        """)

        # Left side: Circular sector map
        map_container = QWidget()
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(5)

        map_title = QLabel("Sector Map")
        map_title.setStyleSheet("color: #858585; font-size: 10pt;")
        map_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        map_layout.addWidget(map_title)

        self.sector_map = CircularSectorMap()
        self.sector_map.setMinimumSize(350, 350)
        self.sector_map.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        map_layout.addWidget(self.sector_map, stretch=1)

        content_splitter.addWidget(map_container)

        # Right side: Convergence table and graph in vertical splitter
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Vertical splitter for table (top) and graph (bottom)
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setHandleWidth(6)
        right_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3c3c3c;
            }
            QSplitter::handle:hover {
                background-color: #4e5157;
            }
        """)

        # Top: Convergence table
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(5)

        table_title = QLabel("Convergence History")
        table_title.setStyleSheet("color: #858585; font-size: 10pt;")
        table_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table_layout.addWidget(table_title)

        self.convergence_table = self._create_convergence_table()
        table_layout.addWidget(self.convergence_table, stretch=1)

        right_splitter.addWidget(table_container)

        # Bottom: Convergence graph
        graph_container = QWidget()
        graph_layout = QVBoxLayout(graph_container)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(5)

        graph_title = QLabel("Convergence Trend")
        graph_title.setStyleSheet("color: #858585; font-size: 10pt;")
        graph_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graph_layout.addWidget(graph_title)

        self.convergence_graph = ConvergenceGraphWidget(title="")
        self.convergence_graph.setMinimumHeight(180)
        graph_layout.addWidget(self.convergence_graph, stretch=1)

        right_splitter.addWidget(graph_container)

        # Set initial splitter sizes (55% table, 45% graph)
        right_splitter.setSizes([300, 250])

        right_layout.addWidget(right_splitter)
        content_splitter.addWidget(right_container)

        # Set initial splitter sizes (55% map, 45% table+graph)
        content_splitter.setSizes([550, 450])

        layout.addWidget(content_splitter, stretch=1)

        # Statistics frame
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setSpacing(8)

        # Progress bar row
        progress_container = QWidget()
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(10)

        progress_label = QLabel("Progress:")
        progress_label.setStyleSheet("color: #cccccc; font-size: 11pt;")
        progress_layout.addWidget(progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setMinimumWidth(250)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #3c3c3c;
                border: none;
                border-radius: 4px;
                height: 18px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #0e639c;
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar, stretch=1)

        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setStyleSheet(
            "color: #4ec9b0; font-size: 11pt; font-weight: bold;"
        )
        self.progress_percent_label.setMinimumWidth(45)
        progress_layout.addWidget(self.progress_percent_label)

        stats_layout.addWidget(progress_container)

        # Statistics row 1: Pass, Sectors
        row1_container = QWidget()
        row1_layout = QHBoxLayout(row1_container)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(25)

        # Pass counter
        pass_widget = QWidget()
        pass_layout = QHBoxLayout(pass_widget)
        pass_layout.setContentsMargins(0, 0, 0, 0)
        pass_layout.setSpacing(5)

        pass_icon = QLabel("Pass:")
        pass_icon.setStyleSheet("color: #858585; font-size: 10pt;")
        pass_layout.addWidget(pass_icon)

        self.pass_label = QLabel("0 / 0")
        self.pass_label.setStyleSheet("color: #ffffff; font-size: 10pt;")
        pass_layout.addWidget(self.pass_label)

        row1_layout.addWidget(pass_widget)

        # Sectors counter
        sectors_widget = QWidget()
        sectors_layout = QHBoxLayout(sectors_widget)
        sectors_layout.setContentsMargins(0, 0, 0, 0)
        sectors_layout.setSpacing(5)

        sectors_icon = QLabel("Sectors:")
        sectors_icon.setStyleSheet("color: #858585; font-size: 10pt;")
        sectors_layout.addWidget(sectors_icon)

        self.sectors_label = QLabel("0 / 2880")
        self.sectors_label.setStyleSheet("color: #ffffff; font-size: 10pt;")
        sectors_layout.addWidget(self.sectors_label)

        row1_layout.addWidget(sectors_widget)

        # Bad sectors counter
        bad_widget = QWidget()
        bad_layout = QHBoxLayout(bad_widget)
        bad_layout.setContentsMargins(0, 0, 0, 0)
        bad_layout.setSpacing(5)

        bad_icon = QLabel("Bad Sectors:")
        bad_icon.setStyleSheet("color: #858585; font-size: 10pt;")
        bad_layout.addWidget(bad_icon)

        self.bad_label = QLabel("0")
        self.bad_label.setStyleSheet("color: #4ec9b0; font-size: 10pt; font-weight: bold;")
        bad_layout.addWidget(self.bad_label)

        row1_layout.addWidget(bad_widget)

        # Recovery rate
        rate_widget = QWidget()
        rate_layout = QHBoxLayout(rate_widget)
        rate_layout.setContentsMargins(0, 0, 0, 0)
        rate_layout.setSpacing(5)

        rate_icon = QLabel("Recovered:")
        rate_icon.setStyleSheet("color: #858585; font-size: 10pt;")
        rate_layout.addWidget(rate_icon)

        self.recovery_rate_label = QLabel("0 (0%)")
        self.recovery_rate_label.setStyleSheet(
            "color: #4ec9b0; font-size: 10pt; font-weight: bold;"
        )
        rate_layout.addWidget(self.recovery_rate_label)

        row1_layout.addWidget(rate_widget)

        row1_layout.addStretch()
        stats_layout.addWidget(row1_container)

        # Statistics row 2: Elapsed, ETA, Status
        row2_container = QWidget()
        row2_layout = QHBoxLayout(row2_container)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(25)

        # Elapsed time
        time_widget = QWidget()
        time_layout = QHBoxLayout(time_widget)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(5)

        time_icon = QLabel("Elapsed:")
        time_icon.setStyleSheet("color: #858585; font-size: 10pt;")
        time_layout.addWidget(time_icon)

        self.elapsed_label = QLabel("00:00")
        self.elapsed_label.setStyleSheet("color: #ffffff; font-size: 10pt;")
        time_layout.addWidget(self.elapsed_label)

        row2_layout.addWidget(time_widget)

        # ETA
        eta_widget = QWidget()
        eta_layout = QHBoxLayout(eta_widget)
        eta_layout.setContentsMargins(0, 0, 0, 0)
        eta_layout.setSpacing(5)

        eta_icon = QLabel("ETA:")
        eta_icon.setStyleSheet("color: #858585; font-size: 10pt;")
        eta_layout.addWidget(eta_icon)

        self.eta_label = QLabel("--:--")
        self.eta_label.setStyleSheet("color: #858585; font-size: 10pt;")
        eta_layout.addWidget(self.eta_label)

        row2_layout.addWidget(eta_widget)

        # Status
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(5)

        status_icon = QLabel("Status:")
        status_icon.setStyleSheet("color: #858585; font-size: 10pt;")
        status_layout.addWidget(status_icon)

        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("color: #ffffff; font-size: 10pt;")
        status_layout.addWidget(self.status_label)

        row2_layout.addWidget(status_widget)

        row2_layout.addStretch()
        stats_layout.addWidget(row2_container)

        layout.addWidget(stats_frame)

        # Button container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 8, 0, 0)
        button_layout.setSpacing(12)

        button_layout.addStretch()

        # Cancel button
        self.cancel_progress_button = QPushButton("Cancel")
        self.cancel_progress_button.setMinimumHeight(42)
        self.cancel_progress_button.setMinimumWidth(110)
        self.cancel_progress_button.setFont(QFont("", 11))
        self.cancel_progress_button.setStyleSheet("""
            QPushButton {
                background-color: #5a1d1d;
                color: #ffffff;
                border: 1px solid #8b3333;
                border-radius: 5px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #752525;
                border-color: #a04040;
            }
            QPushButton:pressed {
                background-color: #4a1515;
            }
            QPushButton:disabled {
                background-color: #2d2d30;
                color: #6c6c6c;
                border-color: #3c3c3c;
            }
        """)
        self.cancel_progress_button.clicked.connect(self._on_cancel_progress_clicked)
        button_layout.addWidget(self.cancel_progress_button)

        # View Report button (hidden initially)
        self.view_report_button = QPushButton("View Report")
        self.view_report_button.setMinimumHeight(42)
        self.view_report_button.setMinimumWidth(130)
        self.view_report_button.setFont(QFont("", 11))
        self.view_report_button.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: #ffffff;
                border: none;
                border-radius: 5px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
        """)
        self.view_report_button.clicked.connect(self._on_view_report_clicked)
        self.view_report_button.hide()
        button_layout.addWidget(self.view_report_button)

        # Done button (hidden initially)
        self.done_button = QPushButton("Done")
        self.done_button.setMinimumHeight(42)
        self.done_button.setMinimumWidth(110)
        self.done_button.setFont(QFont("", 11))
        self.done_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3d41;
                color: #ffffff;
                border: 1px solid #6c6c6c;
                border-radius: 5px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #4e5157;
                border-color: #858585;
            }
            QPushButton:pressed {
                background-color: #2d2d30;
            }
        """)
        self.done_button.clicked.connect(self._on_done_clicked)
        self.done_button.hide()
        button_layout.addWidget(self.done_button)

        button_layout.addStretch()

        layout.addWidget(button_container)

        return widget

    def _create_convergence_table(self) -> QTableWidget:
        """
        Create the convergence history table widget.

        Displays pass number, bad sector count, and delta with colored arrows.

        Returns:
            Configured QTableWidget
        """
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Pass #", "Bad Sectors", "Delta"])

        # Configure header
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                border: none;
                border-bottom: 1px solid #3c3c3c;
                border-right: 1px solid #3c3c3c;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 10pt;
            }
        """)

        # Configure table appearance
        table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                gridline-color: #3c3c3c;
                font-size: 10pt;
            }
            QTableWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #2d2d30;
            }
            QTableWidget::item:selected {
                background-color: #094771;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #4e5157;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5a5d61;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        # Hide row numbers
        table.verticalHeader().setVisible(False)

        # Disable editing
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Selection behavior
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        # Set minimum size
        table.setMinimumWidth(200)
        table.setMinimumHeight(150)

        return table

    def add_convergence_row(self, pass_num: int, bad_count: int, previous_count: int) -> None:
        """
        Add a row to the convergence history table.

        Calculates the delta and formats it with colored arrows:
        - Green down arrow for improvement (fewer bad sectors)
        - Yellow right arrow for no change
        - Red up arrow for worse (more bad sectors)

        Args:
            pass_num: Pass number that completed
            bad_count: Bad sector count after this pass
            previous_count: Bad sector count before this pass
        """
        row = self.convergence_table.rowCount()
        self.convergence_table.insertRow(row)

        # Pass number column
        pass_item = QTableWidgetItem(str(pass_num))
        pass_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.convergence_table.setItem(row, 0, pass_item)

        # Bad sectors column
        bad_item = QTableWidgetItem(str(bad_count))
        bad_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.convergence_table.setItem(row, 1, bad_item)

        # Delta column with colored arrow
        delta = previous_count - bad_count

        if pass_num == 1 or previous_count == 0:
            # First pass - no delta to show
            delta_text = "--"
            delta_color = self.COLOR_UNCHANGED
        elif delta > 0:
            # Improved - fewer bad sectors
            delta_text = f"↓ {delta}"
            delta_color = self.COLOR_IMPROVED
        elif delta < 0:
            # Worsened - more bad sectors
            delta_text = f"↑ {abs(delta)}"
            delta_color = self.COLOR_WORSENED
        else:
            # No change
            delta_text = "→ 0"
            delta_color = self.COLOR_UNCHANGED

        delta_item = QTableWidgetItem(delta_text)
        delta_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        delta_item.setForeground(QBrush(delta_color))
        self.convergence_table.setItem(row, 2, delta_item)

        # Scroll to show the new row
        self.convergence_table.scrollToBottom()

    def clear_convergence_table(self) -> None:
        """Clear all rows from the convergence table."""
        self.convergence_table.setRowCount(0)

    def _on_mode_changed(self) -> None:
        """Handle recovery mode radio button change."""
        is_convergence = self.convergence_radio.isChecked()
        self.fixed_passes_spinbox.setEnabled(not is_convergence)
        self.max_passes_spinbox.setEnabled(is_convergence)

    def _on_targeted_toggled(self, checked: bool) -> None:
        """Handle targeted recovery checkbox toggle."""
        # The checkbox is disabled when no bad sectors are known,
        # so this toggle only fires when it's allowed
        pass

    def _on_multiread_toggled(self, checked: bool) -> None:
        """Handle multi-read mode checkbox toggle."""
        self.multiread_attempts_spinbox.setEnabled(checked)

    def _on_cancel_options_clicked(self) -> None:
        """Handle cancel button click on options panel."""
        self.back_requested.emit()

    def _on_start_restore_clicked(self) -> None:
        """Handle start restore button click."""
        settings = self.get_restore_settings()

        # Show confirmation dialog using the dedicated dialog
        if not show_confirm_restore_dialog(
            self,
            self._device_path or "",
            settings,
            self._known_bad_sectors
        ):
            return

        # Start the restore operation
        self.start_restore()

    def set_device(self, device_path: str, geometry: DiskGeometry) -> None:
        """
        Set the device to restore.

        Args:
            device_path: Path to the device (e.g., '/dev/sde')
            geometry: Disk geometry information
        """
        self._device_path = device_path
        self._geometry = geometry
        self._restore_completed_flag = False
        self._total_sectors = geometry.total_sectors

        # Update device label
        self.device_label.setText(
            f"Device: {device_path} | {geometry.cylinders}C/{geometry.heads}H/"
            f"{geometry.sectors_per_track}S = {self._total_sectors} sectors"
        )

    def set_bad_sectors(self, bad_sector_list: List[int]) -> None:
        """
        Set the list of known bad sectors from a previous scan.

        This is optional - targeted mode will do its own initial scan
        if no bad sectors are provided.

        Args:
            bad_sector_list: List of sector numbers identified as bad
        """
        self._known_bad_sectors = list(bad_sector_list)

    def get_restore_settings(self) -> Dict[str, Any]:
        """
        Get the current restore configuration settings.

        Returns:
            Dictionary containing all restore settings
        """
        is_convergence = self.convergence_radio.isChecked()

        # For targeted mode, pass known bad sectors if available (optional optimization)
        # If None, targeted recovery will do its own initial scan
        bad_sector_list = None
        if self.targeted_checkbox.isChecked() and self._known_bad_sectors:
            bad_sector_list = self._known_bad_sectors.copy()

        return {
            "convergence_mode": is_convergence,
            "passes": (
                self.max_passes_spinbox.value()
                if is_convergence
                else self.fixed_passes_spinbox.value()
            ),
            "convergence_threshold": 3,
            "targeted_mode": self.targeted_checkbox.isChecked(),
            "bad_sector_list": bad_sector_list,
            "multiread_mode": self.multiread_checkbox.isChecked(),
            "multiread_attempts": self.multiread_attempts_spinbox.value(),
            "report_detailed": self.detailed_report_checkbox.isChecked(),
            "report_track_maps": self.track_maps_checkbox.isChecked(),
            "report_hex_dumps": self.hex_dumps_checkbox.isChecked(),
            "report_save_to_file": self.save_to_file_checkbox.isChecked(),
        }

    def start_restore(self) -> None:
        """
        Start the disk restore operation.

        Opens the device, creates the worker thread, and begins restoration.
        """
        if self._restore_in_progress:
            return

        if not self._device_path or not self._geometry:
            QMessageBox.critical(
                self,
                "Error",
                "No device selected. Please select a device first."
            )
            return

        # Get settings and create config
        settings = self.get_restore_settings()
        self._is_convergence_mode = settings["convergence_mode"]
        self._total_passes = settings["passes"]

        config = RestoreConfig(
            convergence_mode=settings["convergence_mode"],
            passes=settings["passes"],
            convergence_threshold=settings["convergence_threshold"],
            targeted_mode=settings["targeted_mode"],
            bad_sector_list=settings["bad_sector_list"],
            multiread_mode=settings["multiread_mode"],
            multiread_attempts=settings["multiread_attempts"],
        )

        # Reset state
        self._reset_progress_state()

        try:
            # Open device for writing
            self._fd = open_device(self._device_path, read_only=False)
        except OSError as e:
            error_msg = str(e)
            if "read-only" in error_msg.lower() or "permission" in error_msg.lower():
                QMessageBox.critical(
                    self,
                    "Write Protected",
                    f"Cannot restore disk - it may be write-protected:\n\n{error_msg}"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Device Error",
                    f"Failed to open device for writing:\n\n{error_msg}"
                )
            return

        # Create worker and thread
        self._thread = QThread()
        self._worker = RestoreWorker(self._fd, self._geometry, config)
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.initial_scan_completed.connect(self._on_initial_scan_completed)
        self._worker.initial_scan_sector.connect(self._on_initial_scan_sector)
        self._worker.progress_updated.connect(self._on_progress_updated)
        self._worker.pass_completed.connect(self._on_pass_completed)
        self._worker.restore_completed.connect(self._on_restore_completed)
        self._worker.operation_failed.connect(self._on_restore_failed)
        self._worker.finished.connect(self._on_worker_finished)

        # Start timing
        self._elapsed_timer.start()
        self._update_timer.start(1000)

        # Update UI
        self.progress_title_label.setText("Restoring Disk...")
        self.progress_subtitle_label.setText("Recovery in progress - do not remove the disk")
        self.progress_subtitle_label.setStyleSheet("color: #f0a030; font-size: 10pt;")

        # Switch to progress view
        self.stacked_widget.setCurrentIndex(self.PHASE_PROGRESS)

        # Start restore
        self._restore_in_progress = True
        self._thread.start()

    def _reset_progress_state(self) -> None:
        """Reset widget state for a new restore operation."""
        self._restore_result = None
        self._restore_completed_flag = False
        self._convergence_history = []
        self._current_pass = 0
        self._previous_bad_count = 0
        self._initial_bad_count = 0
        self._current_bad_count = 0
        self._current_sector = 0

        # Reset UI
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #3c3c3c;
                border: none;
                border-radius: 4px;
                height: 18px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #0e639c;
                border-radius: 4px;
            }
        """)
        self.progress_percent_label.setText("0%")

        if self._is_convergence_mode:
            self.pass_label.setText("0 (Convergence)")
        else:
            self.pass_label.setText(f"0 / {self._total_passes}")

        self.sectors_label.setText(f"0 / {self._total_sectors}")
        self.bad_label.setText("0")
        self.bad_label.setStyleSheet("color: #4ec9b0; font-size: 10pt; font-weight: bold;")
        self.recovery_rate_label.setText("0 (0%)")
        self.recovery_rate_label.setStyleSheet(
            "color: #4ec9b0; font-size: 10pt; font-weight: bold;"
        )
        self.elapsed_label.setText("00:00")
        self.eta_label.setText("--:--")
        self.status_label.setText("Initializing...")
        self.status_label.setStyleSheet("color: #ffffff; font-size: 10pt;")

        # Reset sector map
        self.sector_map.reset_all_sectors()

        # Clear convergence table and graph
        self.clear_convergence_table()
        self.convergence_graph.clear()

        # Reset buttons
        self.cancel_progress_button.setEnabled(True)
        self.cancel_progress_button.show()
        self.view_report_button.hide()
        self.done_button.hide()

    def _on_progress_updated(
        self,
        pass_num: int,
        total_passes: int,
        current_sector: int,
        total_sectors: int,
        bad_count: int,
        converged: bool
    ) -> None:
        """
        Handle restore progress update.

        Handles special pass_num values:
        - pass_num == -1: Initial scan phase
        - pass_num == -2: Pass completion notification (handled by pass_completed)
        - pass_num >= 0: Active recovery pass

        Args:
            pass_num: Current pass number (-1 for initial scan, -2 for pass completion)
            total_passes: Total number of passes
            current_sector: Current sector being processed
            total_sectors: Total sectors
            bad_count: Current bad sector count
            converged: Whether convergence has been detected
        """
        self._current_sector = current_sector
        self._total_sectors = total_sectors
        self._current_bad_count = bad_count
        self._total_passes = total_passes

        if pass_num == -1:
            # Initial scan phase
            self.status_label.setText("Initial Scan...")
            self.status_label.setStyleSheet("color: #dcdcaa; font-size: 10pt;")

            # Update pass label for initial scan
            self.pass_label.setText("Scanning...")

            # Calculate progress for initial scan
            percent = (current_sector / total_sectors * 100) if total_sectors > 0 else 0

            # NOTE: Don't mark sectors as recovering here!
            # The _on_initial_scan_sector handler receives the actual good/bad status
            # and updates the sector map with the correct color. If we mark as
            # recovering here, it overwrites the correct status since this handler
            # runs after _on_initial_scan_sector.

        elif pass_num == -2:
            # Pass completion notification - handled by _on_pass_completed
            # This shouldn't normally reach here as it's intercepted by RestoreWorker
            return

        else:
            # Active recovery pass
            self._current_pass = pass_num + 1

            if self._is_convergence_mode:
                if converged:
                    self.pass_label.setText(f"{self._current_pass} (Converged!)")
                    self.status_label.setText("Converged!")
                    self.status_label.setStyleSheet(
                        "color: #4ec9b0; font-size: 10pt; font-weight: bold;"
                    )
                else:
                    self.pass_label.setText(f"{self._current_pass} (Convergence)")
                    self.status_label.setText(f"Pass {self._current_pass} - Recovering...")
                    self.status_label.setStyleSheet("color: #ffffff; font-size: 10pt;")
            else:
                self.pass_label.setText(f"{self._current_pass} / {total_passes}")
                self.status_label.setText(f"Pass {self._current_pass} - Recovering...")
                self.status_label.setStyleSheet("color: #ffffff; font-size: 10pt;")

            # Calculate progress within current pass
            percent = (current_sector / total_sectors * 100) if total_sectors > 0 else 0

            # Update sector map for active recovery
            valid_range = current_sector >= 0 and current_sector < total_sectors
            if valid_range and self._geometry is not None:
                spt = self._geometry.sectors_per_track

                # The worker reports track-level progress as multiples of sectors_per_track
                # (current_sector = (track_index + 1) * sectors_per_track). Highlight all
                # sectors within the current track to give a ring-like visual during format.
                if spt > 0 and current_sector % spt == 0:
                    track_index = (current_sector // spt) - 1
                    if track_index >= 0:
                        start_sector = track_index * spt
                        for sec in range(start_sector, start_sector + spt):
                            self.sector_map.mark_sector_recovering(sec)
                else:
                    # Fallback: treat current_sector as 1-based sector number
                    sector_idx = current_sector - 1 if current_sector > 0 else 0
                    self.sector_map.mark_sector_recovering(sector_idx)

        # Update progress bar
        self.progress_bar.setValue(int(percent))
        self.progress_percent_label.setText(f"{percent:.0f}%")

        # Update sectors label
        self.sectors_label.setText(f"{current_sector} / {total_sectors}")

        # Update bad sector count
        self.bad_label.setText(str(bad_count))
        if bad_count > 0:
            self.bad_label.setStyleSheet("color: #f14c4c; font-size: 10pt; font-weight: bold;")
        else:
            self.bad_label.setStyleSheet("color: #4ec9b0; font-size: 10pt; font-weight: bold;")

        # Update recovery rate
        self._update_recovery_rate()

        # Update ETA
        self._update_eta()

    def _on_pass_completed(self, pass_num: int, bad_count: int, previous_count: int) -> None:
        """
        Handle completion of a recovery pass.

        Args:
            pass_num: Pass number that completed
            bad_count: Bad sector count after this pass
            previous_count: Bad sector count before this pass
        """
        # Store initial bad count from first pass if we don't already have it
        if self._initial_bad_count == 0:
            # Prefer previous_count if provided; otherwise fall back to stored previous
            if previous_count and previous_count > 0:
                self._initial_bad_count = previous_count
            elif self._previous_bad_count and self._previous_bad_count > 0:
                self._initial_bad_count = self._previous_bad_count
            else:
                # As a last resort, use bad_count (may be post-pass)
                self._initial_bad_count = bad_count

        # Calculate delta
        delta = previous_count - bad_count
        direction = "improved" if delta > 0 else ("unchanged" if delta == 0 else "worsened")

        # Record in convergence history
        self._convergence_history.append({
            "pass": pass_num,
            "bad_count": bad_count,
            "previous_count": previous_count,
            "delta": delta,
            "direction": direction,
        })

        # Keep current/previous counts up to date
        self._previous_bad_count = bad_count
        self._current_bad_count = bad_count

        # Add row to convergence table
        self.add_convergence_row(pass_num, bad_count, previous_count)

        # Add data point to convergence graph
        self.convergence_graph.add_data_point(pass_num, bad_count)

        # Update recovery rate
        self._update_recovery_rate()

    def _on_initial_scan_completed(self, initial_count: int) -> None:
        """Handle initial scan completion and store counts for recovery metrics."""
        self._initial_bad_count = initial_count
        self._previous_bad_count = initial_count
        self._current_bad_count = initial_count

        # Update UI immediately
        self.bad_label.setText(str(initial_count))
        if initial_count > 0:
            self.bad_label.setStyleSheet("color: #f14c4c; font-size: 10pt; font-weight: bold;")
        else:
            self.bad_label.setStyleSheet("color: #4ec9b0; font-size: 10pt; font-weight: bold;")

        self._update_recovery_rate()

    def _on_initial_scan_sector(self, sector_index: int, is_good: bool) -> None:
        """Handle individual sector results during initial scan."""
        # Safely update the sector visualization
        try:
            # sector_index is 0-based from the worker
            self.sector_map.update_sector(sector_index, is_good, animate=False)
        except Exception:
            pass

    def _update_recovery_rate(self) -> None:
        """Update the recovery rate display."""
        if self._initial_bad_count > 0:
            recovered = self._initial_bad_count - self._current_bad_count
            rate = (recovered / self._initial_bad_count * 100) if self._initial_bad_count > 0 else 0

            if recovered >= 0:
                self.recovery_rate_label.setText(f"{recovered} ({rate:.0f}%)")
                if rate > 0:
                    self.recovery_rate_label.setStyleSheet(
                        "color: #4ec9b0; font-size: 10pt; font-weight: bold;"
                    )
                else:
                    self.recovery_rate_label.setStyleSheet(
                        "color: #dcdcaa; font-size: 10pt; font-weight: bold;"
                    )
            else:
                # More bad sectors now than initially (shouldn't happen normally)
                self.recovery_rate_label.setText(f"{recovered} ({rate:.0f}%)")
                self.recovery_rate_label.setStyleSheet(
                    "color: #f14c4c; font-size: 10pt; font-weight: bold;"
                )
        else:
            self.recovery_rate_label.setText("0 (0%)")
            self.recovery_rate_label.setStyleSheet(
                "color: #4ec9b0; font-size: 10pt; font-weight: bold;"
            )

    def _update_eta(self) -> None:
        """Update the estimated time remaining."""
        if not self._elapsed_timer.isValid():
            self.eta_label.setText("--:--")
            return

        elapsed_ms = self._elapsed_timer.elapsed()
        if elapsed_ms < 2000:  # Need at least 2 seconds of data
            self.eta_label.setText("--:--")
            return

        if self._is_convergence_mode:
            # For convergence mode, ETA is harder to estimate
            if self._current_pass > 0 and len(self._convergence_history) > 0:
                avg_pass_time = elapsed_ms / self._current_pass
                # Estimate 3 more passes minimum for convergence
                remaining_ms = avg_pass_time * 3
                remaining_secs = int(remaining_ms / 1000)
                minutes = remaining_secs // 60
                seconds = remaining_secs % 60
                self.eta_label.setText(f"~{minutes:02d}:{seconds:02d}")
                self.eta_label.setStyleSheet("color: #858585; font-size: 10pt;")
            else:
                self.eta_label.setText("Estimating...")
                self.eta_label.setStyleSheet("color: #858585; font-size: 10pt;")
        else:
            # Fixed mode - more accurate ETA
            if self._current_pass > 0:
                avg_pass_time = elapsed_ms / self._current_pass
                remaining_passes = self._total_passes - self._current_pass
                remaining_ms = avg_pass_time * remaining_passes
                remaining_secs = int(remaining_ms / 1000)
                minutes = remaining_secs // 60
                seconds = remaining_secs % 60
                self.eta_label.setText(f"{minutes:02d}:{seconds:02d}")
                self.eta_label.setStyleSheet("color: #ffffff; font-size: 10pt;")
            else:
                self.eta_label.setText("--:--")
                self.eta_label.setStyleSheet("color: #858585; font-size: 10pt;")

    def _on_restore_completed(self, stats) -> None:
        """
        Handle restore completion.

        Args:
            stats: RecoveryStatistics from the restore operation
        """
        self._restore_result = stats
        self._restore_completed_flag = True
        self._restore_in_progress = False

        # Stop timer
        self._update_timer.stop()

        # Get final counts from stats
        initial_bad = getattr(stats, 'initial_bad_sector_count', self._initial_bad_count)
        converged = getattr(stats, 'converged', False)

        # Update sector map with final status
        bad_sector_list = getattr(stats, 'bad_sector_list', [])
        if bad_sector_list:
            for sector in range(self._total_sectors):
                if sector in bad_sector_list:
                    self.sector_map.update_sector(sector, False, animate=False)
                else:
                    self.sector_map.update_sector(sector, True, animate=False)

        # If nothing was bad initially, inform the user and show completion
        if initial_bad == 0:
            QMessageBox.information(
                self,
                "No Bad Sectors",
                "Initial scan found no bad sectors; nothing to restore."
            )

        self._show_completion_ui(stats, converged)

        # Emit completion signal
        self.restore_completed.emit(stats)

    def _on_restore_failed(self, error_message: str) -> None:
        """
        Handle restore failure.

        Args:
            error_message: Description of the error
        """
        self._restore_in_progress = False
        self._update_timer.stop()

        # Close device
        self._cleanup_device()

        # Determine error type
        if "disconnected" in error_message.lower() or "removed" in error_message.lower():
            title = "Device Disconnected"
            message = f"The disk was disconnected during the restore operation:\n\n{error_message}"
        elif "permission" in error_message.lower():
            title = "Permission Denied"
            message = f"Insufficient permissions to complete the restore:\n\n{error_message}"
        elif "write" in error_message.lower() or "read-only" in error_message.lower():
            title = "Write Error"
            message = f"Failed to write to the disk:\n\n{error_message}"
        else:
            title = "Restore Failed"
            message = f"The disk restore failed:\n\n{error_message}"

        QMessageBox.critical(self, title, message)

        # Update UI
        self.progress_title_label.setText("Restore Failed")
        self.progress_subtitle_label.setText("The restore operation did not complete successfully")
        self.progress_subtitle_label.setStyleSheet("color: #f14c4c; font-size: 10pt;")
        self.status_label.setText("Error")
        self.status_label.setStyleSheet("color: #f14c4c; font-size: 10pt; font-weight: bold;")

        # Show done button
        self.cancel_progress_button.hide()
        self.done_button.show()
        self.done_button.setText("Back")

    def _on_worker_finished(self) -> None:
        """Handle worker thread completion."""
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
            self._thread.deleteLater()
            self._thread = None

        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

        self._cleanup_device()

    def _cleanup_device(self) -> None:
        """Close the device if open."""
        if self._fd is not None:
            try:
                close_device(self._fd)
            except Exception:
                pass
            self._fd = None

    def _show_completion_ui(self, stats, converged: bool) -> None:
        """
        Update UI to show restore completion state.

        Args:
            stats: RecoveryStatistics from the operation
            converged: Whether convergence was achieved
        """
        # Update progress to 100%
        self.progress_bar.setValue(100)
        self.progress_percent_label.setText("100%")
        self.sectors_label.setText(f"{self._total_sectors} / {self._total_sectors}")
        self.eta_label.setText("Complete")
        self.eta_label.setStyleSheet("color: #4ec9b0; font-size: 10pt;")

        # Get final counts
        final_bad = getattr(stats, 'final_bad_sector_count', self._current_bad_count)
        initial_bad = getattr(stats, 'initial_bad_sector_count', self._initial_bad_count)
        recovered = initial_bad - final_bad if initial_bad > 0 else 0

        # Update title based on result
        if final_bad == 0:
            self.progress_title_label.setText("Restore Complete")
            self.progress_subtitle_label.setText("All sectors recovered successfully!")
            self.progress_subtitle_label.setStyleSheet("color: #4ec9b0; font-size: 10pt;")
            self.status_label.setText("Complete - All Recovered!")
            self.status_label.setStyleSheet("color: #4ec9b0; font-size: 10pt; font-weight: bold;")
        elif recovered > 0:
            if converged:
                self.progress_title_label.setText("Restore Complete (Converged)")
            else:
                self.progress_title_label.setText("Restore Complete (Partial)")
            self.progress_subtitle_label.setText(
                f"Recovered {recovered} sectors, {final_bad} remain unrecoverable"
            )
            self.progress_subtitle_label.setStyleSheet("color: #f0a030; font-size: 10pt;")
            if converged:
                self.status_label.setText("Converged!")
            else:
                self.status_label.setText("Complete")
            self.status_label.setStyleSheet("color: #dcdcaa; font-size: 10pt; font-weight: bold;")
        else:
            self.progress_title_label.setText("Restore Complete")
            if final_bad > 0:
                self.progress_subtitle_label.setText(f"{final_bad} sectors could not be recovered")
                self.progress_subtitle_label.setStyleSheet("color: #f14c4c; font-size: 10pt;")
            else:
                self.progress_subtitle_label.setText("No bad sectors to recover")
                self.progress_subtitle_label.setStyleSheet("color: #4ec9b0; font-size: 10pt;")
            self.status_label.setText("Complete")
            self.status_label.setStyleSheet("color: #ffffff; font-size: 10pt;")

        # Show completion buttons
        self.cancel_progress_button.hide()
        self.view_report_button.show()
        self.done_button.show()

        # Update progress bar color
        if final_bad == 0:
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    background-color: #3c3c3c;
                    border: none;
                    border-radius: 4px;
                    height: 18px;
                    text-align: center;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background-color: #107c10;
                    border-radius: 4px;
                }
            """)
        elif recovered > 0:
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    background-color: #3c3c3c;
                    border: none;
                    border-radius: 4px;
                    height: 18px;
                    text-align: center;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background-color: #f0a030;
                    border-radius: 4px;
                }
            """)

        # Highlight convergence graph if converged or fully recovered
        if converged or final_bad == 0:
            self.convergence_graph.highlight_convergence(True)

    def _update_elapsed_time(self) -> None:
        """Update the elapsed time display."""
        elapsed_ms = self._elapsed_timer.elapsed()
        elapsed_secs = elapsed_ms // 1000
        minutes = elapsed_secs // 60
        seconds = elapsed_secs % 60
        self.elapsed_label.setText(f"{minutes:02d}:{seconds:02d}")

        # Also update ETA periodically
        self._update_eta()

    def _on_cancel_progress_clicked(self) -> None:
        """Handle cancel button click during restore."""
        if not self._restore_in_progress:
            self._switch_to_options()
            return

        if show_confirm_cancel_dialog(self, "restore"):
            self._cancel_restore()

    def _cancel_restore(self) -> None:
        """Cancel the current restore operation."""
        if self._worker is not None:
            self._worker.cancel()

        self._restore_in_progress = False
        self._update_timer.stop()

        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)

        self._cleanup_device()

        QMessageBox.information(
            self,
            "Restore Cancelled",
            "The restore operation was cancelled.\n\n"
            "Partial recovery may have occurred."
        )

        self.restore_cancelled.emit()

    def _on_view_report_clicked(self) -> None:
        """Handle View Report button click."""
        if self._restore_result is not None:
            self.view_report_requested.emit(self._restore_result)

    def _on_done_clicked(self) -> None:
        """Handle Done button click."""
        self.back_requested.emit()

    def _switch_to_options(self) -> None:
        """Switch back to the options panel."""
        self.stacked_widget.setCurrentIndex(self.PHASE_OPTIONS)

    def show_options_panel(self) -> None:
        """Switch to show the options panel."""
        self.stacked_widget.setCurrentIndex(self.PHASE_OPTIONS)

    def show_progress_view(self) -> None:
        """Switch to show the progress view."""
        self.stacked_widget.setCurrentIndex(self.PHASE_PROGRESS)

    def is_restore_in_progress(self) -> bool:
        """Check if a restore is currently in progress."""
        return self._restore_in_progress

    def get_restore_result(self):
        """Get the restore result."""
        return self._restore_result

    def get_convergence_history(self) -> List[Dict[str, Any]]:
        """Get the convergence history from the restore."""
        return self._convergence_history.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get restore statistics."""
        elapsed_ms = self._elapsed_timer.elapsed() if self._elapsed_timer.isValid() else 0
        settings = self.get_restore_settings()

        return {
            "device_path": self._device_path,
            "elapsed_ms": elapsed_ms,
            "passes_executed": self._current_pass,
            "initial_bad_count": self._initial_bad_count,
            "final_bad_count": self._current_bad_count,
            "convergence_history": self._convergence_history,
            "settings": settings,
            "result": self._restore_result,
        }

    def showEvent(self, event) -> None:
        """Handle widget show event."""
        super().showEvent(event)

        if not self._restore_in_progress and not self._restore_completed_flag:
            self.stacked_widget.setCurrentIndex(self.PHASE_OPTIONS)

    def closeEvent(self, event) -> None:
        """Handle widget close event."""
        if self._restore_in_progress:
            result = QMessageBox.question(
                self,
                "Confirm Close",
                "A restore operation is in progress. Are you sure you want to close?\n\n"
                "The restore will be cancelled and partial recovery may have occurred.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if result != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

            self._cancel_restore()

        self._cleanup_device()
        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        """Handle widget hide event."""
        super().hideEvent(event)
