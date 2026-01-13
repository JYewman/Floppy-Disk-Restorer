#!/usr/bin/env python3
"""
Demo and performance test script for CircularSectorMap widget.

Tests the circular sector visualization with 2,880 wedges and measures
performance to ensure it meets the required targets.
"""

import sys
import time
import random
import psutil
import os
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGroupBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from floppy_formatter.gui.widgets.circular_sector_map import CircularSectorMap


class PerformanceTestWindow(QMainWindow):
    """
    Main window for testing CircularSectorMap performance.
    """

    def __init__(self):
        """Initialize test window."""
        super().__init__()

        self.setWindowTitle("Circular Sector Map - Performance Test")
        self.setMinimumSize(1200, 900)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Title
        title_label = QLabel("Circular Sector Map - 2,880 Sectors")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # Create circular sector map
        self.sector_map = CircularSectorMap()
        main_layout.addWidget(self.sector_map, stretch=1)

        # Control panel
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)

        # Performance metrics
        metrics_panel = self._create_metrics_panel()
        main_layout.addWidget(metrics_panel)

        # FPS counter
        self.fps_counter = 0
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self._update_fps)
        self.fps_timer.start(1000)  # Update every second

        # Animation timer for randomize
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_random)
        self.animation_active = False

        # Store initial memory
        self.process = psutil.Process(os.getpid())
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        # Run initial performance tests
        QTimer.singleShot(500, self._run_initial_tests)

    def _create_control_panel(self) -> QGroupBox:
        """
        Create control panel with test buttons.

        Returns:
            Control panel group box
        """
        group = QGroupBox("Controls")
        layout = QHBoxLayout()

        # Test buttons
        btn_randomize = QPushButton("Randomize")
        btn_randomize.setToolTip("Randomly mark sectors as good or bad")
        btn_randomize.clicked.connect(self._randomize_sectors)

        btn_all_good = QPushButton("Mark All Good")
        btn_all_good.setToolTip("Mark all sectors as good (green)")
        btn_all_good.clicked.connect(self._mark_all_good)

        btn_all_bad = QPushButton("Mark All Bad")
        btn_all_bad.setToolTip("Mark all sectors as bad (red)")
        btn_all_bad.clicked.connect(self._mark_all_bad)

        btn_reset = QPushButton("Reset")
        btn_reset.setToolTip("Reset all sectors to unscanned (gray)")
        btn_reset.clicked.connect(self._reset_sectors)

        btn_animate = QPushButton("Animate Random")
        btn_animate.setToolTip("Continuously animate random sectors")
        btn_animate.clicked.connect(self._toggle_animation)
        self.btn_animate = btn_animate

        btn_test = QPushButton("Run Performance Tests")
        btn_test.setToolTip("Run comprehensive performance tests")
        btn_test.clicked.connect(self._run_performance_tests)

        layout.addWidget(btn_randomize)
        layout.addWidget(btn_all_good)
        layout.addWidget(btn_all_bad)
        layout.addWidget(btn_reset)
        layout.addWidget(btn_animate)
        layout.addWidget(btn_test)

        group.setLayout(layout)
        return group

    def _create_metrics_panel(self) -> QGroupBox:
        """
        Create performance metrics display panel.

        Returns:
            Metrics panel group box
        """
        group = QGroupBox("Performance Metrics")
        layout = QVBoxLayout()

        # Metrics labels
        self.label_fps = QLabel("FPS: --")
        self.label_render_time = QLabel("Initial Render: -- ms")
        self.label_single_update = QLabel("Single Update: -- ms")
        self.label_batch_update = QLabel("Batch Update (2880): -- ms")
        self.label_memory = QLabel("Memory: -- MB")

        font = QFont("Monospace")
        font.setPointSize(10)
        for label in [
            self.label_fps,
            self.label_render_time,
            self.label_single_update,
            self.label_batch_update,
            self.label_memory,
        ]:
            label.setFont(font)
            layout.addWidget(label)

        group.setLayout(layout)
        return group

    def _update_fps(self) -> None:
        """Update FPS counter display."""
        self.label_fps.setText(f"FPS: {self.fps_counter}")
        self.fps_counter = 0

        # Update memory usage
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        memory_used = current_memory - self.initial_memory
        self.label_memory.setText(f"Memory: {memory_used:.1f} MB (Total: {current_memory:.1f} MB)")

    def _run_initial_tests(self) -> None:
        """Run initial performance tests on startup."""
        # Initial render time is already done (widget creation)
        # Let's measure it by recreating
        start_time = time.perf_counter()
        self.sector_map._create_wedges()
        end_time = time.perf_counter()
        render_time = (end_time - start_time) * 1000

        self.label_render_time.setText(f"Initial Render: {render_time:.1f} ms {'✓' if render_time < 200 else '✗'}")

    def _run_performance_tests(self) -> None:
        """Run comprehensive performance tests."""
        print("\n" + "=" * 60)
        print("CIRCULAR SECTOR MAP - PERFORMANCE TEST")
        print("=" * 60)

        # Test 1: Initial render time
        print("\n[1/4] Testing initial render time...")
        start_time = time.perf_counter()
        # Recreate the scene to measure render time
        test_map = CircularSectorMap()
        end_time = time.perf_counter()
        render_time = (end_time - start_time) * 1000

        render_pass = render_time < 200
        print(f"  Initial render: {render_time:.1f} ms {'✓ PASS' if render_pass else '✗ FAIL'} (target: < 200ms)")
        self.label_render_time.setText(f"Initial Render: {render_time:.1f} ms {'✓' if render_pass else '✗'}")

        # Clean up test map
        test_map.deleteLater()

        # Test 2: Single sector update time
        print("\n[2/4] Testing single sector update time...")
        times = []
        for _ in range(100):
            sector_num = random.randint(0, 2879)
            is_good = random.choice([True, False])

            start_time = time.perf_counter()
            self.sector_map.update_sector(sector_num, is_good, animate=False)
            end_time = time.perf_counter()

            times.append((end_time - start_time) * 1000)

        avg_single_update = sum(times) / len(times)
        max_single_update = max(times)
        single_pass = max_single_update < 5

        print(f"  Avg single update: {avg_single_update:.3f} ms")
        print(f"  Max single update: {max_single_update:.3f} ms {'✓ PASS' if single_pass else '✗ FAIL'} (target: < 5ms)")
        self.label_single_update.setText(f"Single Update: {avg_single_update:.3f} ms (max: {max_single_update:.3f} ms) {'✓' if single_pass else '✗'}")

        # Test 3: Batch update all 2,880 sectors
        print("\n[3/4] Testing batch update time (2,880 sectors)...")
        sector_statuses = {i: random.choice([True, False, None]) for i in range(2880)}

        start_time = time.perf_counter()
        self.sector_map.update_all_sectors(sector_statuses, animate=False)
        QApplication.processEvents()  # Process pending events
        end_time = time.perf_counter()

        batch_time = (end_time - start_time) * 1000
        batch_pass = batch_time < 1000

        print(f"  Batch update: {batch_time:.1f} ms {'✓ PASS' if batch_pass else '✗ FAIL'} (target: < 1000ms)")
        self.label_batch_update.setText(f"Batch Update (2880): {batch_time:.1f} ms {'✓' if batch_pass else '✗'}")

        # Test 4: Memory usage
        print("\n[4/4] Testing memory usage...")
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        memory_used = current_memory - self.initial_memory
        memory_pass = memory_used < 200

        print(f"  Memory used: {memory_used:.1f} MB {'✓ PASS' if memory_pass else '✗ FAIL'} (target: < 200MB)")
        print(f"  Total memory: {current_memory:.1f} MB")

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        all_pass = render_pass and single_pass and batch_pass and memory_pass

        print(f"Initial Render:    {render_time:.1f} ms    {'✓ PASS' if render_pass else '✗ FAIL'}")
        print(f"Single Update:     {max_single_update:.3f} ms   {'✓ PASS' if single_pass else '✗ FAIL'}")
        print(f"Batch Update:      {batch_time:.1f} ms   {'✓ PASS' if batch_pass else '✗ FAIL'}")
        print(f"Memory Usage:      {memory_used:.1f} MB   {'✓ PASS' if memory_pass else '✗ FAIL'}")
        print("\n" + ("✓ ALL TESTS PASSED" if all_pass else "✗ SOME TESTS FAILED"))
        print("=" * 60 + "\n")

    def _randomize_sectors(self) -> None:
        """Randomize sector states."""
        print("Randomizing sectors...")
        start_time = time.perf_counter()

        sector_statuses = {}
        for i in range(2880):
            # 70% good, 20% bad, 10% unscanned
            rand = random.random()
            if rand < 0.7:
                sector_statuses[i] = True  # Good
            elif rand < 0.9:
                sector_statuses[i] = False  # Bad
            else:
                sector_statuses[i] = None  # Unscanned

        self.sector_map.update_all_sectors(sector_statuses, animate=False)
        QApplication.processEvents()

        end_time = time.perf_counter()
        elapsed = (end_time - start_time) * 1000
        print(f"  Randomized 2,880 sectors in {elapsed:.1f} ms")

    def _mark_all_good(self) -> None:
        """Mark all sectors as good."""
        print("Marking all sectors as good...")
        start_time = time.perf_counter()

        sector_statuses = {i: True for i in range(2880)}
        self.sector_map.update_all_sectors(sector_statuses, animate=False)
        QApplication.processEvents()

        end_time = time.perf_counter()
        elapsed = (end_time - start_time) * 1000
        print(f"  Marked all sectors good in {elapsed:.1f} ms")

    def _mark_all_bad(self) -> None:
        """Mark all sectors as bad."""
        print("Marking all sectors as bad...")
        start_time = time.perf_counter()

        sector_statuses = {i: False for i in range(2880)}
        self.sector_map.update_all_sectors(sector_statuses, animate=False)
        QApplication.processEvents()

        end_time = time.perf_counter()
        elapsed = (end_time - start_time) * 1000
        print(f"  Marked all sectors bad in {elapsed:.1f} ms")

    def _reset_sectors(self) -> None:
        """Reset all sectors to unscanned."""
        print("Resetting all sectors...")
        start_time = time.perf_counter()

        self.sector_map.reset_all_sectors()
        QApplication.processEvents()

        end_time = time.perf_counter()
        elapsed = (end_time - start_time) * 1000
        print(f"  Reset all sectors in {elapsed:.1f} ms")

    def _toggle_animation(self) -> None:
        """Toggle continuous animation."""
        if self.animation_active:
            self.animation_timer.stop()
            self.animation_active = False
            self.btn_animate.setText("Animate Random")
            print("Animation stopped")
        else:
            self.animation_timer.start(100)  # Update every 100ms
            self.animation_active = True
            self.btn_animate.setText("Stop Animation")
            print("Animation started")

    def _animate_random(self) -> None:
        """Animate random sectors (called by timer)."""
        # Update 10 random sectors per frame
        for _ in range(10):
            sector_num = random.randint(0, 2879)
            is_good = random.choice([True, False, None])
            self.sector_map.update_sector(sector_num, is_good, animate=True)

        # Increment FPS counter
        self.fps_counter += 1

    def paintEvent(self, event) -> None:
        """Handle paint event to count frames."""
        super().paintEvent(event)
        if self.animation_active:
            self.fps_counter += 1


def main():
    """Main entry point for test script."""
    print("Circular Sector Map - Performance Test")
    print("=" * 60)
    print("This test will measure the performance of the circular sector")
    print("visualization with 2,880 wedges.")
    print()
    print("Requirements:")
    print("  - Initial render: < 200ms")
    print("  - Single update: < 5ms")
    print("  - Batch update (2880): < 1000ms")
    print("  - Memory usage: < 200MB")
    print("  - Animations: 60 FPS")
    print("=" * 60)
    print()

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Circular Sector Map Test")

    # Apply dark theme (same as main app)
    app.setStyleSheet("""
        * {
            background-color: #1e1e1e;
            color: #cccccc;
            font-family: "Segoe UI", "Ubuntu", sans-serif;
        }
        QPushButton {
            background-color: #0e639c;
            color: #ffffff;
            border: 1px solid #0e639c;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1177bb;
        }
        QGroupBox {
            border: 1px solid #3a3d41;
            border-radius: 4px;
            margin-top: 12px;
            padding-top: 16px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
        }
    """)

    # Create and show window
    window = PerformanceTestWindow()
    window.show()

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
