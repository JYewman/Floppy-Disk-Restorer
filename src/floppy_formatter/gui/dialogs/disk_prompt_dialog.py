"""
Disk prompt dialog for batch verification.

Modal dialog that prompts the user to insert a specific disk
during batch verification operations.

Part of Phase 11: Batch Operations
"""

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

from floppy_formatter.gui.dialogs.batch_verify_config_dialog import FloppyDiskInfo


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DiskPromptResult:
    """
    Result from disk prompt dialog.

    Attributes:
        confirmed: User confirmed disk is inserted
        skip: User chose to skip this disk
        cancel_batch: User wants to cancel entire batch
    """
    confirmed: bool = False
    skip: bool = False
    cancel_batch: bool = False


# =============================================================================
# Disk Prompt Dialog
# =============================================================================

class DiskPromptDialog(QDialog):
    """
    Dialog prompting user to insert a specific disk.

    Displays which disk number to insert, along with serial number
    and brand information if available. Provides options to:
    - Confirm disk is ready
    - Skip this disk
    - Cancel the entire batch

    Example:
        dialog = DiskPromptDialog(
            parent,
            disk_info=disk_info,
            current_index=2,
            total_count=5,
        )
        result = dialog.exec_and_get_result()
        if result.confirmed:
            # Proceed with verification
        elif result.skip:
            # Skip this disk
        elif result.cancel_batch:
            # Cancel entire batch
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        disk_info: FloppyDiskInfo,
        current_index: int,
        total_count: int,
    ):
        """
        Initialize disk prompt dialog.

        Args:
            parent: Parent widget
            disk_info: Information about the disk to insert
            current_index: Zero-based index of current disk
            total_count: Total number of disks in batch
        """
        super().__init__(parent)
        self._disk_info = disk_info
        self._current_index = current_index
        self._total_count = total_count
        self._result = DiskPromptResult()

        self._setup_ui()
        self._setup_shortcuts()

    def _setup_ui(self) -> None:
        """Set up the dialog user interface."""
        self.setWindowTitle("Insert Disk")
        self.setModal(True)
        self.setFixedWidth(400)
        self.setMinimumHeight(280)

        # Apply dark theme styling
        self._apply_dialog_style()

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(16)

        # Disk icon placeholder (using text for now)
        icon_label = QLabel("\U0001F4BE")  # Floppy disk emoji
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_font = QFont()
        icon_font.setPointSize(48)
        icon_label.setFont(icon_font)
        layout.addWidget(icon_label)

        # Main instruction
        disk_num = self._current_index + 1
        instruction = QLabel(f"Please insert disk {disk_num} of {self._total_count}")
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction_font = QFont()
        instruction_font.setPointSize(14)
        instruction_font.setBold(True)
        instruction.setFont(instruction_font)
        layout.addWidget(instruction)

        # Disk details
        details_frame = QFrame()
        details_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        details_layout = QVBoxLayout(details_frame)
        details_layout.setSpacing(6)

        # Serial number (if available)
        if self._disk_info.serial_number:
            serial_row = QHBoxLayout()
            serial_label = QLabel("Serial:")
            serial_label.setStyleSheet("color: #858585; font-weight: bold;")
            serial_label.setMinimumWidth(60)
            serial_row.addWidget(serial_label)

            serial_value = QLabel(self._disk_info.serial_number)
            serial_value.setStyleSheet("color: #4ec9b0; font-size: 12pt; font-weight: bold;")
            serial_row.addWidget(serial_value)
            serial_row.addStretch()
            details_layout.addLayout(serial_row)

        # Brand
        brand_row = QHBoxLayout()
        brand_label = QLabel("Brand:")
        brand_label.setStyleSheet("color: #858585; font-weight: bold;")
        brand_label.setMinimumWidth(60)
        brand_row.addWidget(brand_label)

        brand_value = QLabel(self._disk_info.brand.value)
        brand_value.setStyleSheet("color: #cccccc;")
        brand_row.addWidget(brand_value)
        brand_row.addStretch()
        details_layout.addLayout(brand_row)

        layout.addWidget(details_frame)

        # Instruction note
        note = QLabel("Ensure the disk is properly inserted and the drive is ready.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet("color: #858585; font-size: 9pt;")
        note.setWordWrap(True)
        layout.addWidget(note)

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

        self._skip_button = QPushButton("Skip Disk")
        self._skip_button.setMinimumWidth(90)
        self._skip_button.setMinimumHeight(32)
        self._skip_button.setToolTip("Skip this disk and continue to next (S)")
        self._skip_button.clicked.connect(self._on_skip_clicked)
        button_layout.addWidget(self._skip_button)

        self._cancel_button = QPushButton("Cancel Batch")
        self._cancel_button.setMinimumWidth(100)
        self._cancel_button.setMinimumHeight(32)
        self._cancel_button.setToolTip("Cancel the entire batch operation (Esc)")
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(self._cancel_button)

        button_layout.addStretch()

        self._ready_button = QPushButton("Disk Ready")
        self._ready_button.setMinimumWidth(110)
        self._ready_button.setMinimumHeight(32)
        self._ready_button.setToolTip("Confirm disk is inserted and ready (Enter)")
        self._ready_button.clicked.connect(self._on_ready_clicked)
        self._ready_button.setDefault(True)
        self._ready_button.setFocus()
        button_layout.addWidget(self._ready_button)

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
        """)

    def _apply_button_styles(self) -> None:
        """Apply button styling."""
        # Skip button - neutral
        self._skip_button.setStyleSheet("""
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

        # Cancel button - warning color
        self._cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #5a3d3d;
                color: #ffffff;
                border: 1px solid #8b5a5a;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6b4a4a;
                border-color: #a06b6b;
            }
            QPushButton:pressed {
                background-color: #4a2d2d;
            }
        """)

        # Ready button - primary action
        self._ready_button.setStyleSheet("""
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

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        # S key for Skip
        skip_shortcut = QShortcut(QKeySequence("S"), self)
        skip_shortcut.activated.connect(self._on_skip_clicked)

        # Escape for Cancel
        cancel_shortcut = QShortcut(QKeySequence("Escape"), self)
        cancel_shortcut.activated.connect(self._on_cancel_clicked)

        # Enter is already handled by default button

    def _on_skip_clicked(self) -> None:
        """Handle Skip Disk button click."""
        self._result = DiskPromptResult(skip=True)
        self.accept()

    def _on_cancel_clicked(self) -> None:
        """Handle Cancel Batch button click."""
        self._result = DiskPromptResult(cancel_batch=True)
        self.reject()

    def _on_ready_clicked(self) -> None:
        """Handle Disk Ready button click."""
        self._result = DiskPromptResult(confirmed=True)
        self.accept()

    def exec_and_get_result(self) -> DiskPromptResult:
        """
        Execute the dialog and return the result.

        Returns:
            DiskPromptResult with user's choice
        """
        self.exec()
        return self._result

    def get_result(self) -> DiskPromptResult:
        """
        Get the dialog result.

        Returns:
            DiskPromptResult with user's choice
        """
        return self._result


def show_disk_prompt_dialog(
    parent: Optional[QWidget],
    disk_info: FloppyDiskInfo,
    current_index: int,
    total_count: int,
) -> DiskPromptResult:
    """
    Show the disk prompt dialog.

    Args:
        parent: Parent widget
        disk_info: Information about the disk to insert
        current_index: Zero-based index of current disk
        total_count: Total number of disks in batch

    Returns:
        DiskPromptResult with user's choice
    """
    dialog = DiskPromptDialog(parent, disk_info, current_index, total_count)
    return dialog.exec_and_get_result()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'DiskPromptDialog',
    'DiskPromptResult',
    'show_disk_prompt_dialog',
]
