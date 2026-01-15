"""
Scan worker for Greaseweazle floppy disk operations.

Provides track-at-a-time scanning with optional flux capture for
comprehensive surface analysis. Supports multiple scan modes for
different use cases from quick sampling to thorough multi-pass analysis.

Part of Phase 9: Workers & Background Processing
"""

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Dict, Optional, Tuple, Any, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal

from floppy_formatter.gui.workers.base_worker import GreaseweazleWorker

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice
    from floppy_formatter.core.geometry import DiskGeometry
    from floppy_formatter.analysis.flux_analyzer import FluxCapture

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class ScanMode(Enum):
    """
    Scan mode determining thoroughness and speed.

    QUICK: Sample tracks only (tracks 0, 40, 79 plus random)
    STANDARD: All tracks with single flux capture
    THOROUGH: All tracks with multi-revolution capture for quality assessment
    """
    QUICK = auto()
    STANDARD = auto()
    THOROUGH = auto()


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SectorResult:
    """
    Result of scanning a single sector.

    Attributes:
        sector_num: 1-based sector number within track
        linear_sector: Linear sector number (0-2879)
        is_good: True if sector read successfully
        error_type: Error description if failed, None if good
        crc_valid: True if CRC check passed
        data_hash: Hash of sector data (for comparison)
        flux_quality: Signal quality score (0.0-1.0) if available
    """
    sector_num: int
    linear_sector: int
    is_good: bool
    error_type: Optional[str] = None
    crc_valid: bool = True
    data_hash: Optional[str] = None
    flux_quality: float = 1.0


@dataclass
class TrackResult:
    """
    Result of scanning an entire track.

    Attributes:
        cylinder: Cylinder number (0-79)
        head: Head number (0-1)
        sector_results: List of results for each sector
        good_count: Number of good sectors
        bad_count: Number of bad sectors
        flux_captured: True if raw flux was saved
        average_quality: Average signal quality (0.0-1.0)
        scan_time_ms: Time to scan this track in milliseconds
    """
    cylinder: int
    head: int
    sector_results: List[SectorResult] = field(default_factory=list)
    good_count: int = 0
    bad_count: int = 0
    flux_captured: bool = False
    average_quality: float = 1.0
    scan_time_ms: float = 0.0

    @property
    def track_number(self) -> int:
        """Linear track number (0-159)."""
        return self.cylinder * 2 + self.head

    @property
    def is_perfect(self) -> bool:
        """True if all sectors are good."""
        return self.bad_count == 0

    @property
    def success_rate(self) -> float:
        """Percentage of good sectors."""
        total = self.good_count + self.bad_count
        if total == 0:
            return 0.0
        return (self.good_count / total) * 100.0


@dataclass
class ScanResult:
    """
    Complete scan result containing all track data.

    Attributes:
        total_sectors: Total number of sectors scanned
        good_sectors: List of good sector numbers
        bad_sectors: List of bad sector numbers
        error_types: Mapping of sector number to error description
        track_results: List of per-track results
        scan_duration: Total scan time in seconds
        mode: Scan mode used
        timestamp: When scan was performed
    """
    total_sectors: int
    good_sectors: List[int] = field(default_factory=list)
    bad_sectors: List[int] = field(default_factory=list)
    error_types: Dict[int, str] = field(default_factory=dict)
    track_results: List[TrackResult] = field(default_factory=list)
    scan_duration: float = 0.0
    mode: ScanMode = ScanMode.STANDARD
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def health_percentage(self) -> float:
        """Overall disk health as percentage."""
        if self.total_sectors == 0:
            return 0.0
        return (len(self.good_sectors) / self.total_sectors) * 100.0

    @property
    def bad_track_count(self) -> int:
        """Number of tracks with at least one bad sector."""
        return sum(1 for t in self.track_results if t.bad_count > 0)

    def get_sector_error(self, sector: int) -> Optional[str]:
        """Get error description for a sector."""
        return self.error_types.get(sector)


# =============================================================================
# Scan Worker
# =============================================================================

class ScanWorker(GreaseweazleWorker):
    """
    Worker for scanning floppy disk surfaces.

    Performs track-at-a-time scanning using Greaseweazle flux captures
    and MFM decoding. Supports multiple scan modes for different
    thoroughness levels.

    Features:
    - Efficient track-at-a-time scanning (one flux capture per track)
    - Optional raw flux data capture for analysis
    - Multiple scan modes (quick/standard/thorough)
    - Real-time progress and sector status reporting
    - Flux quality metrics per sector

    Signals:
        track_scanned(int, int, TrackResult): Emitted per track (cyl, head, result)
        sector_status(int, bool, str): Per-sector status (sector_num, is_good, error)
        scan_complete(ScanResult): Final complete scan result
        flux_captured(int, int, object): Flux data captured (cyl, head, FluxCapture)

    Example:
        worker = ScanWorker(device, geometry, capture_flux=True, mode=ScanMode.THOROUGH)
        worker.track_scanned.connect(on_track_scanned)
        worker.scan_complete.connect(on_scan_complete)
    """

    # Signals specific to scanning
    track_scanned = pyqtSignal(int, int, object)  # cyl, head, TrackResult
    sector_status = pyqtSignal(int, bool, str)     # sector_num, is_good, error_type
    scan_complete = pyqtSignal(object)             # ScanResult
    flux_captured = pyqtSignal(int, int, object)   # cyl, head, FluxCapture

    def __init__(
        self,
        device: 'GreaseweazleDevice',
        geometry: 'DiskGeometry',
        capture_flux: bool = False,
        mode: ScanMode = ScanMode.STANDARD,
    ):
        """
        Initialize scan worker.

        Args:
            device: Connected GreaseweazleDevice instance
            geometry: Disk geometry information
            capture_flux: Whether to save raw flux data
            mode: Scan mode (QUICK, STANDARD, THOROUGH)
        """
        super().__init__(device)
        self._geometry = geometry
        self._capture_flux = capture_flux
        self._mode = mode

        # Store captured flux data for THOROUGH mode multi-pass comparison
        self._flux_cache: Dict[Tuple[int, int], Any] = {}

        logger.info(
            "ScanWorker initialized: mode=%s, capture_flux=%s",
            mode.name, capture_flux
        )

    def run(self) -> None:
        """
        Execute the scan operation.

        Scans all tracks according to the selected mode, reporting
        progress and results via signals.
        """
        from floppy_formatter.hardware import read_track_flux
        from floppy_formatter.analysis.flux_analyzer import FluxCapture

        start_time = time.time()

        # Initialize result
        result = ScanResult(
            total_sectors=self._geometry.total_sectors,
            mode=self._mode,
        )

        # Ensure drive is properly initialized and motor is on
        # Use reinitialize_drive() to ensure proper bus state synchronization
        if not self._device.is_motor_on():
            logger.info("Motor not running, reinitializing drive before scan...")
            self._device.reinitialize_drive()
        else:
            # Even if motor is marked as running, ensure proper state
            logger.debug("Motor marked as running, verifying drive state...")
            # Just ensure motor is on with standard method
            self._device.motor_on()
            time.sleep(0.5)

        # Get tracks to scan based on mode
        tracks_to_scan = self._get_tracks_to_scan()
        total_tracks = len(tracks_to_scan)

        logger.info("Scanning %d tracks in %s mode", total_tracks, self._mode.name)

        # Scan each track
        scanned_count = 0
        for cylinder, head in tracks_to_scan:
            # Check for cancellation
            if self._cancelled:
                logger.info("Scan cancelled at track %d/%d", cylinder, head)
                break

            # Scan the track
            track_result = self._scan_track(cylinder, head)
            result.track_results.append(track_result)

            # Update overall results
            for sector_result in track_result.sector_results:
                if sector_result.is_good:
                    result.good_sectors.append(sector_result.linear_sector)
                else:
                    result.bad_sectors.append(sector_result.linear_sector)
                    if sector_result.error_type:
                        result.error_types[sector_result.linear_sector] = sector_result.error_type

            # Emit track result
            self.track_scanned.emit(cylinder, head, track_result)

            # Update progress
            scanned_count += 1
            progress = int((scanned_count / total_tracks) * 100)
            self.progress.emit(progress)

        # Calculate duration
        result.scan_duration = time.time() - start_time

        # Emit final result
        logger.info(
            "Scan complete: %d good, %d bad sectors in %.1fs",
            len(result.good_sectors), len(result.bad_sectors), result.scan_duration
        )
        self.scan_complete.emit(result)

        # IMPORTANT: Emit finished signal to trigger cleanup
        # This must happen after scan_complete so handlers can process the result first
        self.finished.emit()

    def _get_tracks_to_scan(self) -> List[Tuple[int, int]]:
        """
        Get list of tracks to scan based on mode.

        Returns:
            List of (cylinder, head) tuples to scan
        """
        cylinders = self._geometry.cylinders
        heads = self._geometry.heads

        if self._mode == ScanMode.QUICK:
            # Sample tracks: 0, middle, last, plus random sampling
            tracks = []

            # Always include first, middle, last
            key_tracks = [0, cylinders // 2, cylinders - 1]
            for cyl in key_tracks:
                for head in range(heads):
                    tracks.append((cyl, head))

            # Add random sampling (10% of remaining tracks)
            all_tracks = [
                (cyl, head)
                for cyl in range(cylinders)
                for head in range(heads)
                if cyl not in key_tracks
            ]
            sample_size = max(5, len(all_tracks) // 10)
            if all_tracks:
                random.shuffle(all_tracks)
                tracks.extend(all_tracks[:sample_size])

            # Sort by cylinder for efficient seeking
            tracks.sort(key=lambda t: (t[0], t[1]))
            return tracks

        else:
            # STANDARD and THOROUGH: All tracks
            return [
                (cyl, head)
                for cyl in range(cylinders)
                for head in range(heads)
            ]

    def _scan_track(self, cylinder: int, head: int) -> TrackResult:
        """
        Scan a single track.

        Args:
            cylinder: Cylinder number
            head: Head number

        Returns:
            TrackResult with scan data
        """
        from floppy_formatter.hardware import read_track_flux
        from floppy_formatter.analysis.flux_analyzer import FluxCapture
        from floppy_formatter.analysis.signal_quality import calculate_snr

        # Try to import PLL decoder (preferred method)
        try:
            from floppy_formatter.hardware.pll_decoder import decode_flux_with_pll
            pll_available = True
        except ImportError:
            pll_available = False
            logger.debug("PLL decoder not available, using simple decoder")

        track_start = time.time()

        # Seek to track
        self._device.seek(cylinder, head)

        # Determine revolutions based on mode
        if self._mode == ScanMode.THOROUGH:
            revolutions = 3
        else:
            revolutions = 1.2

        # Capture flux
        flux = read_track_flux(self._device, cylinder, head, revolutions=revolutions)

        # Convert to FluxCapture for analysis
        capture = FluxCapture.from_flux_data(flux)
        capture.cylinder = cylinder
        capture.head = head

        # Emit flux if capturing
        if self._capture_flux:
            self.flux_captured.emit(cylinder, head, capture)
            self._flux_cache[(cylinder, head)] = capture

        # Decode sectors - try PLL decoder first, fall back to simple decoder
        sectors = []
        if pll_available:
            try:
                sectors = decode_flux_with_pll(flux)
                logger.debug("PLL decoder returned %d sectors for C%d:H%d",
                            len(sectors), cylinder, head)
            except Exception as e:
                logger.warning("PLL decoder failed for C%d:H%d: %s, trying simple decoder",
                              cylinder, head, e)
                sectors = []

        # Fall back to simple decoder if PLL didn't work
        if not sectors:
            from floppy_formatter.hardware.mfm_codec import decode_flux_to_sectors
            sectors = decode_flux_to_sectors(flux)
            logger.debug("Simple decoder returned %d sectors for C%d:H%d",
                        len(sectors), cylinder, head)

        # Log decode results for debugging
        logger.info("Track C%d:H%d: decoded %d sectors from flux (%d transitions)",
                    cylinder, head, len(sectors), len(flux.flux_times) if hasattr(flux, 'flux_times') else 0)

        # Calculate signal quality
        try:
            snr_result = calculate_snr(capture)
            avg_quality = min(1.0, snr_result.snr_db / 30.0)  # Normalize to 0-1
        except Exception:
            avg_quality = 0.8  # Default if quality calculation fails

        # Process results
        track_result = TrackResult(
            cylinder=cylinder,
            head=head,
            flux_captured=self._capture_flux,
            average_quality=avg_quality,
        )

        sectors_per_track = self._geometry.sectors_per_track
        base_sector = (cylinder * self._geometry.heads + head) * sectors_per_track

        # Deduplicate sectors - keep best result for each sector number
        # This handles multiple revolutions where same sector appears multiple times
        best_sectors = {}  # sector_num -> best SectorData
        for sector in sectors:
            sector_num = sector.sector
            if sector_num < 1 or sector_num > sectors_per_track:
                # Skip invalid sector numbers (could be from corrupt headers)
                continue

            if sector_num not in best_sectors:
                best_sectors[sector_num] = sector
            else:
                # Prefer good CRC over bad CRC
                existing = best_sectors[sector_num]
                if sector.crc_valid and not existing.crc_valid:
                    best_sectors[sector_num] = sector
                elif sector.crc_valid == existing.crc_valid:
                    # Both same CRC status, prefer better signal quality
                    if hasattr(sector, 'signal_quality') and hasattr(existing, 'signal_quality'):
                        if sector.signal_quality > existing.signal_quality:
                            best_sectors[sector_num] = sector

        logger.debug("Track C%d:H%d: deduplicated %d raw sectors to %d unique sectors",
                    cylinder, head, len(sectors), len(best_sectors))

        # Process all expected sectors (1 through sectors_per_track)
        for sector_num in range(1, sectors_per_track + 1):
            linear_sector = base_sector + (sector_num - 1)

            if sector_num in best_sectors:
                sector = best_sectors[sector_num]
                is_good = sector.data is not None and sector.crc_valid
                error_type = None

                if not is_good:
                    if sector.data is None:
                        error_type = "Missing data"
                    elif not sector.crc_valid:
                        error_type = "CRC error"
                    else:
                        error_type = "Unknown error"

                sector_result = SectorResult(
                    sector_num=sector_num,
                    linear_sector=linear_sector,
                    is_good=is_good,
                    error_type=error_type,
                    crc_valid=sector.crc_valid,
                    flux_quality=avg_quality,
                )
            else:
                # Sector not found in any revolution
                is_good = False
                error_type = "Not found"
                sector_result = SectorResult(
                    sector_num=sector_num,
                    linear_sector=linear_sector,
                    is_good=False,
                    error_type="Not found",
                    crc_valid=False,
                    flux_quality=0.0,
                )

            track_result.sector_results.append(sector_result)

            if is_good:
                track_result.good_count += 1
            else:
                track_result.bad_count += 1

            # Emit per-sector status
            self.sector_status.emit(
                linear_sector,
                is_good,
                error_type or ""
            )

        track_result.scan_time_ms = (time.time() - track_start) * 1000

        logger.debug(
            "Track C%d:H%d scanned: %d/%d good (%.1f ms)",
            cylinder, head, track_result.good_count,
            sectors_per_track, track_result.scan_time_ms
        )

        return track_result

    def get_geometry(self) -> 'DiskGeometry':
        """Get the disk geometry being used."""
        return self._geometry

    def get_mode(self) -> ScanMode:
        """Get the scan mode."""
        return self._mode

    def get_flux_cache(self) -> Dict[Tuple[int, int], Any]:
        """
        Get cached flux data.

        Returns:
            Dictionary mapping (cylinder, head) to FluxCapture
        """
        return dict(self._flux_cache)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'ScanWorker',
    'ScanMode',
    'SectorResult',
    'TrackResult',
    'ScanResult',
]
