"""
Disk Image Writer Worker for writing blank formatted images to physical disks.

Writes bundled blank disk images (IBM PC, Amiga, Atari ST, etc.) to physical
floppy disks using the appropriate encoding for each format.

Part of the Write Image feature.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal

from floppy_formatter.gui.workers.base_worker import GreaseweazleWorker
from floppy_formatter.imaging import (
    DiskFormatSpec,
    Encoding,
    get_image_manager,
)

if TYPE_CHECKING:
    from floppy_formatter.hardware import GreaseweazleDevice

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TrackWriteResult:
    """
    Result of writing a single track.

    Attributes:
        cylinder: Cylinder number (0-79)
        head: Head number (0-1)
        write_success: True if write succeeded
        verify_success: True if verification passed (None if not verified)
        error_message: Error description if failed
        write_time_ms: Time to write this track in milliseconds
    """
    cylinder: int
    head: int
    write_success: bool
    verify_success: Optional[bool] = None
    error_message: Optional[str] = None
    write_time_ms: float = 0.0

    @property
    def track_number(self) -> int:
        """Linear track number."""
        return self.cylinder * 2 + self.head

    @property
    def is_perfect(self) -> bool:
        """True if write and verify (if done) both succeeded."""
        if self.verify_success is None:
            return self.write_success
        return self.write_success and self.verify_success


@dataclass
class WriteImageResult:
    """
    Complete write image result.

    Attributes:
        format_spec: The disk format that was written
        started_at: When the operation started
        completed_at: When the operation completed
        total_tracks: Total tracks to write
        tracks_written: Number of tracks successfully written
        tracks_verified: Number of tracks verified (if enabled)
        tracks_failed: Number of tracks that failed
        track_results: Per-track results
        cancelled: True if operation was cancelled
        error_message: Overall error message if failed
    """
    format_spec: DiskFormatSpec
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_tracks: int = 0
    tracks_written: int = 0
    tracks_verified: int = 0
    tracks_failed: int = 0
    track_results: List[TrackWriteResult] = None
    cancelled: bool = False
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.track_results is None:
            self.track_results = []

    @property
    def duration_seconds(self) -> float:
        """Total operation duration in seconds."""
        if self.completed_at is None:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def success_rate(self) -> float:
        """Percentage of tracks written successfully (0-100)."""
        if self.total_tracks == 0:
            return 0.0
        return (self.tracks_written / self.total_tracks) * 100

    @property
    def is_complete(self) -> bool:
        """True if all tracks were written successfully."""
        return self.tracks_written == self.total_tracks and self.tracks_failed == 0


# =============================================================================
# Worker Class
# =============================================================================

class DiskImageWorker(GreaseweazleWorker):
    """
    Worker for writing blank disk images to physical floppy disks.

    Signals:
        track_written(int, int, bool): Emitted after each track write
            (cylinder, head, success)
        track_verified(int, int, bool): Emitted after each track verify
            (cylinder, head, verified_ok)
        write_complete(WriteImageResult): Emitted when operation completes
        status_update(str): Status message updates

    Example:
        worker = DiskImageWorker(device, format_spec)
        worker.track_written.connect(on_track_written)
        worker.write_complete.connect(on_complete)
        worker.execute()
    """

    # Signals
    track_written = pyqtSignal(int, int, bool)  # cylinder, head, success
    track_verified = pyqtSignal(int, int, bool)  # cylinder, head, verified
    write_complete = pyqtSignal(object)  # WriteImageResult
    status_update = pyqtSignal(str)

    def __init__(
        self,
        device: Optional['GreaseweazleDevice'] = None,
        format_spec: Optional[DiskFormatSpec] = None,
        verify: bool = True,
        parent=None
    ):
        """
        Initialize disk image worker.

        Args:
            device: Greaseweazle device instance
            format_spec: Disk format specification to write
            verify: Whether to verify after writing
            parent: Optional parent QObject
        """
        super().__init__(device, parent)
        self._format_spec = format_spec
        self._verify = verify
        self._result: Optional[WriteImageResult] = None
        self._image_data: Optional[bytes] = None

    def set_format(self, format_spec: DiskFormatSpec) -> None:
        """Set the disk format to write."""
        self._format_spec = format_spec

    def set_verify(self, verify: bool) -> None:
        """Set whether to verify after writing."""
        self._verify = verify

    def run(self) -> None:
        """Execute the disk image writing operation."""
        if self._format_spec is None:
            self.device_error.emit("No format specified")
            self.finished.emit()
            return

        # Initialize result
        self._result = WriteImageResult(
            format_spec=self._format_spec,
            started_at=datetime.now(),
            total_tracks=self._format_spec.total_tracks
        )

        try:
            # Load the image data
            self.status_update.emit(f"Loading {self._format_spec.name} image...")
            manager = get_image_manager()
            self._image_data = manager.get_image_data(self._format_spec)

            if self._image_data is None:
                raise ValueError(
                    f"No image available for {self._format_spec.platform.value} "
                    f"{self._format_spec.name}"
                )

            logger.info(
                "Loaded image: %s %s (%d bytes)",
                self._format_spec.platform.value,
                self._format_spec.name,
                len(self._image_data)
            )

            # Reinitialize drive (uses already-selected drive unit, starts motor, seeks to track 0)
            self.status_update.emit("Initializing drive...")
            self._device.reinitialize_drive()

            # Write all tracks
            self._write_all_tracks()

            # Finalize
            self._result.completed_at = datetime.now()
            self._device.motor_off()

            if self._cancelled:
                self._result.cancelled = True
                self.status_update.emit("Operation cancelled")
            elif self._result.tracks_failed > 0:
                self.status_update.emit(
                    f"Completed with {self._result.tracks_failed} failed tracks"
                )
            else:
                self.status_update.emit("Write complete!")

            self.write_complete.emit(self._result)

        except Exception as e:
            logger.exception("Disk image write failed")
            self._result.error_message = str(e)
            self._result.completed_at = datetime.now()
            self.device_error.emit(f"Write failed: {e}")
            self.write_complete.emit(self._result)

        finally:
            self.finished.emit()

    def _write_all_tracks(self) -> None:
        """Write all tracks from the image to disk."""
        spec = self._format_spec
        total_tracks = spec.total_tracks

        for cyl in range(spec.cylinders):
            if self._cancelled:
                break

            for head in range(spec.heads):
                if self._cancelled:
                    break

                track_num = cyl * spec.heads + head
                progress = int((track_num / total_tracks) * 100)
                self.progress.emit(progress)

                self.status_update.emit(
                    f"Writing track {track_num + 1}/{total_tracks} "
                    f"(C{cyl} H{head})"
                )

                # Write the track
                result = self._write_track(cyl, head)
                self._result.track_results.append(result)

                if result.write_success:
                    self._result.tracks_written += 1
                    self.track_written.emit(cyl, head, True)

                    # Verify if enabled
                    if self._verify and not self._cancelled:
                        verified = self._verify_track(cyl, head)
                        result.verify_success = verified
                        if verified:
                            self._result.tracks_verified += 1
                        self.track_verified.emit(cyl, head, verified)
                else:
                    self._result.tracks_failed += 1
                    self.track_written.emit(cyl, head, False)

        self.progress.emit(100)

    def _write_track(self, cylinder: int, head: int) -> TrackWriteResult:
        """
        Write a single track from the image.

        Args:
            cylinder: Cylinder number
            head: Head number

        Returns:
            TrackWriteResult with outcome
        """
        start_time = time.time()
        spec = self._format_spec

        try:
            # Extract sector data for this track from image
            # Note: write_track_flux handles seeking internally
            sectors_data = self._extract_track_sectors(cylinder, head)

            if not sectors_data:
                return TrackWriteResult(
                    cylinder=cylinder,
                    head=head,
                    write_success=False,
                    error_message="No sector data extracted"
                )

            # Encode and write based on format type
            if spec.encoding == Encoding.MFM:
                success = self._write_mfm_track(cylinder, head, sectors_data)
            elif spec.encoding == Encoding.AMIGA:
                success = self._write_amiga_track(cylinder, head, sectors_data)
            elif spec.encoding == Encoding.FM:
                success = self._write_fm_track(cylinder, head, sectors_data)
            else:
                logger.warning(
                    "Unsupported encoding: %s, using raw write",
                    spec.encoding.value
                )
                success = self._write_raw_track(cylinder, head, sectors_data)

            elapsed_ms = (time.time() - start_time) * 1000

            return TrackWriteResult(
                cylinder=cylinder,
                head=head,
                write_success=success,
                write_time_ms=elapsed_ms
            )

        except Exception as e:
            logger.error("Track write failed C%d H%d: %s", cylinder, head, e)
            return TrackWriteResult(
                cylinder=cylinder,
                head=head,
                write_success=False,
                error_message=str(e),
                write_time_ms=(time.time() - start_time) * 1000
            )

    def _extract_track_sectors(
        self,
        cylinder: int,
        head: int
    ) -> List[bytes]:
        """
        Extract sector data for a track from the image.

        Args:
            cylinder: Cylinder number
            head: Head number

        Returns:
            List of sector data bytes
        """
        spec = self._format_spec
        sector_size = spec.bytes_per_sector
        sectors_per_track = spec.sectors_per_track

        # Calculate offset in image
        track_num = cylinder * spec.heads + head
        track_offset = track_num * sectors_per_track * sector_size

        sectors = []
        for sector in range(sectors_per_track):
            offset = track_offset + (sector * sector_size)
            if offset + sector_size <= len(self._image_data):
                sector_data = self._image_data[offset:offset + sector_size]
                sectors.append(sector_data)
            else:
                # Pad with zeros if image is short
                sectors.append(bytes(sector_size))

        return sectors

    def _write_mfm_track(
        self,
        cylinder: int,
        head: int,
        sectors_data: List[bytes]
    ) -> bool:
        """Write a track using MFM encoding."""
        try:
            from floppy_formatter.hardware.gw_mfm_codec import (
                encode_sectors_to_flux_gw
            )
            from floppy_formatter.hardware.flux_io import write_track_flux
            from floppy_formatter.hardware import SectorData, SectorStatus

            spec = self._format_spec

            # Create SectorData objects for encoding
            sector_objects = []
            for i, data in enumerate(sectors_data):
                sector_id = spec.first_sector_id + i
                sector = SectorData(
                    cylinder=cylinder,
                    head=head,
                    sector=sector_id,
                    data=data,
                    status=SectorStatus.GOOD,
                    crc_valid=True,
                    signal_quality=1.0
                )
                sector_objects.append(sector)

            # Encode to flux - function takes cylinder, head, sectors, sample_freq
            flux_data = encode_sectors_to_flux_gw(
                cylinder, head, sector_objects
            )

            # Write to disk
            write_track_flux(self._device, cylinder, head, flux_data)
            return True

        except Exception as e:
            logger.error("MFM write failed: %s", e)
            return False

    def _write_amiga_track(
        self,
        cylinder: int,
        head: int,
        sectors_data: List[bytes]
    ) -> bool:
        """Write a track using Amiga MFM encoding."""
        try:
            # Try to use Greaseweazle's Amiga codec
            from greaseweazle.codec.amiga import amigados
            from floppy_formatter.hardware.flux_io import write_track_flux

            # Create track data (all sectors concatenated)
            track_data = b''.join(sectors_data)

            # Use Greaseweazle's Amiga encoder
            # Create a MasterFormat for Amiga
            fmt = amigados.AmigaDOS(0)  # tracknr placeholder
            fmt.set_img_track(track_data)

            # Get flux for writeout
            flux = fmt.flux_for_writeout(cue_at_index=True)

            # Write using our flux_io
            write_track_flux(self._device, cylinder, head, flux)
            return True

        except ImportError:
            logger.warning("Greaseweazle Amiga codec not available")
            # Fall back to raw write
            return self._write_raw_track(cylinder, head, sectors_data)
        except Exception as e:
            logger.error("Amiga write failed: %s", e)
            return False

    def _write_fm_track(
        self,
        cylinder: int,
        head: int,
        sectors_data: List[bytes]
    ) -> bool:
        """Write a track using FM encoding (BBC Micro DFS)."""
        try:
            # Try to use Greaseweazle's FM codec
            from greaseweazle.codec.ibm import fm
            from floppy_formatter.hardware.flux_io import write_track_flux

            # Create track data
            track_data = b''.join(sectors_data)

            # Use Greaseweazle's FM encoder
            fmt = fm.IBM_FM(0)  # tracknr placeholder
            fmt.set_img_track(track_data)

            # Get flux for writeout
            flux = fmt.flux_for_writeout(cue_at_index=True)

            # Write using our flux_io
            write_track_flux(self._device, cylinder, head, flux)
            return True

        except ImportError:
            logger.warning("Greaseweazle FM codec not available")
            return False
        except Exception as e:
            logger.error("FM write failed: %s", e)
            return False

    def _write_raw_track(
        self,
        cylinder: int,
        head: int,
        _sectors_data: List[bytes]
    ) -> bool:
        """Write raw track data (fallback for unsupported encodings)."""
        logger.warning(
            "Raw track write not fully implemented for C%d H%d",
            cylinder, head
        )
        return False

    def _verify_track(self, cylinder: int, head: int) -> bool:
        """
        Verify a track was written correctly.

        Args:
            cylinder: Cylinder number
            head: Head number

        Returns:
            True if verification passed
        """
        try:
            from floppy_formatter.hardware.flux_io import read_track_flux

            spec = self._format_spec

            # Read the track back
            flux_data = read_track_flux(self._device, cylinder, head)

            if flux_data is None:
                logger.warning("Verify: no flux data read for C%d H%d", cylinder, head)
                return False

            # Decode the flux to sectors
            all_sectors = self._decode_track(flux_data)

            # Deduplicate sectors by sector ID (flux read may capture >1 revolution)
            # Build a dict keyed by sector ID, keeping first occurrence with valid CRC
            unique_sectors = {}
            for sector in all_sectors:
                sector_id = getattr(sector, 'sector', None)
                if sector_id is None:
                    continue
                # Prefer sectors with valid CRC
                if sector_id not in unique_sectors:
                    unique_sectors[sector_id] = sector
                elif getattr(sector, 'crc_valid', False) and not getattr(
                    unique_sectors[sector_id], 'crc_valid', False
                ):
                    unique_sectors[sector_id] = sector

            # Check we found all expected sectors
            expected_sector_ids = set(
                range(spec.first_sector_id, spec.first_sector_id + spec.sectors_per_track)
            )
            found_sector_ids = set(unique_sectors.keys())

            if found_sector_ids != expected_sector_ids:
                missing = expected_sector_ids - found_sector_ids
                extra = found_sector_ids - expected_sector_ids
                logger.warning(
                    "Verify: sector ID mismatch for C%d H%d - missing: %s, extra: %s",
                    cylinder, head, missing, extra
                )
                return False

            # Compare data with original
            expected_data = self._extract_track_sectors(cylinder, head)
            for i, sector_id in enumerate(
                range(spec.first_sector_id, spec.first_sector_id + spec.sectors_per_track)
            ):
                actual_sector = unique_sectors[sector_id]
                actual_data = getattr(actual_sector, 'data', actual_sector)
                if actual_data != expected_data[i]:
                    logger.warning(
                        "Verify: sector %d data mismatch at C%d H%d",
                        sector_id, cylinder, head
                    )
                    return False

            logger.debug("Verify: C%d H%d passed (%d unique sectors)",
                        cylinder, head, len(unique_sectors))
            return True

        except Exception as e:
            logger.error("Verify failed for C%d H%d: %s", cylinder, head, e)
            return False

    def _decode_track(self, flux_data):
        """Decode flux data to sectors."""
        # Use same decoder as format worker
        try:
            from floppy_formatter.hardware.gw_mfm_codec import decode_flux_to_sectors_gw
            sectors = decode_flux_to_sectors_gw(flux_data)
            if sectors:
                return sectors
        except Exception:
            pass

        try:
            from floppy_formatter.hardware.pll_decoder import decode_flux_with_pll
            sectors = decode_flux_with_pll(flux_data)
            if sectors:
                return sectors
        except Exception:
            pass

        from floppy_formatter.hardware.mfm_codec import decode_flux_to_sectors
        return decode_flux_to_sectors(flux_data)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'DiskImageWorker',
    'TrackWriteResult',
    'WriteImageResult',
]
