"""
Disk scanning screen for USB Floppy Formatter.

Performs full surface scan of all 2,880 sectors with real-time progress
display and sector map visualization.
"""

import time
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Static, ProgressBar
from textual.containers import Container, Vertical, Horizontal
from textual import work
from textual.worker import Worker

from floppy_formatter.core import (
    open_device,
    close_device,
)
from floppy_formatter.analysis import (
    scan_all_sectors,
    SectorMap,
)
from floppy_formatter.tui.widgets.sector_map import SectorMapWidget


class ScanScreen(Screen):
    """Disk scanning operation screen."""

    def __init__(self, device_path: str, geometry):
        """
        Initialize scan screen.

        Args:
            device_path: Device path (e.g., /dev/sde)
            geometry: Disk geometry information
        """
        super().__init__()
        self.device_path = device_path
        self.geometry = geometry
        self.scan_worker = None
        self.scan_result = None
        self.start_time = None
        self.cancelled = False

    def compose(self) -> ComposeResult:
        """Create scan screen layout."""
        yield Header()
        yield Container(
            Vertical(
                Static("[bold]Scanning Disk[/bold]", classes="screen-title"),
                Static(f"Device: {self.device_path}", id="drive-info"),
                Static(""),  # Spacer
                Static("Progress:", classes="label"),
                ProgressBar(total=2880, show_eta=True, show_percentage=True, id="scan-progress"),
                Static("", id="scan-status"),
                Static(""),  # Spacer
                SectorMapWidget(self.geometry, id="sector-map"),
                Static(""),  # Spacer
                Horizontal(
                    Button("Cancel Scan", id="cancel", variant="error"),
                    classes="button-row"
                ),
                classes="scan-content"
            ),
            id="scan-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount - start scanning."""
        self.start_time = time.time()
        self.scan_worker = self.perform_scan()

    def on_unmount(self) -> None:
        """Handle screen unmount - cancel scan worker."""
        self.cancelled = True
        if self.scan_worker and not self.scan_worker.is_finished:
            self.scan_worker.cancel()

    @work(thread=True)
    async def perform_scan(self):
        """
        Perform disk scan in background thread.

        Scans all sectors and updates UI with real-time progress.
        """
        handle = None
        try:
            # Open drive
            handle = open_device(self.device_path, read_only=True)

            # Perform scan with progress callback
            def progress_callback(sector_num, total_sectors, is_good, error_type=None):
                if self.cancelled:
                    return

                self.app.call_from_thread(
                    self.update_scan_progress,
                    sector_num,
                    total_sectors,
                    is_good,
                    error_type
                )

            scan_result = scan_all_sectors(
                handle,
                self.geometry,
                progress_callback=progress_callback
            )

            if not self.cancelled:
                self.app.call_from_thread(
                    self.on_scan_complete,
                    scan_result
                )

        except Exception as e:
            if not self.cancelled:
                self.app.call_from_thread(
                    self.on_scan_error,
                    str(e)
                )

        finally:
            if handle:
                close_device(handle)

    def update_scan_progress(
        self,
        sector_num: int,
        total_sectors: int,
        is_good: bool,
        error_type: str = None
    ) -> None:
        """
        Update scan progress display.

        Args:
            sector_num: Current sector being scanned
            total_sectors: Total number of sectors
            is_good: Whether sector read succeeded
            error_type: Error type if sector is bad
        """
        # Update progress bar
        progress_bar = self.query_one("#scan-progress", ProgressBar)
        progress_bar.update(progress=sector_num + 1)

        # Update status
        elapsed = time.time() - self.start_time
        status_widget = self.query_one("#scan-status", Static)
        status_text = (
            f"Scanning sector {sector_num + 1}/{total_sectors}\n"
            f"Elapsed: {elapsed:.1f}s\n"
        )
        if not is_good and error_type:
            status_text += f"[red]Bad sector detected: {error_type}[/red]"

        status_widget.update(status_text)

        # Update sector map
        sector_map_widget = self.query_one("#sector-map", SectorMapWidget)
        sector_map_widget.update_sector(sector_num, is_good)

    def on_scan_complete(self, scan_result: SectorMap) -> None:
        """
        Handle scan completion.

        Args:
            scan_result: Scan results with sector map
        """
        self.scan_result = scan_result

        # Update status
        elapsed = time.time() - self.start_time
        status_widget = self.query_one("#scan-status", Static)
        bad_count = len(scan_result.bad_sectors)
        good_count = len(scan_result.good_sectors)

        status_widget.update(
            f"[bold green]✓ Scan Complete[/bold green]\n"
            f"Good sectors: {good_count}\n"
            f"Bad sectors: {bad_count}\n"
            f"Time: {elapsed:.1f}s"
        )

        # Replace cancel button with view report button
        cancel_button = self.query_one("#cancel", Button)
        cancel_button.remove()

        button_container = self.query_one(".button-row", Horizontal)
        button_container.mount(
            Button("View Report", id="view-report", variant="primary"),
            Button("Back to Menu", id="back")
        )

    def on_scan_error(self, error_message: str) -> None:
        """
        Handle scan error.

        Args:
            error_message: Error message
        """
        status_widget = self.query_one("#scan-status", Static)
        status_widget.update(
            f"[bold red]✗ Scan Failed[/bold red]\n"
            f"Error: {error_message}"
        )

        # Replace cancel button with back button
        cancel_button = self.query_one("#cancel", Button)
        cancel_button.remove()

        button_container = self.query_one(".button-row", Horizontal)
        button_container.mount(
            Button("Back to Menu", id="back")
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "cancel":
            self.cancelled = True
            if self.scan_worker and not self.scan_worker.is_finished:
                self.scan_worker.cancel()
            self.app.pop_screen()

        elif button_id == "view-report":
            from floppy_formatter.tui.screens.report_screen import ReportScreen
            self.app.push_screen(
                ReportScreen(
                    initial_scan=self.scan_result,
                    operation_type="scan"
                )
            )

        elif button_id == "back":
            self.app.pop_screen()
