"""
TUI (Text User Interface) module for USB Floppy Formatter.

This module provides the interactive Textual-based interface including
screens for drive selection, scanning, formatting, recovery operations,
and report viewing.
"""

from floppy_formatter.tui.app import FloppyFormatterApp

__all__ = [
    "FloppyFormatterApp",
]
