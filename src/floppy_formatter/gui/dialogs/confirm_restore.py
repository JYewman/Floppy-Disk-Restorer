"""
Confirmation dialog for restore operations.

Provides a confirmation dialog used before starting a disk restore
operation, displaying a summary of the selected configuration options.
"""

from PyQt6.QtWidgets import QMessageBox, QWidget
from typing import Optional, Dict, Any, List


def show_confirm_restore_dialog(
    parent: Optional[QWidget] = None,
    device_path: str = "",
    settings: Optional[Dict[str, Any]] = None,
    known_bad_sectors: Optional[List[int]] = None
) -> bool:
    """
    Show a confirmation dialog for starting a restore operation.

    Displays a summary of the selected restore options including recovery mode,
    number of passes, advanced options, and asks for confirmation.

    Args:
        parent: Parent widget for the dialog
        device_path: Path to the device being restored (for display)
        settings: Dictionary containing restore settings from get_restore_settings()
        known_bad_sectors: List of known bad sectors for targeted mode display

    Returns:
        True if user confirms restore, False otherwise

    Example:
        settings = restore_widget.get_restore_settings()
        if show_confirm_restore_dialog(self, "/dev/sde", settings, bad_sectors):
            start_restore()
    """
    if settings is None:
        settings = {}

    if known_bad_sectors is None:
        known_bad_sectors = []

    # Create message box
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Question)
    msg_box.setWindowTitle("Confirm Restore Operation")

    # Build device text
    device_text = f" on {device_path}" if device_path else ""
    msg_box.setText(
        f"<h3>Start disk recovery{device_text}?</h3>"
    )

    # Build settings summary
    is_convergence = settings.get("convergence_mode", False)
    passes = settings.get("passes", 5)
    targeted_mode = settings.get("targeted_mode", False)
    multiread_mode = settings.get("multiread_mode", False)
    multiread_attempts = settings.get("multiread_attempts", 100)

    # Recovery mode section
    if is_convergence:
        mode_text = "Convergence Mode"
        passes_text = f"Maximum {passes} passes"
        mode_desc = "Recovery will continue until bad sector count stabilizes"
    else:
        mode_text = "Fixed Passes"
        passes_text = f"Exactly {passes} passes"
        mode_desc = "Recovery will run for the specified number of passes"

    # Advanced options section
    advanced_items = []
    if targeted_mode:
        bad_count = len(known_bad_sectors)
        advanced_items.append(f"Targeted Recovery: {bad_count} bad sector(s)")
    if multiread_mode:
        advanced_items.append(f"Multi-Read Mode: {multiread_attempts} attempts per sector")

    if advanced_items:
        advanced_text = "<br>".join([f"&bull; {item}" for item in advanced_items])
    else:
        advanced_text = "&bull; None selected"

    # Build informative text with proper formatting
    info_text = (
        f"<p><b>Recovery Mode:</b> {mode_text}</p>"
        f"<p><b>Passes:</b> {passes_text}</p>"
        f"<p style='color: #858585; font-size: 9pt;'>{mode_desc}</p>"
        f"<br>"
        f"<p><b>Advanced Options:</b></p>"
        f"<p style='margin-left: 10px;'>{advanced_text}</p>"
        f"<br>"
        f"<p>The restore process will attempt to recover bad sectors on the disk. "
        f"This operation may take several minutes depending on disk condition.</p>"
        f"<br>"
        f"<p><b>Are you sure you want to start the restore operation?</b></p>"
    )

    msg_box.setInformativeText(info_text)

    # Add custom buttons
    start_button = msg_box.addButton("Yes, Start Restore", QMessageBox.ButtonRole.AcceptRole)
    cancel_button = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

    # Style the start button with primary colors
    start_button.setStyleSheet("""
        QPushButton {
            background-color: #0e639c;
            color: #ffffff;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            min-width: 140px;
        }
        QPushButton:hover {
            background-color: #1177bb;
        }
        QPushButton:pressed {
            background-color: #094771;
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

    return msg_box.clickedButton() == start_button


class ConfirmRestoreDialog:
    """
    Utility class for showing restore confirmation dialogs.

    Provides a consistent way to ask the user for confirmation before
    starting a disk restore operation, displaying a summary of the
    selected configuration options.

    Example:
        dialog = ConfirmRestoreDialog(parent_widget)
        settings = restore_widget.get_restore_settings()
        if dialog.confirm("/dev/sde", settings, bad_sectors):
            start_restore()
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize confirmation dialog.

        Args:
            parent: Parent widget for the dialog
        """
        self._parent = parent

    def confirm(
        self,
        device_path: str = "",
        settings: Optional[Dict[str, Any]] = None,
        known_bad_sectors: Optional[List[int]] = None
    ) -> bool:
        """
        Show the confirmation dialog and get user response.

        Args:
            device_path: Path to device being restored (for display)
            settings: Dictionary of restore settings
            known_bad_sectors: List of known bad sectors for targeted mode

        Returns:
            True if user confirms restore, False otherwise
        """
        return show_confirm_restore_dialog(
            self._parent,
            device_path,
            settings,
            known_bad_sectors
        )

    def set_parent(self, parent: QWidget) -> None:
        """
        Set the parent widget for the dialog.

        Args:
            parent: New parent widget
        """
        self._parent = parent
