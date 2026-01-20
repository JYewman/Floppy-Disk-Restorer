"""
Session manager for Floppy Workbench.

This module provides the SessionManager singleton class that manages the
active disk session and session presets. It provides Qt signals for
session changes and persists presets to disk.

Part of Phase 1: Core Data Model
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    HAS_QT = True
except ImportError:
    HAS_QT = False

    class QObject:
        pass

    def pyqtSignal(*args, **kwargs):
        return None

from floppy_formatter.core.session import DiskSession, get_default_session
from floppy_formatter.core.gw_format_registry import GWFormatRegistry
from floppy_formatter.core.settings import get_settings_dir

# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Session Presets File Path
# =============================================================================

def get_presets_file() -> Path:
    """Get the session presets file path."""
    return get_settings_dir() / 'session_presets.json'


# =============================================================================
# Built-in Presets
# =============================================================================

# Built-in presets for common formats
BUILTIN_PRESETS: List[Tuple[str, str]] = [
    # (display_name, gw_format)
    # IBM PC formats
    ('IBM PC 1.44MB HD (3.5")', 'ibm.1440'),
    ('IBM PC 720KB DD (3.5")', 'ibm.720'),
    ('IBM PC 1.2MB HD (5.25")', 'ibm.1200'),
    ('IBM PC 360KB DD (5.25")', 'ibm.360'),
    ('IBM PC 2.88MB ED (3.5")', 'ibm.2880'),
    ('IBM PC 1.68MB DMF', 'ibm.dmf'),

    # Amiga
    ('Amiga 880KB DD', 'amiga.amigados'),
    ('Amiga 1.76MB HD', 'amiga.amigados_hd'),

    # Macintosh
    ('Macintosh 800KB', 'mac.800'),
    ('Macintosh 400KB', 'mac.400'),

    # Apple II
    ('Apple II DOS 3.3', 'apple2.appledos.140'),
    ('Apple II ProDOS', 'apple2.prodos.140'),

    # Commodore
    ('Commodore 1541', 'commodore.1541'),
    ('Commodore 1571', 'commodore.1571'),
    ('Commodore 1581', 'commodore.1581'),

    # Atari ST
    ('Atari ST 720KB', 'atarist.720'),
    ('Atari ST 360KB', 'atarist.360'),

    # Acorn
    ('Acorn DFS Single-Sided', 'acorn.dfs.ss'),
    ('Acorn ADFS 640KB', 'acorn.adfs.640'),

    # ZX Spectrum
    ('ZX Spectrum +3', 'zx.3dos.ds80'),
    ('ZX Spectrum TR-DOS', 'zx.trdos.ds80'),

    # MSX
    ('MSX 720KB', 'msx.2dd'),
    ('MSX 360KB', 'msx.2d'),

    # Other
    ('NEC PC-98 HD', 'pc98.2hd'),
    ('Ensoniq EPS', 'ensoniq.800'),
    ('Akai S-series', 'akai.800'),
]


# =============================================================================
# Session Manager
# =============================================================================

class SessionManager(QObject):
    """
    Singleton manager for the active disk session.

    This class manages the current active session, provides methods for
    creating sessions from various sources, and handles session preset
    persistence.

    Signals:
        session_changed: Emitted when the active session changes

    Example:
        >>> manager = SessionManager.instance()
        >>> manager.set_active_session(DiskSession.from_gw_format('ibm.1440'))
        >>> print(manager.active_session.gw_format)
        'ibm.1440'
    """

    # Qt signal for session changes
    if HAS_QT:
        session_changed = pyqtSignal(object)  # Emits DiskSession or None
    else:
        session_changed = None

    _instance: Optional['SessionManager'] = None

    def __init__(self):
        """Initialize the session manager."""
        # Initialize QObject
        if HAS_QT:
            super().__init__()

        # Active session
        self._active_session: Optional[DiskSession] = None

        # User presets (loaded from file)
        self._user_presets: Dict[str, Dict[str, Any]] = {}

        # Format registry reference
        self._registry: Optional[GWFormatRegistry] = None

        # Load presets from file
        self._load_presets()

        logger.info("SessionManager initialized")

    @classmethod
    def instance(cls) -> 'SessionManager':
        """Get the singleton session manager instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None

    # =========================================================================
    # Active Session Management
    # =========================================================================

    @property
    def active_session(self) -> Optional[DiskSession]:
        """
        Get the currently active session.

        Returns:
            The active DiskSession or None if no session is active
        """
        return self._active_session

    def set_active_session(self, session: Optional[DiskSession]) -> None:
        """
        Set the active session.

        Args:
            session: The session to set as active, or None to clear

        Emits:
            session_changed signal with the new session
        """
        old_session = self._active_session
        self._active_session = session

        if old_session != session:
            logger.info(f"Active session changed: "
                       f"{session.gw_format if session else 'None'}")

            # Emit signal if Qt is available
            if HAS_QT and self.session_changed is not None:
                self.session_changed.emit(session)

    def clear_active_session(self) -> None:
        """Clear the active session."""
        self.set_active_session(None)

    def has_active_session(self) -> bool:
        """Check if there is an active session."""
        return self._active_session is not None

    # =========================================================================
    # Session Creation
    # =========================================================================

    def create_session_from_gw_format(self, gw_format: str,
                                       name: Optional[str] = None) -> DiskSession:
        """
        Create a session from a Greaseweazle format string.

        Args:
            gw_format: Greaseweazle format string (e.g., 'ibm.1440')
            name: Optional custom name for the session

        Returns:
            New DiskSession instance

        Raises:
            ValueError: If the format is not found
        """
        return DiskSession.from_gw_format(gw_format, name)

    def get_default_session(self) -> DiskSession:
        """
        Get the default session (IBM PC 1.44MB HD 3.5").

        Returns:
            Default DiskSession instance
        """
        return get_default_session()

    def create_and_activate_session(self, gw_format: str,
                                     name: Optional[str] = None) -> DiskSession:
        """
        Create a session from a format and set it as active.

        Args:
            gw_format: Greaseweazle format string
            name: Optional custom name

        Returns:
            The created and activated DiskSession
        """
        session = self.create_session_from_gw_format(gw_format, name)
        self.set_active_session(session)
        return session

    # =========================================================================
    # Format Registry Access
    # =========================================================================

    @property
    def format_registry(self) -> GWFormatRegistry:
        """Get the format registry instance."""
        if self._registry is None:
            self._registry = GWFormatRegistry.instance()
        return self._registry

    def get_available_platforms(self) -> List[Dict[str, Any]]:
        """
        Get all available platforms.

        Returns:
            List of platform dictionaries
        """
        return self.format_registry.get_all_platforms()

    def get_formats_for_platform(self, platform: str) -> List[Dict[str, Any]]:
        """
        Get all formats for a platform.

        Args:
            platform: Platform ID

        Returns:
            List of format dictionaries
        """
        return self.format_registry.get_formats_for_platform(platform)

    def get_format_info(self, gw_format: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific format.

        Args:
            gw_format: Greaseweazle format string

        Returns:
            Format dictionary or None
        """
        return self.format_registry.get_format_info(gw_format)

    # =========================================================================
    # Preset Management
    # =========================================================================

    def save_preset(self, name: str, session: Optional[DiskSession] = None) -> bool:
        """
        Save a session as a user preset.

        Args:
            name: Preset name
            session: Session to save (defaults to active session)

        Returns:
            True if saved successfully

        Raises:
            ValueError: If no session provided and no active session
        """
        if session is None:
            session = self._active_session
            if session is None:
                raise ValueError("No session to save")

        # Store preset data
        self._user_presets[name] = {
            'name': name,
            'session': session.to_dict(),
            'created_at': datetime.now().isoformat(),
        }

        # Persist to file
        success = self._save_presets()

        if success:
            logger.info(f"Preset saved: {name}")
        else:
            logger.error(f"Failed to save preset: {name}")

        return success

    def load_preset(self, name: str) -> Optional[DiskSession]:
        """
        Load a session from a user preset.

        Args:
            name: Preset name

        Returns:
            Loaded DiskSession or None if not found
        """
        preset_data = self._user_presets.get(name)
        if preset_data is None:
            logger.warning(f"Preset not found: {name}")
            return None

        try:
            session_data = preset_data.get('session', {})
            session = DiskSession.from_dict(session_data)
            logger.info(f"Preset loaded: {name}")
            return session
        except Exception as e:
            logger.error(f"Error loading preset {name}: {e}")
            return None

    def load_and_activate_preset(self, name: str) -> Optional[DiskSession]:
        """
        Load a preset and set it as the active session.

        Args:
            name: Preset name

        Returns:
            Loaded DiskSession or None if not found
        """
        session = self.load_preset(name)
        if session:
            self.set_active_session(session)
        return session

    def list_presets(self) -> List[str]:
        """
        Get a list of user preset names.

        Returns:
            List of preset names
        """
        return list(self._user_presets.keys())

    def delete_preset(self, name: str) -> bool:
        """
        Delete a user preset.

        Args:
            name: Preset name

        Returns:
            True if deleted successfully
        """
        if name not in self._user_presets:
            return False

        del self._user_presets[name]
        success = self._save_presets()

        if success:
            logger.info(f"Preset deleted: {name}")
        else:
            logger.error(f"Failed to delete preset: {name}")

        return success

    def get_preset_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a preset without loading it.

        Args:
            name: Preset name

        Returns:
            Preset info dictionary or None
        """
        preset_data = self._user_presets.get(name)
        if preset_data is None:
            return None

        session_data = preset_data.get('session', {})
        return {
            'name': name,
            'gw_format': session_data.get('gw_format', 'unknown'),
            'platform': session_data.get('platform', 'unknown'),
            'created_at': preset_data.get('created_at', ''),
        }

    def get_builtin_presets(self) -> List[Tuple[str, DiskSession]]:
        """
        Get all built-in presets.

        Returns:
            List of tuples (display_name, DiskSession)
        """
        presets = []
        for display_name, gw_format in BUILTIN_PRESETS:
            try:
                session = self.format_registry.session_from_format(gw_format, display_name)
                presets.append((display_name, session))
            except Exception as e:
                logger.warning(f"Could not create builtin preset {display_name}: {e}")
        return presets

    def get_builtin_preset_names(self) -> List[str]:
        """
        Get names of all built-in presets.

        Returns:
            List of builtin preset display names
        """
        return [name for name, _ in BUILTIN_PRESETS]

    def load_builtin_preset(self, name: str) -> Optional[DiskSession]:
        """
        Load a built-in preset by name.

        Args:
            name: Built-in preset display name

        Returns:
            DiskSession or None if not found
        """
        for display_name, gw_format in BUILTIN_PRESETS:
            if display_name == name:
                try:
                    return self.format_registry.session_from_format(gw_format, display_name)
                except Exception as e:
                    logger.error(f"Error loading builtin preset {name}: {e}")
                    return None
        return None

    # =========================================================================
    # Preset Persistence
    # =========================================================================

    def _load_presets(self) -> bool:
        """
        Load user presets from file.

        Returns:
            True if loaded successfully
        """
        presets_file = get_presets_file()

        if not presets_file.exists():
            logger.debug("No presets file found")
            return True

        try:
            with open(presets_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._user_presets = data.get('presets', {})
            logger.info(f"Loaded {len(self._user_presets)} user presets")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in presets file: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading presets: {e}")
            return False

    def _save_presets(self) -> bool:
        """
        Save user presets to file.

        Returns:
            True if saved successfully
        """
        presets_file = get_presets_file()

        try:
            # Ensure directory exists
            presets_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'version': 1,
                'saved_at': datetime.now().isoformat(),
                'presets': self._user_presets,
            }

            # Write to temp file first, then rename (atomic)
            temp_file = presets_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_file.replace(presets_file)

            logger.debug(f"Presets saved to {presets_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving presets: {e}")
            return False

    # =========================================================================
    # Recent Sessions
    # =========================================================================

    def add_to_recent_sessions(self, session: DiskSession) -> None:
        """
        Add a session to the recent sessions list.

        This updates the SessionSettings with the recent session.

        Args:
            session: Session to add to recent list
        """
        try:
            from floppy_formatter.core.settings import Settings
            settings = Settings.instance()

            # Get current recent sessions
            if hasattr(settings, 'session') and hasattr(settings.session, 'recent_sessions'):
                recent = list(settings.session.recent_sessions)
            else:
                recent = []

            # Remove if already in list
            gw_format = session.gw_format
            recent = [r for r in recent if r != gw_format]

            # Add to front
            recent.insert(0, gw_format)

            # Trim to max
            max_recent = 10
            if hasattr(settings, 'session') and hasattr(settings.session, 'max_recent_sessions'):
                max_recent = settings.session.max_recent_sessions
            recent = recent[:max_recent]

            # Save back
            if hasattr(settings, 'session'):
                settings.session.recent_sessions = recent
                settings.save()

        except Exception as e:
            logger.warning(f"Could not update recent sessions: {e}")

    def get_recent_sessions(self) -> List[DiskSession]:
        """
        Get recent sessions.

        Returns:
            List of recent DiskSession instances
        """
        sessions = []
        try:
            from floppy_formatter.core.settings import Settings
            settings = Settings.instance()

            if hasattr(settings, 'session') and hasattr(settings.session, 'recent_sessions'):
                for gw_format in settings.session.recent_sessions:
                    try:
                        session = self.create_session_from_gw_format(gw_format)
                        sessions.append(session)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Could not get recent sessions: {e}")

        return sessions

    # =========================================================================
    # Validation
    # =========================================================================

    def is_valid_format(self, gw_format: str) -> bool:
        """
        Check if a format string is valid.

        Args:
            gw_format: Greaseweazle format string

        Returns:
            True if format is valid and available
        """
        return self.format_registry.get_format_info(gw_format) is not None

    def validate_session(self, session: DiskSession) -> Tuple[bool, Optional[str]]:
        """
        Validate a session configuration.

        Args:
            session: Session to validate

        Returns:
            Tuple of (valid, error_message)
        """
        # Check basic parameters
        if session.cylinders <= 0:
            return False, "Invalid cylinder count"
        if session.heads <= 0 or session.heads > 2:
            return False, "Invalid head count"
        if session.sectors_per_track <= 0:
            return False, "Invalid sectors per track"
        if session.bytes_per_sector <= 0:
            return False, "Invalid bytes per sector"
        if session.rpm <= 0:
            return False, "Invalid RPM"

        # Check that format exists
        if not self.is_valid_format(session.gw_format):
            return False, f"Unknown format: {session.gw_format}"

        return True, None


# =============================================================================
# Module-Level Convenience Functions
# =============================================================================

def get_session_manager() -> SessionManager:
    """
    Get the global session manager instance.

    Returns:
        The singleton SessionManager instance
    """
    return SessionManager.instance()


def get_active_session() -> Optional[DiskSession]:
    """
    Get the currently active session.

    Returns:
        The active DiskSession or None
    """
    return SessionManager.instance().active_session


def set_active_session(session: DiskSession) -> None:
    """
    Set the active session.

    Args:
        session: Session to activate
    """
    SessionManager.instance().set_active_session(session)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'SessionManager',
    'BUILTIN_PRESETS',
    'get_session_manager',
    'get_active_session',
    'set_active_session',
    'get_presets_file',
]
