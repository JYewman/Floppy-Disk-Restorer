"""
Scan screen for Floppy Workbench GUI.

Provides the disk scanning interface with real-time circular sector map
visualization, progress tracking, and statistics display.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QFrame,
    QSpacerItem,
    QSizePolicy,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QElapsedTimer
from PyQt6.QtGui import QFont

from floppy_formatter.gui.widgets.circular_sector_map import CircularSectorMap
from floppy_formatter.gui.workers.scan_worker import ScanWorker
from floppy_formatter.gui.dialogs.confirm_cancel import show_confirm_cancel_dialog
from floppy_formatter.core.geometry import DiskGeometry
from floppy_formatter.core.device_compat import open_device, close_device


class ScanWidget(QWidget):
    """
    Disk scanning screen with circular sector visualization.

    Displays a real-time visualization of the disk scan progress using
    the CircularSectorMap widget, along with progress statistics and
    control buttons.

    Signals:
        scan_completed(object): Emitted when scan finishes with SectorMap result
        scan_cancelled(): Emitted when user cancels the scan
        view_report_requested(object): Emitted when user clicks "View Report"
        back_requested(): Emitted when user wants to go back

    Layout:
        ┌─────────────────────────┐
        │ Circular Sector Map     │
        │ (CircularSectorMap)     │
        ├─────────────────────────┤
        │ Progress: 58%           │
        │ Sector 1672/2880        │
        │ Good: 1650 | Bad: 22    │
        │ Elapsed: 00:45          │
        │ [Cancel] [View Report]  │
        └─────────────────────────┘
    """

    # Signals
    scan_completed = pyqtSignal(object)
    scan_cancelled = pyqtSignal()
    view_report_requested = pyqtSignal(object)
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        """
        Initialize scan widget.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)

        # Device info (set before showing widget)
        self._device_path: Optional[str] = None
        self._geometry: Optional[DiskGeometry] = None
        self._fd: Optional[int] = None

        # Worker and thread
        self._worker: Optional[ScanWorker] = None
        self._thread: Optional[QThread] = None

        # Scan results
        self._sector_map = None
        self._good_count = 0
        self._bad_count = 0

        # Time tracking
        self._elapsed_timer = QElapsedTimer()
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_elapsed_time)

        # State flags
        self._scan_in_progress = False
        self._scan_completed_flag = False

        # Set up UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Title
        title_label = QLabel("Scanning Disk")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #ffffff;")
        main_layout.addWidget(title_label)

        # Circular sector map (takes most space)
        self.sector_map = CircularSectorMap()
        self.sector_map.setMinimumSize(400, 400)
        self.sector_map.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        main_layout.addWidget(self.sector_map, stretch=1)

        # Statistics frame
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setSpacing(10)

        # Progress bar
        progress_container = QWidget()
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(10)

        progress_label = QLabel("Progress:")
        progress_label.setStyleSheet("color: #cccccc; font-size: 12pt;")
        progress_layout.addWidget(progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(2880)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setMinimumWidth(300)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #3c3c3c;
                border: none;
                border-radius: 4px;
                height: 20px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #0e639c;
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar, stretch=1)

        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setStyleSheet("color: #4ec9b0; font-size: 12pt; font-weight: bold;")
        self.progress_percent_label.setMinimumWidth(50)
        progress_layout.addWidget(self.progress_percent_label)

        stats_layout.addWidget(progress_container)

        # Sector counter and statistics in a row
        info_container = QWidget()
        info_layout = QHBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(30)

        # Sector counter
        sector_widget = QWidget()
        sector_layout = QHBoxLayout(sector_widget)
        sector_layout.setContentsMargins(0, 0, 0, 0)
        sector_layout.setSpacing(5)

        sector_icon = QLabel("Sector:")
        sector_icon.setStyleSheet("color: #858585; font-size: 11pt;")
        sector_layout.addWidget(sector_icon)

        self.sector_label = QLabel("0 / 2880")
        self.sector_label.setStyleSheet("color: #ffffff; font-size: 11pt;")
        sector_layout.addWidget(self.sector_label)

        info_layout.addWidget(sector_widget)

        # Good sectors
        good_widget = QWidget()
        good_layout = QHBoxLayout(good_widget)
        good_layout.setContentsMargins(0, 0, 0, 0)
        good_layout.setSpacing(5)

        good_icon = QLabel("Good:")
        good_icon.setStyleSheet("color: #858585; font-size: 11pt;")
        good_layout.addWidget(good_icon)

        self.good_label = QLabel("0")
        self.good_label.setStyleSheet("color: #4ec9b0; font-size: 11pt; font-weight: bold;")
        good_layout.addWidget(self.good_label)

        info_layout.addWidget(good_widget)

        # Bad sectors
        bad_widget = QWidget()
        bad_layout = QHBoxLayout(bad_widget)
        bad_layout.setContentsMargins(0, 0, 0, 0)
        bad_layout.setSpacing(5)

        bad_icon = QLabel("Bad:")
        bad_icon.setStyleSheet("color: #858585; font-size: 11pt;")
        bad_layout.addWidget(bad_icon)

        self.bad_label = QLabel("0")
        self.bad_label.setStyleSheet("color: #f14c4c; font-size: 11pt; font-weight: bold;")
        bad_layout.addWidget(self.bad_label)

        info_layout.addWidget(bad_widget)

        # Elapsed time
        time_widget = QWidget()
        time_layout = QHBoxLayout(time_widget)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(5)

        time_icon = QLabel("Elapsed:")
        time_icon.setStyleSheet("color: #858585; font-size: 11pt;")
        time_layout.addWidget(time_icon)

        self.elapsed_label = QLabel("00:00")
        self.elapsed_label.setStyleSheet("color: #ffffff; font-size: 11pt;")
        time_layout.addWidget(self.elapsed_label)

        info_layout.addWidget(time_widget)

        # ETA
        eta_widget = QWidget()
        eta_layout = QHBoxLayout(eta_widget)
        eta_layout.setContentsMargins(0, 0, 0, 0)
        eta_layout.setSpacing(5)

        eta_icon = QLabel("ETA:")
        eta_icon.setStyleSheet("color: #858585; font-size: 11pt;")
        eta_layout.addWidget(eta_icon)

        self.eta_label = QLabel("--:--")
        self.eta_label.setStyleSheet("color: #858585; font-size: 11pt;")
        eta_layout.addWidget(self.eta_label)

        info_layout.addWidget(eta_widget)

        info_layout.addStretch()
        stats_layout.addWidget(info_container)

        main_layout.addWidget(stats_frame)

        # Button container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(15)

        button_layout.addStretch()

        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumHeight(45)
        self.cancel_button.setMinimumWidth(120)
        self.cancel_button.setFont(QFont("", 12))
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #5a1d1d;
                color: #ffffff;
                border: 1px solid #8b3333;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #752525;
                border-color: #a04040;
            }
            QPushButton:pressed {
                background-color: #4a1515;
            }
            QPushButton:disabled {
                background-color: #2d2d30;
                color: #6c6c6c;
                border-color: #3c3c3c;
            }
        """)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(self.cancel_button)

        # View Report button (hidden initially)
        self.view_report_button = QPushButton("View Report")
        self.view_report_button.setMinimumHeight(45)
        self.view_report_button.setMinimumWidth(140)
        self.view_report_button.setFont(QFont("", 12))
        self.view_report_button.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
        """)
        self.view_report_button.clicked.connect(self._on_view_report_clicked)
        self.view_report_button.hide()  # Hidden until scan completes
        button_layout.addWidget(self.view_report_button)

        # Done button (hidden initially, shown on completion)
        self.done_button = QPushButton("Done")
        self.done_button.setMinimumHeight(45)
        self.done_button.setMinimumWidth(120)
        self.done_button.setFont(QFont("", 12))
        self.done_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3d41;
                color: #ffffff;
                border: 1px solid #6c6c6c;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #4e5157;
                border-color: #858585;
            }
            QPushButton:pressed {
                background-color: #2d2d30;
            }
        """)
        self.done_button.clicked.connect(self._on_done_clicked)
        self.done_button.hide()  # Hidden until scan completes
        button_layout.addWidget(self.done_button)

        button_layout.addStretch()

        main_layout.addWidget(button_container)

    def set_device(self, device_path: str, geometry: DiskGeometry) -> None:
        """
        Set the device to scan.

        Args:
            device_path: Path to the device (e.g., '/dev/sde')
            geometry: Disk geometry information
        """
        self._device_path = device_path
        self._geometry = geometry

    def start_scan(self) -> None:
        """
        Start the disk scan operation.

        Opens the device, creates the worker thread, and begins scanning.
        """
        if self._scan_in_progress:
            return

        if not self._device_path or not self._geometry:
            QMessageBox.critical(
                self,
                "Error",
                "No device selected. Please select a device first."
            )
            return

        # Reset state
        self._reset_state()

        try:
            # Open device
            self._fd = open_device(self._device_path, read_only=True)
        except OSError as e:
            QMessageBox.critical(
                self,
                "Device Error",
                f"Failed to open device:\n\n{str(e)}"
            )
            self.back_requested.emit()
            return

        # Create worker and thread
        self._thread = QThread()
        self._worker = ScanWorker(self._fd, self._geometry)
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.progress_updated.connect(self._on_progress_updated)
        self._worker.scan_completed.connect(self._on_scan_completed)
        self._worker.operation_failed.connect(self._on_scan_failed)
        self._worker.finished.connect(self._on_worker_finished)

        # Start timing
        self._elapsed_timer.start()
        self._update_timer.start(1000)  # Update every second

        # Start scan
        self._scan_in_progress = True
        self._thread.start()

    def _reset_state(self) -> None:
        """Reset widget state for a new scan."""
        self._sector_map = None
        self._good_count = 0
        self._bad_count = 0
        self._scan_completed_flag = False

        # Reset UI
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(self._geometry.total_sectors if self._geometry else 2880)
        self.progress_percent_label.setText("0%")
        self.sector_label.setText(f"0 / {self._geometry.total_sectors if self._geometry else 2880}")
        self.good_label.setText("0")
        self.bad_label.setText("0")
        self.elapsed_label.setText("00:00")
        self.eta_label.setText("--:--")

        # Reset sector map
        self.sector_map.reset_all_sectors()

        # Reset buttons
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.view_report_button.hide()
        self.done_button.hide()

    def _on_progress_updated(self, sector_num: int, total: int, is_good: bool, error_type: str) -> None:
        """
        Handle scan progress update.

        Args:
            sector_num: Current sector number being scanned
            total: Total number of sectors
            is_good: Whether the sector read successfully
            error_type: Error type string if sector failed
        """
        # Convert incoming sector_num (1-based from scanner) to 0-based index
        sector_index = sector_num - 1 if sector_num > 0 else 0

        # Update sector map (0-based index)
        self.sector_map.update_sector(sector_index, is_good, animate=False)

        # Update counters
        if is_good:
            self._good_count += 1
        else:
            self._bad_count += 1

        # Update progress bar
        self.progress_bar.setValue(sector_index + 1)

        # Update percentage
        percent = ((sector_index + 1) / total) * 100 if total > 0 else 0
        self.progress_percent_label.setText(f"{percent:.0f}%")

        # Update sector counter
        self.sector_label.setText(f"{sector_index + 1} / {total}")

        # Update good/bad counts
        self.good_label.setText(str(self._good_count))
        self.bad_label.setText(str(self._bad_count))

        # Update ETA
        self._update_eta(sector_index + 1, total)

    def _on_scan_completed(self, sector_map) -> None:
        """
        Handle scan completion.

        Args:
            sector_map: The SectorMap result from the scan
        """
        self._sector_map = sector_map
        self._scan_completed_flag = True
        self._scan_in_progress = False

        # Stop timer
        self._update_timer.stop()

        # Update UI for completion
        self._show_completion_ui()

        # Emit completion signal
        self.scan_completed.emit(sector_map)

    def _on_scan_failed(self, error_message: str) -> None:
        """
        Handle scan failure.

        Args:
            error_message: Description of the error
        """
        self._scan_in_progress = False
        self._update_timer.stop()

        # Close device
        self._cleanup_device()

        # Show error dialog
        QMessageBox.critical(
            self,
            "Scan Failed",
            f"The disk scan failed:\n\n{error_message}"
        )

        # Show done button to allow navigation
        self.cancel_button.hide()
        self.done_button.show()
        self.done_button.setText("Back")

    def _on_worker_finished(self) -> None:
        """Handle worker thread completion."""
        # Clean up thread
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)  # Wait up to 5 seconds
            self._thread.deleteLater()
            self._thread = None

        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

        # Close device
        self._cleanup_device()

    def _cleanup_device(self) -> None:
        """Close the device if open."""
        if self._fd is not None:
            try:
                close_device(self._fd)
            except Exception:
                pass
            self._fd = None

    def _show_completion_ui(self) -> None:
        """Update UI to show scan completion state."""
        # Update progress to 100%
        total = self._geometry.total_sectors if self._geometry else 2880
        self.progress_bar.setValue(total)
        self.progress_percent_label.setText("100%")
        self.sector_label.setText(f"{total} / {total}")

        # Clear ETA
        self.eta_label.setText("Complete")

        # Show completion buttons
        self.cancel_button.hide()
        self.view_report_button.show()
        self.done_button.show()

        # Update progress bar color to green for completion
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #3c3c3c;
                border: none;
                border-radius: 4px;
                height: 20px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #107c10;
                border-radius: 4px;
            }
        """)

    def _update_elapsed_time(self) -> None:
        """Update the elapsed time display."""
        elapsed_ms = self._elapsed_timer.elapsed()
        elapsed_secs = elapsed_ms // 1000
        minutes = elapsed_secs // 60
        seconds = elapsed_secs % 60
        self.elapsed_label.setText(f"{minutes:02d}:{seconds:02d}")

    def _update_eta(self, current: int, total: int) -> None:
        """
        Update the estimated time remaining.

        Args:
            current: Current sector number (1-based)
            total: Total sectors
        """
        if current <= 0:
            self.eta_label.setText("--:--")
            return

        elapsed_ms = self._elapsed_timer.elapsed()
        if elapsed_ms < 1000:  # Need at least 1 second of data
            self.eta_label.setText("--:--")
            return

        # Calculate rate and remaining time
        sectors_per_ms = current / elapsed_ms
        remaining_sectors = total - current

        if sectors_per_ms > 0:
            remaining_ms = remaining_sectors / sectors_per_ms
            remaining_secs = int(remaining_ms / 1000)
            minutes = remaining_secs // 60
            seconds = remaining_secs % 60
            self.eta_label.setText(f"{minutes:02d}:{seconds:02d}")
        else:
            self.eta_label.setText("--:--")

    def _on_cancel_clicked(self) -> None:
        """Handle cancel button click."""
        if not self._scan_in_progress:
            self.back_requested.emit()
            return

        # Show confirmation dialog
        if show_confirm_cancel_dialog(self, "scan"):
            self._cancel_scan()

    def _cancel_scan(self) -> None:
        """Cancel the current scan operation."""
        if self._worker is not None:
            self._worker.cancel()

        self._scan_in_progress = False
        self._update_timer.stop()

        # Wait for thread to finish
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)  # Wait up to 3 seconds

        # Clean up
        self._cleanup_device()

        # Emit cancellation signal
        self.scan_cancelled.emit()

    def _on_view_report_clicked(self) -> None:
        """Handle View Report button click."""
        if self._sector_map is not None:
            self.view_report_requested.emit(self._sector_map)

    def _on_done_clicked(self) -> None:
        """Handle Done button click."""
        self.back_requested.emit()

    def get_scan_result(self):
        """
        Get the scan result.

        Returns:
            SectorMap result or None if scan not completed
        """
        return self._sector_map

    def get_statistics(self) -> dict:
        """
        Get scan statistics.

        Returns:
            Dictionary with good_count, bad_count, total, elapsed_time
        """
        elapsed_ms = self._elapsed_timer.elapsed() if self._elapsed_timer.isValid() else 0
        total = self._geometry.total_sectors if self._geometry else 2880

        return {
            "good_count": self._good_count,
            "bad_count": self._bad_count,
            "total": total,
            "elapsed_ms": elapsed_ms,
            "device_path": self._device_path,
        }

    def is_scan_in_progress(self) -> bool:
        """
        Check if a scan is currently in progress.

        Returns:
            True if scan is running
        """
        return self._scan_in_progress

    def showEvent(self, event) -> None:
        """Handle widget show event."""
        super().showEvent(event)
        # Auto-start scan when widget becomes visible if device is set
        if self._device_path and self._geometry and not self._scan_in_progress and not self._scan_completed_flag:
            QTimer.singleShot(100, self.start_scan)

    def closeEvent(self, event) -> None:
        """Handle widget close event."""
        # Cancel any running scan
        if self._scan_in_progress:
            self._cancel_scan()

        # Clean up
        self._cleanup_device()

        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        """Handle widget hide event."""
        # If hiding while scan in progress, we need to handle it
        # Don't automatically cancel - let the scan continue
        super().hideEvent(event)
