"""
Test fixtures for USB Floppy Formatter.

Provides mock devices, handles, and data for testing without
requiring physical floppy drives.
"""

from tests.fixtures.mock_devices import (
    MockFloppyHandle,
    MockGeometry,
    MockSectorData,
    MockFormatResult,
    create_good_disk,
    create_bad_sector_0_disk,
    create_write_protected_disk,
    create_disconnected_disk,
    create_degraded_disk,
)

__all__ = [
    "MockFloppyHandle",
    "MockGeometry",
    "MockSectorData",
    "MockFormatResult",
    "create_good_disk",
    "create_bad_sector_0_disk",
    "create_write_protected_disk",
    "create_disconnected_disk",
    "create_degraded_disk",
]
