"""
Flux capture worker for real-time flux display.

Provides continuous flux capture with circular buffering for live
waveform visualization. Captures flux data in the background while
calculating signal quality metrics on-the-fly.

Part of Phase 9: Workers & Background Processing
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Deque, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal

from floppy_formatter.gui.workers.base_worker import GreaseweazleWorker

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice
    from floppy_formatter.core.geometry import DiskGeometry
    from floppy_formatter.analysis.flux_analyzer import FluxCapture

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default capture settings
DEFAULT_BUFFER_SIZE = 10  # Number of captures to keep in buffer
DEFAULT_REVOLUTIONS = 1.2  # Revolutions per capture
DEFAULT_CAPTURE_INTERVAL_MS = 200  # Milliseconds between captures


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CaptureConfig:
    """
    Configuration for continuous flux capture.

    Attributes:
        buffer_size: Number of captures to keep in circular buffer
        revolutions: Revolutions per capture (default 1.2)
        capture_interval_ms: Minimum time between captures
        calculate_quality: Whether to calculate quality metrics
        continuous: Whether to capture continuously or single-shot
    """
    buffer_size: int = DEFAULT_BUFFER_SIZE
    revolutions: float = DEFAULT_REVOLUTIONS
    capture_interval_ms: int = DEFAULT_CAPTURE_INTERVAL_MS
    calculate_quality: bool = True
    continuous: bool = True


@dataclass
class FluxSample:
    """
    Single flux capture sample with metadata.

    Attributes:
        capture: The FluxCapture data
        timestamp: When capture was taken (unix timestamp)
        cylinder: Cylinder number
        head: Head number
        snr_db: Signal-to-noise ratio (if calculated)
        jitter_ns: Timing jitter RMS (if calculated)
        quality_score: Overall quality score 0-100 (if calculated)
        capture_time_ms: Time taken to capture
    """
    capture: 'FluxCapture'
    timestamp: float
    cylinder: int
    head: int
    snr_db: float = 0.0
    jitter_ns: float = 0.0
    quality_score: float = 0.0
    capture_time_ms: float = 0.0

    @property
    def track_number(self) -> int:
        """Linear track number."""
        return self.cylinder * 2 + self.head


@dataclass
class CaptureStats:
    """
    Statistics about the capture session.

    Attributes:
        total_captures: Total number of captures taken
        captures_per_second: Average capture rate
        average_quality: Average quality score
        min_quality: Minimum quality observed
        max_quality: Maximum quality observed
        current_cylinder: Current head position
        current_head: Current head selection
        session_duration: Total session duration in seconds
    """
    total_captures: int = 0
    captures_per_second: float = 0.0
    average_quality: float = 0.0
    min_quality: float = 100.0
    max_quality: float = 0.0
    current_cylinder: int = 0
    current_head: int = 0
    session_duration: float = 0.0


# =============================================================================
# Flux Capture Worker
# =============================================================================

class FluxCaptureWorker(GreaseweazleWorker):
    """
    Worker for real-time flux capture and display.

    Provides continuous flux capture for live waveform visualization.
    Maintains a circular buffer of recent captures and calculates
    signal quality metrics on-the-fly.

    Features:
    - Continuous or single-shot capture modes
    - Circular buffer for smooth live display
    - Real-time SNR and jitter calculation
    - Position tracking for seek operations

    Signals:
        flux_captured(object): New FluxSample available
        quality_update(float, float, float): Quality metrics (snr_db, jitter_ns, score)
        position_changed(int, int): Head position changed (cylinder, head)
        capture_stats(object): Updated CaptureStats

    Example:
        config = CaptureConfig(
            buffer_size=10,
            continuous=True,
            calculate_quality=True
        )
        worker = FluxCaptureWorker(device, geometry, config)
        worker.flux_captured.connect(on_new_capture)
        worker.quality_update.connect(update_quality_display)
    """

    # Signals specific to flux capture
    flux_captured = pyqtSignal(object)          # FluxSample
    quality_update = pyqtSignal(float, float, float)  # snr_db, jitter_ns, quality_score
    position_changed = pyqtSignal(int, int)      # cylinder, head
    capture_stats = pyqtSignal(object)           # CaptureStats

    def __init__(
        self,
        device: 'GreaseweazleDevice',
        geometry: 'DiskGeometry',
        config: Optional[CaptureConfig] = None,
        initial_cylinder: int = 0,
        initial_head: int = 0,
    ):
        """
        Initialize flux capture worker.

        Args:
            device: Connected GreaseweazleDevice instance
            geometry: Disk geometry information
            config: CaptureConfig with capture settings (uses defaults if None)
            initial_cylinder: Starting cylinder position
            initial_head: Starting head selection
        """
        super().__init__(device)
        self._geometry = geometry
        self._config = config or CaptureConfig()

        # Current position
        self._cylinder = initial_cylinder
        self._head = initial_head

        # Circular buffer for captures
        self._buffer: Deque[FluxSample] = deque(maxlen=self._config.buffer_size)

        # Statistics
        self._stats = CaptureStats()
        self._session_start = 0.0

        logger.info(
            "FluxCaptureWorker initialized: buffer=%d, continuous=%s",
            self._config.buffer_size, self._config.continuous
        )

    def run(self) -> None:
        """
        Execute the flux capture operation.

        Captures flux continuously or once based on configuration,
        emitting samples and quality metrics.
        """
        from floppy_formatter.hardware import read_track_flux
        from floppy_formatter.analysis.flux_analyzer import FluxCapture
        from floppy_formatter.analysis.signal_quality import (
            calculate_snr, measure_jitter
        )

        # Ensure motor is on
        if not self._device.is_motor_on():
            self._device.motor_on()

        self._session_start = time.time()
        self._stats = CaptureStats()
        quality_scores = []

        logger.info("Starting flux capture at C%d:H%d", self._cylinder, self._head)

        # Initial seek
        self._device.seek(self._cylinder, self._head)
        self.position_changed.emit(self._cylinder, self._head)

        while not self._cancelled:
            capture_start = time.time()

            try:
                # Capture flux
                flux_data = read_track_flux(
                    self._device,
                    self._cylinder,
                    self._head,
                    revolutions=self._config.revolutions
                )

                capture = FluxCapture.from_flux_data(flux_data)
                capture.cylinder = self._cylinder
                capture.head = self._head

                capture_time_ms = (time.time() - capture_start) * 1000

                # Create sample
                sample = FluxSample(
                    capture=capture,
                    timestamp=time.time(),
                    cylinder=self._cylinder,
                    head=self._head,
                    capture_time_ms=capture_time_ms,
                )

                # Calculate quality if configured
                if self._config.calculate_quality:
                    try:
                        snr_result = calculate_snr(capture)
                        jitter_result = measure_jitter(capture)

                        sample.snr_db = snr_result.snr_db
                        sample.jitter_ns = jitter_result.rms_ns

                        # Quality score from SNR and jitter
                        snr_component = min(50, max(0, (snr_result.snr_db + 10) * 2.5))
                        jitter_component = min(50, max(0, 50 - jitter_result.rms_ns / 10))
                        sample.quality_score = snr_component + jitter_component

                        # Update running quality stats
                        quality_scores.append(sample.quality_score)
                        self._stats.min_quality = min(self._stats.min_quality, sample.quality_score)
                        self._stats.max_quality = max(self._stats.max_quality, sample.quality_score)
                        self._stats.average_quality = sum(quality_scores) / len(quality_scores)

                        # Emit quality update
                        self.quality_update.emit(
                            sample.snr_db,
                            sample.jitter_ns,
                            sample.quality_score
                        )

                    except Exception as e:
                        logger.warning("Quality calculation failed: %s", e)

                # Add to buffer
                self._buffer.append(sample)

                # Update stats
                self._stats.total_captures += 1
                self._stats.current_cylinder = self._cylinder
                self._stats.current_head = self._head
                self._stats.session_duration = time.time() - self._session_start
                if self._stats.session_duration > 0:
                    self._stats.captures_per_second = (
                        self._stats.total_captures / self._stats.session_duration
                    )

                # Emit signals
                self.flux_captured.emit(sample)
                self.capture_stats.emit(self._stats)

                logger.debug(
                    "Captured C%d:H%d: quality=%.1f, %.1f ms",
                    self._cylinder, self._head, sample.quality_score, capture_time_ms
                )

            except Exception as e:
                logger.warning("Capture failed at C%d:H%d: %s", self._cylinder, self._head, e)
                self.error.emit(f"Capture failed: {e}")

            # Exit if single-shot mode
            if not self._config.continuous:
                break

            # Wait for next capture interval
            elapsed = (time.time() - capture_start) * 1000
            wait_time = max(0, self._config.capture_interval_ms - elapsed)
            if wait_time > 0:
                time.sleep(wait_time / 1000)

        logger.info(
            "Flux capture complete: %d captures in %.1fs",
            self._stats.total_captures, self._stats.session_duration
        )
        self.finished.emit()

    def seek_to(self, cylinder: int, head: int) -> None:
        """
        Request seek to a new position.

        Note: This will take effect on the next capture cycle.

        Args:
            cylinder: Target cylinder (0-79)
            head: Target head (0-1)
        """
        if 0 <= cylinder < self._geometry.cylinders:
            self._cylinder = cylinder
        if 0 <= head < self._geometry.heads:
            self._head = head

        # If worker is running, seek immediately
        if self._running and self._device and self._device.is_connected():
            try:
                self._device.seek(self._cylinder, self._head)
                self.position_changed.emit(self._cylinder, self._head)
            except Exception as e:
                logger.warning("Seek failed: %s", e)

    def step_cylinder(self, delta: int) -> None:
        """
        Step the head position by delta cylinders.

        Args:
            delta: Number of cylinders to step (positive = inward)
        """
        new_cyl = max(0, min(self._geometry.cylinders - 1, self._cylinder + delta))
        if new_cyl != self._cylinder:
            self.seek_to(new_cyl, self._head)

    def toggle_head(self) -> None:
        """Toggle between head 0 and head 1."""
        new_head = 1 - self._head
        self.seek_to(self._cylinder, new_head)

    def get_buffer(self) -> List[FluxSample]:
        """
        Get a copy of the current capture buffer.

        Returns:
            List of FluxSample in chronological order
        """
        return list(self._buffer)

    def get_latest_sample(self) -> Optional[FluxSample]:
        """
        Get the most recent flux sample.

        Returns:
            Most recent FluxSample or None if buffer is empty
        """
        if self._buffer:
            return self._buffer[-1]
        return None

    def get_current_position(self) -> tuple:
        """
        Get current head position.

        Returns:
            Tuple of (cylinder, head)
        """
        return (self._cylinder, self._head)

    def get_stats(self) -> CaptureStats:
        """Get current capture statistics."""
        return self._stats

    def get_geometry(self) -> 'DiskGeometry':
        """Get the disk geometry being used."""
        return self._geometry

    def get_config(self) -> CaptureConfig:
        """Get the capture configuration."""
        return self._config


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'FluxCaptureWorker',
    'CaptureConfig',
    'FluxSample',
    'CaptureStats',
    'DEFAULT_BUFFER_SIZE',
    'DEFAULT_REVOLUTIONS',
    'DEFAULT_CAPTURE_INTERVAL_MS',
]
