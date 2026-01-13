"""
Main entry point for Floppy Workbench.

This module provides the main() function that launches the PyQt6 GUI application.
"""

import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

from floppy_formatter.gui.dialogs.splash_screen import SplashScreen


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

    # Create application instance first (required for splash screen)
    app = QApplication(sys.argv)
    app.setApplicationName("Floppy Workbench")
    app.setApplicationVersion("0.2.0")
    app.setOrganizationName("Floppy Workbench")
    app.setOrganizationDomain("github.com/JYewman/Floppy-Disk-Restorer")

    # Set application icon
    icon_path = Path(__file__).parent / "gui" / "resources" / "icons" / "app_logo.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Create and show splash screen
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    # Initialize logging
    splash.set_status("Initializing logging...")
    splash.set_progress(10)
    app.processEvents()
    from floppy_formatter.utils import setup_logging
    setup_logging()

    # Check admin privileges
    splash.set_status("Checking privileges...")
    splash.set_progress(20)
    app.processEvents()
    is_admin = check_admin_privileges()
    view_only_mode = False

    if not is_admin:
        # Hide splash temporarily to show warning dialog
        splash.hide()
        should_continue = show_admin_warning_dialog(app)
        if not should_continue:
            sys.exit(0)
        view_only_mode = True
        splash.show()
        app.processEvents()

    # Loading modules
    splash.set_status("Loading GUI components...")
    splash.set_progress(40)
    app.processEvents()

    # Import MainWindow here (after splash is showing)
    from floppy_formatter.gui import MainWindow

    # Create main window
    splash.set_status("Creating main window...")
    splash.set_progress(60)
    app.processEvents()
    main_window = MainWindow()

    # Apply view-only mode if not running as admin
    if view_only_mode:
        main_window.set_view_only_mode(True)

    # Initialize hardware detection
    splash.set_status("Detecting hardware...")
    splash.set_progress(80)
    app.processEvents()

    # Finalize startup
    splash.set_status("Starting Floppy Workbench...")
    splash.set_progress(100)
    app.processEvents()

    # Use timer to ensure splash is visible for a moment before finishing
    def finish_splash():
        # finish() will fade out splash and show main_window when complete
        splash.finish(main_window)

        # If in view-only mode, show status message after window is visible
        if view_only_mode:
            # Wait for splash fade animation (500ms) plus a little extra
            QTimer.singleShot(700, lambda: QMessageBox.information(
                main_window,
                "View-Only Mode",
                "<h3>Running in View-Only Mode</h3>"
                "<p>Format and Restore operations are disabled.</p>"
                "<p>You can still scan disks and view reports.</p>",
            ))

    # Finish splash after brief delay to let user see 100% progress
    QTimer.singleShot(500, finish_splash)

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
