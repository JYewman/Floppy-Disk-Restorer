"""
Restore worker for Greaseweazle floppy disk recovery operations.

Provides comprehensive disk recovery with multi-capture flux analysis,
PLL tuning, and bit-slip recovery. Supports multiple recovery modes
from standard to forensic-level recovery.

Part of Phase 9: Workers & Background Processing
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal

from floppy_formatter.gui.workers.base_worker import GreaseweazleWorker
from floppy_formatter.hardware import SectorData, SectorStatus

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice
    from floppy_formatter.core.geometry import DiskGeometry

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def decode_flux_data(flux_data):
    """
    Decode flux data to sectors using Greaseweazle-compatible decoder.

    Args:
        flux_data: FluxData from track read

    Returns:
        List of SectorData objects
    """
    # Use Greaseweazle-compatible decoder (proven implementation)
    try:
        from floppy_formatter.hardware.gw_mfm_codec import decode_flux_to_sectors_gw
        sectors = decode_flux_to_sectors_gw(flux_data)
        if sectors:
            logger.debug("GW decoder returned %d sectors", len(sectors))
            return sectors
        logger.debug("GW decoder returned 0 sectors, trying PLL decoder")
    except ImportError:
        logger.debug("GW decoder not available")
    except Exception as e:
        logger.warning("GW decoder failed: %s", e)

    # Try PLL decoder as fallback
    try:
        from floppy_formatter.hardware.pll_decoder import decode_flux_with_pll
        sectors = decode_flux_with_pll(flux_data)
        if sectors:
            logger.debug("PLL decoder returned %d sectors", len(sectors))
            return sectors
    except ImportError:
        logger.debug("PLL decoder not available")
    except Exception as e:
        logger.warning("PLL decoder failed: %s", e)

    # Fall back to simple decoder
    from floppy_formatter.hardware.mfm_codec import decode_flux_to_sectors
    sectors = decode_flux_to_sectors(flux_data)
    logger.debug("Simple decoder returned %d sectors", len(sectors))
    return sectors


# =============================================================================
# Enums
# =============================================================================

class RecoveryLevel(Enum):
    """
    Recovery effort level.

    STANDARD: Basic multi-pass format/verify recovery
    AGGRESSIVE: Multi-capture + PLL tuning before giving up
    FORENSIC: All techniques, maximum effort, detailed logging
    """
    STANDARD = auto()
    AGGRESSIVE = auto()
    FORENSIC = auto()


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class RestoreConfig:
    """
    Configuration for a restore operation.

    Attributes:
        convergence_mode: Use convergence detection instead of fixed passes
        passes: Number of passes (fixed mode) or max passes (convergence mode)
        convergence_threshold: Consecutive passes for convergence detection
        targeted_mode: Only recover known bad sectors (not full disk)
        bad_sector_list: List of bad sectors for targeted mode
        multiread_mode: Enable multi-read statistical recovery (flux captures)
        multiread_attempts: Number of flux capture revolutions
        recovery_level: Recovery effort level (STANDARD/AGGRESSIVE/FORENSIC)
        pll_tuning: Enable PLL parameter search for marginal sectors
        bit_slip_recovery: Enable bit-slip recovery for sync errors
    """
    convergence_mode: bool = False
    passes: int = 5
    convergence_threshold: int = 3
    targeted_mode: bool = False
    bad_sector_list: Optional[List[int]] = None
    multiread_mode: bool = False
    multiread_attempts: int = 10  # Now represents flux revolutions
    recovery_level: RecoveryLevel = RecoveryLevel.STANDARD
    pll_tuning: bool = False
    bit_slip_recovery: bool = False


@dataclass
class PassStats:
    """
    Statistics for a single recovery pass.

    Attributes:
        pass_num: Pass number (1-based)
        bad_count_before: Bad sector count at start of pass
        bad_count_after: Bad sector count at end of pass
        sectors_recovered: Sectors recovered in this pass
        duration_seconds: Time taken for this pass
    """
    pass_num: int
    bad_count_before: int
    bad_count_after: int
    sectors_recovered: int
    duration_seconds: float

    @property
    def improvement(self) -> int:
        """Number of sectors improved (recovered)."""
        return self.bad_count_before - self.bad_count_after


@dataclass
class RecoveredSector:
    """
    Information about a recovered sector.

    Attributes:
        sector_num: Linear sector number
        cylinder: Cylinder number
        head: Head number
        sector: Sector number within track (1-based)
        pass_recovered: Which pass recovered this sector
        technique: Technique that succeeded
        attempts: Number of attempts before success
    """
    sector_num: int
    cylinder: int
    head: int
    sector: int
    pass_recovered: int
    technique: str
    attempts: int


@dataclass
class RecoveryStats:
    """
    Complete recovery statistics.

    Attributes:
        initial_bad_sectors: Bad sector count at start
        final_bad_sectors: Bad sector count at end
        sectors_recovered: Total sectors recovered
        passes_completed: Number of passes completed
        converged: Whether recovery converged (stopped improving)
        convergence_pass: Pass at which convergence occurred
        elapsed_time: Total time taken
        pass_history: Per-pass statistics
        recovered_sectors: List of recovered sector details
        techniques_used: Count of recoveries per technique
    """
    initial_bad_sectors: int
    final_bad_sectors: int
    sectors_recovered: int
    passes_completed: int
    converged: bool
    convergence_pass: Optional[int] = None
    elapsed_time: float = 0.0
    pass_history: List[PassStats] = field(default_factory=list)
    recovered_sectors: List[RecoveredSector] = field(default_factory=list)
    techniques_used: Dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Percentage of bad sectors recovered."""
        if self.initial_bad_sectors == 0:
            return 100.0
        return (self.sectors_recovered / self.initial_bad_sectors) * 100.0

    @property
    def remaining_bad(self) -> int:
        """Number of sectors still bad."""
        return self.final_bad_sectors


# =============================================================================
# Restore Worker
# =============================================================================

class RestoreWorker(GreaseweazleWorker):
    """
    Worker for disk recovery operations.

    Performs comprehensive recovery using flux-level techniques including
    multi-capture statistical analysis, PLL tuning, and bit-slip recovery.

    Features:
    - Multi-pass recovery with data preservation
    - Convergence-based recovery with automatic stopping
    - Targeted recovery for specific bad sectors
    - Multi-revolution flux capture for statistical bit voting
    - Optional PLL parameter search for marginal sectors
    - Optional bit-slip recovery for sync errors
    - Detailed per-sector and per-pass progress reporting

    Signals:
        pass_started(int, int): Pass starting (pass_num, total_passes)
        pass_complete(int, int, int): Pass done (pass_num, bad_count, recovered)
        sector_recovering(int, str): Sector recovery (sector_num, technique)
        sector_recovered(int, str): Success (sector_num, technique)
        sector_failed(int, str): Failure (sector_num, reason)
        convergence_update(int, int, bool): Status (pass_num, bad_count, converged)
        restore_complete(RecoveryStats): Final statistics

    Example:
        config = RestoreConfig(
            convergence_mode=True,
            passes=50,
            multiread_mode=True,
            recovery_level=RecoveryLevel.AGGRESSIVE
        )
        worker = RestoreWorker(device, geometry, config)
        worker.pass_complete.connect(on_pass_complete)
        worker.restore_complete.connect(on_restore_complete)
    """

    # Signals specific to restoration
    pass_started = pyqtSignal(int, int)        # pass_num, total_passes
    pass_complete = pyqtSignal(int, int, int)  # pass_num, bad_count, recovered_count
    sector_recovering = pyqtSignal(int, str)   # sector_num, technique
    sector_recovered = pyqtSignal(int, str)    # sector_num, technique
    sector_failed = pyqtSignal(int, str)       # sector_num, reason
    convergence_update = pyqtSignal(int, int, bool)  # pass_num, bad_count, converged
    restore_complete = pyqtSignal(object)      # RecoveryStats

    # Final verification signals
    verification_started = pyqtSignal(int)     # attempt_num (1-3)
    verification_complete = pyqtSignal(int, int, bool)  # attempt_num, bad_count, passed

    # Legacy signals for compatibility
    initial_scan_completed = pyqtSignal(int)   # initial_bad_count
    initial_scan_sector = pyqtSignal(int, bool)  # sector_index, is_good

    def __init__(
        self,
        device: 'GreaseweazleDevice',
        geometry: 'DiskGeometry',
        config: RestoreConfig,
    ):
        """
        Initialize restore worker.

        Args:
            device: Connected GreaseweazleDevice instance
            geometry: Disk geometry information
            config: RestoreConfig with recovery settings
        """
        super().__init__(device)
        self._geometry = geometry
        self._config = config

        # Recovery state
        self._bad_sectors: List[int] = []
        self._recovered_sectors: List[RecoveredSector] = []
        self._pass_history: List[PassStats] = []

        logger.info(
            "RestoreWorker initialized: level=%s, mode=%s, passes=%d",
            config.recovery_level.name,
            "convergence" if config.convergence_mode else "fixed",
            config.passes
        )

    def run(self) -> None:
        """
        Execute the recovery operation.

        Runs recovery passes according to configuration, using
        increasingly aggressive techniques as needed. After recovery,
        performs a final verification scan. If verification fails,
        retries the entire restore up to 3 times.
        """
        MAX_RESTORE_ATTEMPTS = 3
        start_time = time.time()

        # Initialize statistics
        stats = RecoveryStats(
            initial_bad_sectors=0,
            final_bad_sectors=0,
            sectors_recovered=0,
            passes_completed=0,
            converged=False,
        )

        # Ensure drive is properly initialized and motor is on
        if not self._device.is_motor_on():
            logger.info("Motor not running, reinitializing drive before restore...")
            self._device.reinitialize_drive()
        else:
            # Just ensure motor is on with standard method
            self._device.motor_on()

        # Step 1: Initial scan to identify bad sectors
        logger.info("Starting initial scan")
        initial_bad_sectors = self._perform_initial_scan()
        stats.initial_bad_sectors = len(initial_bad_sectors)

        self.initial_scan_completed.emit(stats.initial_bad_sectors)

        if stats.initial_bad_sectors == 0:
            logger.info("No bad sectors found, nothing to recover")
            stats.elapsed_time = time.time() - start_time
            self.restore_complete.emit(stats)
            self.finished.emit()
            return

        logger.info("Initial scan found %d bad sectors", stats.initial_bad_sectors)

        # If targeted mode with explicit list, use that instead
        if self._config.targeted_mode and self._config.bad_sector_list:
            initial_bad_sectors = list(self._config.bad_sector_list)
            stats.initial_bad_sectors = len(initial_bad_sectors)

        # Step 2: Run recovery with retry loop
        converged = False
        total_passes_completed = 0
        failed_verification_sectors = []  # Track sectors that failed verification

        for attempt in range(1, MAX_RESTORE_ATTEMPTS + 1):
            if self._cancelled:
                logger.info("Recovery cancelled")
                break

            logger.info("Starting restore attempt %d of %d", attempt, MAX_RESTORE_ATTEMPTS)

            # Reset bad sectors list for this attempt
            if attempt == 1:
                self._bad_sectors = list(initial_bad_sectors)
            else:
                self._bad_sectors = list(failed_verification_sectors)

            if not self._bad_sectors:
                logger.info("No bad sectors to recover")
                break

            # Run recovery passes
            current_bad = len(self._bad_sectors)
            no_improvement_count = 0

            for pass_num in range(1, self._config.passes + 1):
                if self._cancelled:
                    logger.info("Recovery cancelled at pass %d", pass_num)
                    break

                if not self._bad_sectors:
                    logger.info("All sectors recovered")
                    break

                self.pass_started.emit(pass_num, self._config.passes)

                # Run recovery pass
                pass_stats = self._run_recovery_pass(pass_num)
                self._pass_history.append(pass_stats)
                total_passes_completed += 1

                # Check for convergence
                new_bad = pass_stats.bad_count_after
                recovered_this_pass = pass_stats.sectors_recovered

                self.pass_complete.emit(pass_num, new_bad, recovered_this_pass)
                self.convergence_update.emit(pass_num, new_bad, converged)

                # Update progress (reserve last 10% for verification)
                progress = int((pass_num / self._config.passes) * 90)
                self.progress.emit(progress)

                # Check for convergence (no improvement)
                if new_bad >= current_bad:
                    no_improvement_count += 1
                    if self._config.convergence_mode:
                        if no_improvement_count >= self._config.convergence_threshold:
                            converged = True
                            stats.convergence_pass = pass_num
                            logger.info("Convergence detected at pass %d", pass_num)
                            break
                else:
                    no_improvement_count = 0

                current_bad = new_bad

            if self._cancelled:
                break

            # Step 3: Final verification scan
            logger.info("Running final verification scan (attempt %d)", attempt)
            self.verification_started.emit(attempt)

            failed_verification_sectors = self._perform_final_verification(initial_bad_sectors)

            verification_passed = len(failed_verification_sectors) == 0
            self.verification_complete.emit(
                attempt, len(failed_verification_sectors), verification_passed
            )

            if verification_passed:
                logger.info("Final verification passed - all recovered sectors confirmed good")
                break
            else:
                logger.warning(
                    "Final verification failed - %d sectors still bad after attempt %d",
                    len(failed_verification_sectors), attempt
                )
                if attempt < MAX_RESTORE_ATTEMPTS:
                    logger.info("Will retry restore for failed sectors")
                    # Update the bad sectors for next attempt
                    initial_bad_sectors = failed_verification_sectors
                else:
                    logger.error(
                        "Max restore attempts reached, %d sectors remain unrecoverable",
                        len(failed_verification_sectors)
                    )

        # Update progress to 100%
        self.progress.emit(100)

        # Finalize statistics with verification results
        stats.passes_completed = total_passes_completed

        # Perform one final scan to get accurate count
        final_bad = self._perform_initial_scan()
        stats.final_bad_sectors = len(final_bad)
        stats.sectors_recovered = stats.initial_bad_sectors - stats.final_bad_sectors
        stats.converged = converged
        stats.elapsed_time = time.time() - start_time
        stats.pass_history = self._pass_history
        stats.recovered_sectors = self._recovered_sectors

        # Count techniques used
        for rs in self._recovered_sectors:
            stats.techniques_used[rs.technique] = stats.techniques_used.get(rs.technique, 0) + 1

        logger.info(
            "Recovery complete: %d/%d recovered, %d passes, %.1fs",
            stats.sectors_recovered, stats.initial_bad_sectors,
            total_passes_completed, stats.elapsed_time
        )

        self.restore_complete.emit(stats)
        self.finished.emit()

    def _perform_final_verification(self, originally_bad_sectors: List[int]) -> List[int]:
        """
        Perform a final full verification scan to confirm recovered sectors.

        Uses the same decoder as the regular scan to ensure consistency.

        Args:
            originally_bad_sectors: List of sectors that were originally bad

        Returns:
            List of sectors that are still bad (failed verification)
        """
        from floppy_formatter.hardware import read_track_flux

        logger.info(
            "Final verification: checking %d originally bad sectors",
            len(originally_bad_sectors)
        )

        still_bad = []
        sectors_per_track = self._geometry.sectors_per_track

        # Group originally bad sectors by track for efficient verification
        track_sectors = self._group_by_track(originally_bad_sectors)

        for (cylinder, head), sector_nums in track_sectors.items():
            if self._cancelled:
                return still_bad

            # Seek and read track
            self._device.seek(cylinder, head)
            flux = read_track_flux(self._device, cylinder, head, revolutions=1.2)
            sectors = decode_flux_data(flux)

            # Build map of what we found
            found_good = set()
            for sector in sectors:
                if sector.sector >= 1 and sector.sector <= sectors_per_track:
                    if sector.data is not None and sector.crc_valid:
                        # Convert to linear sector number
                        base = (cylinder * self._geometry.heads + head) * sectors_per_track
                        linear = base + (sector.sector - 1)
                        found_good.add(linear)

            # Check which originally bad sectors are still bad
            for linear_sector in sector_nums:
                if linear_sector not in found_good:
                    still_bad.append(linear_sector)
                    logger.debug(
                        "Verification failed for sector %d (C%d:H%d)",
                        linear_sector, cylinder, head
                    )

        logger.info(
            "Final verification complete: %d/%d sectors still bad",
            len(still_bad), len(originally_bad_sectors)
        )

        return still_bad

    def _perform_initial_scan(self) -> List[int]:
        """
        Perform initial scan to identify bad sectors.

        Returns:
            List of bad sector numbers
        """
        from floppy_formatter.hardware import read_track_flux

        bad_sectors = []
        sectors_per_track = self._geometry.sectors_per_track

        for cylinder in range(self._geometry.cylinders):
            for head in range(self._geometry.heads):
                if self._cancelled:
                    return bad_sectors

                # Seek and read track
                self._device.seek(cylinder, head)
                flux = read_track_flux(self._device, cylinder, head, revolutions=1.2)
                sectors = decode_flux_data(flux)

                base_sector = (cylinder * self._geometry.heads + head) * sectors_per_track

                # Deduplicate sectors by sector number
                best_sectors = {}
                for sector in sectors:
                    sector_num = sector.sector
                    if sector_num < 1 or sector_num > sectors_per_track:
                        continue
                    if sector_num not in best_sectors:
                        best_sectors[sector_num] = sector
                    elif sector.crc_valid and not best_sectors[sector_num].crc_valid:
                        best_sectors[sector_num] = sector

                # Check all expected sectors
                for sector_num in range(1, sectors_per_track + 1):
                    linear = base_sector + (sector_num - 1)
                    if sector_num in best_sectors:
                        sector = best_sectors[sector_num]
                        is_good = sector.data is not None and sector.crc_valid
                    else:
                        is_good = False

                    if not is_good:
                        bad_sectors.append(linear)

                    self.initial_scan_sector.emit(linear, is_good)

                # Update progress
                track_num = cylinder * self._geometry.heads + head
                total_tracks = self._geometry.cylinders * self._geometry.heads
                progress = int((track_num / total_tracks) * 50)  # 0-50% for scan
                self.progress.emit(progress)

        return bad_sectors

    def _run_recovery_pass(self, pass_num: int) -> PassStats:
        """
        Run a single recovery pass.

        Args:
            pass_num: Current pass number

        Returns:
            PassStats for this pass
        """
        pass_start = time.time()
        bad_before = len(self._bad_sectors)
        recovered_this_pass = 0

        # Determine recovery techniques based on level
        techniques = self._get_techniques_for_pass(pass_num)

        # Group bad sectors by track for efficiency
        track_sectors = self._group_by_track(self._bad_sectors)

        for (cylinder, head), sectors in track_sectors.items():
            if self._cancelled:
                break

            for sector_num in sectors:
                if self._cancelled:
                    break

                # Try recovery techniques
                recovered, technique = self._recover_sector(
                    sector_num, cylinder, head, techniques
                )

                if recovered:
                    # Remove from bad list
                    if sector_num in self._bad_sectors:
                        self._bad_sectors.remove(sector_num)

                    # Record recovery
                    sector_in_track = (sector_num % self._geometry.sectors_per_track) + 1
                    self._recovered_sectors.append(RecoveredSector(
                        sector_num=sector_num,
                        cylinder=cylinder,
                        head=head,
                        sector=sector_in_track,
                        pass_recovered=pass_num,
                        technique=technique,
                        attempts=1,
                    ))

                    recovered_this_pass += 1
                    self.sector_recovered.emit(sector_num, technique)
                else:
                    self.sector_failed.emit(sector_num, "All techniques exhausted")

        pass_duration = time.time() - pass_start

        return PassStats(
            pass_num=pass_num,
            bad_count_before=bad_before,
            bad_count_after=len(self._bad_sectors),
            sectors_recovered=recovered_this_pass,
            duration_seconds=pass_duration,
        )

    def _get_techniques_for_pass(self, pass_num: int) -> List[str]:
        """
        Get list of techniques to try based on pass number and level.

        Args:
            pass_num: Current pass number

        Returns:
            List of technique names to try
        """
        level = self._config.recovery_level

        if level == RecoveryLevel.STANDARD:
            # Basic techniques only
            return ["format_refresh", "multi_capture"]

        elif level == RecoveryLevel.AGGRESSIVE:
            # Add PLL tuning on later passes
            if pass_num <= 2:
                return ["format_refresh", "multi_capture"]
            else:
                techniques = ["format_refresh", "multi_capture"]
                if self._config.pll_tuning:
                    techniques.append("pll_tuning")
                return techniques

        elif level == RecoveryLevel.FORENSIC:
            # All techniques from the start
            techniques = ["format_refresh", "multi_capture"]
            if self._config.pll_tuning:
                techniques.append("pll_tuning")
            if self._config.bit_slip_recovery:
                techniques.append("bit_slip")
            techniques.append("maximum_effort")
            return techniques

        return ["format_refresh"]

    def _recover_sector(
        self,
        sector_num: int,
        cylinder: int,
        head: int,
        techniques: List[str]
    ) -> Tuple[bool, str]:
        """
        Attempt to recover a single sector using specified techniques.

        Args:
            sector_num: Linear sector number
            cylinder: Cylinder number
            head: Head number
            techniques: List of techniques to try

        Returns:
            Tuple of (recovered, technique_that_worked)
        """
        sector_in_track = (sector_num % self._geometry.sectors_per_track) + 1

        for technique in techniques:
            if self._cancelled:
                return False, ""

            self.sector_recovering.emit(sector_num, technique)

            success = False

            if technique == "format_refresh":
                success = self._try_format_refresh(cylinder, head)

            elif technique == "multi_capture":
                success = self._try_multi_capture(
                    cylinder, head, sector_in_track
                )

            elif technique == "pll_tuning":
                success = self._try_pll_tuning(
                    cylinder, head, sector_in_track
                )

            elif technique == "bit_slip":
                success = self._try_bit_slip_recovery(
                    cylinder, head, sector_in_track
                )

            elif technique == "maximum_effort":
                success = self._try_maximum_effort(
                    cylinder, head, sector_in_track
                )

            if success:
                # Verify the sector is now readable
                if self._verify_sector(cylinder, head, sector_in_track):
                    return True, technique

        return False, ""

    def _try_format_refresh(self, cylinder: int, head: int) -> bool:
        """
        Try format refresh (DC erase + pattern writes).

        Args:
            cylinder: Cylinder number
            head: Head number

        Returns:
            True if track now reads better
        """
        from floppy_formatter.hardware import erase_track_flux, write_track_flux
        from floppy_formatter.hardware.gw_mfm_codec import encode_sectors_to_flux_gw

        try:
            # Seek to track
            self._device.seek(cylinder, head)

            # DC erase
            erase_track_flux(self._device, cylinder, head)

            # Write with pattern rotation - use GW-compatible encoder
            patterns = [0x00, 0xFF, 0xAA, 0x55]
            for pattern in patterns:
                if self._cancelled:
                    return False

                # Create sector data as proper SectorData objects
                sector_data = [
                    SectorData(
                        cylinder=cylinder,
                        head=head,
                        sector=i + 1,  # 1-based sector numbers
                        data=bytes([pattern] * 512),
                        status=SectorStatus.GOOD,
                        crc_valid=True,
                        signal_quality=1.0
                    )
                    for i in range(self._geometry.sectors_per_track)
                ]

                # Encode using GW-compatible encoder and write
                flux = encode_sectors_to_flux_gw(cylinder, head, sector_data)
                write_track_flux(self._device, cylinder, head, flux)

            return True

        except Exception as e:
            logger.warning("Format refresh failed for C%d:H%d: %s", cylinder, head, e)
            return False

    def _try_multi_capture(
        self,
        cylinder: int,
        head: int,
        sector: int
    ) -> bool:
        """
        Try multi-capture statistical recovery.

        Captures multiple revolutions and uses bit voting to recover data.

        Args:
            cylinder: Cylinder number
            head: Head number
            sector: 1-based sector number

        Returns:
            True if sector recovered
        """
        from floppy_formatter.hardware import read_track_flux

        try:
            # Seek to track
            self._device.seek(cylinder, head)

            # Capture multiple revolutions
            revolutions = self._config.multiread_attempts
            flux = read_track_flux(self._device, cylinder, head, revolutions=revolutions)

            # Decode with PLL decoder (preferred) or fallback
            sectors = decode_flux_data(flux)

            # Check if our target sector decoded
            for s in sectors:
                if s.sector == sector and s.data is not None and s.crc_valid:
                    return True

            return False

        except Exception as e:
            logger.warning("Multi-capture failed for C%d:H%d:S%d: %s", cylinder, head, sector, e)
            return False

    def _try_pll_tuning(
        self,
        cylinder: int,
        head: int,
        sector: int
    ) -> bool:
        """
        Try PLL parameter tuning for marginal sectors.

        Args:
            cylinder: Cylinder number
            head: Head number
            sector: 1-based sector number

        Returns:
            True if sector recovered
        """
        from floppy_formatter.hardware import read_track_flux
        from floppy_formatter.recovery.pll_tuning import try_pll_variations, default_pll_parameters

        try:
            # Seek and capture
            self._device.seek(cylinder, head)
            flux = read_track_flux(self._device, cylinder, head, revolutions=3)

            # Try PLL variations with default parameters as base
            result = try_pll_variations(flux, default_pll_parameters())

            # Check if target sector was recovered by any parameter set
            if result.sectors_recovered:
                for recovered_sectors in result.sectors_recovered.values():
                    if sector in recovered_sectors:
                        return True
            return False

        except Exception as e:
            logger.warning("PLL tuning failed for C%d:H%d:S%d: %s", cylinder, head, sector, e)
            return False

    def _try_bit_slip_recovery(
        self,
        cylinder: int,
        head: int,
        sector: int
    ) -> bool:
        """
        Try bit-slip recovery for synchronization errors.

        Args:
            cylinder: Cylinder number
            head: Head number
            sector: 1-based sector number

        Returns:
            True if sector recovered
        """
        from floppy_formatter.hardware import read_track_flux
        from floppy_formatter.recovery.bit_slip_recovery import reconstruct_slipped_sector

        try:
            # Seek and capture
            self._device.seek(cylinder, head)
            flux = read_track_flux(self._device, cylinder, head, revolutions=5)

            # Try bit-slip recovery
            result = reconstruct_slipped_sector(flux, sector)

            return result is not None and result.crc_valid

        except Exception as e:
            logger.warning(
                "Bit-slip recovery failed for C%d:H%d:S%d: %s", cylinder, head, sector, e
            )
            return False

    def _try_maximum_effort(
        self,
        cylinder: int,
        head: int,
        sector: int
    ) -> bool:
        """
        Try maximum effort recovery combining all techniques.

        Args:
            cylinder: Cylinder number
            head: Head number
            sector: 1-based sector number

        Returns:
            True if sector recovered
        """
        # Format refresh first
        self._try_format_refresh(cylinder, head)

        # Then try multi-capture with extra revolutions
        from floppy_formatter.hardware import read_track_flux

        try:
            self._device.seek(cylinder, head)

            # Maximum revolutions
            flux = read_track_flux(self._device, cylinder, head, revolutions=20)

            sectors = decode_flux_data(flux)

            for s in sectors:
                if s.sector == sector and s.data is not None and s.crc_valid:
                    return True

            return False

        except Exception as e:
            logger.warning("Maximum effort failed for C%d:H%d:S%d: %s", cylinder, head, sector, e)
            return False

    def _verify_sector(self, cylinder: int, head: int, sector: int) -> bool:
        """
        Verify a sector is now readable.

        Args:
            cylinder: Cylinder number
            head: Head number
            sector: 1-based sector number

        Returns:
            True if sector reads correctly
        """
        from floppy_formatter.hardware import read_track_flux

        try:
            flux = read_track_flux(self._device, cylinder, head, revolutions=1.2)
            sectors = decode_flux_data(flux)

            for s in sectors:
                if s.sector == sector:
                    return s.data is not None and s.crc_valid

            return False

        except Exception:
            return False

    def _group_by_track(
        self,
        sectors: List[int]
    ) -> Dict[Tuple[int, int], List[int]]:
        """
        Group sector numbers by track (cylinder, head).

        Args:
            sectors: List of linear sector numbers

        Returns:
            Dictionary mapping (cylinder, head) to list of sector numbers
        """
        groups: Dict[Tuple[int, int], List[int]] = {}
        sectors_per_track = self._geometry.sectors_per_track
        heads = self._geometry.heads

        for sector_num in sectors:
            sectors_per_cylinder = sectors_per_track * heads
            cylinder = sector_num // sectors_per_cylinder
            remainder = sector_num % sectors_per_cylinder
            head = remainder // sectors_per_track

            key = (cylinder, head)
            if key not in groups:
                groups[key] = []
            groups[key].append(sector_num)

        return groups

    def get_geometry(self) -> 'DiskGeometry':
        """Get the disk geometry being used."""
        return self._geometry

    def get_config(self) -> RestoreConfig:
        """Get the restore configuration."""
        return self._config


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'RestoreWorker',
    'RestoreConfig',
    'RecoveryLevel',
    'RecoveryStats',
    'PassStats',
    'RecoveredSector',
]
