"""
Runtime compatibility checking utilities for USB Floppy Formatter on Linux/WSL2.

Provides functions to check system compatibility and hardware capabilities
at runtime for better error messages and graceful degradation.
"""

import sys
import platform
import os
import logging


def check_linux_kernel() -> tuple[bool, str]:
    """
    Check if running on compatible Linux kernel.

    Returns:
        Tuple of (compatible, version_string)

    Example:
        >>> compatible, version = check_linux_kernel()
        >>> if not compatible:
        ...     print(f"Unsupported kernel: {version}")
    """
    system = platform.system()
    if system != "Linux":
        return (False, f"{system} (Linux required)")

    kernel_version = platform.release()

    # Extract major.minor version
    try:
        parts = kernel_version.split('.')
        major = int(parts[0])
        minor = int(parts[1])

        # Require kernel 3.0+ (most modern distributions)
        if major >= 3:
            return (True, f"Linux {kernel_version}")
        else:
            return (False, f"Linux {kernel_version} (kernel 3.0+ required)")
    except:
        # If we can't parse, assume it's okay
        return (True, f"Linux {kernel_version}")


def check_python_version() -> tuple[bool, str]:
    """
    Check if running on compatible Python version.

    Returns:
        Tuple of (compatible, version_string)

    Example:
        >>> compatible, version = check_python_version()
        >>> if not compatible:
        ...     print(f"Unsupported Python: {version}")
    """
    version = sys.version_info
    version_string = f"{version.major}.{version.minor}.{version.micro}"

    if version.major >= 3 and version.minor >= 10:
        return (True, version_string)
    else:
        return (False, f"{version_string} (Python 3.10+ required)")


def check_root_access() -> tuple[bool, str]:
    """
    Check if running with root privileges.

    Returns:
        Tuple of (is_root, message)

    Example:
        >>> is_root, msg = check_root_access()
        >>> if not is_root:
        ...     print(f"Insufficient privileges: {msg}")
    """
    try:
        is_root = os.geteuid() == 0
        if is_root:
            return (True, "Running as root")
        else:
            import pwd
            username = pwd.getpwuid(os.getuid()).pw_name
            return (False, f"Running as {username} (root required)")
    except Exception as e:
        return (False, f"Unable to check privileges: {e}")


def check_wsl2() -> tuple[bool, str]:
    """
    Check if running under WSL2.

    Returns:
        Tuple of (is_wsl2, message)

    Example:
        >>> is_wsl, msg = check_wsl2()
        >>> if is_wsl:
        ...     print(f"WSL2 detected: {msg}")
    """
    try:
        with open('/proc/version', 'r') as f:
            version = f.read().lower()
            if 'microsoft' in version or 'wsl' in version:
                return (True, "WSL2 environment detected")
            else:
                return (False, "Native Linux")
    except Exception:
        return (False, "Unable to detect WSL2")


def check_usb_storage_support() -> tuple[bool, str]:
    """
    Check if USB storage support is available in kernel.

    Returns:
        Tuple of (supported, message)

    Example:
        >>> supported, msg = check_usb_storage_support()
        >>> if not supported:
        ...     print(f"USB storage issue: {msg}")
    """
    # Check if /sys/bus/usb exists (USB support)
    if not os.path.exists('/sys/bus/usb'):
        return (False, "USB subsystem not available")

    # Check if we can access /sys/block (block device enumeration)
    if not os.path.exists('/sys/block'):
        return (False, "/sys/block not accessible")

    # Try to check kernel config for USB_STORAGE
    config_paths = [
        '/proc/config.gz',
        '/boot/config-' + platform.release(),
    ]

    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                if config_path.endswith('.gz'):
                    import gzip
                    with gzip.open(config_path, 'rt') as f:
                        content = f.read()
                else:
                    with open(config_path, 'r') as f:
                        content = f.read()

                # Check for USB_STORAGE config
                if 'CONFIG_USB_STORAGE=y' in content or 'CONFIG_USB_STORAGE=m' in content:
                    return (True, "USB storage support enabled in kernel")
            except Exception:
                pass

    # If we can't check config, assume it's okay if /sys/bus/usb exists
    return (True, "USB storage support assumed available")


def check_device_access(device_path: str = None) -> tuple[bool, str]:
    """
    Check if we can access block devices.

    Args:
        device_path: Optional specific device to check (e.g., '/dev/sde')

    Returns:
        Tuple of (can_access, message)

    Example:
        >>> can_access, msg = check_device_access('/dev/sde')
        >>> if not can_access:
        ...     print(f"Device access issue: {msg}")
    """
    if device_path:
        # Check specific device
        if not os.path.exists(device_path):
            return (False, f"Device {device_path} does not exist")

        if not os.access(device_path, os.R_OK):
            return (False, f"No read access to {device_path}")

        if not os.access(device_path, os.W_OK):
            return (False, f"No write access to {device_path} (need root)")

        return (True, f"Full access to {device_path}")
    else:
        # Check general /dev access
        if not os.path.exists('/dev'):
            return (False, "/dev directory not accessible")

        # Try to list devices in /dev
        try:
            devices = os.listdir('/dev')
            sd_devices = [d for d in devices if d.startswith('sd')]
            if sd_devices:
                return (True, f"Block devices accessible ({len(sd_devices)} sd* devices found)")
            else:
                return (True, "Block devices accessible (no USB devices currently attached)")
        except Exception as e:
            return (False, f"Cannot access /dev: {e}")


def check_fcntl_available() -> tuple[bool, str]:
    """
    Check if fcntl module is available for ioctl operations.

    Returns:
        Tuple of (available, message)

    Example:
        >>> available, msg = check_fcntl_available()
        >>> if not available:
        ...     print(f"Missing dependency: {msg}")
    """
    try:
        import fcntl
        return (True, "fcntl module available")
    except ImportError as e:
        return (False, f"fcntl module not found: {e}")


def check_system_requirements() -> tuple[bool, list[str]]:
    """
    Check all system requirements.

    Returns:
        Tuple of (all_met, list_of_issues)

    Example:
        >>> all_ok, issues = check_system_requirements()
        >>> if not all_ok:
        ...     for issue in issues:
        ...         print(f"✗ {issue}")
    """
    issues = []

    # Check Linux kernel
    kernel_ok, kernel_ver = check_linux_kernel()
    if not kernel_ok:
        issues.append(f"Incompatible OS: {kernel_ver}")

    # Check Python version
    py_ok, py_ver = check_python_version()
    if not py_ok:
        issues.append(f"Incompatible Python: {py_ver}")

    # Check root access
    root_ok, root_msg = check_root_access()
    if not root_ok:
        issues.append(root_msg)

    # Check fcntl
    fcntl_ok, fcntl_msg = check_fcntl_available()
    if not fcntl_ok:
        issues.append(fcntl_msg)

    # Check USB storage support
    usb_ok, usb_msg = check_usb_storage_support()
    if not usb_ok:
        issues.append(usb_msg)

    # Check device access
    dev_ok, dev_msg = check_device_access()
    if not dev_ok:
        issues.append(dev_msg)

    # Check if WSL2 and provide info
    is_wsl, wsl_msg = check_wsl2()
    if is_wsl:
        # This is informational, not an error
        logging.info(wsl_msg)

    all_met = len(issues) == 0
    return (all_met, issues)


def get_system_info() -> dict:
    """
    Get comprehensive system information.

    Returns:
        Dictionary with system details

    Example:
        >>> info = get_system_info()
        >>> print(f"Running on {info['platform']} {info['release']}")
    """
    try:
        is_root = os.geteuid() == 0
    except:
        is_root = False

    try:
        import pwd
        username = pwd.getpwuid(os.getuid()).pw_name
    except:
        username = "unknown"

    is_wsl, wsl_msg = check_wsl2()

    return {
        'platform': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': sys.version,
        'python_executable': sys.executable,
        'is_root': is_root,
        'username': username,
        'is_wsl2': is_wsl,
        'wsl_message': wsl_msg if is_wsl else None,
    }


def print_system_report():
    """
    Print a comprehensive system compatibility report.

    Useful for troubleshooting and support.
    """
    print("=" * 70)
    print("USB Floppy Formatter - System Compatibility Report (Linux)")
    print("=" * 70)

    info = get_system_info()
    print(f"\nPlatform: {info['platform']} {info['release']}")
    print(f"Version: {info['version']}")
    print(f"Machine: {info['machine']}")
    print(f"Python: {info['python_version']}")
    print(f"User: {info['username']} (root: {info['is_root']})")

    if info['is_wsl2']:
        print(f"Environment: {info['wsl_message']}")

    print("\nRequirement Checks:")
    all_met, issues = check_system_requirements()

    if all_met:
        print("  ✓ All requirements met")
    else:
        for issue in issues:
            print(f"  ✗ {issue}")

    print("\nDependency Checks:")
    fcntl_ok, fcntl_msg = check_fcntl_available()
    if fcntl_ok:
        print(f"  ✓ {fcntl_msg}")
    else:
        print(f"  ✗ {fcntl_msg}")

    usb_ok, usb_msg = check_usb_storage_support()
    if usb_ok:
        print(f"  ✓ {usb_msg}")
    else:
        print(f"  ✗ {usb_msg}")

    print("\nDevice Access:")
    dev_ok, dev_msg = check_device_access()
    if dev_ok:
        print(f"  ✓ {dev_msg}")
    else:
        print(f"  ✗ {dev_msg}")

    print("\n" + "=" * 70)

    if all_met:
        print("System is compatible")
        if info['is_wsl2']:
            print("\nWSL2 Note: Make sure USB floppy is attached with USBIPD-WIN")
            print("See WSL2_USB_SOLUTION.md for setup instructions")
    else:
        print("System has compatibility issues")
        if not info['is_root']:
            print("\nRun with: sudo python -m floppy_formatter")

    print("=" * 70)


def check_format_capability(device_path: str) -> tuple[bool, bool, str]:
    """
    Check format capabilities (Linux always uses sector-level formatting).

    Args:
        device_path: Device path (e.g., '/dev/sde')

    Returns:
        Tuple of (supports_ex, supports_standard, message)

    Example:
        >>> ex, std, msg = check_format_capability('/dev/sde')
        >>> print(msg)
        Linux sector-level formatting (write + verify)
    """
    # On Linux, we always use sector-level formatting
    # No native track formatting ioctl available
    return (
        False,  # No "extended" format (no native track formatting)
        True,   # "Standard" = sector-level formatting
        "Linux sector-level formatting (write zeros + verify)"
    )
