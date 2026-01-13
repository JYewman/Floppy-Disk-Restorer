"""
Worker pool for managing concurrent Greaseweazle operations.

Provides centralized management of worker threads with queue-based
operation scheduling, priority handling, and resource locking to
ensure only one device operation runs at a time.

Part of Phase 9: Workers & Background Processing
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from queue import PriorityQueue, Empty
from typing import Optional, Dict, List, Callable, Any, Type, TYPE_CHECKING

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from floppy_formatter.gui.workers.base_worker import GreaseweazleWorker

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Maximum workers to keep in history
MAX_HISTORY_SIZE = 100

# Time to wait for worker thread to finish during shutdown
WORKER_SHUTDOWN_TIMEOUT_MS = 5000


# =============================================================================
# Enums
# =============================================================================

class OperationPriority(IntEnum):
    """
    Priority levels for queued operations.

    Lower numbers = higher priority.
    """
    URGENT = 0       # User-initiated cancellation, emergency stop
    HIGH = 1         # User-initiated operations (scan, format, etc.)
    NORMAL = 2       # Standard operations
    LOW = 3          # Background operations (auto-refresh, etc.)
    IDLE = 4         # Lowest priority (cleanup, maintenance)


class WorkerState(IntEnum):
    """State of a managed worker."""
    PENDING = 0      # In queue, waiting to run
    RUNNING = 1      # Currently executing
    COMPLETED = 2    # Finished successfully
    FAILED = 3       # Finished with error
    CANCELLED = 4    # User cancelled


# =============================================================================
# Data Classes
# =============================================================================

@dataclass(order=True)
class QueuedOperation:
    """
    Operation waiting in the queue.

    Attributes:
        priority: Operation priority (lower = higher priority)
        timestamp: When operation was queued
        worker: The GreaseweazleWorker instance
        name: Human-readable operation name
        callback: Optional callback when complete
        id: Unique operation identifier
    """
    priority: OperationPriority
    timestamp: float = field(compare=False)
    worker: GreaseweazleWorker = field(compare=False)
    name: str = field(compare=False)
    callback: Optional[Callable[[Any], None]] = field(default=None, compare=False)
    id: int = field(default=0, compare=False)

    def __post_init__(self):
        """Assign unique ID if not set."""
        if self.id == 0:
            self.id = id(self)


@dataclass
class WorkerInfo:
    """
    Information about a managed worker.

    Attributes:
        id: Unique worker identifier
        name: Human-readable name
        worker_type: Class name of the worker
        state: Current state
        priority: Operation priority
        queued_at: When operation was queued
        started_at: When operation started (None if not started)
        completed_at: When operation completed (None if not done)
        error_message: Error message if failed
        progress: Last reported progress (0-100)
    """
    id: int
    name: str
    worker_type: str
    state: WorkerState
    priority: OperationPriority
    queued_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: int = 0

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get operation duration if completed."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


# =============================================================================
# Worker Pool
# =============================================================================

class WorkerPool(QObject):
    """
    Manages concurrent Greaseweazle worker operations.

    Provides centralized management of worker threads with:
    - Priority queue for operation scheduling
    - Resource locking (one device operation at a time)
    - Progress and status aggregation
    - History of completed operations

    Features:
    - Queue operations with priority levels
    - Only one device operation runs at a time
    - Cancel current or queued operations
    - Track operation history and statistics

    Signals:
        worker_started(int, str): Worker started (id, name)
        worker_progress(int, int): Worker progress (id, progress_percent)
        worker_completed(int, str, object): Worker done (id, name, result)
        worker_failed(int, str, str): Worker failed (id, name, error)
        worker_cancelled(int, str): Worker cancelled (id, name)
        queue_changed(int): Queue size changed (new_size)
        pool_idle(): No operations running or queued

    Example:
        pool = WorkerPool(device)

        scan_worker = ScanWorker(device, geometry)
        pool.queue_operation(scan_worker, "Disk Scan", OperationPriority.HIGH)

        # Connect to signals
        pool.worker_completed.connect(on_scan_complete)

        # Cancel if needed
        pool.cancel_current()
    """

    # Signals
    worker_started = pyqtSignal(int, str)       # id, name
    worker_progress = pyqtSignal(int, int)      # id, progress
    worker_completed = pyqtSignal(int, str, object)  # id, name, result
    worker_failed = pyqtSignal(int, str, str)   # id, name, error
    worker_cancelled = pyqtSignal(int, str)     # id, name
    queue_changed = pyqtSignal(int)             # queue_size
    pool_idle = pyqtSignal()

    def __init__(
        self,
        device: Optional['GreaseweazleDevice'] = None,
        parent: Optional[QObject] = None
    ):
        """
        Initialize worker pool.

        Args:
            device: Optional GreaseweazleDevice (can be set later)
            parent: Optional parent QObject
        """
        super().__init__(parent)

        self._device = device

        # Operation queue
        self._queue: PriorityQueue[QueuedOperation] = PriorityQueue()
        self._queue_lock = threading.Lock()

        # Current operation
        self._current_operation: Optional[QueuedOperation] = None
        self._current_thread: Optional[QThread] = None
        self._operation_lock = threading.Lock()

        # History of completed operations
        self._history: List[WorkerInfo] = []
        self._history_lock = threading.Lock()

        # Worker tracking
        self._workers: Dict[int, WorkerInfo] = {}
        self._next_id = 1

        # Pool state
        self._running = True
        self._processor_thread: Optional[threading.Thread] = None

        logger.info("WorkerPool initialized")

    def start(self) -> None:
        """
        Start the worker pool processor.

        Begins processing queued operations.
        """
        if self._processor_thread and self._processor_thread.is_alive():
            return

        self._running = True
        self._processor_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="WorkerPoolProcessor"
        )
        self._processor_thread.start()
        logger.info("WorkerPool processor started")

    def stop(self) -> None:
        """
        Stop the worker pool.

        Cancels current operation and clears queue.
        """
        logger.info("Stopping WorkerPool...")
        self._running = False

        # Cancel current operation
        self.cancel_current()

        # Clear queue
        self.clear_queue()

        # Wait for processor thread
        if self._processor_thread and self._processor_thread.is_alive():
            self._processor_thread.join(timeout=2.0)

        logger.info("WorkerPool stopped")

    def set_device(self, device: Optional['GreaseweazleDevice']) -> None:
        """
        Set the Greaseweazle device.

        Args:
            device: GreaseweazleDevice instance or None
        """
        self._device = device

    def queue_operation(
        self,
        worker: GreaseweazleWorker,
        name: str,
        priority: OperationPriority = OperationPriority.NORMAL,
        callback: Optional[Callable[[Any], None]] = None
    ) -> int:
        """
        Queue an operation for execution.

        Args:
            worker: The GreaseweazleWorker to run
            name: Human-readable operation name
            priority: Operation priority
            callback: Optional callback when complete

        Returns:
            Operation ID for tracking

        Example:
            op_id = pool.queue_operation(
                ScanWorker(device, geometry),
                "Full Disk Scan",
                OperationPriority.HIGH
            )
        """
        # Set device on worker if not set
        if self._device and not worker.has_device():
            worker.set_device(self._device)

        # Create operation
        op_id = self._next_id
        self._next_id += 1

        operation = QueuedOperation(
            priority=priority,
            timestamp=time.time(),
            worker=worker,
            name=name,
            callback=callback,
            id=op_id,
        )

        # Create worker info
        info = WorkerInfo(
            id=op_id,
            name=name,
            worker_type=type(worker).__name__,
            state=WorkerState.PENDING,
            priority=priority,
            queued_at=datetime.now(),
        )
        self._workers[op_id] = info

        # Add to queue
        with self._queue_lock:
            self._queue.put(operation)

        self.queue_changed.emit(self._queue.qsize())
        logger.info("Queued operation %d: %s (priority=%s)",
                    op_id, name, priority.name)

        # Start processor if not running
        self.start()

        return op_id

    def cancel_current(self) -> bool:
        """
        Cancel the currently running operation.

        Returns:
            True if an operation was cancelled
        """
        with self._operation_lock:
            if self._current_operation:
                op = self._current_operation
                logger.info("Cancelling current operation: %s", op.name)

                # Request cancellation
                op.worker.cancel()

                # Update state
                if op.id in self._workers:
                    self._workers[op.id].state = WorkerState.CANCELLED

                self.worker_cancelled.emit(op.id, op.name)
                return True

        return False

    def cancel_operation(self, op_id: int) -> bool:
        """
        Cancel a specific operation by ID.

        Args:
            op_id: Operation ID to cancel

        Returns:
            True if operation was found and cancelled
        """
        # Check if it's the current operation
        with self._operation_lock:
            if self._current_operation and self._current_operation.id == op_id:
                return self.cancel_current()

        # Check queue (need to rebuild without the cancelled item)
        with self._queue_lock:
            items = []
            found = False

            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    if item.id == op_id:
                        found = True
                        if item.id in self._workers:
                            self._workers[item.id].state = WorkerState.CANCELLED
                        self.worker_cancelled.emit(item.id, item.name)
                    else:
                        items.append(item)
                except Empty:
                    break

            # Put remaining items back
            for item in items:
                self._queue.put(item)

            if found:
                self.queue_changed.emit(self._queue.qsize())

            return found

    def clear_queue(self) -> int:
        """
        Clear all pending operations from the queue.

        Does not affect the currently running operation.

        Returns:
            Number of operations cleared
        """
        count = 0
        with self._queue_lock:
            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    if item.id in self._workers:
                        self._workers[item.id].state = WorkerState.CANCELLED
                    self.worker_cancelled.emit(item.id, item.name)
                    count += 1
                except Empty:
                    break

        if count > 0:
            self.queue_changed.emit(0)
            logger.info("Cleared %d operations from queue", count)

        return count

    def is_busy(self) -> bool:
        """Check if an operation is currently running."""
        with self._operation_lock:
            return self._current_operation is not None

    def get_queue_size(self) -> int:
        """Get number of pending operations."""
        with self._queue_lock:
            return self._queue.qsize()

    def get_current_operation(self) -> Optional[WorkerInfo]:
        """Get info about the currently running operation."""
        with self._operation_lock:
            if self._current_operation:
                return self._workers.get(self._current_operation.id)
        return None

    def get_operation_info(self, op_id: int) -> Optional[WorkerInfo]:
        """Get info about a specific operation."""
        return self._workers.get(op_id)

    def get_history(self, limit: int = 20) -> List[WorkerInfo]:
        """
        Get recent operation history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of WorkerInfo, most recent first
        """
        with self._history_lock:
            return list(reversed(self._history[-limit:]))

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get pool statistics.

        Returns:
            Dictionary with pool stats
        """
        with self._history_lock:
            completed = sum(1 for w in self._history
                           if w.state == WorkerState.COMPLETED)
            failed = sum(1 for w in self._history
                        if w.state == WorkerState.FAILED)
            cancelled = sum(1 for w in self._history
                           if w.state == WorkerState.CANCELLED)

        return {
            'queue_size': self.get_queue_size(),
            'is_busy': self.is_busy(),
            'total_operations': len(self._history),
            'completed': completed,
            'failed': failed,
            'cancelled': cancelled,
            'success_rate': (completed / len(self._history) * 100)
                           if self._history else 0,
        }

    def _process_queue(self) -> None:
        """
        Background thread that processes queued operations.

        Runs continuously until stop() is called.
        """
        logger.debug("Queue processor started")

        while self._running:
            # Check for next operation
            operation = None

            with self._queue_lock:
                try:
                    operation = self._queue.get_nowait()
                except Empty:
                    pass

            if operation:
                self._run_operation(operation)
            else:
                # Check if pool is now idle
                if not self.is_busy():
                    self.pool_idle.emit()

                # Wait before checking again
                time.sleep(0.1)

        logger.debug("Queue processor stopped")

    def _run_operation(self, operation: QueuedOperation) -> None:
        """
        Execute a single operation.

        Args:
            operation: The operation to run
        """
        with self._operation_lock:
            self._current_operation = operation

        # Update worker info
        if operation.id in self._workers:
            info = self._workers[operation.id]
            info.state = WorkerState.RUNNING
            info.started_at = datetime.now()

        logger.info("Starting operation %d: %s", operation.id, operation.name)
        self.worker_started.emit(operation.id, operation.name)

        # Create thread
        thread = QThread()
        operation.worker.moveToThread(thread)

        # Result storage
        result = {'value': None, 'error': None}

        def on_progress(progress: int):
            if operation.id in self._workers:
                self._workers[operation.id].progress = progress
            self.worker_progress.emit(operation.id, progress)

        def on_completed(res):
            result['value'] = res

        def on_error(err: str):
            result['error'] = err

        # Connect signals
        thread.started.connect(operation.worker.execute)
        operation.worker.progress.connect(on_progress)
        operation.worker.finished.connect(thread.quit)

        # Check if worker has result-specific signals
        if hasattr(operation.worker, 'scan_complete'):
            operation.worker.scan_complete.connect(on_completed)
        if hasattr(operation.worker, 'format_complete'):
            operation.worker.format_complete.connect(on_completed)
        if hasattr(operation.worker, 'restore_complete'):
            operation.worker.restore_complete.connect(on_completed)
        if hasattr(operation.worker, 'analysis_complete'):
            operation.worker.analysis_complete.connect(on_completed)
        if hasattr(operation.worker, 'alignment_complete'):
            operation.worker.alignment_complete.connect(on_completed)

        # Error handling
        operation.worker.error.connect(on_error)
        operation.worker.device_error.connect(on_error)

        # Start thread
        self._current_thread = thread
        thread.start()

        # Wait for completion
        thread.wait(WORKER_SHUTDOWN_TIMEOUT_MS)

        # Update state based on result
        if operation.id in self._workers:
            info = self._workers[operation.id]
            info.completed_at = datetime.now()

            if operation.worker.is_cancelled():
                info.state = WorkerState.CANCELLED
                self.worker_cancelled.emit(operation.id, operation.name)
            elif result['error']:
                info.state = WorkerState.FAILED
                info.error_message = result['error']
                self.worker_failed.emit(operation.id, operation.name, result['error'])
            else:
                info.state = WorkerState.COMPLETED
                self.worker_completed.emit(operation.id, operation.name, result['value'])

            # Add to history
            with self._history_lock:
                self._history.append(info)
                # Trim history if needed
                while len(self._history) > MAX_HISTORY_SIZE:
                    self._history.pop(0)

        # Cleanup
        thread.deleteLater()

        with self._operation_lock:
            self._current_operation = None
            self._current_thread = None

        # Call user callback if provided
        if operation.callback and not result['error']:
            try:
                operation.callback(result['value'])
            except Exception as e:
                logger.warning("Callback failed for %s: %s", operation.name, e)

        self.queue_changed.emit(self._queue.qsize())

        logger.info("Operation %d complete: %s", operation.id, operation.name)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'WorkerPool',
    'OperationPriority',
    'WorkerState',
    'QueuedOperation',
    'WorkerInfo',
    'MAX_HISTORY_SIZE',
    'WORKER_SHUTDOWN_TIMEOUT_MS',
]
