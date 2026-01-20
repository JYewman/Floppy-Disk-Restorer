"""
Session indicator widget for Floppy Workbench.

Displays a compact session indicator in the main window top bar showing:
- Platform icon
- Format name and disk size
- Change button to return to session screen

Part of Phase 4: UI Implementation
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon

from floppy_formatter.core.session import DiskSession
from floppy_formatter.gui.resources import get_icon

logger = logging.getLogger(__name__)


class SessionIndicator(QWidget):
    """
    Compact session indicator for the main window.

    Displays: [Platform Icon] IBM PC 1.44MB (3.5") [Change]

    Signals:
        change_requested: Emitted when user clicks the Change button
    """

    change_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._session: Optional[DiskSession] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setStyleSheet("""
            SessionIndicator {
                background-color: #2d2d30;
                border: 1px solid #3a3d41;
                border-radius: 4px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Platform icon
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(24, 24)
        self._icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._icon_label)

        # Session label container
        label_container = QWidget()
        label_container.setStyleSheet("background: transparent; border: none;")
        label_layout = QHBoxLayout(label_container)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(6)

        # "Session:" prefix label
        prefix_label = QLabel("Session:")
        prefix_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 13px;
                background: transparent;
                border: none;
            }
        """)
        label_layout.addWidget(prefix_label)

        # Session name label
        self._name_label = QLabel("No session selected")
        self._name_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-weight: bold;
                font-size: 13px;
                background: transparent;
                border: none;
            }
        """)
        label_layout.addWidget(self._name_label)

        # Disk size label
        self._size_label = QLabel("")
        self._size_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 13px;
                background: transparent;
                border: none;
            }
        """)
        label_layout.addWidget(self._size_label)

        layout.addWidget(label_container)

        # Spacer
        layout.addStretch()

        # Change button
        self._change_btn = QPushButton("Change")
        self._change_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3d41;
                color: #cccccc;
                border: 1px solid #4a4d51;
                border-radius: 3px;
                padding: 6px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a4d51;
                border-color: #5a5d61;
            }
            QPushButton:pressed {
                background-color: #2a2d31;
            }
        """)
        self._change_btn.clicked.connect(self._on_change_clicked)
        layout.addWidget(self._change_btn)

        # Set size policy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(40)

    def _on_change_clicked(self) -> None:
        """Handle change button click."""
        self.change_requested.emit()

    def update_session(self, session: Optional[DiskSession]) -> None:
        """
        Update the indicator with a new session.

        Args:
            session: The session to display, or None to clear
        """
        self._session = session

        if session is None:
            self._name_label.setText("No session selected")
            self._size_label.setText("")
            self._icon_label.clear()
            return

        # Update name
        self._name_label.setText(session.name)

        # Update disk size
        self._size_label.setText(f"({session.disk_size})")

        # Update icon based on platform
        icon = self._get_platform_icon(session.platform)
        if icon and not icon.isNull():
            self._icon_label.setPixmap(icon.pixmap(20, 20))
        else:
            self._icon_label.clear()

    def _get_platform_icon(self, platform: str) -> Optional[QIcon]:
        """Get an icon for the platform."""
        # Try to get a platform-specific icon, fall back to generic floppy
        icon = get_icon(f"platform_{platform}")
        if icon.isNull():
            icon = get_icon("floppy")
        return icon

    def get_session(self) -> Optional[DiskSession]:
        """
        Get the currently displayed session.

        Returns:
            The current DiskSession or None
        """
        return self._session

    def has_session(self) -> bool:
        """
        Check if a session is currently set.

        Returns:
            True if a session is set
        """
        return self._session is not None

    def set_enabled(self, enabled: bool) -> None:
        """
        Enable or disable the change button.

        Args:
            enabled: Whether the button should be enabled
        """
        self._change_btn.setEnabled(enabled)


class SessionIndicatorCompact(QWidget):
    """
    Even more compact session indicator variant.

    Displays just the format name with a clickable link style.
    """

    change_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._session: Optional[DiskSession] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Clickable session label
        self._label = QPushButton("No session")
        self._label.setFlat(True)
        self._label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._label.setStyleSheet("""
            QPushButton {
                color: #569cd6;
                border: none;
                background: transparent;
                font-size: 11px;
                text-decoration: underline;
                padding: 0;
            }
            QPushButton:hover {
                color: #7cb9e8;
            }
        """)
        self._label.clicked.connect(self._on_label_clicked)
        layout.addWidget(self._label)

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def _on_label_clicked(self) -> None:
        """Handle label click."""
        self.change_requested.emit()

    def update_session(self, session: Optional[DiskSession]) -> None:
        """Update the indicator with a new session."""
        self._session = session

        if session is None:
            self._label.setText("No session")
        else:
            self._label.setText(f"{session.name} ({session.disk_size})")

    def get_session(self) -> Optional[DiskSession]:
        """Get the currently displayed session."""
        return self._session
