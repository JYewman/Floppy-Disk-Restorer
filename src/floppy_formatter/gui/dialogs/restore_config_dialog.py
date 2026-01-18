"""
Restore configuration dialog for Greaseweazle operations.

Provides comprehensive configuration for disk recovery including
all preserved options from the original application plus new
advanced recovery features like PLL tuning and bit-slip recovery.

CRITICAL: This dialog preserves ALL existing restore options
while adding new advanced capabilities.

Part of Phase 10: Operation Dialogs & Configurations
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, List

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QFrame,
    QScrollArea,
)
from PyQt6.QtGui import QFont


# =============================================================================
# Enums and Data Classes
# =============================================================================

class RecoveryLevel(Enum):
    """Recovery effort level."""
    STANDARD = auto()  # Basic multi-pass format/verify recovery
    AGGRESSIVE = auto()  # Multi-capture + PLL tuning
    FORENSIC = auto()  # All techniques, maximum effort


@dataclass
class RestoreConfig:
    """
    Configuration for a restore operation.

    PRESERVED from original application:
        passes: Number of passes for fixed mode (1-100)
        convergence_mode: Use convergence detection instead of fixed passes
        max_passes: Maximum passes for convergence mode (5-200)
        targeted_mode: Only recover known bad sectors
        multiread_mode: Enable multi-read statistical recovery
        multiread_attempts: Number of read attempts (10-1000)
        bad_sector_list: Pre-identified bad sectors for targeted mode

    NEW advanced options:
        recovery_level: Standard/Aggressive/Forensic
        pll_tuning: Enable PLL parameter search
        bit_slip_recovery: Enable bit-slip recovery for sync errors
        surface_treatment: Enable DC erase + pattern refresh

    Report options:
        generate_report: Generate detailed report
        include_track_maps: Include visual track maps in report
        include_hex_dumps: Include hex dumps of bad sectors
        save_report: Save report to file
    """
    # PRESERVED: Recovery mode options
    convergence_mode: bool = True
    passes: int = 5
    max_passes: int = 50
    convergence_threshold: int = 3

    # PRESERVED: Scope options
    targeted_mode: bool = False
    bad_sector_list: Optional[List[int]] = None

    # PRESERVED: Multi-read options (enhanced with flux)
    multiread_mode: bool = False
    multiread_attempts: int = 100

    # NEW: Recovery level
    recovery_level: RecoveryLevel = RecoveryLevel.STANDARD

    # NEW: Advanced options
    pll_tuning: bool = False
    bit_slip_recovery: bool = False
    surface_treatment: bool = False

    # Report options
    generate_report: bool = True
    include_track_maps: bool = True
    include_hex_dumps: bool = False
    save_report: bool = False


# =============================================================================
# Restore Config Dialog
# =============================================================================

class RestoreConfigDialog(QDialog):
    """
    Dialog for configuring disk restore operations.

    PRESERVES ALL existing restore functionality:
    - Fixed passes vs Convergence mode
    - Pass count configuration
    - Multi-read statistical recovery
    - Targeted recovery mode

    ADDS new advanced recovery options:
    - Recovery level (Standard/Aggressive/Forensic)
    - PLL tuning for marginal sectors
    - Bit-slip recovery for sync errors
    - Surface treatment for weak media

    Example:
        dialog = RestoreConfigDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            # Start restore with config
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        has_scan_data: bool = True,
        bad_sector_count: int = 0
    ):
        """
        Initialize restore config dialog.

        Args:
            parent: Optional parent widget
            has_scan_data: Whether scan data is available for targeted mode
            bad_sector_count: Number of bad sectors from last scan
        """
        super().__init__(parent)
        self._has_scan_data = has_scan_data
        self._bad_sector_count = bad_sector_count
        self._setup_ui()
        self._connect_signals()
        self._update_recovery_level_options()

    def _setup_ui(self) -> None:
        """Set up the dialog user interface."""
        self.setWindowTitle("Restore Configuration")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setMinimumHeight(700)

        # Apply dark theme styling
        self._apply_dialog_style()

        # Main layout with scroll
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: #1e1e1e; border: none; }")

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_label = QLabel("Restore Configuration")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # =====================================================================
        # PRESERVED: Recovery Mode group
        # =====================================================================
        mode_group = QGroupBox("Recovery Mode")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(8)

        self._mode_group = QButtonGroup(self)

        # Fixed passes option
        fixed_row = QHBoxLayout()
        fixed_row.setSpacing(12)

        self._fixed_radio = QRadioButton("Fixed Passes")
        self._fixed_radio.setToolTip("Run exactly N recovery passes")
        self._mode_group.addButton(self._fixed_radio, 0)
        fixed_row.addWidget(self._fixed_radio)

        self._passes_spin = QSpinBox()
        self._passes_spin.setRange(1, 100)
        self._passes_spin.setValue(5)
        self._passes_spin.setToolTip("Number of passes to run (1-100)")
        self._passes_spin.setMinimumWidth(70)
        self._passes_spin.setEnabled(False)
        fixed_row.addWidget(self._passes_spin)

        passes_label = QLabel("passes")
        fixed_row.addWidget(passes_label)
        fixed_row.addStretch()
        mode_layout.addLayout(fixed_row)

        fixed_desc = QLabel("Runs exactly the specified number of format/verify cycles.")
        fixed_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        fixed_desc.setWordWrap(True)
        mode_layout.addWidget(fixed_desc)

        # Convergence mode option
        conv_row = QHBoxLayout()
        conv_row.setSpacing(12)

        self._convergence_radio = QRadioButton("Convergence Mode")
        self._convergence_radio.setToolTip("Continue until bad sector count stabilizes")
        self._convergence_radio.setChecked(True)
        self._mode_group.addButton(self._convergence_radio, 1)
        conv_row.addWidget(self._convergence_radio)

        max_label = QLabel("Max:")
        conv_row.addWidget(max_label)

        self._max_passes_spin = QSpinBox()
        self._max_passes_spin.setRange(5, 200)
        self._max_passes_spin.setValue(50)
        self._max_passes_spin.setToolTip("Maximum passes before stopping (5-200)")
        self._max_passes_spin.setMinimumWidth(70)
        conv_row.addWidget(self._max_passes_spin)

        conv_passes_label = QLabel("passes")
        conv_row.addWidget(conv_passes_label)
        conv_row.addStretch()
        mode_layout.addLayout(conv_row)

        conv_desc = QLabel(
            "Continues recovery until bad sector count stops improving for 3 consecutive passes."
        )
        conv_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        conv_desc.setWordWrap(True)
        mode_layout.addWidget(conv_desc)

        layout.addWidget(mode_group)

        # =====================================================================
        # PRESERVED: Recovery Scope group
        # =====================================================================
        scope_group = QGroupBox("Recovery Scope")
        scope_layout = QVBoxLayout(scope_group)
        scope_layout.setSpacing(8)

        self._scope_group = QButtonGroup(self)

        # Full disk recovery
        self._full_radio = QRadioButton("Full Disk Recovery")
        self._full_radio.setToolTip("Format and recover entire disk")
        self._full_radio.setChecked(True)
        self._scope_group.addButton(self._full_radio, 0)
        scope_layout.addWidget(self._full_radio)

        full_desc = QLabel("Formats and recovers all sectors on the disk.")
        full_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        full_desc.setWordWrap(True)
        scope_layout.addWidget(full_desc)

        # Targeted recovery
        self._targeted_radio = QRadioButton("Targeted Recovery")
        self._targeted_radio.setToolTip("Only recover known bad sectors")
        self._scope_group.addButton(self._targeted_radio, 1)
        scope_layout.addWidget(self._targeted_radio)

        if self._has_scan_data:
            targeted_desc = QLabel(
                f"Only recovers {self._bad_sector_count} bad sectors from last scan. "
                "Preserves good sectors."
            )
        else:
            targeted_desc = QLabel("Requires prior scan to identify bad sectors.")
            self._targeted_radio.setEnabled(False)
        targeted_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        targeted_desc.setWordWrap(True)
        scope_layout.addWidget(targeted_desc)

        layout.addWidget(scope_group)

        # =====================================================================
        # PRESERVED: Multi-Read Recovery group (enhanced with flux)
        # =====================================================================
        multiread_group = QGroupBox("Multi-Read Recovery")
        multiread_layout = QVBoxLayout(multiread_group)
        multiread_layout.setSpacing(8)

        self._multiread_check = QCheckBox("Enable Multi-Read Mode")
        self._multiread_check.setToolTip("Use statistical recovery with multiple reads")
        multiread_layout.addWidget(self._multiread_check)

        attempts_row = QHBoxLayout()
        attempts_row.setSpacing(12)
        attempts_row.addSpacing(24)

        attempts_label = QLabel("Flux captures:")
        attempts_label.setMinimumWidth(90)
        attempts_row.addWidget(attempts_label)

        self._attempts_spin = QSpinBox()
        self._attempts_spin.setRange(10, 1000)
        self._attempts_spin.setValue(100)
        self._attempts_spin.setToolTip("Number of flux revolutions to capture (10-1000)")
        self._attempts_spin.setMinimumWidth(80)
        self._attempts_spin.setEnabled(False)
        attempts_row.addWidget(self._attempts_spin)

        attempts_row.addStretch()
        multiread_layout.addLayout(attempts_row)

        multiread_desc = QLabel(
            "Captures multiple flux revolutions for statistical bit recovery. "
            "More captures = better accuracy but slower."
        )
        multiread_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        multiread_desc.setWordWrap(True)
        multiread_layout.addWidget(multiread_desc)

        multiread_note = QLabel(
            "Enhanced: Now uses flux-level bit voting for improved accuracy "
            "over byte-level recovery."
        )
        multiread_note.setStyleSheet("color: #27ae60; font-size: 9pt; margin-left: 24px;")
        multiread_note.setWordWrap(True)
        multiread_layout.addWidget(multiread_note)

        layout.addWidget(multiread_group)

        # =====================================================================
        # NEW: Recovery Level group
        # =====================================================================
        level_group = QGroupBox("Recovery Level")
        level_layout = QVBoxLayout(level_group)
        level_layout.setSpacing(8)

        level_row = QHBoxLayout()
        level_row.setSpacing(12)

        level_label = QLabel("Level:")
        level_label.setMinimumWidth(50)
        level_row.addWidget(level_label)

        self._level_combo = QComboBox()
        self._level_combo.addItem("Standard", RecoveryLevel.STANDARD)
        self._level_combo.addItem("Aggressive", RecoveryLevel.AGGRESSIVE)
        self._level_combo.addItem("Forensic", RecoveryLevel.FORENSIC)
        self._level_combo.setToolTip("Select recovery aggressiveness")
        self._level_combo.setMinimumWidth(150)
        level_row.addWidget(self._level_combo)

        level_row.addStretch()
        level_layout.addLayout(level_row)

        self._level_desc = QLabel()
        self._level_desc.setStyleSheet("color: #858585; font-size: 9pt;")
        self._level_desc.setWordWrap(True)
        level_layout.addWidget(self._level_desc)

        layout.addWidget(level_group)

        # =====================================================================
        # NEW: Advanced Options group
        # =====================================================================
        advanced_group = QGroupBox("Advanced Options")
        advanced_layout = QVBoxLayout(advanced_group)
        advanced_layout.setSpacing(8)

        self._pll_check = QCheckBox("Enable PLL Tuning")
        self._pll_check.setToolTip("Search for optimal PLL parameters on marginal sectors")
        advanced_layout.addWidget(self._pll_check)

        pll_desc = QLabel("Systematically adjusts decoder parameters to recover marginal sectors.")
        pll_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        pll_desc.setWordWrap(True)
        advanced_layout.addWidget(pll_desc)

        self._bitslip_check = QCheckBox("Enable Bit-Slip Recovery")
        self._bitslip_check.setToolTip("Attempt to recover from synchronization errors")
        advanced_layout.addWidget(self._bitslip_check)

        bitslip_desc = QLabel(
            "Detects and recovers from timing sync losses that cause decode failures."
        )
        bitslip_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        bitslip_desc.setWordWrap(True)
        advanced_layout.addWidget(bitslip_desc)

        self._surface_check = QCheckBox("Enable Surface Treatment")
        self._surface_check.setToolTip("DC erase + pattern refresh for weak areas")
        advanced_layout.addWidget(self._surface_check)

        surface_desc = QLabel(
            "Performs full track degauss followed by pattern writes to refresh "
            "weak magnetic areas."
        )
        surface_desc.setStyleSheet("color: #858585; font-size: 9pt; margin-left: 24px;")
        surface_desc.setWordWrap(True)
        advanced_layout.addWidget(surface_desc)

        advanced_note = QLabel(
            "Options are auto-enabled based on Recovery Level but can be overridden."
        )
        advanced_note.setStyleSheet("color: #b89500; font-size: 9pt; font-style: italic;")
        advanced_note.setWordWrap(True)
        advanced_layout.addWidget(advanced_note)

        layout.addWidget(advanced_group)

        # =====================================================================
        # Report Options group
        # =====================================================================
        report_group = QGroupBox("Report Options")
        report_layout = QVBoxLayout(report_group)
        report_layout.setSpacing(8)

        self._report_check = QCheckBox("Generate detailed report")
        self._report_check.setChecked(True)
        self._report_check.setToolTip("Create a recovery report with statistics")
        report_layout.addWidget(self._report_check)

        self._trackmap_check = QCheckBox("Include track maps")
        self._trackmap_check.setChecked(True)
        self._trackmap_check.setToolTip("Include visual sector maps in report")
        self._trackmap_check.setStyleSheet("margin-left: 24px;")
        report_layout.addWidget(self._trackmap_check)

        self._hexdump_check = QCheckBox("Include hex dumps of bad sectors")
        self._hexdump_check.setToolTip("Include raw data from recovered/failed sectors")
        self._hexdump_check.setStyleSheet("margin-left: 24px;")
        report_layout.addWidget(self._hexdump_check)

        self._save_report_check = QCheckBox("Save report to file")
        self._save_report_check.setToolTip("Automatically save report when complete")
        self._save_report_check.setStyleSheet("margin-left: 24px;")
        report_layout.addWidget(self._save_report_check)

        layout.addWidget(report_group)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3a3d41;")
        separator.setFixedHeight(1)
        main_layout.addWidget(separator)

        # Buttons (outside scroll area)
        button_container = QWidget()
        button_container.setStyleSheet("background-color: #1e1e1e;")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(24, 12, 24, 16)
        button_layout.setSpacing(12)
        button_layout.addStretch()

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setMinimumWidth(100)
        self._cancel_button.setMinimumHeight(32)
        self._cancel_button.clicked.connect(self.reject)
        self._cancel_button.setShortcut("Escape")
        button_layout.addWidget(self._cancel_button)

        self._start_button = QPushButton("Start Restore")
        self._start_button.setMinimumWidth(120)
        self._start_button.setMinimumHeight(32)
        self._start_button.clicked.connect(self._on_start_clicked)
        self._start_button.setDefault(True)
        button_layout.addWidget(self._start_button)

        main_layout.addWidget(button_container)

        # Apply button styles
        self._apply_button_styles()

    def _apply_dialog_style(self) -> None:
        """Apply dark theme styling to dialog."""
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #cccccc;
            }
            QLabel {
                color: #cccccc;
                background-color: transparent;
            }
            QGroupBox {
                border: 1px solid #3a3d41;
                border-radius: 4px;
                margin-top: 12px;
                padding: 12px;
                padding-top: 24px;
                font-weight: bold;
                color: #cccccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                background-color: #1e1e1e;
                color: #cccccc;
            }
            QRadioButton {
                color: #cccccc;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #6c6c6c;
                border-radius: 8px;
                background-color: #3a3d41;
            }
            QRadioButton::indicator:hover {
                border-color: #007acc;
            }
            QRadioButton::indicator:checked {
                background-color: #0e639c;
                border-color: #0e639c;
            }
            QRadioButton:disabled {
                color: #6c6c6c;
            }
            QCheckBox {
                color: #cccccc;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #6c6c6c;
                border-radius: 3px;
                background-color: #3a3d41;
            }
            QCheckBox::indicator:hover {
                border-color: #007acc;
            }
            QCheckBox::indicator:checked {
                background-color: #0e639c;
                border-color: #0e639c;
            }
            QSpinBox {
                background-color: #3a3d41;
                color: #cccccc;
                border: 1px solid #6c6c6c;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QSpinBox:disabled {
                background-color: #2d2d30;
                color: #6c6c6c;
                border-color: #3a3d41;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #4e5157;
                border: none;
                width: 20px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #5a5d63;
            }
            QComboBox {
                background-color: #3a3d41;
                color: #cccccc;
                border: 1px solid #6c6c6c;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QComboBox:hover {
                border-color: #007acc;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d30;
                color: #cccccc;
                selection-background-color: #0e639c;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #3a3d41;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4e5157;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

    def _apply_button_styles(self) -> None:
        """Apply button styling."""
        self._cancel_button.setStyleSheet("""
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
        """)
        self._start_button.setStyleSheet("""
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
        """)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self._mode_group.buttonClicked.connect(self._on_mode_changed)
        self._multiread_check.toggled.connect(self._on_multiread_toggled)
        self._level_combo.currentIndexChanged.connect(self._on_level_changed)
        self._report_check.toggled.connect(self._on_report_toggled)

    def _on_mode_changed(self) -> None:
        """Handle recovery mode radio button change."""
        is_fixed = self._fixed_radio.isChecked()
        self._passes_spin.setEnabled(is_fixed)
        self._max_passes_spin.setEnabled(not is_fixed)

    def _on_multiread_toggled(self, checked: bool) -> None:
        """Handle multi-read checkbox toggle."""
        self._attempts_spin.setEnabled(checked)

    def _on_level_changed(self, index: int) -> None:
        """Handle recovery level combo change."""
        self._update_recovery_level_options()

    def _update_recovery_level_options(self) -> None:
        """Update advanced options based on recovery level."""
        level = self._level_combo.currentData()

        if level == RecoveryLevel.STANDARD:
            self._level_desc.setText(
                "Traditional recovery using format passes and verification. "
                "Suitable for routine recovery tasks."
            )
            # Standard defaults
            self._pll_check.setChecked(False)
            self._bitslip_check.setChecked(False)
            self._surface_check.setChecked(False)

        elif level == RecoveryLevel.AGGRESSIVE:
            self._level_desc.setText(
                "Adds advanced PLL tuning and multi-capture analysis. "
                "Better results for marginal disks."
            )
            # Aggressive defaults
            self._pll_check.setChecked(True)
            self._bitslip_check.setChecked(False)
            self._surface_check.setChecked(True)

        elif level == RecoveryLevel.FORENSIC:
            self._level_desc.setText(
                "Uses all available techniques including bit-slip recovery. "
                "Maximum effort, detailed logging. Slowest but best results."
            )
            # Forensic defaults
            self._pll_check.setChecked(True)
            self._bitslip_check.setChecked(True)
            self._surface_check.setChecked(True)
            self._multiread_check.setChecked(True)

    def _on_report_toggled(self, checked: bool) -> None:
        """Handle report checkbox toggle."""
        self._trackmap_check.setEnabled(checked)
        self._hexdump_check.setEnabled(checked)
        self._save_report_check.setEnabled(checked)

    def _on_start_clicked(self) -> None:
        """Handle Start Restore button click."""
        self.accept()

    def get_config(self) -> RestoreConfig:
        """
        Get the configured restore settings.

        Returns:
            RestoreConfig with current dialog settings
        """
        return RestoreConfig(
            # PRESERVED: Mode options
            convergence_mode=self._convergence_radio.isChecked(),
            passes=self._passes_spin.value(),
            max_passes=self._max_passes_spin.value(),

            # PRESERVED: Scope options
            targeted_mode=self._targeted_radio.isChecked(),

            # PRESERVED: Multi-read options
            multiread_mode=self._multiread_check.isChecked(),
            multiread_attempts=self._attempts_spin.value(),

            # NEW: Recovery level
            recovery_level=self._level_combo.currentData(),

            # NEW: Advanced options
            pll_tuning=self._pll_check.isChecked(),
            bit_slip_recovery=self._bitslip_check.isChecked(),
            surface_treatment=self._surface_check.isChecked(),

            # Report options
            generate_report=self._report_check.isChecked(),
            include_track_maps=self._trackmap_check.isChecked(),
            include_hex_dumps=self._hexdump_check.isChecked(),
            save_report=self._save_report_check.isChecked(),
        )

    def set_config(self, config: RestoreConfig) -> None:
        """
        Set dialog values from a config.

        Args:
            config: RestoreConfig to apply
        """
        # Mode options
        if config.convergence_mode:
            self._convergence_radio.setChecked(True)
        else:
            self._fixed_radio.setChecked(True)

        self._passes_spin.setValue(config.passes)
        self._max_passes_spin.setValue(config.max_passes)
        self._on_mode_changed()

        # Scope options
        if config.targeted_mode:
            self._targeted_radio.setChecked(True)
        else:
            self._full_radio.setChecked(True)

        # Multi-read options
        self._multiread_check.setChecked(config.multiread_mode)
        self._attempts_spin.setValue(config.multiread_attempts)

        # Recovery level
        for i in range(self._level_combo.count()):
            if self._level_combo.itemData(i) == config.recovery_level:
                self._level_combo.setCurrentIndex(i)
                break

        # Advanced options (set after level to override defaults)
        self._pll_check.setChecked(config.pll_tuning)
        self._bitslip_check.setChecked(config.bit_slip_recovery)
        self._surface_check.setChecked(config.surface_treatment)

        # Report options
        self._report_check.setChecked(config.generate_report)
        self._trackmap_check.setChecked(config.include_track_maps)
        self._hexdump_check.setChecked(config.include_hex_dumps)
        self._save_report_check.setChecked(config.save_report)


def show_restore_config_dialog(
    parent: Optional[QWidget] = None,
    has_scan_data: bool = True,
    bad_sector_count: int = 0
) -> Optional[RestoreConfig]:
    """
    Show the restore configuration dialog.

    Args:
        parent: Optional parent widget
        has_scan_data: Whether scan data is available
        bad_sector_count: Number of bad sectors from last scan

    Returns:
        RestoreConfig if accepted, None if cancelled
    """
    dialog = RestoreConfigDialog(parent, has_scan_data, bad_sector_count)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_config()
    return None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'RestoreConfigDialog',
    'RestoreConfig',
    'RecoveryLevel',
    'show_restore_config_dialog',
]
