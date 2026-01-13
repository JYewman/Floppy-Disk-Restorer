"""
Progress panel widget for USB Floppy Formatter.

Displays real-time progress for disk operations including:
- Current pass and mode
- Progress bar with sector counts
- Convergence status with pass-by-pass bad sector tracking
- Time elapsed and estimated remaining
- Cancel button
"""

from textual.app import ComposeResult
from textual.widgets import Static, ProgressBar, Button
from textual.containers import Vertical, Horizontal
from textual.widget import Widget

from floppy_formatter.core import RecoveryStatistics


class ProgressPanel(Widget):
    """Progress display panel for recovery operations."""

    def compose(self) -> ComposeResult:
        """Create progress panel layout."""
        yield Vertical(
            Static("[bold]Restore Progress[/bold]", classes="panel-title"),
            Static("", id="restore-settings"),
            Static("", id="pass-info"),
            ProgressBar(total=2880, show_eta=True, show_percentage=True, id="sector-progress"),
            Static("", id="sector-info"),
            Static(""),  # Spacer
            Static("[bold]Convergence Status:[/bold]", id="convergence-header"),
            Vertical(
                id="convergence-history"
            ),
            Static(""),  # Spacer
            Static("", id="time-info"),
            Static(""),  # Spacer
            Horizontal(
                Button("Cancel Operation", id="cancel-operation", variant="error"),
                classes="button-row"
            ),
            classes="progress-panel"
        )

    def update_progress(
        self,
        pass_num: int,
        total_passes: int,
        current_sector: int,
        total_sectors: int,
        bad_sector_count: int,
        converged: bool,
        elapsed_time: float
    ) -> None:
        """
        Update progress display.

        Args:
            pass_num: Current pass number
            total_passes: Total passes (may be ~ for convergence mode)
            current_sector: Current sector being processed
            total_sectors: Total sectors
            bad_sector_count: Current bad sector count
            converged: Whether convergence detected
            elapsed_time: Elapsed time in seconds
        """
        # Update pass info
        pass_info = self.query_one("#pass-info", Static)

        # Handle initial scan (pass_num == -1)
        if pass_num == -1:
            pass_text = "[yellow]Initial Scan...[/yellow]"
        elif total_passes and total_passes < 100:
            pass_text = f"Pass {pass_num + 1} of {total_passes}"
        else:
            pass_text = f"Pass {pass_num + 1} of ~{total_passes} (Convergence Mode)"

        if converged:
            pass_text += " - [green]CONVERGED[/green]"

        pass_info.update(pass_text)

        # Update progress bar
        progress_bar = self.query_one("#sector-progress", ProgressBar)
        progress_bar.update(progress=current_sector + 1)

        # Update sector info
        sector_info = self.query_one("#sector-info", Static)
        completed = min(current_sector + 1, total_sectors)
        percentage = (completed / total_sectors) * 100
        sector_info.update(
            f"{percentage:.1f}% ({completed}/{total_sectors} sectors)\n"
            f"Bad sectors: {bad_sector_count}"
        )

        # Update time info
        time_info = self.query_one("#time-info", Static)
        elapsed_mins = int(elapsed_time // 60)
        elapsed_secs = int(elapsed_time % 60)

        # Estimate remaining time
        if current_sector > 0:
            time_per_sector = elapsed_time / (current_sector + 1)
            remaining_sectors = total_sectors - (current_sector + 1)
            est_remaining = time_per_sector * remaining_sectors
            est_mins = int(est_remaining // 60)
            est_secs = int(est_remaining % 60)
            time_text = (
                f"Time Elapsed: {elapsed_mins:02d}:{elapsed_secs:02d}  |  "
                f"Est. Remaining: {est_mins:02d}:{est_secs:02d}"
            )
        else:
            time_text = f"Time Elapsed: {elapsed_mins:02d}:{elapsed_secs:02d}"

        time_info.update(time_text)

    def add_convergence_entry(
        self,
        pass_num: int,
        bad_sector_count: int,
        previous_count: int = None
    ) -> None:
        """
        Add convergence history entry.

        Args:
            pass_num: Pass number
            bad_sector_count: Bad sector count after this pass
            previous_count: Previous pass bad sector count (for delta)
        """
        history_container = self.query_one("#convergence-history", Vertical)

        if previous_count is not None:
            delta = bad_sector_count - previous_count
            delta_pct = (delta / previous_count * 100) if previous_count > 0 else 0

            if delta < 0:
                trend = "↓"
                color = "green"
            elif delta > 0:
                trend = "↑"
                color = "red"
            else:
                trend = "→"
                color = "yellow"

            entry_text = (
                f"Pass {pass_num + 1}: {bad_sector_count} bad sectors  "
                f"([{color}]{trend} {delta:+d}, {delta_pct:+.1f}%[/{color}])"
            )
        else:
            entry_text = f"Pass {pass_num + 1}: {bad_sector_count} bad sectors  (· Initial scan)"

        history_container.mount(Static(entry_text))

        # Keep only last 10 entries visible
        entries = list(history_container.query(Static))
        if len(entries) > 10:
            entries[0].remove()

    def show_complete(self, recovery_stats: RecoveryStatistics) -> None:
        """
        Show completion status.

        Args:
            recovery_stats: Recovery statistics
        """
        pass_info = self.query_one("#pass-info", Static)
        pass_info.update("[bold green]✓ Restore Complete[/bold green]")

        sector_info = self.query_one("#sector-info", Static)
        sector_info.update(
            f"Initial bad sectors: {recovery_stats.initial_bad_sectors}\n"
            f"Final bad sectors: {recovery_stats.final_bad_sectors}\n"
            f"Sectors recovered: {recovery_stats.sectors_recovered}\n"
            f"Recovery rate: {recovery_stats.get_recovery_rate():.1f}%"
        )

        if recovery_stats.converged:
            convergence_header = self.query_one("#convergence-header", Static)
            convergence_header.update(
                f"[bold green]✓ Converged after {recovery_stats.convergence_pass + 1} passes[/bold green]"
            )

        # Remove cancel button
        try:
            cancel_button = self.query_one("#cancel-operation", Button)
            cancel_button.remove()
        except:
            pass

    def show_error(self, error_message: str) -> None:
        """
        Show error status.

        Args:
            error_message: Error message
        """
        pass_info = self.query_one("#pass-info", Static)
        pass_info.update("[bold red]✗ Restore Failed[/bold red]")

        sector_info = self.query_one("#sector-info", Static)
        sector_info.update(f"Error: {error_message}")

        # Remove cancel button
        try:
            cancel_button = self.query_one("#cancel-operation", Button)
            cancel_button.remove()
        except:
            pass

    def set_restore_settings(
        self,
        convergence_mode: bool,
        passes: int,
        multiread_mode: bool,
        multiread_attempts: int = 100
    ) -> None:
        """
        Display the restore settings being used.

        Args:
            convergence_mode: Whether convergence mode is enabled
            passes: Number of passes (or max passes for convergence)
            multiread_mode: Whether multi-read mode is enabled
            multiread_attempts: Multi-read attempts per sector
        """
        settings_widget = self.query_one("#restore-settings", Static)

        mode_text = "Convergence Mode" if convergence_mode else "Fixed Pass Mode"
        passes_text = f"Max {passes} passes" if convergence_mode else f"{passes} passes"

        settings_parts = [f"{mode_text} ({passes_text})"]

        if multiread_mode:
            settings_parts.append(f"Multi-read enabled ({multiread_attempts} attempts/sector)")

        settings_text = "[dim]" + " • ".join(settings_parts) + "[/dim]"
        settings_widget.update(settings_text)

    def add_completion_buttons(self) -> None:
        """Add completion buttons (View Report, Back to Menu)."""
        button_row = self.query_one(".button-row", Horizontal)
        button_row.mount(
            Button("View Report", id="view-report", variant="primary"),
            Button("Back to Menu", id="back")
        )
