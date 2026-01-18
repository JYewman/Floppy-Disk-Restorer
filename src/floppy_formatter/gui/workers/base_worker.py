"""
Base worker class for Greaseweazle floppy operations.

Provides the foundation for all threaded disk operations with:
- Device reference management
- Cancellation with motor-safe shutdown
- Error handling with device recovery
- Signal-based communication

Part of Phase 9: Workers & Background Processing
"""

import logging
import time
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Time to wait for motor to spin down after shutdown
MOTOR_SPINDOWN_DELAY = 0.3  # seconds

# Maximum recovery attempts before giving up
MAX_RECOVERY_ATTEMPTS = 3

# Delay between recovery attempts
RECOVERY_DELAY = 0.5  # seconds


# =============================================================================
# Base Worker Class
# =============================================================================

class BaseWorker(QObject):
    """
    Base class for all disk operation workers.

    This class provides the foundation for threaded disk operations with:
    - Progress reporting via signals
    - Operation completion/failure notification
    - Cancellation support
    - Error handling

    Workers should be moved to a QThread using moveToThread() and connected
    to the thread's started signal to begin work.

    Example:
        thread = QThread()
        worker = ScanWorker(device, geometry)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.operation_completed.connect(handle_result)
        worker.operation_failed.connect(handle_error)
        thread.start()
    """

    # Signal emitted when operation completes successfully
    # Carries the result object (type varies by worker)
    operation_completed = pyqtSignal(object)

    # Signal emitted when operation fails
    # Carries error message string
    operation_failed = pyqtSignal(str)

    # Signal to indicate worker has finished (success or failure)
    # Used to trigger thread cleanup
    finished = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        """
        Initialize base worker.

        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._cancelled = False
        self._running = False

    def cancel(self) -> None:
        """
        Request cancellation of the operation.

        Sets the internal cancellation flag which should be checked
        periodically during long-running operations. The worker should
        stop gracefully when this flag is set.
        """
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """
        Check if cancellation has been requested.

        Returns:
            True if cancel() has been called, False otherwise
        """
        return self._cancelled

    def is_running(self) -> bool:
        """
        Check if the worker is currently running.

        Returns:
            True if run() is executing, False otherwise
        """
        return self._running

    def run(self) -> None:
        """
        Execute the worker's operation.

        Subclasses must override this method to implement their
        specific disk operation. The implementation should:
        1. Set self._running = True at the start
        2. Periodically check self._cancelled and stop if True
        3. Emit operation_completed on success
        4. Emit operation_failed on error
        5. Set self._running = False at the end
        6. Emit finished when done (success or failure)
        """
        raise NotImplementedError("Subclasses must implement run()")

    def _emit_completed(self, result: object) -> None:
        """
        Helper to emit completion signal and finish.

        Args:
            result: The result object to send
        """
        self._running = False
        self.operation_completed.emit(result)
        self.finished.emit()

    def _emit_failed(self, error_message: str) -> None:
        """
        Helper to emit failure signal and finish.

        Args:
            error_message: Description of the error
        """
        self._running = False
        self.operation_failed.emit(error_message)
        self.finished.emit()

    def _emit_cancelled(self) -> None:
        """
        Helper to emit cancellation as a failure and finish.
        """
        self._emit_failed("Operation cancelled by user")


# =============================================================================
# Greaseweazle Worker Base Class
# =============================================================================

class GreaseweazleWorker(QObject):
    """
    Base class for all Greaseweazle disk operation workers.

    Provides comprehensive device management, cancellation with motor-safe
    shutdown, and error handling with device recovery. All workers that
    interact with the Greaseweazle hardware should inherit from this class.

    Features:
    - Device reference management with None handling
    - Cancellation with motor-safe shutdown sequence
    - Error handling with automatic device recovery attempts
    - Standard signal set for UI integration
    - Execute wrapper for setup/cleanup

    Signals:
        started: Emitted when operation begins
        finished: Emitted when operation completes (success or failure)
        progress(int): Overall progress percentage (0-100)
        error(str): Emitted on non-fatal errors
        device_error(str): Emitted on unrecoverable device errors

    Example:
        class MyScanWorker(GreaseweazleWorker):
            scan_complete = pyqtSignal(object)

            def __init__(self, device, geometry):
                super().__init__(device)
                self._geometry = geometry

            def run(self):
                # Implement scanning logic here
                pass
    """

    # Standard signals for all Greaseweazle workers
    started = pyqtSignal()
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    error = pyqtSignal(str)
    device_error = pyqtSignal(str)

    def __init__(
        self,
        device: Optional['GreaseweazleDevice'] = None,
        parent: Optional[QObject] = None
    ):
        """
        Initialize Greaseweazle worker.

        Args:
            device: Optional GreaseweazleDevice instance. Operations will
                   fail gracefully if device is None.
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._device = device
        self._cancelled = False
        self._running = False
        self._motor_was_on = False

        logger.debug(
            "%s initialized with device=%s",
            self.__class__.__name__,
            "connected" if device else "None"
        )

    # =========================================================================
    # Device Management
    # =========================================================================

    def get_device(self) -> Optional['GreaseweazleDevice']:
        """
        Get the Greaseweazle device reference.

        Returns:
            GreaseweazleDevice instance or None if not available
        """
        return self._device

    def set_device(self, device: Optional['GreaseweazleDevice']) -> None:
        """
        Set the Greaseweazle device reference.

        Args:
            device: GreaseweazleDevice instance or None
        """
        self._device = device

    def has_device(self) -> bool:
        """
        Check if a valid device is available.

        Returns:
            True if device is set and connected, False otherwise
        """
        if self._device is None:
            return False
        return self._device.is_connected()

    def _ensure_device(self) -> bool:
        """
        Ensure device is available and connected.

        Returns:
            True if device is ready, False otherwise

        Side effects:
            Emits device_error signal if device not available
        """
        if self._device is None:
            self.device_error.emit("No device connected")
            logger.error("Operation attempted without device")
            return False

        if not self._device.is_connected():
            self.device_error.emit("Device not connected")
            logger.error("Operation attempted with disconnected device")
            return False

        return True

    # =========================================================================
    # Cancellation and Shutdown
    # =========================================================================

    def cancel(self) -> None:
        """
        Request cancellation of the operation.

        Sets the cancellation flag and initiates safe shutdown sequence.
        The motor will be turned off before the operation stops.
        """
        logger.info("%s: Cancellation requested", self.__class__.__name__)
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """
        Check if cancellation has been requested.

        Returns:
            True if cancel() has been called, False otherwise
        """
        return self._cancelled

    def safe_shutdown(self) -> None:
        """
        Perform motor-safe shutdown sequence.

        Ensures the motor is turned off before stopping operations.
        Waits briefly for motor to spin down.
        """
        logger.debug("%s: Performing safe shutdown", self.__class__.__name__)

        if self._device is not None and self._device.is_connected():
            try:
                if self._device.is_motor_on():
                    logger.debug("Turning motor off for safe shutdown")
                    self._device.motor_off()
                    # Wait for motor to spin down
                    time.sleep(MOTOR_SPINDOWN_DELAY)
            except Exception as e:
                logger.warning("Error during safe shutdown: %s", e)

    # =========================================================================
    # Error Handling and Recovery
    # =========================================================================

    def handle_device_error(self, error: Exception) -> bool:
        """
        Handle a device error and attempt recovery.

        Attempts to recover from device errors by resetting device state.
        If recovery fails, emits device_error signal.

        Args:
            error: The exception that occurred

        Returns:
            True if recovery was successful, False otherwise
        """
        logger.error(
            "%s: Device error occurred: %s",
            self.__class__.__name__, error
        )

        # Attempt recovery
        if self.attempt_recovery():
            logger.info("Device recovery successful")
            self.error.emit(f"Recovered from error: {error}")
            return True
        else:
            logger.error("Device recovery failed")
            self.device_error.emit(f"Unrecoverable device error: {error}")
            return False

    def attempt_recovery(self) -> bool:
        """
        Attempt to recover device to a known good state.

        Recovery sequence:
        1. Turn motor off
        2. Deselect drive
        3. Reconnect if necessary

        Returns:
            True if recovery successful, False otherwise
        """
        if self._device is None:
            return False

        logger.info("Attempting device recovery...")

        for attempt in range(MAX_RECOVERY_ATTEMPTS):
            try:
                # Step 1: Turn motor off if possible
                if self._device.is_connected():
                    try:
                        if self._device.motor_running:
                            self._device.motor_off()
                    except Exception as e:
                        logger.warning("Motor off failed: %s", e)

                    # Step 2: Deselect drive
                    try:
                        if self._device.selected_drive is not None:
                            self._device.deselect_drive()
                    except Exception as e:
                        logger.warning("Drive deselect failed: %s", e)

                # Wait before retry
                time.sleep(RECOVERY_DELAY)

                # Step 3: Try to reconnect if disconnected
                if not self._device.is_connected():
                    logger.info("Attempting to reconnect device...")
                    self._device.connect()

                # Verify connection
                if self._device.is_connected():
                    logger.info(
                        "Device recovery successful on attempt %d",
                        attempt + 1
                    )
                    return True

            except Exception as e:
                logger.warning(
                    "Recovery attempt %d failed: %s",
                    attempt + 1, e
                )
                time.sleep(RECOVERY_DELAY)

        logger.error("All recovery attempts failed")
        return False

    # =========================================================================
    # Running State
    # =========================================================================

    def is_running(self) -> bool:
        """
        Check if the worker is currently running.

        Returns:
            True if run() is executing, False otherwise
        """
        return self._running

    # =========================================================================
    # Abstract Method
    # =========================================================================

    def run(self) -> None:
        """
        Execute the worker's operation.

        Subclasses must override this method to implement their
        specific operation. The implementation should:
        1. Check for cancellation periodically
        2. Handle errors gracefully
        3. Update progress via progress signal
        4. Clean up device state on completion

        The execute() wrapper method handles setup and cleanup automatically.
        """
        raise NotImplementedError("Subclasses must implement run()")

    # =========================================================================
    # Execution Wrapper
    # =========================================================================

    def execute(self) -> None:
        """
        Execute the operation with proper setup and cleanup.

        This wrapper method handles:
        - Emitting started signal
        - Setting running state
        - Calling subclass run() method
        - Handling exceptions
        - Performing safe shutdown
        - Emitting finished signal

        Workers connected to QThread.started should use this method
        rather than run() directly for proper lifecycle management.
        """
        logger.info("%s: Starting execution", self.__class__.__name__)

        self._running = True
        self._cancelled = False
        self.started.emit()

        try:
            # Check device availability
            if not self._ensure_device():
                return

            # Record motor state
            self._motor_was_on = self._device.is_motor_on()

            # Execute the operation
            self.run()

        except InterruptedError:
            logger.info("%s: Operation interrupted", self.__class__.__name__)
            self.error.emit("Operation cancelled by user")

        except Exception as e:
            logger.exception("%s: Unexpected error", self.__class__.__name__)
            if not self.handle_device_error(e):
                self.device_error.emit(f"Operation failed: {e}")

        finally:
            # Ensure safe shutdown
            if self._cancelled:
                self.safe_shutdown()

            self._running = False
            logger.info("%s: Execution complete", self.__class__.__name__)
            self.finished.emit()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'BaseWorker',
    'GreaseweazleWorker',
    'MOTOR_SPINDOWN_DELAY',
    'MAX_RECOVERY_ATTEMPTS',
    'RECOVERY_DELAY',
]
