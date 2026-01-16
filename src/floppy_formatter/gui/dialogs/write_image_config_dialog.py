"""
Write Image configuration dialog.

Allows users to select a disk format (IBM PC, Amiga, Atari ST, etc.)
and configure options for writing a blank formatted disk image.

Part of the Write Image feature.
"""

from dataclasses import dataclass
from typing import Optional, List

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QCheckBox,
    QComboBox,
    QFrame,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from floppy_formatter.imaging import (
    Platform,
    DiskFormatSpec,
    get_format_registry,
    get_image_manager,
)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class WriteImageConfig:
    """
    Configuration for a write image operation.

    Attributes:
        format_spec: The disk format specification to write
        verify_after_write: Whether to verify each track after writing
    """
    format_spec: Optional[DiskFormatSpec] = None
    verify_after_write: bool = True


# =============================================================================
# Dialog Class
# =============================================================================

class WriteImageConfigDialog(QDialog):
    """
    Dialog for configuring write image operations.

    Allows selection of platform and format from available bundled images,
    displays format details, and configures write options.

    Example:
        dialog = WriteImageConfigDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            # Use config.format_spec to write the image
    """

    def __init__(self, parent=None):
        """
        Initialize the dialog.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._config = WriteImageConfig()
        self._format_registry = get_format_registry()
        self._image_manager = get_image_manager()

        self._setup_ui()
        self._populate_platforms()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Write Disk Image")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Title
        title = QLabel("Write Blank Disk Image")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Write a blank formatted disk image to a physical floppy disk.\n"
            "Select the platform and format that matches your target system."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # Format selection group
        format_group = QGroupBox("Disk Format")
        format_layout = QVBoxLayout(format_group)

        # Platform selection
        platform_row = QHBoxLayout()
        platform_label = QLabel("Platform:")
        platform_label.setFixedWidth(80)
        self._platform_combo = QComboBox()
        self._platform_combo.setMinimumWidth(250)
        platform_row.addWidget(platform_label)
        platform_row.addWidget(self._platform_combo)
        platform_row.addStretch()
        format_layout.addLayout(platform_row)

        # Format selection
        format_row = QHBoxLayout()
        format_label = QLabel("Format:")
        format_label.setFixedWidth(80)
        self._format_combo = QComboBox()
        self._format_combo.setMinimumWidth(250)
        format_row.addWidget(format_label)
        format_row.addWidget(self._format_combo)
        format_row.addStretch()
        format_layout.addLayout(format_row)

        layout.addWidget(format_group)

        # Format details group
        details_group = QGroupBox("Format Details")
        details_layout = QVBoxLayout(details_group)

        # Details labels
        self._details_label = QLabel("Select a format to see details")
        self._details_label.setWordWrap(True)
        self._details_label.setStyleSheet("color: gray;")
        details_layout.addWidget(self._details_label)

        # Geometry info
        self._geometry_label = QLabel("")
        self._geometry_label.setStyleSheet("font-family: monospace;")
        details_layout.addWidget(self._geometry_label)

        # Encoding info
        self._encoding_label = QLabel("")
        details_layout.addWidget(self._encoding_label)

        layout.addWidget(details_group)

        # Options group
        options_group = QGroupBox("Write Options")
        options_layout = QVBoxLayout(options_group)

        self._verify_checkbox = QCheckBox("Verify after writing")
        self._verify_checkbox.setChecked(True)
        self._verify_checkbox.setToolTip(
            "Read back each track after writing to verify data integrity"
        )
        options_layout.addWidget(self._verify_checkbox)

        layout.addWidget(options_group)

        # Warning label
        self._warning_label = QLabel("")
        self._warning_label.setStyleSheet("color: orange;")
        self._warning_label.setWordWrap(True)
        self._warning_label.hide()
        layout.addWidget(self._warning_label)

        # Spacer
        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()

        self._ok_button = QPushButton("OK")
        self._ok_button.setDefault(True)
        self._ok_button.setEnabled(False)

        self._cancel_button = QPushButton("Cancel")

        button_layout.addStretch()
        button_layout.addWidget(self._ok_button)
        button_layout.addWidget(self._cancel_button)

        layout.addLayout(button_layout)

    def _populate_platforms(self) -> None:
        """Populate the platform dropdown with available platforms."""
        self._platform_combo.clear()

        # Get platforms that have available images
        available_platforms = self._image_manager.list_available_platforms()

        if not available_platforms:
            self._platform_combo.addItem("No formats available", None)
            return

        for platform in available_platforms:
            self._platform_combo.addItem(platform.value, platform)

        # Select first platform and populate formats
        if available_platforms:
            self._populate_formats(available_platforms[0])

    def _populate_formats(self, platform: Platform) -> None:
        """
        Populate the format dropdown for a platform.

        Args:
            platform: Platform to get formats for
        """
        self._format_combo.clear()

        formats = self._image_manager.get_available_formats_for_platform(platform)

        if not formats:
            self._format_combo.addItem("No formats available", None)
            self._ok_button.setEnabled(False)
            return

        for fmt in formats:
            self._format_combo.addItem(fmt.display_name, fmt)

        # Select first format
        if formats:
            self._update_format_details(formats[0])
            self._ok_button.setEnabled(True)

    def _update_format_details(self, fmt: Optional[DiskFormatSpec]) -> None:
        """
        Update the format details display.

        Args:
            fmt: Format specification to display
        """
        if fmt is None:
            self._details_label.setText("Select a format to see details")
            self._details_label.setStyleSheet("color: gray;")
            self._geometry_label.setText("")
            self._encoding_label.setText("")
            self._warning_label.hide()
            self._config.format_spec = None
            return

        # Update details
        self._details_label.setText(fmt.description)
        self._details_label.setStyleSheet("")

        # Geometry
        self._geometry_label.setText(
            f"Geometry: {fmt.cylinders} cylinders x {fmt.heads} heads x "
            f"{fmt.sectors_per_track} sectors x {fmt.bytes_per_sector} bytes\n"
            f"Capacity: {fmt.capacity_kb} KB ({fmt.total_sectors} total sectors)"
        )

        # Encoding
        self._encoding_label.setText(
            f"Encoding: {fmt.encoding.value}, {fmt.density.value}, "
            f"{fmt.data_rate_kbps} kbps"
        )

        # Check for warnings
        supported, reason = self._format_registry.is_format_supported(fmt)
        if not supported:
            self._warning_label.setText(f"Warning: {reason}")
            self._warning_label.show()
        else:
            self._warning_label.hide()

        # Store selected format
        self._config.format_spec = fmt

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self._platform_combo.currentIndexChanged.connect(self._on_platform_changed)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        self._verify_checkbox.stateChanged.connect(self._on_verify_changed)
        self._ok_button.clicked.connect(self.accept)
        self._cancel_button.clicked.connect(self.reject)

    def _on_platform_changed(self, index: int) -> None:
        """Handle platform selection change."""
        platform = self._platform_combo.currentData()
        if platform is not None:
            self._populate_formats(platform)

    def _on_format_changed(self, index: int) -> None:
        """Handle format selection change."""
        fmt = self._format_combo.currentData()
        self._update_format_details(fmt)

    def _on_verify_changed(self, state: int) -> None:
        """Handle verify checkbox change."""
        self._config.verify_after_write = state == Qt.CheckState.Checked.value

    def get_config(self) -> WriteImageConfig:
        """
        Get the current configuration.

        Returns:
            WriteImageConfig with selected options
        """
        return self._config

    def accept(self) -> None:
        """Handle dialog acceptance."""
        if self._config.format_spec is None:
            QMessageBox.warning(
                self,
                "No Format Selected",
                "Please select a disk format before continuing."
            )
            return

        # Confirm destructive operation
        result = QMessageBox.warning(
            self,
            "Confirm Write",
            f"This will write a blank {self._config.format_spec.name} "
            f"({self._config.format_spec.platform.value}) disk image.\n\n"
            "All existing data on the disk will be erased!\n\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if result == QMessageBox.StandardButton.Yes:
            super().accept()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'WriteImageConfigDialog',
    'WriteImageConfig',
]
