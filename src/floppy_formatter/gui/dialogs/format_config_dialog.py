"""
Format configuration dialog for Greaseweazle operations.

Provides user-configurable settings for disk formatting including
format type, fill pattern, and verification options.

Part of Phase 10: Operation Dialogs & Configurations
"""

import re
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
    QComboBox,
    QLineEdit,
    QFrame,
)
from PyQt6.QtGui import QFont


# =============================================================================
# Enums and Data Classes
# =============================================================================

class FormatType(Enum):
    """Format type determining the formatting approach."""
    STANDARD = auto()           # Normal format with fill pattern
    LOW_LEVEL_REFRESH = auto()  # Degauss + multiple pattern writes
    SECURE_ERASE = auto()       # Multiple overwrites for data destruction


# Standard fill pattern values
PATTERN_ZERO = 0x00
PATTERN_ONE = 0xFF
PATTERN_E5 = 0xE5
PATTERN_AA = 0xAA
PATTERN_55 = 0x55


@dataclass
class FormatConfig:
    """
    Configuration for a format operation.

    Attributes:
        format_type: Type of format (STANDARD, LOW_LEVEL_REFRESH, SECURE_ERASE)
        fill_pattern: Byte value to fill sectors with (0x00-0xFF)
        verify: Whether to verify after formatting
    """
    format_type: FormatType = FormatType.STANDARD
    fill_pattern: int = PATTERN_E5
    verify: bool = True


# =============================================================================
# Format Config Dialog
# =============================================================================

class FormatConfigDialog(QDialog):
    """
    Dialog for configuring disk format operations.

    Provides options for:
    - Format type (Standard/Low-Level Refresh/Secure Erase)
    - Fill pattern selection
    - Verification after format

    Example:
        dialog = FormatConfigDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            # Start format with config
    """

    # Pattern options for combobox
    PATTERN_OPTIONS = [
        ("Zeros (0x00)", PATTERN_ZERO),
        ("Ones (0xFF)", PATTERN_ONE),
        ("Standard (0xE5)", PATTERN_E5),
        ("Alternating (0xAA)", PATTERN_AA),
        ("Inverse Alt (0x55)", PATTERN_55),
        ("Custom...", -1),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize format config dialog.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._custom_pattern: int = PATTERN_E5
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the dialog user interface."""
        self.setWindowTitle("Format Configuration")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setMinimumHeight(520)

        # Apply dark theme styling
        self._apply_dialog_style()

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_label = QLabel("Format Configuration")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # Format Type group
        type_group = QGroupBox("Format Type")
        type_layout = QVBoxLayout(type_group)
        type_layout.setSpacing(8)

        self._type_group = QButtonGroup(self)

        # Standard format
        self._standard_radio = QRadioButton("Standard Format")
        self._standard_radio.setToolTip("Normal format with specified fill pattern")
        self._standard_radio.setChecked(True)
        self._type_group.addButton(self._standard_radio, 0)
        type_layout.addWidget(self._standard_radio)

        standard_desc = QLabel(
            "Normal format operation. Erases and writes fill pattern to all sectors."
        )
        standard_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        standard_desc.setWordWrap(True)
        type_layout.addWidget(standard_desc)

        # Low-level refresh
        self._refresh_radio = QRadioButton("Low-Level Refresh")
        self._refresh_radio.setToolTip("Degauss + multiple pattern writes to refresh media")
        self._type_group.addButton(self._refresh_radio, 1)
        type_layout.addWidget(self._refresh_radio)

        refresh_desc = QLabel(
            "DC erase followed by multiple pattern writes (0x00, 0xFF, 0xAA, 0x55). "
            "Refreshes weak magnetic areas."
        )
        refresh_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        refresh_desc.setWordWrap(True)
        type_layout.addWidget(refresh_desc)

        # Secure erase
        self._secure_radio = QRadioButton("Secure Erase")
        self._secure_radio.setToolTip("Multiple overwrites for data destruction")
        self._type_group.addButton(self._secure_radio, 2)
        type_layout.addWidget(self._secure_radio)

        secure_desc = QLabel(
            "Multiple overwrite passes with different patterns for secure data destruction."
        )
        secure_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        secure_desc.setWordWrap(True)
        type_layout.addWidget(secure_desc)

        secure_warn = QLabel("This will make data unrecoverable.")
        secure_warn.setStyleSheet(
            "color: #e74c3c; font-size: 9pt; font-weight: bold; margin-left: 24px;"
        )
        type_layout.addWidget(secure_warn)

        layout.addWidget(type_group)

        # Fill Pattern group
        pattern_group = QGroupBox("Fill Pattern")
        pattern_layout = QVBoxLayout(pattern_group)
        pattern_layout.setSpacing(8)

        pattern_row = QHBoxLayout()
        pattern_row.setSpacing(12)

        pattern_label = QLabel("Pattern:")
        pattern_label.setMinimumWidth(60)
        pattern_row.addWidget(pattern_label)

        self._pattern_combo = QComboBox()
        self._pattern_combo.setToolTip("Byte value to fill each sector with")
        for name, _ in self.PATTERN_OPTIONS:
            self._pattern_combo.addItem(name)
        self._pattern_combo.setCurrentIndex(2)  # Standard (0xE5)
        self._pattern_combo.setMinimumWidth(150)
        pattern_row.addWidget(self._pattern_combo)

        self._custom_edit = QLineEdit()
        self._custom_edit.setPlaceholderText("00-FF")
        self._custom_edit.setToolTip("Enter custom hex value (00-FF)")
        self._custom_edit.setMaximumWidth(60)
        self._custom_edit.setEnabled(False)
        pattern_row.addWidget(self._custom_edit)

        self._custom_error = QLabel()
        self._custom_error.setStyleSheet("color: #e74c3c; font-size: 9pt;")
        pattern_row.addWidget(self._custom_error)

        pattern_row.addStretch()
        pattern_layout.addLayout(pattern_row)

        pattern_note = QLabel(
            "The fill pattern is written to all data sectors. Standard (0xE5) is the DOS default."
        )
        pattern_note.setStyleSheet("color: #858585; font-size: 9pt;")
        pattern_note.setWordWrap(True)
        pattern_layout.addWidget(pattern_note)

        layout.addWidget(pattern_group)

        # Verification group
        verify_group = QGroupBox("Verification")
        verify_layout = QVBoxLayout(verify_group)
        verify_layout.setSpacing(8)

        self._verify_check = QCheckBox("Verify after format")
        self._verify_check.setChecked(True)
        self._verify_check.setToolTip("Read back all sectors to confirm successful format")
        verify_layout.addWidget(self._verify_check)

        verify_desc = QLabel(
            "Reads back all sectors to confirm they were formatted correctly. Recommended."
        )
        verify_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        verify_desc.setWordWrap(True)
        verify_layout.addWidget(verify_desc)

        layout.addWidget(verify_group)

        # Warning section
        warning_frame = QFrame()
        warning_frame.setStyleSheet("""
            QFrame {
                background-color: #3d2a1a;
                border: 1px solid #e74c3c;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        warning_layout = QHBoxLayout(warning_frame)
        warning_layout.setContentsMargins(12, 8, 12, 8)

        warning_icon = QLabel("\u26a0")  # Warning triangle
        warning_icon.setStyleSheet("font-size: 18pt; color: #e74c3c;")
        warning_layout.addWidget(warning_icon)

        warning_text = QLabel("This will ERASE ALL DATA on the disk!")
        warning_text.setStyleSheet("color: #f39c12; font-weight: bold; font-size: 11pt;")
        warning_layout.addWidget(warning_text)
        warning_layout.addStretch()

        layout.addWidget(warning_frame)

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

        self._format_button = QPushButton("Start Format")
        self._format_button.setMinimumWidth(120)
        self._format_button.setMinimumHeight(32)
        self._format_button.clicked.connect(self._on_format_clicked)
        self._format_button.setDefault(True)
        button_layout.addWidget(self._format_button)

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
                padding: 4px 8px;
            }
            QLineEdit:disabled {
                background-color: #2d2d30;
                color: #6c6c6c;
                border-color: #3a3d41;
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
        # Destructive action - use warning color
        self._format_button.setStyleSheet("""
            QPushButton {
                background-color: #c0392b;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e74c3c;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
            QPushButton:disabled {
                background-color: #5a3d3a;
                color: #888888;
            }
        """)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self._pattern_combo.currentIndexChanged.connect(self._on_pattern_changed)
        self._custom_edit.textChanged.connect(self._validate_custom_pattern)

    def _on_pattern_changed(self, index: int) -> None:
        """Handle pattern combobox change."""
        is_custom = (index == len(self.PATTERN_OPTIONS) - 1)
        self._custom_edit.setEnabled(is_custom)
        if is_custom:
            self._custom_edit.setFocus()
            self._validate_custom_pattern()
        else:
            self._custom_error.setText("")
            self._format_button.setEnabled(True)

    def _validate_custom_pattern(self) -> None:
        """Validate custom pattern input."""
        text = self._custom_edit.text().strip()

        if not text:
            self._custom_error.setText("Enter a hex value")
            self._format_button.setEnabled(False)
            return

        # Try to parse as hex
        if not re.match(r'^[0-9a-fA-F]{1,2}$', text):
            self._custom_error.setText("Invalid hex")
            self._format_button.setEnabled(False)
            return

        value = int(text, 16)
        if value < 0 or value > 255:
            self._custom_error.setText("Out of range")
            self._format_button.setEnabled(False)
            return

        self._custom_pattern = value
        self._custom_error.setText("")
        self._format_button.setEnabled(True)

    def _on_format_clicked(self) -> None:
        """Handle Start Format button click."""
        # Final validation for custom pattern
        if self._pattern_combo.currentIndex() == len(self.PATTERN_OPTIONS) - 1:
            if not self._custom_edit.text().strip():
                self._custom_error.setText("Enter a hex value")
                return

        self.accept()

    def get_config(self) -> FormatConfig:
        """
        Get the configured format settings.

        Returns:
            FormatConfig with current dialog settings
        """
        # Determine format type
        if self._refresh_radio.isChecked():
            format_type = FormatType.LOW_LEVEL_REFRESH
        elif self._secure_radio.isChecked():
            format_type = FormatType.SECURE_ERASE
        else:
            format_type = FormatType.STANDARD

        # Determine fill pattern
        index = self._pattern_combo.currentIndex()
        if index < len(self.PATTERN_OPTIONS) - 1:
            fill_pattern = self.PATTERN_OPTIONS[index][1]
        else:
            fill_pattern = self._custom_pattern

        return FormatConfig(
            format_type=format_type,
            fill_pattern=fill_pattern,
            verify=self._verify_check.isChecked(),
        )

    def set_config(self, config: FormatConfig) -> None:
        """
        Set dialog values from a config.

        Args:
            config: FormatConfig to apply
        """
        # Set format type
        if config.format_type == FormatType.LOW_LEVEL_REFRESH:
            self._refresh_radio.setChecked(True)
        elif config.format_type == FormatType.SECURE_ERASE:
            self._secure_radio.setChecked(True)
        else:
            self._standard_radio.setChecked(True)

        # Set fill pattern
        found = False
        for i, (_, value) in enumerate(self.PATTERN_OPTIONS[:-1]):
            if value == config.fill_pattern:
                self._pattern_combo.setCurrentIndex(i)
                found = True
                break

        if not found:
            self._pattern_combo.setCurrentIndex(len(self.PATTERN_OPTIONS) - 1)
            self._custom_pattern = config.fill_pattern
            self._custom_edit.setText(f"{config.fill_pattern:02X}")

        self._verify_check.setChecked(config.verify)


def show_format_config_dialog(parent: Optional[QWidget] = None) -> Optional[FormatConfig]:
    """
    Show the format configuration dialog.

    Args:
        parent: Optional parent widget

    Returns:
        FormatConfig if accepted, None if cancelled
    """
    dialog = FormatConfigDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_config()
    return None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'FormatConfigDialog',
    'FormatConfig',
    'FormatType',
    'PATTERN_ZERO',
    'PATTERN_ONE',
    'PATTERN_E5',
    'PATTERN_AA',
    'PATTERN_55',
    'show_format_config_dialog',
]
