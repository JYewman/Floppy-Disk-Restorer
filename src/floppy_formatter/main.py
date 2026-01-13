"""
Main entry point for Floppy Workbench.

This module provides the main() function that launches the PyQt6 GUI application.
"""

import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from floppy_formatter.gui import MainWindow


def check_admin_privileges() -> bool:
    """
    Check if the application is running with administrative/root privileges.

    Returns:
        True if running as root/admin, False otherwise
    """
    try:
        # Unix/Linux check
        return os.geteuid() == 0
    except AttributeError:
        # Windows check (not supported for this application, but included for completeness)
        import ctypes
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False


def show_admin_warning_dialog(app: QApplication) -> bool:
    """
    Show warning dialog when not running as administrator.

    Args:
        app: QApplication instance

    Returns:
        True if user wants to continue in view-only mode, False if user wants to exit
    """
    msg_box = QMessageBox()
    msg_box.setWindowTitle("Administrator Privileges Required")
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setText(
        "<h3>Administrator Privileges Required</h3>"
        "<p>This application requires root/administrator privileges to access "
        "block devices and perform disk operations.</p>"
    )
    msg_box.setInformativeText(
        "Please run the application with sudo:\n\n"
        "<code>sudo python -m floppy_formatter</code>\n\n"
        "You can continue in <b>View-Only Mode</b>, but format and restore "
        "operations will be disabled."
    )

    # Add buttons
    view_only_button = msg_box.addButton("Continue (View-Only)", QMessageBox.ButtonRole.AcceptRole)
    exit_button = msg_box.addButton("Exit", QMessageBox.ButtonRole.RejectRole)
    msg_box.setDefaultButton(exit_button)

    # Show dialog
    msg_box.exec()

    # Check which button was clicked
    if msg_box.clickedButton() == view_only_button:
        return True  # Continue in view-only mode
    else:
        return False  # Exit application


def main():
    """
    Main entry point for Floppy Workbench.

    Launches the PyQt6 GUI application with admin privilege checking
    and drive detection.
    """
    # Configure High DPI scaling for better Windows support
    # Use Round for more predictable scaling on high DPI displays
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.Round
    )

    # Initialize logging for GUI run
    from floppy_formatter.utils import setup_logging
    setup_logging()

    # Create application instance
    app = QApplication(sys.argv)
    app.setApplicationName("Floppy Workbench")
    app.setApplicationVersion("0.2.0")
    app.setOrganizationName("Floppy Workbench")
    app.setOrganizationDomain("github.com/JYewman/USB-Floppy-Formatter")

    # Check admin privileges
    is_admin = check_admin_privileges()
    view_only_mode = False

    if not is_admin:
        # Show warning dialog
        should_continue = show_admin_warning_dialog(app)
        if not should_continue:
            sys.exit(0)
        view_only_mode = True

    # Create and show main window
    main_window = MainWindow()

    # Apply view-only mode if not running as admin
    if view_only_mode:
        main_window.set_view_only_mode(True)

    # Show window
    main_window.show()

    # If in view-only mode, show status message
    if view_only_mode:
        QMessageBox.information(
            main_window,
            "View-Only Mode",
            "<h3>Running in View-Only Mode</h3>"
            "<p>Format and Restore operations are disabled.</p>"
            "<p>You can still scan disks and view reports.</p>",
        )

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
