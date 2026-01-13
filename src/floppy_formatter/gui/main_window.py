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
from PyQt6.QtCore import Qt, QSize, QTimer, QUrl
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
from floppy_formatter.hardware import GreaseweazleDevice

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
        self._operation_toolbar.set_enabled(is_connected and is_idle)

        # Update status strip based on connection
        if is_connected:
            device_info = self._drive_control.get_device_info()
            self._status_strip.set_connection_status(True, device_info)

            # Update drive status
            if self._drive_control.is_motor_on():
                rpm = self._drive_control.get_rpm()
                self._status_strip.set_drive_status("3.5\" HD", rpm, True)
            else:
                self._status_strip.set_drive_status("3.5\" HD", None, False)
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

        self._update_state()

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
            rpm = self._drive_control.get_rpm()
            self._status_strip.set_drive_status("3.5\" HD", rpm, True)
        else:
            self._status_strip.set_drive_status("3.5\" HD", None, False)

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

        # Update status strip
        if operation == "scan":
            self._status_strip.set_scanning(0, 160)
        elif operation == "format":
            self._status_strip.set_formatting(0, 160)
        elif operation == "restore":
            self._status_strip.set_restoring(1, 5, 0, 2880)
        elif operation == "analyze":
            self._status_strip.set_analyzing("flux data")

        # Placeholder: actual worker implementation in Phase 9
        # For now, simulate operation completion after delay
        QTimer.singleShot(2000, self._on_operation_complete)

    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        logger.info("Stopping operation")
        self._state = WorkbenchState.IDLE
        self._operation_toolbar.stop_operation()
        self._status_strip.set_warning("Operation cancelled")
        self._update_state()

    def _on_pause_clicked(self) -> None:
        """Handle pause button click."""
        logger.info("Operation paused")
        self._status_strip.set_warning("Operation paused")

    def _on_operation_complete(self) -> None:
        """Handle operation completion (placeholder)."""
        self._state = WorkbenchState.IDLE
        self._operation_toolbar.stop_operation()
        self._operation_toolbar.set_progress(100)
        self._status_strip.set_success("Operation complete")

        # Play completion sound
        play_complete_sound()

        # Simulate health update after scan
        self._disk_health = 95
        self._status_strip.set_health(self._disk_health)

        self._update_state()

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
        # Placeholder: actual flux capture implementation in Phase 9

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
        # Placeholder: actual flux capture implementation in Phase 9

    def _on_export_flux_requested(self, file_path: str) -> None:
        """
        Handle flux export request from flux tab.

        Args:
            file_path: Target file path for export
        """
        logger.info("Export flux requested: %s", file_path)
        self._status_strip.set_operation_status(f"Exporting flux to {file_path}")
        # Placeholder: actual export implementation in Phase 11

    def _on_run_alignment_requested(self) -> None:
        """Handle alignment test request from diagnostics tab."""
        logger.info("Alignment test requested")

        if not self._device:
            self._status_strip.set_error("No device connected")
            return

        self._status_strip.set_analyzing("head alignment")
        # Placeholder: actual alignment test implementation in Phase 9

    def _on_run_self_test_requested(self) -> None:
        """Handle self-test request from diagnostics tab."""
        logger.info("Self-test requested")

        if not self._device:
            self._status_strip.set_error("No device connected")
            return

        self._status_strip.set_analyzing("drive self-test")
        # Placeholder: actual self-test implementation in Phase 9

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
