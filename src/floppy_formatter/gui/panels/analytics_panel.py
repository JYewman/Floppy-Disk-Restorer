"""
Analytics dashboard panel for Floppy Workbench.

Provides a tabbed interface containing:
- Overview tab: Health score, statistics, recommendations
- Flux tab: Waveform and histogram visualization
- Errors tab: Error heatmap, pie chart, log
- Recovery tab: Convergence graph, pass history
- Diagnostics tab: Alignment, RPM, self-test

Part of Phase 7: Analytics Dashboard
"""

from typing import Optional, List, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal

from floppy_formatter.gui.tabs.overview_tab import (
    OverviewTab,
    Recommendation,
)
from floppy_formatter.gui.tabs.flux_tab import FluxTab
from floppy_formatter.gui.tabs.errors_tab import ErrorsTab, SectorError
from floppy_formatter.gui.tabs.recovery_tab import (
    RecoveryTab,
    PassStats,
    RecoveryStats,
    RecoveredSector,
)
from floppy_formatter.gui.tabs.diagnostics_tab import (
    DiagnosticsTab,
    AlignmentResults,
    SelfTestResults,
    TestStatus,
)
from floppy_formatter.gui.resources import get_icon

if TYPE_CHECKING:
    from floppy_formatter.analysis.flux_analyzer import FluxCapture

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Tab names for external reference
TAB_OVERVIEW = "overview"
TAB_FLUX = "flux"
TAB_ERRORS = "errors"
TAB_RECOVERY = "recovery"
TAB_DIAGNOSTICS = "diagnostics"

# Minimum panel height
MIN_HEIGHT = 250
DEFAULT_HEIGHT = 300


# =============================================================================
# Analytics Panel
# =============================================================================

class AnalyticsPanel(QWidget):
    """
    Tabbed analytics dashboard panel.

    Contains five tabs for comprehensive disk analysis:
    - Overview: Health score and recommendations
    - Flux: Raw flux visualization
    - Errors: Error analysis and patterns
    - Recovery: Recovery progress tracking
    - Diagnostics: Drive health diagnostics

    Signals:
        tab_changed(str): Emitted when user switches tabs (tab name)
        recommendation_action(str): Forwarded from OverviewTab
        sector_selected(int, int, int): Forwarded from ErrorsTab (cyl, head, sector)
        load_flux_requested(int, int, int): Forwarded from FluxTab (cyl, head, sector)
        capture_flux_requested(int, int): Forwarded from FluxTab (cyl, head)
        export_flux_requested(str): Forwarded from FluxTab (file path)
        run_alignment_requested(): Forwarded from DiagnosticsTab
        run_self_test_requested(): Forwarded from DiagnosticsTab
    """

    tab_changed = pyqtSignal(str)
    recommendation_action = pyqtSignal(str)
    sector_selected = pyqtSignal(int, int, int)
    load_flux_requested = pyqtSignal(int, int, int)
    capture_flux_requested = pyqtSignal(int, int)
    export_flux_requested = pyqtSignal(str)
    run_alignment_requested = pyqtSignal()
    run_self_test_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setMinimumHeight(MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab widget
        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3a3d41;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 8px 16px;
                border: 1px solid #3a3d41;
                border-bottom: none;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                border-bottom: 1px solid #1e1e1e;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3a3d41;
            }
        """)

        # Create tabs
        self._overview_tab = OverviewTab()
        self._flux_tab = FluxTab()
        self._errors_tab = ErrorsTab()
        self._recovery_tab = RecoveryTab()
        self._diagnostics_tab = DiagnosticsTab()

        # Add tabs with icons (if available)
        self._tab_widget.addTab(self._overview_tab, "Overview")
        self._tab_widget.addTab(self._flux_tab, "Flux")
        self._tab_widget.addTab(self._errors_tab, "Errors")
        self._tab_widget.addTab(self._recovery_tab, "Recovery")
        self._tab_widget.addTab(self._diagnostics_tab, "Diagnostics")

        # Try to add icons
        self._add_tab_icons()

        # Store tab name mapping
        self._tab_names = {
            0: TAB_OVERVIEW,
            1: TAB_FLUX,
            2: TAB_ERRORS,
            3: TAB_RECOVERY,
            4: TAB_DIAGNOSTICS,
        }

        self._tab_indices = {v: k for k, v in self._tab_names.items()}

        layout.addWidget(self._tab_widget)

    def _add_tab_icons(self) -> None:
        """Add icons to tabs."""
        icons = {
            0: "info",      # Overview
            1: "chart",     # Flux
            2: "warning",   # Errors
            3: "refresh",   # Recovery
            4: "settings",  # Diagnostics
        }

        for index, icon_name in icons.items():
            icon = get_icon(icon_name)
            if icon and not icon.isNull():
                self._tab_widget.setTabIcon(index, icon)

    def _connect_signals(self) -> None:
        """Connect tab signals."""
        # Tab changed
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        # Overview tab
        self._overview_tab.recommendation_action.connect(self.recommendation_action)

        # Flux tab
        self._flux_tab.load_flux_requested.connect(self.load_flux_requested)
        self._flux_tab.capture_flux_requested.connect(self.capture_flux_requested)
        self._flux_tab.export_requested.connect(self.export_flux_requested)

        # Errors tab
        self._errors_tab.sector_selected.connect(self.sector_selected)

        # Diagnostics tab
        self._diagnostics_tab.run_alignment_requested.connect(self.run_alignment_requested)
        self._diagnostics_tab.run_self_test_requested.connect(self.run_self_test_requested)

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change."""
        tab_name = self._tab_names.get(index, "")
        self.tab_changed.emit(tab_name)

    # =========================================================================
    # Public API - Tab Control
    # =========================================================================

    def show_tab(self, tab_name: str) -> None:
        """
        Switch to a specific tab.

        Args:
            tab_name: Tab name (overview, flux, errors, recovery, diagnostics)
        """
        index = self._tab_indices.get(tab_name.lower())
        if index is not None:
            self._tab_widget.setCurrentIndex(index)

    def get_current_tab(self) -> str:
        """Get the name of the current tab."""
        return self._tab_names.get(self._tab_widget.currentIndex(), "")

    def set_tab_enabled(self, tab_name: str, enabled: bool) -> None:
        """
        Enable or disable a specific tab.

        Args:
            tab_name: Tab name
            enabled: Whether tab should be enabled
        """
        index = self._tab_indices.get(tab_name.lower())
        if index is not None:
            self._tab_widget.setTabEnabled(index, enabled)

    def is_tab_enabled(self, tab_name: str) -> bool:
        """Check if a tab is enabled."""
        index = self._tab_indices.get(tab_name.lower())
        if index is not None:
            return self._tab_widget.isTabEnabled(index)
        return False

    # =========================================================================
    # Public API - Overview Tab
    # =========================================================================

    def update_overview(
        self,
        total_sectors: int = 2880,
        good_sectors: int = 0,
        bad_sectors: int = 0,
        recovered_sectors: int = 0,
        health_score: Optional[float] = None
    ) -> None:
        """
        Update overview tab with scan results.

        Args:
            total_sectors: Total number of sectors
            good_sectors: Number of good sectors
            bad_sectors: Number of bad sectors
            recovered_sectors: Number of recovered sectors
            health_score: Optional explicit health score
        """
        self._overview_tab.update_overview(
            total_sectors, good_sectors, bad_sectors, recovered_sectors, health_score
        )

    def clear_overview(self) -> None:
        """Clear overview tab."""
        self._overview_tab.clear_overview()

    def set_recommendations(self, recommendations: List[Recommendation]) -> None:
        """Set explicit recommendations."""
        self._overview_tab.set_recommendations(recommendations)

    # =========================================================================
    # Public API - Flux Tab
    # =========================================================================

    def load_flux_data(self, flux: 'FluxCapture') -> None:
        """Load flux data into the flux tab."""
        self._flux_tab.load_flux_data(flux)

    def clear_flux_display(self) -> None:
        """Clear flux tab display."""
        self._flux_tab.clear_flux_display()

    def set_flux_device_connected(self, connected: bool) -> None:
        """Update flux tab based on device connection."""
        self._flux_tab.set_device_connected(connected)

    def get_current_flux_data(self) -> Optional['FluxCapture']:
        """
        Get the currently loaded flux data from flux tab.

        Returns:
            FluxCapture object or None if no flux is loaded
        """
        return self._flux_tab.get_current_flux()

    # =========================================================================
    # Public API - Errors Tab
    # =========================================================================

    def update_errors(self, errors: List[SectorError]) -> None:
        """Update errors tab with error list."""
        self._errors_tab.update_errors(errors)

    def add_error(self, error: SectorError) -> None:
        """Add a single error."""
        self._errors_tab.add_error(error)

    def clear_errors(self) -> None:
        """Clear errors tab."""
        self._errors_tab.clear_errors()

    # =========================================================================
    # Public API - Recovery Tab
    # =========================================================================

    def update_recovery_progress(self, pass_num: int, stats: PassStats) -> None:
        """Update recovery tab with pass progress."""
        self._recovery_tab.update_recovery_progress(pass_num, stats)

    def set_recovery_complete(self, final_stats: RecoveryStats) -> None:
        """Set recovery as complete."""
        self._recovery_tab.set_recovery_complete(final_stats)

    def clear_recovery_data(self) -> None:
        """Clear recovery tab."""
        self._recovery_tab.clear_recovery_data()

    def add_convergence_point(self, pass_num: int, bad_count: int) -> None:
        """Add a convergence point to the chart."""
        self._recovery_tab.add_convergence_point(pass_num, bad_count)

    def set_initial_bad_sectors(self, count: int) -> None:
        """Set initial bad sector count for recovery prediction."""
        self._recovery_tab.set_initial_bad_sectors(count)

    def add_recovered_sector(self, sector: RecoveredSector) -> None:
        """Add a recovered sector to the timeline."""
        self._recovery_tab.add_recovered_sector(sector)

    # =========================================================================
    # Public API - Diagnostics Tab
    # =========================================================================

    def update_alignment_results(self, results: AlignmentResults) -> None:
        """Update alignment visualization."""
        self._diagnostics_tab.update_alignment_results(results)

    def update_rpm_data(self, rpm_history: List[float]) -> None:
        """Update RPM chart."""
        self._diagnostics_tab.update_rpm_data(rpm_history)

    def add_rpm_measurement(self, rpm: float) -> None:
        """Add a single RPM measurement."""
        self._diagnostics_tab.add_rpm_measurement(rpm)

    def update_self_test_results(self, results: SelfTestResults) -> None:
        """Update self-test results."""
        self._diagnostics_tab.update_self_test_results(results)

    def update_test_item(self, test_name: str, status: TestStatus, details: str = "") -> None:
        """Update a single test item."""
        self._diagnostics_tab.update_test_item(test_name, status, details)

    def set_self_test_running(self, running: bool) -> None:
        """Set whether self-test is running."""
        self._diagnostics_tab.set_self_test_running(running)

    def update_drive_info(
        self,
        firmware: str = "--",
        drive_type: str = "--",
        disk_type: str = "--",
        serial: str = "--"
    ) -> None:
        """Update drive information display."""
        self._diagnostics_tab.update_drive_info(firmware, drive_type, disk_type, serial)

    def update_temperature(self, temp_c: Optional[float]) -> None:
        """Update temperature display."""
        self._diagnostics_tab.update_temperature(temp_c)

    def run_diagnostics(self) -> None:
        """Trigger full diagnostic sequence."""
        self._diagnostics_tab.run_diagnostics()

    # =========================================================================
    # Public API - Tab Access
    # =========================================================================

    def get_overview_tab(self) -> OverviewTab:
        """Get the overview tab widget."""
        return self._overview_tab

    def get_flux_tab(self) -> FluxTab:
        """Get the flux tab widget."""
        return self._flux_tab

    def get_errors_tab(self) -> ErrorsTab:
        """Get the errors tab widget."""
        return self._errors_tab

    def get_recovery_tab(self) -> RecoveryTab:
        """Get the recovery tab widget."""
        return self._recovery_tab

    def get_diagnostics_tab(self) -> DiagnosticsTab:
        """Get the diagnostics tab widget."""
        return self._diagnostics_tab


__all__ = [
    'AnalyticsPanel',
    'TAB_OVERVIEW',
    'TAB_FLUX',
    'TAB_ERRORS',
    'TAB_RECOVERY',
    'TAB_DIAGNOSTICS',
]
