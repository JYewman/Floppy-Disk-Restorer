"""
Verification tab for Analytics Dashboard.

Displays verification results including:
- Overall verification statistics
- Per-track sector status breakdown
- Verification history/results table
- Grade distribution chart

Part of Phase 11: Batch Operations & Verification Display
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSizePolicy,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

COLOR_BACKGROUND = QColor("#1e1e1e")
COLOR_CARD_BG = QColor("#252526")
COLOR_CARD_BORDER = QColor("#3a3d41")
COLOR_TEXT = QColor("#cccccc")
COLOR_TEXT_DIM = QColor("#808080")

COLOR_GRADE_A = QColor("#4ec9b0")  # Excellent - Green
COLOR_GRADE_B = QColor("#569cd6")  # Good - Blue
COLOR_GRADE_C = QColor("#dcdcaa")  # Fair - Yellow
COLOR_GRADE_D = QColor("#ce9178")  # Poor - Orange
COLOR_GRADE_F = QColor("#f14c4c")  # Failed - Red
COLOR_SKIPPED = QColor("#808080")  # Skipped - Gray


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TrackVerificationResult:
    """
    Verification result for a single track.

    Attributes:
        cylinder: Cylinder number
        head: Head number
        good_sectors: Number of good sectors
        bad_sectors: Number of bad sectors
        weak_sectors: Number of weak sectors
        total_sectors: Total sectors on track
        errors: List of error descriptions
    """
    cylinder: int
    head: int
    good_sectors: int = 0
    bad_sectors: int = 0
    weak_sectors: int = 0
    total_sectors: int = 18
    errors: List[str] = field(default_factory=list)

    @property
    def is_perfect(self) -> bool:
        """Check if all sectors are good."""
        return self.good_sectors == self.total_sectors

    @property
    def has_errors(self) -> bool:
        """Check if any sectors have errors."""
        return self.bad_sectors > 0


@dataclass
class VerificationSummary:
    """
    Summary of a verification operation.

    Attributes:
        timestamp: When verification was performed
        total_sectors: Total sectors checked
        good_sectors: Number of good sectors
        bad_sectors: Number of bad sectors
        weak_sectors: Number of weak/marginal sectors
        grade: Overall grade (A-F)
        score: Numeric score (0-100)
        duration_ms: Duration in milliseconds
        disk_type: Disk type (HD/DD)
        encoding: Detected encoding
        track_results: Per-track results
    """
    timestamp: datetime = field(default_factory=datetime.now)
    total_sectors: int = 2880
    good_sectors: int = 0
    bad_sectors: int = 0
    weak_sectors: int = 0
    grade: str = "F"
    score: float = 0.0
    duration_ms: int = 0
    disk_type: str = "HD"
    encoding: str = "MFM"
    track_results: List[TrackVerificationResult] = field(default_factory=list)

    @property
    def good_percentage(self) -> float:
        """Percentage of good sectors."""
        if self.total_sectors == 0:
            return 0.0
        return (self.good_sectors / self.total_sectors) * 100

    @property
    def bad_percentage(self) -> float:
        """Percentage of bad sectors."""
        if self.total_sectors == 0:
            return 0.0
        return (self.bad_sectors / self.total_sectors) * 100

    @property
    def bad_track_count(self) -> int:
        """Number of tracks with at least one error."""
        return sum(1 for t in self.track_results if t.has_errors)


# =============================================================================
# Widgets
# =============================================================================

class GradeWidget(QWidget):
    """Widget displaying a letter grade with color."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self._grade = "?"
        self._color = COLOR_TEXT_DIM

    def set_grade(self, grade: str) -> None:
        """Set the grade to display."""
        self._grade = grade

        # Set color based on grade
        color_map = {
            'A': COLOR_GRADE_A,
            'B': COLOR_GRADE_B,
            'C': COLOR_GRADE_C,
            'D': COLOR_GRADE_D,
            'F': COLOR_GRADE_F,
            'S': COLOR_SKIPPED,
        }
        self._color = color_map.get(grade, COLOR_TEXT_DIM)
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the grade circle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw circle background
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.setPen(QPen(self._color, 3))
        painter.setBrush(QBrush(COLOR_CARD_BG))
        painter.drawEllipse(rect)

        # Draw grade letter
        font = QFont()
        font.setPointSize(32)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self._color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._grade)

        painter.end()


class StatCard(QWidget):
    """Card widget displaying a statistic."""

    def __init__(
        self,
        title: str,
        value: str = "0",
        subtitle: str = "",
        color: QColor = COLOR_TEXT,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        # No border - parent container provides the border
        self.setStyleSheet("background: transparent;")
        # Set minimum size and size policy to expand
        self.setMinimumSize(100, 70)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # Title
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 11px; background: transparent;")
        layout.addWidget(self._title_label)

        # Value
        self._value_label = QLabel(value)
        self._value_label.setStyleSheet(f"color: {color.name()}; font-size: 22px; font-weight: bold; background: transparent;")
        layout.addWidget(self._value_label)

        # Subtitle
        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 10px; background: transparent;")
        layout.addWidget(self._subtitle_label)

    def set_value(self, value: str, color: Optional[QColor] = None) -> None:
        """Update the displayed value."""
        self._value_label.setText(value)
        if color:
            self._value_label.setStyleSheet(f"color: {color.name()}; font-size: 22px; font-weight: bold; background: transparent;")

    def set_subtitle(self, subtitle: str) -> None:
        """Update the subtitle."""
        self._subtitle_label.setText(subtitle)


class GradeDistributionBar(QWidget):
    """Horizontal bar showing grade distribution."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self._distribution: Dict[str, int] = {}
        self._total = 0

    def set_distribution(self, distribution: Dict[str, int]) -> None:
        """Set the grade distribution to display."""
        self._distribution = distribution
        self._total = sum(distribution.values())
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the distribution bar."""
        if self._total == 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = {
            'A': COLOR_GRADE_A,
            'B': COLOR_GRADE_B,
            'C': COLOR_GRADE_C,
            'D': COLOR_GRADE_D,
            'F': COLOR_GRADE_F,
            'S': COLOR_SKIPPED,
        }

        x = 0
        width = self.width()
        height = self.height()

        for grade in ['A', 'B', 'C', 'D', 'F', 'S']:
            count = self._distribution.get(grade, 0)
            if count == 0:
                continue

            segment_width = int((count / self._total) * width)
            if segment_width < 1:
                segment_width = 1

            color = colors.get(grade, COLOR_TEXT_DIM)
            painter.fillRect(x, 0, segment_width, height, color)

            # Draw count label if segment is wide enough
            if segment_width > 20:
                painter.setPen(Qt.GlobalColor.white if grade != 'C' else Qt.GlobalColor.black)
                font = QFont()
                font.setPointSize(9)
                painter.setFont(font)
                painter.drawText(x, 0, segment_width, height,
                               Qt.AlignmentFlag.AlignCenter, str(count))

            x += segment_width

        painter.end()


# =============================================================================
# Verification Tab
# =============================================================================

class VerificationTab(QWidget):
    """
    Tab displaying verification results.

    Shows:
    - Overall grade and score
    - Sector statistics (good/bad/weak)
    - Track-by-track breakdown table
    - Grade distribution

    Signals:
        track_selected(int, int): Emitted when user clicks a track (cyl, head)
    """

    track_selected = pyqtSignal(int, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_summary: Optional[VerificationSummary] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        # Main layout with scroll area for the entire tab
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
        """)

        # Content widget inside scroll area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(16)

        # === Top Section: Grade and Stats ===
        top_frame = QFrame()
        top_frame.setObjectName("topFrame")
        top_frame.setStyleSheet(f"""
            QFrame#topFrame {{
                background-color: {COLOR_CARD_BG.name()};
                border: 1px solid {COLOR_CARD_BORDER.name()};
                border-radius: 6px;
            }}
            QFrame#topFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(16, 16, 16, 16)
        top_layout.setSpacing(20)

        # Grade widget (fixed size)
        self._grade_widget = GradeWidget()
        top_layout.addWidget(self._grade_widget, 0, Qt.AlignmentFlag.AlignTop)

        # Stats cards in vertical pairs
        cards_layout = QVBoxLayout()
        cards_layout.setSpacing(12)

        # First row of cards
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        self._score_card = StatCard("Score", "0%", "Overall quality")
        self._good_card = StatCard("Good Sectors", "0", "of 2880", COLOR_GRADE_A)
        row1.addWidget(self._score_card)
        row1.addWidget(self._good_card)
        cards_layout.addLayout(row1)

        # Second row of cards
        row2 = QHBoxLayout()
        row2.setSpacing(12)
        self._bad_card = StatCard("Bad Sectors", "0", "with errors", COLOR_GRADE_F)
        self._weak_card = StatCard("Weak Sectors", "0", "marginal quality", COLOR_GRADE_C)
        row2.addWidget(self._bad_card)
        row2.addWidget(self._weak_card)
        cards_layout.addLayout(row2)

        top_layout.addLayout(cards_layout, 1)
        content_layout.addWidget(top_frame)

        # === Info Line ===
        self._info_label = QLabel("No verification data")
        self._info_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 11px;")
        self._info_label.setWordWrap(True)
        content_layout.addWidget(self._info_label)

        # === Grade Distribution Section ===
        dist_frame = QFrame()
        dist_frame.setObjectName("distFrame")
        dist_frame.setStyleSheet(f"""
            QFrame#distFrame {{
                background-color: {COLOR_CARD_BG.name()};
                border: 1px solid {COLOR_CARD_BORDER.name()};
                border-radius: 4px;
            }}
            QFrame#distFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        dist_frame_layout = QVBoxLayout(dist_frame)
        dist_frame_layout.setContentsMargins(12, 8, 12, 8)
        dist_frame_layout.setSpacing(8)

        dist_label = QLabel("Grade Distribution:")
        dist_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()};")
        dist_frame_layout.addWidget(dist_label)

        self._distribution_bar = GradeDistributionBar()
        self._distribution_bar.setMinimumWidth(100)
        self._distribution_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        dist_frame_layout.addWidget(self._distribution_bar)

        content_layout.addWidget(dist_frame)

        # === Track Results Table ===
        table_label = QLabel("Track Results:")
        table_label.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-weight: bold;")
        content_layout.addWidget(table_label)

        self._track_table = QTableWidget()
        self._track_table.setColumnCount(6)
        self._track_table.setHorizontalHeaderLabels([
            "Track", "Good", "Bad", "Weak", "Status", "Errors"
        ])

        # Table sizing
        self._track_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._track_table.setMinimumHeight(200)

        # Table styling
        self._track_table.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                border: 1px solid #3a3d41;
                gridline-color: #3a3d41;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 6px;
                border: 1px solid #3a3d41;
            }
        """)

        header = self._track_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self._track_table.setColumnWidth(0, 80)
        self._track_table.setColumnWidth(1, 60)
        self._track_table.setColumnWidth(2, 60)
        self._track_table.setColumnWidth(3, 60)
        self._track_table.setColumnWidth(4, 80)

        self._track_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._track_table.setAlternatingRowColors(True)
        self._track_table.cellDoubleClicked.connect(self._on_track_double_clicked)

        content_layout.addWidget(self._track_table, 1)

        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

    def _on_track_double_clicked(self, row: int, col: int) -> None:
        """Handle double-click on track row."""
        if self._current_summary and row < len(self._current_summary.track_results):
            track = self._current_summary.track_results[row]
            self.track_selected.emit(track.cylinder, track.head)

    def clear(self) -> None:
        """Clear all verification data."""
        self._current_summary = None
        self._grade_widget.set_grade("?")
        self._score_card.set_value("0%")
        self._good_card.set_value("0")
        self._good_card.set_subtitle("of 2880")
        self._bad_card.set_value("0")
        self._weak_card.set_value("0")
        self._info_label.setText("No verification data")
        self._distribution_bar.set_distribution({})
        self._track_table.setRowCount(0)

    def set_verification_result(self, summary: VerificationSummary) -> None:
        """
        Display verification results.

        Args:
            summary: VerificationSummary with all results
        """
        self._current_summary = summary

        # Update grade
        self._grade_widget.set_grade(summary.grade)

        # Update score
        score_color = COLOR_GRADE_A if summary.score >= 90 else (
            COLOR_GRADE_B if summary.score >= 80 else (
            COLOR_GRADE_C if summary.score >= 70 else (
            COLOR_GRADE_D if summary.score >= 60 else COLOR_GRADE_F)))
        self._score_card.set_value(f"{summary.score:.1f}%", score_color)

        # Update sector counts
        self._good_card.set_value(str(summary.good_sectors))
        self._good_card.set_subtitle(f"of {summary.total_sectors} ({summary.good_percentage:.1f}%)")

        self._bad_card.set_value(str(summary.bad_sectors))
        self._bad_card.set_subtitle(f"{summary.bad_percentage:.1f}% with errors")

        self._weak_card.set_value(str(summary.weak_sectors))

        # Update info line
        duration_sec = summary.duration_ms / 1000
        timestamp_str = summary.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        bad_tracks = summary.bad_track_count
        self._info_label.setText(
            f"Verified at {timestamp_str} | Duration: {duration_sec:.1f}s | "
            f"Type: {summary.disk_type} {summary.encoding} | "
            f"Bad tracks: {bad_tracks}"
        )

        # Update grade distribution (for single disk, just show one)
        dist = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0, 'S': 0}
        dist[summary.grade] = 1
        self._distribution_bar.set_distribution(dist)

        # Update track table
        self._update_track_table(summary.track_results)

    def _update_track_table(self, track_results: List[TrackVerificationResult]) -> None:
        """Update the track results table."""
        self._track_table.setRowCount(len(track_results))

        for row, track in enumerate(track_results):
            # Track identifier
            track_item = QTableWidgetItem(f"C{track.cylinder}:H{track.head}")
            track_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._track_table.setItem(row, 0, track_item)

            # Good sectors
            good_item = QTableWidgetItem(str(track.good_sectors))
            good_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            good_item.setForeground(COLOR_GRADE_A)
            self._track_table.setItem(row, 1, good_item)

            # Bad sectors
            bad_item = QTableWidgetItem(str(track.bad_sectors))
            bad_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if track.bad_sectors > 0:
                bad_item.setForeground(COLOR_GRADE_F)
            self._track_table.setItem(row, 2, bad_item)

            # Weak sectors
            weak_item = QTableWidgetItem(str(track.weak_sectors))
            weak_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if track.weak_sectors > 0:
                weak_item.setForeground(COLOR_GRADE_C)
            self._track_table.setItem(row, 3, weak_item)

            # Status
            if track.is_perfect:
                status_text = "OK"
                status_color = COLOR_GRADE_A
            elif track.has_errors:
                status_text = "ERROR"
                status_color = COLOR_GRADE_F
            else:
                status_text = "WARN"
                status_color = COLOR_GRADE_C

            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(status_color)
            self._track_table.setItem(row, 4, status_item)

            # Errors
            errors_text = "; ".join(track.errors) if track.errors else "-"
            errors_item = QTableWidgetItem(errors_text)
            self._track_table.setItem(row, 5, errors_item)

    def update_track_progress(
        self,
        cylinder: int,
        head: int,
        good: int,
        bad: int,
        weak: int,
        total: int
    ) -> None:
        """
        Update a single track's results during verification.

        Called as tracks are verified to provide live updates.

        Args:
            cylinder: Cylinder number
            head: Head number
            good: Good sector count
            bad: Bad sector count
            weak: Weak sector count
            total: Total sectors on track
        """
        # Find or create row for this track
        track_id = f"C{cylinder}:H{head}"

        # Check if row exists
        row = -1
        for i in range(self._track_table.rowCount()):
            item = self._track_table.item(i, 0)
            if item and item.text() == track_id:
                row = i
                break

        if row == -1:
            # Add new row
            row = self._track_table.rowCount()
            self._track_table.insertRow(row)

            track_item = QTableWidgetItem(track_id)
            track_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._track_table.setItem(row, 0, track_item)

        # Update values
        good_item = QTableWidgetItem(str(good))
        good_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        good_item.setForeground(COLOR_GRADE_A)
        self._track_table.setItem(row, 1, good_item)

        bad_item = QTableWidgetItem(str(bad))
        bad_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if bad > 0:
            bad_item.setForeground(COLOR_GRADE_F)
        self._track_table.setItem(row, 2, bad_item)

        weak_item = QTableWidgetItem(str(weak))
        weak_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if weak > 0:
            weak_item.setForeground(COLOR_GRADE_C)
        self._track_table.setItem(row, 3, weak_item)

        # Status
        if good == total and bad == 0:
            status_text = "OK"
            status_color = COLOR_GRADE_A
        elif bad > 0:
            status_text = "ERROR"
            status_color = COLOR_GRADE_F
        else:
            status_text = "WARN"
            status_color = COLOR_GRADE_C

        status_item = QTableWidgetItem(status_text)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        status_item.setForeground(status_color)
        self._track_table.setItem(row, 4, status_item)

        # Scroll to show new row
        self._track_table.scrollToItem(self._track_table.item(row, 0))


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'VerificationTab',
    'VerificationSummary',
    'TrackVerificationResult',
    'GradeWidget',
    'StatCard',
]
