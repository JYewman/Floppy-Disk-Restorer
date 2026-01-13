"""
Floppy disk image import/export module.

This module provides comprehensive support for reading, writing, and
converting floppy disk images in both sector-level and flux-level formats.

Supported Formats:
    Sector-Level:
        - IMG/IMA: Raw sector images (no header)
        - DSK: CPC/Spectrum DSK format with header

    Flux-Level:
        - SCP: SuperCard Pro flux image
        - HFE: HxC Floppy Emulator format

Key Features:
    - Format detection and metadata extraction
    - Sector-level read/write access
    - Flux-level track operations
    - Format conversion (sector <-> flux)
    - Image comparison tools
    - Disk read/write operations

Part of Phase 11: Image Import/Export

Example Usage:
    # Load and read a sector image
    from floppy_formatter.imaging import SectorImage
    image = SectorImage("disk.img")
    data = image.get_sector(0, 0, 1)

    # Convert between formats
    from floppy_formatter.imaging import convert_format
    convert_format("disk.img", "disk.scp")

    # Read disk to image
    from floppy_formatter.imaging import read_disk_to_image
    metadata = read_disk_to_image(device, "backup.scp", ImageFormat.SCP)
"""

# Import from image_formats
from .image_formats import (
    # Exceptions
    ImageError,
    ImageFormatError,
    ImageCorruptError,
    ImageGeometryError,
    ImageReadError,
    ImageWriteError,
    # Enums
    ImageFormat,
    # Data classes
    ImageMetadata,
    # Functions
    detect_format,
    read_metadata,
    validate_image,
    get_supported_extensions,
    get_format_for_extension,
    is_flux_format,
    is_sector_format,
    get_expected_size,
    # Constants
    STANDARD_GEOMETRIES,
    SCP_MAGIC,
    HFE_MAGIC,
    DSK_MAGIC,
)

# Import from sector_image
from .sector_image import (
    SectorImage,
    ImageComparison,
    compare_images,
    DEFAULT_FILL_BYTE,
    HD_35_GEOMETRY,
    DD_35_GEOMETRY,
    HD_525_GEOMETRY,
    DD_525_GEOMETRY,
)

# Import from flux_image
from .flux_image import (
    # Classes
    FluxImage,
    SCPImage,
    HFEImage,
    # Data classes
    SCPHeader,
    HFEHeader,
    WriteResult,
    # Conversion functions
    convert_sector_to_flux,
    convert_flux_to_sector,
    convert_format,
    # Disk operations
    read_disk_to_image,
    write_image_to_disk,
    compare_image_to_disk,
    # Constants
    SCP_HEADER_SIZE,
    HFE_HEADER_SIZE,
    DEFAULT_SAMPLE_FREQ,
)


__all__ = [
    # ==========================================================================
    # Exceptions
    # ==========================================================================
    'ImageError',
    'ImageFormatError',
    'ImageCorruptError',
    'ImageGeometryError',
    'ImageReadError',
    'ImageWriteError',

    # ==========================================================================
    # Enums
    # ==========================================================================
    'ImageFormat',

    # ==========================================================================
    # Data Classes
    # ==========================================================================
    'ImageMetadata',
    'ImageComparison',
    'SCPHeader',
    'HFEHeader',
    'WriteResult',

    # ==========================================================================
    # Image Classes
    # ==========================================================================
    'SectorImage',
    'FluxImage',
    'SCPImage',
    'HFEImage',

    # ==========================================================================
    # Format Detection & Metadata
    # ==========================================================================
    'detect_format',
    'read_metadata',
    'validate_image',
    'get_supported_extensions',
    'get_format_for_extension',
    'is_flux_format',
    'is_sector_format',
    'get_expected_size',

    # ==========================================================================
    # Conversion Functions
    # ==========================================================================
    'convert_sector_to_flux',
    'convert_flux_to_sector',
    'convert_format',

    # ==========================================================================
    # Disk Operations
    # ==========================================================================
    'read_disk_to_image',
    'write_image_to_disk',
    'compare_image_to_disk',

    # ==========================================================================
    # Comparison Functions
    # ==========================================================================
    'compare_images',

    # ==========================================================================
    # Constants
    # ==========================================================================
    'DEFAULT_FILL_BYTE',
    'DEFAULT_SAMPLE_FREQ',
    'SCP_HEADER_SIZE',
    'HFE_HEADER_SIZE',
    'SCP_MAGIC',
    'HFE_MAGIC',
    'DSK_MAGIC',
    'STANDARD_GEOMETRIES',
    'HD_35_GEOMETRY',
    'DD_35_GEOMETRY',
    'HD_525_GEOMETRY',
    'DD_525_GEOMETRY',
]


# =============================================================================
# Module-Level Convenience Functions
# =============================================================================

def open_image(filepath: str):
    """
    Open any supported image file.

    Auto-detects format and returns appropriate image class.

    Args:
        filepath: Path to image file

    Returns:
        SectorImage or FluxImage subclass

    Example:
        image = open_image("disk.img")  # Returns SectorImage
        image = open_image("disk.scp")  # Returns SCPImage
    """
    format_type = detect_format(filepath)

    if is_flux_format(format_type):
        return FluxImage.open(filepath)
    else:
        return SectorImage(filepath)


def create_blank_image(format_type: ImageFormat,
                       cylinders: int = 80,
                       heads: int = 2,
                       **kwargs):
    """
    Create a new blank image.

    Args:
        format_type: Desired image format
        cylinders: Number of cylinders
        heads: Number of heads
        **kwargs: Format-specific options

    Returns:
        New image instance

    Example:
        # Create blank sector image
        image = create_blank_image(ImageFormat.IMG, 80, 2)

        # Create blank flux image with 3 revolutions
        image = create_blank_image(ImageFormat.SCP, 80, 2, revolutions=3)
    """
    if format_type in (ImageFormat.IMG, ImageFormat.IMA, ImageFormat.DSK):
        image = SectorImage()
        sectors_per_track = kwargs.get('sectors_per_track', 18)
        sector_size = kwargs.get('sector_size', 512)
        fill_byte = kwargs.get('fill_byte', DEFAULT_FILL_BYTE)
        image.create_blank(cylinders, heads, sectors_per_track, sector_size, fill_byte)
        return image

    elif format_type == ImageFormat.SCP:
        image = SCPImage()
        revolutions = kwargs.get('revolutions', 2)
        image.create_blank(cylinders, heads, revolutions)
        return image

    elif format_type == ImageFormat.HFE:
        image = HFEImage()
        bit_rate = kwargs.get('bit_rate', 250000)
        image.create_blank(cylinders, heads, bit_rate)
        return image

    else:
        raise ImageFormatError(f"Cannot create blank image for format: {format_type.name}")


# Add convenience functions to __all__
__all__.extend([
    'open_image',
    'create_blank_image',
])
