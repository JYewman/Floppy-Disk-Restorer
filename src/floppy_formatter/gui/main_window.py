"""
Main window for Floppy Workbench GUI.

Provides a single-page professional workbench interface with:
- Top panel: Drive controls and operation toolbar
- Center panel: Live visualization (sector map with toolbar and info panel)
- Bottom panel: Tabbed analytics/diagnostics (AnalyticsPanel)

Phase 5: Workbench GUI - Main Layout
Phase 6: Enhanced Sector Map Visualization (integrated)
Phase 7: Analytics Dashboard (integrated)
"""

import sys
import logging
from pathlib import Path
from typing import Optional
from enum import Enum, auto

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QFrame,
    QApplication,
    QMessageBox,
    QMenuBar,
    QMenu,
    QToolBar,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize, QTimer, QUrl, QThread
from PyQt6.QtGui import QIcon, QAction, QKeySequence, QDesktopServices, QShortcut

from floppy_formatter.gui.panels import (
    DriveControlPanel,
    OperationToolbar,
    StatusStrip,
    OperationState,
    AnalyticsPanel,
)
from floppy_formatter.gui.widgets import (
    CircularSectorMap,
    SectorMapToolbar,
    SectorInfoPanel,
    SectorStatus,
    ViewMode,
    ActivityType,
)
from floppy_formatter.gui.dialogs import (
    show_about_dialog,
    show_settings_dialog,
)
from floppy_formatter.gui.resources import get_icon, get_theme, set_theme
from floppy_formatter.gui.utils import (
    fade_in_widget,
    fade_out_widget,
    animations_enabled,
    play_complete_sound,
    play_error_sound,
    play_success_sound,
)
from floppy_formatter.core.geometry import DiskGeometry
from floppy_formatter.hardware import GreaseweazleDevice, read_track_flux
from floppy_formatter.gui.workers.scan_worker import ScanWorker, ScanMode, ScanResult, TrackResult
from floppy_formatter.gui.workers.format_worker import FormatWorker, FormatType, FormatResult
from floppy_formatter.gui.workers.restore_worker import RestoreWorker, RestoreConfig, RecoveryLevel, RecoveryStats
from floppy_formatter.gui.workers.analyze_worker import (
    AnalyzeWorker, AnalysisConfig, AnalysisDepth, AnalysisComponent, DiskAnalysisResult
)
from floppy_formatter.gui.workers.flux_capture_worker import FluxCaptureWorker, CaptureConfig, FluxSample
from floppy_formatter.analysis.flux_analyzer import FluxCapture

logger = logging.getLogger(__name__)


class WorkbenchState(Enum):
    """Overall workbench state."""
    IDLE = auto()
    SCANNING = auto()
    FORMATTING = auto()
    RESTORING = auto()
    ANALYZING = auto()


class ThemeManager:
    """
    Manages application themes and stylesheets.

    Handles loading QSS files, applying themes to the application,
    and switching between different themes.
    """

    THEMES = {
        "dark": "dark_theme.qss",
        "light": "light_theme.qss",
    }

    def __init__(self, app: QApplication):
        """
        Initialize theme manager.

        Args:
            app: QApplication instance to apply themes to
        """
        self.app = app
        self.current_theme = "dark"
        self.styles_dir = Path(__file__).parent / "styles"

    def load_stylesheet(self, theme_name: str) -> str:
        """
        Load stylesheet from file.

        Args:
            theme_name: Name of the theme (e.g., "dark", "light")

        Returns:
            Stylesheet content as string

        Raises:
            FileNotFoundError: If stylesheet file doesn't exist
            KeyError: If theme name is not registered
        """
        if theme_name not in self.THEMES:
            raise KeyError(f"Theme '{theme_name}' not found. Available themes: {list(self.THEMES.keys())}")

        stylesheet_file = self.styles_dir / self.THEMES[theme_name]

        if not stylesheet_file.exists():
            # Fallback to dark theme if requested theme not found
            if theme_name != "dark":
                return self.load_stylesheet("dark")
            raise FileNotFoundError(f"Stylesheet file not found: {stylesheet_file}")

        with open(stylesheet_file, "r", encoding="utf-8") as f:
            return f.read()

    def apply_theme(self, theme_name: str) -> None:
        """
        Apply theme to the application.

        Args:
            theme_name: Name of the theme to apply
        """
        try:
            stylesheet = self.load_stylesheet(theme_name)
            self.app.setStyleSheet(stylesheet)
            self.current_theme = theme_name
        except FileNotFoundError:
            logger.warning("Theme file not found, using default styling")
        except Exception as e:
            logger.error("Failed to apply theme: %s", e)

    def switch_theme(self, theme_name: Optional[str] = None) -> None:
        """
        Switch to a different theme.

        If no theme name is provided, toggles between dark and light themes.

        Args:
            theme_name: Optional theme name to switch to
        """
        if theme_name is None:
            theme_name = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme(theme_name)

    def get_current_theme(self) -> str:
        """
        Get the currently active theme name.

        Returns:
            Current theme name
        """
        return self.current_theme


class SectorMapPanel(QWidget):
    """
    Center panel containing the sector map with toolbar and info panel.

    Layout:
    - Top: SectorMapToolbar
    - Center: CircularSectorMap (expandable)
    - Right: SectorInfoPanel (collapsible sidebar)

    Part of Phase 6: Enhanced Sector Map Visualization
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize sector map panel."""
        super().__init__(parent)

        self.setStyleSheet("""
            SectorMapPanel {
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 4px;
            }
        """)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sector map toolbar at top
        self._toolbar = SectorMapToolbar()
        main_layout.addWidget(self._toolbar)

        # Horizontal splitter for map and info panel
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setHandleWidth(3)
        content_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3a3d41;
            }
            QSplitter::handle:hover {
                background-color: #007acc;
            }
        """)

        # Sector map (main content)
        self._sector_map = CircularSectorMap()
        content_splitter.addWidget(self._sector_map)

        # Sector info panel (collapsible sidebar)
        self._info_panel = SectorInfoPanel()
        content_splitter.addWidget(self._info_panel)

        # Set initial sizes (map takes most space)
        content_splitter.setSizes([700, 280])

        # Don't allow info panel to be completely hidden
        content_splitter.setCollapsible(0, False)
        content_splitter.setCollapsible(1, True)

        main_layout.addWidget(content_splitter, 1)

        # Connect toolbar to sector map
        self._toolbar.connect_to_sector_map(self._sector_map)

        # Connect info panel to sector map
        self._info_panel.connect_to_sector_map(self._sector_map)

    def get_sector_map(self) -> CircularSectorMap:
        """Get the sector map widget."""
        return self._sector_map

    def get_toolbar(self) -> SectorMapToolbar:
        """Get the toolbar widget."""
        return self._toolbar

    def get_info_panel(self) -> SectorInfoPanel:
        """Get the info panel widget."""
        return self._info_panel


class MainWindow(QMainWindow):
    """
    Main application window for Floppy Workbench.

    Provides a single-page workbench interface with three main panels:
    - Top: Drive controls and operation toolbar
    - Center: Sector map visualization (expandable)
    - Bottom: Analytics dashboard (resizable)

    Features:
    - Greaseweazle device connection management
    - Motor control and head positioning
    - Operation execution (Scan, Format, Restore, Analyze)
    - Real-time status display
    - Theme management
    """

    # GitHub documentation URL
    GITHUB_URL = "https://github.com/JYewman/Floppy-Disk-Restorer"

    # Application title
    APP_TITLE = "Floppy Workbench"

    def __init__(self):
        """Initialize main window."""
        super().__init__()

        # Window setup
        self.setWindowTitle(self.APP_TITLE)
        self.setMinimumSize(QSize(800, 600))

        # Center window on screen
        self._center_on_screen()

        # Initialize theme manager
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication instance not found. Create QApplication before MainWindow.")

        self.theme_manager = ThemeManager(app)

        # Load saved theme preference
        try:
            saved_theme = get_theme()
            self.theme_manager.apply_theme(saved_theme)
        except Exception as e:
            logger.warning("Failed to load saved theme: %s", e)

        # State tracking
        self._state = WorkbenchState.IDLE
        self._is_fullscreen = False
        self._view_only_mode = False

        # Device reference (shared between panels)
        self._device: Optional[GreaseweazleDevice] = None

        # Geometry for current disk
        self._geometry: Optional[DiskGeometry] = None

        # Scan/operation results
        self._last_scan_result = None
        self._disk_health: Optional[int] = None

        # Worker and thread for background operations
        self._scan_worker: Optional[ScanWorker] = None
        self._scan_thread: Optional[QThread] = None
        self._format_worker: Optional[FormatWorker] = None
        self._format_thread: Optional[QThread] = None
        self._restore_worker: Optional[RestoreWorker] = None
        self._restore_thread: Optional[QThread] = None
        self._analyze_worker: Optional[AnalyzeWorker] = None
        self._analyze_thread: Optional[QThread] = None
        self._flux_capture_worker: Optional[FluxCaptureWorker] = None
        self._flux_capture_thread: Optional[QThread] = None

        # Build UI
        self._init_menu_bar()
        self._init_central_widget()
        self._init_keyboard_shortcuts()

        # Connect panel signals
        self._connect_signals()

        # Initial state
        self._update_state()

    def _center_on_screen(self) -> None:
        """Center the window on the screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return

        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()

        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def _init_menu_bar(self) -> None:
        """Initialize the menu bar."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        self._exit_action = QAction("E&xit", self)
        self._exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        self._exit_action.setStatusTip("Exit the application")
        self._exit_action.triggered.connect(self.close)
        file_menu.addAction(self._exit_action)

        # Tools menu
        tools_menu = menu_bar.addMenu("&Tools")

        self._settings_action = QAction("Se&ttings...", self)
        self._settings_action.setStatusTip("Configure application settings")
        settings_icon = get_icon("settings")
        if not settings_icon.isNull():
            self._settings_action.setIcon(settings_icon)
        self._settings_action.triggered.connect(self._on_settings_clicked)
        tools_menu.addAction(self._settings_action)

        # View menu
        view_menu = menu_bar.addMenu("&View")

        self._toggle_theme_action = QAction("Toggle &Dark Mode", self)
        self._toggle_theme_action.setShortcut(QKeySequence("Ctrl+D"))
        self._toggle_theme_action.setStatusTip("Switch between dark and light themes")
        self._toggle_theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(self._toggle_theme_action)

        self._fullscreen_action = QAction("&Full Screen", self)
        self._fullscreen_action.setShortcut(QKeySequence("F11"))
        self._fullscreen_action.setStatusTip("Toggle full screen mode")
        self._fullscreen_action.setCheckable(True)
        self._fullscreen_action.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(self._fullscreen_action)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        self._documentation_action = QAction("&Documentation", self)
        self._documentation_action.setStatusTip("Open GitHub documentation in browser")
        self._documentation_action.triggered.connect(self._open_documentation)
        help_menu.addAction(self._documentation_action)

        help_menu.addSeparator()

        self._about_action = QAction("&About", self)
        self._about_action.setStatusTip("About Floppy Workbench")
        info_icon = get_icon("info")
        if not info_icon.isNull():
            self._about_action.setIcon(info_icon)
        self._about_action.triggered.connect(self._on_about_clicked)
        help_menu.addAction(self._about_action)

    def _init_central_widget(self) -> None:
        """Initialize the central widget with three-panel layout."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main vertical layout - compact
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        # Top panel - two rows of controls
        top_panel = self._create_top_panel()
        top_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_panel.setMaximumHeight(100)
        main_layout.addWidget(top_panel)

        # Center and bottom panels with splitter
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3a3d41;
            }
            QSplitter::handle:hover {
                background-color: #007acc;
            }
        """)

        # Center panel with sector map (expandable)
        self._sector_map_panel = SectorMapPanel()
        self._sector_map_panel.setMinimumHeight(150)
        splitter.addWidget(self._sector_map_panel)

        # Keep reference to sector map for convenience
        self._sector_map = self._sector_map_panel.get_sector_map()

        # Bottom panel (analytics dashboard)
        self._analytics_panel = AnalyticsPanel()
        self._analytics_panel.setMinimumHeight(180)
        splitter.addWidget(self._analytics_panel)

        # Set initial sizes (60% center, 40% bottom)
        splitter.setSizes([400, 280])

        main_layout.addWidget(splitter, 1)  # Stretch factor 1

        # Status strip (fixed height at bottom)
        self._status_strip = StatusStrip()
        main_layout.addWidget(self._status_strip)

    def _create_top_panel(self) -> QWidget:
        """Create the top panel with two rows: drive controls and operation toolbar."""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #2d2d30;
                border: 1px solid #3a3d41;
                border-radius: 3px;
            }
        """)

        # Vertical layout for two rows
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Row 1: Drive control panel
        self._drive_control = DriveControlPanel()
        layout.addWidget(self._drive_control)

        # Horizontal separator between rows
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("QFrame { color: #3a3d41; }")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # Row 2: Operation toolbar
        self._operation_toolbar = OperationToolbar()
        layout.addWidget(self._operation_toolbar)

        return panel

    def _connect_signals(self) -> None:
        """Connect signals between panels."""
        # Drive control signals
        self._drive_control.connected.connect(self._on_device_connected)
        self._drive_control.disconnected.connect(self._on_device_disconnected)
        self._drive_control.motor_changed.connect(self._on_motor_changed)
        self._drive_control.position_changed.connect(self._on_position_changed)
        self._drive_control.calibration_complete.connect(self._on_calibration_complete)
        self._drive_control.error_occurred.connect(self._on_error)
        self._drive_control.rpm_updated.connect(self._on_rpm_updated)

        # Operation toolbar signals
        self._operation_toolbar.operation_requested.connect(self._on_operation_requested)
        self._operation_toolbar.mode_changed.connect(self._on_mode_changed)
        self._operation_toolbar.start_clicked.connect(self._on_start_clicked)
        self._operation_toolbar.stop_clicked.connect(self._on_stop_clicked)
        self._operation_toolbar.pause_clicked.connect(self._on_pause_clicked)

        # Sector map signals
        sector_map = self._sector_map_panel.get_sector_map()
        sector_map.selection_changed.connect(self._on_selection_changed)
        sector_map.sector_clicked.connect(self._on_sector_clicked)

        # Analytics panel signals
        self._analytics_panel.tab_changed.connect(self._on_analytics_tab_changed)
        self._analytics_panel.recommendation_action.connect(self._on_recommendation_action)
        self._analytics_panel.sector_selected.connect(self._on_analytics_sector_selected)
        self._analytics_panel.load_flux_requested.connect(self._on_load_flux_requested)
        self._analytics_panel.capture_flux_requested.connect(self._on_capture_flux_requested)
        self._analytics_panel.export_flux_requested.connect(self._on_export_flux_requested)
        self._analytics_panel.run_alignment_requested.connect(self._on_run_alignment_requested)
        self._analytics_panel.run_self_test_requested.connect(self._on_run_self_test_requested)

    def _init_keyboard_shortcuts(self) -> None:
        """
        Initialize keyboard shortcuts.

        Available shortcuts:
        - Ctrl+S: Start scan
        - Ctrl+F: Start format
        - Ctrl+R: Start restore
        - Ctrl+A: Analyze
        - Space: Pause/Resume operation
        - Escape: Cancel/stop operation
        - Ctrl+Shift+C: Connect/Disconnect device
        - Ctrl+0: Seek to track 0
        - Ctrl+M: Toggle motor
        - Ctrl+D: Toggle dark/light theme
        - F11: Toggle fullscreen
        """
        # Operation shortcuts
        # Ctrl+S: Start scan
        self._scan_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self._scan_shortcut.activated.connect(self._start_scan_shortcut)

        # Ctrl+F: Start format (Ctrl+Shift+F to avoid conflict with find)
        self._format_shortcut = QShortcut(QKeySequence("Ctrl+Shift+F"), self)
        self._format_shortcut.activated.connect(self._start_format_shortcut)

        # Ctrl+R: Start restore
        self._restore_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self._restore_shortcut.activated.connect(self._start_restore_shortcut)

        # Ctrl+Shift+A: Analyze (Ctrl+A often used for select all)
        self._analyze_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
        self._analyze_shortcut.activated.connect(self._start_analyze_shortcut)

        # Space: Pause/Resume operation
        self._pause_shortcut = QShortcut(QKeySequence("Space"), self)
        self._pause_shortcut.activated.connect(self._toggle_pause)

        # Escape: Stop/cancel operation
        self._escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        self._escape_shortcut.activated.connect(self._on_escape)

        # Device control shortcuts
        # Ctrl+Shift+C: Connect/Disconnect toggle
        self._connect_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        self._connect_shortcut.activated.connect(self._toggle_connection)

        # Ctrl+0: Seek to track 0
        self._track0_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        self._track0_shortcut.activated.connect(self._seek_track0)

        # Ctrl+M: Motor on/off toggle
        self._motor_shortcut = QShortcut(QKeySequence("Ctrl+M"), self)
        self._motor_shortcut.activated.connect(self._toggle_motor)

    def _update_state(self) -> None:
        """Update UI state based on current workbench state."""
        is_idle = self._state == WorkbenchState.IDLE
        is_connected = self._drive_control.is_connected()

        # Enable/disable operation toolbar
        logger.debug("_update_state: is_connected=%s, is_idle=%s, enabling toolbar=%s",
                    is_connected, is_idle, is_connected and is_idle)
        self._operation_toolbar.set_enabled(is_connected and is_idle)

        # Update status strip based on connection
        if is_connected:
            device_info = self._drive_control.get_device_info()
            self._status_strip.set_connection_status(True, device_info)

            # Update drive status - assume disk present when connected
            # (actual disk presence is detected during read operations)
            if self._drive_control.is_motor_on():
                try:
                    rpm = self._drive_control.get_rpm()
                    self._status_strip.set_drive_status("3.5\" HD", rpm, True)
                except Exception:
                    # RPM measurement can fail during spin-up
                    self._status_strip.set_drive_status("3.5\" HD", None, True)
            else:
                self._status_strip.set_drive_status("3.5\" HD", None, True)
        else:
            self._status_strip.set_connection_status(False)
            self._status_strip.set_drive_status(None)

        # Update operation status
        if self._state == WorkbenchState.IDLE:
            self._status_strip.set_idle()

    # =========================================================================
    # Signal Handlers - Device
    # =========================================================================

    def _on_device_connected(self) -> None:
        """Handle device connection."""
        logger.info("Device connected")
        self._device = self._drive_control.get_device()

        # Create default geometry for 3.5" HD (1.44MB)
        self._geometry = DiskGeometry(
            media_type=0x0F,  # 1.44MB 3.5" HD
            cylinders=80,
            heads=2,
            sectors_per_track=18,
            bytes_per_sector=512
        )

        # Update diagnostics tab with drive information
        self._update_drive_info_display()

        self._update_state()

    def _update_drive_info_display(self) -> None:
        """Update the diagnostics tab with drive information."""
        if not self._device:
            self._analytics_panel.update_drive_info(
                firmware="--",
                drive_type="--",
                disk_type="--",
                serial="--"
            )
            return

        try:
            # Get device info from Greaseweazle Unit object
            unit = getattr(self._device, '_unit', None)
            if unit:
                hw_model = getattr(unit, 'hw_model', 'Unknown')
                fw_major = getattr(unit, 'major', '?')
                fw_minor = getattr(unit, 'minor', '?')
                firmware = f"V{hw_model} FW {fw_major}.{fw_minor}"

                # Get serial if available
                serial = getattr(unit, 'serial', None)
                if serial:
                    serial_str = serial[:12] if len(serial) > 12 else serial
                else:
                    serial_str = "N/A"
            else:
                firmware = "Unknown"
                serial_str = "N/A"

            # Update diagnostics tab
            self._analytics_panel.update_drive_info(
                firmware=firmware,
                drive_type="3.5\" Floppy",
                disk_type="HD (1.44MB)",
                serial=serial_str
            )
            logger.debug("Updated drive info display: firmware=%s", firmware)

        except Exception as e:
            logger.warning("Failed to get drive info: %s", e)
            self._analytics_panel.update_drive_info(
                firmware="Error",
                drive_type="3.5\" Floppy",
                disk_type="Unknown",
                serial="--"
            )

    def _on_device_disconnected(self) -> None:
        """Handle device disconnection."""
        logger.info("Device disconnected")
        self._device = None
        self._geometry = None
        self._disk_health = None

        # Stop any running operation
        if self._state != WorkbenchState.IDLE:
            self._state = WorkbenchState.IDLE
            self._operation_toolbar.stop_operation()

        self._status_strip.clear_health()
        self._update_state()

    def _on_motor_changed(self, is_on: bool) -> None:
        """Handle motor state change."""
        logger.debug("Motor changed: %s", "ON" if is_on else "OFF")

        if is_on:
            try:
                rpm = self._drive_control.get_rpm()
                self._status_strip.set_drive_status("3.5\" HD", rpm, True)
            except Exception:
                # RPM measurement can fail during spin-up
                self._status_strip.set_drive_status("3.5\" HD", None, True)
        else:
            # Keep has_disk=True since we don't know if disk was removed
            self._status_strip.set_drive_status("3.5\" HD", None, True)

    def _on_position_changed(self, cylinder: int, head: int) -> None:
        """Handle head position change."""
        logger.debug("Position changed: cyl=%d, head=%d", cylinder, head)

    def _on_calibration_complete(self, success: bool, message: str) -> None:
        """Handle calibration completion."""
        if success:
            self._status_strip.set_success(f"Calibration: {message}")
        else:
            self._status_strip.set_error(f"Calibration failed: {message}")

    def _on_error(self, message: str) -> None:
        """Handle error from panels."""
        logger.error("Panel error: %s", message)
        self._status_strip.set_error(message)

    def _on_rpm_updated(self, rpm: float) -> None:
        """Handle RPM measurement update from drive control."""
        # Send RPM to diagnostics tab for the RPM stability chart
        self._analytics_panel.add_rpm_measurement(rpm)

    # =========================================================================
    # Signal Handlers - Operations
    # =========================================================================

    def _on_operation_requested(self, operation: str) -> None:
        """Handle operation button click."""
        logger.debug("Operation requested: %s", operation)

    def _on_mode_changed(self, mode: str) -> None:
        """Handle operation mode change."""
        logger.debug("Mode changed: %s", mode)

    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        operation = self._operation_toolbar.get_selected_operation()
        if not operation:
            return

        logger.info("Starting operation: %s", operation)

        # Check device is connected
        if not self._device:
            self._status_strip.set_error("No device connected")
            QMessageBox.warning(
                self, "No Device",
                "Please connect to a Greaseweazle device first."
            )
            return

        # Check geometry is set
        if not self._geometry:
            self._status_strip.set_error("No disk geometry")
            QMessageBox.warning(
                self, "No Geometry",
                "Disk geometry not configured."
            )
            return

        # Map operation to state
        state_map = {
            "scan": WorkbenchState.SCANNING,
            "format": WorkbenchState.FORMATTING,
            "restore": WorkbenchState.RESTORING,
            "analyze": WorkbenchState.ANALYZING,
        }

        self._state = state_map.get(operation, WorkbenchState.IDLE)
        self._operation_toolbar.start_operation()
        self._update_state()

        # IMPORTANT: Stop RPM polling to prevent USB communication conflicts
        # The scan/format/restore/analyze workers will be reading from the device
        self._drive_control.pause_rpm_polling()

        # Update status strip and start operation
        if operation == "scan":
            self._status_strip.set_scanning(0, 160)
            self._start_scan_operation()
        elif operation == "format":
            self._status_strip.set_formatting(0, 160)
            self._start_format_operation()
        elif operation == "restore":
            self._status_strip.set_restoring(1, 5, 0, 2880)
            self._start_restore_operation()
        elif operation == "analyze":
            self._status_strip.set_analyzing("flux data")
            self._start_analyze_operation()

    def _start_scan_operation(self) -> None:
        """Start the actual scan operation with worker thread."""
        # Clean up any existing worker
        self._cleanup_scan_worker()

        # Reset sector map to pending state (no animation for instant visual update)
        total_sectors = self._geometry.total_sectors
        for sector in range(total_sectors):
            self._sector_map.set_sector_status(sector, SectorStatus.PENDING, animate=False)
        self._sector_map.scene.update()

        # Create thread and worker
        self._scan_thread = QThread()
        self._scan_worker = ScanWorker(
            device=self._device,
            geometry=self._geometry,
            capture_flux=False,
            mode=ScanMode.STANDARD,
        )
        self._scan_worker.moveToThread(self._scan_thread)

        # Connect worker signals
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.track_scanned.connect(self._on_track_scanned)
        self._scan_worker.sector_status.connect(self._on_sector_status)
        self._scan_worker.scan_complete.connect(self._on_scan_complete)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.finished.connect(self._on_scan_finished)

        # Start the scan
        logger.info("Starting scan worker thread")
        self._scan_thread.start()

    def _cleanup_scan_worker(self) -> None:
        """Clean up scan worker and thread."""
        logger.debug("_cleanup_scan_worker: starting cleanup")
        try:
            if self._scan_worker:
                logger.debug("_cleanup_scan_worker: cancelling worker")
                self._scan_worker.cancel()
                self._scan_worker = None
                logger.debug("_cleanup_scan_worker: worker cancelled and cleared")

            if self._scan_thread:
                logger.debug("_cleanup_scan_worker: cleaning up thread (isRunning=%s)",
                            self._scan_thread.isRunning())
                if self._scan_thread.isRunning():
                    logger.debug("_cleanup_scan_worker: calling thread.quit()")
                    self._scan_thread.quit()
                    logger.debug("_cleanup_scan_worker: calling thread.wait(3000)")
                    if not self._scan_thread.wait(3000):
                        logger.warning("_cleanup_scan_worker: thread did not stop in 3 seconds")
                    else:
                        logger.debug("_cleanup_scan_worker: thread stopped")
                self._scan_thread = None
                logger.debug("_cleanup_scan_worker: thread cleared")
            logger.debug("_cleanup_scan_worker: cleanup complete")
        except Exception as e:
            logger.exception("Error in _cleanup_scan_worker: %s", e)

    def _on_track_scanned(self, cylinder: int, head: int, track_result: TrackResult) -> None:
        """Handle track scan completion."""
        logger.debug("Track scanned: cyl=%d, head=%d, good=%d, bad=%d",
                     cylinder, head, track_result.good_count, track_result.bad_count)

        # Update sector map with track results - disable animation for immediate visual feedback
        for sector_result in track_result.sector_results:
            if sector_result.is_good:
                status = SectorStatus.GOOD
            else:
                status = SectorStatus.BAD
            self._sector_map.set_sector_status(sector_result.linear_sector, status, animate=False)

        # Show activity on current track
        track_number = cylinder * 2 + head
        start_sector = track_number * self._geometry.sectors_per_track
        self._sector_map.set_active_sector(start_sector, ActivityType.READING)

        # Force scene repaint after each track for visual feedback
        self._sector_map.scene.update()

    def _on_sector_status(self, sector_num: int, is_good: bool, error_type: str) -> None:
        """Handle individual sector status update."""
        status = SectorStatus.GOOD if is_good else SectorStatus.BAD
        # Disable animation for immediate visual feedback during scanning
        self._sector_map.set_sector_status(sector_num, status, animate=False)

    def _on_scan_complete(self, result: ScanResult) -> None:
        """Handle scan operation completion."""
        try:
            logger.info("Scan complete: %d good, %d bad sectors",
                        len(result.good_sectors), len(result.bad_sectors))

            # Store result
            self._last_scan_result = result
            logger.debug("Scan result stored")

            # Calculate disk health percentage
            total = result.total_sectors
            good = len(result.good_sectors)
            if total > 0:
                self._disk_health = int((good / total) * 100)
                logger.debug("Setting health to %d%%", self._disk_health)
                self._status_strip.set_health(self._disk_health)
                logger.debug("Health set on status strip")

            # Update status
            if len(result.bad_sectors) == 0 and good > 0:
                logger.debug("All sectors OK")
                self._status_strip.set_success(
                    f"Scan complete: All {total} sectors OK"
                )
                # Sound disabled - was causing crash in Qt multimedia
                # play_success_sound()
            elif good == 0 and len(result.bad_sectors) == 0:
                # No sectors decoded at all - likely flux decode issue
                logger.debug("No sectors decoded")
                self._status_strip.set_warning(
                    f"Scan complete: No sectors decoded (flux read issue?)"
                )
            else:
                logger.debug("Bad sectors found: %d", len(result.bad_sectors))
                self._status_strip.set_warning(
                    f"Scan complete: {len(result.bad_sectors)} bad sectors found"
                )
                # Sound disabled - was causing crash in Qt multimedia
                # try:
                #     play_error_sound()
                # except Exception as sound_err:
                #     logger.warning("Failed to play error sound: %s", sound_err)
                logger.debug("Status warning set (sound disabled)")

            # Update analytics panel with results
            logger.debug("Updating analytics panel")
            self._analytics_panel.update_overview(
                total_sectors=result.total_sectors,
                good_sectors=len(result.good_sectors),
                bad_sectors=len(result.bad_sectors),
                recovered_sectors=0,
                health_score=self._disk_health,
            )
            logger.debug("Analytics panel updated")
            logger.info("_on_scan_complete finished successfully")
        except Exception as e:
            logger.exception("Error in _on_scan_complete: %s", e)
            self._status_strip.set_error(f"Scan completion error: {e}")

    def _on_scan_progress(self, progress: int) -> None:
        """Handle scan progress update."""
        # Update operation toolbar progress bar
        self._operation_toolbar.set_progress(progress)

        # Update status strip with progress
        total_tracks = self._geometry.cylinders * self._geometry.heads
        current_track = int((progress / 100) * total_tracks)
        self._status_strip.set_scanning(current_track, total_tracks)

    def _on_scan_error(self, error_message: str) -> None:
        """Handle scan error."""
        logger.error("Scan error: %s", error_message)
        self._status_strip.set_error(f"Scan error: {error_message}")
        play_error_sound()

    def _on_scan_finished(self) -> None:
        """Handle scan worker finished (cleanup)."""
        try:
            logger.info("_on_scan_finished called - starting cleanup")
            logger.debug("Calling _on_operation_complete")
            self._on_operation_complete()
            logger.debug("_on_operation_complete returned, calling _cleanup_scan_worker")
            self._cleanup_scan_worker()
            logger.info("_on_scan_finished completed successfully")
        except Exception as e:
            logger.exception("Error in _on_scan_finished: %s", e)

    # =========================================================================
    # Format Operation
    # =========================================================================

    def _start_format_operation(self) -> None:
        """Start the format operation with worker thread."""
        self._cleanup_format_worker()

        # Reset sector map to pending state (no animation for instant visual update)
        total_sectors = self._geometry.total_sectors
        for sector in range(total_sectors):
            self._sector_map.set_sector_status(sector, SectorStatus.PENDING, animate=False)
        self._sector_map.scene.update()

        # Create thread and worker
        self._format_thread = QThread()
        self._format_worker = FormatWorker(
            device=self._device,
            geometry=self._geometry,
            fill_pattern=0xE5,
            verify=True,
            format_type=FormatType.STANDARD,
        )
        self._format_worker.moveToThread(self._format_thread)

        # Connect worker signals
        self._format_thread.started.connect(self._format_worker.run)
        self._format_worker.track_formatted.connect(self._on_track_formatted)
        self._format_worker.track_verified.connect(self._on_track_verified)
        self._format_worker.format_complete.connect(self._on_format_complete)
        self._format_worker.progress.connect(self._on_format_progress)
        self._format_worker.error.connect(self._on_format_error)
        self._format_worker.finished.connect(self._on_format_finished)

        logger.info("Starting format worker thread")
        self._format_thread.start()

    def _cleanup_format_worker(self) -> None:
        """Clean up format worker and thread."""
        if self._format_worker:
            self._format_worker.cancel()
            self._format_worker = None

        if self._format_thread:
            if self._format_thread.isRunning():
                self._format_thread.quit()
                self._format_thread.wait(3000)
            self._format_thread = None

    def _on_track_formatted(self, cylinder: int, head: int, success: bool) -> None:
        """Handle track format completion."""
        logger.debug("Track formatted: cyl=%d, head=%d, success=%s", cylinder, head, success)
        track_number = cylinder * 2 + head
        start_sector = track_number * self._geometry.sectors_per_track

        status = SectorStatus.GOOD if success else SectorStatus.BAD
        for i in range(self._geometry.sectors_per_track):
            self._sector_map.set_sector_status(start_sector + i, status, animate=False)

        self._sector_map.set_active_sector(start_sector, ActivityType.WRITING)

        # Force scene repaint for visual feedback
        self._sector_map.scene.update()

    def _on_track_verified(self, cylinder: int, head: int, verified_ok: bool) -> None:
        """Handle track verification completion."""
        logger.debug("Track verified: cyl=%d, head=%d, ok=%s", cylinder, head, verified_ok)
        if not verified_ok:
            track_number = cylinder * 2 + head
            start_sector = track_number * self._geometry.sectors_per_track
            for i in range(self._geometry.sectors_per_track):
                self._sector_map.set_sector_status(start_sector + i, SectorStatus.WEAK, animate=False)
            # Force scene repaint
            self._sector_map.scene.update()

    def _on_format_complete(self, result: FormatResult) -> None:
        """Handle format operation completion."""
        logger.info("Format complete: %d/%d tracks OK, %d bad sectors",
                    result.tracks_formatted, result.total_tracks, len(result.bad_sectors))

        if result.success:
            self._status_strip.set_success(
                f"Format complete: {result.tracks_formatted} tracks formatted"
            )
            play_success_sound()
        else:
            self._status_strip.set_warning(
                f"Format complete with errors: {result.tracks_failed} tracks failed"
            )
            play_error_sound()

    def _on_format_progress(self, progress: int) -> None:
        """Handle format progress update."""
        # Update operation toolbar progress bar
        self._operation_toolbar.set_progress(progress)

        # Update status strip
        total_tracks = self._geometry.cylinders * self._geometry.heads
        current_track = int((progress / 100) * total_tracks)
        self._status_strip.set_formatting(current_track, total_tracks)

    def _on_format_error(self, error_message: str) -> None:
        """Handle format error."""
        logger.error("Format error: %s", error_message)
        self._status_strip.set_error(f"Format error: {error_message}")
        play_error_sound()

    def _on_format_finished(self) -> None:
        """Handle format worker finished (cleanup)."""
        logger.debug("Format worker finished")
        self._on_operation_complete()
        self._cleanup_format_worker()

    # =========================================================================
    # Restore Operation
    # =========================================================================

    def _start_restore_operation(self) -> None:
        """Start the restore operation with worker thread."""
        self._cleanup_restore_worker()

        # Get operation mode from toolbar and map to recovery level
        mode_text = self._operation_toolbar.get_selected_mode()

        # Map operation mode to recovery level and settings
        if mode_text == "Quick":
            recovery_level = RecoveryLevel.STANDARD
            passes = 3
            pll_tuning = False
            bit_slip_recovery = False
        elif mode_text == "Standard":
            recovery_level = RecoveryLevel.STANDARD
            passes = 10
            pll_tuning = False
            bit_slip_recovery = False
        elif mode_text == "Thorough":
            recovery_level = RecoveryLevel.AGGRESSIVE
            passes = 20
            pll_tuning = True
            bit_slip_recovery = False
        elif mode_text == "Forensic":
            recovery_level = RecoveryLevel.FORENSIC
            passes = 50
            pll_tuning = True
            bit_slip_recovery = True
        else:
            # Default to Standard
            recovery_level = RecoveryLevel.STANDARD
            passes = 10
            pll_tuning = False
            bit_slip_recovery = False

        logger.info("Starting restore with mode=%s, level=%s, pll=%s, bitslip=%s",
                    mode_text, recovery_level.name, pll_tuning, bit_slip_recovery)

        # Create restore config
        config = RestoreConfig(
            convergence_mode=True,
            passes=passes,
            convergence_threshold=3,
            multiread_mode=True,
            multiread_attempts=5,
            recovery_level=recovery_level,
            pll_tuning=pll_tuning,
            bit_slip_recovery=bit_slip_recovery,
        )

        # Create thread and worker
        self._restore_thread = QThread()
        self._restore_worker = RestoreWorker(
            device=self._device,
            geometry=self._geometry,
            config=config,
        )
        self._restore_worker.moveToThread(self._restore_thread)

        # Connect worker signals
        self._restore_thread.started.connect(self._restore_worker.run)
        self._restore_worker.pass_started.connect(self._on_restore_pass_started)
        self._restore_worker.pass_complete.connect(self._on_restore_pass_complete)
        self._restore_worker.sector_recovered.connect(self._on_sector_recovered)
        self._restore_worker.sector_failed.connect(self._on_sector_failed)
        self._restore_worker.initial_scan_sector.connect(self._on_restore_initial_scan_sector)
        self._restore_worker.restore_complete.connect(self._on_restore_complete)
        self._restore_worker.progress.connect(self._on_restore_progress)
        self._restore_worker.error.connect(self._on_restore_error)
        self._restore_worker.finished.connect(self._on_restore_finished)

        logger.info("Starting restore worker thread")
        self._restore_thread.start()

    def _cleanup_restore_worker(self) -> None:
        """Clean up restore worker and thread."""
        if self._restore_worker:
            self._restore_worker.cancel()
            self._restore_worker = None

        if self._restore_thread:
            if self._restore_thread.isRunning():
                self._restore_thread.quit()
                self._restore_thread.wait(3000)
            self._restore_thread = None

    def _on_restore_pass_started(self, pass_num: int, total_passes: int) -> None:
        """Handle restore pass start."""
        logger.debug("Restore pass started: %d/%d", pass_num, total_passes)
        self._status_strip.set_restoring(pass_num, total_passes, 0, self._geometry.total_sectors)

    def _on_restore_pass_complete(self, pass_num: int, bad_count: int, recovered_count: int) -> None:
        """Handle restore pass completion."""
        logger.debug("Restore pass complete: pass=%d, bad=%d, recovered=%d",
                     pass_num, bad_count, recovered_count)

    def _on_sector_recovered(self, sector_num: int, technique: str) -> None:
        """Handle sector recovery success."""
        logger.debug("Sector recovered: %d using %s", sector_num, technique)
        self._sector_map.set_sector_status(sector_num, SectorStatus.RECOVERED, animate=False)
        self._sector_map.set_active_sector(sector_num, ActivityType.WRITING)
        self._sector_map.scene.update()

    def _on_sector_failed(self, sector_num: int, reason: str) -> None:
        """Handle sector recovery failure."""
        logger.debug("Sector failed: %d - %s", sector_num, reason)
        self._sector_map.set_sector_status(sector_num, SectorStatus.BAD, animate=False)
        self._sector_map.scene.update()

    def _on_restore_initial_scan_sector(self, sector_num: int, is_good: bool) -> None:
        """Handle initial scan sector result during restore."""
        status = SectorStatus.GOOD if is_good else SectorStatus.BAD
        self._sector_map.set_sector_status(sector_num, status, animate=False)

    def _on_restore_complete(self, stats: RecoveryStats) -> None:
        """Handle restore operation completion."""
        logger.info("Restore complete: %d/%d sectors recovered",
                    stats.sectors_recovered, stats.initial_bad_sectors)

        if stats.final_bad_sectors == 0:
            self._status_strip.set_success(
                f"Restore complete: All {stats.sectors_recovered} bad sectors recovered"
            )
            play_success_sound()
        elif stats.sectors_recovered > 0:
            self._status_strip.set_warning(
                f"Restore complete: {stats.sectors_recovered} recovered, "
                f"{stats.final_bad_sectors} unrecoverable"
            )
            play_complete_sound()
        else:
            self._status_strip.set_error(
                f"Restore failed: {stats.final_bad_sectors} sectors unrecoverable"
            )
            play_error_sound()

        # Update health based on recovery
        if self._geometry.total_sectors > 0:
            good_sectors = self._geometry.total_sectors - stats.final_bad_sectors
            self._disk_health = int((good_sectors / self._geometry.total_sectors) * 100)
            self._status_strip.set_health(self._disk_health)

    def _on_restore_progress(self, progress: int) -> None:
        """Handle restore progress update."""
        # Update operation toolbar progress bar
        self._operation_toolbar.set_progress(progress)

        # Update status strip with progress info
        self._status_strip.set_operation_status(f"Restoring: {progress}%")

    def _on_restore_error(self, error_message: str) -> None:
        """Handle restore error."""
        logger.error("Restore error: %s", error_message)
        self._status_strip.set_error(f"Restore error: {error_message}")
        play_error_sound()

    def _on_restore_finished(self) -> None:
        """Handle restore worker finished (cleanup)."""
        logger.debug("Restore worker finished")
        self._on_operation_complete()
        self._cleanup_restore_worker()

    # =========================================================================
    # Analyze Operation
    # =========================================================================

    def _start_analyze_operation(self) -> None:
        """Start the analyze operation with worker thread."""
        self._cleanup_analyze_worker()

        # Get operation mode from toolbar and map to analysis config
        mode_text = self._operation_toolbar.get_selected_mode()

        # Map operation mode to analysis depth and components
        if mode_text == "Quick":
            depth = AnalysisDepth.QUICK
            revolutions = 1
            components = [
                AnalysisComponent.FLUX_TIMING,
                AnalysisComponent.SIGNAL_QUALITY,
            ]
        elif mode_text == "Standard":
            depth = AnalysisDepth.STANDARD
            revolutions = 2
            components = [
                AnalysisComponent.FLUX_TIMING,
                AnalysisComponent.SIGNAL_QUALITY,
                AnalysisComponent.ENCODING,
            ]
        elif mode_text == "Thorough":
            depth = AnalysisDepth.COMPREHENSIVE
            revolutions = 3
            components = [
                AnalysisComponent.FLUX_TIMING,
                AnalysisComponent.SIGNAL_QUALITY,
                AnalysisComponent.ENCODING,
                AnalysisComponent.WEAK_BITS,
            ]
        elif mode_text == "Forensic":
            depth = AnalysisDepth.COMPREHENSIVE
            revolutions = 5
            components = [
                AnalysisComponent.FLUX_TIMING,
                AnalysisComponent.SIGNAL_QUALITY,
                AnalysisComponent.ENCODING,
                AnalysisComponent.WEAK_BITS,
                AnalysisComponent.FORENSICS,
            ]
        else:
            # Default to standard
            depth = AnalysisDepth.STANDARD
            revolutions = 2
            components = [
                AnalysisComponent.FLUX_TIMING,
                AnalysisComponent.SIGNAL_QUALITY,
                AnalysisComponent.ENCODING,
            ]

        logger.info("Starting analysis with mode=%s, depth=%s, revolutions=%d",
                    mode_text, depth.name, revolutions)

        # Create analysis config
        config = AnalysisConfig(
            depth=depth,
            components=components,
            capture_revolutions=revolutions,
            save_flux=False,
        )

        # Create thread and worker
        self._analyze_thread = QThread()
        self._analyze_worker = AnalyzeWorker(
            device=self._device,
            geometry=self._geometry,
            config=config,
        )
        self._analyze_worker.moveToThread(self._analyze_thread)

        # Connect worker signals
        self._analyze_thread.started.connect(self._analyze_worker.run)
        self._analyze_worker.track_analyzed.connect(self._on_track_analyzed)
        self._analyze_worker.flux_quality_update.connect(self._on_flux_quality_update)
        self._analyze_worker.analysis_complete.connect(self._on_analysis_complete)
        self._analyze_worker.progress.connect(self._on_analyze_progress)
        self._analyze_worker.error.connect(self._on_analyze_error)
        self._analyze_worker.finished.connect(self._on_analyze_finished)

        logger.info("Starting analyze worker thread")
        self._analyze_thread.start()

    def _cleanup_analyze_worker(self) -> None:
        """Clean up analyze worker and thread."""
        if self._analyze_worker:
            self._analyze_worker.cancel()
            self._analyze_worker = None

        if self._analyze_thread:
            if self._analyze_thread.isRunning():
                self._analyze_thread.quit()
                self._analyze_thread.wait(3000)
            self._analyze_thread = None

    def _on_track_analyzed(self, cylinder: int, head: int, result) -> None:
        """Handle track analysis completion."""
        logger.debug("Track analyzed: cyl=%d, head=%d, grade=%s",
                     cylinder, head, result.grade)

        track_number = cylinder * 2 + head
        start_sector = track_number * self._geometry.sectors_per_track

        # Map grade to sector status
        grade_status = {
            'A': SectorStatus.GOOD,
            'B': SectorStatus.GOOD,
            'C': SectorStatus.WEAK,
            'D': SectorStatus.WEAK,
            'F': SectorStatus.BAD,
        }
        status = grade_status.get(result.grade, SectorStatus.UNKNOWN)

        for i in range(self._geometry.sectors_per_track):
            self._sector_map.set_sector_status(start_sector + i, status, animate=False)

        self._sector_map.set_active_sector(start_sector, ActivityType.READING)

        # Force scene repaint for visual feedback
        self._sector_map.scene.update()

    def _on_flux_quality_update(self, cylinder: int, head: int, score: float) -> None:
        """Handle flux quality update."""
        pass  # Quality is displayed via track_analyzed

    def _on_analysis_complete(self, result: DiskAnalysisResult) -> None:
        """Handle analysis operation completion."""
        logger.info("Analysis complete: grade=%s, score=%.1f",
                    result.overall_grade, result.overall_quality_score)

        # Update disk health
        self._disk_health = int(result.overall_quality_score)
        self._status_strip.set_health(self._disk_health)

        grade = result.overall_grade
        if grade in ('A', 'B'):
            self._status_strip.set_success(
                f"Analysis complete: Grade {grade} ({result.overall_quality_score:.0f}%)"
            )
            play_success_sound()
        elif grade == 'C':
            self._status_strip.set_warning(
                f"Analysis complete: Grade {grade} - Some degradation detected"
            )
            play_complete_sound()
        else:
            self._status_strip.set_error(
                f"Analysis complete: Grade {grade} - Significant issues found"
            )
            play_error_sound()

        # Update analytics panel with analysis results
        # Convert analysis result to overview format
        grade_dist = result.get_grade_distribution()
        good_sectors = (grade_dist.get('A', 0) + grade_dist.get('B', 0)) * self._geometry.sectors_per_track
        weak_sectors = (grade_dist.get('C', 0) + grade_dist.get('D', 0)) * self._geometry.sectors_per_track
        bad_sectors = grade_dist.get('F', 0) * self._geometry.sectors_per_track

        self._analytics_panel.update_overview(
            total_sectors=self._geometry.total_sectors,
            good_sectors=good_sectors,
            bad_sectors=bad_sectors,
            recovered_sectors=0,
            health_score=result.overall_quality_score,
        )

        # Display forensics results if available
        if result.is_copy_protected:
            protection_msg = f"Copy protection detected on {result.protected_track_count} tracks"
            if result.protection_types:
                protection_msg += f": {', '.join(result.protection_types[:3])}"
            logger.warning(protection_msg)
            # Show warning in status
            self._status_strip.set_warning(protection_msg)

        if result.format_type and result.format_type != "UNKNOWN":
            logger.info("Detected format: %s (standard=%s)",
                        result.format_type, result.format_is_standard)

        # Log recommendations
        if result.recommendations:
            logger.info("Analysis recommendations:")
            for rec in result.recommendations:
                logger.info("  - %s", rec)

    def _on_analyze_progress(self, progress: int) -> None:
        """Handle analyze progress update."""
        # Update operation toolbar progress bar
        self._operation_toolbar.set_progress(progress)

        # Update status strip
        total_tracks = self._geometry.cylinders * self._geometry.heads
        current_track = int((progress / 100) * total_tracks)
        self._status_strip.set_analyzing(f"track {current_track}/{total_tracks}")

    def _on_analyze_error(self, error_message: str) -> None:
        """Handle analyze error."""
        logger.error("Analyze error: %s", error_message)
        self._status_strip.set_error(f"Analysis error: {error_message}")
        play_error_sound()

    def _on_analyze_finished(self) -> None:
        """Handle analyze worker finished (cleanup)."""
        logger.debug("Analyze worker finished")
        self._on_operation_complete()
        self._cleanup_analyze_worker()

    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        logger.info("Stopping operation")

        # Cancel any running workers
        if self._scan_worker:
            self._scan_worker.cancel()
        if self._format_worker:
            self._format_worker.cancel()
        if self._restore_worker:
            self._restore_worker.cancel()
        if self._analyze_worker:
            self._analyze_worker.cancel()
        if self._flux_capture_worker:
            self._flux_capture_worker.cancel()

        self._state = WorkbenchState.IDLE
        self._operation_toolbar.stop_operation()
        self._status_strip.set_warning("Operation cancelled")
        self._update_state()

        # Turn off the motor
        if self._device and self._device.is_connected():
            try:
                self._device.motor_off()
                logger.debug("Motor stopped after cancel")
            except Exception as motor_err:
                logger.warning("Failed to stop motor: %s", motor_err)

        # Resume RPM polling now that the operation is stopped
        self._drive_control.resume_rpm_polling()

        # Cleanup all workers after a short delay to let them finish
        QTimer.singleShot(500, self._cleanup_all_workers)

    def _cleanup_all_workers(self) -> None:
        """Clean up all worker threads."""
        self._cleanup_scan_worker()
        self._cleanup_format_worker()
        self._cleanup_restore_worker()
        self._cleanup_analyze_worker()
        self._cleanup_flux_capture_worker()

    def _cleanup_flux_capture_worker(self) -> None:
        """Clean up flux capture worker and thread."""
        if self._flux_capture_worker:
            self._flux_capture_worker.cancel()
            self._flux_capture_worker = None

        if self._flux_capture_thread:
            if self._flux_capture_thread.isRunning():
                self._flux_capture_thread.quit()
                self._flux_capture_thread.wait(3000)
            self._flux_capture_thread = None

    def _on_pause_clicked(self) -> None:
        """Handle pause button click."""
        logger.info("Operation paused")
        self._status_strip.set_warning("Operation paused")

    def _on_operation_complete(self) -> None:
        """Handle operation completion (cleanup and state reset)."""
        try:
            logger.debug("_on_operation_complete: setting state to IDLE")
            self._state = WorkbenchState.IDLE
            logger.debug("_on_operation_complete: stopping operation toolbar")
            self._operation_toolbar.stop_operation()
            self._operation_toolbar.set_progress(100)

            # Don't overwrite status - scan_complete/format_complete already set it

            # Play completion sound - DISABLED due to Qt multimedia crash
            # logger.debug("_on_operation_complete: playing completion sound")
            # try:
            #     play_complete_sound()
            # except Exception as sound_err:
            #     logger.warning("Failed to play completion sound: %s", sound_err)
            logger.debug("_on_operation_complete: sounds disabled")

            # Turn off the motor now that the operation is complete
            logger.debug("_on_operation_complete: stopping motor")
            if self._device and self._device.is_connected():
                try:
                    self._device.motor_off()
                    logger.debug("_on_operation_complete: motor stopped")
                except Exception as motor_err:
                    logger.warning("Failed to stop motor: %s", motor_err)

            # Resume RPM polling now that the operation is complete
            logger.debug("_on_operation_complete: resuming RPM polling")
            self._drive_control.resume_rpm_polling()

            logger.debug("_on_operation_complete: updating state")
            self._update_state()
            logger.debug("_on_operation_complete: completed")
        except Exception as e:
            logger.exception("Error in _on_operation_complete: %s", e)

    def _on_operation_error(self, message: str) -> None:
        """
        Handle operation error.

        Args:
            message: Error message
        """
        self._state = WorkbenchState.IDLE
        self._operation_toolbar.stop_operation()
        self._status_strip.set_error(message)

        # Play error sound
        play_error_sound()

        # Resume RPM polling now that the operation has ended
        self._drive_control.resume_rpm_polling()

        self._update_state()

    def _on_operation_success(self, message: str) -> None:
        """
        Handle operation success with custom message.

        Args:
            message: Success message
        """
        self._state = WorkbenchState.IDLE
        self._operation_toolbar.stop_operation()
        self._operation_toolbar.set_progress(100)
        self._status_strip.set_success(message)

        # Play success sound
        play_success_sound()

        # Resume RPM polling now that the operation is complete
        self._drive_control.resume_rpm_polling()

        self._update_state()

    # =========================================================================
    # Signal Handlers - Sector Map
    # =========================================================================

    def _on_selection_changed(self, selected_sectors: list) -> None:
        """
        Handle sector selection change in the sector map.

        Args:
            selected_sectors: List of selected sector numbers
        """
        count = len(selected_sectors)
        if count == 0:
            logger.debug("Sector selection cleared")
            self._status_strip.set_idle()
        elif count == 1:
            logger.debug("Selected sector: %d", selected_sectors[0])
            self._status_strip.set_operation_status(f"Selected sector {selected_sectors[0]}")
        else:
            logger.debug("Selected %d sectors: %s", count, selected_sectors[:5])
            self._status_strip.set_operation_status(f"Selected {count} sectors")

    def _on_sector_clicked(self, sector_num: int) -> None:
        """
        Handle sector click in the sector map.

        Args:
            sector_num: The clicked sector number (0-based)
        """
        logger.debug("Sector clicked: %d", sector_num)

        # Calculate CHS from sector number
        if self._geometry:
            sectors_per_track = self._geometry.sectors_per_track
            heads = self._geometry.heads
            sectors_per_cylinder = sectors_per_track * heads

            cylinder = sector_num // sectors_per_cylinder
            remainder = sector_num % sectors_per_cylinder
            head = remainder // sectors_per_track
            sector = (remainder % sectors_per_track) + 1  # 1-based sector

            logger.debug("Sector %d = C:%d H:%d S:%d", sector_num, cylinder, head, sector)

    # =========================================================================
    # Signal Handlers - Analytics Panel
    # =========================================================================

    def _on_analytics_tab_changed(self, tab_name: str) -> None:
        """Handle analytics panel tab change."""
        logger.debug("Analytics tab changed: %s", tab_name)

    def _on_recommendation_action(self, action_id: str) -> None:
        """
        Handle recommendation action from overview tab.

        Args:
            action_id: The action identifier from the recommendation
        """
        logger.info("Recommendation action triggered: %s", action_id)

        # Handle specific recommendation actions
        if action_id == "scan_disk":
            self._operation_toolbar.set_operation("scan")
            self._on_start_clicked()
        elif action_id == "run_recovery":
            self._operation_toolbar.set_operation("restore")
        elif action_id == "run_alignment":
            self._analytics_panel.show_tab("diagnostics")
            self._on_run_alignment_requested()
        elif action_id == "run_self_test":
            self._analytics_panel.show_tab("diagnostics")
            self._on_run_self_test_requested()
        else:
            logger.warning("Unknown recommendation action: %s", action_id)

    def _on_analytics_sector_selected(self, cylinder: int, head: int, sector: int) -> None:
        """
        Handle sector selection from errors tab.

        Args:
            cylinder: Cylinder number
            head: Head number
            sector: Sector number (1-based)
        """
        logger.debug("Analytics sector selected: C:%d H:%d S:%d", cylinder, head, sector)

        # Calculate LBA and highlight in sector map
        if self._geometry:
            sectors_per_track = self._geometry.sectors_per_track
            heads = self._geometry.heads
            sectors_per_cylinder = sectors_per_track * heads

            lba = (cylinder * sectors_per_cylinder) + (head * sectors_per_track) + (sector - 1)

            # Select in sector map
            sector_map = self._sector_map_panel.get_sector_map()
            sector_map.select_sector(lba)
            sector_map.center_on_sector(lba)

    def _on_load_flux_requested(self, cylinder: int, head: int, sector: int) -> None:
        """
        Handle flux load request from flux tab.

        Args:
            cylinder: Cylinder number
            head: Head number
            sector: Sector number (1-based)
        """
        logger.info("Load flux requested: C:%d H:%d S:%d", cylinder, head, sector)

        if not self._device:
            self._status_strip.set_error("No device connected")
            return

        self._status_strip.set_analyzing("flux data")

        try:
            # Ensure motor is on
            if not self._device.is_motor_on():
                self._device.motor_on()

            # Seek and capture flux
            self._device.seek(cylinder, head)
            flux_data = read_track_flux(self._device, cylinder, head, revolutions=2)
            capture = FluxCapture.from_flux_data(flux_data)
            capture.cylinder = cylinder
            capture.head = head

            # Update flux tab with captured data
            self._analytics_panel.load_flux_data(capture)

            self._status_strip.set_success(f"Flux loaded: C{cylinder}:H{head}")
            logger.info("Flux capture complete for C%d:H%d", cylinder, head)

        except Exception as e:
            logger.error("Flux capture failed: %s", e)
            self._status_strip.set_error(f"Flux capture failed: {e}")

    def _on_capture_flux_requested(self, cylinder: int, head: int) -> None:
        """
        Handle flux capture request from flux tab.

        Args:
            cylinder: Cylinder number
            head: Head number
        """
        logger.info("Capture flux requested: C:%d H:%d", cylinder, head)

        if not self._device:
            self._status_strip.set_error("No device connected")
            return

        self._status_strip.set_analyzing("flux capture")

        try:
            # Ensure motor is on
            if not self._device.is_motor_on():
                self._device.motor_on()

            # Seek and capture flux with multiple revolutions
            self._device.seek(cylinder, head)
            flux_data = read_track_flux(self._device, cylinder, head, revolutions=3)
            capture = FluxCapture.from_flux_data(flux_data)
            capture.cylinder = cylinder
            capture.head = head

            # Update flux tab with captured data
            self._analytics_panel.load_flux_data(capture)

            self._status_strip.set_success(f"Flux captured: C{cylinder}:H{head}")
            logger.info("Flux capture complete for C%d:H%d", cylinder, head)

        except Exception as e:
            logger.error("Flux capture failed: %s", e)
            self._status_strip.set_error(f"Flux capture failed: {e}")

    def _on_export_flux_requested(self, file_path: str) -> None:
        """
        Handle flux export request from flux tab.

        Args:
            file_path: Target file path for export
        """
        logger.info("Export flux requested: %s", file_path)
        self._status_strip.set_operation_status(f"Exporting flux to {file_path}")

        try:
            from floppy_formatter.imaging.image_formats import export_flux_to_scp

            # Get current flux data from analytics panel
            flux_data = self._analytics_panel.get_current_flux_data()
            if flux_data is None:
                self._status_strip.set_error("No flux data to export")
                return

            # Export based on file extension
            if file_path.lower().endswith('.scp'):
                export_flux_to_scp(flux_data, file_path)
            else:
                # Default to raw flux export
                with open(file_path, 'wb') as f:
                    f.write(flux_data.to_bytes())

            self._status_strip.set_success(f"Flux exported to {file_path}")
            logger.info("Flux export complete: %s", file_path)

        except Exception as e:
            logger.error("Flux export failed: %s", e)
            self._status_strip.set_error(f"Export failed: {e}")

    def _on_run_alignment_requested(self) -> None:
        """Handle alignment test request from diagnostics tab."""
        logger.info("Alignment test requested")

        if not self._device:
            self._status_strip.set_error("No device connected")
            return

        self._status_strip.set_analyzing("head alignment")

        try:
            from floppy_formatter.hardware.drive_calibration import check_track_alignment

            # Ensure motor is on
            if not self._device.is_motor_on():
                self._device.motor_on()

            # Run alignment check on sample cylinders (inner, middle, outer)
            results = []
            test_cylinders = [2, 40, 78]  # Outer, middle, inner cylinders

            for cylinder in test_cylinders:
                result = check_track_alignment(self._device, cylinder)
                results.append(result)

            # Calculate overall alignment score using alignment_score property
            avg_score = sum(r.alignment_score for r in results) / len(results)
            alignment_ok = avg_score >= 0.7  # 70% is good threshold

            if alignment_ok:
                self._status_strip.set_success(
                    f"Head alignment OK (score: {avg_score:.0%})"
                )
            else:
                self._status_strip.set_warning(
                    f"Head alignment marginal (score: {avg_score:.0%})"
                )

            # Convert to AlignmentResults format expected by diagnostics tab
            from floppy_formatter.gui.tabs.diagnostics_tab import AlignmentResults

            alignment_results = AlignmentResults(
                score=avg_score * 100,  # Convert to 0-100 scale
                status="Aligned" if alignment_ok else "Slightly Off" if avg_score >= 0.5 else "Misaligned",
                inner_margin=0.0,  # Not measured
                outer_margin=0.0,  # Not measured
                center_offset=0.0,  # Not measured
                cylinders_tested=test_cylinders,
                per_cylinder_scores=[r.alignment_score * 100 for r in results],
            )

            # Update diagnostics tab with results
            self._analytics_panel.update_alignment_results(alignment_results)

            logger.info("Alignment test complete: avg_score=%.2f", avg_score)

        except Exception as e:
            logger.error("Alignment test failed: %s", e)
            self._status_strip.set_error(f"Alignment test failed: {e}")

    def _on_run_self_test_requested(self) -> None:
        """Handle self-test request from diagnostics tab."""
        logger.info("Self-test requested")

        if not self._device:
            self._status_strip.set_error("No device connected")
            return

        self._status_strip.set_analyzing("drive self-test")

        try:
            from floppy_formatter.hardware.drive_calibration import quick_calibration

            # Ensure motor is on
            if not self._device.is_motor_on():
                self._device.motor_on()

            # Get the currently selected drive unit (default to 0 if none selected)
            drive_unit = self._device.selected_drive if self._device.selected_drive is not None else 0

            # Run quick calibration/self-test on the current drive
            calibration = quick_calibration(self._device, drive_unit=drive_unit)

            if calibration.calibration_successful:
                health = calibration.health
                self._status_strip.set_success(
                    f"Self-test passed: Grade {health.grade_letter}, "
                    f"RPM={calibration.rpm.rpm:.1f}"
                )
            else:
                # Report issues found
                issues = calibration.health.issues
                issue_msg = issues[0] if issues else "Unknown issue"
                self._status_strip.set_warning(
                    f"Self-test completed with warnings: {issue_msg}"
                )

            # Convert DriveCalibration to SelfTestResults format
            from floppy_formatter.gui.tabs.diagnostics_tab import (
                SelfTestResults, SelfTestItem, TestStatus
            )
            from datetime import datetime

            # Build test items from calibration results
            test_items = [
                SelfTestItem(
                    name="Track 0 seek",
                    status=TestStatus.PASS,
                    details="Seek to track 0 successful",
                ),
                SelfTestItem(
                    name="RPM stability",
                    status=TestStatus.PASS if calibration.rpm.within_spec else TestStatus.FAIL,
                    details=f"{calibration.rpm.rpm:.1f} RPM (±{calibration.rpm.std_dev:.1f})",
                ),
                SelfTestItem(
                    name="Bit timing",
                    status=TestStatus.PASS if calibration.bit_timing.within_spec else TestStatus.FAIL,
                    details=f"{calibration.bit_timing.bit_cell_us:.3f}µs bit cell",
                ),
                SelfTestItem(
                    name="Head alignment",
                    status=TestStatus.PASS if calibration.health.alignment_ok else TestStatus.FAIL,
                    details=f"Score: {calibration.health.score:.0%}",
                ),
                SelfTestItem(
                    name="Overall health",
                    status=TestStatus.PASS if calibration.calibration_successful else TestStatus.FAIL,
                    details=f"Grade {calibration.health.grade_letter}",
                ),
            ]

            self_test_results = SelfTestResults(
                tests=test_items,
                timestamp=datetime.now(),
                overall_pass=calibration.calibration_successful,
            )

            # Update diagnostics tab with results
            self._analytics_panel.update_self_test_results(self_test_results)

            logger.info("Self-test complete: success=%s, grade=%s",
                        calibration.calibration_successful,
                        calibration.health.grade_letter)

        except Exception as e:
            logger.error("Self-test failed: %s", e)
            self._status_strip.set_error(f"Self-test failed: {e}")

    # =========================================================================
    # Keyboard Shortcut Handlers
    # =========================================================================

    def _start_scan_shortcut(self) -> None:
        """Start scan operation (Ctrl+S)."""
        if self._can_start_operation():
            self._operation_toolbar.set_operation("scan")
            self._on_start_clicked()

    def _start_format_shortcut(self) -> None:
        """Start format operation (Ctrl+Shift+F)."""
        if self._can_start_operation():
            self._operation_toolbar.set_operation("format")
            self._on_start_clicked()

    def _start_restore_shortcut(self) -> None:
        """Start restore operation (Ctrl+R)."""
        if self._can_start_operation():
            self._operation_toolbar.set_operation("restore")
            self._on_start_clicked()

    def _start_analyze_shortcut(self) -> None:
        """Start analyze operation (Ctrl+Shift+A)."""
        if self._can_start_operation():
            self._operation_toolbar.set_operation("analyze")
            self._on_start_clicked()

    def _toggle_pause(self) -> None:
        """Toggle pause/resume (Space)."""
        if self._state != WorkbenchState.IDLE:
            self._on_pause_clicked()

    def _can_start_operation(self) -> bool:
        """
        Check if an operation can be started.

        Returns:
            True if operation can be started
        """
        if not self._drive_control.is_connected():
            self._status_strip.set_warning("Connect device first (Ctrl+Shift+C)")
            return False

        if self._state != WorkbenchState.IDLE:
            self._status_strip.set_warning("Operation in progress")
            return False

        if self._view_only_mode:
            self._status_strip.set_warning("View-only mode enabled")
            return False

        return True

    def _toggle_connection(self) -> None:
        """Toggle device connection (Ctrl+Shift+C)."""
        if self._drive_control.is_connected():
            self._drive_control._disconnect_device()
        else:
            self._drive_control._connect_device()

    def _seek_track0(self) -> None:
        """Seek to track 0 (Ctrl+0)."""
        if self._drive_control.is_connected():
            self._drive_control._on_track0_clicked()

    def _toggle_motor(self) -> None:
        """Toggle motor on/off (Ctrl+M)."""
        if self._drive_control.is_connected():
            self._drive_control._motor_button.click()

    def _on_escape(self) -> None:
        """Handle escape key."""
        if self._state != WorkbenchState.IDLE:
            # Stop current operation
            self._on_stop_clicked()

    # =========================================================================
    # Menu Handlers
    # =========================================================================

    def _on_settings_clicked(self) -> None:
        """Show the settings dialog."""
        show_settings_dialog(self, on_theme_changed=self._on_theme_changed)

    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change from settings dialog."""
        self.theme_manager.apply_theme(theme)

        # Update the menu item text
        if theme == "dark":
            self._toggle_theme_action.setText("Toggle &Dark Mode")
        else:
            self._toggle_theme_action.setText("Toggle &Light Mode")

    def _toggle_theme(self) -> None:
        """Toggle between dark and light themes."""
        current_theme = self.theme_manager.get_current_theme()
        new_theme = "light" if current_theme == "dark" else "dark"

        self.theme_manager.apply_theme(new_theme)
        set_theme(new_theme)

        # Update the menu item text
        if new_theme == "dark":
            self._toggle_theme_action.setText("Toggle &Dark Mode")
        else:
            self._toggle_theme_action.setText("Toggle &Light Mode")

    def _toggle_fullscreen(self) -> None:
        """Toggle full screen mode."""
        if self._is_fullscreen:
            self.showNormal()
            self._is_fullscreen = False
            self._fullscreen_action.setChecked(False)
        else:
            self.showFullScreen()
            self._is_fullscreen = True
            self._fullscreen_action.setChecked(True)

    def _open_documentation(self) -> None:
        """Open the GitHub documentation in the default browser."""
        QDesktopServices.openUrl(QUrl(self.GITHUB_URL))

    def _on_about_clicked(self) -> None:
        """Show the about dialog."""
        show_about_dialog(self)

    # =========================================================================
    # Public API
    # =========================================================================

    def get_device(self) -> Optional[GreaseweazleDevice]:
        """
        Get the connected Greaseweazle device.

        Returns:
            GreaseweazleDevice instance or None
        """
        return self._device

    def get_geometry(self) -> Optional[DiskGeometry]:
        """
        Get the current disk geometry.

        Returns:
            DiskGeometry or None
        """
        return self._geometry

    def get_state(self) -> WorkbenchState:
        """
        Get current workbench state.

        Returns:
            Current WorkbenchState
        """
        return self._state

    def is_operation_running(self) -> bool:
        """
        Check if an operation is running.

        Returns:
            True if operation is in progress
        """
        return self._state != WorkbenchState.IDLE

    def set_view_only_mode(self, enabled: bool) -> None:
        """
        Enable or disable view-only mode.

        In view-only mode, destructive operations are disabled.

        Args:
            enabled: True to enable view-only mode
        """
        self._view_only_mode = enabled
        # Operation toolbar handles its own enable state based on connection

    def is_view_only_mode(self) -> bool:
        """
        Check if view-only mode is enabled.

        Returns:
            True if view-only mode is active
        """
        return self._view_only_mode

    def get_sector_map(self) -> CircularSectorMap:
        """
        Get the sector map widget.

        Returns:
            CircularSectorMap widget instance
        """
        return self._sector_map_panel.get_sector_map()

    def get_sector_map_toolbar(self) -> SectorMapToolbar:
        """
        Get the sector map toolbar widget.

        Returns:
            SectorMapToolbar widget instance
        """
        return self._sector_map_panel.get_toolbar()

    def get_sector_info_panel(self) -> SectorInfoPanel:
        """
        Get the sector info panel widget.

        Returns:
            SectorInfoPanel widget instance
        """
        return self._sector_map_panel.get_info_panel()

    def get_selected_sectors(self) -> list:
        """
        Get list of currently selected sectors.

        Returns:
            List of selected sector numbers
        """
        return self._sector_map_panel.get_sector_map().get_selected_sectors()

    def get_analytics_panel(self) -> AnalyticsPanel:
        """
        Get the analytics panel widget.

        Returns:
            AnalyticsPanel widget instance
        """
        return self._analytics_panel

    def show_analytics_tab(self, tab_name: str) -> None:
        """
        Switch to a specific analytics tab.

        Args:
            tab_name: Tab name (overview, flux, errors, recovery, diagnostics)
        """
        self._analytics_panel.show_tab(tab_name)

    def update_analytics_overview(
        self,
        total_sectors: int = 2880,
        good_sectors: int = 0,
        bad_sectors: int = 0,
        recovered_sectors: int = 0,
        health_score: float = None
    ) -> None:
        """
        Update the analytics overview tab with scan results.

        Args:
            total_sectors: Total number of sectors on disk
            good_sectors: Number of good sectors
            bad_sectors: Number of bad sectors
            recovered_sectors: Number of recovered sectors
            health_score: Optional explicit health score (0-100)
        """
        self._analytics_panel.update_overview(
            total_sectors, good_sectors, bad_sectors, recovered_sectors, health_score
        )

        # Also update status strip health
        if health_score is not None:
            self._status_strip.set_health(int(health_score))

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        # Check if operation is in progress
        if self._state != WorkbenchState.IDLE:
            result = QMessageBox.question(
                self,
                "Confirm Exit",
                "An operation is in progress. Are you sure you want to exit?\n\n"
                "The operation will be cancelled.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if result != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        # Clean up device connection
        if self._drive_control.is_connected():
            self._drive_control.cleanup()

        event.accept()

    def keyPressEvent(self, event) -> None:
        """Handle key press events."""
        # F11 for fullscreen toggle
        if event.key() == Qt.Key.Key_F11:
            self._toggle_fullscreen()
        else:
            super().keyPressEvent(event)
