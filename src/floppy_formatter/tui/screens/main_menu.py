"""
Main menu screen for USB Floppy Formatter.

Provides the primary navigation menu for selecting operations:
- Scan Disk
- Format Disk
- Restore Disk (Recovery)
- View Reports
- Settings
- Exit
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Static
from textual.containers import Container, Vertical


class MainMenu(Screen):
    """Main menu with operation selection."""

    def compose(self) -> ComposeResult:
        """Create main menu screen layout."""
        yield Header()
        yield Container(
            Vertical(
                Static(
                    "[bold cyan]USB Floppy Formatter[/bold cyan]\n"
                    "[dim]Professional Floppy Disk Recovery Tool[/dim]",
                    classes="title"
                ),
                Static(""),  # Spacer
                Button("Scan Disk", id="scan", variant="primary"),
                Button("Format Disk", id="format"),
                Button("Restore Disk (Recovery)", id="restore", variant="success"),
                Button("View Reports", id="reports"),
                Button("Settings", id="settings"),
                Button("Exit", id="exit", variant="error"),
                classes="menu-buttons"
            ),
            id="main-menu-container"
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle menu button presses."""
        button_id = event.button.id

        if button_id == "exit":
            self.app.exit()

        elif button_id == "scan":
            # Import here to avoid circular imports
            from floppy_formatter.tui.screens.drive_select import DriveSelect
            self.app.push_screen(DriveSelect(operation="scan"))

        elif button_id == "format":
            from floppy_formatter.tui.screens.drive_select import DriveSelect
            self.app.push_screen(DriveSelect(operation="format"))

        elif button_id == "restore":
            from floppy_formatter.tui.screens.drive_select import DriveSelect
            self.app.push_screen(DriveSelect(operation="restore"))

        elif button_id == "reports":
            from floppy_formatter.tui.screens.report_screen import ReportScreen
            # Show most recent report if available
            self.app.push_screen(ReportScreen())

        elif button_id == "settings":
            # Settings screen not yet implemented in Phase 8
            self.notify("Settings coming soon!")
