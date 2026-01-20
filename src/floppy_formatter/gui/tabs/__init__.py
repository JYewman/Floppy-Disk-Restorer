"""
Analytics dashboard tabs for Floppy Workbench.

Contains specialized tab widgets for the analytics panel:
- OverviewTab: Health gauge, statistics, recommendations
- FluxTab: Waveform and histogram visualization
- ErrorsTab: Error heatmap, pie chart, error log
- RecoveryTab: Convergence graph, pass comparison, timeline
- DiagnosticsTab: Alignment, RPM, self-test panels

Part of Phase 7: Analytics Dashboard
"""

# Overview tab and data classes
from floppy_formatter.gui.tabs.overview_tab import (
    # Main widget
    OverviewTab,
    # Component widgets
    HealthGaugeWidget,
    StatisticsCard,
    TrendChartWidget,
    RecommendationsWidget,
    # Data classes
    Recommendation,
    RecommendationSeverity,
    DiskStatistics,
    TrendPoint,
)

# Flux tab
from floppy_formatter.gui.tabs.flux_tab import (
    FluxTab,
    TrackSectorSelector,
)

# Errors tab and data classes
from floppy_formatter.gui.tabs.errors_tab import (
    # Main widget
    ErrorsTab,
    # Component widgets
    ErrorHeatmapWidget,
    ErrorPieChartWidget,
    ErrorLogTable,
    PatternDetectionWidget,
    # Data classes
    SectorError,
    ErrorType,
)

# Recovery tab and data classes
from floppy_formatter.gui.tabs.recovery_tab import (
    # Main widget
    RecoveryTab,
    # Component widgets
    ConvergenceChartWidget,
    PassComparisonTable,
    RecoveryTimelineWidget,
    RecoveryPredictionWidget,
    RecoveryStatsWidget,
    # Data classes
    PassStats,
    RecoveryStats,
    RecoveredSector,
)

# Diagnostics tab and data classes
from floppy_formatter.gui.tabs.diagnostics_tab import (
    # Main widget
    DiagnosticsTab,
    # Component widgets
    AlignmentVisualizationWidget,
    RPMChartWidget,
    SelfTestWidget,
    DriveInfoWidget,
    TemperatureWidget,
    # Data classes
    SelfTestItem,
    SelfTestResults,
    TestStatus,
    AlignmentResults,
)

# Verification tab and data classes
from floppy_formatter.gui.tabs.verification_tab import (
    # Main widget
    VerificationTab,
    # Component widgets
    GradeWidget,
    StatCard,
    # Data classes
    VerificationSummary,
    TrackVerificationResult,
)

# Analysis tab and data classes
from floppy_formatter.gui.tabs.analysis_tab import (
    # Main widget
    AnalysisTab,
    # Component widgets
    GradeDisplayWidget,
    GradeDistributionWidget,
    HeadQualityCard,
    SignalQualityCard,
    EncodingInfoCard,
    CopyProtectionCard,
    AnalysisRecommendationsCard,
    # Data classes
    AnalysisSummary,
    HeadQuality,
)


__all__ = [
    # Overview tab
    "OverviewTab",
    "HealthGaugeWidget",
    "StatisticsCard",
    "TrendChartWidget",
    "RecommendationsWidget",
    "Recommendation",
    "RecommendationSeverity",
    "DiskStatistics",
    "TrendPoint",
    # Flux tab
    "FluxTab",
    "TrackSectorSelector",
    # Errors tab
    "ErrorsTab",
    "ErrorHeatmapWidget",
    "ErrorPieChartWidget",
    "ErrorLogTable",
    "PatternDetectionWidget",
    "SectorError",
    "ErrorType",
    # Recovery tab
    "RecoveryTab",
    "ConvergenceChartWidget",
    "PassComparisonTable",
    "RecoveryTimelineWidget",
    "RecoveryPredictionWidget",
    "RecoveryStatsWidget",
    "PassStats",
    "RecoveryStats",
    "RecoveredSector",
    # Diagnostics tab
    "DiagnosticsTab",
    "AlignmentVisualizationWidget",
    "RPMChartWidget",
    "SelfTestWidget",
    "DriveInfoWidget",
    "TemperatureWidget",
    "SelfTestItem",
    "SelfTestResults",
    "TestStatus",
    "AlignmentResults",
    # Verification tab
    "VerificationTab",
    "GradeWidget",
    "StatCard",
    "VerificationSummary",
    "TrackVerificationResult",
    # Analysis tab
    "AnalysisTab",
    "GradeDisplayWidget",
    "GradeDistributionWidget",
    "HeadQualityCard",
    "SignalQualityCard",
    "EncodingInfoCard",
    "CopyProtectionCard",
    "AnalysisRecommendationsCard",
    "AnalysisSummary",
    "HeadQuality",
]
