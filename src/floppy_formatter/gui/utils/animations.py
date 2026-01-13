"""
Animation utilities for Floppy Workbench.

Provides reusable animation classes and helpers for creating smooth,
professional UI transitions and micro-interactions.

Classes:
    - FadeAnimation: Opacity-based fade effects
    - SlideAnimation: Position-based slide effects
    - ScaleAnimation: Scale/transform effects
    - ProgressAnimation: Smooth progress bar updates
    - AnimationGroup: Parallel/sequential animation coordination
    - EasingCurves: Standard easing curve definitions

Part of Phase 14: Polish & Professional Touches
"""

import logging
from typing import Optional, List, Callable, Any
from enum import Enum

from PyQt6.QtCore import (
    QObject,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QSequentialAnimationGroup,
    QEasingCurve,
    QPoint,
    QRect,
    QAbstractAnimation,
    pyqtSignal,
    QTimer,
    Qt,
)
from PyQt6.QtWidgets import (
    QWidget,
    QGraphicsOpacityEffect,
    QProgressBar,
    QApplication,
)
from PyQt6.QtGui import QColor


# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Global Animation Settings
# =============================================================================

class AnimationSettings:
    """Global animation settings singleton."""

    _instance: Optional["AnimationSettings"] = None

    def __new__(cls) -> "AnimationSettings":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._enabled = True
        self._speed_multiplier = 1.0

    @property
    def enabled(self) -> bool:
        """Check if animations are enabled."""
        try:
            from floppy_formatter.core.settings import get_settings
            settings = get_settings()
            return settings.display.animate_operations
        except Exception:
            return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def speed_multiplier(self) -> float:
        """Get animation speed multiplier."""
        return self._speed_multiplier

    @speed_multiplier.setter
    def speed_multiplier(self, value: float) -> None:
        self._speed_multiplier = max(0.1, min(3.0, value))

    def get_duration(self, base_duration: int) -> int:
        """Get adjusted duration based on settings."""
        if not self.enabled:
            return 0
        return int(base_duration * self._speed_multiplier)


def get_animation_settings() -> AnimationSettings:
    """Get the global animation settings instance."""
    return AnimationSettings()


def animations_enabled() -> bool:
    """Quick check if animations are enabled."""
    return get_animation_settings().enabled


# =============================================================================
# Easing Curves
# =============================================================================

class EasingCurves:
    """Standard easing curves for consistent animation feel."""

    # Default curve for most animations
    EASE_OUT_CUBIC = QEasingCurve.Type.OutCubic

    # For transitions between states
    EASE_IN_OUT = QEasingCurve.Type.InOutQuad

    # Spring/bounce effects
    SPRING = QEasingCurve.Type.OutBack

    # Smooth deceleration
    EASE_OUT = QEasingCurve.Type.OutQuad

    # Smooth acceleration
    EASE_IN = QEasingCurve.Type.InQuad

    # Linear for progress bars
    LINEAR = QEasingCurve.Type.Linear

    # Elastic bounce
    ELASTIC = QEasingCurve.Type.OutElastic

    # Overshoot and settle
    OVERSHOOT = QEasingCurve.Type.OutBack


# =============================================================================
# Fade Animation
# =============================================================================

class FadeAnimation(QObject):
    """
    Opacity-based fade animations.

    Provides fade in, fade out, and cross-fade effects using
    QGraphicsOpacityEffect.
    """

    finished = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._animation: Optional[QPropertyAnimation] = None
        self._effect: Optional[QGraphicsOpacityEffect] = None

    def fade_in(
        self,
        widget: QWidget,
        duration_ms: int = 300,
        start_opacity: float = 0.0,
        end_opacity: float = 1.0,
        on_finished: Optional[Callable] = None
    ) -> Optional[QPropertyAnimation]:
        """
        Fade a widget in (from transparent to visible).

        Args:
            widget: Widget to animate
            duration_ms: Animation duration in milliseconds
            start_opacity: Starting opacity (0.0-1.0)
            end_opacity: Ending opacity (0.0-1.0)
            on_finished: Optional callback when animation completes

        Returns:
            The animation object, or None if animations disabled
        """
        if not animations_enabled():
            widget.show()
            if on_finished:
                on_finished()
            return None

        duration = get_animation_settings().get_duration(duration_ms)

        # Ensure widget is visible but transparent
        widget.show()

        # Create or get opacity effect
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        effect.setOpacity(start_opacity)

        # Create animation
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(duration)
        animation.setStartValue(start_opacity)
        animation.setEndValue(end_opacity)
        animation.setEasingCurve(EasingCurves.EASE_OUT_CUBIC)

        def on_animation_finished():
            if end_opacity >= 1.0:
                # Remove effect when fully visible for better performance
                widget.setGraphicsEffect(None)
            self.finished.emit()
            if on_finished:
                on_finished()

        animation.finished.connect(on_animation_finished)
        animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        self._animation = animation
        self._effect = effect

        return animation

    def fade_out(
        self,
        widget: QWidget,
        duration_ms: int = 300,
        start_opacity: float = 1.0,
        end_opacity: float = 0.0,
        hide_on_finish: bool = True,
        on_finished: Optional[Callable] = None
    ) -> Optional[QPropertyAnimation]:
        """
        Fade a widget out (from visible to transparent).

        Args:
            widget: Widget to animate
            duration_ms: Animation duration in milliseconds
            start_opacity: Starting opacity (0.0-1.0)
            end_opacity: Ending opacity (0.0-1.0)
            hide_on_finish: Whether to hide widget when animation completes
            on_finished: Optional callback when animation completes

        Returns:
            The animation object, or None if animations disabled
        """
        if not animations_enabled():
            if hide_on_finish:
                widget.hide()
            if on_finished:
                on_finished()
            return None

        duration = get_animation_settings().get_duration(duration_ms)

        # Create or get opacity effect
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        effect.setOpacity(start_opacity)

        # Create animation
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(duration)
        animation.setStartValue(start_opacity)
        animation.setEndValue(end_opacity)
        animation.setEasingCurve(EasingCurves.EASE_OUT_CUBIC)

        def on_animation_finished():
            if hide_on_finish:
                widget.hide()
                widget.setGraphicsEffect(None)
            self.finished.emit()
            if on_finished:
                on_finished()

        animation.finished.connect(on_animation_finished)
        animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        self._animation = animation
        self._effect = effect

        return animation

    def cross_fade(
        self,
        old_widget: QWidget,
        new_widget: QWidget,
        duration_ms: int = 300,
        on_finished: Optional[Callable] = None
    ) -> Optional[QParallelAnimationGroup]:
        """
        Cross-fade between two widgets (one fades out while other fades in).

        Args:
            old_widget: Widget to fade out
            new_widget: Widget to fade in
            duration_ms: Animation duration in milliseconds
            on_finished: Optional callback when animation completes

        Returns:
            The animation group, or None if animations disabled
        """
        if not animations_enabled():
            old_widget.hide()
            new_widget.show()
            if on_finished:
                on_finished()
            return None

        duration = get_animation_settings().get_duration(duration_ms)

        # Set up effects
        old_effect = QGraphicsOpacityEffect(old_widget)
        old_effect.setOpacity(1.0)
        old_widget.setGraphicsEffect(old_effect)

        new_effect = QGraphicsOpacityEffect(new_widget)
        new_effect.setOpacity(0.0)
        new_widget.setGraphicsEffect(new_effect)
        new_widget.show()

        # Create animations
        fade_out_anim = QPropertyAnimation(old_effect, b"opacity", self)
        fade_out_anim.setDuration(duration)
        fade_out_anim.setStartValue(1.0)
        fade_out_anim.setEndValue(0.0)
        fade_out_anim.setEasingCurve(EasingCurves.EASE_IN_OUT)

        fade_in_anim = QPropertyAnimation(new_effect, b"opacity", self)
        fade_in_anim.setDuration(duration)
        fade_in_anim.setStartValue(0.0)
        fade_in_anim.setEndValue(1.0)
        fade_in_anim.setEasingCurve(EasingCurves.EASE_IN_OUT)

        # Group them
        group = QParallelAnimationGroup(self)
        group.addAnimation(fade_out_anim)
        group.addAnimation(fade_in_anim)

        def on_group_finished():
            old_widget.hide()
            old_widget.setGraphicsEffect(None)
            new_widget.setGraphicsEffect(None)
            self.finished.emit()
            if on_finished:
                on_finished()

        group.finished.connect(on_group_finished)
        group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        return group

    def stop(self) -> None:
        """Stop any running animation."""
        if self._animation:
            self._animation.stop()


# =============================================================================
# Slide Animation
# =============================================================================

class SlideAnimation(QObject):
    """
    Position-based slide animations.

    Provides slide in/out effects from different directions.
    """

    finished = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._animation: Optional[QPropertyAnimation] = None

    def _slide_in(
        self,
        widget: QWidget,
        duration_ms: int,
        start_offset: QPoint,
        on_finished: Optional[Callable] = None
    ) -> Optional[QPropertyAnimation]:
        """Internal slide-in implementation."""
        if not animations_enabled():
            widget.show()
            if on_finished:
                on_finished()
            return None

        duration = get_animation_settings().get_duration(duration_ms)

        # Get target position (current position)
        target_pos = widget.pos()
        start_pos = target_pos + start_offset

        widget.move(start_pos)
        widget.show()

        animation = QPropertyAnimation(widget, b"pos", self)
        animation.setDuration(duration)
        animation.setStartValue(start_pos)
        animation.setEndValue(target_pos)
        animation.setEasingCurve(EasingCurves.EASE_OUT_CUBIC)

        def on_animation_finished():
            self.finished.emit()
            if on_finished:
                on_finished()

        animation.finished.connect(on_animation_finished)
        animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        self._animation = animation
        return animation

    def slide_in_left(
        self,
        widget: QWidget,
        duration_ms: int = 300,
        distance: Optional[int] = None,
        on_finished: Optional[Callable] = None
    ) -> Optional[QPropertyAnimation]:
        """Slide widget in from the left."""
        dist = distance or widget.width()
        return self._slide_in(widget, duration_ms, QPoint(-dist, 0), on_finished)

    def slide_in_right(
        self,
        widget: QWidget,
        duration_ms: int = 300,
        distance: Optional[int] = None,
        on_finished: Optional[Callable] = None
    ) -> Optional[QPropertyAnimation]:
        """Slide widget in from the right."""
        dist = distance or widget.width()
        return self._slide_in(widget, duration_ms, QPoint(dist, 0), on_finished)

    def slide_in_top(
        self,
        widget: QWidget,
        duration_ms: int = 300,
        distance: Optional[int] = None,
        on_finished: Optional[Callable] = None
    ) -> Optional[QPropertyAnimation]:
        """Slide widget in from the top."""
        dist = distance or widget.height()
        return self._slide_in(widget, duration_ms, QPoint(0, -dist), on_finished)

    def slide_in_bottom(
        self,
        widget: QWidget,
        duration_ms: int = 300,
        distance: Optional[int] = None,
        on_finished: Optional[Callable] = None
    ) -> Optional[QPropertyAnimation]:
        """Slide widget in from the bottom."""
        dist = distance or widget.height()
        return self._slide_in(widget, duration_ms, QPoint(0, dist), on_finished)

    def slide_out_left(
        self,
        widget: QWidget,
        duration_ms: int = 300,
        distance: Optional[int] = None,
        hide_on_finish: bool = True,
        on_finished: Optional[Callable] = None
    ) -> Optional[QPropertyAnimation]:
        """Slide widget out to the left."""
        if not animations_enabled():
            if hide_on_finish:
                widget.hide()
            if on_finished:
                on_finished()
            return None

        duration = get_animation_settings().get_duration(duration_ms)
        dist = distance or widget.width()

        start_pos = widget.pos()
        end_pos = start_pos + QPoint(-dist, 0)

        animation = QPropertyAnimation(widget, b"pos", self)
        animation.setDuration(duration)
        animation.setStartValue(start_pos)
        animation.setEndValue(end_pos)
        animation.setEasingCurve(EasingCurves.EASE_IN)

        def on_animation_finished():
            if hide_on_finish:
                widget.hide()
            widget.move(start_pos)
            self.finished.emit()
            if on_finished:
                on_finished()

        animation.finished.connect(on_animation_finished)
        animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        self._animation = animation
        return animation

    def stop(self) -> None:
        """Stop any running animation."""
        if self._animation:
            self._animation.stop()


# =============================================================================
# Scale Animation
# =============================================================================

class ScaleAnimation(QObject):
    """
    Scale/transform animations.

    Provides pulse, grow, and shrink effects using geometry animation.
    """

    finished = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._animation: Optional[QPropertyAnimation] = None
        self._original_geometry: Optional[QRect] = None

    def pulse(
        self,
        widget: QWidget,
        scale: float = 1.1,
        duration_ms: int = 200,
        on_finished: Optional[Callable] = None
    ) -> Optional[QSequentialAnimationGroup]:
        """
        Pulse animation (scale up then back to normal).

        Args:
            widget: Widget to animate
            scale: Maximum scale factor
            duration_ms: Duration of one pulse (up and down)
            on_finished: Optional callback when animation completes
        """
        if not animations_enabled():
            if on_finished:
                on_finished()
            return None

        duration = get_animation_settings().get_duration(duration_ms)
        half_duration = duration // 2

        original_geom = widget.geometry()
        center = original_geom.center()

        # Calculate scaled geometry
        scaled_width = int(original_geom.width() * scale)
        scaled_height = int(original_geom.height() * scale)
        scaled_geom = QRect(
            center.x() - scaled_width // 2,
            center.y() - scaled_height // 2,
            scaled_width,
            scaled_height
        )

        # Scale up animation
        scale_up = QPropertyAnimation(widget, b"geometry", self)
        scale_up.setDuration(half_duration)
        scale_up.setStartValue(original_geom)
        scale_up.setEndValue(scaled_geom)
        scale_up.setEasingCurve(EasingCurves.EASE_OUT)

        # Scale down animation
        scale_down = QPropertyAnimation(widget, b"geometry", self)
        scale_down.setDuration(half_duration)
        scale_down.setStartValue(scaled_geom)
        scale_down.setEndValue(original_geom)
        scale_down.setEasingCurve(EasingCurves.SPRING)

        # Sequence
        group = QSequentialAnimationGroup(self)
        group.addAnimation(scale_up)
        group.addAnimation(scale_down)

        def on_group_finished():
            widget.setGeometry(original_geom)
            self.finished.emit()
            if on_finished:
                on_finished()

        group.finished.connect(on_group_finished)
        group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        return group

    def grow_in(
        self,
        widget: QWidget,
        duration_ms: int = 300,
        on_finished: Optional[Callable] = None
    ) -> Optional[QPropertyAnimation]:
        """
        Grow widget from nothing to full size.

        Args:
            widget: Widget to animate
            duration_ms: Animation duration
            on_finished: Optional callback
        """
        if not animations_enabled():
            widget.show()
            if on_finished:
                on_finished()
            return None

        duration = get_animation_settings().get_duration(duration_ms)

        target_geom = widget.geometry()
        center = target_geom.center()

        # Start from center point (zero size)
        start_geom = QRect(center.x(), center.y(), 0, 0)

        widget.setGeometry(start_geom)
        widget.show()

        animation = QPropertyAnimation(widget, b"geometry", self)
        animation.setDuration(duration)
        animation.setStartValue(start_geom)
        animation.setEndValue(target_geom)
        animation.setEasingCurve(EasingCurves.SPRING)

        def on_animation_finished():
            self.finished.emit()
            if on_finished:
                on_finished()

        animation.finished.connect(on_animation_finished)
        animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        self._animation = animation
        self._original_geometry = target_geom

        return animation

    def shrink_out(
        self,
        widget: QWidget,
        duration_ms: int = 300,
        hide_on_finish: bool = True,
        on_finished: Optional[Callable] = None
    ) -> Optional[QPropertyAnimation]:
        """
        Shrink widget down to nothing.

        Args:
            widget: Widget to animate
            duration_ms: Animation duration
            hide_on_finish: Whether to hide widget when done
            on_finished: Optional callback
        """
        if not animations_enabled():
            if hide_on_finish:
                widget.hide()
            if on_finished:
                on_finished()
            return None

        duration = get_animation_settings().get_duration(duration_ms)

        start_geom = widget.geometry()
        center = start_geom.center()

        # End at center point (zero size)
        end_geom = QRect(center.x(), center.y(), 0, 0)

        animation = QPropertyAnimation(widget, b"geometry", self)
        animation.setDuration(duration)
        animation.setStartValue(start_geom)
        animation.setEndValue(end_geom)
        animation.setEasingCurve(EasingCurves.EASE_IN)

        def on_animation_finished():
            if hide_on_finish:
                widget.hide()
            widget.setGeometry(start_geom)
            self.finished.emit()
            if on_finished:
                on_finished()

        animation.finished.connect(on_animation_finished)
        animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        self._animation = animation
        self._original_geometry = start_geom

        return animation

    def stop(self) -> None:
        """Stop any running animation and restore geometry."""
        if self._animation:
            self._animation.stop()
            if self._original_geometry and self._animation.targetObject():
                self._animation.targetObject().setGeometry(self._original_geometry)


# =============================================================================
# Progress Animation
# =============================================================================

class ProgressAnimation(QObject):
    """
    Smooth progress bar animations.

    Prevents jarring jumps in progress display by smoothly
    animating value changes.
    """

    finished = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._animation: Optional[QPropertyAnimation] = None

    def smooth_progress(
        self,
        progress_bar: QProgressBar,
        target_value: int,
        duration_ms: int = 100,
        on_finished: Optional[Callable] = None
    ) -> Optional[QPropertyAnimation]:
        """
        Smoothly animate progress bar to target value.

        Args:
            progress_bar: QProgressBar to animate
            target_value: Target value
            duration_ms: Animation duration
            on_finished: Optional callback
        """
        if not animations_enabled():
            progress_bar.setValue(target_value)
            if on_finished:
                on_finished()
            return None

        duration = get_animation_settings().get_duration(duration_ms)

        # Stop any existing animation
        if self._animation:
            self._animation.stop()

        current_value = progress_bar.value()

        # Don't animate if values are same or very close
        if abs(current_value - target_value) <= 1:
            progress_bar.setValue(target_value)
            if on_finished:
                on_finished()
            return None

        animation = QPropertyAnimation(progress_bar, b"value", self)
        animation.setDuration(duration)
        animation.setStartValue(current_value)
        animation.setEndValue(target_value)
        animation.setEasingCurve(EasingCurves.LINEAR)

        def on_animation_finished():
            self.finished.emit()
            if on_finished:
                on_finished()

        animation.finished.connect(on_animation_finished)
        animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        self._animation = animation
        return animation

    def stop(self) -> None:
        """Stop any running animation."""
        if self._animation:
            self._animation.stop()


# =============================================================================
# Animation Group Helpers
# =============================================================================

class AnimationGroup(QObject):
    """
    Helper for coordinating multiple animations.
    """

    finished = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._group: Optional[QAbstractAnimation] = None

    def run_parallel(
        self,
        animations: List[QPropertyAnimation],
        on_finished: Optional[Callable] = None
    ) -> QParallelAnimationGroup:
        """
        Run multiple animations simultaneously.

        Args:
            animations: List of animations to run in parallel
            on_finished: Optional callback when all complete
        """
        group = QParallelAnimationGroup(self)

        for anim in animations:
            group.addAnimation(anim)

        def on_group_finished():
            self.finished.emit()
            if on_finished:
                on_finished()

        group.finished.connect(on_group_finished)
        group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        self._group = group
        return group

    def run_sequential(
        self,
        animations: List[QPropertyAnimation],
        on_finished: Optional[Callable] = None
    ) -> QSequentialAnimationGroup:
        """
        Run multiple animations one after another.

        Args:
            animations: List of animations to run sequentially
            on_finished: Optional callback when all complete
        """
        group = QSequentialAnimationGroup(self)

        for anim in animations:
            group.addAnimation(anim)

        def on_group_finished():
            self.finished.emit()
            if on_finished:
                on_finished()

        group.finished.connect(on_group_finished)
        group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        self._group = group
        return group

    def stop(self) -> None:
        """Stop the animation group."""
        if self._group:
            self._group.stop()


# =============================================================================
# Shake Animation (for errors)
# =============================================================================

class ShakeAnimation(QObject):
    """
    Shake animation for error feedback.

    Creates a horizontal shake effect to draw attention.
    """

    finished = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._animation: Optional[QSequentialAnimationGroup] = None
        self._original_pos: Optional[QPoint] = None

    def shake(
        self,
        widget: QWidget,
        amplitude: int = 10,
        duration_ms: int = 400,
        shakes: int = 4,
        on_finished: Optional[Callable] = None
    ) -> Optional[QSequentialAnimationGroup]:
        """
        Shake a widget horizontally.

        Args:
            widget: Widget to shake
            amplitude: Maximum displacement in pixels
            duration_ms: Total animation duration
            shakes: Number of shakes
            on_finished: Optional callback
        """
        if not animations_enabled():
            if on_finished:
                on_finished()
            return None

        duration = get_animation_settings().get_duration(duration_ms)
        shake_duration = duration // (shakes * 2)

        original_pos = widget.pos()
        self._original_pos = original_pos

        group = QSequentialAnimationGroup(self)

        for i in range(shakes):
            # Shake left
            left_anim = QPropertyAnimation(widget, b"pos", self)
            left_anim.setDuration(shake_duration)
            left_anim.setStartValue(original_pos if i == 0 else original_pos + QPoint(amplitude, 0))
            left_anim.setEndValue(original_pos + QPoint(-amplitude, 0))
            left_anim.setEasingCurve(EasingCurves.EASE_OUT)
            group.addAnimation(left_anim)

            # Shake right
            right_anim = QPropertyAnimation(widget, b"pos", self)
            right_anim.setDuration(shake_duration)
            right_anim.setStartValue(original_pos + QPoint(-amplitude, 0))
            right_anim.setEndValue(original_pos + QPoint(amplitude, 0) if i < shakes - 1 else original_pos)
            right_anim.setEasingCurve(EasingCurves.EASE_OUT)
            group.addAnimation(right_anim)

        def on_group_finished():
            widget.move(original_pos)
            self.finished.emit()
            if on_finished:
                on_finished()

        group.finished.connect(on_group_finished)
        group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        self._animation = group
        return group

    def stop(self) -> None:
        """Stop and reset position."""
        if self._animation:
            self._animation.stop()
            if self._original_pos and self._animation.animationAt(0):
                widget = self._animation.animationAt(0).targetObject()
                if widget:
                    widget.move(self._original_pos)


# =============================================================================
# Flash Animation (for success/error feedback)
# =============================================================================

class FlashAnimation(QObject):
    """
    Flash animation for feedback.

    Briefly changes widget background color and fades back.
    """

    finished = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._timer: Optional[QTimer] = None

    def flash_success(
        self,
        widget: QWidget,
        duration_ms: int = 500,
        on_finished: Optional[Callable] = None
    ) -> None:
        """Flash widget with success color (green)."""
        self._flash(widget, "#4ec9b0", duration_ms, on_finished)

    def flash_error(
        self,
        widget: QWidget,
        duration_ms: int = 500,
        on_finished: Optional[Callable] = None
    ) -> None:
        """Flash widget with error color (red)."""
        self._flash(widget, "#f14c4c", duration_ms, on_finished)

    def flash_warning(
        self,
        widget: QWidget,
        duration_ms: int = 500,
        on_finished: Optional[Callable] = None
    ) -> None:
        """Flash widget with warning color (yellow/orange)."""
        self._flash(widget, "#f0a030", duration_ms, on_finished)

    def _flash(
        self,
        widget: QWidget,
        color: str,
        duration_ms: int,
        on_finished: Optional[Callable] = None
    ) -> None:
        """Internal flash implementation."""
        if not animations_enabled():
            if on_finished:
                on_finished()
            return

        duration = get_animation_settings().get_duration(duration_ms)

        # Store original stylesheet
        original_style = widget.styleSheet()

        # Apply flash color
        flash_style = f"{original_style}\nbackground-color: {color};"
        widget.setStyleSheet(flash_style)

        # Timer to restore original style
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)

        def restore():
            widget.setStyleSheet(original_style)
            self.finished.emit()
            if on_finished:
                on_finished()

        self._timer.timeout.connect(restore)
        self._timer.start(duration)


# =============================================================================
# Convenience Functions
# =============================================================================

def fade_in_widget(
    widget: QWidget,
    duration_ms: int = 300,
    on_finished: Optional[Callable] = None
) -> Optional[QPropertyAnimation]:
    """Convenience function to fade in a widget."""
    fade = FadeAnimation()
    return fade.fade_in(widget, duration_ms, on_finished=on_finished)


def fade_out_widget(
    widget: QWidget,
    duration_ms: int = 300,
    hide: bool = True,
    on_finished: Optional[Callable] = None
) -> Optional[QPropertyAnimation]:
    """Convenience function to fade out a widget."""
    fade = FadeAnimation()
    return fade.fade_out(widget, duration_ms, hide_on_finish=hide, on_finished=on_finished)


def pulse_widget(
    widget: QWidget,
    scale: float = 1.1,
    duration_ms: int = 200
) -> Optional[QSequentialAnimationGroup]:
    """Convenience function to pulse a widget."""
    scale_anim = ScaleAnimation()
    return scale_anim.pulse(widget, scale, duration_ms)


def shake_widget(
    widget: QWidget,
    amplitude: int = 10,
    duration_ms: int = 400
) -> Optional[QSequentialAnimationGroup]:
    """Convenience function to shake a widget."""
    shake = ShakeAnimation()
    return shake.shake(widget, amplitude, duration_ms)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Settings
    'AnimationSettings',
    'get_animation_settings',
    'animations_enabled',

    # Easing curves
    'EasingCurves',

    # Animation classes
    'FadeAnimation',
    'SlideAnimation',
    'ScaleAnimation',
    'ProgressAnimation',
    'AnimationGroup',
    'ShakeAnimation',
    'FlashAnimation',

    # Convenience functions
    'fade_in_widget',
    'fade_out_widget',
    'pulse_widget',
    'shake_widget',
]
