"""
Sound notification system for Floppy Workbench.

Provides audio feedback for operation completion, errors, and other events.
Uses native system sounds for reliability across platforms.

Part of Phase 14: Polish & Professional Touches
"""

import logging
import struct
import wave
import io
import sys
import subprocess
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Dict

from PyQt6.QtCore import QObject, QUrl

# Module logger
logger = logging.getLogger(__name__)

# Platform detection
_IS_WINDOWS = sys.platform == 'win32'
_IS_LINUX = sys.platform.startswith('linux')
_IS_MACOS = sys.platform == 'darwin'

# Windows sound support
if _IS_WINDOWS:
    try:
        import winsound
        _WINSOUND_AVAILABLE = True
    except ImportError:
        _WINSOUND_AVAILABLE = False
        logger.debug("winsound not available")
else:
    _WINSOUND_AVAILABLE = False

# Try to import Qt multimedia (may not be available on all systems)
_AUDIO_AVAILABLE = False
try:
    from PyQt6.QtMultimedia import QSoundEffect, QAudioOutput, QMediaPlayer
    _AUDIO_AVAILABLE = True
except ImportError as e:
    logger.warning("Qt multimedia not available: %s - sound notifications disabled", e)
    # Create stub classes for systems without audio support

    class QSoundEffect:
        """Stub for QSoundEffect when audio is unavailable."""
        def __init__(self, *args, **kwargs): pass
        def setSource(self, *args): pass
        def setVolume(self, *args): pass
        def play(self): pass
        def stop(self): pass
        def isLoaded(self): return False

    class QAudioOutput:
        """Stub for QAudioOutput when audio is unavailable."""
        def __init__(self, *args, **kwargs): pass
        def setVolume(self, *args): pass

    class QMediaPlayer:
        """Stub for QMediaPlayer when audio is unavailable."""
        def __init__(self, *args, **kwargs): pass
        def setAudioOutput(self, *args): pass
        def setSource(self, *args): pass
        def play(self): pass
        def stop(self): pass


# =============================================================================
# Sound Types
# =============================================================================

class SoundType(Enum):
    """Types of sound notifications."""
    OPERATION_COMPLETE = auto()   # Pleasant chime for successful completion
    OPERATION_ERROR = auto()      # Alert sound for errors
    RECOVERY_SUCCESS = auto()     # Triumphant sound when sectors recovered
    WARNING = auto()              # Attention-getting sound for warnings
    CLICK = auto()                # Subtle click for button feedback
    NOTIFICATION = auto()         # General notification sound
    PROGRESS_TICK = auto()        # Subtle tick for progress milestones


# =============================================================================
# Tone Generator
# =============================================================================

class ToneGenerator:
    """
    Generates simple tones programmatically.

    Creates basic waveforms that can be used as fallback sounds
    when sound files are not available.
    """

    SAMPLE_RATE = 44100

    @classmethod
    def generate_sine_wave(
        cls,
        frequency: float,
        duration_ms: int,
        volume: float = 0.5,
        fade_ms: int = 20
    ) -> bytes:
        """
        Generate a sine wave tone.

        Args:
            frequency: Frequency in Hz
            duration_ms: Duration in milliseconds
            volume: Volume (0.0 to 1.0)
            fade_ms: Fade in/out duration in milliseconds

        Returns:
            WAV file data as bytes
        """
        import math

        num_samples = int(cls.SAMPLE_RATE * duration_ms / 1000)
        fade_samples = int(cls.SAMPLE_RATE * fade_ms / 1000)

        samples = []
        for i in range(num_samples):
            # Generate sine wave
            t = i / cls.SAMPLE_RATE
            sample = math.sin(2 * math.pi * frequency * t)

            # Apply fade envelope
            if i < fade_samples:
                sample *= i / fade_samples
            elif i > num_samples - fade_samples:
                sample *= (num_samples - i) / fade_samples

            # Scale by volume and convert to 16-bit
            sample = int(sample * volume * 32767)
            samples.append(sample)

        # Create WAV file in memory
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(cls.SAMPLE_RATE)
            wav.writeframes(struct.pack(f'<{len(samples)}h', *samples))

        return buffer.getvalue()

    @classmethod
    def generate_chime(cls, volume: float = 0.5) -> bytes:
        """Generate a pleasant completion chime."""
        import math

        # Two-note chime (C5 to E5)
        duration_ms = 400
        num_samples = int(cls.SAMPLE_RATE * duration_ms / 1000)
        fade_samples = int(cls.SAMPLE_RATE * 30 / 1000)

        # Frequencies for C5 and E5
        freq1 = 523.25  # C5
        freq2 = 659.25  # E5

        samples = []
        for i in range(num_samples):
            t = i / cls.SAMPLE_RATE
            progress = i / num_samples

            # First note fades out, second note fades in
            note1_vol = max(0, 1 - progress * 2)
            note2_vol = max(0, progress * 2 - 0.5)

            sample = (
                math.sin(2 * math.pi * freq1 * t) * note1_vol +
                math.sin(2 * math.pi * freq2 * t) * note2_vol
            )

            # Apply envelope
            if i < fade_samples:
                sample *= i / fade_samples
            elif i > num_samples - fade_samples:
                sample *= (num_samples - i) / fade_samples

            sample = int(sample * volume * 0.7 * 32767)
            samples.append(sample)

        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(cls.SAMPLE_RATE)
            wav.writeframes(struct.pack(f'<{len(samples)}h', *samples))

        return buffer.getvalue()

    @classmethod
    def generate_error_sound(cls, volume: float = 0.5) -> bytes:
        """Generate an error alert sound."""
        import math

        duration_ms = 300
        num_samples = int(cls.SAMPLE_RATE * duration_ms / 1000)
        fade_samples = int(cls.SAMPLE_RATE * 10 / 1000)

        # Low frequency for error
        frequency = 220  # A3

        samples = []
        for i in range(num_samples):
            t = i / cls.SAMPLE_RATE

            # Add some harmonics for a harsher sound
            sample = (
                math.sin(2 * math.pi * frequency * t) * 0.7 +
                math.sin(2 * math.pi * frequency * 2 * t) * 0.2 +
                math.sin(2 * math.pi * frequency * 3 * t) * 0.1
            )

            # Pulsing envelope
            pulse = 0.5 + 0.5 * math.sin(2 * math.pi * 8 * t)
            sample *= pulse

            # Fade
            if i < fade_samples:
                sample *= i / fade_samples
            elif i > num_samples - fade_samples:
                sample *= (num_samples - i) / fade_samples

            sample = int(sample * volume * 32767)
            samples.append(sample)

        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(cls.SAMPLE_RATE)
            wav.writeframes(struct.pack(f'<{len(samples)}h', *samples))

        return buffer.getvalue()

    @classmethod
    def generate_success_fanfare(cls, volume: float = 0.5) -> bytes:
        """Generate a triumphant success sound."""
        import math

        duration_ms = 600
        num_samples = int(cls.SAMPLE_RATE * duration_ms / 1000)
        fade_samples = int(cls.SAMPLE_RATE * 30 / 1000)

        # Major chord arpeggio: C5 -> E5 -> G5 -> C6
        notes = [
            (523.25, 0.0, 0.4),  # C5
            (659.25, 0.15, 0.4),  # E5
            (783.99, 0.3, 0.4),  # G5
            (1046.5, 0.45, 0.55),  # C6
        ]

        samples = []
        for i in range(num_samples):
            t = i / cls.SAMPLE_RATE
            progress = i / num_samples

            sample = 0
            for freq, start, dur in notes:
                note_progress = (progress - start) / dur
                if 0 <= note_progress <= 1:
                    # Note envelope
                    env = math.sin(note_progress * math.pi) ** 0.5
                    sample += math.sin(2 * math.pi * freq * t) * env * 0.4

            # Overall fade
            if i < fade_samples:
                sample *= i / fade_samples
            elif i > num_samples - fade_samples:
                sample *= (num_samples - i) / fade_samples

            sample = int(sample * volume * 32767)
            samples.append(sample)

        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(cls.SAMPLE_RATE)
            wav.writeframes(struct.pack(f'<{len(samples)}h', *samples))

        return buffer.getvalue()

    @classmethod
    def generate_warning_sound(cls, volume: float = 0.5) -> bytes:
        """Generate an attention-getting warning sound."""
        import math

        duration_ms = 400
        num_samples = int(cls.SAMPLE_RATE * duration_ms / 1000)

        # Two alternating tones
        freq1 = 440  # A4
        freq2 = 554  # C#5

        samples = []
        for i in range(num_samples):
            t = i / cls.SAMPLE_RATE
            progress = i / num_samples

            # Alternate between tones
            if int(progress * 4) % 2 == 0:
                freq = freq1
            else:
                freq = freq2

            sample = math.sin(2 * math.pi * freq * t)

            # Envelope
            env = 1 - abs(progress - 0.5) * 2
            sample *= env

            sample = int(sample * volume * 0.6 * 32767)
            samples.append(sample)

        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(cls.SAMPLE_RATE)
            wav.writeframes(struct.pack(f'<{len(samples)}h', *samples))

        return buffer.getvalue()

    @classmethod
    def generate_click(cls, volume: float = 0.3) -> bytes:
        """Generate a subtle click sound."""
        duration_ms = 30
        num_samples = int(cls.SAMPLE_RATE * duration_ms / 1000)

        samples = []
        for i in range(num_samples):
            progress = i / num_samples

            # White noise burst with quick decay
            import random
            noise = random.random() * 2 - 1
            env = (1 - progress) ** 3

            sample = int(noise * env * volume * 32767)
            samples.append(sample)

        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(cls.SAMPLE_RATE)
            wav.writeframes(struct.pack(f'<{len(samples)}h', *samples))

        return buffer.getvalue()

    @classmethod
    def generate_notification(cls, volume: float = 0.5) -> bytes:
        """Generate a general notification sound."""
        import math

        duration_ms = 200
        num_samples = int(cls.SAMPLE_RATE * duration_ms / 1000)
        fade_samples = int(cls.SAMPLE_RATE * 20 / 1000)

        frequency = 880  # A5

        samples = []
        for i in range(num_samples):
            t = i / cls.SAMPLE_RATE

            sample = math.sin(2 * math.pi * frequency * t)

            # Quick decay
            progress = i / num_samples
            env = (1 - progress) ** 2

            # Fade
            if i < fade_samples:
                sample *= i / fade_samples

            sample = int(sample * env * volume * 32767)
            samples.append(sample)

        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(cls.SAMPLE_RATE)
            wav.writeframes(struct.pack(f'<{len(samples)}h', *samples))

        return buffer.getvalue()

    @classmethod
    def generate_tick(cls, volume: float = 0.2) -> bytes:
        """Generate a subtle progress tick."""
        import math

        duration_ms = 20
        num_samples = int(cls.SAMPLE_RATE * duration_ms / 1000)

        frequency = 1200

        samples = []
        for i in range(num_samples):
            t = i / cls.SAMPLE_RATE
            progress = i / num_samples

            sample = math.sin(2 * math.pi * frequency * t)
            env = (1 - progress) ** 4

            sample = int(sample * env * volume * 32767)
            samples.append(sample)

        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(cls.SAMPLE_RATE)
            wav.writeframes(struct.pack(f'<{len(samples)}h', *samples))

        return buffer.getvalue()


# =============================================================================
# Sound Manager
# =============================================================================

class SoundManager(QObject):
    """
    Singleton sound manager for playing notification sounds.

    Manages sound loading, caching, and playback with volume control.
    """

    _instance: Optional["SoundManager"] = None

    def __new__(cls) -> "SoundManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        super().__init__()
        self._initialized = True

        self._enabled = True
        self._volume = 0.7

        # Sound effects cache
        self._sounds: Dict[SoundType, QSoundEffect] = {}
        self._sound_data: Dict[SoundType, bytes] = {}

        # Initialize sounds
        self._init_sounds()

        logger.info("SoundManager initialized")

    def _init_sounds(self) -> None:
        """Initialize sound effects."""
        # Generate sounds programmatically
        self._sound_data[SoundType.OPERATION_COMPLETE] = ToneGenerator.generate_chime(self._volume)
        self._sound_data[SoundType.OPERATION_ERROR] = (
            ToneGenerator.generate_error_sound(self._volume)
        )
        self._sound_data[SoundType.RECOVERY_SUCCESS] = (
            ToneGenerator.generate_success_fanfare(self._volume)
        )
        self._sound_data[SoundType.WARNING] = ToneGenerator.generate_warning_sound(self._volume)
        self._sound_data[SoundType.CLICK] = ToneGenerator.generate_click(self._volume)
        self._sound_data[SoundType.NOTIFICATION] = ToneGenerator.generate_notification(self._volume)
        self._sound_data[SoundType.PROGRESS_TICK] = ToneGenerator.generate_tick(self._volume)

        # Try to load from files if available
        sounds_dir = self._get_sounds_dir()
        if sounds_dir and sounds_dir.exists():
            self._load_sounds_from_directory(sounds_dir)

    def _get_sounds_dir(self) -> Optional[Path]:
        """Get the sounds directory path."""
        try:
            # Try relative to this module
            module_dir = Path(__file__).parent.parent
            sounds_dir = module_dir / "resources" / "sounds"
            if sounds_dir.exists():
                return sounds_dir
        except Exception:
            pass
        return None

    def _load_sounds_from_directory(self, directory: Path) -> None:
        """Load sound files from a directory."""
        sound_files = {
            SoundType.OPERATION_COMPLETE: ["complete.wav", "chime.wav", "success.wav"],
            SoundType.OPERATION_ERROR: ["error.wav", "alert.wav"],
            SoundType.RECOVERY_SUCCESS: ["fanfare.wav", "triumph.wav"],
            SoundType.WARNING: ["warning.wav", "attention.wav"],
            SoundType.CLICK: ["click.wav", "tap.wav"],
            SoundType.NOTIFICATION: ["notification.wav", "notify.wav"],
            SoundType.PROGRESS_TICK: ["tick.wav"],
        }

        for sound_type, filenames in sound_files.items():
            for filename in filenames:
                filepath = directory / filename
                if filepath.exists():
                    try:
                        with open(filepath, 'rb') as f:
                            self._sound_data[sound_type] = f.read()
                        logger.debug(f"Loaded sound: {filepath}")
                        break
                    except Exception as e:
                        logger.warning(f"Failed to load sound {filepath}: {e}")

    @classmethod
    def instance(cls) -> "SoundManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def enabled(self) -> bool:
        """Check if sounds are enabled."""
        try:
            from floppy_formatter.core.settings import get_settings
            settings = get_settings()
            # Check if sound_enabled exists in settings
            if hasattr(settings.display, 'sound_enabled'):
                return settings.display.sound_enabled
        except Exception:
            pass
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set sounds enabled state."""
        self._enabled = value

    def set_enabled(self, enabled: bool) -> None:
        """Set whether sounds are enabled."""
        self._enabled = enabled

    @property
    def volume(self) -> float:
        """Get current volume (0.0-1.0)."""
        try:
            from floppy_formatter.core.settings import get_settings
            settings = get_settings()
            if hasattr(settings.display, 'sound_volume'):
                return settings.display.sound_volume
        except Exception:
            pass
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        """Set volume (0.0-1.0)."""
        self._volume = max(0.0, min(1.0, value))

    def set_volume(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        self._volume = max(0.0, min(1.0, volume))

    def play_sound(self, sound_type: SoundType) -> None:
        """
        Play a sound effect.

        Args:
            sound_type: The type of sound to play
        """
        if not self.enabled:
            return

        try:
            # Get or create sound effect
            if sound_type not in self._sounds:
                self._create_sound_effect(sound_type)

            effect = self._sounds.get(sound_type)
            if effect:
                effect.setVolume(self.volume)
                effect.play()

        except Exception as e:
            logger.warning(f"Failed to play sound {sound_type}: {e}")

    def _create_sound_effect(self, sound_type: SoundType) -> None:
        """Create a QSoundEffect for the given sound type."""
        if sound_type not in self._sound_data:
            return

        try:
            # Write to temp file (QSoundEffect requires file URL)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(self._sound_data[sound_type])
                temp_path = f.name

            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(temp_path))
            effect.setVolume(self.volume)

            self._sounds[sound_type] = effect

        except Exception as e:
            logger.warning(f"Failed to create sound effect for {sound_type}: {e}")

    def play_operation_complete(self) -> None:
        """Play the operation complete sound."""
        self.play_sound(SoundType.OPERATION_COMPLETE)

    def play_error(self) -> None:
        """Play the error sound."""
        self.play_sound(SoundType.OPERATION_ERROR)

    def play_recovery_success(self) -> None:
        """Play the recovery success sound."""
        self.play_sound(SoundType.RECOVERY_SUCCESS)

    def play_warning(self) -> None:
        """Play the warning sound."""
        self.play_sound(SoundType.WARNING)

    def play_click(self) -> None:
        """Play the click sound."""
        self.play_sound(SoundType.CLICK)

    def play_notification(self) -> None:
        """Play the notification sound."""
        self.play_sound(SoundType.NOTIFICATION)

    def play_tick(self) -> None:
        """Play the progress tick sound."""
        self.play_sound(SoundType.PROGRESS_TICK)


# =============================================================================
# Convenience Functions
# =============================================================================

def get_sound_manager() -> SoundManager:
    """Get the global sound manager instance."""
    return SoundManager.instance()


def play_sound(sound_type: SoundType) -> None:
    """Convenience function to play a sound."""
    get_sound_manager().play_sound(sound_type)


def _play_system_sound(sound_type: str) -> None:
    """
    Play a system sound based on platform.

    Args:
        sound_type: One of 'complete', 'error', 'success', 'warning'
    """
    try:
        if _IS_WINDOWS and _WINSOUND_AVAILABLE:
            # Windows system sounds
            if sound_type == 'error':
                winsound.MessageBeep(winsound.MB_ICONHAND)
            elif sound_type == 'warning':
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif sound_type in ('complete', 'success'):
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            else:
                winsound.MessageBeep(winsound.MB_OK)
        elif _IS_LINUX:
            # Linux - try paplay with freedesktop sounds, fall back to bell
            sound_files = {
                'complete': '/usr/share/sounds/freedesktop/stereo/complete.oga',
                'success': '/usr/share/sounds/freedesktop/stereo/complete.oga',
                'error': '/usr/share/sounds/freedesktop/stereo/dialog-error.oga',
                'warning': '/usr/share/sounds/freedesktop/stereo/dialog-warning.oga',
            }
            sound_file = sound_files.get(sound_type, sound_files['complete'])

            if Path(sound_file).exists():
                subprocess.Popen(
                    ['paplay', sound_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Fall back to terminal bell
                print('\a', end='', flush=True)
        elif _IS_MACOS:
            # macOS - use afplay with system sounds
            sound_files = {
                'complete': '/System/Library/Sounds/Glass.aiff',
                'success': '/System/Library/Sounds/Hero.aiff',
                'error': '/System/Library/Sounds/Basso.aiff',
                'warning': '/System/Library/Sounds/Sosumi.aiff',
            }
            sound_file = sound_files.get(sound_type, sound_files['complete'])

            if Path(sound_file).exists():
                subprocess.Popen(
                    ['afplay', sound_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        else:
            # Unknown platform - try terminal bell
            print('\a', end='', flush=True)
    except Exception as e:
        logger.debug("Could not play system sound: %s", e)


def play_complete_sound() -> None:
    """Play the operation complete sound using system sounds."""
    _play_system_sound('complete')


def play_error_sound() -> None:
    """Play the error sound using system sounds."""
    _play_system_sound('error')


def play_success_sound() -> None:
    """Play the recovery success sound using system sounds."""
    _play_system_sound('success')


def play_warning_sound() -> None:
    """Play the warning sound using system sounds."""
    _play_system_sound('warning')


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Enums
    'SoundType',

    # Classes
    'SoundManager',
    'ToneGenerator',

    # Functions
    'get_sound_manager',
    'play_sound',
    'play_complete_sound',
    'play_error_sound',
    'play_success_sound',
    'play_warning_sound',
]
