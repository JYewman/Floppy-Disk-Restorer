"""
Drive selection screen for USB Floppy Formatter.

Auto-detects floppy drive and displays drive information including:
- Drive letter mapping
- Physical drive number
- Disk geometry
- Format status
- Bad sector 0 detection
"""

import logging
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Static
from textual.containers import Container, Vertical
from textual import work
from textual.worker import Worker

from floppy_formatter.core.device_manager import (
    find_floppy_devices,
    get_device_path,
    open_device,
    close_device,
    enumerate_devices,
)
from floppy_formatter.core.geometry import get_disk_geometry
from floppy_formatter.utils import (
    handle_disk_error,
    log_operation,
    log_device_info,
)


class DriveSelect(Screen):
    """Drive selection and status screen."""

    def __init__(self, operation: str = "scan"):
        """
        Initialize drive selection screen.

        Args:
            operation: Operation to perform ("scan", "format", "restore")
        """
        super().__init__()
        self.operation = operation
        self.device_path = None
        self.drive_letter = "A"
        self.geometry = None
        self.drive_info = None
        self.detection_worker = None

    def compose(self) -> ComposeResult:
        """Create drive selection screen layout."""
        yield Header()
        yield Container(
            Vertical(
                Static(
                    f"[bold]Select Floppy Drive - {self.operation.title()} Operation[/bold]",
                    classes="screen-title"
                ),
                Static(
                    "[dim]Detecting floppy drive...[/dim]",
                    id="drive-status"
                ),
                Static("", id="drive-details"),
                Static(""),  # Spacer
                Button("Continue", id="continue", variant="primary", disabled=True),
                Button("Refresh", id="refresh"),
                Button("Cancel", id="cancel"),
                classes="drive-select-content"
            ),
            id="drive-select-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount - start drive detection."""
        self.detection_worker = self.detect_drive()

    def on_unmount(self) -> None:
        """Handle screen unmount - cancel any running workers."""
        if self.detection_worker and not self.detection_worker.is_finished:
            self.detection_worker.cancel()

    @work(thread=True)
    async def detect_drive(self):
        """
        Detect floppy drive in background thread.

        Uses enumerate_devices to find USB floppy drives
        and retrieves geometry information.
        """
        try:
            logging.info("Detecting USB floppy drives")
            log_operation("drive_detection", "Starting detection")

            # Find all floppy devices
            device_paths = enumerate_devices()
            if not device_paths:
                raise IOError("No USB floppy drives found")

            # Use the first device found
            device_path = device_paths[0]
            logging.info(f"Found floppy at {device_path}")

            # Open device to get geometry
            fd = open_device(device_path, read_only=True)
            try:
                geometry = get_disk_geometry(fd)
                log_device_info(device_path, geometry, "Detected Floppy")
            finally:
                close_device(fd)

            # Update UI from main thread
            self.app.call_from_thread(
                self.on_drive_detected,
                device_path,
                geometry
            )

        except Exception as e:
            logging.error(f"Drive detection failed: {e}")
            log_operation("drive_detection", f"Failed: {e}", logging.ERROR)
            self.app.call_from_thread(
                self.on_drive_detection_failed,
                str(e)
            )

    def on_drive_detected(self, device_path: str, geometry) -> None:
        """
        Handle successful drive detection.

        Args:
            device_path: Device path (e.g., /dev/sde)
            geometry: Disk geometry information
        """
        self.device_path = device_path
        self.geometry = geometry

        # Format drive information
        status_widget = self.query_one("#drive-status", Static)
        details_widget = self.query_one("#drive-details", Static)
        continue_button = self.query_one("#continue", Button)

        status_widget.update("[green]✓ Floppy drive detected[/green]")

        details = (
            f"[bold]Drive:[/bold] {self.drive_letter}: → {device_path}\n"
            f"[bold]Geometry:[/bold] {geometry.cylinders} cyl / {geometry.heads} heads / "
            f"{geometry.sectors_per_track} sectors\n"
            f"[bold]Capacity:[/bold] {geometry.cylinders * geometry.heads * geometry.sectors_per_track * geometry.bytes_per_sector // 1024} KB\n"
            f"[bold]Status:[/bold] Ready for {self.operation}"
        )
        details_widget.update(details)

        # Enable continue button
        continue_button.disabled = False

    def on_drive_detection_failed(self, error_message: str) -> None:
        """
        Handle drive detection failure.

        Args:
            error_message: Error message describing the failure
        """
        status_widget = self.query_one("#drive-status", Static)
        details_widget = self.query_one("#drive-details", Static)

        status_widget.update("[red]✗ Drive detection failed[/red]")
        details_widget.update(
            f"[yellow]Error:[/yellow] {error_message}\n\n"
            "[dim]Possible causes:\n"
            "• No floppy disk inserted\n"
            "• USB drive not connected\n"
            "• Drive not ready\n"
            "• Group Policy blocking access\n\n"
            "Click Refresh to try again.[/dim]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "cancel":
            self.app.pop_screen()

        elif button_id == "refresh":
            # Restart detection
            status_widget = self.query_one("#drive-status", Static)
            details_widget = self.query_one("#drive-details", Static)
            continue_button = self.query_one("#continue", Button)

            status_widget.update("[dim]Detecting floppy drive...[/dim]")
            details_widget.update("")
            continue_button.disabled = True

            if self.detection_worker and not self.detection_worker.is_finished:
                self.detection_worker.cancel()

            self.detection_worker = self.detect_drive()

        elif button_id == "continue":
            # Proceed to operation screen
            if self.device_path is None or self.geometry is None:
                self.notify("Please wait for drive detection to complete", severity="warning")
                return

            if self.operation == "scan":
                from floppy_formatter.tui.screens.scan_screen import ScanScreen
                self.app.push_screen(ScanScreen(self.device_path, self.geometry))

            elif self.operation == "format":
                from floppy_formatter.tui.screens.format_screen import FormatScreen
                self.app.push_screen(FormatScreen(self.device_path, self.geometry))

            elif self.operation == "restore":
                from floppy_formatter.tui.screens.restore_screen import RestoreScreen
                self.app.push_screen(RestoreScreen(self.device_path, self.geometry))
