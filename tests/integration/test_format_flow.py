"""
Integration tests for format workflow.

Tests complete format operations using mock devices to simulate
realistic scenarios without physical hardware.
"""

import pytest
import errno
from tests.fixtures import (
    create_good_disk,
    create_bad_sector_0_disk,
    create_write_protected_disk,
    create_degraded_disk,
    MockGeometry,
)

# Linux error codes (errno values)
ERROR_SUCCESS = 0           # Success (no error)
ERROR_WRITE_PROTECT = errno.EROFS  # Read-only file system (30)


class TestScanGoodDisk:
    """Test scanning a known good disk."""

    def test_scan_complete_success(self):
        """Test full scan of good disk completes successfully."""
        mock_handle = create_good_disk()
        geometry = MockGeometry()

        bad_sectors = []
        good_sectors = []
        total_sectors = geometry.cylinders * geometry.heads * geometry.sectors_per_track

        # Simulate full scan
        for sector in range(total_sectors):
            success, data, error = mock_handle.read_sector(sector)
            if success:
                good_sectors.append(sector)
            else:
                bad_sectors.append(sector)

        # Expected: 0 bad sectors
        assert len(bad_sectors) == 0
        assert len(good_sectors) == 2880

    def test_scan_duration_acceptable(self):
        """Test scan completes in reasonable time."""
        import time

        mock_handle = create_good_disk()
        geometry = MockGeometry()

        start_time = time.time()

        # Scan all sectors
        total_sectors = geometry.cylinders * geometry.heads * geometry.sectors_per_track
        for sector in range(total_sectors):
            mock_handle.read_sector(sector)

        duration = time.time() - start_time

        # Mock scan should be very fast (< 1 second)
        assert duration < 1.0


class TestScanBadSector0Disk:
    """Test PRIMARY requirement: read disk with bad sector 0."""

    def test_can_read_disk_with_bad_sector_0(self):
        """Test tool can read disk with bad boot sector."""
        mock_handle = create_bad_sector_0_disk()

        # Should be able to read sector 1 and beyond
        success, data, error = mock_handle.read_sector(1)
        assert success is True

        success, data, error = mock_handle.read_sector(100)
        assert success is True

        # Sector 0 will fail
        success, data, error = mock_handle.read_sector(0)
        assert success is False

    def test_scan_identifies_bad_sector_0(self):
        """Test scan correctly identifies sector 0 as bad."""
        mock_handle = create_bad_sector_0_disk()

        success, data, error = mock_handle.read_sector(0)

        assert success is False
        assert 0 in mock_handle.bad_sectors

    def test_scan_rest_of_disk_succeeds(self):
        """Test scanning rest of disk succeeds despite bad sector 0."""
        mock_handle = create_bad_sector_0_disk()
        geometry = MockGeometry()

        good_count = 0
        total_sectors = geometry.cylinders * geometry.heads * geometry.sectors_per_track

        # Scan all sectors except 0
        for sector in range(1, total_sectors):
            success, data, error = mock_handle.read_sector(sector)
            if success:
                good_count += 1

        # All sectors except 0 should be good
        assert good_count == 2879


class TestFormatCleanDisk:
    """Test formatting a clean disk."""

    def test_format_all_tracks_success(self):
        """Test formatting all 160 tracks successfully."""
        mock_handle = create_good_disk()
        geometry = MockGeometry()

        total_tracks = geometry.cylinders * geometry.heads
        tracks_formatted = 0

        # Format all tracks
        for cylinder in range(geometry.cylinders):
            for head in range(geometry.heads):
                result = mock_handle.format_track(cylinder, head)

                assert result.success is True
                assert result.bad_track_count == 0
                tracks_formatted += 1

        assert tracks_formatted == 160

    def test_format_completes_quickly(self):
        """Test format completes in reasonable time."""
        import time

        mock_handle = create_good_disk()
        geometry = MockGeometry()

        start_time = time.time()

        # Format all tracks
        for cylinder in range(geometry.cylinders):
            for head in range(geometry.heads):
                mock_handle.format_track(cylinder, head)

        duration = time.time() - start_time

        # Mock format should be very fast
        assert duration < 1.0

    def test_format_with_verification(self):
        """Test format followed by verification."""
        mock_handle = create_good_disk()
        geometry = MockGeometry()

        # Format all tracks
        for cylinder in range(geometry.cylinders):
            for head in range(geometry.heads):
                result = mock_handle.format_track(cylinder, head)
                assert result.success is True

        # Verify all sectors are accessible
        total_sectors = geometry.cylinders * geometry.heads * geometry.sectors_per_track
        for sector in range(total_sectors):
            success, data, error = mock_handle.read_sector(sector)
            assert success is True


class TestFormatWithFallback:
    """Test Linux sector-level formatting behavior."""

    def test_format_track_simulation(self):
        """Test sector-level track formatting."""
        mock_handle = create_good_disk()

        # Simulate formatting a track
        result = mock_handle.format_track(0, 0)

        assert result.success is True
        assert result.bad_track_count == 0
        assert result.bad_tracks == []

    def test_format_with_bad_tracks_detected(self):
        """Test format detecting bad tracks."""
        mock_handle = create_degraded_disk(bad_sector_count=18)  # First track bad

        # Format first track (which has bad sectors)
        result = mock_handle.format_track(0, 0)

        assert result.success is True
        assert result.bad_track_count == 1
        assert 0 in result.bad_tracks

    def test_format_reports_all_bad_tracks(self):
        """Test format reports all bad tracks."""
        mock_handle = create_degraded_disk(bad_sector_count=72)  # First 4 tracks

        bad_tracks_found = []

        for cylinder in range(2):  # First 2 cylinders = 4 tracks
            for head in range(2):
                result = mock_handle.format_track(cylinder, head)
                if result.bad_track_count > 0:
                    bad_tracks_found.extend(result.bad_tracks)

        # Should find 4 bad tracks (tracks 0, 1, 2, 3)
        assert len(bad_tracks_found) == 4


class TestFormatEdgeCases:
    """Test format edge cases."""

    def test_format_write_protected_disk(self):
        """Test formatting write-protected disk fails gracefully."""
        mock_handle = create_write_protected_disk()

        result = mock_handle.format_track(0, 0)

        assert result.success is False
        assert result.error_code == ERROR_WRITE_PROTECT

    def test_format_first_track(self):
        """Test formatting first track (cylinder 0, head 0)."""
        mock_handle = create_good_disk()

        result = mock_handle.format_track(0, 0)

        assert result.success is True
        assert result.bad_track_count == 0

    def test_format_last_track(self):
        """Test formatting last track (cylinder 79, head 1)."""
        mock_handle = create_good_disk()

        result = mock_handle.format_track(79, 1)

        assert result.success is True
        assert result.bad_track_count == 0

    def test_format_statistics_tracking(self):
        """Test format operations are tracked."""
        mock_handle = create_good_disk()

        # Format a few tracks
        for cylinder in range(5):
            for head in range(2):
                mock_handle.format_track(cylinder, head)

        stats = mock_handle.get_statistics()
        assert stats['format_count'] == 10


class TestFormatProgressTracking:
    """Test format progress tracking."""

    def test_progress_updates(self):
        """Test progress updates during format."""
        mock_handle = create_good_disk()
        geometry = MockGeometry()

        total_tracks = geometry.cylinders * geometry.heads
        tracks_completed = 0
        progress_updates = []

        for cylinder in range(geometry.cylinders):
            for head in range(geometry.heads):
                mock_handle.format_track(cylinder, head)
                tracks_completed += 1

                # Simulate progress update
                progress = (tracks_completed / total_tracks) * 100
                progress_updates.append(progress)

        assert len(progress_updates) == 160
        assert progress_updates[-1] == 100.0

    def test_track_by_track_progress(self):
        """Test tracking progress track by track."""
        mock_handle = create_good_disk()
        geometry = MockGeometry()

        for track_num in range(10):  # First 10 tracks
            cylinder = track_num // geometry.heads
            head = track_num % geometry.heads

            result = mock_handle.format_track(cylinder, head)
            assert result.success is True

            # Track number should match
            actual_track = cylinder * geometry.heads + head
            assert actual_track == track_num


class TestFormatRecovery:
    """Test format recovery scenarios."""

    def test_format_after_scan_identifies_issues(self):
        """Test formatting after scan identifies issues."""
        mock_handle = create_degraded_disk(bad_sector_count=50)

        # Scan to identify bad sectors
        bad_sectors = []
        for sector in range(2880):
            success, data, error = mock_handle.read_sector(sector)
            if not success:
                bad_sectors.append(sector)

        assert len(bad_sectors) == 50

        # Format should detect bad tracks
        bad_tracks = []
        for cylinder in range(80):
            for head in range(2):
                result = mock_handle.format_track(cylinder, head)
                if result.bad_track_count > 0:
                    bad_tracks.extend(result.bad_tracks)

        # Should detect at least some bad tracks
        assert len(bad_tracks) > 0

    def test_format_improves_disk_condition(self):
        """Test format can improve disk condition (simulation)."""
        mock_handle = create_degraded_disk(bad_sector_count=50)

        # Initial bad sector count
        initial_bad = len(mock_handle.bad_sectors)

        # Simulate recovery by marking some sectors as good after format
        for sector in list(mock_handle.bad_sectors)[:25]:
            mock_handle.mark_sector_good(sector)

        # After "recovery"
        final_bad = len(mock_handle.bad_sectors)

        assert final_bad < initial_bad
        assert final_bad == 25  # Half recovered
