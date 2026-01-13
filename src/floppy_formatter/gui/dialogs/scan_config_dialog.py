"""
Scan configuration dialog for Greaseweazle operations.

Provides user-configurable settings for disk scanning including
scan mode, flux capture options, and track range selection.

Part of Phase 10: Operation Dialogs & Configurations
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QSpinBox,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


# =============================================================================
# Enums and Data Classes
# =============================================================================

class ScanMode(Enum):
    """Scan mode determining thoroughness and speed."""
    QUICK = auto()      # Sample tracks only
    STANDARD = auto()   # All tracks, single pass
    THOROUGH = auto()   # All tracks with multi-revolution capture


@dataclass
class ScanConfig:
    """
    Configuration for a scan operation.

    Attributes:
        mode: Scan mode (QUICK, STANDARD, THOROUGH)
        capture_flux: Whether to save raw flux data
        start_cylinder: Starting cylinder for range scan
        end_cylinder: Ending cylinder for range scan
        scan_all_tracks: Whether to scan all tracks
    """
    mode: ScanMode = ScanMode.STANDARD
    capture_flux: bool = False
    start_cylinder: int = 0
    end_cylinder: int = 79
    scan_all_tracks: bool = True


# =============================================================================
# Scan Config Dialog
# =============================================================================

class ScanConfigDialog(QDialog):
    """
    Dialog for configuring disk scan operations.

    Provides options for:
    - Scan mode (Quick/Standard/Thorough)
    - Flux capture enable/disable
    - Track range selection

    Example:
        dialog = ScanConfigDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            # Start scan with config
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize scan config dialog.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the dialog user interface."""
        self.setWindowTitle("Scan Configuration")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setMinimumHeight(480)

        # Apply dark theme styling
        self._apply_dialog_style()

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_label = QLabel("Scan Configuration")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # Scan Mode group
        mode_group = QGroupBox("Scan Mode")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(8)

        self._mode_group = QButtonGroup(self)

        # Quick mode
        self._quick_radio = QRadioButton("Quick")
        self._quick_radio.setToolTip("Fast scan of sample tracks only")
        self._mode_group.addButton(self._quick_radio, 0)
        mode_layout.addWidget(self._quick_radio)

        quick_desc = QLabel("Scans tracks 0, 40, 79 plus random samples. Fast but may miss problems.")
        quick_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        quick_desc.setWordWrap(True)
        mode_layout.addWidget(quick_desc)

        # Standard mode
        self._standard_radio = QRadioButton("Standard")
        self._standard_radio.setToolTip("Full scan with single pass per track")
        self._standard_radio.setChecked(True)
        self._mode_group.addButton(self._standard_radio, 1)
        mode_layout.addWidget(self._standard_radio)

        standard_desc = QLabel("Scans all tracks with single-revolution capture. Recommended for routine checks.")
        standard_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        standard_desc.setWordWrap(True)
        mode_layout.addWidget(standard_desc)

        # Thorough mode
        self._thorough_radio = QRadioButton("Thorough")
        self._thorough_radio.setToolTip("Deep scan with multiple revolutions for quality assessment")
        self._mode_group.addButton(self._thorough_radio, 2)
        mode_layout.addWidget(self._thorough_radio)

        thorough_desc = QLabel("Multi-revolution capture for quality assessment. Slower but detects marginal sectors.")
        thorough_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        thorough_desc.setWordWrap(True)
        mode_layout.addWidget(thorough_desc)

        layout.addWidget(mode_group)

        # Flux Capture group
        flux_group = QGroupBox("Flux Capture")
        flux_layout = QVBoxLayout(flux_group)
        flux_layout.setSpacing(8)

        self._capture_flux_check = QCheckBox("Save raw flux data")
        self._capture_flux_check.setToolTip("Store raw flux timing data for detailed analysis")
        flux_layout.addWidget(self._capture_flux_check)

        flux_desc = QLabel("Enables detailed flux analysis in the Flux tab. View waveforms, histograms, and signal quality.")
        flux_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        flux_desc.setWordWrap(True)
        flux_layout.addWidget(flux_desc)

        flux_note = QLabel("Note: Enabling flux capture increases memory usage significantly.")
        flux_note.setStyleSheet("color: #b89500; font-size: 9pt; margin-left: 24px;")
        flux_note.setWordWrap(True)
        flux_layout.addWidget(flux_note)

        layout.addWidget(flux_group)

        # Track Range group
        range_group = QGroupBox("Track Range")
        range_layout = QVBoxLayout(range_group)
        range_layout.setSpacing(8)

        self._scan_all_check = QCheckBox("Scan all tracks")
        self._scan_all_check.setChecked(True)
        self._scan_all_check.setToolTip("Scan all 80 cylinders (160 tracks)")
        range_layout.addWidget(self._scan_all_check)

        # Cylinder range
        range_row = QHBoxLayout()
        range_row.setSpacing(12)

        start_label = QLabel("Start cylinder:")
        start_label.setMinimumWidth(90)
        range_row.addWidget(start_label)

        self._start_spin = QSpinBox()
        self._start_spin.setRange(0, 79)
        self._start_spin.setValue(0)
        self._start_spin.setEnabled(False)
        self._start_spin.setToolTip("First cylinder to scan (0-79)")
        self._start_spin.setMinimumWidth(70)
        range_row.addWidget(self._start_spin)

        range_row.addSpacing(20)

        end_label = QLabel("End cylinder:")
        end_label.setMinimumWidth(80)
        range_row.addWidget(end_label)

        self._end_spin = QSpinBox()
        self._end_spin.setRange(0, 79)
        self._end_spin.setValue(79)
        self._end_spin.setEnabled(False)
        self._end_spin.setToolTip("Last cylinder to scan (0-79)")
        self._end_spin.setMinimumWidth(70)
        range_row.addWidget(self._end_spin)

        range_row.addStretch()
        range_layout.addLayout(range_row)

        layout.addWidget(range_group)

        # Spacer
        layout.addStretch()

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3a3d41;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.addStretch()

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setMinimumWidth(100)
        self._cancel_button.setMinimumHeight(32)
        self._cancel_button.clicked.connect(self.reject)
        self._cancel_button.setShortcut("Escape")
        button_layout.addWidget(self._cancel_button)

        self._start_button = QPushButton("Start Scan")
        self._start_button.setMinimumWidth(120)
        self._start_button.setMinimumHeight(32)
        self._start_button.clicked.connect(self._on_start_clicked)
        self._start_button.setDefault(True)
        button_layout.addWidget(self._start_button)

        layout.addLayout(button_layout)

        # Apply button styles
        self._apply_button_styles()

    def _apply_dialog_style(self) -> None:
        """Apply dark theme styling to dialog."""
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #cccccc;
            }
            QLabel {
                color: #cccccc;
                background-color: transparent;
            }
            QGroupBox {
                border: 1px solid #3a3d41;
                border-radius: 4px;
                margin-top: 12px;
                padding: 12px;
                padding-top: 24px;
                font-weight: bold;
                color: #cccccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                background-color: #1e1e1e;
                color: #cccccc;
            }
            QRadioButton {
                color: #cccccc;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #6c6c6c;
                border-radius: 8px;
                background-color: #3a3d41;
            }
            QRadioButton::indicator:hover {
                border-color: #007acc;
            }
            QRadioButton::indicator:checked {
                background-color: #0e639c;
                border-color: #0e639c;
            }
            QCheckBox {
                color: #cccccc;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #6c6c6c;
                border-radius: 3px;
                background-color: #3a3d41;
            }
            QCheckBox::indicator:hover {
                border-color: #007acc;
            }
            QCheckBox::indicator:checked {
                background-color: #0e639c;
                border-color: #0e639c;
            }
            QSpinBox {
                background-color: #3a3d41;
                color: #cccccc;
                border: 1px solid #6c6c6c;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QSpinBox:disabled {
                background-color: #2d2d30;
                color: #6c6c6c;
                border-color: #3a3d41;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #4e5157;
                border: none;
                width: 20px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #5a5d63;
            }
        """)

    def _apply_button_styles(self) -> None:
        """Apply button styling."""
        self._cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3d41;
                color: #ffffff;
                border: 1px solid #6c6c6c;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4e5157;
                border-color: #858585;
            }
            QPushButton:pressed {
                background-color: #2d2d30;
            }
        """)
        self._start_button.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
        """)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self._scan_all_check.toggled.connect(self._on_scan_all_toggled)
        self._start_spin.valueChanged.connect(self._validate_range)
        self._end_spin.valueChanged.connect(self._validate_range)

    def _on_scan_all_toggled(self, checked: bool) -> None:
        """Handle scan all tracks checkbox toggle."""
        self._start_spin.setEnabled(not checked)
        self._end_spin.setEnabled(not checked)

    def _validate_range(self) -> None:
        """Validate cylinder range and update UI."""
        start = self._start_spin.value()
        end = self._end_spin.value()

        # Ensure start <= end
        if start > end:
            if self.sender() == self._start_spin:
                self._end_spin.setValue(start)
            else:
                self._start_spin.setValue(end)

    def _on_start_clicked(self) -> None:
        """Handle Start Scan button click."""
        self.accept()

    def get_config(self) -> ScanConfig:
        """
        Get the configured scan settings.

        Returns:
            ScanConfig with current dialog settings
        """
        # Determine mode
        if self._quick_radio.isChecked():
            mode = ScanMode.QUICK
        elif self._thorough_radio.isChecked():
            mode = ScanMode.THOROUGH
        else:
            mode = ScanMode.STANDARD

        return ScanConfig(
            mode=mode,
            capture_flux=self._capture_flux_check.isChecked(),
            start_cylinder=self._start_spin.value(),
            end_cylinder=self._end_spin.value(),
            scan_all_tracks=self._scan_all_check.isChecked(),
        )

    def set_config(self, config: ScanConfig) -> None:
        """
        Set dialog values from a config.

        Args:
            config: ScanConfig to apply
        """
        # Set mode
        if config.mode == ScanMode.QUICK:
            self._quick_radio.setChecked(True)
        elif config.mode == ScanMode.THOROUGH:
            self._thorough_radio.setChecked(True)
        else:
            self._standard_radio.setChecked(True)

        self._capture_flux_check.setChecked(config.capture_flux)
        self._scan_all_check.setChecked(config.scan_all_tracks)
        self._start_spin.setValue(config.start_cylinder)
        self._end_spin.setValue(config.end_cylinder)


def show_scan_config_dialog(parent: Optional[QWidget] = None) -> Optional[ScanConfig]:
    """
    Show the scan configuration dialog.

    Args:
        parent: Optional parent widget

    Returns:
        ScanConfig if accepted, None if cancelled
    """
    dialog = ScanConfigDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_config()
    return None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'ScanConfigDialog',
    'ScanConfig',
    'ScanMode',
    'show_scan_config_dialog',
]
