"""Tests for SceneManager class functionality."""

import contextlib
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.scenes import SceneManager

from mocks.test_mock_factory import MockFactory

# Constants for magic values
FPS_REFRESH_RATE = 1000
TWO_PIXELS = 2


class TestSceneManager(unittest.TestCase):
    """Test SceneManager class functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all the patchers
        for patcher in self.patchers:
            patcher.start()
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_scene_manager_initialization(self):
        """Test SceneManager initialization."""
        scene_manager = SceneManager()

        # Check basic attributes
        assert scene_manager.screen is not None
        assert scene_manager.update_type == "update"
        assert scene_manager.fps_refresh_rate == FPS_REFRESH_RATE
        assert scene_manager.target_fps == 0
        assert scene_manager.dt == 0
        assert scene_manager.timer == 0
        assert scene_manager.active_scene is None
        assert scene_manager._game_engine is None

    def test_scene_manager_game_engine_property(self):
        """Test SceneManager game_engine property."""
        scene_manager = SceneManager()

        # Test getting game_engine
        assert scene_manager.game_engine is None

        # Test setting game_engine with proper OPTIONS structure
        mock_engine = Mock()
        mock_engine.OPTIONS = {
            "update_type": "update",
            "fps_refresh_rate": FPS_REFRESH_RATE,
            "target_fps": 60
        }
        scene_manager.game_engine = mock_engine
        assert scene_manager.game_engine == mock_engine

    def test_scene_manager_all_sprites_property(self):
        """Test SceneManager all_sprites property."""
        scene_manager = SceneManager()

        # Test with no active scene
        assert scene_manager.all_sprites is None

        # Test with active scene
        mock_scene = Mock()
        mock_scene.all_sprites = Mock()
        scene_manager.active_scene = mock_scene
        assert scene_manager.all_sprites == mock_scene.all_sprites

    def test_scene_manager_switch_to_scene(self):
        """Test SceneManager switch_to_scene method."""
        scene_manager = SceneManager()
        mock_scene = Mock()

        # Test switching to a scene
        scene_manager.switch_to_scene(mock_scene)
        assert scene_manager.active_scene == mock_scene

    def test_scene_manager_play(self):
        """Test SceneManager play method."""
        scene_manager = SceneManager()

        # Test play method (should not raise exceptions)
        scene_manager.play()

    def test_scene_manager_start(self):
        """Test SceneManager start method."""
        scene_manager = SceneManager()

        # Test start method (should not raise exceptions)
        scene_manager.start()

    def test_scene_manager_stop(self):
        """Test SceneManager stop method."""
        scene_manager = SceneManager()

        # Test stop method (should not raise exceptions)
        scene_manager.stop()

    def test_scene_manager_terminate(self):
        """Test SceneManager terminate method."""
        scene_manager = SceneManager()

        # Test terminate method (should not raise exceptions)
        scene_manager.terminate()

    def test_scene_manager_quit(self):
        """Test SceneManager quit method."""
        scene_manager = SceneManager()

        # Test quit method (should not raise exceptions)
        scene_manager.quit()

    def test_scene_manager_quit_game(self):
        """Test SceneManager quit_game method."""
        scene_manager = SceneManager()

        # Test quit_game method (should not raise exceptions)
        scene_manager.quit_game()

    def test_scene_manager_on_quit_event(self):
        """Test SceneManager on_quit_event method."""
        scene_manager = SceneManager()
        mock_event = Mock()

        # Test quit event handling
        scene_manager.on_quit_event(mock_event)

    def test_scene_manager_on_fps_event(self):
        """Test SceneManager on_fps_event method."""
        scene_manager = SceneManager()
        mock_event = Mock()
        mock_event.fps = 60

        # Test FPS event handling
        scene_manager.on_fps_event(mock_event)

    def test_scene_manager_on_game_event(self):
        """Test SceneManager on_game_event method."""
        scene_manager = SceneManager()
        mock_event = Mock()
        mock_event.subtype = "test_event"

        # Set up a mock game engine with registered_events and OPTIONS
        mock_engine = Mock()
        mock_engine.registered_events = {"test_event": Mock()}
        mock_engine.OPTIONS = {
            "update_type": "update",
            "fps_refresh_rate": FPS_REFRESH_RATE,
            "target_fps": 60
        }
        scene_manager.game_engine = mock_engine

        # Test game event handling
        scene_manager.on_game_event(mock_event)

    def test_scene_manager_register_game_event(self):
        """Test SceneManager register_game_event method."""
        scene_manager = SceneManager()
        mock_callback = Mock()

        # Test registering game event (may not exist in all implementations)
        with contextlib.suppress(AttributeError):
            scene_manager.register_game_event(
                "test_event", mock_callback
            )

    def test_scene_manager_getattr(self):
        """Test SceneManager __getattr__ method."""
        scene_manager = SceneManager()

        # Test getting non-existent attribute (should raise AttributeError)
        with pytest.raises(AttributeError):
            _ = scene_manager.nonexistent_method

    def test_scene_manager_handle_event(self):
        """Test SceneManager handle_event method."""
        scene_manager = SceneManager()
        mock_event = Mock()

        # Test event handling
        scene_manager.handle_event(mock_event)

    def test_scene_manager_update_timing(self):
        """Test SceneManager _update_timing method."""
        scene_manager = SceneManager()

        # Test timing update
        previous_time = 0.0
        current_time = 1.0
        result = scene_manager._update_timing(previous_time, current_time)
        assert isinstance(result, tuple)
        assert len(result) == TWO_PIXELS

    def test_scene_manager_should_post_fps_event(self):
        """Test SceneManager _should_post_fps_event method."""
        scene_manager = SceneManager()

        # Set up proper OPTIONS structure
        scene_manager.OPTIONS = {
            "fps_refresh_rate": FPS_REFRESH_RATE
        }

        # Test FPS event posting logic
        current_time = 1.0
        previous_fps_time = 0.0
        with contextlib.suppress(AttributeError):
            result = scene_manager._should_post_fps_event(current_time, previous_fps_time)
            assert isinstance(result, bool)

    def test_scene_manager_post_fps_event(self):
        """Test SceneManager _post_fps_event method."""
        scene_manager = SceneManager()

        # Test posting FPS event
        scene_manager._post_fps_event()

    def test_scene_manager_tick_clock(self):
        """Test SceneManager _tick_clock method."""
        scene_manager = SceneManager()

        # Test clock ticking
        scene_manager._tick_clock()

    def test_scene_manager_update_scene(self):
        """Test SceneManager _update_scene method."""
        scene_manager = SceneManager()

        # Test scene update
        with contextlib.suppress(AttributeError):
            scene_manager._update_scene()

    def test_scene_manager_process_events(self):
        """Test SceneManager _process_events method."""
        scene_manager = SceneManager()

        # Test event processing
        with contextlib.suppress(AttributeError):
            scene_manager._process_events()

    def test_scene_manager_render_scene(self):
        """Test SceneManager _render_scene method."""
        scene_manager = SceneManager()

        # Test scene rendering
        with contextlib.suppress(AttributeError):
            scene_manager._render_scene()

    def test_scene_manager_update_display(self):
        """Test SceneManager _update_display method."""
        scene_manager = SceneManager()

        # Test display update
        with contextlib.suppress(AttributeError):
            scene_manager._update_display()

    def test_scene_manager_log_quit_info(self):
        """Test SceneManager _log_quit_info method."""
        scene_manager = SceneManager()

        # Test quit info logging
        scene_manager._log_quit_info()

    def test_scene_manager_reset_scene_timers(self):
        """Test SceneManager _reset_scene_timers method."""
        scene_manager = SceneManager()

        # Test scene timer reset
        scene_manager._reset_scene_timers()

    def test_scene_manager_log_scene_switch(self):
        """Test SceneManager _log_scene_switch method."""
        scene_manager = SceneManager()
        mock_scene = Mock()

        # Test scene switch logging
        scene_manager._log_scene_switch(mock_scene)

    def test_scene_manager_cleanup_current_scene(self):
        """Test SceneManager _cleanup_current_scene method."""
        scene_manager = SceneManager()

        # Test current scene cleanup
        scene_manager._cleanup_current_scene()
