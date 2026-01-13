"""
Drag and drop functionality for Floppy Workbench.

Provides drop zone overlays, file validation, and drag handling
for disk images and sector maps.

Part of Phase 14: Polish & Professional Touches
"""

import logging
from pathlib import Path
from typing import Optional, Callable, List, Set

from PyQt6.QtCore import Qt, QMimeData, QUrl, pyqtSignal, QTimer, QPoint
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QFrame,
    QApplication,
    QMessageBox,
)
from PyQt6.QtGui import (
    QDragEnterEvent,
    QDragMoveEvent,
    QDragLeaveEvent,
    QDropEvent,
    QDrag,
    QPixmap,
    QPainter,
    QColor,
    QFont,
    QPen,
)


# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Valid File Extensions
# =============================================================================

# Sector-level disk images
SECTOR_IMAGE_EXTENSIONS = {'.img', '.ima', '.dsk', '.bin', '.raw'}

# Flux-level images
FLUX_IMAGE_EXTENSIONS = {'.scp', '.hfe', '.adf', '.ipf'}

# All valid image extensions
ALL_IMAGE_EXTENSIONS = SECTOR_IMAGE_EXTENSIONS | FLUX_IMAGE_EXTENSIONS

# Report files
REPORT_EXTENSIONS = {'.html', '.htm', '.pdf', '.txt'}


def get_file_type(path: Path) -> Optional[str]:
    """
    Determine the file type from its extension.

    Args:
        path: File path

    Returns:
        'sector', 'flux', 'report', or None if unknown
    """
    ext = path.suffix.lower()

    if ext in SECTOR_IMAGE_EXTENSIONS:
        return 'sector'
    elif ext in FLUX_IMAGE_EXTENSIONS:
        return 'flux'
    elif ext in REPORT_EXTENSIONS:
        return 'report'
    return None


def is_valid_image_file(path: Path) -> bool:
    """Check if a file is a valid disk image."""
    return path.suffix.lower() in ALL_IMAGE_EXTENSIONS


def is_valid_sector_image(path: Path) -> bool:
    """Check if a file is a valid sector-level image."""
    return path.suffix.lower() in SECTOR_IMAGE_EXTENSIONS


def is_valid_flux_image(path: Path) -> bool:
    """Check if a file is a valid flux-level image."""
    return path.suffix.lower() in FLUX_IMAGE_EXTENSIONS


# =============================================================================
# Drop Zone Overlay
# =============================================================================

class DropZoneOverlay(QWidget):
    """
    Overlay widget that appears when files are dragged over the application.

    Shows visual feedback for valid/invalid drops and provides
    instructions to the user.
    """

    file_dropped = pyqtSignal(str)  # Emitted with file path when dropped

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._valid_drop = False
        self._file_path: Optional[str] = None
        self._setup_ui()
        self.hide()

    def _setup_ui(self) -> None:
        """Set up the overlay UI."""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Content frame
        self._frame = QFrame()
        self._frame.setObjectName("dropZoneFrame")
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon label (will be set based on validity)
        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedSize(80, 80)
        frame_layout.addWidget(self._icon_label)

        # Message label
        self._message_label = QLabel("Drop disk image to write to disk")
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setObjectName("dropZoneMessage")
        message_font = QFont()
        message_font.setPointSize(14)
        message_font.setBold(True)
        self._message_label.setFont(message_font)
        frame_layout.addWidget(self._message_label)

        # Hint label
        self._hint_label = QLabel("Supported formats: IMG, IMA, SCP, HFE")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setObjectName("dropZoneHint")
        hint_font = QFont()
        hint_font.setPointSize(10)
        self._hint_label.setFont(hint_font)
        frame_layout.addWidget(self._hint_label)

        layout.addWidget(self._frame)

        # Apply styling
        self._update_style()

    def _update_style(self) -> None:
        """Update styling based on validity state."""
        if self._valid_drop:
            border_color = "#4ec9b0"
            bg_color = "rgba(78, 201, 176, 50)"
            text_color = "#4ec9b0"
            icon_text = "+"
        else:
            border_color = "#f14c4c"
            bg_color = "rgba(241, 76, 76, 50)"
            text_color = "#f14c4c"
            icon_text = "X"

        self._frame.setStyleSheet(f"""
            QFrame#dropZoneFrame {{
                background-color: {bg_color};
                border: 3px dashed {border_color};
                border-radius: 20px;
            }}
        """)

        self._message_label.setStyleSheet(f"color: {text_color};")
        self._hint_label.setStyleSheet(f"color: {text_color}; opacity: 0.8;")

        # Create icon
        pixmap = QPixmap(80, 80)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw circle
        pen = QPen(QColor(border_color))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawEllipse(5, 5, 70, 70)

        # Draw icon text
        font = QFont()
        font.setPointSize(40)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(border_color))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, icon_text)

        painter.end()
        self._icon_label.setPixmap(pixmap)

    def set_valid(self, valid: bool, filename: str = "") -> None:
        """
        Set the validity state of the drop.

        Args:
            valid: Whether the current drag is valid
            filename: Name of the file being dragged
        """
        self._valid_drop = valid

        if valid:
            self._message_label.setText(f"Drop to write: {filename}")
            self._hint_label.setText("Release to start write operation")
        else:
            self._message_label.setText("Invalid file type")
            self._hint_label.setText("Supported formats: IMG, IMA, SCP, HFE")

        self._update_style()

    def show_overlay(self) -> None:
        """Show the overlay and resize to parent."""
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()

    def hide_overlay(self) -> None:
        """Hide the overlay."""
        self.hide()
        self._file_path = None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = Path(urls[0].toLocalFile())
                if is_valid_image_file(path):
                    self.set_valid(True, path.name)
                    self._file_path = str(path)
                    event.acceptProposedAction()
                    return
                else:
                    self.set_valid(False)

        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Handle drag move."""
        if self._valid_drop:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """Handle drag leave."""
        self.hide_overlay()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle file drop."""
        if self._valid_drop and self._file_path:
            event.acceptProposedAction()
            self.file_dropped.emit(self._file_path)
        else:
            event.ignore()

        self.hide_overlay()


# =============================================================================
# Drag and Drop Handler Mixin
# =============================================================================

class DragDropHandler:
    """
    Mixin class providing drag and drop handling for widgets.

    Add this to a QWidget subclass to enable drag and drop support
    for disk images.
    """

    # These should be overridden by the actual widget class
    _drop_overlay: Optional[DropZoneOverlay] = None
    _on_image_drop_callback: Optional[Callable[[str], None]] = None

    def setup_drag_drop(
        self,
        on_image_drop: Optional[Callable[[str], None]] = None
    ) -> None:
        """
        Set up drag and drop handling.

        Args:
            on_image_drop: Callback function when an image file is dropped
        """
        self._on_image_drop_callback = on_image_drop

        # Create drop overlay
        self._drop_overlay = DropZoneOverlay(self)
        self._drop_overlay.file_dropped.connect(self._handle_image_drop)

        # Enable drops on this widget
        self.setAcceptDrops(True)

    def _handle_image_drop(self, filepath: str) -> None:
        """
        Handle a dropped image file.

        Args:
            filepath: Path to the dropped file
        """
        logger.info(f"Image file dropped: {filepath}")

        path = Path(filepath)
        file_type = get_file_type(path)

        # Show confirmation dialog
        msg = QMessageBox(self)
        msg.setWindowTitle("Write Image to Disk")
        msg.setText(f"Write '{path.name}' to disk?")

        if file_type == 'flux':
            msg.setInformativeText(
                "This is a flux-level image. It will be written "
                "directly to the disk preserving exact timing data."
            )
        else:
            msg.setInformativeText(
                "This will overwrite all data on the disk with the contents "
                "of this image file."
            )

        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)

        if msg.exec() == QMessageBox.StandardButton.Yes:
            if self._on_image_drop_callback:
                self._on_image_drop_callback(filepath)

    def handle_drag_enter(self, event: QDragEnterEvent) -> bool:
        """
        Handle drag enter event.

        Returns True if the event was handled.
        """
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = Path(urls[0].toLocalFile())
                if is_valid_image_file(path):
                    if self._drop_overlay:
                        self._drop_overlay.set_valid(True, path.name)
                        self._drop_overlay.show_overlay()
                    event.acceptProposedAction()
                    return True
                else:
                    if self._drop_overlay:
                        self._drop_overlay.set_valid(False)
                        self._drop_overlay.show_overlay()
                    event.ignore()
                    return True

        return False

    def handle_drag_leave(self, event: QDragLeaveEvent) -> bool:
        """
        Handle drag leave event.

        Returns True if the event was handled.
        """
        if self._drop_overlay:
            self._drop_overlay.hide_overlay()
        return True

    def handle_drop(self, event: QDropEvent) -> bool:
        """
        Handle drop event.

        Returns True if the event was handled.
        """
        if self._drop_overlay:
            self._drop_overlay.hide_overlay()

        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = Path(urls[0].toLocalFile())
                if is_valid_image_file(path):
                    event.acceptProposedAction()
                    self._handle_image_drop(str(path))
                    return True

        event.ignore()
        return True


# =============================================================================
# Sector Map Drag Source
# =============================================================================

class SectorMapDragSource:
    """
    Helper for making sector maps draggable.

    Allows users to drag the sector map image to save as PNG.
    """

    @staticmethod
    def start_drag(widget: QWidget, pixmap: QPixmap) -> None:
        """
        Start a drag operation with a sector map image.

        Args:
            widget: Source widget for the drag
            pixmap: The sector map image to drag
        """
        drag = QDrag(widget)
        mime_data = QMimeData()

        # Set the image as drag data
        mime_data.setImageData(pixmap.toImage())

        # Create a smaller preview pixmap
        preview_size = 100
        preview = pixmap.scaled(
            preview_size, preview_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        drag.setMimeData(mime_data)
        drag.setPixmap(preview)
        drag.setHotSpot(QPoint(preview.width() // 2, preview.height() // 2))

        # Execute drag
        result = drag.exec(Qt.DropAction.CopyAction)

        logger.debug(f"Sector map drag completed with result: {result}")

    @staticmethod
    def create_drag_pixmap(
        sector_map_widget,
        size: int = 400
    ) -> QPixmap:
        """
        Create a pixmap from a sector map widget for dragging.

        Args:
            sector_map_widget: The CircularSectorMap widget
            size: Size of the output pixmap

        Returns:
            QPixmap of the sector map
        """
        # Render the widget to a pixmap
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        # Use the widget's render method if available
        if hasattr(sector_map_widget, 'render_to_pixmap'):
            return sector_map_widget.render_to_pixmap(size)

        # Fallback: grab the widget
        return sector_map_widget.grab()


# =============================================================================
# File Drop Target Widget
# =============================================================================

class FileDropTarget(QFrame):
    """
    A visual drop target widget for files.

    Displays a bordered area that accepts file drops and
    provides visual feedback.
    """

    file_dropped = pyqtSignal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        valid_extensions: Optional[Set[str]] = None,
        message: str = "Drop file here"
    ):
        super().__init__(parent)
        self._valid_extensions = valid_extensions or ALL_IMAGE_EXTENSIONS
        self._message = message
        self._hover = False
        self._valid = True
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        self.setAcceptDrops(True)
        self.setMinimumSize(200, 100)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(self._message)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._update_style()

    def _update_style(self) -> None:
        """Update styling based on state."""
        if self._hover:
            if self._valid:
                border_color = "#4ec9b0"
                bg_color = "rgba(78, 201, 176, 30)"
                text_color = "#4ec9b0"
            else:
                border_color = "#f14c4c"
                bg_color = "rgba(241, 76, 76, 30)"
                text_color = "#f14c4c"
        else:
            border_color = "#6c6c6c"
            bg_color = "rgba(60, 60, 60, 50)"
            text_color = "#cccccc"

        self.setStyleSheet(f"""
            FileDropTarget {{
                background-color: {bg_color};
                border: 2px dashed {border_color};
                border-radius: 8px;
            }}
            QLabel {{
                color: {text_color};
            }}
        """)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter."""
        self._hover = True

        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = Path(urls[0].toLocalFile())
                ext = path.suffix.lower()
                self._valid = ext in self._valid_extensions

                if self._valid:
                    self._label.setText(f"Drop: {path.name}")
                else:
                    self._label.setText("Invalid file type")

                self._update_style()
                event.acceptProposedAction()
                return

        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Handle drag move."""
        if self._valid:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """Handle drag leave."""
        self._hover = False
        self._label.setText(self._message)
        self._update_style()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop."""
        self._hover = False
        self._label.setText(self._message)
        self._update_style()

        if event.mimeData().hasUrls() and self._valid:
            urls = event.mimeData().urls()
            if urls:
                filepath = urls[0].toLocalFile()
                event.acceptProposedAction()
                self.file_dropped.emit(filepath)
                return

        event.ignore()


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Constants
    'SECTOR_IMAGE_EXTENSIONS',
    'FLUX_IMAGE_EXTENSIONS',
    'ALL_IMAGE_EXTENSIONS',
    'REPORT_EXTENSIONS',

    # Functions
    'get_file_type',
    'is_valid_image_file',
    'is_valid_sector_image',
    'is_valid_flux_image',

    # Classes
    'DropZoneOverlay',
    'DragDropHandler',
    'SectorMapDragSource',
    'FileDropTarget',
]
