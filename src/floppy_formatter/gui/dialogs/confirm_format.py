"""
Confirmation dialog for format operations.

Provides a warning dialog used before starting a destructive disk format
operation to ensure the user understands the consequences.
"""

from PyQt6.QtWidgets import QMessageBox, QWidget, QPushButton
from typing import Optional


def show_confirm_format_dialog(
    parent: Optional[QWidget] = None,
    device_path: str = ""
) -> bool:
    """
    Show a confirmation dialog for formatting a disk.

    Displays a warning dialog with destructive styling to ensure the user
    understands that formatting will erase all data on the disk.

    Args:
        parent: Parent widget for the dialog
        device_path: Path to the device being formatted (for display)

    Returns:
        True if user confirms format, False otherwise

    Example:
        if show_confirm_format_dialog(self, "/dev/sde"):
            start_format()
    """
    # Create message box
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setWindowTitle("Confirm Format")

    # Build message text
    device_text = f" ({device_path})" if device_path else ""
    msg_box.setText(
        f"<h3>This will ERASE ALL DATA on the disk{device_text}.</h3>"
    )
    msg_box.setInformativeText(
        "The format operation will:\n"
        "- Erase all existing data permanently\n"
        "- Low-level format all 160 tracks\n"
        "- Detect and mark any bad sectors\n\n"
        "This action cannot be undone. Are you sure you want to continue?"
    )

    # Add custom buttons
    format_button = msg_box.addButton("Yes, Format Disk", QMessageBox.ButtonRole.AcceptRole)
    cancel_button = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

    # Style the format button with warning/destructive colors
    format_button.setStyleSheet("""
        QPushButton {
            background-color: #a02020;
            color: #ffffff;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            min-width: 120px;
        }
        QPushButton:hover {
            background-color: #c02828;
        }
        QPushButton:pressed {
            background-color: #801818;
        }
    """)

    # Style the cancel button
    cancel_button.setStyleSheet("""
        QPushButton {
            background-color: #3a3d41;
            color: #ffffff;
            border: 1px solid #6c6c6c;
            border-radius: 4px;
            padding: 8px 16px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #4e5157;
            border-color: #858585;
        }
        QPushButton:pressed {
            background-color: #2d2d30;
        }
    """)

    # Set Cancel as default for safety
    msg_box.setDefaultButton(cancel_button)

    # Style the message box itself
    msg_box.setStyleSheet("""
        QMessageBox {
            background-color: #1e1e1e;
        }
        QMessageBox QLabel {
            color: #ffffff;
        }
    """)

    # Execute and check result
    msg_box.exec()

    return msg_box.clickedButton() == format_button


class ConfirmFormatDialog:
    """
    Utility class for showing format confirmation dialogs.

    Provides a consistent way to ask the user for confirmation before
    starting a destructive disk format operation.

    Example:
        dialog = ConfirmFormatDialog(parent_widget)
        if dialog.confirm("/dev/sde"):
            start_format()
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize confirmation dialog.

        Args:
            parent: Parent widget for the dialog
        """
        self._parent = parent

    def confirm(self, device_path: str = "") -> bool:
        """
        Show the confirmation dialog and get user response.

        Args:
            device_path: Path to device being formatted (for display)

        Returns:
            True if user confirms format, False otherwise
        """
        return show_confirm_format_dialog(self._parent, device_path)

    def set_parent(self, parent: QWidget) -> None:
        """
        Set the parent widget for the dialog.

        Args:
            parent: New parent widget
        """
        self._parent = parent
