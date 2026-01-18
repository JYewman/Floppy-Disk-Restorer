"""
Settings dialog for Floppy Workbench.

Provides comprehensive settings management with a tabbed interface for:
- Device settings (drive unit, motor, seek speed)
- Display settings (theme, color scheme, animations)
- Recovery settings (modes, passes, PLL tuning)
- Export settings (formats, directories, naming)

Part of Phase 13: Settings & Persistence
"""

import logging
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QTabWidget,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QFrame,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QSlider,
    QLineEdit,
    QFileDialog,
    QFormLayout,
    QMessageBox,
    QToolButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from floppy_formatter.core.settings import (
    Settings,
    SeekSpeed,
    ColorScheme,
    RecoveryLevel,
    ExportFormat,
    ReportFormat,
    Theme,
    COLOR_SCHEMES,
    get_settings,
)


# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Device Settings Tab
# =============================================================================

class DeviceSettingsTab(QWidget):
    """Tab for device-related settings."""

    def __init__(self, settings: Settings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Set up the device settings UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Drive Configuration Group
        drive_group = QGroupBox("Drive Configuration")
        drive_layout = QFormLayout(drive_group)
        drive_layout.setContentsMargins(8, 12, 8, 8)
        drive_layout.setSpacing(6)

        # Default drive unit
        self.drive_unit_combo = QComboBox()
        self.drive_unit_combo.addItems(["Drive 0 (A:)", "Drive 1 (B:)"])
        self.drive_unit_combo.setToolTip("Default drive unit to select on connection")
        drive_layout.addRow("Default Drive:", self.drive_unit_combo)

        # Double step mode
        self.double_step_check = QCheckBox("Enable double-step mode")
        self.double_step_check.setToolTip(
            "Enable for 40-track drives in 80-track machines"
        )
        drive_layout.addRow("", self.double_step_check)

        # Auto-detect geometry
        self.auto_detect_check = QCheckBox("Auto-detect disk geometry")
        self.auto_detect_check.setToolTip(
            "Automatically detect disk type and geometry on insertion"
        )
        drive_layout.addRow("", self.auto_detect_check)

        layout.addWidget(drive_group)

        # Motor Control Group
        motor_group = QGroupBox("Motor Control")
        motor_layout = QFormLayout(motor_group)
        motor_layout.setContentsMargins(8, 12, 8, 8)
        motor_layout.setSpacing(6)

        # Motor timeout
        motor_timeout_layout = QHBoxLayout()
        self.motor_timeout_spin = QSpinBox()
        self.motor_timeout_spin.setRange(5, 300)
        self.motor_timeout_spin.setSuffix(" seconds")
        self.motor_timeout_spin.setToolTip(
            "Time to keep motor running after operation completes"
        )
        motor_timeout_layout.addWidget(self.motor_timeout_spin)
        motor_timeout_layout.addStretch()
        motor_layout.addRow("Motor Timeout:", motor_timeout_layout)

        # Default RPM
        rpm_layout = QHBoxLayout()
        self.default_rpm_spin = QSpinBox()
        self.default_rpm_spin.setRange(250, 400)
        self.default_rpm_spin.setSuffix(" RPM")
        self.default_rpm_spin.setToolTip(
            "Expected motor RPM (300 for 3.5\" HD, 360 for 5.25\")"
        )
        rpm_layout.addWidget(self.default_rpm_spin)
        rpm_layout.addStretch()
        motor_layout.addRow("Expected RPM:", rpm_layout)

        layout.addWidget(motor_group)

        # Seek Settings Group
        seek_group = QGroupBox("Seek Settings")
        seek_layout = QFormLayout(seek_group)
        seek_layout.setContentsMargins(8, 12, 8, 8)
        seek_layout.setSpacing(6)

        # Seek speed
        self.seek_speed_combo = QComboBox()
        self.seek_speed_combo.addItems([
            "Slow (Conservative)",
            "Normal",
            "Fast (Aggressive)",
        ])
        self.seek_speed_combo.setToolTip(
            "Seek speed - slower is gentler on old drives"
        )
        seek_layout.addRow("Seek Speed:", self.seek_speed_combo)

        # Verify seeks
        self.verify_seeks_check = QCheckBox("Verify seek operations")
        self.verify_seeks_check.setToolTip(
            "Read track ID after seek to verify head position"
        )
        seek_layout.addRow("", self.verify_seeks_check)

        layout.addWidget(seek_group)

        # Spacer
        layout.addStretch()

    def _load_settings(self) -> None:
        """Load current settings into controls."""
        device = self.settings.device

        self.drive_unit_combo.setCurrentIndex(device.default_drive_unit)
        self.double_step_check.setChecked(device.double_step)
        self.auto_detect_check.setChecked(device.auto_detect_geometry)
        self.motor_timeout_spin.setValue(device.motor_timeout)
        self.default_rpm_spin.setValue(device.default_rpm)

        # Seek speed
        seek_speed = device.get_seek_speed()
        speed_index = {
            SeekSpeed.SLOW: 0,
            SeekSpeed.NORMAL: 1,
            SeekSpeed.FAST: 2,
        }.get(seek_speed, 1)
        self.seek_speed_combo.setCurrentIndex(speed_index)

        self.verify_seeks_check.setChecked(device.verify_seeks)

    def save_settings(self) -> None:
        """Save control values to settings."""
        device = self.settings.device

        device.default_drive_unit = self.drive_unit_combo.currentIndex()
        device.double_step = self.double_step_check.isChecked()
        device.auto_detect_geometry = self.auto_detect_check.isChecked()
        device.motor_timeout = self.motor_timeout_spin.value()
        device.default_rpm = self.default_rpm_spin.value()

        seek_speeds = [SeekSpeed.SLOW, SeekSpeed.NORMAL, SeekSpeed.FAST]
        device.seek_speed = seek_speeds[self.seek_speed_combo.currentIndex()].value

        device.verify_seeks = self.verify_seeks_check.isChecked()


# =============================================================================
# Display Settings Tab
# =============================================================================

class DisplaySettingsTab(QWidget):
    """Tab for display and UI settings."""

    theme_preview_requested = pyqtSignal(str)

    def __init__(self, settings: Settings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Set up the display settings UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Theme Group
        theme_group = QGroupBox("Theme")
        theme_layout = QVBoxLayout(theme_group)
        theme_layout.setContentsMargins(8, 12, 8, 8)
        theme_layout.setSpacing(6)

        # Theme selection
        theme_button_layout = QHBoxLayout()
        self._theme_group = QButtonGroup(self)

        self.dark_radio = QRadioButton("Dark")
        self.dark_radio.setToolTip("Dark theme with light text on dark background")
        self._theme_group.addButton(self.dark_radio, 0)
        theme_button_layout.addWidget(self.dark_radio)

        self.light_radio = QRadioButton("Light")
        self.light_radio.setToolTip("Light theme with dark text on light background")
        self._theme_group.addButton(self.light_radio, 1)
        theme_button_layout.addWidget(self.light_radio)

        self.system_radio = QRadioButton("System")
        self.system_radio.setToolTip("Follow system theme preference")
        self._theme_group.addButton(self.system_radio, 2)
        theme_button_layout.addWidget(self.system_radio)

        theme_button_layout.addStretch()
        theme_layout.addLayout(theme_button_layout)

        # Connect for live preview
        self._theme_group.buttonClicked.connect(self._on_theme_changed)

        layout.addWidget(theme_group)

        # Color Scheme Group (for accessibility)
        color_group = QGroupBox("Sector Map Colors")
        color_layout = QFormLayout(color_group)
        color_layout.setContentsMargins(8, 12, 8, 8)
        color_layout.setSpacing(6)

        # Color scheme dropdown
        self.color_scheme_combo = QComboBox()
        self.color_scheme_combo.addItems([
            "Standard",
            "Deuteranopia (Red-Green Colorblind)",
            "Protanopia (Red Colorblind)",
            "Tritanopia (Blue-Yellow Colorblind)",
            "High Contrast",
            "Monochrome",
        ])
        self.color_scheme_combo.setToolTip(
            "Color scheme for sector map visualization - select for accessibility needs"
        )
        self.color_scheme_combo.currentIndexChanged.connect(self._on_color_scheme_changed)
        color_layout.addRow("Color Scheme:", self.color_scheme_combo)

        # Color preview
        self.color_preview = ColorSchemePreview()
        color_layout.addRow("Preview:", self.color_preview)

        layout.addWidget(color_group)

        # Visual Effects Group
        effects_group = QGroupBox("Visual Effects")
        effects_layout = QFormLayout(effects_group)
        effects_layout.setContentsMargins(8, 12, 8, 8)
        effects_layout.setSpacing(4)

        self.animate_check = QCheckBox("Animate sector map during operations")
        self.animate_check.setToolTip(
            "Show real-time animation while scanning/formatting"
        )
        effects_layout.addRow("", self.animate_check)

        self.tooltips_check = QCheckBox("Show tooltips")
        self.tooltips_check.setToolTip("Display helpful tooltips on hover")
        effects_layout.addRow("", self.tooltips_check)

        self.track_labels_check = QCheckBox("Show track labels on sector map")
        self.track_labels_check.setToolTip(
            "Display track numbers on the circular sector map"
        )
        effects_layout.addRow("", self.track_labels_check)

        self.show_waveform_check = QCheckBox("Show flux waveform by default")
        self.show_waveform_check.setToolTip(
            "Display flux waveform panel when reading tracks"
        )
        effects_layout.addRow("", self.show_waveform_check)

        layout.addWidget(effects_group)

        # Sizes Group
        sizes_group = QGroupBox("Sizes")
        sizes_layout = QFormLayout(sizes_group)
        sizes_layout.setContentsMargins(8, 12, 8, 8)
        sizes_layout.setSpacing(6)

        # Sector map size
        map_size_layout = QHBoxLayout()
        self.sector_map_size_spin = QSpinBox()
        self.sector_map_size_spin.setRange(200, 800)
        self.sector_map_size_spin.setSuffix(" px")
        self.sector_map_size_spin.setToolTip("Default size of the circular sector map")
        map_size_layout.addWidget(self.sector_map_size_spin)
        map_size_layout.addStretch()
        sizes_layout.addRow("Sector Map Size:", map_size_layout)

        # Font size
        font_size_layout = QHBoxLayout()
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 16)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setToolTip("Base font size for the UI")
        font_size_layout.addWidget(self.font_size_spin)
        font_size_layout.addStretch()
        sizes_layout.addRow("Font Size:", font_size_layout)

        # Default analytics tab
        analytics_layout = QHBoxLayout()
        self.default_tab_combo = QComboBox()
        self.default_tab_combo.addItems([
            "Overview",
            "Flux",
            "Errors",
            "Recovery",
            "Diagnostics",
        ])
        self.default_tab_combo.setToolTip("Default tab in the analytics panel")
        analytics_layout.addWidget(self.default_tab_combo)
        analytics_layout.addStretch()
        sizes_layout.addRow("Default Analytics Tab:", analytics_layout)

        layout.addWidget(sizes_group)

        # Spacer
        layout.addStretch()

    def _load_settings(self) -> None:
        """Load current settings into controls."""
        display = self.settings.display

        # Theme
        theme = display.get_theme()
        if theme == Theme.DARK:
            self.dark_radio.setChecked(True)
        elif theme == Theme.LIGHT:
            self.light_radio.setChecked(True)
        else:
            self.system_radio.setChecked(True)

        # Color scheme
        scheme = display.get_color_scheme()
        scheme_index = {
            ColorScheme.STANDARD: 0,
            ColorScheme.DEUTERANOPIA: 1,
            ColorScheme.PROTANOPIA: 2,
            ColorScheme.TRITANOPIA: 3,
            ColorScheme.HIGH_CONTRAST: 4,
            ColorScheme.MONOCHROME: 5,
        }.get(scheme, 0)
        self.color_scheme_combo.setCurrentIndex(scheme_index)
        self._update_color_preview(scheme_index)

        # Effects
        self.animate_check.setChecked(display.animate_operations)
        self.tooltips_check.setChecked(display.show_tooltips)
        self.track_labels_check.setChecked(display.show_track_labels)
        self.show_waveform_check.setChecked(display.show_flux_waveform)

        # Sizes
        self.sector_map_size_spin.setValue(display.sector_map_size)
        self.font_size_spin.setValue(display.font_size)
        self.default_tab_combo.setCurrentIndex(display.default_analytics_tab)

    def _on_theme_changed(self) -> None:
        """Handle theme radio button change."""
        if self.dark_radio.isChecked():
            theme = "dark"
        elif self.light_radio.isChecked():
            theme = "light"
        else:
            theme = "system"
        self.theme_preview_requested.emit(theme)

    def _on_color_scheme_changed(self, index: int) -> None:
        """Handle color scheme combo change."""
        self._update_color_preview(index)

    def _update_color_preview(self, index: int) -> None:
        """Update the color preview widget."""
        schemes = list(ColorScheme)
        if 0 <= index < len(schemes):
            scheme = schemes[index]
            colors = COLOR_SCHEMES.get(scheme)
            if colors:
                self.color_preview.set_colors(colors)

    def save_settings(self) -> None:
        """Save control values to settings."""
        display = self.settings.display

        # Theme
        if self.dark_radio.isChecked():
            display.theme = Theme.DARK.value
        elif self.light_radio.isChecked():
            display.theme = Theme.LIGHT.value
        else:
            display.theme = Theme.SYSTEM.value

        # Color scheme
        schemes = [
            ColorScheme.STANDARD,
            ColorScheme.DEUTERANOPIA,
            ColorScheme.PROTANOPIA,
            ColorScheme.TRITANOPIA,
            ColorScheme.HIGH_CONTRAST,
            ColorScheme.MONOCHROME,
        ]
        display.color_scheme = schemes[self.color_scheme_combo.currentIndex()].value

        # Effects
        display.animate_operations = self.animate_check.isChecked()
        display.show_tooltips = self.tooltips_check.isChecked()
        display.show_track_labels = self.track_labels_check.isChecked()
        display.show_flux_waveform = self.show_waveform_check.isChecked()

        # Sizes
        display.sector_map_size = self.sector_map_size_spin.value()
        display.font_size = self.font_size_spin.value()
        display.default_analytics_tab = self.default_tab_combo.currentIndex()

    def get_current_theme(self) -> str:
        """Get the currently selected theme."""
        if self.dark_radio.isChecked():
            return "dark"
        elif self.light_radio.isChecked():
            return "light"
        return "system"


class ColorSchemePreview(QWidget):
    """Widget showing a preview of sector map colors."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setMinimumWidth(200)
        self._colors = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the preview UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self._color_labels = []
        color_names = ["Good", "Bad", "Weak", "Unknown", "Reading", "Writing"]

        for name in color_names:
            frame = QFrame()
            frame.setFixedSize(28, 18)
            frame.setFrameShape(QFrame.Shape.Box)
            frame.setToolTip(name)
            self._color_labels.append(frame)
            layout.addWidget(frame)

        layout.addStretch()

    def set_colors(self, colors) -> None:
        """Set the colors to preview."""
        self._colors = colors
        if colors:
            color_values = [
                colors.good,
                colors.bad,
                colors.weak,
                colors.unknown,
                colors.reading,
                colors.writing,
            ]
            for label, color in zip(self._color_labels, color_values):
                label.setStyleSheet(f"""
                    QFrame {{
                        background-color: {color};
                        border: 1px solid #666666;
                        border-radius: 2px;
                    }}
                """)


# =============================================================================
# Recovery Settings Tab
# =============================================================================

class RecoverySettingsTab(QWidget):
    """Tab for recovery operation settings."""

    def __init__(self, settings: Settings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Set up the recovery settings UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Recovery Mode Group
        mode_group = QGroupBox("Default Recovery Mode")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setContentsMargins(8, 12, 8, 8)
        mode_layout.setSpacing(4)

        # Recovery level
        level_layout = QHBoxLayout()
        level_label = QLabel("Recovery Level:")
        self.recovery_level_combo = QComboBox()
        self.recovery_level_combo.addItems([
            "Standard - Basic multi-pass recovery",
            "Aggressive - Multi-capture + PLL tuning",
            "Forensic - All techniques, maximum effort",
        ])
        self.recovery_level_combo.setToolTip(
            "Default recovery aggressiveness level"
        )
        self.recovery_level_combo.currentIndexChanged.connect(
            self._on_recovery_level_changed
        )
        level_layout.addWidget(level_label)
        level_layout.addWidget(self.recovery_level_combo, 1)
        mode_layout.addLayout(level_layout)

        # Convergence mode
        self.convergence_check = QCheckBox(
            "Use convergence mode (stop when no improvement)"
        )
        self.convergence_check.setToolTip(
            "Continue passes until bad sector count stabilizes"
        )
        self.convergence_check.stateChanged.connect(self._on_convergence_changed)
        mode_layout.addWidget(self.convergence_check)

        # Preserve good sectors
        self.preserve_good_check = QCheckBox(
            "Preserve good sectors (targeted recovery only)"
        )
        self.preserve_good_check.setToolTip(
            "Don't overwrite sectors that are already readable"
        )
        mode_layout.addWidget(self.preserve_good_check)

        layout.addWidget(mode_group)

        # Pass Settings Group
        pass_group = QGroupBox("Pass Settings")
        pass_layout = QFormLayout(pass_group)
        pass_layout.setContentsMargins(8, 12, 8, 8)
        pass_layout.setSpacing(6)

        # Default fixed passes
        passes_layout = QHBoxLayout()
        self.default_passes_spin = QSpinBox()
        self.default_passes_spin.setRange(1, 100)
        self.default_passes_spin.setToolTip(
            "Default number of passes for fixed-pass mode"
        )
        passes_layout.addWidget(self.default_passes_spin)
        passes_layout.addStretch()
        pass_layout.addRow("Default Passes:", passes_layout)

        # Max passes for convergence
        max_passes_layout = QHBoxLayout()
        self.max_passes_spin = QSpinBox()
        self.max_passes_spin.setRange(5, 200)
        self.max_passes_spin.setToolTip(
            "Maximum passes to run in convergence mode before stopping"
        )
        max_passes_layout.addWidget(self.max_passes_spin)
        max_passes_layout.addStretch()
        pass_layout.addRow("Max Passes (Convergence):", max_passes_layout)

        layout.addWidget(pass_group)

        # Multi-Read Settings Group
        multiread_group = QGroupBox("Multi-Read Statistical Recovery")
        multiread_layout = QFormLayout(multiread_group)
        multiread_layout.setContentsMargins(8, 12, 8, 8)
        multiread_layout.setSpacing(6)

        # Enable multi-read
        self.multiread_check = QCheckBox("Enable multi-read by default")
        self.multiread_check.setToolTip(
            "Read sectors multiple times and use statistical analysis to recover data"
        )
        self.multiread_check.stateChanged.connect(self._on_multiread_changed)
        multiread_layout.addRow("", self.multiread_check)

        # Capture count
        captures_layout = QHBoxLayout()
        self.multiread_captures_spin = QSpinBox()
        self.multiread_captures_spin.setRange(10, 1000)
        self.multiread_captures_spin.setToolTip(
            "Number of flux captures for statistical recovery"
        )
        captures_layout.addWidget(self.multiread_captures_spin)
        self.multiread_captures_label = QLabel("captures")
        captures_layout.addWidget(self.multiread_captures_label)
        captures_layout.addStretch()
        multiread_layout.addRow("Capture Count:", captures_layout)

        layout.addWidget(multiread_group)

        # Advanced Recovery Group
        advanced_group = QGroupBox("Advanced Recovery (Aggressive/Forensic)")
        advanced_layout = QFormLayout(advanced_group)
        advanced_layout.setContentsMargins(8, 12, 8, 8)
        advanced_layout.setSpacing(4)

        # PLL tuning
        self.pll_check = QCheckBox("Enable PLL parameter tuning")
        self.pll_check.setToolTip(
            "Search for optimal PLL parameters on marginal sectors"
        )
        advanced_layout.addRow("", self.pll_check)

        # PLL aggressiveness slider
        pll_slider_layout = QHBoxLayout()
        self.pll_slider = QSlider(Qt.Orientation.Horizontal)
        self.pll_slider.setRange(0, 100)
        self.pll_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.pll_slider.setTickInterval(25)
        self.pll_slider.setToolTip("PLL tuning effort (0 = minimal, 100 = exhaustive)")
        self.pll_value_label = QLabel("50")
        self.pll_value_label.setMinimumWidth(30)
        self.pll_slider.valueChanged.connect(
            lambda v: self.pll_value_label.setText(str(v))
        )
        pll_slider_layout.addWidget(self.pll_slider)
        pll_slider_layout.addWidget(self.pll_value_label)
        advanced_layout.addRow("PLL Effort:", pll_slider_layout)

        # Bit-slip recovery
        self.bit_slip_check = QCheckBox("Enable bit-slip recovery")
        self.bit_slip_check.setToolTip(
            "Attempt to realign and reconstruct sectors with timing errors"
        )
        advanced_layout.addRow("", self.bit_slip_check)

        # Auto retry
        self.auto_retry_check = QCheckBox("Auto-retry on transient errors")
        self.auto_retry_check.setToolTip(
            "Automatically retry operations that fail due to transient errors"
        )
        advanced_layout.addRow("", self.auto_retry_check)

        layout.addWidget(advanced_group)

        # Spacer
        layout.addStretch()

    def _load_settings(self) -> None:
        """Load current settings into controls."""
        recovery = self.settings.recovery

        # Recovery level
        level = recovery.get_recovery_level()
        level_index = {
            RecoveryLevel.STANDARD: 0,
            RecoveryLevel.AGGRESSIVE: 1,
            RecoveryLevel.FORENSIC: 2,
        }.get(level, 0)
        self.recovery_level_combo.setCurrentIndex(level_index)

        # Mode
        self.convergence_check.setChecked(recovery.default_convergence_mode)
        self.preserve_good_check.setChecked(recovery.preserve_good_sectors)

        # Passes
        self.default_passes_spin.setValue(recovery.default_passes)
        self.max_passes_spin.setValue(recovery.max_passes)

        # Multi-read
        self.multiread_check.setChecked(recovery.default_multiread)
        self.multiread_captures_spin.setValue(recovery.multiread_captures)

        # Advanced
        self.pll_check.setChecked(recovery.pll_tuning_enabled)
        self.pll_slider.setValue(recovery.pll_aggressiveness)
        self.bit_slip_check.setChecked(recovery.bit_slip_recovery)
        self.auto_retry_check.setChecked(recovery.auto_retry_on_error)

        # Update UI state
        self._update_ui_state()

    def _on_recovery_level_changed(self, index: int) -> None:
        """Handle recovery level change."""
        self._update_ui_state()

    def _on_convergence_changed(self, state: int) -> None:
        """Handle convergence mode toggle."""
        self._update_ui_state()

    def _on_multiread_changed(self, state: int) -> None:
        """Handle multi-read toggle."""
        self._update_ui_state()

    def _update_ui_state(self) -> None:
        """Update UI enabled states based on selections."""
        # Convergence affects max passes visibility
        convergence = self.convergence_check.isChecked()
        self.max_passes_spin.setEnabled(convergence)

        # Multi-read affects captures
        multiread = self.multiread_check.isChecked()
        self.multiread_captures_spin.setEnabled(multiread)
        self.multiread_captures_label.setEnabled(multiread)

        # Recovery level affects advanced options
        level_index = self.recovery_level_combo.currentIndex()
        advanced_enabled = level_index >= 1  # Aggressive or Forensic
        self.pll_check.setEnabled(advanced_enabled)
        self.pll_slider.setEnabled(advanced_enabled and self.pll_check.isChecked())
        self.pll_value_label.setEnabled(advanced_enabled and self.pll_check.isChecked())

        # Bit-slip only in forensic mode
        self.bit_slip_check.setEnabled(level_index == 2)

    def save_settings(self) -> None:
        """Save control values to settings."""
        recovery = self.settings.recovery

        # Level
        levels = [RecoveryLevel.STANDARD, RecoveryLevel.AGGRESSIVE, RecoveryLevel.FORENSIC]
        recovery.default_recovery_level = levels[
            self.recovery_level_combo.currentIndex()
        ].value

        # Mode
        recovery.default_convergence_mode = self.convergence_check.isChecked()
        recovery.preserve_good_sectors = self.preserve_good_check.isChecked()

        # Passes
        recovery.default_passes = self.default_passes_spin.value()
        recovery.max_passes = self.max_passes_spin.value()

        # Multi-read
        recovery.default_multiread = self.multiread_check.isChecked()
        recovery.multiread_captures = self.multiread_captures_spin.value()

        # Advanced
        recovery.pll_tuning_enabled = self.pll_check.isChecked()
        recovery.pll_aggressiveness = self.pll_slider.value()
        recovery.bit_slip_recovery = self.bit_slip_check.isChecked()
        recovery.auto_retry_on_error = self.auto_retry_check.isChecked()


# =============================================================================
# Export Settings Tab
# =============================================================================

class ExportSettingsTab(QWidget):
    """Tab for export and file settings."""

    def __init__(self, settings: Settings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Set up the export settings UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Default Formats Group
        formats_group = QGroupBox("Default Formats")
        formats_layout = QFormLayout(formats_group)
        formats_layout.setContentsMargins(8, 12, 8, 8)
        formats_layout.setSpacing(6)

        # Default image format
        self.image_format_combo = QComboBox()
        self.image_format_combo.addItems(["IMG", "IMA"])
        self.image_format_combo.setToolTip("Default format for disk image exports")
        formats_layout.addRow("Disk Image Format:", self.image_format_combo)

        # Default flux format
        self.flux_format_combo = QComboBox()
        self.flux_format_combo.addItems(["SCP (SuperCard Pro)", "HFE (HxC Emulator)"])
        self.flux_format_combo.setToolTip("Default format for flux image exports")
        formats_layout.addRow("Flux Image Format:", self.flux_format_combo)

        # Default report format
        self.report_format_combo = QComboBox()
        self.report_format_combo.addItems(["HTML", "PDF", "Plain Text"])
        self.report_format_combo.setToolTip("Default format for report exports")
        formats_layout.addRow("Report Format:", self.report_format_combo)

        layout.addWidget(formats_group)

        # Directories Group
        dirs_group = QGroupBox("Default Directories")
        dirs_layout = QFormLayout(dirs_group)
        dirs_layout.setContentsMargins(8, 12, 8, 8)
        dirs_layout.setSpacing(6)

        # Export directory
        export_dir_layout = QHBoxLayout()
        self.export_dir_edit = QLineEdit()
        self.export_dir_edit.setPlaceholderText("Use last directory")
        self.export_dir_edit.setToolTip("Default directory for exports")
        export_dir_layout.addWidget(self.export_dir_edit)
        self.export_dir_button = QToolButton()
        self.export_dir_button.setText("...")
        self.export_dir_button.setToolTip("Browse for directory")
        self.export_dir_button.clicked.connect(self._browse_export_dir)
        export_dir_layout.addWidget(self.export_dir_button)
        dirs_layout.addRow("Export Directory:", export_dir_layout)

        layout.addWidget(dirs_group)

        # Naming Options Group
        naming_group = QGroupBox("File Naming")
        naming_layout = QFormLayout(naming_group)
        naming_layout.setContentsMargins(8, 12, 8, 8)
        naming_layout.setSpacing(4)

        # Auto name exports
        self.auto_name_check = QCheckBox("Auto-generate filenames")
        self.auto_name_check.setToolTip(
            "Automatically generate descriptive filenames for exports"
        )
        naming_layout.addRow("", self.auto_name_check)

        # Include timestamp
        self.timestamp_check = QCheckBox("Include timestamp in filenames")
        self.timestamp_check.setToolTip(
            "Add date/time to auto-generated filenames"
        )
        naming_layout.addRow("", self.timestamp_check)

        layout.addWidget(naming_group)

        # Export Options Group
        options_group = QGroupBox("Export Options")
        options_layout = QFormLayout(options_group)
        options_layout.setContentsMargins(8, 12, 8, 8)
        options_layout.setSpacing(4)

        # Compress exports
        self.compress_check = QCheckBox("Compress exported files (when supported)")
        self.compress_check.setToolTip(
            "Apply compression to exported files where format supports it"
        )
        options_layout.addRow("", self.compress_check)

        # Embed flux in reports
        self.embed_flux_check = QCheckBox("Embed flux data in HTML reports")
        self.embed_flux_check.setToolTip(
            "Include flux waveform images in HTML reports (increases file size)"
        )
        options_layout.addRow("", self.embed_flux_check)

        layout.addWidget(options_group)

        # Recent Files Group
        recent_group = QGroupBox("Recent Files")
        recent_layout = QVBoxLayout(recent_group)
        recent_layout.setContentsMargins(8, 12, 8, 8)
        recent_layout.setSpacing(6)

        recent_info = QLabel("Recent files are stored in the settings directory.")
        recent_info.setStyleSheet("color: #858585; font-size: 8pt;")
        recent_layout.addWidget(recent_info)

        clear_recent_button = QPushButton("Clear Recent Files")
        clear_recent_button.setToolTip("Clear the recent files list")
        clear_recent_button.clicked.connect(self._clear_recent_files)
        recent_layout.addWidget(clear_recent_button)

        layout.addWidget(recent_group)

        # Spacer
        layout.addStretch()

    def _load_settings(self) -> None:
        """Load current settings into controls."""
        export = self.settings.export

        # Formats
        image_format = export.get_image_format()
        image_index = {ExportFormat.IMG: 0, ExportFormat.IMA: 1}.get(image_format, 0)
        self.image_format_combo.setCurrentIndex(image_index)

        flux_format = export.get_flux_format()
        flux_index = {ExportFormat.SCP: 0, ExportFormat.HFE: 1}.get(flux_format, 0)
        self.flux_format_combo.setCurrentIndex(flux_index)

        report_format = export.get_report_format()
        report_index = {
            ReportFormat.HTML: 0,
            ReportFormat.PDF: 1,
            ReportFormat.TXT: 2,
        }.get(report_format, 0)
        self.report_format_combo.setCurrentIndex(report_index)

        # Directories
        self.export_dir_edit.setText(export.default_export_directory)

        # Naming
        self.auto_name_check.setChecked(export.auto_name_exports)
        self.timestamp_check.setChecked(export.include_timestamp)

        # Options
        self.compress_check.setChecked(export.compress_exports)
        self.embed_flux_check.setChecked(export.embed_flux_in_reports)

    def _browse_export_dir(self) -> None:
        """Browse for export directory."""
        current = self.export_dir_edit.text() or str(self.settings.export.get_export_directory())
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Export Directory",
            current,
            QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self.export_dir_edit.setText(directory)

    def _clear_recent_files(self) -> None:
        """Clear recent files list."""
        reply = QMessageBox.question(
            self,
            "Clear Recent Files",
            "Are you sure you want to clear the recent files list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.clear_recent_files()
            QMessageBox.information(
                self,
                "Recent Files Cleared",
                "The recent files list has been cleared.",
            )

    def save_settings(self) -> None:
        """Save control values to settings."""
        export = self.settings.export

        # Formats
        image_formats = [ExportFormat.IMG, ExportFormat.IMA]
        export.default_image_format = image_formats[
            self.image_format_combo.currentIndex()
        ].value

        flux_formats = [ExportFormat.SCP, ExportFormat.HFE]
        export.default_flux_format = flux_formats[
            self.flux_format_combo.currentIndex()
        ].value

        report_formats = [ReportFormat.HTML, ReportFormat.PDF, ReportFormat.TXT]
        export.default_report_format = report_formats[
            self.report_format_combo.currentIndex()
        ].value

        # Directories
        export.default_export_directory = self.export_dir_edit.text()

        # Naming
        export.auto_name_exports = self.auto_name_check.isChecked()
        export.include_timestamp = self.timestamp_check.isChecked()

        # Options
        export.compress_exports = self.compress_check.isChecked()
        export.embed_flux_in_reports = self.embed_flux_check.isChecked()


# =============================================================================
# Main Settings Dialog
# =============================================================================

class SettingsDialog(QDialog):
    """
    Comprehensive settings dialog with tabbed interface.

    Provides access to all application settings organized into categories:
    - Device: Drive configuration, motor control, seek settings
    - Display: Theme, colors, visual effects, sizes
    - Recovery: Recovery modes, passes, multi-read, PLL tuning
    - Export: File formats, directories, naming options

    Signals:
        theme_changed(str): Emitted when theme is changed
        settings_saved: Emitted when settings are successfully saved
    """

    theme_changed = pyqtSignal(str)
    settings_saved = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize settings dialog.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self.settings = get_settings()
        self._original_theme = self.settings.display.theme
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumSize(600, 700)
        self.resize(650, 750)

        # Apply styling
        self._apply_dialog_style()

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("Settings")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Reset button
        reset_button = QPushButton("Reset to Defaults")
        reset_button.setToolTip("Reset all settings to default values")
        reset_button.clicked.connect(self._on_reset_clicked)
        header_layout.addWidget(reset_button)

        layout.addLayout(header_layout)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)

        # Create tabs
        self.device_tab = DeviceSettingsTab(self.settings)
        self.display_tab = DisplaySettingsTab(self.settings)
        self.recovery_tab = RecoverySettingsTab(self.settings)
        self.export_tab = ExportSettingsTab(self.settings)

        # Add tabs
        self.tab_widget.addTab(self.device_tab, "Device")
        self.tab_widget.addTab(self.display_tab, "Display")
        self.tab_widget.addTab(self.recovery_tab, "Recovery")
        self.tab_widget.addTab(self.export_tab, "Export")

        # Connect theme preview signal
        self.display_tab.theme_preview_requested.connect(self._on_theme_preview)

        layout.addWidget(self.tab_widget)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3a3d41;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # Settings file info
        settings_path = QLabel(f"Settings: {self.settings.settings_file}")
        settings_path.setStyleSheet("color: #858585; font-size: 8pt;")
        button_layout.addWidget(settings_path)

        button_layout.addStretch()

        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumWidth(80)
        self.cancel_button.setMinimumHeight(26)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(self.cancel_button)

        # Apply button
        self.apply_button = QPushButton("Apply")
        self.apply_button.setMinimumWidth(80)
        self.apply_button.setMinimumHeight(26)
        self.apply_button.clicked.connect(self._on_apply_clicked)
        button_layout.addWidget(self.apply_button)

        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.setMinimumWidth(80)
        self.save_button.setMinimumHeight(26)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)

        layout.addLayout(button_layout)

        # Apply button styles
        self._update_button_styles()

    def _apply_dialog_style(self) -> None:
        """Apply dialog styling based on current theme."""
        current_theme = self.settings.display.theme

        if current_theme in ("dark", "system"):
            self.setStyleSheet("""
                QDialog {
                    background-color: #1e1e1e;
                    color: #cccccc;
                }
                QLabel {
                    color: #cccccc;
                    background-color: transparent;
                    font-size: 9pt;
                }
                QGroupBox {
                    border: 1px solid #3a3d41;
                    border-radius: 4px;
                    margin-top: 8px;
                    padding-top: 8px;
                    font-weight: bold;
                    font-size: 9pt;
                    color: #cccccc;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 6px;
                    background-color: #1e1e1e;
                    color: #cccccc;
                }
                QTabWidget::pane {
                    border: 1px solid #3a3d41;
                    background-color: #252526;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #2d2d30;
                    color: #cccccc;
                    padding: 6px 12px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    font-size: 9pt;
                }
                QTabBar::tab:selected {
                    background-color: #252526;
                    border-bottom: 2px solid #0e639c;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #3a3d41;
                }
                QComboBox {
                    background-color: #3a3d41;
                    color: #cccccc;
                    border: 1px solid #6c6c6c;
                    border-radius: 3px;
                    padding: 2px 6px;
                    min-height: 20px;
                    font-size: 9pt;
                }
                QComboBox:hover {
                    border-color: #858585;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px;
                }
                QComboBox QAbstractItemView {
                    background-color: #252526;
                    color: #cccccc;
                    selection-background-color: #0e639c;
                }
                QSpinBox {
                    background-color: #3a3d41;
                    color: #cccccc;
                    border: 1px solid #6c6c6c;
                    border-radius: 3px;
                    padding: 2px 6px;
                    min-height: 20px;
                    font-size: 9pt;
                }
                QSpinBox:hover {
                    border-color: #858585;
                }
                QCheckBox {
                    color: #cccccc;
                    spacing: 6px;
                    font-size: 9pt;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                    border: 1px solid #6c6c6c;
                    border-radius: 2px;
                    background-color: #3a3d41;
                }
                QCheckBox::indicator:hover {
                    border-color: #858585;
                }
                QCheckBox::indicator:checked {
                    background-color: #0e639c;
                    border-color: #0e639c;
                }
                QRadioButton {
                    color: #cccccc;
                    spacing: 6px;
                    font-size: 9pt;
                }
                QRadioButton::indicator {
                    width: 14px;
                    height: 14px;
                    border: 1px solid #6c6c6c;
                    border-radius: 7px;
                    background-color: #3a3d41;
                }
                QRadioButton::indicator:hover {
                    border-color: #858585;
                }
                QRadioButton::indicator:checked {
                    background-color: #0e639c;
                    border-color: #0e639c;
                }
                QLineEdit {
                    background-color: #3a3d41;
                    color: #cccccc;
                    border: 1px solid #6c6c6c;
                    border-radius: 3px;
                    padding: 2px 6px;
                    min-height: 20px;
                    font-size: 9pt;
                }
                QLineEdit:hover {
                    border-color: #858585;
                }
                QLineEdit:focus {
                    border-color: #0e639c;
                }
                QSlider::groove:horizontal {
                    height: 4px;
                    background-color: #3a3d41;
                    border-radius: 2px;
                }
                QSlider::handle:horizontal {
                    width: 16px;
                    height: 16px;
                    background-color: #0e639c;
                    border-radius: 8px;
                    margin: -6px 0;
                }
                QSlider::handle:horizontal:hover {
                    background-color: #1177bb;
                }
                QToolButton {
                    background-color: #3a3d41;
                    color: #cccccc;
                    border: 1px solid #6c6c6c;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
                QToolButton:hover {
                    background-color: #4e5157;
                    border-color: #858585;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #ffffff;
                    color: #1e1e1e;
                }
                QLabel {
                    color: #1e1e1e;
                    background-color: transparent;
                    font-size: 9pt;
                }
                QGroupBox {
                    border: 1px solid #d4d4d4;
                    border-radius: 4px;
                    margin-top: 8px;
                    padding-top: 8px;
                    font-weight: bold;
                    font-size: 9pt;
                    color: #1e1e1e;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 6px;
                    background-color: #ffffff;
                    color: #1e1e1e;
                }
                QTabWidget::pane {
                    border: 1px solid #d4d4d4;
                    background-color: #f5f5f5;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #e0e0e0;
                    color: #1e1e1e;
                    padding: 6px 12px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    font-size: 9pt;
                }
                QTabBar::tab:selected {
                    background-color: #f5f5f5;
                    border-bottom: 2px solid #0e639c;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #d0d0d0;
                }
                QComboBox, QSpinBox, QLineEdit {
                    background-color: #ffffff;
                    color: #1e1e1e;
                    border: 1px solid #c0c0c0;
                    border-radius: 3px;
                    padding: 2px 6px;
                    min-height: 20px;
                    font-size: 9pt;
                }
                QCheckBox, QRadioButton {
                    color: #1e1e1e;
                    spacing: 6px;
                    font-size: 9pt;
                }
                QCheckBox::indicator, QRadioButton::indicator {
                    width: 14px;
                    height: 14px;
                    border: 1px solid #888888;
                    background-color: #ffffff;
                }
                QCheckBox::indicator:checked, QRadioButton::indicator:checked {
                    background-color: #0e639c;
                    border-color: #0e639c;
                }
            """)

    def _update_button_styles(self) -> None:
        """Update button styles based on current theme."""
        current_theme = self.settings.display.theme

        if current_theme in ("dark", "system"):
            secondary_style = """
                QPushButton {
                    background-color: #3a3d41;
                    color: #ffffff;
                    border: 1px solid #6c6c6c;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4e5157;
                    border-color: #858585;
                }
                QPushButton:pressed {
                    background-color: #2d2d30;
                }
            """
            primary_style = """
                QPushButton {
                    background-color: #0e639c;
                    color: #ffffff;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1177bb;
                }
                QPushButton:pressed {
                    background-color: #094771;
                }
            """
        else:
            secondary_style = """
                QPushButton {
                    background-color: #e0e0e0;
                    color: #1e1e1e;
                    border: 1px solid #c0c0c0;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #d0d0d0;
                    border-color: #a0a0a0;
                }
                QPushButton:pressed {
                    background-color: #c0c0c0;
                }
            """
            primary_style = """
                QPushButton {
                    background-color: #0e639c;
                    color: #ffffff;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1177bb;
                }
                QPushButton:pressed {
                    background-color: #094771;
                }
            """

        self.cancel_button.setStyleSheet(secondary_style)
        self.apply_button.setStyleSheet(secondary_style)
        self.save_button.setStyleSheet(primary_style)

    def _on_theme_preview(self, theme: str) -> None:
        """Handle theme preview request."""
        # Store temporarily for preview
        old_theme = self.settings.display.theme
        self.settings.display.theme = theme
        self._apply_dialog_style()
        self._update_button_styles()
        # Restore (actual save happens on Apply/Save)
        self.settings.display.theme = old_theme

    def _on_reset_clicked(self) -> None:
        """Handle Reset to Defaults button click."""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to their default values?\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Reset all categories
            self.settings.reset_to_defaults()

            # Reload all tabs
            self.device_tab._load_settings()
            self.display_tab._load_settings()
            self.recovery_tab._load_settings()
            self.export_tab._load_settings()

            # Update dialog styling
            self._apply_dialog_style()
            self._update_button_styles()

            QMessageBox.information(
                self,
                "Settings Reset",
                "All settings have been reset to their default values.",
            )

    def _on_apply_clicked(self) -> None:
        """Handle Apply button click - save without closing."""
        self._save_all_settings()

    def _on_save_clicked(self) -> None:
        """Handle Save button click - save and close."""
        if self._save_all_settings():
            self.accept()

    def _on_cancel_clicked(self) -> None:
        """Handle Cancel button click - revert and close."""
        # Reload settings to discard changes
        self.settings.load()
        self.reject()

    def _save_all_settings(self) -> bool:
        """
        Save all settings from all tabs.

        Returns:
            True if settings were saved successfully
        """
        try:
            # Save from each tab
            self.device_tab.save_settings()
            self.display_tab.save_settings()
            self.recovery_tab.save_settings()
            self.export_tab.save_settings()

            # Check if theme changed
            new_theme = self.display_tab.get_current_theme()
            if new_theme != self._original_theme:
                self.theme_changed.emit(new_theme)
                self._original_theme = new_theme

            # Persist to file
            if self.settings.save():
                self.settings_saved.emit()

                # Emit signals for change notifications
                if self.settings.signals:
                    self.settings.signals.device_settings_changed.emit()
                    self.settings.signals.display_settings_changed.emit()
                    self.settings.signals.recovery_settings_changed.emit()
                    self.settings.signals.export_settings_changed.emit()

                logger.info("Settings saved successfully")
                return True
            else:
                QMessageBox.warning(
                    self,
                    "Save Failed",
                    "Could not save settings to file.\n\n"
                    "Please check that you have write permission to the settings directory.",
                )
                return False

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while saving settings:\n\n{e}",
            )
            return False


# =============================================================================
# Convenience Functions
# =============================================================================

def show_settings_dialog(
    parent: Optional[QWidget] = None,
    on_theme_changed: Optional[Callable[[str], None]] = None,
    on_settings_saved: Optional[Callable[[], None]] = None,
) -> bool:
    """
    Show the settings dialog.

    This is a convenience function that creates and executes the dialog.

    Args:
        parent: Optional parent widget
        on_theme_changed: Optional callback for theme changes
        on_settings_saved: Optional callback when settings are saved

    Returns:
        True if settings were saved, False if cancelled
    """
    dialog = SettingsDialog(parent)

    if on_theme_changed:
        dialog.theme_changed.connect(on_theme_changed)
    if on_settings_saved:
        dialog.settings_saved.connect(on_settings_saved)

    result = dialog.exec()
    return result == QDialog.DialogCode.Accepted


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'SettingsDialog',
    'DeviceSettingsTab',
    'DisplaySettingsTab',
    'RecoverySettingsTab',
    'ExportSettingsTab',
    'show_settings_dialog',
]
