"""
Flux histogram visualization widget for Floppy Workbench.

Displays pulse width distribution as a histogram with:
- Overlay of expected MFM peak positions (2T, 3T, 4T)
- Gaussian fit curves for detected peaks
- Quality metrics display
- Image export functionality
- Peak analysis with deviation from expected positions

Part of Phase 7-8: Analytics Dashboard & Flux Visualization
"""

import math
import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QPainterPath,
    QFont,
    QFontMetrics,
    QPaintEvent,
    QResizeEvent,
    QPixmap,
    QImage,
)

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Display colors
COLOR_BACKGROUND = QColor("#1e1e1e")
COLOR_GRID = QColor("#3a3d41")
COLOR_AXIS = QColor("#808080")
COLOR_BARS = QColor("#4ec9b0")
# Semi-transparent bars (78, 201, 176, 180)
_bars_fill = QColor("#4ec9b0")
_bars_fill.setAlpha(180)
COLOR_BARS_FILL = _bars_fill
COLOR_PEAK_2T = QColor("#569cd6")  # Blue
COLOR_PEAK_3T = QColor("#4ec9b0")  # Green
COLOR_PEAK_4T = QColor("#c586c0")  # Purple
COLOR_GAUSSIAN = QColor("#dcdcaa")  # Yellow
COLOR_TEXT = QColor("#cccccc")

# MFM timing constants for HD (300 RPM, 500 kbps)
MFM_HD_2T_US = 4.0   # 2 bit cells
MFM_HD_3T_US = 6.0   # 3 bit cells
MFM_HD_4T_US = 8.0   # 4 bit cells

# Display settings
MARGIN_LEFT = 60
MARGIN_RIGHT = 20
MARGIN_TOP = 30
MARGIN_BOTTOM = 50
MIN_BIN_WIDTH_PX = 2


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class GaussianFit:
    """
    Gaussian curve fit parameters.

    Attributes:
        amplitude: Peak height
        center: Peak center position (microseconds)
        sigma: Standard deviation
        label: Peak label (e.g., "2T")
        color: Display color
    """
    amplitude: float
    center: float
    sigma: float
    label: str = ""
    color: QColor = field(default_factory=lambda: QColor("#dcdcaa"))

    @property
    def fwhm(self) -> float:
        """Full width at half maximum."""
        return 2.355 * self.sigma

    def evaluate(self, x: float) -> float:
        """Evaluate Gaussian at position x."""
        if self.sigma == 0:
            return 0.0
        exponent = -((x - self.center) ** 2) / (2 * self.sigma ** 2)
        return self.amplitude * math.exp(exponent)


@dataclass
class DetectedPeak:
    """
    Detected peak with analysis results.

    Attributes:
        center_us: Peak center position in microseconds
        sigma_ns: Standard deviation in nanoseconds
        amplitude: Peak height (count)
        expected_position: Theoretical expected position
        deviation_ns: Deviation from expected in nanoseconds
        label: Peak label (e.g., "2T")
    """
    center_us: float
    sigma_ns: float
    amplitude: int
    expected_position: float = 0.0
    deviation_ns: float = 0.0
    label: str = ""

    @classmethod
    def from_gaussian_fit(cls, fit: GaussianFit, expected_positions: Dict[str, float] = None) -> 'DetectedPeak':
        """Create DetectedPeak from GaussianFit."""
        expected_pos = 0.0
        deviation = 0.0

        if expected_positions and fit.label in expected_positions:
            expected_pos = expected_positions[fit.label]
            deviation = (fit.center - expected_pos) * 1000  # Convert to nanoseconds

        return cls(
            center_us=fit.center,
            sigma_ns=fit.sigma * 1000,  # Convert to nanoseconds
            amplitude=int(fit.amplitude),
            expected_position=expected_pos,
            deviation_ns=deviation,
            label=fit.label,
        )


@dataclass
class PeakAnalysis:
    """
    Complete peak analysis results.

    Attributes:
        peaks: List of detected peaks
        separation_ratios: Ratios between adjacent peak separations
        overall_quality: Quality score (0.0-1.0)
        quality_label: Human-readable quality label
    """
    peaks: List[DetectedPeak]
    separation_ratios: List[float]
    overall_quality: float
    quality_label: str = "Unknown"

    @property
    def peak_count(self) -> int:
        """Number of detected peaks."""
        return len(self.peaks)

    @property
    def average_jitter_ns(self) -> float:
        """Average jitter (sigma) in nanoseconds."""
        if not self.peaks:
            return 0.0
        return statistics.mean(p.sigma_ns for p in self.peaks)

    def get_peak_by_label(self, label: str) -> Optional[DetectedPeak]:
        """Get peak by label (e.g., '2T')."""
        for peak in self.peaks:
            if peak.label == label:
                return peak
        return None


@dataclass
class HistogramData:
    """
    Processed histogram data for display.

    Attributes:
        bin_centers: Center position of each bin (microseconds)
        bin_counts: Count in each bin
        bin_width: Width of each bin (microseconds)
        total_count: Total number of samples
        peaks: Detected peaks with Gaussian fits
    """
    bin_centers: List[float]
    bin_counts: List[int]
    bin_width: float
    total_count: int
    peaks: List[GaussianFit]

    @property
    def max_count(self) -> int:
        """Maximum bin count."""
        return max(self.bin_counts) if self.bin_counts else 0


# =============================================================================
# Main Histogram Widget
# =============================================================================

class FluxHistogramWidget(QWidget):
    """
    Flux pulse width histogram visualization.

    Displays a histogram of pulse widths with:
    - Bar chart of pulse width distribution
    - Vertical reference lines for expected MFM peaks
    - Gaussian fit curves overlaid on peaks
    - Quality metrics display

    Signals:
        peak_clicked(float): Emitted when user clicks on a peak (center in µs)
    """

    peak_clicked = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Widget settings
        self.setMinimumSize(300, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

        # Data
        self._histogram: Optional[HistogramData] = None
        self._show_mfm_reference = True
        self._show_gaussian_fits = True
        self._hover_bin: int = -1

        # Fonts
        self._font_label = QFont("Consolas", 9)
        self._font_title = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self._font_small = QFont("Consolas", 8)

        # Quality metrics
        self._quality_score: float = 0.0
        self._peak_separation: float = 0.0
        self._avg_jitter: float = 0.0

    # =========================================================================
    # Public API
    # =========================================================================

    def set_histogram_data(self, timings_us: List[float], bins: int = 100,
                          min_us: float = 2.0, max_us: float = 12.0) -> None:
        """
        Set histogram data from raw timing values.

        Args:
            timings_us: List of pulse widths in microseconds
            bins: Number of histogram bins
            min_us: Minimum value for histogram range
            max_us: Maximum value for histogram range
        """
        if not timings_us:
            self._histogram = None
            self._quality_score = 0.0
            self.update()
            return

        # Filter to range
        filtered = [t for t in timings_us if min_us <= t <= max_us]

        if not filtered:
            self._histogram = None
            self.update()
            return

        # Create bins
        bin_width = (max_us - min_us) / bins
        bin_centers = [min_us + (i + 0.5) * bin_width for i in range(bins)]
        bin_counts = [0] * bins

        for t in filtered:
            idx = int((t - min_us) / bin_width)
            if 0 <= idx < bins:
                bin_counts[idx] += 1

        # Detect peaks and fit Gaussians
        peaks = self._detect_and_fit_peaks(bin_centers, bin_counts, bin_width)

        self._histogram = HistogramData(
            bin_centers=bin_centers,
            bin_counts=bin_counts,
            bin_width=bin_width,
            total_count=len(filtered),
            peaks=peaks,
        )

        # Calculate quality metrics
        self._calculate_quality_metrics()

        self.update()

    def clear_histogram(self) -> None:
        """Clear histogram data."""
        self._histogram = None
        self._quality_score = 0.0
        self._peak_separation = 0.0
        self._avg_jitter = 0.0
        self.update()

    def set_show_mfm_reference(self, show: bool) -> None:
        """Enable/disable MFM reference lines."""
        self._show_mfm_reference = show
        self.update()

    def set_show_gaussian_fits(self, show: bool) -> None:
        """Enable/disable Gaussian fit curves."""
        self._show_gaussian_fits = show
        self.update()

    def get_quality_score(self) -> float:
        """Get overall quality score (0.0-1.0)."""
        return self._quality_score

    def get_peak_separation(self) -> float:
        """Get average peak separation in microseconds."""
        return self._peak_separation

    def get_average_jitter(self) -> float:
        """Get average peak jitter (sigma) in microseconds."""
        return self._avg_jitter

    def get_peak_analysis(self) -> Optional[PeakAnalysis]:
        """
        Get comprehensive peak analysis results.

        Returns:
            PeakAnalysis object or None if no data
        """
        if not self._histogram or not self._histogram.peaks:
            return None

        # Expected positions for MFM HD
        expected_positions = {
            "2T": MFM_HD_2T_US,
            "3T": MFM_HD_3T_US,
            "4T": MFM_HD_4T_US,
        }

        # Convert Gaussian fits to DetectedPeak objects
        detected_peaks = [
            DetectedPeak.from_gaussian_fit(fit, expected_positions)
            for fit in self._histogram.peaks
        ]

        # Calculate separation ratios
        separation_ratios = []
        if len(detected_peaks) >= 2:
            separations = []
            for i in range(1, len(detected_peaks)):
                sep = detected_peaks[i].center_us - detected_peaks[i-1].center_us
                separations.append(sep)

            # Expected ratio for MFM is 1.5 (6/4 = 1.5, 8/6 = 1.33)
            for i in range(1, len(separations)):
                if separations[i-1] > 0:
                    separation_ratios.append(separations[i] / separations[i-1])

        # Determine quality label
        if self._quality_score >= 0.8:
            quality_label = "Excellent"
        elif self._quality_score >= 0.6:
            quality_label = "Good"
        elif self._quality_score >= 0.4:
            quality_label = "Marginal"
        else:
            quality_label = "Poor"

        return PeakAnalysis(
            peaks=detected_peaks,
            separation_ratios=separation_ratios,
            overall_quality=self._quality_score,
            quality_label=quality_label,
        )

    def set_expected_peaks(self, peaks: List[float]) -> None:
        """
        Set expected peak positions for reference lines.

        Args:
            peaks: List of expected peak positions in microseconds
        """
        # Store custom expected peaks (currently not implemented, uses MFM defaults)
        pass

    def update_histogram(self) -> None:
        """Force recalculation and redraw of histogram."""
        self.update()

    def export_image(self, filepath: str, width: int = 800, height: int = 400) -> bool:
        """
        Export histogram as image file.

        Args:
            filepath: Target file path (supports PNG, JPG, BMP)
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            True if export successful, False otherwise
        """
        # Create pixmap at specified size
        pixmap = QPixmap(width, height)
        pixmap.fill(COLOR_BACKGROUND)

        # Create painter and render
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Temporarily store original size
        original_size = self.size()

        # Manually render components at export size
        self._render_to_painter(painter, width, height)

        painter.end()

        # Save to file
        try:
            return pixmap.save(filepath)
        except Exception as e:
            logger.error("Failed to export histogram image: %s", e)
            return False

    def _render_to_painter(self, painter: QPainter, width: int, height: int) -> None:
        """Render histogram to a painter at specified dimensions."""
        if not self._histogram:
            # Draw empty state
            painter.setFont(self._font_title)
            painter.setPen(QPen(COLOR_AXIS))
            painter.drawText(width // 2 - 60, height // 2, "No flux data loaded")
            return

        # Calculate plot area
        plot_left = MARGIN_LEFT
        plot_right = width - MARGIN_RIGHT
        plot_top = MARGIN_TOP
        plot_bottom = height - MARGIN_BOTTOM
        plot_width = plot_right - plot_left
        plot_height = plot_bottom - plot_top

        # Helper functions for this render
        def us_to_x(us: float) -> float:
            min_us = self._histogram.bin_centers[0] - self._histogram.bin_width / 2
            max_us = self._histogram.bin_centers[-1] + self._histogram.bin_width / 2
            range_us = max_us - min_us
            if range_us == 0:
                return plot_left
            return plot_left + (us - min_us) / range_us * plot_width

        def count_to_y(count: int) -> float:
            if self._histogram.max_count == 0:
                return plot_bottom
            return plot_bottom - (count / self._histogram.max_count) * plot_height

        # Draw grid
        pen = QPen(COLOR_GRID, 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)
        for i in range(1, 5):
            y = plot_top + i * plot_height / 5
            painter.drawLine(int(plot_left), int(y), int(plot_right), int(y))
        for us in [2, 4, 6, 8, 10]:
            x = us_to_x(us)
            if plot_left <= x <= plot_right:
                painter.drawLine(int(x), int(plot_top), int(x), int(plot_bottom))

        # Draw MFM reference lines
        if self._show_mfm_reference:
            painter.setFont(self._font_small)
            for us, label, color in [(MFM_HD_2T_US, "2T", COLOR_PEAK_2T),
                                     (MFM_HD_3T_US, "3T", COLOR_PEAK_3T),
                                     (MFM_HD_4T_US, "4T", COLOR_PEAK_4T)]:
                x = us_to_x(us)
                pen = QPen(color, 1, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawLine(int(x), int(plot_top), int(x), int(plot_bottom))
                painter.setPen(QPen(color))
                painter.drawText(int(x - 8), int(plot_top - 5), label)

        # Draw histogram bars
        n_bins = len(self._histogram.bin_centers)
        bar_width = max(MIN_BIN_WIDTH_PX, plot_width / n_bins - 1)
        pen = QPen(COLOR_BARS, 1)
        brush = QBrush(COLOR_BARS_FILL)
        painter.setPen(pen)
        painter.setBrush(brush)

        for center, count in zip(self._histogram.bin_centers, self._histogram.bin_counts):
            if count == 0:
                continue
            x = us_to_x(center) - bar_width / 2
            y = count_to_y(count)
            bar_height = plot_bottom - y
            painter.drawRect(QRectF(x, y, bar_width, bar_height))

        # Draw Gaussian fits
        if self._show_gaussian_fits:
            for peak in self._histogram.peaks:
                pen = QPen(peak.color, 2)
                painter.setPen(pen)
                path = QPainterPath()
                first_point = True
                min_us = self._histogram.bin_centers[0] - self._histogram.bin_width / 2
                max_us = self._histogram.bin_centers[-1] + self._histogram.bin_width / 2
                start_us = max(min_us, peak.center - 3 * peak.sigma)
                end_us = min(max_us, peak.center + 3 * peak.sigma)
                steps = 50
                step_size = (end_us - start_us) / steps
                for i in range(steps + 1):
                    us = start_us + i * step_size
                    value = peak.evaluate(us)
                    x = us_to_x(us)
                    y = count_to_y(int(value))
                    if first_point:
                        path.moveTo(x, y)
                        first_point = False
                    else:
                        path.lineTo(x, y)
                painter.drawPath(path)

        # Draw axes
        pen = QPen(COLOR_AXIS, 1)
        painter.setPen(pen)
        painter.setFont(self._font_label)
        painter.drawLine(int(plot_left), int(plot_bottom), int(plot_right), int(plot_bottom))
        painter.drawLine(int(plot_left), int(plot_top), int(plot_left), int(plot_bottom))

        # X axis labels
        for us in [2, 4, 6, 8, 10]:
            x = us_to_x(us)
            if plot_left <= x <= plot_right:
                painter.drawText(int(x - 10), int(plot_bottom + 15), f"{us}")

        painter.drawText(int((plot_left + plot_right) / 2 - 40), int(height - 5), "Pulse Width (µs)")

        # Y axis labels
        if self._histogram.max_count > 0:
            for i in range(5):
                count = int(self._histogram.max_count * (4 - i) / 4)
                y = plot_top + i * plot_height / 4
                if count >= 1000:
                    label = f"{count // 1000}k"
                else:
                    label = str(count)
                painter.drawText(int(plot_left - 35), int(y + 5), label)

        # Quality metrics
        painter.setFont(self._font_small)
        painter.setPen(QPen(COLOR_TEXT))
        x = width - MARGIN_RIGHT - 100
        y = MARGIN_TOP + 15
        score_color = QColor("#4ec9b0") if self._quality_score >= 0.7 else \
                     QColor("#dcdcaa") if self._quality_score >= 0.4 else \
                     QColor("#f14c4c")
        painter.setPen(QPen(score_color))
        painter.drawText(int(x), int(y), f"Quality: {self._quality_score:.0%}")
        painter.setPen(QPen(COLOR_TEXT))
        painter.drawText(int(x), int(y + 15), f"Peaks: {len(self._histogram.peaks)}")
        painter.drawText(int(x), int(y + 30), f"Jitter: {self._avg_jitter:.2f}µs")

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _detect_and_fit_peaks(
        self,
        centers: List[float],
        counts: List[int],
        bin_width: float
    ) -> List[GaussianFit]:
        """Detect peaks and fit Gaussians."""
        if not counts:
            return []

        max_count = max(counts)
        threshold = max_count * 0.05  # 5% threshold

        peaks = []
        n = len(counts)

        # Find local maxima
        for i in range(1, n - 1):
            if counts[i] > threshold:
                # Check if local maximum
                if counts[i] > counts[i - 1] and counts[i] > counts[i + 1]:
                    # Additional check: higher than neighbors by margin
                    left_min = min(counts[max(0, i - 3):i])
                    right_min = min(counts[i + 1:min(n, i + 4)])

                    if counts[i] > left_min * 1.2 and counts[i] > right_min * 1.2:
                        # Fit Gaussian to this peak
                        fit = self._fit_gaussian_at_peak(centers, counts, i, bin_width)
                        if fit:
                            peaks.append(fit)

        # Merge close peaks and assign labels
        peaks = self._merge_close_peaks(peaks)
        peaks = self._label_peaks(peaks)

        return peaks

    def _fit_gaussian_at_peak(
        self,
        centers: List[float],
        counts: List[int],
        peak_idx: int,
        bin_width: float
    ) -> Optional[GaussianFit]:
        """Fit a Gaussian curve around a detected peak."""
        if peak_idx < 0 or peak_idx >= len(counts):
            return None

        # Get data around peak
        window = 5
        start = max(0, peak_idx - window)
        end = min(len(counts), peak_idx + window + 1)

        local_centers = centers[start:end]
        local_counts = counts[start:end]

        if not local_counts:
            return None

        # Find maximum
        max_idx = local_counts.index(max(local_counts))
        amplitude = float(local_counts[max_idx])
        center = local_centers[max_idx]

        # Estimate sigma from FWHM
        half_max = amplitude / 2
        left_idx = max_idx
        right_idx = max_idx

        for i in range(max_idx, -1, -1):
            if local_counts[i] < half_max:
                left_idx = i
                break

        for i in range(max_idx, len(local_counts)):
            if local_counts[i] < half_max:
                right_idx = i
                break

        fwhm = local_centers[right_idx] - local_centers[left_idx] if right_idx > left_idx else bin_width * 2
        sigma = max(0.1, fwhm / 2.355)

        return GaussianFit(
            amplitude=amplitude,
            center=center,
            sigma=sigma,
        )

    def _merge_close_peaks(self, peaks: List[GaussianFit]) -> List[GaussianFit]:
        """Merge peaks that are too close together."""
        if not peaks:
            return []

        # Sort by center position
        peaks = sorted(peaks, key=lambda p: p.center)

        merged = [peaks[0]]
        min_separation = 0.8  # Minimum 0.8 µs between peaks

        for peak in peaks[1:]:
            if peak.center - merged[-1].center < min_separation:
                # Keep the higher amplitude peak
                if peak.amplitude > merged[-1].amplitude:
                    merged[-1] = peak
            else:
                merged.append(peak)

        return merged

    def _label_peaks(self, peaks: List[GaussianFit]) -> List[GaussianFit]:
        """Assign labels and colors to detected peaks based on MFM timing."""
        if not peaks:
            return []

        # Expected positions for HD MFM
        expected = [
            (MFM_HD_2T_US, "2T", COLOR_PEAK_2T),
            (MFM_HD_3T_US, "3T", COLOR_PEAK_3T),
            (MFM_HD_4T_US, "4T", COLOR_PEAK_4T),
        ]

        labeled = []
        for peak in peaks:
            # Find closest expected position
            best_match = None
            best_dist = float('inf')

            for exp_pos, label, color in expected:
                dist = abs(peak.center - exp_pos)
                if dist < best_dist and dist < 1.5:  # Within 1.5 µs
                    best_dist = dist
                    best_match = (label, color)

            if best_match:
                peak.label = best_match[0]
                peak.color = best_match[1]
            else:
                peak.label = f"{peak.center:.1f}"
                peak.color = COLOR_GAUSSIAN

            labeled.append(peak)

        return labeled

    def _calculate_quality_metrics(self) -> None:
        """Calculate quality metrics from histogram data."""
        if not self._histogram or not self._histogram.peaks:
            self._quality_score = 0.0
            self._peak_separation = 0.0
            self._avg_jitter = 0.0
            return

        peaks = self._histogram.peaks

        # Peak separation (average distance between peaks)
        if len(peaks) >= 2:
            separations = []
            for i in range(1, len(peaks)):
                separations.append(peaks[i].center - peaks[i - 1].center)
            self._peak_separation = statistics.mean(separations)
        else:
            self._peak_separation = 0.0

        # Average jitter (average sigma)
        self._avg_jitter = statistics.mean([p.sigma for p in peaks])

        # Quality score based on:
        # 1. Number of peaks (3 is ideal for MFM)
        # 2. Peak sharpness (low sigma is better)
        # 3. Peak separation (should be ~2 µs for HD)

        scores = []

        # Peak count score
        num_peaks = len(peaks)
        if num_peaks == 3:
            scores.append(1.0)
        elif num_peaks == 2:
            scores.append(0.7)
        elif num_peaks == 1:
            scores.append(0.4)
        else:
            scores.append(max(0.3, 1.0 - abs(num_peaks - 3) * 0.1))

        # Sharpness score (sigma < 0.3 is excellent, > 1.0 is poor)
        sharpness_score = max(0, 1.0 - (self._avg_jitter - 0.2) / 0.8)
        scores.append(sharpness_score)

        # Separation score (should be ~2 µs)
        if self._peak_separation > 0:
            sep_score = max(0, 1.0 - abs(self._peak_separation - 2.0) / 2.0)
            scores.append(sep_score)

        self._quality_score = statistics.mean(scores) if scores else 0.0

    def _us_to_x(self, us: float) -> float:
        """Convert microseconds to X pixel coordinate."""
        if not self._histogram:
            return MARGIN_LEFT

        min_us = self._histogram.bin_centers[0] - self._histogram.bin_width / 2
        max_us = self._histogram.bin_centers[-1] + self._histogram.bin_width / 2
        range_us = max_us - min_us

        plot_width = self.width() - MARGIN_LEFT - MARGIN_RIGHT
        if range_us == 0:
            return MARGIN_LEFT

        return MARGIN_LEFT + (us - min_us) / range_us * plot_width

    def _count_to_y(self, count: int) -> float:
        """Convert count to Y pixel coordinate."""
        if not self._histogram or self._histogram.max_count == 0:
            return self.height() - MARGIN_BOTTOM

        plot_height = self.height() - MARGIN_TOP - MARGIN_BOTTOM
        return self.height() - MARGIN_BOTTOM - (count / self._histogram.max_count) * plot_height

    def _x_to_us(self, x: float) -> float:
        """Convert X pixel coordinate to microseconds."""
        if not self._histogram:
            return 0.0

        min_us = self._histogram.bin_centers[0] - self._histogram.bin_width / 2
        max_us = self._histogram.bin_centers[-1] + self._histogram.bin_width / 2
        range_us = max_us - min_us

        plot_width = self.width() - MARGIN_LEFT - MARGIN_RIGHT
        if plot_width == 0:
            return min_us

        return min_us + (x - MARGIN_LEFT) / plot_width * range_us

    # =========================================================================
    # Paint Event
    # =========================================================================

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the histogram."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), COLOR_BACKGROUND)

        if not self._histogram:
            self._draw_empty_state(painter)
            return

        # Draw components
        self._draw_grid(painter)
        self._draw_mfm_reference(painter)
        self._draw_histogram_bars(painter)
        self._draw_gaussian_fits(painter)
        self._draw_axes(painter)
        self._draw_quality_metrics(painter)

    def _draw_empty_state(self, painter: QPainter) -> None:
        """Draw empty state message."""
        painter.setFont(self._font_title)
        painter.setPen(QPen(COLOR_AXIS))

        text = "No flux data loaded"
        fm = QFontMetrics(self._font_title)
        text_rect = fm.boundingRect(text)

        x = (self.width() - text_rect.width()) / 2
        y = (self.height() + text_rect.height()) / 2

        painter.drawText(int(x), int(y), text)

    def _draw_grid(self, painter: QPainter) -> None:
        """Draw background grid."""
        pen = QPen(COLOR_GRID, 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)

        plot_left = MARGIN_LEFT
        plot_right = self.width() - MARGIN_RIGHT
        plot_top = MARGIN_TOP
        plot_bottom = self.height() - MARGIN_BOTTOM

        # Horizontal grid lines (5 divisions)
        for i in range(1, 5):
            y = plot_top + i * (plot_bottom - plot_top) / 5
            painter.drawLine(int(plot_left), int(y), int(plot_right), int(y))

        # Vertical grid lines (at 2, 4, 6, 8, 10 µs)
        for us in [2, 4, 6, 8, 10]:
            x = self._us_to_x(us)
            if plot_left <= x <= plot_right:
                painter.drawLine(int(x), int(plot_top), int(x), int(plot_bottom))

    def _draw_mfm_reference(self, painter: QPainter) -> None:
        """Draw MFM reference lines."""
        if not self._show_mfm_reference:
            return

        plot_top = MARGIN_TOP
        plot_bottom = self.height() - MARGIN_BOTTOM

        references = [
            (MFM_HD_2T_US, "2T", COLOR_PEAK_2T),
            (MFM_HD_3T_US, "3T", COLOR_PEAK_3T),
            (MFM_HD_4T_US, "4T", COLOR_PEAK_4T),
        ]

        painter.setFont(self._font_small)

        for us, label, color in references:
            x = self._us_to_x(us)

            # Draw vertical line
            pen = QPen(color, 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(int(x), int(plot_top), int(x), int(plot_bottom))

            # Draw label
            painter.setPen(QPen(color))
            painter.drawText(int(x - 8), int(plot_top - 5), label)

    def _draw_histogram_bars(self, painter: QPainter) -> None:
        """Draw histogram bars."""
        if not self._histogram:
            return

        plot_bottom = self.height() - MARGIN_BOTTOM
        plot_width = self.width() - MARGIN_LEFT - MARGIN_RIGHT
        n_bins = len(self._histogram.bin_centers)

        if n_bins == 0:
            return

        bar_width = max(MIN_BIN_WIDTH_PX, plot_width / n_bins - 1)

        pen = QPen(COLOR_BARS, 1)
        brush = QBrush(COLOR_BARS_FILL)

        painter.setPen(pen)
        painter.setBrush(brush)

        for i, (center, count) in enumerate(zip(self._histogram.bin_centers,
                                                self._histogram.bin_counts)):
            if count == 0:
                continue

            x = self._us_to_x(center) - bar_width / 2
            y = self._count_to_y(count)
            height = plot_bottom - y

            # Highlight hovered bar
            if i == self._hover_bin:
                painter.setBrush(QBrush(COLOR_BARS))
            else:
                painter.setBrush(brush)

            painter.drawRect(QRectF(x, y, bar_width, height))

    def _draw_gaussian_fits(self, painter: QPainter) -> None:
        """Draw Gaussian fit curves."""
        if not self._show_gaussian_fits or not self._histogram:
            return

        for peak in self._histogram.peaks:
            self._draw_single_gaussian(painter, peak)

    def _draw_single_gaussian(self, painter: QPainter, peak: GaussianFit) -> None:
        """Draw a single Gaussian curve."""
        pen = QPen(peak.color, 2)
        painter.setPen(pen)

        path = QPainterPath()
        first_point = True

        # Draw curve across visible range
        min_us = self._histogram.bin_centers[0] - self._histogram.bin_width / 2
        max_us = self._histogram.bin_centers[-1] + self._histogram.bin_width / 2

        # Only draw near the peak (center ± 3 sigma)
        start_us = max(min_us, peak.center - 3 * peak.sigma)
        end_us = min(max_us, peak.center + 3 * peak.sigma)

        steps = 50
        step_size = (end_us - start_us) / steps

        for i in range(steps + 1):
            us = start_us + i * step_size
            value = peak.evaluate(us)

            x = self._us_to_x(us)
            y = self._count_to_y(int(value))

            if first_point:
                path.moveTo(x, y)
                first_point = False
            else:
                path.lineTo(x, y)

        painter.drawPath(path)

        # Draw peak label
        painter.setFont(self._font_small)
        x_center = self._us_to_x(peak.center)
        y_top = self._count_to_y(int(peak.amplitude))

        label_text = f"{peak.label}\n{peak.center:.2f}µs"
        painter.drawText(int(x_center - 15), int(y_top - 25), label_text)

    def _draw_axes(self, painter: QPainter) -> None:
        """Draw axis lines and labels."""
        pen = QPen(COLOR_AXIS, 1)
        painter.setPen(pen)
        painter.setFont(self._font_label)

        plot_left = MARGIN_LEFT
        plot_right = self.width() - MARGIN_RIGHT
        plot_top = MARGIN_TOP
        plot_bottom = self.height() - MARGIN_BOTTOM

        # X axis
        painter.drawLine(int(plot_left), int(plot_bottom),
                        int(plot_right), int(plot_bottom))

        # Y axis
        painter.drawLine(int(plot_left), int(plot_top),
                        int(plot_left), int(plot_bottom))

        # X axis labels
        for us in [2, 4, 6, 8, 10]:
            x = self._us_to_x(us)
            if plot_left <= x <= plot_right:
                painter.drawText(int(x - 10), int(plot_bottom + 15), f"{us}")

        # X axis title
        painter.drawText(int((plot_left + plot_right) / 2 - 40),
                        int(self.height() - 5), "Pulse Width (µs)")

        # Y axis labels
        if self._histogram and self._histogram.max_count > 0:
            for i in range(5):
                count = int(self._histogram.max_count * (4 - i) / 4)
                y = plot_top + i * (plot_bottom - plot_top) / 4

                if count >= 1000:
                    label = f"{count // 1000}k"
                else:
                    label = str(count)

                painter.drawText(int(plot_left - 35), int(y + 5), label)

        # Y axis title (rotated)
        painter.save()
        painter.translate(15, (plot_top + plot_bottom) / 2)
        painter.rotate(-90)
        painter.drawText(0, 0, "Count")
        painter.restore()

    def _draw_quality_metrics(self, painter: QPainter) -> None:
        """Draw quality metrics display."""
        if not self._histogram:
            return

        painter.setFont(self._font_small)
        painter.setPen(QPen(COLOR_TEXT))

        x = self.width() - MARGIN_RIGHT - 100
        y = MARGIN_TOP + 15

        # Quality score with color
        score_color = QColor("#4ec9b0") if self._quality_score >= 0.7 else \
                     QColor("#dcdcaa") if self._quality_score >= 0.4 else \
                     QColor("#f14c4c")

        painter.setPen(QPen(score_color))
        painter.drawText(int(x), int(y), f"Quality: {self._quality_score:.0%}")

        painter.setPen(QPen(COLOR_TEXT))
        painter.drawText(int(x), int(y + 15), f"Peaks: {len(self._histogram.peaks)}")
        painter.drawText(int(x), int(y + 30), f"Jitter: {self._avg_jitter:.2f}µs")

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for hover effects."""
        if not self._histogram:
            return

        us = self._x_to_us(event.position().x())

        # Find bin under cursor
        old_hover = self._hover_bin
        self._hover_bin = -1

        for i, center in enumerate(self._histogram.bin_centers):
            if abs(center - us) < self._histogram.bin_width / 2:
                self._hover_bin = i
                break

        if self._hover_bin != old_hover:
            self.update()

        # Show tooltip
        if self._hover_bin >= 0:
            count = self._histogram.bin_counts[self._hover_bin]
            pct = (count / self._histogram.total_count * 100) if self._histogram.total_count > 0 else 0
            self.setToolTip(f"{us:.2f} µs\nCount: {count:,}\n{pct:.1f}%")
        else:
            self.setToolTip("")

    def mousePressEvent(self, event) -> None:
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton and self._histogram:
            us = self._x_to_us(event.position().x())

            # Check if clicked near a peak
            for peak in self._histogram.peaks:
                if abs(peak.center - us) < peak.sigma * 2:
                    self.peak_clicked.emit(peak.center)
                    break

    def leaveEvent(self, event) -> None:
        """Handle mouse leave."""
        self._hover_bin = -1
        self.update()


# =============================================================================
# Histogram Panel with Stats
# =============================================================================

class FluxHistogramPanel(QWidget):
    """
    Histogram widget with statistics panel.

    Combines the histogram visualization with a statistics display
    showing peak information and quality metrics.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Histogram widget
        self._histogram = FluxHistogramWidget()
        layout.addWidget(self._histogram, 1)

        # Stats bar
        stats_bar = QFrame()
        stats_bar.setStyleSheet("""
            QFrame {
                background-color: #2d2d30;
                border-top: 1px solid #3a3d41;
            }
            QLabel {
                color: #cccccc;
                padding: 2px 4px;
            }
        """)
        stats_layout = QHBoxLayout(stats_bar)
        stats_layout.setContentsMargins(8, 4, 8, 4)
        stats_layout.setSpacing(16)

        self._total_label = QLabel("Total: --")
        stats_layout.addWidget(self._total_label)

        self._peak_2t_label = QLabel("2T: --")
        self._peak_2t_label.setStyleSheet("color: #569cd6;")
        stats_layout.addWidget(self._peak_2t_label)

        self._peak_3t_label = QLabel("3T: --")
        self._peak_3t_label.setStyleSheet("color: #4ec9b0;")
        stats_layout.addWidget(self._peak_3t_label)

        self._peak_4t_label = QLabel("4T: --")
        self._peak_4t_label.setStyleSheet("color: #c586c0;")
        stats_layout.addWidget(self._peak_4t_label)

        stats_layout.addStretch()

        self._sep_label = QLabel("Sep: --")
        stats_layout.addWidget(self._sep_label)

        layout.addWidget(stats_bar)

    def get_histogram_widget(self) -> FluxHistogramWidget:
        """Get the histogram widget."""
        return self._histogram

    def set_histogram_data(self, timings_us: List[float], bins: int = 100,
                          min_us: float = 2.0, max_us: float = 12.0) -> None:
        """Set histogram data and update stats."""
        self._histogram.set_histogram_data(timings_us, bins, min_us, max_us)
        self._update_stats()

    def clear_histogram(self) -> None:
        """Clear histogram and stats."""
        self._histogram.clear_histogram()
        self._total_label.setText("Total: --")
        self._peak_2t_label.setText("2T: --")
        self._peak_3t_label.setText("3T: --")
        self._peak_4t_label.setText("4T: --")
        self._sep_label.setText("Sep: --")

    def _update_stats(self) -> None:
        """Update statistics labels."""
        hist = self._histogram._histogram
        if not hist:
            return

        self._total_label.setText(f"Total: {hist.total_count:,}")

        # Update peak labels
        peak_labels = {
            "2T": self._peak_2t_label,
            "3T": self._peak_3t_label,
            "4T": self._peak_4t_label,
        }

        for label in peak_labels.values():
            label.setText(label.text().split(":")[0] + ": --")

        for peak in hist.peaks:
            if peak.label in peak_labels:
                peak_labels[peak.label].setText(f"{peak.label}: {peak.center:.2f}µs")

        # Update separation
        sep = self._histogram.get_peak_separation()
        if sep > 0:
            self._sep_label.setText(f"Sep: {sep:.2f}µs")
        else:
            self._sep_label.setText("Sep: --")


__all__ = [
    'FluxHistogramWidget',
    'FluxHistogramPanel',
    'HistogramData',
    'GaussianFit',
    'DetectedPeak',
    'PeakAnalysis',
]
