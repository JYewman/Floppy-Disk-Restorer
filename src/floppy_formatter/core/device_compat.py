"""
Compatibility layer for legacy device operations.

This module provides stub functions for the old USB floppy device management API.
These functions are deprecated and will raise NotImplementedError when called.

The Floppy Workbench 2.0 uses GreaseweazleDevice from the hardware module instead
of direct file descriptor access.

Migration Guide:
    Old (USB Floppy):
        fd = open_device('/dev/fd0', read_only=True)
        # ... do operations ...
        close_device(fd)

    New (Greaseweazle):
        from floppy_formatter.hardware import GreaseweazleDevice
        device = GreaseweazleDevice()
        device.connect()
        device.select_drive(0)
        device.motor_on()
        # ... do operations ...
        device.disconnect()
"""

import warnings
from typing import Optional


def open_device(device_path: str, read_only: bool = True) -> int:
    """
    DEPRECATED: Open a floppy device for reading/writing.

    This function is a stub for the old USB floppy API. Floppy Workbench 2.0
    uses GreaseweazleDevice instead of direct file descriptor access.

    Args:
        device_path: Path to the device (e.g., '/dev/fd0')
        read_only: If True, open for reading only

    Returns:
        File descriptor (always -1 in this stub)

    Raises:
        NotImplementedError: Always raised - use GreaseweazleDevice instead

    Example:
        # Old code (no longer works):
        fd = open_device('/dev/fd0')

        # New code:
        from floppy_formatter.hardware import GreaseweazleDevice
        device = GreaseweazleDevice()
        device.connect()
    """
    warnings.warn(
        "open_device() is deprecated. Use GreaseweazleDevice from "
        "floppy_formatter.hardware instead.",
        DeprecationWarning,
        stacklevel=2
    )
    raise NotImplementedError(
        "USB floppy device access has been removed in Floppy Workbench 2.0. "
        f"Cannot open '{device_path}'. "
        "Use GreaseweazleDevice from floppy_formatter.hardware instead. "
        "See the migration guide in the docstring."
    )


def close_device(fd: int) -> None:
    """
    DEPRECATED: Close an open device.

    This function is a stub for the old USB floppy API. Floppy Workbench 2.0
    uses GreaseweazleDevice.disconnect() instead.

    Args:
        fd: File descriptor to close

    Raises:
        NotImplementedError: Always raised - use GreaseweazleDevice instead

    Example:
        # Old code (no longer works):
        close_device(fd)

        # New code:
        device.disconnect()
    """
    warnings.warn(
        "close_device() is deprecated. Use GreaseweazleDevice.disconnect() "
        "from floppy_formatter.hardware instead.",
        DeprecationWarning,
        stacklevel=2
    )
    raise NotImplementedError(
        "USB floppy device access has been removed in Floppy Workbench 2.0. "
        "Use GreaseweazleDevice.disconnect() from floppy_formatter.hardware instead."
    )


def get_device_info(fd: int) -> dict:
    """
    DEPRECATED: Get information about an open device.

    This function is a stub for the old USB floppy API. Floppy Workbench 2.0
    uses GreaseweazleDevice.get_drive_info() instead.

    Args:
        fd: File descriptor

    Returns:
        Device information dictionary (never returns - always raises)

    Raises:
        NotImplementedError: Always raised - use GreaseweazleDevice instead
    """
    warnings.warn(
        "get_device_info() is deprecated. Use GreaseweazleDevice.get_drive_info() "
        "from floppy_formatter.hardware instead.",
        DeprecationWarning,
        stacklevel=2
    )
    raise NotImplementedError(
        "USB floppy device access has been removed in Floppy Workbench 2.0. "
        "Use GreaseweazleDevice.get_drive_info() from floppy_formatter.hardware instead."
    )


__all__ = ['open_device', 'close_device', 'get_device_info']
