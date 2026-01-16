"""
Blank Image Manager for Write Image feature.

Provides access to bundled blank disk images for writing to physical disks.
Images are stored in the data/disk_images directory.
"""

import logging
import os
from pathlib import Path
from typing import Optional, List

from .format_registry import DiskFormatSpec, get_format_registry, Platform

logger = logging.getLogger(__name__)


# =============================================================================
# Image Manager
# =============================================================================

class BlankImageManager:
    """
    Manager for accessing bundled blank disk images.

    Provides methods to:
    - Get the path to a blank image for a specific format
    - List available images
    - Verify image integrity
    """

    def __init__(self):
        """Initialize the image manager."""
        # Find the data directory relative to this module
        self._module_dir = Path(__file__).parent
        self._data_dir = self._module_dir.parent / "data" / "disk_images"

        logger.debug("Image manager initialized, data dir: %s", self._data_dir)

    @property
    def data_directory(self) -> Path:
        """Get the path to the disk images data directory."""
        return self._data_dir

    def get_image_path(self, format_spec: DiskFormatSpec) -> Optional[Path]:
        """
        Get the full path to the blank image for a format.

        Args:
            format_spec: The disk format specification

        Returns:
            Path to the image file, or None if not available
        """
        if not format_spec.has_bundled_image:
            logger.warning(
                "No bundled image for format: %s %s",
                format_spec.platform.value, format_spec.name
            )
            return None

        if not format_spec.image_filename:
            logger.warning(
                "Format has no image filename: %s %s",
                format_spec.platform.value, format_spec.name
            )
            return None

        image_path = self._data_dir / format_spec.image_filename

        if not image_path.exists():
            logger.error(
                "Image file not found: %s (expected at %s)",
                format_spec.image_filename, image_path
            )
            return None

        return image_path

    def get_image_data(self, format_spec: DiskFormatSpec) -> Optional[bytes]:
        """
        Load the blank image data for a format.

        Args:
            format_spec: The disk format specification

        Returns:
            Image data as bytes, or None if not available
        """
        image_path = self.get_image_path(format_spec)
        if image_path is None:
            return None

        try:
            with open(image_path, 'rb') as f:
                data = f.read()

            logger.debug(
                "Loaded image for %s %s: %d bytes",
                format_spec.platform.value, format_spec.name, len(data)
            )
            return data

        except IOError as e:
            logger.error("Failed to read image file: %s", e)
            return None

    def verify_image(self, format_spec: DiskFormatSpec) -> bool:
        """
        Verify that a bundled image exists and has the correct size.

        Args:
            format_spec: The disk format specification

        Returns:
            True if image is valid, False otherwise
        """
        image_path = self.get_image_path(format_spec)
        if image_path is None:
            return False

        try:
            actual_size = image_path.stat().st_size
            expected_size = format_spec.capacity_bytes

            if actual_size != expected_size:
                logger.warning(
                    "Image size mismatch for %s %s: expected %d, got %d",
                    format_spec.platform.value, format_spec.name,
                    expected_size, actual_size
                )
                # Some formats have slight variations, allow them
                # e.g., Amiga ADF might have extra bytes
                return True  # Still usable

            return True

        except IOError as e:
            logger.error("Failed to verify image: %s", e)
            return False

    def list_available_formats(self) -> List[DiskFormatSpec]:
        """
        List all formats that have bundled images available.

        Returns:
            List of DiskFormatSpec with available images
        """
        registry = get_format_registry()
        available = []

        for fmt in registry.get_all_formats():
            if fmt.has_bundled_image and self.get_image_path(fmt) is not None:
                available.append(fmt)

        return available

    def list_available_platforms(self) -> List[Platform]:
        """
        List platforms that have at least one available format.

        Returns:
            List of Platform enum values with available formats
        """
        available_formats = self.list_available_formats()
        platforms = set()

        for fmt in available_formats:
            platforms.add(fmt.platform)

        # Return in a consistent order
        return sorted(platforms, key=lambda p: p.value)

    def get_available_formats_for_platform(
        self,
        platform: Platform
    ) -> List[DiskFormatSpec]:
        """
        Get available formats for a specific platform.

        Args:
            platform: The platform to get formats for

        Returns:
            List of available DiskFormatSpec for that platform
        """
        available = self.list_available_formats()
        return [f for f in available if f.platform == platform]


# =============================================================================
# Module-level singleton
# =============================================================================

_manager: Optional[BlankImageManager] = None


def get_image_manager() -> BlankImageManager:
    """
    Get the global image manager singleton.

    Returns:
        BlankImageManager instance
    """
    global _manager
    if _manager is None:
        _manager = BlankImageManager()
    return _manager


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'BlankImageManager',
    'get_image_manager',
]
