"""
Analysis configuration dialog for Greaseweazle operations.

Provides user-configurable settings for disk analysis including
analysis depth, component selection, track range, and report options.

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
    QComboBox,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


# =============================================================================
# Enums and Data Classes
# =============================================================================

class AnalysisDepth(Enum):
    """Analysis depth determining thoroughness and speed."""
    QUICK = auto()          # Sample tracks, basic metrics
    FULL = auto()           # All tracks, full analysis
    COMPREHENSIVE = auto()  # All tracks plus forensics


@dataclass
class AnalysisConfig:
    """
    Configuration for an analysis operation.

    Attributes:
        depth: Analysis depth (QUICK, FULL, COMPREHENSIVE)
        analyze_flux: Enable flux timing and histogram analysis
        analyze_alignment: Enable head alignment measurement
        analyze_forensics: Enable forensic analysis (copy protection, etc.)
        start_cylinder: Starting cylinder for range analysis
        end_cylinder: Ending cylinder for range analysis
        analyze_all_tracks: Whether to analyze all tracks
        revolutions_per_track: Flux revolutions to capture per track
        save_report: Whether to save analysis report
        report_format: Output report format (html, pdf, json)
    """
    depth: AnalysisDepth = AnalysisDepth.FULL
    analyze_flux: bool = True
    analyze_alignment: bool = False
    analyze_forensics: bool = False
    start_cylinder: int = 0
    end_cylinder: int = 79
    analyze_all_tracks: bool = True
    revolutions_per_track: int = 3
    save_report: bool = True
    report_format: str = 'html'


# =============================================================================
# Analyze Config Dialog
# =============================================================================

class AnalyzeConfigDialog(QDialog):
    """
    Dialog for configuring disk analysis operations.

    Provides options for:
    - Analysis depth (Quick/Full/Comprehensive)
    - Analysis components (Flux/Alignment/Forensics)
    - Track range selection
    - Capture settings
    - Report output options

    Example:
        dialog = AnalyzeConfigDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            # Start analysis with config
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize analyze config dialog.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        self._update_depth_components()

    def _setup_ui(self) -> None:
        """Set up the dialog user interface."""
        self.setWindowTitle("Analysis Configuration")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(620)

        # Apply dark theme styling
        self._apply_dialog_style()

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_label = QLabel("Analysis Configuration")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # Analysis Depth group
        depth_group = QGroupBox("Analysis Depth")
        depth_layout = QVBoxLayout(depth_group)
        depth_layout.setSpacing(8)

        self._depth_group = QButtonGroup(self)

        # Quick analysis
        self._quick_radio = QRadioButton("Quick")
        self._quick_radio.setToolTip("Basic flux quality check on sample tracks")
        self._depth_group.addButton(self._quick_radio, 0)
        depth_layout.addWidget(self._quick_radio)

        quick_desc = QLabel("Fast quality check on sample tracks (0, 40, 79). Basic signal metrics only.")
        quick_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        quick_desc.setWordWrap(True)
        depth_layout.addWidget(quick_desc)

        # Full analysis
        self._full_radio = QRadioButton("Full")
        self._full_radio.setToolTip("Complete flux analysis on all tracks")
        self._full_radio.setChecked(True)
        self._depth_group.addButton(self._full_radio, 1)
        depth_layout.addWidget(self._full_radio)

        full_desc = QLabel("Complete analysis of all tracks. Includes flux timing, histograms, and quality grading.")
        full_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        full_desc.setWordWrap(True)
        depth_layout.addWidget(full_desc)

        # Comprehensive analysis
        self._comprehensive_radio = QRadioButton("Comprehensive")
        self._comprehensive_radio.setToolTip("Full analysis plus forensic examination")
        self._depth_group.addButton(self._comprehensive_radio, 2)
        depth_layout.addWidget(self._comprehensive_radio)

        comp_desc = QLabel("Full analysis plus forensic examination. Detects copy protection, non-standard formats, deleted data.")
        comp_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        comp_desc.setWordWrap(True)
        depth_layout.addWidget(comp_desc)

        layout.addWidget(depth_group)

        # Analysis Components group
        components_group = QGroupBox("Analysis Components")
        components_layout = QVBoxLayout(components_group)
        components_layout.setSpacing(8)

        self._flux_check = QCheckBox("Flux Analysis")
        self._flux_check.setChecked(True)
        self._flux_check.setToolTip("Signal quality, timing jitter, histogram analysis")
        components_layout.addWidget(self._flux_check)

        flux_desc = QLabel("Analyzes signal quality, timing jitter, and pulse width distribution.")
        flux_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        flux_desc.setWordWrap(True)
        components_layout.addWidget(flux_desc)

        self._alignment_check = QCheckBox("Head Alignment")
        self._alignment_check.setToolTip("Track margin measurement, azimuth detection")
        components_layout.addWidget(self._alignment_check)

        alignment_desc = QLabel("Measures track margins and detects head alignment issues.")
        alignment_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        alignment_desc.setWordWrap(True)
        components_layout.addWidget(alignment_desc)

        self._forensics_check = QCheckBox("Forensic Analysis")
        self._forensics_check.setToolTip("Copy protection detection, format analysis, deleted data recovery")
        components_layout.addWidget(self._forensics_check)

        forensics_desc = QLabel("Detects copy protection, analyzes format type, attempts deleted data recovery.")
        forensics_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        forensics_desc.setWordWrap(True)
        components_layout.addWidget(forensics_desc)

        components_note = QLabel("Components are auto-selected based on depth but can be manually adjusted.")
        components_note.setStyleSheet("color: #b89500; font-size: 9pt; font-style: italic;")
        components_note.setWordWrap(True)
        components_layout.addWidget(components_note)

        layout.addWidget(components_group)

        # Track Range group
        range_group = QGroupBox("Track Range")
        range_layout = QVBoxLayout(range_group)
        range_layout.setSpacing(8)

        self._analyze_all_check = QCheckBox("Analyze all tracks")
        self._analyze_all_check.setChecked(True)
        self._analyze_all_check.setToolTip("Analyze all 80 cylinders (160 tracks)")
        range_layout.addWidget(self._analyze_all_check)

        range_row = QHBoxLayout()
        range_row.setSpacing(12)

        start_label = QLabel("Start cylinder:")
        start_label.setMinimumWidth(90)
        range_row.addWidget(start_label)

        self._start_spin = QSpinBox()
        self._start_spin.setRange(0, 79)
        self._start_spin.setValue(0)
        self._start_spin.setEnabled(False)
        self._start_spin.setToolTip("First cylinder to analyze (0-79)")
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
        self._end_spin.setToolTip("Last cylinder to analyze (0-79)")
        self._end_spin.setMinimumWidth(70)
        range_row.addWidget(self._end_spin)

        range_row.addStretch()
        range_layout.addLayout(range_row)

        layout.addWidget(range_group)

        # Capture Settings group
        capture_group = QGroupBox("Capture Settings")
        capture_layout = QVBoxLayout(capture_group)
        capture_layout.setSpacing(8)

        rev_row = QHBoxLayout()
        rev_row.setSpacing(12)

        rev_label = QLabel("Revolutions per track:")
        rev_label.setMinimumWidth(140)
        rev_row.addWidget(rev_label)

        self._revolutions_spin = QSpinBox()
        self._revolutions_spin.setRange(1, 20)
        self._revolutions_spin.setValue(3)
        self._revolutions_spin.setToolTip("Number of disk revolutions to capture (1-20)")
        self._revolutions_spin.setMinimumWidth(70)
        rev_row.addWidget(self._revolutions_spin)

        rev_row.addStretch()
        capture_layout.addLayout(rev_row)

        rev_desc = QLabel("More revolutions = better quality assessment but slower analysis.")
        rev_desc.setStyleSheet("color: #858585; font-size: 9pt;")
        rev_desc.setWordWrap(True)
        capture_layout.addWidget(rev_desc)

        layout.addWidget(capture_group)

        # Output group
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)
        output_layout.setSpacing(8)

        self._save_report_check = QCheckBox("Save analysis report")
        self._save_report_check.setChecked(True)
        self._save_report_check.setToolTip("Generate and save detailed analysis report")
        output_layout.addWidget(self._save_report_check)

        format_row = QHBoxLayout()
        format_row.setSpacing(12)
        format_row.addSpacing(24)

        format_label = QLabel("Report format:")
        format_label.setMinimumWidth(90)
        format_row.addWidget(format_label)

        self._format_combo = QComboBox()
        self._format_combo.addItem("HTML", "html")
        self._format_combo.addItem("PDF", "pdf")
        self._format_combo.addItem("JSON", "json")
        self._format_combo.setToolTip("Output format for analysis report")
        self._format_combo.setMinimumWidth(100)
        format_row.addWidget(self._format_combo)

        format_row.addStretch()
        output_layout.addLayout(format_row)

        layout.addWidget(output_group)

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

        self._start_button = QPushButton("Start Analysis")
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
            QComboBox {
                background-color: #3a3d41;
                color: #cccccc;
                border: 1px solid #6c6c6c;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QComboBox:hover {
                border-color: #007acc;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d30;
                color: #cccccc;
                selection-background-color: #0e639c;
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
        self._depth_group.buttonClicked.connect(self._on_depth_changed)
        self._analyze_all_check.toggled.connect(self._on_analyze_all_toggled)
        self._save_report_check.toggled.connect(self._on_save_report_toggled)
        self._start_spin.valueChanged.connect(self._validate_range)
        self._end_spin.valueChanged.connect(self._validate_range)

    def _on_depth_changed(self) -> None:
        """Handle analysis depth change."""
        self._update_depth_components()

    def _update_depth_components(self) -> None:
        """Update component checkboxes based on depth selection."""
        if self._quick_radio.isChecked():
            # Quick: flux only
            self._flux_check.setChecked(True)
            self._alignment_check.setChecked(False)
            self._forensics_check.setChecked(False)
            self._revolutions_spin.setValue(1)
        elif self._full_radio.isChecked():
            # Full: flux + optional alignment
            self._flux_check.setChecked(True)
            self._alignment_check.setChecked(False)
            self._forensics_check.setChecked(False)
            self._revolutions_spin.setValue(3)
        elif self._comprehensive_radio.isChecked():
            # Comprehensive: everything
            self._flux_check.setChecked(True)
            self._alignment_check.setChecked(True)
            self._forensics_check.setChecked(True)
            self._revolutions_spin.setValue(5)

    def _on_analyze_all_toggled(self, checked: bool) -> None:
        """Handle analyze all tracks checkbox toggle."""
        self._start_spin.setEnabled(not checked)
        self._end_spin.setEnabled(not checked)

    def _on_save_report_toggled(self, checked: bool) -> None:
        """Handle save report checkbox toggle."""
        self._format_combo.setEnabled(checked)

    def _validate_range(self) -> None:
        """Validate cylinder range."""
        start = self._start_spin.value()
        end = self._end_spin.value()

        if start > end:
            if self.sender() == self._start_spin:
                self._end_spin.setValue(start)
            else:
                self._start_spin.setValue(end)

    def _on_start_clicked(self) -> None:
        """Handle Start Analysis button click."""
        self.accept()

    def get_config(self) -> AnalysisConfig:
        """
        Get the configured analysis settings.

        Returns:
            AnalysisConfig with current dialog settings
        """
        # Determine depth
        if self._quick_radio.isChecked():
            depth = AnalysisDepth.QUICK
        elif self._comprehensive_radio.isChecked():
            depth = AnalysisDepth.COMPREHENSIVE
        else:
            depth = AnalysisDepth.FULL

        return AnalysisConfig(
            depth=depth,
            analyze_flux=self._flux_check.isChecked(),
            analyze_alignment=self._alignment_check.isChecked(),
            analyze_forensics=self._forensics_check.isChecked(),
            start_cylinder=self._start_spin.value(),
            end_cylinder=self._end_spin.value(),
            analyze_all_tracks=self._analyze_all_check.isChecked(),
            revolutions_per_track=self._revolutions_spin.value(),
            save_report=self._save_report_check.isChecked(),
            report_format=self._format_combo.currentData(),
        )

    def set_config(self, config: AnalysisConfig) -> None:
        """
        Set dialog values from a config.

        Args:
            config: AnalysisConfig to apply
        """
        # Set depth
        if config.depth == AnalysisDepth.QUICK:
            self._quick_radio.setChecked(True)
        elif config.depth == AnalysisDepth.COMPREHENSIVE:
            self._comprehensive_radio.setChecked(True)
        else:
            self._full_radio.setChecked(True)

        # Set components (after depth to override defaults)
        self._flux_check.setChecked(config.analyze_flux)
        self._alignment_check.setChecked(config.analyze_alignment)
        self._forensics_check.setChecked(config.analyze_forensics)

        # Set track range
        self._analyze_all_check.setChecked(config.analyze_all_tracks)
        self._start_spin.setValue(config.start_cylinder)
        self._end_spin.setValue(config.end_cylinder)

        # Set capture settings
        self._revolutions_spin.setValue(config.revolutions_per_track)

        # Set output options
        self._save_report_check.setChecked(config.save_report)
        for i in range(self._format_combo.count()):
            if self._format_combo.itemData(i) == config.report_format:
                self._format_combo.setCurrentIndex(i)
                break


def show_analyze_config_dialog(parent: Optional[QWidget] = None) -> Optional[AnalysisConfig]:
    """
    Show the analysis configuration dialog.

    Args:
        parent: Optional parent widget

    Returns:
        AnalysisConfig if accepted, None if cancelled
    """
    dialog = AnalyzeConfigDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_config()
    return None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'AnalyzeConfigDialog',
    'AnalysisConfig',
    'AnalysisDepth',
    'show_analyze_config_dialog',
]
