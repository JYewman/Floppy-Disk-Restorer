"""
Bad sector scanning and surface analysis for floppy disks.

This module provides comprehensive disk scanning functionality including:
- Full surface scan of all 2,880 sectors
- Bad sector detection and classification
- Track-level analysis and reporting
- Real-time progress reporting
- Performance metrics tracking
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Tuple

from floppy_formatter.core.sector_io import read_sector, classify_error, ERROR_SUCCESS, BYTES_PER_SECTOR
from floppy_formatter.core.geometry import (
    DiskGeometry,
    CYLINDERS_1PT44MB,
    HEADS_PER_CYLINDER_1PT44MB,
    SECTORS_PER_TRACK_1PT44MB,
    TOTAL_SECTORS_1PT44MB,
)


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class SectorMap:
    """
    Complete map of sector status across the disk.

    This data structure holds the results of a full surface scan,
    including which sectors are good, which are bad, and what
    specific errors were encountered.

    Attributes:
        total_sectors: Total number of sectors scanned (should be 2880 for 1.44MB)
        good_sectors: List of sector numbers that read successfully
        bad_sectors: List of sector numbers that failed to read
        error_types: Mapping of sector number to error description
        scan_duration: Time taken to complete scan in seconds

    Example:
        >>> sector_map = scan_all_sectors(handle, geometry)
        >>> print(f"Bad sectors: {len(sector_map.bad_sectors)}")
        >>> for sector in sector_map.bad_sectors:
        ...     print(f"Sector {sector}: {sector_map.error_types[sector]}")
    """
    total_sectors: int
    good_sectors: List[int] = field(default_factory=list)
    bad_sectors: List[int] = field(default_factory=list)
    error_types: Dict[int, str] = field(default_factory=dict)
    scan_duration: float = 0.0

    def get_good_sector_count(self) -> int:
        """Get count of successfully read sectors."""
        return len(self.good_sectors)

    def get_bad_sector_count(self) -> int:
        """Get count of failed sectors."""
        return len(self.bad_sectors)

    def get_success_rate(self) -> float:
        """
        Get percentage of sectors that read successfully.

        Returns:
            Success rate as percentage (0.0 to 100.0)
        """
        if self.total_sectors == 0:
            return 0.0
        return (len(self.good_sectors) / self.total_sectors) * 100.0

    def is_sector_good(self, sector_number: int) -> bool:
        """Check if a specific sector read successfully."""
        return sector_number in self.good_sectors

    def is_sector_bad(self, sector_number: int) -> bool:
        """Check if a specific sector failed to read."""
        return sector_number in self.bad_sectors

    def get_sector_error(self, sector_number: int) -> Optional[str]:
        """
        Get error description for a bad sector.

        Args:
            sector_number: Sector number to query

        Returns:
            Error description string, or None if sector is good
        """
        return self.error_types.get(sector_number)


@dataclass
class TrackInfo:
    """
    Information about a single track (cylinder/head combination).

    A track consists of 18 consecutive sectors. This structure
    provides track-level grouping for efficient reporting.

    Attributes:
        cylinder: Cylinder number (0-79)
        head: Head number (0-1)
        start_sector: First sector number in this track
        end_sector: Last sector number in this track (inclusive)
        good_sectors: List of good sector numbers in this track
        bad_sectors: List of bad sector numbers in this track
        error_types: Mapping of sector number to error description

    Example:
        >>> track = get_track_info(sector_map, cylinder=0, head=0)
        >>> print(f"Track C{track.cylinder}:H{track.head}")
        >>> print(f"  Good: {len(track.good_sectors)}/18")
        >>> print(f"  Bad: {len(track.bad_sectors)}/18")
    """
    cylinder: int
    head: int
    start_sector: int
    end_sector: int
    good_sectors: List[int] = field(default_factory=list)
    bad_sectors: List[int] = field(default_factory=list)
    error_types: Dict[int, str] = field(default_factory=dict)

    def get_track_number(self) -> int:
        """
        Get linear track number (0-159).

        Track numbering: track = cylinder * 2 + head
        """
        return self.cylinder * HEADS_PER_CYLINDER_1PT44MB + self.head

    def get_good_sector_count(self) -> int:
        """Get count of good sectors in this track."""
        return len(self.good_sectors)

    def get_bad_sector_count(self) -> int:
        """Get count of bad sectors in this track."""
        return len(self.bad_sectors)

    def is_track_good(self) -> bool:
        """Check if all sectors in track are good."""
        return len(self.bad_sectors) == 0

    def is_track_bad(self) -> bool:
        """Check if any sectors in track are bad."""
        return len(self.bad_sectors) > 0

    def get_health_percentage(self) -> float:
        """
        Get track health as percentage.

        Returns:
            Percentage of good sectors (0.0 to 100.0)
        """
        total = len(self.good_sectors) + len(self.bad_sectors)
        if total == 0:
            return 0.0
        return (len(self.good_sectors) / total) * 100.0


@dataclass
class ScanStatistics:
    """
    Performance and summary statistics for a disk scan.

    Attributes:
        total_sectors: Total sectors scanned
        good_sectors: Count of good sectors
        bad_sectors: Count of bad sectors
        scan_duration: Total scan time in seconds
        sectors_per_second: Average read speed
        error_breakdown: Count of each error type
        track_count: Total number of tracks (160 for 1.44MB)
        good_tracks: Count of tracks with all sectors good
        bad_tracks: Count of tracks with at least one bad sector

    Example:
        >>> stats = get_scan_statistics(sector_map)
        >>> print(f"Scan completed in {stats.scan_duration:.2f} seconds")
        >>> print(f"Read speed: {stats.sectors_per_second:.1f} sectors/sec")
        >>> print(f"Success rate: {stats.get_success_rate():.1f}%")
    """
    total_sectors: int
    good_sectors: int
    bad_sectors: int
    scan_duration: float
    sectors_per_second: float
    error_breakdown: Dict[str, int] = field(default_factory=dict)
    track_count: int = 160
    good_tracks: int = 0
    bad_tracks: int = 0

    def get_success_rate(self) -> float:
        """Get success rate as percentage (0.0 to 100.0)."""
        if self.total_sectors == 0:
            return 0.0
        return (self.good_sectors / self.total_sectors) * 100.0

    def get_failure_rate(self) -> float:
        """Get failure rate as percentage (0.0 to 100.0)."""
        return 100.0 - self.get_success_rate()

    def get_estimated_time_remaining(self, sectors_scanned: int) -> float:
        """
        Estimate time remaining based on current progress.

        Args:
            sectors_scanned: Number of sectors scanned so far

        Returns:
            Estimated seconds remaining
        """
        if sectors_scanned == 0 or self.sectors_per_second == 0:
            return 0.0
        sectors_remaining = self.total_sectors - sectors_scanned
        return sectors_remaining / self.sectors_per_second


# =============================================================================
# Sector Scanning Functions
# =============================================================================


def scan_all_sectors(
    handle,
    geometry: DiskGeometry,
    progress_callback: Optional[Callable[[int, int, bool, Optional[str]], None]] = None
) -> SectorMap:
    """
    Perform full surface scan of all sectors on the disk.

    This function reads every sector on the disk sequentially,
    recording which sectors are good, which are bad, and what
    specific errors occurred. Progress can be reported via callback.

    Args:
        handle: Linux file descriptor to physical drive
        geometry: Disk geometry information
        progress_callback: Optional function(sector_num, total, is_good, error_type)
                          for progress updates

    Returns:
        SectorMap with complete scan results

    Example:
        >>> def show_progress(sector_num, total, is_good, error_type):
        ...     percent = (sector_num / total) * 100
        ...     status = "OK" if is_good else f"BAD ({error_type})"
        ...     print(f"Scanning: {percent:.1f}% - Sector {sector_num}: {status}")
        >>>
        >>> handle = open_physical_drive(drive_num)
        >>> geometry = get_disk_geometry(handle)
        >>> sector_map = scan_all_sectors(handle, geometry, show_progress)
        >>> print(f"Scan complete: {len(sector_map.bad_sectors)} bad sectors")
        >>> close_handle(handle)
    """
    # Initialize sector map
    sector_map = SectorMap(total_sectors=geometry.total_sectors)

    # Record start time for performance tracking
    start_time = time.time()

    # Scan each sector sequentially
    for sector_number in range(geometry.total_sectors):
        # Read the sector
        success, data, error_code = read_sector(
            handle, sector_number, geometry.bytes_per_sector
        )

        if success:
            # Sector read successfully
            sector_map.good_sectors.append(sector_number)
            error_description = None
        else:
            # Sector failed to read
            sector_map.bad_sectors.append(sector_number)
            # Classify and record the error
            error_description = classify_error(error_code)
            sector_map.error_types[sector_number] = error_description

        # Report progress if callback provided
        if progress_callback is not None:
            progress_callback(
                sector_number + 1,
                geometry.total_sectors,
                success,
                error_description
            )

    # Record scan duration
    end_time = time.time()
    sector_map.scan_duration = end_time - start_time

    return sector_map


def scan_track(
    handle,
    cylinder: int,
    head: int,
    geometry: DiskGeometry,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> TrackInfo:
    """
    Scan all sectors in a single track.

    A track consists of 18 consecutive sectors on a specific
    cylinder and head. This function scans just that track.

    Args:
        handle: Linux file descriptor to physical drive
        cylinder: Cylinder number (0-79)
        head: Head number (0-1)
        geometry: Disk geometry information
        progress_callback: Optional function(current, total) for progress updates

    Returns:
        TrackInfo with scan results for this track

    Example:
        >>> track = scan_track(handle, cylinder=0, head=0, geometry)
        >>> if track.is_track_good():
        ...     print("Track is perfect!")
        ... else:
        ...     print(f"Track has {track.get_bad_sector_count()} bad sectors")
    """
    # Calculate sector range for this track
    # Formula: start_sector = (cylinder * heads + head) * sectors_per_track
    start_sector = (cylinder * geometry.heads + head) * geometry.sectors_per_track
    end_sector = start_sector + geometry.sectors_per_track - 1

    # Initialize track info
    track = TrackInfo(
        cylinder=cylinder,
        head=head,
        start_sector=start_sector,
        end_sector=end_sector
    )

    # Scan each sector in the track
    for i in range(geometry.sectors_per_track):
        sector_number = start_sector + i

        # Read the sector
        success, data, error_code = read_sector(
            handle, sector_number, geometry.bytes_per_sector
        )

        if success:
            # Sector read successfully
            track.good_sectors.append(sector_number)
        else:
            # Sector failed to read
            track.bad_sectors.append(sector_number)
            # Classify and record the error
            error_description = classify_error(error_code)
            track.error_types[sector_number] = error_description

        # Report progress if callback provided
        if progress_callback is not None:
            progress_callback(i + 1, geometry.sectors_per_track)

    return track


def get_track_info(
    sector_map: SectorMap,
    cylinder: int,
    head: int,
    geometry: Optional[DiskGeometry] = None
) -> TrackInfo:
    """
    Extract track information from a complete sector map.

    This function analyzes a full sector map and extracts
    information about a specific track.

    Args:
        sector_map: Complete sector map from scan_all_sectors()
        cylinder: Cylinder number (0-79)
        head: Head number (0-1)
        geometry: Optional disk geometry (uses defaults if not provided)

    Returns:
        TrackInfo for the specified track

    Example:
        >>> sector_map = scan_all_sectors(handle, geometry)
        >>> # Analyze track 0 (cylinder 0, head 0)
        >>> track = get_track_info(sector_map, 0, 0)
        >>> print(f"Track 0: {track.get_good_sector_count()}/18 good")
    """
    # Use provided geometry or defaults
    if geometry is None:
        sectors_per_track = SECTORS_PER_TRACK_1PT44MB
        heads = HEADS_PER_CYLINDER_1PT44MB
    else:
        sectors_per_track = geometry.sectors_per_track
        heads = geometry.heads

    # Calculate sector range for this track
    start_sector = (cylinder * heads + head) * sectors_per_track
    end_sector = start_sector + sectors_per_track - 1

    # Initialize track info
    track = TrackInfo(
        cylinder=cylinder,
        head=head,
        start_sector=start_sector,
        end_sector=end_sector
    )

    # Extract sector information for this track
    for sector_number in range(start_sector, end_sector + 1):
        if sector_map.is_sector_good(sector_number):
            track.good_sectors.append(sector_number)
        elif sector_map.is_sector_bad(sector_number):
            track.bad_sectors.append(sector_number)
            error = sector_map.get_sector_error(sector_number)
            if error:
                track.error_types[sector_number] = error

    return track


def get_all_tracks(
    sector_map: SectorMap,
    geometry: Optional[DiskGeometry] = None
) -> List[TrackInfo]:
    """
    Extract information for all tracks from a sector map.

    Args:
        sector_map: Complete sector map from scan_all_sectors()
        geometry: Optional disk geometry (uses defaults if not provided)

    Returns:
        List of TrackInfo objects (160 tracks for 1.44MB floppy)

    Example:
        >>> sector_map = scan_all_sectors(handle, geometry)
        >>> all_tracks = get_all_tracks(sector_map)
        >>> bad_track_count = sum(1 for t in all_tracks if t.is_track_bad())
        >>> print(f"Bad tracks: {bad_track_count}/160")
    """
    # Use provided geometry or defaults
    if geometry is None:
        cylinders = CYLINDERS_1PT44MB
        heads = HEADS_PER_CYLINDER_1PT44MB
    else:
        cylinders = geometry.cylinders
        heads = geometry.heads

    tracks = []

    # Extract info for each track
    for cylinder in range(cylinders):
        for head in range(heads):
            track = get_track_info(sector_map, cylinder, head, geometry)
            tracks.append(track)

    return tracks


def get_scan_statistics(
    sector_map: SectorMap,
    geometry: Optional[DiskGeometry] = None
) -> ScanStatistics:
    """
    Calculate comprehensive statistics from a sector map.

    This function analyzes a complete sector map and generates
    detailed statistics including performance metrics, error
    breakdowns, and track-level summaries.

    Args:
        sector_map: Complete sector map from scan_all_sectors()
        geometry: Optional disk geometry (uses defaults if not provided)

    Returns:
        ScanStatistics with comprehensive analysis

    Example:
        >>> sector_map = scan_all_sectors(handle, geometry)
        >>> stats = get_scan_statistics(sector_map)
        >>> print(f"Scan took {stats.scan_duration:.2f} seconds")
        >>> print(f"Speed: {stats.sectors_per_second:.1f} sectors/sec")
        >>> print(f"Bad sectors: {stats.bad_sectors} ({stats.get_failure_rate():.1f}%)")
        >>> print("\\nError breakdown:")
        >>> for error_type, count in stats.error_breakdown.items():
        ...     print(f"  {error_type}: {count}")
    """
    # Calculate sectors per second
    if sector_map.scan_duration > 0:
        sectors_per_second = sector_map.total_sectors / sector_map.scan_duration
    else:
        sectors_per_second = 0.0

    # Build error breakdown
    error_breakdown: Dict[str, int] = {}
    for error_type in sector_map.error_types.values():
        error_breakdown[error_type] = error_breakdown.get(error_type, 0) + 1

    # Analyze tracks
    all_tracks = get_all_tracks(sector_map, geometry)
    good_tracks = sum(1 for track in all_tracks if track.is_track_good())
    bad_tracks = sum(1 for track in all_tracks if track.is_track_bad())

    # Create statistics object
    stats = ScanStatistics(
        total_sectors=sector_map.total_sectors,
        good_sectors=len(sector_map.good_sectors),
        bad_sectors=len(sector_map.bad_sectors),
        scan_duration=sector_map.scan_duration,
        sectors_per_second=sectors_per_second,
        error_breakdown=error_breakdown,
        track_count=len(all_tracks),
        good_tracks=good_tracks,
        bad_tracks=bad_tracks,
    )

    return stats


def find_bad_track_clusters(
    sector_map: SectorMap,
    geometry: Optional[DiskGeometry] = None,
    cluster_size: int = 3
) -> List[Tuple[int, int]]:
    """
    Find clusters of consecutive bad tracks.

    Physical damage often affects multiple adjacent tracks.
    This function identifies groups of consecutive bad tracks
    which likely indicate physical damage to the disk surface.

    Args:
        sector_map: Complete sector map from scan_all_sectors()
        geometry: Optional disk geometry (uses defaults if not provided)
        cluster_size: Minimum number of consecutive bad tracks to report

    Returns:
        List of (start_track, end_track) tuples for each cluster

    Example:
        >>> sector_map = scan_all_sectors(handle, geometry)
        >>> clusters = find_bad_track_clusters(sector_map)
        >>> for start, end in clusters:
        ...     track_count = end - start + 1
        ...     print(f"Damage cluster: tracks {start}-{end} ({track_count} tracks)")
    """
    all_tracks = get_all_tracks(sector_map, geometry)

    clusters = []
    cluster_start = None
    cluster_length = 0

    for i, track in enumerate(all_tracks):
        if track.is_track_bad():
            if cluster_start is None:
                # Start of new cluster
                cluster_start = i
                cluster_length = 1
            else:
                # Continue existing cluster
                cluster_length += 1
        else:
            # End of cluster (if any)
            if cluster_start is not None and cluster_length >= cluster_size:
                clusters.append((cluster_start, cluster_start + cluster_length - 1))
            cluster_start = None
            cluster_length = 0

    # Check for cluster at end of disk
    if cluster_start is not None and cluster_length >= cluster_size:
        clusters.append((cluster_start, cluster_start + cluster_length - 1))

    return clusters


def get_sector_address(
    sector_number: int,
    geometry: Optional[DiskGeometry] = None
) -> Tuple[int, int, int]:
    """
    Convert linear sector number to cylinder/head/sector address.

    Args:
        sector_number: Linear sector number (0-2879)
        geometry: Optional disk geometry (uses defaults if not provided)

    Returns:
        Tuple of (cylinder, head, sector) where sector is 0-based

    Example:
        >>> cylinder, head, sector = get_sector_address(36)
        >>> print(f"Sector 36 = C{cylinder}:H{head}:S{sector}")
        Sector 36 = C1:H0:S0
    """
    # Use provided geometry or defaults
    if geometry is None:
        sectors_per_track = SECTORS_PER_TRACK_1PT44MB
        heads = HEADS_PER_CYLINDER_1PT44MB
    else:
        sectors_per_track = geometry.sectors_per_track
        heads = geometry.heads

    # Calculate cylinder, head, and sector
    sectors_per_cylinder = sectors_per_track * heads
    cylinder = sector_number // sectors_per_cylinder
    remainder = sector_number % sectors_per_cylinder
    head = remainder // sectors_per_track
    sector = remainder % sectors_per_track

    return (cylinder, head, sector)


def format_sector_address(
    sector_number: int,
    geometry: Optional[DiskGeometry] = None
) -> str:
    """
    Format sector number as human-readable address.

    Args:
        sector_number: Linear sector number (0-2879)
        geometry: Optional disk geometry (uses defaults if not provided)

    Returns:
        Formatted string like "C10:H1:S5 (Sector 365)"

    Example:
        >>> print(format_sector_address(0))
        C0:H0:S0 (Sector 0)
        >>> print(format_sector_address(2879))
        C79:H1:S17 (Sector 2879)
    """
    cylinder, head, sector = get_sector_address(sector_number, geometry)
    return f"C{cylinder}:H{head}:S{sector} (Sector {sector_number})"
