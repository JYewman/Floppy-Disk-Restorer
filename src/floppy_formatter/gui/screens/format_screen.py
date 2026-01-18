"""
Format screen for Floppy Workbench GUI.

Provides the disk formatting interface with real-time circular sector map
visualization, track-based progress tracking, and statistics display.
"""

from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QFrame,
    QSizePolicy,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QElapsedTimer
from PyQt6.QtGui import QFont

from floppy_formatter.gui.widgets.circular_sector_map import CircularSectorMap
from floppy_formatter.gui.workers.format_worker import FormatWorker, FormatResult
from floppy_formatter.gui.dialogs.confirm_cancel import show_confirm_cancel_dialog
from floppy_formatter.gui.dialogs.confirm_format import show_confirm_format_dialog
from floppy_formatter.core.geometry import DiskGeometry
from floppy_formatter.core.device_compat import open_device, close_device


class FormatWidget(QWidget):
    """
    Disk formatting screen with circular sector visualization.

    Displays a real-time visualization of the disk format progress using
    the CircularSectorMap widget, along with progress statistics and
    control buttons.

    The format operation shows track-based progress (160 tracks for a
    standard 1.44MB floppy: 80 cylinders × 2 heads).

    Signals:
        format_completed(object): Emitted when format finishes with FormatResult
        format_cancelled(): Emitted when user cancels the format
        view_report_requested(object): Emitted when user clicks "View Report"
        back_requested(): Emitted when user wants to go back

    Layout:
        ┌─────────────────────────┐
        │ Circular Sector Map     │
        │ (CircularSectorMap)     │
        ├─────────────────────────┤
        │ Progress: 58%           │
        │ Track 93/160            │
        │ Bad Sectors: 0          │
        │ Elapsed: 00:45          │
        │ [Cancel] [View Report]  │
        └─────────────────────────┘
    """

    # Signals
    format_completed = pyqtSignal(object)
    format_cancelled = pyqtSignal()
    view_report_requested = pyqtSignal(object)
    back_requested = pyqtSignal()

    # Constants
    SECTORS_PER_TRACK = 18

    def __init__(self, parent=None):
        """
        Initialize format widget.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)

        # Device info (set before showing widget)
        self._device_path: Optional[str] = None
        self._geometry: Optional[DiskGeometry] = None
        self._fd: Optional[int] = None

        # Worker and thread
        self._worker: Optional[FormatWorker] = None
        self._thread: Optional[QThread] = None

        # Format results
        self._format_result: Optional[FormatResult] = None
        self._bad_sector_list: List[int] = []

        # Time tracking
        self._elapsed_timer = QElapsedTimer()
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_elapsed_time)

        # State flags
        self._format_in_progress = False
        self._format_completed_flag = False
        self._confirmation_shown = False

        # Total tracks (set when geometry is provided)
        self._total_tracks = 160  # Default for 1.44MB floppy

        # Set up UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Title
        self.title_label = QLabel("Formatting Disk")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("color: #ffffff;")
        main_layout.addWidget(self.title_label)

        # Warning subtitle
        self.warning_label = QLabel("All data on the disk will be erased")
        self.warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_label.setStyleSheet("color: #f0a030; font-size: 11pt;")
        main_layout.addWidget(self.warning_label)

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
        self.progress_bar.setMaximum(160)
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
        self.progress_percent_label.setStyleSheet(
            "color: #4ec9b0; font-size: 12pt; font-weight: bold;"
        )
        self.progress_percent_label.setMinimumWidth(50)
        progress_layout.addWidget(self.progress_percent_label)

        stats_layout.addWidget(progress_container)

        # Track counter and statistics in a row
        info_container = QWidget()
        info_layout = QHBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(30)

        # Track counter
        track_widget = QWidget()
        track_layout = QHBoxLayout(track_widget)
        track_layout.setContentsMargins(0, 0, 0, 0)
        track_layout.setSpacing(5)

        track_icon = QLabel("Track:")
        track_icon.setStyleSheet("color: #858585; font-size: 11pt;")
        track_layout.addWidget(track_icon)

        self.track_label = QLabel("0 / 160")
        self.track_label.setStyleSheet("color: #ffffff; font-size: 11pt;")
        track_layout.addWidget(self.track_label)

        info_layout.addWidget(track_widget)

        # Bad sectors counter
        bad_widget = QWidget()
        bad_layout = QHBoxLayout(bad_widget)
        bad_layout.setContentsMargins(0, 0, 0, 0)
        bad_layout.setSpacing(5)

        bad_icon = QLabel("Bad Sectors:")
        bad_icon.setStyleSheet("color: #858585; font-size: 11pt;")
        bad_layout.addWidget(bad_icon)

        self.bad_label = QLabel("0")
        self.bad_label.setStyleSheet("color: #4ec9b0; font-size: 11pt; font-weight: bold;")
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
        self.view_report_button.hide()
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
        self.done_button.hide()
        button_layout.addWidget(self.done_button)

        button_layout.addStretch()

        main_layout.addWidget(button_container)

    def set_device(self, device_path: str, geometry: DiskGeometry) -> None:
        """
        Set the device to format.

        Args:
            device_path: Path to the device (e.g., '/dev/sde')
            geometry: Disk geometry information
        """
        self._device_path = device_path
        self._geometry = geometry
        self._total_tracks = geometry.cylinders * geometry.heads
        self._confirmation_shown = False
        self._format_completed_flag = False

    def start_format(self) -> None:
        """
        Start the disk format operation.

        Opens the device, creates the worker thread, and begins formatting.
        This should only be called after the user has confirmed the format.
        """
        if self._format_in_progress:
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
            # Open device for writing
            self._fd = open_device(self._device_path, read_only=False)
        except OSError as e:
            error_msg = str(e)
            if "read-only" in error_msg.lower() or "permission" in error_msg.lower():
                QMessageBox.critical(
                    self,
                    "Write Protected",
                    f"Cannot format disk - it may be write-protected:\n\n{error_msg}"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Device Error",
                    f"Failed to open device for writing:\n\n{error_msg}"
                )
            self.back_requested.emit()
            return

        # Create worker and thread
        self._thread = QThread()
        self._worker = FormatWorker(self._fd, self._geometry)
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.progress_updated.connect(self._on_progress_updated)
        self._worker.format_completed.connect(self._on_format_completed)
        self._worker.operation_failed.connect(self._on_format_failed)
        self._worker.finished.connect(self._on_worker_finished)

        # Start timing
        self._elapsed_timer.start()
        self._update_timer.start(1000)  # Update every second

        # Update UI
        self.title_label.setText("Formatting Disk...")
        self.warning_label.setText("Do not remove the disk during formatting")
        self.warning_label.setStyleSheet("color: #f14c4c; font-size: 11pt; font-weight: bold;")

        # Start format
        self._format_in_progress = True
        self._thread.start()

    def _reset_state(self) -> None:
        """Reset widget state for a new format."""
        self._format_result = None
        self._bad_sector_list = []
        self._format_completed_flag = False

        # Reset UI
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(self._total_tracks)
        self.progress_percent_label.setText("0%")
        self.track_label.setText(f"0 / {self._total_tracks}")
        self.bad_label.setText("0")
        self.bad_label.setStyleSheet("color: #4ec9b0; font-size: 11pt; font-weight: bold;")
        self.elapsed_label.setText("00:00")
        self.eta_label.setText("--:--")

        # Reset sector map
        self.sector_map.reset_all_sectors()

        # Reset progress bar color
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

        # Reset buttons
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.view_report_button.hide()
        self.done_button.hide()

        # Reset title
        self.title_label.setText("Formatting Disk")
        self.warning_label.setText("All data on the disk will be erased")
        self.warning_label.setStyleSheet("color: #f0a030; font-size: 11pt;")

    def _on_progress_updated(self, track_num: int, total_tracks: int) -> None:
        """
        Handle format progress update.

        Args:
            track_num: Current track number being formatted (0-based)
            total_tracks: Total number of tracks
        """
        # Update sector map - mark all sectors in this track as good (formatted)
        # Track to sector mapping: track * 18 to (track + 1) * 18 - 1
        start_sector = track_num * self.SECTORS_PER_TRACK
        end_sector = start_sector + self.SECTORS_PER_TRACK

        for sector in range(start_sector, end_sector):
            self.sector_map.update_sector(sector, True, animate=False)

        # Update progress bar (track_num is 0-based, but represents completed tracks)
        completed_tracks = track_num + 1
        self.progress_bar.setValue(completed_tracks)

        # Update percentage
        percent = (completed_tracks / total_tracks) * 100
        self.progress_percent_label.setText(f"{percent:.0f}%")

        # Update track counter
        self.track_label.setText(f"{completed_tracks} / {total_tracks}")

        # Update ETA
        self._update_eta(completed_tracks, total_tracks)

    def _on_format_completed(self, result: FormatResult) -> None:
        """
        Handle format completion.

        Args:
            result: The FormatResult from the format operation
        """
        self._format_result = result
        self._bad_sector_list = result.bad_sector_list
        self._format_completed_flag = True
        self._format_in_progress = False

        # Stop timer
        self._update_timer.stop()

        # Mark any bad sectors on the map
        for sector in result.bad_sector_list:
            self.sector_map.update_sector(sector, False, animate=True)

        # Update bad sector count
        if result.total_bad_sectors > 0:
            self.bad_label.setText(str(result.total_bad_sectors))
            self.bad_label.setStyleSheet("color: #f14c4c; font-size: 11pt; font-weight: bold;")
        else:
            self.bad_label.setText("0")
            self.bad_label.setStyleSheet("color: #4ec9b0; font-size: 11pt; font-weight: bold;")

        # Update UI for completion
        self._show_completion_ui(result)

        # Emit completion signal
        self.format_completed.emit(result)

    def _on_format_failed(self, error_message: str) -> None:
        """
        Handle format failure.

        Args:
            error_message: Description of the error
        """
        self._format_in_progress = False
        self._update_timer.stop()

        # Close device
        self._cleanup_device()

        # Determine error type and show appropriate message
        if "write-protected" in error_message.lower() or "read-only" in error_message.lower():
            QMessageBox.critical(
                self,
                "Write Protected",
                f"The disk appears to be write-protected:\n\n{error_message}\n\n"
                f"Please check the write-protect tab on the disk."
            )
        elif "track 0" in error_message.lower() or "first track" in error_message.lower():
            QMessageBox.critical(
                self,
                "Critical Error",
                f"Failed to format the first track:\n\n{error_message}\n\n"
                f"The disk may be unusable. Try a different disk."
            )
        else:
            QMessageBox.critical(
                self,
                "Format Failed",
                f"The disk format failed:\n\n{error_message}\n\n"
                f"The disk may be in an inconsistent state."
            )

        # Update UI
        self.title_label.setText("Format Failed")
        self.warning_label.setText("The format operation did not complete successfully")
        self.warning_label.setStyleSheet("color: #f14c4c; font-size: 11pt;")

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

    def _show_completion_ui(self, result: FormatResult) -> None:
        """
        Update UI to show format completion state.

        Args:
            result: The format result
        """
        # Update progress to 100%
        self.progress_bar.setValue(self._total_tracks)
        self.progress_percent_label.setText("100%")
        self.track_label.setText(f"{self._total_tracks} / {self._total_tracks}")

        # Clear ETA
        self.eta_label.setText("Complete")

        # Update title based on result
        if result.success and result.total_bad_sectors == 0:
            self.title_label.setText("Format Complete")
            self.warning_label.setText("Disk formatted successfully - no bad sectors found")
            self.warning_label.setStyleSheet("color: #4ec9b0; font-size: 11pt;")
        elif result.success:
            self.title_label.setText("Format Complete (with warnings)")
            self.warning_label.setText(
                f"Format completed with {result.total_bad_sectors} bad sector(s) detected"
            )
            self.warning_label.setStyleSheet("color: #f0a030; font-size: 11pt;")
        else:
            self.title_label.setText("Format Issues")
            self.warning_label.setText("Format completed with errors")
            self.warning_label.setStyleSheet("color: #f14c4c; font-size: 11pt;")

        # Show completion buttons
        self.cancel_button.hide()
        self.view_report_button.show()
        self.done_button.show()

        # Update progress bar color to green for success
        if result.success and result.total_bad_sectors == 0:
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
        elif result.total_bad_sectors > 0:
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
                    background-color: #f0a030;
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
            current: Current track number (1-based, completed)
            total: Total tracks
        """
        if current <= 0:
            self.eta_label.setText("--:--")
            return

        elapsed_ms = self._elapsed_timer.elapsed()
        if elapsed_ms < 1000:  # Need at least 1 second of data
            self.eta_label.setText("--:--")
            return

        # Calculate rate and remaining time
        tracks_per_ms = current / elapsed_ms
        remaining_tracks = total - current

        if tracks_per_ms > 0:
            remaining_ms = remaining_tracks / tracks_per_ms
            remaining_secs = int(remaining_ms / 1000)
            minutes = remaining_secs // 60
            seconds = remaining_secs % 60
            self.eta_label.setText(f"{minutes:02d}:{seconds:02d}")
        else:
            self.eta_label.setText("--:--")

    def _on_cancel_clicked(self) -> None:
        """Handle cancel button click."""
        if not self._format_in_progress:
            self.back_requested.emit()
            return

        # Show confirmation dialog
        if show_confirm_cancel_dialog(self, "format"):
            self._cancel_format()

    def _cancel_format(self) -> None:
        """Cancel the current format operation."""
        if self._worker is not None:
            self._worker.cancel()

        self._format_in_progress = False
        self._update_timer.stop()

        # Wait for thread to finish
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)  # Wait up to 3 seconds

        # Clean up
        self._cleanup_device()

        # Show warning about inconsistent state
        QMessageBox.warning(
            self,
            "Format Cancelled",
            "The format operation was cancelled.\n\n"
            "The disk may be in an inconsistent state and should not be used "
            "until it has been reformatted successfully."
        )

        # Emit cancellation signal
        self.format_cancelled.emit()

    def _on_view_report_clicked(self) -> None:
        """Handle View Report button click."""
        if self._format_result is not None:
            self.view_report_requested.emit(self._format_result)

    def _on_done_clicked(self) -> None:
        """Handle Done button click."""
        self.back_requested.emit()

    def get_format_result(self) -> Optional[FormatResult]:
        """
        Get the format result.

        Returns:
            FormatResult or None if format not completed
        """
        return self._format_result

    def get_statistics(self) -> dict:
        """
        Get format statistics.

        Returns:
            Dictionary with format statistics
        """
        elapsed_ms = self._elapsed_timer.elapsed() if self._elapsed_timer.isValid() else 0

        return {
            "total_tracks": self._total_tracks,
            "bad_sectors": len(self._bad_sector_list),
            "bad_sector_list": self._bad_sector_list,
            "elapsed_ms": elapsed_ms,
            "device_path": self._device_path,
            "success": self._format_result.success if self._format_result else False,
        }

    def is_format_in_progress(self) -> bool:
        """
        Check if a format is currently in progress.

        Returns:
            True if format is running
        """
        return self._format_in_progress

    def showEvent(self, event) -> None:
        """Handle widget show event."""
        super().showEvent(event)

        # Show confirmation dialog if not already shown and device is set
        can_show = (
            self._device_path and self._geometry and
            not self._format_in_progress and
            not self._format_completed_flag and
            not self._confirmation_shown
        )
        if can_show:

            self._confirmation_shown = True
            # Use QTimer to show dialog after widget is fully shown
            QTimer.singleShot(100, self._show_confirmation_and_start)

    def _show_confirmation_and_start(self) -> None:
        """Show confirmation dialog and start format if confirmed."""
        if show_confirm_format_dialog(self, self._device_path):
            self.start_format()
        else:
            # User cancelled - go back
            self.back_requested.emit()

    def closeEvent(self, event) -> None:
        """Handle widget close event."""
        # Cancel any running format
        if self._format_in_progress:
            self._cancel_format()

        # Clean up
        self._cleanup_device()

        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        """Handle widget hide event."""
        super().hideEvent(event)
