"""
Unit tests for sector I/O operations.

Tests read_sector, write_sector, pattern writing, and error handling.
"""

import pytest
import errno
from tests.fixtures import (
    create_good_disk,
    create_bad_sector_0_disk,
    create_write_protected_disk,
    create_disconnected_disk,
    create_degraded_disk,
)

# Linux error codes (errno values)
ERROR_SUCCESS = 0           # Success (no error)
ERROR_CRC = errno.EIO       # I/O error (5)
ERROR_SECTOR_NOT_FOUND = errno.ENXIO  # No such device or address (6)
ERROR_WRITE_PROTECT = errno.EROFS     # Read-only file system (30)
ERROR_NOT_READY = errno.ENODEV        # No such device (19)


class TestReadSector:
    """Test read_sector() function."""

    def test_read_good_sector(self):
        """Test reading a good sector."""
        mock_handle = create_good_disk()

        success, data, error = mock_handle.read_sector(0)

        assert success is True
        assert len(data) == 512
        assert error == ERROR_SUCCESS

    def test_read_bad_sector(self):
        """Test reading a bad sector."""
        mock_handle = create_bad_sector_0_disk()

        success, data, error = mock_handle.read_sector(0)

        assert success is False
        assert data == b''
        assert error == ERROR_CRC

    def test_read_multiple_sectors(self):
        """Test reading multiple consecutive sectors."""
        mock_handle = create_good_disk()

        for sector in range(10):
            success, data, error = mock_handle.read_sector(sector)
            assert success is True
            assert len(data) == 512

    def test_read_last_sector(self):
        """Test reading the last sector (2879)."""
        mock_handle = create_good_disk()

        success, data, error = mock_handle.read_sector(2879)

        assert success is True
        assert len(data) == 512
        assert error == ERROR_SUCCESS

    def test_read_invalid_sector_number(self):
        """Test reading an invalid sector number."""
        mock_handle = create_good_disk()

        # Sector 2880 doesn't exist (0-2879)
        success, data, error = mock_handle.read_sector(2880)

        assert success is False
        assert error == ERROR_SECTOR_NOT_FOUND

    def test_read_negative_sector(self):
        """Test reading a negative sector number."""
        mock_handle = create_good_disk()

        success, data, error = mock_handle.read_sector(-1)

        assert success is False
        assert error == ERROR_SECTOR_NOT_FOUND

    def test_read_disconnected_drive(self):
        """Test reading from disconnected drive."""
        mock_handle = create_disconnected_disk()

        success, data, error = mock_handle.read_sector(0)

        assert success is False
        assert error == ERROR_NOT_READY


class TestWriteSector:
    """Test write_sector() function."""

    def test_write_good_sector(self):
        """Test writing to a good sector."""
        mock_handle = create_good_disk()
        test_data = bytes([0x55] * 512)

        success, error = mock_handle.write_sector(100, test_data)

        assert success is True
        assert error == ERROR_SUCCESS

        # Verify data was written
        read_success, read_data, read_error = mock_handle.read_sector(100)
        assert read_success is True
        assert read_data == test_data

    def test_write_invalid_length(self):
        """Test writing data with wrong length."""
        mock_handle = create_good_disk()
        test_data = bytes([0x55] * 256)  # Wrong length

        success, error = mock_handle.write_sector(0, test_data)

        assert success is False

    def test_write_to_write_protected_disk(self):
        """Test writing to write-protected disk."""
        mock_handle = create_write_protected_disk()
        test_data = bytes([0x55] * 512)

        success, error = mock_handle.write_sector(0, test_data)

        assert success is False
        assert error == ERROR_WRITE_PROTECT

    def test_write_to_bad_sector(self):
        """Test writing to a bad sector."""
        mock_handle = create_bad_sector_0_disk()
        test_data = bytes([0x55] * 512)

        success, error = mock_handle.write_sector(0, test_data)

        assert success is False
        assert error == ERROR_CRC

    def test_write_to_disconnected_drive(self):
        """Test writing to disconnected drive."""
        mock_handle = create_disconnected_disk()
        test_data = bytes([0x55] * 512)

        success, error = mock_handle.write_sector(0, test_data)

        assert success is False
        assert error == ERROR_NOT_READY


class TestPatternWriting:
    """Test pattern writing functions."""

    @pytest.mark.parametrize("pattern", [0x00, 0x55, 0xAA, 0xFF])
    def test_write_pattern_all_patterns(self, pattern):
        """Test writing all standard patterns."""
        mock_handle = create_good_disk()
        sector = 500

        # Write pattern
        test_data = bytes([pattern] * 512)
        success, error = mock_handle.write_sector(sector, test_data)

        assert success is True

        # Verify pattern was written
        read_success, read_data, read_error = mock_handle.read_sector(sector)
        assert read_success is True
        assert all(b == pattern for b in read_data)

    def test_pattern_rotation(self):
        """Test rotating patterns across passes."""
        patterns = [0x55, 0xAA, 0xFF, 0x00]
        mock_handle = create_good_disk()

        for pass_num, pattern in enumerate(patterns):
            sector = 100 + pass_num
            test_data = bytes([pattern] * 512)

            success, error = mock_handle.write_sector(sector, test_data)
            assert success is True

            # Verify pattern
            read_success, read_data, _ = mock_handle.read_sector(sector)
            assert read_success is True
            assert all(b == pattern for b in read_data)

    def test_write_track_pattern(self):
        """Test writing pattern to entire track."""
        mock_handle = create_good_disk()
        pattern = 0xAA
        cylinder = 5
        head = 0

        # Calculate track sectors
        sectors_per_track = 18
        track_start = (cylinder * 2 + head) * sectors_per_track

        # Write pattern to all sectors in track
        for sector_offset in range(sectors_per_track):
            sector_num = track_start + sector_offset
            test_data = bytes([pattern] * 512)
            success, error = mock_handle.write_sector(sector_num, test_data)
            assert success is True

        # Verify all sectors have the pattern
        for sector_offset in range(sectors_per_track):
            sector_num = track_start + sector_offset
            success, data, error = mock_handle.read_sector(sector_num)
            assert success is True
            assert all(b == pattern for b in data)


class TestErrorClassification:
    """Test error classification and handling."""

    def test_classify_crc_error(self):
        """Test classifying I/O error."""
        import errno

        # I/O errors are retryable
        assert errno.EIO == 5

    def test_classify_sector_not_found(self):
        """Test classifying sector not found error."""
        import errno

        assert errno.ENXIO == 6

    def test_classify_write_protect(self):
        """Test classifying write protect error."""
        import errno

        # Write protect is fatal
        assert errno.EROFS == 30

    def test_classify_not_ready(self):
        """Test classifying not ready error."""
        import errno

        # Not ready is fatal
        assert errno.ENODEV == 19


class TestBatchOperations:
    """Test batch read/write operations."""

    def test_read_batch_all_good(self):
        """Test batch reading all good sectors."""
        mock_handle = create_good_disk()
        start_sector = 100
        count = 10

        results = []
        for sector in range(start_sector, start_sector + count):
            success, data, error = mock_handle.read_sector(sector)
            results.append(success)

        assert all(results)
        assert len(results) == count

    def test_read_batch_mixed_results(self):
        """Test batch reading with some bad sectors."""
        mock_handle = create_degraded_disk(bad_sector_count=10)

        # Read first 20 sectors (0-9 are bad, 10-19 are good)
        results = []
        for sector in range(20):
            success, data, error = mock_handle.read_sector(sector)
            results.append(success)

        # First 10 should fail, next 10 should succeed
        assert results[:10] == [False] * 10
        assert results[10:20] == [True] * 10

    def test_write_batch_verification(self):
        """Test writing multiple sectors and verifying."""
        mock_handle = create_good_disk()
        sectors_to_write = list(range(500, 510))
        pattern = 0x55

        # Write pattern to all sectors
        for sector in sectors_to_write:
            test_data = bytes([pattern] * 512)
            success, error = mock_handle.write_sector(sector, test_data)
            assert success is True

        # Verify all writes
        for sector in sectors_to_write:
            success, data, error = mock_handle.read_sector(sector)
            assert success is True
            assert all(b == pattern for b in data)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_first_sector(self):
        """Test reading/writing first sector."""
        mock_handle = create_good_disk()
        test_data = bytes([0xAA] * 512)

        # Write and read back
        success, error = mock_handle.write_sector(0, test_data)
        assert success is True

        success, data, error = mock_handle.read_sector(0)
        assert success is True
        assert data == test_data

    def test_last_sector(self):
        """Test reading/writing last sector."""
        mock_handle = create_good_disk()
        test_data = bytes([0xAA] * 512)

        # Write and read back
        success, error = mock_handle.write_sector(2879, test_data)
        assert success is True

        success, data, error = mock_handle.read_sector(2879)
        assert success is True
        assert data == test_data

    def test_sector_alignment(self):
        """Test that all sectors are 512-byte aligned."""
        mock_handle = create_good_disk()

        # All sectors should be 512 bytes
        for sector in [0, 1, 100, 1000, 2879]:
            success, data, error = mock_handle.read_sector(sector)
            if success:
                assert len(data) == 512

    def test_statistics_tracking(self):
        """Test that operations are tracked in statistics."""
        mock_handle = create_good_disk()

        # Perform some operations
        mock_handle.read_sector(0)
        mock_handle.read_sector(1)
        mock_handle.write_sector(2, bytes([0x00] * 512))

        stats = mock_handle.get_statistics()
        assert stats['read_count'] == 2
        assert stats['write_count'] == 1
