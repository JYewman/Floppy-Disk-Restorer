"""
Custom widgets for Floppy Workbench GUI.

Contains reusable UI components for the workbench interface:
- Circular sector map with selection, zoom, and quality overlay
- Sector map toolbar with view/zoom/selection/export controls
- Sector info panel with detailed sector information
- Convergence graph for recovery visualization
- Flux waveform widget for oscilloscope-style visualization
- Flux histogram widget for pulse width distribution
- Timing jitter widget for scatter plot visualization
- Loading skeleton widgets with shimmer animation
- Animated buttons with hover, press, and ripple effects

Part of Phase 6-8, 14: Enhanced Sector Map, Analytics Dashboard, Flux Visualization, and Polish
"""

# Circular sector map and related classes
from floppy_formatter.gui.widgets.circular_sector_map import (
    # Main widget
    CircularSectorMap,
    SectorWedgeItem,
    # Enums
    SectorStatus,
    ViewMode,
    ActivityType,
    # Data classes
    SectorMetadata,
    FluxQualityMetrics,
    HistoryEntry,
    # Cache
    SectorDataCache,
)

# Sector map toolbar
from floppy_formatter.gui.widgets.sector_map_toolbar import (
    SectorMapToolbar,
    ViewModeButton,
    ZoomButton,
)

# Sector info panel
from floppy_formatter.gui.widgets.sector_info_panel import (
    SectorInfoPanel,
    StatusIndicator,
    CollapsibleSection,
    HexDumpWidget,
    QualityMetricsWidget,
)

# Convergence graph
from floppy_formatter.gui.widgets.convergence_graph import ConvergenceGraphWidget

# Flux visualization widgets
from floppy_formatter.gui.widgets.flux_waveform_widget import (
    FluxWaveformWidget,
    FluxWaveformPanel,
    FluxMarker,
    MarkerType,
    TransitionPoint,
)

from floppy_formatter.gui.widgets.flux_histogram_widget import (
    FluxHistogramWidget,
    FluxHistogramPanel,
    GaussianFit,
    HistogramData,
    DetectedPeak,
    PeakAnalysis,
)

# Timing jitter widget
from floppy_formatter.gui.widgets.timing_jitter_widget import (
    TimingJitterWidget,
    TimingJitterPanel,
    JitterPoint,
    JitterStatistics,
    TrendLine,
)

# Loading skeleton widgets (Phase 14)
from floppy_formatter.gui.widgets.loading_skeleton import (
    SkeletonWidget,
    SkeletonText,
    SkeletonCard,
    SkeletonTable,
    SkeletonSectorMap,
    LoadingStateManager,
)

# Animated button widgets (Phase 14)
from floppy_formatter.gui.widgets.animated_button import (
    AnimatedButton,
    IconButton,
    OperationButton,
    ToggleButton,
)

# Session indicator widget (Phase 4)
from floppy_formatter.gui.widgets.session_indicator import (
    SessionIndicator,
    SessionIndicatorCompact,
)


__all__ = [
    # Circular sector map
    "CircularSectorMap",
    "SectorWedgeItem",
    # Enums
    "SectorStatus",
    "ViewMode",
    "ActivityType",
    # Data classes
    "SectorMetadata",
    "FluxQualityMetrics",
    "HistoryEntry",
    # Cache
    "SectorDataCache",
    # Sector map toolbar
    "SectorMapToolbar",
    "ViewModeButton",
    "ZoomButton",
    # Sector info panel
    "SectorInfoPanel",
    "StatusIndicator",
    "CollapsibleSection",
    "HexDumpWidget",
    "QualityMetricsWidget",
    # Convergence graph
    "ConvergenceGraphWidget",
    # Flux waveform widget
    "FluxWaveformWidget",
    "FluxWaveformPanel",
    "FluxMarker",
    "MarkerType",
    "TransitionPoint",
    # Flux histogram widget
    "FluxHistogramWidget",
    "FluxHistogramPanel",
    "GaussianFit",
    "HistogramData",
    "DetectedPeak",
    "PeakAnalysis",
    # Timing jitter widget
    "TimingJitterWidget",
    "TimingJitterPanel",
    "JitterPoint",
    "JitterStatistics",
    "TrendLine",
    # Loading skeleton widgets (Phase 14)
    "SkeletonWidget",
    "SkeletonText",
    "SkeletonCard",
    "SkeletonTable",
    "SkeletonSectorMap",
    "LoadingStateManager",
    # Animated button widgets (Phase 14)
    "AnimatedButton",
    "IconButton",
    "OperationButton",
    "ToggleButton",
    # Session indicator widget (Phase 4)
    "SessionIndicator",
    "SessionIndicatorCompact",
]
