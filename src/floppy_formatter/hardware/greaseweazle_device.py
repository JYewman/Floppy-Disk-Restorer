"""
Greaseweazle device driver for USB floppy controller.

This module provides the GreaseweazleDevice class which wraps the
greaseweazle.usb.Unit class to provide a high-level interface for
floppy disk operations including motor control, head positioning,
and flux-level read/write operations.

Key Features:
    - Direct motor control (no firmware timeout issues)
    - Accurate head positioning with verification
    - Raw flux capture and write operations
    - RPM measurement and drive detection
    - Full context manager support for safe resource cleanup

Example:
    with GreaseweazleDevice() as device:
        device.select_drive(0)
        device.motor_on()
        device.seek(0, 0)
        flux = device.read_track(0, 0, revolutions=1.2)
        device.motor_off()
"""

from __future__ import annotations  # PEP 563: Postponed evaluation of annotations

import logging
import time
from typing import Optional, Tuple, List

# Greaseweazle imports
try:
    from greaseweazle import usb as gw_usb
    from greaseweazle.usb import BusType
    from greaseweazle.flux import Flux
    from greaseweazle.tools.util import usb_open, find_port
    GREASEWEAZLE_AVAILABLE = True
except ImportError:
    GREASEWEAZLE_AVAILABLE = False
    gw_usb = None
    BusType = None
    Flux = None
    usb_open = None
    find_port = None

from . import (
    IFloppyDevice,
    GreaseweazleError,
    ConnectionError,
    MotorError,
    SeekError,
    FluxError,
    NoDeviceError,
    NoDiskError,
    TimeoutError,
    DriveType,
    DriveInfo,
)
from .flux_io import FluxData

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Standard 3.5" HD floppy parameters
HD_35_CYLINDERS = 80
HD_35_HEADS = 2
HD_35_SECTORS_PER_TRACK = 18
HD_35_SECTOR_SIZE = 512
HD_35_RPM_NOMINAL = 300.0
HD_35_RPM_TOLERANCE = 10.0  # +/- RPM

# Standard 3.5" DD floppy parameters
DD_35_CYLINDERS = 80
DD_35_HEADS = 2
DD_35_SECTORS_PER_TRACK = 9
DD_35_SECTOR_SIZE = 512
DD_35_RPM_NOMINAL = 300.0

# Timing constants
MOTOR_SPINUP_TIME = 0.5  # seconds to wait for motor to reach speed
SEEK_SETTLE_TIME = 0.015  # seconds to wait for head to settle (15ms)
INDEX_TIMEOUT = 2.0  # seconds to wait for index pulse


class GreaseweazleDevice(IFloppyDevice):
    """
    High-level interface for Greaseweazle floppy controller.

    This class wraps the greaseweazle Python library to provide a clean
    interface for floppy disk operations. It implements the IFloppyDevice
    interface for compatibility with the rest of the application.

    Attributes:
        unit: The underlying greaseweazle.usb.Unit object
        selected_drive: Currently selected drive unit (0 or 1)
        motor_running: Whether the drive motor is currently on
        current_cylinder: Current head position (cylinder)
        current_head: Current head position (head)
    """

    def __init__(self, usb_path: Optional[str] = None):
        """
        Initialize the Greaseweazle device.

        Args:
            usb_path: Optional specific USB device path. If None, the
                     first available Greaseweazle device is used.
        """
        if not GREASEWEAZLE_AVAILABLE:
            raise ImportError(
                "greaseweazle package not installed. "
                "Install with: pip install greaseweazle"
            )

        self._usb_path = usb_path
        self._unit: Optional[gw_usb.Unit] = None
        self._selected_drive: Optional[int] = None
        self._motor_running: bool = False
        self._current_cylinder: int = 0
        self._current_head: int = 0
        self._drive_info: Optional[DriveInfo] = None
        self._device_info: Optional[str] = None

        logger.debug("GreaseweazleDevice initialized (usb_path=%s)", usb_path)

    @property
    def unit(self) -> Optional[gw_usb.Unit]:
        """Get the underlying Greaseweazle unit object."""
        return self._unit

    @property
    def selected_drive(self) -> Optional[int]:
        """Get the currently selected drive unit."""
        return self._selected_drive

    @property
    def motor_running(self) -> bool:
        """Check if motor is running."""
        return self._motor_running

    @property
    def current_cylinder(self) -> int:
        """Get current head cylinder position."""
        return self._current_cylinder

    @property
    def current_head(self) -> int:
        """Get current head side (0 or 1)."""
        return self._current_head

    # =========================================================================
    # Connection Management
    # =========================================================================

    def connect(self) -> None:
        """
        Connect to the Greaseweazle device.

        Establishes USB connection to the Greaseweazle controller.
        If a specific USB path was provided during initialization,
        connects to that device; otherwise connects to the first
        available Greaseweazle.

        Raises:
            NoDeviceError: If no Greaseweazle device is found
            ConnectionError: If connection fails
        """
        if self._unit is not None:
            logger.warning("Already connected, disconnecting first")
            self.disconnect()

        logger.info("Connecting to Greaseweazle device...")

        try:
            # Find and open the device using greaseweazle's utility functions
            # usb_open handles finding the port and creating the serial connection
            device_path = self._usb_path

            if device_path is None:
                # Auto-detect the Greaseweazle device
                try:
                    device_path = find_port()
                    logger.debug("Auto-detected Greaseweazle at: %s", device_path)
                except Exception as e:
                    raise NoDeviceError(
                        "No Greaseweazle device found. Please check USB connection."
                    ) from e

            # Open the device (mode_check=False to avoid update mode prompts)
            self._unit = usb_open(device_path, is_update=False, mode_check=True)
            self._usb_path = device_path
            logger.debug("Connected to device: %s", device_path)

            # Set bus type to IBM PC (standard PC floppy interface)
            # This must be done before any drive operations
            # Note: set_bus_type expects an integer, not the enum directly
            self._unit.set_bus_type(BusType.IBMPC.value)
            logger.debug("Bus type set to IBM PC")

            # Get device information for logging
            self._device_info = self._get_device_info_string()
            logger.info("Connected to %s", self._device_info)

        except NoDeviceError:
            raise
        except Exception as e:
            logger.error("Failed to connect to Greaseweazle: %s", e)
            self._unit = None
            raise ConnectionError(
                f"Failed to connect to Greaseweazle: {e}",
                usb_path=self._usb_path
            ) from e

    def disconnect(self) -> None:
        """
        Disconnect from the Greaseweazle device.

        Safely shuts down the connection by:
        1. Turning off the motor if running
        2. Deselecting any selected drive
        3. Closing the USB connection

        This method is safe to call multiple times.
        """
        if self._unit is None:
            logger.debug("Already disconnected")
            return

        logger.info("Disconnecting from Greaseweazle...")

        try:
            # Ensure motor is off
            if self._motor_running:
                try:
                    self.motor_off()
                except MotorError as e:
                    logger.warning("Error turning off motor during disconnect: %s", e)

            # Deselect drive
            if self._selected_drive is not None:
                try:
                    self.deselect_drive()
                except GreaseweazleError as e:
                    logger.warning("Error deselecting drive during disconnect: %s", e)

            # Close the serial connection (Unit stores it in self.ser)
            if hasattr(self._unit, 'ser') and self._unit.ser:
                self._unit.ser.close()
            logger.info("Disconnected from Greaseweazle")

        except Exception as e:
            logger.error("Error during disconnect: %s", e)
        finally:
            self._unit = None
            self._selected_drive = None
            self._motor_running = False
            self._device_info = None

    def is_connected(self) -> bool:
        """
        Check if device is currently connected.

        Returns:
            True if connected to a Greaseweazle device, False otherwise.
        """
        return self._unit is not None

    def _ensure_connected(self) -> None:
        """Ensure device is connected, raise if not."""
        if self._unit is None:
            raise ConnectionError(
                "Not connected to Greaseweazle device. Call connect() first."
            )

    def _get_device_info_string(self) -> str:
        """Get a string describing the connected device."""
        if self._unit is None:
            return "Not connected"

        try:
            # The Unit object has hw_model, major, minor as direct attributes
            hw_model = getattr(self._unit, 'hw_model', 'Unknown')
            fw_major = getattr(self._unit, 'major', '?')
            fw_minor = getattr(self._unit, 'minor', '?')
            return f"Greaseweazle V{hw_model} (FW: {fw_major}.{fw_minor})"
        except Exception:
            return "Greaseweazle (unknown model)"

    # =========================================================================
    # Drive Selection
    # =========================================================================

    def select_drive(self, unit: int) -> None:
        """
        Select a drive unit for operations.

        The Greaseweazle can control up to 2 floppy drives. This method
        selects which drive subsequent operations will affect.

        Args:
            unit: Drive unit number (0 or 1)

        Raises:
            ConnectionError: If not connected
            GreaseweazleError: If drive selection fails
            ValueError: If unit is not 0 or 1
        """
        self._ensure_connected()

        if unit not in (0, 1):
            raise ValueError(f"Drive unit must be 0 or 1, got {unit}")

        if self._selected_drive == unit:
            logger.debug("Drive %d already selected", unit)
            return

        # Deselect current drive if any
        if self._selected_drive is not None:
            self.deselect_drive()

        logger.info("Selecting drive %d", unit)

        try:
            self._unit.drive_select(unit)
            self._selected_drive = unit
            logger.debug("Drive %d selected", unit)
        except Exception as e:
            logger.error("Failed to select drive %d: %s", unit, e)
            raise GreaseweazleError(
                f"Failed to select drive {unit}: {e}",
                device_info=self._device_info
            ) from e

    def deselect_drive(self) -> None:
        """
        Deselect the current drive.

        Turns off motor if running and deselects the current drive.
        Safe to call even if no drive is selected.
        """
        if self._selected_drive is None:
            logger.debug("No drive selected")
            return

        self._ensure_connected()

        # Turn off motor first
        if self._motor_running:
            try:
                self.motor_off()
            except MotorError as e:
                logger.warning("Error turning off motor during deselect: %s", e)

        logger.info("Deselecting drive %d", self._selected_drive)

        try:
            self._unit.drive_deselect()
            self._selected_drive = None
            logger.debug("Drive deselected")
        except Exception as e:
            logger.error("Failed to deselect drive: %s", e)
            raise GreaseweazleError(
                f"Failed to deselect drive: {e}",
                device_info=self._device_info
            ) from e

    def _ensure_drive_selected(self) -> None:
        """Ensure a drive is selected, raise if not."""
        if self._selected_drive is None:
            raise GreaseweazleError(
                "No drive selected. Call select_drive() first.",
                device_info=self._device_info
            )

    # =========================================================================
    # Motor Control
    # =========================================================================

    def motor_on(self) -> None:
        """
        Turn on the drive motor.

        Unlike USB floppy drives with firmware-controlled motors,
        the Greaseweazle gives us direct motor control. The motor
        will stay on until explicitly turned off.

        Waits for motor to reach operating speed before returning.

        Raises:
            ConnectionError: If not connected
            GreaseweazleError: If no drive selected
            MotorError: If motor control fails
        """
        self._ensure_connected()
        self._ensure_drive_selected()

        if self._motor_running:
            logger.debug("Motor already running")
            return

        logger.info("Turning motor on for drive %d", self._selected_drive)

        try:
            self._unit.drive_motor(self._selected_drive, True)
            self._motor_running = True

            # Wait for motor to spin up
            logger.debug("Waiting %.2fs for motor spinup", MOTOR_SPINUP_TIME)
            time.sleep(MOTOR_SPINUP_TIME)

            logger.debug("Motor is running")
        except Exception as e:
            logger.error("Failed to turn on motor: %s", e)
            self._motor_running = False
            raise MotorError(
                f"Failed to turn on motor: {e}",
                motor_state=False,
                device_info=self._device_info
            ) from e

    def motor_off(self) -> None:
        """
        Turn off the drive motor.

        Safely stops the drive motor. This should be called when
        operations are complete to avoid unnecessary wear.

        Raises:
            ConnectionError: If not connected
            MotorError: If motor control fails
        """
        self._ensure_connected()

        if not self._motor_running:
            logger.debug("Motor already off")
            return

        if self._selected_drive is None:
            logger.warning("Motor marked as running but no drive selected")
            self._motor_running = False
            return

        logger.info("Turning motor off for drive %d", self._selected_drive)

        try:
            self._unit.drive_motor(self._selected_drive, False)
            self._motor_running = False
            logger.debug("Motor is off")
        except Exception as e:
            logger.error("Failed to turn off motor: %s", e)
            raise MotorError(
                f"Failed to turn off motor: {e}",
                motor_state=True,
                device_info=self._device_info
            ) from e

    def is_motor_on(self) -> bool:
        """
        Check if drive motor is currently running.

        Returns:
            True if motor is on, False otherwise.
        """
        return self._motor_running

    # =========================================================================
    # Head Positioning
    # =========================================================================

    def seek(self, cylinder: int, head: int) -> None:
        """
        Move the head to the specified cylinder and head.

        Performs a seek operation to position the head at the specified
        cylinder. The head parameter selects which side of the disk
        to use (0 = bottom, 1 = top).

        Args:
            cylinder: Target cylinder number (0-79 for 3.5" HD)
            head: Target head number (0 or 1)

        Raises:
            ConnectionError: If not connected
            GreaseweazleError: If no drive selected
            SeekError: If seek operation fails
            ValueError: If cylinder or head is out of range
        """
        self._ensure_connected()
        self._ensure_drive_selected()

        # Validate parameters
        if cylinder < 0 or cylinder >= HD_35_CYLINDERS:
            raise ValueError(
                f"Cylinder must be 0-{HD_35_CYLINDERS - 1}, got {cylinder}"
            )
        if head not in (0, 1):
            raise ValueError(f"Head must be 0 or 1, got {head}")

        # Check if already at position
        if self._current_cylinder == cylinder and self._current_head == head:
            logger.debug("Already at C%d H%d", cylinder, head)
            return

        logger.debug("Seeking to cylinder %d, head %d", cylinder, head)

        try:
            # Greaseweazle's seek takes cylinder and head parameters
            self._unit.seek(cylinder, head)

            # Update position tracking
            self._current_cylinder = cylinder
            self._current_head = head

            # Allow time for head to settle
            time.sleep(SEEK_SETTLE_TIME)

            logger.debug("Seek complete, now at C%d H%d", cylinder, head)
        except Exception as e:
            logger.error("Seek to C%d H%d failed: %s", cylinder, head, e)
            raise SeekError(
                f"Seek failed: {e}",
                target_cylinder=cylinder,
                target_head=head,
                device_info=self._device_info
            ) from e

    def seek_track0(self) -> None:
        """
        Seek to track 0 (recalibrate).

        Moves the head to cylinder 0 using the drive's track 0 sensor.
        This is useful for recalibration and ensuring accurate positioning.

        Raises:
            ConnectionError: If not connected
            GreaseweazleError: If no drive selected
            SeekError: If seek fails
        """
        logger.info("Seeking to track 0 (recalibrate)")
        self.seek(0, 0)

    def get_current_position(self) -> Tuple[int, int]:
        """
        Get current head position.

        Returns:
            Tuple of (cylinder, head)
        """
        return (self._current_cylinder, self._current_head)

    # =========================================================================
    # Track Operations
    # =========================================================================

    def read_track(self, cylinder: int, head: int,
                   revolutions: float = 1.2) -> FluxData:
        """
        Read raw flux data from a track.

        Captures the magnetic flux transitions from the specified track.
        The flux data can then be decoded to extract sector data.

        Args:
            cylinder: Cylinder number to read (0-79)
            head: Head number to read (0 or 1)
            revolutions: Number of disk revolutions to capture (default 1.2)

        Returns:
            FluxData object containing the captured flux timing data

        Raises:
            ConnectionError: If not connected
            GreaseweazleError: If no drive selected or motor not running
            FluxError: If read operation fails
        """
        self._ensure_connected()
        self._ensure_drive_selected()

        if not self._motor_running:
            raise GreaseweazleError(
                "Motor must be running to read track. Call motor_on() first.",
                device_info=self._device_info
            )

        # Seek to the target track
        self.seek(cylinder, head)

        # Convert float revolutions to int for API (round up to ensure full coverage)
        revs_int = max(1, int(revolutions + 0.5))

        logger.debug(
            "Reading track C%d H%d (%d revolutions)",
            cylinder, head, revs_int
        )

        try:
            # Read the track using Greaseweazle
            # The head selection is done via seek before this call
            flux = self._unit.read_track(revs=revs_int)

            # Convert to our FluxData format
            flux_data = FluxData.from_greaseweazle_flux(flux, cylinder, head)

            logger.debug(
                "Read %d flux transitions from C%d H%d",
                len(flux_data.flux_times), cylinder, head
            )

            return flux_data

        except Exception as e:
            logger.error("Failed to read track C%d H%d: %s", cylinder, head, e)
            raise FluxError(
                f"Failed to read track: {e}",
                cylinder=cylinder,
                head=head,
                operation="read",
                device_info=self._device_info
            ) from e

    def write_track(self, cylinder: int, head: int, flux_data: FluxData) -> None:
        """
        Write raw flux data to a track.

        Writes pre-encoded flux data to the specified track. The flux
        data should be properly formatted for the target disk format
        (typically MFM-encoded).

        Args:
            cylinder: Cylinder number to write (0-79)
            head: Head number to write (0 or 1)
            flux_data: FluxData object containing the flux to write

        Raises:
            ConnectionError: If not connected
            GreaseweazleError: If no drive selected or motor not running
            FluxError: If write operation fails
        """
        self._ensure_connected()
        self._ensure_drive_selected()

        if not self._motor_running:
            raise GreaseweazleError(
                "Motor must be running to write track. Call motor_on() first.",
                device_info=self._device_info
            )

        # Seek to the target track
        self.seek(cylinder, head)

        logger.info("Writing track C%d H%d", cylinder, head)

        try:
            # Convert to Greaseweazle flux format
            gw_flux = flux_data.to_greaseweazle_flux()

            # Write the track
            self._unit.write_track(gw_flux)

            logger.debug("Successfully wrote track C%d H%d", cylinder, head)

        except Exception as e:
            logger.error("Failed to write track C%d H%d: %s", cylinder, head, e)
            raise FluxError(
                f"Failed to write track: {e}",
                cylinder=cylinder,
                head=head,
                operation="write",
                device_info=self._device_info
            ) from e

    def erase_track(self, cylinder: int, head: int) -> None:
        """
        Erase a track (DC erase).

        Performs a bulk erase of the specified track. This is useful
        before writing new data to ensure a clean magnetic surface.

        Args:
            cylinder: Cylinder number to erase (0-79)
            head: Head number to erase (0 or 1)

        Raises:
            ConnectionError: If not connected
            GreaseweazleError: If no drive selected or motor not running
            FluxError: If erase operation fails
        """
        self._ensure_connected()
        self._ensure_drive_selected()

        if not self._motor_running:
            raise GreaseweazleError(
                "Motor must be running to erase track. Call motor_on() first.",
                device_info=self._device_info
            )

        # Seek to the target track
        self.seek(cylinder, head)

        logger.info("Erasing track C%d H%d", cylinder, head)

        try:
            self._unit.erase_track()
            logger.debug("Successfully erased track C%d H%d", cylinder, head)

        except Exception as e:
            logger.error("Failed to erase track C%d H%d: %s", cylinder, head, e)
            raise FluxError(
                f"Failed to erase track: {e}",
                cylinder=cylinder,
                head=head,
                operation="erase",
                device_info=self._device_info
            ) from e

    # =========================================================================
    # Drive Information
    # =========================================================================

    def reinitialize_drive(self) -> None:
        """
        Reinitialize the drive connection to a known good state.

        This is useful when the drive state may be out of sync with the
        Greaseweazle controller (e.g., after motor auto-start from disk
        insertion). It ensures proper bus configuration without doing
        a full reset (which can conflict with motor auto-start drives).

        Raises:
            ConnectionError: If not connected
            GreaseweazleError: If reinitialization fails
        """
        self._ensure_connected()

        logger.info("Reinitializing drive connection...")

        # Save current state
        drive_unit = self._selected_drive if self._selected_drive is not None else 0

        try:
            # DON'T use power_on_reset() - it can conflict with drives that
            # have motor auto-start (motor already spinning when we connect).
            # Instead, just ensure proper configuration without resetting.

            # Set bus type (safe to call even if already set)
            self._unit.set_bus_type(BusType.IBMPC.value)
            logger.debug("Bus type set to IBM PC")

            # Select drive (asserts DRIVE SELECT line)
            self._unit.drive_select(drive_unit)
            self._selected_drive = drive_unit
            logger.debug("Drive %d selected", drive_unit)

            # Turn on motor (asserts MOTOR ENABLE line)
            # Even if motor is physically running due to auto-start,
            # we need to assert the MOTOR ENABLE line for the Greaseweazle
            # to properly communicate with the drive
            self._unit.drive_motor(drive_unit, True)
            self._motor_running = True
            logger.debug("Motor command sent")

            # Wait for motor to stabilize (even if already running)
            time.sleep(MOTOR_SPINUP_TIME)

            # Try to seek to track 0 - helps with index pulse detection
            # but not critical for basic operations like RPM measurement.
            # Some drives may fail TRK00 detection but still work fine.
            try:
                logger.debug("Seeking to track 0...")
                self._unit.seek(0, 0)
                self._current_cylinder = 0
                self._current_head = 0
                logger.debug("Seek to track 0 complete")
            except Exception as seek_error:
                # TRK00 sensor issue - log warning but continue
                logger.warning("Seek to track 0 failed: %s (continuing anyway)", seek_error)
                # Head position unknown, but motor is running
                self._current_cylinder = None
                self._current_head = None

            # Additional delay for head to settle
            time.sleep(0.2)

            # Verify drive state using firmware query
            try:
                drive_info = self._unit.get_current_drive_info()
                logger.info("Drive info: motor_on=%s, cyl=%s",
                           drive_info.motor_on, drive_info.cyl)
                if not drive_info.motor_on:
                    logger.warning("Drive reports motor is off after motor_on command")
            except Exception as e:
                logger.debug("Could not query drive info: %s", e)

            logger.info("Drive reinitialized successfully")

        except Exception as e:
            logger.error("Failed to reinitialize drive: %s", e)
            raise GreaseweazleError(
                f"Failed to reinitialize drive: {e}",
                device_info=self._device_info
            ) from e

    def get_rpm(self) -> float:
        """
        Measure the current drive RPM.

        Measures the actual rotational speed of the disk by timing
        index pulses. The drive motor must be running.

        Returns:
            Measured RPM value (typically ~300 for 3.5" drives)

        Raises:
            ConnectionError: If not connected
            GreaseweazleError: If no drive selected or motor not running
            TimeoutError: If index pulse not detected
        """
        self._ensure_connected()
        self._ensure_drive_selected()

        logger.debug("Measuring drive RPM...")

        # If motor isn't marked as running, reinitialize the entire drive
        # connection to ensure proper state synchronization
        if not self._motor_running:
            logger.info("Motor not running, reinitializing drive...")
            self.reinitialize_drive()

        # Seek to track 0 for reliable RPM measurement
        try:
            self._unit.seek(0, 0)
            self._current_cylinder = 0
            self._current_head = 0
        except Exception as e:
            logger.debug("Seek to track 0 failed: %s", e)
            # If seek fails, try reinitializing and seek again
            self.reinitialize_drive()
            try:
                self._unit.seek(0, 0)
                self._current_cylinder = 0
                self._current_head = 0
            except Exception as e2:
                logger.warning("Seek to track 0 failed after reinit: %s", e2)

        # Retry logic for index pulse detection
        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                # Read 1 revolution - same approach as official 'gw rpm' command
                # The index_list[-1] value represents total samples from start
                # to the final INDEX pulse, which equals one rotation period
                flux = self._unit.read_track(revs=1)

                if not flux.index_list or len(flux.index_list) < 1:
                    if attempt < max_attempts - 1:
                        logger.debug("No index pulse detected, retrying (attempt %d/%d)...",
                                     attempt + 1, max_attempts)
                        # On failure, try reinitializing
                        if attempt == 1:
                            logger.info("Reinitializing drive after index detection failure...")
                            self.reinitialize_drive()
                        time.sleep(0.3)
                        continue
                    raise TimeoutError(
                        "Could not detect index pulse for RPM measurement. "
                        "Check that a disk is inserted and the drive is working.",
                        operation="rpm_measurement",
                        device_info=self._device_info
                    )

                # Use the same calculation as official 'gw rpm' command:
                # time_per_revolution = index_list[-1] / sample_freq
                # This gives the time from start of capture to the final INDEX pulse
                logger.debug("RPM calc: sample_freq=%s, index_list=%s",
                            flux.sample_freq, flux.index_list)

                time_per_rev = flux.index_list[-1] / flux.sample_freq
                rpm = 60.0 / time_per_rev

                logger.debug("RPM calc: time_per_rev=%.3f ms, rpm=%.1f",
                            time_per_rev * 1000, rpm)

                # Sanity check - if RPM is way off, log detailed diagnostics
                if rpm < 100 or rpm > 500:
                    logger.warning(
                        "RPM calculation seems wrong (%.1f): sample_freq=%s, "
                        "time_per_rev=%.6f, index_list=%s",
                        rpm, flux.sample_freq, time_per_rev, flux.index_list
                    )

                logger.info("Measured RPM: %.1f", rpm)
                return rpm

            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    logger.debug("RPM measurement failed (attempt %d/%d): %s",
                                 attempt + 1, max_attempts, e)
                    # On second attempt, reinitialize
                    if attempt == 0:
                        logger.info("Reinitializing drive after RPM measurement failure...")
                        try:
                            self.reinitialize_drive()
                        except Exception as reinit_error:
                            logger.warning("Reinitialize failed: %s", reinit_error)
                    time.sleep(0.3)
                else:
                    break

        # All retries failed
        if last_error:
            logger.error("RPM measurement failed after %d attempts: %s", max_attempts, last_error)
            raise GreaseweazleError(
                f"Failed to measure RPM: {last_error}",
                device_info=self._device_info
            ) from last_error

        # Should never reach here
        raise GreaseweazleError(
            "RPM measurement failed unexpectedly",
            device_info=self._device_info
        )

    def try_get_rpm(self) -> Optional[float]:
        """
        Try to measure drive RPM without aggressive retry/reinitialize.

        This is a lightweight version of get_rpm() suitable for background
        polling. It makes a single attempt and returns None on failure
        instead of raising exceptions or triggering reinitialization.

        Returns:
            Measured RPM value, or None if measurement failed
        """
        if not self.is_connected() or self._unit is None:
            return None

        if self._selected_drive is None:
            return None

        if not self._motor_running:
            return None

        try:
            # Single attempt to read flux - same approach as official 'gw rpm'
            flux = self._unit.read_track(revs=1)

            if not flux.index_list or len(flux.index_list) < 1:
                return None

            # Use the same calculation as official 'gw rpm' command:
            # time_per_revolution = index_list[-1] / sample_freq
            time_per_rev = flux.index_list[-1] / flux.sample_freq
            rpm = 60.0 / time_per_rev

            # Basic sanity check - reject obviously wrong values
            if rpm < 100 or rpm > 500:
                return None

            logger.debug("Polled RPM: %.1f", rpm)
            return rpm

        except Exception:
            # Silent failure for polling - caller handles display
            return None

    def get_drive_info(self) -> DriveInfo:
        """
        Get information about the connected drive.

        Returns information about the drive geometry and capabilities.
        This is determined by measuring the drive characteristics.

        Returns:
            DriveInfo object with drive specifications

        Note:
            Currently assumes 3.5" HD drive. Future versions may
            auto-detect drive type.
        """
        if self._drive_info is not None:
            return self._drive_info

        # Try to measure RPM if motor is running
        rpm = HD_35_RPM_NOMINAL
        if self._motor_running:
            try:
                rpm = self.get_rpm()
            except (GreaseweazleError, TimeoutError):
                logger.warning("Could not measure RPM, using nominal value")

        # Assume 3.5" HD for now
        # Future: Could probe track 80+ to detect 40-track drives
        self._drive_info = DriveInfo(
            drive_type=DriveType.HD_35,
            cylinders=HD_35_CYLINDERS,
            heads=HD_35_HEADS,
            sectors_per_track=HD_35_SECTORS_PER_TRACK,
            sector_size=HD_35_SECTOR_SIZE,
            rpm=rpm
        )

        return self._drive_info

    def is_disk_present(self) -> bool:
        """
        Check if a disk is present in the drive.

        Attempts to detect disk presence by looking for index pulses.
        The motor must be running for this to work.

        Returns:
            True if disk is present, False otherwise

        Note:
            This may give false negatives for very damaged disks that
            don't have readable index holes.
        """
        self._ensure_connected()
        self._ensure_drive_selected()

        if not self._motor_running:
            # Can't detect without motor running
            logger.warning("Cannot detect disk presence without motor running")
            return False

        try:
            # Try to read a bit of flux and look for index pulse
            flux = self._unit.read_track(revs=2)

            # If we got index pulses, a disk is present
            has_disk = bool(flux.index_list and len(flux.index_list) > 0)

            logger.debug("Disk present: %s", has_disk)
            return has_disk

        except Exception as e:
            logger.warning("Error checking disk presence: %s", e)
            return False

    # =========================================================================
    # Context Manager
    # =========================================================================

    def __enter__(self) -> 'GreaseweazleDevice':
        """Context manager entry - connect to device."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - safely disconnect."""
        self.disconnect()

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def reset(self) -> None:
        """
        Reset the device to a known state.

        Turns off motor, deselects drive, and seeks to track 0.
        Useful for error recovery.
        """
        logger.info("Resetting device state")

        try:
            if self._motor_running:
                self.motor_off()
        except MotorError as e:
            logger.warning("Error turning off motor during reset: %s", e)

        self._current_cylinder = 0
        self._current_head = 0

        logger.debug("Device reset complete")

    def __repr__(self) -> str:
        """String representation of device state."""
        if not self.is_connected():
            return "GreaseweazleDevice(not connected)"

        return (
            f"GreaseweazleDevice("
            f"device={self._device_info}, "
            f"drive={self._selected_drive}, "
            f"motor={'on' if self._motor_running else 'off'}, "
            f"position=C{self._current_cylinder}H{self._current_head})"
        )
