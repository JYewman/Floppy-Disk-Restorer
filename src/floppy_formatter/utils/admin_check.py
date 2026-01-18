"""
Permission and environment checking for Floppy Workbench.

This module provides functions to verify permissions required for
Greaseweazle USB access on Linux and Windows systems.
"""

import os
from typing import Tuple, List


# =============================================================================
# Root Privilege Checking
# =============================================================================


def is_admin() -> bool:
    """
    Check if the current process has administrator/root privileges.

    Note: Greaseweazle uses libusb which typically doesn't require root
    on Linux if proper udev rules are installed, or on Windows. However,
    some operations may still benefit from elevated privileges.

    Returns:
        True if running as root/administrator, False otherwise

    Example:
        >>> if not is_admin():
        ...     print("Consider running with elevated privileges")
    """
    try:
        # Check for Unix-like systems
        if hasattr(os, 'geteuid'):
            return os.geteuid() == 0
        # Check for Windows
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    except Exception:
        return False


def get_current_user() -> str:
    """
    Get the name of the current user.

    Returns:
        Username string

    Example:
        >>> user = get_current_user()
        >>> print(f"Running as: {user}")
        Running as: joshua
    """
    try:
        import pwd
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        try:
            return os.getlogin()
        except Exception:
            return os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))


# =============================================================================
# Permission Checking
# =============================================================================


def check_greaseweazle_permissions() -> Tuple[bool, str]:
    """
    Check if the current user can access Greaseweazle devices.

    On Linux, Greaseweazle uses libusb which requires:
    - Being in the 'plugdev' group, OR
    - Having proper udev rules installed, OR
    - Running as root

    On Windows, Greaseweazle typically works without special permissions
    once the WinUSB driver is installed.

    Returns:
        Tuple of (has_permission: bool, message: str)
        - has_permission: True if Greaseweazle should be accessible
        - message: Descriptive message about access status

    Example:
        >>> has_perm, msg = check_greaseweazle_permissions()
        >>> if not has_perm:
        ...     print(f"Access may be limited: {msg}")
    """
    # Try to import greaseweazle and detect devices
    try:
        from greaseweazle import usb as gw_usb
        devices = gw_usb.find()
        if devices:
            return (True, f"Found {len(devices)} Greaseweazle device(s)")
        else:
            return (False, "No Greaseweazle devices found. Check USB connection.")
    except ImportError:
        return (False, "Greaseweazle library not installed. Run: pip install greaseweazle")
    except PermissionError:
        return (
            False,
            "Permission denied accessing Greaseweazle. Try sudo or check udev rules."
        )
    except Exception as e:
        return (False, f"Error detecting Greaseweazle: {e}")


# =============================================================================
# WSL Detection
# =============================================================================


def is_wsl() -> bool:
    """
    Detect if running under WSL (Windows Subsystem for Linux).

    Returns:
        True if running in WSL, False otherwise

    Example:
        >>> if is_wsl():
        ...     print("Running in WSL - USB passthrough required for Greaseweazle")
    """
    try:
        with open('/proc/version', 'r') as f:
            version = f.read().lower()
            return 'microsoft' in version or 'wsl' in version
    except Exception:
        return False


def get_wsl_instructions() -> str:
    """
    Get instructions for using Greaseweazle in WSL2.

    Returns:
        Multi-line string with step-by-step instructions

    Example:
        >>> if is_wsl():
        ...     print(get_wsl_instructions())
    """
    return """
WSL2 Greaseweazle Setup Instructions:
=====================================

Greaseweazle requires USB passthrough using USBIPD-WIN.

1. Install USBIPD-WIN (on Windows host):
   - Open PowerShell as Administrator
   - Run: winget install --interactive --exact dorssel.usbipd-win

2. Attach Greaseweazle to WSL2 (each time you plug in):
   - In PowerShell (Admin):
     * List USB devices: usbipd list
     * Find your Greaseweazle (look for "Greaseweazle" or USB VID:PID)
     * Note the BUSID (e.g., 2-2)
     * Bind the device: usbipd bind --busid 2-2
     * Attach to WSL: usbipd attach --wsl --busid 2-2

3. Verify in WSL2:
   - Run: lsusb
   - Look for Greaseweazle device

4. Run Floppy Workbench:
   - python -m floppy_formatter

Note: The greaseweazle library uses libusb, which should work
without root privileges once USB passthrough is established.
"""


# =============================================================================
# Permission Summary
# =============================================================================


def check_all_permissions() -> Tuple[bool, List[str]]:
    """
    Check all permissions required for Floppy Workbench to function.

    Performs comprehensive checking:
    - Greaseweazle accessibility
    - WSL2 environment detection

    Returns:
        Tuple of (all_ok: bool, issues: List[str])
        - all_ok: True if no critical issues detected
        - issues: List of human-readable issue descriptions

    Example:
        >>> all_ok, issues = check_all_permissions()
        >>> if not all_ok:
        ...     print("Issues detected:")
        ...     for issue in issues:
        ...         print(f"  - {issue}")
    """
    issues = []

    # Check Greaseweazle access
    gw_ok, gw_msg = check_greaseweazle_permissions()
    if not gw_ok:
        issues.append(gw_msg)

    # Provide WSL-specific info
    if is_wsl():
        issues.append(
            "Running in WSL2. Make sure Greaseweazle is attached using USBIPD-WIN. "
            "See get_wsl_instructions() for setup details."
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
        return "All permissions OK - Greaseweazle accessible"

    lines = ["PERMISSION/ACCESS ISSUES DETECTED", "=" * 70, ""]
    lines.extend(issues)
    lines.append("")
    lines.append("=" * 70)
    lines.append("SOLUTIONS:")
    lines.append("")

    # Check if Greaseweazle issue exists
    if any("greaseweazle" in issue.lower() or "permission" in issue.lower() for issue in issues):
        lines.append("For Greaseweazle access issues:")
        lines.append("  1. Check USB connection - is Greaseweazle plugged in?")
        lines.append("  2. On Linux, you may need to add yourself to the 'plugdev' group:")
        lines.append("     sudo usermod -a -G plugdev $USER")
        lines.append("     (then log out and back in)")
        lines.append("  3. Or run with sudo: sudo python -m floppy_formatter")
        lines.append("")

    # Check if WSL issue exists
    if any("WSL" in issue for issue in issues):
        lines.append("For WSL2 USB passthrough:")
        lines.append(get_wsl_instructions())

    return "\n".join(lines)


# =============================================================================
# Quick Checks
# =============================================================================


def require_greaseweazle(exit_on_fail: bool = True) -> bool:
    """
    Require Greaseweazle to be accessible or exit/return False.

    Args:
        exit_on_fail: If True, exit the program if Greaseweazle not found.
                     If False, return False if not accessible.

    Returns:
        True if Greaseweazle is accessible, False otherwise (if exit_on_fail=False)

    Example:
        >>> # Exit if Greaseweazle not found
        >>> require_greaseweazle()
        >>>
        >>> # Or check and handle manually
        >>> if not require_greaseweazle(exit_on_fail=False):
        ...     print("Please connect Greaseweazle")
    """
    has_perm, msg = check_greaseweazle_permissions()

    if has_perm:
        return True

    if exit_on_fail:
        import sys
        print(f"ERROR: {msg}", file=sys.stderr)
        print("Please connect Greaseweazle and try again.", file=sys.stderr)
        sys.exit(1)
    else:
        return False
