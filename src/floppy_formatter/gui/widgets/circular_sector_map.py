"""
Enhanced circular sector map widget for Floppy Workbench GUI.

Visualizes all 2,880 sectors of a 1.44MB floppy disk in a circular layout
mimicking the physical geometry of the disk (80 cylinders, 2 heads, 18 sectors/track).

Phase 6 Enhancements:
- Seven color states: Unscanned, Good, Bad, Recovering, Reading, Writing, Verifying
- Flux quality overlay mode with gradient coloring
- Selection mode for targeted operations
- Zoom to track and pan functionality
- Enhanced tooltips with detailed sector information
- Real-time animations during operations
- Export to PNG/SVG

Part of Phase 6: Enhanced Sector Map Visualization
"""

import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Dict, List, Set, Tuple

from PyQt6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsEllipseItem,
    QToolTip,
    QApplication,
)
from PyQt6.QtCore import (
    Qt,
    QRectF,
    QPointF,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    QSize,
)
from PyQt6.QtGui import (
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QBrush,
    QImage,
)
from PyQt6.QtSvg import QSvgGenerator


# =============================================================================
# Enums and Data Classes
# =============================================================================


class SectorStatus(Enum):
    """
    Status states for disk sectors.

    Each state has an associated color for visualization.
    """
    UNSCANNED = auto()    # Gray - not yet scanned
    PENDING = auto()      # Gray - awaiting scan (alias for UNSCANNED)
    GOOD = auto()         # Green - sector reads correctly
    BAD = auto()          # Red - sector has errors
    WEAK = auto()         # Yellow-orange - sector readable but marginal quality
    RECOVERED = auto()    # Light green - sector was recovered successfully
    RECOVERING = auto()   # Yellow - recovery in progress
    READING = auto()      # Blue - currently being read
    WRITING = auto()      # Purple - currently being written
    VERIFYING = auto()    # Orange - being verified
    UNKNOWN = auto()      # Gray - status not determined


class ViewMode(Enum):
    """
    View modes for the sector map display.
    """
    STATUS = auto()  # Show sector status (good/bad/etc.)
    QUALITY = auto()  # Show flux quality gradient
    ERRORS = auto()  # Highlight only error sectors, dim others
    DATA_PATTERN = auto()  # Show data pattern visualization


class ActivityType(Enum):
    """
    Types of activity for real-time animation.
    """
    NONE = auto()
    READING = auto()
    WRITING = auto()
    VERIFYING = auto()


@dataclass
class FluxQualityMetrics:
    """
    Flux-level quality metrics for a sector.
    """
    signal_strength: float = 0.0    # 0.0 to 1.0
    jitter: float = 0.0             # Timing jitter in microseconds
    snr: float = 0.0                # Signal-to-noise ratio in dB
    bit_errors: int = 0             # Estimated bit errors
    quality_grade: str = "?"        # A/B/C/D/F grade

    def get_overall_quality(self) -> float:
        """Calculate overall quality score (0.0 to 1.0)."""
        # Weighted combination of metrics
        strength_weight = 0.4
        jitter_weight = 0.3
        snr_weight = 0.3

        # Normalize jitter (lower is better, assume 0-2us range)
        jitter_score = max(0.0, 1.0 - (self.jitter / 2.0))

        # Normalize SNR (assume 10-40 dB range)
        snr_score = min(1.0, max(0.0, (self.snr - 10.0) / 30.0))

        return (
            self.signal_strength * strength_weight +
            jitter_score * jitter_weight +
            snr_score * snr_weight
        )


@dataclass
class HistoryEntry:
    """
    A single entry in a sector's status history.
    """
    timestamp: datetime
    operation: str          # "scan", "format", "restore", "verify"
    result: str             # "success", "error", "crc_error", etc.
    details: str = ""       # Additional details

    def format_time(self) -> str:
        """Format timestamp for display."""
        return self.timestamp.strftime("%H:%M:%S")


@dataclass
class SectorMetadata:
    """
    Complete metadata for a single sector.
    """
    sector_num: int
    cylinder: int
    head: int
    sector_offset: int
    status: SectorStatus = SectorStatus.UNSCANNED
    quality: float = 0.0              # 0.0 to 1.0
    error_type: Optional[str] = None  # "CRC", "Missing", "Weak", etc.
    crc_valid: bool = True
    last_read_time: Optional[datetime] = None
    data: Optional[bytes] = None      # First 64 bytes if available
    flux_quality: Optional[FluxQualityMetrics] = None
    history: List[HistoryEntry] = field(default_factory=list)

    def get_lba(self) -> int:
        """Get logical block address."""
        return self.sector_num

    def get_byte_offset(self) -> int:
        """Get byte offset on disk (512 bytes per sector)."""
        return self.sector_num * 512

    def get_chs_string(self) -> str:
        """Get formatted CHS address."""
        return f"{self.cylinder}/{self.head}/{self.sector_offset + 1}"

    def add_history_entry(self, operation: str, result: str, details: str = "") -> None:
        """Add a new history entry."""
        entry = HistoryEntry(
            timestamp=datetime.now(),
            operation=operation,
            result=result,
            details=details
        )
        self.history.append(entry)
        # Keep only last 20 entries
        if len(self.history) > 20:
            self.history = self.history[-20:]


class SectorDataCache:
    """
    Cache for sector data and metadata.

    Stores per-sector information including data bytes, flux quality,
    status history, and error details.
    """

    def __init__(self, total_sectors: int = 2880):
        """
        Initialize the sector data cache.

        Args:
            total_sectors: Total number of sectors on disk
        """
        self._total_sectors = total_sectors
        self._metadata: Dict[int, SectorMetadata] = {}
        self._initialize_metadata()

    def _initialize_metadata(self) -> None:
        """Initialize metadata for all sectors."""
        for sector_num in range(self._total_sectors):
            cylinder = sector_num // (18 * 2)
            head = (sector_num // 18) % 2
            sector_offset = sector_num % 18

            self._metadata[sector_num] = SectorMetadata(
                sector_num=sector_num,
                cylinder=cylinder,
                head=head,
                sector_offset=sector_offset
            )

    def get_metadata(self, sector_num: int) -> Optional[SectorMetadata]:
        """Get metadata for a sector."""
        return self._metadata.get(sector_num)

    def set_status(self, sector_num: int, status: SectorStatus) -> None:
        """Set sector status."""
        if sector_num in self._metadata:
            self._metadata[sector_num].status = status

    def set_quality(self, sector_num: int, quality: float) -> None:
        """Set sector quality (0.0 to 1.0)."""
        if sector_num in self._metadata:
            self._metadata[sector_num].quality = max(0.0, min(1.0, quality))

    def set_error(self, sector_num: int, error_type: str, crc_valid: bool = False) -> None:
        """Set sector error information."""
        if sector_num in self._metadata:
            self._metadata[sector_num].error_type = error_type
            self._metadata[sector_num].crc_valid = crc_valid

    def store_sector_data(self, sector_num: int, data: bytes) -> None:
        """Store sector data (first 64 bytes)."""
        if sector_num in self._metadata:
            self._metadata[sector_num].data = data[:64] if data else None
            self._metadata[sector_num].last_read_time = datetime.now()

    def store_flux_quality(self, sector_num: int, metrics: FluxQualityMetrics) -> None:
        """Store flux quality metrics for a sector."""
        if sector_num in self._metadata:
            self._metadata[sector_num].flux_quality = metrics
            self._metadata[sector_num].quality = metrics.get_overall_quality()

    def add_history_entry(
        self, sector_num: int, operation: str, result: str, details: str = ""
    ) -> None:
        """Add a history entry for a sector."""
        if sector_num in self._metadata:
            self._metadata[sector_num].add_history_entry(operation, result, details)

    def clear(self) -> None:
        """Clear all cached data and reset to initial state."""
        self._initialize_metadata()

    def get_bad_sectors(self) -> List[int]:
        """Get list of all bad sector numbers."""
        return [
            num for num, meta in self._metadata.items()
            if meta.status == SectorStatus.BAD
        ]

    def get_sectors_by_status(self, status: SectorStatus) -> List[int]:
        """Get list of sectors with a specific status."""
        return [
            num for num, meta in self._metadata.items()
            if meta.status == status
        ]


# =============================================================================
# Sector Wedge Item
# =============================================================================


class SectorWedgeItem(QGraphicsItem):
    """
    Graphical representation of a single sector as a wedge in the circular map.

    Each wedge represents one 512-byte sector on the floppy disk, positioned
    according to its physical geometry (cylinder, head, sector offset).

    Phase 6 Enhancements:
    - Seven color states
    - Selection highlight
    - Quality overlay mode
    - Pulse animation for active sectors
    """

    # Color definitions for different sector states
    STATUS_COLORS = {
        SectorStatus.UNSCANNED: QColor(80, 80, 80),      # Dark gray
        SectorStatus.PENDING: QColor(80, 80, 80),        # Dark gray (same as unscanned)
        SectorStatus.GOOD: QColor(0, 200, 0),            # Bright green
        SectorStatus.BAD: QColor(200, 50, 50),           # Red
        SectorStatus.WEAK: QColor(255, 200, 50),         # Yellow - marginal quality
        SectorStatus.RECOVERED: QColor(100, 220, 100),   # Light green - recovered
        SectorStatus.RECOVERING: QColor(255, 180, 0),    # Yellow/Orange
        SectorStatus.READING: QColor(50, 120, 220),      # Blue
        SectorStatus.WRITING: QColor(150, 50, 200),      # Purple
        SectorStatus.VERIFYING: QColor(255, 140, 50),    # Orange
        SectorStatus.UNKNOWN: QColor(100, 100, 100),     # Gray
    }

    # Quality gradient colors (worst to best)
    QUALITY_COLORS = [
        (0.0, QColor(200, 50, 50)),      # Very poor - Red
        (0.3, QColor(255, 140, 50)),     # Poor - Orange
        (0.5, QColor(255, 220, 50)),     # Fair - Yellow
        (0.7, QColor(150, 220, 50)),     # Good - Light green
        (0.9, QColor(0, 180, 0)),        # Excellent - Dark green
    ]

    # Selection colors
    SELECTION_BORDER_COLOR = QColor(0, 180, 255)  # Cyan
    SELECTION_BORDER_WIDTH = 2.0

    # Dimmed color for non-error sectors in ERROR mode
    DIMMED_COLOR = QColor(50, 50, 50, 180)

    def __init__(
        self,
        sector_num: int,
        cylinder: int,
        head: int,
        sector_offset: int,
        inner_radius: float,
        outer_radius: float,
        start_angle: float,
        span_angle: float,
    ):
        """
        Initialize sector wedge item.

        Args:
            sector_num: Logical sector number (0-2879)
            cylinder: Cylinder number (0-79)
            head: Head number (0-1)
            sector_offset: Sector offset within track (0-17)
            inner_radius: Inner radius of the wedge
            outer_radius: Outer radius of the wedge
            start_angle: Starting angle in degrees (0-360)
            span_angle: Angular span of the wedge in degrees
        """
        super().__init__()

        # Sector identification
        self.sector_num = sector_num
        self.cylinder = cylinder
        self.head = head
        self.sector_offset = sector_offset

        # Geometry
        self.inner_radius = inner_radius
        self.outer_radius = outer_radius
        self.start_angle = start_angle
        self.span_angle = span_angle

        # Current state
        self._status = SectorStatus.UNSCANNED
        self._quality = 0.0
        self._view_mode = ViewMode.STATUS
        self._is_selected = False
        self._is_active = False
        self._activity_type = ActivityType.NONE

        # Animation state
        self._current_color = self.STATUS_COLORS[SectorStatus.UNSCANNED]
        self._target_color = self._current_color
        self._animation_progress = 1.0
        self._pulse_phase = 0.0  # For active sector pulse animation
        self._scale_factor = 1.0  # For selection/activity highlight

        # Metadata reference
        self._metadata: Optional[SectorMetadata] = None

        # Enable hover events for tooltips
        self.setAcceptHoverEvents(True)

        # Cache bounding rect
        self._bounding_rect = self._calculate_bounding_rect()

        # Cache device rendering for better performance
        try:
            self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        except Exception:
            pass

        # Cache the wedge path for performance
        self._wedge_path = self._create_wedge_path()
        self._selection_path = self._create_selection_path()

        # Animation timer
        self._animation_timer: Optional[QTimer] = None
        self._animation_duration: int = 200  # ms
        self._animation_interval: int = 16   # ms per frame (~60 FPS)
        self._animation_step: float = self._animation_interval / self._animation_duration

        # Pulse animation timer (for active sectors)
        self._pulse_timer: Optional[QTimer] = None

    def _calculate_bounding_rect(self) -> QRectF:
        """Calculate the bounding rectangle for this wedge."""
        # Add margin for selection border
        margin = self.SELECTION_BORDER_WIDTH + 2
        size = (self.outer_radius + margin) * 2
        return QRectF(
            -self.outer_radius - margin,
            -self.outer_radius - margin,
            size, size
        )

    def _create_wedge_path(self) -> QPainterPath:
        """Create and cache the wedge path for efficient painting."""
        path = QPainterPath()

        # No gap between wedges - adjacent wedges touch exactly
        # Z-ordering ensures inner cylinders render on top of outer ones
        # so there's no z-fighting, and no gaps for outer colors to bleed through
        gap = 0.0
        effective_span = self.span_angle - gap

        # Create outer and inner arc rectangles
        outer_rect = QRectF(
            -self.outer_radius, -self.outer_radius,
            self.outer_radius * 2, self.outer_radius * 2
        )
        inner_rect = QRectF(
            -self.inner_radius, -self.inner_radius,
            self.inner_radius * 2, self.inner_radius * 2
        )

        # Calculate endpoints
        start_rad = math.radians(self.start_angle)
        end_rad = math.radians(self.start_angle + effective_span)

        # Start at inner arc
        inner_start_x = self.inner_radius * math.cos(start_rad)
        inner_start_y = self.inner_radius * math.sin(start_rad)

        # Outer arc start
        outer_start_x = self.outer_radius * math.cos(start_rad)
        outer_start_y = self.outer_radius * math.sin(start_rad)

        # Inner arc end
        inner_end_x = self.inner_radius * math.cos(end_rad)
        inner_end_y = self.inner_radius * math.sin(end_rad)

        # Build path
        path.moveTo(inner_start_x, inner_start_y)
        path.lineTo(outer_start_x, outer_start_y)
        path.arcTo(outer_rect, self.start_angle, effective_span)
        path.lineTo(inner_end_x, inner_end_y)
        path.arcTo(inner_rect, self.start_angle + effective_span, -effective_span)
        path.closeSubpath()

        return path

    def _create_selection_path(self) -> QPainterPath:
        """Create path for selection border."""
        path = QPainterPath()

        # Slightly larger path for selection border
        margin = 1.5
        outer_r = self.outer_radius + margin
        inner_r = self.inner_radius - margin

        gap = 0.0
        effective_span = self.span_angle - gap

        outer_rect = QRectF(-outer_r, -outer_r, outer_r * 2, outer_r * 2)
        inner_rect = QRectF(-inner_r, -inner_r, inner_r * 2, inner_r * 2)

        start_rad = math.radians(self.start_angle)
        end_rad = math.radians(self.start_angle + effective_span)

        inner_start_x = inner_r * math.cos(start_rad)
        inner_start_y = inner_r * math.sin(start_rad)
        outer_start_x = outer_r * math.cos(start_rad)
        outer_start_y = outer_r * math.sin(start_rad)
        inner_end_x = inner_r * math.cos(end_rad)
        inner_end_y = inner_r * math.sin(end_rad)

        path.moveTo(inner_start_x, inner_start_y)
        path.lineTo(outer_start_x, outer_start_y)
        path.arcTo(outer_rect, self.start_angle, effective_span)
        path.lineTo(inner_end_x, inner_end_y)
        path.arcTo(inner_rect, self.start_angle + effective_span, -effective_span)
        path.closeSubpath()

        return path

    def boundingRect(self) -> QRectF:
        """Get the bounding rectangle for collision detection."""
        return self._bounding_rect

    def _get_display_color(self) -> QColor:
        """Get the color to display based on current view mode and state."""
        if self._view_mode == ViewMode.STATUS:
            return self._get_status_color()
        elif self._view_mode == ViewMode.QUALITY:
            return self._get_quality_color()
        elif self._view_mode == ViewMode.ERRORS:
            return self._get_error_mode_color()
        elif self._view_mode == ViewMode.DATA_PATTERN:
            return self._get_data_pattern_color()
        return self._get_status_color()

    def _get_status_color(self) -> QColor:
        """Get color based on sector status."""
        return self.STATUS_COLORS.get(self._status, self.STATUS_COLORS[SectorStatus.UNSCANNED])

    def _get_quality_color(self) -> QColor:
        """Get color based on flux quality (gradient)."""
        quality = self._quality

        # Find the two colors to interpolate between
        lower_threshold = 0.0
        lower_color = self.QUALITY_COLORS[0][1]
        upper_color = self.QUALITY_COLORS[-1][1]

        for i, (threshold, color) in enumerate(self.QUALITY_COLORS):
            if quality <= threshold:
                if i > 0:
                    lower_threshold, lower_color = self.QUALITY_COLORS[i - 1]
                upper_color = color

                # Interpolate
                if threshold > lower_threshold:
                    t = (quality - lower_threshold) / (threshold - lower_threshold)
                else:
                    t = 0.0

                r = int(lower_color.red() + (upper_color.red() - lower_color.red()) * t)
                g = int(lower_color.green() + (upper_color.green() - lower_color.green()) * t)
                b = int(lower_color.blue() + (upper_color.blue() - lower_color.blue()) * t)
                return QColor(r, g, b)

            lower_threshold = threshold
            lower_color = color

        return upper_color

    def _get_error_mode_color(self) -> QColor:
        """Get color for error view mode (only errors highlighted)."""
        if self._status == SectorStatus.BAD:
            return self.STATUS_COLORS[SectorStatus.BAD]
        return self.DIMMED_COLOR

    def _get_data_pattern_color(self) -> QColor:
        """Get color based on data pattern analysis."""
        base = self._get_status_color()
        if self._metadata and self._metadata.data and len(self._metadata.data) > 0:
            data = self._metadata.data
            data_len = len(data)

            # Analyze data pattern for visualization
            # Calculate entropy-like measure and dominant pattern

            # Check for common fill patterns
            first_byte = data[0]
            if all(b == first_byte for b in data[:min(32, data_len)]):
                # Uniform fill pattern - use a distinctive color
                if first_byte == 0x00:
                    return QColor(40, 40, 60)      # Dark blue-gray for zeros
                elif first_byte == 0xFF:
                    return QColor(200, 200, 220)  # Light gray for FF
                elif first_byte == 0xE5:
                    return QColor(100, 150, 100)  # Green for formatted (E5)
                elif first_byte == 0xF6:
                    return QColor(150, 100, 100)  # Red-ish for F6
                else:
                    # Other uniform pattern - base on byte value
                    hue = (first_byte / 255.0) * 0.8  # 0-288 degrees (avoid red)
                    return QColor.fromHslF(hue, 0.5, 0.4)

            # Non-uniform data - calculate simple entropy indicator
            unique_bytes = len(set(data[:min(64, data_len)]))
            entropy_ratio = unique_bytes / min(64, data_len)

            if entropy_ratio > 0.8:
                # High entropy (compressed/encrypted data) - purple tones
                return QColor.fromHslF(0.75, 0.6, 0.45)
            elif entropy_ratio > 0.4:
                # Medium entropy (normal data) - blue tones
                avg_byte = sum(data[:min(64, data_len)]) // min(64, data_len)
                lightness = 0.3 + (avg_byte / 255.0) * 0.4
                return QColor.fromHslF(0.58, 0.5, lightness)
            else:
                # Low entropy (repetitive data) - green tones
                return QColor.fromHslF(0.35, 0.5, 0.45)

        return base

    def paint(self, painter: QPainter, option, widget=None) -> None:
        """Paint the sector wedge."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Calculate display color (with animation interpolation)
        if self._animation_progress < 1.0:
            cc = self._current_color
            r1, g1, b1 = cc.red(), cc.green(), cc.blue()
            target = self._get_display_color()
            r2, g2, b2 = target.red(), target.green(), target.blue()
            p = self._animation_progress
            color = QColor(
                int(r1 + (r2 - r1) * p),
                int(g1 + (g2 - g1) * p),
                int(b1 + (b2 - b1) * p)
            )
        else:
            color = self._get_display_color()

        # Apply pulse effect for active sectors
        if self._is_active and self._activity_type != ActivityType.NONE:
            pulse = 0.5 + 0.5 * math.sin(self._pulse_phase)
            # Make color brighter during pulse
            r = min(255, int(color.red() + 50 * pulse))
            g = min(255, int(color.green() + 50 * pulse))
            b = min(255, int(color.blue() + 50 * pulse))
            color = QColor(r, g, b)

        # Fill the wedge
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(self._wedge_path)

        # Draw selection border if selected
        if self._is_selected:
            pen = QPen(self.SELECTION_BORDER_COLOR, self.SELECTION_BORDER_WIDTH)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self._selection_path)

        # Draw activity indicator
        if self._is_active:
            self._draw_activity_indicator(painter)

    def _draw_activity_indicator(self, painter: QPainter) -> None:
        """Draw a small indicator for active sector."""
        # Calculate center of wedge
        mid_radius = (self.inner_radius + self.outer_radius) / 2
        mid_angle = math.radians(self.start_angle + self.span_angle / 2)

        cx = mid_radius * math.cos(mid_angle)
        cy = mid_radius * math.sin(mid_angle)

        # Draw a small pulsing circle
        pulse = 0.5 + 0.5 * math.sin(self._pulse_phase)
        radius = 3 + 2 * pulse

        if self._activity_type == ActivityType.READING:
            color = QColor(100, 180, 255)  # Light blue
        elif self._activity_type == ActivityType.WRITING:
            color = QColor(200, 100, 255)  # Light purple
        elif self._activity_type == ActivityType.VERIFYING:
            color = QColor(255, 200, 100)  # Light orange
        else:
            color = QColor(255, 255, 255)  # White

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

    def set_status(self, status: SectorStatus, animate: bool = True) -> None:
        """
        Set the sector status.

        Args:
            status: New sector status
            animate: Whether to animate the color transition
        """
        if self._status == status:
            return

        self._status = status
        target_color = self._get_display_color()

        if target_color == self._target_color:
            return

        self._stop_animation_timer()

        if animate:
            self._current_color = self._target_color
            self._target_color = target_color
            self._animation_progress = 0.0
            self._start_animation_timer()
        else:
            self._current_color = target_color
            self._target_color = target_color
            self._animation_progress = 1.0
            self.update()

    def set_quality(self, quality: float) -> None:
        """Set flux quality value (0.0 to 1.0)."""
        self._quality = max(0.0, min(1.0, quality))
        if self._view_mode == ViewMode.QUALITY:
            self.update()

    def set_view_mode(self, mode: ViewMode) -> None:
        """Set the view mode for display."""
        if self._view_mode != mode:
            self._view_mode = mode
            self.update()

    def set_selected(self, selected: bool) -> None:
        """Set selection state."""
        if self._is_selected != selected:
            self._is_selected = selected
            self.update()

    def is_selected(self) -> bool:
        """Check if sector is selected."""
        return self._is_selected

    def set_active(self, active: bool, activity_type: ActivityType = ActivityType.NONE) -> None:
        """Set active state for real-time animation."""
        was_active = self._is_active
        self._is_active = active
        self._activity_type = activity_type

        if active and not was_active:
            self._start_pulse_animation()
        elif not active and was_active:
            self._stop_pulse_animation()

        self.update()

    def set_metadata(self, metadata: SectorMetadata) -> None:
        """Set sector metadata for tooltip and info display."""
        self._metadata = metadata

    def get_metadata(self) -> Optional[SectorMetadata]:
        """Get sector metadata."""
        return self._metadata

    def update_status(self, is_good: Optional[bool], animate: bool = True) -> None:
        """
        Legacy method: Update the sector status with optional animation.

        Args:
            is_good: True if sector is good, False if bad, None if unscanned
            animate: Whether to animate the color transition
        """
        if is_good is None:
            status = SectorStatus.UNSCANNED
        elif is_good:
            status = SectorStatus.GOOD
        else:
            status = SectorStatus.BAD

        self.set_status(status, animate)

    def set_recovering(self, animate: bool = True) -> None:
        """Mark sector as recovering (yellow/orange state)."""
        self.set_status(SectorStatus.RECOVERING, animate)

    def _start_animation_timer(self) -> None:
        """Start the color transition animation timer."""
        self._animation_timer = QTimer()
        self._animation_timer.setInterval(self._animation_interval)
        self._animation_timer.timeout.connect(self._on_animation_tick)
        self._animation_timer.start()

    def _stop_animation_timer(self) -> None:
        """Stop the color transition animation timer."""
        if self._animation_timer is not None:
            try:
                self._animation_timer.stop()
                self._animation_timer.deleteLater()
            except Exception:
                pass
            self._animation_timer = None

    def _on_animation_tick(self) -> None:
        """Advance animation progress."""
        self._animation_progress += self._animation_step
        if self._animation_progress >= 1.0:
            self._animation_progress = 1.0
            self._current_color = self._target_color
            self._stop_animation_timer()
        self.update()

    def _start_pulse_animation(self) -> None:
        """Start pulse animation for active sectors."""
        self._pulse_phase = 0.0
        self._pulse_timer = QTimer()
        self._pulse_timer.setInterval(50)  # 20 FPS for pulse
        self._pulse_timer.timeout.connect(self._on_pulse_tick)
        self._pulse_timer.start()

    def _stop_pulse_animation(self) -> None:
        """Stop pulse animation."""
        if self._pulse_timer is not None:
            try:
                self._pulse_timer.stop()
                self._pulse_timer.deleteLater()
            except Exception:
                pass
            self._pulse_timer = None
        self._pulse_phase = 0.0

    def _on_pulse_tick(self) -> None:
        """Update pulse phase."""
        self._pulse_phase += 0.3
        if self._pulse_phase > 2 * math.pi:
            self._pulse_phase -= 2 * math.pi
        self.update()

    @pyqtProperty(float)
    def animationProgress(self) -> float:
        """Get animation progress (for QPropertyAnimation)."""
        return self._animation_progress

    @animationProgress.setter
    def animationProgress(self, value: float) -> None:
        """Set animation progress (for QPropertyAnimation)."""
        self._animation_progress = value
        self.update()

    def hoverEnterEvent(self, event) -> None:
        """Handle mouse hover enter event - show tooltip."""
        tooltip_lines = [
            f"Sector {self.sector_num}",
            f"C:{self.cylinder} H:{self.head} S:{self.sector_offset + 1}",
            f"Status: {self._status.name.capitalize()}"
        ]

        if self._metadata:
            if self._metadata.quality > 0:
                tooltip_lines.append(f"Quality: {int(self._metadata.quality * 100)}%")
            if self._metadata.error_type:
                tooltip_lines.append(f"Error: {self._metadata.error_type}")
            tooltip_lines.append(f"CRC: {'Valid' if self._metadata.crc_valid else 'Invalid'}")
        elif self._quality > 0:
            tooltip_lines.append(f"Quality: {int(self._quality * 100)}%")

        tooltip_text = "\n".join(tooltip_lines)
        QToolTip.showText(event.screenPos(), tooltip_text)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        """Handle mouse hover leave event."""
        QToolTip.hideText()
        super().hoverLeaveEvent(event)


# =============================================================================
# Circular Sector Map
# =============================================================================


class CircularSectorMap(QGraphicsView):
    """
    Circular visualization of all 2,880 sectors on a 1.44MB floppy disk.

    Displays sectors in a circular layout with 80 concentric rings (cylinders),
    each divided into 36 wedges (18 sectors x 2 heads).

    Phase 6 Enhancements:
    - Selection mode with click, Shift+click, Ctrl+click
    - Zoom to track with double-click
    - Pan with click-and-drag when zoomed
    - View mode switching (Status/Quality/Errors/Data Pattern)
    - Real-time activity animations
    - Export to PNG/SVG

    Signals:
        sector_hovered(int): Emitted when a sector is hovered (sector number)
        sector_clicked(int): Emitted when a sector is clicked
        selection_changed(list): Emitted when selection changes (list of sector numbers)
        zoom_changed(float): Emitted when zoom level changes
    """

    # Signals
    sector_hovered = pyqtSignal(int)
    sector_clicked = pyqtSignal(int)
    selection_changed = pyqtSignal(list)
    zoom_changed = pyqtSignal(float)
    double_clicked = pyqtSignal(int)  # cylinder number

    # Layout constants matching real floppy disk geometry:
    # - Cylinder 0 is at the OUTER edge (largest radius)
    # - Cylinder 79 is at the INNER edge (smallest radius, near spindle)
    # - Each track has 18 sectors spanning 360 degrees (20° per sector)
    CENTER_HOLE_RADIUS = 50  # Spindle hole visual
    INNER_RADIUS = 55        # Where cylinder 79 (innermost track) ends
    OUTER_RADIUS = 350       # Where cylinder 0 (outermost track) starts
    RING_WIDTH = (350 - 55) / 80  # ~3.6875 pixels per cylinder

    def __init__(self, parent=None, head_filter: Optional[int] = None):
        """
        Initialize circular sector map.

        Args:
            parent: Parent widget
            head_filter: If specified (0 or 1), only show sectors for that head.
                        If None, show both heads (legacy mode with 180-degree halves).
        """
        super().__init__(parent)

        # Head filter: None = both heads, 0 = head 0 only, 1 = head 1 only
        self._head_filter = head_filter

        # Create scene
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # Enable anti-aliasing
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Full viewport update for smooth animations
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

        # Dark background
        self.scene.setBackgroundBrush(QBrush(QColor(40, 40, 40)))

        # Configure view
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        # State
        self._wedges: Dict[int, SectorWedgeItem] = {}
        self._selected_sectors: Set[int] = set()
        self._view_mode = ViewMode.STATUS
        self._zoom_level = 1.0
        self._min_zoom = 0.5
        self._max_zoom = 4.0
        self._selectable = True
        self._last_clicked_sector: Optional[int] = None

        # Pan state
        self._is_panning = False
        self._pan_start_pos = QPointF()

        # Activity tracking (for trail effect)
        self._activity_trail: List[Tuple[int, float]] = []  # (sector_num, timestamp)
        self._trail_duration = 2.0  # seconds
        self._trail_timer: Optional[QTimer] = None

        # Data cache - only cache sectors for the filtered head if applicable
        self._data_cache = SectorDataCache()

        # Create the disk visualization
        self._create_disk_base()
        self._create_wedges()
        self._create_center_hole()

        # Set scene rect
        margin = 20
        total_size = (self.OUTER_RADIUS + margin) * 2
        self.scene.setSceneRect(
            -self.OUTER_RADIUS - margin,
            -self.OUTER_RADIUS - margin,
            total_size,
            total_size,
        )

        # Fit view to content
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Start trail cleanup timer
        self._start_trail_timer()

    def _create_disk_base(self) -> None:
        """Create the disk base (outer ring/bezel)."""
        outer_disk = QGraphicsEllipseItem(
            -self.OUTER_RADIUS - 5, -self.OUTER_RADIUS - 5,
            (self.OUTER_RADIUS + 5) * 2, (self.OUTER_RADIUS + 5) * 2
        )
        outer_disk.setBrush(QBrush(QColor(60, 60, 60)))
        outer_disk.setPen(QPen(QColor(80, 80, 80), 2))
        outer_disk.setZValue(-100)
        self.scene.addItem(outer_disk)

    def _create_center_hole(self) -> None:
        """Create the center spindle hole."""
        center_hole = QGraphicsEllipseItem(
            -self.CENTER_HOLE_RADIUS, -self.CENTER_HOLE_RADIUS,
            self.CENTER_HOLE_RADIUS * 2, self.CENTER_HOLE_RADIUS * 2
        )
        center_hole.setBrush(QBrush(QColor(30, 30, 30)))
        center_hole.setPen(QPen(QColor(50, 50, 50), 2))
        center_hole.setZValue(1000)
        self.scene.addItem(center_hole)

        # Metal ring around hole
        metal_ring = QGraphicsEllipseItem(
            -self.CENTER_HOLE_RADIUS - 8, -self.CENTER_HOLE_RADIUS - 8,
            (self.CENTER_HOLE_RADIUS + 8) * 2, (self.CENTER_HOLE_RADIUS + 8) * 2
        )
        metal_ring.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        metal_ring.setPen(QPen(QColor(100, 100, 100), 3))
        metal_ring.setZValue(999)
        self.scene.addItem(metal_ring)

    def _create_wedges(self) -> None:
        """Create sector wedge items matching real floppy disk geometry.

        Real floppy disk layout:
        - 80 cylinders (cylinder 0 = outermost track, cylinder 79 = innermost)
        - 2 heads (sides of the disk)
        - 18 sectors per track, each spanning 20 degrees (360° / 18)

        When head_filter is None (both heads mode):
            - Creates 2,880 wedges (80 cylinders × 2 heads × 18 sectors)
            - Each head occupies 180 degrees (head 0: right half, head 1: left half)

        When head_filter is 0 or 1 (single head mode):
            - Creates 1,440 wedges for the specified head only
            - Uses full 360 degrees, 20 degrees per sector
        """
        total_sectors = 2880
        sectors_per_track = 18

        # Each sector spans 20 degrees (full circle / 18 sectors)
        # This is physically accurate - all tracks have same angular sector spacing
        sector_span = 360.0 / sectors_per_track  # 20 degrees

        for sector_num in range(total_sectors):
            cylinder = sector_num // (sectors_per_track * 2)
            head = (sector_num // sectors_per_track) % 2
            sector_offset = sector_num % sectors_per_track

            # Skip sectors not matching the head filter
            if self._head_filter is not None and head != self._head_filter:
                continue

            # Calculate angle - sector position around the disk
            # Start at top (-90 degrees from horizontal, i.e., 12 o'clock) and go clockwise
            # Each of the 18 sectors spans 20 degrees
            if self._head_filter is not None:
                # Single head mode: full 360 degrees
                angle = (sector_offset * sector_span) - 90
            else:
                # Both heads mode: each head gets 180 degrees
                # Head 0: right half (-90 to +90), Head 1: left half (+90 to +270)
                half_span = 180.0 / sectors_per_track  # 10 degrees per sector in this mode
                angle = (head * 180) + (sector_offset * half_span) - 90
                sector_span = half_span  # Use reduced span for both-heads mode

            # Calculate radius - cylinder 0 at OUTER edge, cylinder 79 at INNER edge
            # This matches real floppy disk geometry where track 0 is outermost
            outer_radius = self.OUTER_RADIUS - (cylinder * self.RING_WIDTH)
            inner_radius = outer_radius - self.RING_WIDTH

            wedge = SectorWedgeItem(
                sector_num=sector_num,
                cylinder=cylinder,
                head=head,
                sector_offset=sector_offset,
                inner_radius=inner_radius,
                outer_radius=outer_radius,
                start_angle=angle,
                span_angle=sector_span,
            )

            self.scene.addItem(wedge)
            # Z-order: inner cylinders (higher number) drawn on top of outer ones
            wedge.setZValue(cylinder)
            self._wedges[sector_num] = wedge

            # Link metadata
            metadata = self._data_cache.get_metadata(sector_num)
            if metadata:
                wedge.set_metadata(metadata)

            # Reset sector_span for next iteration if we modified it
            sector_span = 360.0 / sectors_per_track

    def _start_trail_timer(self) -> None:
        """Start timer for cleaning up activity trail."""
        self._trail_timer = QTimer(self)
        self._trail_timer.setInterval(200)
        self._trail_timer.timeout.connect(self._cleanup_trail)
        self._trail_timer.start()

    def _cleanup_trail(self) -> None:
        """Remove old entries from activity trail."""
        current_time = time.time()
        cutoff_time = current_time - self._trail_duration

        # Remove expired entries
        self._activity_trail = [
            (sector, timestamp) for sector, timestamp in self._activity_trail
            if timestamp > cutoff_time
        ]

    # =========================================================================
    # Public API - View Mode
    # =========================================================================

    def set_view_mode(self, mode: ViewMode) -> None:
        """
        Set the view mode for display.

        Args:
            mode: ViewMode enum value
        """
        if self._view_mode != mode:
            self._view_mode = mode
            for wedge in self._wedges.values():
                wedge.set_view_mode(mode)

    def get_view_mode(self) -> ViewMode:
        """Get current view mode."""
        return self._view_mode

    def get_head_filter(self) -> Optional[int]:
        """Get the head filter (0, 1, or None for both)."""
        return self._head_filter

    def select_sector(self, sector_num: int) -> None:
        """Select a single sector (clearing previous selection)."""
        self.clear_selection()
        if sector_num in self._wedges:
            self._selected_sectors.add(sector_num)
            self._wedges[sector_num].set_selected(True)
            self.selection_changed.emit(self.get_selected_sectors())

    def center_on_sector(self, sector_num: int) -> None:
        """Center the view on a specific sector."""
        if sector_num not in self._wedges:
            return

        wedge = self._wedges[sector_num]
        # Calculate center of wedge
        mid_radius = (wedge.inner_radius + wedge.outer_radius) / 2
        mid_angle = math.radians(wedge.start_angle + wedge.span_angle / 2)
        cx = mid_radius * math.cos(mid_angle)
        cy = mid_radius * math.sin(mid_angle)

        self.centerOn(cx, cy)

    # =========================================================================
    # Public API - Sector Status
    # =========================================================================

    def update_sector(self, sector_num: int, is_good: Optional[bool], animate: bool = True) -> None:
        """Update the status of a single sector (legacy method)."""
        if sector_num in self._wedges:
            self._wedges[sector_num].update_status(is_good, animate)
            # Update cache
            if is_good is None:
                self._data_cache.set_status(sector_num, SectorStatus.UNSCANNED)
            elif is_good:
                self._data_cache.set_status(sector_num, SectorStatus.GOOD)
            else:
                self._data_cache.set_status(sector_num, SectorStatus.BAD)

    def set_sector_status(
        self, sector_num: int, status: SectorStatus, animate: bool = True
    ) -> None:
        """Set sector status using SectorStatus enum."""
        if sector_num in self._wedges:
            self._wedges[sector_num].set_status(status, animate)
            self._data_cache.set_status(sector_num, status)

    def set_sector_quality(self, sector_num: int, quality: float) -> None:
        """Set flux quality for a sector (0.0 to 1.0)."""
        if sector_num in self._wedges:
            self._wedges[sector_num].set_quality(quality)
            self._data_cache.set_quality(sector_num, quality)

    def set_sector_metadata(self, sector_num: int, metadata: SectorMetadata) -> None:
        """Set complete metadata for a sector."""
        if sector_num in self._wedges:
            self._wedges[sector_num].set_metadata(metadata)
            # Update cache
            self._data_cache._metadata[sector_num] = metadata

    def update_all_sectors(
        self, sector_statuses: Dict[int, Optional[bool]], animate: bool = False
    ) -> None:
        """Update multiple sectors at once."""
        for sector_num, is_good in sector_statuses.items():
            if sector_num in self._wedges:
                self._wedges[sector_num].update_status(is_good, animate)

    def reset_all_sectors(self) -> None:
        """Reset all sectors to unscanned state."""
        for wedge in self._wedges.values():
            wedge.update_status(None, animate=False)
        self._data_cache.clear()
        self._selected_sectors.clear()
        self.selection_changed.emit([])

    def mark_all_good(self) -> None:
        """Mark all sectors as good."""
        for wedge in self._wedges.values():
            wedge.update_status(True, animate=False)

    def mark_all_bad(self) -> None:
        """Mark all sectors as bad."""
        for wedge in self._wedges.values():
            wedge.update_status(False, animate=False)

    def mark_sector_recovering(self, sector_num: int, animate: bool = True) -> None:
        """Mark a sector as recovering."""
        if sector_num in self._wedges:
            self._wedges[sector_num].set_recovering(animate)

    # =========================================================================
    # Public API - Activity Animation
    # =========================================================================

    def set_active_sector(self, sector_num: int, activity: ActivityType) -> None:
        """
        Set a sector as active with animation.

        Args:
            sector_num: Sector number to activate
            activity: Type of activity (READING, WRITING, VERIFYING, or NONE to deactivate)
        """
        # Deactivate previous active sectors
        for wedge in self._wedges.values():
            if wedge._is_active and wedge.sector_num != sector_num:
                wedge.set_active(False)

        # Activate the specified sector
        if sector_num in self._wedges:
            is_active = activity != ActivityType.NONE
            self._wedges[sector_num].set_active(is_active, activity)

            # Add to trail
            if is_active:
                self._activity_trail.append((sector_num, time.time()))

    def clear_active_sectors(self) -> None:
        """Clear all active sector animations."""
        for wedge in self._wedges.values():
            wedge.set_active(False)

    # =========================================================================
    # Public API - Selection
    # =========================================================================

    def set_selectable(self, selectable: bool) -> None:
        """Enable or disable selection mode."""
        self._selectable = selectable
        if not selectable:
            self.clear_selection()

    def is_selectable(self) -> bool:
        """Check if selection is enabled."""
        return self._selectable

    def get_selected_sectors(self) -> List[int]:
        """Get list of selected sector numbers."""
        return sorted(list(self._selected_sectors))

    def set_selected_sectors(self, sectors: List[int]) -> None:
        """Set the selected sectors."""
        # Clear current selection
        for sector_num in self._selected_sectors:
            if sector_num in self._wedges:
                self._wedges[sector_num].set_selected(False)

        # Set new selection
        self._selected_sectors = set(sectors)
        for sector_num in self._selected_sectors:
            if sector_num in self._wedges:
                self._wedges[sector_num].set_selected(True)

        self.selection_changed.emit(self.get_selected_sectors())

    def clear_selection(self) -> None:
        """Clear all selection."""
        for sector_num in self._selected_sectors:
            if sector_num in self._wedges:
                self._wedges[sector_num].set_selected(False)
        self._selected_sectors.clear()
        self.selection_changed.emit([])

    def select_all_bad_sectors(self) -> None:
        """Select all sectors with bad status."""
        bad_sectors = self._data_cache.get_bad_sectors()
        self.set_selected_sectors(bad_sectors)

    def invert_selection(self) -> None:
        """Invert the current selection."""
        all_sectors = set(range(2880))
        inverted = all_sectors - self._selected_sectors
        self.set_selected_sectors(list(inverted))

    def _toggle_sector_selection(self, sector_num: int) -> None:
        """Toggle selection of a single sector."""
        if sector_num in self._selected_sectors:
            self._selected_sectors.remove(sector_num)
            if sector_num in self._wedges:
                self._wedges[sector_num].set_selected(False)
        else:
            self._selected_sectors.add(sector_num)
            if sector_num in self._wedges:
                self._wedges[sector_num].set_selected(True)

        self.selection_changed.emit(self.get_selected_sectors())

    def _select_range(self, start_sector: int, end_sector: int) -> None:
        """Select a range of sectors."""
        min_sector = min(start_sector, end_sector)
        max_sector = max(start_sector, end_sector)

        for sector_num in range(min_sector, max_sector + 1):
            self._selected_sectors.add(sector_num)
            if sector_num in self._wedges:
                self._wedges[sector_num].set_selected(True)

        self.selection_changed.emit(self.get_selected_sectors())

    # =========================================================================
    # Public API - Zoom
    # =========================================================================

    def set_zoom_level(self, level: float) -> None:
        """
        Set zoom level.

        Args:
            level: Zoom level (1.0 = 100%, 2.0 = 200%, etc.)
        """
        level = max(self._min_zoom, min(self._max_zoom, level))

        if abs(level - self._zoom_level) < 0.01:
            return

        # Calculate scale factor
        scale_factor = level / self._zoom_level
        self._zoom_level = level

        self.scale(scale_factor, scale_factor)
        self.zoom_changed.emit(level)

    def get_zoom_level(self) -> float:
        """Get current zoom level."""
        return self._zoom_level

    def zoom_to_fit(self) -> None:
        """Reset zoom to fit entire disk in view."""
        self.resetTransform()
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_level = 1.0
        self.zoom_changed.emit(1.0)

    def zoom_to_cylinder(self, cylinder: int) -> None:
        """
        Zoom to show a specific cylinder in detail.

        Args:
            cylinder: Cylinder number (0-79)
        """
        if cylinder < 0 or cylinder > 79:
            return

        # Calculate the radius range for this cylinder
        # Cylinder 0 is at outer edge, cylinder 79 at inner edge
        outer_r = self.OUTER_RADIUS - (cylinder * self.RING_WIDTH)
        inner_r = outer_r - self.RING_WIDTH

        # Create a rect around this cylinder ring
        margin = self.RING_WIDTH * 3
        rect = QRectF(
            -outer_r - margin, -outer_r - margin,
            (outer_r + margin) * 2, (outer_r + margin) * 2
        )

        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

        # Update zoom level based on transform
        transform = self.transform()
        self._zoom_level = transform.m11()  # Horizontal scale
        self.zoom_changed.emit(self._zoom_level)

    # =========================================================================
    # Public API - Export
    # =========================================================================

    def export_to_png(self, filepath: str, width: int = 1024, height: int = 1024) -> bool:
        """
        Export sector map to PNG image.

        Args:
            filepath: Path to save the PNG file
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            True if export was successful
        """
        try:
            # Create image
            image = QImage(width, height, QImage.Format.Format_ARGB32)
            image.fill(QColor(40, 40, 40))

            # Create painter
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            # Render scene
            self.scene.render(painter)

            # Draw legend
            self._draw_legend(painter, width, height)

            painter.end()

            # Save image
            return image.save(filepath)

        except Exception:
            return False

    def export_to_svg(self, filepath: str) -> bool:
        """
        Export sector map to SVG vector image.

        Args:
            filepath: Path to save the SVG file

        Returns:
            True if export was successful
        """
        try:
            # Create SVG generator
            generator = QSvgGenerator()
            generator.setFileName(filepath)
            generator.setSize(QSize(1024, 1024))
            generator.setViewBox(self.scene.sceneRect())
            generator.setTitle("Floppy Workbench Sector Map")
            generator.setDescription("Sector map export from Floppy Workbench")

            # Create painter
            painter = QPainter(generator)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            # Render scene
            self.scene.render(painter)

            painter.end()
            return True

        except Exception:
            return False

    def _draw_legend(self, painter: QPainter, width: int, height: int) -> None:
        """Draw a legend on the exported image."""
        legend_items = [
            ("Good", SectorWedgeItem.STATUS_COLORS[SectorStatus.GOOD]),
            ("Bad", SectorWedgeItem.STATUS_COLORS[SectorStatus.BAD]),
            ("Weak", SectorWedgeItem.STATUS_COLORS[SectorStatus.WEAK]),
            ("Recovered", SectorWedgeItem.STATUS_COLORS[SectorStatus.RECOVERED]),
            ("Reading", SectorWedgeItem.STATUS_COLORS[SectorStatus.READING]),
            ("Writing", SectorWedgeItem.STATUS_COLORS[SectorStatus.WRITING]),
            ("Recovering", SectorWedgeItem.STATUS_COLORS[SectorStatus.RECOVERING]),
            ("Unscanned", SectorWedgeItem.STATUS_COLORS[SectorStatus.UNSCANNED]),
        ]

        # Position legend at bottom right
        x_start = width - 150
        y_start = height - 20 - (len(legend_items) * 25)

        # Draw legend background
        painter.setBrush(QBrush(QColor(30, 30, 30, 200)))
        painter.setPen(QPen(QColor(80, 80, 80)))
        painter.drawRoundedRect(x_start - 10, y_start - 10,
                                150, len(legend_items) * 25 + 15, 5, 5)

        # Draw legend items
        painter.setPen(QPen(QColor(200, 200, 200)))
        for i, (label, color) in enumerate(legend_items):
            y = y_start + i * 25

            # Color box
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(x_start, y, 20, 15)

            # Label
            painter.setPen(QPen(QColor(200, 200, 200)))
            painter.drawText(x_start + 30, y + 12, label)

    # =========================================================================
    # Data Cache Access
    # =========================================================================

    def get_data_cache(self) -> SectorDataCache:
        """Get the sector data cache."""
        return self._data_cache

    def store_sector_data(self, sector_num: int, data: bytes) -> None:
        """Store sector data bytes."""
        self._data_cache.store_sector_data(sector_num, data)

    def store_flux_quality(self, sector_num: int, metrics: FluxQualityMetrics) -> None:
        """Store flux quality metrics for a sector."""
        self._data_cache.store_flux_quality(sector_num, metrics)
        if sector_num in self._wedges:
            self._wedges[sector_num].set_quality(metrics.get_overall_quality())

    def add_sector_history(
        self, sector_num: int, operation: str, result: str, details: str = ""
    ) -> None:
        """Add a history entry for a sector."""
        self._data_cache.add_history_entry(sector_num, operation, result, details)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_sector_count(self) -> int:
        """Get total number of sectors."""
        return len(self._wedges)

    def get_sector_at_point(self, pos: QPointF) -> Optional[int]:
        """
        Get sector number at a scene position.

        Args:
            pos: Position in scene coordinates

        Returns:
            Sector number or None if not on a sector
        """
        item = self.scene.itemAt(pos, self.transform())
        if isinstance(item, SectorWedgeItem):
            return item.sector_num
        return None

    def get_cylinder_at_point(self, pos: QPointF) -> Optional[int]:
        """
        Get cylinder number at a scene position.

        Args:
            pos: Position in scene coordinates

        Returns:
            Cylinder number (0-79) or None if not on disk
        """
        # Calculate distance from center
        distance = math.sqrt(pos.x() ** 2 + pos.y() ** 2)

        if distance < self.INNER_RADIUS or distance > self.OUTER_RADIUS:
            return None

        # Calculate cylinder - cylinder 0 is at OUTER edge, cylinder 79 at INNER edge
        cylinder = int((self.OUTER_RADIUS - distance) / self.RING_WIDTH)
        return max(0, min(79, cylinder))

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def wheelEvent(self, event) -> None:
        """Handle mouse wheel for zooming."""
        zoom_factor = 1.15
        if event.angleDelta().y() > 0:
            new_zoom = self._zoom_level * zoom_factor
        else:
            new_zoom = self._zoom_level / zoom_factor

        self.set_zoom_level(new_zoom)

    def mousePressEvent(self, event) -> None:
        """Handle mouse press event."""
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            sector = self.get_sector_at_point(scene_pos)

            if sector is not None and self._selectable:
                modifiers = QApplication.keyboardModifiers()

                if modifiers & Qt.KeyboardModifier.ControlModifier:
                    # Ctrl+click: toggle single sector
                    self._toggle_sector_selection(sector)
                elif modifiers & Qt.KeyboardModifier.ShiftModifier:
                    # Shift+click: select range
                    if self._last_clicked_sector is not None:
                        self._select_range(self._last_clicked_sector, sector)
                    else:
                        self._toggle_sector_selection(sector)
                else:
                    # Regular click: clear and select single
                    self.clear_selection()
                    self._toggle_sector_selection(sector)

                self._last_clicked_sector = sector
                self.sector_clicked.emit(sector)
            else:
                # Start panning if not on a sector
                self._is_panning = True
                self._pan_start_pos = event.pos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release event."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move event."""
        if self._is_panning:
            # Pan the view
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()

            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
        else:
            # Track hover for sector_hovered signal
            scene_pos = self.mapToScene(event.pos())
            sector = self.get_sector_at_point(scene_pos)
            if sector is not None:
                self.sector_hovered.emit(sector)

        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double-click event."""
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            cylinder = self.get_cylinder_at_point(scene_pos)

            if cylinder is not None:
                self.zoom_to_cylinder(cylinder)
                self.double_clicked.emit(cylinder)

        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event) -> None:
        """Handle resize to maintain aspect ratio."""
        super().resizeEvent(event)
        if self._zoom_level == 1.0:
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
