"""
Screen widgets for Floppy Workbench GUI.

Contains operation screens for scan, format, restore, and report generation.
The main application now uses a single-page workbench layout with these
screens available as operation dialogs/components.

Note: MainMenuWidget and DriveSelectWidget have been removed in v2.0.0
as they were replaced by the workbench GUI layout with DriveControlPanel
and OperationToolbar.
"""

from floppy_formatter.gui.screens.scan_screen import ScanWidget
from floppy_formatter.gui.screens.format_screen import FormatWidget
from floppy_formatter.gui.screens.restore_screen import RestoreWidget
from floppy_formatter.gui.screens.report_screen import ReportWidget
from floppy_formatter.gui.screens.session_screen import SessionScreen

__all__ = [
    "ScanWidget",
    "FormatWidget",
    "RestoreWidget",
    "ReportWidget",
    "SessionScreen",
]
