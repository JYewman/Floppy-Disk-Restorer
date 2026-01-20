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
    QSizePolicy,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, QSize, QTimer, QUrl, QThread
from PyQt6.QtGui import QAction, QKeySequence, QDesktopServices, QShortcut

from floppy_formatter.gui.panels import (
    DriveControlPanel,
    OperationToolbar,
    StatusStrip,
    AnalyticsPanel,
)
from floppy_formatter.gui.widgets import (
    CircularSectorMap,
    SectorMapToolbar,
    SectorInfoPanel,
    SectorStatus,
    ActivityType,
    SessionIndicator,
)
from floppy_formatter.gui.screens import SessionScreen
from floppy_formatter.core.session import DiskSession
from floppy_formatter.core.session_manager import SessionManager
from floppy_formatter.gui.dialogs import (
    show_about_dialog,
    show_settings_dialog,
    ExportDialog,
    ExportConfig,
    show_export_dialog,
    # Operation configuration dialogs
    show_format_config_dialog,
    FormatConfig,
    FormatType as FormatDialogType,
    show_restore_config_dialog,
    RestoreConfig as RestoreDialogConfig,
    RecoveryLevel as RestoreRecoveryLevel,
    show_analyze_config_dialog,
    AnalysisConfig as AnalyzeDialogConfig,
    AnalysisDepth as AnalyzeDialogDepth,
)
from floppy_formatter.gui.resources import get_icon, get_theme, set_theme
from floppy_formatter.gui.utils import (
    play_complete_sound,
    play_error_sound,
    play_success_sound,
)
from floppy_formatter.core.geometry import DiskGeometry
from floppy_formatter.hardware import GreaseweazleDevice, read_track_flux
from floppy_formatter.gui.workers.scan_worker import (
    ScanWorker, ScanMode, ScanResult, TrackResult,
)
from floppy_formatter.gui.workers.format_worker import (
    FormatWorker, FormatType, FormatResult,
)
from floppy_formatter.gui.workers.restore_worker import (
    RestoreWorker, RestoreConfig, RecoveryLevel, RecoveryStats,
)
from floppy_formatter.gui.tabs.recovery_tab import PassStats as RecoveryTabPassStats
from floppy_formatter.gui.tabs.errors_tab import SectorError, ErrorType
from floppy_formatter.gui.workers.analyze_worker import (
    AnalyzeWorker, AnalysisConfig, AnalysisDepth, AnalysisComponent, DiskAnalysisResult
)
from floppy_formatter.gui.workers.flux_capture_worker import FluxCaptureWorker
from floppy_formatter.gui.workers.disk_image_worker import DiskImageWorker, WriteImageResult
from floppy_formatter.gui.dialogs.write_image_config_dialog import (
    WriteImageConfigDialog, WriteImageConfig,
)
from floppy_formatter.analysis.flux_analyzer import FluxCapture
from floppy_formatter.gui.dialogs.batch_verify_config_dialog import (  # noqa: F401
    BatchVerifyConfigDialog, BatchVerifyConfig, FloppyDiskInfo, FloppyBrand,
)
from floppy_formatter.gui.dialogs.disk_prompt_dialog import (
    DiskPromptDialog, DiskPromptResult
)
from floppy_formatter.gui.workers.batch_verify_worker import (
    BatchVerifyWorker, SingleDiskResult, BatchVerificationResult, DiskGrade
)
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkbenchState(Enum):
    """Overall workbench state."""
    IDLE = auto()
    SCANNING = auto()
    FORMATTING = auto()
    RESTORING = auto()
    ANALYZING = auto()
    WRITING_IMAGE = auto()
    BATCH_VERIFYING = auto()


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
            available = list(self.THEMES.keys())
            raise KeyError(f"Theme '{theme_name}' not found. Available: {available}")

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
    Center panel containing dual sector maps (one per head) with toolbar and info panel.

    Layout:
    - Top: SectorMapToolbar
    - Center: Two CircularSectorMap widgets side by side (Head 0 and Head 1)
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

        # Horizontal splitter for maps and info panel
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

        # Container for dual sector maps
        maps_container = QWidget()
        maps_layout = QHBoxLayout(maps_container)
        maps_layout.setContentsMargins(4, 4, 4, 4)
        maps_layout.setSpacing(8)

        # Head 0 sector map with label
        head0_container = QWidget()
        head0_layout = QVBoxLayout(head0_container)
        head0_layout.setContentsMargins(0, 0, 0, 0)
        head0_layout.setSpacing(2)

        head0_label = QLabel("Head 0 (Side A)")
        head0_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head0_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-weight: bold;
                font-size: 11px;
                padding: 2px;
                background-color: #2d2d30;
                border: 1px solid #3a3d41;
                border-radius: 3px;
            }
        """)
        head0_layout.addWidget(head0_label)

        self._sector_map_h0 = CircularSectorMap(head_filter=0)
        head0_layout.addWidget(self._sector_map_h0, 1)
        maps_layout.addWidget(head0_container, 1)

        # Head 1 sector map with label
        head1_container = QWidget()
        head1_layout = QVBoxLayout(head1_container)
        head1_layout.setContentsMargins(0, 0, 0, 0)
        head1_layout.setSpacing(2)

        head1_label = QLabel("Head 1 (Side B)")
        head1_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head1_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-weight: bold;
                font-size: 11px;
                padding: 2px;
                background-color: #2d2d30;
                border: 1px solid #3a3d41;
                border-radius: 3px;
            }
        """)
        head1_layout.addWidget(head1_label)

        self._sector_map_h1 = CircularSectorMap(head_filter=1)
        head1_layout.addWidget(self._sector_map_h1, 1)
        maps_layout.addWidget(head1_container, 1)

        content_splitter.addWidget(maps_container)

        # Sector info panel (collapsible sidebar)
        self._info_panel = SectorInfoPanel()
        content_splitter.addWidget(self._info_panel)

        # Set initial sizes (maps take most space)
        content_splitter.setSizes([700, 250])

        # Don't allow info panel to be completely hidden
        content_splitter.setCollapsible(0, False)
        content_splitter.setCollapsible(1, True)

        main_layout.addWidget(content_splitter, 1)

        # Connect toolbar to both sector maps
        self._toolbar.connect_to_sector_map(self._sector_map_h0)
        self._toolbar.connect_to_sector_map(self._sector_map_h1)

        # Connect info panel to head 0 map (primary)
        self._info_panel.connect_to_sector_map(self._sector_map_h0)

        # Also connect head 1 map signals to info panel for hover/click updates
        self._sector_map_h1.sector_hovered.connect(self._info_panel.update_for_sector)
        self._sector_map_h1.sector_clicked.connect(self._info_panel.update_for_sector)

    def get_sector_map(self) -> CircularSectorMap:
        """Get the primary sector map widget (Head 0 for backwards compatibility)."""
        return self._sector_map_h0

    def get_sector_map_h0(self) -> CircularSectorMap:
        """Get the Head 0 sector map widget."""
        return self._sector_map_h0

    def get_sector_map_h1(self) -> CircularSectorMap:
        """Get the Head 1 sector map widget."""
        return self._sector_map_h1

    def get_toolbar(self) -> SectorMapToolbar:
        """Get the toolbar widget."""
        return self._toolbar

    def get_info_panel(self) -> SectorInfoPanel:
        """Get the info panel widget."""
        return self._info_panel

    def set_sector_status(self, sector_num: int, status, animate: bool = True) -> None:
        """Set sector status on the appropriate map based on sector head."""
        # Determine which head this sector belongs to
        sectors_per_track = 18
        head = (sector_num // sectors_per_track) % 2

        if head == 0:
            self._sector_map_h0.set_sector_status(sector_num, status, animate)
        else:
            self._sector_map_h1.set_sector_status(sector_num, status, animate)

    def set_active_sector(self, sector_num: int, activity) -> None:
        """Set active sector on the appropriate map."""
        sectors_per_track = 18
        head = (sector_num // sectors_per_track) % 2

        # Clear active on both maps first
        self._sector_map_h0.clear_active_sectors()
        self._sector_map_h1.clear_active_sectors()

        if head == 0:
            self._sector_map_h0.set_active_sector(sector_num, activity)
        else:
            self._sector_map_h1.set_active_sector(sector_num, activity)

    def update_scenes(self) -> None:
        """Update both sector map scenes."""
        self._sector_map_h0.scene.update()
        self._sector_map_h1.scene.update()

    def reset_all_sectors(self) -> None:
        """Reset all sectors on both maps to pending state."""
        self._sector_map_h0.reset_all_sectors()
        self._sector_map_h1.reset_all_sectors()

    def set_all_sectors_pending(self, total_sectors: int) -> None:
        """Set all sectors to pending state on both maps."""
        from floppy_formatter.gui.widgets.circular_sector_map import SectorStatus
        for sector in range(total_sectors):
            self.set_sector_status(sector, SectorStatus.PENDING, animate=False)
        self.update_scenes()


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

        # Start maximized (full size with title bar and taskbar visible)
        self.setWindowState(Qt.WindowState.WindowMaximized)

        # Initialize theme manager
        app = QApplication.instance()
        if app is None:
            raise RuntimeError(
                "QApplication instance not found. Create QApplication before MainWindow."
            )

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
        self._session_screen_visible = True  # Start with session screen visible

        # Session manager
        self._session_manager = SessionManager.instance()
        self._active_session: Optional[DiskSession] = None

        # Device reference (shared between panels)
        self._device: Optional[GreaseweazleDevice] = None

        # Geometry for current disk
        self._geometry: Optional[DiskGeometry] = None

        # Scan/operation results
        self._last_scan_result = None
        self._last_format_result = None
        self._last_restore_stats = None
        self._last_analysis_result = None
        self._last_operation_type: Optional[str] = None  # "scan", "format", "restore", "analyze"
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
        self._disk_image_worker: Optional[DiskImageWorker] = None
        self._disk_image_thread: Optional[QThread] = None
        self._write_image_config: Optional[WriteImageConfig] = None

        # Batch verification state
        self._batch_config: Optional[BatchVerifyConfig] = None
        self._batch_results: list = []
        self._current_batch_index: int = 0
        self._batch_start_time: Optional[datetime] = None
        self._batch_verify_worker: Optional[BatchVerifyWorker] = None
        self._batch_verify_thread: Optional[QThread] = None
        self._last_batch_result: Optional[BatchVerificationResult] = None

        # Build UI
        self._init_menu_bar()
        self._init_central_widget()
        self._init_keyboard_shortcuts()

        # Connect panel signals
        self._connect_signals()

        # Initial state
        self._update_state()

        # Update print button visibility based on settings
        self._update_print_button_visibility()

    def _init_menu_bar(self) -> None:
        """Initialize the menu bar."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        # Session menu items
        self._new_session_action = QAction("&New Session...", self)
        self._new_session_action.setShortcut(QKeySequence("Ctrl+N"))
        self._new_session_action.setStatusTip("Select a new disk format session")
        self._new_session_action.triggered.connect(self._on_new_session)
        file_menu.addAction(self._new_session_action)

        self._load_preset_action = QAction("&Load Session Preset...", self)
        self._load_preset_action.setStatusTip("Load a saved session preset")
        self._load_preset_action.triggered.connect(self._on_load_preset)
        file_menu.addAction(self._load_preset_action)

        self._save_preset_action = QAction("&Save Session Preset...", self)
        self._save_preset_action.setStatusTip("Save current session as a preset")
        self._save_preset_action.triggered.connect(self._on_save_preset)
        self._save_preset_action.setEnabled(False)
        file_menu.addAction(self._save_preset_action)

        file_menu.addSeparator()

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
        """Initialize the central widget with session screen and workbench layout."""
        # Create central widget with stacked layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout holds the stacked widget
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Stacked widget for session screen and workbench
        self._main_stack = QStackedWidget()
        main_layout.addWidget(self._main_stack)

        # Page 0: Session screen
        self._session_screen = SessionScreen()
        self._session_screen.session_selected.connect(self._on_session_selected)
        self._main_stack.addWidget(self._session_screen)

        # Page 1: Workbench content
        self._workbench_widget = self._create_workbench_widget()
        self._main_stack.addWidget(self._workbench_widget)

        # Start with session screen visible
        self._main_stack.setCurrentIndex(0)
        self._session_screen_visible = True

    def _create_workbench_widget(self) -> QWidget:
        """Create the main workbench widget with three-panel layout."""
        workbench = QWidget()

        # Main vertical layout - compact
        main_layout = QVBoxLayout(workbench)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        # Top panel - session indicator + drive controls + operation toolbar
        top_panel = self._create_top_panel()
        top_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_panel.setMaximumHeight(130)
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

        return workbench

    def _create_top_panel(self) -> QWidget:
        """Create the top panel with session indicator, drive controls, and operation toolbar."""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #2d2d30;
                border: 1px solid #3a3d41;
                border-radius: 3px;
            }
        """)

        # Vertical layout for three rows
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Row 0: Session indicator
        self._session_indicator = SessionIndicator()
        self._session_indicator.change_requested.connect(self._show_session_screen)
        layout.addWidget(self._session_indicator)

        # Horizontal separator
        separator0 = QFrame()
        separator0.setFrameShape(QFrame.Shape.HLine)
        separator0.setStyleSheet("QFrame { color: #3a3d41; }")
        separator0.setFixedHeight(1)
        layout.addWidget(separator0)

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
        self._operation_toolbar.report_export_clicked.connect(self._on_report_export_clicked)
        self._operation_toolbar.print_report_clicked.connect(self._on_print_report_clicked)
        self._operation_toolbar.batch_verify_clicked.connect(self._on_batch_verify_clicked)
        self._operation_toolbar.export_image_clicked.connect(self._on_export_image_clicked)

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
        logger.debug(
            "_update_state: is_connected=%s, is_idle=%s, enabling toolbar=%s",
            is_connected, is_idle, is_connected and is_idle
        )
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
        """Handle start button click - shows configuration dialog then starts operation."""
        operation = self._operation_toolbar.get_selected_operation()
        if not operation:
            return

        logger.info("Start clicked for operation: %s", operation)

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

        # Show operation-specific configuration dialog
        # If user cancels, the dialog returns None and we abort
        # Note: Scan starts immediately without a dialog (only one mode)
        if operation == "scan":
            pass  # No dialog needed for scan
        elif operation == "format":
            config = show_format_config_dialog(self)
            if config is None:
                logger.info("Format cancelled by user")
                return
            self._format_config = config
        elif operation == "restore":
            # Check if we have scan data to determine bad sector count
            bad_sector_count = len(self._last_bad_sectors) if hasattr(self, '_last_bad_sectors') else 0
            has_scan_data = hasattr(self, '_last_scan_result') and self._last_scan_result is not None
            config = show_restore_config_dialog(
                self,
                has_scan_data=has_scan_data,
                bad_sector_count=bad_sector_count
            )
            if config is None:
                logger.info("Restore cancelled by user")
                return
            self._restore_dialog_config = config
        elif operation == "analyze":
            config = show_analyze_config_dialog(self)
            if config is None:
                logger.info("Analyze cancelled by user")
                return
            self._analyze_config = config
        elif operation == "write_image":
            # Write image already shows its own dialog
            self._start_write_image_operation()
            return

        logger.info("Starting operation: %s with user-configured settings", operation)

        # Clear sector map from previous operation
        self._sector_map_panel.reset_all_sectors()

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

        # Start progress tracking in the Progress tab
        total_tracks = self._geometry.cylinders * self._geometry.heads
        total_sectors = self._geometry.total_sectors

        # Update status strip and start operation
        if operation == "scan":
            self._analytics_panel.start_progress("scan", total_tracks, total_sectors)
            self._status_strip.set_scanning(0, total_tracks)
            self._start_scan_operation()
        elif operation == "format":
            self._analytics_panel.start_progress("format", total_tracks, total_sectors)
            self._status_strip.set_formatting(0, total_tracks)
            self._start_format_operation()
        elif operation == "restore":
            # Get passes from restore config
            passes = self._restore_dialog_config.passes if hasattr(self, '_restore_dialog_config') else 5
            self._analytics_panel.start_progress("restore", total_tracks, total_sectors, passes)
            self._status_strip.set_restoring(1, passes, 0, total_sectors)
            self._start_restore_operation()
        elif operation == "analyze":
            self._analytics_panel.start_progress("analyze", total_tracks, total_sectors)
            self._status_strip.set_analyzing("flux data")
            self._start_analyze_operation()

    def _start_scan_operation(self) -> None:
        """Start the actual scan operation with worker thread."""
        # Clean up any existing worker
        self._cleanup_scan_worker()

        # Reset scan tracking counters for Progress tab
        self._scan_good_count = 0
        self._scan_bad_count = 0

        # Reset sector map to pending state (no animation for instant visual update)
        total_sectors = self._geometry.total_sectors
        self._sector_map_panel.set_all_sectors_pending(total_sectors)

        # Clear analytics tabs from previous operations
        self._analytics_panel.clear_overview()
        self._analytics_panel.clear_errors()
        self._analytics_panel.clear_recovery_data()

        # Scan uses standard mode without a configuration dialog
        scan_mode = ScanMode.STANDARD
        capture_flux = False
        logger.info("Starting scan with mode=%s, capture_flux=%s", scan_mode.name, capture_flux)

        # Create thread and worker
        self._scan_thread = QThread()
        self._scan_worker = ScanWorker(
            device=self._device,
            geometry=self._geometry,
            capture_flux=capture_flux,
            mode=scan_mode,
            session=self._active_session,
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
                logger.debug(
                    "_cleanup_scan_worker: cleaning up thread (isRunning=%s)",
                    self._scan_thread.isRunning()
                )
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

        # Track cumulative sector counts for Progress tab
        if not hasattr(self, '_scan_good_count'):
            self._scan_good_count = 0
            self._scan_bad_count = 0
        self._scan_good_count += track_result.good_count
        self._scan_bad_count += track_result.bad_count

        # Update sector map with track results - disable animation for immediate visual feedback
        for sector_result in track_result.sector_results:
            if sector_result.is_good:
                status = SectorStatus.GOOD
            else:
                status = SectorStatus.BAD
                # Add error to analytics panel for bad sectors
                error_type_enum = self._map_error_type(sector_result.error_type)
                error = SectorError.from_chs(
                    cyl=cylinder,
                    head=head,
                    sector=sector_result.sector_num,
                    error_type=error_type_enum,
                    details=sector_result.error_type or "Read failed",
                    sectors_per_track=self._geometry.sectors_per_track,
                )
                self._analytics_panel.add_error(error)
            self._sector_map_panel.set_sector_status(
                sector_result.linear_sector, status, animate=False
            )

        # Show activity on current track
        track_number = cylinder * 2 + head
        start_sector = track_number * self._geometry.sectors_per_track
        self._sector_map_panel.set_active_sector(start_sector, ActivityType.READING)

        # Update Progress tab with current sector counts
        self._analytics_panel.update_progress_sector_counts(
            good=self._scan_good_count,
            bad=self._scan_bad_count,
            recovered=0
        )

        # Force scene repaint after each track for visual feedback
        self._sector_map_panel.update_scenes()

    def _map_error_type(self, error_str: Optional[str]) -> ErrorType:
        """Map error type string to ErrorType enum."""
        if not error_str:
            return ErrorType.OTHER

        error_lower = error_str.lower()
        if "crc" in error_lower and "header" in error_lower:
            return ErrorType.HEADER_CRC
        elif "crc" in error_lower:
            return ErrorType.CRC
        elif "missing" in error_lower or "not found" in error_lower:
            return ErrorType.MISSING
        elif "weak" in error_lower:
            return ErrorType.WEAK
        elif "address" in error_lower or "idam" in error_lower:
            return ErrorType.NO_ADDRESS
        elif "deleted" in error_lower:
            return ErrorType.DELETED
        else:
            return ErrorType.OTHER

    def _on_sector_status(self, sector_num: int, is_good: bool, error_type: str) -> None:
        """Handle individual sector status update."""
        status = SectorStatus.GOOD if is_good else SectorStatus.BAD
        # Disable animation for immediate visual feedback during scanning
        self._sector_map_panel.set_sector_status(sector_num, status, animate=False)

    def _on_scan_complete(self, result: ScanResult) -> None:
        """Handle scan operation completion."""
        try:
            logger.info("Scan complete: %d good, %d bad sectors",
                        len(result.good_sectors), len(result.bad_sectors))

            # Store result
            self._last_scan_result = result
            self._last_operation_type = "scan"
            logger.debug("Scan result stored")

            # Enable report export
            self._enable_report_buttons(True)

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
                    "Scan complete: No sectors decoded (flux read issue?)"
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

            # Show completion dialog
            if len(result.bad_sectors) == 0 and good > 0:
                self._show_completion_dialog(
                    "Scan Successful",
                    f"All {total} sectors are readable.",
                    success=True,
                    details=f"Disk health: {self._disk_health}%"
                )
            elif good == 0 and len(result.bad_sectors) == 0:
                self._show_completion_dialog(
                    "Scan Error",
                    "No sectors could be decoded.",
                    success=False,
                    details="This may indicate a flux read issue or incompatible disk format."
                )
            else:
                details = (
                    f"Disk health: {self._disk_health}%\n\n"
                    "Consider running a Restore operation to attempt recovery."
                )
                self._show_completion_dialog(
                    "Bad Sectors Found",
                    f"Found {len(result.bad_sectors)} bad sector(s) out of {total}.",
                    success=False,
                    details=details
                )

            logger.info("_on_scan_complete finished successfully")
        except Exception as e:
            logger.exception("Error in _on_scan_complete: %s", e)
            self._status_strip.set_error(f"Scan completion error: {e}")

    def _on_scan_progress(self, progress: int) -> None:
        """Handle scan progress update."""
        # Update operation toolbar progress bar (now a no-op, kept for compatibility)
        self._operation_toolbar.set_progress(progress)

        # Update Progress tab with live progress
        total_tracks = self._geometry.cylinders * self._geometry.heads
        current_track = int((progress / 100) * total_tracks)
        current_head = current_track % 2
        current_cylinder = current_track // 2

        self._analytics_panel.update_progress(progress)
        self._analytics_panel.update_progress_track(current_cylinder, current_head)
        self._analytics_panel.update_progress_message(
            f"Scanning track {current_track} of {total_tracks} (Cylinder {current_cylinder}, Head {current_head})"
        )

        # Update status strip with progress
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
        self._sector_map_panel.set_all_sectors_pending(total_sectors)

        # Clear analytics tabs from previous operations
        self._analytics_panel.clear_overview()
        self._analytics_panel.clear_errors()
        self._analytics_panel.clear_recovery_data()

        # Get format configuration from dialog (stored in _on_start_clicked)
        format_config = getattr(self, '_format_config', None)

        if format_config:
            # Map dialog format type to worker format type
            type_map = {
                FormatDialogType.STANDARD: FormatType.STANDARD,
                FormatDialogType.LOW_LEVEL_REFRESH: FormatType.LOW_LEVEL_REFRESH,
                FormatDialogType.SECURE_ERASE: FormatType.SECURE_ERASE,
            }
            format_type = type_map.get(format_config.format_type, FormatType.STANDARD)
            fill_pattern = format_config.fill_pattern
            verify = format_config.verify
            logger.info("Format config from dialog: type=%s, pattern=0x%02X, verify=%s",
                        format_config.format_type.name, fill_pattern, verify)
        else:
            # Fallback defaults
            format_type = FormatType.STANDARD
            fill_pattern = 0xE5
            verify = True

        # Create thread and worker
        self._format_thread = QThread()
        self._format_worker = FormatWorker(
            device=self._device,
            geometry=self._geometry,
            fill_pattern=fill_pattern,
            verify=verify,
            format_type=format_type,
            session=self._active_session,
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
            self._sector_map_panel.set_sector_status(start_sector + i, status, animate=False)

        self._sector_map_panel.set_active_sector(start_sector, ActivityType.WRITING)

        # Force scene repaint for visual feedback
        self._sector_map_panel.update_scenes()

    def _on_track_verified(self, cylinder: int, head: int, verified_ok: bool) -> None:
        """Handle track verification completion."""
        logger.debug("Track verified: cyl=%d, head=%d, ok=%s", cylinder, head, verified_ok)
        if not verified_ok:
            track_number = cylinder * 2 + head
            start_sector = track_number * self._geometry.sectors_per_track
            for i in range(self._geometry.sectors_per_track):
                self._sector_map_panel.set_sector_status(
                    start_sector + i, SectorStatus.WEAK, animate=False
                )
            # Force scene repaint
            self._sector_map_panel.update_scenes()

    def _on_format_complete(self, result: FormatResult) -> None:
        """Handle format operation completion."""
        logger.info("Format complete: %d/%d tracks OK, %d bad sectors",
                    result.tracks_formatted, result.total_tracks, len(result.bad_sectors))

        # Store result and enable report export
        self._last_format_result = result
        self._last_operation_type = "format"
        self._enable_report_buttons(True)

        if result.success:
            self._status_strip.set_success(
                f"Format complete: {result.tracks_formatted} tracks formatted"
            )
            play_success_sound()
            self._show_completion_dialog(
                "Format Successful",
                f"Successfully formatted {result.tracks_formatted} tracks.",
                success=True,
                details=f"Total sectors: {result.tracks_formatted * 18}"
            )
        else:
            self._status_strip.set_warning(
                f"Format complete with errors: {result.tracks_failed} tracks failed"
            )
            play_error_sound()
            self._show_completion_dialog(
                "Format Error",
                "Format completed with errors.",
                success=False,
                details=(
                    f"Tracks formatted: {result.tracks_formatted}\n"
                    f"Tracks failed: {result.tracks_failed}\n"
                    f"Bad sectors: {len(result.bad_sectors)}"
                )
            )

    def _on_format_progress(self, progress: int) -> None:
        """Handle format progress update."""
        # Update operation toolbar progress bar (now a no-op, kept for compatibility)
        self._operation_toolbar.set_progress(progress)

        # Update Progress tab with live progress
        total_tracks = self._geometry.cylinders * self._geometry.heads
        current_track = int((progress / 100) * total_tracks)
        current_head = current_track % 2
        current_cylinder = current_track // 2

        self._analytics_panel.update_progress(progress)
        self._analytics_panel.update_progress_track(current_cylinder, current_head)
        self._analytics_panel.update_progress_message(
            f"Formatting track {current_track} of {total_tracks} (Cylinder {current_cylinder}, Head {current_head})"
        )

        # Update status strip
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

        # Clear analytics tabs for fresh restore data
        self._analytics_panel.clear_overview()
        self._analytics_panel.clear_recovery_data()
        self._analytics_panel.clear_errors()

        # Initialize restore tracking state
        self._restore_previous_bad_count = 0
        self._restore_initial_bad_count = 0

        # Get restore configuration from dialog (stored in _on_start_clicked)
        dialog_config = getattr(self, '_restore_dialog_config', None)

        if dialog_config:
            # Map dialog recovery level to worker recovery level
            level_map = {
                RestoreRecoveryLevel.STANDARD: RecoveryLevel.STANDARD,
                RestoreRecoveryLevel.AGGRESSIVE: RecoveryLevel.AGGRESSIVE,
                RestoreRecoveryLevel.FORENSIC: RecoveryLevel.FORENSIC,
            }
            recovery_level = level_map.get(dialog_config.recovery_level, RecoveryLevel.STANDARD)

            # Use settings from dialog
            passes = dialog_config.passes if dialog_config.convergence_mode else dialog_config.max_passes
            convergence_threshold = dialog_config.convergence_threshold
            multiread_mode = dialog_config.multiread_mode
            multiread_attempts = dialog_config.multiread_attempts
            pll_tuning = dialog_config.pll_tuning
            bit_slip_recovery = dialog_config.bit_slip_recovery

            logger.info("Restore config from dialog: level=%s, passes=%d, convergence=%d, "
                        "multiread=%s, pll=%s, bitslip=%s",
                        recovery_level.name, passes, convergence_threshold,
                        multiread_mode, pll_tuning, bit_slip_recovery)
        else:
            # Fallback defaults
            recovery_level = RecoveryLevel.STANDARD
            passes = 10
            convergence_threshold = 3
            multiread_mode = True
            multiread_attempts = 5
            pll_tuning = False
            bit_slip_recovery = False
            logger.info("Using default restore config: level=%s, passes=%d",
                        recovery_level.name, passes)

        # Create restore config for worker
        config = RestoreConfig(
            convergence_mode=dialog_config.convergence_mode if dialog_config else True,
            passes=passes,
            convergence_threshold=convergence_threshold,
            multiread_mode=multiread_mode,
            multiread_attempts=multiread_attempts,
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
            session=self._active_session,
        )
        self._restore_worker.moveToThread(self._restore_thread)

        # Connect worker signals
        self._restore_thread.started.connect(self._restore_worker.run)
        self._restore_worker.pass_started.connect(self._on_restore_pass_started)
        self._restore_worker.pass_complete.connect(self._on_restore_pass_complete)
        self._restore_worker.sector_recovered.connect(self._on_sector_recovered)
        self._restore_worker.sector_failed.connect(self._on_sector_failed)
        self._restore_worker.initial_scan_sector.connect(self._on_restore_initial_scan_sector)
        self._restore_worker.initial_scan_completed.connect(self._on_restore_initial_scan_completed)
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

        # Update Progress tab with pass information
        self._analytics_panel.update_progress_pass(pass_num, total_passes)
        self._analytics_panel.update_progress_message(
            f"Starting pass {pass_num} of {total_passes}"
        )

        self._status_strip.set_restoring(pass_num, total_passes, 0, self._geometry.total_sectors)

    def _on_restore_pass_complete(
        self, pass_num: int, bad_count: int, recovered_count: int
    ) -> None:
        """Handle restore pass completion."""
        logger.debug("Restore pass complete: pass=%d, bad=%d, recovered=%d",
                     pass_num, bad_count, recovered_count)

        # Update recovery tab with pass stats
        # Convert to recovery tab's PassStats format
        previous_bad = getattr(self, '_restore_previous_bad_count', bad_count + recovered_count)
        delta = previous_bad - bad_count

        pass_stats = RecoveryTabPassStats(
            pass_num=pass_num,
            bad_sectors=bad_count,
            recovered=recovered_count,
            failed=0,  # Will be updated on completion
            delta=-delta,  # Negative delta = improvement
            duration_seconds=0.0,  # Not available from signal
            technique="standard",
        )

        self._analytics_panel.update_recovery_progress(pass_num, pass_stats)
        self._analytics_panel.add_convergence_point(pass_num, bad_count)

        # Store for next pass delta calculation
        self._restore_previous_bad_count = bad_count

        # Update overview tab with current progress
        total_sectors = self._geometry.total_sectors
        good_sectors = total_sectors - bad_count
        self._analytics_panel.update_overview(
            total_sectors=total_sectors,
            good_sectors=good_sectors,
            bad_sectors=bad_count,
            recovered_sectors=recovered_count,
        )

        # Update Progress tab with sector counts
        self._analytics_panel.update_progress_sector_counts(
            good=good_sectors,
            bad=bad_count,
            recovered=recovered_count
        )
        self._analytics_panel.update_progress_message(
            f"Pass {pass_num} complete: {recovered_count} sectors recovered, {bad_count} bad remaining"
        )

    def _on_sector_recovered(self, sector_num: int, technique: str) -> None:
        """Handle sector recovery success."""
        logger.debug("Sector recovered: %d using %s", sector_num, technique)
        self._sector_map_panel.set_sector_status(sector_num, SectorStatus.RECOVERED, animate=False)
        self._sector_map_panel.set_active_sector(sector_num, ActivityType.WRITING)
        self._sector_map_panel.update_scenes()

    def _on_sector_failed(self, sector_num: int, reason: str) -> None:
        """Handle sector recovery failure."""
        logger.debug("Sector failed: %d - %s", sector_num, reason)
        self._sector_map_panel.set_sector_status(sector_num, SectorStatus.BAD, animate=False)
        self._sector_map_panel.update_scenes()

        # Add error to errors tab
        sectors_per_track = self._geometry.sectors_per_track
        cyl = sector_num // (sectors_per_track * 2)
        head = (sector_num // sectors_per_track) % 2
        sector = (sector_num % sectors_per_track) + 1

        error = SectorError.from_chs(
            cyl=cyl,
            head=head,
            sector=sector,
            error_type=ErrorType.CRC,  # Default to CRC error
            details=reason,
            sectors_per_track=sectors_per_track,
        )
        self._analytics_panel.add_error(error)

    def _on_restore_initial_scan_sector(self, sector_num: int, is_good: bool) -> None:
        """Handle initial scan sector result during restore."""
        status = SectorStatus.GOOD if is_good else SectorStatus.BAD
        self._sector_map_panel.set_sector_status(sector_num, status, animate=False)

        # Track bad sectors in errors tab
        if not is_good:
            sectors_per_track = self._geometry.sectors_per_track
            cyl = sector_num // (sectors_per_track * 2)
            head = (sector_num // sectors_per_track) % 2
            sector = (sector_num % sectors_per_track) + 1

            error = SectorError.from_chs(
                cyl=cyl,
                head=head,
                sector=sector,
                error_type=ErrorType.CRC,
                details="Initial scan - sector unreadable",
                sectors_per_track=sectors_per_track,
            )
            self._analytics_panel.add_error(error)

            # Track initial bad count for recovery tab
            if not hasattr(self, '_restore_initial_bad_count'):
                self._restore_initial_bad_count = 0
            self._restore_initial_bad_count += 1

    def _on_restore_initial_scan_completed(self, initial_bad_count: int) -> None:
        """Handle initial scan completion during restore."""
        logger.info("Restore initial scan complete: %d bad sectors found", initial_bad_count)

        # Set up recovery tab with initial bad sector count
        self._analytics_panel.set_initial_bad_sectors(initial_bad_count)
        self._restore_previous_bad_count = initial_bad_count
        self._restore_initial_bad_count = initial_bad_count

        # Add initial convergence point (pass 0 = baseline before recovery)
        # This establishes the starting point so the chart can draw lines
        self._analytics_panel.add_convergence_point(0, initial_bad_count)

        # Update overview with initial scan results
        total_sectors = self._geometry.total_sectors
        good_sectors = total_sectors - initial_bad_count
        self._analytics_panel.update_overview(
            total_sectors=total_sectors,
            good_sectors=good_sectors,
            bad_sectors=initial_bad_count,
            recovered_sectors=0,
        )

    def _on_restore_complete(self, stats: RecoveryStats) -> None:
        """Handle restore operation completion."""
        logger.info("Restore complete: %d/%d sectors recovered",
                    stats.sectors_recovered, stats.initial_bad_sectors)

        # Store result and enable report export
        self._last_restore_stats = stats
        self._last_operation_type = "restore"
        self._enable_report_buttons(True)

        if stats.final_bad_sectors == 0:
            self._status_strip.set_success(
                f"Restore complete: All {stats.sectors_recovered} bad sectors recovered"
            )
            play_success_sound()
            details = (
                f"Passes completed: {stats.passes_completed}\n"
                f"Time elapsed: {stats.elapsed_time:.1f}s"
            )
            self._show_completion_dialog(
                "Restore Successful",
                f"All {stats.sectors_recovered} bad sector(s) have been recovered.",
                success=True,
                details=details
            )
        elif stats.sectors_recovered > 0:
            self._status_strip.set_warning(
                f"Restore complete: {stats.sectors_recovered} recovered, "
                f"{stats.final_bad_sectors} unrecoverable"
            )
            play_complete_sound()
            details = (
                f"Remaining bad sectors: {stats.final_bad_sectors}\n"
                f"Passes completed: {stats.passes_completed}\n"
                f"Time elapsed: {stats.elapsed_time:.1f}s"
            )
            self._show_completion_dialog(
                "Partial Recovery",
                f"Recovered {stats.sectors_recovered} of "
                f"{stats.initial_bad_sectors} bad sector(s).",
                success=False,
                details=details
            )
        else:
            self._status_strip.set_error(
                f"Restore failed: {stats.final_bad_sectors} sectors unrecoverable"
            )
            play_error_sound()
            details = (
                "The disk may have physical damage that cannot be repaired.\n"
                f"Passes completed: {stats.passes_completed}"
            )
            self._show_completion_dialog(
                "Restore Failed",
                f"Could not recover any of the {stats.final_bad_sectors} bad sector(s).",
                success=False,
                details=details
            )

        # Update health based on recovery
        total_sectors = self._geometry.total_sectors
        if total_sectors > 0:
            good_sectors = total_sectors - stats.final_bad_sectors
            self._disk_health = int((good_sectors / total_sectors) * 100)
            self._status_strip.set_health(self._disk_health)

            # Update overview tab with final results
            self._analytics_panel.update_overview(
                total_sectors=total_sectors,
                good_sectors=good_sectors,
                bad_sectors=stats.final_bad_sectors,
                recovered_sectors=stats.sectors_recovered,
                health_score=self._disk_health,
            )

        # Update recovery tab with final stats
        from floppy_formatter.gui.tabs.recovery_tab import RecoveryStats as RecoveryTabStats
        final_recovery_stats = RecoveryTabStats(
            initial_bad_sectors=stats.initial_bad_sectors,
            final_bad_sectors=stats.final_bad_sectors,
            sectors_recovered=stats.sectors_recovered,
            passes_completed=stats.passes_completed,
            converged=stats.converged,
            convergence_pass=stats.convergence_pass or 0,
            elapsed_time=stats.elapsed_time,
        )
        self._analytics_panel.set_recovery_complete(final_recovery_stats)

        # Clean up restore tracking state
        if hasattr(self, '_restore_previous_bad_count'):
            del self._restore_previous_bad_count
        if hasattr(self, '_restore_initial_bad_count'):
            del self._restore_initial_bad_count

    def _on_restore_progress(self, progress: int) -> None:
        """Handle restore progress update."""
        # Update operation toolbar progress bar (now a no-op, kept for compatibility)
        self._operation_toolbar.set_progress(progress)

        # Update Progress tab with live progress
        self._analytics_panel.update_progress(progress)
        self._analytics_panel.update_progress_message(f"Restoring disk: {progress}% complete")

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

        # Clear analytics tabs from previous operations
        self._analytics_panel.clear_overview()
        self._analytics_panel.clear_errors()
        self._analytics_panel.clear_recovery_data()

        # Get analyze configuration from dialog (stored in _on_start_clicked)
        dialog_config = getattr(self, '_analyze_config', None)

        if dialog_config:
            # Map dialog depth to worker depth
            depth_map = {
                AnalyzeDialogDepth.QUICK: AnalysisDepth.QUICK,
                AnalyzeDialogDepth.STANDARD: AnalysisDepth.STANDARD,
                AnalyzeDialogDepth.FULL: AnalysisDepth.COMPREHENSIVE,
            }
            depth = depth_map.get(dialog_config.depth, AnalysisDepth.STANDARD)
            revolutions = dialog_config.revolutions_per_track

            # Build components list based on dialog settings
            components = [
                AnalysisComponent.FLUX_TIMING,
                AnalysisComponent.SIGNAL_QUALITY,
            ]
            if dialog_config.analyze_flux:
                components.append(AnalysisComponent.ENCODING)
            if dialog_config.analyze_alignment:
                components.append(AnalysisComponent.WEAK_BITS)
            if dialog_config.analyze_forensics:
                components.append(AnalysisComponent.FORENSICS)

            logger.info("Analyze config from dialog: depth=%s, revolutions=%d, "
                        "flux=%s, alignment=%s, forensics=%s",
                        depth.name, revolutions, dialog_config.analyze_flux,
                        dialog_config.analyze_alignment, dialog_config.analyze_forensics)
        else:
            # Fallback defaults
            depth = AnalysisDepth.STANDARD
            revolutions = 2
            components = [
                AnalysisComponent.FLUX_TIMING,
                AnalysisComponent.SIGNAL_QUALITY,
                AnalysisComponent.ENCODING,
            ]
            logger.info("Using default analyze config: depth=%s, revolutions=%d",
                        depth.name, revolutions)

        logger.info("Starting analysis with depth=%s, revolutions=%d, components=%s",
                    depth.name, revolutions, [c.name for c in components])

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
            session=self._active_session,
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

        # Add errors for bad (F) or weak (D) grades
        if result.grade in ('F', 'D'):
            error_type = ErrorType.WEAK if result.grade == 'D' else ErrorType.OTHER
            quality = getattr(result, 'quality_score', 0)
            details = f"Track grade: {result.grade} (quality: {quality:.0%})"
            for i in range(self._geometry.sectors_per_track):
                error = SectorError.from_chs(
                    cyl=cylinder,
                    head=head,
                    sector=i + 1,  # 1-based sector number
                    error_type=error_type,
                    details=details,
                    sectors_per_track=self._geometry.sectors_per_track,
                )
                self._analytics_panel.add_error(error)

        for i in range(self._geometry.sectors_per_track):
            self._sector_map_panel.set_sector_status(start_sector + i, status, animate=False)

        self._sector_map_panel.set_active_sector(start_sector, ActivityType.READING)

        # Force scene repaint for visual feedback
        self._sector_map_panel.update_scenes()

    def _on_flux_quality_update(self, cylinder: int, head: int, score: float) -> None:
        """Handle flux quality update."""
        pass  # Quality is displayed via track_analyzed

    def _on_analysis_complete(self, result: DiskAnalysisResult) -> None:
        """Handle analysis operation completion."""
        logger.info("Analysis complete: grade=%s, score=%.1f",
                    result.overall_grade, result.overall_quality_score)

        # Store result and enable report export
        self._last_analysis_result = result
        self._last_operation_type = "analyze"
        self._enable_report_buttons(True)

        # Update disk health
        self._disk_health = int(result.overall_quality_score)
        self._status_strip.set_health(self._disk_health)

        grade = result.overall_grade
        if grade in ('A', 'B'):
            self._status_strip.set_success(
                f"Analysis complete: Grade {grade} ({result.overall_quality_score:.0f}%)"
            )
            play_success_sound()
            self._show_completion_dialog(
                "Analysis Successful",
                f"Disk received grade {grade} ({result.overall_quality_score:.0f}%).",
                success=True,
                details="The disk is in good condition."
            )
        elif grade == 'C':
            self._status_strip.set_warning(
                f"Analysis complete: Grade {grade} - Some degradation detected"
            )
            play_complete_sound()
            self._show_completion_dialog(
                "Analysis Complete",
                f"Disk received grade {grade} ({result.overall_quality_score:.0f}%).",
                success=False,
                details="Some degradation detected. Consider backing up the disk."
            )
        else:
            self._status_strip.set_error(
                f"Analysis complete: Grade {grade} - Significant issues found"
            )
            play_error_sound()
            self._show_completion_dialog(
                "Analysis Warning",
                f"Disk received grade {grade} ({result.overall_quality_score:.0f}%).",
                success=False,
                details=(
                    "Significant issues found. The disk may need restoration or "
                    "data should be recovered immediately."
                )
            )

        # Update analytics panel with analysis results
        # Convert analysis result to overview format
        grade_dist = result.get_grade_distribution()
        good_grades = grade_dist.get('A', 0) + grade_dist.get('B', 0)
        good_sectors = good_grades * self._geometry.sectors_per_track
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

        # Update analysis tab with full results
        self._analytics_panel.update_analysis(result)

        # Switch to Analysis tab to show results
        self._analytics_panel.show_tab("analysis")

    def _on_analyze_progress(self, progress: int) -> None:
        """Handle analyze progress update."""
        # Update operation toolbar progress bar (now a no-op, kept for compatibility)
        self._operation_toolbar.set_progress(progress)

        # Update Progress tab with live progress
        total_tracks = self._geometry.cylinders * self._geometry.heads
        current_track = int((progress / 100) * total_tracks)
        current_head = current_track % 2
        current_cylinder = current_track // 2

        self._analytics_panel.update_progress(progress)
        self._analytics_panel.update_progress_track(current_cylinder, current_head)
        self._analytics_panel.update_progress_message(
            f"Analyzing track {current_track} of {total_tracks} (Cylinder {current_cylinder}, Head {current_head})"
        )

        # Update status strip
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

    # =========================================================================
    # Write Image Operation
    # =========================================================================

    def _start_write_image_operation(self) -> None:
        """Start the write image operation with configuration dialog."""
        # Show configuration dialog
        dialog = WriteImageConfigDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            # User cancelled - reset state
            self._state = WorkbenchState.IDLE
            self._operation_toolbar.stop_operation()
            self._drive_control.resume_rpm_polling()
            self._update_state()
            return

        self._write_image_config = dialog.get_config()
        if not self._write_image_config.format_spec:
            self._state = WorkbenchState.IDLE
            self._operation_toolbar.stop_operation()
            self._drive_control.resume_rpm_polling()
            self._update_state()
            return

        # Clean up any existing worker
        self._cleanup_disk_image_worker()

        # Get format spec details
        spec = self._write_image_config.format_spec
        format_name = spec.name
        total_sectors = spec.total_sectors

        # Initialize sector map with pending sectors
        self._sector_map_panel.set_all_sectors_pending(total_sectors)

        # Clear analytics tabs from previous operations
        self._analytics_panel.clear_overview()
        self._analytics_panel.clear_errors()
        self._analytics_panel.clear_recovery_data()

        # Update status
        self._status_strip.set_formatting(0, spec.total_tracks)

        logger.info("Starting write image operation: %s", format_name)

        # Create thread and worker
        self._disk_image_thread = QThread()
        self._disk_image_worker = DiskImageWorker(
            device=self._device,
            format_spec=self._write_image_config.format_spec,
            verify=self._write_image_config.verify_after_write,
        )
        self._disk_image_worker.moveToThread(self._disk_image_thread)

        # Connect worker signals
        self._disk_image_thread.started.connect(self._disk_image_worker.run)
        self._disk_image_worker.track_written.connect(self._on_image_track_written)
        self._disk_image_worker.track_verified.connect(self._on_image_track_verified)
        self._disk_image_worker.write_complete.connect(self._on_write_image_complete)
        self._disk_image_worker.progress.connect(self._on_write_image_progress)
        self._disk_image_worker.status_update.connect(self._on_write_image_status)
        self._disk_image_worker.error.connect(self._on_write_image_error)
        self._disk_image_worker.device_error.connect(self._on_write_image_error)
        self._disk_image_worker.finished.connect(self._on_write_image_finished)

        logger.info("Starting disk image worker thread")
        self._disk_image_thread.start()

    def _cleanup_disk_image_worker(self) -> None:
        """Clean up disk image worker and thread."""
        if self._disk_image_worker:
            self._disk_image_worker.cancel()
            self._disk_image_worker = None

        if self._disk_image_thread:
            if self._disk_image_thread.isRunning():
                self._disk_image_thread.quit()
                self._disk_image_thread.wait(3000)
            self._disk_image_thread = None

    def _on_image_track_written(self, cylinder: int, head: int, success: bool) -> None:
        """Handle track written signal from disk image worker."""
        track_number = cylinder * 2 + head

        if self._write_image_config and self._write_image_config.format_spec:
            spec = self._write_image_config.format_spec
            start_sector = track_number * spec.sectors_per_track

            # Update sector map
            status = SectorStatus.GOOD if success else SectorStatus.BAD
            for i in range(spec.sectors_per_track):
                self._sector_map_panel.set_sector_status(
                    start_sector + i, status, animate=False
                )
            self._sector_map_panel.update_scenes()

    def _on_image_track_verified(self, cylinder: int, head: int, verified: bool) -> None:
        """Handle track verified signal from disk image worker."""
        if not verified:
            track_number = cylinder * 2 + head
            logger.warning(
                "Track verification failed: C%d H%d (track %d)",
                cylinder, head, track_number
            )

    def _on_write_image_complete(self, result: WriteImageResult) -> None:
        """Handle write image completion."""
        logger.info(
            "Write image complete: %s, %d/%d tracks, %.1fs",
            result.format_spec.name,
            result.tracks_written,
            result.total_tracks,
            result.duration_seconds
        )

        # Show completion message
        if result.cancelled:
            self._status_strip.set_warning("Write cancelled")
            play_error_sound()
        elif result.tracks_failed > 0:
            self._status_strip.set_error(
                f"Write completed with {result.tracks_failed} failed tracks"
            )
            play_error_sound()
            QMessageBox.warning(
                self, "Write Completed with Errors",
                f"Wrote {result.format_spec.name} image.\n\n"
                f"Tracks written: {result.tracks_written}/{result.total_tracks}\n"
                f"Failed tracks: {result.tracks_failed}\n"
                f"Duration: {result.duration_seconds:.1f}s"
            )
        else:
            self._status_strip.set_success(
                f"Write complete: {result.format_spec.name}"
            )
            play_complete_sound()
            QMessageBox.information(
                self, "Write Complete",
                f"Successfully wrote {result.format_spec.name} image.\n\n"
                f"Platform: {result.format_spec.platform.value}\n"
                f"Tracks: {result.tracks_written}\n"
                f"Duration: {result.duration_seconds:.1f}s"
            )

    def _on_write_image_progress(self, progress: int) -> None:
        """Handle write image progress update."""
        self._operation_toolbar.set_progress(progress)

    def _on_write_image_status(self, status: str) -> None:
        """Handle write image status message."""
        self._status_strip.set_operation_status(status)

    def _on_write_image_error(self, error: str) -> None:
        """Handle write image error."""
        logger.error("Write image error: %s", error)
        self._status_strip.set_error(error)

    def _on_write_image_finished(self) -> None:
        """Handle write image worker finished (cleanup)."""
        logger.debug("Write image worker finished")
        self._on_operation_complete()
        self._cleanup_disk_image_worker()

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
        if self._disk_image_worker:
            self._disk_image_worker.cancel()

        self._state = WorkbenchState.IDLE
        self._operation_toolbar.stop_operation()
        self._status_strip.set_warning("Operation cancelled")
        self._update_state()

        # Turn off the motor - use force=True since we may have interrupted an operation
        if self._device and self._device.is_connected():
            try:
                self._device.motor_off(force=True)
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
        self._cleanup_disk_image_worker()

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

            # Update state FIRST to ensure toolbar is enabled before stop_operation
            # This sets _is_enabled=True so stop_operation's _update_control_states works
            logger.debug("_on_operation_complete: updating state to re-enable toolbar")
            self._update_state()

            logger.debug("_on_operation_complete: stopping operation toolbar")
            self._operation_toolbar.stop_operation()
            self._operation_toolbar.set_progress(100)

            # Stop progress tracking in Progress tab
            logger.debug("_on_operation_complete: stopping progress tracking")
            self._analytics_panel.stop_progress(success=True, message="Operation completed successfully")

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

    def _show_completion_dialog(
        self,
        title: str,
        message: str,
        success: bool = True,
        details: Optional[str] = None
    ) -> None:
        """
        Show a completion dialog for an operation.

        Args:
            title: Dialog title (e.g., "Scan Complete")
            message: Main message to show
            success: True for success icon, False for warning icon
            details: Optional detailed information
        """
        try:
            if success:
                icon = QMessageBox.Icon.Information
            else:
                icon = QMessageBox.Icon.Warning

            msg_box = QMessageBox(self)
            msg_box.setIcon(icon)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)

            if details:
                msg_box.setInformativeText(details)

            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
        except Exception as e:
            logger.exception("Error showing completion dialog: %s", e)

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

            if alignment_ok:
                status = "Aligned"
            elif avg_score >= 0.5:
                status = "Slightly Off"
            else:
                status = "Misaligned"
            alignment_results = AlignmentResults(
                score=avg_score * 100,  # Convert to 0-100 scale
                status=status,
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
            selected = self._device.selected_drive
            drive_unit = selected if selected is not None else 0

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
                    status=(TestStatus.PASS if calibration.bit_timing.within_spec
                            else TestStatus.FAIL),
                    details=f"{calibration.bit_timing.bit_cell_us:.3f}µs bit cell",
                ),
                SelfTestItem(
                    name="Head alignment",
                    status=(TestStatus.PASS if calibration.health.alignment_ok
                            else TestStatus.FAIL),
                    details=f"Score: {calibration.health.score:.0%}",
                ),
                SelfTestItem(
                    name="Overall health",
                    status=(TestStatus.PASS if calibration.calibration_successful
                            else TestStatus.FAIL),
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
        show_settings_dialog(
            self,
            on_theme_changed=self._on_theme_changed,
            on_settings_saved=self._on_settings_saved
        )

    def _on_settings_saved(self) -> None:
        """Handle settings saved - update UI based on new settings."""
        # Update print button visibility based on printer settings
        self._update_print_button_visibility()

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
    # Session Handlers
    # =========================================================================

    def _on_new_session(self) -> None:
        """Handle File > New Session menu action."""
        self._show_session_screen()

    def _on_load_preset(self) -> None:
        """Handle File > Load Session Preset menu action."""
        from floppy_formatter.gui.dialogs.session_preset_dialog import SessionPresetDialog

        dialog = SessionPresetDialog(mode="manage", parent=self)
        dialog.exec()

        # If a session was loaded and activated, update the UI
        if self._session_manager.has_active_session():
            session = self._session_manager.active_session
            self._apply_session(session)

    def _on_save_preset(self) -> None:
        """Handle File > Save Session Preset menu action."""
        if not self._active_session:
            QMessageBox.warning(
                self, "No Session",
                "No active session to save. Select a disk format first."
            )
            return

        from floppy_formatter.gui.dialogs.session_preset_dialog import SessionPresetDialog

        dialog = SessionPresetDialog(mode="save", session=self._active_session, parent=self)
        dialog.exec()

    def _on_session_selected(self, session: DiskSession) -> None:
        """Handle session selection from the session screen."""
        logger.info(f"Session selected: {session.gw_format}")
        self._apply_session(session)
        self._hide_session_screen()

    def _apply_session(self, session: DiskSession) -> None:
        """
        Apply a session configuration to the workbench.

        Updates geometry, sector maps, and UI to reflect the session.
        """
        self._active_session = session
        self._session_manager.set_active_session(session)

        # Update geometry from session
        self._geometry = session.to_geometry()
        logger.info(f"Geometry set: {self._geometry.cylinders}C/{self._geometry.heads}H/"
                    f"{self._geometry.sectors_per_track}S")

        # Update session indicator
        self._session_indicator.update_session(session)

        # Update sector maps with new geometry
        self._update_sector_maps_geometry(session)

        # Enable save preset action
        self._save_preset_action.setEnabled(True)

        # Update status strip
        self._status_strip.set_success(f"Session: {session.name}")

        # Update drive status with disk type from session
        disk_type = f"{session.disk_size} {session.encoding.upper()}"
        if hasattr(self, '_status_strip'):
            self._status_strip.set_drive_status(disk_type, None, True)

    def _update_sector_maps_geometry(self, session: DiskSession) -> None:
        """
        Update sector maps to reflect session geometry.

        Args:
            session: The session with geometry information
        """
        if hasattr(self, '_sector_map_panel'):
            # Update both sector maps with new geometry
            h0_map = self._sector_map_panel.get_sector_map_h0()
            h1_map = self._sector_map_panel.get_sector_map_h1()

            if hasattr(h0_map, 'set_geometry'):
                h0_map.set_geometry(
                    cylinders=session.cylinders,
                    heads=session.heads,
                    sectors_per_track=session.sectors_per_track
                )
            if hasattr(h1_map, 'set_geometry'):
                h1_map.set_geometry(
                    cylinders=session.cylinders,
                    heads=session.heads,
                    sectors_per_track=session.sectors_per_track
                )

            # Reset all sectors to pending/unscanned state
            self._sector_map_panel.reset_all_sectors()

    def _show_session_screen(self) -> None:
        """Show the session selection screen."""
        if self._state != WorkbenchState.IDLE:
            QMessageBox.warning(
                self, "Operation in Progress",
                "Cannot change session while an operation is running."
            )
            return

        self._main_stack.setCurrentIndex(0)
        self._session_screen_visible = True

        # If there's an active session, show it in the session screen
        if self._active_session:
            self._session_screen.set_session(self._active_session)

    def _hide_session_screen(self) -> None:
        """Hide the session screen and show the workbench."""
        self._main_stack.setCurrentIndex(1)
        self._session_screen_visible = False

    def is_session_screen_visible(self) -> bool:
        """Check if the session screen is currently visible."""
        return self._session_screen_visible

    def get_active_session(self) -> Optional[DiskSession]:
        """Get the currently active session."""
        return self._active_session

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
    # Report Export
    # =========================================================================

    def _on_report_export_clicked(self) -> None:
        """Handle Export Report button click - generate and export report for last operation."""
        from PyQt6.QtWidgets import QFileDialog
        from floppy_formatter.reports import ReportGenerator, DARK_THEME
        from floppy_formatter.core.settings import get_settings
        from datetime import datetime

        if not self._last_operation_type:
            QMessageBox.warning(
                self,
                "No Report Data",
                "No operation has been completed yet. Run a scan, format, "
                "restore, or analyze operation first."
            )
            return

        # Get settings to determine report format
        settings = get_settings()
        report_format = settings.export.get_report_format()

        # Determine file extension and filter based on format
        # Keys are lowercase to match ReportFormat.value (e.g., "html", "pdf", "txt")
        format_filters = {
            "html": ("HTML Files (*.html)", ".html"),
            "pdf": ("PDF Files (*.pdf)", ".pdf"),
            "txt": ("Text Files (*.txt)", ".txt"),
        }
        default_filter = ("HTML Files (*.html)", ".html")
        filter_text, extension = format_filters.get(report_format.value, default_filter)

        # Generate default filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"floppy_workbench_{self._last_operation_type}_{timestamp}{extension}"

        # Show save dialog
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report",
            default_filename,
            f"{filter_text};;All Files (*.*)"
        )

        if not filepath:
            return  # User cancelled

        try:
            # Build report data based on operation type
            report_type, report_data = self._build_report_data()

            # Generate sector map images as base64
            sector_map_h0_base64 = self._export_sector_map_as_base64(0)
            sector_map_h1_base64 = self._export_sector_map_as_base64(1)

            # Add sector maps to raw data
            report_data.raw_data["sector_map_h0_image"] = sector_map_h0_base64
            report_data.raw_data["sector_map_h1_image"] = sector_map_h1_base64

            # Add app logo to raw data
            logo_base64 = self._get_app_logo_base64()
            if logo_base64:
                report_data.raw_data["app_logo"] = logo_base64

            # Create generator and generate report
            generator = ReportGenerator(report_type, report_data, DARK_THEME)

            # Export in appropriate format
            if filepath.endswith(".html"):
                generator.export_html(filepath)
            elif filepath.endswith(".pdf"):
                generator.export_pdf(filepath)
            elif filepath.endswith(".txt"):
                generator.export_text(filepath)
            else:
                # Default to HTML
                generator.export_html(filepath)

            self._status_strip.set_success(f"Report exported to: {filepath}")
            logger.info("Report exported successfully to: %s", filepath)

            # Offer to open the report
            result = QMessageBox.question(
                self,
                "Report Exported",
                f"Report has been exported to:\n{filepath}\n\nWould you like to open it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if result == QMessageBox.StandardButton.Yes:
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))

        except Exception as e:
            logger.exception("Failed to export report: %s", e)
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export report:\n{str(e)}"
            )
            self._status_strip.set_error(f"Report export failed: {e}")

    def _build_report_data(self):
        """Build ReportData based on the last operation type."""
        from floppy_formatter.reports import (
            ReportType,
            ReportMetadata,
            ReportData,
            SummaryItem,
            StatusLevel,
        )
        from datetime import datetime

        device_path = ""
        if self._device:
            if hasattr(self._device, 'port'):
                device_path = str(self._device.port)
            else:
                device_path = "Greaseweazle"

        geometry_str = ""
        if self._geometry:
            geometry_str = (
                f"{self._geometry.cylinders}C × {self._geometry.heads}H × "
                f"{self._geometry.sectors_per_track}S"
            )

        raw_data = {}

        if self._last_operation_type == "scan":
            report_type = ReportType.SCAN
            result = self._last_scan_result

            raw_data = {
                "total_sectors": result.total_sectors,
                "good_sectors": len(result.good_sectors),
                "bad_sectors": len(result.bad_sectors),
                "bad_sector_list": result.bad_sectors,
                "good_sector_list": result.good_sectors,
                "elapsed_ms": (
                    int(result.elapsed_time * 1000) if hasattr(result, 'elapsed_time') else 0
                ),
                "health_percentage": self._disk_health or 0,
            }

            status = StatusLevel.SUCCESS if len(result.bad_sectors) == 0 else StatusLevel.WARNING
            if len(result.bad_sectors) == 0:
                status_message = "All sectors readable"
            else:
                status_message = f"{len(result.bad_sectors)} bad sectors found"

            summary_items = [
                SummaryItem("Total Sectors", result.total_sectors),
                SummaryItem("Good Sectors", len(result.good_sectors), StatusLevel.SUCCESS),
                SummaryItem(
                    "Bad Sectors", len(result.bad_sectors),
                    StatusLevel.SUCCESS if len(result.bad_sectors) == 0 else StatusLevel.ERROR
                ),
                SummaryItem(
                    "Disk Health", f"{self._disk_health or 0}%",
                    StatusLevel.SUCCESS if (self._disk_health or 0) >= 95 else StatusLevel.WARNING
                ),
            ]

            metadata = ReportMetadata(
                title="Disk Scan Report",
                subtitle=f"Scan completed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                report_type=report_type,
                device_path=device_path,
                geometry=geometry_str,
            )

        elif self._last_operation_type == "format":
            report_type = ReportType.FORMAT
            result = self._last_format_result

            raw_data = {
                "tracks_formatted": result.tracks_formatted,
                "total_tracks": result.total_tracks,
                "tracks_failed": result.tracks_failed,
                "bad_sectors": result.bad_sectors,
                "success": result.success,
                "verify_passed": getattr(result, 'verify_passed', True),
            }

            status = StatusLevel.SUCCESS if result.success else StatusLevel.ERROR
            if result.success:
                status_message = "Format completed successfully"
            else:
                status_message = f"Format completed with {result.tracks_failed} failed tracks"

            summary_items = [
                SummaryItem("Total Tracks", result.total_tracks),
                SummaryItem("Tracks Formatted", result.tracks_formatted, StatusLevel.SUCCESS),
                SummaryItem(
                    "Tracks Failed", result.tracks_failed,
                    StatusLevel.SUCCESS if result.tracks_failed == 0 else StatusLevel.ERROR
                ),
                SummaryItem("Status", "Success" if result.success else "Failed", status),
            ]

            metadata = ReportMetadata(
                title="Disk Format Report",
                subtitle=f"Format completed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                report_type=report_type,
                device_path=device_path,
                geometry=geometry_str,
            )

        elif self._last_operation_type == "restore":
            report_type = ReportType.RECOVERY
            stats = self._last_restore_stats

            # Get convergence data from analytics panel
            convergence_history = []
            try:
                recovery_tab = self._analytics_panel._tabs.get("recovery")
                if recovery_tab and hasattr(recovery_tab, '_convergence_points'):
                    for pass_num, bad_count in recovery_tab._convergence_points:
                        convergence_history.append({
                            "pass": pass_num,
                            "bad_sectors": bad_count,
                        })
            except Exception:
                pass

            raw_data = {
                "initial_bad": stats.initial_bad_sectors,
                "final_bad": stats.final_bad_sectors,
                "sectors_recovered": stats.sectors_recovered,
                "passes_executed": stats.passes_completed,
                "converged": stats.converged,
                "convergence_pass": stats.convergence_pass,
                "elapsed_ms": int(stats.elapsed_time * 1000) if stats.elapsed_time else 0,
                "convergence_history": convergence_history,
                "recovery_percentage": int(
                    (stats.sectors_recovered / max(stats.initial_bad_sectors, 1)) * 100
                ),
            }

            if stats.final_bad_sectors == 0:
                status = StatusLevel.SUCCESS
                status_message = "All sectors recovered successfully"
            elif stats.sectors_recovered > 0:
                status = StatusLevel.WARNING
                status_message = (
                    f"Partial recovery: {stats.sectors_recovered} of "
                    f"{stats.initial_bad_sectors} sectors recovered"
                )
            else:
                status = StatusLevel.ERROR
                status_message = "Recovery failed - no sectors recovered"

            summary_items = [
                SummaryItem("Initial Bad Sectors", stats.initial_bad_sectors),
                SummaryItem(
                    "Sectors Recovered", stats.sectors_recovered,
                    StatusLevel.SUCCESS if stats.sectors_recovered > 0 else StatusLevel.ERROR
                ),
                SummaryItem(
                    "Final Bad Sectors", stats.final_bad_sectors,
                    StatusLevel.SUCCESS if stats.final_bad_sectors == 0 else StatusLevel.ERROR
                ),
                SummaryItem("Passes Completed", stats.passes_completed),
                SummaryItem(
                    "Converged", "Yes" if stats.converged else "No",
                    StatusLevel.SUCCESS if stats.converged else StatusLevel.WARNING
                ),
                SummaryItem(
                    "Recovery Rate", f"{raw_data['recovery_percentage']}%",
                    (StatusLevel.SUCCESS if raw_data['recovery_percentage'] >= 80
                     else StatusLevel.WARNING)
                ),
            ]

            metadata = ReportMetadata(
                title="Disk Recovery Report",
                subtitle=f"Recovery completed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                report_type=report_type,
                device_path=device_path,
                geometry=geometry_str,
            )

        elif self._last_operation_type == "analyze":
            report_type = ReportType.ANALYSIS
            result = self._last_analysis_result

            grade_dist = result.get_grade_distribution()

            raw_data = {
                "overall_grade": result.overall_grade,
                "overall_quality_score": result.overall_quality_score,
                "grade_distribution": grade_dist,
                "format_type": result.format_type,
                "format_is_standard": result.format_is_standard,
                "is_copy_protected": result.is_copy_protected,
                "protection_types": result.protection_types,
                "protected_track_count": result.protected_track_count,
                "recommendations": result.recommendations,
                "track_results": [
                    {
                        "cylinder": tr.cylinder,
                        "head": tr.head,
                        "quality_score": tr.quality_score,
                        "grade": tr.grade,
                    }
                    for tr in result.track_results[:20]  # First 20 for summary
                ] if result.track_results else [],
            }

            if result.overall_grade in ('A', 'B'):
                status = StatusLevel.SUCCESS
                status_message = f"Disk is in good condition (Grade {result.overall_grade})"
            elif result.overall_grade == 'C':
                status = StatusLevel.WARNING
                status_message = f"Disk shows some degradation (Grade {result.overall_grade})"
            else:
                status = StatusLevel.ERROR
                status_message = f"Disk has significant issues (Grade {result.overall_grade})"

            summary_items = [
                SummaryItem("Overall Grade", result.overall_grade, status),
                SummaryItem("Quality Score", f"{result.overall_quality_score:.1f}%", status),
                SummaryItem("Format Type", result.format_type or "Unknown"),
                SummaryItem(
                    "Copy Protected", "Yes" if result.is_copy_protected else "No",
                    StatusLevel.WARNING if result.is_copy_protected else StatusLevel.INFO
                ),
            ]

            # Add grade distribution
            for grade in ['A', 'B', 'C', 'D', 'F']:
                count = grade_dist.get(grade, 0)
                if count > 0:
                    summary_items.append(SummaryItem(f"Grade {grade} Tracks", count))

            metadata = ReportMetadata(
                title="Disk Analysis Report",
                subtitle=f"Analysis completed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                report_type=report_type,
                device_path=device_path,
                geometry=geometry_str,
            )

        else:
            raise ValueError(f"Unknown operation type: {self._last_operation_type}")

        report_data = ReportData(
            metadata=metadata,
            summary_items=summary_items,
            status=status,
            status_message=status_message,
            raw_data=raw_data,
        )

        return report_type, report_data

    def _export_sector_map_as_base64(self, head: int) -> str:
        """Export a sector map widget as base64 PNG image."""
        from PyQt6.QtCore import QBuffer, QIODevice
        from PyQt6.QtGui import QImage, QPainter
        import base64

        try:
            # Get the appropriate sector map
            if head == 0:
                sector_map = self._sector_map_panel.get_sector_map_h0()
            else:
                sector_map = self._sector_map_panel.get_sector_map_h1()

            # Render the widget to an image
            size = sector_map.size()
            # Use a reasonable export size
            export_width = min(size.width(), 800)
            export_height = min(size.height(), 800)

            image = QImage(export_width, export_height, QImage.Format.Format_ARGB32)
            image.fill(0xFF1e1e1e)  # Dark background

            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Render the viewport
            sector_map.render(painter)
            painter.end()

            # Convert to PNG bytes
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, "PNG")

            # Encode to base64
            png_data = bytes(buffer.data())
            base64_data = base64.b64encode(png_data).decode('utf-8')

            return f"data:image/png;base64,{base64_data}"

        except Exception as e:
            logger.warning("Failed to export sector map for head %d: %s", head, e)
            return ""

    def _get_app_logo_base64(self) -> str:
        """Get the app logo as a base64-encoded PNG string."""
        from PyQt6.QtCore import QBuffer, QIODevice
        from PyQt6.QtGui import QImage
        from floppy_formatter.gui.resources import get_icon_path
        import base64

        try:
            logo_path = get_icon_path("app_logo")
            if not logo_path or not logo_path.exists():
                logger.warning("App logo not found")
                return ""

            # Load the image
            image = QImage(str(logo_path))
            if image.isNull():
                logger.warning("Failed to load app logo image")
                return ""

            # Convert to PNG bytes
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, "PNG")

            # Encode to base64
            png_data = bytes(buffer.data())
            base64_data = base64.b64encode(png_data).decode('utf-8')

            return f"data:image/png;base64,{base64_data}"

        except Exception as e:
            logger.warning("Failed to get app logo: %s", e)
            return ""

    # =========================================================================
    # Thermal Printing
    # =========================================================================

    def _on_print_report_clicked(self) -> None:
        """Handle Print Report button click - print report to thermal printer."""
        from floppy_formatter.utils.thermal_printer import ThermalPrinter
        from floppy_formatter.core.settings import get_settings

        if not self._last_operation_type:
            QMessageBox.warning(
                self,
                "No Report Data",
                "No operation has been completed yet. Run a scan, format, "
                "restore, or analyze operation first."
            )
            return

        # Get printer settings
        settings = get_settings()
        if not settings.printer.enabled:
            QMessageBox.warning(
                self,
                "Printer Not Configured",
                "Thermal printing is not enabled.\n\n"
                "Please enable it in Settings > Printer."
            )
            return

        try:
            # Build thermal report data
            report_data = self._build_thermal_report_data()

            # Create printer
            printer = ThermalPrinter(
                printer_name=settings.printer.printer_name,
                auto_cut=settings.printer.auto_cut
            )

            if not printer.is_available:
                QMessageBox.warning(
                    self,
                    "Printer Not Available",
                    f"Could not connect to printer: {settings.printer.printer_name}\n\n"
                    "Please check that the printer is connected and turned on."
                )
                return

            # Print the report
            self._status_strip.set_operation("Printing report...")

            success = printer.print_report(
                report_data,
                include_sector_map=settings.printer.print_sector_map,
                include_logo=settings.printer.print_logo,
                char_width=settings.printer.char_width
            )

            if success:
                self._status_strip.set_success("Report printed successfully")
                logger.info("Report printed to: %s", settings.printer.printer_name)
                play_success_sound()
            else:
                self._status_strip.set_error("Failed to print report")
                QMessageBox.warning(
                    self,
                    "Print Failed",
                    "Failed to print the report. Please check the printer connection."
                )

        except Exception as e:
            logger.exception("Failed to print report: %s", e)
            QMessageBox.critical(
                self,
                "Print Error",
                f"Failed to print report:\n{str(e)}"
            )
            self._status_strip.set_error(f"Print failed: {e}")

    def _build_thermal_report_data(self):
        """Build ThermalReportData based on the last operation type."""
        from floppy_formatter.utils.thermal_printer import ThermalReportData
        from datetime import datetime

        # Get geometry info
        cylinders = self._geometry.cylinders if self._geometry else 80
        heads = self._geometry.heads if self._geometry else 2
        sectors_per_track = self._geometry.sectors_per_track if self._geometry else 18
        total_sectors = cylinders * heads * sectors_per_track

        # Default values
        good_sectors = 0
        bad_sectors = 0
        weak_sectors = 0
        signal_quality = 0.0
        duration = 0.0
        disk_label = ""

        # Build data based on operation type
        if self._last_operation_type == "scan" and self._last_scan_result:
            result = self._last_scan_result
            good_sectors = len(result.good_sectors) if hasattr(result, 'good_sectors') else 0
            bad_sectors = len(result.bad_sectors) if hasattr(result, 'bad_sectors') else 0
            weak_sectors = getattr(result, 'weak_sectors', 0)
            if isinstance(weak_sectors, list):
                weak_sectors = len(weak_sectors)
            duration = getattr(result, 'elapsed_time', 0)
            signal_quality = self._disk_health or 0

        elif self._last_operation_type == "format" and self._last_format_result:
            result = self._last_format_result
            good_sectors = total_sectors
            bad_sectors = 0
            duration = getattr(result, 'elapsed_time', 0)
            signal_quality = 100.0

        elif self._last_operation_type == "restore" and self._last_restore_result:
            result = self._last_restore_result
            good_sectors = getattr(result, 'recovered_sectors', 0)
            bad_sectors = getattr(result, 'failed_sectors', 0)
            duration = getattr(result, 'elapsed_time', 0)
            signal_quality = (
                good_sectors / max(total_sectors, 1) * 100
            )

        elif self._last_operation_type == "analyze" and self._last_analysis_result:
            result = self._last_analysis_result
            signal_quality = getattr(result, 'overall_health', 0)
            duration = getattr(result, 'elapsed_time', 0)

        # Build sector map data for thermal printing
        sector_map_data = self._build_thermal_sector_map()

        # Calculate read success rate
        read_success_rate = (good_sectors / max(total_sectors, 1)) * 100

        return ThermalReportData(
            title=f"DISK {self._last_operation_type.upper()} REPORT",
            disk_label=disk_label,
            timestamp=datetime.now(),
            format_type=f"IBM PC {total_sectors * 512 // 1024}KB",
            cylinders=cylinders,
            heads=heads,
            sectors_per_track=sectors_per_track,
            total_sectors=total_sectors,
            good_sectors=good_sectors,
            bad_sectors=bad_sectors,
            weak_sectors=weak_sectors,
            signal_quality=signal_quality,
            read_success_rate=read_success_rate,
            operation_type=self._last_operation_type.capitalize(),
            duration_seconds=duration,
            sector_map=sector_map_data,
        )

    def _build_thermal_sector_map(self) -> dict:
        """Build sector map data for thermal printing."""
        sector_map_data = {}

        if not self._geometry:
            return sector_map_data

        sector_map = self._sector_map_panel.get_sector_map()
        if not sector_map:
            return sector_map_data

        for cyl in range(self._geometry.cylinders):
            sector_map_data[cyl] = {}
            for head in range(self._geometry.heads):
                sector_map_data[cyl][head] = []
                for sec in range(self._geometry.sectors_per_track):
                    index = (
                        cyl * self._geometry.heads * self._geometry.sectors_per_track +
                        head * self._geometry.sectors_per_track +
                        sec
                    )
                    status = sector_map.get_sector_status(index)
                    if status == SectorStatus.GOOD:
                        sector_map_data[cyl][head].append("good")
                    elif status == SectorStatus.BAD:
                        sector_map_data[cyl][head].append("bad")
                    elif status == SectorStatus.WEAK:
                        sector_map_data[cyl][head].append("weak")
                    else:
                        sector_map_data[cyl][head].append("unknown")

        return sector_map_data

    def _update_print_button_visibility(self) -> None:
        """Update print button visibility based on settings."""
        from floppy_formatter.core.settings import get_settings
        settings = get_settings()
        self._operation_toolbar.set_print_visible(settings.printer.enabled)

    def _enable_report_buttons(self, enabled: bool) -> None:
        """
        Enable or disable both report and print buttons.

        Args:
            enabled: True to enable, False to disable
        """
        self._operation_toolbar.set_report_enabled(enabled)
        # Print button enabled state matches report, visibility is separate
        self._operation_toolbar.set_print_enabled(enabled)

    # =========================================================================
    # Export Image
    # =========================================================================

    def _on_export_image_clicked(self) -> None:
        """Handle Export Image button click."""
        # Check device connection
        if not self._device:
            QMessageBox.warning(
                self, "No Device",
                "Please connect to a Greaseweazle device first."
            )
            return

        # Check if an operation is running
        if self._state != WorkbenchState.IDLE:
            QMessageBox.warning(
                self, "Operation in Progress",
                "Please wait for the current operation to complete."
            )
            return

        # Check if we have scan data to export
        sector_map = self._sector_map_panel.get_sector_map()
        if not sector_map or sector_map.get_total_sectors() == 0:
            QMessageBox.warning(
                self, "No Data",
                "Please scan a disk first before exporting.\n\n"
                "The export function requires sector data from a completed scan."
            )
            return

        # Show export dialog
        dialog = ExportDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        # Get config
        config = dialog.get_config()
        if not config or not config.output_path:
            return

        logger.info(
            "Exporting disk to %s format: %s",
            config.export_type.name,
            config.output_path
        )

        # Perform the export based on type
        try:
            self._perform_export(config)
        except Exception as e:
            logger.error("Export failed: %s", e, exc_info=True)
            QMessageBox.critical(
                self, "Export Failed",
                f"Failed to export disk image:\n\n{e}"
            )

    def _perform_export(self, config: ExportConfig) -> None:
        """
        Perform the disk export operation.

        Args:
            config: Export configuration
        """
        from floppy_formatter.imaging.image_formats import ImageManager
        from floppy_formatter.gui.dialogs.export_dialog import ExportType

        # Get sector data from the model
        sector_map = self._sector_map_panel.get_sector_map()
        total_sectors = sector_map.get_total_sectors()

        if total_sectors == 0:
            raise ValueError("No sector data available for export")

        # Build sector data from sector map
        # Get geometry from session if available, otherwise fall back to stored geometry
        if self._active_session is not None:
            geometry = self._active_session.to_geometry()
        elif self._geometry is not None:
            geometry = self._geometry
        else:
            geometry = DiskGeometry.standard_144()
        sector_data: dict[tuple[int, int, int], bytes] = {}

        # Collect sector data
        # Note: This is a simplified implementation - in production you'd
        # want to use cached sector data from the last scan
        for cyl in range(geometry.cylinders):
            for head in range(geometry.heads):
                for sec in range(1, geometry.sectors_per_track + 1):
                    # Get sector data if available (from last scan)
                    # For now, create empty sectors for missing data
                    sector_data[(cyl, head, sec)] = bytes(geometry.sector_size)

        # Create image manager and export
        manager = ImageManager()

        if config.export_type == ExportType.IMG:
            manager.export_img(
                config.output_path,
                sector_data,
                geometry,
                pad_to_standard=config.pad_to_standard
            )
        elif config.export_type == ExportType.SCP:
            # SCP requires flux data - would need flux capture
            QMessageBox.information(
                self, "Flux Export",
                "SCP export requires flux data.\n\n"
                "Please use the Flux Analysis tab to capture and export flux data."
            )
            return
        elif config.export_type == ExportType.HFE:
            # HFE requires flux data
            QMessageBox.information(
                self, "Flux Export",
                "HFE export requires flux data.\n\n"
                "Please use the Flux Analysis tab to capture and export flux data."
            )
            return
        else:
            # PDF/HTML reports handled elsewhere
            QMessageBox.information(
                self, "Report Export",
                "For PDF/HTML reports, please use the Export Report button."
            )
            return

        # Success
        QMessageBox.information(
            self, "Export Complete",
            f"Successfully exported disk image to:\n\n{config.output_path}"
        )
        play_success_sound()
        logger.info("Export completed: %s", config.output_path)

    # =========================================================================
    # Batch Verification
    # =========================================================================

    def _on_batch_verify_clicked(self) -> None:
        """Handle Batch Verify button click."""
        # Check device connection
        if not self._device:
            QMessageBox.warning(
                self, "No Device",
                "Please connect to a Greaseweazle device first."
            )
            return

        # Check if an operation is running
        if self._state != WorkbenchState.IDLE:
            QMessageBox.warning(
                self, "Operation in Progress",
                "Please wait for the current operation to complete."
            )
            return

        # Show config dialog
        dialog = BatchVerifyConfigDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        # Get config and start batch
        self._batch_config = dialog.get_config()
        self._batch_results = []
        self._current_batch_index = 0
        self._batch_start_time = datetime.now()

        logger.info(
            "Starting batch verification: %d disks, brand=%s, depth=%s",
            self._batch_config.disk_count,
            self._batch_config.brand.value,
            self._batch_config.analysis_depth
        )

        # Start the batch verification loop
        self._verify_next_disk()

    def _verify_next_disk(self) -> None:
        """Prompt for and verify the next disk in batch."""
        if self._batch_config is None:
            return

        # Check if batch is complete
        if self._current_batch_index >= self._batch_config.disk_count:
            self._complete_batch_verification()
            return

        # Get current disk info
        disk_info = self._batch_config.disks[self._current_batch_index]

        # Ensure motor is off before disk swap - use force=True in case operation was interrupted
        if self._device and self._device.is_motor_on():
            try:
                self._device.motor_off(force=True)
                import time
                time.sleep(0.5)  # Wait for spindown
            except Exception as e:
                logger.warning("Failed to stop motor: %s", e)

        # Show prompt dialog
        prompt = DiskPromptDialog(
            self,
            disk_info=disk_info,
            current_index=self._current_batch_index,
            total_count=self._batch_config.disk_count,
        )
        result: DiskPromptResult = prompt.exec_and_get_result()

        if result.cancel_batch:
            self._cancel_batch_verification()
            return

        if result.skip:
            # Record skipped disk
            skipped_result = SingleDiskResult(
                disk_info=disk_info,
                grade=DiskGrade.SKIPPED,
                skipped=True,
                timestamp=datetime.now(),
            )
            self._batch_results.append(skipped_result)
            logger.info("Disk %d skipped", self._current_batch_index + 1)

            self._current_batch_index += 1
            # Use timer to avoid deep recursion
            QTimer.singleShot(100, self._verify_next_disk)
            return

        # Start verification for this disk
        self._start_single_disk_verification(disk_info)

    def _start_single_disk_verification(self, disk_info: FloppyDiskInfo) -> None:
        """Start verification of a single disk in the batch."""
        if self._batch_config is None or self._geometry is None:
            return

        self._state = WorkbenchState.BATCH_VERIFYING
        self._operation_toolbar.start_operation()
        self._drive_control.pause_rpm_polling()

        # Reset sector map and verification tab
        self._sector_map_panel.reset_all_sectors()
        self._analytics_panel.clear_verification()

        # Update status
        disk_num = self._current_batch_index + 1
        total = self._batch_config.disk_count
        serial_info = f" ({disk_info.serial_number})" if disk_info.serial_number else ""
        self._status_strip.set_status(f"Verifying disk {disk_num}/{total}{serial_info}...")

        # Create and run worker
        self._batch_verify_worker = BatchVerifyWorker(
            device=self._device,
            geometry=self._geometry,
            disk_info=disk_info,
            analysis_depth=self._batch_config.analysis_depth,
            session=self._active_session,
        )
        self._batch_verify_thread = QThread()
        self._batch_verify_worker.moveToThread(self._batch_verify_thread)

        # Connect signals
        self._batch_verify_thread.started.connect(self._batch_verify_worker.run)
        self._batch_verify_worker.disk_verified.connect(self._on_disk_verified)
        self._batch_verify_worker.verification_failed.connect(self._on_disk_verification_failed)
        self._batch_verify_worker.progress.connect(self._on_batch_progress)
        self._batch_verify_worker.track_verified.connect(self._on_batch_track_verified)
        self._batch_verify_worker.finished.connect(self._on_single_verification_finished)

        self._batch_verify_thread.start()

    def _on_disk_verified(self, result: SingleDiskResult) -> None:
        """Handle single disk verification completion."""
        self._batch_results.append(result)
        logger.info(
            "Disk %d verified: grade=%s, score=%.1f",
            self._current_batch_index + 1,
            result.grade.value,
            result.overall_score
        )

        # Update verification tab with results
        self._update_verification_tab(result)

    def _on_disk_verification_failed(self, error: str) -> None:
        """Handle disk verification failure."""
        logger.error("Disk %d verification failed: %s", self._current_batch_index + 1, error)
        self._status_strip.set_error(f"Verification failed: {error}")

    def _on_batch_progress(self, progress: int) -> None:
        """Handle progress update during batch verification."""
        self._operation_toolbar.set_progress(progress)

    def _on_batch_track_verified(self, cyl: int, head: int, track_result) -> None:
        """Handle track verification result for sector map and verification tab update."""
        from floppy_formatter.gui.workers.batch_verify_worker import TrackVerifyResult

        sectors_per_track = self._geometry.sectors_per_track if self._geometry else 18
        base_sector = (cyl * 2 + head) * sectors_per_track

        # Update sector map based on actual sector results
        if isinstance(track_result, TrackVerifyResult):
            # Update verification tab with live progress
            self._analytics_panel.update_verification_track(
                cyl, head,
                track_result.good_sectors,
                track_result.bad_sectors,
                track_result.weak_sectors,
                track_result.total_expected
            )

            # Update sector map - use sector_errors to determine per-sector status
            for s in range(1, sectors_per_track + 1):
                sector_num = base_sector + (s - 1)
                if sector_num >= 2880:
                    continue

                if s in track_result.sector_errors:
                    # This sector has an error
                    error = track_result.sector_errors[s]
                    if "Missing" in error:
                        status = SectorStatus.MISSING
                    else:
                        status = SectorStatus.CRC_ERROR
                else:
                    # No error = good sector
                    status = SectorStatus.GOOD

                self._sector_map_panel.set_sector_status(sector_num, status)
        else:
            # Fallback for legacy format
            for s in range(sectors_per_track):
                sector_num = base_sector + s
                if sector_num < 2880:
                    self._sector_map_panel.set_sector_status(sector_num, SectorStatus.GOOD)

    def _on_single_verification_finished(self) -> None:
        """Handle single disk verification thread cleanup."""
        self._cleanup_batch_verify_worker()
        self._drive_control.resume_rpm_polling()

        self._current_batch_index += 1

        # Continue to next disk
        QTimer.singleShot(100, self._verify_next_disk)

    def _update_verification_tab(self, result: SingleDiskResult) -> None:
        """
        Update the verification tab with disk verification results.

        Converts SingleDiskResult to VerificationSummary format for display.
        """
        from floppy_formatter.gui.tabs.verification_tab import (
            VerificationSummary, TrackVerificationResult
        )

        # Convert track results to the format expected by VerificationTab
        track_results = []
        for tr in result.track_results:
            track_results.append(TrackVerificationResult(
                cylinder=tr.cylinder,
                head=tr.head,
                good_sectors=tr.good_sectors,
                bad_sectors=tr.bad_sectors + tr.missing_sectors,  # Combine bad + missing
                weak_sectors=tr.weak_sectors,
                total_sectors=tr.total_expected,
                errors=list(tr.sector_errors.values()) if tr.sector_errors else []
            ))

        # Create verification summary
        summary = VerificationSummary(
            timestamp=result.timestamp,
            total_sectors=result.total_sectors,
            good_sectors=result.good_sectors,
            bad_sectors=result.bad_sectors + result.missing_sectors,
            weak_sectors=result.weak_sectors,
            grade=result.grade.value,
            score=result.overall_score,
            duration_ms=result.analysis_duration_ms,
            disk_type=result.disk_type,
            encoding=result.encoding_type,
            track_results=track_results,
        )

        # Update the verification tab
        self._analytics_panel.set_verification_result(summary)

        # Switch to verification tab to show results
        self._analytics_panel.show_tab("verification")

    def _complete_batch_verification(self) -> None:
        """Finalize batch verification and generate report."""
        if self._batch_config is None:
            return

        end_time = datetime.now()

        # Build final result
        batch_result = BatchVerificationResult(
            config=self._batch_config,
            disk_results=self._batch_results,
            start_time=self._batch_start_time or datetime.now(),
            end_time=end_time,
        )
        batch_result.finalize()

        # Store for report export
        self._last_batch_result = batch_result
        self._last_operation_type = "batch_verify"

        # Reset state
        self._state = WorkbenchState.IDLE
        self._operation_toolbar.stop_operation()
        self._enable_report_buttons(True)

        # Generate report
        self._generate_batch_report(batch_result)

        # Show completion message
        play_complete_sound()
        QMessageBox.information(
            self, "Batch Complete",
            f"Verified {batch_result.disks_verified} disk(s).\n"
            f"Skipped: {batch_result.disks_skipped}\n"
            f"Failed: {batch_result.disks_failed}\n"
            f"Pass rate: {batch_result.pass_rate:.1f}%\n\n"
            f"Average score: {batch_result.average_score:.1f}%"
        )

        self._status_strip.set_status("Batch verification complete")
        logger.info("Batch verification complete: %s", batch_result.get_summary())

    def _cancel_batch_verification(self) -> None:
        """Handle batch verification cancellation."""
        logger.info("Batch verification cancelled at disk %d", self._current_batch_index + 1)

        # Clean up any running worker
        if self._batch_verify_worker:
            self._batch_verify_worker.cancel()
        self._cleanup_batch_verify_worker()

        # Generate partial report if any disks were verified
        if self._batch_results and self._batch_config:
            batch_result = BatchVerificationResult(
                config=self._batch_config,
                disk_results=self._batch_results,
                start_time=self._batch_start_time or datetime.now(),
                end_time=datetime.now(),
            )
            batch_result.finalize()
            self._last_batch_result = batch_result
            self._last_operation_type = "batch_verify"

        # Reset state
        self._state = WorkbenchState.IDLE
        self._operation_toolbar.stop_operation()
        self._drive_control.resume_rpm_polling()

        self._status_strip.set_status("Batch verification cancelled")

        QMessageBox.information(
            self, "Batch Cancelled",
            f"Batch verification was cancelled.\n"
            f"Verified {len(self._batch_results)} disk(s) before cancellation."
        )

    def _generate_batch_report(self, result: BatchVerificationResult) -> None:
        """
        Generate and save the batch verification report as PDF.

        Automatically prompts user to save the report when batch verification
        completes. Includes all batch configuration info and per-disk results.
        """
        from PyQt6.QtWidgets import QFileDialog
        from floppy_formatter.reports import (
            ReportGenerator, ReportType, ReportData, ReportMetadata
        )

        try:
            # Build batch config dict from BatchVerifyConfig
            batch_config = {}
            if self._batch_config:
                batch_config = {
                    'batch_name': self._batch_config.batch_name,
                    'operator': self._batch_config.operator,
                    'total_disks': self._batch_config.disk_count,
                    'analysis_depth': self._batch_config.analysis_depth,
                    'notes': self._batch_config.notes or '',
                    'brand': self._batch_config.brand.value if self._batch_config.brand else 'Unknown',
                }

            # Create report data
            metadata = ReportMetadata(
                title="Batch Disk Verification Report",
                report_type=ReportType.BATCH_VERIFY,
                timestamp=datetime.now(),
            )

            report_data = ReportData(
                metadata=metadata,
                raw_data={
                    'batch_result': result,
                    'batch_config': batch_config,
                },
            )

            # Generate HTML using the template
            generator = ReportGenerator(ReportType.BATCH_VERIFY, report_data)
            html_content = generator.generate_html()

            # Default to PDF - prompt user to save
            default_name = f"batch_report_{result.start_time.strftime('%Y%m%d_%H%M%S')}.pdf"

            file_path, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Save Batch Verification Report",
                default_name,
                "PDF Files (*.pdf);;HTML Files (*.html)"
            )

            if not file_path:
                logger.info("User cancelled batch report save")
                return

            # Determine format from file extension or filter
            if file_path.lower().endswith('.pdf') or 'PDF' in selected_filter:
                self._save_batch_report_pdf(html_content, file_path)
            else:
                # Save as HTML
                if not file_path.lower().endswith('.html'):
                    file_path += '.html'
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)

            self._status_strip.set_status(f"Report saved to {file_path}")
            logger.info("Batch report saved to %s", file_path)

        except Exception as e:
            logger.error("Failed to generate batch report: %s", e, exc_info=True)
            QMessageBox.warning(self, "Report Error", f"Failed to save report: {e}")

    def _build_batch_report_html(self, result: BatchVerificationResult) -> str:
        """Build HTML content for batch report."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Batch Verification Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #1e1e1e; color: #cccccc; padding: 20px;
        }}
        h1 {{ color: #4ec9b0; border-bottom: 2px solid #3a3d41; padding-bottom: 10px; }}
        h2 {{ color: #569cd6; margin-top: 30px; }}
        .summary {{ background: #252526; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }}
        .summary-item {{
            background: #2d2d30; padding: 15px; border-radius: 6px; text-align: center;
        }}
        .summary-value {{ font-size: 24px; font-weight: bold; color: #4ec9b0; }}
        .summary-label {{ font-size: 12px; color: #858585; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #3a3d41; }}
        th {{ background: #2d2d30; color: #cccccc; font-weight: bold; }}
        tr:hover {{ background: #2a2a2a; }}
        .grade-A {{ color: #4ec9b0; font-weight: bold; }}
        .grade-B {{ color: #89d185; font-weight: bold; }}
        .grade-C {{ color: #dcdcaa; font-weight: bold; }}
        .grade-D {{ color: #ce9178; font-weight: bold; }}
        .grade-F {{ color: #f14c4c; font-weight: bold; }}
        .grade-S {{ color: #858585; font-weight: bold; }}
        .pass {{ color: #4ec9b0; }}
        .fail {{ color: #f14c4c; }}
        .timestamp {{ color: #858585; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>Batch Verification Report</h1>
    <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="summary">
        <h2>Summary</h2>
        <div class="summary-grid">
            <div class="summary-item">
                <div class="summary-value">{result.config.disk_count}</div>
                <div class="summary-label">Total Disks</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">{result.disks_verified}</div>
                <div class="summary-label">Verified</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">{result.pass_rate:.1f}%</div>
                <div class="summary-label">Pass Rate</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">{result.average_score:.1f}%</div>
                <div class="summary-label">Avg Score</div>
            </div>
        </div>
        <p style="margin-top: 15px;">
            <strong>Batch:</strong> {result.config.batch_name}<br>
            <strong>Brand:</strong> {result.config.brand.value}<br>
            <strong>Analysis Depth:</strong> {result.config.analysis_depth}
        </p>
    </div>

    <h2>Results by Disk</h2>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Serial/ID</th>
                <th>Grade</th>
                <th>Score</th>
                <th>Good</th>
                <th>Bad</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
"""
        for i, disk_result in enumerate(result.disk_results):
            serial = disk_result.disk_info.serial_number or f"Disk {i + 1}"
            grade = disk_result.display_grade
            grade_class = f"grade-{grade}"

            if disk_result.skipped:
                status = '<span class="grade-S">Skipped</span>'
            elif disk_result.error_message:
                status = f'<span class="fail">Error: {disk_result.error_message}</span>'
            elif disk_result.is_passing:
                status = '<span class="pass">Pass</span>'
            else:
                status = '<span class="fail">Fail</span>'

            html += f"""
            <tr>
                <td>{i + 1}</td>
                <td>{serial}</td>
                <td class="{grade_class}">{grade}</td>
                <td>{disk_result.overall_score:.1f}%</td>
                <td>{disk_result.good_sectors}</td>
                <td>{disk_result.bad_sectors}</td>
                <td>{status}</td>
            </tr>
"""

        html += """
        </tbody>
    </table>

    <p class="timestamp" style="margin-top: 30px;">
        Generated by Floppy Workbench
    </p>
</body>
</html>
"""
        return html

    def _save_batch_report_pdf(self, html_content: str, file_path: str) -> None:
        """Save batch report as PDF."""
        from PyQt6.QtGui import QTextDocument
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtCore import QMarginsF

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageMargins(QMarginsF(15, 15, 15, 15))

        doc = QTextDocument()
        doc.setHtml(html_content)
        doc.print_(printer)

    def _cleanup_batch_verify_worker(self) -> None:
        """Clean up batch verify worker and thread."""
        if self._batch_verify_worker:
            try:
                self._batch_verify_worker.deleteLater()
            except RuntimeError:
                pass
            self._batch_verify_worker = None

        if self._batch_verify_thread:
            try:
                if self._batch_verify_thread.isRunning():
                    self._batch_verify_thread.quit()
                    self._batch_verify_thread.wait(2000)
                self._batch_verify_thread.deleteLater()
            except RuntimeError:
                pass
            self._batch_verify_thread = None

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
