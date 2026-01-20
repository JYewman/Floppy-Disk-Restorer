"""
Forensic analysis for Greaseweazle flux captures.

This module provides advanced forensic analysis capabilities for
floppy disk preservation and copy protection research, including:

- Copy protection detection and identification
- Format type analysis (standard vs non-standard)
- Deleted/overwritten data recovery
- Flux capture comparison and diff analysis

These tools are essential for:
- Disk preservation and archival
- Understanding historical copy protection schemes
- Recovering data from partially overwritten disks
- Verifying disk duplication quality

Key Classes:
    CopyProtectionResult: Copy protection analysis findings
    FormatAnalysis: Disk format characteristics
    DeletedSector: Recovered overwritten sector data
    FluxComparison: Detailed comparison of two captures

Key Functions:
    detect_copy_protection: Identify protection schemes
    analyze_format_type: Determine standard vs non-standard format
    extract_deleted_data: Recover overwritten sectors
    compare_flux_captures: Detailed diff analysis
"""

import statistics
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Tuple, TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from floppy_formatter.analysis.flux_analyzer import FluxCapture

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Standard track length in microseconds (at 300 RPM = 200ms per revolution)
STANDARD_TRACK_US = 200_000

# Standard sector count for various formats
PC_HD_SECTORS = 18
PC_DD_SECTORS = 9
AMIGA_SECTORS = 11

# Copy protection signatures
WEAK_BIT_THRESHOLD = 0.3  # Variance threshold for weak bit detection
LONG_TRACK_THRESHOLD = 1.05  # Track > 105% of standard
SHORT_TRACK_THRESHOLD = 0.95  # Track < 95% of standard

# Data field address marks
DATA_MARK_NORMAL = 0xFB    # Normal data
DATA_MARK_DELETED = 0xF8   # Deleted data mark


# =============================================================================
# Enums
# =============================================================================

class ProtectionType(Enum):
    """Types of copy protection schemes."""
    NONE = auto()                   # No protection detected
    WEAK_BITS = auto()              # Intentional weak/unstable bits
    LONG_TRACK = auto()             # Track longer than standard
    SHORT_TRACK = auto()            # Track shorter than standard
    NON_STANDARD_FORMAT = auto()    # Non-standard sector layout
    FUZZY_BITS = auto()             # Bits that read differently each time
    TIMING_PROTECTION = auto()      # Specific timing requirements
    DENSITY_VARIATION = auto()      # Mixed HD/DD on same disk
    SPIRAL_TRACK = auto()           # Data spans multiple tracks
    LASER_HOLE = auto()             # Physical media modification
    MULTIPLE_SCHEMES = auto()       # Combination of protection types
    UNKNOWN = auto()                # Unidentified protection


class FormatType(Enum):
    """Disk format types."""
    PC_HD_MFM = auto()        # IBM PC 1.44MB HD MFM
    PC_DD_MFM = auto()        # IBM PC 720KB DD MFM
    PC_HD_FM = auto()         # PC HD FM (rare)
    AMIGA_DD = auto()         # Amiga 880KB
    AMIGA_HD = auto()         # Amiga 1.76MB
    ATARI_ST = auto()         # Atari ST format
    APPLE_GCR = auto()        # Apple II GCR
    COMMODORE_GCR = auto()    # Commodore 64/128 GCR
    MAC_GCR = auto()          # Macintosh 400K/800K GCR
    RAW_MFM = auto()          # MFM but non-standard layout
    RAW_FM = auto()           # FM but non-standard layout
    MIXED = auto()            # Mixed formats on disk
    UNKNOWN = auto()          # Unable to determine


class SectorMarkType(Enum):
    """Type of sector data address mark."""
    NORMAL = auto()       # Standard data (0xFB)
    DELETED = auto()      # Deleted data mark (0xF8)
    MISSING = auto()      # No valid mark found
    UNKNOWN = auto()      # Unrecognized mark


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ProtectionSignature:
    """
    Signature of a detected copy protection element.

    Attributes:
        protection_type: Type of protection detected
        location_us: Position in track (microseconds from index)
        strength: How strong/clear the protection is (0.0-1.0)
        description: Human-readable description
        raw_data: Optional raw data associated with protection
    """
    protection_type: ProtectionType
    location_us: float
    strength: float
    description: str
    raw_data: Optional[bytes] = None


@dataclass
class CopyProtectionResult:
    """
    Complete copy protection analysis result.

    Contains all detected protection schemes and their characteristics
    for a disk or track.

    Attributes:
        is_protected: Whether any protection was detected
        protection_types: List of detected protection types
        signatures: Detailed signatures for each protection element
        confidence: Overall confidence in detection (0.0-1.0)
        complexity_score: How complex the protection is (1-10)
        known_scheme: Name of known protection if identified
        description: Human-readable summary
        cylinder: Cylinder analyzed (-1 if full disk)
        head: Head analyzed (-1 if full disk)
        recommendations: Recommendations for copying/preservation
    """
    is_protected: bool
    protection_types: List[ProtectionType]
    signatures: List[ProtectionSignature]
    confidence: float
    complexity_score: int
    known_scheme: Optional[str]
    description: str
    cylinder: int = -1
    head: int = -1
    recommendations: List[str] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get one-line summary of protection status."""
        if not self.is_protected:
            return "No copy protection detected"

        types_str = ", ".join(t.name for t in self.protection_types[:3])
        if len(self.protection_types) > 3:
            types_str += f" (+{len(self.protection_types) - 3} more)"

        return f"Protected: {types_str} (complexity: {self.complexity_score}/10)"


@dataclass
class SectorInfo:
    """Information about a single sector from format analysis."""
    sector_number: int
    cylinder: int
    head: int
    size_bytes: int
    position_us: float
    mark_type: SectorMarkType
    crc_valid: bool
    encoding: str  # "MFM", "FM", "GCR"
    gap_after_us: float


@dataclass
class FormatAnalysis:
    """
    Disk format analysis result.

    Contains detailed information about the disk format including
    sector layout, encoding type, and any non-standard elements.

    Attributes:
        format_type: Detected format type
        encoding: Primary encoding (MFM/FM/GCR)
        sectors_per_track: Number of sectors per track
        bytes_per_sector: Sector size in bytes
        track_length_us: Actual track length in microseconds
        track_length_ratio: Ratio to standard length
        sector_interleave: Sector interleave factor
        sectors: Detailed info for each sector found
        is_standard: Whether format matches a standard
        deviations: List of deviations from standard format
        cylinder: Cylinder analyzed
        head: Head analyzed
        confidence: Confidence in analysis (0.0-1.0)
    """
    format_type: FormatType
    encoding: str
    sectors_per_track: int
    bytes_per_sector: int
    track_length_us: float
    track_length_ratio: float
    sector_interleave: int
    sectors: List[SectorInfo]
    is_standard: bool
    deviations: List[str]
    cylinder: int
    head: int
    confidence: float

    def get_capacity_estimate(self, total_cylinders: int = 80, heads: int = 2) -> int:
        """
        Estimate total disk capacity based on format.

        Args:
            total_cylinders: Number of cylinders (default 80)
            heads: Number of heads (default 2)

        Returns:
            Estimated capacity in bytes
        """
        return self.sectors_per_track * self.bytes_per_sector * total_cylinders * heads

    def matches_format(self, format_type: FormatType) -> bool:
        """Check if analysis matches a specific format type."""
        return self.format_type == format_type


@dataclass
class DeletedSector:
    """
    Recovered deleted/overwritten sector data.

    When a sector is overwritten, remnants of the old data may
    remain in the flux transitions due to imperfect erasure.
    This class represents recovered data from such sectors.

    Attributes:
        cylinder: Cylinder number
        head: Head number
        sector: Sector number
        original_data: Recovered original data (may be partial)
        current_data: Currently visible data
        recovery_confidence: Confidence in recovered data (0.0-1.0)
        recovered_bytes: Number of bytes successfully recovered
        total_bytes: Total sector size
        was_deleted_mark: Whether sector had deleted data mark
        flux_analysis: Additional flux analysis data
    """
    cylinder: int
    head: int
    sector: int
    original_data: bytes
    current_data: bytes
    recovery_confidence: float
    recovered_bytes: int
    total_bytes: int
    was_deleted_mark: bool
    flux_analysis: Dict[str, Any] = field(default_factory=dict)

    @property
    def recovery_percentage(self) -> float:
        """Calculate percentage of data recovered."""
        if self.total_bytes == 0:
            return 0.0
        return (self.recovered_bytes / self.total_bytes) * 100

    def has_differences(self) -> bool:
        """Check if original and current data differ."""
        return self.original_data != self.current_data


@dataclass
class FluxDifference:
    """Single difference point between two flux captures."""
    position_us: float
    flux1_timing_us: float
    flux2_timing_us: float
    difference_us: float
    significance: str  # "minor", "moderate", "significant"


@dataclass
class FluxComparison:
    """
    Detailed comparison between two flux captures.

    Useful for verifying disk duplication quality, detecting
    changes over time, or comparing different reads of the
    same track.

    Attributes:
        match_percentage: Overall match percentage (0-100)
        timing_correlation: Correlation coefficient for timing
        total_transitions_1: Transitions in first capture
        total_transitions_2: Transitions in second capture
        transition_difference: Difference in transition count
        mean_timing_diff_us: Average timing difference
        max_timing_diff_us: Maximum timing difference
        differences: List of significant differences
        regions_match: Number of matching regions
        regions_differ: Number of differing regions
        is_same_source: Whether captures appear from same source
        quality_assessment: Quality comparison assessment
    """
    match_percentage: float
    timing_correlation: float
    total_transitions_1: int
    total_transitions_2: int
    transition_difference: int
    mean_timing_diff_us: float
    max_timing_diff_us: float
    differences: List[FluxDifference]
    regions_match: int
    regions_differ: int
    is_same_source: bool
    quality_assessment: str

    def get_summary(self) -> str:
        """Get one-line comparison summary."""
        return (
            f"Match: {self.match_percentage:.1f}% - "
            f"Correlation: {self.timing_correlation:.3f} - "
            f"{self.regions_differ} differing regions"
        )

    def is_identical(self, threshold: float = 99.0) -> bool:
        """Check if captures are essentially identical."""
        return self.match_percentage >= threshold


# =============================================================================
# Analysis Functions
# =============================================================================

def detect_copy_protection(
    flux: 'FluxCapture',
    additional_captures: Optional[List['FluxCapture']] = None
) -> CopyProtectionResult:
    """
    Identify copy protection schemes in flux data.

    Analyzes flux capture for various copy protection indicators
    including weak bits, unusual timing, long/short tracks, and
    non-standard formats.

    Args:
        flux: Primary FluxCapture to analyze
        additional_captures: Optional additional captures for
                            weak bit detection (need 2+ reads)

    Returns:
        CopyProtectionResult with detected protection schemes

    Example:
        >>> captures = [read_track(device, cyl, head) for _ in range(5)]
        >>> result = detect_copy_protection(captures[0], captures[1:])
        >>> if result.is_protected:
        ...     print(f"Protection detected: {result.get_summary()}")
        ...     for sig in result.signatures:
        ...         print(f"  - {sig.description}")
    """
    from floppy_formatter.analysis.flux_analyzer import detect_encoding_type
    from floppy_formatter.analysis.signal_quality import detect_weak_bits

    protection_types = []
    signatures = []
    recommendations = []

    # Get timing data
    times_us = flux.get_timings_microseconds()
    if not times_us:
        return CopyProtectionResult(
            is_protected=False,
            protection_types=[ProtectionType.NONE],
            signatures=[],
            confidence=0.0,
            complexity_score=0,
            known_scheme=None,
            description="No data to analyze",
            cylinder=flux.cylinder,
            head=flux.head,
        )

    # Convert to numpy for fast operations
    times_np = np.array(times_us, dtype=np.float64)

    # Check track length (numpy sum is ~100x faster)
    track_length = float(np.sum(times_np))
    track_ratio = track_length / STANDARD_TRACK_US

    if track_ratio > LONG_TRACK_THRESHOLD:
        protection_types.append(ProtectionType.LONG_TRACK)
        signatures.append(ProtectionSignature(
            protection_type=ProtectionType.LONG_TRACK,
            location_us=0.0,
            strength=(track_ratio - 1.0) / 0.1,  # Strength based on excess
            description=f"Long track: {track_ratio:.1%} of standard length",
        ))
        recommendations.append("Use raw flux capture for preservation")

    elif track_ratio < SHORT_TRACK_THRESHOLD:
        protection_types.append(ProtectionType.SHORT_TRACK)
        signatures.append(ProtectionSignature(
            protection_type=ProtectionType.SHORT_TRACK,
            location_us=0.0,
            strength=(1.0 - track_ratio) / 0.1,
            description=f"Short track: {track_ratio:.1%} of standard length",
        ))

    # Check for weak bits
    if additional_captures:
        all_captures = [flux] + additional_captures
        weak_bits = detect_weak_bits(all_captures)

        # Look for clusters of weak bits (intentional protection)
        if weak_bits:
            critical_weak = [wb for wb in weak_bits if wb.is_critical()]

            if len(critical_weak) > 20:
                # Many weak bits suggest intentional protection
                protection_types.append(ProtectionType.WEAK_BITS)
                signatures.append(ProtectionSignature(
                    protection_type=ProtectionType.WEAK_BITS,
                    location_us=critical_weak[0].position_us,
                    strength=min(1.0, len(critical_weak) / 50),
                    description=f"{len(critical_weak)} intentional weak bits detected",
                ))
                recommendations.append("Use multiple captures for weak bit recovery")

            # Check for fuzzy bits (extreme variance)
            fuzzy_bits = [wb for wb in weak_bits if wb.variance > 0.5]
            if fuzzy_bits:
                protection_types.append(ProtectionType.FUZZY_BITS)
                signatures.append(ProtectionSignature(
                    protection_type=ProtectionType.FUZZY_BITS,
                    location_us=fuzzy_bits[0].position_us,
                    strength=min(1.0, len(fuzzy_bits) / 20),
                    description=f"{len(fuzzy_bits)} fuzzy/unstable bits detected",
                ))

    # Check for timing-based protection
    timing_protection = _check_timing_protection(times_us)
    if timing_protection:
        protection_types.append(ProtectionType.TIMING_PROTECTION)
        signatures.append(timing_protection)
        recommendations.append("Preserve exact timing for compatibility")

    # Check for non-standard format
    encoding_type, encoding_conf = detect_encoding_type(flux)
    format_analysis = analyze_format_type(flux)

    if not format_analysis.is_standard:
        protection_types.append(ProtectionType.NON_STANDARD_FORMAT)
        signatures.append(ProtectionSignature(
            protection_type=ProtectionType.NON_STANDARD_FORMAT,
            location_us=0.0,
            strength=1.0 - format_analysis.confidence,
            description=f"Non-standard format: {', '.join(format_analysis.deviations[:3])}",
        ))
        recommendations.append("Analyze format before attempting standard decode")

    # Determine if protected and calculate metrics
    is_protected = len(protection_types) > 0 and ProtectionType.NONE not in protection_types

    if not is_protected:
        protection_types = [ProtectionType.NONE]

    # Calculate complexity score (1-10)
    complexity = min(10, len(protection_types) * 2 + len(signatures))

    # Calculate confidence
    if signatures:
        confidence = statistics.mean(s.strength for s in signatures)
    else:
        confidence = 0.0 if is_protected else 1.0

    # Try to identify known protection scheme
    known_scheme = _identify_known_scheme(protection_types, signatures)

    # Generate description
    if not is_protected:
        description = "No copy protection detected - standard format"
    else:
        description = f"Copy protection detected: {', '.join(t.name for t in protection_types)}"

    if not recommendations:
        recommendations.append("Standard copy methods should work")

    return CopyProtectionResult(
        is_protected=is_protected,
        protection_types=protection_types,
        signatures=signatures,
        confidence=confidence,
        complexity_score=complexity,
        known_scheme=known_scheme,
        description=description,
        cylinder=flux.cylinder,
        head=flux.head,
        recommendations=recommendations,
    )


def analyze_format_type(
    flux: 'FluxCapture',
    expected_format: Optional[FormatType] = None
) -> FormatAnalysis:
    """
    Determine disk format (standard vs non-standard).

    Analyzes the flux capture to identify the disk format type,
    including sector layout, encoding, and any deviations from
    standard formats.

    Args:
        flux: FluxCapture to analyze
        expected_format: Optional expected format for comparison

    Returns:
        FormatAnalysis with format details

    Example:
        >>> analysis = analyze_format_type(capture)
        >>> print(f"Format: {analysis.format_type.name}")
        >>> if not analysis.is_standard:
        ...     print("Deviations from standard:")
        ...     for dev in analysis.deviations:
        ...         print(f"  - {dev}")
    """
    from floppy_formatter.analysis.flux_analyzer import (
        detect_encoding_type, generate_histogram_numpy
    )

    times_us = flux.get_timings_microseconds()
    deviations = []

    if not times_us:
        return FormatAnalysis(
            format_type=FormatType.UNKNOWN,
            encoding="Unknown",
            sectors_per_track=0,
            bytes_per_sector=0,
            track_length_us=0.0,
            track_length_ratio=0.0,
            sector_interleave=0,
            sectors=[],
            is_standard=False,
            deviations=["No flux data"],
            cylinder=flux.cylinder,
            head=flux.head,
            confidence=0.0,
        )

    # Convert to numpy for fast operations
    times_np = np.array(times_us, dtype=np.float64)

    # Detect encoding type
    encoding_type, encoding_conf = detect_encoding_type(flux)
    encoding_str = encoding_type.name if encoding_type else "Unknown"

    # Calculate track length (numpy sum is ~100x faster)
    track_length = float(np.sum(times_np))
    track_ratio = track_length / STANDARD_TRACK_US

    # Analyze histogram for format detection (using fast numpy version)
    histogram = generate_histogram_numpy(times_np)

    # Use histogram to determine HD vs DD based on timing peaks
    # HD (1.44MB) has bit cell ~2us, DD (720KB) has bit cell ~4us
    peak_positions = histogram.get('peak_positions', []) if isinstance(histogram, dict) else []
    histogram_suggests_hd = False
    if peak_positions and len(peak_positions) >= 2:
        # Check if peaks suggest HD timing (primary peak around 2us, secondary around 4us)
        primary_peak = min(peak_positions) if peak_positions else 0
        histogram_suggests_hd = primary_peak < 3.0

    # Determine format based on encoding and timing
    sectors_per_track = 0
    bytes_per_sector = 512
    format_type = FormatType.UNKNOWN

    # Adjust confidence based on histogram analysis and encoding detection confidence
    analysis_confidence = encoding_conf

    if encoding_str == "MFM":
        # Check for PC format based on track timing
        if 0.95 <= track_ratio <= 1.05:
            # Standard length track
            # HD has 18 sectors, DD has 9
            mean_timing = float(np.mean(times_np))

            # Use both mean timing and histogram for HD/DD determination
            timing_suggests_hd = mean_timing < 7.0
            if timing_suggests_hd and histogram_suggests_hd:
                sectors_per_track = 18
                format_type = FormatType.PC_HD_MFM
                analysis_confidence = min(1.0, encoding_conf + 0.1)  # Boost confidence
            elif not timing_suggests_hd and not histogram_suggests_hd:
                sectors_per_track = 9
                format_type = FormatType.PC_DD_MFM
                analysis_confidence = min(1.0, encoding_conf + 0.1)  # Boost confidence
            elif timing_suggests_hd:
                # Timing suggests HD but histogram doesn't confirm
                sectors_per_track = 18
                format_type = FormatType.PC_HD_MFM
                analysis_confidence = max(0.5, encoding_conf - 0.1)
            else:
                sectors_per_track = 9
                format_type = FormatType.PC_DD_MFM
                analysis_confidence = max(0.5, encoding_conf - 0.1)
        else:
            format_type = FormatType.RAW_MFM
            deviations.append(f"Non-standard track length: {track_ratio:.1%}")
            analysis_confidence = max(0.3, encoding_conf - 0.2)

    elif encoding_str == "FM":
        format_type = FormatType.RAW_FM
        sectors_per_track = 9  # Typical FM
        deviations.append("FM encoding (rare for 3.5\" disks)")
        analysis_confidence = encoding_conf * 0.9  # Slightly lower for unusual format

    elif encoding_str == "GCR":
        # Could be Apple, Mac, or Commodore
        format_type = FormatType.APPLE_GCR
        deviations.append("GCR encoding detected")
        analysis_confidence = encoding_conf * 0.8  # Lower for ambiguous GCR

    # Check for non-standard track length
    if track_ratio > 1.05:
        deviations.append(f"Long track: {track_ratio:.1%} of standard")
    elif track_ratio < 0.95:
        deviations.append(f"Short track: {track_ratio:.1%} of standard")

    # Extract sector information
    sectors = _extract_sector_info(flux, encoding_str)

    if sectors:
        # Verify sector count
        actual_sector_count = len(sectors)
        if sectors_per_track > 0 and actual_sector_count != sectors_per_track:
            deviations.append(f"Expected {sectors_per_track} sectors, found {actual_sector_count}")
            sectors_per_track = actual_sector_count

        # Check for deleted data marks
        deleted_sectors = [s for s in sectors if s.mark_type == SectorMarkType.DELETED]
        if deleted_sectors:
            deviations.append(f"{len(deleted_sectors)} sectors have deleted data marks")

        # Determine interleave
        sector_interleave = _calculate_interleave(sectors)
    else:
        sector_interleave = 1

    # Determine if standard format
    is_standard = len(deviations) == 0

    # If expected format provided, check for match
    if expected_format and format_type != expected_format:
        deviations.append(f"Expected {expected_format.name}, detected {format_type.name}")
        is_standard = False

    return FormatAnalysis(
        format_type=format_type,
        encoding=encoding_str,
        sectors_per_track=sectors_per_track,
        bytes_per_sector=bytes_per_sector,
        track_length_us=track_length,
        track_length_ratio=track_ratio,
        sector_interleave=sector_interleave,
        sectors=sectors,
        is_standard=is_standard,
        deviations=deviations,
        cylinder=flux.cylinder,
        head=flux.head,
        confidence=analysis_confidence,
    )


def extract_deleted_data(
    flux: 'FluxCapture',
    additional_captures: Optional[List['FluxCapture']] = None
) -> List[DeletedSector]:
    """
    Recover data from deleted or overwritten sectors.

    When sectors are overwritten, remnants of the original data
    may remain in the flux transitions. This function attempts
    to recover such data by analyzing multiple captures and
    looking for inconsistent bits.

    Args:
        flux: Primary FluxCapture to analyze
        additional_captures: Optional additional captures for
                            better recovery

    Returns:
        List of DeletedSector with recovered data

    Example:
        >>> captures = [read_track(device, cyl, head) for _ in range(10)]
        >>> deleted = extract_deleted_data(captures[0], captures[1:])
        >>> for sector in deleted:
        ...     print(f"Sector {sector.sector}: {sector.recovery_percentage:.0f}% recovered")
        ...     if sector.has_differences():
        ...         print("  Original data differs from current!")
    """
    from floppy_formatter.hardware import decode_flux_data

    deleted_sectors = []

    # First, decode sectors to find deleted data marks
    try:
        from floppy_formatter.hardware import FluxData

        # Convert FluxCapture to FluxData for decoding
        # Handle both FluxCapture (sample_rate) and FluxData (sample_freq)
        sample_freq = getattr(flux, 'sample_freq', None) or getattr(flux, 'sample_rate', 72_000_000)
        flux_times = getattr(flux, 'flux_times', None) or getattr(flux, 'raw_timings', [])

        flux_data = FluxData(
            flux_times=flux_times,
            sample_freq=sample_freq,
            index_positions=flux.index_positions,
            cylinder=flux.cylinder,
            head=flux.head,
            index_cued=getattr(flux, 'index_cued', True),
        )
        sectors = decode_flux_data(flux_data)
    except Exception as e:
        logger.warning("Could not decode sectors: %s", e)
        sectors = []

    # Look for sectors with deleted data marks
    for sector in sectors:
        # Check for deleted data mark indicator
        # This would be set during MFM decoding based on address mark
        is_deleted_mark = getattr(sector, 'deleted_mark', False)

        if is_deleted_mark or (sector.data and len(sector.data) > 0):
            # Attempt to recover original data from weak bits
            original_data, confidence = _recover_overwritten_data(
                flux, sector, additional_captures
            )

            if confidence > 0.1:  # Some recovery was possible
                deleted_sectors.append(DeletedSector(
                    cylinder=flux.cylinder,
                    head=flux.head,
                    sector=sector.sector,
                    original_data=original_data,
                    current_data=sector.data if sector.data else bytes(),
                    recovery_confidence=confidence,
                    recovered_bytes=len(original_data),
                    total_bytes=512,
                    was_deleted_mark=is_deleted_mark,
                    flux_analysis={
                        'sector_position': getattr(sector, 'position', 0),
                        'crc_valid': sector.crc_valid,
                    },
                ))

    # Also check for data in gaps or unusual positions
    gap_data = _scan_for_hidden_data(flux)
    for gap_sector in gap_data:
        deleted_sectors.append(gap_sector)

    return deleted_sectors


def compare_flux_captures(
    flux1: 'FluxCapture',
    flux2: 'FluxCapture',
    tolerance_us: float = 0.5
) -> FluxComparison:
    """
    Perform detailed comparison of two flux captures.

    Compares two captures of the same (or similar) tracks to
    identify differences. Useful for:
    - Verifying disk duplication quality
    - Detecting disk degradation over time
    - Identifying weak bits through multiple reads

    Args:
        flux1: First FluxCapture
        flux2: Second FluxCapture
        tolerance_us: Timing tolerance in microseconds

    Returns:
        FluxComparison with detailed diff analysis

    Example:
        >>> original = read_track(device, 0, 0)
        >>> copy = read_track_from_copy(device, 0, 0)
        >>> comparison = compare_flux_captures(original, copy)
        >>> print(comparison.get_summary())
        >>> if not comparison.is_identical():
        ...     print(f"Found {len(comparison.differences)} differences")
    """
    times1 = flux1.get_timings_microseconds()
    times2 = flux2.get_timings_microseconds()

    if not times1 or not times2:
        return FluxComparison(
            match_percentage=0.0,
            timing_correlation=0.0,
            total_transitions_1=len(times1),
            total_transitions_2=len(times2),
            transition_difference=abs(len(times1) - len(times2)),
            mean_timing_diff_us=float('inf'),
            max_timing_diff_us=float('inf'),
            differences=[],
            regions_match=0,
            regions_differ=1,
            is_same_source=False,
            quality_assessment="Insufficient data for comparison",
        )

    # Align captures by finding best offset
    offset, correlation = _find_best_alignment(times1, times2)

    # Apply offset for comparison
    if offset > 0:
        times2 = times2[offset:]
    elif offset < 0:
        times1 = times1[-offset:]

    # Compare aligned sequences
    min_len = min(len(times1), len(times2))
    differences = []
    matches = 0
    timing_diffs = []

    cumulative_pos = 0.0
    for i in range(min_len):
        diff = abs(times1[i] - times2[i])
        timing_diffs.append(diff)
        cumulative_pos += times1[i]

        if diff <= tolerance_us:
            matches += 1
        else:
            # Significant difference
            significance = "minor"
            if diff > tolerance_us * 2:
                significance = "moderate"
            if diff > tolerance_us * 4:
                significance = "significant"

            differences.append(FluxDifference(
                position_us=cumulative_pos,
                flux1_timing_us=times1[i],
                flux2_timing_us=times2[i],
                difference_us=diff,
                significance=significance,
            ))

    # Calculate statistics
    match_percentage = (matches / min_len * 100) if min_len > 0 else 0.0
    mean_diff = statistics.mean(timing_diffs) if timing_diffs else 0.0
    max_diff = max(timing_diffs) if timing_diffs else 0.0

    # Count matching/differing regions
    regions_match = 0
    regions_differ = 0
    in_match_region = True

    for i in range(min_len):
        if timing_diffs[i] <= tolerance_us:
            if not in_match_region:
                regions_match += 1
                in_match_region = True
        else:
            if in_match_region:
                regions_differ += 1
                in_match_region = False

    # Final region
    if in_match_region:
        regions_match += 1
    else:
        regions_differ += 1

    # Determine if same source
    is_same_source = (
        match_percentage > 95.0 and
        correlation > 0.95 and
        abs(len(times1) - len(times2)) < min(len(times1), len(times2)) * 0.05
    )

    # Quality assessment
    if match_percentage >= 99.0:
        assessment = "Excellent match - captures are virtually identical"
    elif match_percentage >= 95.0:
        assessment = "Good match - minor timing variations"
    elif match_percentage >= 80.0:
        assessment = "Fair match - some significant differences"
    elif match_percentage >= 50.0:
        assessment = "Poor match - many differences detected"
    else:
        assessment = "No match - captures appear to be different tracks"

    return FluxComparison(
        match_percentage=match_percentage,
        timing_correlation=correlation,
        total_transitions_1=len(flux1.raw_timings),
        total_transitions_2=len(flux2.raw_timings),
        transition_difference=abs(len(flux1.raw_timings) - len(flux2.raw_timings)),
        mean_timing_diff_us=mean_diff,
        max_timing_diff_us=max_diff,
        differences=differences[:100],  # Limit to first 100 differences
        regions_match=regions_match,
        regions_differ=regions_differ,
        is_same_source=is_same_source,
        quality_assessment=assessment,
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _check_timing_protection(times_us: List[float]) -> Optional[ProtectionSignature]:
    """
    Check for timing-based copy protection.

    Uses numpy for fast sliding window analysis (~1000x faster than pure Python).

    Returns:
        ProtectionSignature if timing protection detected, None otherwise
    """
    if len(times_us) < 1000:
        return None

    # Convert to numpy for fast operations
    times_np = np.array(times_us, dtype=np.float64)

    # Look for unusual timing patterns
    # Timing protection often uses specific gap lengths

    # Use numpy sliding window for efficient mean/std calculation
    window_size = 50
    n = len(times_np)

    # Create sliding window view using stride tricks (very fast, no copy)
    # This creates a view where each row is a window of window_size elements
    shape = (n - window_size + 1, window_size)
    strides = (times_np.strides[0], times_np.strides[0])
    windows = np.lib.stride_tricks.as_strided(times_np, shape=shape, strides=strides)

    # Calculate mean and std for all windows at once (vectorized)
    means = np.mean(windows, axis=1)
    stds = np.std(windows, axis=1, ddof=1)

    # Find windows with extremely tight timing (std < 0.1 and mean > 10.0)
    tight_timing_mask = (stds < 0.1) & (means > 10.0)

    # Check if any window matches
    if np.any(tight_timing_mask):
        # Find the first occurrence
        first_idx = int(np.argmax(tight_timing_mask))
        # Calculate cumulative position up to this point
        cumulative = float(np.sum(times_np[:first_idx]))
        return ProtectionSignature(
            protection_type=ProtectionType.TIMING_PROTECTION,
            location_us=cumulative,
            strength=0.8,
            description=f"Precise timing region at {cumulative:.0f}us",
        )

    return None


def _identify_known_scheme(
    protection_types: List[ProtectionType],
    signatures: List[ProtectionSignature]
) -> Optional[str]:
    """
    Attempt to identify a known copy protection scheme.

    Returns:
        Name of known scheme if identified, None otherwise
    """
    # Check for common protection combinations
    type_set = set(protection_types)

    if ProtectionType.WEAK_BITS in type_set:
        if ProtectionType.LONG_TRACK in type_set:
            return "Possibly Copylock / Dungeon Master style"
        return "Weak bit protection (common in various schemes)"

    if ProtectionType.LONG_TRACK in type_set:
        if ProtectionType.NON_STANDARD_FORMAT in type_set:
            return "Possibly Rob Northen Copylock"
        return "Long track protection"

    if ProtectionType.TIMING_PROTECTION in type_set:
        return "Timing-based protection"

    return None


def _extract_sector_info(flux: 'FluxCapture', encoding: str) -> List[SectorInfo]:
    """
    Extract detailed sector information from flux capture.

    Returns:
        List of SectorInfo for each detected sector
    """
    sectors = []

    try:
        from floppy_formatter.hardware import FluxData, decode_flux_data

        # Handle both FluxCapture (sample_rate) and FluxData (sample_freq)
        sample_freq = getattr(flux, 'sample_freq', None) or getattr(flux, 'sample_rate', 72_000_000)
        flux_times = getattr(flux, 'flux_times', None) or getattr(flux, 'raw_timings', [])

        flux_data = FluxData(
            flux_times=flux_times,
            sample_freq=sample_freq,
            index_positions=flux.index_positions,
            cylinder=flux.cylinder,
            head=flux.head,
            index_cued=getattr(flux, 'index_cued', True),
        )

        decoded = decode_flux_data(flux_data)

        # Convert to SectorInfo
        times_us = flux.get_timings_microseconds()
        # Calculate track length once (not inside loop)
        track_length = float(np.sum(np.array(times_us, dtype=np.float64))) if times_us else 0.0
        sector_spacing = track_length / 18 if track_length > 0 else 0.0

        for sector in decoded:
            # Estimate position (rough approximation)
            estimated_pos = sector.sector * sector_spacing

            mark_type = SectorMarkType.NORMAL
            if not sector.data:
                mark_type = SectorMarkType.MISSING
            elif getattr(sector, 'deleted_mark', False):
                mark_type = SectorMarkType.DELETED

            sectors.append(SectorInfo(
                sector_number=sector.sector,
                cylinder=sector.cylinder,
                head=sector.head,
                size_bytes=len(sector.data) if sector.data else 0,
                position_us=estimated_pos,
                mark_type=mark_type,
                crc_valid=sector.crc_valid,
                encoding=encoding,
                gap_after_us=0.0,  # Would need detailed gap analysis
            ))

    except Exception as e:
        logger.debug("Could not extract sector info: %s", e)

    return sectors


def _calculate_interleave(sectors: List[SectorInfo]) -> int:
    """
    Calculate sector interleave factor.

    Returns:
        Interleave factor (1 = no interleave)
    """
    if len(sectors) < 2:
        return 1

    # Sort by position
    sorted_sectors = sorted(sectors, key=lambda s: s.position_us)

    # Look at sector number differences
    differences = []
    for i in range(1, len(sorted_sectors)):
        diff = sorted_sectors[i].sector_number - sorted_sectors[i - 1].sector_number
        if diff != 0:
            differences.append(abs(diff))

    if not differences:
        return 1

    # Most common difference is the interleave
    try:
        return statistics.mode(differences)
    except statistics.StatisticsError:
        return 1


def _recover_overwritten_data(
    flux: 'FluxCapture',
    sector: Any,
    additional_captures: Optional[List['FluxCapture']]
) -> Tuple[bytes, float]:
    """
    Attempt to recover overwritten data from a sector.

    Analyzes weak bits across multiple captures to potentially recover
    remnants of previously written data that was overwritten.

    Returns:
        Tuple of (recovered_data, confidence)
    """
    if not additional_captures:
        # Without multiple captures, limited recovery possible
        return bytes(), 0.0

    # Use weak bit detection to find inconsistent positions
    from floppy_formatter.analysis.signal_quality import detect_weak_bits

    all_captures = [flux] + additional_captures
    weak_bits = detect_weak_bits(all_captures)

    if not weak_bits:
        return bytes(), 0.0

    # Get sector position if available
    sector_position = getattr(sector, 'position', 0)
    sector_size_bits = 512 * 8  # Standard sector = 512 bytes = 4096 bits

    # Estimate sector position in microseconds
    # For HD MFM: ~2us per bit cell, so 512 bytes = ~8192 bit cells = ~16ms
    sector_duration_us = 16000  # Approximate sector duration

    # Filter weak bits that fall within this sector's data area
    sector_weak_bits = []
    for wb in weak_bits:
        wb_pos = getattr(wb, 'position_us', 0)
        # Check if weak bit is within sector boundaries (with some margin)
        if sector_position <= wb_pos <= (sector_position + sector_duration_us):
            sector_weak_bits.append(wb)

    if not sector_weak_bits:
        # No weak bits in this sector - no evidence of overwritten data
        return bytes(), 0.0

    # Attempt bit voting to recover original data
    # For overwritten sectors, weak bits may show remnants of old data
    recovered = bytearray()
    total_confidence = 0.0
    bits_analyzed = 0

    # Group weak bits and analyze their variance patterns
    for wb in sector_weak_bits:
        variance = getattr(wb, 'variance', 0.0)
        # High variance suggests the bit position has conflicting data
        # (potentially old vs new data fighting)
        if variance > WEAK_BIT_THRESHOLD:
            bits_analyzed += 1
            # The minority vote might represent old data
            minority_value = getattr(wb, 'minority_value', None)
            if minority_value is not None:
                # Confidence based on how close the vote was
                vote_ratio = getattr(wb, 'vote_ratio', 0.5)
                bit_confidence = 1.0 - abs(vote_ratio - 0.5) * 2
                total_confidence += bit_confidence

    # Calculate overall confidence
    if bits_analyzed > 0:
        confidence = total_confidence / bits_analyzed
        # Scale confidence based on how many weak bits we found
        # More weak bits = potentially more recoverable data
        coverage = min(1.0, len(sector_weak_bits) / (sector_size_bits * 0.1))
        confidence *= coverage
    else:
        confidence = 0.0

    # Build recovered data (partial reconstruction)
    # This is a simplified version - full implementation would
    # reconstruct byte-by-byte from minority votes
    if confidence > 0.1 and sector.data:
        # Start with current data and mark uncertain bytes
        recovered = bytearray(sector.data)
        # In practice, we'd modify specific bytes based on weak bit analysis

    return bytes(recovered), confidence


def _scan_for_hidden_data(flux: 'FluxCapture') -> List[DeletedSector]:
    """
    Scan for data hidden in gaps or unusual locations.

    Searches for:
    - Data in track tail (after expected track end)
    - Unusually large inter-sector gaps that may contain data
    - Regions with unusual timing patterns

    Returns:
        List of DeletedSector for any hidden data found
    """
    hidden_data = []

    times_us = flux.get_timings_microseconds()
    if not times_us:
        return hidden_data

    track_length = sum(times_us)
    expected_end = STANDARD_TRACK_US * 0.95

    # 1. Check for data in track tail (after expected track end)
    if track_length > expected_end * 1.1:
        tail_length = track_length - expected_end
        # Estimate byte count: ~2us per bit cell in MFM, 8 bits per byte
        estimated_bytes = int(tail_length / (2.0 * 8))

        hidden_data.append(DeletedSector(
            cylinder=flux.cylinder,
            head=flux.head,
            sector=-1,  # Unknown sector
            original_data=bytes(),
            current_data=bytes(),
            recovery_confidence=0.3,
            recovered_bytes=0,
            total_bytes=estimated_bytes,
            was_deleted_mark=False,
            flux_analysis={
                'location': 'track_tail',
                'tail_length_us': tail_length,
                'track_length_us': track_length,
            },
        ))

    # 2. Scan for unusually large gaps that may contain hidden data
    # Normal inter-sector gaps are ~40-80 bytes, look for much larger ones
    cumulative_pos = 0.0
    gap_regions = []

    # Look for sequences of consistent timing that could be data in gaps
    window_size = 100
    for i in range(len(times_us) - window_size):
        window = times_us[i:i + window_size]
        window_sum = sum(window)

        # Check if this looks like structured data (consistent timing)
        if len(window) > 10:
            mean = window_sum / len(window)
            # MFM data has timing around 2us, 4us, or 6us
            if 1.5 < mean < 7.0:
                variance = sum((t - mean) ** 2 for t in window) / len(window)
                # Low variance = consistent timing = likely data
                if variance < 2.0:
                    cumulative_pos += times_us[i]
                    # Check if we're in an unexpected location
                    track_fraction = cumulative_pos / STANDARD_TRACK_US
                    # Gaps typically occur at specific positions
                    # If we find data-like patterns in unusual spots, flag it
                    if 0.98 < track_fraction < 1.05:
                        gap_regions.append({
                            'position_us': cumulative_pos,
                            'mean_timing': mean,
                            'variance': variance,
                        })
                    continue

        cumulative_pos += times_us[i]

    # Report significant gap regions as potential hidden data
    for gap in gap_regions[:3]:  # Limit to first 3
        hidden_data.append(DeletedSector(
            cylinder=flux.cylinder,
            head=flux.head,
            sector=-2,  # Gap data indicator
            original_data=bytes(),
            current_data=bytes(),
            recovery_confidence=0.2,
            recovered_bytes=0,
            total_bytes=0,  # Unknown
            was_deleted_mark=False,
            flux_analysis={
                'location': 'gap_region',
                'position_us': gap['position_us'],
                'mean_timing_us': gap['mean_timing'],
            },
        ))

    return hidden_data


def _find_best_alignment(
    times1: List[float],
    times2: List[float],
    max_offset: int = 100
) -> Tuple[int, float]:
    """
    Find the best alignment offset between two timing sequences.

    Returns:
        Tuple of (best_offset, correlation)
    """
    min_len = min(len(times1), len(times2))
    if min_len < max_offset:
        return 0, 0.0

    best_offset = 0
    best_correlation = 0.0

    # Try different offsets
    for offset in range(-max_offset, max_offset + 1):
        # Apply offset
        if offset >= 0:
            t1 = times1[offset:offset + min_len - max_offset]
            t2 = times2[:min_len - max_offset]
        else:
            t1 = times1[:min_len - max_offset]
            t2 = times2[-offset:-offset + min_len - max_offset]

        if len(t1) < 10 or len(t2) < 10:
            continue

        # Calculate correlation
        try:
            mean1 = statistics.mean(t1)
            mean2 = statistics.mean(t2)
            std1 = statistics.stdev(t1)
            std2 = statistics.stdev(t2)

            if std1 == 0 or std2 == 0:
                continue

            covariance = sum((a - mean1) * (b - mean2) for a, b in zip(t1, t2)) / len(t1)
            correlation = covariance / (std1 * std2)

            if correlation > best_correlation:
                best_correlation = correlation
                best_offset = offset

        except statistics.StatisticsError:
            continue

    return best_offset, best_correlation


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Enums
    'ProtectionType',
    'FormatType',
    'SectorMarkType',
    # Data classes
    'ProtectionSignature',
    'CopyProtectionResult',
    'SectorInfo',
    'FormatAnalysis',
    'DeletedSector',
    'FluxDifference',
    'FluxComparison',
    # Functions
    'detect_copy_protection',
    'analyze_format_type',
    'extract_deleted_data',
    'compare_flux_captures',
    # Constants
    'STANDARD_TRACK_US',
    'PC_HD_SECTORS',
    'PC_DD_SECTORS',
    'DATA_MARK_NORMAL',
    'DATA_MARK_DELETED',
]
