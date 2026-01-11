"""
Mock device fixtures for testing USB Floppy Formatter.

Provides mock implementations of Linux file descriptors, geometry data,
and sector I/O operations for testing without physical hardware.
"""

from dataclasses import dataclass
from typing import Dict, List, Set, Optional
import struct
import errno

from floppy_formatter.core import DiskGeometry

# Linux error codes (errno values)
ERROR_SUCCESS = 0           # Success (no error)
ERROR_CRC = errno.EIO       # I/O error (5)
ERROR_SECTOR_NOT_FOUND = errno.ENXIO  # No such device or address (6)
ERROR_WRITE_PROTECT = errno.EROFS     # Read-only file system (30)
ERROR_NOT_READY = errno.ENODEV        # No such device (19)
ERROR_ACCESS_DENIED = errno.EACCES    # Permission denied (13)


@dataclass
class MockGeometry:
    """
    Mock disk geometry for 1.44MB floppy.

    Returns standard 80/2/18/512 configuration.
    """
    cylinders: int = 80
    heads: int = 2
    sectors_per_track: int = 18
    bytes_per_sector: int = 512

    def to_disk_geometry(self) -> DiskGeometry:
        """Convert to DiskGeometry object."""
        return DiskGeometry(
            media_type=0x0F,  # F3_1Pt44_512
            cylinders=self.cylinders,
            heads=self.heads,
            sectors_per_track=self.sectors_per_track,
            bytes_per_sector=self.bytes_per_sector
        )


@dataclass
class MockSectorData:
    """
    Mock sector data for read/write operations.

    Attributes:
        sector_number: Sector number (0-2879)
        data: Sector data bytes
        is_good: Whether sector is readable
        error_code: Error code if sector is bad
    """
    sector_number: int
    data: bytes
    is_good: bool = True
    error_code: int = ERROR_SUCCESS

    @staticmethod
    def create_good_sector(sector_number: int, pattern: int = 0x00) -> "MockSectorData":
        """Create a good sector with specified pattern."""
        return MockSectorData(
            sector_number=sector_number,
            data=bytes([pattern] * 512),
            is_good=True,
            error_code=ERROR_SUCCESS
        )

    @staticmethod
    def create_bad_sector(sector_number: int, error_code: int = ERROR_CRC) -> "MockSectorData":
        """Create a bad sector with specified error."""
        return MockSectorData(
            sector_number=sector_number,
            data=b'',
            is_good=False,
            error_code=error_code
        )


@dataclass
class MockFormatResult:
    """
    Mock format operation result.

    Attributes:
        success: Whether format succeeded
        bad_track_count: Number of bad tracks detected
        bad_tracks: List of bad track numbers
        error_code: Error code if format failed
    """
    success: bool = True
    bad_track_count: int = 0
    bad_tracks: List[int] = None
    error_code: int = ERROR_SUCCESS

    def __post_init__(self):
        if self.bad_tracks is None:
            self.bad_tracks = []


class MockFloppyHandle:
    """
    Mock floppy drive file descriptor simulating Linux behavior.

    Provides realistic simulation of disk operations including:
    - Sector read/write with configurable errors
    - Track formatting with bad track detection
    - Device state (connected, write-protected, etc.)
    """

    def __init__(
        self,
        geometry: MockGeometry = None,
        bad_sectors: Set[int] = None,
        write_protected: bool = False,
        disconnected: bool = False
    ):
        """
        Initialize mock floppy handle.

        Args:
            geometry: Disk geometry (default: 80/2/18/512)
            bad_sectors: Set of bad sector numbers
            write_protected: Whether disk is write-protected
            disconnected: Whether disk is disconnected
        """
        self.geometry = geometry or MockGeometry()
        self.bad_sectors = bad_sectors or set()
        self.write_protected = write_protected
        self.disconnected = disconnected
        self.sector_data: Dict[int, bytes] = {}
        self.read_count = 0
        self.write_count = 0
        self.format_count = 0

        # Initialize all sectors with zeros
        total_sectors = (
            self.geometry.cylinders *
            self.geometry.heads *
            self.geometry.sectors_per_track
        )
        for sector in range(total_sectors):
            if sector not in self.bad_sectors:
                self.sector_data[sector] = bytes([0x00] * self.geometry.bytes_per_sector)

    def read_sector(self, sector_number: int) -> tuple[bool, bytes, int]:
        """
        Simulate reading a sector.

        Args:
            sector_number: Sector to read

        Returns:
            Tuple of (success, data, error_code)
        """
        self.read_count += 1

        if self.disconnected:
            return (False, b'', ERROR_NOT_READY)

        if sector_number in self.bad_sectors:
            return (False, b'', ERROR_CRC)

        if sector_number < 0 or sector_number >= 2880:
            return (False, b'', ERROR_SECTOR_NOT_FOUND)

        data = self.sector_data.get(sector_number, bytes([0x00] * 512))
        return (True, data, ERROR_SUCCESS)

    def write_sector(self, sector_number: int, data: bytes) -> tuple[bool, int]:
        """
        Simulate writing a sector.

        Args:
            sector_number: Sector to write
            data: Data to write (must be 512 bytes)

        Returns:
            Tuple of (success, error_code)
        """
        self.write_count += 1

        if self.disconnected:
            return (False, ERROR_NOT_READY)

        if self.write_protected:
            return (False, ERROR_WRITE_PROTECT)

        if len(data) != self.geometry.bytes_per_sector:
            return (False, ERROR_ACCESS_DENIED)

        if sector_number in self.bad_sectors:
            return (False, ERROR_CRC)

        if sector_number < 0 or sector_number >= 2880:
            return (False, ERROR_SECTOR_NOT_FOUND)

        self.sector_data[sector_number] = data
        return (True, ERROR_SUCCESS)

    def format_track(self, cylinder: int, head: int) -> MockFormatResult:
        """
        Simulate formatting a track.

        Args:
            cylinder: Cylinder number (0-79)
            head: Head number (0-1)

        Returns:
            MockFormatResult with format status
        """
        self.format_count += 1

        if self.disconnected:
            return MockFormatResult(
                success=False,
                error_code=ERROR_NOT_READY
            )

        if self.write_protected:
            return MockFormatResult(
                success=False,
                error_code=ERROR_WRITE_PROTECT
            )

        # Calculate track sectors
        track_start = (cylinder * self.geometry.heads + head) * self.geometry.sectors_per_track

        # Check if any sectors in this track are bad
        bad_in_track = [
            s for s in range(track_start, track_start + self.geometry.sectors_per_track)
            if s in self.bad_sectors
        ]

        if bad_in_track:
            # Track has bad sectors
            track_number = cylinder * self.geometry.heads + head
            return MockFormatResult(
                success=True,
                bad_track_count=1,
                bad_tracks=[track_number]
            )
        else:
            # Track is good
            return MockFormatResult(
                success=True,
                bad_track_count=0,
                bad_tracks=[]
            )

    def disconnect(self):
        """Simulate device disconnection."""
        self.disconnected = True

    def reconnect(self):
        """Simulate device reconnection."""
        self.disconnected = False

    def set_write_protect(self, protected: bool):
        """Set write protection state."""
        self.write_protected = protected

    def mark_sector_bad(self, sector_number: int):
        """Mark a sector as bad."""
        self.bad_sectors.add(sector_number)

    def mark_sector_good(self, sector_number: int):
        """Mark a sector as good (recovery simulation)."""
        if sector_number in self.bad_sectors:
            self.bad_sectors.remove(sector_number)
            self.sector_data[sector_number] = bytes([0x00] * 512)

    def get_statistics(self) -> dict:
        """Get operation statistics."""
        return {
            'read_count': self.read_count,
            'write_count': self.write_count,
            'format_count': self.format_count,
            'bad_sectors': len(self.bad_sectors),
        }


def create_good_disk() -> MockFloppyHandle:
    """
    Create a mock handle for a good disk with no bad sectors.

    Returns:
        MockFloppyHandle with all sectors good
    """
    return MockFloppyHandle(
        geometry=MockGeometry(),
        bad_sectors=set(),
        write_protected=False,
        disconnected=False
    )


def create_bad_sector_0_disk() -> MockFloppyHandle:
    """
    Create a mock handle for a disk with bad sector 0.

    This simulates the PRIMARY requirement - disks with bad boot sector
    that need recovery.

    Returns:
        MockFloppyHandle with sector 0 marked bad
    """
    return MockFloppyHandle(
        geometry=MockGeometry(),
        bad_sectors={0},
        write_protected=False,
        disconnected=False
    )


def create_write_protected_disk() -> MockFloppyHandle:
    """
    Create a mock handle for a write-protected disk.

    Returns:
        MockFloppyHandle with write protection enabled
    """
    return MockFloppyHandle(
        geometry=MockGeometry(),
        bad_sectors=set(),
        write_protected=True,
        disconnected=False
    )


def create_disconnected_disk() -> MockFloppyHandle:
    """
    Create a mock handle for a disconnected disk.

    Returns:
        MockFloppyHandle in disconnected state
    """
    return MockFloppyHandle(
        geometry=MockGeometry(),
        bad_sectors=set(),
        write_protected=False,
        disconnected=True
    )


def create_degraded_disk(bad_sector_count: int = 147) -> MockFloppyHandle:
    """
    Create a mock handle for a degraded disk with multiple bad sectors.

    Args:
        bad_sector_count: Number of bad sectors to create

    Returns:
        MockFloppyHandle with specified number of bad sectors
    """
    # Create bad sectors scattered across the disk
    bad_sectors = set(range(0, bad_sector_count))

    return MockFloppyHandle(
        geometry=MockGeometry(),
        bad_sectors=bad_sectors,
        write_protected=False,
        disconnected=False
    )
