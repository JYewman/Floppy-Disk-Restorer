"""
Context managers for USB Floppy Formatter.

Provides safe resource management patterns for disk operations including
automatic file descriptor cleanup and resource management.
"""

import os
import logging

from floppy_formatter.core import (
    open_device,
    close_device,
    prevent_sleep,
    allow_sleep,
)


class DiskOperationContext:
    """
    Context manager for safe disk operations.

    Handles opening/closing block devices, resource management, and ensures
    proper cleanup even if exceptions occur.

    Attributes:
        device_path: Device path (e.g. /dev/sdb)
        read_only: Whether to open in read-only mode
        fd: Linux file descriptor (set during context)

    Example:
        >>> with DiskOperationContext("/dev/sdb", read_only=True) as fd:
        ...     scan_results = scan_all_sectors(fd, geometry)
        >>> # File descriptor automatically closed
    """

    def __init__(self, device_path: str, read_only: bool = False):
        """
        Initialize disk operation context.

        Args:
            device_path: Device path (e.g. /dev/sdb)
            read_only: Whether to open in read-only mode (default: False)
        """
        self.device_path = device_path
        self.read_only = read_only
        self.fd = None

    def __enter__(self):
        """
        Enter context - open device.

        Returns:
            Linux file descriptor

        Raises:
            IOError: If device cannot be opened
        """
        try:
            logging.debug(
                f"Opening {self.device_path} "
                f"(read_only={self.read_only})"
            )

            self.fd = open_device(self.device_path, self.read_only)
            prevent_sleep()

            logging.debug("Device opened successfully")
            return self.fd

        except Exception as e:
            logging.error(f"Failed to open device: {e}")
            # Clean up if partial initialization occurred
            if self.fd is not None:
                try:
                    close_device(self.fd)
                except:
                    pass
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context - flush, close file descriptor.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)

        Returns:
            False to not suppress exceptions
        """
        if self.fd is not None:
            try:
                # Flush pending writes to ensure data integrity
                if not self.read_only:
                    try:
                        os.fsync(self.fd)
                        logging.debug("File buffers flushed")
                    except Exception as flush_error:
                        logging.warning(f"Failed to flush buffers: {flush_error}")

            except Exception as e:
                logging.error(f"Error during cleanup: {e}")

            finally:
                # Always close file descriptor
                try:
                    close_device(self.fd)
                    logging.debug("Device closed")
                except Exception as close_error:
                    logging.error(f"Failed to close file descriptor: {close_error}")

                try:
                    allow_sleep()
                    logging.debug("Sleep prevention disabled")
                except Exception as sleep_error:
                    logging.warning(f"Failed to disable sleep prevention: {sleep_error}")

        # Don't suppress exceptions
        return False


class SafeOperationContext:
    """
    Generic context manager for operations that need cleanup.

    Provides a pattern for operations that require setup and teardown,
    with guaranteed cleanup even on exceptions.

    Attributes:
        setup_func: Function to call on entry
        cleanup_func: Function to call on exit
        name: Operation name for logging

    Example:
        >>> def setup():
        ...     print("Starting operation")
        ...     return "context_data"
        >>> def cleanup():
        ...     print("Cleaning up")
        >>> with SafeOperationContext(setup, cleanup, "my_op") as data:
        ...     perform_operation(data)
    """

    def __init__(self, setup_func, cleanup_func, name: str = "operation"):
        """
        Initialize safe operation context.

        Args:
            setup_func: Function to call on entry (should return context data)
            cleanup_func: Function to call on exit
            name: Operation name for logging
        """
        self.setup_func = setup_func
        self.cleanup_func = cleanup_func
        self.name = name
        self.context_data = None

    def __enter__(self):
        """
        Enter context - run setup function.

        Returns:
            Result of setup_func
        """
        try:
            logging.debug(f"Starting {self.name}")
            self.context_data = self.setup_func()
            return self.context_data
        except Exception as e:
            logging.error(f"Failed to start {self.name}: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context - run cleanup function.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)

        Returns:
            False to not suppress exceptions
        """
        try:
            logging.debug(f"Cleaning up {self.name}")
            self.cleanup_func()
        except Exception as e:
            logging.error(f"Cleanup failed for {self.name}: {e}")

        # Don't suppress exceptions
        return False
