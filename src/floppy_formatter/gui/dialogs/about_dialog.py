"""
About dialog for Floppy Workbench.

Displays application information including name, version, description,
GitHub link, license information, and credits.

Part of Phase 14: Polish & Professional Touches
"""

from typing import Optional
import importlib.metadata

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QSpacerItem,
    QSizePolicy,
    QFrame,
    QScrollArea,
    QTabWidget,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QDesktopServices

from floppy_formatter.gui.resources import get_icon, get_version


class AboutDialog(QDialog):
    """
    About dialog displaying application information.

    Shows:
    - Application name and version
    - Description
    - GitHub repository link (clickable)
    - License information
    - Credits and acknowledgments
    - Keyboard shortcuts reference

    Example:
        dialog = AboutDialog(parent)
        dialog.exec()
    """

    GITHUB_URL = "https://github.com/JYewman/Floppy-Disk-Restorer"
    APP_NAME = "Floppy Workbench"
    APP_SUBTITLE = "Professional Floppy Disk Analysis & Recovery"

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize about dialog.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog user interface."""
        self.setWindowTitle(f"About {self.APP_NAME}")
        self.setModal(True)
        self.setFixedSize(520, 520)

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
                min-width: 100px;
                min-height: 32px;
                border-radius: 4px;
                font-weight: bold;
                padding: 6px 16px;
            }
            QTabWidget::pane {
                border: 1px solid #3a3d41;
                border-radius: 4px;
                background-color: #252526;
            }
            QTabBar::tab {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 8px 16px;
                border: 1px solid #3a3d41;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #252526;
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3a3d41;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header with icon and title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        # Application icon - use the RTC logo
        icon_label = QLabel()
        icon = get_icon("app_logo")
        if not icon.isNull():
            pixmap = icon.pixmap(80, 80)
            icon_label.setPixmap(pixmap)
        else:
            # Fallback to app_icon SVG
            icon = get_icon("app_icon")
            if not icon.isNull():
                pixmap = icon.pixmap(72, 72)
                icon_label.setPixmap(pixmap)
            else:
                icon_label.setText("💾")
                icon_label.setStyleSheet("font-size: 48pt;")
        icon_label.setFixedSize(80, 80)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(icon_label)

        # Title and version
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        app_name_label = QLabel(self.APP_NAME)
        app_name_font = QFont()
        app_name_font.setPointSize(18)
        app_name_font.setBold(True)
        app_name_label.setFont(app_name_font)
        app_name_label.setStyleSheet("color: #ffffff;")
        title_layout.addWidget(app_name_label)

        version_label = QLabel(f"Version {get_version()}")
        version_label.setStyleSheet("color: #858585; font-size: 11pt;")
        title_layout.addWidget(version_label)

        title_layout.addStretch()
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Description
        description_label = QLabel(self.APP_SUBTITLE)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description_label.setStyleSheet("color: #cccccc; font-size: 12pt;")
        layout.addWidget(description_label)

        # Tab widget for different info sections
        tab_widget = QTabWidget()

        # About tab
        about_tab = self._create_about_tab()
        tab_widget.addTab(about_tab, "About")

        # Credits tab
        credits_tab = self._create_credits_tab()
        tab_widget.addTab(credits_tab, "Credits")

        # Shortcuts tab
        shortcuts_tab = self._create_shortcuts_tab()
        tab_widget.addTab(shortcuts_tab, "Shortcuts")

        layout.addWidget(tab_widget, 1)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Open GitHub button
        github_button = QPushButton("Open GitHub")
        github_button.setStyleSheet("""
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
        github_button.clicked.connect(self._on_github_clicked)
        button_layout.addWidget(github_button)

        # OK button
        ok_button = QPushButton("OK")
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
        """)
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)

    def _create_about_tab(self) -> QWidget:
        """Create the About tab content."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # GitHub link
        github_layout = QHBoxLayout()
        github_label = QLabel("GitHub:")
        github_label.setStyleSheet("color: #858585;")
        github_label.setFixedWidth(80)
        github_layout.addWidget(github_label)

        github_link = QLabel(f'<a href="{self.GITHUB_URL}" style="color: #3794ff;">{self.GITHUB_URL}</a>')
        github_link.setOpenExternalLinks(True)
        github_link.setTextFormat(Qt.TextFormat.RichText)
        github_link.setCursor(Qt.CursorShape.PointingHandCursor)
        github_layout.addWidget(github_link)
        github_layout.addStretch()
        layout.addLayout(github_layout)

        # License
        license_layout = QHBoxLayout()
        license_label = QLabel("License:")
        license_label.setStyleSheet("color: #858585;")
        license_label.setFixedWidth(80)
        license_layout.addWidget(license_label)

        license_value = QLabel("MIT License")
        license_value.setStyleSheet("color: #cccccc;")
        license_layout.addWidget(license_value)
        license_layout.addStretch()
        layout.addLayout(license_layout)

        # Author
        author_layout = QHBoxLayout()
        author_label = QLabel("Author:")
        author_label.setStyleSheet("color: #858585;")
        author_label.setFixedWidth(80)
        author_layout.addWidget(author_label)

        author_value = QLabel("Joshua Yewman")
        author_value.setStyleSheet("color: #cccccc;")
        author_layout.addWidget(author_value)
        author_layout.addStretch()
        layout.addLayout(author_layout)

        layout.addStretch()

        # Attribution message
        attribution_label = QLabel("Made with love for the floppy disk preservation community")
        attribution_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        attribution_label.setStyleSheet("color: #858585; font-style: italic;")
        layout.addWidget(attribution_label)

        return tab

    def _create_credits_tab(self) -> QWidget:
        """Create the Credits tab content."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Scroll area for credits
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(10)

        # Credits sections
        credits_data = [
            ("Hardware Support", [
                ("Greaseweazle", "Keir Fraser", "Flux-level floppy drive controller"),
            ]),
            ("Libraries & Frameworks", [
                ("PyQt6", "Riverbank Computing", "Python bindings for Qt"),
                ("greaseweazle", "Keir Fraser", "Python library for Greaseweazle"),
            ]),
            ("Special Thanks", [
                ("Floppy Disk Preservation Community", "", "For keeping magnetic media alive"),
                ("Archive.org", "", "Digital preservation efforts"),
                ("SCP/HFE Format Authors", "", "Flux image format specifications"),
            ]),
            ("Icons", [
                ("Feather Icons", "Cole Bemis", "Open source icon set"),
            ]),
        ]

        for section_title, items in credits_data:
            # Section header
            section_label = QLabel(section_title)
            section_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 9pt;")
            content_layout.addWidget(section_label)

            for name, author, description in items:
                item_layout = QHBoxLayout()
                item_layout.setContentsMargins(12, 0, 0, 0)
                item_layout.setSpacing(6)

                name_label = QLabel(f"• {name}")
                name_label.setStyleSheet("color: #4ec9b0; font-size: 8pt;")
                name_label.setFixedWidth(160)
                item_layout.addWidget(name_label)

                if author:
                    author_label = QLabel(author)
                    author_label.setStyleSheet("color: #cccccc; font-size: 8pt;")
                    author_label.setFixedWidth(100)
                    item_layout.addWidget(author_label)

                desc_label = QLabel(description)
                desc_label.setStyleSheet("color: #858585; font-size: 8pt;")
                desc_label.setWordWrap(True)
                item_layout.addWidget(desc_label, 1)

                content_layout.addLayout(item_layout)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        return tab

    def _create_shortcuts_tab(self) -> QWidget:
        """Create the Keyboard Shortcuts tab content."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Scroll area for shortcuts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(12)

        # Shortcuts sections
        shortcuts_data = [
            ("Operations", [
                ("Ctrl+S", "Start Scan"),
                ("Ctrl+Shift+F", "Start Format"),
                ("Ctrl+R", "Start Restore/Recovery"),
                ("Ctrl+Shift+A", "Start Analysis"),
                ("Space", "Pause/Resume Operation"),
                ("Escape", "Cancel Operation"),
            ]),
            ("Device Control", [
                ("Ctrl+Shift+C", "Connect/Disconnect Device"),
                ("Ctrl+M", "Toggle Motor On/Off"),
                ("Ctrl+0", "Seek to Track 0"),
            ]),
            ("View", [
                ("Ctrl+D", "Toggle Dark/Light Theme"),
                ("F11", "Toggle Fullscreen"),
            ]),
            ("Application", [
                ("Ctrl+Q", "Exit Application"),
            ]),
        ]

        for section_title, shortcuts in shortcuts_data:
            # Section header
            section_label = QLabel(section_title)
            section_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 11pt;")
            content_layout.addWidget(section_label)

            for shortcut, description in shortcuts:
                item_layout = QHBoxLayout()
                item_layout.setContentsMargins(16, 0, 0, 0)

                # Shortcut key badge
                key_label = QLabel(shortcut)
                key_label.setStyleSheet("""
                    color: #ffffff;
                    background-color: #3a3d41;
                    border: 1px solid #6c6c6c;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-family: "Consolas", "Monaco", monospace;
                    font-size: 10pt;
                """)
                key_label.setFixedWidth(120)
                item_layout.addWidget(key_label)

                desc_label = QLabel(description)
                desc_label.setStyleSheet("color: #cccccc;")
                item_layout.addWidget(desc_label, 1)

                content_layout.addLayout(item_layout)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        return tab

    def _on_github_clicked(self) -> None:
        """Open the GitHub repository in the default browser."""
        QDesktopServices.openUrl(QUrl(self.GITHUB_URL))


def show_about_dialog(parent: Optional[QWidget] = None) -> None:
    """
    Show the about dialog.

    This is a convenience function that creates and executes the dialog.

    Args:
        parent: Optional parent widget
    """
    dialog = AboutDialog(parent)
    dialog.exec()
