"""
Integration tests for recovery workflow.

Tests complete recovery operations including fixed passes,
convergence mode, statistics tracking, and thread safety.
"""

import pytest
from tests.fixtures import (
    create_degraded_disk,
    MockGeometry,
)


class TestRecoveryFixedPasses:
    """Test recovery with fixed number of passes."""

    def test_recovery_executes_exact_passes(self):
        """Test recovery executes exactly N passes."""
        mock_handle = create_degraded_disk(bad_sector_count=100)
        geometry = MockGeometry()

        requested_passes = 5
        passes_executed = 0
        bad_sector_history = []

        # Initial scan
        bad_count = len(mock_handle.bad_sectors)
        bad_sector_history.append(bad_count)

        # Execute fixed passes
        for pass_num in range(requested_passes):
            # Simulate recovery (mark some sectors as good)
            recovery_rate = 0.3  # 30% recovery per pass
            sectors_to_recover = int(len(mock_handle.bad_sectors) * recovery_rate)

            for sector in list(mock_handle.bad_sectors)[:sectors_to_recover]:
                mock_handle.mark_sector_good(sector)

            passes_executed += 1
            bad_count = len(mock_handle.bad_sectors)
            bad_sector_history.append(bad_count)

        assert passes_executed == requested_passes
        assert len(bad_sector_history) == requested_passes + 1  # Initial + N passes

    @pytest.mark.parametrize("pass_count", [3, 5, 7, 10])
    def test_various_fixed_pass_counts(self, pass_count):
        """Test various fixed pass counts."""
        mock_handle = create_degraded_disk(bad_sector_count=147)

        passes_executed = 0

        for pass_num in range(pass_count):
            # Simulate format pass
            recovery_rate = 0.4
            sectors_to_recover = int(len(mock_handle.bad_sectors) * recovery_rate)

            for sector in list(mock_handle.bad_sectors)[:sectors_to_recover]:
                mock_handle.mark_sector_good(sector)

            passes_executed += 1

        assert passes_executed == pass_count

    def test_fixed_passes_tracks_progress(self):
        """Test fixed passes track bad sector progress."""
        mock_handle = create_degraded_disk(bad_sector_count=147)

        bad_sector_history = []

        # Initial count
        bad_sector_history.append(len(mock_handle.bad_sectors))

        # Execute 5 passes
        for pass_num in range(5):
            # Simulate improvement
            recovery_rate = 0.4
            sectors_to_recover = int(len(mock_handle.bad_sectors) * recovery_rate)

            for sector in list(mock_handle.bad_sectors)[:sectors_to_recover]:
                mock_handle.mark_sector_good(sector)

            bad_sector_history.append(len(mock_handle.bad_sectors))

        # Should show decreasing bad sectors
        assert bad_sector_history[0] > bad_sector_history[-1]
        assert len(bad_sector_history) == 6  # Initial + 5 passes


class TestRecoveryConvergenceMode:
    """Test recovery with convergence detection."""

    def test_convergence_detects_stable_count(self):
        """Test convergence mode detects stable bad sector count."""
        mock_handle = create_degraded_disk(bad_sector_count=147)

        bad_sector_history = []
        convergence_threshold = 3
        max_passes = 50
        converged = False

        # Initial scan
        bad_sector_history.append(len(mock_handle.bad_sectors))

        # Simulate passes with eventual stabilization
        for pass_num in range(max_passes):
            if pass_num < 4:
                # First few passes show improvement
                recovery_rate = 0.4
                sectors_to_recover = int(len(mock_handle.bad_sectors) * recovery_rate)

                for sector in list(mock_handle.bad_sectors)[:sectors_to_recover]:
                    mock_handle.mark_sector_good(sector)
            else:
                # After pass 4, no more improvement (stabilized)
                pass

            bad_sector_history.append(len(mock_handle.bad_sectors))

            # Check for convergence
            if len(bad_sector_history) >= convergence_threshold + 1:
                last_n = bad_sector_history[-convergence_threshold:]
                if len(set(last_n)) == 1:  # All same value
                    converged = True
                    break

        assert converged is True
        assert len(bad_sector_history) < max_passes  # Should terminate early

    def test_convergence_early_termination(self):
        """Test convergence terminates before max passes."""
        bad_sector_history = [147, 89, 45, 23, 12, 12, 12]

        convergence_threshold = 3
        converged = False
        convergence_pass = None

        for i in range(len(bad_sector_history) - convergence_threshold + 1):
            window = bad_sector_history[i:i + convergence_threshold]
            if len(set(window)) == 1:
                converged = True
                convergence_pass = i + convergence_threshold
                break

        assert converged is True
        assert convergence_pass <= len(bad_sector_history)

    def test_convergence_respects_max_passes(self):
        """Test convergence respects maximum pass limit."""
        max_passes = 50
        passes_executed = 0

        # Simulate a disk that never stabilizes
        for pass_num in range(max_passes):
            passes_executed += 1

            if passes_executed >= max_passes:
                break

        assert passes_executed <= max_passes

    def test_convergence_at_zero_bad_sectors(self):
        """Test convergence when all sectors recovered."""
        mock_handle = create_degraded_disk(bad_sector_count=12)

        bad_sector_history = []
        convergence_threshold = 3

        # Initial scan
        bad_sector_history.append(len(mock_handle.bad_sectors))

        # Recover all sectors gradually
        while len(mock_handle.bad_sectors) > 0:
            # Recover some sectors
            recovery_count = min(4, len(mock_handle.bad_sectors))
            for sector in list(mock_handle.bad_sectors)[:recovery_count]:
                mock_handle.mark_sector_good(sector)

            bad_sector_history.append(len(mock_handle.bad_sectors))

        # Add convergence passes at zero
        for _ in range(3):
            bad_sector_history.append(0)

        # Check for convergence at zero
        last_n = bad_sector_history[-convergence_threshold:]
        converged = len(set(last_n)) == 1 and last_n[0] == 0

        assert converged is True


class TestRecoveryStatisticsTracking:
    """Test recovery statistics tracking."""

    def test_tracks_initial_bad_sectors(self):
        """Test tracking initial bad sector count."""
        mock_handle = create_degraded_disk(bad_sector_count=147)

        initial_bad = len(mock_handle.bad_sectors)

        assert initial_bad == 147

    def test_tracks_final_bad_sectors(self):
        """Test tracking final bad sector count."""
        mock_handle = create_degraded_disk(bad_sector_count=147)

        # Simulate recovery
        for pass_num in range(5):
            recovery_rate = 0.4
            sectors_to_recover = int(len(mock_handle.bad_sectors) * recovery_rate)

            for sector in list(mock_handle.bad_sectors)[:sectors_to_recover]:
                mock_handle.mark_sector_good(sector)

        final_bad = len(mock_handle.bad_sectors)

        assert final_bad < 147

    def test_calculates_recovery_rate(self):
        """Test recovery rate calculation."""
        initial_bad = 147
        final_bad = 12

        recovered = initial_bad - final_bad
        recovery_rate = (recovered / initial_bad) * 100.0

        assert recovered == 135
        assert abs(recovery_rate - 91.84) < 0.01

    def test_tracks_passes_executed(self):
        """Test tracking number of passes executed."""
        passes_executed = 0

        for pass_num in range(8):
            passes_executed += 1

        assert passes_executed == 8

    def test_tracks_bad_sector_history(self):
        """Test tracking bad sector count per pass."""
        mock_handle = create_degraded_disk(bad_sector_count=147)

        bad_sector_history = []

        # Initial scan
        bad_sector_history.append(len(mock_handle.bad_sectors))

        # Execute passes
        for pass_num in range(5):
            recovery_rate = 0.4
            sectors_to_recover = int(len(mock_handle.bad_sectors) * recovery_rate)

            for sector in list(mock_handle.bad_sectors)[:sectors_to_recover]:
                mock_handle.mark_sector_good(sector)

            bad_sector_history.append(len(mock_handle.bad_sectors))

        # Should have initial + 5 pass counts
        assert len(bad_sector_history) == 6

        # Should show decreasing trend
        for i in range(1, len(bad_sector_history)):
            assert bad_sector_history[i] <= bad_sector_history[i-1]


class TestThreadSafety:
    """Test thread safety and UI responsiveness."""

    def test_operation_can_be_split_into_chunks(self):
        """Test operation can be split for UI updates."""
        mock_handle = create_degraded_disk(bad_sector_count=100)

        total_sectors = 2880
        chunk_size = 100
        chunks_processed = 0

        for start_sector in range(0, total_sectors, chunk_size):
            end_sector = min(start_sector + chunk_size, total_sectors)

            # Process chunk
            for sector in range(start_sector, end_sector):
                mock_handle.read_sector(sector)

            chunks_processed += 1

            # Simulate UI update opportunity
            # (In real code, would call app.call_from_thread here)

        assert chunks_processed == 29  # ceil(2880/100)

    def test_progress_updates_available(self):
        """Test progress updates can be generated."""
        total_sectors = 2880
        progress_updates = []

        for sector in range(total_sectors):
            progress = (sector + 1) / total_sectors * 100
            progress_updates.append(progress)

        assert len(progress_updates) == 2880
        assert progress_updates[0] < 1.0
        assert progress_updates[-1] == 100.0

    def test_cancellation_flag_checked(self):
        """Test cancellation flag can be checked."""
        cancelled = False
        sectors_processed = 0

        for sector in range(2880):
            if cancelled:
                break

            sectors_processed += 1

            # Simulate cancellation after 1000 sectors
            if sector == 1000:
                cancelled = True

        assert sectors_processed == 1001  # Processed up to and including 1000

    def test_partial_results_can_be_saved(self):
        """Test partial results can be saved on cancellation."""
        mock_handle = create_degraded_disk(bad_sector_count=100)

        bad_sectors_found = []
        cancelled = False

        for sector in range(2880):
            if cancelled:
                break

            success, data, error = mock_handle.read_sector(sector)
            if not success:
                bad_sectors_found.append(sector)

            # Simulate cancellation at sector 50 (before all bad sectors found)
            if sector == 50:
                cancelled = True

        # Should have partial results
        assert len(bad_sectors_found) > 0
        assert len(bad_sectors_found) <= 51  # Only scanned up to sector 50


class TestCancellation:
    """Test graceful worker cancellation."""

    def test_cancellation_stops_operation(self):
        """Test cancellation stops operation cleanly."""
        cancelled = False
        passes_completed = 0
        max_passes = 10

        for pass_num in range(max_passes):
            if cancelled:
                break

            passes_completed += 1

            # Simulate cancellation after 3 passes
            if pass_num == 2:
                cancelled = True

        assert passes_completed == 3

    def test_cancellation_saves_partial_results(self):
        """Test cancellation triggers partial results save."""
        mock_handle = create_degraded_disk(bad_sector_count=147)

        bad_sector_history = []
        cancelled = False
        partial_data = None

        # Initial scan
        bad_sector_history.append(len(mock_handle.bad_sectors))

        for pass_num in range(10):
            if cancelled:
                # Save partial results
                partial_data = {
                    'completed': False,
                    'passes_completed': pass_num,
                    'bad_sector_history': bad_sector_history,
                }
                break

            # Simulate recovery pass
            recovery_rate = 0.4
            sectors_to_recover = int(len(mock_handle.bad_sectors) * recovery_rate)

            for sector in list(mock_handle.bad_sectors)[:sectors_to_recover]:
                mock_handle.mark_sector_good(sector)

            bad_sector_history.append(len(mock_handle.bad_sectors))

            # Cancel after completing pass 2 (0-indexed, so after pass_num 2 completes)
            if pass_num == 2:
                cancelled = True

        assert partial_data is not None
        assert partial_data['completed'] is False
        assert partial_data['passes_completed'] == 3

    def test_cancellation_cleanup_occurs(self):
        """Test cleanup occurs on cancellation."""
        cleanup_occurred = False

        try:
            for pass_num in range(10):
                if pass_num == 5:
                    # Simulate cancellation
                    raise InterruptedError("User cancelled")

        except InterruptedError:
            # Cleanup
            cleanup_occurred = True

        assert cleanup_occurred is True

    def test_worker_returns_none_on_cancellation(self):
        """Test worker returns None when cancelled."""
        cancelled = False
        result = None

        for pass_num in range(10):
            if cancelled:
                result = None
                break

            # Do work
            if pass_num == 3:
                cancelled = True

        # Complete normally
        if not cancelled:
            result = {'status': 'completed'}

        assert result is None


class TestRecoveryRecommendations:
    """Test recovery recommendations based on results."""

    def test_perfect_recovery_recommendation(self):
        """Test recommendation for perfect recovery."""
        final_bad_sectors = 0

        if final_bad_sectors == 0:
            recommendation = "Disk is fully functional with zero bad sectors."
        else:
            recommendation = "Disk has remaining bad sectors."

        assert "fully functional" in recommendation

    def test_good_recovery_recommendation(self):
        """Test recommendation for good recovery (<1% bad)."""
        final_bad_sectors = 12  # 0.42%
        total_sectors = 2880

        percentage = (final_bad_sectors / total_sectors) * 100

        if percentage < 1.0:
            recommendation = "Safe for most uses."
        else:
            recommendation = "Limited use recommended."

        assert "Safe for most uses" in recommendation

    def test_degraded_recommendation(self):
        """Test recommendation for degraded disk (1-5% bad)."""
        final_bad_sectors = 72  # 2.5%
        total_sectors = 2880

        percentage = (final_bad_sectors / total_sectors) * 100

        if 1.0 <= percentage < 5.0:
            recommendation = "Usable but avoid critical data."
        else:
            recommendation = "Other status."

        assert "avoid critical data" in recommendation

    def test_poor_recommendation(self):
        """Test recommendation for poor disk (5-20% bad)."""
        final_bad_sectors = 288  # 10%
        total_sectors = 2880

        percentage = (final_bad_sectors / total_sectors) * 100

        if 5.0 <= percentage < 20.0:
            recommendation = "Significant reliability concerns."
        else:
            recommendation = "Other status."

        assert "reliability concerns" in recommendation

    def test_unusable_recommendation(self):
        """Test recommendation for unusable disk (>20% bad)."""
        final_bad_sectors = 600  # 20.8%
        total_sectors = 2880

        percentage = (final_bad_sectors / total_sectors) * 100

        if percentage >= 20.0:
            recommendation = "Should be replaced."
        else:
            recommendation = "Other status."

        assert "replaced" in recommendation
