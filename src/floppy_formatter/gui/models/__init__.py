"""
GUI data models for Floppy Workbench.

This module provides data models for efficient handling of flux data
with lazy loading, caching, and background processing.

Part of Phase 8: Flux Visualization Widgets
"""

from floppy_formatter.gui.models.flux_data_model import (
    # Enums
    TrackState,
    # Dataclasses
    SectorData,
    TrackQuality,
    HistogramResult,
    JitterResult,
    TrackAnalysis,
    TrackFluxData,
    # Utility classes
    LRUCache,
    # Worker classes
    AnalysisWorker,
    # Main model
    FluxDataModel,
)

__all__ = [
    # Enums
    'TrackState',
    # Dataclasses
    'SectorData',
    'TrackQuality',
    'HistogramResult',
    'JitterResult',
    'TrackAnalysis',
    'TrackFluxData',
    # Utility classes
    'LRUCache',
    # Worker classes
    'AnalysisWorker',
    # Main model
    'FluxDataModel',
]
