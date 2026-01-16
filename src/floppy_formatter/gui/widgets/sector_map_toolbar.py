"""
Sector map toolbar for Floppy Workbench GUI.

Provides controls for the circular sector map:
- View mode selector (Status/Quality/Errors/Data Pattern)
- Zoom controls (Fit, 100%, 200%, slider)
- Selection tools (Select All Bad, Clear Selection, Invert)
- Export options (PNG, SVG)

Part of Phase 6: Enhanced Sector Map Visualization
"""

import logging
from typing import Optional, List, Set

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QSlider,
    QFrame,
    QToolButton,
    QButtonGroup,
    QSpacerItem,
    QSizePolicy,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon

from floppy_formatter.gui.widgets.circular_sector_map import (
    CircularSectorMap,
    ViewMode,
)
from floppy_formatter.gui.resources import get_icon

logger = logging.getLogger(__name__)


class ViewModeButton(QToolButton):
    """
    A toggle button for view mode selection.
    """

    def __init__(
        self,
        text: str,
        tooltip: str,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize view mode button.

        Args:
            text: Button text
            tooltip: Tooltip text
            parent: Parent widget
        """
        super().__init__(parent)

        self.setText(text)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setMinimumWidth(50)
        self.setMinimumHeight(20)

        self.setStyleSheet("""
            QToolButton {
                background-color: #2d2d30;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 3px;
                padding: 2px 5px;
                font-size: 8pt;
            }
            QToolButton:hover {
                background-color: #3a3d41;
                border-color: #007acc;
            }
            QToolButton:checked {
                background-color: #094771;
                border-color: #007acc;
                color: #ffffff;
            }
            QToolButton:disabled {
                color: #6c6c6c;
                background-color: #252526;
            }
        """)


class ZoomButton(QPushButton):
    """
    A small button for zoom presets.
    """

    def __init__(
        self,
        text: str,
        tooltip: str,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize zoom button.

        Args:
            text: Button text
            tooltip: Tooltip text
            parent: Parent widget
        """
        super().__init__(text, parent)

        self.setToolTip(tooltip)
        self.setFixedWidth(40)
        self.setFixedHeight(20)

        self.setStyleSheet("""
            QPushButton {
                background-color: #2d2d30;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 3px;
                padding: 1px 4px;
                font-size: 8pt;
            }
            QPushButton:hover {
                background-color: #3a3d41;
                border-color: #007acc;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
            QPushButton:disabled {
                color: #6c6c6c;
                background-color: #252526;
            }
        """)


class SectorMapToolbar(QWidget):
    """
    Toolbar for the circular sector map.

    Provides controls for:
    - View mode switching (Status/Quality/Errors/Data Pattern)
    - Zoom controls (Fit, 100%, 200%, slider)
    - Selection tools (Select All Bad, Clear, Invert)
    - Export options (PNG, SVG)

    Signals:
        view_mode_changed(str): Emitted when view mode changes
        zoom_changed(float): Emitted when zoom level changes
        export_requested(str): Emitted when export is requested (format: "png" or "svg")
    """

    # Signals
    view_mode_changed = pyqtSignal(str)
    zoom_changed = pyqtSignal(float)
    export_requested = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize sector map toolbar.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # References to sector maps (can have multiple, e.g., one per head)
        self._sector_maps: List[CircularSectorMap] = []

        # Current state
        self._current_view_mode = ViewMode.STATUS
        self._current_zoom = 1.0
        self._selection_count = 0

        # Build UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setFixedHeight(28)

        # Apply toolbar styling
        self.setStyleSheet("""
            SectorMapToolbar {
                background-color: #252526;
                border-bottom: 1px solid #3a3d41;
            }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 2, 4, 2)
        main_layout.setSpacing(3)

        # View mode section
        self._add_view_mode_section(main_layout)

        # Separator
        main_layout.addWidget(self._create_separator())

        # Zoom section
        self._add_zoom_section(main_layout)

        # Separator
        main_layout.addWidget(self._create_separator())

        # Selection section
        self._add_selection_section(main_layout)

        # Separator
        main_layout.addWidget(self._create_separator())

        # Export section
        self._add_export_section(main_layout)

        # Stretch to push everything left
        main_layout.addStretch(1)

    def _create_separator(self) -> QFrame:
        """Create a vertical separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        separator.setStyleSheet("QFrame { color: #3a3d41; }")
        separator.setFixedWidth(1)
        return separator

    def _add_view_mode_section(self, layout: QHBoxLayout) -> None:
        """Add view mode buttons section."""
        # Label
        label = QLabel("View:")
        label.setStyleSheet("color: #cccccc; font-size: 8pt; font-weight: bold;")
        layout.addWidget(label)

        # Button group for exclusive selection
        self._view_mode_group = QButtonGroup(self)
        self._view_mode_group.setExclusive(True)

        # Status button
        self._status_btn = ViewModeButton("Status", "Show sector status (Good/Bad/Recovering)")
        self._status_btn.setChecked(True)
        self._view_mode_group.addButton(self._status_btn, 0)
        layout.addWidget(self._status_btn)

        # Quality button
        self._quality_btn = ViewModeButton("Quality", "Show flux quality gradient")
        self._view_mode_group.addButton(self._quality_btn, 1)
        layout.addWidget(self._quality_btn)

        # Errors button
        self._errors_btn = ViewModeButton("Errors", "Highlight only error sectors")
        self._view_mode_group.addButton(self._errors_btn, 2)
        layout.addWidget(self._errors_btn)

        # Data Pattern button
        self._pattern_btn = ViewModeButton("Pattern", "Show data pattern visualization")
        self._view_mode_group.addButton(self._pattern_btn, 3)
        layout.addWidget(self._pattern_btn)

        # Connect button group
        self._view_mode_group.idClicked.connect(self._on_view_mode_clicked)

    def _add_zoom_section(self, layout: QHBoxLayout) -> None:
        """Add zoom controls section."""
        # Label
        label = QLabel("Zoom:")
        label.setStyleSheet("color: #cccccc; font-size: 8pt; font-weight: bold;")
        layout.addWidget(label)

        # Fit button
        self._fit_btn = ZoomButton("Fit", "Zoom to fit entire disk")
        self._fit_btn.clicked.connect(self._on_fit_clicked)
        layout.addWidget(self._fit_btn)

        # 100% button
        self._zoom_100_btn = ZoomButton("100%", "Zoom to 100%")
        self._zoom_100_btn.clicked.connect(self._on_zoom_100_clicked)
        layout.addWidget(self._zoom_100_btn)

        # 200% button
        self._zoom_200_btn = ZoomButton("200%", "Zoom to 200%")
        self._zoom_200_btn.clicked.connect(self._on_zoom_200_clicked)
        layout.addWidget(self._zoom_200_btn)

        # Zoom slider
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setMinimum(50)   # 50%
        self._zoom_slider.setMaximum(400)  # 400%
        self._zoom_slider.setValue(100)    # 100%
        self._zoom_slider.setFixedWidth(100)
        self._zoom_slider.setToolTip("Adjust zoom level (50% - 400%)")
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        self._zoom_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #3a3d41;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #007acc;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #1e90ff;
            }
        """)
        layout.addWidget(self._zoom_slider)

        # Zoom level display
        self._zoom_label = QLabel("100%")
        self._zoom_label.setStyleSheet("color: #858585; font-size: 9pt; min-width: 40px;")
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._zoom_label)

    def _add_selection_section(self, layout: QHBoxLayout) -> None:
        """Add selection tools section."""
        # Label
        label = QLabel("Selection:")
        label.setStyleSheet("color: #cccccc; font-size: 8pt; font-weight: bold;")
        layout.addWidget(label)

        # Select All Bad button
        self._select_bad_btn = QPushButton("Select Bad")
        self._select_bad_btn.setToolTip("Select all bad sectors")
        self._select_bad_btn.setFixedHeight(26)
        self._select_bad_btn.clicked.connect(self._on_select_bad_clicked)
        self._select_bad_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d30;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #3a3d41;
                border-color: #007acc;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
        """)
        layout.addWidget(self._select_bad_btn)

        # Clear Selection button
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Clear all selection")
        self._clear_btn.setFixedHeight(26)
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        self._clear_btn.setStyleSheet(self._select_bad_btn.styleSheet())
        layout.addWidget(self._clear_btn)

        # Invert button
        self._invert_btn = QPushButton("Invert")
        self._invert_btn.setToolTip("Invert current selection")
        self._invert_btn.setFixedHeight(26)
        self._invert_btn.clicked.connect(self._on_invert_clicked)
        self._invert_btn.setStyleSheet(self._select_bad_btn.styleSheet())
        layout.addWidget(self._invert_btn)

        # Selection count display
        self._selection_label = QLabel("Selected: 0")
        self._selection_label.setStyleSheet("color: #858585; font-size: 9pt; min-width: 80px;")
        layout.addWidget(self._selection_label)

    def _add_export_section(self, layout: QHBoxLayout) -> None:
        """Add export buttons section."""
        # Label
        label = QLabel("Export:")
        label.setStyleSheet("color: #cccccc; font-size: 8pt; font-weight: bold;")
        layout.addWidget(label)

        # PNG button
        self._export_png_btn = QPushButton("PNG")
        self._export_png_btn.setToolTip("Export sector map as PNG image")
        self._export_png_btn.setFixedHeight(26)
        self._export_png_btn.clicked.connect(self._on_export_png_clicked)
        self._export_png_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d30;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 3px;
                padding: 2px 10px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #3a3d41;
                border-color: #33cc33;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
        """)
        layout.addWidget(self._export_png_btn)

        # SVG button
        self._export_svg_btn = QPushButton("SVG")
        self._export_svg_btn.setToolTip("Export sector map as SVG vector")
        self._export_svg_btn.setFixedHeight(26)
        self._export_svg_btn.clicked.connect(self._on_export_svg_clicked)
        self._export_svg_btn.setStyleSheet(self._export_png_btn.styleSheet())
        layout.addWidget(self._export_svg_btn)

    # =========================================================================
    # Signal Handlers
    # =========================================================================

    def _on_view_mode_clicked(self, button_id: int) -> None:
        """Handle view mode button click."""
        mode_map = {
            0: ViewMode.STATUS,
            1: ViewMode.QUALITY,
            2: ViewMode.ERRORS,
            3: ViewMode.DATA_PATTERN,
        }

        mode = mode_map.get(button_id, ViewMode.STATUS)
        self._current_view_mode = mode

        # Update all connected sector maps
        for sector_map in self._sector_maps:
            sector_map.set_view_mode(mode)

        # Emit signal
        self.view_mode_changed.emit(mode.name.lower())

    def _on_fit_clicked(self) -> None:
        """Handle Fit button click."""
        for sector_map in self._sector_maps:
            sector_map.zoom_to_fit()
        self._update_zoom_display(1.0)

    def _on_zoom_100_clicked(self) -> None:
        """Handle 100% zoom button click."""
        for sector_map in self._sector_maps:
            sector_map.set_zoom_level(1.0)
        self._update_zoom_display(1.0)

    def _on_zoom_200_clicked(self) -> None:
        """Handle 200% zoom button click."""
        for sector_map in self._sector_maps:
            sector_map.set_zoom_level(2.0)
        self._update_zoom_display(2.0)

    def _on_zoom_slider_changed(self, value: int) -> None:
        """Handle zoom slider change."""
        zoom_level = value / 100.0
        self._current_zoom = zoom_level

        for sector_map in self._sector_maps:
            sector_map.set_zoom_level(zoom_level)

        self._zoom_label.setText(f"{value}%")
        self.zoom_changed.emit(zoom_level)

    def _on_select_bad_clicked(self) -> None:
        """Handle Select Bad button click."""
        for sector_map in self._sector_maps:
            sector_map.select_all_bad_sectors()

    def _on_clear_clicked(self) -> None:
        """Handle Clear button click."""
        for sector_map in self._sector_maps:
            sector_map.clear_selection()

    def _on_invert_clicked(self) -> None:
        """Handle Invert button click."""
        for sector_map in self._sector_maps:
            sector_map.invert_selection()

    def _on_export_png_clicked(self) -> None:
        """Handle Export PNG button click."""
        if not self._sector_maps:
            return

        # Show file dialog
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Sector Map as PNG",
            "sector_map.png",
            "PNG Images (*.png)"
        )

        if filepath:
            if not filepath.lower().endswith('.png'):
                filepath += '.png'

            # Export each map with head suffix if multiple maps
            all_success = True
            for sector_map in self._sector_maps:
                head_filter = sector_map.get_head_filter()
                if head_filter is not None and len(self._sector_maps) > 1:
                    # Add head suffix: sector_map.png -> sector_map_h0.png
                    base = filepath[:-4]  # Remove .png
                    export_path = f"{base}_h{head_filter}.png"
                else:
                    export_path = filepath

                success = sector_map.export_to_png(export_path)
                if success:
                    logger.info(f"Exported sector map to {export_path}")
                else:
                    all_success = False

            if all_success:
                self.export_requested.emit("png")
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    f"Failed to export one or more sector maps"
                )

    def _on_export_svg_clicked(self) -> None:
        """Handle Export SVG button click."""
        if not self._sector_maps:
            return

        # Show file dialog
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Sector Map as SVG",
            "sector_map.svg",
            "SVG Files (*.svg)"
        )

        if filepath:
            if not filepath.lower().endswith('.svg'):
                filepath += '.svg'

            # Export each map with head suffix if multiple maps
            all_success = True
            for sector_map in self._sector_maps:
                head_filter = sector_map.get_head_filter()
                if head_filter is not None and len(self._sector_maps) > 1:
                    # Add head suffix: sector_map.svg -> sector_map_h0.svg
                    base = filepath[:-4]  # Remove .svg
                    export_path = f"{base}_h{head_filter}.svg"
                else:
                    export_path = filepath

                success = sector_map.export_to_svg(export_path)
                if success:
                    logger.info(f"Exported sector map to {export_path}")
                else:
                    all_success = False

            if all_success:
                self.export_requested.emit("svg")
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    f"Failed to export one or more sector maps"
                )

    def _on_selection_changed(self, selected_sectors: List[int]) -> None:
        """Handle selection changed from any sector map."""
        # Count total selections across all maps
        total_selected: Set[int] = set()
        for sector_map in self._sector_maps:
            total_selected.update(sector_map.get_selected_sectors())
        self._selection_count = len(total_selected)
        self._selection_label.setText(f"Selected: {self._selection_count}")

    def _on_zoom_changed(self, zoom_level: float) -> None:
        """Handle zoom changed from sector map."""
        self._update_zoom_display(zoom_level)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _update_zoom_display(self, zoom_level: float) -> None:
        """Update zoom slider and label to match current zoom."""
        self._current_zoom = zoom_level
        zoom_percent = int(zoom_level * 100)

        # Update slider without triggering signal
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(max(50, min(400, zoom_percent)))
        self._zoom_slider.blockSignals(False)

        self._zoom_label.setText(f"{zoom_percent}%")

    # =========================================================================
    # Public API
    # =========================================================================

    def connect_to_sector_map(self, sector_map: CircularSectorMap) -> None:
        """
        Connect this toolbar to a CircularSectorMap instance.

        Can be called multiple times to connect multiple sector maps
        (e.g., one for each head).

        Args:
            sector_map: The sector map to control
        """
        if sector_map not in self._sector_maps:
            self._sector_maps.append(sector_map)

            # Connect sector map signals
            sector_map.selection_changed.connect(self._on_selection_changed)
            sector_map.zoom_changed.connect(self._on_zoom_changed)

            # Sync initial state from first map
            if len(self._sector_maps) == 1:
                self._update_zoom_display(sector_map.get_zoom_level())

    def disconnect_from_sector_map(self, sector_map: Optional[CircularSectorMap] = None) -> None:
        """
        Disconnect from a sector map.

        Args:
            sector_map: Specific map to disconnect, or None to disconnect all
        """
        if sector_map is None:
            # Disconnect all
            for sm in self._sector_maps:
                try:
                    sm.selection_changed.disconnect(self._on_selection_changed)
                    sm.zoom_changed.disconnect(self._on_zoom_changed)
                except Exception:
                    pass
            self._sector_maps.clear()
        elif sector_map in self._sector_maps:
            try:
                sector_map.selection_changed.disconnect(self._on_selection_changed)
                sector_map.zoom_changed.disconnect(self._on_zoom_changed)
            except Exception:
                pass
            self._sector_maps.remove(sector_map)

    def get_view_mode(self) -> ViewMode:
        """Get current view mode."""
        return self._current_view_mode

    def set_view_mode(self, mode: ViewMode) -> None:
        """
        Set the current view mode.

        Args:
            mode: ViewMode to set
        """
        mode_button_map = {
            ViewMode.STATUS: self._status_btn,
            ViewMode.QUALITY: self._quality_btn,
            ViewMode.ERRORS: self._errors_btn,
            ViewMode.DATA_PATTERN: self._pattern_btn,
        }

        button = mode_button_map.get(mode)
        if button:
            button.setChecked(True)
            self._current_view_mode = mode

            for sector_map in self._sector_maps:
                sector_map.set_view_mode(mode)

    def get_zoom_level(self) -> float:
        """Get current zoom level."""
        return self._current_zoom

    def set_zoom_level(self, level: float) -> None:
        """
        Set the zoom level.

        Args:
            level: Zoom level (1.0 = 100%)
        """
        for sector_map in self._sector_maps:
            sector_map.set_zoom_level(level)
        self._update_zoom_display(level)

    def get_selection_count(self) -> int:
        """Get number of selected sectors."""
        return self._selection_count

    def set_enabled(self, enabled: bool) -> None:
        """
        Enable or disable all toolbar controls.

        Args:
            enabled: True to enable, False to disable
        """
        # View mode buttons
        self._status_btn.setEnabled(enabled)
        self._quality_btn.setEnabled(enabled)
        self._errors_btn.setEnabled(enabled)
        self._pattern_btn.setEnabled(enabled)

        # Zoom controls
        self._fit_btn.setEnabled(enabled)
        self._zoom_100_btn.setEnabled(enabled)
        self._zoom_200_btn.setEnabled(enabled)
        self._zoom_slider.setEnabled(enabled)

        # Selection controls
        self._select_bad_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)
        self._invert_btn.setEnabled(enabled)

        # Export controls
        self._export_png_btn.setEnabled(enabled)
        self._export_svg_btn.setEnabled(enabled)
