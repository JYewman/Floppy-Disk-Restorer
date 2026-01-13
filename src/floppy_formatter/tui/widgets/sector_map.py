"""
Sector map widget for USB Floppy Formatter.

Displays visual representation of all disk sectors with:
- Color-coded status (good/bad/recovering)
- Real-time updates during scanning
- Click for sector details
- Legend display
"""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Vertical


class SectorMapWidget(Static):
    """Visual sector map widget."""

    DEFAULT_CSS = """
    SectorMapWidget {
        padding: 1;
        border: heavy green;
        background: $surface;
        width: 100%;
        height: auto;
        min-height: 18;
    }
    """

    def __init__(self, geometry, **kwargs):
        """
        Initialize sector map widget.

        Args:
            geometry: Disk geometry information
        """
        # Initialize with placeholder content
        initial_content = (
            "[bold cyan]═══ Disk Visualization (Real-time) ═══[/bold cyan]\n"
            "\n"
            "[dim]Waiting for scan to begin...[/dim]\n"
            "\n"
            f"[dim]Total sectors: {geometry.total_sectors}[/dim]\n"
            "\n"
            "[dim]Legend: [green]█[/green] Good  [red]X[/red] Bad  [dim]·[/dim] Unscanned[/dim]"
        )
        super().__init__(initial_content, **kwargs)
        self.geometry = geometry
        self.sector_status = {}  # sector_num -> is_good

    def compose(self) -> ComposeResult:
        """Create sector map layout."""
        return []

    def on_mount(self) -> None:
        """Handle widget mount - initialize sector map display."""
        self.rebuild_map()

    def rebuild_map(self) -> None:
        """Rebuild the entire sector map display as a compact track visualization."""
        # Calculate statistics
        good_count = sum(1 for is_good in self.sector_status.values() if is_good)
        bad_count = sum(1 for is_good in self.sector_status.values() if not is_good)
        scanned_count = len(self.sector_status)

        # Build the entire visualization as a single rich text string
        lines = []
        lines.append("[bold cyan]═══ Disk Visualization (Real-time) ═══[/bold cyan]")
        lines.append("")

        # If no sectors scanned yet, show placeholder
        if scanned_count == 0:
            lines.append("[dim]Waiting for scan to begin...[/dim]")
            lines.append("")
            lines.append(f"[dim]Total sectors: {self.geometry.total_sectors}[/dim]")
        else:
            # Display tracks in a compact grid format
            total_tracks = self.geometry.cylinders * self.geometry.heads
            sectors_per_track = self.geometry.sectors_per_track
            track_step = max(1, total_tracks // 40)

            for track_num in range(0, total_tracks, track_step):
                track_symbols = []
                start_sector = track_num * sectors_per_track

                for sector_offset in range(min(sectors_per_track, 36)):
                    sector_num = start_sector + sector_offset
                    if sector_num >= self.geometry.total_sectors:
                        break

                    if sector_num not in self.sector_status:
                        track_symbols.append("[dim]·[/dim]")
                    elif self.sector_status[sector_num]:
                        track_symbols.append("[green]█[/green]")
                    else:
                        track_symbols.append("[red]X[/red]")

                if track_symbols:
                    track_line = f"[dim]T{track_num:03d}[/dim] " + "".join(track_symbols)
                    lines.append(track_line)

            # Add statistics
            lines.append("")
            lines.append(
                f"[dim]Scanned: {scanned_count}/{self.geometry.total_sectors} | "
                f"[green]Good: {good_count}[/green] | [red]Bad: {bad_count}[/red][/dim]"
            )

        lines.append("")
        lines.append("[dim]Legend: [green]█[/green] Good  [red]X[/red] Bad  [dim]·[/dim] Unscanned[/dim]")

        # Update the Static widget's content
        self.update("\n".join(lines))

    def get_sector_symbol_colored(self, sector_num: int) -> str:
        """
        Get colored symbol for a sector (with markup for circular display).

        Args:
            sector_num: Sector number

        Returns:
            Symbol string with color markup
        """
        if sector_num not in self.sector_status:
            return "[dim]·[/dim]"  # Unscanned

        is_good = self.sector_status[sector_num]
        if is_good:
            return "[green]█[/green]"  # Good sector - solid green block
        else:
            return "[red]X[/red]"  # Bad sector - red X mark

    def get_sector_symbol_simple(self, sector_num: int) -> str:
        """
        Get simple symbol for a sector (without markup for circular display).

        Args:
            sector_num: Sector number

        Returns:
            Single character symbol
        """
        if sector_num not in self.sector_status:
            return "·"  # Unscanned

        is_good = self.sector_status[sector_num]
        if is_good:
            return "█"  # Good sector - solid block
        else:
            return "X"  # Bad sector - X mark

    def get_sector_symbol(self, sector_num: int) -> str:
        """
        Get display symbol for a sector.

        Args:
            sector_num: Sector number

        Returns:
            Symbol string with color markup
        """
        if sector_num not in self.sector_status:
            return "[dim]·[/dim]"  # Unscanned

        is_good = self.sector_status[sector_num]
        if is_good:
            return "[green]●[/green]"  # Good sector
        else:
            return "[red]●[/red]"  # Bad sector

    def update_sector(self, sector_num: int, is_good: bool) -> None:
        """
        Update a single sector status.

        Args:
            sector_num: Sector number
            is_good: Whether sector is good
        """
        self.sector_status[sector_num] = is_good

        # Rebuild map periodically for performance
        # Rebuild every 2 tracks (36 sectors) for smooth updates without lag
        sectors_per_track = self.geometry.sectors_per_track
        if sector_num % (sectors_per_track * 2) == 0 or sector_num == self.geometry.total_sectors - 1:
            self.rebuild_map()

    def mark_sector_recovering(self, sector_num: int) -> None:
        """
        Mark a sector as being recovered.

        Args:
            sector_num: Sector number
        """
        # For now, just mark as bad until recovery completes
        # Could be enhanced to show different status
        self.update_sector(sector_num, False)
