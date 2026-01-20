"""
Analytics dashboard panel for Floppy Workbench.

Provides a tabbed interface containing:
- Summary tab: Health score, statistics, recommendations
- Analysis tab: Signal quality, encoding detection
- Flux tab: Waveform and histogram visualization
- Errors tab: Error heatmap, pie chart, log
- Recovery tab: Convergence graph, pass history
- Diagnostics tab: Alignment, RPM, self-test
- Verification tab: Track-by-track results

Part of Phase 7: Analytics Dashboard
"""

from typing import Optional, List, Dict, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTabBar,
    QSizePolicy,
    QLabel,
    QStylePainter,
    QStyleOptionTab,
    QStyle,
)
from PyQt6.QtCore import pyqtSignal, Qt, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

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
from floppy_formatter.gui.tabs.verification_tab import (
    VerificationTab,
    VerificationSummary,
    TrackVerificationResult,
)
from floppy_formatter.gui.tabs.analysis_tab import (
    AnalysisTab,
    AnalysisSummary,
)
from floppy_formatter.gui.tabs.progress_tab import (
    ProgressTab,
    ProgressData,
    OperationStatus,
)
from floppy_formatter.gui.resources import get_colored_icon

if TYPE_CHECKING:
    from floppy_formatter.analysis.flux_analyzer import FluxCapture

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Tab names for external reference (renamed Overview to Summary)
TAB_PROGRESS = "progress"
TAB_SUMMARY = "summary"
TAB_OVERVIEW = "summary"  # Alias for backward compatibility
TAB_FLUX = "flux"
TAB_ERRORS = "errors"
TAB_RECOVERY = "recovery"
TAB_DIAGNOSTICS = "diagnostics"
TAB_VERIFICATION = "verification"
TAB_ANALYSIS = "analysis"

# Minimum panel height
MIN_HEIGHT = 250
DEFAULT_HEIGHT = 300


class BadgeTabBar(QTabBar):
    """
    Custom tab bar that can display notification badges on tabs.

    Badges appear as small colored dots next to tab text to indicate
    data availability or issues.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._badges: Dict[int, str] = {}  # tab_index -> badge_color
        self._badge_counts: Dict[int, int] = {}  # tab_index -> count (optional)

    def set_tab_badge(self, index: int, color: Optional[str] = None, count: int = 0) -> None:
        """
        Set a badge on a tab.

        Args:
            index: Tab index
            color: Badge color (CSS color string) or None to remove
            count: Optional count to display (0 = just show dot)
        """
        if color is None:
            self._badges.pop(index, None)
            self._badge_counts.pop(index, None)
        else:
            self._badges[index] = color
            self._badge_counts[index] = count
        self.update()

    def clear_badge(self, index: int) -> None:
        """Remove badge from a tab."""
        self._badges.pop(index, None)
        self._badge_counts.pop(index, None)
        self.update()

    def clear_all_badges(self) -> None:
        """Remove all badges."""
        self._badges.clear()
        self._badge_counts.clear()
        self.update()

    def tabSizeHint(self, index: int) -> QSize:
        """Return tab size with space for badge."""
        size = super().tabSizeHint(index)
        if index in self._badges:
            # Add extra width for badge
            size.setWidth(size.width() + 18)
        return size

    def paintEvent(self, event) -> None:
        """Paint tabs with badges."""
        # Let parent draw the tabs first
        super().paintEvent(event)

        # Draw badges on top
        if not self._badges:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for index, color in self._badges.items():
            if index >= self.count():
                continue

            tab_rect = self.tabRect(index)

            # Position badge at right side of tab
            badge_size = 10
            badge_x = tab_rect.right() - badge_size - 8
            badge_y = tab_rect.center().y() - badge_size // 2

            # Draw badge circle
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(color)))
            painter.drawEllipse(badge_x, badge_y, badge_size, badge_size)

            # Draw count if > 0
            count = self._badge_counts.get(index, 0)
            if count > 0 and count < 100:
                painter.setPen(QPen(QColor("#ffffff")))
                font = painter.font()
                font.setPointSize(7)
                font.setBold(True)
                painter.setFont(font)
                text = str(count) if count < 10 else "9+"
                painter.drawText(
                    QRect(badge_x, badge_y, badge_size, badge_size),
                    Qt.AlignmentFlag.AlignCenter,
                    text
                )

        painter.end()


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

        # Tab widget with custom badge-enabled tab bar
        self._tab_widget = QTabWidget()
        self._tab_bar = BadgeTabBar()
        self._tab_widget.setTabBar(self._tab_bar)
        self._tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3a3d41;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 8px 20px;
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
            QTabBar::tab:disabled {
                color: #666666;
            }
        """)

        # Create tabs
        self._progress_tab = ProgressTab()
        self._overview_tab = OverviewTab()
        self._flux_tab = FluxTab()
        self._errors_tab = ErrorsTab()
        self._recovery_tab = RecoveryTab()
        self._diagnostics_tab = DiagnosticsTab()
        self._verification_tab = VerificationTab()
        self._analysis_tab = AnalysisTab()

        # Add tabs in logical order:
        # 0. Progress - live operation progress (first for visibility during operations)
        # 1. Summary (formerly Overview) - main health summary
        # 2. Analysis - signal quality, encoding detection
        # 3. Flux - raw flux visualization
        # 4. Errors - error analysis (Issues group)
        # 5. Recovery - recovery progress (Issues group)
        # 6. Verification - track-by-track results (Hardware group)
        # 7. Diagnostics - drive health (Hardware group)
        self._tab_widget.addTab(self._progress_tab, "Progress")
        self._tab_widget.addTab(self._overview_tab, "Summary")
        self._tab_widget.addTab(self._analysis_tab, "Analysis")
        self._tab_widget.addTab(self._flux_tab, "Flux")
        self._tab_widget.addTab(self._errors_tab, "Errors")
        self._tab_widget.addTab(self._recovery_tab, "Recovery")
        self._tab_widget.addTab(self._verification_tab, "Verification")
        self._tab_widget.addTab(self._diagnostics_tab, "Diagnostics")

        # Try to add icons
        self._add_tab_icons()

        # Store tab name mapping (updated order with Progress tab first)
        self._tab_names = {
            0: TAB_PROGRESS,
            1: TAB_SUMMARY,
            2: TAB_ANALYSIS,
            3: TAB_FLUX,
            4: TAB_ERRORS,
            5: TAB_RECOVERY,
            6: TAB_VERIFICATION,
            7: TAB_DIAGNOSTICS,
        }

        self._tab_indices = {v: k for k, v in self._tab_names.items()}
        # Add backward-compatible alias
        self._tab_indices[TAB_OVERVIEW] = 1

        layout.addWidget(self._tab_widget)

    def _add_tab_icons(self) -> None:
        """Add icons to tabs (updated for new tab order with Progress first)."""
        icons = {
            0: "play",      # Progress
            1: "info",      # Summary
            2: "activity",  # Analysis
            3: "chart",     # Flux
            4: "warning",   # Errors
            5: "refresh",   # Recovery
            6: "check",     # Verification
            7: "settings",  # Diagnostics
        }

        for index, icon_name in icons.items():
            # Use white colored icons for visibility on dark background
            icon = get_colored_icon(icon_name, "#cccccc", 20)
            if icon and not icon.isNull():
                self._tab_widget.setTabIcon(index, icon)

    # =========================================================================
    # Public API - Tab Badges
    # =========================================================================

    def set_tab_badge(self, tab_name: str, color: Optional[str] = None, count: int = 0) -> None:
        """
        Set a badge on a tab to indicate data availability.

        Args:
            tab_name: Tab name (summary, analysis, flux, errors, recovery, etc.)
            color: Badge color (CSS color string) or None to remove badge
            count: Optional count to display in badge
        """
        index = self._tab_indices.get(tab_name.lower())
        if index is not None:
            self._tab_bar.set_tab_badge(index, color, count)

    def set_errors_badge(self, error_count: int) -> None:
        """
        Set badge on Errors tab based on error count.

        Args:
            error_count: Number of errors (0 = remove badge)
        """
        if error_count > 0:
            self._tab_bar.set_tab_badge(4, "#e81123", error_count)  # Red badge
        else:
            self._tab_bar.clear_badge(4)

    def set_recovery_badge(self, has_recoverable: bool) -> None:
        """
        Set badge on Recovery tab if recoverable sectors exist.

        Args:
            has_recoverable: True if recoverable sectors exist
        """
        if has_recoverable:
            self._tab_bar.set_tab_badge(5, "#f7b731", 0)  # Yellow badge
        else:
            self._tab_bar.clear_badge(5)

    def set_analysis_badge(self, has_data: bool) -> None:
        """
        Set badge on Analysis tab if analysis data is available.

        Args:
            has_data: True if analysis data is available
        """
        if has_data:
            self._tab_bar.set_tab_badge(2, "#33cc33", 0)  # Green badge
        else:
            self._tab_bar.clear_badge(2)

    def set_verification_badge(self, has_issues: bool) -> None:
        """
        Set badge on Verification tab if issues were found.

        Args:
            has_issues: True if verification found issues
        """
        if has_issues:
            self._tab_bar.set_tab_badge(6, "#f7b731", 0)  # Yellow badge
        else:
            self._tab_bar.clear_badge(6)

    def set_progress_badge(self, is_running: bool) -> None:
        """
        Set badge on Progress tab if operation is running.

        Args:
            is_running: True if operation is in progress
        """
        if is_running:
            self._tab_bar.set_tab_badge(0, "#569cd6", 0)  # Blue badge
        else:
            self._tab_bar.clear_badge(0)

    def clear_all_badges(self) -> None:
        """Clear all tab badges."""
        self._tab_bar.clear_all_badges()

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

    def get_verification_tab(self) -> VerificationTab:
        """Get the verification tab widget."""
        return self._verification_tab

    def get_analysis_tab(self) -> AnalysisTab:
        """Get the analysis tab widget."""
        return self._analysis_tab

    # =========================================================================
    # Public API - Verification Tab
    # =========================================================================

    def set_verification_result(self, summary: VerificationSummary) -> None:
        """
        Display verification results.

        Args:
            summary: VerificationSummary with all results
        """
        self._verification_tab.set_verification_result(summary)

    def update_verification_track(
        self,
        cylinder: int,
        head: int,
        good: int,
        bad: int,
        weak: int,
        total: int
    ) -> None:
        """
        Update a single track's verification results (live updates).

        Args:
            cylinder: Cylinder number
            head: Head number
            good: Good sector count
            bad: Bad sector count
            weak: Weak sector count
            total: Total sectors on track
        """
        self._verification_tab.update_track_progress(cylinder, head, good, bad, weak, total)

    def clear_verification(self) -> None:
        """Clear verification tab."""
        self._verification_tab.clear()

    # =========================================================================
    # Public API - Analysis Tab
    # =========================================================================

    def update_analysis(self, result) -> None:
        """
        Update analysis tab with DiskAnalysisResult.

        Args:
            result: DiskAnalysisResult from analyze_worker
        """
        self._analysis_tab.update_from_result(result)

    def set_analysis_summary(self, summary: AnalysisSummary) -> None:
        """
        Update analysis tab with pre-built summary.

        Args:
            summary: AnalysisSummary with analysis data
        """
        self._analysis_tab.update_analysis(summary)

    def clear_analysis(self) -> None:
        """Clear analysis tab."""
        self._analysis_tab.clear_analysis()

    # =========================================================================
    # Public API - Progress Tab
    # =========================================================================

    def get_progress_tab(self) -> ProgressTab:
        """Get the progress tab widget."""
        return self._progress_tab

    def start_progress(
        self,
        operation_type: str,
        total_tracks: int = 160,
        total_sectors: int = 2880,
        total_passes: int = 1
    ) -> None:
        """
        Start tracking progress for an operation.

        Args:
            operation_type: Type of operation (scan, format, restore, analyze)
            total_tracks: Total number of tracks to process
            total_sectors: Total number of sectors
            total_passes: Total number of passes (for multi-pass operations)
        """
        self._progress_tab.start_operation(
            operation_type, total_tracks, total_sectors, total_passes
        )
        self.set_progress_badge(True)
        self.show_tab(TAB_PROGRESS)

    def stop_progress(self, success: bool = True, message: str = "") -> None:
        """
        Stop tracking progress.

        Args:
            success: Whether the operation completed successfully
            message: Optional completion message
        """
        self._progress_tab.stop_operation(success, message)
        self.set_progress_badge(False)

    def cancel_progress(self) -> None:
        """Mark the operation as cancelled."""
        self._progress_tab.cancel_operation()
        self.set_progress_badge(False)

    def reset_progress(self) -> None:
        """Reset the progress tab to initial state."""
        self._progress_tab.reset()
        self.set_progress_badge(False)

    def update_progress(self, progress: int, eta_seconds: float = None) -> None:
        """
        Update progress percentage.

        Args:
            progress: Progress percentage (0-100)
            eta_seconds: Optional estimated time remaining
        """
        self._progress_tab.set_progress(progress, eta_seconds)

    def update_progress_track(self, track: int, head: int = 0) -> None:
        """
        Update current track and head position.

        Args:
            track: Current track number
            head: Current head (0 or 1)
        """
        self._progress_tab.set_track(track, head)

    def update_progress_sector(self, sector: int) -> None:
        """
        Update current sector.

        Args:
            sector: Current sector number
        """
        self._progress_tab.set_sector(sector)

    def update_progress_pass(self, pass_num: int, total_passes: int = None) -> None:
        """
        Update current pass number.

        Args:
            pass_num: Current pass number
            total_passes: Optional total passes
        """
        self._progress_tab.set_pass(pass_num, total_passes)

    def update_progress_sector_counts(
        self, good: int = 0, bad: int = 0, recovered: int = 0
    ) -> None:
        """
        Update sector count statistics.

        Args:
            good: Number of good sectors
            bad: Number of bad sectors
            recovered: Number of recovered sectors
        """
        self._progress_tab.set_sector_counts(good, bad, recovered)

    def update_progress_message(self, message: str) -> None:
        """
        Update the progress status message.

        Args:
            message: Status message to display
        """
        self._progress_tab.set_message(message)


__all__ = [
    'AnalyticsPanel',
    'BadgeTabBar',
    'TAB_PROGRESS',
    'TAB_SUMMARY',
    'TAB_OVERVIEW',  # Backward-compatible alias for TAB_SUMMARY
    'TAB_FLUX',
    'TAB_ERRORS',
    'TAB_RECOVERY',
    'TAB_DIAGNOSTICS',
    'TAB_VERIFICATION',
    'TAB_ANALYSIS',
]
