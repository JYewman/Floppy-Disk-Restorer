"""
Drive control panel for Greaseweazle workbench.

This panel provides controls for:
- Greaseweazle connection management
- Drive selection (Drive 0 / Drive 1)
- Motor control with RPM display
- Head position display and manual seek controls
- Drive calibration

Part of Phase 5: Workbench GUI - Main Layout
"""

import logging
from typing import Optional
from enum import Enum, auto

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QSlider,
    QSpinBox,
    QGroupBox,
    QFrame,
    QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from floppy_formatter.hardware import GreaseweazleDevice
from floppy_formatter.hardware import (
    NoDeviceError,
    ConnectionError as GWConnectionError,
    MotorError,
    SeekError,
)

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Greaseweazle connection state."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


class LEDIndicator(QWidget):
    """
    LED-style status indicator widget.

    Displays a circular indicator that can be set to different colors
    to represent different states.
    """

    def __init__(self, size: int = 16, parent: Optional[QWidget] = None):
        """
        Initialize LED indicator.

        Args:
            size: Diameter of the LED in pixels
            parent: Parent widget
        """
        super().__init__(parent)

        self._size = size
        self._color = "#666666"  # Default gray (off)

        self.setFixedSize(size, size)
        self._update_style()

    def set_color(self, color: str) -> None:
        """
        Set the LED color.

        Args:
            color: CSS color string (e.g., "#00ff00", "green")
        """
        self._color = color
        self._update_style()

    def set_state(self, state: ConnectionState) -> None:
        """
        Set LED color based on connection state.

        Args:
            state: Connection state
        """
        colors = {
            ConnectionState.DISCONNECTED: "#cc3333",  # Red
            ConnectionState.CONNECTING: "#cccc33",    # Yellow
            ConnectionState.CONNECTED: "#33cc33",     # Green
            ConnectionState.ERROR: "#cc3333",         # Red
        }
        self.set_color(colors.get(state, "#666666"))

    def _update_style(self) -> None:
        """Update the widget stylesheet."""
        self.setStyleSheet(f"""
            LEDIndicator {{
                background-color: {self._color};
                border-radius: {self._size // 2}px;
                border: 1px solid #1e1e1e;
            }}
        """)


class DriveControlPanel(QWidget):
    """
    Drive control panel for the workbench GUI.

    Provides controls for Greaseweazle device connection, drive selection,
    motor control, head positioning, and calibration.

    Signals:
        connected: Emitted when device is connected
        disconnected: Emitted when device is disconnected
        motor_changed: Emitted when motor state changes (bool: is_on)
        position_changed: Emitted when head position changes (cyl, head)
        calibration_complete: Emitted when calibration finishes (success, message)
        error_occurred: Emitted when an error occurs (message)
    """

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    motor_changed = pyqtSignal(bool)
    position_changed = pyqtSignal(int, int)
    calibration_complete = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize drive control panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Device reference
        self._device: Optional[GreaseweazleDevice] = None

        # State tracking
        self._connection_state = ConnectionState.DISCONNECTED
        self._motor_on = False
        self._current_rpm = 0.0
        self._current_cylinder = 0
        self._current_head = 0

        # RPM update timer
        self._rpm_timer = QTimer(self)
        self._rpm_timer.timeout.connect(self._update_rpm_display)

        # Build UI
        self._setup_ui()

        # Initial state update
        self._update_control_states()

    def _setup_ui(self) -> None:
        """Set up the user interface - single horizontal row."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(6)

        # Connection: LED + Connect button + Drive combo
        self._connection_led = LEDIndicator(12)
        self._connection_led.set_state(ConnectionState.DISCONNECTED)
        main_layout.addWidget(self._connection_led)

        self._connect_button = QPushButton("Connect")
        self._connect_button.setFixedWidth(80)
        self._connect_button.clicked.connect(self._on_connect_clicked)
        main_layout.addWidget(self._connect_button)

        drive_label = QLabel("Drive:")
        drive_label.setStyleSheet("color: #cccccc;")
        main_layout.addWidget(drive_label)

        self._drive_combo = QComboBox()
        self._drive_combo.addItems(["0", "1"])
        self._drive_combo.setFixedWidth(50)
        self._drive_combo.currentIndexChanged.connect(self._on_drive_changed)
        main_layout.addWidget(self._drive_combo)

        # Separator
        main_layout.addWidget(self._create_separator())

        # Motor: Button + RPM display
        self._motor_button = QPushButton("Motor OFF")
        self._motor_button.setCheckable(True)
        self._motor_button.setFixedWidth(95)
        self._motor_button.clicked.connect(self._on_motor_clicked)
        main_layout.addWidget(self._motor_button)

        rpm_label = QLabel("RPM:")
        rpm_label.setStyleSheet("color: #cccccc;")
        main_layout.addWidget(rpm_label)

        self._rpm_value_label = QLabel("---")
        self._rpm_value_label.setStyleSheet("color: #33cc33; font-weight: bold;")
        self._rpm_value_label.setFixedWidth(40)
        main_layout.addWidget(self._rpm_value_label)

        # Separator
        main_layout.addWidget(self._create_separator())

        # Position: Label + Cylinder slider/spin + Head combo + buttons
        pos_label = QLabel("Cyl:")
        pos_label.setStyleSheet("color: #cccccc;")
        main_layout.addWidget(pos_label)

        self._cylinder_slider = QSlider(Qt.Orientation.Horizontal)
        self._cylinder_slider.setRange(0, 79)
        self._cylinder_slider.setValue(0)
        self._cylinder_slider.setFixedWidth(60)
        self._cylinder_slider.valueChanged.connect(self._on_cylinder_slider_changed)
        main_layout.addWidget(self._cylinder_slider)

        self._cylinder_spinbox = QSpinBox()
        self._cylinder_spinbox.setRange(0, 79)
        self._cylinder_spinbox.setValue(0)
        self._cylinder_spinbox.setFixedWidth(50)
        self._cylinder_spinbox.valueChanged.connect(self._on_cylinder_spinbox_changed)
        main_layout.addWidget(self._cylinder_spinbox)

        head_label = QLabel("Hd:")
        head_label.setStyleSheet("color: #cccccc;")
        main_layout.addWidget(head_label)

        self._head_combo = QComboBox()
        self._head_combo.addItems(["0", "1"])
        self._head_combo.setFixedWidth(55)
        main_layout.addWidget(self._head_combo)

        self._track0_button = QPushButton("T0")
        self._track0_button.setToolTip("Seek to Track 0")
        self._track0_button.setFixedWidth(40)
        self._track0_button.clicked.connect(self._on_track0_clicked)
        main_layout.addWidget(self._track0_button)

        self._seek_button = QPushButton("Go")
        self._seek_button.setToolTip("Seek to selected position")
        self._seek_button.setFixedWidth(40)
        self._seek_button.clicked.connect(self._on_seek_clicked)
        main_layout.addWidget(self._seek_button)

        # Separator
        main_layout.addWidget(self._create_separator())

        # Calibrate button + status
        self._calibrate_button = QPushButton("Calibrate")
        self._calibrate_button.setToolTip("Measure RPM and seek to track 0")
        self._calibrate_button.setFixedWidth(85)
        self._calibrate_button.clicked.connect(self._on_calibrate_clicked)
        main_layout.addWidget(self._calibrate_button)

        self._calibration_status = QLabel("Not calibrated")
        self._calibration_status.setStyleSheet("color: #858585;")
        main_layout.addWidget(self._calibration_status)

        # Position display (at end)
        main_layout.addStretch(1)

        self._position_label = QLabel("C:-- H:-")
        self._position_label.setStyleSheet("color: #33cc33; font-weight: bold;")
        main_layout.addWidget(self._position_label)

    def _create_separator(self) -> QFrame:
        """Create a vertical separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { color: #3a3d41; }")
        return separator

    def _update_control_states(self) -> None:
        """Update enabled/disabled states of controls based on connection."""
        is_connected = self._connection_state == ConnectionState.CONNECTED

        # Connection controls
        if is_connected:
            self._connect_button.setText("Disconnect")
            self._connect_button.setProperty("variant", "error")
        else:
            self._connect_button.setText("Connect")
            self._connect_button.setProperty("variant", "primary")

        # Style refresh for property changes
        self._connect_button.style().unpolish(self._connect_button)
        self._connect_button.style().polish(self._connect_button)

        # Drive selection
        self._drive_combo.setEnabled(is_connected)

        # Motor control
        self._motor_button.setEnabled(is_connected)
        if not is_connected:
            self._motor_button.setChecked(False)
            self._motor_button.setText("Motor OFF")
            self._rpm_value_label.setText("---")

        # Seek controls
        self._cylinder_slider.setEnabled(is_connected)
        self._cylinder_spinbox.setEnabled(is_connected)
        self._head_combo.setEnabled(is_connected)
        self._track0_button.setEnabled(is_connected)
        self._seek_button.setEnabled(is_connected)

        # Position display
        if not is_connected:
            self._position_label.setText("C:-- H:-")

        # Calibration
        self._calibrate_button.setEnabled(is_connected)
        if not is_connected:
            self._calibration_status.setText("Not calibrated")
            self._calibration_status.setStyleSheet("color: #858585;")

    def _on_connect_clicked(self) -> None:
        """Handle connect/disconnect button click."""
        if self._connection_state == ConnectionState.CONNECTED:
            self._disconnect_device()
        else:
            self._connect_device()

    def _connect_device(self) -> None:
        """Attempt to connect to Greaseweazle device."""
        self._connection_state = ConnectionState.CONNECTING
        self._connection_led.set_state(ConnectionState.CONNECTING)
        self._connect_button.setEnabled(False)
        self._connect_button.setText("Connecting...")

        try:
            # Create and connect device
            self._device = GreaseweazleDevice()
            self._device.connect()

            # Select default drive
            drive_unit = self._drive_combo.currentIndex()
            self._device.select_drive(drive_unit)

            # Update state
            self._connection_state = ConnectionState.CONNECTED
            self._connection_led.set_state(ConnectionState.CONNECTED)

            logger.info("Connected to Greaseweazle device")

            # Emit signal
            self.connected.emit()

        except NoDeviceError as e:
            logger.error("No device found: %s", e)
            self._connection_state = ConnectionState.DISCONNECTED
            self._connection_led.set_state(ConnectionState.DISCONNECTED)
            self._device = None
            self.error_occurred.emit("No Greaseweazle device found. Check USB connection.")
            QMessageBox.warning(
                self, "Connection Failed",
                "No Greaseweazle device found.\n\n"
                "Please check that the device is connected via USB."
            )

        except GWConnectionError as e:
            logger.error("Connection error: %s", e)
            self._connection_state = ConnectionState.ERROR
            self._connection_led.set_state(ConnectionState.ERROR)
            self._device = None
            self.error_occurred.emit(f"Connection failed: {e}")
            QMessageBox.warning(
                self, "Connection Failed",
                f"Failed to connect to Greaseweazle:\n\n{e}"
            )

        except Exception as e:
            logger.error("Unexpected error during connection: %s", e)
            self._connection_state = ConnectionState.ERROR
            self._connection_led.set_state(ConnectionState.ERROR)
            self._device = None
            self.error_occurred.emit(f"Unexpected error: {e}")
            QMessageBox.critical(
                self, "Connection Error",
                f"An unexpected error occurred:\n\n{e}"
            )

        finally:
            self._connect_button.setEnabled(True)
            self._update_control_states()

    def _disconnect_device(self) -> None:
        """Disconnect from Greaseweazle device."""
        if self._device is None:
            return

        try:
            # Stop motor if running
            if self._motor_on:
                self._device.motor_off()
                self._motor_on = False

            # Stop RPM timer
            self._rpm_timer.stop()

            # Deselect drive and disconnect
            self._device.deselect_drive()
            self._device.disconnect()

            logger.info("Disconnected from Greaseweazle device")

        except Exception as e:
            logger.warning("Error during disconnect: %s", e)

        finally:
            self._device = None
            self._connection_state = ConnectionState.DISCONNECTED
            self._connection_led.set_state(ConnectionState.DISCONNECTED)
            self._motor_on = False
            self._current_rpm = 0.0

            self._update_control_states()
            self.disconnected.emit()

    def _on_drive_changed(self, index: int) -> None:
        """Handle drive selection change."""
        if self._device is None or self._connection_state != ConnectionState.CONNECTED:
            return

        try:
            # Motor must be off to change drive
            if self._motor_on:
                self._device.motor_off()
                self._motor_on = False
                self._motor_button.setChecked(False)
                self._motor_button.setText("Motor OFF")
                self._rpm_timer.stop()

            self._device.select_drive(index)
            logger.info("Selected Drive %d", index)

        except Exception as e:
            logger.error("Failed to select drive: %s", e)
            self.error_occurred.emit(f"Failed to select drive: {e}")

    def _on_motor_clicked(self) -> None:
        """Handle motor toggle button click."""
        if self._device is None or self._connection_state != ConnectionState.CONNECTED:
            return

        try:
            if self._motor_button.isChecked():
                # Turn motor on
                self._device.motor_on()
                self._motor_on = True
                self._motor_button.setText("Motor ON")
                self._motor_button.setProperty("variant", "success")

                # Start RPM monitoring after spin-up delay (500ms for motor to reach speed)
                self._rpm_timer.start(500)  # Update every 500ms
                # Don't measure RPM immediately - wait for first timer tick
                # The motor needs ~500ms to spin up before index pulses are detectable

                logger.info("Motor turned ON")

            else:
                # Turn motor off
                self._device.motor_off()
                self._motor_on = False
                self._motor_button.setText("Motor OFF")
                self._motor_button.setProperty("variant", "")

                # Stop RPM monitoring
                self._rpm_timer.stop()
                self._rpm_value_label.setText("---")
                self._current_rpm = 0.0

                logger.info("Motor turned OFF")

            # Refresh button style
            self._motor_button.style().unpolish(self._motor_button)
            self._motor_button.style().polish(self._motor_button)

            self.motor_changed.emit(self._motor_on)

        except MotorError as e:
            logger.error("Motor error: %s", e)
            self._motor_button.setChecked(False)
            self._motor_on = False
            self.error_occurred.emit(f"Motor control error: {e}")

        except Exception as e:
            logger.error("Unexpected motor error: %s", e)
            self._motor_button.setChecked(False)
            self._motor_on = False
            self.error_occurred.emit(f"Motor error: {e}")

    def _update_rpm_display(self) -> None:
        """Update the RPM display with current measurement."""
        if self._device is None or not self._motor_on:
            return

        try:
            rpm = self._device.get_rpm()
            self._current_rpm = rpm

            if rpm > 0:
                self._rpm_value_label.setText(f"{rpm:.0f}")

                # Color code based on RPM (nominal 300 RPM)
                if 290 <= rpm <= 310:
                    self._rpm_value_label.setStyleSheet("color: #33cc33; font-weight: bold;")
                elif 280 <= rpm <= 320:
                    self._rpm_value_label.setStyleSheet("color: #cccc33; font-weight: bold;")
                else:
                    self._rpm_value_label.setStyleSheet("color: #cc3333; font-weight: bold;")

                # Update motor button text - keep it short
                self._motor_button.setText("Motor ON")
            else:
                self._rpm_value_label.setText("---")

        except Exception as e:
            logger.warning("Failed to get RPM: %s", e)

    def _on_cylinder_slider_changed(self, value: int) -> None:
        """Handle cylinder slider change."""
        self._cylinder_spinbox.blockSignals(True)
        self._cylinder_spinbox.setValue(value)
        self._cylinder_spinbox.blockSignals(False)

    def _on_cylinder_spinbox_changed(self, value: int) -> None:
        """Handle cylinder spinbox change."""
        self._cylinder_slider.blockSignals(True)
        self._cylinder_slider.setValue(value)
        self._cylinder_slider.blockSignals(False)

    def _on_track0_clicked(self) -> None:
        """Handle Track 0 button click."""
        self._cylinder_slider.setValue(0)
        self._cylinder_spinbox.setValue(0)
        self._head_combo.setCurrentIndex(0)
        self._perform_seek(0, 0)

    def _on_seek_clicked(self) -> None:
        """Handle Seek button click."""
        cylinder = self._cylinder_spinbox.value()
        head = self._head_combo.currentIndex()
        self._perform_seek(cylinder, head)

    def _perform_seek(self, cylinder: int, head: int) -> None:
        """
        Perform seek to specified position.

        Args:
            cylinder: Target cylinder (0-79)
            head: Target head (0-1)
        """
        if self._device is None or self._connection_state != ConnectionState.CONNECTED:
            return

        try:
            self._device.seek(cylinder, head)
            self._current_cylinder = cylinder
            self._current_head = head

            self._position_label.setText(f"C:{cylinder:02d} H:{head}")
            logger.info("Seek to cylinder %d, head %d", cylinder, head)

            self.position_changed.emit(cylinder, head)

        except SeekError as e:
            logger.error("Seek error: %s", e)
            self.error_occurred.emit(f"Seek failed: {e}")

        except Exception as e:
            logger.error("Unexpected seek error: %s", e)
            self.error_occurred.emit(f"Seek error: {e}")

    def _on_calibrate_clicked(self) -> None:
        """Handle Calibrate button click."""
        if self._device is None or self._connection_state != ConnectionState.CONNECTED:
            return

        self._calibrate_button.setEnabled(False)
        self._calibration_status.setText("Calibrating...")
        self._calibration_status.setStyleSheet("color: #cccc33;")

        try:
            # Ensure motor is on
            if not self._motor_on:
                self._device.motor_on()
                self._motor_on = True
                self._motor_button.setChecked(True)
                self._motor_button.setText("Motor ON")
                self._rpm_timer.start(500)

            # Wait for motor to spin up
            import time
            time.sleep(0.5)

            # Measure RPM
            rpm = self._device.get_rpm()
            self._current_rpm = rpm

            # Seek to track 0 for calibration
            self._device.seek(0, 0)
            self._current_cylinder = 0
            self._current_head = 0
            self._position_label.setText("C:00 H:0")

            # Update cylinder controls
            self._cylinder_slider.setValue(0)
            self._cylinder_spinbox.setValue(0)
            self._head_combo.setCurrentIndex(0)

            # Check RPM
            if 290 <= rpm <= 310:
                status = f"OK - {rpm:.0f} RPM"
                color = "#33cc33"
                success = True
                message = f"Calibration successful. RPM: {rpm:.0f}"
            elif 280 <= rpm <= 320:
                status = f"Warning - {rpm:.0f} RPM"
                color = "#cccc33"
                success = True
                message = f"Calibration complete with warnings. RPM: {rpm:.0f} (nominal: 300)"
            else:
                status = f"Error - {rpm:.0f} RPM"
                color = "#cc3333"
                success = False
                message = f"Calibration failed. RPM: {rpm:.0f} is outside acceptable range (280-320)"

            self._calibration_status.setText(status)
            self._calibration_status.setStyleSheet(f"color: {color};")

            logger.info("Calibration: %s", message)
            self.calibration_complete.emit(success, message)

        except Exception as e:
            logger.error("Calibration error: %s", e)
            self._calibration_status.setText("Error")
            self._calibration_status.setStyleSheet("color: #cc3333;")
            self.error_occurred.emit(f"Calibration failed: {e}")
            self.calibration_complete.emit(False, str(e))

        finally:
            self._calibrate_button.setEnabled(True)

    # =========================================================================
    # Public API
    # =========================================================================

    def get_device(self) -> Optional[GreaseweazleDevice]:
        """
        Get the connected Greaseweazle device.

        Returns:
            GreaseweazleDevice instance or None if not connected
        """
        return self._device

    def set_device(self, device: Optional[GreaseweazleDevice]) -> None:
        """
        Set an external device reference.

        Useful for sharing a device between components.

        Args:
            device: GreaseweazleDevice instance or None
        """
        if self._device is not None and self._device != device:
            self._disconnect_device()

        self._device = device

        if device is not None:
            self._connection_state = ConnectionState.CONNECTED
            self._connection_led.set_state(ConnectionState.CONNECTED)
        else:
            self._connection_state = ConnectionState.DISCONNECTED
            self._connection_led.set_state(ConnectionState.DISCONNECTED)

        self._update_control_states()

    def is_connected(self) -> bool:
        """
        Check if device is connected.

        Returns:
            True if connected to Greaseweazle
        """
        return self._connection_state == ConnectionState.CONNECTED

    def is_motor_on(self) -> bool:
        """
        Check if motor is running.

        Returns:
            True if motor is on
        """
        return self._motor_on

    def get_rpm(self) -> float:
        """
        Get current RPM reading.

        Returns:
            Current RPM or 0.0 if not available
        """
        return self._current_rpm

    def get_position(self) -> tuple:
        """
        Get current head position.

        Returns:
            Tuple of (cylinder, head)
        """
        return (self._current_cylinder, self._current_head)

    def get_device_info(self) -> Optional[str]:
        """
        Get device information string.

        Returns:
            Device info string or None if not connected
        """
        if self._device is None:
            return None

        try:
            return self._device.get_device_info()
        except Exception:
            return "Greaseweazle"

    def cleanup(self) -> None:
        """Clean up resources before destruction."""
        self._rpm_timer.stop()
        if self._device is not None:
            self._disconnect_device()
