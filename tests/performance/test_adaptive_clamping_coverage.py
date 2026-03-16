"""Additional tests for adaptive clamping to increase coverage.

Targets uncovered lines in get_statistical_aggregates, set_trim_percent,
get_performance_stats, get_shutdown_stats, get_per_scene_shutdown_stats,
_log_fps_stats, _log_fps_histogram, print_shutdown_report,
print_per_scene_shutdown_report, _track_fps, and reset.
"""

import math

import pytest

from glitchygames.performance.adaptive_clamping import AdaptiveClamping


class TestGetStatisticalAggregates:
    """Test get_statistical_aggregates with various scenarios."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_specific_scene_not_found(self):
        """Test requesting stats for a scene that does not exist."""
        result = self.instance.get_statistical_aggregates(scene_name='NonExistent')
        assert result == {'message': 'Scene not found'}

    def test_specific_scene_no_data(self):
        """Test requesting stats for a scene with no samples."""
        self.instance.set_current_scene('EmptyScene')
        result = self.instance.get_statistical_aggregates(scene_name='EmptyScene')
        assert result == {'message': 'No data available'}

    def test_specific_scene_with_data(self):
        """Test requesting stats for a scene with tracked FPS data."""
        self.instance.set_current_scene('GameScene')
        for _ in range(20):
            self.instance.track_fps_from_event(60.0)

        result = self.instance.get_statistical_aggregates(scene_name='GameScene')

        assert result['total_samples'] == 20
        assert math.isclose(result['mean_fps'], 60.0)
        assert math.isclose(result['std_deviation'], 0.0, abs_tol=1e-9)
        assert math.isclose(result['min_fps'], 60.0)
        assert math.isclose(result['max_fps'], 60.0)
        assert 'confidence_interval_99_999' in result
        assert 'Limited' in result['reliability_level']

    def test_aggregate_all_scenes_no_scenes(self):
        """Test aggregating stats when no scenes exist."""
        result = self.instance.get_statistical_aggregates(scene_name=None)
        assert result == {'message': 'No data available'}

    def test_aggregate_all_scenes_with_data(self):
        """Test aggregating stats across multiple scenes."""
        self.instance.set_current_scene('Scene1')
        for _ in range(10):
            self.instance.track_fps_from_event(60.0)

        self.instance.set_current_scene('Scene2')
        for _ in range(10):
            self.instance.track_fps_from_event(30.0)

        result = self.instance.get_statistical_aggregates(scene_name=None)

        assert result['total_samples'] == 20
        assert math.isclose(result['mean_fps'], 45.0)
        assert math.isclose(result['min_fps'], 30.0)
        assert math.isclose(result['max_fps'], 60.0)
        assert result['std_deviation'] > 0
        assert 'confidence_interval_99_999' in result
        confidence = result['confidence_interval_99_999']
        assert confidence['lower'] < result['mean_fps']
        assert confidence['upper'] > result['mean_fps']
        assert confidence['margin_of_error'] > 0

    def test_aggregate_all_scenes_with_empty_scenes(self):
        """Test aggregation when some scenes have no data."""
        self.instance.set_current_scene('EmptyScene')
        # Don't add any FPS data

        self.instance.set_current_scene('ActiveScene')
        for _ in range(5):
            self.instance.track_fps_from_event(120.0)

        result = self.instance.get_statistical_aggregates(scene_name=None)

        assert result['total_samples'] == 5
        assert math.isclose(result['mean_fps'], 120.0)


class TestSetTrimPercent:
    """Test set_trim_percent edge cases."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_negative_value_clamps_to_zero(self):
        """Test that negative values are clamped to 0."""
        self.instance.set_trim_percent(-5.0)
        assert math.isclose(self.instance._trim_percent, 0.0)

    def test_large_negative_value_clamps_to_zero(self):
        """Test that large negative values are clamped to 0."""
        self.instance.set_trim_percent(-100.0)
        assert math.isclose(self.instance._trim_percent, 0.0)

    def test_value_at_max_clamps_to_49_9(self):
        """Test that value equal to MAX_TRIM_PERCENT (50) clamps to 49.9."""
        self.instance.set_trim_percent(50.0)
        assert math.isclose(self.instance._trim_percent, 49.9)

    def test_value_above_max_clamps_to_49_9(self):
        """Test that value above MAX_TRIM_PERCENT clamps to 49.9."""
        self.instance.set_trim_percent(99.0)
        assert math.isclose(self.instance._trim_percent, 49.9)

    def test_valid_value_is_accepted(self):
        """Test that a valid value within range is accepted."""
        self.instance.set_trim_percent(25.0)
        assert math.isclose(self.instance._trim_percent, 25.0)

    def test_zero_is_accepted(self):
        """Test that zero disables trimming."""
        self.instance.set_trim_percent(0.0)
        assert math.isclose(self.instance._trim_percent, 0.0)


class TestGetPerformanceStats:
    """Test get_performance_stats with various dt history sizes."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_fewer_than_two_dt_entries(self):
        """Test with fewer than MIN_DT_HISTORY_FOR_STATS entries."""
        self.instance._dt_history = [0.016]
        result = self.instance.get_performance_stats()

        assert math.isclose(result['avg_fps'], 60.0)
        assert result['history_length'] == 0

    def test_empty_dt_history(self):
        """Test with no dt entries."""
        result = self.instance.get_performance_stats()

        assert math.isclose(result['avg_fps'], 60.0)
        assert result['history_length'] == 0

    def test_two_dt_entries(self):
        """Test with exactly MIN_DT_HISTORY_FOR_STATS entries."""
        self.instance._dt_history = [0.016, 0.017]
        result = self.instance.get_performance_stats()

        expected_avg_dt = (0.016 + 0.017) / 2
        expected_avg_fps = 1.0 / expected_avg_dt

        assert math.isclose(result['avg_fps'], expected_avg_fps, rel_tol=1e-3)
        assert result['history_length'] == 2
        assert result['recent_dt'] == [0.016, 0.017]

    def test_five_or_more_dt_entries_recent_dt_slice(self):
        """Test that recent_dt returns last 5 entries when history has >= 5."""
        self.instance._dt_history = [0.010, 0.011, 0.012, 0.013, 0.014, 0.015]
        result = self.instance.get_performance_stats()

        assert result['history_length'] == 6
        assert result['recent_dt'] == [0.011, 0.012, 0.013, 0.014, 0.015]

    def test_exactly_five_dt_entries(self):
        """Test with exactly RECENT_DT_SAMPLE_COUNT entries."""
        self.instance._dt_history = [0.016, 0.017, 0.018, 0.019, 0.020]
        result = self.instance.get_performance_stats()

        assert result['history_length'] == 5
        assert result['recent_dt'] == [0.016, 0.017, 0.018, 0.019, 0.020]

    def test_three_dt_entries_fewer_than_five(self):
        """Test that recent_dt returns full history when < 5 entries."""
        self.instance._dt_history = [0.016, 0.017, 0.018]
        result = self.instance.get_performance_stats()

        assert result['history_length'] == 3
        assert result['recent_dt'] == [0.016, 0.017, 0.018]

    def test_zero_avg_dt_returns_default_fps(self):
        """Test that zero avg dt produces default 60.0 FPS."""
        self.instance._dt_history = [0.0, 0.0]
        result = self.instance.get_performance_stats()

        assert math.isclose(result['avg_fps'], 60.0)


class TestTrackFps:
    """Test the _track_fps method."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()
        # _track_fps uses self._fps_history which is not initialized by __init__
        # It is set by reset(), so we need to initialize it manually
        self.instance._fps_history = []

    def test_track_fps_appends_value(self):
        """Test that _track_fps appends FPS to history."""
        self.instance._track_fps(60.0)
        assert self.instance._fps_history == [60.0]

    def test_track_fps_respects_history_limit(self):
        """Test that _track_fps limits history to FPS_HISTORY_MAX_SIZE."""
        for i in range(10001):
            self.instance._track_fps(float(i))

        assert len(self.instance._fps_history) == 10000
        # First element should be 1.0 (0.0 was popped)
        assert math.isclose(self.instance._fps_history[0], 1.0)
        assert math.isclose(self.instance._fps_history[-1], 10000.0)


class TestReset:
    """Test the reset method."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_reset_clears_dt_history(self, mocker):
        """Test that reset clears dt_history."""
        mocker.patch('glitchygames.performance.adaptive_clamping.LOG')
        self.instance._dt_history = [0.016, 0.017]
        self.instance.reset()
        assert self.instance._dt_history == []

    def test_reset_clears_fps_history(self, mocker):
        """Test that reset creates empty fps_history."""
        mocker.patch('glitchygames.performance.adaptive_clamping.LOG')
        self.instance.reset()
        assert self.instance._fps_history == []

    def test_reset_clears_fps_histogram(self, mocker):
        """Test that reset creates empty fps_histogram."""
        mocker.patch('glitchygames.performance.adaptive_clamping.LOG')
        self.instance.reset()
        assert self.instance._fps_histogram == {}

    def test_reset_logs_message(self, mocker):
        """Test that reset logs a reset message."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')
        self.instance.reset()
        mock_log.info.assert_called_once_with('Reset performance tracking')


class TestGetShutdownStatsDetailed:
    """Test get_shutdown_stats with trimming and histogram building."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_all_zero_fps_values(self):
        """Test shutdown stats when all FPS values are zero (filtered out)."""
        self.instance.set_current_scene('TestScene')
        self.instance.track_fps_from_event(0.0)
        self.instance.track_fps_from_event(0.0)

        result = self.instance.get_shutdown_stats()
        assert result == {'message': 'No valid FPS data collected'}

    def test_trimming_with_enough_data(self):
        """Test that trimming removes top and bottom percentiles."""
        self.instance.set_current_scene('TestScene')
        self.instance.set_trim_percent(10.0)

        # Add 100 FPS values: 1 through 100
        for fps in range(1, 101):
            self.instance.track_fps_from_event(float(fps))

        result = self.instance.get_shutdown_stats()

        # With 10% trim, drop 10 from each end
        assert result['total_frames'] == 100
        assert result['trimmed_frames'] == 80  # 100 - 2*10
        # Min/max from original data
        assert math.isclose(result['min_fps'], 1.0)
        assert math.isclose(result['max_fps'], 100.0)
        # Avg should be of trimmed data (11 to 90)
        expected_avg = sum(range(11, 91)) / 80
        assert result['avg_fps'] == pytest.approx(expected_avg, rel=1e-2)

    def test_no_trimming_when_percent_is_zero(self):
        """Test that zero trim percent uses all data."""
        self.instance.set_current_scene('TestScene')
        self.instance.set_trim_percent(0.0)

        for fps in [10.0, 20.0, 30.0, 40.0, 50.0]:
            self.instance.track_fps_from_event(fps)

        result = self.instance.get_shutdown_stats()

        assert result['total_frames'] == 5
        assert result['trimmed_frames'] == 5

    def test_histogram_is_built_from_trimmed_data(self):
        """Test that the histogram is built from trimmed FPS data."""
        self.instance.set_current_scene('TestScene')
        self.instance.set_trim_percent(0.0)

        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(61.0)

        result = self.instance.get_shutdown_stats()

        histogram = result['fps_histogram']
        assert '60' in histogram
        assert histogram['60'] == 2
        assert '61' in histogram
        assert histogram['61'] == 1

    def test_trimming_too_aggressive_falls_back(self):
        """Test trimming when drop_count exceeds half the data."""
        self.instance.set_current_scene('TestScene')
        self.instance.set_trim_percent(49.9)

        # With only 3 values and 49.9% trim, drop_count = int(3 * 0.499) = 1
        # 3 > 2*1, so trimmed_fps = fps_values[1:-1] = middle value
        self.instance.track_fps_from_event(10.0)
        self.instance.track_fps_from_event(50.0)
        self.instance.track_fps_from_event(90.0)

        result = self.instance.get_shutdown_stats()

        assert result['total_frames'] == 3
        assert result['trimmed_frames'] == 1
        assert math.isclose(result['avg_fps'], 50.0)


class TestGetPerSceneShutdownStatsEdgeCases:
    """Test get_per_scene_shutdown_stats edge cases."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_empty_scene_fps_history(self):
        """Test per-scene stats for a scene with empty fps_history."""
        self.instance.set_current_scene('EmptyScene')
        # Don't add any FPS data

        result = self.instance.get_per_scene_shutdown_stats()
        assert result['EmptyScene'] == {'message': 'Not enough data'}

    def test_scene_with_only_zero_fps(self):
        """Test per-scene stats when all FPS values are zero."""
        self.instance.set_current_scene('ZeroScene')
        self.instance.track_fps_from_event(0.0)
        self.instance.track_fps_from_event(0.0)

        result = self.instance.get_per_scene_shutdown_stats()
        assert result['ZeroScene'] == {'message': 'No valid FPS data collected'}

    def test_per_scene_histogram_building(self):
        """Test that per-scene histograms are built correctly."""
        self.instance.set_current_scene('GameScene')
        self.instance.set_trim_percent(0.0)

        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(59.0)

        result = self.instance.get_per_scene_shutdown_stats()
        scene_stats = result['GameScene']

        assert scene_stats['total_frames'] == 3
        assert '60' in scene_stats['fps_histogram']
        assert scene_stats['fps_histogram']['60'] == 2
        assert '59' in scene_stats['fps_histogram']
        assert scene_stats['fps_histogram']['59'] == 1

    def test_per_scene_trimming(self):
        """Test that per-scene stats apply trimming correctly."""
        self.instance.set_current_scene('TrimScene')
        self.instance.set_trim_percent(10.0)

        for fps in range(1, 101):
            self.instance.track_fps_from_event(float(fps))

        result = self.instance.get_per_scene_shutdown_stats()
        scene_stats = result['TrimScene']

        assert scene_stats['total_frames'] == 100
        assert scene_stats['trimmed_frames'] == 80


class TestLogFpsStats:
    """Test _log_fps_stats logging output."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_log_fps_stats_without_spare_time(self, mocker):
        """Test _log_fps_stats when spare_stats has a message (no spare time)."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        stats = {
            'total_frames': 100,
            'trimmed_frames': 90,
            'avg_fps': 60.0,
            'min_fps': 55.0,
            'max_fps': 65.0,
            'median_fps': 60.0,
            'performance_grade': 'A (Very Good)',
        }
        spare_stats = {'message': 'Not applicable for unlimited FPS'}

        self.instance._trim_percent = 5.0
        self.instance._log_fps_stats(stats, spare_stats)

        # Should log basic stats but not spare time details
        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]

        assert any('Total Frames: 100' in arg for arg in call_args_list)
        assert any('Analyzed Frames: 90' in arg for arg in call_args_list)
        assert any('Average FPS: 60.0' in arg for arg in call_args_list)
        assert any('Minimum FPS: 55.0' in arg for arg in call_args_list)
        assert any('Maximum FPS: 65.0' in arg for arg in call_args_list)
        assert any('Median FPS: 60.0' in arg for arg in call_args_list)
        assert any('Performance Grade: A (Very Good)' in arg for arg in call_args_list)
        # Should NOT log spare time stats
        assert not any('Spare Time' in arg for arg in call_args_list)

    def test_log_fps_stats_with_spare_time(self, mocker):
        """Test _log_fps_stats when spare time data is available."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        stats = {
            'total_frames': 100,
            'trimmed_frames': 90,
            'avg_fps': 60.0,
            'min_fps': 55.0,
            'max_fps': 65.0,
            'median_fps': 60.0,
            'performance_grade': 'A+ (Excellent)',
        }
        spare_stats = {
            'target_frame_time_ms': 16.67,
            'avg_frame_time_ms': 10.0,
            'avg_spare_time_ms': 6.67,
            'spare_capacity_percent': 40.0,
            'could_tick_times': 1.667,
        }

        self.instance._target_fps = 60.0
        self.instance._trim_percent = 5.0
        self.instance._log_fps_stats(stats, spare_stats)

        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]

        assert any('Target FPS: 60.0' in arg for arg in call_args_list)
        assert any('Spare Time' in arg for arg in call_args_list)
        assert any('Draw Time' in arg for arg in call_args_list)
        assert any('Could Tick' in arg for arg in call_args_list)

    def test_log_fps_stats_no_trimming_label(self, mocker):
        """Test _log_fps_stats shows 'no trimming' when trim_percent is 0."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        stats = {
            'total_frames': 50,
            'trimmed_frames': 50,
            'avg_fps': 60.0,
            'min_fps': 58.0,
            'max_fps': 62.0,
            'median_fps': 60.0,
            'performance_grade': 'A (Very Good)',
        }
        spare_stats = {'message': 'Not applicable'}

        self.instance._trim_percent = 0.0
        self.instance._log_fps_stats(stats, spare_stats)

        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('no trimming' in arg for arg in call_args_list)


class TestLogFpsHistogram:
    """Test _log_fps_histogram logging output."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_log_fps_histogram_with_string_keys(self, mocker):
        """Test histogram logging with string bucket keys."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        fps_histogram = {'60': 80, '59': 15, '61': 5}
        trimmed_frames = 100

        AdaptiveClamping._log_fps_histogram(fps_histogram, trimmed_frames)

        # Should log the header and each bucket
        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('FPS Distribution' in arg for arg in call_args_list)
        assert any('FPS' in arg and 'frames' in arg for arg in call_args_list)

    def test_log_fps_histogram_with_integer_keys(self, mocker):
        """Test histogram logging with integer bucket keys (tuple branch)."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        # Integer keys trigger the else branch in the formatting
        fps_histogram = {60: 50, 65: 30, 70: 20}
        trimmed_frames = 100

        AdaptiveClamping._log_fps_histogram(fps_histogram, trimmed_frames)

        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('FPS Distribution' in arg for arg in call_args_list)

    def test_log_fps_histogram_with_tuple_keys(self, mocker):
        """Test histogram logging with tuple bucket keys."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        fps_histogram = {(55, 59): 20, (60, 64): 60, (65, 69): 20}
        trimmed_frames = 100

        AdaptiveClamping._log_fps_histogram(fps_histogram, trimmed_frames)

        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('FPS Distribution' in arg for arg in call_args_list)

    def test_log_fps_histogram_bell_curve_ordering(self, mocker):
        """Test that histogram entries are reordered into bell curve shape."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        fps_histogram = {'58': 5, '59': 20, '60': 50, '61': 20, '62': 5}
        trimmed_frames = 100

        AdaptiveClamping._log_fps_histogram(fps_histogram, trimmed_frames)

        # Should have logged header + 5 bucket lines
        assert mock_log.info.call_count == 6

    def test_log_fps_histogram_zero_trimmed_frames(self, mocker):
        """Test histogram with zero trimmed frames (avoid division by zero)."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        fps_histogram = {'60': 10}
        trimmed_frames = 0

        AdaptiveClamping._log_fps_histogram(fps_histogram, trimmed_frames)

        # Should still log without error (percentage will be 0)
        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('0.0%' in arg for arg in call_args_list)


class TestPrintShutdownReport:
    """Test print_shutdown_report method."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_print_shutdown_report_no_data(self, mocker):
        """Test shutdown report when there is no data (early return)."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        self.instance.print_shutdown_report()

        # Should return early without logging anything
        mock_log.info.assert_not_called()

    def test_print_shutdown_report_with_data(self, mocker):
        """Test shutdown report with sufficient FPS data."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        self.instance.set_current_scene('TestScene')
        for _ in range(20):
            self.instance.track_fps_from_event(60.0)

        self.instance.print_shutdown_report()

        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('GAME PERFORMANCE REPORT' in arg for arg in call_args_list)
        assert any('=' * 80 in arg for arg in call_args_list)

    def test_print_shutdown_report_with_histogram(self, mocker):
        """Test that shutdown report includes histogram when available."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        self.instance.set_current_scene('TestScene')
        self.instance.set_trim_percent(0.0)
        for fps in [58.0, 59.0, 60.0, 61.0, 62.0]:
            self.instance.track_fps_from_event(fps)

        self.instance.print_shutdown_report()

        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('FPS Distribution' in arg for arg in call_args_list)


class TestPrintPerSceneShutdownReport:
    """Test print_per_scene_shutdown_report method."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_per_scene_report_no_data(self, mocker):
        """Test per-scene report when no scenes have data."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        self.instance.print_per_scene_shutdown_report()

        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('PER-SCENE PERFORMANCE REPORT' in arg for arg in call_args_list)
        assert any('No scene performance data collected' in arg for arg in call_args_list)

    def test_per_scene_report_with_data(self, mocker):
        """Test per-scene report with FPS data across scenes."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        self.instance.set_current_scene('MainMenu')
        for _ in range(10):
            self.instance.track_fps_from_event(60.0)

        self.instance.set_current_scene('GamePlay')
        for _ in range(10):
            self.instance.track_fps_from_event(45.0)

        self.instance.print_per_scene_shutdown_report()

        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('PER-SCENE PERFORMANCE REPORT' in arg for arg in call_args_list)
        assert any('MainMenu' in arg for arg in call_args_list)
        assert any('GamePlay' in arg for arg in call_args_list)

    def test_per_scene_report_with_message_scene(self, mocker):
        """Test per-scene report when a scene has only a message (no valid data)."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        self.instance.set_current_scene('EmptyScene')
        # Don't add FPS data - will produce {'message': 'Not enough data'}

        self.instance.set_current_scene('ActiveScene')
        for _ in range(5):
            self.instance.track_fps_from_event(60.0)

        self.instance.print_per_scene_shutdown_report()

        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('EmptyScene' in arg for arg in call_args_list)
        assert any('Not enough data' in arg for arg in call_args_list)
        assert any('ActiveScene' in arg for arg in call_args_list)

    def test_per_scene_report_with_spare_time(self, mocker):
        """Test per-scene report includes spare time when target FPS is set."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        self.instance._target_fps = 60.0
        self.instance.set_current_scene('GameScene')
        for _ in range(10):
            self.instance.track_fps_from_event(60.0, 0.010)

        self.instance.print_per_scene_shutdown_report()

        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('PER-SCENE PERFORMANCE REPORT' in arg for arg in call_args_list)
        assert any('GameScene' in arg for arg in call_args_list)

    def test_per_scene_report_with_histogram(self, mocker):
        """Test per-scene report includes histogram data."""
        mock_log = mocker.patch('glitchygames.performance.adaptive_clamping.LOG')

        self.instance.set_current_scene('GameScene')
        self.instance.set_trim_percent(0.0)
        for fps in [58.0, 59.0, 60.0, 61.0, 62.0]:
            self.instance.track_fps_from_event(fps)

        self.instance.print_per_scene_shutdown_report()

        call_args_list = [call.args[0] for call in mock_log.info.call_args_list]
        assert any('FPS Distribution' in arg for arg in call_args_list)


class TestPerformanceGradeEdgeCases:
    """Test _calculate_performance_grade edge cases for uncovered lines."""

    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()

    def test_empty_fps_values_returns_na(self):
        """Test that empty FPS list returns N/A grade."""
        result = self.instance._calculate_performance_grade([])
        assert result == 'N/A'

    def test_unlimited_fps_poor_grade(self):
        """Test poor grade with unlimited FPS target (20 <= avg < 30)."""
        self.instance._target_fps = 0.0
        result = self.instance._calculate_performance_grade([25.0])
        assert result == 'D (Poor)'

    def test_unlimited_fps_very_poor_grade(self):
        """Test very poor grade with unlimited FPS target (avg < 20)."""
        self.instance._target_fps = 0.0
        result = self.instance._calculate_performance_grade([10.0])
        assert result == 'F (Very Poor)'

    def test_capped_fps_very_poor_grade(self):
        """Test very poor grade with capped FPS (ratio < 0.70)."""
        self.instance._target_fps = 60.0
        # 30/60 = 0.5 ratio, < 0.70
        result = self.instance._calculate_performance_grade([30.0])
        assert result == 'F (Very Poor)'
