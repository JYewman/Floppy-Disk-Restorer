"""
GUI utilities for Floppy Workbench.

This module provides reusable utility classes and functions for
animations, drag-and-drop, and sound notifications.

Part of Phase 14: Polish & Professional Touches
"""

from floppy_formatter.gui.utils.animations import (
    # Settings
    AnimationSettings,
    get_animation_settings,
    animations_enabled,

    # Easing curves
    EasingCurves,

    # Animation classes
    FadeAnimation,
    SlideAnimation,
    ScaleAnimation,
    ProgressAnimation,
    AnimationGroup,
    ShakeAnimation,
    FlashAnimation,

    # Convenience functions
    fade_in_widget,
    fade_out_widget,
    pulse_widget,
    shake_widget,
)

from floppy_formatter.gui.utils.drag_drop import (
    # Constants
    SECTOR_IMAGE_EXTENSIONS,
    FLUX_IMAGE_EXTENSIONS,
    ALL_IMAGE_EXTENSIONS,
    REPORT_EXTENSIONS,

    # Functions
    get_file_type,
    is_valid_image_file,
    is_valid_sector_image,
    is_valid_flux_image,

    # Classes
    DropZoneOverlay,
    DragDropHandler,
    SectorMapDragSource,
    FileDropTarget,
)

from floppy_formatter.gui.utils.sounds import (
    # Enums
    SoundType,

    # Classes
    SoundManager,
    ToneGenerator,

    # Functions
    get_sound_manager,
    play_sound,
    play_complete_sound,
    play_error_sound,
    play_success_sound,
    play_warning_sound,
)


__all__ = [
    # Animation settings
    'AnimationSettings',
    'get_animation_settings',
    'animations_enabled',

    # Easing curves
    'EasingCurves',

    # Animation classes
    'FadeAnimation',
    'SlideAnimation',
    'ScaleAnimation',
    'ProgressAnimation',
    'AnimationGroup',
    'ShakeAnimation',
    'FlashAnimation',

    # Animation convenience functions
    'fade_in_widget',
    'fade_out_widget',
    'pulse_widget',
    'shake_widget',

    # Drag-drop constants
    'SECTOR_IMAGE_EXTENSIONS',
    'FLUX_IMAGE_EXTENSIONS',
    'ALL_IMAGE_EXTENSIONS',
    'REPORT_EXTENSIONS',

    # Drag-drop functions
    'get_file_type',
    'is_valid_image_file',
    'is_valid_sector_image',
    'is_valid_flux_image',

    # Drag-drop classes
    'DropZoneOverlay',
    'DragDropHandler',
    'SectorMapDragSource',
    'FileDropTarget',

    # Sound enums
    'SoundType',

    # Sound classes
    'SoundManager',
    'ToneGenerator',

    # Sound functions
    'get_sound_manager',
    'play_sound',
    'play_complete_sound',
    'play_error_sound',
    'play_success_sound',
    'play_warning_sound',
]
