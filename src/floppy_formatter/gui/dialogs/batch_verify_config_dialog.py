"""
Batch verification configuration dialog.

Allows users to configure batch verification of multiple floppy disks,
including brand selection, disk count, optional serial numbers, and
analysis depth settings.

Part of Phase 11: Batch Operations
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

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
    QLineEdit,
    QScrollArea,
)
from PyQt6.QtGui import QFont


# =============================================================================
# Enums and Data Classes
# =============================================================================

class FloppyBrand(Enum):
    """Common floppy disk brands."""
    SONY = "Sony"
    TDK = "TDK"
    MAXELL = "Maxell"
    FUJIFILM = "Fujifilm"
    MEMOREX = "Memorex"
    IMATION = "Imation"
    VERBATIM = "Verbatim"
    THREE_M = "3M"
    GENERIC = "Generic/Unknown"
    OTHER = "Other"


@dataclass
class FloppyDiskInfo:
    """
    Information about a single floppy disk in the batch.

    Attributes:
        index: Position in batch (0-based)
        serial_number: User-entered serial (may be None)
        brand: Brand of this disk
        label: Optional user label/description
    """
    index: int
    serial_number: Optional[str] = None
    brand: FloppyBrand = FloppyBrand.GENERIC
    label: str = ""


@dataclass
class BatchVerifyConfig:
    """
    Configuration for batch verification operation.

    Attributes:
        batch_name: Name/description for the batch
        brand: Default brand for the batch
        disk_count: Number of disks to verify
        disks: List of disk info objects
        use_serial_numbers: Whether serials are being used
        analysis_depth: Analysis depth (Quick/Standard/Thorough/Forensic)
    """
    batch_name: str = "Batch Verification"
    brand: FloppyBrand = FloppyBrand.GENERIC
    disk_count: int = 1
    disks: List[FloppyDiskInfo] = field(default_factory=list)
    use_serial_numbers: bool = False
    analysis_depth: str = "Standard"


# =============================================================================
# Batch Verify Config Dialog
# =============================================================================

class BatchVerifyConfigDialog(QDialog):
    """
    Dialog for configuring batch disk verification.

    Provides options for:
    - Batch name and brand selection
    - Number of disks to verify
    - Optional serial number entry for each disk
    - Analysis depth selection

    Example:
        dialog = BatchVerifyConfigDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            # Start batch verification with config
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize batch verify config dialog.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._serial_inputs: List[QLineEdit] = []
        self._setup_ui()
        self._connect_signals()
        self._update_serial_inputs()

    def _setup_ui(self) -> None:
        """Set up the dialog user interface."""
        self.setWindowTitle("Batch Verification Configuration")
        self.setModal(True)
        self.setMinimumWidth(550)
        self.setMinimumHeight(600)

        # Apply dark theme styling
        self._apply_dialog_style()

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_label = QLabel("Batch Verification Configuration")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # Batch Information group
        batch_group = QGroupBox("Batch Information")
        batch_layout = QVBoxLayout(batch_group)
        batch_layout.setSpacing(12)

        # Batch name
        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        name_label = QLabel("Batch Name:")
        name_label.setMinimumWidth(100)
        name_row.addWidget(name_label)

        self._batch_name_edit = QLineEdit()
        self._batch_name_edit.setPlaceholderText("Enter batch name or description")
        self._batch_name_edit.setText("Batch Verification")
        name_row.addWidget(self._batch_name_edit)
        batch_layout.addLayout(name_row)

        # Brand selection
        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        brand_label = QLabel("Media Brand:")
        brand_label.setMinimumWidth(100)
        brand_row.addWidget(brand_label)

        self._brand_combo = QComboBox()
        for brand in FloppyBrand:
            self._brand_combo.addItem(brand.value, brand)
        self._brand_combo.setCurrentIndex(
            list(FloppyBrand).index(FloppyBrand.GENERIC)
        )
        self._brand_combo.setMinimumWidth(150)
        brand_row.addWidget(self._brand_combo)
        brand_row.addStretch()
        batch_layout.addLayout(brand_row)

        # Disk count
        count_row = QHBoxLayout()
        count_row.setSpacing(12)
        count_label = QLabel("Number of Disks:")
        count_label.setMinimumWidth(100)
        count_row.addWidget(count_label)

        self._disk_count_spin = QSpinBox()
        self._disk_count_spin.setRange(1, 50)
        self._disk_count_spin.setValue(1)
        self._disk_count_spin.setMinimumWidth(80)
        self._disk_count_spin.setToolTip("Number of floppy disks to verify (1-50)")
        count_row.addWidget(self._disk_count_spin)
        count_row.addStretch()
        batch_layout.addLayout(count_row)

        layout.addWidget(batch_group)

        # Serial Numbers group
        serial_group = QGroupBox("Serial Numbers (Optional)")
        serial_layout = QVBoxLayout(serial_group)
        serial_layout.setSpacing(8)

        self._use_serials_check = QCheckBox("Use serial numbers for identification")
        self._use_serials_check.setToolTip(
            "Enable to enter serial numbers for each disk. "
            "Disks will be prompted by serial number during verification."
        )
        serial_layout.addWidget(self._use_serials_check)

        serial_desc = QLabel(
            "If enabled, you can enter the serial number for each disk. "
            "During verification, you'll be prompted to insert each disk by its serial number."
        )
        serial_desc.setStyleSheet("color: #858585; font-size: 9pt;")
        serial_desc.setWordWrap(True)
        serial_layout.addWidget(serial_desc)

        # Scroll area for serial number inputs
        self._serial_scroll = QScrollArea()
        self._serial_scroll.setWidgetResizable(True)
        self._serial_scroll.setMaximumHeight(200)
        self._serial_scroll.setMinimumHeight(100)
        self._serial_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #3a3d41;
                border-radius: 4px;
                background-color: #252526;
            }
        """)

        self._serial_container = QWidget()
        self._serial_container_layout = QVBoxLayout(self._serial_container)
        self._serial_container_layout.setContentsMargins(8, 8, 8, 8)
        self._serial_container_layout.setSpacing(6)
        self._serial_container_layout.addStretch()

        self._serial_scroll.setWidget(self._serial_container)
        self._serial_scroll.setEnabled(False)
        serial_layout.addWidget(self._serial_scroll)

        layout.addWidget(serial_group)

        # Analysis Settings group
        analysis_group = QGroupBox("Analysis Settings")
        analysis_layout = QVBoxLayout(analysis_group)
        analysis_layout.setSpacing(8)

        depth_label = QLabel("Analysis Depth:")
        analysis_layout.addWidget(depth_label)

        self._depth_group = QButtonGroup(self)

        # Quick
        self._quick_radio = QRadioButton("Quick")
        self._quick_radio.setToolTip("Fast verification on sample tracks only")
        self._depth_group.addButton(self._quick_radio, 0)
        analysis_layout.addWidget(self._quick_radio)

        quick_desc = QLabel("Fast check on sample tracks. Good for initial screening.")
        quick_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        quick_desc.setWordWrap(True)
        analysis_layout.addWidget(quick_desc)

        # Standard
        self._standard_radio = QRadioButton("Standard")
        self._standard_radio.setToolTip("Full verification of all tracks")
        self._standard_radio.setChecked(True)
        self._depth_group.addButton(self._standard_radio, 1)
        analysis_layout.addWidget(self._standard_radio)

        standard_desc = QLabel("Complete verification of all tracks. Recommended for most cases.")
        standard_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        standard_desc.setWordWrap(True)
        analysis_layout.addWidget(standard_desc)

        # Thorough
        self._thorough_radio = QRadioButton("Thorough")
        self._thorough_radio.setToolTip("Extended verification with multiple passes")
        self._depth_group.addButton(self._thorough_radio, 2)
        analysis_layout.addWidget(self._thorough_radio)

        thorough_desc = QLabel("Multiple passes per track for detailed quality assessment.")
        thorough_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        thorough_desc.setWordWrap(True)
        analysis_layout.addWidget(thorough_desc)

        # Forensic
        self._forensic_radio = QRadioButton("Forensic")
        self._forensic_radio.setToolTip("Deep analysis including copy protection detection")
        self._depth_group.addButton(self._forensic_radio, 3)
        analysis_layout.addWidget(self._forensic_radio)

        forensic_desc = QLabel("Comprehensive analysis including forensic examination.")
        forensic_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        forensic_desc.setWordWrap(True)
        analysis_layout.addWidget(forensic_desc)

        layout.addWidget(analysis_group)

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

        self._start_button = QPushButton("Start Batch")
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
            QLineEdit:disabled {
                background-color: #2d2d30;
                color: #6c6c6c;
                border-color: #3a3d41;
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
        self._disk_count_spin.valueChanged.connect(self._update_serial_inputs)
        self._use_serials_check.toggled.connect(self._on_use_serials_toggled)

    def _on_use_serials_toggled(self, checked: bool) -> None:
        """Handle use serial numbers checkbox toggle."""
        self._serial_scroll.setEnabled(checked)
        for line_edit in self._serial_inputs:
            line_edit.setEnabled(checked)

    def _update_serial_inputs(self) -> None:
        """Update the serial number input fields based on disk count."""
        count = self._disk_count_spin.value()
        current_count = len(self._serial_inputs)

        # Remove excess inputs
        while len(self._serial_inputs) > count:
            line_edit = self._serial_inputs.pop()
            row_widget = line_edit.parent()
            if row_widget:
                row_widget.deleteLater()

        # Add new inputs
        for i in range(current_count, count):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            label = QLabel(f"Disk {i + 1}:")
            label.setMinimumWidth(60)
            label.setStyleSheet("color: #cccccc;")
            row_layout.addWidget(label)

            line_edit = QLineEdit()
            line_edit.setPlaceholderText("Serial number (optional)")
            line_edit.setEnabled(self._use_serials_check.isChecked())
            row_layout.addWidget(line_edit)

            self._serial_inputs.append(line_edit)

            # Insert before the stretch
            self._serial_container_layout.insertWidget(
                self._serial_container_layout.count() - 1, row_widget
            )

    def _on_start_clicked(self) -> None:
        """Handle Start Batch button click."""
        # Validate batch name
        if not self._batch_name_edit.text().strip():
            self._batch_name_edit.setFocus()
            return

        self.accept()

    def get_config(self) -> BatchVerifyConfig:
        """
        Get the configured batch verification settings.

        Returns:
            BatchVerifyConfig with current dialog settings
        """
        # Determine depth
        if self._quick_radio.isChecked():
            depth = "Quick"
        elif self._thorough_radio.isChecked():
            depth = "Thorough"
        elif self._forensic_radio.isChecked():
            depth = "Forensic"
        else:
            depth = "Standard"

        # Get brand
        brand = self._brand_combo.currentData()

        # Build disk info list
        disk_count = self._disk_count_spin.value()
        disks = []
        for i in range(disk_count):
            serial = None
            if self._use_serials_check.isChecked() and i < len(self._serial_inputs):
                serial_text = self._serial_inputs[i].text().strip()
                if serial_text:
                    serial = serial_text

            disks.append(FloppyDiskInfo(
                index=i,
                serial_number=serial,
                brand=brand,
            ))

        return BatchVerifyConfig(
            batch_name=self._batch_name_edit.text().strip(),
            brand=brand,
            disk_count=disk_count,
            disks=disks,
            use_serial_numbers=self._use_serials_check.isChecked(),
            analysis_depth=depth,
        )

    def set_config(self, config: BatchVerifyConfig) -> None:
        """
        Set dialog values from a config.

        Args:
            config: BatchVerifyConfig to apply
        """
        self._batch_name_edit.setText(config.batch_name)

        # Set brand
        for i in range(self._brand_combo.count()):
            if self._brand_combo.itemData(i) == config.brand:
                self._brand_combo.setCurrentIndex(i)
                break

        # Set disk count
        self._disk_count_spin.setValue(config.disk_count)

        # Set serial numbers
        self._use_serials_check.setChecked(config.use_serial_numbers)
        for i, disk_info in enumerate(config.disks):
            if i < len(self._serial_inputs) and disk_info.serial_number:
                self._serial_inputs[i].setText(disk_info.serial_number)

        # Set depth
        if config.analysis_depth == "Quick":
            self._quick_radio.setChecked(True)
        elif config.analysis_depth == "Thorough":
            self._thorough_radio.setChecked(True)
        elif config.analysis_depth == "Forensic":
            self._forensic_radio.setChecked(True)
        else:
            self._standard_radio.setChecked(True)


def show_batch_verify_config_dialog(
    parent: Optional[QWidget] = None
) -> Optional[BatchVerifyConfig]:
    """
    Show the batch verification configuration dialog.

    Args:
        parent: Optional parent widget

    Returns:
        BatchVerifyConfig if accepted, None if cancelled
    """
    dialog = BatchVerifyConfigDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_config()
    return None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'BatchVerifyConfigDialog',
    'BatchVerifyConfig',
    'FloppyBrand',
    'FloppyDiskInfo',
    'show_batch_verify_config_dialog',
]
