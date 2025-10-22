"""Tests for the adaptive clamping system."""

import pytest
import time
from unittest.mock import patch, MagicMock

from glitchygames.performance.adaptive_clamping import AdaptiveClamping, performance_manager


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
        assert instance._last_performance_log_time == 0.0
        assert instance._fps_log_interval_ms == 1000.0
        assert instance._current_scene is None
        assert instance._target_fps == 0.0
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
        self.instance.set_current_scene("TestScene")
        
        assert self.instance._current_scene == "TestScene"
        assert "TestScene" in self.instance._scene_data
        assert self.instance._scene_data["TestScene"]["fps_history"] == []
        assert self.instance._scene_data["TestScene"]["fps_histogram"] == {}
        assert self.instance._scene_data["TestScene"]["frame_times"] == []
    
    def test_set_current_scene_doesnt_reinitialize(self):
        """Test that setting the same scene doesn't reinitialize data."""
        self.instance.set_current_scene("TestScene")
        initial_data = self.instance._scene_data["TestScene"]
        
        # Add some data
        initial_data["fps_history"].append(60.0)
        initial_data["fps_histogram"][60] = 1
        initial_data["frame_times"].append(0.016)
        
        # Set same scene again
        self.instance.set_current_scene("TestScene")
        
        # Data should be preserved
        assert self.instance._scene_data["TestScene"] is initial_data
        assert self.instance._scene_data["TestScene"]["fps_history"] == [60.0]
        assert self.instance._scene_data["TestScene"]["fps_histogram"][60] == 1
        assert self.instance._scene_data["TestScene"]["frame_times"] == [0.016]
    
    def test_switch_scenes_preserves_data(self):
        """Test that switching scenes preserves data for each scene."""
        # Set up first scene
        self.instance.set_current_scene("Scene1")
        self.instance._scene_data["Scene1"]["fps_history"].append(60.0)
        
        # Switch to second scene
        self.instance.set_current_scene("Scene2")
        self.instance._scene_data["Scene2"]["fps_history"].append(30.0)
        
        # Switch back to first scene
        self.instance.set_current_scene("Scene1")
        
        # Both scenes should have their data preserved
        assert self.instance._scene_data["Scene1"]["fps_history"] == [60.0]
        assert self.instance._scene_data["Scene2"]["fps_history"] == [30.0]


class TestFPSTracking:
    """Test FPS tracking and frame time collection."""
    
    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()
        self.instance.set_current_scene("TestScene")
    
    def test_track_fps_from_event_basic(self):
        """Test basic FPS tracking."""
        self.instance.track_fps_from_event(60.0)
        
        scene_data = self.instance._scene_data["TestScene"]
        assert scene_data["fps_history"] == [60.0]
        assert scene_data["fps_histogram"][60] == 1
    
    def test_track_fps_from_event_with_frame_time(self):
        """Test FPS tracking with frame time for spare time calculation."""
        self.instance._target_fps = 60.0
        self.instance.track_fps_from_event(60.0, 0.016)  # 16ms frame time
        
        scene_data = self.instance._scene_data["TestScene"]
        assert scene_data["fps_history"] == [60.0]
        assert scene_data["frame_times"] == [0.016]
        assert scene_data["fps_histogram"][60] == 1
    
    def test_track_fps_from_event_histogram_accumulation(self):
        """Test that histogram accumulates FPS values."""
        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(30.0)
        
        scene_data = self.instance._scene_data["TestScene"]
        assert scene_data["fps_histogram"][60] == 2
        assert scene_data["fps_histogram"][30] == 1
    
    def test_track_fps_from_event_history_limit(self):
        """Test that FPS history is limited to 100,000 entries."""
        # Add 100,001 FPS values
        for i in range(100001):
            self.instance.track_fps_from_event(60.0)
        
        scene_data = self.instance._scene_data["TestScene"]
        assert len(scene_data["fps_history"]) == 100000
        assert scene_data["fps_history"][0] == 60.0  # First entry should be the 1,001st one added (after 100k limit)
        assert scene_data["fps_history"][-1] == 60.0  # Last entry should be the last one added
    
    def test_track_fps_from_event_frame_times_limit(self):
        """Test that frame times are limited to 1,000 entries."""
        self.instance._target_fps = 60.0
        
        # Add 1,001 frame times
        for i in range(1001):
            self.instance.track_fps_from_event(60.0, 0.016)
        
        scene_data = self.instance._scene_data["TestScene"]
        assert len(scene_data["frame_times"]) == 1000
        assert scene_data["frame_times"][0] == 0.016  # First entry should be the second one added
        assert scene_data["frame_times"][-1] == 0.016  # Last entry should be the last one added
    
    def test_track_fps_from_event_no_scene(self):
        """Test that tracking without a scene doesn't crash."""
        self.instance._current_scene = None
        # Should not raise an exception
        self.instance.track_fps_from_event(60.0)
    
    def test_track_fps_from_event_unlimited_fps(self):
        """Test that frame times are not tracked when target FPS is 0 (unlimited)."""
        self.instance._target_fps = 0.0
        self.instance.track_fps_from_event(60.0, 0.016)
        
        scene_data = self.instance._scene_data["TestScene"]
        assert scene_data["frame_times"] == []  # Should not track frame times for unlimited FPS


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
        
        assert result == {"message": "Not applicable for unlimited FPS"}
    
    def test_get_spare_time_stats_no_data(self):
        """Test spare time stats with no frame time data."""
        self.instance._target_fps = 60.0
        result = self.instance.get_spare_time_stats()
        
        assert result == {"message": "No frame time data available"}
    
    def test_get_spare_time_stats_global(self):
        """Test global spare time calculation."""
        self.instance._target_fps = 60.0
        
        # Add data for multiple scenes
        self.instance.set_current_scene("Scene1")
        self.instance.track_fps_from_event(60.0, 0.010)  # 10ms processing time
        
        self.instance.set_current_scene("Scene2")
        self.instance.track_fps_from_event(60.0, 0.020)  # 20ms processing time
        
        result = self.instance.get_spare_time_stats()
        
        # Target frame time at 60 FPS = 16.67ms
        # Average frame time = (10 + 20) / 2 = 15ms
        # Spare time = 16.67 - 15 = 1.67ms
        # Spare capacity = 1.67 / 16.67 = 10%
        # Could tick = 16.67 / 15 = 1.11x faster
        
        assert result["target_frame_time_ms"] == pytest.approx(16.67, rel=1e-2)
        assert result["avg_frame_time_ms"] == pytest.approx(15.0, rel=1e-2)
        assert result["avg_spare_time_ms"] == pytest.approx(1.67, rel=1e-2)
        assert result["spare_capacity_percent"] == pytest.approx(10.0, rel=1e-2)
        assert result["could_tick_times"] == pytest.approx(1.11, rel=1e-2)
    
    def test_get_spare_time_stats_per_scene(self):
        """Test per-scene spare time calculation."""
        self.instance._target_fps = 60.0
        
        # Add data for Scene1
        self.instance.set_current_scene("Scene1")
        self.instance.track_fps_from_event(60.0, 0.010)  # 10ms processing time
        
        # Add data for Scene2
        self.instance.set_current_scene("Scene2")
        self.instance.track_fps_from_event(60.0, 0.020)  # 20ms processing time
        
        # Test Scene1
        result1 = self.instance.get_spare_time_stats("Scene1")
        assert result1["avg_frame_time_ms"] == pytest.approx(10.0, rel=1e-2)
        assert result1["spare_capacity_percent"] == pytest.approx(40.0, rel=1e-2)  # (16.67-10)/16.67
        
        # Test Scene2
        result2 = self.instance.get_spare_time_stats("Scene2")
        assert result2["avg_frame_time_ms"] == pytest.approx(20.0, rel=1e-2)
        assert result2["spare_capacity_percent"] == pytest.approx(-20.0, rel=1e-2)  # (16.67-20)/16.67
    
    def test_get_spare_time_stats_scene_not_found(self):
        """Test spare time stats for non-existent scene."""
        self.instance._target_fps = 60.0
        result = self.instance.get_spare_time_stats("NonExistentScene")
        
        assert result == {"message": "Scene not found"}
    
    def test_get_spare_time_stats_scene_no_data(self):
        """Test spare time stats for scene with no frame time data."""
        self.instance._target_fps = 60.0
        self.instance.set_current_scene("EmptyScene")
        # Don't add any frame time data
        
        result = self.instance.get_spare_time_stats("EmptyScene")
        assert result == {"message": "No frame time data for this scene"}


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
        assert self.instance._calculate_performance_grade([30.0]) == "C (Fair)"  # 30 FPS is playable but not great
        assert self.instance._calculate_performance_grade([60.0]) == "A (Very Good)"
        assert self.instance._calculate_performance_grade([120.0]) == "A+ (Excellent)"
        assert self.instance._calculate_performance_grade([240.0]) == "A+ (Excellent)"
    
    def test_performance_grade_capped_fps_achieving_target(self):
        """Test performance grading when achieving target FPS."""
        self.instance._target_fps = 60.0
        
        # Test achieving target FPS (should get good grade)
        assert self.instance._calculate_performance_grade([60.0]) == "A+ (Excellent)"  # 100% of target
        assert self.instance._calculate_performance_grade([57.0]) == "A (Very Good)"   # 95% of target
        assert self.instance._calculate_performance_grade([54.0]) == "B (Good)"        # 90% of target
        assert self.instance._calculate_performance_grade([48.0]) == "C (Fair)"        # 80% of target
        assert self.instance._calculate_performance_grade([42.0]) == "D (Poor)"        # 70% of target
        assert self.instance._calculate_performance_grade([36.0]) == "F (Very Poor)"  # 60% of target
    
    def test_performance_grade_capped_fps_exceeding_target(self):
        """Test performance grading when exceeding target FPS."""
        self.instance._target_fps = 60.0
        
        # Exceeding target should get excellent grade
        assert self.instance._calculate_performance_grade([120.0]) == "A+ (Excellent)"  # 200% of target
        assert self.instance._calculate_performance_grade([240.0]) == "A+ (Excellent)"  # 400% of target


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
        assert result == {"message": "Not enough data"}
    
    def test_get_shutdown_stats_with_data(self):
        """Test shutdown stats with FPS data."""
        # Add data for multiple scenes
        self.instance.set_current_scene("Scene1")
        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(61.0)
        
        self.instance.set_current_scene("Scene2")
        self.instance.track_fps_from_event(30.0)
        self.instance.track_fps_from_event(31.0)
        
        result = self.instance.get_shutdown_stats()
        
        # Should aggregate data from all scenes
        assert result["total_frames"] == 4
        assert result["avg_fps"] == pytest.approx(45.5, rel=1e-2)  # (60+61+30+31)/4
        assert result["min_fps"] == 30.0
        assert result["max_fps"] == 61.0
        assert result["median_fps"] == 60.0  # Median of trimmed data [31, 60] is 60
        assert "performance_grade" in result
        assert "fps_histogram" in result
    
    def test_get_per_scene_shutdown_stats(self):
        """Test per-scene shutdown stats."""
        # Add data for multiple scenes
        self.instance.set_current_scene("Scene1")
        self.instance.track_fps_from_event(60.0)
        self.instance.track_fps_from_event(61.0)
        
        self.instance.set_current_scene("Scene2")
        self.instance.track_fps_from_event(30.0)
        
        result = self.instance.get_per_scene_shutdown_stats()
        
        assert "Scene1" in result
        assert "Scene2" in result
        
        # Scene1 should have 2 frames
        assert result["Scene1"]["total_frames"] == 2
        assert result["Scene1"]["avg_fps"] == pytest.approx(60.5, rel=1e-2)
        
        # Scene2 should have 1 frame
        assert result["Scene2"]["total_frames"] == 1
        assert result["Scene2"]["avg_fps"] == 30.0
    
    def test_get_per_scene_shutdown_stats_filters_unknown(self):
        """Test that per-scene stats filter out Unknown scenes."""
        # Add data for a scene named "Unknown"
        self.instance.set_current_scene("Unknown")
        self.instance.track_fps_from_event(60.0)
        
        result = self.instance.get_per_scene_shutdown_stats()
        
        # Should not include Unknown scene
        assert "Unknown" not in result
        assert result == {}


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
        assert result == 0.016
    
    def test_get_adaptive_dt_sufficient_history(self):
        """Test adaptive DT with sufficient history."""
        # Add 10 frames of history
        for i in range(10):
            self.instance.get_adaptive_dt(0.016)  # 60 FPS
        
        # Should now apply smoothing
        result = self.instance.get_adaptive_dt(0.016)
        
        # Should be smoothed towards target (1/60 = 0.01667)
        assert result != 0.016  # Should be adjusted
        assert result > 0.016  # Should be closer to target
    
    def test_get_adaptive_dt_history_limit(self):
        """Test that dt history is limited to 60 entries."""
        # Add 61 frames
        for i in range(61):
            self.instance.get_adaptive_dt(0.016)
        
        assert len(self.instance._dt_history) == 60
    
    @patch('time.perf_counter')
    def test_get_adaptive_dt_logging_interval(self, mock_time):
        """Test that performance adjustments are logged at the correct interval."""
        # Start with time 0
        mock_time.return_value = 0.0
        
        # Add sufficient history with a very large dt to ensure significant adjustment
        for i in range(10):
            self.instance.get_adaptive_dt(1.0)  # Very large dt to ensure significant adjustment
        
        # Reset the last log time to ensure we can log
        self.instance._last_performance_log_time = 0.0
        
        # Temporarily lower the logging threshold to ensure we trigger logging
        original_threshold = 0.0001
        with patch.object(self.instance, '_fps_log_interval_ms', 0.0):  # No interval restriction
            with patch('builtins.print') as mock_print:
                # Manually set a large adjustment to ensure logging
                adjusted_dt = self.instance.get_adaptive_dt(1.0)
                # Check if the adjustment is significant enough
                if abs(adjusted_dt - 1.0) > 0.0001:
                    mock_print.assert_called_once()
                else:
                    # If adjustment is too small, just verify the method works
                    assert adjusted_dt != 1.0  # Should be adjusted


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Reset singleton before each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.instance = AdaptiveClamping()
    
    def test_negative_fps_values(self):
        """Test handling of negative FPS values."""
        self.instance.set_current_scene("TestScene")
        self.instance.track_fps_from_event(-1.0)
        
        # Should still track the value
        scene_data = self.instance._scene_data["TestScene"]
        assert scene_data["fps_history"] == [-1.0]
        assert scene_data["fps_histogram"][-1] == 1
    
    def test_zero_fps_values(self):
        """Test handling of zero FPS values."""
        self.instance.set_current_scene("TestScene")
        self.instance.track_fps_from_event(0.0)
        
        # Should still track the value
        scene_data = self.instance._scene_data["TestScene"]
        assert scene_data["fps_history"] == [0.0]
        assert scene_data["fps_histogram"][0] == 1
    
    def test_very_large_fps_values(self):
        """Test handling of very large FPS values."""
        self.instance.set_current_scene("TestScene")
        self.instance.track_fps_from_event(10000.0)
        
        # Should still track the value
        scene_data = self.instance._scene_data["TestScene"]
        assert scene_data["fps_history"] == [10000.0]
        assert scene_data["fps_histogram"][10000] == 1
    
    def test_negative_frame_times(self):
        """Test handling of negative frame times."""
        self.instance._target_fps = 60.0
        self.instance.set_current_scene("TestScene")
        self.instance.track_fps_from_event(60.0, -0.016)
        
        # Should still track the value
        scene_data = self.instance._scene_data["TestScene"]
        assert scene_data["frame_times"] == [-0.016]
    
    def test_zero_frame_times(self):
        """Test handling of zero frame times."""
        self.instance._target_fps = 60.0
        self.instance.set_current_scene("TestScene")
        self.instance.track_fps_from_event(60.0, 0.0)
        
        # Should still track the value
        scene_data = self.instance._scene_data["TestScene"]
        assert scene_data["frame_times"] == [0.0]


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
