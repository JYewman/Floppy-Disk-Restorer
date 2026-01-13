"""
Loading skeleton widgets for Floppy Workbench.

Provides animated placeholder widgets that display during data loading,
giving users visual feedback that content is being prepared.

Part of Phase 14: Polish & Professional Touches
"""

import logging
from typing import Optional, List

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    pyqtProperty,
    QRect,
    QSize,
)
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QGridLayout,
    QSizePolicy,
)
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QLinearGradient,
    QBrush,
    QPen,
    QPaintEvent,
)


# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Skeleton Base Widget
# =============================================================================

class SkeletonWidget(QWidget):
    """
    Base class for skeleton loading placeholders.

    Displays an animated shimmer effect to indicate loading state.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        shape: str = "rectangle",
        corner_radius: int = 4
    ):
        """
        Initialize skeleton widget.

        Args:
            parent: Parent widget
            shape: Shape type ('rectangle', 'circle', 'rounded')
            corner_radius: Corner radius for rounded shapes
        """
        super().__init__(parent)
        self._shape = shape
        self._corner_radius = corner_radius
        self._shimmer_position = 0.0
        self._base_color = QColor("#3c3c3c")
        self._shimmer_color = QColor("#505050")

        # Animation
        self._animation = QPropertyAnimation(self, b"shimmerPosition", self)
        self._animation.setDuration(1500)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setLoopCount(-1)  # Infinite loop
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)

        self.setMinimumSize(20, 20)

    def start_animation(self) -> None:
        """Start the shimmer animation."""
        self._animation.start()

    def stop_animation(self) -> None:
        """Stop the shimmer animation."""
        self._animation.stop()

    def showEvent(self, event) -> None:
        """Start animation when shown."""
        super().showEvent(event)
        self.start_animation()

    def hideEvent(self, event) -> None:
        """Stop animation when hidden."""
        super().hideEvent(event)
        self.stop_animation()

    @pyqtProperty(float)
    def shimmerPosition(self) -> float:
        """Get shimmer position (0.0 to 1.0)."""
        return self._shimmer_position

    @shimmerPosition.setter
    def shimmerPosition(self, value: float) -> None:
        """Set shimmer position and trigger repaint."""
        self._shimmer_position = value
        self.update()

    def set_colors(self, base: QColor, shimmer: QColor) -> None:
        """Set the base and shimmer colors."""
        self._base_color = base
        self._shimmer_color = shimmer
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the skeleton with shimmer effect."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Create gradient for shimmer effect
        gradient = QLinearGradient(0, 0, self.width(), 0)

        # Position the shimmer highlight
        shimmer_width = 0.3  # Width of shimmer as fraction of widget
        shimmer_start = self._shimmer_position - shimmer_width
        shimmer_end = self._shimmer_position + shimmer_width

        gradient.setColorAt(0.0, self._base_color)
        gradient.setColorAt(max(0.0, shimmer_start), self._base_color)
        gradient.setColorAt(max(0.0, min(1.0, self._shimmer_position)), self._shimmer_color)
        gradient.setColorAt(min(1.0, shimmer_end), self._base_color)
        gradient.setColorAt(1.0, self._base_color)

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)

        # Draw shape
        rect = self.rect()
        if self._shape == "circle":
            size = min(rect.width(), rect.height())
            x = (rect.width() - size) // 2
            y = (rect.height() - size) // 2
            painter.drawEllipse(x, y, size, size)
        elif self._shape == "rounded":
            painter.drawRoundedRect(rect, self._corner_radius, self._corner_radius)
        else:
            painter.drawRect(rect)


# =============================================================================
# Skeleton Text
# =============================================================================

class SkeletonText(QWidget):
    """
    Skeleton placeholder that mimics text lines.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        line_count: int = 3,
        line_height: int = 16,
        line_spacing: int = 8,
        varying_width: bool = True
    ):
        """
        Initialize skeleton text.

        Args:
            parent: Parent widget
            line_count: Number of text lines to show
            line_height: Height of each line
            line_spacing: Spacing between lines
            varying_width: Whether lines should have varying widths
        """
        super().__init__(parent)
        self._line_count = line_count
        self._line_height = line_height
        self._line_spacing = line_spacing
        self._varying_width = varying_width
        self._shimmer_position = 0.0

        # Calculate size
        height = line_count * line_height + (line_count - 1) * line_spacing
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Animation
        self._animation = QPropertyAnimation(self, b"shimmerPosition", self)
        self._animation.setDuration(1500)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)

    def start_animation(self) -> None:
        """Start the shimmer animation."""
        self._animation.start()

    def stop_animation(self) -> None:
        """Stop the shimmer animation."""
        self._animation.stop()

    def showEvent(self, event) -> None:
        """Start animation when shown."""
        super().showEvent(event)
        self.start_animation()

    def hideEvent(self, event) -> None:
        """Stop animation when hidden."""
        super().hideEvent(event)
        self.stop_animation()

    @pyqtProperty(float)
    def shimmerPosition(self) -> float:
        """Get shimmer position."""
        return self._shimmer_position

    @shimmerPosition.setter
    def shimmerPosition(self, value: float) -> None:
        """Set shimmer position."""
        self._shimmer_position = value
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the skeleton text lines."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        base_color = QColor("#3c3c3c")
        shimmer_color = QColor("#505050")

        # Line widths (varying if enabled)
        widths = [1.0, 0.9, 0.75, 0.85, 0.6, 0.95, 0.7]

        for i in range(self._line_count):
            y = i * (self._line_height + self._line_spacing)

            # Calculate line width
            if self._varying_width:
                width_factor = widths[i % len(widths)]
            else:
                width_factor = 1.0

            line_width = int(self.width() * width_factor)

            # Create gradient for this line
            gradient = QLinearGradient(0, 0, self.width(), 0)

            shimmer_width = 0.3
            shimmer_start = self._shimmer_position - shimmer_width
            shimmer_end = self._shimmer_position + shimmer_width

            gradient.setColorAt(0.0, base_color)
            gradient.setColorAt(max(0.0, shimmer_start), base_color)
            gradient.setColorAt(max(0.0, min(1.0, self._shimmer_position)), shimmer_color)
            gradient.setColorAt(min(1.0, shimmer_end), base_color)
            gradient.setColorAt(1.0, base_color)

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, y, line_width, self._line_height, 3, 3)


# =============================================================================
# Skeleton Card
# =============================================================================

class SkeletonCard(QFrame):
    """
    Skeleton placeholder that mimics a card/panel with header, body, footer.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        show_header: bool = True,
        show_body: bool = True,
        show_footer: bool = True,
        body_lines: int = 3
    ):
        """
        Initialize skeleton card.

        Args:
            parent: Parent widget
            show_header: Show header section
            show_body: Show body section
            show_footer: Show footer section
            body_lines: Number of lines in body
        """
        super().__init__(parent)
        self._skeletons: List[QWidget] = []
        self._setup_ui(show_header, show_body, show_footer, body_lines)

    def _setup_ui(
        self,
        show_header: bool,
        show_body: bool,
        show_footer: bool,
        body_lines: int
    ) -> None:
        """Set up the card UI."""
        self.setStyleSheet("""
            SkeletonCard {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        if show_header:
            header = SkeletonWidget(self, shape="rounded", corner_radius=4)
            header.setFixedHeight(24)
            layout.addWidget(header)
            self._skeletons.append(header)

        if show_body:
            body = SkeletonText(self, line_count=body_lines)
            layout.addWidget(body)
            self._skeletons.append(body)

        if show_footer:
            footer_layout = QHBoxLayout()
            footer_layout.setSpacing(8)

            for width in [80, 60]:
                btn = SkeletonWidget(self, shape="rounded", corner_radius=4)
                btn.setFixedSize(width, 28)
                footer_layout.addWidget(btn)
                self._skeletons.append(btn)

            footer_layout.addStretch()
            layout.addLayout(footer_layout)

    def start_animation(self) -> None:
        """Start all skeleton animations."""
        for skeleton in self._skeletons:
            if hasattr(skeleton, 'start_animation'):
                skeleton.start_animation()

    def stop_animation(self) -> None:
        """Stop all skeleton animations."""
        for skeleton in self._skeletons:
            if hasattr(skeleton, 'stop_animation'):
                skeleton.stop_animation()


# =============================================================================
# Skeleton Table
# =============================================================================

class SkeletonTable(QWidget):
    """
    Skeleton placeholder that mimics a table with rows and columns.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        rows: int = 5,
        columns: int = 4,
        header_height: int = 32,
        row_height: int = 28,
        row_spacing: int = 4
    ):
        """
        Initialize skeleton table.

        Args:
            parent: Parent widget
            rows: Number of data rows
            columns: Number of columns
            header_height: Height of header row
            row_height: Height of data rows
            row_spacing: Spacing between rows
        """
        super().__init__(parent)
        self._rows = rows
        self._columns = columns
        self._header_height = header_height
        self._row_height = row_height
        self._row_spacing = row_spacing
        self._skeletons: List[SkeletonWidget] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the table UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._row_spacing)

        # Header row (darker)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        for _ in range(self._columns):
            cell = SkeletonWidget(self, shape="rounded", corner_radius=3)
            cell.setFixedHeight(self._header_height)
            cell.set_colors(QColor("#2d2d30"), QColor("#454548"))
            header_layout.addWidget(cell)
            self._skeletons.append(cell)

        layout.addLayout(header_layout)

        # Data rows
        for _ in range(self._rows):
            row_layout = QHBoxLayout()
            row_layout.setSpacing(8)

            for _ in range(self._columns):
                cell = SkeletonWidget(self, shape="rounded", corner_radius=3)
                cell.setFixedHeight(self._row_height)
                row_layout.addWidget(cell)
                self._skeletons.append(cell)

            layout.addLayout(row_layout)

    def start_animation(self) -> None:
        """Start all skeleton animations."""
        for skeleton in self._skeletons:
            skeleton.start_animation()

    def stop_animation(self) -> None:
        """Stop all skeleton animations."""
        for skeleton in self._skeletons:
            skeleton.stop_animation()


# =============================================================================
# Skeleton Sector Map
# =============================================================================

class SkeletonSectorMap(QWidget):
    """
    Circular skeleton placeholder for sector map visualization.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        size: int = 300
    ):
        """
        Initialize skeleton sector map.

        Args:
            parent: Parent widget
            size: Size of the circular map
        """
        super().__init__(parent)
        self._size = size
        self._shimmer_angle = 0.0

        self.setFixedSize(size, size)

        # Animation
        self._animation = QPropertyAnimation(self, b"shimmerAngle", self)
        self._animation.setDuration(2000)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(360.0)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)

    def start_animation(self) -> None:
        """Start the shimmer animation."""
        self._animation.start()

    def stop_animation(self) -> None:
        """Stop the shimmer animation."""
        self._animation.stop()

    def showEvent(self, event) -> None:
        """Start animation when shown."""
        super().showEvent(event)
        self.start_animation()

    def hideEvent(self, event) -> None:
        """Stop animation when hidden."""
        super().hideEvent(event)
        self.stop_animation()

    @pyqtProperty(float)
    def shimmerAngle(self) -> float:
        """Get shimmer angle."""
        return self._shimmer_angle

    @shimmerAngle.setter
    def shimmerAngle(self, value: float) -> None:
        """Set shimmer angle."""
        self._shimmer_angle = value
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the circular skeleton."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() // 2
        center_y = self.height() // 2
        max_radius = min(center_x, center_y) - 5

        base_color = QColor("#3c3c3c")
        shimmer_color = QColor("#505050")

        # Draw concentric rings
        num_rings = 8
        ring_width = max_radius / num_rings

        import math
        shimmer_rad = math.radians(self._shimmer_angle)

        for i in range(num_rings):
            inner_radius = i * ring_width
            outer_radius = (i + 1) * ring_width

            # Draw ring segments
            num_segments = 36
            segment_angle = 360 / num_segments

            for j in range(num_segments):
                angle = j * segment_angle
                angle_rad = math.radians(angle)

                # Calculate distance from shimmer position
                angle_diff = abs(angle_rad - shimmer_rad)
                if angle_diff > math.pi:
                    angle_diff = 2 * math.pi - angle_diff

                # Shimmer falloff
                shimmer_factor = max(0, 1 - angle_diff / (math.pi / 4))
                color = QColor()
                color.setRedF(
                    base_color.redF() + (shimmer_color.redF() - base_color.redF()) * shimmer_factor
                )
                color.setGreenF(
                    base_color.greenF() + (shimmer_color.greenF() - base_color.greenF()) * shimmer_factor
                )
                color.setBlueF(
                    base_color.blueF() + (shimmer_color.blueF() - base_color.blueF()) * shimmer_factor
                )

                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor("#2d2d30"), 1))

                # Draw pie segment
                rect = QRect(
                    int(center_x - outer_radius),
                    int(center_y - outer_radius),
                    int(outer_radius * 2),
                    int(outer_radius * 2)
                )
                painter.drawPie(rect, int(angle * 16), int(segment_angle * 16))

        # Draw center circle
        painter.setBrush(QBrush(QColor("#1e1e1e")))
        painter.setPen(QPen(QColor("#3c3c3c"), 2))
        center_radius = max_radius * 0.15
        painter.drawEllipse(
            int(center_x - center_radius),
            int(center_y - center_radius),
            int(center_radius * 2),
            int(center_radius * 2)
        )


# =============================================================================
# Loading State Manager
# =============================================================================

class LoadingStateManager:
    """
    Helper for managing loading states in the UI.

    Shows skeleton placeholders while content loads, then
    transitions to real content.
    """

    @staticmethod
    def show_loading(
        container: QWidget,
        skeleton: QWidget
    ) -> QWidget:
        """
        Show loading skeleton in a container.

        Args:
            container: Container widget
            skeleton: Skeleton widget to show

        Returns:
            The skeleton widget
        """
        # Hide existing children
        for child in container.findChildren(QWidget):
            if child != skeleton:
                child.hide()

        # Add and show skeleton
        if skeleton.parent() != container:
            skeleton.setParent(container)

        # Try to add to layout
        layout = container.layout()
        if layout:
            layout.addWidget(skeleton)

        skeleton.show()

        if hasattr(skeleton, 'start_animation'):
            skeleton.start_animation()

        return skeleton

    @staticmethod
    def hide_loading(
        skeleton: QWidget,
        real_widget: QWidget,
        animate: bool = True
    ) -> None:
        """
        Hide loading skeleton and show real content.

        Args:
            skeleton: Skeleton widget to hide
            real_widget: Real content widget to show
            animate: Whether to animate the transition
        """
        if hasattr(skeleton, 'stop_animation'):
            skeleton.stop_animation()

        if animate:
            try:
                from floppy_formatter.gui.utils.animations import FadeAnimation

                # Fade out skeleton
                fade = FadeAnimation()
                fade.fade_out(skeleton, duration_ms=200, hide_on_finish=True)

                # Fade in real widget after short delay
                QTimer.singleShot(100, lambda: _show_real_widget(real_widget))

            except ImportError:
                skeleton.hide()
                real_widget.show()
        else:
            skeleton.hide()
            real_widget.show()


def _show_real_widget(widget: QWidget) -> None:
    """Helper to show real widget with fade."""
    try:
        from floppy_formatter.gui.utils.animations import FadeAnimation
        fade = FadeAnimation()
        fade.fade_in(widget, duration_ms=200)
    except ImportError:
        widget.show()


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'SkeletonWidget',
    'SkeletonText',
    'SkeletonCard',
    'SkeletonTable',
    'SkeletonSectorMap',
    'LoadingStateManager',
]
