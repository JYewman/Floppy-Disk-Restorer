"""
Statistics panel widget for USB Floppy Formatter.

Displays operation statistics including:
- Sector counts (good/bad/total)
- Error breakdown by type
- Performance metrics
- Disk health assessment
"""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Vertical
from textual.widget import Widget


class StatsPanel(Widget):
    """Statistics display panel."""

    def compose(self) -> ComposeResult:
        """Create stats panel layout."""
        yield Vertical(
            Static("[bold]Statistics[/bold]", classes="widget-title"),
            Static("", id="sector-stats"),
            Static("", id="error-stats"),
            Static("", id="performance-stats"),
            classes="stats-panel"
        )

    def update_stats(
        self,
        total_sectors: int,
        good_sectors: int,
        bad_sectors: int,
        error_breakdown: dict = None,
        scan_duration: float = None
    ) -> None:
        """
        Update statistics display.

        Args:
            total_sectors: Total number of sectors
            good_sectors: Number of good sectors
            bad_sectors: Number of bad sectors
            error_breakdown: Dictionary of error type -> count
            scan_duration: Scan duration in seconds
        """
        # Update sector stats
        sector_stats = self.query_one("#sector-stats", Static)
        percentage_good = (good_sectors / total_sectors * 100) if total_sectors > 0 else 0
        percentage_bad = (bad_sectors / total_sectors * 100) if total_sectors > 0 else 0

        sector_text = (
            f"[bold]Sector Summary:[/bold]\n"
            f"  Total: {total_sectors}\n"
            f"  Good: [green]{good_sectors}[/green] ({percentage_good:.1f}%)\n"
            f"  Bad: [red]{bad_sectors}[/red] ({percentage_bad:.1f}%)"
        )
        sector_stats.update(sector_text)

        # Update error stats if provided
        if error_breakdown:
            error_stats = self.query_one("#error-stats", Static)
            error_lines = ["[bold]Error Breakdown:[/bold]"]
            for error_type, count in sorted(error_breakdown.items()):
                error_lines.append(f"  {error_type}: {count}")
            error_stats.update("\n".join(error_lines))

        # Update performance stats if provided
        if scan_duration:
            performance_stats = self.query_one("#performance-stats", Static)
            sectors_per_sec = total_sectors / scan_duration if scan_duration > 0 else 0
            perf_text = (
                f"[bold]Performance:[/bold]\n"
                f"  Duration: {scan_duration:.1f}s\n"
                f"  Speed: {sectors_per_sec:.1f} sectors/sec"
            )
            performance_stats.update(perf_text)

    def update_recovery_stats(
        self,
        initial_bad: int,
        final_bad: int,
        recovered: int,
        recovery_rate: float
    ) -> None:
        """
        Update recovery statistics.

        Args:
            initial_bad: Initial bad sector count
            final_bad: Final bad sector count
            recovered: Number of sectors recovered
            recovery_rate: Recovery rate percentage
        """
        sector_stats = self.query_one("#sector-stats", Static)
        sector_text = (
            f"[bold]Recovery Summary:[/bold]\n"
            f"  Before: [red]{initial_bad}[/red] bad sectors\n"
            f"  After: [yellow]{final_bad}[/yellow] bad sectors\n"
            f"  Recovered: [green]{recovered}[/green] sectors\n"
            f"  Rate: {recovery_rate:.1f}%"
        )
        sector_stats.update(sector_text)
