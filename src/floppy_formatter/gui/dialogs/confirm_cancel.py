"""
Confirmation dialog for cancelling operations.

Provides a simple Yes/No confirmation dialog used when the user
attempts to cancel an in-progress operation.
"""

from PyQt6.QtWidgets import QMessageBox, QWidget
from typing import Optional


def show_confirm_cancel_dialog(
    parent: Optional[QWidget] = None,
    operation_name: str = "operation"
) -> bool:
    """
    Show a confirmation dialog for cancelling an operation.

    Args:
        parent: Parent widget for the dialog
        operation_name: Name of the operation being cancelled (e.g., "scan", "format")

    Returns:
        True if user confirms cancellation, False otherwise

    Example:
        if show_confirm_cancel_dialog(self, "scan"):
            worker.cancel()
    """
    result = QMessageBox.question(
        parent,
        "Cancel Operation",
        f"Are you sure you want to cancel the {operation_name}?\n\n"
        f"Any progress will be lost.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No
    )

    return result == QMessageBox.StandardButton.Yes


class ConfirmCancelDialog:
    """
    Utility class for showing cancellation confirmation dialogs.

    Provides a consistent way to ask the user for confirmation before
    cancelling an in-progress disk operation.

    Example:
        dialog = ConfirmCancelDialog(parent_widget)
        if dialog.confirm("scan"):
            worker.cancel()
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize confirmation dialog.

        Args:
            parent: Parent widget for the dialog
        """
        self._parent = parent

    def confirm(self, operation_name: str = "operation") -> bool:
        """
        Show the confirmation dialog and get user response.

        Args:
            operation_name: Name of the operation being cancelled

        Returns:
            True if user confirms cancellation, False otherwise
        """
        return show_confirm_cancel_dialog(self._parent, operation_name)

    def confirm_scan_cancel(self) -> bool:
        """
        Show confirmation dialog specifically for scan cancellation.

        Returns:
            True if user confirms cancellation, False otherwise
        """
        return show_confirm_cancel_dialog(self._parent, "scan")

    def confirm_format_cancel(self) -> bool:
        """
        Show confirmation dialog specifically for format cancellation.

        Returns:
            True if user confirms cancellation, False otherwise
        """
        return show_confirm_cancel_dialog(self._parent, "format")

    def confirm_restore_cancel(self) -> bool:
        """
        Show confirmation dialog specifically for restore cancellation.

        Returns:
            True if user confirms cancellation, False otherwise
        """
        return show_confirm_cancel_dialog(self._parent, "restore")

    def set_parent(self, parent: QWidget) -> None:
        """
        Set the parent widget for the dialog.

        Args:
            parent: New parent widget
        """
        self._parent = parent
