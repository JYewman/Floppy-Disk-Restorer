"""
Analysis tab for Analytics Dashboard.

Displays comprehensive analysis results including:
- Overall grade and score with per-head breakdown
- Track grade distribution chart
- Signal quality metrics (SNR, jitter)
- Encoding and format detection
- Copy protection status
- Analysis recommendations

Part of Phase 7: Analytics Dashboard - Analysis Extension
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QGridLayout,
    QSizePolicy,
    QScrollArea,
    QGroupBox,
)
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPaintEvent,
)

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

COLOR_GRADE_A = QColor("#4ec9b0")  # Green
COLOR_GRADE_B = QColor("#9cdcfe")  # Light blue
COLOR_GRADE_C = QColor("#dcdcaa")  # Yellow
COLOR_GRADE_D = QColor("#ce9178")  # Orange
COLOR_GRADE_F = QColor("#f14c4c")  # Red

GRADE_COLORS = {
    'A': COLOR_GRADE_A,
    'B': COLOR_GRADE_B,
    'C': COLOR_GRADE_C,
    'D': COLOR_GRADE_D,
    'F': COLOR_GRADE_F,
    '?': COLOR_TEXT_DIM,
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class HeadQuality:
    """Quality metrics for a single head."""
    head: int
    track_count: int = 0
    grade_a_count: int = 0
    grade_b_count: int = 0
    grade_c_count: int = 0
    grade_d_count: int = 0
    grade_f_count: int = 0
    average_score: float = 0.0

    @property
    def grade(self) -> str:
        """Get letter grade for this head."""
        if self.average_score >= 90:
            return 'A'
        elif self.average_score >= 75:
            return 'B'
        elif self.average_score >= 60:
            return 'C'
        elif self.average_score >= 40:
            return 'D'
        else:
            return 'F'


@dataclass
class AnalysisSummary:
    """
    Summary of analysis results for display.

    Populated from DiskAnalysisResult.
    """
    overall_grade: str = "?"
    overall_score: float = 0.0
    tracks_analyzed: int = 0
    total_tracks: int = 160

    # Grade distribution
    grade_distribution: Dict[str, int] = field(default_factory=dict)

    # Per-head breakdown
    head_qualities: List[HeadQuality] = field(default_factory=list)

    # Signal quality
    average_snr_db: float = 0.0
    average_jitter_ns: float = 0.0
    weak_track_count: int = 0
    bad_track_count: int = 0

    # Encoding
    encoding_type: str = "UNKNOWN"
    disk_type: str = "UNKNOWN"

    # Forensics
    is_copy_protected: bool = False
    protection_types: List[str] = field(default_factory=list)
    protected_track_count: int = 0
    format_type: str = "UNKNOWN"
    format_is_standard: bool = True

    # Recommendations
    recommendations: List[str] = field(default_factory=list)

    # Timing
    analysis_duration: float = 0.0


# =============================================================================
# Grade Display Widget
# =============================================================================

class GradeDisplayWidget(QWidget):
    """
    Large grade display with score.

    Shows the letter grade prominently with numerical score below.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._grade: str = "?"
        self._score: float = 0.0
        self._label: str = "Overall"

        self.setMinimumSize(100, 100)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def set_grade(self, grade: str, score: float, label: str = "Overall") -> None:
        """Set the displayed grade and score."""
        self._grade = grade
        self._score = score
        self._label = label
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the grade display."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        cx = width / 2
        cy = height / 2

        # Background circle
        radius = min(width, height) / 2 - 5
        painter.setPen(QPen(COLOR_CARD_BORDER, 2))
        painter.setBrush(QBrush(COLOR_CARD_BG))
        painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        # Grade color
        grade_color = GRADE_COLORS.get(self._grade, COLOR_TEXT_DIM)

        # Grade letter
        font_grade = QFont("Segoe UI", int(radius * 0.6), QFont.Weight.Bold)
        painter.setFont(font_grade)
        painter.setPen(QPen(grade_color))

        fm = QFontMetrics(font_grade)
        grade_width = fm.horizontalAdvance(self._grade)
        painter.drawText(int(cx - grade_width / 2), int(cy + fm.height() / 4), self._grade)

        # Score below
        font_score = QFont("Segoe UI", int(radius * 0.18))
        painter.setFont(font_score)
        painter.setPen(QPen(COLOR_TEXT_DIM))

        score_text = f"{self._score:.1f}%"
        fm_score = QFontMetrics(font_score)
        score_width = fm_score.horizontalAdvance(score_text)
        painter.drawText(int(cx - score_width / 2), int(cy + radius * 0.5), score_text)

        # Label above
        font_label = QFont("Segoe UI", 9)
        painter.setFont(font_label)

        fm_label = QFontMetrics(font_label)
        label_width = fm_label.horizontalAdvance(self._label)
        painter.drawText(int(cx - label_width / 2), int(cy - radius - 5), self._label)


# =============================================================================
# Grade Distribution Chart
# =============================================================================

class GradeDistributionWidget(QWidget):
    """
    Bar chart showing track grade distribution.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._distribution: Dict[str, int] = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}

        self.setMinimumSize(200, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_distribution(self, distribution: Dict[str, int]) -> None:
        """Set the grade distribution."""
        self._distribution = distribution
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the distribution chart."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), COLOR_CARD_BG)

        width = self.width()
        height = self.height()

        margin_left = 30
        margin_right = 10
        margin_top = 25
        margin_bottom = 25

        plot_width = width - margin_left - margin_right
        plot_height = height - margin_top - margin_bottom

        # Title
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QPen(COLOR_TEXT))
        painter.drawText(margin_left, 15, "Track Grade Distribution")

        # Get max value for scale
        grades = ['A', 'B', 'C', 'D', 'F']
        max_val = max(self._distribution.get(g, 0) for g in grades)
        max_val = max(10, max_val)  # Minimum scale

        total = sum(self._distribution.get(g, 0) for g in grades)

        # Draw bars
        bar_width = plot_width / len(grades) - 10

        for i, grade in enumerate(grades):
            count = self._distribution.get(grade, 0)
            bar_height = (count / max_val) * plot_height if max_val > 0 else 0

            x = margin_left + i * (plot_width / len(grades)) + 5
            y = margin_top + plot_height - bar_height

            # Bar
            color = GRADE_COLORS.get(grade, COLOR_TEXT_DIM)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRect(int(x), int(y), int(bar_width), int(bar_height))

            # Grade label
            painter.setPen(QPen(COLOR_TEXT))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            fm = QFontMetrics(painter.font())
            label_width = fm.horizontalAdvance(grade)
            painter.drawText(int(x + bar_width / 2 - label_width / 2),
                           int(margin_top + plot_height + 15), grade)

            # Count label on top of bar
            if count > 0:
                painter.setFont(QFont("Segoe UI", 8))
                count_text = str(count)
                fm2 = QFontMetrics(painter.font())
                count_width = fm2.horizontalAdvance(count_text)
                painter.drawText(int(x + bar_width / 2 - count_width / 2),
                               int(y - 3), count_text)

        # Y axis labels
        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QPen(COLOR_TEXT_DIM))
        for i in range(5):
            value = int(max_val * (4 - i) / 4)
            y = margin_top + i * plot_height / 4
            painter.drawText(5, int(y + 4), str(value))


# =============================================================================
# Head Quality Card
# =============================================================================

class HeadQualityCard(QFrame):
    """
    Card showing quality breakdown for a single head.
    """

    def __init__(self, head: int, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._head = head
        obj_name = f"headQualityCard{head}"
        self.setObjectName(obj_name)

        self.setStyleSheet(f"""
            QFrame#{obj_name} {{
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 6px;
            }}
            QFrame#{obj_name} QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        self.setMinimumSize(150, 80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Header
        header = QLabel(f"Head {head} (Side {head + 1})")
        header.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-weight: bold;")
        layout.addWidget(header)

        # Grade display
        self._grade_label = QLabel("?")
        self._grade_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self._grade_label)

        # Score
        self._score_label = QLabel("0.0%")
        self._score_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()};")
        layout.addWidget(self._score_label)

    def set_quality(self, quality: HeadQuality) -> None:
        """Set the head quality data."""
        grade = quality.grade
        color = GRADE_COLORS.get(grade, COLOR_TEXT_DIM)

        self._grade_label.setText(grade)
        self._grade_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color.name()};")
        self._score_label.setText(f"{quality.average_score:.1f}%")


# =============================================================================
# Signal Quality Card
# =============================================================================

class SignalQualityCard(QFrame):
    """
    Card showing signal quality metrics.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setObjectName("signalQualityCard")
        self.setStyleSheet("""
            QFrame#signalQualityCard {
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 6px;
            }
            QFrame#signalQualityCard QLabel {
                border: none;
                background: transparent;
            }
        """)

        self.setMinimumSize(200, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Header
        header = QLabel("Signal Quality")
        header.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-weight: bold;")
        layout.addWidget(header)

        # Grid for metrics
        grid = QGridLayout()
        grid.setSpacing(8)

        # SNR
        grid.addWidget(QLabel("SNR:"), 0, 0)
        self._snr_label = QLabel("-- dB")
        self._snr_label.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        grid.addWidget(self._snr_label, 0, 1)

        # Jitter
        grid.addWidget(QLabel("Jitter:"), 1, 0)
        self._jitter_label = QLabel("-- ns")
        self._jitter_label.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        grid.addWidget(self._jitter_label, 1, 1)

        # Weak tracks
        grid.addWidget(QLabel("Weak Tracks:"), 2, 0)
        self._weak_label = QLabel("0")
        self._weak_label.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        grid.addWidget(self._weak_label, 2, 1)

        layout.addLayout(grid)

    def set_metrics(self, snr_db: float, jitter_ns: float, weak_tracks: int) -> None:
        """Set the signal quality metrics."""
        self._snr_label.setText(f"{snr_db:.1f} dB")
        self._jitter_label.setText(f"{jitter_ns:.1f} ns")
        self._weak_label.setText(str(weak_tracks))

        # Color code based on quality
        if snr_db >= 20:
            self._snr_label.setStyleSheet(f"color: {COLOR_GRADE_A.name()};")
        elif snr_db >= 15:
            self._snr_label.setStyleSheet(f"color: {COLOR_GRADE_B.name()};")
        elif snr_db >= 10:
            self._snr_label.setStyleSheet(f"color: {COLOR_GRADE_C.name()};")
        else:
            self._snr_label.setStyleSheet(f"color: {COLOR_GRADE_F.name()};")

        if jitter_ns < 50:
            self._jitter_label.setStyleSheet(f"color: {COLOR_GRADE_A.name()};")
        elif jitter_ns < 100:
            self._jitter_label.setStyleSheet(f"color: {COLOR_GRADE_B.name()};")
        elif jitter_ns < 200:
            self._jitter_label.setStyleSheet(f"color: {COLOR_GRADE_C.name()};")
        else:
            self._jitter_label.setStyleSheet(f"color: {COLOR_GRADE_F.name()};")


# =============================================================================
# Encoding Info Card
# =============================================================================

class EncodingInfoCard(QFrame):
    """
    Card showing encoding and format detection.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setObjectName("encodingInfoCard")
        self.setStyleSheet("""
            QFrame#encodingInfoCard {
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 6px;
            }
            QFrame#encodingInfoCard QLabel {
                border: none;
                background: transparent;
            }
        """)

        self.setMinimumSize(200, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Header
        header = QLabel("Encoding Detection")
        header.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-weight: bold;")
        layout.addWidget(header)

        # Grid for info
        grid = QGridLayout()
        grid.setSpacing(8)

        # Encoding
        grid.addWidget(QLabel("Encoding:"), 0, 0)
        self._encoding_label = QLabel("UNKNOWN")
        self._encoding_label.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        grid.addWidget(self._encoding_label, 0, 1)

        # Disk type
        grid.addWidget(QLabel("Disk Type:"), 1, 0)
        self._type_label = QLabel("UNKNOWN")
        self._type_label.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        grid.addWidget(self._type_label, 1, 1)

        # Format
        grid.addWidget(QLabel("Format:"), 2, 0)
        self._format_label = QLabel("UNKNOWN")
        self._format_label.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        grid.addWidget(self._format_label, 2, 1)

        layout.addLayout(grid)

    def set_info(self, encoding: str, disk_type: str, format_type: str, is_standard: bool) -> None:
        """Set the encoding info."""
        self._encoding_label.setText(encoding)
        self._type_label.setText(disk_type)

        format_text = format_type
        if not is_standard:
            format_text += " (non-standard)"
            self._format_label.setStyleSheet(f"color: {COLOR_GRADE_C.name()};")
        else:
            self._format_label.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        self._format_label.setText(format_text)


# =============================================================================
# Copy Protection Card
# =============================================================================

class CopyProtectionCard(QFrame):
    """
    Card showing copy protection detection status.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setObjectName("copyProtectionCard")
        self.setStyleSheet("""
            QFrame#copyProtectionCard {
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 6px;
            }
            QFrame#copyProtectionCard QLabel {
                border: none;
                background: transparent;
            }
        """)

        self.setMinimumSize(200, 80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Header
        header = QLabel("Copy Protection")
        header.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-weight: bold;")
        layout.addWidget(header)

        # Status
        self._status_label = QLabel("Not detected")
        self._status_label.setStyleSheet(f"color: {COLOR_GRADE_A.name()};")
        layout.addWidget(self._status_label)

        # Details
        self._details_label = QLabel("")
        self._details_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 10px;")
        self._details_label.setWordWrap(True)
        layout.addWidget(self._details_label)

    def set_protection(self, is_protected: bool, track_count: int, types: List[str]) -> None:
        """Set the copy protection info."""
        if is_protected:
            self._status_label.setText(f"DETECTED on {track_count} tracks")
            self._status_label.setStyleSheet(f"color: {COLOR_GRADE_C.name()}; font-weight: bold;")

            if types:
                self._details_label.setText(f"Types: {', '.join(types[:3])}")
            else:
                self._details_label.setText("")
        else:
            self._status_label.setText("Not detected")
            self._status_label.setStyleSheet(f"color: {COLOR_GRADE_A.name()};")
            self._details_label.setText("")


# =============================================================================
# Recommendations Card
# =============================================================================

class AnalysisRecommendationsCard(QFrame):
    """
    Card showing analysis recommendations.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setObjectName("analysisRecommendationsCard")
        self.setStyleSheet("""
            QFrame#analysisRecommendationsCard {
                background-color: #252526;
                border: 1px solid #3a3d41;
                border-radius: 6px;
            }
            QFrame#analysisRecommendationsCard QLabel {
                border: none;
                background: transparent;
            }
        """)

        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Header
        header = QLabel("Recommendations")
        header.setStyleSheet(f"color: {COLOR_TEXT.name()}; font-weight: bold;")
        layout.addWidget(header)

        # Recommendations list
        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(4)
        layout.addLayout(self._list_layout)
        layout.addStretch()

    def set_recommendations(self, recommendations: List[str]) -> None:
        """Set the recommendations list."""
        # Clear existing
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not recommendations:
            label = QLabel("No recommendations")
            label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()};")
            self._list_layout.addWidget(label)
            return

        for rec in recommendations:
            # Determine severity by keywords
            if any(word in rec.lower() for word in ['excellent', 'good condition']):
                icon = "\u2714"  # Checkmark
                color = COLOR_GRADE_A
            elif any(word in rec.lower() for word in ['warning', 'degraded', 'detected']):
                icon = "\u26A0"  # Warning
                color = COLOR_GRADE_C
            elif any(word in rec.lower() for word in ['critical', 'severe', 'poor']):
                icon = "\u2718"  # X mark
                color = COLOR_GRADE_F
            else:
                icon = "\u2139"  # Info
                color = COLOR_GRADE_B

            label = QLabel(f"{icon}  {rec}")
            label.setStyleSheet(f"color: {color.name()};")
            label.setWordWrap(True)
            self._list_layout.addWidget(label)


# =============================================================================
# Analysis Tab
# =============================================================================

class AnalysisTab(QWidget):
    """
    Analysis tab showing comprehensive disk analysis results.

    Displays:
    - Overall grade and per-head breakdown
    - Track grade distribution chart
    - Signal quality metrics
    - Encoding and format detection
    - Copy protection status
    - Analysis recommendations

    Signals:
        None (read-only display)
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._summary: Optional[AnalysisSummary] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        # Use scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1e1e1e;
            }
        """)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top row: Grades
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        # Overall grade
        self._overall_grade = GradeDisplayWidget()
        self._overall_grade.setMinimumSize(120, 130)
        top_row.addWidget(self._overall_grade)

        # Per-head grades
        head_layout = QVBoxLayout()
        head_layout.setSpacing(4)

        self._head0_card = HeadQualityCard(0)
        head_layout.addWidget(self._head0_card)

        self._head1_card = HeadQualityCard(1)
        head_layout.addWidget(self._head1_card)

        top_row.addLayout(head_layout)

        # Grade distribution chart
        self._distribution_chart = GradeDistributionWidget()
        top_row.addWidget(self._distribution_chart, 1)

        layout.addLayout(top_row)

        # Middle row: Details
        mid_row = QHBoxLayout()
        mid_row.setSpacing(8)

        # Signal quality
        self._signal_card = SignalQualityCard()
        mid_row.addWidget(self._signal_card)

        # Encoding info
        self._encoding_card = EncodingInfoCard()
        mid_row.addWidget(self._encoding_card)

        # Copy protection
        self._protection_card = CopyProtectionCard()
        mid_row.addWidget(self._protection_card)

        layout.addLayout(mid_row)

        # Bottom: Recommendations
        self._recommendations_card = AnalysisRecommendationsCard()
        layout.addWidget(self._recommendations_card, 1)

        # Info label (empty state)
        self._info_label = QLabel("Run an analysis to see results")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet(f"color: {COLOR_TEXT_DIM.name()}; font-size: 14px;")
        layout.addWidget(self._info_label)

        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        # Initially hide content, show info
        self._set_content_visible(False)

    def _set_content_visible(self, visible: bool) -> None:
        """Show or hide the content."""
        self._overall_grade.setVisible(visible)
        self._head0_card.setVisible(visible)
        self._head1_card.setVisible(visible)
        self._distribution_chart.setVisible(visible)
        self._signal_card.setVisible(visible)
        self._encoding_card.setVisible(visible)
        self._protection_card.setVisible(visible)
        self._recommendations_card.setVisible(visible)
        self._info_label.setVisible(not visible)

    def update_analysis(self, summary: AnalysisSummary) -> None:
        """
        Update the tab with analysis results.

        Args:
            summary: AnalysisSummary with analysis data
        """
        self._summary = summary
        self._set_content_visible(True)

        # Overall grade
        self._overall_grade.set_grade(
            summary.overall_grade,
            summary.overall_score,
            "Overall"
        )

        # Per-head breakdown
        if len(summary.head_qualities) >= 2:
            self._head0_card.set_quality(summary.head_qualities[0])
            self._head1_card.set_quality(summary.head_qualities[1])

        # Distribution
        self._distribution_chart.set_distribution(summary.grade_distribution)

        # Signal quality
        self._signal_card.set_metrics(
            summary.average_snr_db,
            summary.average_jitter_ns,
            summary.weak_track_count
        )

        # Encoding
        self._encoding_card.set_info(
            summary.encoding_type,
            summary.disk_type,
            summary.format_type,
            summary.format_is_standard
        )

        # Copy protection
        self._protection_card.set_protection(
            summary.is_copy_protected,
            summary.protected_track_count,
            summary.protection_types
        )

        # Recommendations
        self._recommendations_card.set_recommendations(summary.recommendations)

        logger.debug("Analysis tab updated: grade=%s, score=%.1f",
                    summary.overall_grade, summary.overall_score)

    def update_from_result(self, result: Any) -> None:
        """
        Update from a DiskAnalysisResult object.

        This is a convenience method that converts DiskAnalysisResult
        to AnalysisSummary and updates the display.

        Args:
            result: DiskAnalysisResult from analyze_worker
        """
        # Extract per-head breakdown
        head_qualities = []
        for head in range(2):
            head_tracks = [tr for tr in result.track_results if tr.head == head]

            quality = HeadQuality(head=head, track_count=len(head_tracks))

            if head_tracks:
                # Count grades
                for tr in head_tracks:
                    grade = tr.grade
                    if grade == 'A':
                        quality.grade_a_count += 1
                    elif grade == 'B':
                        quality.grade_b_count += 1
                    elif grade == 'C':
                        quality.grade_c_count += 1
                    elif grade == 'D':
                        quality.grade_d_count += 1
                    elif grade == 'F':
                        quality.grade_f_count += 1

                # Calculate average score
                scores = [tr.quality.score for tr in head_tracks
                         if tr.quality is not None]
                if scores:
                    quality.average_score = sum(scores) / len(scores)

            head_qualities.append(quality)

        summary = AnalysisSummary(
            overall_grade=result.overall_grade,
            overall_score=result.overall_quality_score,
            tracks_analyzed=result.tracks_analyzed,
            total_tracks=result.total_tracks,
            grade_distribution=result.get_grade_distribution(),
            head_qualities=head_qualities,
            average_snr_db=result.average_snr_db,
            average_jitter_ns=result.average_jitter_ns,
            weak_track_count=result.weak_track_count,
            bad_track_count=result.bad_track_count,
            encoding_type=result.encoding_type,
            disk_type=result.disk_type,
            is_copy_protected=result.is_copy_protected,
            protection_types=result.protection_types,
            protected_track_count=result.protected_track_count,
            format_type=result.format_type,
            format_is_standard=result.format_is_standard,
            recommendations=result.recommendations,
            analysis_duration=result.analysis_duration,
        )

        self.update_analysis(summary)

    def clear_analysis(self) -> None:
        """Clear all analysis data."""
        self._summary = None
        self._set_content_visible(False)

    def get_summary(self) -> Optional[AnalysisSummary]:
        """Get the current analysis summary."""
        return self._summary


__all__ = [
    'AnalysisTab',
    'AnalysisSummary',
    'HeadQuality',
    'GradeDisplayWidget',
    'GradeDistributionWidget',
    'HeadQualityCard',
    'SignalQualityCard',
    'EncodingInfoCard',
    'CopyProtectionCard',
    'AnalysisRecommendationsCard',
]
