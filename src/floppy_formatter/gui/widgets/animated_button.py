"""
Animated button widgets for Floppy Workbench.

Provides interactive buttons with micro-animations for hover,
press, and feedback states.

Part of Phase 14: Polish & Professional Touches
"""

import logging
from typing import Optional

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    pyqtProperty,
    pyqtSignal,
    QPoint,
    QSize,
    QRect,
    QRectF,
)
from PyQt6.QtWidgets import (
    QPushButton,
    QWidget,
)
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QIcon,
    QPaintEvent,
    QMouseEvent,
    QEnterEvent,
    QPixmap,
    QRadialGradient,
)


# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Animated Button
# =============================================================================

class AnimatedButton(QPushButton):
    """
    Push button with hover and press animations.

    Features:
    - Subtle scale-up on hover (1.02x)
    - Scale-down on press (0.98x)
    - Spring-back animation on release
    - Ripple effect on click (material design style)
    - Respects animation settings
    """

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        enable_ripple: bool = True
    ):
        """
        Initialize animated button.

        Args:
            text: Button text
            parent: Parent widget
            enable_ripple: Whether to show ripple effect on click
        """
        super().__init__(text, parent)
        self._enable_ripple = enable_ripple
        self._hover_scale = 1.0
        self._press_scale = 1.0
        self._ripple_radius = 0.0
        self._ripple_opacity = 0.0
        self._ripple_center = QPoint(0, 0)
        self._original_geometry: Optional[QRect] = None

        # Hover animation
        self._hover_animation = QPropertyAnimation(self, b"hoverScale", self)
        self._hover_animation.setDuration(150)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Press animation
        self._press_animation = QPropertyAnimation(self, b"pressScale", self)
        self._press_animation.setDuration(100)
        self._press_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Ripple animation
        self._ripple_radius_animation = QPropertyAnimation(self, b"rippleRadius", self)
        self._ripple_radius_animation.setDuration(400)
        self._ripple_radius_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._ripple_opacity_animation = QPropertyAnimation(self, b"rippleOpacity", self)
        self._ripple_opacity_animation.setDuration(400)
        self._ripple_opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Default styling
        self.setMinimumHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _animations_enabled(self) -> bool:
        """Check if animations are enabled in settings."""
        try:
            from floppy_formatter.gui.utils.animations import animations_enabled
            return animations_enabled()
        except ImportError:
            return True

    @pyqtProperty(float)
    def hoverScale(self) -> float:
        return self._hover_scale

    @hoverScale.setter
    def hoverScale(self, value: float) -> None:
        self._hover_scale = value
        self.update()

    @pyqtProperty(float)
    def pressScale(self) -> float:
        return self._press_scale

    @pressScale.setter
    def pressScale(self, value: float) -> None:
        self._press_scale = value
        self.update()

    @pyqtProperty(float)
    def rippleRadius(self) -> float:
        return self._ripple_radius

    @rippleRadius.setter
    def rippleRadius(self, value: float) -> None:
        self._ripple_radius = value
        self.update()

    @pyqtProperty(float)
    def rippleOpacity(self) -> float:
        return self._ripple_opacity

    @rippleOpacity.setter
    def rippleOpacity(self, value: float) -> None:
        self._ripple_opacity = value
        self.update()

    def enterEvent(self, event: QEnterEvent) -> None:
        """Handle mouse enter."""
        super().enterEvent(event)
        if self._animations_enabled() and self.isEnabled():
            self._hover_animation.stop()
            self._hover_animation.setStartValue(self._hover_scale)
            self._hover_animation.setEndValue(1.02)
            self._hover_animation.start()

    def leaveEvent(self, event) -> None:
        """Handle mouse leave."""
        super().leaveEvent(event)
        if self._animations_enabled():
            self._hover_animation.stop()
            self._hover_animation.setStartValue(self._hover_scale)
            self._hover_animation.setEndValue(1.0)
            self._hover_animation.start()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press."""
        super().mousePressEvent(event)
        if self._animations_enabled() and self.isEnabled():
            self._press_animation.stop()
            self._press_animation.setStartValue(self._press_scale)
            self._press_animation.setEndValue(0.98)
            self._press_animation.start()

            # Start ripple
            if self._enable_ripple:
                self._ripple_center = event.pos()
                self._start_ripple()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        super().mouseReleaseEvent(event)
        if self._animations_enabled():
            self._press_animation.stop()
            self._press_animation.setStartValue(self._press_scale)
            self._press_animation.setEndValue(1.0)
            self._press_animation.setEasingCurve(QEasingCurve.Type.OutBack)
            self._press_animation.start()

    def _start_ripple(self) -> None:
        """Start the ripple effect."""
        # Calculate max radius (diagonal of button)
        max_radius = (self.width() ** 2 + self.height() ** 2) ** 0.5

        self._ripple_radius = 0
        self._ripple_opacity = 0.3

        # Radius animation
        self._ripple_radius_animation.stop()
        self._ripple_radius_animation.setStartValue(0)
        self._ripple_radius_animation.setEndValue(max_radius)
        self._ripple_radius_animation.start()

        # Opacity animation (fade out)
        self._ripple_opacity_animation.stop()
        self._ripple_opacity_animation.setStartValue(0.3)
        self._ripple_opacity_animation.setEndValue(0.0)
        self._ripple_opacity_animation.start()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Custom paint with scale and ripple effects."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate scaled rect
        scale = self._hover_scale * self._press_scale
        if abs(scale - 1.0) > 0.001:
            center = self.rect().center()
            painter.translate(center)
            painter.scale(scale, scale)
            painter.translate(-center)

        # Draw button background
        rect = self.rect()
        radius = 4

        # Background color
        if not self.isEnabled():
            bg_color = QColor("#2d2d30")
            text_color = QColor("#6c6c6c")
        elif self.isDown():
            bg_color = QColor("#094771")
            text_color = QColor("#ffffff")
        elif self.underMouse():
            bg_color = QColor("#1177bb")
            text_color = QColor("#ffffff")
        else:
            bg_color = QColor("#0e639c")
            text_color = QColor("#ffffff")

        # Check if this is a secondary/outline button via property
        if self.property("secondary"):
            if not self.isEnabled():
                bg_color = QColor("#2d2d30")
                border_color = QColor("#3c3c3c")
                text_color = QColor("#6c6c6c")
            elif self.isDown():
                bg_color = QColor("#2d2d30")
                border_color = QColor("#6c6c6c")
                text_color = QColor("#ffffff")
            elif self.underMouse():
                bg_color = QColor("#4e5157")
                border_color = QColor("#858585")
                text_color = QColor("#ffffff")
            else:
                bg_color = QColor("#3a3d41")
                border_color = QColor("#6c6c6c")
                text_color = QColor("#ffffff")

            painter.setBrush(QBrush(bg_color))
            painter.setPen(QPen(border_color, 1))
        else:
            painter.setBrush(QBrush(bg_color))
            painter.setPen(Qt.PenStyle.NoPen)

        painter.drawRoundedRect(rect, radius, radius)

        # Draw ripple
        if self._ripple_radius > 0 and self._ripple_opacity > 0:
            ripple_color = QColor(255, 255, 255, int(self._ripple_opacity * 255))
            gradient = QRadialGradient(
                self._ripple_center.x(),
                self._ripple_center.y(),
                self._ripple_radius
            )
            gradient.setColorAt(0, ripple_color)
            gradient.setColorAt(1, QColor(255, 255, 255, 0))

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, radius, radius)

        # Draw text
        painter.setPen(text_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())

        # Draw icon if set
        if not self.icon().isNull():
            icon_size = self.iconSize()
            icon_pixmap = self.icon().pixmap(icon_size)

            # Position icon
            text_width = painter.fontMetrics().horizontalAdvance(self.text())
            total_width = icon_size.width() + 8 + text_width
            icon_x = (self.width() - total_width) // 2
            icon_y = (self.height() - icon_size.height()) // 2

            painter.drawPixmap(icon_x, icon_y, icon_pixmap)


# =============================================================================
# Icon Button
# =============================================================================

class IconButton(QPushButton):
    """
    Circular button with icon only.

    Features:
    - Circular shape
    - Hover background color
    - Tooltip display
    """

    def __init__(
        self,
        icon: Optional[QIcon] = None,
        size: int = 32,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize icon button.

        Args:
            icon: Button icon
            size: Button size (diameter)
            parent: Parent widget
        """
        super().__init__(parent)
        self._size = size
        self._hover = False
        self._pressed = False

        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if icon:
            self.setIcon(icon)
            self.setIconSize(QSize(size - 12, size - 12))

    def enterEvent(self, event: QEnterEvent) -> None:
        """Handle mouse enter."""
        super().enterEvent(event)
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        """Handle mouse leave."""
        super().leaveEvent(event)
        self._hover = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press."""
        super().mousePressEvent(event)
        self._pressed = True
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        super().mouseReleaseEvent(event)
        self._pressed = False
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the circular button."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # Background
        if not self.isEnabled():
            bg_color = QColor("#2d2d30")
        elif self._pressed:
            bg_color = QColor("#2d2d30")
        elif self._hover:
            bg_color = QColor("#3a3d41")
        else:
            bg_color = Qt.GlobalColor.transparent

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)

        # Icon
        if not self.icon().isNull():
            icon_size = self.iconSize()
            icon_pixmap = self.icon().pixmap(
                icon_size,
                QIcon.Mode.Disabled if not self.isEnabled() else QIcon.Mode.Normal
            )
            icon_x = (rect.width() - icon_size.width()) // 2
            icon_y = (rect.height() - icon_size.height()) // 2
            painter.drawPixmap(icon_x, icon_y, icon_pixmap)


# =============================================================================
# Operation Button
# =============================================================================

class OperationButton(QWidget):
    """
    Large button with icon above text for toolbar operations.

    Features:
    - Icon above text layout
    - Loading spinner overlay
    - Success/error flash animations
    """

    clicked = pyqtSignal()

    def __init__(
        self,
        text: str,
        icon: Optional[QIcon] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize operation button.

        Args:
            text: Button text
            icon: Button icon
            parent: Parent widget
        """
        super().__init__(parent)
        self._text = text
        self._icon = icon
        self._hover = False
        self._pressed = False
        self._loading = False
        self._loading_angle = 0
        self._flash_color: Optional[QColor] = None
        self._flash_opacity = 0.0
        self._enabled = True

        self.setFixedSize(80, 70)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Loading animation timer
        self._loading_timer = QTimer(self)
        self._loading_timer.timeout.connect(self._update_loading)

        # Flash animation
        self._flash_animation = QPropertyAnimation(self, b"flashOpacity", self)
        self._flash_animation.setDuration(500)
        self._flash_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def setEnabled(self, enabled: bool) -> None:
        """Set enabled state."""
        self._enabled = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ForbiddenCursor)
        self.update()

    def isEnabled(self) -> bool:
        """Check if enabled."""
        return self._enabled

    @pyqtProperty(float)
    def flashOpacity(self) -> float:
        return self._flash_opacity

    @flashOpacity.setter
    def flashOpacity(self, value: float) -> None:
        self._flash_opacity = value
        self.update()

    def set_loading(self, loading: bool) -> None:
        """
        Set loading state.

        Args:
            loading: Whether operation is running
        """
        self._loading = loading
        if loading:
            self._loading_timer.start(50)
        else:
            self._loading_timer.stop()
        self.update()

    def _update_loading(self) -> None:
        """Update loading spinner angle."""
        self._loading_angle = (self._loading_angle + 10) % 360
        self.update()

    def flash_success(self) -> None:
        """Flash with success color."""
        self._flash_color = QColor("#4ec9b0")
        self._flash_animation.stop()
        self._flash_animation.setStartValue(0.5)
        self._flash_animation.setEndValue(0.0)
        self._flash_animation.start()

    def flash_error(self) -> None:
        """Flash with error color."""
        self._flash_color = QColor("#f14c4c")
        self._flash_animation.stop()
        self._flash_animation.setStartValue(0.5)
        self._flash_animation.setEndValue(0.0)
        self._flash_animation.start()

    def enterEvent(self, event: QEnterEvent) -> None:
        """Handle mouse enter."""
        if self._enabled:
            self._hover = True
            self.update()

    def leaveEvent(self, event) -> None:
        """Handle mouse leave."""
        self._hover = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press."""
        if self._enabled and event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        was_pressed = self._pressed
        self._pressed = False
        self.update()

        if was_pressed and self._enabled and self.rect().contains(event.pos()):
            self.clicked.emit()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the operation button."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        radius = 6

        # Background
        if not self._enabled:
            bg_color = QColor("#2d2d30")
            text_color = QColor("#6c6c6c")
            icon_opacity = 0.3
        elif self._pressed:
            bg_color = QColor("#1e1e1e")
            text_color = QColor("#ffffff")
            icon_opacity = 1.0
        elif self._hover:
            bg_color = QColor("#3a3d41")
            text_color = QColor("#ffffff")
            icon_opacity = 1.0
        else:
            bg_color = QColor("#252526")
            text_color = QColor("#cccccc")
            icon_opacity = 0.8

        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(QColor("#3c3c3c"), 1))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)

        # Flash overlay
        if self._flash_color and self._flash_opacity > 0:
            flash = QColor(self._flash_color)
            flash.setAlphaF(self._flash_opacity)
            painter.setBrush(QBrush(flash))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)

        # Icon
        icon_size = 28
        icon_y = 10

        if self._loading:
            # Draw loading spinner
            spinner_rect = QRectF(
                (rect.width() - icon_size) / 2,
                icon_y,
                icon_size,
                icon_size
            )

            painter.setPen(QPen(QColor("#0e639c"), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            start_angle = self._loading_angle * 16
            span_angle = 270 * 16
            painter.drawArc(spinner_rect, start_angle, span_angle)

        elif self._icon:
            icon_pixmap = self._icon.pixmap(QSize(icon_size, icon_size))

            if icon_opacity < 1.0:
                effect_pixmap = QPixmap(icon_pixmap.size())
                effect_pixmap.fill(Qt.GlobalColor.transparent)
                effect_painter = QPainter(effect_pixmap)
                effect_painter.setOpacity(icon_opacity)
                effect_painter.drawPixmap(0, 0, icon_pixmap)
                effect_painter.end()
                icon_pixmap = effect_pixmap

            icon_x = (rect.width() - icon_size) // 2
            painter.drawPixmap(icon_x, icon_y, icon_pixmap)

        # Text
        painter.setPen(text_color)
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)

        text_rect = QRect(0, 42, rect.width(), 24)
        alignment = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        painter.drawText(text_rect, alignment, self._text)

    def setIcon(self, icon: QIcon) -> None:
        """Set the button icon."""
        self._icon = icon
        self.update()

    def setText(self, text: str) -> None:
        """Set the button text."""
        self._text = text
        self.update()


# =============================================================================
# Toggle Button
# =============================================================================

class ToggleButton(QPushButton):
    """
    Animated toggle switch button.
    """

    toggled_changed = pyqtSignal(bool)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        initial_state: bool = False
    ):
        """
        Initialize toggle button.

        Args:
            parent: Parent widget
            initial_state: Initial toggle state
        """
        super().__init__(parent)
        self._checked = initial_state
        self._thumb_position = 1.0 if initial_state else 0.0

        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setChecked(initial_state)

        # Thumb animation
        self._animation = QPropertyAnimation(self, b"thumbPosition", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.clicked.connect(self._on_clicked)

    @pyqtProperty(float)
    def thumbPosition(self) -> float:
        return self._thumb_position

    @thumbPosition.setter
    def thumbPosition(self, value: float) -> None:
        self._thumb_position = value
        self.update()

    def _on_clicked(self) -> None:
        """Handle click."""
        self._checked = not self._checked
        self._animation.stop()
        self._animation.setStartValue(self._thumb_position)
        self._animation.setEndValue(1.0 if self._checked else 0.0)
        self._animation.start()
        self.toggled_changed.emit(self._checked)

    def isToggled(self) -> bool:
        """Get current toggle state."""
        return self._checked

    def setToggled(self, checked: bool, animate: bool = True) -> None:
        """Set toggle state."""
        if checked != self._checked:
            self._checked = checked
            if animate:
                self._animation.stop()
                self._animation.setStartValue(self._thumb_position)
                self._animation.setEndValue(1.0 if checked else 0.0)
                self._animation.start()
            else:
                self._thumb_position = 1.0 if checked else 0.0
                self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the toggle switch."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        height = rect.height()
        width = rect.width()

        # Track
        track_color = QColor("#4ec9b0") if self._checked else QColor("#3c3c3c")
        if not self.isEnabled():
            track_color = QColor("#2d2d30")

        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, height // 2, height // 2)

        # Thumb
        thumb_size = height - 4
        thumb_x = 2 + self._thumb_position * (width - thumb_size - 4)
        thumb_y = 2

        thumb_color = QColor("#ffffff") if self.isEnabled() else QColor("#6c6c6c")
        painter.setBrush(QBrush(thumb_color))
        painter.drawEllipse(int(thumb_x), thumb_y, thumb_size, thumb_size)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'AnimatedButton',
    'IconButton',
    'OperationButton',
    'ToggleButton',
]
