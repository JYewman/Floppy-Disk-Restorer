"""
Export dialog for Greaseweazle operations.

Provides configuration for exporting disk data in various formats
including sector images (IMG/IMA), flux images (SCP/HFE), and
analysis reports (PDF/HTML).

Part of Phase 10: Operation Dialogs & Configurations
"""

import os
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
    QLineEdit,
    QFrame,
    QFileDialog,
    QStackedWidget,
)
from PyQt6.QtGui import QFont


# =============================================================================
# Enums and Data Classes
# =============================================================================

class ExportType(Enum):
    """Export format types."""
    IMG = auto()   # Sector image (IMG/IMA)
    SCP = auto()   # SuperCard Pro flux image
    HFE = auto()   # HxC Floppy Emulator flux image
    PDF = auto()   # PDF analysis report
    HTML = auto()  # HTML analysis report


# File extensions for each export type
EXPORT_EXTENSIONS = {
    ExportType.IMG: ".img",
    ExportType.SCP: ".scp",
    ExportType.HFE: ".hfe",
    ExportType.PDF: ".pdf",
    ExportType.HTML: ".html",
}

# File filter strings for save dialogs
EXPORT_FILTERS = {
    ExportType.IMG: "Disk Image (*.img *.ima);;All Files (*)",
    ExportType.SCP: "SuperCard Pro Image (*.scp);;All Files (*)",
    ExportType.HFE: "HxC Floppy Emulator Image (*.hfe);;All Files (*)",
    ExportType.PDF: "PDF Document (*.pdf);;All Files (*)",
    ExportType.HTML: "HTML Document (*.html *.htm);;All Files (*)",
}


@dataclass
class ExportConfig:
    """
    Configuration for an export operation.

    Attributes:
        export_type: Type of export (IMG, SCP, HFE, PDF, HTML)
        start_cylinder: Starting cylinder for partial export
        end_cylinder: Ending cylinder for partial export
        export_all_tracks: Whether to export all tracks
        include_bad_sectors: Fill bad sectors with zeros in image
        pad_to_standard: Pad image to standard 1.44MB size
        revolutions: Flux revolutions to capture for flux images
        normalize_flux: Normalize timing in flux images
        include_charts: Include flux charts in reports
        include_sector_map: Include sector map in reports
        compress: Whether to compress output
        compression_type: Type of compression (none, zip, gzip)
        output_path: Full path for output file
    """
    export_type: ExportType = ExportType.IMG
    start_cylinder: int = 0
    end_cylinder: int = 79
    export_all_tracks: bool = True
    include_bad_sectors: bool = True
    pad_to_standard: bool = True
    revolutions: int = 2
    normalize_flux: bool = True
    include_charts: bool = True
    include_sector_map: bool = True
    compress: bool = False
    compression_type: str = 'none'
    output_path: str = ''


# =============================================================================
# Export Dialog
# =============================================================================

class ExportDialog(QDialog):
    """
    Dialog for configuring disk export operations.

    Provides options for:
    - Export type selection (IMG, SCP, HFE, PDF, HTML)
    - Track range for image exports
    - Format-specific options
    - Compression settings
    - Output file selection

    Example:
        dialog = ExportDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            # Start export with config
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        default_filename: str = "disk_export"
    ):
        """
        Initialize export dialog.

        Args:
            parent: Optional parent widget
            default_filename: Default filename without extension
        """
        super().__init__(parent)
        self._default_filename = default_filename
        self._setup_ui()
        self._connect_signals()
        self._update_options_visibility()
        self._update_filename()

    def _setup_ui(self) -> None:
        """Set up the dialog user interface."""
        self.setWindowTitle("Export Disk Image")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setMinimumHeight(580)

        # Apply dark theme styling
        self._apply_dialog_style()

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_label = QLabel("Export Disk Image")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # Export Type group
        type_group = QGroupBox("Export Type")
        type_layout = QVBoxLayout(type_group)
        type_layout.setSpacing(8)

        self._type_group = QButtonGroup(self)

        # Sector Image (IMG/IMA)
        self._img_radio = QRadioButton("Sector Image (IMG/IMA)")
        self._img_radio.setToolTip("Standard sector-level disk image")
        self._img_radio.setChecked(True)
        self._type_group.addButton(self._img_radio, 0)
        type_layout.addWidget(self._img_radio)

        img_desc = QLabel("Standard sector image, compatible with emulators and disk utilities.")
        img_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        img_desc.setWordWrap(True)
        type_layout.addWidget(img_desc)

        # SCP Flux Image
        self._scp_radio = QRadioButton("Flux Image (SCP)")
        self._scp_radio.setToolTip("SuperCard Pro raw flux format")
        self._type_group.addButton(self._scp_radio, 1)
        type_layout.addWidget(self._scp_radio)

        scp_desc = QLabel(
            "Raw flux data in SuperCard Pro format. Best for archival and preservation."
        )
        scp_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        scp_desc.setWordWrap(True)
        type_layout.addWidget(scp_desc)

        # HFE Flux Image
        self._hfe_radio = QRadioButton("Flux Image (HFE)")
        self._hfe_radio.setToolTip("HxC Floppy Emulator format")
        self._type_group.addButton(self._hfe_radio, 2)
        type_layout.addWidget(self._hfe_radio)

        hfe_desc = QLabel("Flux image for HxC Floppy Emulator hardware and Gotek drives.")
        hfe_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        hfe_desc.setWordWrap(True)
        type_layout.addWidget(hfe_desc)

        # PDF Report
        self._pdf_radio = QRadioButton("Analysis Report (PDF)")
        self._pdf_radio.setToolTip("Export analysis as PDF document")
        self._type_group.addButton(self._pdf_radio, 3)
        type_layout.addWidget(self._pdf_radio)

        pdf_desc = QLabel("Detailed report with charts and analysis in PDF format.")
        pdf_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        pdf_desc.setWordWrap(True)
        type_layout.addWidget(pdf_desc)

        # HTML Report
        self._html_radio = QRadioButton("Analysis Report (HTML)")
        self._html_radio.setToolTip("Export analysis as web page")
        self._type_group.addButton(self._html_radio, 4)
        type_layout.addWidget(self._html_radio)

        html_desc = QLabel("Detailed report as interactive HTML web page.")
        html_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        html_desc.setWordWrap(True)
        type_layout.addWidget(html_desc)

        layout.addWidget(type_group)

        # Track Range group (for image exports only)
        self._range_group = QGroupBox("Track Range")
        range_layout = QVBoxLayout(self._range_group)
        range_layout.setSpacing(8)

        self._export_all_check = QCheckBox("Export all tracks")
        self._export_all_check.setChecked(True)
        self._export_all_check.setToolTip("Export all 80 cylinders (160 tracks)")
        range_layout.addWidget(self._export_all_check)

        range_row = QHBoxLayout()
        range_row.setSpacing(12)

        start_label = QLabel("Start cylinder:")
        start_label.setMinimumWidth(90)
        range_row.addWidget(start_label)

        self._start_spin = QSpinBox()
        self._start_spin.setRange(0, 79)
        self._start_spin.setValue(0)
        self._start_spin.setEnabled(False)
        self._start_spin.setToolTip("First cylinder to export (0-79)")
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
        self._end_spin.setToolTip("Last cylinder to export (0-79)")
        self._end_spin.setMinimumWidth(70)
        range_row.addWidget(self._end_spin)

        range_row.addStretch()
        range_layout.addLayout(range_row)

        layout.addWidget(self._range_group)

        # Options group (content changes based on export type)
        self._options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(self._options_group)
        options_layout.setSpacing(8)

        # Create stacked widget for different option sets
        self._options_stack = QStackedWidget()

        # Page 0: Sector image options
        sector_options = QWidget()
        sector_layout = QVBoxLayout(sector_options)
        sector_layout.setContentsMargins(0, 0, 0, 0)
        sector_layout.setSpacing(8)

        self._bad_sectors_check = QCheckBox("Include bad sectors as zeros")
        self._bad_sectors_check.setChecked(True)
        self._bad_sectors_check.setToolTip("Fill unreadable sectors with zero bytes")
        sector_layout.addWidget(self._bad_sectors_check)

        self._pad_check = QCheckBox("Pad to standard size (1.44MB)")
        self._pad_check.setChecked(True)
        self._pad_check.setToolTip("Ensure image is exactly 1,474,560 bytes")
        sector_layout.addWidget(self._pad_check)

        sector_layout.addStretch()
        self._options_stack.addWidget(sector_options)

        # Page 1: Flux image options
        flux_options = QWidget()
        flux_layout = QVBoxLayout(flux_options)
        flux_layout.setContentsMargins(0, 0, 0, 0)
        flux_layout.setSpacing(8)

        rev_row = QHBoxLayout()
        rev_row.setSpacing(12)

        rev_label = QLabel("Revolutions to capture:")
        rev_label.setMinimumWidth(140)
        rev_row.addWidget(rev_label)

        self._revolutions_spin = QSpinBox()
        self._revolutions_spin.setRange(1, 10)
        self._revolutions_spin.setValue(2)
        self._revolutions_spin.setToolTip("Number of disk revolutions per track (1-10)")
        self._revolutions_spin.setMinimumWidth(70)
        rev_row.addWidget(self._revolutions_spin)

        rev_row.addStretch()
        flux_layout.addLayout(rev_row)

        self._normalize_check = QCheckBox("Normalize flux timing")
        self._normalize_check.setChecked(True)
        self._normalize_check.setToolTip("Adjust timing for consistency across captures")
        flux_layout.addWidget(self._normalize_check)

        flux_layout.addStretch()
        self._options_stack.addWidget(flux_options)

        # Page 2: Report options
        report_options = QWidget()
        report_layout = QVBoxLayout(report_options)
        report_layout.setContentsMargins(0, 0, 0, 0)
        report_layout.setSpacing(8)

        self._charts_check = QCheckBox("Include flux charts")
        self._charts_check.setChecked(True)
        self._charts_check.setToolTip("Include flux histogram and waveform charts")
        report_layout.addWidget(self._charts_check)

        self._sector_map_check = QCheckBox("Include sector map image")
        self._sector_map_check.setChecked(True)
        self._sector_map_check.setToolTip("Include visual sector map in report")
        report_layout.addWidget(self._sector_map_check)

        report_layout.addStretch()
        self._options_stack.addWidget(report_options)

        options_layout.addWidget(self._options_stack)
        layout.addWidget(self._options_group)

        # Compression group (for image formats only)
        self._compress_group = QGroupBox("Compression")
        compress_layout = QVBoxLayout(self._compress_group)
        compress_layout.setSpacing(8)

        self._compress_check = QCheckBox("Compress output")
        self._compress_check.setToolTip("Apply compression to output file")
        compress_layout.addWidget(self._compress_check)

        compress_row = QHBoxLayout()
        compress_row.setSpacing(12)
        compress_row.addSpacing(24)

        compress_label = QLabel("Compression type:")
        compress_label.setMinimumWidth(110)
        compress_row.addWidget(compress_label)

        self._compress_combo = QComboBox()
        self._compress_combo.addItem("None", "none")
        self._compress_combo.addItem("ZIP", "zip")
        self._compress_combo.addItem("GZIP", "gzip")
        self._compress_combo.setToolTip("Compression algorithm to use")
        self._compress_combo.setMinimumWidth(100)
        self._compress_combo.setEnabled(False)
        compress_row.addWidget(self._compress_combo)

        compress_row.addStretch()
        compress_layout.addLayout(compress_row)

        layout.addWidget(self._compress_group)

        # File Destination group
        dest_group = QGroupBox("File Destination")
        dest_layout = QVBoxLayout(dest_group)
        dest_layout.setSpacing(8)

        path_row = QHBoxLayout()
        path_row.setSpacing(12)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select output file...")
        self._path_edit.setToolTip("Full path for output file")
        path_row.addWidget(self._path_edit)

        self._browse_button = QPushButton("Browse...")
        self._browse_button.setMinimumWidth(80)
        self._browse_button.setToolTip("Choose output file location")
        path_row.addWidget(self._browse_button)

        dest_layout.addLayout(path_row)

        self._path_error = QLabel()
        self._path_error.setStyleSheet("color: #e74c3c; font-size: 9pt;")
        dest_layout.addWidget(self._path_error)

        layout.addWidget(dest_group)

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

        self._export_button = QPushButton("Export")
        self._export_button.setMinimumWidth(120)
        self._export_button.setMinimumHeight(32)
        self._export_button.clicked.connect(self._on_export_clicked)
        self._export_button.setDefault(True)
        self._export_button.setEnabled(False)
        button_layout.addWidget(self._export_button)

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
            QComboBox:disabled {
                background-color: #2d2d30;
                color: #6c6c6c;
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
            QLineEdit {
                background-color: #3a3d41;
                color: #cccccc;
                border: 1px solid #6c6c6c;
                border-radius: 4px;
                padding: 6px 8px;
            }
            QLineEdit:focus {
                border-color: #007acc;
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
        self._browse_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3d41;
                color: #ffffff;
                border: 1px solid #6c6c6c;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4e5157;
                border-color: #858585;
            }
            QPushButton:pressed {
                background-color: #2d2d30;
            }
        """)
        self._export_button.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #2d4a5e;
                color: #888888;
            }
        """)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self._type_group.buttonClicked.connect(self._on_type_changed)
        self._export_all_check.toggled.connect(self._on_export_all_toggled)
        self._compress_check.toggled.connect(self._on_compress_toggled)
        self._browse_button.clicked.connect(self._on_browse_clicked)
        self._path_edit.textChanged.connect(self._validate_path)
        self._start_spin.valueChanged.connect(self._validate_range)
        self._end_spin.valueChanged.connect(self._validate_range)

    def _on_type_changed(self) -> None:
        """Handle export type change."""
        self._update_options_visibility()
        self._update_filename()

    def _update_options_visibility(self) -> None:
        """Update visible options based on export type."""
        export_type = self._get_selected_type()
        is_report = export_type in (ExportType.PDF, ExportType.HTML)
        is_flux = export_type in (ExportType.SCP, ExportType.HFE)
        is_sector = export_type == ExportType.IMG

        # Track range only for images
        self._range_group.setEnabled(not is_report)

        # Compression only for images
        self._compress_group.setEnabled(not is_report)

        # Select appropriate options page
        if is_sector:
            self._options_stack.setCurrentIndex(0)
        elif is_flux:
            self._options_stack.setCurrentIndex(1)
        else:
            self._options_stack.setCurrentIndex(2)

    def _update_filename(self) -> None:
        """Update suggested filename based on export type."""
        current_path = self._path_edit.text().strip()

        # Get new extension
        export_type = self._get_selected_type()
        new_ext = EXPORT_EXTENSIONS[export_type]

        if current_path:
            # Update extension of existing path
            base, _ = os.path.splitext(current_path)
            new_path = base + new_ext
        else:
            # Suggest new filename
            new_path = self._default_filename + new_ext

        self._path_edit.setText(new_path)

    def _get_selected_type(self) -> ExportType:
        """Get the currently selected export type."""
        if self._scp_radio.isChecked():
            return ExportType.SCP
        elif self._hfe_radio.isChecked():
            return ExportType.HFE
        elif self._pdf_radio.isChecked():
            return ExportType.PDF
        elif self._html_radio.isChecked():
            return ExportType.HTML
        else:
            return ExportType.IMG

    def _on_export_all_toggled(self, checked: bool) -> None:
        """Handle export all tracks checkbox toggle."""
        self._start_spin.setEnabled(not checked)
        self._end_spin.setEnabled(not checked)

    def _on_compress_toggled(self, checked: bool) -> None:
        """Handle compress checkbox toggle."""
        self._compress_combo.setEnabled(checked)

    def _on_browse_clicked(self) -> None:
        """Handle Browse button click."""
        export_type = self._get_selected_type()
        filter_str = EXPORT_FILTERS[export_type]

        # Get current path or use default
        current_path = self._path_edit.text().strip()
        if not current_path:
            current_path = self._default_filename + EXPORT_EXTENSIONS[export_type]

        # Show save dialog
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Export As",
            current_path,
            filter_str
        )

        if path:
            self._path_edit.setText(path)
            self._validate_path()

    def _validate_path(self) -> None:
        """Validate the output path."""
        path = self._path_edit.text().strip()

        if not path:
            self._path_error.setText("Please select an output file")
            self._export_button.setEnabled(False)
            return

        # Check if directory exists
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            self._path_error.setText("Directory does not exist")
            self._export_button.setEnabled(False)
            return

        # Check if we can write to this location
        if directory:
            if not os.access(directory, os.W_OK):
                self._path_error.setText("Cannot write to this location")
                self._export_button.setEnabled(False)
                return

        self._path_error.setText("")
        self._export_button.setEnabled(True)

    def _validate_range(self) -> None:
        """Validate cylinder range."""
        start = self._start_spin.value()
        end = self._end_spin.value()

        if start > end:
            if self.sender() == self._start_spin:
                self._end_spin.setValue(start)
            else:
                self._start_spin.setValue(end)

    def _on_export_clicked(self) -> None:
        """Handle Export button click."""
        # Final path validation
        if not self._path_edit.text().strip():
            self._path_error.setText("Please select an output file")
            return

        self.accept()

    def get_config(self) -> ExportConfig:
        """
        Get the configured export settings.

        Returns:
            ExportConfig with current dialog settings
        """
        export_type = self._get_selected_type()

        return ExportConfig(
            export_type=export_type,
            start_cylinder=self._start_spin.value(),
            end_cylinder=self._end_spin.value(),
            export_all_tracks=self._export_all_check.isChecked(),
            include_bad_sectors=self._bad_sectors_check.isChecked(),
            pad_to_standard=self._pad_check.isChecked(),
            revolutions=self._revolutions_spin.value(),
            normalize_flux=self._normalize_check.isChecked(),
            include_charts=self._charts_check.isChecked(),
            include_sector_map=self._sector_map_check.isChecked(),
            compress=self._compress_check.isChecked(),
            compression_type=self._compress_combo.currentData() or 'none',
            output_path=self._path_edit.text().strip(),
        )

    def set_config(self, config: ExportConfig) -> None:
        """
        Set dialog values from a config.

        Args:
            config: ExportConfig to apply
        """
        # Set export type
        if config.export_type == ExportType.SCP:
            self._scp_radio.setChecked(True)
        elif config.export_type == ExportType.HFE:
            self._hfe_radio.setChecked(True)
        elif config.export_type == ExportType.PDF:
            self._pdf_radio.setChecked(True)
        elif config.export_type == ExportType.HTML:
            self._html_radio.setChecked(True)
        else:
            self._img_radio.setChecked(True)

        self._update_options_visibility()

        # Set track range
        self._export_all_check.setChecked(config.export_all_tracks)
        self._start_spin.setValue(config.start_cylinder)
        self._end_spin.setValue(config.end_cylinder)

        # Set sector options
        self._bad_sectors_check.setChecked(config.include_bad_sectors)
        self._pad_check.setChecked(config.pad_to_standard)

        # Set flux options
        self._revolutions_spin.setValue(config.revolutions)
        self._normalize_check.setChecked(config.normalize_flux)

        # Set report options
        self._charts_check.setChecked(config.include_charts)
        self._sector_map_check.setChecked(config.include_sector_map)

        # Set compression
        self._compress_check.setChecked(config.compress)
        for i in range(self._compress_combo.count()):
            if self._compress_combo.itemData(i) == config.compression_type:
                self._compress_combo.setCurrentIndex(i)
                break

        # Set path
        self._path_edit.setText(config.output_path)


def show_export_dialog(
    parent: Optional[QWidget] = None,
    default_filename: str = "disk_export"
) -> Optional[ExportConfig]:
    """
    Show the export configuration dialog.

    Args:
        parent: Optional parent widget
        default_filename: Default filename without extension

    Returns:
        ExportConfig if accepted, None if cancelled
    """
    dialog = ExportDialog(parent, default_filename)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_config()
    return None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'ExportDialog',
    'ExportConfig',
    'ExportType',
    'EXPORT_EXTENSIONS',
    'EXPORT_FILTERS',
    'show_export_dialog',
]
