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
    from floppy_formatter.analysis.flux_analyzer import (
        FluxCapture, generate_histogram, detect_encoding_type
    )
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

    # Check track length
    track_length = sum(times_us)
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
        detect_encoding_type, generate_histogram
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

    # Detect encoding type
    encoding_type, encoding_conf = detect_encoding_type(flux)
    encoding_str = encoding_type.name if encoding_type else "Unknown"

    # Calculate track length
    track_length = sum(times_us)
    track_ratio = track_length / STANDARD_TRACK_US

    # Analyze histogram for format detection
    histogram = generate_histogram(flux)

    # Determine format based on encoding and timing
    sectors_per_track = 0
    bytes_per_sector = 512
    format_type = FormatType.UNKNOWN

    if encoding_str == "MFM":
        # Check for PC format based on track timing
        if 0.95 <= track_ratio <= 1.05:
            # Standard length track
            # HD has 18 sectors, DD has 9
            mean_timing = statistics.mean(times_us)
            if mean_timing < 7.0:  # HD timing
                sectors_per_track = 18
                format_type = FormatType.PC_HD_MFM
            else:  # DD timing
                sectors_per_track = 9
                format_type = FormatType.PC_DD_MFM
        else:
            format_type = FormatType.RAW_MFM
            deviations.append(f"Non-standard track length: {track_ratio:.1%}")

    elif encoding_str == "FM":
        format_type = FormatType.RAW_FM
        sectors_per_track = 9  # Typical FM
        deviations.append("FM encoding (rare for 3.5\" disks)")

    elif encoding_str == "GCR":
        # Could be Apple, Mac, or Commodore
        format_type = FormatType.APPLE_GCR
        deviations.append("GCR encoding detected")

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
        confidence=encoding_conf,
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
    from floppy_formatter.hardware import decode_flux_to_sectors
    from floppy_formatter.analysis.signal_quality import detect_weak_bits

    deleted_sectors = []

    # First, decode sectors to find deleted data marks
    try:
        from floppy_formatter.hardware import FluxData

        # Convert FluxCapture to FluxData for decoding
        flux_data = FluxData(
            flux_times=flux.raw_timings,
            sample_freq=flux.sample_rate,
            index_positions=flux.index_positions,
            cylinder=flux.cylinder,
            head=flux.head,
        )
        sectors = decode_flux_to_sectors(flux_data)
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

    Returns:
        ProtectionSignature if timing protection detected, None otherwise
    """
    if len(times_us) < 1000:
        return None

    # Look for unusual timing patterns
    # Timing protection often uses specific gap lengths

    # Calculate running average and look for outliers
    window_size = 50
    for i in range(len(times_us) - window_size):
        window = times_us[i:i + window_size]
        mean = statistics.mean(window)
        std = statistics.stdev(window)

        # Look for extremely tight timing requirements
        if std < 0.1 and mean > 10.0:
            cumulative = sum(times_us[:i])
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
        from floppy_formatter.hardware import FluxData, decode_flux_to_sectors

        flux_data = FluxData(
            flux_times=flux.raw_timings,
            sample_freq=flux.sample_rate,
            index_positions=flux.index_positions,
            cylinder=flux.cylinder,
            head=flux.head,
        )

        decoded = decode_flux_to_sectors(flux_data)

        # Convert to SectorInfo
        cumulative_pos = 0.0
        times_us = flux.get_timings_microseconds()

        for sector in decoded:
            # Estimate position (rough approximation)
            estimated_pos = sector.sector * (sum(times_us) / 18) if times_us else 0.0

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

    # Check if weak bits fall within this sector's range
    sector_weak_bits = []
    # This would need sector position information for accurate filtering

    if not sector_weak_bits:
        return bytes(), 0.0

    # Attempt bit voting to recover original data
    # This is a simplified implementation
    recovered = bytearray()
    confidence = 0.0

    # In a full implementation, this would:
    # 1. Align multiple captures at the sector boundary
    # 2. For each weak bit, determine if it's showing old or new data
    # 3. Use statistical analysis to reconstruct original bits

    return bytes(recovered), confidence


def _scan_for_hidden_data(flux: 'FluxCapture') -> List[DeletedSector]:
    """
    Scan for data hidden in gaps or unusual locations.

    Returns:
        List of DeletedSector for any hidden data found
    """
    hidden_data = []

    # This would scan the flux for:
    # - Data in inter-sector gaps
    # - Data after track end
    # - Data in unusual encoding

    # Simplified implementation
    times_us = flux.get_timings_microseconds()
    if not times_us:
        return hidden_data

    # Look for data patterns in track tail (after last normal sector)
    track_length = sum(times_us)
    expected_end = STANDARD_TRACK_US * 0.95

    if track_length > expected_end * 1.1:
        # Significant data after expected track end
        hidden_data.append(DeletedSector(
            cylinder=flux.cylinder,
            head=flux.head,
            sector=-1,  # Unknown sector
            original_data=bytes(),
            current_data=bytes(),
            recovery_confidence=0.3,
            recovered_bytes=0,
            total_bytes=int((track_length - expected_end) / 8),  # Rough estimate
            was_deleted_mark=False,
            flux_analysis={'location': 'track_tail'},
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
