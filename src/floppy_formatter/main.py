"""
Main entry point for USB Floppy Formatter.

This module provides the main() function that launches the Textual TUI application.
"""

from floppy_formatter.tui.app import FloppyFormatterApp


def main():
    """
    Main entry point for USB Floppy Formatter.

    Launches the Textual TUI application with admin privilege checking
    and drive detection.
    """
    app = FloppyFormatterApp()
    app.run()


if __name__ == "__main__":
    main()
