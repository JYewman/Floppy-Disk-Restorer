"""
Main Textual application for USB Floppy Formatter.

This module contains the primary application class that manages screens,
key bindings, and overall application state.
"""

import logging
from pathlib import Path
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static, Button
from textual.containers import Container

# Import utilities
from floppy_formatter.utils import setup_logging, is_admin

# Import screens
from floppy_formatter.tui.screens.main_menu import MainMenu


class AdminWarningScreen(Screen):
    """Warning screen shown when not running as root."""

    def compose(self) -> ComposeResult:
        """Create root privilege warning screen."""
        yield Container(
            Static("⚠ Root Privileges Required", classes="warning-title"),
            Static(
                "This application requires root privileges to access block devices.\n\n"
                "To run with root privileges:\n"
                "1. Use sudo: sudo python3 -m floppy_formatter\n"
                "2. Or: sudo floppy-format\n\n"
                "Without root access, the application cannot:\n"
                "• Open block devices (/dev/sdX)\n"
                "• Read/write sectors directly\n"
                "• Perform low-level formatting operations",
                classes="warning-message"
            ),
            Button("Exit Application", variant="error", id="exit"),
            classes="warning-container"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "exit":
            self.app.exit()


class FloppyFormatterApp(App):
    """
    Main Textual application for USB Floppy Formatter.

    Provides an interactive TUI for floppy disk operations including
    scanning, formatting, and recovery with real-time progress display.
    """

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("d", "toggle_dark", "Toggle Dark Mode", show=True),
        Binding("escape", "back", "Back", show=False),
    ]

    TITLE = "USB Floppy Formatter"
    SUB_TITLE = "v0.1.0"

    def __init__(self):
        """Initialize the application."""
        super().__init__()
        self.dark = True

        # Set up logging on initialization
        setup_logging()
        logging.info("USB Floppy Formatter application starting")

    def on_mount(self) -> None:
        """Handle application mount - check root privileges and start."""
        if not is_admin():
            logging.warning("Application started without root privileges")
            self.push_screen(AdminWarningScreen())
        else:
            logging.info("Application started with root privileges")
            self.push_screen(MainMenu())

    def action_back(self) -> None:
        """Navigate back to previous screen (Escape key)."""
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_toggle_dark(self) -> None:
        """Toggle dark mode (D key)."""
        self.dark = not self.dark

    def action_quit(self) -> None:
        """Quit the application (Q key)."""
        self.exit()
