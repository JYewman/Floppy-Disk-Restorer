"""
Background worker threads for Greaseweazle floppy operations.

Provides QThread workers for all disk operations including scanning,
formatting, recovery, analysis, alignment testing, and real-time
flux capture. Includes a worker pool for managing concurrent operations.

Part of Phase 9: Workers & Background Processing
"""

# Base worker classes
from floppy_formatter.gui.workers.base_worker import (
    BaseWorker,
    GreaseweazleWorker,
    MOTOR_SPINDOWN_DELAY,
    MAX_RECOVERY_ATTEMPTS,
    RECOVERY_DELAY,
)

# Scan worker
from floppy_formatter.gui.workers.scan_worker import (
    ScanWorker,
    ScanMode,
    SectorResult,
    TrackResult,
    ScanResult,
)

# Format worker
from floppy_formatter.gui.workers.format_worker import (
    FormatWorker,
    FormatType,
    FormatResult,
    TrackFormatResult,
    PATTERN_ZERO,
    PATTERN_ONE,
    PATTERN_E5,
    PATTERN_AA,
    PATTERN_55,
)

# Restore worker
from floppy_formatter.gui.workers.restore_worker import (
    RestoreWorker,
    RestoreConfig,
    RecoveryLevel,
    RecoveryStats,
    PassStats,
    RecoveredSector,
)

# Analyze worker
from floppy_formatter.gui.workers.analyze_worker import (
    AnalyzeWorker,
    AnalysisConfig,
    AnalysisDepth,
    AnalysisComponent,
    TrackAnalysisResult,
    DiskAnalysisResult,
)

# Alignment worker
from floppy_formatter.gui.workers.alignment_worker import (
    AlignmentWorker,
    AlignmentConfig,
    CylinderTestResult,
    DEFAULT_TEST_CYLINDERS,
)

# Flux capture worker
from floppy_formatter.gui.workers.flux_capture_worker import (
    FluxCaptureWorker,
    CaptureConfig,
    FluxSample,
    CaptureStats,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_REVOLUTIONS,
    DEFAULT_CAPTURE_INTERVAL_MS,
)

# Worker pool
from floppy_formatter.gui.workers.worker_pool import (
    WorkerPool,
    OperationPriority,
    WorkerState,
    QueuedOperation,
    WorkerInfo,
    MAX_HISTORY_SIZE,
    WORKER_SHUTDOWN_TIMEOUT_MS,
)


__all__ = [
    # Base workers
    'BaseWorker',
    'GreaseweazleWorker',
    'MOTOR_SPINDOWN_DELAY',
    'MAX_RECOVERY_ATTEMPTS',
    'RECOVERY_DELAY',

    # Scan worker
    'ScanWorker',
    'ScanMode',
    'SectorResult',
    'TrackResult',
    'ScanResult',

    # Format worker
    'FormatWorker',
    'FormatType',
    'FormatResult',
    'TrackFormatResult',
    'PATTERN_ZERO',
    'PATTERN_ONE',
    'PATTERN_E5',
    'PATTERN_AA',
    'PATTERN_55',

    # Restore worker
    'RestoreWorker',
    'RestoreConfig',
    'RecoveryLevel',
    'RecoveryStats',
    'PassStats',
    'RecoveredSector',

    # Analyze worker
    'AnalyzeWorker',
    'AnalysisConfig',
    'AnalysisDepth',
    'AnalysisComponent',
    'TrackAnalysisResult',
    'DiskAnalysisResult',

    # Alignment worker
    'AlignmentWorker',
    'AlignmentConfig',
    'CylinderTestResult',
    'DEFAULT_TEST_CYLINDERS',

    # Flux capture worker
    'FluxCaptureWorker',
    'CaptureConfig',
    'FluxSample',
    'CaptureStats',
    'DEFAULT_BUFFER_SIZE',
    'DEFAULT_REVOLUTIONS',
    'DEFAULT_CAPTURE_INTERVAL_MS',

    # Worker pool
    'WorkerPool',
    'OperationPriority',
    'WorkerState',
    'QueuedOperation',
    'WorkerInfo',
    'MAX_HISTORY_SIZE',
    'WORKER_SHUTDOWN_TIMEOUT_MS',
]
