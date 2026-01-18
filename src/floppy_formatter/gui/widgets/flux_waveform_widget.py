"""
Flux waveform visualization widget for Floppy Workbench.

Provides an oscilloscope-style display of flux transitions captured
from floppy disks. Features include:
- Rising/falling edge visualization
- Time axis with microsecond resolution
- Zoom and pan functionality (mouse wheel, keyboard)
- Visual markers for index, sectors, and data regions
- Color coding for signal quality
- Level-of-detail rendering for performance
- Cursor tracking with position display
- Region selection with shift+click+drag

Part of Phase 7-8: Analytics Dashboard & Flux Visualization
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple, Dict, Any

from PyQt6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsLineItem,
    QGraphicsTextItem,
    QGraphicsRectItem,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QFrame,
    QToolTip,
)
from PyQt6.QtCore import (
    Qt,
    QRectF,
    QPointF,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QPainterPath,
    QFont,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QCursor,
    QTransform,
)

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Display colors
COLOR_BACKGROUND = QColor("#1e1e1e")
COLOR_GRID_MAJOR = QColor("#3a3d41")
COLOR_GRID_MINOR = QColor("#2d2d30")
COLOR_AXIS = QColor("#808080")
COLOR_WAVEFORM_GOOD = QColor("#4ec9b0")  # Green-cyan
COLOR_WAVEFORM_WEAK = QColor("#dcdcaa")  # Yellow
COLOR_WAVEFORM_ERROR = QColor("#f14c4c")  # Red
COLOR_INDEX_MARKER = QColor("#c586c0")  # Purple
COLOR_SECTOR_MARKER = QColor("#569cd6")  # Blue
COLOR_DATA_REGION = QColor("#264f78")  # Dark blue
# Semi-transparent gold (255, 215, 0, 80)
_highlight = QColor("#ffd700")
_highlight.setAlpha(80)
COLOR_HIGHLIGHT = _highlight

# MFM timing for HD
HD_BIT_CELL_US = 2.0
SECTOR_DURATION_US = 1000.0  # Approximately 1ms per sector for HD

# Display settings
DEFAULT_US_PER_PIXEL = 0.1  # 0.1 microseconds per pixel at 100% zoom
MIN_US_PER_PIXEL = 0.01   # Maximum zoom in
MAX_US_PER_PIXEL = 10.0   # Maximum zoom out
WAVEFORM_HEIGHT = 60      # Height of waveform in pixels
MARGIN_TOP = 40           # Top margin for time axis
MARGIN_BOTTOM = 20
MARGIN_LEFT = 60          # Left margin for labels
MARGIN_RIGHT = 20


# =============================================================================
# Data Classes
# =============================================================================

class MarkerType(Enum):
    """Types of markers that can be displayed on the waveform."""
    INDEX = auto()      # Index pulse marker
    SECTOR = auto()     # Sector header (IDAM)
    DATA = auto()       # Data region start
    GAP = auto()        # Gap region
    CUSTOM = auto()     # User-defined marker


@dataclass
class FluxMarker:
    """
    Marker to display on the flux waveform.

    Attributes:
        position_us: Position in microseconds from start
        marker_type: Type of marker
        label: Optional label text
        color: Optional custom color
        width_us: Optional width for region markers
    """
    position_us: float
    marker_type: MarkerType
    label: str = ""
    color: Optional[QColor] = None
    width_us: float = 0.0

    def get_color(self) -> QColor:
        """Get the color for this marker."""
        if self.color:
            return self.color
        color_map = {
            MarkerType.INDEX: COLOR_INDEX_MARKER,
            MarkerType.SECTOR: COLOR_SECTOR_MARKER,
            MarkerType.DATA: COLOR_DATA_REGION,
            MarkerType.GAP: QColor("#505050"),
            MarkerType.CUSTOM: QColor("#ffffff"),
        }
        return color_map.get(self.marker_type, QColor("#ffffff"))


@dataclass
class TransitionPoint:
    """
    Single flux transition point.

    Attributes:
        time_us: Time position in microseconds
        confidence: Confidence/quality of this transition (0.0-1.0)
        is_rising: True for rising edge, False for falling
    """
    time_us: float
    confidence: float = 1.0
    is_rising: bool = True


# =============================================================================
# Waveform Graphics Items
# =============================================================================

class WaveformPathItem(QGraphicsPathItem):
    """Graphics item for the waveform path."""

    def __init__(self, parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self._pen_good = QPen(COLOR_WAVEFORM_GOOD, 1.5)
        self._pen_weak = QPen(COLOR_WAVEFORM_WEAK, 1.5)
        self._pen_error = QPen(COLOR_WAVEFORM_ERROR, 1.5)
        self.setPen(self._pen_good)
        self.setAcceptHoverEvents(True)

    def set_quality_mode(self, quality: str) -> None:
        """Set the pen based on quality level."""
        if quality == "good":
            self.setPen(self._pen_good)
        elif quality == "weak":
            self.setPen(self._pen_weak)
        else:
            self.setPen(self._pen_error)


class MarkerItem(QGraphicsItem):
    """Graphics item for a waveform marker."""

    def __init__(
        self,
        marker: FluxMarker,
        height: float,
        parent: Optional[QGraphicsItem] = None
    ):
        super().__init__(parent)
        self._marker = marker
        self._height = height
        self._pen = QPen(marker.get_color(), 1.5, Qt.PenStyle.DashLine)
        self._brush = QBrush(QColor(
            marker.get_color().red(),
            marker.get_color().green(),
            marker.get_color().blue(), 40
        ))
        self._font = QFont("Consolas", 8)
        self.setAcceptHoverEvents(True)
        self.setToolTip(
            f"{marker.marker_type.name}: {marker.label}\n"
            f"Position: {marker.position_us:.2f} µs"
        )

    def boundingRect(self) -> QRectF:
        width = max(2, self._marker.width_us) if self._marker.width_us > 0 else 2
        return QRectF(0, 0, width, self._height)

    def paint(
        self,
        painter: QPainter,
        option: Any,
        widget: Optional[QWidget] = None
    ) -> None:
        painter.setPen(self._pen)

        if self._marker.width_us > 0:
            # Draw region
            rect = QRectF(0, 0, self._marker.width_us, self._height)
            painter.fillRect(rect, self._brush)
            painter.drawRect(rect)
        else:
            # Draw vertical line
            painter.drawLine(QPointF(0, 0), QPointF(0, self._height))

        # Draw label if present
        if self._marker.label:
            painter.setFont(self._font)
            painter.setPen(QPen(self._marker.get_color()))
            painter.drawText(QPointF(3, 12), self._marker.label)


# =============================================================================
# Main Waveform Widget
# =============================================================================

class FluxWaveformWidget(QGraphicsView):
    """
    Oscilloscope-style flux waveform visualization widget.

    Displays flux transitions as a square wave pattern with:
    - Time axis with microsecond resolution
    - Zoom and pan capabilities
    - Visual markers for significant positions
    - Color coding based on signal quality

    Signals:
        position_changed(float): Emitted when cursor position changes (in µs)
        region_selected(float, float): Emitted when a region is selected (start, end in µs)
        zoom_changed(float): Emitted when zoom level changes
    """

    position_changed = pyqtSignal(float)
    region_selected = pyqtSignal(float, float)
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Scene setup
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setBackgroundBrush(QBrush(COLOR_BACKGROUND))
        self.setMinimumHeight(150)

        # Flux data
        self._transitions: List[TransitionPoint] = []
        self._markers: List[FluxMarker] = []
        self._duration_us: float = 0.0

        # View state
        self._us_per_pixel = DEFAULT_US_PER_PIXEL
        self._view_start_us: float = 0.0
        self._is_panning = False
        self._pan_start_pos: Optional[QPointF] = None
        self._pan_start_view: float = 0.0

        # Selection state
        self._selection_start_us: Optional[float] = None
        self._selection_end_us: Optional[float] = None
        self._is_selecting = False
        self._selection_rect: Optional[QGraphicsRectItem] = None

        # Graphics items
        self._waveform_items: List[WaveformPathItem] = []
        self._marker_items: List[MarkerItem] = []
        self._grid_items: List[QGraphicsLineItem] = []
        self._axis_labels: List[QGraphicsTextItem] = []

        # Cursor tracking
        self.setMouseTracking(True)
        self._cursor_us: float = 0.0
        self._cursor_line: Optional[QGraphicsLineItem] = None
        self._show_cursor_line = True

        # Bit quality map (transition index -> quality 0.0-1.0)
        self._bit_quality_map: Dict[int, float] = {}

        # Level-of-detail settings
        self._lod_threshold_transitions = 5000  # Simplify above this many visible transitions
        self._lod_skip_factor = 1  # How many transitions to skip in simplified mode

        # Enable keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Pan step size (microseconds per arrow key press)
        self._pan_step_us = 100.0

        # Build initial display
        self._rebuild_scene()

    # =========================================================================
    # Public API
    # =========================================================================

    def set_flux_data(
        self, timings_us: List[float], confidences: Optional[List[float]] = None
    ) -> None:
        """
        Set flux data from timing values.

        Args:
            timings_us: List of pulse widths in microseconds
            confidences: Optional confidence values (0.0-1.0) for each transition
        """
        self._transitions.clear()

        current_time = 0.0
        is_rising = True

        for i, timing in enumerate(timings_us):
            conf = confidences[i] if confidences and i < len(confidences) else 1.0
            self._transitions.append(TransitionPoint(
                time_us=current_time,
                confidence=conf,
                is_rising=is_rising
            ))
            current_time += timing
            is_rising = not is_rising

        self._duration_us = current_time
        self._rebuild_scene()
        self.zoom_to_fit()

    def clear_flux_data(self) -> None:
        """Clear all flux data."""
        self._transitions.clear()
        self._markers.clear()
        self._duration_us = 0.0
        self._rebuild_scene()

    def set_markers(self, markers: List[FluxMarker]) -> None:
        """Set display markers."""
        self._markers = list(markers)
        self._rebuild_markers()

    def add_marker(self, marker: FluxMarker) -> None:
        """Add a single marker."""
        self._markers.append(marker)
        self._rebuild_markers()

    def clear_markers(self) -> None:
        """Clear all markers."""
        self._markers.clear()
        self._rebuild_markers()

    def highlight_region(self, start_us: float, end_us: float) -> None:
        """
        Highlight a region of the waveform.

        Args:
            start_us: Start position in microseconds
            end_us: End position in microseconds
        """
        self._selection_start_us = min(start_us, end_us)
        self._selection_end_us = max(start_us, end_us)
        self._update_selection_rect()

    def clear_highlight(self) -> None:
        """Clear the highlighted region."""
        self._selection_start_us = None
        self._selection_end_us = None
        if self._selection_rect:
            self._scene.removeItem(self._selection_rect)
            self._selection_rect = None

    def zoom_to_fit(self) -> None:
        """Zoom to show the entire waveform."""
        if self._duration_us <= 0:
            return

        view_width = self.viewport().width() - MARGIN_LEFT - MARGIN_RIGHT
        if view_width <= 0:
            return

        self._us_per_pixel = self._duration_us / view_width
        self._us_per_pixel = max(MIN_US_PER_PIXEL, min(MAX_US_PER_PIXEL, self._us_per_pixel))
        self._view_start_us = 0.0
        self._rebuild_scene()
        self.zoom_changed.emit(self._get_zoom_percent())

    def zoom_to_sector(self, sector_num: int) -> None:
        """
        Zoom to show a specific sector.

        Args:
            sector_num: Sector number (0-17 for HD)
        """
        # Calculate approximate sector position
        sector_start_us = sector_num * SECTOR_DURATION_US
        sector_end_us = sector_start_us + SECTOR_DURATION_US

        # Add some margin
        margin = SECTOR_DURATION_US * 0.1
        start_us = max(0, sector_start_us - margin)
        end_us = min(self._duration_us, sector_end_us + margin)

        self._zoom_to_range(start_us, end_us)

    def zoom_in(self) -> None:
        """Zoom in by 2x."""
        self._set_zoom(self._us_per_pixel / 2.0)

    def zoom_out(self) -> None:
        """Zoom out by 2x."""
        self._set_zoom(self._us_per_pixel * 2.0)

    def set_zoom_percent(self, percent: float) -> None:
        """
        Set zoom level as percentage.

        Args:
            percent: Zoom percentage (100 = 1:1 scale)
        """
        self._set_zoom(DEFAULT_US_PER_PIXEL * 100.0 / percent)

    def get_duration_us(self) -> float:
        """Get total duration of flux data in microseconds."""
        return self._duration_us

    def get_transition_count(self) -> int:
        """Get number of flux transitions."""
        return len(self._transitions)

    def set_bit_quality(self, quality_map: Dict[int, float]) -> None:
        """
        Set per-transition quality values.

        Args:
            quality_map: Dictionary mapping transition index to quality (0.0-1.0)
        """
        self._bit_quality_map = dict(quality_map)
        self._rebuild_scene()

    def clear_bit_quality(self) -> None:
        """Clear bit quality map."""
        self._bit_quality_map.clear()
        self._rebuild_scene()

    def zoom_to_region(self, start_us: float, end_us: float) -> None:
        """
        Zoom to show a specific time region.

        Args:
            start_us: Start time in microseconds
            end_us: End time in microseconds
        """
        self._zoom_to_range(start_us, end_us)

    def set_zoom_level(self, us_per_pixel: float) -> None:
        """
        Set exact zoom level.

        Args:
            us_per_pixel: Microseconds per pixel
        """
        self._set_zoom(us_per_pixel)

    def get_zoom_level(self) -> float:
        """
        Get current zoom level in microseconds per pixel.

        Returns:
            Current µs/pixel value
        """
        return self._us_per_pixel

    def scroll_to_time(self, time_us: float) -> None:
        """
        Scroll view to center on a specific time position.

        Args:
            time_us: Time position in microseconds
        """
        view_width = self.viewport().width() - MARGIN_LEFT - MARGIN_RIGHT
        half_view_us = (view_width / 2) * self._us_per_pixel

        self._view_start_us = max(0, time_us - half_view_us)
        self._view_start_us = min(self._view_start_us,
                                  max(0, self._duration_us - view_width * self._us_per_pixel))
        self._rebuild_scene()

    def get_selected_region(self) -> Optional[Tuple[float, float]]:
        """
        Get the currently selected region.

        Returns:
            Tuple of (start_us, end_us) or None if no selection
        """
        if self._selection_start_us is not None and self._selection_end_us is not None:
            return (min(self._selection_start_us, self._selection_end_us),
                    max(self._selection_start_us, self._selection_end_us))
        return None

    def clear(self) -> None:
        """Clear all flux data and reset view."""
        self._transitions.clear()
        self._markers.clear()
        self._bit_quality_map.clear()
        self._duration_us = 0.0
        self._selection_start_us = None
        self._selection_end_us = None
        self._view_start_us = 0.0
        self._us_per_pixel = DEFAULT_US_PER_PIXEL
        self._rebuild_scene()

    def set_show_cursor_line(self, show: bool) -> None:
        """Enable or disable cursor tracking line."""
        self._show_cursor_line = show
        self._update_cursor_line()

    def scroll_left(self) -> None:
        """Scroll view left by pan step."""
        self._view_start_us = max(0, self._view_start_us - self._pan_step_us)
        self._rebuild_scene()

    def scroll_right(self) -> None:
        """Scroll view right by pan step."""
        view_width = self.viewport().width() - MARGIN_LEFT - MARGIN_RIGHT
        max_start = max(0, self._duration_us - view_width * self._us_per_pixel)
        self._view_start_us = min(max_start, self._view_start_us + self._pan_step_us)
        self._rebuild_scene()

    def scroll_to_start(self) -> None:
        """Scroll to the beginning of the flux data."""
        self._view_start_us = 0.0
        self._rebuild_scene()

    def scroll_to_end(self) -> None:
        """Scroll to the end of the flux data."""
        view_width = self.viewport().width() - MARGIN_LEFT - MARGIN_RIGHT
        self._view_start_us = max(0, self._duration_us - view_width * self._us_per_pixel)
        self._rebuild_scene()

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _get_zoom_percent(self) -> float:
        """Get current zoom as percentage."""
        return DEFAULT_US_PER_PIXEL / self._us_per_pixel * 100.0

    def _set_zoom(self, us_per_pixel: float) -> None:
        """Set zoom level with bounds checking."""
        old_zoom = self._us_per_pixel
        self._us_per_pixel = max(MIN_US_PER_PIXEL, min(MAX_US_PER_PIXEL, us_per_pixel))

        if self._us_per_pixel != old_zoom:
            # Adjust view to keep center stable
            view_width = self.viewport().width() - MARGIN_LEFT - MARGIN_RIGHT
            center_us = self._view_start_us + (view_width / 2) * old_zoom
            self._view_start_us = center_us - (view_width / 2) * self._us_per_pixel
            self._view_start_us = max(0, self._view_start_us)

            self._rebuild_scene()
            self.zoom_changed.emit(self._get_zoom_percent())

    def _zoom_to_range(self, start_us: float, end_us: float) -> None:
        """Zoom to show a specific time range."""
        if end_us <= start_us:
            return

        view_width = self.viewport().width() - MARGIN_LEFT - MARGIN_RIGHT
        if view_width <= 0:
            return

        range_us = end_us - start_us
        self._us_per_pixel = range_us / view_width
        self._us_per_pixel = max(MIN_US_PER_PIXEL, min(MAX_US_PER_PIXEL, self._us_per_pixel))
        self._view_start_us = start_us

        self._rebuild_scene()
        self.zoom_changed.emit(self._get_zoom_percent())

    def _us_to_x(self, us: float) -> float:
        """Convert microseconds to X pixel position."""
        return MARGIN_LEFT + (us - self._view_start_us) / self._us_per_pixel

    def _x_to_us(self, x: float) -> float:
        """Convert X pixel position to microseconds."""
        return self._view_start_us + (x - MARGIN_LEFT) * self._us_per_pixel

    def _rebuild_scene(self) -> None:
        """Rebuild the entire scene."""
        self._scene.clear()
        self._waveform_items.clear()
        self._marker_items.clear()
        self._grid_items.clear()
        self._axis_labels.clear()
        self._selection_rect = None

        view_width = self.viewport().width()
        view_height = self.viewport().height()

        if view_width <= 0 or view_height <= 0:
            return

        # Set scene rect
        total_width_us = max(self._duration_us, 1000.0)
        scene_width = MARGIN_LEFT + total_width_us / self._us_per_pixel + MARGIN_RIGHT
        self._scene.setSceneRect(0, 0, scene_width, view_height)

        # Draw grid
        self._draw_grid(view_width, view_height)

        # Draw waveform
        self._draw_waveform(view_height)

        # Draw markers
        self._rebuild_markers()

        # Restore selection if present
        self._update_selection_rect()

        # Add cursor line (initially hidden)
        self._cursor_line = self._scene.addLine(
            0, MARGIN_TOP, 0, view_height - MARGIN_BOTTOM,
            QPen(QColor("#ffffff"), 1, Qt.PenStyle.DashLine)
        )
        self._cursor_line.setVisible(False)

        # Update scroll position
        self.horizontalScrollBar().setValue(int(self._us_to_x(self._view_start_us)))

    def _draw_grid(self, width: float, height: float) -> None:
        """Draw time grid and axis labels."""
        waveform_top = MARGIN_TOP
        waveform_bottom = height - MARGIN_BOTTOM

        # Calculate grid spacing based on zoom level
        # Aim for grid lines every 50-100 pixels
        target_spacing_px = 80
        spacing_us = self._us_per_pixel * target_spacing_px

        # Round to nice numbers
        if spacing_us < 1:
            spacing_us = round(spacing_us * 10) / 10
        elif spacing_us < 10:
            spacing_us = round(spacing_us)
        elif spacing_us < 100:
            spacing_us = round(spacing_us / 10) * 10
        else:
            spacing_us = round(spacing_us / 100) * 100

        spacing_us = max(0.1, spacing_us)

        # Draw vertical grid lines
        start_time = (self._view_start_us // spacing_us) * spacing_us
        pen_major = QPen(COLOR_GRID_MAJOR, 1)
        pen_minor = QPen(COLOR_GRID_MINOR, 1)

        t = start_time
        while t <= self._view_start_us + width * self._us_per_pixel:
            x = self._us_to_x(t)

            if MARGIN_LEFT <= x <= width - MARGIN_RIGHT:
                # Determine if major or minor
                is_major = abs(t % (spacing_us * 5)) < 0.001
                line = self._scene.addLine(
                    x, waveform_top, x, waveform_bottom,
                    pen_major if is_major else pen_minor
                )
                self._grid_items.append(line)

                # Add label for major lines
                if is_major or spacing_us >= 1:
                    label = self._scene.addText(f"{t:.1f}", QFont("Consolas", 8))
                    label.setDefaultTextColor(COLOR_AXIS)
                    label.setPos(x - 15, waveform_top - 20)
                    self._axis_labels.append(label)

            t += spacing_us

        # Draw horizontal center line
        center_y = (waveform_top + waveform_bottom) / 2
        self._scene.addLine(
            MARGIN_LEFT, center_y, width - MARGIN_RIGHT, center_y,
            QPen(COLOR_GRID_MAJOR, 1)
        )

        # Draw axis label
        label = self._scene.addText("Time (µs)", QFont("Consolas", 9))
        label.setDefaultTextColor(COLOR_AXIS)
        label.setPos(width - 70, waveform_top - 20)

    def _draw_waveform(self, height: float) -> None:
        """Draw the waveform from transition data with level-of-detail optimization."""
        if not self._transitions:
            return

        waveform_top = MARGIN_TOP
        waveform_bottom = height - MARGIN_BOTTOM
        waveform_center = (waveform_top + waveform_bottom) / 2
        amplitude = (waveform_bottom - waveform_top) / 2 - 10

        # Calculate level-of-detail skip factor
        lod_skip = self._calculate_lod_skip()
        self._lod_skip_factor = lod_skip

        # Build path segments based on quality
        current_path = QPainterPath()
        current_quality = "good"
        first_point = True

        view_start = self._view_start_us
        view_width = self.viewport().width()
        view_end = view_start + view_width * self._us_per_pixel

        transition_count = 0
        for i, trans in enumerate(self._transitions):
            if trans.time_us > view_end:
                break

            # Skip transitions for level-of-detail (keep first and last visible)
            if lod_skip > 1 and i % lod_skip != 0:
                continue

            transition_count += 1

            # Check bit quality map first, then use transition confidence
            if i in self._bit_quality_map:
                conf = self._bit_quality_map[i]
            else:
                conf = trans.confidence

            # Determine quality from confidence
            if conf >= 0.8:
                quality = "good"
            elif conf >= 0.5:
                quality = "weak"
            else:
                quality = "error"

            # Calculate Y position with amplitude based on confidence
            base_amplitude = amplitude
            if conf < 1.0:
                # Reduce amplitude for weak transitions
                base_amplitude *= (0.5 + 0.5 * conf)

            y_high = waveform_center - base_amplitude
            y_low = waveform_center + base_amplitude

            x = self._us_to_x(trans.time_us)
            y = y_high if trans.is_rising else y_low

            # If quality changes, finish current path and start new one
            if quality != current_quality and not first_point:
                item = WaveformPathItem()
                item.setPath(current_path)
                item.set_quality_mode(current_quality)
                self._scene.addItem(item)
                self._waveform_items.append(item)
                current_path = QPainterPath()
                first_point = True

            current_quality = quality

            if first_point:
                current_path.moveTo(x, y)
                first_point = False
            else:
                # Draw horizontal line from previous state
                prev_y = y_low if trans.is_rising else y_high
                current_path.lineTo(x, prev_y)
                # Draw vertical transition
                current_path.lineTo(x, y)

        # Add final path segment
        if not first_point:
            item = WaveformPathItem()
            item.setPath(current_path)
            item.set_quality_mode(current_quality)
            self._scene.addItem(item)
            self._waveform_items.append(item)

    def _rebuild_markers(self) -> None:
        """Rebuild marker display."""
        # Remove old markers
        for item in self._marker_items:
            self._scene.removeItem(item)
        self._marker_items.clear()

        if not self._markers:
            return

        height = self.viewport().height()
        waveform_height = height - MARGIN_TOP - MARGIN_BOTTOM

        for marker in self._markers:
            x = self._us_to_x(marker.position_us)

            item = MarkerItem(marker, waveform_height)
            item.setPos(x, MARGIN_TOP)

            # Scale width for region markers
            if marker.width_us > 0:
                scale_x = 1.0 / self._us_per_pixel
                item.setTransform(QTransform().scale(scale_x, 1.0))

            self._scene.addItem(item)
            self._marker_items.append(item)

    def _update_selection_rect(self) -> None:
        """Update selection rectangle display."""
        if self._selection_rect:
            self._scene.removeItem(self._selection_rect)
            self._selection_rect = None

        if self._selection_start_us is None or self._selection_end_us is None:
            return

        height = self.viewport().height()
        x1 = self._us_to_x(self._selection_start_us)
        x2 = self._us_to_x(self._selection_end_us)

        self._selection_rect = self._scene.addRect(
            min(x1, x2), MARGIN_TOP,
            abs(x2 - x1), height - MARGIN_TOP - MARGIN_BOTTOM,
            QPen(COLOR_HIGHLIGHT.darker(150), 2),
            QBrush(COLOR_HIGHLIGHT)
        )
        self._selection_rect.setZValue(-1)  # Behind waveform

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
        else:
            # Scroll
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for panning/selection."""
        if event.button() == Qt.MouseButton.MiddleButton:
            # Start panning
            self._is_panning = True
            self._pan_start_pos = event.position()
            self._pan_start_view = self._view_start_us
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Start selection
                self._is_selecting = True
                pos = self.mapToScene(event.position().toPoint())
                self._selection_start_us = self._x_to_us(pos.x())
                self._selection_end_us = self._selection_start_us
                event.accept()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for panning/selection/cursor tracking."""
        pos = self.mapToScene(event.position().toPoint())
        self._cursor_us = self._x_to_us(pos.x())
        self.position_changed.emit(self._cursor_us)

        # Update cursor line
        self._update_cursor_line()

        if self._is_panning and self._pan_start_pos:
            # Pan view
            delta_px = event.position().x() - self._pan_start_pos.x()
            delta_us = delta_px * self._us_per_pixel
            self._view_start_us = max(0, self._pan_start_view - delta_us)
            self._rebuild_scene()
            event.accept()
        elif self._is_selecting:
            # Update selection
            self._selection_end_us = self._cursor_us
            self._update_selection_rect()
            event.accept()
        else:
            # Show tooltip with position info
            if 0 <= self._cursor_us <= self._duration_us:
                # Find nearest transition
                nearest_idx = self._find_nearest_transition(self._cursor_us)
                if nearest_idx >= 0:
                    trans = self._transitions[nearest_idx]
                    tip = (
                        f"Time: {self._cursor_us:.2f} µs\n"
                        f"Transition #{nearest_idx}\n"
                        f"Confidence: {trans.confidence:.0%}"
                    )
                    QToolTip.showText(event.globalPosition().toPoint(), tip, self)

            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.MiddleButton and self._is_panning:
            self._is_panning = False
            self._pan_start_pos = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            if self._selection_start_us is not None and self._selection_end_us is not None:
                start = min(self._selection_start_us, self._selection_end_us)
                end = max(self._selection_start_us, self._selection_end_us)
                if end - start > 0.1:  # Minimum selection size
                    self.region_selected.emit(start, end)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        """Handle widget resize."""
        super().resizeEvent(event)
        self._rebuild_scene()

    def _find_nearest_transition(self, time_us: float) -> int:
        """Find index of nearest transition to given time."""
        if not self._transitions:
            return -1

        # Binary search
        left, right = 0, len(self._transitions) - 1

        while left < right:
            mid = (left + right) // 2
            if self._transitions[mid].time_us < time_us:
                left = mid + 1
            else:
                right = mid

        # Check which neighbor is closer
        if left > 0:
            dist_left = abs(self._transitions[left - 1].time_us - time_us)
            dist_right = abs(self._transitions[left].time_us - time_us)
            if dist_left < dist_right:
                return left - 1

        return left

    def _update_cursor_line(self) -> None:
        """Update cursor line position and visibility."""
        if self._cursor_line is None:
            return

        if not self._show_cursor_line or self._cursor_us < 0 or self._cursor_us > self._duration_us:
            self._cursor_line.setVisible(False)
            return

        x = self._us_to_x(self._cursor_us)
        view_height = self.viewport().height()

        self._cursor_line.setLine(x, MARGIN_TOP, x, view_height - MARGIN_BOTTOM)
        self._cursor_line.setVisible(True)

    def _calculate_lod_skip(self) -> int:
        """
        Calculate level-of-detail skip factor based on visible transitions.

        Returns:
            Skip factor (1 = render all, 2 = every other, etc.)
        """
        if not self._transitions:
            return 1

        view_width = self.viewport().width() - MARGIN_LEFT - MARGIN_RIGHT
        view_start = self._view_start_us
        view_end = view_start + view_width * self._us_per_pixel

        # Count visible transitions
        visible_count = 0
        for trans in self._transitions:
            if trans.time_us > view_end:
                break
            if trans.time_us >= view_start:
                visible_count += 1

        # Calculate skip factor to keep rendering fast
        if visible_count > self._lod_threshold_transitions:
            return max(1, visible_count // self._lod_threshold_transitions)

        return 1

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard navigation."""
        key = event.key()

        if key == Qt.Key.Key_Left:
            # Scroll left
            self.scroll_left()
            event.accept()
        elif key == Qt.Key.Key_Right:
            # Scroll right
            self.scroll_right()
            event.accept()
        elif key == Qt.Key.Key_Home:
            # Jump to start
            self.scroll_to_start()
            event.accept()
        elif key == Qt.Key.Key_End:
            # Jump to end
            self.scroll_to_end()
            event.accept()
        elif key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
            # Zoom in
            self.zoom_in()
            event.accept()
        elif key == Qt.Key.Key_Minus:
            # Zoom out
            self.zoom_out()
            event.accept()
        elif key == Qt.Key.Key_0:
            # Fit to view
            self.zoom_to_fit()
            event.accept()
        elif key == Qt.Key.Key_Escape:
            # Clear selection
            self.clear_highlight()
            event.accept()
        else:
            super().keyPressEvent(event)


# =============================================================================
# Waveform Widget with Controls
# =============================================================================

class FluxWaveformPanel(QWidget):
    """
    Complete flux waveform panel with toolbar controls.

    Includes the waveform widget plus zoom controls and position display.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Toolbar
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #2d2d30;
                border-bottom: 1px solid #3a3d41;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 2, 4, 2)
        toolbar_layout.setSpacing(4)

        # Zoom controls
        self._zoom_fit_btn = QToolButton()
        self._zoom_fit_btn.setText("Fit")
        self._zoom_fit_btn.setToolTip("Zoom to fit entire waveform")
        toolbar_layout.addWidget(self._zoom_fit_btn)

        self._zoom_in_btn = QToolButton()
        self._zoom_in_btn.setText("+")
        self._zoom_in_btn.setToolTip("Zoom in")
        toolbar_layout.addWidget(self._zoom_in_btn)

        self._zoom_out_btn = QToolButton()
        self._zoom_out_btn.setText("-")
        self._zoom_out_btn.setToolTip("Zoom out")
        toolbar_layout.addWidget(self._zoom_out_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setStyleSheet("color: #cccccc; min-width: 50px;")
        toolbar_layout.addWidget(self._zoom_label)

        toolbar_layout.addStretch()

        # Position display
        self._position_label = QLabel("Position: -- µs")
        self._position_label.setStyleSheet("color: #cccccc;")
        toolbar_layout.addWidget(self._position_label)

        # Statistics display
        self._stats_label = QLabel("Transitions: --")
        self._stats_label.setStyleSheet("color: #808080; margin-left: 20px;")
        toolbar_layout.addWidget(self._stats_label)

        layout.addWidget(toolbar)

        # Waveform widget
        self._waveform = FluxWaveformWidget()
        layout.addWidget(self._waveform, 1)

        # Connect signals
        self._zoom_fit_btn.clicked.connect(self._waveform.zoom_to_fit)
        self._zoom_in_btn.clicked.connect(self._waveform.zoom_in)
        self._zoom_out_btn.clicked.connect(self._waveform.zoom_out)
        self._waveform.zoom_changed.connect(self._on_zoom_changed)
        self._waveform.position_changed.connect(self._on_position_changed)

    def get_waveform_widget(self) -> FluxWaveformWidget:
        """Get the waveform widget."""
        return self._waveform

    def set_flux_data(
        self, timings_us: List[float], confidences: Optional[List[float]] = None
    ) -> None:
        """Set flux data."""
        self._waveform.set_flux_data(timings_us, confidences)
        self._stats_label.setText(f"Transitions: {self._waveform.get_transition_count():,}")

    def _on_zoom_changed(self, percent: float) -> None:
        """Handle zoom change."""
        self._zoom_label.setText(f"{percent:.0f}%")

    def _on_position_changed(self, us: float) -> None:
        """Handle cursor position change."""
        if us >= 0:
            self._position_label.setText(f"Position: {us:.2f} µs")
        else:
            self._position_label.setText("Position: -- µs")


__all__ = [
    'FluxWaveformWidget',
    'FluxWaveformPanel',
    'FluxMarker',
    'MarkerType',
    'TransitionPoint',
]
