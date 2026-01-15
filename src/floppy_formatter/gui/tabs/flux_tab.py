"""
Flux analysis tab for Analytics Dashboard.

Provides detailed flux visualization including:
- Track/sector selector for loading flux data
- Flux waveform widget (oscilloscope-style)
- Flux histogram widget (pulse width distribution)
- Export capabilities

Part of Phase 7: Analytics Dashboard
"""

from dataclasses import dataclass
from typing import List, Optional, Any, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QSpinBox,
    QComboBox,
    QPushButton,
    QSplitter,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal

from floppy_formatter.gui.widgets.flux_waveform_widget import (
    FluxWaveformWidget,
    FluxWaveformPanel,
    FluxMarker,
    MarkerType,
)
from floppy_formatter.gui.widgets.flux_histogram_widget import (
    FluxHistogramWidget,
    FluxHistogramPanel,
)

if TYPE_CHECKING:
    from floppy_formatter.analysis.flux_analyzer import FluxCapture

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

COLOR_BACKGROUND = "#1e1e1e"
COLOR_PANEL_BG = "#252526"
COLOR_BORDER = "#3a3d41"
COLOR_TEXT = "#cccccc"
COLOR_TEXT_DIM = "#808080"


# =============================================================================
# Sector Selector Widget
# =============================================================================

class TrackSectorSelector(QFrame):
    """
    Widget for selecting cylinder, head, and sector.

    Provides controls for loading flux data from a specific track
    or sector, with buttons for loading and live capture.

    Signals:
        load_requested(int, int, int): Emitted when Load Flux clicked (cyl, head, sector)
        capture_requested(int, int): Emitted when Capture Live clicked (cyl, head)
    """

    load_requested = pyqtSignal(int, int, int)  # cylinder, head, sector
    capture_requested = pyqtSignal(int, int)     # cylinder, head

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setStyleSheet(f"""
            TrackSectorSelector {{
                background-color: {COLOR_PANEL_BG};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
            }}
            QLabel {{
                color: {COLOR_TEXT};
            }}
            QSpinBox, QComboBox {{
                background-color: #3c3c3c;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 3px;
                padding: 4px;
                min-width: 60px;
            }}
            QPushButton {{
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: #1177bb;
            }}
            QPushButton:disabled {{
                background-color: #3c3c3c;
                color: #808080;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)

        # Cylinder
        layout.addWidget(QLabel("Cylinder:"))
        self._cylinder_spin = QSpinBox()
        self._cylinder_spin.setRange(0, 79)
        self._cylinder_spin.setValue(0)
        layout.addWidget(self._cylinder_spin)

        # Head
        layout.addWidget(QLabel("Head:"))
        self._head_combo = QComboBox()
        self._head_combo.addItems(["0", "1"])
        layout.addWidget(self._head_combo)

        # Sector
        layout.addWidget(QLabel("Sector:"))
        self._sector_spin = QSpinBox()
        self._sector_spin.setRange(0, 18)  # 0 = all sectors
        self._sector_spin.setSpecialValueText("All")
        self._sector_spin.setValue(0)
        layout.addWidget(self._sector_spin)

        layout.addStretch()

        # Load button
        self._load_btn = QPushButton("Load Flux")
        self._load_btn.clicked.connect(self._on_load_clicked)
        layout.addWidget(self._load_btn)

        # Capture button
        self._capture_btn = QPushButton("Capture Live")
        self._capture_btn.clicked.connect(self._on_capture_clicked)
        layout.addWidget(self._capture_btn)

    def get_cylinder(self) -> int:
        """Get selected cylinder."""
        return self._cylinder_spin.value()

    def get_head(self) -> int:
        """Get selected head."""
        return self._head_combo.currentIndex()

    def get_sector(self) -> int:
        """Get selected sector (0 = all)."""
        return self._sector_spin.value()

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable controls."""
        self._cylinder_spin.setEnabled(enabled)
        self._head_combo.setEnabled(enabled)
        self._sector_spin.setEnabled(enabled)
        self._load_btn.setEnabled(enabled)
        self._capture_btn.setEnabled(enabled)

    def _on_load_clicked(self) -> None:
        """Handle load button click."""
        self.load_requested.emit(
            self.get_cylinder(),
            self.get_head(),
            self.get_sector()
        )

    def _on_capture_clicked(self) -> None:
        """Handle capture button click."""
        self.capture_requested.emit(
            self.get_cylinder(),
            self.get_head()
        )


# =============================================================================
# Flux Tab
# =============================================================================

class FluxTab(QWidget):
    """
    Flux analysis tab with waveform and histogram visualization.

    Contains:
    - Track/sector selector for loading flux data
    - FluxWaveformWidget for oscilloscope-style display
    - FluxHistogramWidget for pulse width distribution
    - Export button for saving flux data

    Signals:
        load_flux_requested(int, int, int): Request to load flux (cyl, head, sector)
        capture_flux_requested(int, int): Request to capture live flux (cyl, head)
        export_requested(str): Request to export flux to file path
    """

    load_flux_requested = pyqtSignal(int, int, int)
    capture_flux_requested = pyqtSignal(int, int)
    export_requested = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._current_flux: Optional['FluxCapture'] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Top: Track/sector selector
        selector_row = QHBoxLayout()

        self._selector = TrackSectorSelector()
        self._selector.load_requested.connect(self._on_load_requested)
        self._selector.capture_requested.connect(self._on_capture_requested)
        selector_row.addWidget(self._selector, 1)

        # Export button
        self._export_btn = QPushButton("Export Flux...")
        self._export_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 3px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            QPushButton:disabled {
                color: #808080;
            }
        """)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export_clicked)
        selector_row.addWidget(self._export_btn)

        layout.addLayout(selector_row)

        # Splitter for waveform and histogram
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

        # Waveform panel
        self._waveform_panel = FluxWaveformPanel()
        splitter.addWidget(self._waveform_panel)

        # Histogram panel
        self._histogram_panel = FluxHistogramPanel()
        splitter.addWidget(self._histogram_panel)

        # Set initial sizes (70% waveform, 30% histogram)
        splitter.setSizes([300, 130])

        layout.addWidget(splitter, 1)

        # Info bar
        info_bar = QFrame()
        info_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PANEL_BG};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
            }}
            QLabel {{
                color: {COLOR_TEXT_DIM};
                font-size: 11px;
            }}
        """)
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(8, 4, 8, 4)
        info_layout.setSpacing(16)

        self._track_label = QLabel("Track: --")
        info_layout.addWidget(self._track_label)

        self._duration_label = QLabel("Duration: --")
        info_layout.addWidget(self._duration_label)

        self._transitions_label = QLabel("Transitions: --")
        info_layout.addWidget(self._transitions_label)

        self._quality_label = QLabel("Quality: --")
        info_layout.addWidget(self._quality_label)

        info_layout.addStretch()

        layout.addWidget(info_bar)

    def load_flux_data(self, flux: 'FluxCapture') -> None:
        """
        Load flux capture data for display.

        Args:
            flux: FluxCapture object from flux_analyzer
        """
        self._current_flux = flux

        # Convert to timing data in microseconds
        timings_us = flux.get_timings_microseconds()

        if not timings_us:
            self.clear_flux_display()
            return

        # Load into waveform
        self._waveform_panel.set_flux_data(timings_us)

        # Load into histogram
        self._histogram_panel.set_histogram_data(timings_us)

        # Add markers for sector positions (approximate)
        markers = self._generate_sector_markers(timings_us)
        self._waveform_panel.get_waveform_widget().set_markers(markers)

        # Update info bar
        self._track_label.setText(f"Track: C{flux.cylinder} H{flux.head}")
        self._duration_label.setText(f"Duration: {flux.duration_ms:.2f} ms")
        self._transitions_label.setText(f"Transitions: {flux.transition_count:,}")

        quality = self._histogram_panel.get_histogram_widget().get_quality_score()
        quality_text = f"Quality: {quality:.0%}"
        self._quality_label.setText(quality_text)

        # Enable export
        self._export_btn.setEnabled(True)

    def clear_flux_display(self) -> None:
        """Clear the flux display."""
        self._current_flux = None
        self._waveform_panel.get_waveform_widget().clear_flux_data()
        self._histogram_panel.clear_histogram()

        self._track_label.setText("Track: --")
        self._duration_label.setText("Duration: --")
        self._transitions_label.setText("Transitions: --")
        self._quality_label.setText("Quality: --")

        self._export_btn.setEnabled(False)

    def set_device_connected(self, connected: bool) -> None:
        """Update UI based on device connection state."""
        self._selector.set_enabled(connected)

    def _generate_sector_markers(self, timings_us: List[float]) -> List[FluxMarker]:
        """Generate approximate sector markers."""
        markers = []

        # For HD disks, approximately 18 sectors per track
        # Each sector is roughly 1/18th of 200ms (at 300 RPM)
        # That's about 11.1 ms per sector

        total_time = sum(timings_us) / 1000.0  # Convert to ms

        if total_time > 0:
            # Add index marker at start
            markers.append(FluxMarker(
                position_us=0,
                marker_type=MarkerType.INDEX,
                label="Index"
            ))

            # Add approximate sector markers
            sector_duration_ms = total_time / 18  # Assuming 18 sectors
            for sector in range(18):
                pos_us = sector * sector_duration_ms * 1000
                markers.append(FluxMarker(
                    position_us=pos_us,
                    marker_type=MarkerType.SECTOR,
                    label=f"S{sector + 1}"
                ))

        return markers

    def _on_load_requested(self, cylinder: int, head: int, sector: int) -> None:
        """Handle load flux request."""
        self.load_flux_requested.emit(cylinder, head, sector)

    def _on_capture_requested(self, cylinder: int, head: int) -> None:
        """Handle capture flux request."""
        self.capture_flux_requested.emit(cylinder, head)

    def _on_export_clicked(self) -> None:
        """Handle export button click."""
        if not self._current_flux:
            return

        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Flux Data",
            f"flux_c{self._current_flux.cylinder}_h{self._current_flux.head}.scp",
            "SuperCard Pro Files (*.scp);;All Files (*)"
        )

        if file_path:
            self.export_requested.emit(file_path)

    def get_waveform_widget(self) -> FluxWaveformWidget:
        """Get the waveform widget."""
        return self._waveform_panel.get_waveform_widget()

    def get_histogram_widget(self) -> FluxHistogramWidget:
        """Get the histogram widget."""
        return self._histogram_panel.get_histogram_widget()

    def get_current_flux(self) -> Optional['FluxCapture']:
        """
        Get the currently loaded flux data.

        Returns:
            FluxCapture object or None if no flux is loaded
        """
        return self._current_flux


__all__ = [
    'FluxTab',
    'TrackSectorSelector',
]
