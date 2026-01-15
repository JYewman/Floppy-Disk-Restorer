"""
Greaseweazle hardware abstraction layer for floppy disk operations.

This module provides the hardware interface for communicating with floppy drives
via Greaseweazle V4.1 USB controller. It includes device management, flux-level
I/O operations, MFM encoding/decoding, and drive calibration.

Classes:
    GreaseweazleDevice: Main device class for Greaseweazle operations
    FluxData: Dataclass for raw flux capture data
    IFloppyDevice: Abstract interface for floppy device implementations

Exceptions:
    GreaseweazleError: Base exception for all Greaseweazle-related errors
    ConnectionError: USB connection/disconnection errors
    MotorError: Motor control failures
    SeekError: Head positioning errors
    FluxError: Flux read/write errors
    CRCError: Data CRC validation failures
    NoDeviceError: No Greaseweazle device found
    NoDiskError: No disk in drive
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Tuple, Callable
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class GreaseweazleError(Exception):
    """Base exception for all Greaseweazle-related errors."""

    def __init__(self, message: str, device_info: Optional[str] = None):
        self.message = message
        self.device_info = device_info
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.device_info:
            return f"{self.message} [Device: {self.device_info}]"
        return self.message


class ConnectionError(GreaseweazleError):
    """Raised when USB connection or disconnection fails."""

    def __init__(self, message: str, usb_path: Optional[str] = None,
                 device_info: Optional[str] = None):
        self.usb_path = usb_path
        super().__init__(message, device_info)

    def _format_message(self) -> str:
        base = super()._format_message()
        if self.usb_path:
            return f"{base} [USB: {self.usb_path}]"
        return base


class MotorError(GreaseweazleError):
    """Raised when motor control operations fail."""

    def __init__(self, message: str, motor_state: Optional[bool] = None,
                 device_info: Optional[str] = None):
        self.motor_state = motor_state
        super().__init__(message, device_info)


class SeekError(GreaseweazleError):
    """Raised when head positioning fails."""

    def __init__(self, message: str, target_cylinder: Optional[int] = None,
                 target_head: Optional[int] = None,
                 device_info: Optional[str] = None):
        self.target_cylinder = target_cylinder
        self.target_head = target_head
        super().__init__(message, device_info)

    def _format_message(self) -> str:
        base = super()._format_message()
        if self.target_cylinder is not None:
            return f"{base} [Target: C{self.target_cylinder}H{self.target_head or 0}]"
        return base


class FluxError(GreaseweazleError):
    """Raised when flux read/write operations fail."""

    def __init__(self, message: str, cylinder: Optional[int] = None,
                 head: Optional[int] = None, operation: Optional[str] = None,
                 device_info: Optional[str] = None):
        self.cylinder = cylinder
        self.head = head
        self.operation = operation
        super().__init__(message, device_info)

    def _format_message(self) -> str:
        base = super()._format_message()
        parts = []
        if self.operation:
            parts.append(f"Op: {self.operation}")
        if self.cylinder is not None:
            parts.append(f"C{self.cylinder}H{self.head or 0}")
        if parts:
            return f"{base} [{', '.join(parts)}]"
        return base


class CRCError(GreaseweazleError):
    """Raised when CRC validation fails for sector data."""

    def __init__(self, message: str, cylinder: Optional[int] = None,
                 head: Optional[int] = None, sector: Optional[int] = None,
                 expected_crc: Optional[int] = None,
                 actual_crc: Optional[int] = None,
                 device_info: Optional[str] = None):
        self.cylinder = cylinder
        self.head = head
        self.sector = sector
        self.expected_crc = expected_crc
        self.actual_crc = actual_crc
        super().__init__(message, device_info)

    def _format_message(self) -> str:
        base = super()._format_message()
        parts = []
        if self.cylinder is not None:
            parts.append(f"CHS: {self.cylinder}/{self.head or 0}/{self.sector or 0}")
        if self.expected_crc is not None and self.actual_crc is not None:
            parts.append(f"CRC: expected 0x{self.expected_crc:04X}, got 0x{self.actual_crc:04X}")
        if parts:
            return f"{base} [{', '.join(parts)}]"
        return base


class NoDeviceError(GreaseweazleError):
    """Raised when no Greaseweazle device is found."""

    def __init__(self, message: str = "No Greaseweazle device found"):
        super().__init__(message)


class NoDiskError(GreaseweazleError):
    """Raised when no disk is present in the drive."""

    def __init__(self, message: str = "No disk in drive",
                 drive_unit: Optional[int] = None,
                 device_info: Optional[str] = None):
        self.drive_unit = drive_unit
        super().__init__(message, device_info)

    def _format_message(self) -> str:
        base = super()._format_message()
        if self.drive_unit is not None:
            return f"{base} [Drive: {self.drive_unit}]"
        return base


class TimeoutError(GreaseweazleError):
    """Raised when an operation times out."""

    def __init__(self, message: str, operation: Optional[str] = None,
                 timeout_seconds: Optional[float] = None,
                 device_info: Optional[str] = None):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        super().__init__(message, device_info)

    def _format_message(self) -> str:
        base = super()._format_message()
        parts = []
        if self.operation:
            parts.append(f"Op: {self.operation}")
        if self.timeout_seconds is not None:
            parts.append(f"Timeout: {self.timeout_seconds}s")
        if parts:
            return f"{base} [{', '.join(parts)}]"
        return base


# =============================================================================
# Enums and Constants
# =============================================================================

class DriveType(IntEnum):
    """Floppy drive type enumeration."""
    UNKNOWN = 0
    DD_35 = 1      # 3.5" Double Density (720KB)
    HD_35 = 2      # 3.5" High Density (1.44MB)
    DD_525 = 3     # 5.25" Double Density (360KB)
    HD_525 = 4     # 5.25" High Density (1.2MB)


class SectorStatus(IntEnum):
    """Status of a decoded sector."""
    GOOD = 0           # Sector decoded successfully with valid CRC
    CRC_ERROR = 1      # Sector decoded but CRC failed
    MISSING = 2        # Sector header not found
    WEAK = 3           # Sector decoded but signal quality poor
    NO_DATA = 4        # Header found but data field missing/corrupted


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DriveInfo:
    """Information about the connected floppy drive."""
    drive_type: DriveType
    cylinders: int
    heads: int
    sectors_per_track: int
    sector_size: int
    rpm: float

    @property
    def total_sectors(self) -> int:
        """Calculate total number of sectors on disk."""
        return self.cylinders * self.heads * self.sectors_per_track

    @property
    def capacity_bytes(self) -> int:
        """Calculate total disk capacity in bytes."""
        return self.total_sectors * self.sector_size

    @property
    def capacity_kb(self) -> float:
        """Calculate total disk capacity in kilobytes."""
        return self.capacity_bytes / 1024


@dataclass
class SectorData:
    """Represents decoded sector data with metadata."""
    cylinder: int
    head: int
    sector: int
    data: bytes
    status: SectorStatus
    crc_valid: bool
    signal_quality: float  # 0.0 to 1.0, higher is better

    @property
    def chs(self) -> Tuple[int, int, int]:
        """Return cylinder, head, sector as tuple."""
        return (self.cylinder, self.head, self.sector)

    @property
    def is_good(self) -> bool:
        """Check if sector was read successfully."""
        return self.status == SectorStatus.GOOD and self.crc_valid


# =============================================================================
# Abstract Interface
# =============================================================================

class IFloppyDevice(ABC):
    """
    Abstract interface for floppy device implementations.

    This interface allows for different hardware backends (Greaseweazle,
    KryoFlux, SuperCard Pro, etc.) to be used interchangeably.
    """

    @abstractmethod
    def connect(self) -> None:
        """
        Establish connection to the device.

        Raises:
            ConnectionError: If connection fails
            NoDeviceError: If no device is found
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnect from the device and release resources.

        Should be safe to call multiple times.
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if device is currently connected."""
        pass

    @abstractmethod
    def select_drive(self, unit: int) -> None:
        """
        Select a drive unit for operations.

        Args:
            unit: Drive unit number (0 or 1)

        Raises:
            GreaseweazleError: If drive selection fails
        """
        pass

    @abstractmethod
    def deselect_drive(self) -> None:
        """Deselect the current drive."""
        pass

    @abstractmethod
    def motor_on(self) -> None:
        """
        Turn on the drive motor.

        Raises:
            MotorError: If motor control fails
        """
        pass

    @abstractmethod
    def motor_off(self) -> None:
        """
        Turn off the drive motor.

        Raises:
            MotorError: If motor control fails
        """
        pass

    @abstractmethod
    def is_motor_on(self) -> bool:
        """Check if drive motor is currently running."""
        pass

    @abstractmethod
    def seek(self, cylinder: int, head: int) -> None:
        """
        Move the head to the specified cylinder and head.

        Args:
            cylinder: Target cylinder number (0-79 for 3.5" HD)
            head: Target head number (0 or 1)

        Raises:
            SeekError: If seek operation fails
        """
        pass

    @abstractmethod
    def get_current_position(self) -> Tuple[int, int]:
        """
        Get current head position.

        Returns:
            Tuple of (cylinder, head)
        """
        pass

    @abstractmethod
    def read_track(self, cylinder: int, head: int,
                   revolutions: float = 1.2) -> 'FluxData':
        """
        Read raw flux data from a track.

        Args:
            cylinder: Cylinder number to read
            head: Head number to read
            revolutions: Number of disk revolutions to capture

        Returns:
            FluxData object containing raw flux timing data

        Raises:
            FluxError: If read operation fails
        """
        pass

    @abstractmethod
    def write_track(self, cylinder: int, head: int, flux_data: 'FluxData') -> None:
        """
        Write raw flux data to a track.

        Args:
            cylinder: Cylinder number to write
            head: Head number to write
            flux_data: FluxData object containing flux to write

        Raises:
            FluxError: If write operation fails
        """
        pass

    @abstractmethod
    def erase_track(self, cylinder: int, head: int) -> None:
        """
        Erase a track (DC erase).

        Args:
            cylinder: Cylinder number to erase
            head: Head number to erase

        Raises:
            FluxError: If erase operation fails
        """
        pass

    @abstractmethod
    def get_rpm(self) -> float:
        """
        Measure the current drive RPM.

        Returns:
            Measured RPM value

        Raises:
            GreaseweazleError: If RPM measurement fails
        """
        pass

    @abstractmethod
    def get_drive_info(self) -> DriveInfo:
        """
        Get information about the connected drive.

        Returns:
            DriveInfo object with drive specifications
        """
        pass

    @abstractmethod
    def is_disk_present(self) -> bool:
        """
        Check if a disk is present in the drive.

        Returns:
            True if disk is present, False otherwise
        """
        pass

    def __enter__(self) -> 'IFloppyDevice':
        """Context manager entry - connect to device."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - disconnect from device."""
        self.disconnect()


# =============================================================================
# Type Aliases
# =============================================================================

# Progress callback type: (current_track, total_tracks, operation_name)
ProgressCallback = Callable[[int, int, str], None]

# Sector callback type: (cylinder, head, sector, status)
SectorCallback = Callable[[int, int, int, SectorStatus], None]


# =============================================================================
# Package Exports
# =============================================================================

# Import main classes for convenient access
__all__ = [
    # Exceptions
    'GreaseweazleError',
    'ConnectionError',
    'MotorError',
    'SeekError',
    'FluxError',
    'CRCError',
    'NoDeviceError',
    'NoDiskError',
    'TimeoutError',
    # Enums
    'DriveType',
    'SectorStatus',
    # Data classes (from __init__)
    'DriveInfo',
    'SectorData',
    # Interface
    'IFloppyDevice',
    # Type aliases
    'ProgressCallback',
    'SectorCallback',
    # From greaseweazle_device.py
    'GreaseweazleDevice',
    # From flux_io.py
    'FluxData',
    'FluxReader',
    'FluxWriter',
    'read_track_flux',
    'write_track_flux',
    'erase_track_flux',
    'analyze_flux_quality',
    'compare_flux_captures',
    'merge_flux_captures',
    # From mfm_codec.py
    'MFMDecoder',
    'MFMEncoder',
    'MFMBitstream',
    'decode_flux_to_sectors',
    'decode_flux_data',
    'encode_sectors_to_flux',
    'verify_sector_crc',
    'calculate_crc',
    'create_formatted_track',
    'create_pattern_track',
    # From drive_calibration.py
    'DriveCalibration',
    'RPMMeasurement',
    'BitTimingMeasurement',
    'AlignmentResult',
    'DriveHealth',
    'HealthGrade',
    'calibrate_drive',
    'quick_calibration',
    'measure_rpm',
    'measure_bit_timing',
    'check_head_alignment',
    'format_calibration_report',
]

# =============================================================================
# Submodule Imports (after base classes are defined to avoid circular imports)
# =============================================================================

# Import classes from submodules - these depend on base classes defined above
from .flux_io import FluxData, FluxReader, FluxWriter
from .greaseweazle_device import GreaseweazleDevice
from .mfm_codec import (
    MFMDecoder, MFMEncoder, MFMBitstream,
    decode_flux_to_sectors, encode_sectors_to_flux,
    verify_sector_crc, calculate_crc,
    create_formatted_track, create_pattern_track,
)
from .drive_calibration import (
    DriveCalibration, RPMMeasurement, BitTimingMeasurement,
    AlignmentResult, DriveHealth, HealthGrade,
    calibrate_drive, quick_calibration, measure_rpm,
    measure_bit_timing, check_head_alignment,
    format_calibration_report,
)

# Also import the flux I/O functions
from .flux_io import (
    read_track_flux, write_track_flux, erase_track_flux,
    analyze_flux_quality, compare_flux_captures, merge_flux_captures,
)


# =============================================================================
# PLL Decoder Helper
# =============================================================================

def decode_flux_data(flux_data: 'FluxData') -> List['SectorData']:
    """
    Decode flux data to sectors using PLL decoder (preferred) or simple decoder (fallback).

    The PLL (Phase-Locked Loop) decoder dynamically adjusts phase and frequency to
    track timing variations, providing much more robust decoding than the simple
    division-based method.

    Args:
        flux_data: FluxData from track read

    Returns:
        List of SectorData objects
    """
    # Try PLL decoder first (more robust for real-world flux data)
    try:
        from .pll_decoder import decode_flux_with_pll
        sectors = decode_flux_with_pll(flux_data)
        if sectors:
            logger.debug("PLL decoder returned %d sectors", len(sectors))
            return sectors
    except ImportError:
        logger.debug("PLL decoder not available, using simple decoder")
    except Exception as e:
        logger.warning("PLL decoder failed: %s, falling back to simple decoder", e)

    # Fall back to simple decoder
    sectors = decode_flux_to_sectors(flux_data)
    logger.debug("Simple decoder returned %d sectors", len(sectors))
    return sectors
