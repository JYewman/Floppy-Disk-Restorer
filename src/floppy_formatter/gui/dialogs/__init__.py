"""
Dialog windows for Floppy Workbench GUI.

Contains confirmation dialogs, settings, about, operation configuration dialogs,
splash screen, and other modal windows.

Part of Phase 10, 14: Operation Dialogs & Configurations, Polish & Professional Touches
"""

from floppy_formatter.gui.dialogs.confirm_cancel import (
    ConfirmCancelDialog,
    show_confirm_cancel_dialog,
)
from floppy_formatter.gui.dialogs.confirm_format import (
    ConfirmFormatDialog,
    show_confirm_format_dialog,
)
from floppy_formatter.gui.dialogs.confirm_restore import (
    ConfirmRestoreDialog,
    show_confirm_restore_dialog,
)
from floppy_formatter.gui.dialogs.admin_warning import (
    AdminWarningDialog,
    AdminWarningResult,
    show_admin_warning_dialog,
    check_admin_privileges,
)
from floppy_formatter.gui.dialogs.about_dialog import (
    AboutDialog,
    show_about_dialog,
)
from floppy_formatter.gui.dialogs.settings_dialog import (
    SettingsDialog,
    show_settings_dialog,
)

# Phase 10: Operation Configuration Dialogs
from floppy_formatter.gui.dialogs.scan_config_dialog import (
    ScanConfigDialog,
    ScanConfig,
    ScanMode,
    show_scan_config_dialog,
)
from floppy_formatter.gui.dialogs.format_config_dialog import (
    FormatConfigDialog,
    FormatConfig,
    FormatType,
    PATTERN_ZERO,
    PATTERN_ONE,
    PATTERN_E5,
    PATTERN_AA,
    PATTERN_55,
    show_format_config_dialog,
)
from floppy_formatter.gui.dialogs.restore_config_dialog import (
    RestoreConfigDialog,
    RestoreConfig,
    RecoveryLevel,
    show_restore_config_dialog,
)
from floppy_formatter.gui.dialogs.analyze_config_dialog import (
    AnalyzeConfigDialog,
    AnalysisConfig,
    AnalysisDepth,
    show_analyze_config_dialog,
)
from floppy_formatter.gui.dialogs.export_dialog import (
    ExportDialog,
    ExportConfig,
    ExportType,
    show_export_dialog,
)

# Write Image configuration (Write Image feature)
from floppy_formatter.gui.dialogs.write_image_config_dialog import (
    WriteImageConfigDialog,
    WriteImageConfig,
)

# Phase 14: Splash Screen
from floppy_formatter.gui.dialogs.splash_screen import (
    SplashScreen,
    LoadingSequence,
    SplashScreenManager,
    show_splash,
    update_splash_progress,
    finish_splash,
)

# Batch Verification Dialogs (Phase 11)
from floppy_formatter.gui.dialogs.batch_verify_config_dialog import (
    BatchVerifyConfigDialog,
    BatchVerifyConfig,
    FloppyBrand,
    FloppyDiskInfo,
    show_batch_verify_config_dialog,
)
from floppy_formatter.gui.dialogs.disk_prompt_dialog import (
    DiskPromptDialog,
    DiskPromptResult,
    show_disk_prompt_dialog,
)

__all__ = [
    # Confirmation dialogs
    "ConfirmCancelDialog",
    "show_confirm_cancel_dialog",
    "ConfirmFormatDialog",
    "show_confirm_format_dialog",
    "ConfirmRestoreDialog",
    "show_confirm_restore_dialog",
    # Admin warning
    "AdminWarningDialog",
    "AdminWarningResult",
    "show_admin_warning_dialog",
    "check_admin_privileges",
    # About and settings
    "AboutDialog",
    "show_about_dialog",
    "SettingsDialog",
    "show_settings_dialog",
    # Scan configuration
    "ScanConfigDialog",
    "ScanConfig",
    "ScanMode",
    "show_scan_config_dialog",
    # Format configuration
    "FormatConfigDialog",
    "FormatConfig",
    "FormatType",
    "PATTERN_ZERO",
    "PATTERN_ONE",
    "PATTERN_E5",
    "PATTERN_AA",
    "PATTERN_55",
    "show_format_config_dialog",
    # Restore configuration
    "RestoreConfigDialog",
    "RestoreConfig",
    "RecoveryLevel",
    "show_restore_config_dialog",
    # Analyze configuration
    "AnalyzeConfigDialog",
    "AnalysisConfig",
    "AnalysisDepth",
    "show_analyze_config_dialog",
    # Export configuration
    "ExportDialog",
    "ExportConfig",
    "ExportType",
    "show_export_dialog",
    # Write Image configuration
    "WriteImageConfigDialog",
    "WriteImageConfig",
    # Splash screen (Phase 14)
    "SplashScreen",
    "LoadingSequence",
    "SplashScreenManager",
    "show_splash",
    "update_splash_progress",
    "finish_splash",
    # Batch Verification (Phase 11)
    "BatchVerifyConfigDialog",
    "BatchVerifyConfig",
    "FloppyBrand",
    "FloppyDiskInfo",
    "show_batch_verify_config_dialog",
    "DiskPromptDialog",
    "DiskPromptResult",
    "show_disk_prompt_dialog",
]
