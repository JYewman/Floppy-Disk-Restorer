"""
Administrator privilege warning dialog.

Shows a warning when the application is not running with root/administrator
privileges, offering options to exit or continue in view-only mode.
"""

from enum import Enum
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QSpacerItem,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor

from floppy_formatter.gui.resources import get_icon


class AdminWarningResult(Enum):
    """Result of the admin warning dialog."""
    EXIT = "exit"
    VIEW_ONLY = "view_only"


class AdminWarningDialog(QDialog):
    """
    Dialog shown when application is not running with administrator privileges.

    Presents two options:
    - Exit: Close the application entirely
    - View Only Mode: Continue with limited functionality (destructive operations disabled)

    Example:
        dialog = AdminWarningDialog(parent)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            if dialog.get_result() == AdminWarningResult.VIEW_ONLY:
                enable_view_only_mode()
            else:
                sys.exit(0)
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize admin warning dialog.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._result = AdminWarningResult.EXIT
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog user interface."""
        self.setWindowTitle("Administrator Privileges Required")
        self.setModal(True)
        self.setFixedSize(500, 280)

        # Apply dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #cccccc;
            }
            QLabel {
                color: #cccccc;
                background-color: transparent;
            }
            QPushButton {
                min-width: 120px;
                min-height: 36px;
                border-radius: 4px;
                font-weight: bold;
                padding: 8px 16px;
            }
        """)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header with icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        # Warning icon
        icon_label = QLabel()
        icon = get_icon("alert-triangle")
        if not icon.isNull():
            # Render icon with warning color
            pixmap = icon.pixmap(48, 48)
            # Create colored version
            colored_pixmap = QPixmap(pixmap.size())
            colored_pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(colored_pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.drawPixmap(0, 0, pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(colored_pixmap.rect(), QColor("#f0a030"))
            painter.end()
            icon_label.setPixmap(colored_pixmap)
        else:
            # Fallback: use text warning symbol
            icon_label.setText("⚠")
            icon_label.setStyleSheet("font-size: 36pt; color: #f0a030;")
        icon_label.setFixedSize(64, 64)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(icon_label)

        # Title and message
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)

        title_label = QLabel("Administrator Privileges Required")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #ffffff;")
        text_layout.addWidget(title_label)

        message_label = QLabel(
            "This application requires root/administrator privileges to access "
            "disk devices directly."
        )
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: #cccccc;")
        text_layout.addWidget(message_label)

        header_layout.addLayout(text_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Secondary message
        secondary_label = QLabel(
            "Without elevated privileges, disk operations will fail. You can either:\n\n"
            "• Run the application with sudo/root privileges\n"
            "• Continue in View Only mode (scan is read-only, but format and restore are disabled)"
        )
        secondary_label.setWordWrap(True)
        secondary_label.setStyleSheet("color: #858585; padding-left: 80px;")
        layout.addWidget(secondary_label)

        # Spacer
        layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.addStretch()

        # View Only button (secondary)
        self.view_only_button = QPushButton("View Only Mode")
        self.view_only_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3d41;
                color: #ffffff;
                border: 1px solid #6c6c6c;
            }
            QPushButton:hover {
                background-color: #4e5157;
                border-color: #858585;
            }
            QPushButton:pressed {
                background-color: #2d2d30;
            }
        """)
        self.view_only_button.clicked.connect(self._on_view_only_clicked)
        button_layout.addWidget(self.view_only_button)

        # Exit button (primary/destructive)
        self.exit_button = QPushButton("Exit")
        self.exit_button.setStyleSheet("""
            QPushButton {
                background-color: #e81123;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #f1374b;
            }
            QPushButton:pressed {
                background-color: #c50f1f;
            }
        """)
        self.exit_button.clicked.connect(self._on_exit_clicked)
        self.exit_button.setDefault(True)
        button_layout.addWidget(self.exit_button)

        layout.addLayout(button_layout)

    def _on_exit_clicked(self) -> None:
        """Handle Exit button click."""
        self._result = AdminWarningResult.EXIT
        self.reject()

    def _on_view_only_clicked(self) -> None:
        """Handle View Only button click."""
        self._result = AdminWarningResult.VIEW_ONLY
        self.accept()

    def get_result(self) -> AdminWarningResult:
        """
        Get the user's choice.

        Returns:
            AdminWarningResult indicating the user's selection
        """
        return self._result


def show_admin_warning_dialog(parent: Optional[QWidget] = None) -> AdminWarningResult:
    """
    Show the admin warning dialog and return the user's choice.

    This is a convenience function that creates and executes the dialog.

    Args:
        parent: Optional parent widget

    Returns:
        AdminWarningResult indicating whether to exit or continue in view-only mode
    """
    dialog = AdminWarningDialog(parent)
    dialog.exec()
    return dialog.get_result()


def check_admin_privileges() -> bool:
    """
    Check if the application is running with administrator privileges.

    Returns:
        True if running as root/admin, False otherwise
    """
    import os

    # On Unix-like systems, check if UID is 0 (root)
    if hasattr(os, 'getuid'):
        return os.getuid() == 0

    # On Windows, check if running as administrator
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except (AttributeError, OSError):
        return False
