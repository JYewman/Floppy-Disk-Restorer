"""
TUI widgets for USB Floppy Formatter.

This module contains reusable widgets:
- SectorMap: Visual sector map visualization
- ProgressPanel: Progress display with convergence tracking
- StatsPanel: Statistics display panel
"""

from floppy_formatter.tui.widgets.sector_map import SectorMapWidget
from floppy_formatter.tui.widgets.progress_panel import ProgressPanel
from floppy_formatter.tui.widgets.stats_panel import StatsPanel

__all__ = [
    "SectorMapWidget",
    "ProgressPanel",
    "StatsPanel",
]
