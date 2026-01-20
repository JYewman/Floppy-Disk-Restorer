"""
Session selection screen for Floppy Workbench.

This screen allows users to select a disk format before performing operations.
It provides:
- Platform selection panel (IBM PC, Amiga, Mac, etc.)
- Format selection panel with disk size filtering
- Session preview panel with format details and disk visualization
- Preset management (save/load)

Part of Phase 4: UI Implementation
"""

import logging
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QPushButton,
    QButtonGroup,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QMenu,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QPainter, QColor, QPen, QBrush, QRadialGradient

from floppy_formatter.core.session import DiskSession, DiskSize
from floppy_formatter.core.session_manager import SessionManager
from floppy_formatter.core.gw_format_registry import GWFormatRegistry
from floppy_formatter.gui.resources import get_icon

logger = logging.getLogger(__name__)


class DiskVisualizationWidget(QWidget):
    """
    Visual representation of a floppy disk magnetic surface.

    Displays a clean circular visualization showing:
    - Magnetic disk surface with gradient
    - Track rings representing cylinders
    - Sector divisions
    - Center spindle hole
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(140, 140)
        self.setMaximumSize(180, 180)

        self._cylinders = 80
        self._heads = 2
        self._sectors_per_track = 18
        self._disk_size = '3.5"'

    def set_geometry(self, cylinders: int, heads: int, sectors_per_track: int,
                     disk_size: str = '3.5"') -> None:
        """Update the displayed geometry."""
        self._cylinders = cylinders
        self._heads = heads
        self._sectors_per_track = sectors_per_track
        self._disk_size = disk_size
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the disk visualization."""
        import math

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate dimensions
        width = self.width()
        height = self.height()
        size = min(width, height) - 16
        cx = width / 2
        cy = height / 2
        outer_radius = size / 2
        inner_radius = size * 0.12  # Spindle hole

        # Color scheme based on disk size
        if self._disk_size == '3.5"':
            surface_color = QColor(45, 42, 38)
            track_color = QColor(65, 60, 52)
            highlight_color = QColor(85, 78, 68)
        elif self._disk_size == '5.25"':
            surface_color = QColor(48, 44, 38)
            track_color = QColor(68, 62, 52)
            highlight_color = QColor(88, 80, 68)
        else:  # 8"
            surface_color = QColor(42, 42, 42)
            track_color = QColor(62, 62, 58)
            highlight_color = QColor(82, 82, 78)

        # Draw outer shadow/border
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(20, 20, 22)))
        painter.drawEllipse(int(cx - outer_radius - 2), int(cy - outer_radius - 2),
                           int(outer_radius * 2 + 4), int(outer_radius * 2 + 4))

        # Draw disk surface with radial gradient
        gradient = QRadialGradient(cx, cy, outer_radius)
        gradient.setColorAt(0.0, highlight_color)
        gradient.setColorAt(0.3, surface_color)
        gradient.setColorAt(0.7, surface_color)
        gradient.setColorAt(1.0, QColor(35, 32, 28))

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(30, 28, 25), 1))
        painter.drawEllipse(int(cx - outer_radius), int(cy - outer_radius),
                           int(outer_radius * 2), int(outer_radius * 2))

        # Draw track rings
        track_area = outer_radius - inner_radius - 8
        num_tracks = min(12, max(4, self._cylinders // 7))
        track_spacing = track_area / num_tracks

        for i in range(num_tracks):
            r = inner_radius + 6 + (i * track_spacing)
            # Alternate track colors for visibility
            if i % 2 == 0:
                painter.setPen(QPen(track_color, 1))
            else:
                painter.setPen(QPen(QColor(track_color.red() - 8,
                                          track_color.green() - 8,
                                          track_color.blue() - 6), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        # Draw sector lines (subtle)
        num_sectors = min(self._sectors_per_track, 18)
        painter.setPen(QPen(QColor(track_color.red(), track_color.green(),
                                   track_color.blue(), 60), 1))
        for i in range(num_sectors):
            angle = (2 * math.pi * i) / num_sectors
            x1 = cx + (inner_radius + 4) * math.cos(angle)
            y1 = cy + (inner_radius + 4) * math.sin(angle)
            x2 = cx + (outer_radius - 4) * math.cos(angle)
            y2 = cy + (outer_radius - 4) * math.sin(angle)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Draw spindle hole with gradient
        hole_gradient = QRadialGradient(cx, cy, inner_radius)
        hole_gradient.setColorAt(0.0, QColor(25, 25, 28))
        hole_gradient.setColorAt(0.7, QColor(18, 18, 20))
        hole_gradient.setColorAt(1.0, QColor(35, 32, 30))

        painter.setBrush(QBrush(hole_gradient))
        painter.setPen(QPen(QColor(50, 48, 45), 1.5))
        painter.drawEllipse(int(cx - inner_radius), int(cy - inner_radius),
                           int(inner_radius * 2), int(inner_radius * 2))

        # Draw center hub ring
        hub_radius = inner_radius * 0.5
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(60, 58, 55), 1))
        painter.drawEllipse(int(cx - hub_radius), int(cy - hub_radius),
                           int(hub_radius * 2), int(hub_radius * 2))


class PlatformListWidget(QListWidget):
    """
    List widget displaying available platforms.

    Shows platform icons and names, with format count badges.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setSpacing(2)
        self.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 4px;
                outline: none;
            }
            QListWidget::item {
                color: #cccccc;
                padding: 8px 12px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
            QListWidget::item:hover:!selected {
                background-color: #2a2d2e;
            }
        """)


class FormatListWidget(QListWidget):
    """
    List widget displaying formats for the selected platform.

    Shows format name, capacity, and brief description.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setSpacing(2)
        self.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 4px;
                outline: none;
            }
            QListWidget::item {
                color: #cccccc;
                padding: 10px 12px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
            QListWidget::item:hover:!selected {
                background-color: #2a2d2e;
            }
        """)


class SessionScreen(QWidget):
    """
    Full-screen session selection interface.

    Layout:
    +-------------------------------------------------------------+
    |  FLOPPY WORKBENCH - Select Disk Format                      |
    +----------+----------------------+---------------------------+
    | PLATFORM | FORMAT               | SESSION PREVIEW           |
    |          |                      |                           |
    | o IBM PC | +------------------+ | IBM PC 1.44MB HD          |
    | o Amiga  | | [3.5"] [5.25"]   | | -------------------       |
    | o Mac    | +------------------+ | Cylinders: 80             |
    | o C64    | | * 1.44MB HD      | | Heads: 2                  |
    | o Apple  | | o 720KB DD       | | Sectors: 18               |
    | o Atari  | | o 360KB DD       | | Encoding: MFM             |
    | o BBC    | | o 1.2MB HD       | | Data Rate: 500 kbps       |
    | o MSX    | |   ...            | |                           |
    | o ZX     | +------------------+ | [Disk Visualization]      |
    | ...      |                      |                           |
    +----------+----------------------+---------------------------+
    | [Load Preset v]        [Save as Preset]       [Continue ->] |
    +-------------------------------------------------------------+

    Signals:
        session_selected: Emitted when user clicks Continue with valid session
    """

    session_selected = pyqtSignal(object)  # Emits DiskSession

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._registry = GWFormatRegistry.instance()
        self._session_manager = SessionManager.instance()

        self._selected_platform: Optional[str] = None
        self._selected_format: Optional[str] = None
        self._selected_disk_size: str = '3.5"'
        self._current_session: Optional[DiskSession] = None

        self._setup_ui()
        self._connect_signals()
        self._load_platforms()

        # Select IBM PC by default
        self._select_platform('ibm')

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header
        header = self._create_header()
        main_layout.addWidget(header)

        # Main content splitter
        content = self._create_content()
        main_layout.addWidget(content, 1)

        # Footer with buttons
        footer = self._create_footer()
        main_layout.addWidget(footer)

    def _create_header(self) -> QWidget:
        """Create the header with title."""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #3a3d41;
                border-radius: 6px;
                padding: 12px;
            }
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)

        # App logo icon
        icon_label = QLabel()
        app_icon = get_icon("app_logo")
        if not app_icon.isNull():
            icon_label.setPixmap(app_icon.pixmap(32, 32))
        layout.addWidget(icon_label)

        # Title
        title_label = QLabel("FLOPPY WORKBENCH - Select Disk Format")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        layout.addWidget(title_label)

        layout.addStretch()

        # Subtitle
        subtitle_label = QLabel("Choose the disk format before scanning, formatting, or restoring")
        subtitle_label.setStyleSheet("color: #888888; background: transparent; border: none;")
        layout.addWidget(subtitle_label)

        return header

    def _create_content(self) -> QWidget:
        """Create the main content area with three panels."""
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3a3d41;
            }
            QSplitter::handle:hover {
                background-color: #007acc;
            }
        """)

        # Platform panel
        platform_panel = self._create_platform_panel()
        splitter.addWidget(platform_panel)

        # Format panel
        format_panel = self._create_format_panel()
        splitter.addWidget(format_panel)

        # Preview panel
        preview_panel = self._create_preview_panel()
        splitter.addWidget(preview_panel)

        # Set initial sizes
        splitter.setSizes([200, 350, 300])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)

        return splitter

    def _create_platform_panel(self) -> QWidget:
        """Create the platform selection panel."""
        panel = QGroupBox("Platform")
        panel.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #cccccc;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 16, 8, 8)

        self._platform_list = PlatformListWidget()
        layout.addWidget(self._platform_list)

        return panel

    def _create_format_panel(self) -> QWidget:
        """Create the format selection panel with disk size tabs."""
        panel = QGroupBox("Format")
        panel.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #cccccc;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 16, 8, 8)

        # Disk size filter buttons
        size_frame = QFrame()
        size_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d30;
                border: 1px solid #3a3d41;
                border-radius: 4px;
            }
        """)
        size_layout = QHBoxLayout(size_frame)
        size_layout.setContentsMargins(8, 6, 8, 6)
        size_layout.setSpacing(8)

        self._disk_size_group = QButtonGroup(self)

        button_style = """
            QRadioButton {
                color: #cccccc;
                spacing: 4px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
            }
            QRadioButton::indicator:checked {
                background-color: #007acc;
                border: 2px solid #007acc;
                border-radius: 7px;
            }
            QRadioButton::indicator:unchecked {
                background-color: #3a3d41;
                border: 2px solid #3a3d41;
                border-radius: 7px;
            }
        """

        self._size_35_btn = QRadioButton('3.5"')
        self._size_35_btn.setStyleSheet(button_style)
        self._size_35_btn.setChecked(True)
        self._disk_size_group.addButton(self._size_35_btn)
        size_layout.addWidget(self._size_35_btn)

        self._size_525_btn = QRadioButton('5.25"')
        self._size_525_btn.setStyleSheet(button_style)
        self._disk_size_group.addButton(self._size_525_btn)
        size_layout.addWidget(self._size_525_btn)

        self._size_8_btn = QRadioButton('8"')
        self._size_8_btn.setStyleSheet(button_style)
        self._disk_size_group.addButton(self._size_8_btn)
        size_layout.addWidget(self._size_8_btn)

        self._size_all_btn = QRadioButton("All")
        self._size_all_btn.setStyleSheet(button_style)
        self._disk_size_group.addButton(self._size_all_btn)
        size_layout.addWidget(self._size_all_btn)

        size_layout.addStretch()
        layout.addWidget(size_frame)

        # Format list
        self._format_list = FormatListWidget()
        layout.addWidget(self._format_list)

        return panel

    def _create_preview_panel(self) -> QWidget:
        """Create the session preview panel."""
        panel = QGroupBox("Session Preview")
        panel.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #cccccc;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(12)

        # Format name (large)
        self._preview_name = QLabel("Select a format")
        name_font = QFont()
        name_font.setPointSize(14)
        name_font.setBold(True)
        self._preview_name.setFont(name_font)
        self._preview_name.setStyleSheet("color: #ffffff;")
        self._preview_name.setWordWrap(True)
        layout.addWidget(self._preview_name)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3a3d41;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # Details grid
        details_frame = QFrame()
        details_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d30;
                border: 1px solid #3a3d41;
                border-radius: 4px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(8)

        label_style = "color: #888888;"
        value_style = "color: #cccccc; font-weight: bold;"

        # Cylinders
        row1 = QHBoxLayout()
        row1.addWidget(self._make_label("Cylinders:", label_style))
        self._preview_cylinders = QLabel("--")
        self._preview_cylinders.setStyleSheet(value_style)
        row1.addWidget(self._preview_cylinders)
        row1.addStretch()
        details_layout.addLayout(row1)

        # Heads
        row2 = QHBoxLayout()
        row2.addWidget(self._make_label("Heads:", label_style))
        self._preview_heads = QLabel("--")
        self._preview_heads.setStyleSheet(value_style)
        row2.addWidget(self._preview_heads)
        row2.addStretch()
        details_layout.addLayout(row2)

        # Sectors per track
        row3 = QHBoxLayout()
        row3.addWidget(self._make_label("Sectors/Track:", label_style))
        self._preview_sectors = QLabel("--")
        self._preview_sectors.setStyleSheet(value_style)
        row3.addWidget(self._preview_sectors)
        row3.addStretch()
        details_layout.addLayout(row3)

        # Total sectors
        row4 = QHBoxLayout()
        row4.addWidget(self._make_label("Total Sectors:", label_style))
        self._preview_total = QLabel("--")
        self._preview_total.setStyleSheet(value_style)
        row4.addWidget(self._preview_total)
        row4.addStretch()
        details_layout.addLayout(row4)

        # Encoding
        row5 = QHBoxLayout()
        row5.addWidget(self._make_label("Encoding:", label_style))
        self._preview_encoding = QLabel("--")
        self._preview_encoding.setStyleSheet(value_style)
        row5.addWidget(self._preview_encoding)
        row5.addStretch()
        details_layout.addLayout(row5)

        # Data rate
        row6 = QHBoxLayout()
        row6.addWidget(self._make_label("Data Rate:", label_style))
        self._preview_data_rate = QLabel("--")
        self._preview_data_rate.setStyleSheet(value_style)
        row6.addWidget(self._preview_data_rate)
        row6.addStretch()
        details_layout.addLayout(row6)

        # RPM
        row7 = QHBoxLayout()
        row7.addWidget(self._make_label("RPM:", label_style))
        self._preview_rpm = QLabel("--")
        self._preview_rpm.setStyleSheet(value_style)
        row7.addWidget(self._preview_rpm)
        row7.addStretch()
        details_layout.addLayout(row7)

        # Capacity
        row8 = QHBoxLayout()
        row8.addWidget(self._make_label("Capacity:", label_style))
        self._preview_capacity = QLabel("--")
        self._preview_capacity.setStyleSheet(value_style)
        row8.addWidget(self._preview_capacity)
        row8.addStretch()
        details_layout.addLayout(row8)

        layout.addWidget(details_frame)

        # Disk visualization
        viz_label = QLabel("Disk Visualization")
        viz_label.setStyleSheet("color: #888888; font-weight: bold;")
        viz_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(viz_label)

        self._disk_viz = DiskVisualizationWidget()
        layout.addWidget(self._disk_viz, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()

        return panel

    def _create_footer(self) -> QWidget:
        """Create the footer with preset and continue buttons."""
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #3a3d41;
                border-radius: 6px;
            }
        """)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 12, 16, 12)

        button_style = """
            QPushButton {
                background-color: #3a3d41;
                color: #cccccc;
                border: 1px solid #4a4d51;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a4d51;
                border-color: #5a5d61;
            }
            QPushButton:pressed {
                background-color: #2a2d31;
            }
            QPushButton:disabled {
                background-color: #2a2d31;
                color: #666666;
                border-color: #3a3d41;
            }
        """

        # Load preset button with dropdown
        self._load_preset_btn = QToolButton()
        self._load_preset_btn.setText("Load Preset")
        self._load_preset_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._load_preset_btn.setStyleSheet("""
            QToolButton {
                background-color: #3a3d41;
                color: #cccccc;
                border: 1px solid #4a4d51;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #4a4d51;
                border-color: #5a5d61;
            }
            QToolButton::menu-indicator {
                image: none;
                width: 0px;
            }
        """)
        self._preset_menu = QMenu(self._load_preset_btn)
        self._load_preset_btn.setMenu(self._preset_menu)
        layout.addWidget(self._load_preset_btn)

        # Save preset button
        self._save_preset_btn = QPushButton("Save as Preset")
        self._save_preset_btn.setStyleSheet(button_style)
        self._save_preset_btn.setEnabled(False)
        layout.addWidget(self._save_preset_btn)

        layout.addStretch()

        # Continue button
        self._continue_btn = QPushButton("Continue")
        self._continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: #ffffff;
                border: 1px solid #0088dd;
                border-radius: 4px;
                padding: 8px 32px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0088dd;
                border-color: #0099ee;
            }
            QPushButton:pressed {
                background-color: #006abb;
            }
            QPushButton:disabled {
                background-color: #3a3d41;
                color: #666666;
                border-color: #4a4d51;
            }
        """)
        self._continue_btn.setEnabled(False)
        self._continue_btn.setMinimumWidth(150)
        layout.addWidget(self._continue_btn)

        return footer

    def _make_label(self, text: str, style: str) -> QLabel:
        """Create a styled label."""
        label = QLabel(text)
        label.setStyleSheet(style)
        label.setMinimumWidth(100)
        return label

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self._platform_list.currentItemChanged.connect(self._on_platform_selected)
        self._format_list.currentItemChanged.connect(self._on_format_selected)
        self._disk_size_group.buttonClicked.connect(self._on_disk_size_changed)
        self._continue_btn.clicked.connect(self._on_continue_clicked)
        self._save_preset_btn.clicked.connect(self._on_save_preset_clicked)
        self._preset_menu.aboutToShow.connect(self._populate_preset_menu)

    def _load_platforms(self) -> None:
        """Load all available platforms into the list."""
        platforms = self._registry.get_all_platforms()

        for platform in platforms:
            item = QListWidgetItem()
            item.setText(f"{platform['display_name']} ({platform['format_count']})")
            item.setData(Qt.ItemDataRole.UserRole, platform['id'])
            item.setToolTip(platform['description'])
            self._platform_list.addItem(item)

    def _select_platform(self, platform_id: str) -> None:
        """Programmatically select a platform."""
        for i in range(self._platform_list.count()):
            item = self._platform_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == platform_id:
                self._platform_list.setCurrentItem(item)
                break

    def _on_platform_selected(self, current: Optional[QListWidgetItem],
                               previous: Optional[QListWidgetItem]) -> None:
        """Handle platform selection change."""
        if current is None:
            return

        platform_id = current.data(Qt.ItemDataRole.UserRole)
        self._selected_platform = platform_id
        self._load_formats_for_platform(platform_id)

    def _on_disk_size_changed(self, button: QRadioButton) -> None:
        """Handle disk size filter change."""
        if button == self._size_35_btn:
            self._selected_disk_size = '3.5"'
        elif button == self._size_525_btn:
            self._selected_disk_size = '5.25"'
        elif button == self._size_8_btn:
            self._selected_disk_size = '8"'
        else:
            self._selected_disk_size = 'all'

        if self._selected_platform:
            self._load_formats_for_platform(self._selected_platform)

    def _load_formats_for_platform(self, platform_id: str) -> None:
        """Load formats for the selected platform."""
        self._format_list.clear()
        self._selected_format = None
        self._current_session = None
        self._continue_btn.setEnabled(False)
        self._save_preset_btn.setEnabled(False)

        formats = self._registry.get_formats_for_platform(platform_id)

        for fmt in formats:
            # Apply disk size filter
            if self._selected_disk_size != 'all':
                if fmt['disk_size'] != self._selected_disk_size:
                    continue

            item = QListWidgetItem()

            # Format the display text
            capacity = fmt['capacity_kb']
            if capacity >= 1024:
                capacity_str = f"{capacity / 1024:.2f}MB".rstrip('0').rstrip('.')
            else:
                capacity_str = f"{capacity}KB"

            display_text = f"{fmt['format_name']} - {capacity_str}"
            if fmt['disk_size']:
                display_text += f" ({fmt['disk_size']})"

            item.setText(display_text)
            item.setData(Qt.ItemDataRole.UserRole, fmt['gw_format'])
            item.setToolTip(f"{fmt['display_name']}\n{fmt['description']}")
            self._format_list.addItem(item)

        # Auto-select first item if available
        if self._format_list.count() > 0:
            self._format_list.setCurrentRow(0)

    def _on_format_selected(self, current: Optional[QListWidgetItem],
                            previous: Optional[QListWidgetItem]) -> None:
        """Handle format selection change."""
        if current is None:
            self._clear_preview()
            return

        gw_format = current.data(Qt.ItemDataRole.UserRole)
        self._selected_format = gw_format

        try:
            session = DiskSession.from_gw_format(gw_format)
            self._current_session = session
            self._update_preview(session)
            self._continue_btn.setEnabled(True)
            self._save_preset_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"Error creating session for {gw_format}: {e}")
            self._clear_preview()
            # Show error to user
            self._preview_name.setText(f"Error loading format: {gw_format}")
            self._preview_name.setStyleSheet("color: #e81123;")  # Red for error

    def _update_preview(self, session: DiskSession) -> None:
        """Update the preview panel with session details."""
        self._preview_name.setText(session.name)
        self._preview_name.setStyleSheet("color: #ffffff;")  # Reset to white
        self._preview_cylinders.setText(str(session.cylinders))
        self._preview_heads.setText(str(session.heads))
        self._preview_sectors.setText(str(session.sectors_per_track))
        self._preview_total.setText(f"{session.total_sectors:,}")
        self._preview_encoding.setText(session.encoding.upper())
        self._preview_data_rate.setText(f"{session.data_rate_kbps} kbps")
        self._preview_rpm.setText(str(session.rpm))

        # Format capacity
        if session.capacity_kb >= 1024:
            capacity_str = f"{session.capacity_mb:.2f} MB".rstrip('0').rstrip('.')
        else:
            capacity_str = f"{session.capacity_kb} KB"
        self._preview_capacity.setText(capacity_str)

        # Update disk visualization
        self._disk_viz.set_geometry(
            session.cylinders,
            session.heads,
            session.sectors_per_track,
            session.disk_size
        )

    def _clear_preview(self) -> None:
        """Clear the preview panel."""
        self._preview_name.setText("Select a format")
        self._preview_cylinders.setText("--")
        self._preview_heads.setText("--")
        self._preview_sectors.setText("--")
        self._preview_total.setText("--")
        self._preview_encoding.setText("--")
        self._preview_data_rate.setText("--")
        self._preview_rpm.setText("--")
        self._preview_capacity.setText("--")
        self._continue_btn.setEnabled(False)
        self._save_preset_btn.setEnabled(False)

    def _on_continue_clicked(self) -> None:
        """Handle continue button click."""
        if self._current_session is None:
            return

        # Set as active session
        self._session_manager.set_active_session(self._current_session)
        self._session_manager.add_to_recent_sessions(self._current_session)

        # Emit signal
        self.session_selected.emit(self._current_session)
        logger.info(f"Session selected: {self._current_session.gw_format}")

    def _on_save_preset_clicked(self) -> None:
        """Handle save preset button click."""
        if self._current_session is None:
            return

        from floppy_formatter.gui.dialogs.session_preset_dialog import SessionPresetDialog

        dialog = SessionPresetDialog(mode="save", session=self._current_session, parent=self)
        if dialog.exec():
            logger.info(f"Preset saved: {dialog.get_preset_name()}")

    def _populate_preset_menu(self) -> None:
        """Populate the preset menu with available presets."""
        self._preset_menu.clear()

        # Built-in presets submenu
        builtin_menu = self._preset_menu.addMenu("Built-in Presets")
        for name, gw_format in self._session_manager.format_registry.get_all_platforms()[:10]:
            pass  # Skip - use builtin presets from session manager instead

        builtin_presets = self._session_manager.get_builtin_preset_names()
        for name in builtin_presets[:15]:  # Limit to 15 entries
            action = builtin_menu.addAction(name)
            action.setData(("builtin", name))
            action.triggered.connect(lambda checked, n=name: self._load_builtin_preset(n))

        # User presets
        self._preset_menu.addSeparator()
        user_presets = self._session_manager.list_presets()

        if user_presets:
            user_menu = self._preset_menu.addMenu("My Presets")
            for name in user_presets:
                action = user_menu.addAction(name)
                action.setData(("user", name))
                action.triggered.connect(lambda checked, n=name: self._load_user_preset(n))
        else:
            no_presets = self._preset_menu.addAction("No saved presets")
            no_presets.setEnabled(False)

    def _load_builtin_preset(self, name: str) -> None:
        """Load a built-in preset."""
        session = self._session_manager.load_builtin_preset(name)
        if session:
            self._apply_session(session)

    def _load_user_preset(self, name: str) -> None:
        """Load a user preset."""
        session = self._session_manager.load_preset(name)
        if session:
            self._apply_session(session)

    def _apply_session(self, session: DiskSession) -> None:
        """Apply a loaded session to the UI."""
        # Select the platform
        self._select_platform(session.platform)

        # Find and select the format in the list
        for i in range(self._format_list.count()):
            item = self._format_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == session.gw_format:
                self._format_list.setCurrentItem(item)
                break

    def set_session(self, session: DiskSession) -> None:
        """
        Set the screen to display a specific session.

        Args:
            session: The session to display
        """
        self._apply_session(session)

    def get_selected_session(self) -> Optional[DiskSession]:
        """
        Get the currently selected session.

        Returns:
            The selected DiskSession or None
        """
        return self._current_session

    def keyPressEvent(self, event) -> None:
        """
        Handle keyboard navigation.

        Supported keys:
            - Enter/Return: Click Continue button (if enabled)
            - Escape: Not handled here (parent handles it)
            - Tab: Standard Qt tab navigation
            - Arrow keys: Navigate lists (handled by QListWidget)
        """
        key = event.key()

        # Enter/Return activates Continue button
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._continue_btn.isEnabled():
                self._on_continue_clicked()
                return

        # Let parent handle other keys
        super().keyPressEvent(event)

    def showEvent(self, event) -> None:
        """Set up focus and tab order when shown."""
        super().showEvent(event)

        # Set up tab order for logical navigation
        self.setTabOrder(self._platform_list, self._size_35_btn)
        self.setTabOrder(self._size_35_btn, self._size_525_btn)
        self.setTabOrder(self._size_525_btn, self._size_8_btn)
        self.setTabOrder(self._size_8_btn, self._size_all_btn)
        self.setTabOrder(self._size_all_btn, self._format_list)
        self.setTabOrder(self._format_list, self._load_preset_btn)
        self.setTabOrder(self._load_preset_btn, self._save_preset_btn)
        self.setTabOrder(self._save_preset_btn, self._continue_btn)

        # Set initial focus to platform list
        self._platform_list.setFocus()
