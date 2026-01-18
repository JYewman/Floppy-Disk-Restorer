"""
Splash screen dialog for Floppy Workbench.

Professional splash screen with loading progress, status messages,
and animated transitions.

Part of Phase 14: Polish & Professional Touches
"""

from typing import Optional, List, Callable
import importlib.metadata

from PyQt6.QtWidgets import (
    QSplashScreen, QWidget, QGraphicsOpacityEffect, QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal,
    QRect
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QFont,
    QLinearGradient, QPen, QPainterPath
)
from pathlib import Path


class SplashScreen(QSplashScreen):
    """
    Professional splash screen with loading progress and animations.

    Features:
    - Animated logo/icon display
    - Application name and version
    - Loading progress bar with status messages
    - Fade in/out transitions
    - Dark theme styling

    Usage:
        splash = SplashScreen()
        splash.show()

        # During loading
        splash.set_progress(25, "Loading configuration...")
        splash.set_progress(50, "Initializing hardware...")
        splash.set_progress(75, "Loading GUI components...")
        splash.set_progress(100, "Ready!")

        # When done
        splash.finish(main_window)
    """

    # Signal emitted when splash screen is closing
    closing = pyqtSignal()

    # Application info
    APP_NAME = "Floppy Workbench"
    APP_SUBTITLE = "Professional Floppy Disk Analysis & Recovery"

    # Dimensions
    WIDTH = 500
    HEIGHT = 350

    # Colors
    BG_COLOR = QColor(30, 30, 35)
    ACCENT_COLOR = QColor(70, 130, 180)  # Steel blue
    TEXT_COLOR = QColor(220, 220, 220)
    SUBTEXT_COLOR = QColor(150, 150, 150)
    PROGRESS_BG = QColor(50, 50, 55)

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize splash screen."""
        # Create pixmap for splash content
        pixmap = QPixmap(self.WIDTH, self.HEIGHT)
        pixmap.fill(Qt.GlobalColor.transparent)

        super().__init__(parent, pixmap)

        # Remove window frame
        self.setWindowFlags(
            Qt.WindowType.SplashScreen |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        # Enable transparency
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # State
        self._progress = 0
        self._status_message = "Initializing..."
        self._version = self._get_version()
        self._opacity = 0.0
        self._loading_dots = 0

        # Opacity effect for fade animations
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        # Fade animation
        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(500)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Loading dots animation timer
        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._update_loading_dots)
        self._dots_timer.setInterval(400)

        # Redraw the initial splash
        self._redraw()

    def _get_version(self) -> str:
        """Get application version from package metadata."""
        try:
            return importlib.metadata.version("floppy-formatter")
        except importlib.metadata.PackageNotFoundError:
            return "2.0.0-dev"

    def _redraw(self) -> None:
        """Redraw splash screen content."""
        pixmap = QPixmap(self.WIDTH, self.HEIGHT)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Draw background with rounded corners
        self._draw_background(painter)

        # Draw logo/icon
        self._draw_logo(painter)

        # Draw application name
        self._draw_title(painter)

        # Draw progress bar
        self._draw_progress(painter)

        # Draw status message
        self._draw_status(painter)

        # Draw version
        self._draw_version(painter)

        painter.end()

        self.setPixmap(pixmap)

    def _draw_background(self, painter: QPainter) -> None:
        """Draw rounded background with subtle gradient."""
        rect = QRect(0, 0, self.WIDTH, self.HEIGHT)
        radius = 12

        # Create gradient background
        gradient = QLinearGradient(0, 0, 0, self.HEIGHT)
        gradient.setColorAt(0.0, QColor(40, 40, 48))
        gradient.setColorAt(0.5, self.BG_COLOR)
        gradient.setColorAt(1.0, QColor(25, 25, 30))

        # Draw rounded rectangle
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), radius, radius)

        painter.fillPath(path, gradient)

        # Draw subtle border
        painter.setPen(QPen(QColor(60, 60, 70), 1))
        painter.drawPath(path)

        # Draw accent line at top
        accent_path = QPainterPath()
        accent_path.moveTo(radius, 0)
        accent_path.lineTo(self.WIDTH - radius, 0)
        accent_path.arcTo(self.WIDTH - 2 * radius, 0, 2 * radius, 2 * radius, 90, -90)
        accent_path.lineTo(self.WIDTH, radius)
        accent_path.arcTo(self.WIDTH - 2 * radius, 0, 2 * radius, 2 * radius, 0, 90)
        accent_path.closeSubpath()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.ACCENT_COLOR)
        painter.setOpacity(0.3)
        painter.drawRect(0, 0, self.WIDTH, 4)
        painter.setOpacity(1.0)

    def _draw_logo(self, painter: QPainter) -> None:
        """Draw application logo/icon."""
        # Logo position and size
        logo_size = 100
        logo_x = (self.WIDTH - logo_size) // 2
        logo_y = 30

        # Try to load the RTC logo PNG
        logo_path = Path(__file__).parent.parent / "resources" / "icons" / "app_logo.png"

        if logo_path.exists():
            # Load and draw the PNG logo
            logo_pixmap = QPixmap(str(logo_path))
            if not logo_pixmap.isNull():
                # Scale to desired size while maintaining aspect ratio
                scaled_pixmap = logo_pixmap.scaled(
                    logo_size, logo_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                # Center the scaled pixmap
                actual_x = logo_x + (logo_size - scaled_pixmap.width()) // 2
                actual_y = logo_y + (logo_size - scaled_pixmap.height()) // 2
                painter.drawPixmap(actual_x, actual_y, scaled_pixmap)
                return

        # Fallback: Draw a simple placeholder if logo not found
        center_x = logo_x + logo_size // 2
        center_y = logo_y + logo_size // 2

        # Outer glow
        for i in range(5):
            painter.setOpacity(0.1 - i * 0.02)
            glow_radius = logo_size // 2 + 10 + i * 3
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.ACCENT_COLOR)
            painter.drawEllipse(
                center_x - glow_radius,
                center_y - glow_radius,
                glow_radius * 2,
                glow_radius * 2
            )
        painter.setOpacity(1.0)

        # Main circle with gradient
        gradient = QLinearGradient(logo_x, logo_y, logo_x, logo_y + logo_size)
        gradient.setColorAt(0.0, QColor(90, 150, 200))
        gradient.setColorAt(1.0, QColor(50, 110, 160))

        painter.setPen(QPen(QColor(100, 160, 210), 2))
        painter.setBrush(gradient)
        painter.drawEllipse(logo_x, logo_y, logo_size, logo_size)

        # Draw "RTC" text as fallback
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        text_rect = QRect(logo_x, logo_y, logo_size, logo_size)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "RTC")

    def _draw_title(self, painter: QPainter) -> None:
        """Draw application name and subtitle."""
        # Main title - adjusted position for larger logo
        title_font = QFont("Segoe UI", 24, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(self.TEXT_COLOR)

        title_rect = QRect(0, 145, self.WIDTH, 40)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self.APP_NAME)

        # Subtitle
        subtitle_font = QFont("Segoe UI", 10)
        painter.setFont(subtitle_font)
        painter.setPen(self.SUBTEXT_COLOR)

        subtitle_rect = QRect(0, 185, self.WIDTH, 25)
        painter.drawText(subtitle_rect, Qt.AlignmentFlag.AlignCenter, self.APP_SUBTITLE)

    def _draw_progress(self, painter: QPainter) -> None:
        """Draw progress bar."""
        # Progress bar dimensions
        bar_width = self.WIDTH - 80
        bar_height = 8
        bar_x = 40
        bar_y = 250
        radius = 4

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.PROGRESS_BG)
        painter.drawRoundedRect(bar_x, bar_y, bar_width, bar_height, radius, radius)

        # Progress fill
        if self._progress > 0:
            fill_width = int(bar_width * self._progress / 100)

            # Gradient fill
            gradient = QLinearGradient(bar_x, 0, bar_x + bar_width, 0)
            gradient.setColorAt(0.0, QColor(70, 130, 180))
            gradient.setColorAt(1.0, QColor(100, 160, 210))

            painter.setBrush(gradient)

            # Clip to rounded rect
            if fill_width > 0:
                path = QPainterPath()
                path.addRoundedRect(bar_x, bar_y, fill_width, bar_height, radius, radius)
                painter.drawPath(path)

        # Progress percentage
        percent_font = QFont("Segoe UI", 9)
        painter.setFont(percent_font)
        painter.setPen(self.TEXT_COLOR)

        percent_text = f"{self._progress}%"
        percent_rect = QRect(bar_x + bar_width + 10, bar_y - 2, 40, bar_height + 4)
        alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.drawText(percent_rect, alignment, percent_text)

    def _draw_status(self, painter: QPainter) -> None:
        """Draw status message."""
        status_font = QFont("Segoe UI", 10)
        painter.setFont(status_font)
        painter.setPen(self.SUBTEXT_COLOR)

        # Add loading dots animation
        dots = "." * self._loading_dots
        display_message = self._status_message
        if not display_message.endswith("...") and not display_message.endswith("!"):
            display_message = display_message.rstrip(".") + dots

        status_rect = QRect(0, 275, self.WIDTH, 25)
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, display_message)

    def _draw_version(self, painter: QPainter) -> None:
        """Draw version number."""
        version_font = QFont("Segoe UI", 9)
        painter.setFont(version_font)
        painter.setPen(QColor(100, 100, 100))

        version_text = f"Version {self._version}"
        version_rect = QRect(0, self.HEIGHT - 35, self.WIDTH, 25)
        painter.drawText(version_rect, Qt.AlignmentFlag.AlignCenter, version_text)

    def _update_loading_dots(self) -> None:
        """Update loading dots animation."""
        self._loading_dots = (self._loading_dots + 1) % 4
        self._redraw()

    def show(self) -> None:
        """Show splash screen with fade-in animation."""
        super().show()

        # Start loading dots animation
        self._dots_timer.start()

        # Fade in
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()

        # Center on screen
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        """Center splash screen on primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            x = (screen_geometry.width() - self.WIDTH) // 2
            y = (screen_geometry.height() - self.HEIGHT) // 2
            self.move(x, y)

    def set_progress(self, value: int, message: str = "") -> None:
        """
        Update progress bar and status message.

        Args:
            value: Progress percentage (0-100)
            message: Status message to display
        """
        self._progress = max(0, min(100, value))
        if message:
            self._status_message = message

        self._redraw()
        QApplication.processEvents()

    def set_status(self, message: str) -> None:
        """
        Update status message without changing progress.

        Args:
            message: Status message to display
        """
        self._status_message = message
        self._redraw()
        QApplication.processEvents()

    def finish(self, main_window: Optional[QWidget] = None) -> None:
        """
        Finish splash screen with fade-out animation.

        Args:
            main_window: Main window to show after splash closes
        """
        # Stop loading dots
        self._dots_timer.stop()

        # Set progress to 100%
        self.set_progress(100, "Ready!")

        # Emit closing signal
        self.closing.emit()

        # Fade out animation
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)

        def on_fade_complete():
            if main_window:
                main_window.show()
            self.close()

        self._fade_animation.finished.connect(on_fade_complete)
        self._fade_animation.start()

    def close_immediately(self) -> None:
        """Close splash screen without animation."""
        self._dots_timer.stop()
        self.closing.emit()
        self.close()


class LoadingSequence:
    """
    Helper class for managing splash screen loading sequences.

    Usage:
        splash = SplashScreen()
        splash.show()

        sequence = LoadingSequence(splash)
        sequence.add_step("Loading configuration", config_loader.load)
        sequence.add_step("Initializing hardware", hardware.init)
        sequence.add_step("Loading GUI", gui.setup)

        sequence.run(on_complete=lambda: splash.finish(main_window))
    """

    def __init__(self, splash: SplashScreen):
        """
        Initialize loading sequence.

        Args:
            splash: Splash screen to update
        """
        self._splash = splash
        self._steps: List[tuple] = []
        self._current_step = 0

    def add_step(
        self,
        message: str,
        callback: Optional[Callable] = None,
        weight: int = 1
    ) -> 'LoadingSequence':
        """
        Add a loading step.

        Args:
            message: Status message for this step
            callback: Function to execute (can be None for display-only steps)
            weight: Relative weight for progress calculation

        Returns:
            Self for method chaining
        """
        self._steps.append((message, callback, weight))
        return self

    def run(self, on_complete: Optional[Callable] = None) -> None:
        """
        Run all loading steps sequentially.

        Args:
            on_complete: Callback when all steps complete
        """
        if not self._steps:
            if on_complete:
                on_complete()
            return

        # Calculate total weight
        total_weight = sum(step[2] for step in self._steps)

        # Execute steps
        accumulated_weight = 0

        for message, callback, weight in self._steps:
            # Update splash with current step
            progress = int((accumulated_weight / total_weight) * 100)
            self._splash.set_progress(progress, message)

            # Process events to update UI
            QApplication.processEvents()

            # Execute callback if provided
            if callback:
                try:
                    callback()
                except Exception as e:
                    # Log error but continue
                    print(f"Loading step failed: {message} - {e}")

            accumulated_weight += weight

        # Final progress update
        self._splash.set_progress(100, "Complete!")

        # Call completion callback
        if on_complete:
            QTimer.singleShot(500, on_complete)


class SplashScreenManager:
    """
    Singleton manager for splash screen operations.

    Usage:
        manager = SplashScreenManager.instance()
        manager.show_splash()
        manager.update_progress(50, "Loading...")
        manager.finish_splash(main_window)
    """

    _instance: Optional['SplashScreenManager'] = None

    @classmethod
    def instance(cls) -> 'SplashScreenManager':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Initialize manager."""
        if SplashScreenManager._instance is not None:
            raise RuntimeError("Use SplashScreenManager.instance() instead")

        self._splash: Optional[SplashScreen] = None

    def show_splash(self) -> SplashScreen:
        """
        Create and show splash screen.

        Returns:
            The splash screen instance
        """
        if self._splash is not None:
            self._splash.close()

        self._splash = SplashScreen()
        self._splash.show()
        return self._splash

    def update_progress(self, value: int, message: str = "") -> None:
        """
        Update splash screen progress.

        Args:
            value: Progress percentage (0-100)
            message: Status message
        """
        if self._splash:
            self._splash.set_progress(value, message)

    def update_status(self, message: str) -> None:
        """
        Update splash screen status message.

        Args:
            message: Status message
        """
        if self._splash:
            self._splash.set_status(message)

    def finish_splash(self, main_window: Optional[QWidget] = None) -> None:
        """
        Finish and close splash screen.

        Args:
            main_window: Main window to show after splash closes
        """
        if self._splash:
            self._splash.finish(main_window)
            self._splash = None

    def close_splash(self) -> None:
        """Close splash screen immediately without animation."""
        if self._splash:
            self._splash.close_immediately()
            self._splash = None

    @property
    def splash(self) -> Optional[SplashScreen]:
        """Get current splash screen instance."""
        return self._splash


# Convenience functions
def show_splash() -> SplashScreen:
    """Show application splash screen."""
    return SplashScreenManager.instance().show_splash()


def update_splash_progress(value: int, message: str = "") -> None:
    """Update splash screen progress."""
    SplashScreenManager.instance().update_progress(value, message)


def finish_splash(main_window: Optional[QWidget] = None) -> None:
    """Finish and close splash screen."""
    SplashScreenManager.instance().finish_splash(main_window)
