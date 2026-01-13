"""
Report viewing screen for USB Floppy Formatter.

Displays comprehensive operation results including:
- Before/after comparison
- Recovery statistics
- Disk status assessment
- Detailed sector reports
- Export options
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Static
from textual.containers import Container, Vertical, Horizontal, VerticalScroll

from floppy_formatter.core import RecoveryStatistics
from floppy_formatter.analysis import (
    SectorMap,
    create_comparison_statistics,
    create_format_statistics,
    generate_comparison_report,
    generate_format_report,
    generate_bad_sector_list,
    generate_complete_report,
)


class ReportScreen(Screen):
    """Results and report viewing screen."""

    def __init__(
        self,
        initial_scan: SectorMap = None,
        final_scan: SectorMap = None,
        recovery_stats: RecoveryStatistics = None,
        operation_type: str = "unknown"
    ):
        """
        Initialize report screen.

        Args:
            initial_scan: Initial sector scan before operation
            final_scan: Final sector scan after operation
            recovery_stats: Recovery statistics (if recovery operation)
            operation_type: Type of operation ("scan", "format", "restore")
        """
        super().__init__()
        self.initial_scan = initial_scan
        self.final_scan = final_scan
        self.recovery_stats = recovery_stats
        self.operation_type = operation_type

    def compose(self) -> ComposeResult:
        """Create report screen layout."""
        yield Header()
        yield Container(
            VerticalScroll(
                Static(
                    f"[bold]{self.operation_type.title()} Results[/bold]",
                    classes="screen-title"
                ),
                Static("", id="report-content"),
                Static(""),  # Spacer
                Horizontal(
                    Button("Save Report", id="save-report"),
                    Button("Back to Menu", id="back", variant="primary"),
                    classes="button-row"
                ),
                classes="report-content"
            ),
            id="report-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount - generate and display report."""
        self.generate_report()

    def generate_report(self) -> None:
        """Generate and display the appropriate report."""
        report_widget = self.query_one("#report-content", Static)

        if self.operation_type == "scan":
            report = self.generate_scan_report()
        elif self.operation_type == "restore":
            report = self.generate_restore_report()
        elif self.operation_type == "format":
            report = self.generate_format_report_text()
        else:
            report = "[yellow]No report data available[/yellow]"

        report_widget.update(report)

    def generate_scan_report(self) -> str:
        """
        Generate scan operation report.

        Returns:
            Formatted report text
        """
        if not self.initial_scan:
            return "[yellow]No scan data available[/yellow]"

        bad_count = len(self.initial_scan.bad_sectors)
        good_count = len(self.initial_scan.good_sectors)
        total = self.initial_scan.total_sectors

        report_lines = []
        report_lines.append("[bold cyan]Scan Results Summary[/bold cyan]")
        report_lines.append("=" * 60)
        report_lines.append("")
        report_lines.append(f"Total sectors: {total}")
        report_lines.append(f"Good sectors: [green]{good_count}[/green]")
        report_lines.append(f"Bad sectors: [red]{bad_count}[/red]")
        report_lines.append(f"Scan duration: {self.initial_scan.scan_duration:.1f}s")
        report_lines.append("")

        if bad_count > 0:
            report_lines.append("[bold]Bad Sector Details:[/bold]")
            report_lines.append("")

            # Generate bad sector list
            bad_list = generate_bad_sector_list(self.initial_scan, include_error_types=True)
            report_lines.append(bad_list)
        else:
            report_lines.append("[green]✓ No bad sectors detected - disk is in perfect condition![/green]")

        return "\n".join(report_lines)

    def generate_restore_report(self) -> str:
        """
        Generate restore operation report.

        Returns:
            Formatted report text
        """
        if not self.recovery_stats:
            return "[yellow]No recovery data available[/yellow]"

        report_lines = []
        report_lines.append("[bold cyan]Restore Results Summary[/bold cyan]")
        report_lines.append("=" * 60)
        report_lines.append("")

        # Convergence status
        if self.recovery_stats.converged:
            report_lines.append(
                f"[bold green]✓ CONVERGED after {self.recovery_stats.convergence_pass + 1} passes[/bold green]"
            )
        else:
            report_lines.append(
                f"[yellow]Completed {self.recovery_stats.passes_executed} passes (did not converge)[/yellow]"
            )
        report_lines.append("")

        # Recovery metrics
        report_lines.append("[bold]Recovery Metrics:[/bold]")
        report_lines.append(f"  Initial bad sectors: {self.recovery_stats.initial_bad_sectors}")
        report_lines.append(f"  Final bad sectors: {self.recovery_stats.final_bad_sectors}")
        report_lines.append(f"  Sectors recovered: [green]{self.recovery_stats.sectors_recovered}[/green]")
        report_lines.append(f"  Recovery rate: {self.recovery_stats.get_recovery_rate():.1f}%")
        report_lines.append("")

        # Duration
        duration_mins = int(self.recovery_stats.recovery_duration // 60)
        duration_secs = int(self.recovery_stats.recovery_duration % 60)
        report_lines.append(f"Total time: {duration_mins}m {duration_secs}s")
        report_lines.append(f"Passes executed: {self.recovery_stats.passes_executed}")
        report_lines.append("")

        # Disk status assessment
        if self.recovery_stats.final_bad_sectors == 0:
            status = "[bold green]Perfect[/bold green]"
            message = "Disk is fully functional with zero bad sectors."
        elif self.recovery_stats.final_bad_sectors < 29:  # <1% of 2880
            status = "[green]Good[/green]"
            message = "Disk is safe for most uses."
        elif self.recovery_stats.final_bad_sectors < 144:  # <5% of 2880
            status = "[yellow]Degraded[/yellow]"
            message = "Disk is usable but avoid critical data."
        elif self.recovery_stats.final_bad_sectors < 576:  # <20% of 2880
            status = "[red]Poor[/red]"
            message = "Significant reliability concerns."
        else:
            status = "[bold red]Unusable[/bold red]"
            message = "Disk should be replaced."

        report_lines.append(f"[bold]Disk Status:[/bold] {status}")
        report_lines.append(f"  {message}")
        report_lines.append("")

        # Bad sector history
        if self.recovery_stats.bad_sector_history:
            report_lines.append("[bold]Bad Sector History:[/bold]")
            for i, count in enumerate(self.recovery_stats.bad_sector_history):
                if i == 0:
                    report_lines.append(f"  Initial scan: {count} bad sectors")
                else:
                    prev_count = self.recovery_stats.bad_sector_history[i - 1]
                    delta = count - prev_count
                    if delta < 0:
                        delta_str = f"[green]{delta:+d}[/green]"
                    elif delta > 0:
                        delta_str = f"[red]{delta:+d}[/red]"
                    else:
                        delta_str = "[yellow]no change[/yellow]"
                    report_lines.append(f"  After pass {i}: {count} bad sectors ({delta_str})")

        return "\n".join(report_lines)

    def generate_format_report_text(self) -> str:
        """
        Generate format operation report.

        Returns:
            Formatted report text
        """
        report_lines = []
        report_lines.append("[bold cyan]Format Results Summary[/bold cyan]")
        report_lines.append("=" * 60)
        report_lines.append("")
        report_lines.append("[green]✓ Format operation completed successfully[/green]")
        report_lines.append("")
        report_lines.append("The disk has been formatted and is ready for use.")

        return "\n".join(report_lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "back":
            self.app.pop_screen()

        elif button_id == "save-report":
            # Save report to file
            try:
                filename = f"floppy_report_{self.operation_type}.txt"
                report_content = self.query_one("#report-content", Static).renderable

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(str(report_content))

                self.notify(f"Report saved to {filename}", severity="information")
            except Exception as e:
                self.notify(f"Failed to save report: {e}", severity="error")
