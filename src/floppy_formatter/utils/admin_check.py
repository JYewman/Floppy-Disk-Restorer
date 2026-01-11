"""
Root privilege checking for Linux/WSL2.

This module provides functions to verify root privileges required for
raw device access on Linux systems.
"""

import os
from typing import Tuple, List


# =============================================================================
# Root Privilege Checking
# =============================================================================


def is_admin() -> bool:
    """
    Check if the current process is running with root privileges.

    This check is CRITICAL for the application because:
    - Opening /dev/sdX devices requires root privileges
    - O_RDWR | O_DIRECT access to block devices is restricted
    - Without root rights, all device operations will fail with EACCES

    Returns:
        True if running as root (UID 0), False otherwise

    Implementation Notes:
        Uses os.geteuid() to check effective user ID
        Returns False if UID != 0

    Example:
        >>> if not is_admin():
        ...     print("Please run as root (use sudo)")
        ...     sys.exit(1)
    """
    try:
        return os.geteuid() == 0
    except Exception:
        # If we can't determine, assume not root for safety
        return False


def get_current_user() -> str:
    """
    Get the name of the current user.

    Returns:
        Username string

    Example:
        >>> user = get_current_user()
        >>> print(f"Running as: {user}")
        Running as: root
    """
    try:
        import pwd
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        return "unknown"


# =============================================================================
# Permission Checking
# =============================================================================


def check_device_permissions(device_path: str) -> Tuple[bool, str]:
    """
    Check if the current user has permission to access a device.

    Args:
        device_path: Device path (e.g., '/dev/sde')

    Returns:
        Tuple of (has_permission: bool, message: str)
        - has_permission: True if device is accessible
        - message: Descriptive message about access status

    Example:
        >>> has_perm, msg = check_device_permissions('/dev/sde')
        >>> if not has_perm:
        ...     print(f"Access denied: {msg}")
    """
    if not os.path.exists(device_path):
        return (False, f"Device {device_path} does not exist")

    try:
        # Try to check if device is readable
        if os.access(device_path, os.R_OK):
            if os.access(device_path, os.W_OK):
                return (True, f"Read/write access to {device_path}")
            else:
                return (False, f"Read-only access to {device_path} (need write access)")
        else:
            return (False, f"No read access to {device_path}")
    except Exception as e:
        return (False, f"Error checking permissions: {e}")


# =============================================================================
# WSL Detection
# =============================================================================


def is_wsl() -> bool:
    """
    Detect if running under WSL (Linux subsystem on a different OS).

    Returns:
        True if running in WSL, False otherwise

    Example:
        >>> if is_wsl():
        ...     print("Running in WSL2 - USB passthrough required")
    """
    try:
        # Check for WSL in kernel version string
        with open('/proc/version', 'r') as f:
            version = f.read().lower()
            return 'microsoft' in version or 'wsl' in version
    except Exception:
        return False


def get_wsl_instructions() -> str:
    """
    Get instructions for setting up USB passthrough in WSL2.

    Returns:
        Multi-line string with step-by-step instructions

    Example:
        >>> if is_wsl():
        ...     print(get_wsl_instructions())
    """
    return """
WSL2 USB Floppy Setup Instructions:
====================================

USB floppy drives require USB passthrough using USBIPD-WIN.

1. Install USBIPD-WIN (on host side):
   - Open PowerShell as Administrator
   - Run: winget install --interactive --exact dorssel.usbipd-win

2. Attach USB floppy to WSL2 (each time you plug in the drive):
   - In PowerShell (Admin):
     * List USB devices: usbipd list
     * Find your USB floppy (look for "TEAC" or similar)
     * Note the BUSID (e.g., 2-2)
     * Bind the device: usbipd bind --busid 2-2
     * Attach to WSL: usbipd attach --wsl --busid 2-2

3. Verify in WSL2:
   - Run: lsblk
   - Look for 1.4M device (usually /dev/sde)

4. Run this tool with sudo:
   - sudo python -m floppy_formatter

For more information, see: WSL2_USB_SOLUTION.md
"""


# =============================================================================
# Permission Summary
# =============================================================================


def check_all_permissions() -> Tuple[bool, List[str]]:
    """
    Check all permissions required for the application to function.

    Performs comprehensive permission checking:
    - Root privileges
    - WSL2 environment detection

    Returns:
        Tuple of (all_ok: bool, issues: List[str])
        - all_ok: True if no issues detected
        - issues: List of human-readable issue descriptions

    Example:
        >>> all_ok, issues = check_all_permissions()
        >>> if not all_ok:
        ...     print("Permission issues detected:")
        ...     for issue in issues:
        ...         print(f"  - {issue}")
    """
    issues = []

    # Check root privileges
    if not is_admin():
        user = get_current_user()
        issues.append(
            f"Not running as root (current user: {user}). "
            f"Root privileges are required to access block devices. "
            f"Please run with: sudo python -m floppy_formatter"
        )

    # Check if running in WSL and provide helpful info
    if is_wsl():
        issues.append(
            "Running in WSL2. Make sure USB floppy is attached using USBIPD-WIN. "
            "See WSL2_USB_SOLUTION.md for details."
        )

    return (len(issues) == 0, issues)


def format_permission_errors(issues: List[str]) -> str:
    """
    Format permission issues into a user-friendly error message.

    Args:
        issues: List of permission issue descriptions from check_all_permissions()

    Returns:
        Formatted multi-line error message

    Example:
        >>> all_ok, issues = check_all_permissions()
        >>> if not all_ok:
        ...     print(format_permission_errors(issues))
    """
    if not issues:
        return "All permissions OK"

    lines = ["PERMISSION ISSUES DETECTED", "=" * 70, ""]
    lines.extend(issues)
    lines.append("")
    lines.append("=" * 70)
    lines.append("SOLUTIONS:")
    lines.append("")

    # Check if root issue exists
    if any("root" in issue.lower() for issue in issues):
        lines.append("For root privileges:")
        lines.append("  1. Run this application with sudo:")
        lines.append("     sudo python -m floppy_formatter")
        lines.append("")
        lines.append("  2. Or if using a script:")
        lines.append("     sudo ./your_script.py")
        lines.append("")

    # Check if WSL issue exists
    if any("WSL" in issue for issue in issues):
        lines.append("For WSL2 USB passthrough:")
        lines.append(get_wsl_instructions())

    return "\n".join(lines)


# =============================================================================
# Quick Checks
# =============================================================================


def require_root(exit_on_fail: bool = True) -> bool:
    """
    Require root privileges or exit/return False.

    Args:
        exit_on_fail: If True, exit the program if not root.
                     If False, return False if not root.

    Returns:
        True if running as root, False otherwise (if exit_on_fail=False)

    Example:
        >>> # Exit if not root
        >>> require_root()
        >>>
        >>> # Or check and handle manually
        >>> if not require_root(exit_on_fail=False):
        ...     print("Please run as root")
        ...     # Handle error
    """
    if is_admin():
        return True

    if exit_on_fail:
        import sys
        print("ERROR: Root privileges required", file=sys.stderr)
        print("Please run with: sudo python -m floppy_formatter", file=sys.stderr)
        sys.exit(1)
    else:
        return False
