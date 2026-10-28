"""Adaptive delta time adjustment based on performance."""

from __future__ import annotations

import logging
import math
import statistics
from bisect import bisect_right
from collections import deque
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Self

from glitchygames.clock import raw_counter_seconds

if TYPE_CHECKING:
    from collections.abc import Collection

LOG = logging.getLogger(__name__)

# FPS grade thresholds (absolute grading when target FPS is unlimited)
FPS_GRADE_EXCELLENT = 120
FPS_GRADE_VERY_GOOD = 60
FPS_GRADE_GOOD = 45
FPS_GRADE_FAIR = 30
FPS_GRADE_POOR = 20

# FPS ratio thresholds (relative grading when target FPS is set)
FPS_RATIO_EXCELLENT = 0.95
FPS_RATIO_VERY_GOOD = 0.90
FPS_RATIO_GOOD = 0.80
FPS_RATIO_POOR = 0.70

# Delta time history and averaging
DT_HISTORY_WINDOW = 60
MIN_HISTORY_FOR_AVERAGING = 10
DT_ADJUSTMENT_LOG_THRESHOLD = 0.0001
MIN_DT_HISTORY_FOR_STATS = 2
RECENT_DT_SAMPLE_COUNT = 5

# Scene frame time and FPS history limits
MAX_SCENE_FRAME_TIME_HISTORY = 1000
FPS_HISTORY_MAX_SIZE = 10000

# Trim percent ceiling (must be below 50% to avoid trimming all data)
MAX_TRIM_PERCENT = 50.0

# Equal-range histogram: exactly this many equal-width buckets span the analyzed [min, max],
# so the distribution is readable on one screen.
HISTOGRAM_BUCKET_COUNT = 10

# Target-relative histogram: buckets are this many percentage points of the target FPS wide.
TARGET_RELATIVE_STEP_PERCENT = 10

# Targets below this FPS (or non-integer targets) label target-relative FPS bounds in tenths.
DECIMAL_LABEL_TARGET_FPS = 20

# "1% low" definition: the mean FPS of the slowest ONE_PERCENT_LOW_FRACTION of ALL valid
# (untrimmed) frames, using max(1, ceil(fraction * total_frames)) frames.
ONE_PERCENT_LOW_FRACTION = 0.01

# Reliability: minimum samples for "5 nines" (99.999%) confidence
RELIABILITY_MIN_SAMPLES = 1000000


class FpsHistogramMode(Enum):
    """How the shutdown FPS histogram groups frames into buckets."""

    EQUAL_RANGE = 'equal-range'
    TARGET_RELATIVE = 'target-relative'


class AdaptiveClamping:
    """Singleton class for performance-based delta time adjustment.

    This class automatically adjusts delta time to maintain consistent game speed
    regardless of frame rate, supporting infinite frame rates with smooth performance.
    """

    _instance = None
    _initialized = False

    def __new__(cls: type[Self]) -> Self:
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # type: ignore[return-value]

    def __init__(self: Self) -> None:
        """Initialize the adaptive clamping system."""
        if not self._initialized:
            self._dt_history: list[float] = []
            # deque(maxlen=...) discards the oldest sample in O(1); list.pop(0) shifted the whole
            # list on every frame once full (measured 12.5 us per frame per 100k-entry list).
            self._fps_history: deque[float] = deque(maxlen=FPS_HISTORY_MAX_SIZE)
            # Track performance per scene:
            # {scene_name: {'fps_history': deque, 'fps_histogram': {},
            #  'frame_times': deque, 'statistical_aggregates': {}}}
            self._scene_data: dict[str, dict[str, Any]] = {}
            self._last_performance_log_time = 0.0
            self._fps_log_interval_ms: float | None = 1000.0  # Default 1 second
            self._current_scene = None
            self._target_fps = 0.0  # 0 means unlimited FPS
            # Percentage of frames to trim from both tails when summarizing FPS.
            self._trim_percent = 5.0
            self._histogram_mode = FpsHistogramMode.EQUAL_RANGE
            # Sliding window configuration for low-RAM systems
            self._max_fps_history = 100000  # Keep 100k samples in memory
            self._statistical_sample_size = 1000000  # Target 1M samples for 5 9s reliability
            self._sampling_interval = 10  # Sample every 10th frame for statistical aggregates
            self._initialized = True

    def get_adaptive_dt(self: Self, dt: float) -> float:
        """Get adaptively adjusted delta time based on performance.

        This method automatically adjusts dt to maintain consistent game speed
        regardless of frame rate, supporting infinite frame rates.

        Args:
            dt (float): The raw delta time.

        Returns:
            float: The adjusted delta time.

        """
        # Track recent delta times for performance analysis
        self._dt_history.append(dt)
        if len(self._dt_history) > DT_HISTORY_WINDOW:  # Keep last 60 frames
            self._dt_history.pop(0)

        # Note: FPS tracking is now handled by FPS events, not here
        # This prevents double-counting and ensures we use the accurate FPS from pygame.clock

        # Calculate average performance
        if len(self._dt_history) >= MIN_HISTORY_FOR_AVERAGING:
            avg_dt = sum(self._dt_history) / len(self._dt_history)
            avg_fps = 1.0 / avg_dt if avg_dt > 0 else 60

            # Use a target FPS of 60 for consistent game speed
            # This ensures the game runs at the same speed regardless of actual FPS
            target_dt = 1.0 / 60.0  # 60 FPS target

            # Smooth adjustment: blend between current dt and target dt
            # This prevents jarring changes while maintaining consistent speed
            smoothing_factor = 0.1  # How quickly to adjust (0.1 = 10% per frame)
            adjusted_dt = dt * (1 - smoothing_factor) + target_dt * smoothing_factor

            # Only log significant adjustments at the configured interval
            current_time = raw_counter_seconds()
            # Be robust if tests or external code set interval to None
            interval_ms = (
                self._fps_log_interval_ms if self._fps_log_interval_ms is not None else 1000.0
            )
            log_interval_seconds = interval_ms / 1000.0
            if (
                abs(adjusted_dt - dt) > DT_ADJUSTMENT_LOG_THRESHOLD
                and current_time - self._last_performance_log_time >= log_interval_seconds
            ):
                LOG.info(
                    'Adjusted dt from %.1fms to %.1fms per frame (avg_fps=%.1f)',
                    dt * 1000,
                    adjusted_dt * 1000,
                    avg_fps,
                )
                self._last_performance_log_time = current_time

            return adjusted_dt

        return dt

    def set_fps_log_interval(self: Self, interval_ms: float) -> None:
        """Set the FPS log interval in milliseconds.

        Args:
            interval_ms (float): Log interval in milliseconds.

        """
        self._fps_log_interval_ms = interval_ms

    def set_target_fps(self: Self, target_fps: float) -> None:
        """Set the target FPS for performance grading.

        Args:
            target_fps (float): Target FPS (0 means unlimited).

        """
        self._target_fps = target_fps

    def set_trim_percent(self: Self, percent: float) -> None:
        """Set percentage of frames to trim from both tails for summaries.

        Args:
            percent (float): Percentage in [0, 50). 0 disables trimming.

        """
        if percent < 0:
            percent = 0.0
        if percent >= MAX_TRIM_PERCENT:
            # Prevent trimming away all data; clamp just below 50%
            percent = 49.9
        self._trim_percent = float(percent)

    def set_histogram_mode(self: Self, mode: str) -> None:
        """Choose how the shutdown FPS histogram groups frames.

        Args:
            mode (str): 'equal-range' (10 equal buckets spanning the analyzed min to max) or
                'target-relative' (10% steps of the target FPS).

        Raises:
            ValueError: If mode is not one of the allowed values.

        """
        try:
            self._histogram_mode = FpsHistogramMode(mode)
        except ValueError:
            allowed_values = ', '.join(repr(member.value) for member in FpsHistogramMode)
            message = f'Unknown FPS histogram mode {mode!r}; allowed values: {allowed_values}'
            raise ValueError(message) from None

    def set_current_scene(self: Self, scene_name: str) -> None:
        """Set the current scene for per-scene tracking.

        Args:
            scene_name (str): Name of the current scene.

        """
        if scene_name != self._current_scene:
            # Initialize new scene data if it doesn't exist
            if scene_name not in self._scene_data:
                self._scene_data[scene_name] = {
                    'fps_history': deque(maxlen=self._max_fps_history),
                    'fps_histogram': {},
                    'frame_times': deque(maxlen=MAX_SCENE_FRAME_TIME_HISTORY),
                    'statistical_aggregates': {
                        'total_samples': 0,
                        'sum_fps': 0.0,
                        'sum_squared_fps': 0.0,
                        'min_fps': float('inf'),
                        'max_fps': 0.0,
                        # Sliding window of every Nth sample
                        'sampled_fps_history': deque(maxlen=self._max_fps_history),
                    },
                }

            self._current_scene = scene_name

    def track_fps_from_event(self: Self, fps: float, frame_time: float | None = None) -> None:
        """Track FPS from FPS events with sliding window and statistical sampling.

        Args:
            fps (float): The current FPS value from pygame.clock.get_fps().
            frame_time (float, optional): Actual frame time in seconds for spare time calculation.

        """
        # Track data for the current scene
        if self._current_scene and self._current_scene in self._scene_data:
            scene_data = self._scene_data[self._current_scene]
            stats = scene_data['statistical_aggregates']

            # Update statistical aggregates for 5 9s reliability
            stats['total_samples'] += 1
            stats['sum_fps'] += fps
            stats['sum_squared_fps'] += fps * fps
            stats['min_fps'] = min(stats['min_fps'], fps)
            stats['max_fps'] = max(stats['max_fps'], fps)

            # Sliding window: the deque's maxlen keeps the newest 100k samples in memory
            scene_data['fps_history'].append(fps)

            # Statistical sampling: sample every Nth frame for detailed analysis
            if stats['total_samples'] % self._sampling_interval == 0:
                stats['sampled_fps_history'].append(fps)

            # Track frame times for spare time calculation (only for capped FPS)
            if frame_time is not None and self._target_fps > 0:
                # The deque's maxlen keeps the newest 1000 frame times
                scene_data['frame_times'].append(frame_time)

            # Track histogram
            fps_int = round(fps)
            if fps_int in scene_data['fps_histogram']:
                scene_data['fps_histogram'][fps_int] += 1
            else:
                scene_data['fps_histogram'][fps_int] = 1

    def get_statistical_aggregates(self: Self, scene_name: str | None = None) -> dict[str, Any]:
        """Get statistical aggregates for 5 9s reliability analysis.

        Args:
            scene_name (str, optional): Scene name to get stats for. If None, aggregates all scenes.

        Returns:
            dict: Statistical aggregates including mean, variance, and confidence intervals.

        """
        if scene_name:
            # Get stats for specific scene
            if scene_name not in self._scene_data:
                return {'message': 'Scene not found'}
            stats = self._scene_data[scene_name]['statistical_aggregates']
        else:
            # Aggregate stats from all scenes
            total_samples = 0
            sum_fps = 0.0
            sum_squared_fps = 0.0
            min_fps = float('inf')
            max_fps = 0.0

            for scene_data in self._scene_data.values():
                stats = scene_data['statistical_aggregates']
                total_samples += stats['total_samples']
                sum_fps += stats['sum_fps']
                sum_squared_fps += stats['sum_squared_fps']
                min_fps = min(min_fps, stats['min_fps'])
                max_fps = max(max_fps, stats['max_fps'])

            stats = {
                'total_samples': total_samples,
                'sum_fps': sum_fps,
                'sum_squared_fps': sum_squared_fps,
                'min_fps': min_fps,
                'max_fps': max_fps,
            }

        if stats['total_samples'] == 0:
            return {'message': 'No data available'}

        # Calculate statistical measures
        mean_fps = stats['sum_fps'] / stats['total_samples']
        variance = (stats['sum_squared_fps'] / stats['total_samples']) - (mean_fps**2)
        std_dev = variance**0.5 if variance > 0 else 0.0

        # 5 9s confidence interval (99.999% confidence)
        # Z-score for 99.999% confidence is approximately 4.265
        z_score = 4.265
        margin_of_error = z_score * (std_dev / (stats['total_samples'] ** 0.5))

        return {
            'total_samples': stats['total_samples'],
            'mean_fps': mean_fps,
            'std_deviation': std_dev,
            'min_fps': stats['min_fps'],
            'max_fps': stats['max_fps'],
            'confidence_interval_99_999': {
                'lower': mean_fps - margin_of_error,
                'upper': mean_fps + margin_of_error,
                'margin_of_error': margin_of_error,
            },
            'reliability_level': '5 9s (99.999%)'
            if stats['total_samples'] >= RELIABILITY_MIN_SAMPLES
            else f'Limited ({stats["total_samples"]:,} samples)',
        }

    def _track_fps(self: Self, fps: float) -> None:
        """Track FPS in histogram buckets for efficient storage.

        Args:
            fps (float): The current FPS value.

        """
        # Also keep recent FPS for immediate stats
        # The deque's maxlen keeps the last 10,000 FPS readings (~83s at 120fps, ~42s at 240fps)
        self._fps_history.append(fps)

    def get_performance_stats(self: Self) -> dict[str, Any]:
        """Get current performance statistics.

        Returns:
            dict: Performance statistics including average FPS and history.

        """
        if len(self._dt_history) < MIN_DT_HISTORY_FOR_STATS:
            return {'avg_fps': 60.0, 'history_length': 0}

        avg_dt = sum(self._dt_history) / len(self._dt_history)
        avg_fps = 1.0 / avg_dt if avg_dt > 0 else 60.0

        return {
            'avg_fps': avg_fps,
            'history_length': len(self._dt_history),
            'recent_dt': self._dt_history[-RECENT_DT_SAMPLE_COUNT:]
            if len(self._dt_history) >= RECENT_DT_SAMPLE_COUNT
            else self._dt_history,
        }

    def reset(self: Self) -> None:
        """Reset performance tracking."""
        self._dt_history = []
        self._fps_history = deque(maxlen=FPS_HISTORY_MAX_SIZE)
        LOG.info('Reset performance tracking')

    @staticmethod
    def _count_equal_range_buckets(trimmed_fps: list[float]) -> tuple[list[int], list[float]]:
        """Count frames per equal-width bucket using precomputed boundaries.

        Compares against boundaries computed once rather than flooring (fps - min) / width:
        with non-dyadic widths the division puts a value on a boundary in the lower bucket
        (for example 0.7 * 3 / 0.7 = 2.9999999999999996).

        Args:
            trimmed_fps: Analyzed (trimmed) FPS values, ascending, with max greater than min

        Returns:
            Tuple of (frame count per bucket, lower boundary of each bucket).

        """
        lowest_fps = trimmed_fps[0]
        bucket_width = (trimmed_fps[-1] - lowest_fps) / HISTOGRAM_BUCKET_COUNT
        boundaries = [
            lowest_fps + bucket_index * bucket_width
            for bucket_index in range(HISTOGRAM_BUCKET_COUNT)
        ]
        counts_by_index = [0] * HISTOGRAM_BUCKET_COUNT
        for fps in trimmed_fps:
            bucket_index = min(HISTOGRAM_BUCKET_COUNT - 1, bisect_right(boundaries, fps) - 1)
            counts_by_index[bucket_index] += 1
        return counts_by_index, boundaries

    @staticmethod
    def _build_equal_range_histogram(trimmed_fps: list[float]) -> tuple[dict[str, int], float]:
        """Count frames in HISTOGRAM_BUCKET_COUNT equal-width buckets spanning [min, max].

        A value goes to the highest bucket whose precomputed boundary (min + index * width) it
        reaches, so a value on a boundary lands in the upper bucket and the maximum in the last.

        Labels use integer bounds "lower-upper" with lower = round(min + index * width)
        and upper = (the next bucket's lower) - 1, the last bucket's upper being round(max).
        Buckets whose rounded lower bounds collide (a spread narrower than the
        bucket count) are merged so labels stay unique and ascending.

        Args:
            trimmed_fps: Analyzed (trimmed) FPS values, ascending

        Returns:
            Tuple of (label to frame count in ascending FPS order, bucket width in FPS).

        """
        lowest_fps = trimmed_fps[0]
        highest_fps = trimmed_fps[-1]
        bucket_width = (highest_fps - lowest_fps) / HISTOGRAM_BUCKET_COUNT
        if bucket_width == 0:
            return {f'{round(lowest_fps)}': len(trimmed_fps)}, 0.0

        counts_by_index, boundaries = AdaptiveClamping._count_equal_range_buckets(trimmed_fps)

        # Merge consecutive buckets that share the same rounded lower bound.
        merged_buckets: list[list[int]] = []  # each entry: [rounded lower bound, frame count]
        for bucket_index, count in enumerate(counts_by_index):
            lower_bound = round(boundaries[bucket_index])
            if merged_buckets and merged_buckets[-1][0] == lower_bound:
                merged_buckets[-1][1] += count
            else:
                merged_buckets.append([lower_bound, count])

        fps_histogram: dict[str, int] = {}
        for merged_index, (lower_bound, count) in enumerate(merged_buckets):
            if merged_index + 1 < len(merged_buckets):
                upper_bound = merged_buckets[merged_index + 1][0] - 1
            else:
                upper_bound = round(highest_fps)
            upper_bound = max(lower_bound, upper_bound)
            label = (
                f'{lower_bound}' if lower_bound == upper_bound else f'{lower_bound}-{upper_bound}'
            )
            fps_histogram[label] = count
        return fps_histogram, bucket_width

    @staticmethod
    def _build_target_relative_histogram(
        trimmed_fps: list[float],
        target_fps: float,
    ) -> dict[str, int]:
        """Count frames in 10% steps of the target FPS, listing only non-empty buckets.

        A frame belongs to step floor(percent / 10) * 10 where percent = fps / target * 100;
        100% and above share the top bucket. FPS bounds in the labels are integers derived from
        the target: step N covers ceil(N% of target) through ceil((N + 10)% of target) - 1.

        Args:
            trimmed_fps: Analyzed (trimmed) FPS values
            target_fps: Target FPS (must be greater than 0)

        Returns:
            Dictionary mapping label to frame count, lowest FPS first (">=100%" is last).

        """
        top_step_index = 100 // TARGET_RELATIVE_STEP_PERCENT
        counts_by_step_index: dict[int, int] = {}
        for fps in trimmed_fps:
            # Multiply before dividing so exact boundaries (54 of 60 FPS = 90%) stay exact.
            step_index = min(
                top_step_index,
                math.floor(fps * 100 / (target_fps * TARGET_RELATIVE_STEP_PERCENT)),
            )
            counts_by_step_index[step_index] = counts_by_step_index.get(step_index, 0) + 1

        # Small or fractional targets collapse or overlap integer FPS ranges (target 5 gives
        # 10-19% as "1-1" and 20-29% as "1-1"), so they are labelled in tenths of an FPS.
        use_decimals = target_fps < DECIMAL_LABEL_TARGET_FPS or not float(target_fps).is_integer()
        scale = 10 if use_decimals else 1

        def lower_bound_scaled(step_index: int) -> int:
            return math.ceil(step_index * TARGET_RELATIVE_STEP_PERCENT * target_fps * scale / 100)

        def format_bound(scaled_value: int) -> str:
            return f'{scaled_value / scale:.1f}' if use_decimals else f'{scaled_value}'

        fps_histogram: dict[str, int] = {}
        for step_index in sorted(counts_by_step_index):
            lower_bound = lower_bound_scaled(step_index)
            if step_index == top_step_index:
                label = f'>=100% ({target_fps:g}+ FPS)'
            elif step_index == 0:
                label = f'<{TARGET_RELATIVE_STEP_PERCENT}% (<{format_bound(lower_bound_scaled(1))})'
            else:
                upper_bound = max(lower_bound, lower_bound_scaled(step_index + 1) - 1)
                step_percent = step_index * TARGET_RELATIVE_STEP_PERCENT
                label = (
                    f'{step_percent}-{step_percent + TARGET_RELATIVE_STEP_PERCENT - 1}% '
                    f'({format_bound(lower_bound)}-{format_bound(upper_bound)})'
                )
            fps_histogram[label] = counts_by_step_index[step_index]
        return fps_histogram

    def _build_histogram_stats(self: Self, trimmed_fps: list[float]) -> dict[str, Any]:
        """Build the histogram entries of the stats dictionary for the selected mode.

        Target-relative mode needs a target FPS; with an uncapped target (0) it falls back to
        equal range, and 'fps_histogram_mode' reports the mode actually used.

        Args:
            trimmed_fps: Analyzed (trimmed) FPS values, ascending

        Returns:
            Dictionary with 'fps_histogram_mode', 'fps_histogram' and, in equal-range mode,
            'fps_bucket_width'.

        """
        if self._histogram_mode is FpsHistogramMode.TARGET_RELATIVE and self._target_fps > 0:
            return {
                'fps_histogram_mode': FpsHistogramMode.TARGET_RELATIVE.value,
                'fps_histogram': self._build_target_relative_histogram(
                    trimmed_fps, target_fps=self._target_fps
                ),
            }

        fps_histogram, bucket_width = self._build_equal_range_histogram(trimmed_fps)
        return {
            'fps_histogram_mode': FpsHistogramMode.EQUAL_RANGE.value,
            'fps_bucket_width': bucket_width,
            'fps_histogram': fps_histogram,
        }

    def _calculate_fps_stats(self: Self, fps_history: Collection[float]) -> dict[str, Any]:
        """Calculate FPS statistics for one set of samples (shared by global and per-scene).

        Minimum, maximum and the 1% low come from ALL valid frames; the average, median,
        histogram and grade come from the analyzed (trimmed) frames.

        Args:
            fps_history: Recorded FPS samples

        Returns:
            Statistics dictionary, or a dictionary with a 'message' key when there is no data.

        """
        if not fps_history:
            return {'message': 'Not enough data'}

        fps_values: list[float] = sorted(fps for fps in fps_history if fps > 0)
        if not fps_values:
            return {'message': 'No valid FPS data collected'}

        total_frames = len(fps_values)

        # Drop top and bottom self._trim_percent
        trim_ratio = max(0.0, min(self._trim_percent, 49.9)) / 100.0
        drop_count = int(total_frames * trim_ratio)
        # drop_count < total_frames / 2 always holds: the ratio is capped at 49.9%.
        # (A zero drop_count must not slice: fps_values[0:-0] is empty.)
        trimmed_fps: list[float] = (
            fps_values if drop_count == 0 else fps_values[drop_count:-drop_count]
        )

        slowest_frame_count = max(1, math.ceil(ONE_PERCENT_LOW_FRACTION * total_frames))
        histogram_stats = self._build_histogram_stats(trimmed_fps)

        return {
            'total_frames': total_frames,
            'trimmed_frames': len(trimmed_fps),
            'avg_fps': sum(trimmed_fps) / len(trimmed_fps),
            'min_fps': fps_values[0],
            'max_fps': fps_values[-1],
            'one_percent_low_fps': sum(fps_values[:slowest_frame_count]) / slowest_frame_count,
            'median_fps': statistics.median(trimmed_fps),
            **histogram_stats,
            'performance_grade': self._calculate_performance_grade(trimmed_fps),
        }

    def get_shutdown_stats(self: Self) -> dict[str, Any]:
        """Get comprehensive performance statistics for shutdown reporting.

        Returns:
            dict: Complete performance statistics with histogram data.

        """
        # Aggregate all scene data for global report
        all_fps_history: list[float] = []
        for scene_data in self._scene_data.values():
            fps_history_list: list[float] = scene_data['fps_history']
            all_fps_history.extend(fps_history_list)

        return self._calculate_fps_stats(all_fps_history)

    def get_per_scene_shutdown_stats(self: Self) -> dict[str, Any]:
        """Get comprehensive performance statistics per scene for shutdown reporting.

        Returns:
            dict: Per-scene performance statistics with histogram data.

        """
        per_scene_stats: dict[str, Any] = {}

        for scene_name, scene_data in self._scene_data.items():
            # Filter out "Unknown" scenes
            if scene_name == 'Unknown':
                LOG.info('Filtering out Unknown scene from per-scene stats')
                continue
            per_scene_stats[scene_name] = self._calculate_fps_stats(scene_data['fps_history'])

        return per_scene_stats

    # Absolute FPS grade thresholds: (min_fps, grade_label)
    # Ordered from highest to lowest threshold
    _ABSOLUTE_GRADE_THRESHOLDS: ClassVar[list[tuple[float, str]]] = [
        (FPS_GRADE_EXCELLENT, 'A+ (Excellent)'),
        (FPS_GRADE_VERY_GOOD, 'A (Very Good)'),
        (FPS_GRADE_GOOD, 'B (Good)'),
        (FPS_GRADE_FAIR, 'C (Fair)'),
        (FPS_GRADE_POOR, 'D (Poor)'),
    ]

    # Relative FPS ratio grade thresholds: (min_ratio, grade_label)
    # Ordered from highest to lowest threshold
    _RELATIVE_GRADE_THRESHOLDS: ClassVar[list[tuple[float, str]]] = [
        (1.0, 'A+ (Excellent)'),
        (FPS_RATIO_EXCELLENT, 'A (Very Good)'),
        (FPS_RATIO_VERY_GOOD, 'B (Good)'),
        (FPS_RATIO_GOOD, 'C (Fair)'),
        (FPS_RATIO_POOR, 'D (Poor)'),
    ]

    def _calculate_performance_grade(self: Self, fps_values: list[float]) -> str:
        """Calculate a performance grade based on FPS distribution relative to target FPS.

        Args:
            fps_values: List of FPS values.

        Returns:
            str: Performance grade (A+, A, B, C, D, F).

        """
        if not fps_values:
            return 'N/A'

        avg_fps = sum(fps_values) / len(fps_values)

        # If target FPS is 0 (unlimited), use absolute grading
        if self._target_fps == 0:
            thresholds = self._ABSOLUTE_GRADE_THRESHOLDS
            value = avg_fps
        else:
            # For target FPS > 0, grade relative to target
            thresholds = self._RELATIVE_GRADE_THRESHOLDS
            value = avg_fps / self._target_fps

        for threshold, grade in thresholds:
            if value >= threshold:
                return grade

        return 'F (Very Poor)'

    def get_spare_time_stats(self: Self, scene_name: str | None = None) -> dict[str, Any]:
        """Calculate spare time statistics for capped frame rates.

        Args:
            scene_name (str, optional): Scene name to get stats for. If None, aggregates all scenes.

        Returns:
            dict: Spare time statistics including average spare time and capacity.

        """
        if self._target_fps == 0:
            return {'message': 'Not applicable for unlimited FPS'}

        frame_times: list[float]
        if scene_name:
            # Get frame times for specific scene
            if scene_name not in self._scene_data:
                return {'message': 'Scene not found'}
            frame_times = self._scene_data[scene_name]['frame_times']
            if not frame_times:
                return {'message': 'No frame time data for this scene'}
        else:
            # Aggregate frame times from all scenes for global report
            frame_times = []
            for scene_data in self._scene_data.values():
                scene_frame_times: list[float] = scene_data['frame_times']
                frame_times.extend(scene_frame_times)
            if not frame_times:
                return {'message': 'No frame time data available'}

        target_frame_time = 1.0 / self._target_fps
        avg_frame_time = sum(frame_times) / len(frame_times)
        avg_spare_time = target_frame_time - avg_frame_time
        spare_capacity_percent = (avg_spare_time / target_frame_time) * 100

        return {
            'target_frame_time_ms': target_frame_time * 1000,
            'avg_frame_time_ms': avg_frame_time * 1000,
            'avg_spare_time_ms': avg_spare_time * 1000,
            'spare_capacity_percent': spare_capacity_percent,
            'could_tick_times': target_frame_time / avg_frame_time if avg_frame_time > 0 else 0,
        }

    @staticmethod
    def _pluralize_frames(count: int) -> str:
        """Return 'frame' for exactly one, otherwise 'frames'."""
        return 'frame' if count == 1 else 'frames'

    def _build_trim_label(self: Self, stats: dict[str, Any]) -> str:
        """Describe, from the actual numbers, how many frames trimming dropped.

        Args:
            stats: Stats dictionary containing total_frames and trimmed_frames

        Returns:
            Human-readable description of the trimming that was applied.

        """
        if self._trim_percent == 0:
            return 'no trimming'

        total_frames = stats['total_frames']
        dropped_frames = total_frames - stats['trimmed_frames']
        if dropped_frames == 0:
            # Smallest total where int(total * percent / 100) >= 1.
            minimum_frames = math.ceil(100 / self._trim_percent)
            return (
                f'dropped 0 of {total_frames:,} {self._pluralize_frames(total_frames)}; '
                f'the {self._trim_percent:.1f}% setting needs at least {minimum_frames:,}'
            )

        frames_per_end = dropped_frames // 2
        return (
            f'dropped {frames_per_end:,} {self._pluralize_frames(frames_per_end)} '
            f'from each end ({self._trim_percent:.1f}%)'
        )

    def _log_fps_stats(
        self: Self,
        stats: dict[str, Any],
        spare_stats: dict[str, Any],
    ) -> None:
        """Log FPS statistics and spare time information.

        Args:
            stats: Shutdown stats dictionary with FPS data
            spare_stats: Spare time stats dictionary

        """
        LOG.info('📊 Total Frames: %s', format(stats['total_frames'], ','))
        trim_label = self._build_trim_label(stats=stats)
        LOG.info('📈 Analyzed Frames: %s (%s)', format(stats['trimmed_frames'], ','), trim_label)

        if 'message' not in spare_stats:
            LOG.info('🎯 Target FPS: %.1f', self._target_fps)

        LOG.info('⚡ Average FPS (analyzed frames): %.1f', stats['avg_fps'])
        LOG.info('📉 Minimum FPS (all frames): %.1f', stats['min_fps'])
        LOG.info('🐌 1%% Low FPS (all frames): %.1f', stats['one_percent_low_fps'])
        LOG.info('📈 Maximum FPS (all frames): %.1f', stats['max_fps'])
        LOG.info('📊 Median FPS (analyzed frames): %.1f', stats['median_fps'])
        LOG.info('🏆 Performance Grade: %s', stats['performance_grade'])

        if 'message' not in spare_stats:
            LOG.info('⏱️  Target Frame Time: %.1fms per-tick', spare_stats['target_frame_time_ms'])
            LOG.info('⏱️  Average Frame Time: %.1fms per-tick', spare_stats['avg_frame_time_ms'])
            LOG.info(
                '⏱️  Spare Time: %.1fms per-tick (%.1f%% of scheduled capacity)',
                spare_stats['avg_spare_time_ms'],
                spare_stats['spare_capacity_percent'],
            )
            LOG.info(
                '🎨 Draw Time: %.1fms per-tick (%.1f%% of scheduled capacity)',
                spare_stats['avg_frame_time_ms'],
                100 - spare_stats['spare_capacity_percent'],
            )
            LOG.info('🔄 Could Tick: %.1fx faster', spare_stats['could_tick_times'])

    def _build_histogram_header(self: Self, stats: dict[str, Any]) -> str:
        """Describe how the histogram buckets were chosen.

        Args:
            stats: Stats dictionary with 'fps_histogram_mode' and, for equal range,
                'fps_bucket_width'

        Returns:
            The header line printed above the histogram.

        """
        if stats['fps_histogram_mode'] == FpsHistogramMode.TARGET_RELATIVE.value:
            return f'\n📊 FPS Distribution (relative to target {self._target_fps:g} FPS):'

        bucket_width = stats['fps_bucket_width']
        if bucket_width == 0:
            description = 'single bucket; every analyzed frame has the same FPS'
        else:
            bucket_count = len(stats['fps_histogram'])
            if bucket_count == HISTOGRAM_BUCKET_COUNT:
                description = f'{bucket_count} equal buckets, {bucket_width:.1f} FPS wide'
            else:
                description = (
                    f'{bucket_count} buckets after merging equal labels, '
                    f'{bucket_width:.1f} FPS wide'
                )
        if self._histogram_mode is FpsHistogramMode.TARGET_RELATIVE:
            description += '; no target FPS set for target-relative'
        return f'\n📊 FPS Distribution ({description}):'

    def _log_fps_histogram(self: Self, stats: dict[str, Any]) -> None:
        """Log the FPS histogram, lowest FPS first (the stats dictionary is already ordered).

        Args:
            stats: Stats dictionary with 'fps_histogram', 'fps_histogram_mode',
                'fps_bucket_width' (equal range) and 'trimmed_frames'

        """
        fps_histogram: dict[str, int] = stats['fps_histogram']
        trimmed_frames: int = stats['trimmed_frames']
        LOG.info(self._build_histogram_header(stats))
        max_count = max(fps_histogram.values())

        # Equal-range labels are bare FPS bounds; target-relative labels carry their own units.
        unit_suffix = (
            '' if stats['fps_histogram_mode'] == FpsHistogramMode.TARGET_RELATIVE.value else ' FPS'
        )

        # Calculate available space for bars (accounting for prefix text)
        prefix_length = 40  # Conservative estimate for prefix text
        max_bar_length = 80 - prefix_length  # Maximum bar length (40 chars)

        label_width = max(len(bucket) for bucket in fps_histogram)
        for bucket, count in fps_histogram.items():
            percentage = (count / trimmed_frames) * 100 if trimmed_frames > 0 else 0
            bar_length = int((count / max_count) * max_bar_length) if max_count > 0 else 0
            bar_length = min(bar_length, max_bar_length)
            bar = '█' * bar_length
            LOG.info(
                '  %*s%s %5d frames (%5.1f%%) %s',
                label_width,
                bucket,
                unit_suffix,
                count,
                percentage,
                bar,
            )

    def print_shutdown_report(self: Self) -> None:
        """Print a comprehensive performance report at shutdown."""
        stats = self.get_shutdown_stats()

        if 'message' in stats:
            # Skip global report if not enough data - per-scene reports are more useful
            return

        LOG.info('\n%s', '=' * 80)
        LOG.info('🎮 GAME PERFORMANCE REPORT')
        LOG.info('=' * 80)

        spare_stats = self.get_spare_time_stats()
        self._log_fps_stats(stats, spare_stats)

        # Stats without a 'message' come from at least one frame, so the histogram has a bucket
        self._log_fps_histogram(stats)

        LOG.info('=' * 80)

    def print_per_scene_shutdown_report(self: Self) -> None:
        """Print a comprehensive performance report per scene at shutdown."""
        per_scene_stats = self.get_per_scene_shutdown_stats()

        # No need to filter here anymore - filtering is done in get_per_scene_shutdown_stats
        filtered_stats = per_scene_stats

        if not filtered_stats:
            LOG.info('\n%s', '=' * 80)
            LOG.info('🎮 PER-SCENE PERFORMANCE REPORT')
            LOG.info('=' * 80)
            LOG.info('No scene performance data collected')
            LOG.info('=' * 80)
            return

        LOG.info('\n%s', '=' * 80)
        LOG.info('🎮 PER-SCENE PERFORMANCE REPORT')
        LOG.info('=' * 80)

        for scene_name, stats in filtered_stats.items():
            LOG.info('\n📊 Scene: %s', scene_name)
            LOG.info('-' * 40)

            if 'message' in stats:
                LOG.info('   %s', stats['message'])
                continue

            spare_stats = self.get_spare_time_stats(scene_name)
            self._log_fps_stats(stats, spare_stats)

            # Stats without a 'message' come from at least one frame: the histogram has a bucket
            self._log_fps_histogram(stats)

        LOG.info('=' * 80)


# Global instance for easy access
performance_manager = AdaptiveClamping()
