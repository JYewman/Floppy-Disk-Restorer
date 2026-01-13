"""
Utility functions for Floppy Workbench.

This module provides administrative privilege checking, error handling,
logging, context managers, and other utility functions for the floppy
formatter application.
"""

from floppy_formatter.utils.admin_check import (
    is_admin,
    is_wsl,
)

from floppy_formatter.utils.error_handler import (
    handle_disk_error,
    detect_device_disconnection,
    is_fatal_error,
    is_retryable_error,
    get_error_severity,
)

from floppy_formatter.utils.logging import (
    setup_logging,
    log_system_info,
    log_operation,
    log_error,
    log_performance,
    log_recovery_progress,
    log_device_info,
)

from floppy_formatter.utils.context_managers import (
    DiskOperationContext,
    SafeOperationContext,
)

from floppy_formatter.utils.partial_results import (
    save_partial_results,
    load_partial_results,
    save_recovery_progress,
    RecoveryWorker,
)

__all__ = [
    # Admin utilities
    "is_admin",
    "is_wsl",

    # Error handling
    "handle_disk_error",
    "detect_device_disconnection",
    "is_fatal_error",
    "is_retryable_error",
    "get_error_severity",

    # Logging
    "setup_logging",
    "log_system_info",
    "log_operation",
    "log_error",
    "log_performance",
    "log_recovery_progress",
    "log_device_info",

    # Context managers
    "DiskOperationContext",
    "SafeOperationContext",

    # Partial results
    "save_partial_results",
    "load_partial_results",
    "save_recovery_progress",
    "RecoveryWorker",
]
