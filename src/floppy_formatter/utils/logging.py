"""
Logging configuration for USB Floppy Formatter.

Provides structured logging with system information capture for debugging
and troubleshooting.
"""

import logging
import sys
import platform
from pathlib import Path


def setup_logging(log_file: str = "floppy_formatter.log", level: int = logging.DEBUG) -> None:
    """
    Configure structured logging for the application.

    Sets up file-based logging with DEBUG level and captures system information
    on startup for troubleshooting purposes.

    Args:
        log_file: Path to log file (default: "floppy_formatter.log")
        level: Logging level (default: logging.DEBUG)

    Example:
        >>> setup_logging()
        >>> logging.info("Application started")
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        filename=log_file,
        level=level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Also log to console for development
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logging.getLogger().addHandler(console_handler)

    # Log system information on startup
    log_system_info()


def log_system_info() -> None:
    """
    Log system information for debugging purposes.

    Captures Linux kernel version, Python version, and root status
    to aid in troubleshooting platform-specific issues.
    """
    try:
        from floppy_formatter.utils.admin_check import is_admin

        logging.info("=" * 60)
        logging.info("USB Floppy Formatter - System Information")
        logging.info("=" * 60)
        logging.info(f"Platform: {platform.system()} {platform.release()}")
        logging.info(f"Platform version: {platform.version()}")
        logging.info(f"Machine: {platform.machine()}")
        logging.info(f"Python version: {sys.version}")
        logging.info(f"Python executable: {sys.executable}")
        logging.info(f"Running as admin: {is_admin()}")
        logging.info("=" * 60)

    except Exception as e:
        logging.error(f"Failed to log system info: {e}")


def log_operation(operation: str, details: str, level: int = logging.INFO) -> None:
    """
    Log a disk operation with details.

    Provides a standardized way to log operations throughout the application.

    Args:
        operation: Name of the operation (e.g., "scan_sector", "format_track")
        details: Additional details about the operation
        level: Logging level (default: logging.INFO)

    Example:
        >>> log_operation("scan_sector", "sector 100: CRC error")
        >>> log_operation("format_track", "C0:H0 complete", logging.DEBUG)
    """
    logging.log(level, f"{operation}: {details}")


def log_error(operation: str, error_code: int, error_message: str) -> None:
    """
    Log an error with operation context.

    Args:
        operation: Name of the operation that failed
        error_code: Linux errno code
        error_message: Error message or description

    Example:
        >>> log_error("read_sector", ERROR_CRC, "CRC error on sector 100")
    """
    logging.error(f"{operation} failed - Error {error_code}: {error_message}")


def log_performance(operation: str, duration: float, **metrics) -> None:
    """
    Log performance metrics for an operation.

    Args:
        operation: Name of the operation
        duration: Duration in seconds
        **metrics: Additional performance metrics (e.g., sectors_per_second)

    Example:
        >>> log_performance("scan_disk", 120.5, sectors=2880, sectors_per_second=23.9)
    """
    metrics_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
    logging.info(f"Performance - {operation}: {duration:.2f}s, {metrics_str}")


def log_recovery_progress(pass_num: int, bad_sectors: int, delta: int = None) -> None:
    """
    Log recovery progress with convergence tracking.

    Args:
        pass_num: Current pass number
        bad_sectors: Current bad sector count
        delta: Change from previous pass (optional)

    Example:
        >>> log_recovery_progress(0, 147)
        >>> log_recovery_progress(1, 89, delta=-58)
    """
    if delta is not None:
        delta_str = f" ({delta:+d})"
    else:
        delta_str = ""

    logging.info(f"Recovery Pass {pass_num + 1}: {bad_sectors} bad sectors{delta_str}")


def log_device_info(device_path: str, geometry, device_type: str = "Unknown") -> None:
    """
    Log device information.

    Args:
        device_path: Device path (e.g., '/dev/sde')
        geometry: DiskGeometry object
        device_type: Type of device (e.g., "USB Floppy", "Internal Floppy")

    Example:
        >>> log_device_info('/dev/sde', geometry, "USB Floppy")
    """
    logging.info(f"Device: {device_path} ({device_type})")
    logging.info(
        f"Geometry: {geometry.cylinders}C/{geometry.heads}H/"
        f"{geometry.sectors_per_track}S ({geometry.bytes_per_sector} bytes/sector)"
    )
    total_sectors = geometry.cylinders * geometry.heads * geometry.sectors_per_track
    total_kb = total_sectors * geometry.bytes_per_sector // 1024
    logging.info(f"Capacity: {total_sectors} sectors ({total_kb} KB)")
