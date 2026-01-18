"""
Sound resources for Floppy Workbench.

This directory contains optional sound files for audio notifications.
If sound files are not present, the application will generate tones
programmatically as a fallback.

Expected sound files (WAV format):
- complete.wav      - Operation complete notification
- error.wav         - Error notification
- success.wav       - Success/recovery notification
- warning.wav       - Warning notification
- click.wav         - UI click feedback
- notification.wav  - General notification
- progress.wav      - Progress tick sound

Sound files should be:
- Format: WAV (PCM, 16-bit)
- Sample rate: 44100 Hz (recommended)
- Duration: Short (< 2 seconds)
- Volume: Normalized to avoid clipping

Part of Phase 14: Polish & Professional Touches
"""

from pathlib import Path

# Sound directory path
SOUNDS_DIR = Path(__file__).parent

# Expected sound files
SOUND_FILES = {
    'complete': 'complete.wav',
    'error': 'error.wav',
    'success': 'success.wav',
    'warning': 'warning.wav',
    'click': 'click.wav',
    'notification': 'notification.wav',
    'progress': 'progress.wav',
}


def get_sound_path(sound_name: str) -> Path:
    """
    Get path to a sound file.

    Args:
        sound_name: Name of sound (without extension)

    Returns:
        Path to sound file (may not exist)
    """
    filename = SOUND_FILES.get(sound_name, f"{sound_name}.wav")
    return SOUNDS_DIR / filename


def sound_exists(sound_name: str) -> bool:
    """
    Check if a sound file exists.

    Args:
        sound_name: Name of sound (without extension)

    Returns:
        True if sound file exists
    """
    return get_sound_path(sound_name).exists()


def list_available_sounds() -> list:
    """
    List all available sound files.

    Returns:
        List of sound names that have files present
    """
    return [name for name in SOUND_FILES if sound_exists(name)]
