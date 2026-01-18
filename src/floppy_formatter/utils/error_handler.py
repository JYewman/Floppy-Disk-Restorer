"""
Error handling utilities for Floppy Workbench on Linux/WSL2.

Provides comprehensive Linux error code handling with context-aware
messages and device disconnection detection.
"""

import errno
from floppy_formatter.core.sector_adapter import (
    ERROR_SUCCESS,
    ERROR_PERMISSION_DENIED,
    ERROR_NOT_READY,
    ERROR_WRITE_PROTECT,
    ERROR_CRC,
    ERROR_SECTOR_NOT_FOUND,
)


def handle_disk_error(error_code: int, operation: str = "disk operation") -> str:
    """
    Centralized error handling with context-aware messages.

    Provides detailed, actionable error messages for common Linux error codes
    encountered during disk operations.

    Args:
        error_code: Linux errno value (e.g., errno.EACCES)
        operation: Description of the operation that failed

    Returns:
        Formatted error message with troubleshooting guidance

    Example:
        >>> error_msg = handle_disk_error(errno.EACCES, "read sector")
        >>> print(error_msg)
        read sector failed: Permission denied. Check:
        1. Running as root (use sudo)?
        2. Device permissions correct?
    """
    error_messages = {
        ERROR_PERMISSION_DENIED: (  # EACCES = 13
            "Permission denied. Check:\n"
            "1. Running as root (use sudo)?\n"
            "2. Device permissions correct?\n"
            "3. SELinux/AppArmor blocking access?"
        ),
        ERROR_NOT_READY: "No disk inserted or device not ready (ENODEV)",  # ENODEV = 19
        ERROR_WRITE_PROTECT: "Disk is write-protected (EROFS)",  # EROFS = 30
        ERROR_CRC: "I/O error - disk may have bad sectors (EIO)",  # EIO = 5
        ERROR_SECTOR_NOT_FOUND: "Sector not found - severe disk damage (ENXIO)",  # ENXIO = 6
        errno.ENOENT: "Device does not exist - check device path",  # ENOENT = 2
        errno.EBUSY: "Device is busy - already in use by another process",  # EBUSY = 16
        errno.EINVAL: "Invalid argument - check sector alignment",  # EINVAL = 22
    }

    code_name = errno.errorcode.get(error_code, 'UNKNOWN')
    message = error_messages.get(error_code, f"Unknown error {error_code}: {code_name}")
    return f"{operation} failed: {message}"


def detect_device_disconnection(fd: int) -> tuple[bool, str | None]:
    """
    Check if device is still connected.

    Performs a simple geometry read to verify the device is still accessible.
    Useful during long-running operations to detect if the user has removed
    the USB drive.

    Args:
        fd: File descriptor to the block device

    Returns:
        Tuple of (connected, error_message)
        - connected: True if device is connected, False otherwise
        - error_message: Error description if disconnected, None if connected

    Example:
        >>> connected, error = detect_device_disconnection(fd)
        >>> if not connected:
        ...     print(f"Device lost: {error}")
        ...     break
    """
    try:
        # Try a simple lseek to sector 0 to verify connection
        import os
        pos = os.lseek(fd, 0, os.SEEK_SET)
        if pos == 0:
            return (True, None)
        else:
            return (False, "Device position error")
    except OSError as e:
        if e.errno == ERROR_NOT_READY or e.errno == errno.ENOENT:
            return (False, "Device disconnected during operation")
        return (False, f"Device connection lost: {e}")
    except Exception as e:
        return (False, f"Device connection lost: {str(e)}")


def is_fatal_error(error_code: int) -> bool:
    """
    Determine if an error is fatal and operation should be aborted.

    Fatal errors are those that indicate the operation cannot continue,
    such as device disconnection or access denial. Non-fatal errors like
    I/O errors may allow the operation to continue with degraded results.

    Args:
        error_code: Linux errno value

    Returns:
        True if error is fatal, False otherwise

    Example:
        >>> if is_fatal_error(error_code):
        ...     abort_operation()
        ... else:
        ...     continue_with_degraded_mode()
    """
    fatal_errors = {
        ERROR_PERMISSION_DENIED,  # EACCES
        ERROR_NOT_READY,          # ENODEV
        ERROR_WRITE_PROTECT,      # EROFS
        errno.ENOENT,             # Device doesn't exist
        errno.EBUSY,              # Device busy
    }
    return error_code in fatal_errors


def is_retryable_error(error_code: int) -> bool:
    """
    Determine if an error is retryable.

    Retryable errors are those that may succeed on subsequent attempts,
    such as I/O errors or sector not found errors. These are typically
    caused by transient disk issues.

    Args:
        error_code: Linux errno value

    Returns:
        True if error is retryable, False otherwise

    Example:
        >>> if is_retryable_error(error_code):
        ...     for attempt in range(max_retries):
        ...         if retry_operation():
        ...             break
    """
    retryable_errors = {
        ERROR_CRC,  # EIO - I/O error
        ERROR_SECTOR_NOT_FOUND,  # ENXIO - Sector not found
    }
    return error_code in retryable_errors


def get_error_severity(error_code: int) -> str:
    """
    Get the severity level of an error.

    Classifies errors into severity levels for logging and UI display.

    Args:
        error_code: Linux errno value

    Returns:
        Severity level: "critical", "error", "warning", or "info"

    Example:
        >>> severity = get_error_severity(errno.EIO)
        >>> logger.log(severity.upper(), f"Error: {error_code}")
    """
    if error_code == ERROR_SUCCESS:
        return "info"

    if is_fatal_error(error_code):
        return "critical"

    if is_retryable_error(error_code):
        return "warning"

    return "error"
