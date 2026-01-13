"""
Recovery package for advanced floppy disk data recovery.

This package provides sophisticated recovery techniques that go beyond
traditional multi-pass format/verify cycles. It builds ON TOP of existing
recovery algorithms and does NOT replace them.

Recovery Levels:
- STANDARD: Traditional multi-pass recovery (existing algorithms preserved)
- AGGRESSIVE: Multi-capture + PLL tuning before giving up
- FORENSIC: All techniques, maximum effort, detailed logging

Modules:
- multi_capture: Multi-revolution flux capture and statistical bit voting
- pll_tuning: PLL parameter optimization for marginal sectors
- bit_slip_recovery: Synchronization loss detection and correction
- surface_treatment: Degaussing and magnetic domain refresh

Part of Phase 4: Advanced Data Recovery
"""

from .multi_capture import (
    # Dataclasses
    CaptureMetadata,
    MultiCaptureResult,
    AlignedCaptures,
    ReconstructedSector,
    ReconstructedFlux,

    # Main functions
    capture_multiple_revolutions,
    align_flux_captures,
    reconstruct_from_captures,
    multi_capture_recover_track,
    multi_capture_recover_sector,

    # Utilities
    calculate_capture_quality,
    estimate_recovery_potential,
)

from .pll_tuning import (
    # Dataclasses
    PLLParameters,
    DecodedSectorResult,
    PLLDecodeResult,
    PLLSearchResult,
    OptimalPLLResult,

    # Classes
    PLLDecoder,
    PLLState,

    # Main functions
    decode_with_pll,
    try_pll_variations,
    find_optimal_pll,
    optimize_for_sector,

    # Utilities
    create_parameter_grid,
    default_pll_parameters,
)

from .bit_slip_recovery import (
    # Dataclasses
    BitSlipEvent,
    PhaseTrackingState,
    SlipCorrection,
    SlipRecoveryResult,
    CorrectedFlux,
    SlipPattern,

    # Enums
    SlipType,

    # Main functions
    detect_bit_slips,
    analyze_slip_pattern,
    realign_after_slip,
    apply_all_slip_corrections,
    reconstruct_slipped_sector,

    # Utilities
    calculate_phase_continuity,
    estimate_slip_severity,
)

from .surface_treatment import (
    # Dataclasses
    DegaussResult,
    PatternWriteResult,
    RefreshResult,
    SectorTreatmentResult,
    BulkTreatmentResult,

    # Enums
    TreatmentType,
    TreatmentPattern,

    # Constants
    REFRESH_CYCLE_PATTERNS,

    # Main functions
    degauss_track,
    write_recovery_pattern,
    refresh_track,
    treat_weak_sector,

    # Bulk operations
    bulk_refresh_tracks,
    refresh_weak_tracks,
    emergency_degauss_disk,
)


__all__ = [
    # multi_capture
    'CaptureMetadata',
    'MultiCaptureResult',
    'AlignedCaptures',
    'ReconstructedSector',
    'ReconstructedFlux',
    'capture_multiple_revolutions',
    'align_flux_captures',
    'reconstruct_from_captures',
    'multi_capture_recover_track',
    'multi_capture_recover_sector',
    'calculate_capture_quality',
    'estimate_recovery_potential',

    # pll_tuning
    'PLLParameters',
    'DecodedSectorResult',
    'PLLDecodeResult',
    'PLLSearchResult',
    'OptimalPLLResult',
    'PLLDecoder',
    'PLLState',
    'decode_with_pll',
    'try_pll_variations',
    'find_optimal_pll',
    'optimize_for_sector',
    'create_parameter_grid',
    'default_pll_parameters',

    # bit_slip_recovery
    'BitSlipEvent',
    'PhaseTrackingState',
    'SlipCorrection',
    'SlipRecoveryResult',
    'CorrectedFlux',
    'SlipPattern',
    'SlipType',
    'detect_bit_slips',
    'analyze_slip_pattern',
    'realign_after_slip',
    'apply_all_slip_corrections',
    'reconstruct_slipped_sector',
    'calculate_phase_continuity',
    'estimate_slip_severity',

    # surface_treatment
    'DegaussResult',
    'PatternWriteResult',
    'RefreshResult',
    'SectorTreatmentResult',
    'BulkTreatmentResult',
    'TreatmentType',
    'TreatmentPattern',
    'REFRESH_CYCLE_PATTERNS',
    'degauss_track',
    'write_recovery_pattern',
    'refresh_track',
    'treat_weak_sector',
    'bulk_refresh_tracks',
    'refresh_weak_tracks',
    'emergency_degauss_disk',
]
