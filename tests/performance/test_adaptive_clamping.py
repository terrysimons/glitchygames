"""Tests for the adaptive clamping system."""

import math
import re

import pytest

from glitchygames.performance.adaptive_clamping import (
    FPS_HISTORY_MAX_SIZE,
    HISTOGRAM_BUCKET_COUNT,
    MAX_SCENE_FRAME_TIME_HISTORY,
    AdaptiveClamping,
    FpsHistogramMode,
)


class TestAdaptiveClampingSingleton:
    """Test the singleton pattern and initialization."""

    def test_singleton_pattern(self):
        """Test that only one instance exists."""
        # Reset singleton state
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False

        instance1 = AdaptiveClamping()
        instance2 = AdaptiveClamping()

        assert instance1 is instance2
        assert AdaptiveClamping._instance is instance1

    def test_initialization_only_once(self):
        """Test that initialization only happens once."""
        # Reset singleton state
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False

        instance1 = AdaptiveClamping()
        initial_dt_history = instance1._dt_history

        # Create another instance
        instance2 = AdaptiveClamping()

        # Should be the same instance with same data
        assert instance1 is instance2
        assert instance2._dt_history is initial_dt_history

    def test_initial_state(self):
        """Test that initial state is correct."""
        # Reset singleton state
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False

        instance = AdaptiveClamping()

        assert instance._dt_history == []
        assert instance._scene_data == {}
        assert math.isclose(instance._last_performance_log_time, 0.0, abs_tol=1e-9)
        assert instance._fps_log_interval_ms is not None
        assert math.isclose(instance._fps_log_interval_ms, 1000.0)
        assert instance._current_scene is None
        assert math.isclose(instance._target_fps, 0.0, abs_tol=1e-9)
        assert instance._initialized is True


class TestSceneManagement:
    """Test scene tracking and data management."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_set_current_scene_initializes_data(self):
        """Test that setting current scene initializes data structure."""
        self.instance.set_current_scene('TestScene')

        assert self.instance._current_scene == 'TestScene'
        assert 'TestScene' in self.instance._scene_data
        assert list(self.instance._scene_data['TestScene']['fps_history']) == []
        assert self.instance._scene_data['TestScene']['fps_histogram'] == {}
        assert list(self.instance._scene_data['TestScene']['frame_times']) == []

    def test_set_current_scene_doesnt_reinitialize(self):
        """Test that setting the same scene doesn't reinitialize data."""
        self.instance.set_current_scene('TestScene')
        initial_data = self.instance._scene_data['TestScene']

        # Add some data
        initial_data['fps_history'].append(60.0)
        initial_data['fps_histogram'][60] = 1
        initial_data['frame_times'].append(0.016)

        # Set same scene again
        self.instance.set_current_scene('TestScene')

        # Data should be preserved
        assert self.instance._scene_data['TestScene'] is initial_data
        assert list(self.instance._scene_data['TestScene']['fps_history']) == [60.0]
        assert self.instance._scene_data['TestScene']['fps_histogram'][60] == 1
        assert list(self.instance._scene_data['TestScene']['frame_times']) == [0.016]

    def test_switch_scenes_preserves_data(self):
        """Test that switching scenes preserves data for each scene."""
        # Set up first scene
        self.instance.set_current_scene('Scene1')
        self.instance._scene_data['Scene1']['fps_history'].append(60.0)

        # Switch to second scene
        self.instance.set_current_scene('Scene2')
        self.instance._scene_data['Scene2']['fps_history'].append(30.0)

        # Switch back to first scene
        self.instance.set_current_scene('Scene1')

        # Both scenes should have their data preserved
        assert list(self.instance._scene_data['Scene1']['fps_history']) == [60.0]
        assert list(self.instance._scene_data['Scene2']['fps_history']) == [30.0]


class TestFPSTracking:
    """Test FPS tracking and frame time collection."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()
        self.instance.set_current_scene('TestScene')

    def test_track_fps_from_event_basic(self):
        """Test basic FPS tracking."""
        self.instance.track_fps_from_event(60.0)

        scene_data = self.instance._scene_data['TestScene']
        assert list(scene_data['fps_history']) == [60.0]
        assert scene_data['fps_histogram'][60] == 1

    def test_track_fps_from_event_with_frame_time(self):
        """Test FPS tracking with frame time for spare time calculation."""
        self.instance._target_fps = 60.0
        self.instance.track_fps_from_event(60.0, 0.016)  # 16ms frame time

        scene_data = self.instance._scene_data['TestScene']
        assert list(scene_data['fps_history']) == [60.0]
        assert list(scene_data['frame_times']) == [0.016]
        assert scene_data['fps_histogram'][60] == 1

    def test_track_fps_from_event_histogram_accumulation(self):
        """Test that histogram accumulates FPS values."""
        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(30.0)

        scene_data = self.instance._scene_data['TestScene']
        assert scene_data['fps_histogram'][60] == 2
        assert scene_data['fps_histogram'][30] == 1

    def test_track_fps_from_event_history_limit(self):
        """Test that FPS history is limited to 100,000 entries."""
        # Add 100,001 FPS values
        for i in range(100001):
            self.instance.track_fps_from_event(60.0)

        scene_data = self.instance._scene_data['TestScene']
        assert len(scene_data['fps_history']) == 100000
        assert math.isclose(
            scene_data['fps_history'][0],
            60.0,
        )  # First entry should be the 1,001st one added (after 100k limit)
        assert math.isclose(
            scene_data['fps_history'][-1],
            60.0,
        )  # Last entry should be the last one added

    def test_track_fps_from_event_frame_times_limit(self):
        """Test that frame times are limited to 1,000 entries."""
        self.instance._target_fps = 60.0

        # Add 1,001 frame times
        for i in range(1001):
            self.instance.track_fps_from_event(60.0, 0.016)

        scene_data = self.instance._scene_data['TestScene']
        assert len(scene_data['frame_times']) == 1000
        assert math.isclose(
            scene_data['frame_times'][0],
            0.016,
        )  # First entry should be the second one added
        assert math.isclose(
            scene_data['frame_times'][-1],
            0.016,
        )  # Last entry should be the last one added

    def test_track_fps_from_event_no_scene(self):
        """Test that tracking without a scene doesn't crash."""
        self.instance._current_scene = None
        # Should not raise an exception
        self.instance.track_fps_from_event(60.0)

    def test_track_fps_from_event_unlimited_fps(self):
        """Test that frame times are not tracked when target FPS is 0 (unlimited)."""
        self.instance._target_fps = 0.0
        self.instance.track_fps_from_event(60.0, 0.016)

        scene_data = self.instance._scene_data['TestScene']
        assert (
            list(scene_data['frame_times']) == []
        )  # Should not track frame times for unlimited FPS


class TestSpareTimeCalculation:
    """Test spare time calculations."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_get_spare_time_stats_unlimited_fps(self):
        """Test spare time stats for unlimited FPS."""
        self.instance._target_fps = 0.0
        result = self.instance.get_spare_time_stats()

        assert result == {'message': 'Not applicable for unlimited FPS'}

    def test_get_spare_time_stats_no_data(self):
        """Test spare time stats with no frame time data."""
        self.instance._target_fps = 60.0
        result = self.instance.get_spare_time_stats()

        assert result == {'message': 'No frame time data available'}

    def test_get_spare_time_stats_global(self):
        """Test global spare time calculation."""
        self.instance._target_fps = 60.0

        # Add data for multiple scenes
        self.instance.set_current_scene('Scene1')
        self.instance.track_fps_from_event(60.0, 0.010)  # 10ms processing time

        self.instance.set_current_scene('Scene2')
        self.instance.track_fps_from_event(60.0, 0.020)  # 20ms processing time

        result = self.instance.get_spare_time_stats()

        # Target frame time at 60 FPS = 16.67ms
        # Average frame time = (10 + 20) / 2 = 15ms
        # Spare time = 16.67 - 15 = 1.67ms
        # Spare capacity = 1.67 / 16.67 = 10%
        # Could tick = 16.67 / 15 = 1.11x faster

        assert result['target_frame_time_ms'] == pytest.approx(16.67, rel=1e-2)
        assert result['avg_frame_time_ms'] == pytest.approx(15.0, rel=1e-2)
        assert result['avg_spare_time_ms'] == pytest.approx(1.67, rel=1e-2)
        assert result['spare_capacity_percent'] == pytest.approx(10.0, rel=1e-2)
        assert result['could_tick_times'] == pytest.approx(1.11, rel=1e-2)

    def test_get_spare_time_stats_per_scene(self):
        """Test per-scene spare time calculation."""
        self.instance._target_fps = 60.0

        # Add data for Scene1
        self.instance.set_current_scene('Scene1')
        self.instance.track_fps_from_event(60.0, 0.010)  # 10ms processing time

        # Add data for Scene2
        self.instance.set_current_scene('Scene2')
        self.instance.track_fps_from_event(60.0, 0.020)  # 20ms processing time

        # Test Scene1
        result1 = self.instance.get_spare_time_stats('Scene1')
        assert result1['avg_frame_time_ms'] == pytest.approx(10.0, rel=1e-2)
        assert result1['spare_capacity_percent'] == pytest.approx(
            40.0,
            rel=1e-2,
        )  # (16.67-10)/16.67

        # Test Scene2
        result2 = self.instance.get_spare_time_stats('Scene2')
        assert result2['avg_frame_time_ms'] == pytest.approx(20.0, rel=1e-2)
        assert result2['spare_capacity_percent'] == pytest.approx(
            -20.0,
            rel=1e-2,
        )  # (16.67-20)/16.67

    def test_get_spare_time_stats_scene_not_found(self):
        """Test spare time stats for non-existent scene."""
        self.instance._target_fps = 60.0
        result = self.instance.get_spare_time_stats('NonExistentScene')

        assert result == {'message': 'Scene not found'}

    def test_get_spare_time_stats_scene_no_data(self):
        """Test spare time stats for scene with no frame time data."""
        self.instance._target_fps = 60.0
        self.instance.set_current_scene('EmptyScene')
        # Don't add any frame time data

        result = self.instance.get_spare_time_stats('EmptyScene')
        assert result == {'message': 'No frame time data for this scene'}


class TestPerformanceGrading:
    """Test performance grading system."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_performance_grade_unlimited_fps(self):
        """Test performance grading for unlimited FPS (target_fps = 0)."""
        self.instance._target_fps = 0.0

        # Test various FPS values with corrected grading
        assert (
            self.instance._calculate_performance_grade([30.0]) == 'C (Fair)'
        )  # 30 FPS is playable but not great
        assert self.instance._calculate_performance_grade([60.0]) == 'A (Very Good)'
        assert self.instance._calculate_performance_grade([120.0]) == 'A+ (Excellent)'
        assert self.instance._calculate_performance_grade([240.0]) == 'A+ (Excellent)'

    def test_performance_grade_capped_fps_achieving_target(self):
        """Test performance grading when achieving target FPS."""
        self.instance._target_fps = 60.0

        # Test achieving target FPS (should get good grade)
        assert (
            self.instance._calculate_performance_grade([60.0]) == 'A+ (Excellent)'
        )  # 100% of target
        assert (
            self.instance._calculate_performance_grade([57.0]) == 'A (Very Good)'
        )  # 95% of target
        assert self.instance._calculate_performance_grade([54.0]) == 'B (Good)'  # 90% of target
        assert self.instance._calculate_performance_grade([48.0]) == 'C (Fair)'  # 80% of target
        assert self.instance._calculate_performance_grade([42.0]) == 'D (Poor)'  # 70% of target
        assert (
            self.instance._calculate_performance_grade([36.0]) == 'F (Very Poor)'
        )  # 60% of target

    def test_performance_grade_capped_fps_exceeding_target(self):
        """Test performance grading when exceeding target FPS."""
        self.instance._target_fps = 60.0

        # Exceeding target should get excellent grade
        assert (
            self.instance._calculate_performance_grade([120.0]) == 'A+ (Excellent)'
        )  # 200% of target
        assert (
            self.instance._calculate_performance_grade([240.0]) == 'A+ (Excellent)'
        )  # 400% of target


class TestStatisticalAggregates:
    """get_statistical_aggregates: mean, spread and a 99.999% confidence interval of the FPS."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_unknown_scene(self):
        """A scene that never ran answers 'Scene not found'."""
        assert self.instance.get_statistical_aggregates(scene_name='Nowhere') == {
            'message': 'Scene not found'
        }

    def test_no_scenes_have_no_data(self):
        """Across no scenes at all there is nothing to aggregate."""
        assert self.instance.get_statistical_aggregates() == {'message': 'No data available'}

    def test_a_scene_without_samples_has_no_data(self):
        """A scene set current but given no FPS samples has no data."""
        self.instance.set_current_scene('Empty')

        assert self.instance.get_statistical_aggregates(scene_name='Empty') == {
            'message': 'No data available'
        }

    def test_one_scenes_aggregates(self):
        """Samples 50 and 70: mean 60, deviation 10, interval 60 +/- 4.265 * 10 / sqrt(2)."""
        self.instance.set_current_scene('Level')
        self.instance.track_fps_from_event(50.0)
        self.instance.track_fps_from_event(70.0)

        aggregates = self.instance.get_statistical_aggregates(scene_name='Level')

        margin_of_error = 4.265 * 10.0 / math.sqrt(2)
        assert aggregates['total_samples'] == 2
        assert aggregates['mean_fps'] == pytest.approx(60.0)
        assert aggregates['std_deviation'] == pytest.approx(10.0)
        assert aggregates['min_fps'] == 50.0
        assert aggregates['max_fps'] == 70.0
        assert aggregates['confidence_interval_99_999'] == pytest.approx({
            'lower': 60.0 - margin_of_error,
            'upper': 60.0 + margin_of_error,
            'margin_of_error': margin_of_error,
        })
        assert aggregates['reliability_level'] == 'Limited (2 samples)'

    def test_constant_fps_has_no_spread(self):
        """Identical samples have zero deviation and a zero-width interval."""
        self.instance.set_current_scene('Steady')
        for _sample in range(3):
            self.instance.track_fps_from_event(60.0)

        aggregates = self.instance.get_statistical_aggregates(scene_name='Steady')

        assert aggregates['std_deviation'] == 0.0
        assert aggregates['confidence_interval_99_999']['margin_of_error'] == 0.0

    def test_all_scenes_are_combined(self):
        """Without a scene name the samples of every scene are aggregated together."""
        self.instance.set_current_scene('First')
        self.instance.track_fps_from_event(30.0)
        self.instance.set_current_scene('Second')
        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(90.0)

        aggregates = self.instance.get_statistical_aggregates()

        assert aggregates['total_samples'] == 3
        assert aggregates['mean_fps'] == pytest.approx(60.0)
        assert aggregates['min_fps'] == 30.0
        assert aggregates['max_fps'] == 90.0

    def test_a_million_samples_earn_the_five_nines_label(self):
        """At RELIABILITY_MIN_SAMPLES samples the result is labelled 5 9s."""
        self.instance.set_current_scene('Long')
        statistical_aggregates = self.instance._scene_data['Long']['statistical_aggregates']
        statistical_aggregates.update(
            total_samples=1_000_000,
            sum_fps=60.0 * 1_000_000,
            sum_squared_fps=3600.0 * 1_000_000,
            min_fps=60.0,
            max_fps=60.0,
        )

        aggregates = self.instance.get_statistical_aggregates(scene_name='Long')

        assert aggregates['reliability_level'] == '5 9s (99.999%)'


class TestPerformanceStats:
    """get_performance_stats needs a few frame times before it measures anything."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_too_little_history_answers_the_default(self):
        """With fewer than two frame times the stats are the 60 FPS default and no history."""
        self.instance.get_adaptive_dt(0.02)

        assert self.instance.get_performance_stats() == {'avg_fps': 60.0, 'history_length': 0}

    def test_two_frame_times_give_their_average_fps(self):
        """Frame times 0.02 s and 0.03 s average 0.025 s: 40 FPS."""
        self.instance.get_adaptive_dt(0.02)
        self.instance.get_adaptive_dt(0.03)

        stats = self.instance.get_performance_stats()

        assert stats['avg_fps'] == pytest.approx(40.0)
        assert stats['history_length'] == 2


class TestShutdownReporting:
    """Test shutdown reporting functionality."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_get_shutdown_stats_no_data(self):
        """Test shutdown stats with no data."""
        result = self.instance.get_shutdown_stats()
        assert result == {'message': 'Not enough data'}

    def test_get_shutdown_stats_with_data(self):
        """Test shutdown stats with FPS data."""
        # Add data for multiple scenes
        self.instance.set_current_scene('Scene1')
        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(61.0)

        self.instance.set_current_scene('Scene2')
        self.instance.track_fps_from_event(30.0)
        self.instance.track_fps_from_event(31.0)

        result = self.instance.get_shutdown_stats()

        # Should aggregate data from all scenes
        assert result['total_frames'] == 4
        assert result['avg_fps'] == pytest.approx(45.5, rel=1e-2)  # (60+61+30+31)/4
        assert math.isclose(result['min_fps'], 30.0)
        assert math.isclose(result['max_fps'], 61.0)
        assert math.isclose(result['median_fps'], 45.5)  # True median of [30, 31, 60, 61]
        assert 'performance_grade' in result
        assert 'fps_histogram' in result

    def test_get_per_scene_shutdown_stats(self):
        """Test per-scene shutdown stats."""
        # Add data for multiple scenes
        self.instance.set_current_scene('Scene1')
        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(61.0)

        self.instance.set_current_scene('Scene2')
        self.instance.track_fps_from_event(30.0)

        result = self.instance.get_per_scene_shutdown_stats()

        assert 'Scene1' in result
        assert 'Scene2' in result

        # Scene1 should have 2 frames
        assert result['Scene1']['total_frames'] == 2
        assert result['Scene1']['avg_fps'] == pytest.approx(60.5, rel=1e-2)

        # Scene2 should have 1 frame
        assert result['Scene2']['total_frames'] == 1
        assert math.isclose(result['Scene2']['avg_fps'], 30.0)

    def test_get_per_scene_shutdown_stats_filters_unknown(self):
        """Test that per-scene stats filter out Unknown scenes."""
        # Add data for a scene named "Unknown"
        self.instance.set_current_scene('Unknown')
        self.instance.track_fps_from_event(60.0)

        result = self.instance.get_per_scene_shutdown_stats()

        # Should not include Unknown scene
        assert 'Unknown' not in result
        assert result == {}

    def _feed_distinct_frames(self, frame_count):
        """Feed frame_count distinct FPS values so trimming is observable."""
        self.instance.set_current_scene('TrimScene')
        for frame_index in range(frame_count):
            self.instance.track_fps_from_event(100.0 + frame_index)

    def test_trim_label_pluralizes_single_frame(self):
        """A single recorded frame reads 'dropped 0 of 1 frame'."""
        self.instance.set_trim_percent(5.0)
        self._feed_distinct_frames(1)
        stats = self.instance.get_shutdown_stats()
        assert self.instance._build_trim_label(stats=stats) == (
            'dropped 0 of 1 frame; the 5.0% setting needs at least 20'
        )

    def test_trim_label_pluralizes_multiple_frames_per_end(self):
        """Two frames dropped from each end reads 'dropped 2 frames from each end'."""
        self.instance.set_trim_percent(5.0)
        self._feed_distinct_frames(40)
        stats = self.instance.get_shutdown_stats()
        assert self.instance._build_trim_label(stats=stats) == (
            'dropped 2 frames from each end (5.0%)'
        )

    def test_trim_label_zero_percent_says_no_trimming(self):
        """A trim percent of 0 is labelled as no trimming."""
        self.instance.set_trim_percent(0.0)
        self._feed_distinct_frames(10)
        stats = self.instance.get_shutdown_stats()
        assert self.instance._build_trim_label(stats=stats) == 'no trimming'

    def test_trim_label_ten_frames_at_five_percent_explains_nothing_dropped(self):
        """10 frames at 5% drops nothing and the label says why."""
        self.instance.set_trim_percent(5.0)
        self._feed_distinct_frames(10)
        stats = self.instance.get_shutdown_stats()
        assert stats['trimmed_frames'] == 10
        assert self.instance._build_trim_label(stats=stats) == (
            'dropped 0 of 10 frames; the 5.0% setting needs at least 20'
        )

    def test_trim_label_boundary_at_minimum_frames(self):
        """19 frames drop nothing at 5%, 20 frames drop one from each end."""
        self.instance.set_trim_percent(5.0)
        self._feed_distinct_frames(19)
        stats = self.instance.get_shutdown_stats()
        assert stats['trimmed_frames'] == 19
        assert self.instance._build_trim_label(stats=stats) == (
            'dropped 0 of 19 frames; the 5.0% setting needs at least 20'
        )

        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()
        self.instance.set_trim_percent(5.0)
        self._feed_distinct_frames(20)
        stats = self.instance.get_shutdown_stats()
        assert stats['trimmed_frames'] == 18
        assert self.instance._build_trim_label(stats=stats) == (
            'dropped 1 frame from each end (5.0%)'
        )

    def test_trim_label_reported_in_log_output(self, caplog):
        """The shutdown log prints the honest label, not a claim of dropped frames."""
        self.instance.set_trim_percent(5.0)
        self._feed_distinct_frames(10)
        stats = self.instance.get_shutdown_stats()
        with caplog.at_level('INFO'):
            self.instance._log_fps_stats(stats=stats, spare_stats={'message': 'none'})
        assert 'dropped 0 of 10 frames; the 5.0% setting needs at least 20' in caplog.text
        assert 'dropped top/bottom' not in caplog.text


class TestShutdownStatistics:
    """Test shutdown statistics, trimming, medians and 1% lows."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()
        self.instance.set_trim_percent(0.0)

    def _feed(self, scene_name, fps_values):
        """Record fps_values for scene_name."""
        self.instance.set_current_scene(scene_name)
        for fps in fps_values:
            self.instance.track_fps_from_event(fps)

    # 1. The user's report
    def test_user_report_nine_repeated_samples_and_one_stale(self):
        """9 x 10000/41 and 1 x 10000/19 gives median == minimum, which is correct for that data."""
        self.instance.set_trim_percent(5.0)
        self._feed('PauseScene', [10000 / 41] * 9 + [10000 / 19])

        stats = self.instance.get_shutdown_stats()

        assert stats['total_frames'] == 10
        assert stats['trimmed_frames'] == 10
        assert stats['median_fps'] == pytest.approx(243.9, abs=0.05)
        assert stats['min_fps'] == pytest.approx(243.9, abs=0.05)
        assert stats['avg_fps'] == pytest.approx(272.1, abs=0.05)
        assert stats['fps_bucket_width'] == pytest.approx((10000 / 19 - 10000 / 41) / 10)
        assert stats['fps_histogram'] == {
            '244-271': 9,
            '272-299': 0,
            '300-328': 0,
            '329-356': 0,
            '357-384': 0,
            '385-412': 0,
            '413-441': 0,
            '442-469': 0,
            '470-497': 0,
            '498-526': 1,
        }

    # 4. Trimming
    def test_trim_boundaries_at_five_percent(self):
        """19 frames drop 0; 20 frames drop 1 from each end."""
        self.instance.set_trim_percent(5.0)
        self._feed('Scene', [100.0 + index for index in range(19)])
        assert self.instance.get_shutdown_stats()['trimmed_frames'] == 19

        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()
        self.instance.set_trim_percent(5.0)
        self._feed('Scene', [100.0 + index for index in range(20)])
        stats = self.instance.get_shutdown_stats()
        assert stats['trimmed_frames'] == 18
        assert stats['avg_fps'] == pytest.approx(109.5)

    def test_trim_zero_keeps_all_frames(self):
        """Trim 0 keeps every frame."""
        self._feed('Scene', [100.0 + index for index in range(50)])
        assert self.instance.get_shutdown_stats()['trimmed_frames'] == 50

    def test_trim_percent_clamped_below_fifty(self):
        """Percentages of 50 or more clamp to 49.9 so some data always remains."""
        self.instance.set_trim_percent(75.0)
        assert self.instance._trim_percent == pytest.approx(49.9)
        self.instance.set_trim_percent(-5.0)
        assert self.instance._trim_percent == 0.0

    def test_extreme_trim_percent_with_three_frames_keeps_the_middle_one(self):
        """At 49.9% three frames drop one from each end and keep the median frame."""
        self.instance.set_trim_percent(75.0)
        self._feed('Scene', [100.0, 200.0, 300.0])

        stats = self.instance.get_shutdown_stats()

        assert stats['trimmed_frames'] == 1
        assert stats['median_fps'] == 200.0

    # 5. Degenerate data
    def test_empty_history(self):
        """No samples at all reports 'Not enough data'."""
        assert self.instance.get_shutdown_stats() == {'message': 'Not enough data'}

    def test_only_non_positive_fps(self):
        """Only fps <= 0 reports no valid data, globally and per scene."""
        self._feed('Scene', [0.0, -5.0])

        assert self.instance.get_shutdown_stats() == {'message': 'No valid FPS data collected'}
        assert self.instance.get_per_scene_shutdown_stats()['Scene'] == {
            'message': 'No valid FPS data collected',
        }

    def test_single_frame(self):
        """A single frame is its own minimum, median, maximum and 1% low."""
        self._feed('Scene', [123.5])

        stats = self.instance.get_shutdown_stats()

        assert stats['min_fps'] == stats['median_fps'] == stats['max_fps'] == 123.5
        assert stats['one_percent_low_fps'] == 123.5
        assert stats['fps_histogram'] == {'124': 1}
        assert stats['fps_bucket_width'] == 0.0

    def test_unknown_scene_excluded_from_per_scene_stats(self):
        """The 'Unknown' scene never appears in per-scene stats."""
        self._feed('Unknown', [60.0])
        self._feed('Real', [61.0])

        assert list(self.instance.get_per_scene_shutdown_stats()) == ['Real']

    # Discrepancy fixes: median, min/max, 1% low
    @pytest.mark.parametrize(
        ('values', 'expected_median'),
        [([300.0, 100.0, 200.0], 200.0), ([100.0, 200.0, 300.0, 400.0], 250.0), ([77.0], 77.0)],
    )
    def test_median_is_true_median(self, values, expected_median):
        """Odd count: middle value; even count: mean of the two middle values."""
        self._feed('Scene', values)

        assert self.instance.get_shutdown_stats()['median_fps'] == expected_median
        assert self.instance.get_per_scene_shutdown_stats()['Scene']['median_fps'] == (
            expected_median
        )

    def test_min_and_max_come_from_all_frames_and_agree_globally_and_per_scene(self):
        """The worst frame inside the trimmed tail is still the minimum, in both reports."""
        self.instance.set_trim_percent(5.0)
        self._feed('Scene', [5.0] * 2 + [100.0 + index for index in range(36)] + [900.0] * 2)

        global_stats = self.instance.get_shutdown_stats()
        scene_stats = self.instance.get_per_scene_shutdown_stats()['Scene']

        assert global_stats['trimmed_frames'] == 36
        assert global_stats['min_fps'] == scene_stats['min_fps'] == 5.0
        assert global_stats['max_fps'] == scene_stats['max_fps'] == 900.0
        assert global_stats == scene_stats

    @pytest.mark.parametrize(
        ('frame_count', 'slowest_count'),
        [(1, 1), (100, 1), (101, 2), (250, 3)],
    )
    def test_one_percent_low_is_mean_of_slowest_frames(self, frame_count, slowest_count):
        """1% low is the mean of the slowest max(1, ceil(1%)) of all valid frames."""
        values = [float(100 + index) for index in range(frame_count)]
        self._feed('Scene', values)

        stats = self.instance.get_shutdown_stats()

        expected = sum(sorted(values)[:slowest_count]) / slowest_count
        assert stats['one_percent_low_fps'] == pytest.approx(expected)
        assert stats['min_fps'] <= stats['one_percent_low_fps'] <= stats['median_fps']
        assert self.instance.get_per_scene_shutdown_stats()['Scene']['one_percent_low_fps'] == (
            pytest.approx(expected)
        )

    # Deque-backed histories
    def test_histories_are_bounded_and_keep_newest_samples(self):
        """History never exceeds maxlen and keeps the newest samples."""
        self.instance._target_fps = 60.0
        self.instance.set_current_scene('Scene')
        for index in range(100_005):
            self.instance.track_fps_from_event(float(index + 1), 0.001 * (index % 7 + 1))
            self.instance._track_fps(float(index + 1))

        scene_data = self.instance._scene_data['Scene']
        assert len(scene_data['fps_history']) == 100_000
        assert scene_data['fps_history'][0] == 6.0
        assert scene_data['fps_history'][-1] == 100_005.0
        assert len(scene_data['frame_times']) == MAX_SCENE_FRAME_TIME_HISTORY
        assert len(scene_data['statistical_aggregates']['sampled_fps_history']) == 10_000
        assert len(self.instance._fps_history) == FPS_HISTORY_MAX_SIZE
        assert self.instance._fps_history[0] == 100_005.0 - FPS_HISTORY_MAX_SIZE + 1


class TestHistogramBucketing:
    """Test histogram bucketing, printing and bounded histories."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()
        self.instance.set_trim_percent(0.0)

    def _feed(self, scene_name, fps_values):
        """Record fps_values for scene_name."""
        self.instance.set_current_scene(scene_name)
        for fps in fps_values:
            self.instance.track_fps_from_event(fps)

    # 2. pygame-counter shape versus 1/dt sampling
    def test_pygame_counter_shape_gives_counts_in_multiples_of_ten(self):
        """Values repeated in runs of 10 (pygame's counter) make every bucket a multiple of 10."""
        counter_values = [10000 / 28, 10000 / 26, 10000 / 20]
        repeated = [value for value in counter_values for _ in range(10)]
        self._feed('Scene', repeated)

        stats = self.instance.get_shutdown_stats()

        assert stats['trimmed_frames'] == 30
        assert len(set(repeated)) == 3
        assert all(count % 10 == 0 for count in stats['fps_histogram'].values())
        assert all(
            math.isclose(value * round(10000 / value), 10000, rel_tol=1e-9)
            for value in counter_values
        )

    def test_distinct_dt_samples_give_distinct_values(self, mock_pygame_patches, mocker):
        """With 1/dt sampling distinct dts give distinct FPS and get_fps is never called."""
        from glitchygames.scenes.scene import SceneManager

        self.instance.set_current_scene('Scene')
        mocker.patch('glitchygames.performance.performance_manager', self.instance)
        manager = SceneManager()
        mock_get_fps = mocker.patch.object(manager.clock, 'get_fps', return_value=500.0)

        for frame_index in range(20):
            manager.dt = 1.0 / (400.0 + frame_index * 2.5)
            manager._track_performance(processing_time=0.001)

        recorded = list(self.instance._scene_data['Scene']['fps_history'])
        mock_get_fps.assert_not_called()
        assert len(set(recorded)) == 20
        stats = self.instance.get_shutdown_stats()
        assert sum(stats['fps_histogram'].values()) == 20
        assert not all(count % 10 == 0 for count in stats['fps_histogram'].values())

    # 3. Equal-range bucketing
    def test_histogram_counts_sum_to_trimmed_frames_and_use_trimmed_data(self):
        """Histogram counts sum to trimmed_frames and exclude the trimmed tails."""
        self.instance.set_trim_percent(5.0)
        self._feed(
            'Scene', [1000.0] * 2 + [200.0 + index * 0.1 for index in range(36)] + [10.0] * 2
        )

        stats = self.instance.get_shutdown_stats()

        assert stats['total_frames'] == 40
        assert stats['trimmed_frames'] == 36
        assert sum(stats['fps_histogram'].values()) == 36
        assert stats['fps_bucket_width'] == pytest.approx(0.35)  # 200.0 to 203.5

    def test_spread_data_gets_exactly_ten_buckets(self):
        """Spread data fills ten buckets; min is in the first, max in the last."""
        self._feed('Scene', [100.0 + index * 100 for index in range(11)])  # 100 to 1100

        stats = self.instance.get_shutdown_stats()

        assert stats['fps_histogram_mode'] == 'equal-range'
        assert stats['fps_bucket_width'] == pytest.approx(100.0)
        assert len(stats['fps_histogram']) == HISTOGRAM_BUCKET_COUNT == 10
        counts = list(stats['fps_histogram'].values())
        assert counts[0] == 1
        assert counts[-1] == 2  # 1000.0 is on the last boundary, and the maximum 1100.0 joins it
        assert sum(counts) == 11
        assert list(stats['fps_histogram']) == [
            '100-199',
            '200-299',
            '300-399',
            '400-499',
            '500-599',
            '600-699',
            '700-799',
            '800-899',
            '900-999',
            '1000-1100',
        ]

    def test_value_on_internal_boundary_goes_to_upper_bucket(self):
        """500.0 is the boundary between 400-499 and 500-599 and lands in the upper one."""
        self._feed('Scene', [100.0, 500.0, 1100.0])

        histogram = self.instance.get_shutdown_stats()['fps_histogram']

        assert histogram['100-199'] == 1
        assert histogram['400-499'] == 0
        assert histogram['500-599'] == 1
        assert histogram['1000-1100'] == 1

    @pytest.mark.parametrize(('lowest', 'highest'), [(100.0, 137.0), (0.0, 7.0)])
    def test_every_constructed_boundary_value_lands_in_its_upper_bucket(self, lowest, highest):
        """With non-dyadic widths (3.7, 0.7) boundary values must not fall into the lower bucket."""
        width = (highest - lowest) / HISTOGRAM_BUCKET_COUNT
        boundary_values = [lowest + index * width for index in range(HISTOGRAM_BUCKET_COUNT)]
        counts_by_index, _ = AdaptiveClamping._count_equal_range_buckets(
            sorted([*boundary_values, highest])
        )

        # One value per boundary; the maximum joins the last bucket.
        assert counts_by_index == [1] * (HISTOGRAM_BUCKET_COUNT - 1) + [2]

    def test_identical_values_give_a_single_bucket(self):
        """Equal minimum and maximum collapse to one bucket of width 0."""
        self._feed('Scene', [250.0] * 4)

        stats = self.instance.get_shutdown_stats()

        assert stats['fps_histogram'] == {'250': 4}
        assert stats['fps_bucket_width'] == 0.0

    def test_narrow_spread_merges_buckets_so_labels_stay_unique_and_ascending(self):
        """A 3 FPS spread has sub-1 FPS buckets; colliding rounded labels merge."""
        self._feed('Scene', [244.0, 244.5, 245.0, 245.5, 246.0, 246.5, 247.0, 247.2, 244.1, 246.9])

        stats = self.instance.get_shutdown_stats()
        labels = list(stats['fps_histogram'])

        assert len(labels) == len(set(labels))
        lower_bounds = [int(label.split('-')[0]) for label in labels]
        assert lower_bounds == sorted(set(lower_bounds))
        assert sum(stats['fps_histogram'].values()) == 10
        assert stats['fps_bucket_width'] == pytest.approx(0.32)
        assert len(labels) < HISTOGRAM_BUCKET_COUNT

    def test_buckets_ordered_numerically_across_digit_counts(self):
        """Buckets with 2 and 4 digit bounds are ordered by value, not as strings."""
        self._feed('Scene', [90.0, 345.0, 1000.0])

        labels = list(self.instance.get_shutdown_stats()['fps_histogram'])

        assert labels[0] == '90-180'
        assert labels[-1].endswith('-1000')
        assert labels == sorted(labels, key=lambda label: int(label.split('-')[0]))
        assert sorted(labels) != labels  # string order differs

    def test_fps_bucket_width_reported_per_scene(self):
        """Per-scene stats carry the mode, bucket width and ordered labels."""
        self._feed('Scene', [345.0, 625.0])

        scene_stats = self.instance.get_per_scene_shutdown_stats()['Scene']

        assert scene_stats['fps_histogram_mode'] == 'equal-range'
        assert scene_stats['fps_bucket_width'] == pytest.approx(28.0)
        assert next(iter(scene_stats['fps_histogram'])) == '345-372'
        assert scene_stats == self.instance.get_shutdown_stats()

    def test_reset_recreates_bounded_history(self):
        """reset() keeps the global history bounded."""
        self.instance.reset()

        assert self.instance._fps_history.maxlen == FPS_HISTORY_MAX_SIZE


class TestHistogramModes:
    """Test the target-relative histogram mode, mode switching and the printed histogram."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()
        self.instance.set_trim_percent(0.0)

    def _feed(self, scene_name, fps_values):
        """Record fps_values for scene_name."""
        self.instance.set_current_scene(scene_name)
        for fps in fps_values:
            self.instance.track_fps_from_event(fps)

    # 3b. Target-relative bucketing
    def _target_relative_histogram(self, fps_values, target_fps=60.0):
        """Return the target-relative stats histogram for fps_values."""
        self.instance.set_histogram_mode('target-relative')
        self.instance.set_target_fps(target_fps)
        self._feed('Scene', fps_values)
        return self.instance.get_shutdown_stats()

    @pytest.mark.parametrize(
        ('fps', 'expected_label'),
        [
            (60.0, '>=100% (60+ FPS)'),
            (75.0, '>=100% (60+ FPS)'),
            (59.9, '90-99% (54-59)'),
            (54.0, '90-99% (54-59)'),
            (53.99, '80-89% (48-53)'),
            (6.0, '10-19% (6-11)'),
            (5.9, '<10% (<6)'),
        ],
    )
    def test_target_relative_assigns_frames_by_percentage_of_target(self, fps, expected_label):
        """Frames land in floor(percent / 10) * 10 steps; 100% and above share the top."""
        stats = self._target_relative_histogram([fps])

        assert stats['fps_histogram_mode'] == 'target-relative'
        assert stats['fps_histogram'] == {expected_label: 1}
        assert 'fps_bucket_width' not in stats

    def test_target_relative_lists_only_non_empty_buckets_lowest_fps_first(self):
        """Empty steps are omitted; counts sum to the analyzed frames; top bucket is last."""
        stats = self._target_relative_histogram([75.0, 5.9, 59.9, 60.0, 30.0, 59.0])

        assert list(stats['fps_histogram']) == [
            '<10% (<6)',
            '50-59% (30-35)',
            '90-99% (54-59)',
            '>=100% (60+ FPS)',
        ]
        assert list(stats['fps_histogram'].values()) == [1, 1, 2, 2]
        assert sum(stats['fps_histogram'].values()) == stats['trimmed_frames']

    def test_target_relative_with_no_target_falls_back_to_equal_range(self):
        """An uncapped target (0) reports the equal-range mode actually used."""
        stats = self._target_relative_histogram([100.0, 200.0], target_fps=0.0)

        assert stats['fps_histogram_mode'] == 'equal-range'
        assert stats['fps_bucket_width'] == pytest.approx(10.0)

    def test_set_histogram_mode_accepts_both_modes(self):
        """Both documented values are accepted."""
        self.instance.set_histogram_mode('target-relative')
        assert self.instance._histogram_mode is FpsHistogramMode.TARGET_RELATIVE
        self.instance.set_histogram_mode('equal-range')
        assert self.instance._histogram_mode is FpsHistogramMode.EQUAL_RANGE

    def test_set_histogram_mode_rejects_unknown_values(self):
        """An unknown mode raises ValueError naming the allowed values."""
        with pytest.raises(ValueError, match=r"'equal-range', 'target-relative'"):
            self.instance.set_histogram_mode('logarithmic')

    # 6. Printed histogram
    def _printed_lines(self, mocker):
        """Print the global shutdown histogram with a mocked logger and return its lines."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')
        self.instance._log_fps_histogram(self.instance.get_shutdown_stats())
        return [call.args[0] for call in mock_log.info.call_args_list]

    def test_equal_range_header_and_rows_ascend(self, mocker):
        """The header states the width; rows run from the lowest FPS to the highest."""
        self._feed('Scene', [100.0, 300.0, 1100.0, 1100.0])

        lines = self._printed_lines(mocker)

        assert lines[0] == '\n📊 FPS Distribution (10 equal buckets, 100.0 FPS wide):'
        rows = [line for line in lines if ' frames (' in line]
        assert len(rows) == 10
        assert '100-199 FPS' in rows[0]
        assert '1000-1100 FPS' in rows[-1]
        assert [int(re.search(r'FPS\s+(\d+) frames', row).group(1)) for row in rows] == [
            1,
            0,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
            2,
        ]

    def test_target_relative_header_and_rows(self, mocker):
        """The header names the target; rows run from <10% up to >=100%."""
        self.instance.set_histogram_mode('target-relative')
        self.instance.set_target_fps(60.0)
        self._feed('Scene', [5.0, 60.0, 61.0])

        lines = self._printed_lines(mocker)

        assert lines[0] == '\n📊 FPS Distribution (relative to target 60 FPS):'
        rows = [line for line in lines if ' frames (' in line]
        assert '<10% (<6)' in rows[0]
        assert '>=100% (60+ FPS)' in rows[-1]
        assert 'FPS FPS' not in rows[-1]

    def test_fallback_header_says_no_target_fps_set(self, mocker):
        """Target-relative with no target prints the equal-range header plus the reason."""
        self.instance.set_histogram_mode('target-relative')
        self._feed('Scene', [100.0, 900.0])

        lines = self._printed_lines(mocker)

        assert lines[0] == (
            '\n📊 FPS Distribution (10 equal buckets, 80.0 FPS wide; '
            'no target FPS set for target-relative):'
        )

    def test_header_reports_real_bucket_count_after_merging(self, mocker):
        """A narrow spread merges buckets, so the header must not claim 10 equal buckets."""
        self._feed('Scene', [1.0 + 0.7 * index for index in range(11)])  # 1.0 to 8.0

        lines = self._printed_lines(mocker)

        assert lines[0] == (
            '\n📊 FPS Distribution (7 buckets after merging equal labels, 0.7 FPS wide):'
        )

    def test_target_relative_small_target_uses_one_decimal_bounds(self):
        """Target 5 gives distinct tenths-of-an-FPS ranges instead of colliding '1-1' labels."""
        stats = self._target_relative_histogram([0.4, 0.5, 0.9, 1.0, 1.4, 2.0, 5.0], target_fps=5.0)

        assert stats['fps_histogram'] == {
            '<10% (<0.5)': 1,
            '10-19% (0.5-0.9)': 2,
            '20-29% (1.0-1.4)': 2,
            '40-49% (2.0-2.4)': 1,
            '>=100% (5+ FPS)': 1,
        }

    def test_target_relative_fractional_target_uses_exact_target_for_top_bucket(self):
        """Target 59.94 labels the top bucket '59.94+' and uses one-decimal bounds."""
        stats = self._target_relative_histogram([5.0, 53.9, 53.95, 59.94], target_fps=59.94)

        assert stats['fps_histogram'] == {
            '<10% (<6.0)': 1,
            '80-89% (48.0-53.9)': 1,
            '90-99% (54.0-59.9)': 1,
            '>=100% (59.94+ FPS)': 1,
        }

    def test_histogram_percentages_use_trimmed_frames(self, mocker):
        """Percentages are count / trimmed_frames."""
        self._feed('Scene', [100.0] * 9 + [200.0] * 12)

        lines = self._printed_lines(mocker)

        percentages = [
            float(re.search(r'\(\s*([\d.]+)%\)', line).group(1))
            for line in lines
            if ' frames (' in line
        ]
        assert percentages[0] == pytest.approx(42.9, abs=0.05)
        assert percentages[-1] == pytest.approx(57.1, abs=0.05)

    def test_histogram_label_column_fits_widest_label(self, mocker):
        """Labels are never truncated and the label column is aligned."""
        self._feed('Scene', [90.0, 345.0, 1000.0])

        rows = [line for line in self._printed_lines(mocker) if ' frames (' in line]

        assert '90-180 FPS' in rows[0]
        assert '909-1000 FPS' in rows[-1]
        assert len({row.index(' FPS') for row in rows}) == 1


class TestAdaptiveDeltaTime:
    """Test the adaptive delta time adjustment."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_get_adaptive_dt_insufficient_history(self):
        """Test adaptive DT with insufficient history."""
        # With less than 10 frames, should return original dt
        result = self.instance.get_adaptive_dt(0.016)
        assert math.isclose(result, 0.016)

    def test_get_adaptive_dt_sufficient_history(self):
        """Test adaptive DT with sufficient history."""
        # Add 10 frames of history
        for i in range(10):
            self.instance.get_adaptive_dt(0.016)  # 60 FPS

        # Should now apply smoothing
        result = self.instance.get_adaptive_dt(0.016)

        # Should be smoothed towards target (1/60 = 0.01667)
        assert not math.isclose(result, 0.016)  # Should be adjusted
        assert result > 0.016  # Should be closer to target

    def test_get_adaptive_dt_history_limit(self):
        """Test that dt history is limited to 60 entries."""
        # Add 61 frames
        for i in range(61):
            self.instance.get_adaptive_dt(0.016)

        assert len(self.instance._dt_history) == 60

    def test_get_adaptive_dt_logging_interval(self, mocker):
        """Test that performance adjustments are logged at the correct interval."""
        # Start with time 0
        mock_time = mocker.patch('time.perf_counter', return_value=0.0)

        # Add sufficient history with a very large dt to ensure significant adjustment
        for i in range(10):
            self.instance.get_adaptive_dt(1.0)  # Very large dt to ensure significant adjustment

        # Reset the last log time to ensure we can log
        self.instance._last_performance_log_time = 0.0

        # Temporarily lower the logging threshold to ensure we trigger logging
        mocker.patch.object(self.instance, '_fps_log_interval_ms', 0.0)  # No interval restriction
        mock_log_info = mocker.patch('glitchygames.performance.adaptive_clamping.LOG.info')
        # Manually set a large adjustment to ensure logging
        adjusted_dt = self.instance.get_adaptive_dt(1.0)
        # Check if the adjustment is significant enough
        if abs(adjusted_dt - 1.0) > 0.0001:
            mock_log_info.assert_called_once()
        else:
            # If adjustment is too small, just verify the method works
            assert not math.isclose(adjusted_dt, 1.0)  # Should be adjusted


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_negative_fps_values(self):
        """Test handling of negative FPS values."""
        self.instance.set_current_scene('TestScene')
        self.instance.track_fps_from_event(-1.0)

        # Should still track the value
        scene_data = self.instance._scene_data['TestScene']
        assert list(scene_data['fps_history']) == [-1.0]
        assert scene_data['fps_histogram'][-1] == 1

    def test_zero_fps_values(self):
        """Test handling of zero FPS values."""
        self.instance.set_current_scene('TestScene')
        self.instance.track_fps_from_event(0.0)

        # Should still track the value
        scene_data = self.instance._scene_data['TestScene']
        assert list(scene_data['fps_history']) == [0.0]
        assert scene_data['fps_histogram'][0] == 1

    def test_very_large_fps_values(self):
        """Test handling of very large FPS values."""
        self.instance.set_current_scene('TestScene')
        self.instance.track_fps_from_event(10000.0)

        # Should still track the value
        scene_data = self.instance._scene_data['TestScene']
        assert list(scene_data['fps_history']) == [10000.0]
        assert scene_data['fps_histogram'][10000] == 1

    def test_negative_frame_times(self):
        """Test handling of negative frame times."""
        self.instance._target_fps = 60.0
        self.instance.set_current_scene('TestScene')
        self.instance.track_fps_from_event(60.0, -0.016)

        # Should still track the value
        scene_data = self.instance._scene_data['TestScene']
        assert list(scene_data['frame_times']) == [-0.016]

    def test_zero_frame_times(self):
        """Test handling of zero frame times."""
        self.instance._target_fps = 60.0
        self.instance.set_current_scene('TestScene')
        self.instance.track_fps_from_event(60.0, 0.0)

        # Should still track the value
        scene_data = self.instance._scene_data['TestScene']
        assert list(scene_data['frame_times']) == [0.0]


class TestPerformanceManagerGlobal:
    """Test the global performance_manager instance."""

    def test_performance_manager_is_singleton(self):
        """Test that performance_manager is a singleton."""
        # Test that multiple calls to AdaptiveClamping() return the same instance
        instance1 = AdaptiveClamping()
        instance2 = AdaptiveClamping()
        instance3 = AdaptiveClamping()

        # All instances should be the same object
        assert instance1 is instance2
        assert instance2 is instance3
        assert instance1 is instance3

        # Test that the global performance_manager is also a singleton
        from glitchygames.performance import performance_manager

        assert performance_manager is not None
        assert hasattr(performance_manager, '_initialized')

    def test_performance_manager_initialized(self):
        """Test that performance_manager is properly initialized."""
        from glitchygames.performance import performance_manager

        assert performance_manager._initialized is True
        assert hasattr(performance_manager, '_dt_history')
        assert hasattr(performance_manager, '_scene_data')
        assert hasattr(performance_manager, '_current_scene')
        assert hasattr(performance_manager, '_target_fps')
