"""
Resource management utilities for Floppy Workbench GUI.

Provides utilities for loading icons, reading application version,
and managing user settings persistence.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtGui import QIcon, QPixmap

# Configure logger
logger = logging.getLogger(__name__)

# Paths
RESOURCES_DIR = Path(__file__).parent
ICONS_DIR = RESOURCES_DIR / "icons"
CONFIG_DIR = Path.home() / ".config" / "floppy_formatter"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# Version cache
_cached_version: Optional[str] = None


def get_icon(name: str, fallback: bool = True) -> QIcon:
    """
    Load an icon from the icons directory.

    Args:
        name: Icon name without extension (e.g., "search" for "search.svg")
        fallback: If True, return empty QIcon on failure instead of raising

    Returns:
        QIcon object, or empty QIcon if not found and fallback is True

    Raises:
        FileNotFoundError: If icon not found and fallback is False
    """
    # Try SVG first, then PNG
    for ext in (".svg", ".png"):
        icon_path = ICONS_DIR / f"{name}{ext}"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                return icon
            logger.warning(f"Icon file exists but failed to load: {icon_path}")

    # Icon not found
    if fallback:
        logger.warning(f"Icon not found: {name} (falling back to empty icon)")
        return QIcon()
    else:
        raise FileNotFoundError(f"Icon not found: {name}")


def get_icon_path(name: str) -> Optional[Path]:
    """
    Get the path to an icon file.

    Args:
        name: Icon name without extension

    Returns:
        Path to icon file, or None if not found
    """
    for ext in (".svg", ".png"):
        icon_path = ICONS_DIR / f"{name}{ext}"
        if icon_path.exists():
            return icon_path
    return None


def get_icon_pixmap(name: str, size: int = 24) -> QPixmap:
    """
    Load an icon as a QPixmap with specified size.

    Args:
        name: Icon name without extension
        size: Desired size in pixels (width and height)

    Returns:
        QPixmap scaled to specified size, or empty QPixmap if not found
    """
    icon = get_icon(name, fallback=True)
    if icon.isNull():
        return QPixmap()
    return icon.pixmap(size, size)


def get_version() -> str:
    """
    Get the application version from pyproject.toml.

    Reads the version once and caches it for subsequent calls.
    Falls back to a hardcoded version if the file cannot be read.

    Returns:
        Version string (e.g., "0.2.0")
    """
    global _cached_version

    if _cached_version is not None:
        return _cached_version

    # Default version if reading fails
    fallback_version = "0.2.0"

    # Find pyproject.toml (walk up from resources directory)
    current = Path(__file__).parent
    pyproject_path = None

    for _ in range(10):  # Limit search depth
        candidate = current / "pyproject.toml"
        if candidate.exists():
            pyproject_path = candidate
            break
        parent = current.parent
        if parent == current:  # Reached root
            break
        current = parent

    if pyproject_path is None:
        logger.warning("pyproject.toml not found, using fallback version")
        _cached_version = fallback_version
        return _cached_version

    try:
        # Try tomllib (Python 3.11+) first
        try:
            import tomllib
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
        except ImportError:
            # Fall back to reading manually for Python 3.10
            with open(pyproject_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Simple parsing for version line
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("version"):
                        # Parse: version = "0.2.0"
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            version_str = parts[1].strip().strip('"').strip("'")
                            _cached_version = version_str
                            return _cached_version
                logger.warning("Version not found in pyproject.toml")
                _cached_version = fallback_version
                return _cached_version

        # Extract version from parsed TOML
        version = data.get("tool", {}).get("poetry", {}).get("version")
        if version:
            _cached_version = version
            return _cached_version

        logger.warning("Version key not found in pyproject.toml")
        _cached_version = fallback_version
        return _cached_version

    except Exception as e:
        logger.warning(f"Error reading pyproject.toml: {e}")
        _cached_version = fallback_version
        return _cached_version


def get_settings() -> Dict[str, Any]:
    """
    Load user settings from the config file.

    Creates the config directory if it doesn't exist.
    Returns default settings if file doesn't exist or is corrupted.

    Returns:
        Dictionary of settings
    """
    default_settings = {
        "theme": "dark",
    }

    if not SETTINGS_FILE.exists():
        return default_settings.copy()

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)

        # Validate settings structure
        if not isinstance(settings, dict):
            logger.warning("Settings file corrupted (not a dict), using defaults")
            return default_settings.copy()

        # Merge with defaults (in case new settings were added)
        merged = default_settings.copy()
        merged.update(settings)
        return merged

    except json.JSONDecodeError as e:
        logger.warning(f"Settings file corrupted: {e}, using defaults")
        return default_settings.copy()
    except Exception as e:
        logger.warning(f"Error reading settings: {e}, using defaults")
        return default_settings.copy()


def save_settings(settings: Dict[str, Any]) -> bool:
    """
    Save user settings to the config file.

    Creates the config directory if it doesn't exist.

    Args:
        settings: Dictionary of settings to save

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Create config directory if it doesn't exist
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Write settings
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

        return True

    except PermissionError as e:
        logger.warning(f"Permission denied writing settings: {e}")
        return False
    except Exception as e:
        logger.warning(f"Error saving settings: {e}")
        return False


def get_setting(key: str, default: Any = None) -> Any:
    """
    Get a specific setting value.

    Args:
        key: Setting key to retrieve
        default: Default value if key doesn't exist

    Returns:
        Setting value or default
    """
    settings = get_settings()
    return settings.get(key, default)


def set_setting(key: str, value: Any) -> bool:
    """
    Set a specific setting value.

    Args:
        key: Setting key to set
        value: Value to store

    Returns:
        True if saved successfully, False otherwise
    """
    settings = get_settings()
    settings[key] = value
    return save_settings(settings)


def get_theme() -> str:
    """
    Get the current theme setting.

    Returns:
        Theme name ("dark" or "light")
    """
    theme = get_setting("theme", "dark")
    if theme not in ("dark", "light"):
        return "dark"
    return theme


def set_theme(theme: str) -> bool:
    """
    Set the theme setting.

    Args:
        theme: Theme name ("dark" or "light")

    Returns:
        True if saved successfully, False otherwise
    """
    if theme not in ("dark", "light"):
        logger.warning(f"Invalid theme: {theme}, defaulting to dark")
        theme = "dark"
    return set_setting("theme", theme)


__all__ = [
    "get_icon",
    "get_icon_path",
    "get_icon_pixmap",
    "get_version",
    "get_settings",
    "save_settings",
    "get_setting",
    "set_setting",
    "get_theme",
    "set_theme",
    "RESOURCES_DIR",
    "ICONS_DIR",
    "CONFIG_DIR",
    "SETTINGS_FILE",
]
