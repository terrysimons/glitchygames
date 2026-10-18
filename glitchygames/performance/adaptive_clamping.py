"""Adaptive delta time adjustment based on performance."""

from __future__ import annotations

import logging
import math
import statistics
import time
from collections import deque
from typing import TYPE_CHECKING, Any, ClassVar, Self

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

# Histogram bucketing: at most this many buckets, so the distribution is readable on one screen
MAX_HISTOGRAM_BUCKETS = 10

# "1% low" definition: the mean FPS of the slowest ONE_PERCENT_LOW_FRACTION of ALL valid
# (untrimmed) frames, using max(1, ceil(fraction * total_frames)) frames.
ONE_PERCENT_LOW_FRACTION = 0.01

# Reliability: minimum samples for "5 nines" (99.999%) confidence
RELIABILITY_MIN_SAMPLES = 1000000


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
            self._fps_histogram: dict[str, int] = {}
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
            current_time = time.perf_counter()
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
                    f'Adjusted dt from {dt * 1000:.1f}ms to '
                    f'{adjusted_dt * 1000:.1f}ms per frame '
                    f'(avg_fps={avg_fps:.1f})',
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
        self._fps_histogram = {}
        LOG.info('Reset performance tracking')

    @staticmethod
    def _choose_bucket_width(lowest_fps: float, highest_fps: float) -> int:
        """Choose the smallest "nice" bucket width that fits MAX_HISTOGRAM_BUCKETS.

        Widths follow the 1, 2, 5, 10, 20, 50, 100, ... (1/2/5 x 10^k) sequence.

        Args:
            lowest_fps: Lowest FPS value in the analyzed (trimmed) data
            highest_fps: Highest FPS value in the analyzed (trimmed) data

        Returns:
            The bucket width in FPS.

        """
        power_of_ten = 1
        while True:
            for multiplier in (1, 2, 5):
                width = multiplier * power_of_ten
                bucket_count = math.floor(highest_fps / width) - math.floor(lowest_fps / width) + 1
                if bucket_count <= MAX_HISTOGRAM_BUCKETS:
                    return width
            power_of_ten *= 10

    @staticmethod
    def _build_fps_histogram(trimmed_fps: list[float], bucket_width: int) -> dict[str, int]:
        """Count frames per bucket, ordered numerically by bucket lower bound.

        A bucket covers [lower, lower + bucket_width). The key is "lower" when the width is 1,
        otherwise "lower-upper" with upper = lower + bucket_width - 1.

        Args:
            trimmed_fps: Analyzed (trimmed) FPS values
            bucket_width: Width of each bucket in FPS

        Returns:
            Dictionary mapping bucket label to frame count, in ascending FPS order.

        """
        counts_by_lower_bound: dict[int, int] = {}
        for fps in trimmed_fps:
            lower_bound = math.floor(fps / bucket_width) * bucket_width
            counts_by_lower_bound[lower_bound] = counts_by_lower_bound.get(lower_bound, 0) + 1

        fps_histogram: dict[str, int] = {}
        for lower_bound in sorted(counts_by_lower_bound):
            if bucket_width == 1:
                label = f'{lower_bound}'
            else:
                label = f'{lower_bound}-{lower_bound + bucket_width - 1}'
            fps_histogram[label] = counts_by_lower_bound[lower_bound]
        return fps_histogram

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
        trimmed_fps: list[float]
        if drop_count == 0 or total_frames <= 2 * drop_count:
            trimmed_fps = fps_values
        else:
            trimmed_fps = fps_values[drop_count:-drop_count]

        slowest_frame_count = max(1, math.ceil(ONE_PERCENT_LOW_FRACTION * total_frames))
        bucket_width = self._choose_bucket_width(
            lowest_fps=trimmed_fps[0],
            highest_fps=trimmed_fps[-1],
        )

        return {
            'total_frames': total_frames,
            'trimmed_frames': len(trimmed_fps),
            'avg_fps': sum(trimmed_fps) / len(trimmed_fps),
            'min_fps': fps_values[0],
            'max_fps': fps_values[-1],
            'one_percent_low_fps': sum(fps_values[:slowest_frame_count]) / slowest_frame_count,
            'median_fps': statistics.median(trimmed_fps),
            'fps_bucket_width': bucket_width,
            'fps_histogram': self._build_fps_histogram(trimmed_fps, bucket_width),
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
                f'dropped 0 of {total_frames:,} frames; '
                f'the {self._trim_percent:.1f}% setting needs at least {minimum_frames:,}'
            )

        frames_per_end = dropped_frames // 2
        return f'dropped {frames_per_end:,} frames from each end ({self._trim_percent:.1f}%)'

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
        LOG.info(f'📊 Total Frames: {stats["total_frames"]:,}')
        trim_label = self._build_trim_label(stats=stats)
        LOG.info(f'📈 Analyzed Frames: {stats["trimmed_frames"]:,} ({trim_label})')

        if 'message' not in spare_stats:
            LOG.info(f'🎯 Target FPS: {self._target_fps:.1f}')

        LOG.info(f'⚡ Average FPS (analyzed frames): {stats["avg_fps"]:.1f}')
        LOG.info(f'📉 Minimum FPS (all frames): {stats["min_fps"]:.1f}')
        LOG.info(f'🐌 1% Low FPS (all frames): {stats["one_percent_low_fps"]:.1f}')
        LOG.info(f'📈 Maximum FPS (all frames): {stats["max_fps"]:.1f}')
        LOG.info(f'📊 Median FPS (analyzed frames): {stats["median_fps"]:.1f}')
        LOG.info(f'🏆 Performance Grade: {stats["performance_grade"]}')

        if 'message' not in spare_stats:
            LOG.info(f'⏱️  Target Frame Time: {spare_stats["target_frame_time_ms"]:.1f}ms per-tick')
            LOG.info(f'⏱️  Average Frame Time: {spare_stats["avg_frame_time_ms"]:.1f}ms per-tick')
            LOG.info(
                f'⏱️  Spare Time: {spare_stats["avg_spare_time_ms"]:.1f}ms'
                f' per-tick ({spare_stats["spare_capacity_percent"]:.1f}%'
                ' of scheduled capacity)',
            )
            LOG.info(
                f'🎨 Draw Time: {spare_stats["avg_frame_time_ms"]:.1f}ms'
                f' per-tick ({(100 - spare_stats["spare_capacity_percent"]):.1f}%'
                ' of scheduled capacity)',
            )
            LOG.info(f'🔄 Could Tick: {spare_stats["could_tick_times"]:.1f}x faster')

    @staticmethod
    def _log_fps_histogram(fps_histogram: dict[str, int], trimmed_frames: int) -> None:
        """Log FPS histogram in ascending numeric order of bucket lower bound.

        Args:
            fps_histogram: Dictionary mapping bucket keys to frame counts
            trimmed_frames: Total number of trimmed frames for percentage calculation

        """
        LOG.info('\n📊 FPS Distribution:')
        max_count = max(fps_histogram.values())

        # Build bucket list with percentages
        all_buckets: list[tuple[str, int, float]] = []
        for bucket, count in fps_histogram.items():
            percentage = (count / trimmed_frames) * 100 if trimmed_frames > 0 else 0
            all_buckets.append((bucket, count, percentage))

        # Ascending numeric order of the bucket's lower bound (lowest FPS first); with range
        # buckets this already shows the shape of the distribution. Sorting by int, not by
        # string, keeps '900-999' before '1000-1099'.
        all_buckets.sort(key=lambda bucket_entry: int(bucket_entry[0].split('-')[0]))

        # Calculate available space for bars (accounting for prefix text)
        prefix_length = 40  # Conservative estimate for prefix text
        max_bar_length = 80 - prefix_length  # Maximum bar length (40 chars)

        label_width = max(len(bucket) for bucket in fps_histogram)
        for bucket, count, percentage in all_buckets:
            bar_length = int((count / max_count) * max_bar_length) if max_count > 0 else 0
            bar_length = min(bar_length, max_bar_length)
            bar = '█' * bar_length
            fps_range = f'{bucket:>{label_width}s} FPS'
            LOG.info(f'  {fps_range} {count:5d} frames ({percentage:5.1f}%) {bar}')

    def print_shutdown_report(self: Self) -> None:
        """Print a comprehensive performance report at shutdown."""
        stats = self.get_shutdown_stats()

        if 'message' in stats:
            # Skip global report if not enough data - per-scene reports are more useful
            return

        LOG.info(f'\n{"=" * 80}')
        LOG.info('🎮 GAME PERFORMANCE REPORT')
        LOG.info('=' * 80)

        spare_stats = self.get_spare_time_stats()
        self._log_fps_stats(stats, spare_stats)

        if stats['fps_histogram']:
            self._log_fps_histogram(stats['fps_histogram'], stats['trimmed_frames'])

        LOG.info('=' * 80)

    def print_per_scene_shutdown_report(self: Self) -> None:
        """Print a comprehensive performance report per scene at shutdown."""
        per_scene_stats = self.get_per_scene_shutdown_stats()

        # No need to filter here anymore - filtering is done in get_per_scene_shutdown_stats
        filtered_stats = per_scene_stats

        if not filtered_stats:
            LOG.info(f'\n{"=" * 80}')
            LOG.info('🎮 PER-SCENE PERFORMANCE REPORT')
            LOG.info('=' * 80)
            LOG.info('No scene performance data collected')
            LOG.info('=' * 80)
            return

        LOG.info(f'\n{"=" * 80}')
        LOG.info('🎮 PER-SCENE PERFORMANCE REPORT')
        LOG.info('=' * 80)

        for scene_name, stats in filtered_stats.items():
            LOG.info(f'\n📊 Scene: {scene_name}')
            LOG.info('-' * 40)

            if 'message' in stats:
                LOG.info(f'   {stats["message"]}')
                continue

            spare_stats = self.get_spare_time_stats(scene_name)
            self._log_fps_stats(stats, spare_stats)

            if stats['fps_histogram']:
                self._log_fps_histogram(stats['fps_histogram'], stats['trimmed_frames'])

        LOG.info('=' * 80)


# Global instance for easy access
performance_manager = AdaptiveClamping()
