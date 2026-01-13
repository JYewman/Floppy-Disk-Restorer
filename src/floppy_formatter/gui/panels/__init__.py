"""
GUI panels package for Greaseweazle workbench.

This package contains the main panels used in the single-page workbench layout:
- DriveControlPanel: Connection, motor control, and seek controls
- OperationToolbar: Operation buttons and progress display
- StatusStrip: Status bar with connection, drive, operation, and health info
- AnalyticsPanel: Tabbed analytics dashboard with 5 tabs

Part of Phase 5-7: Workbench GUI - Main Layout & Analytics Dashboard
"""

from .drive_control_panel import (
    DriveControlPanel,
    ConnectionState,
    LEDIndicator,
)

from .operation_toolbar import (
    OperationToolbar,
    OperationType,
    OperationMode,
    OperationState,
    LargeOperationButton,
)

from .status_strip import (
    StatusStrip,
    StatusSection,
    HealthIndicator,
)

from .analytics_panel import (
    AnalyticsPanel,
    TAB_OVERVIEW,
    TAB_FLUX,
    TAB_ERRORS,
    TAB_RECOVERY,
    TAB_DIAGNOSTICS,
)


__all__ = [
    # Drive control panel
    'DriveControlPanel',
    'ConnectionState',
    'LEDIndicator',

    # Operation toolbar
    'OperationToolbar',
    'OperationType',
    'OperationMode',
    'OperationState',
    'LargeOperationButton',

    # Status strip
    'StatusStrip',
    'StatusSection',
    'HealthIndicator',

    # Analytics panel
    'AnalyticsPanel',
    'TAB_OVERVIEW',
    'TAB_FLUX',
    'TAB_ERRORS',
    'TAB_RECOVERY',
    'TAB_DIAGNOSTICS',
]
