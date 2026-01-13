"""
Disk formatting screen for USB Floppy Formatter.

Performs low-level disk formatting with real-time progress display.
"""

import time
from textual.app import ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import Header, Footer, Button, Static, ProgressBar
from textual.containers import Container, Vertical, Horizontal
from textual import work
from textual.worker import Worker

from floppy_formatter.core import (
    open_device,
    close_device,
    format_disk,
    prevent_sleep,
    allow_sleep,
)


class ConfirmFormatDialog(ModalScreen):
    """Confirmation dialog for destructive format operation."""

    def compose(self) -> ComposeResult:
        """Create confirmation dialog."""
        yield Container(
            Vertical(
                Static(
                    "[bold yellow]⚠ Warning[/bold yellow]",
                    classes="dialog-title"
                ),
                Static(
                    "This will erase ALL data on the floppy disk.\n\n"
                    "This operation is DESTRUCTIVE and cannot be undone.\n\n"
                    "Are you sure you want to continue?",
                    classes="dialog-message"
                ),
                Horizontal(
                    Button("Yes, Format Disk", id="confirm", variant="error"),
                    Button("Cancel", id="cancel", variant="primary"),
                    classes="dialog-buttons"
                ),
                classes="dialog-content"
            ),
            id="confirmation-dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        self.dismiss(event.button.id == "confirm")


class FormatScreen(Screen):
    """Disk formatting operation screen."""

    def __init__(self, device_path: str, geometry):
        """
        Initialize format screen.

        Args:
            device_path: Device path (e.g., /dev/sde)
            geometry: Disk geometry information
        """
        super().__init__()
        self.device_path = device_path
        self.geometry = geometry
        self.format_worker = None
        self.start_time = None
        self.cancelled = False

    def compose(self) -> ComposeResult:
        """Create format screen layout."""
        yield Header()
        yield Container(
            Vertical(
                Static("[bold]Format Disk[/bold]", classes="screen-title"),
                Static(f"Device: {self.device_path}", id="drive-info"),
                Static(""),  # Spacer
                Static(
                    "[yellow]Ready to format disk[/yellow]\n\n"
                    "Click 'Start Format' to begin.\n"
                    "This will erase all data on the disk.",
                    id="format-status"
                ),
                Static(""),  # Spacer
                Static("Progress:", classes="label", id="progress-label"),
                ProgressBar(total=160, show_eta=True, show_percentage=True, id="format-progress"),
                Static("", id="format-details"),
                Static(""),  # Spacer
                Horizontal(
                    Button("Start Format", id="start", variant="primary"),
                    Button("Cancel", id="cancel"),
                    classes="button-row"
                ),
                classes="format-content"
            ),
            id="format-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount - initialize display states."""
        # Hide progress initially
        self.query_one("#progress-label", Static).display = False
        self.query_one("#format-progress", ProgressBar).display = False

    def on_unmount(self) -> None:
        """Handle screen unmount - cancel format worker and restore sleep."""
        self.cancelled = True
        if self.format_worker and not self.format_worker.is_finished:
            self.format_worker.cancel()
        allow_sleep()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "start":
            # Show confirmation dialog with callback
            def check_confirmation(confirmed: bool) -> None:
                if confirmed:
                    self.start_format()

            self.app.push_screen(ConfirmFormatDialog(), check_confirmation)

        elif button_id == "cancel":
            self.cancelled = True
            if self.format_worker and not self.format_worker.is_finished:
                self.format_worker.cancel()
            self.app.pop_screen()

        elif button_id == "back":
            self.app.pop_screen()

    def start_format(self) -> None:
        """Start the formatting operation."""
        # Calculate total tracks
        total_tracks = self.geometry.cylinders * self.geometry.heads

        # Update UI with geometry info for debugging
        status_widget = self.query_one("#format-status", Static)
        status_widget.update(
            f"[yellow]Formatting in progress...[/yellow]\n\n"
            f"[dim]Geometry: {self.geometry.cylinders} cyl × {self.geometry.heads} heads "
            f"× {self.geometry.sectors_per_track} sectors = {self.geometry.total_sectors} sectors\n"
            f"Total tracks: {total_tracks}[/dim]"
        )

        # Show progress
        self.query_one("#progress-label", Static).display = True
        progress_bar = self.query_one("#format-progress", ProgressBar)
        progress_bar.display = True

        # Set progress bar total to actual number of tracks
        progress_bar.update(total=total_tracks)

        # Disable start button
        start_button = self.query_one("#start", Button)
        start_button.disabled = True

        # Start timing
        self.start_time = time.time()

        # Start worker
        self.format_worker = self.perform_format()

    @work(thread=True)
    async def perform_format(self):
        """
        Perform disk format in background thread.

        Formats all tracks and updates UI with real-time progress.
        """
        handle = None
        try:
            # Prevent system sleep
            prevent_sleep()

            # Open drive
            handle = open_device(self.device_path, read_only=False)

            # Format disk with progress callback
            def progress_callback(track_num, total_tracks):
                if self.cancelled:
                    return

                self.app.call_from_thread(
                    self.update_format_progress,
                    track_num,
                    total_tracks
                )

            success, bad_track_count, bad_tracks = format_disk(
                handle,
                self.geometry,
                progress_callback=progress_callback
            )

            if not self.cancelled:
                self.app.call_from_thread(
                    self.on_format_complete,
                    success,
                    bad_track_count,
                    bad_tracks
                )

        except Exception as e:
            if not self.cancelled:
                self.app.call_from_thread(
                    self.on_format_error,
                    str(e)
                )

        finally:
            if handle:
                close_device(handle)
            allow_sleep()

    def update_format_progress(self, track_num: int, total_tracks: int) -> None:
        """
        Update format progress display.

        Args:
            track_num: Current track being formatted
            total_tracks: Total number of tracks
        """
        # Update progress bar
        progress_bar = self.query_one("#format-progress", ProgressBar)
        progress_bar.update(progress=track_num + 1)

        # Update details
        elapsed = time.time() - self.start_time
        details_widget = self.query_one("#format-details", Static)
        details_widget.update(
            f"Formatting track {track_num + 1}/{total_tracks}\n"
            f"Elapsed: {elapsed:.1f}s"
        )

    def on_format_complete(
        self,
        success: bool,
        bad_track_count: int,
        bad_tracks: list
    ) -> None:
        """
        Handle format completion.

        Args:
            success: Whether format succeeded
            bad_track_count: Number of bad tracks detected
            bad_tracks: List of bad track numbers
        """
        elapsed = time.time() - self.start_time
        status_widget = self.query_one("#format-status", Static)

        if success:
            status_widget.update(
                f"[bold green]✓ Format Complete[/bold green]\n\n"
                f"Time: {elapsed:.1f}s\n"
                f"Bad tracks: {bad_track_count}"
            )
        else:
            status_widget.update(
                f"[bold yellow]⚠ Format Completed with Issues[/bold yellow]\n\n"
                f"Time: {elapsed:.1f}s\n"
                f"Bad tracks: {bad_track_count}"
            )

        # Update buttons
        start_button = self.query_one("#start", Button)
        start_button.remove()

        button_container = self.query_one(".button-row", Horizontal)
        button_container.mount(
            Button("Back to Menu", id="back", variant="primary")
        )

    def on_format_error(self, error_message: str) -> None:
        """
        Handle format error.

        Args:
            error_message: Error message
        """
        status_widget = self.query_one("#format-status", Static)
        status_widget.update(
            f"[bold red]✗ Format Failed[/bold red]\n\n"
            f"Error: {error_message}"
        )

        # Update buttons
        start_button = self.query_one("#start", Button)
        start_button.disabled = False

        details_widget = self.query_one("#format-details", Static)
        details_widget.update(
            "[dim]Check error message and try again.\n"
            "Possible causes:\n"
            "• Write-protected disk\n"
            "• Drive not ready\n"
            "• USB controller limitation[/dim]"
        )
