"""
Partial results handling for Floppy Workbench.

Provides functionality to save operation state when interrupted, allowing
recovery or analysis of partial results.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


def save_partial_results(
    scan_data: Dict[str, Any],
    filename: str = "partial_scan.json"
) -> None:
    """
    Save scan results even if operation is interrupted.

    Preserves partial scan data to JSON file for recovery or analysis.
    Useful when operations are cancelled or encounter errors.

    Args:
        scan_data: Dictionary containing scan data with keys:
            - completed: bool - Whether scan completed
            - sectors_scanned: int - Number of sectors scanned
            - bad_sectors: list - List of bad sector numbers
            - error_types: dict - Mapping of sector -> error type
        filename: Output filename (default: "partial_scan.json")

    Example:
        >>> scan_data = {
        ...     'completed': False,
        ...     'sectors_scanned': 1500,
        ...     'bad_sectors': [0, 1, 100],
        ...     'error_types': {0: 'CRC Error', 1: 'CRC Error'}
        ... }
        >>> save_partial_results(scan_data)
    """
    try:
        data = {
            'timestamp': datetime.now().isoformat(),
            'completed': scan_data.get('completed', False),
            'sectors_scanned': scan_data.get('sectors_scanned', 0),
            'bad_sectors': scan_data.get('bad_sectors', []),
            'error_types': scan_data.get('error_types', {}),
        }

        # Ensure directory exists
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        logging.info(f"Partial results saved to {filename}")
        logging.info(
            f"Scanned {data['sectors_scanned']} sectors, "
            f"found {len(data['bad_sectors'])} bad sectors"
        )

    except Exception as e:
        logging.error(f"Failed to save partial results: {e}")


def load_partial_results(filename: str = "partial_scan.json") -> Optional[Dict[str, Any]]:
    """
    Load previously saved partial results.

    Args:
        filename: Input filename (default: "partial_scan.json")

    Returns:
        Dictionary with scan data, or None if file doesn't exist or is invalid

    Example:
        >>> previous_scan = load_partial_results()
        >>> if previous_scan:
        ...     print(f"Previously scanned {previous_scan['sectors_scanned']} sectors")
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        logging.info(f"Loaded partial results from {filename}")
        return data

    except FileNotFoundError:
        logging.debug(f"No partial results file found: {filename}")
        return None

    except Exception as e:
        logging.error(f"Failed to load partial results: {e}")
        return None


def save_recovery_progress(
    pass_num: int,
    bad_sector_history: List[int],
    current_scan_data: Dict[str, Any],
    filename: str = "recovery_progress.json"
) -> None:
    """
    Save recovery operation progress.

    Args:
        pass_num: Current pass number
        bad_sector_history: List of bad sector counts per pass
        current_scan_data: Current scan results
        filename: Output filename (default: "recovery_progress.json")

    Example:
        >>> save_recovery_progress(
        ...     pass_num=3,
        ...     bad_sector_history=[147, 89, 45, 23],
        ...     current_scan_data={'bad_sectors': [0, 5, 10, ...]}
        ... )
    """
    try:
        data = {
            'timestamp': datetime.now().isoformat(),
            'passes_completed': pass_num,
            'bad_sector_history': bad_sector_history,
            'current_bad_sectors': current_scan_data.get('bad_sectors', []),
            'completed': False,
        }

        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        logging.info(f"Recovery progress saved: pass {pass_num + 1}")

    except Exception as e:
        logging.error(f"Failed to save recovery progress: {e}")


class RecoveryWorker:
    """
    Worker class for graceful recovery operation cancellation.

    Manages a recovery operation with support for cancellation at any point,
    saving partial results before stopping.

    Attributes:
        handle: Linux file descriptor to physical drive
        geometry: Disk geometry information
        options: Recovery options (passes, convergence_mode, etc.)
        cancelled: Flag indicating if operation has been cancelled

    Example:
        >>> worker = RecoveryWorker(handle, geometry, options)
        >>> # In another thread:
        >>> worker.cancel()
        >>> # Worker will save partial results and return None
    """

    def __init__(self, handle, geometry, options):
        """
        Initialize recovery worker.

        Args:
            handle: Linux file descriptor to physical drive
            geometry: DiskGeometry object
            options: Dictionary or object with recovery options:
                - passes: int - Number of passes (fixed mode)
                - convergence_mode: bool - Use convergence detection
                - max_passes: int - Maximum passes (convergence mode)
        """
        self.handle = handle
        self.geometry = geometry
        self.options = options
        self.cancelled = False
        self.current_pass = 0
        self.bad_sector_history = []

    def cancel(self) -> None:
        """
        Request cancellation of the recovery operation.

        Sets the cancelled flag, which will be checked at the start of
        each pass. The operation will save partial results and return None.
        """
        self.cancelled = True
        logging.info("Recovery cancellation requested")

    def run_recovery(self, progress_callback=None) -> Optional[Any]:
        """
        Run the recovery operation with cancellation support.

        Performs multi-pass recovery, checking for cancellation at each pass.
        If cancelled, saves partial results before returning.

        Args:
            progress_callback: Optional callback function(pass_num, details)

        Returns:
            Final recovery statistics if completed, None if cancelled

        Example:
            >>> def on_progress(pass_num, details):
            ...     print(f"Pass {pass_num}: {details}")
            >>> result = worker.run_recovery(on_progress)
            >>> if result is None:
            ...     print("Operation was cancelled")
        """
        from floppy_formatter.core import recover_disk

        try:
            # Determine pass count
            if hasattr(self.options, 'convergence_mode'):
                convergence_mode = self.options.convergence_mode
                passes = self.options.max_passes if convergence_mode else self.options.passes
            else:
                # Dictionary-based options
                convergence_mode = self.options.get('convergence_mode', False)
                passes = self.options.get('max_passes' if convergence_mode else 'passes', 5)

            # Create internal progress callback that checks cancellation
            def internal_progress_callback(*args, **kwargs):
                if self.cancelled:
                    # Save partial results
                    self._save_partial_state()
                    raise InterruptedError("Operation cancelled by user")

                if progress_callback:
                    progress_callback(*args, **kwargs)

            # Run recovery
            result = recover_disk(
                self.handle,
                self.geometry,
                passes=passes,
                convergence_mode=convergence_mode,
                progress_callback=internal_progress_callback
            )

            return result

        except InterruptedError:
            logging.info("Recovery operation cancelled")
            return None

        except Exception as e:
            logging.error(f"Recovery operation failed: {e}")
            self._save_partial_state()
            raise

    def _save_partial_state(self) -> None:
        """Save current recovery state to file."""
        try:
            scan_data = {
                'completed': False,
                'passes_completed': self.current_pass,
                'bad_sector_history': self.bad_sector_history,
                'timestamp': datetime.now().isoformat(),
            }

            save_recovery_progress(
                self.current_pass,
                self.bad_sector_history,
                scan_data
            )

        except Exception as e:
            logging.error(f"Failed to save partial state: {e}")
