"""
Disk restore/recovery screen for USB Floppy Formatter.

Provides interactive recovery options including:
- Fixed pass mode or convergence mode
- Configurable pass counts
- Report options
- Real-time progress with convergence tracking
"""

import time
from textual.app import ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import (
    Header,
    Footer,
    Button,
    Static,
    RadioButton,
    RadioSet,
    Input,
    Checkbox,
)
from textual.containers import Container, Vertical, Horizontal, VerticalScroll
from textual import work
from textual.worker import Worker

from floppy_formatter.core import (
    open_device,
    close_device,
    recover_disk,
    recover_bad_sectors_only,
    RecoveryStatistics,
    prevent_sleep,
    allow_sleep,
)
from floppy_formatter.analysis import (
    scan_all_sectors,
    create_comparison_statistics,
    create_format_statistics,
)
from floppy_formatter.tui.widgets.progress_panel import ProgressPanel
from floppy_formatter.tui.widgets.sector_map import SectorMapWidget


class ConfirmRestoreDialog(ModalScreen):
    """Confirmation dialog for destructive restore operation."""

    def compose(self) -> ComposeResult:
        """Create confirmation dialog."""
        yield Container(
            Vertical(
                Static(
                    "[bold yellow]⚠ Warning[/bold yellow]",
                    classes="dialog-title"
                ),
                Static(
                    "This will perform multiple format passes on the disk.\n\n"
                    "This operation is DESTRUCTIVE and cannot be undone.\n"
                    "All data will be erased.\n\n"
                    "Are you sure you want to continue?",
                    classes="dialog-message"
                ),
                Horizontal(
                    Button("Yes, Restore Disk", id="confirm", variant="error"),
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


class RestoreScreen(Screen):
    """Disk restore/recovery operation screen."""

    def __init__(self, device_path: str, geometry):
        """
        Initialize restore screen.

        Args:
            device_path: Device path (e.g., /dev/sde)
            geometry: Disk geometry information
        """
        super().__init__()
        self.device_path = device_path
        self.geometry = geometry
        self.restore_worker = None
        self.start_time = None
        self.cancelled = False
        self.initial_scan = None
        self.recovery_stats = None
        self.showing_options = True

    def compose(self) -> ComposeResult:
        """Create restore screen layout."""
        yield Header()
        yield Container(
            VerticalScroll(
                Static("[bold]Restore Disk Options[/bold]", classes="screen-title"),
                Static(f"Device: {self.device_path}", id="drive-info"),
                Static(""),  # Spacer
                Static("[bold]Recovery Mode:[/bold]", classes="section-header"),
                RadioSet(
                    RadioButton("Fixed Passes", id="fixed-mode"),
                    RadioButton("Convergence Mode (Recommended)", value=True, id="convergence-mode"),
                    id="mode-select"
                ),
                Static(""),  # Spacer
                Container(
                    Static("Number of passes:", classes="input-label"),
                    Input(value="5", placeholder="5", id="fixed-passes"),
                    classes="input-group",
                    id="fixed-options"
                ),
                Container(
                    Static("Maximum passes:", classes="input-label"),
                    Input(value="50", placeholder="50", id="max-passes"),
                    Static(
                        "[dim](Stops when bad sectors stabilize)[/dim]",
                        classes="input-hint"
                    ),
                    classes="input-group",
                    id="convergence-options"
                ),
                Static(""),  # Spacer
                Static("[bold]Advanced Recovery:[/bold]", classes="section-header"),
                Checkbox(
                    "Targeted Recovery (Only format tracks with bad sectors)",
                    value=True,
                    id="targeted-mode"
                ),
                Checkbox(
                    "Multi-Read Mode (Aggressive multi-read recovery)",
                    value=False,
                    id="multiread-mode"
                ),
                Container(
                    Static("Multi-read attempts per sector:", classes="input-label"),
                    Input(value="100", placeholder="100", id="multiread-attempts"),
                    Static(
                        "[dim](Higher = slower but more thorough)[/dim]",
                        classes="input-hint"
                    ),
                    classes="input-group",
                    id="multiread-options"
                ),
                Static(""),  # Spacer
                Static("[bold]Report Options:[/bold]", classes="section-header"),
                Checkbox("Detailed sector-by-sector report", value=True, id="detailed-report"),
                Checkbox("Track maps", value=True, id="track-maps"),
                Checkbox("Hex dumps of bad sectors", value=True, id="hex-dumps"),
                Checkbox("Save report to file", value=True, id="save-report"),
                Static(""),  # Spacer
                Horizontal(
                    Button("Start Restore", id="start", variant="primary"),
                    Button("Cancel", id="cancel"),
                    classes="button-row"
                ),
                id="options-panel"
            ),
            Container(
                ProgressPanel(id="progress-panel"),
                VerticalScroll(
                    SectorMapWidget(self.geometry, id="sector-map"),
                    id="sector-map-scroll"
                ),
                id="progress-container"
            ),
            id="restore-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount - initialize display states."""
        # Hide progress initially
        self.query_one("#progress-container", Container).display = False

        # Show only convergence options initially
        self.query_one("#fixed-options", Container).display = False

        # Hide multi-read options initially
        self.query_one("#multiread-options", Container).display = False

    def on_unmount(self) -> None:
        """Handle screen unmount - cancel restore worker and restore sleep."""
        self.cancelled = True
        if self.restore_worker and not self.restore_worker.is_finished:
            self.restore_worker.cancel()
        allow_sleep()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle recovery mode selection change."""
        selected_id = event.pressed.id

        fixed_options = self.query_one("#fixed-options", Container)
        convergence_options = self.query_one("#convergence-options", Container)

        if selected_id == "fixed-mode":
            fixed_options.display = True
            convergence_options.display = False
        elif selected_id == "convergence-mode":
            fixed_options.display = False
            convergence_options.display = True

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes."""
        if event.checkbox.id == "multiread-mode":
            # Show/hide multi-read options based on checkbox
            multiread_options = self.query_one("#multiread-options", Container)
            multiread_options.display = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "start":
            # Show confirmation dialog with callback
            def check_confirmation(confirmed: bool) -> None:
                if confirmed:
                    self.start_restore()

            self.app.push_screen(ConfirmRestoreDialog(), check_confirmation)

        elif button_id == "cancel" or button_id == "cancel-operation":
            self.cancelled = True
            if self.restore_worker and not self.restore_worker.is_finished:
                self.restore_worker.cancel()
            if button_id == "cancel":
                self.app.pop_screen()

        elif button_id == "view-report":
            from floppy_formatter.tui.screens.report_screen import ReportScreen
            self.app.push_screen(
                ReportScreen(
                    initial_scan=self.initial_scan,
                    recovery_stats=self.recovery_stats,
                    operation_type="restore"
                )
            )

        elif button_id == "back":
            self.app.pop_screen()

    def start_restore(self) -> None:
        """Start the restore operation."""
        # Get options
        mode_select = self.query_one("#mode-select", RadioSet)
        convergence_mode = mode_select.pressed_button.id == "convergence-mode"

        if convergence_mode:
            max_passes_input = self.query_one("#max-passes", Input)
            try:
                max_passes = int(max_passes_input.value)
            except:
                max_passes = 50
            passes = max_passes  # Will be used as max_passes parameter
        else:
            fixed_passes_input = self.query_one("#fixed-passes", Input)
            try:
                passes = int(fixed_passes_input.value)
            except:
                passes = 5

        # Get targeted recovery option
        targeted_mode = self.query_one("#targeted-mode", Checkbox).value

        # Get multi-read options
        multiread_mode = self.query_one("#multiread-mode", Checkbox).value
        if multiread_mode:
            multiread_attempts_input = self.query_one("#multiread-attempts", Input)
            try:
                multiread_attempts = int(multiread_attempts_input.value)
                if multiread_attempts < 10:
                    multiread_attempts = 10
                elif multiread_attempts > 2000:
                    multiread_attempts = 2000
            except:
                multiread_attempts = 100
        else:
            multiread_attempts = 100

        # Get report options
        detailed_report = self.query_one("#detailed-report", Checkbox).value
        track_maps = self.query_one("#track-maps", Checkbox).value
        hex_dumps = self.query_one("#hex-dumps", Checkbox).value
        save_report = self.query_one("#save-report", Checkbox).value

        # Hide options panel, show progress
        self.query_one("#options-panel", VerticalScroll).display = False
        self.query_one("#progress-container", Container).display = True

        # Display selected settings in progress panel
        progress_panel = self.query_one("#progress-panel", ProgressPanel)
        progress_panel.set_restore_settings(
            convergence_mode=convergence_mode,
            passes=passes,
            multiread_mode=multiread_mode,
            multiread_attempts=multiread_attempts
        )

        # Start timing
        self.start_time = time.time()
        self.showing_options = False

        # Start worker
        self.restore_worker = self.perform_restore(
            convergence_mode=convergence_mode,
            passes=passes,
            max_passes=passes if convergence_mode else 50,
            targeted_mode=targeted_mode,
            multiread_mode=multiread_mode,
            multiread_attempts=multiread_attempts
        )

    @work(thread=True)
    async def perform_restore(
        self,
        convergence_mode: bool,
        passes: int,
        max_passes: int,
        targeted_mode: bool,
        multiread_mode: bool,
        multiread_attempts: int
    ):
        """
        Perform disk restore in background thread.

        Args:
            convergence_mode: Whether to use convergence mode
            passes: Number of passes (fixed mode) or max passes (convergence)
            max_passes: Maximum passes in convergence mode
            targeted_mode: Whether to only format tracks with bad sectors
            multiread_mode: Whether to use multi-read recovery
            multiread_attempts: Number of read attempts per bad sector in multi-read mode
        """
        handle = None
        try:
            # Prevent system sleep
            prevent_sleep()

            # Open drive
            handle = open_device(self.device_path, read_only=False)

            # Progress callback with extended signature for sector-level updates
            def progress_callback(
                pass_num,
                total_passes,
                current_sector,
                total_sectors,
                bad_sector_count,
                converged=False,
                is_good=None,
                error_type=None
            ):
                if self.cancelled:
                    # Raise exception to stop recovery immediately
                    raise InterruptedError("Operation cancelled by user")

                try:
                    # Check if this is a pass completion notification
                    if pass_num == -2:
                        # pass_num=-2 means pass complete
                        # total_passes has the actual pass number
                        # current_sector has the bad sector count
                        # total_sectors has the previous bad sector count
                        self.app.call_from_thread(
                            self.add_pass_to_convergence,
                            total_passes,  # actual pass number
                            current_sector,  # bad sector count
                            total_sectors if total_sectors > 0 else None  # previous count
                        )
                    elif pass_num == -1 and is_good is not None:
                        # Initial scan with sector-level information - update sector map
                        self.app.call_from_thread(
                            self.update_sector_map,
                            current_sector,
                            is_good
                        )
                        # Also update normal progress
                        self.app.call_from_thread(
                            self.update_restore_progress,
                            pass_num,
                            total_passes,
                            current_sector,
                            total_sectors,
                            bad_sector_count,
                            converged
                        )
                    else:
                        # Normal progress update
                        self.app.call_from_thread(
                            self.update_restore_progress,
                            pass_num,
                            total_passes,
                            current_sector,
                            total_sectors,
                            bad_sector_count,
                            converged
                        )
                except Exception as e:
                    import logging
                    logging.error(f"Progress update failed: {e}", exc_info=True)

            # Perform initial scan (required for targeted mode and storing results)
            from floppy_formatter.analysis import scan_all_sectors

            # Create initial scan callback
            def initial_scan_cb(sector_num, total, is_good, error_type):
                if self.cancelled:
                    # Raise exception to stop the scan immediately
                    raise InterruptedError("Operation cancelled by user")
                # Update sector map during initial scan
                if is_good is not None:
                    self.app.call_from_thread(
                        self.update_sector_map,
                        sector_num,
                        is_good
                    )
                # Update progress
                try:
                    progress_callback(-1, 1, sector_num, total, 0, False, is_good, error_type)
                except:
                    pass

            try:
                self.initial_scan = scan_all_sectors(handle, self.geometry, initial_scan_cb)
            except InterruptedError:
                # User cancelled during initial scan
                return

            # Perform recovery
            try:
                if targeted_mode and len(self.initial_scan.bad_sectors) > 0:
                    # Targeted recovery - only format tracks with bad sectors
                    recovery_stats = recover_bad_sectors_only(
                        handle,
                        self.geometry,
                        self.initial_scan.bad_sectors,
                        passes=passes if not convergence_mode else 5,
                        multiread_mode=multiread_mode,
                        multiread_attempts=multiread_attempts,
                        progress_callback=progress_callback
                    )
                else:
                    # Full disk recovery
                    recovery_stats = recover_disk(
                        handle,
                        self.geometry,
                        passes=passes if not convergence_mode else 5,
                        convergence_mode=convergence_mode,
                        max_passes=max_passes,
                        multiread_mode=multiread_mode,
                        multiread_attempts=multiread_attempts,
                        progress_callback=progress_callback
                    )

                if not self.cancelled:
                    self.app.call_from_thread(
                        self.on_restore_complete,
                        recovery_stats
                    )
            except InterruptedError:
                # User cancelled during recovery - just return silently
                return

        except Exception as e:
            if not self.cancelled:
                self.app.call_from_thread(
                    self.on_restore_error,
                    str(e)
                )

        finally:
            if handle:
                close_device(handle)
            allow_sleep()

    def update_sector_map(self, sector_num: int, is_good: bool) -> None:
        """
        Update sector map visualization.

        Args:
            sector_num: Sector number
            is_good: Whether sector read successfully
        """
        try:
            sector_map_widget = self.query_one("#sector-map", SectorMapWidget)
            sector_map_widget.update_sector(sector_num, is_good)
        except Exception as e:
            import logging
            logging.error(f"Sector map update failed: {e}", exc_info=True)

    def update_restore_progress(
        self,
        pass_num: int,
        total_passes: int,
        current_sector: int,
        total_sectors: int,
        bad_sector_count: int,
        converged: bool
    ) -> None:
        """
        Update restore progress display.

        Args:
            pass_num: Current pass number
            total_passes: Total passes (may be unknown in convergence mode)
            current_sector: Current sector being processed
            total_sectors: Total sectors
            bad_sector_count: Current bad sector count
            converged: Whether convergence has been detected
        """
        progress_panel = self.query_one("#progress-panel", ProgressPanel)
        progress_panel.update_progress(
            pass_num=pass_num,
            total_passes=total_passes,
            current_sector=current_sector,
            total_sectors=total_sectors,
            bad_sector_count=bad_sector_count,
            converged=converged,
            elapsed_time=time.time() - self.start_time
        )

    def add_pass_to_convergence(
        self,
        pass_num: int,
        bad_sector_count: int,
        previous_count: int = None
    ) -> None:
        """
        Add convergence history entry after pass completes.

        Args:
            pass_num: Pass number that just completed
            bad_sector_count: Bad sector count after this pass
            previous_count: Previous pass bad sector count (for delta)
        """
        progress_panel = self.query_one("#progress-panel", ProgressPanel)
        progress_panel.add_convergence_entry(pass_num, bad_sector_count, previous_count)

    def on_restore_complete(self, recovery_stats: RecoveryStatistics) -> None:
        """
        Handle restore completion.

        Args:
            recovery_stats: Recovery statistics
        """
        self.recovery_stats = recovery_stats

        progress_panel = self.query_one("#progress-panel", ProgressPanel)
        progress_panel.show_complete(recovery_stats)

        # Add buttons
        progress_panel.add_completion_buttons()

    def on_restore_error(self, error_message: str) -> None:
        """
        Handle restore error.

        Args:
            error_message: Error message
        """
        progress_panel = self.query_one("#progress-panel", ProgressPanel)
        progress_panel.show_error(error_message)
