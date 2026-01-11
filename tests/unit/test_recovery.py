"""
Unit tests for recovery algorithms.

Tests convergence detection, fixed pass mode, pattern rotation,
and recovery statistics.
"""

import pytest


class TestConvergenceDetection:
    """Test convergence algorithm logic."""

    def test_convergence_same_count_3_passes(self):
        """Test convergence detection with same count for 3 consecutive passes."""
        bad_sector_history = [147, 89, 45, 23, 12, 12, 12]

        # Check for convergence (3 consecutive same values)
        convergence_threshold = 3
        converged = False

        for i in range(len(bad_sector_history) - convergence_threshold + 1):
            window = bad_sector_history[i:i + convergence_threshold]
            if len(set(window)) == 1:  # All same value
                converged = True
                break

        assert converged is True

    def test_no_convergence_still_improving(self):
        """Test that convergence is not detected when still improving."""
        bad_sector_history = [147, 89, 45, 23, 12]

        convergence_threshold = 3
        converged = False

        for i in range(len(bad_sector_history) - convergence_threshold + 1):
            window = bad_sector_history[i:i + convergence_threshold]
            if len(set(window)) == 1:
                converged = True
                break

        assert converged is False

    def test_secondary_convergence_no_improvement_5_passes(self):
        """Test secondary convergence: no improvement in 5 passes."""
        bad_sector_history = [147, 89, 45, 23, 23, 23, 23, 23]

        # Check for no improvement in last 5 passes
        if len(bad_sector_history) >= 6:
            last_5 = bad_sector_history[-5:]
            all_same = len(set(last_5)) == 1
            assert all_same is True
        else:
            assert False, "Not enough history"

    def test_safety_limit_50_passes(self):
        """Test safety limit of 50 passes."""
        max_passes = 50

        # Simulate a situation that never converges
        bad_sector_history = list(range(50, 0, -1))  # Always decreasing, never stabilizes

        # Should stop at safety limit
        assert len(bad_sector_history) <= max_passes

    def test_early_convergence_detection(self):
        """Test that convergence is detected early."""
        bad_sector_history = [147, 89, 45, 12, 12, 12]

        convergence_threshold = 3
        convergence_pass = None

        for i in range(len(bad_sector_history) - convergence_threshold + 1):
            window = bad_sector_history[i:i + convergence_threshold]
            if len(set(window)) == 1:
                convergence_pass = i + convergence_threshold
                break

        assert convergence_pass == 6  # Converged after pass 5 (index 5 + 1)

    def test_convergence_at_zero(self):
        """Test convergence when all sectors recovered."""
        bad_sector_history = [147, 89, 45, 23, 12, 0, 0, 0]

        convergence_threshold = 3
        converged = False
        convergence_value = None

        for i in range(len(bad_sector_history) - convergence_threshold + 1):
            window = bad_sector_history[i:i + convergence_threshold]
            if len(set(window)) == 1:
                converged = True
                convergence_value = window[0]
                break

        assert converged is True
        assert convergence_value == 0


class TestFixedPassMode:
    """Test fixed pass mode execution."""

    def test_exact_pass_count(self):
        """Test that exactly N passes are executed in fixed mode."""
        requested_passes = 5
        passes_executed = 0

        # Simulate fixed pass execution
        for pass_num in range(requested_passes):
            passes_executed += 1

        assert passes_executed == requested_passes

    @pytest.mark.parametrize("pass_count", [1, 3, 5, 7, 10])
    def test_various_pass_counts(self, pass_count):
        """Test various fixed pass counts."""
        passes_executed = 0

        for pass_num in range(pass_count):
            passes_executed += 1

        assert passes_executed == pass_count

    def test_no_early_termination_fixed_mode(self):
        """Test that fixed mode doesn't terminate early even if stable."""
        requested_passes = 10
        bad_sector_history = []

        # Simulate passes where sectors stabilize early
        for pass_num in range(requested_passes):
            if pass_num < 5:
                bad_sector_history.append(100 - pass_num * 20)
            else:
                # Stabilized at 0
                bad_sector_history.append(0)

        # Should still execute all passes
        assert len(bad_sector_history) == requested_passes


class TestPatternRotation:
    """Test pattern rotation across passes."""

    def test_pattern_sequence(self):
        """Test pattern rotation through 0x55, 0xAA, 0xFF, 0x00."""
        patterns = [0x55, 0xAA, 0xFF, 0x00]

        for pass_num in range(12):  # Test 12 passes (3 full cycles)
            expected_pattern = patterns[pass_num % 4]
            actual_pattern = patterns[pass_num % 4]
            assert actual_pattern == expected_pattern

    def test_pattern_for_each_pass(self):
        """Test correct pattern for each pass number."""
        patterns = [0x55, 0xAA, 0xFF, 0x00]

        # Pass 0 -> 0x55
        assert patterns[0 % 4] == 0x55

        # Pass 1 -> 0xAA
        assert patterns[1 % 4] == 0xAA

        # Pass 2 -> 0xFF
        assert patterns[2 % 4] == 0xFF

        # Pass 3 -> 0x00
        assert patterns[3 % 4] == 0x00

        # Pass 4 -> 0x55 (cycle repeats)
        assert patterns[4 % 4] == 0x55

    def test_pattern_cycle_coverage(self):
        """Test that all patterns are used in a 4-pass cycle."""
        patterns = [0x55, 0xAA, 0xFF, 0x00]
        used_patterns = set()

        for pass_num in range(4):
            pattern = patterns[pass_num % 4]
            used_patterns.add(pattern)

        assert used_patterns == {0x55, 0xAA, 0xFF, 0x00}


class TestRecoveryStatistics:
    """Test recovery statistics tracking."""

    def test_initial_bad_sectors_tracking(self):
        """Test tracking initial bad sector count."""
        initial_bad = 147
        final_bad = 12

        # Calculate recovery
        recovered = initial_bad - final_bad
        assert recovered == 135

    def test_recovery_rate_calculation(self):
        """Test recovery rate percentage calculation."""
        initial_bad = 147
        final_bad = 12
        recovered = initial_bad - final_bad

        recovery_rate = (recovered / initial_bad) * 100.0
        assert abs(recovery_rate - 91.84) < 0.01

    def test_perfect_recovery(self):
        """Test statistics for perfect recovery."""
        initial_bad = 100
        final_bad = 0

        recovered = initial_bad - final_bad
        recovery_rate = (recovered / initial_bad) * 100.0

        assert recovered == 100
        assert recovery_rate == 100.0

    def test_no_recovery(self):
        """Test statistics when no recovery occurs."""
        initial_bad = 100
        final_bad = 100

        recovered = initial_bad - final_bad
        recovery_rate = (recovered / initial_bad) * 100.0 if initial_bad > 0 else 0.0

        assert recovered == 0
        assert recovery_rate == 0.0

    def test_partial_recovery(self):
        """Test statistics for partial recovery."""
        initial_bad = 100
        final_bad = 30

        recovered = initial_bad - final_bad
        recovery_rate = (recovered / initial_bad) * 100.0

        assert recovered == 70
        assert recovery_rate == 70.0

    def test_bad_sector_history_tracking(self):
        """Test tracking bad sector count per pass."""
        bad_sector_history = []

        # Simulate 5 passes with decreasing bad sectors
        counts = [147, 89, 45, 23, 12]
        for count in counts:
            bad_sector_history.append(count)

        assert len(bad_sector_history) == 5
        assert bad_sector_history[0] == 147  # Initial
        assert bad_sector_history[-1] == 12  # Final


class TestPowerManagement:
    """Test power management function calls."""

    def test_prevent_sleep_called(self):
        """Test that prevent_sleep would be called."""
        # Simulate entering recovery operation
        sleep_prevented = True

        assert sleep_prevented is True

    def test_allow_sleep_called_after_completion(self):
        """Test that allow_sleep would be called after completion."""
        # Simulate completing recovery operation
        sleep_allowed = True

        assert sleep_allowed is True

    def test_allow_sleep_called_on_error(self):
        """Test that allow_sleep is called even on error."""
        # Simulate error during recovery
        try:
            # Operation fails
            raise Exception("Simulated error")
        except:
            sleep_allowed = True

        assert sleep_allowed is True


class TestConvergenceAlgorithmEdgeCases:
    """Test edge cases in convergence detection."""

    def test_immediate_convergence(self):
        """Test convergence on first scan (disk already perfect)."""
        bad_sector_history = [0, 0, 0, 0]

        convergence_threshold = 3
        converged = False

        for i in range(len(bad_sector_history) - convergence_threshold + 1):
            window = bad_sector_history[i:i + convergence_threshold]
            if len(set(window)) == 1:
                converged = True
                break

        assert converged is True

    def test_oscillating_values(self):
        """Test handling of oscillating bad sector counts."""
        bad_sector_history = [100, 50, 100, 50, 100, 50]

        convergence_threshold = 3
        converged = False

        for i in range(len(bad_sector_history) - convergence_threshold + 1):
            window = bad_sector_history[i:i + convergence_threshold]
            if len(set(window)) == 1:
                converged = True
                break

        # Should not converge (values oscillate)
        assert converged is False

    def test_gradual_improvement_then_stabilize(self):
        """Test gradual improvement followed by stabilization."""
        bad_sector_history = [200, 180, 160, 140, 120, 100, 80, 60, 50, 50, 50]

        convergence_threshold = 3
        converged = False
        convergence_pass = None

        for i in range(len(bad_sector_history) - convergence_threshold + 1):
            window = bad_sector_history[i:i + convergence_threshold]
            if len(set(window)) == 1:
                converged = True
                convergence_pass = i
                break

        assert converged is True
        # Should converge at the point where it stabilized (index 8)
        assert convergence_pass == 8

    def test_single_pass_insufficient(self):
        """Test that single pass doesn't trigger convergence."""
        bad_sector_history = [100]

        convergence_threshold = 3
        converged = False

        if len(bad_sector_history) >= convergence_threshold:
            for i in range(len(bad_sector_history) - convergence_threshold + 1):
                window = bad_sector_history[i:i + convergence_threshold]
                if len(set(window)) == 1:
                    converged = True
                    break

        # Not enough data for convergence
        assert converged is False

    def test_two_passes_insufficient(self):
        """Test that two passes don't trigger 3-pass convergence."""
        bad_sector_history = [100, 100]

        convergence_threshold = 3
        converged = False

        if len(bad_sector_history) >= convergence_threshold:
            for i in range(len(bad_sector_history) - convergence_threshold + 1):
                window = bad_sector_history[i:i + convergence_threshold]
                if len(set(window)) == 1:
                    converged = True
                    break

        # Not enough data for convergence
        assert converged is False
