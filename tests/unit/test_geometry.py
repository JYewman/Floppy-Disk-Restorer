"""
Unit tests for geometry detection and calculations.

Tests the DiskGeometry dataclass and sector address calculations.
"""

import pytest
from floppy_formatter.core import DiskGeometry


class TestDiskGeometry:
    """Test DiskGeometry dataclass."""

    def test_geometry_creation(self):
        """Test creating a DiskGeometry object."""
        geometry = DiskGeometry(
            media_type=0x0F,
            cylinders=80,
            heads=2,
            sectors_per_track=18,
            bytes_per_sector=512
        )

        assert geometry.media_type == 0x0F
        assert geometry.cylinders == 80
        assert geometry.heads == 2
        assert geometry.sectors_per_track == 18
        assert geometry.bytes_per_sector == 512

    def test_geometry_field_access(self):
        """Test accessing geometry fields."""
        geometry = DiskGeometry(
            media_type=0x0F,
            cylinders=80,
            heads=2,
            sectors_per_track=18,
            bytes_per_sector=512
        )

        # All fields should be accessible
        assert hasattr(geometry, 'media_type')
        assert hasattr(geometry, 'cylinders')
        assert hasattr(geometry, 'heads')
        assert hasattr(geometry, 'sectors_per_track')
        assert hasattr(geometry, 'bytes_per_sector')

    def test_standard_floppy_geometry(self):
        """Test standard 1.44MB floppy geometry."""
        geometry = DiskGeometry(
            media_type=0x0F,
            cylinders=80,
            heads=2,
            sectors_per_track=18,
            bytes_per_sector=512
        )

        # Calculate total sectors
        total_sectors = geometry.cylinders * geometry.heads * geometry.sectors_per_track
        assert total_sectors == 2880

        # Calculate total capacity
        total_bytes = total_sectors * geometry.bytes_per_sector
        total_kb = total_bytes // 1024
        assert total_kb == 1440


class TestSectorAddressCalculations:
    """Test sector address calculations (CHS <-> linear)."""

    @pytest.fixture
    def geometry(self):
        """Standard floppy geometry fixture."""
        return DiskGeometry(
            media_type=0x0F,
            cylinders=80,
            heads=2,
            sectors_per_track=18,
            bytes_per_sector=512
        )

    def test_sector_0_address(self, geometry):
        """Test sector 0 address calculation (C0:H0:S0)."""
        # Sector 0 = cylinder 0, head 0, sector 0
        sector = 0
        cylinder = sector // (geometry.heads * geometry.sectors_per_track)
        head = (sector % (geometry.heads * geometry.sectors_per_track)) // geometry.sectors_per_track
        sector_offset = sector % geometry.sectors_per_track

        assert cylinder == 0
        assert head == 0
        assert sector_offset == 0

    def test_sector_18_address(self, geometry):
        """Test sector 18 address calculation (C0:H1:S0)."""
        # Sector 18 = cylinder 0, head 1, sector 0
        sector = 18
        cylinder = sector // (geometry.heads * geometry.sectors_per_track)
        head = (sector % (geometry.heads * geometry.sectors_per_track)) // geometry.sectors_per_track
        sector_offset = sector % geometry.sectors_per_track

        assert cylinder == 0
        assert head == 1
        assert sector_offset == 0

    def test_sector_36_address(self, geometry):
        """Test sector 36 address calculation (C1:H0:S0)."""
        # Sector 36 = cylinder 1, head 0, sector 0
        sector = 36
        cylinder = sector // (geometry.heads * geometry.sectors_per_track)
        head = (sector % (geometry.heads * geometry.sectors_per_track)) // geometry.sectors_per_track
        sector_offset = sector % geometry.sectors_per_track

        assert cylinder == 1
        assert head == 0
        assert sector_offset == 0

    def test_last_sector_address(self, geometry):
        """Test last sector address calculation (C79:H1:S17)."""
        # Sector 2879 = cylinder 79, head 1, sector 17
        sector = 2879
        cylinder = sector // (geometry.heads * geometry.sectors_per_track)
        head = (sector % (geometry.heads * geometry.sectors_per_track)) // geometry.sectors_per_track
        sector_offset = sector % geometry.sectors_per_track

        assert cylinder == 79
        assert head == 1
        assert sector_offset == 17

    def test_chs_to_linear_conversion(self, geometry):
        """Test converting C/H/S to linear sector number."""
        test_cases = [
            (0, 0, 0, 0),      # First sector
            (0, 0, 17, 17),    # Last sector of first track
            (0, 1, 0, 18),     # First sector of second track
            (1, 0, 0, 36),     # First sector of second cylinder
            (79, 1, 17, 2879), # Last sector
        ]

        for cylinder, head, sector_offset, expected_linear in test_cases:
            linear = (cylinder * geometry.heads + head) * geometry.sectors_per_track + sector_offset
            assert linear == expected_linear, f"C{cylinder}:H{head}:S{sector_offset} failed"

    def test_linear_to_chs_conversion(self, geometry):
        """Test converting linear sector number to C/H/S."""
        test_cases = [
            (0, 0, 0, 0),
            (17, 0, 0, 17),
            (18, 0, 1, 0),
            (36, 1, 0, 0),
            (2879, 79, 1, 17),
        ]

        for linear, expected_c, expected_h, expected_s in test_cases:
            cylinder = linear // (geometry.heads * geometry.sectors_per_track)
            head = (linear % (geometry.heads * geometry.sectors_per_track)) // geometry.sectors_per_track
            sector_offset = linear % geometry.sectors_per_track

            assert cylinder == expected_c, f"Sector {linear} cylinder mismatch"
            assert head == expected_h, f"Sector {linear} head mismatch"
            assert sector_offset == expected_s, f"Sector {linear} sector mismatch"

    def test_all_sectors_addressable(self, geometry):
        """Test that all 2880 sectors have valid addresses."""
        total_sectors = geometry.cylinders * geometry.heads * geometry.sectors_per_track

        for sector in range(total_sectors):
            cylinder = sector // (geometry.heads * geometry.sectors_per_track)
            head = (sector % (geometry.heads * geometry.sectors_per_track)) // geometry.sectors_per_track
            sector_offset = sector % geometry.sectors_per_track

            # Verify addresses are in valid ranges
            assert 0 <= cylinder < geometry.cylinders
            assert 0 <= head < geometry.heads
            assert 0 <= sector_offset < geometry.sectors_per_track

    def test_track_calculation(self, geometry):
        """Test calculating track number from sector."""
        # Track 0 = cylinder 0, head 0
        assert 0 // geometry.sectors_per_track == 0

        # Track 1 = cylinder 0, head 1
        assert 18 // geometry.sectors_per_track == 1

        # Track 2 = cylinder 1, head 0
        assert 36 // geometry.sectors_per_track == 2

        # Last track = cylinder 79, head 1
        assert 2862 // geometry.sectors_per_track == 159


class TestGeometryValidation:
    """Test geometry validation."""

    def test_valid_floppy_geometry(self):
        """Test that standard floppy geometry passes validation."""
        geometry = DiskGeometry(
            media_type=0x0F,
            cylinders=80,
            heads=2,
            sectors_per_track=18,
            bytes_per_sector=512
        )

        # Should have expected values
        assert geometry.cylinders == 80
        assert geometry.heads == 2
        assert geometry.sectors_per_track == 18

    def test_invalid_geometry_detection(self):
        """Test detection of non-floppy geometry."""
        # Hard drive geometry
        hdd_geometry = DiskGeometry(
            media_type=0x0C,
            cylinders=16383,
            heads=255,
            sectors_per_track=63,
            bytes_per_sector=512
        )

        # Should not match floppy geometry
        assert hdd_geometry.cylinders != 80
        assert hdd_geometry.heads != 2
        assert hdd_geometry.sectors_per_track != 18

    def test_720kb_floppy_geometry(self):
        """Test 720KB floppy geometry (different but valid)."""
        geometry = DiskGeometry(
            media_type=0x0D,  # F3_720_512
            cylinders=80,
            heads=2,
            sectors_per_track=9,  # Half the sectors
            bytes_per_sector=512
        )

        total_sectors = geometry.cylinders * geometry.heads * geometry.sectors_per_track
        assert total_sectors == 1440  # 720KB

    @pytest.mark.parametrize("cylinders,heads,sectors,expected_total", [
        (80, 2, 18, 2880),  # 1.44MB
        (80, 2, 9, 1440),   # 720KB
        (40, 2, 9, 720),    # 360KB
        (40, 2, 8, 640),    # 320KB
    ])
    def test_various_floppy_formats(self, cylinders, heads, sectors, expected_total):
        """Test various floppy disk formats."""
        geometry = DiskGeometry(
            media_type=0x0F,
            cylinders=cylinders,
            heads=heads,
            sectors_per_track=sectors,
            bytes_per_sector=512
        )

        total = geometry.cylinders * geometry.heads * geometry.sectors_per_track
        assert total == expected_total
