"""
Settings management module for Floppy Workbench.

This module provides comprehensive settings management with JSON-based
persistence, singleton pattern, and Qt signal notifications for changes.

Features:
    - Singleton pattern for global settings access
    - JSON-based configuration file persistence
    - Platform-specific settings paths
    - Settings change notifications via Qt signals
    - Migration support between versions
    - Edge case handling (file locked, disk full, invalid JSON)
    - Category-based settings organization

Settings Categories:
    - Device: Drive unit, motor timeout, seek speed
    - Display: Theme, color scheme, sector map colors
    - Recovery: Default modes, passes, PLL settings
    - Export: Default formats, directories, naming
    - Window: Size, position, panel layouts

Part of Phase 13: Settings & Persistence
"""

import json
import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    HAS_QT = True
except ImportError:
    HAS_QT = False
    # Provide stub for non-Qt environments
    class QObject:
        pass
    def pyqtSignal(*args, **kwargs):
        return None


# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Settings File Paths
# =============================================================================

def get_settings_dir() -> Path:
    """
    Get the platform-specific settings directory.

    Returns:
        Path to settings directory

    Platform paths:
        - Linux: ~/.config/floppy-workbench/
        - Windows: %APPDATA%/FloppyWorkbench/
        - macOS: ~/Library/Application Support/FloppyWorkbench/
    """
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
        return base / 'FloppyWorkbench'
    elif sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'FloppyWorkbench'
    else:
        # Linux and other Unix-like
        xdg_config = os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')
        return Path(xdg_config) / 'floppy-workbench'


def get_settings_file() -> Path:
    """Get the settings file path."""
    return get_settings_dir() / 'settings.json'


def get_recent_files_path() -> Path:
    """Get the recent files list path."""
    return get_settings_dir() / 'recent_files.json'


# =============================================================================
# Enumerations
# =============================================================================

class SeekSpeed(Enum):
    """Drive seek speed preferences."""
    SLOW = "slow"          # Conservative, gentler on old drives
    NORMAL = "normal"      # Standard seek timing
    FAST = "fast"          # Aggressive, faster operations


class ColorScheme(Enum):
    """Color scheme options for accessibility."""
    STANDARD = "standard"          # Default red/yellow/green
    DEUTERANOPIA = "deuteranopia"  # Red-green colorblind (most common)
    PROTANOPIA = "protanopia"      # Red colorblind
    TRITANOPIA = "tritanopia"      # Blue-yellow colorblind
    HIGH_CONTRAST = "high_contrast"  # Maximum contrast for visibility
    MONOCHROME = "monochrome"      # Grayscale only


class RecoveryLevel(Enum):
    """Recovery aggressiveness levels."""
    STANDARD = "standard"      # Basic multi-pass recovery
    AGGRESSIVE = "aggressive"  # Multi-capture + PLL tuning
    FORENSIC = "forensic"      # All techniques, maximum effort


class ExportFormat(Enum):
    """Default export format preferences."""
    IMG = "img"      # Raw sector image
    IMA = "ima"      # IBM PC format image
    SCP = "scp"      # SuperCard Pro flux image
    HFE = "hfe"      # HxC Floppy Emulator flux image


class ReportFormat(Enum):
    """Report export format preferences."""
    HTML = "html"
    PDF = "pdf"
    TXT = "txt"


class Theme(Enum):
    """Application theme options."""
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


# =============================================================================
# Color Scheme Definitions
# =============================================================================

@dataclass
class SectorMapColors:
    """Color definitions for sector map visualization."""
    good: str = "#4ec9b0"       # Green - good sectors
    bad: str = "#f14c4c"        # Red - bad sectors
    weak: str = "#f0a030"       # Orange/Yellow - weak sectors
    unknown: str = "#3c3c3c"    # Gray - unscanned sectors
    reading: str = "#0e639c"    # Blue - currently reading
    writing: str = "#9b59b6"    # Purple - currently writing
    recovering: str = "#e67e22" # Orange - recovering
    selected: str = "#ffffff"   # White - selected sector


# Predefined color schemes for accessibility
COLOR_SCHEMES: Dict[ColorScheme, SectorMapColors] = {
    ColorScheme.STANDARD: SectorMapColors(
        good="#4ec9b0",
        bad="#f14c4c",
        weak="#f0a030",
        unknown="#3c3c3c",
        reading="#0e639c",
        writing="#9b59b6",
        recovering="#e67e22",
        selected="#ffffff",
    ),
    ColorScheme.DEUTERANOPIA: SectorMapColors(
        good="#0077bb",      # Blue instead of green
        bad="#ee7733",       # Orange instead of red
        weak="#ccbb44",      # Yellow
        unknown="#3c3c3c",
        reading="#33bbee",   # Light blue
        writing="#aa3377",   # Magenta
        recovering="#ee3377", # Pink
        selected="#ffffff",
    ),
    ColorScheme.PROTANOPIA: SectorMapColors(
        good="#0077bb",      # Blue
        bad="#ee7733",       # Orange
        weak="#ccbb44",      # Yellow
        unknown="#3c3c3c",
        reading="#33bbee",
        writing="#aa3377",
        recovering="#ee3377",
        selected="#ffffff",
    ),
    ColorScheme.TRITANOPIA: SectorMapColors(
        good="#009988",      # Teal
        bad="#ee3377",       # Pink/Magenta
        weak="#33bbee",      # Light blue
        unknown="#3c3c3c",
        reading="#0077bb",
        writing="#cc3311",   # Red-orange
        recovering="#ee7733",
        selected="#ffffff",
    ),
    ColorScheme.HIGH_CONTRAST: SectorMapColors(
        good="#00ff00",      # Bright green
        bad="#ff0000",       # Bright red
        weak="#ffff00",      # Bright yellow
        unknown="#404040",
        reading="#00ffff",   # Cyan
        writing="#ff00ff",   # Magenta
        recovering="#ff8000", # Orange
        selected="#ffffff",
    ),
    ColorScheme.MONOCHROME: SectorMapColors(
        good="#ffffff",      # White
        bad="#404040",       # Dark gray
        weak="#a0a0a0",      # Medium gray
        unknown="#606060",
        reading="#c0c0c0",   # Light gray
        writing="#808080",
        recovering="#909090",
        selected="#ffffff",
    ),
}


# =============================================================================
# Settings Dataclasses
# =============================================================================

@dataclass
class DeviceSettings:
    """Device-related settings."""
    default_drive_unit: int = 0              # Default drive (0 or 1)
    motor_timeout: int = 30                  # Seconds to keep motor on after operation
    seek_speed: str = SeekSpeed.NORMAL.value # Seek speed preference
    auto_detect_geometry: bool = True        # Auto-detect disk geometry
    verify_seeks: bool = True                # Verify seek operations
    double_step: bool = False                # Double-step for 40-track drives
    default_rpm: int = 300                   # Expected RPM (300 for HD, 360 for 5.25")

    def get_seek_speed(self) -> SeekSpeed:
        """Get seek speed as enum."""
        try:
            return SeekSpeed(self.seek_speed)
        except ValueError:
            return SeekSpeed.NORMAL


@dataclass
class DisplaySettings:
    """Display and UI settings."""
    theme: str = Theme.DARK.value            # Application theme
    color_scheme: str = ColorScheme.STANDARD.value  # Sector map color scheme
    default_analytics_tab: int = 0           # Default tab in analytics panel
    show_flux_waveform: bool = True          # Show flux waveform by default
    show_tooltips: bool = True               # Show tooltips
    animate_operations: bool = True          # Animate sector map during operations
    show_track_labels: bool = True           # Show track labels on sector map
    sector_map_size: int = 400               # Default sector map size in pixels
    font_size: int = 10                      # UI font size

    def get_theme(self) -> Theme:
        """Get theme as enum."""
        try:
            return Theme(self.theme)
        except ValueError:
            return Theme.DARK

    def get_color_scheme(self) -> ColorScheme:
        """Get color scheme as enum."""
        try:
            return ColorScheme(self.color_scheme)
        except ValueError:
            return ColorScheme.STANDARD

    def get_sector_colors(self) -> SectorMapColors:
        """Get sector map colors for current scheme."""
        scheme = self.get_color_scheme()
        return COLOR_SCHEMES.get(scheme, COLOR_SCHEMES[ColorScheme.STANDARD])


@dataclass
class RecoverySettings:
    """Recovery operation settings."""
    default_recovery_level: str = RecoveryLevel.STANDARD.value
    default_convergence_mode: bool = True    # Use convergence mode by default
    default_passes: int = 5                  # Default fixed passes
    max_passes: int = 50                     # Max passes for convergence mode
    default_multiread: bool = True           # Enable multi-read by default
    multiread_captures: int = 100            # Default flux capture count
    pll_tuning_enabled: bool = False         # Enable PLL parameter tuning
    pll_aggressiveness: int = 50             # PLL tuning effort (0-100)
    bit_slip_recovery: bool = False          # Enable bit-slip recovery
    auto_retry_on_error: bool = True         # Auto-retry failed operations
    preserve_good_sectors: bool = True       # Don't overwrite good sectors

    def get_recovery_level(self) -> RecoveryLevel:
        """Get recovery level as enum."""
        try:
            return RecoveryLevel(self.default_recovery_level)
        except ValueError:
            return RecoveryLevel.STANDARD


@dataclass
class ExportSettings:
    """Export and file settings."""
    default_image_format: str = ExportFormat.IMG.value
    default_flux_format: str = ExportFormat.SCP.value
    default_report_format: str = ReportFormat.HTML.value
    default_export_directory: str = ""       # Empty = use last directory
    last_export_directory: str = ""          # Last used export directory
    last_import_directory: str = ""          # Last used import directory
    auto_name_exports: bool = True           # Auto-generate export filenames
    include_timestamp: bool = True           # Include timestamp in filenames
    compress_exports: bool = False           # Compress exported files
    embed_flux_in_reports: bool = True       # Embed flux data in reports

    def get_image_format(self) -> ExportFormat:
        """Get default image format as enum."""
        try:
            return ExportFormat(self.default_image_format)
        except ValueError:
            return ExportFormat.IMG

    def get_flux_format(self) -> ExportFormat:
        """Get default flux format as enum."""
        try:
            return ExportFormat(self.default_flux_format)
        except ValueError:
            return ExportFormat.SCP

    def get_report_format(self) -> ReportFormat:
        """Get default report format as enum."""
        try:
            return ReportFormat(self.default_report_format)
        except ValueError:
            return ReportFormat.HTML

    def get_export_directory(self) -> Path:
        """Get export directory, defaulting to home if not set."""
        if self.default_export_directory:
            path = Path(self.default_export_directory)
            if path.exists():
                return path
        if self.last_export_directory:
            path = Path(self.last_export_directory)
            if path.exists():
                return path
        return Path.home()


@dataclass
class WindowSettings:
    """Window geometry and layout settings."""
    window_x: int = 100
    window_y: int = 100
    window_width: int = 1400
    window_height: int = 900
    window_maximized: bool = False
    splitter_sizes: List[int] = field(default_factory=lambda: [400, 600])
    panel_collapsed: Dict[str, bool] = field(default_factory=dict)
    last_tab_index: int = 0


@dataclass
class RecentFile:
    """A recent file entry."""
    path: str
    timestamp: str
    file_type: str = "image"  # "image" or "flux"

    @classmethod
    def create(cls, path: str, file_type: str = "image") -> "RecentFile":
        """Create a new recent file entry with current timestamp."""
        return cls(
            path=path,
            timestamp=datetime.now().isoformat(),
            file_type=file_type,
        )


# =============================================================================
# Settings Manager (Singleton)
# =============================================================================

class SettingsSignals(QObject):
    """Qt signals for settings changes."""

    # Emitted when any setting changes
    settings_changed = pyqtSignal(str, object)  # (setting_path, new_value)

    # Category-specific signals
    device_settings_changed = pyqtSignal()
    display_settings_changed = pyqtSignal()
    recovery_settings_changed = pyqtSignal()
    export_settings_changed = pyqtSignal()
    window_settings_changed = pyqtSignal()

    # Specific setting signals
    theme_changed = pyqtSignal(str)
    color_scheme_changed = pyqtSignal(str)


class Settings:
    """
    Singleton settings manager for Floppy Workbench.

    Provides centralized settings management with automatic persistence,
    change notifications, and migration support.

    Usage:
        settings = Settings.instance()
        settings.device.motor_timeout = 60
        settings.save()

        # Or with context manager for auto-save:
        with settings.modify():
            settings.device.motor_timeout = 60
    """

    _instance: Optional["Settings"] = None
    _initialized: bool = False

    # Settings version for migration
    SETTINGS_VERSION = 1

    def __new__(cls) -> "Settings":
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize settings (only runs once due to singleton)."""
        if self._initialized:
            return

        self._initialized = True

        # Initialize settings categories
        self.device = DeviceSettings()
        self.display = DisplaySettings()
        self.recovery = RecoverySettings()
        self.export = ExportSettings()
        self.window = WindowSettings()

        # Recent files list
        self._recent_files: List[RecentFile] = []
        self._max_recent_files: int = 20

        # Qt signals (only if Qt available)
        if HAS_QT:
            self.signals = SettingsSignals()
        else:
            self.signals = None

        # Track if settings have been modified
        self._dirty = False

        # Load settings from file
        self.load()

        logger.info("Settings initialized")

    @classmethod
    def instance(cls) -> "Settings":
        """Get the singleton settings instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None
        cls._initialized = False

    # =========================================================================
    # Persistence
    # =========================================================================

    def load(self) -> bool:
        """
        Load settings from file.

        Returns:
            True if settings were loaded successfully
        """
        settings_file = get_settings_file()

        if not settings_file.exists():
            logger.info(f"Settings file not found: {settings_file}")
            return False

        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check version for migration
            version = data.get('version', 0)
            if version < self.SETTINGS_VERSION:
                data = self._migrate_settings(data, version)

            # Load each category
            if 'device' in data:
                self._load_dataclass(self.device, data['device'])
            if 'display' in data:
                self._load_dataclass(self.display, data['display'])
            if 'recovery' in data:
                self._load_dataclass(self.recovery, data['recovery'])
            if 'export' in data:
                self._load_dataclass(self.export, data['export'])
            if 'window' in data:
                self._load_dataclass(self.window, data['window'])

            logger.info(f"Settings loaded from {settings_file}")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in settings file: {e}")
            # Backup corrupted file
            self._backup_corrupted_file(settings_file)
            return False
        except PermissionError as e:
            logger.error(f"Permission denied reading settings: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return False

    def save(self) -> bool:
        """
        Save settings to file.

        Returns:
            True if settings were saved successfully
        """
        settings_dir = get_settings_dir()
        settings_file = get_settings_file()

        try:
            # Ensure directory exists
            settings_dir.mkdir(parents=True, exist_ok=True)

            # Build settings dictionary
            data = {
                'version': self.SETTINGS_VERSION,
                'saved_at': datetime.now().isoformat(),
                'device': asdict(self.device),
                'display': asdict(self.display),
                'recovery': asdict(self.recovery),
                'export': asdict(self.export),
                'window': asdict(self.window),
            }

            # Write to temp file first, then rename (atomic)
            temp_file = settings_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_file.replace(settings_file)

            self._dirty = False
            logger.info(f"Settings saved to {settings_file}")
            return True

        except PermissionError as e:
            logger.error(f"Permission denied saving settings: {e}")
            return False
        except OSError as e:
            if "No space left" in str(e) or e.errno == 28:
                logger.error("Disk full - cannot save settings")
            else:
                logger.error(f"OS error saving settings: {e}")
            return False
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False

    def _load_dataclass(self, target: Any, data: Dict[str, Any]) -> None:
        """Load data into a dataclass, ignoring unknown fields."""
        for key, value in data.items():
            if hasattr(target, key):
                try:
                    setattr(target, key, value)
                except Exception as e:
                    logger.warning(f"Could not set {key}: {e}")

    def _migrate_settings(self, data: Dict[str, Any], from_version: int) -> Dict[str, Any]:
        """
        Migrate settings from older versions.

        Args:
            data: Settings data dictionary
            from_version: Version of the loaded settings

        Returns:
            Migrated settings data
        """
        logger.info(f"Migrating settings from version {from_version} to {self.SETTINGS_VERSION}")

        # Version 0 -> 1: Initial migration if needed
        if from_version < 1:
            # Add any migration logic here
            pass

        data['version'] = self.SETTINGS_VERSION
        return data

    def _backup_corrupted_file(self, file_path: Path) -> None:
        """Backup a corrupted settings file."""
        try:
            backup_path = file_path.with_suffix('.backup')
            file_path.rename(backup_path)
            logger.info(f"Corrupted settings backed up to {backup_path}")
        except Exception as e:
            logger.error(f"Could not backup corrupted file: {e}")

    # =========================================================================
    # Recent Files
    # =========================================================================

    def load_recent_files(self) -> None:
        """Load recent files list from file."""
        recent_file = get_recent_files_path()

        if not recent_file.exists():
            return

        try:
            with open(recent_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._recent_files = []
            for entry in data.get('files', []):
                if isinstance(entry, dict) and 'path' in entry:
                    self._recent_files.append(RecentFile(
                        path=entry['path'],
                        timestamp=entry.get('timestamp', ''),
                        file_type=entry.get('file_type', 'image'),
                    ))

            logger.debug(f"Loaded {len(self._recent_files)} recent files")

        except Exception as e:
            logger.error(f"Error loading recent files: {e}")

    def save_recent_files(self) -> None:
        """Save recent files list to file."""
        recent_file = get_recent_files_path()

        try:
            settings_dir = get_settings_dir()
            settings_dir.mkdir(parents=True, exist_ok=True)

            data = {
                'files': [asdict(rf) for rf in self._recent_files]
            }

            with open(recent_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving recent files: {e}")

    def add_recent_file(self, path: str, file_type: str = "image") -> None:
        """
        Add a file to the recent files list.

        Args:
            path: File path to add
            file_type: Type of file ("image" or "flux")
        """
        # Remove existing entry for this path
        self._recent_files = [rf for rf in self._recent_files if rf.path != path]

        # Add new entry at the beginning
        self._recent_files.insert(0, RecentFile.create(path, file_type))

        # Trim to max size
        self._recent_files = self._recent_files[:self._max_recent_files]

        # Save immediately
        self.save_recent_files()

    def get_recent_files(self, file_type: Optional[str] = None) -> List[RecentFile]:
        """
        Get recent files list.

        Args:
            file_type: Filter by type ("image" or "flux"), or None for all

        Returns:
            List of recent files
        """
        if file_type is None:
            return list(self._recent_files)
        return [rf for rf in self._recent_files if rf.file_type == file_type]

    def clear_recent_files(self) -> None:
        """Clear the recent files list."""
        self._recent_files = []
        self.save_recent_files()

    # =========================================================================
    # Change Notifications
    # =========================================================================

    def set_device_setting(self, name: str, value: Any) -> None:
        """Set a device setting and emit change signal."""
        if hasattr(self.device, name):
            setattr(self.device, name, value)
            self._dirty = True
            if self.signals:
                self.signals.settings_changed.emit(f'device.{name}', value)
                self.signals.device_settings_changed.emit()

    def set_display_setting(self, name: str, value: Any) -> None:
        """Set a display setting and emit change signal."""
        if hasattr(self.display, name):
            old_value = getattr(self.display, name, None)
            setattr(self.display, name, value)
            self._dirty = True

            if self.signals:
                self.signals.settings_changed.emit(f'display.{name}', value)
                self.signals.display_settings_changed.emit()

                # Emit specific signals
                if name == 'theme' and old_value != value:
                    self.signals.theme_changed.emit(value)
                elif name == 'color_scheme' and old_value != value:
                    self.signals.color_scheme_changed.emit(value)

    def set_recovery_setting(self, name: str, value: Any) -> None:
        """Set a recovery setting and emit change signal."""
        if hasattr(self.recovery, name):
            setattr(self.recovery, name, value)
            self._dirty = True
            if self.signals:
                self.signals.settings_changed.emit(f'recovery.{name}', value)
                self.signals.recovery_settings_changed.emit()

    def set_export_setting(self, name: str, value: Any) -> None:
        """Set an export setting and emit change signal."""
        if hasattr(self.export, name):
            setattr(self.export, name, value)
            self._dirty = True
            if self.signals:
                self.signals.settings_changed.emit(f'export.{name}', value)
                self.signals.export_settings_changed.emit()

    def set_window_setting(self, name: str, value: Any) -> None:
        """Set a window setting and emit change signal."""
        if hasattr(self.window, name):
            setattr(self.window, name, value)
            self._dirty = True
            if self.signals:
                self.signals.settings_changed.emit(f'window.{name}', value)
                self.signals.window_settings_changed.emit()

    # =========================================================================
    # Context Manager
    # =========================================================================

    class _ModifyContext:
        """Context manager for modifying settings with auto-save."""

        def __init__(self, settings: "Settings"):
            self.settings = settings

        def __enter__(self) -> "Settings":
            return self.settings

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            if exc_type is None:
                self.settings.save()

    def modify(self) -> "_ModifyContext":
        """
        Context manager for modifying settings with auto-save.

        Usage:
            with settings.modify():
                settings.device.motor_timeout = 60
                settings.display.theme = "light"
            # Settings automatically saved on exit
        """
        return self._ModifyContext(self)

    # =========================================================================
    # Reset
    # =========================================================================

    def reset_to_defaults(self, category: Optional[str] = None) -> None:
        """
        Reset settings to defaults.

        Args:
            category: Specific category to reset, or None for all
        """
        if category is None or category == 'device':
            self.device = DeviceSettings()
            if self.signals:
                self.signals.device_settings_changed.emit()

        if category is None or category == 'display':
            self.display = DisplaySettings()
            if self.signals:
                self.signals.display_settings_changed.emit()
                self.signals.theme_changed.emit(self.display.theme)
                self.signals.color_scheme_changed.emit(self.display.color_scheme)

        if category is None or category == 'recovery':
            self.recovery = RecoverySettings()
            if self.signals:
                self.signals.recovery_settings_changed.emit()

        if category is None or category == 'export':
            self.export = ExportSettings()
            if self.signals:
                self.signals.export_settings_changed.emit()

        if category is None or category == 'window':
            self.window = WindowSettings()
            if self.signals:
                self.signals.window_settings_changed.emit()

        self._dirty = True
        logger.info(f"Settings reset to defaults: {category or 'all'}")

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_dirty(self) -> bool:
        """Check if settings have been modified since last save."""
        return self._dirty

    @property
    def settings_file(self) -> Path:
        """Get the settings file path."""
        return get_settings_file()


# =============================================================================
# Module-Level Convenience Functions
# =============================================================================

def get_settings() -> Settings:
    """
    Get the global settings instance.

    This is a convenience function equivalent to Settings.instance().

    Returns:
        The singleton Settings instance
    """
    return Settings.instance()


def get_sector_colors() -> SectorMapColors:
    """
    Get the current sector map colors based on settings.

    Returns:
        SectorMapColors for the current color scheme
    """
    settings = get_settings()
    return settings.display.get_sector_colors()


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Enums
    'SeekSpeed',
    'ColorScheme',
    'RecoveryLevel',
    'ExportFormat',
    'ReportFormat',
    'Theme',

    # Dataclasses
    'SectorMapColors',
    'DeviceSettings',
    'DisplaySettings',
    'RecoverySettings',
    'ExportSettings',
    'WindowSettings',
    'RecentFile',

    # Color schemes
    'COLOR_SCHEMES',

    # Signals
    'SettingsSignals',

    # Main class
    'Settings',

    # Convenience functions
    'get_settings',
    'get_sector_colors',
    'get_settings_dir',
    'get_settings_file',
]
