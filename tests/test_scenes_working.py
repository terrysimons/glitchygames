"""Working tests for Scenes module to actually increase coverage.

This module focuses on simple, working tests that cover missing lines.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene, SceneManager

from test_mock_factory import MockFactory


class TestScenesWorking(unittest.TestCase):
    """Test coverage for working Scenes functionality to increase coverage."""

    def setUp(self):
        """Set up test fixtures using centralized MockFactory."""
        # Use the centralized pygame mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        
        # Get the mocked objects for direct access
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_scene_manager_switch_to_scene_fps_override_line_155(self):
        """Test SceneManager switch_to_scene FPS override (covers line 155)."""
        scene_manager = SceneManager()
        scene_manager.target_fps = 60
        
        # Create a mock scene with no target_fps
        mock_scene = Mock()
        mock_scene.target_fps = 0  # No specific FPS requirements
        mock_scene.NAME = "TestScene"
        mock_scene.load_resources = Mock()
        mock_scene.setup = Mock()
        mock_scene.background = self.mock_surface
        
        # Test switch_to_scene
        scene_manager.switch_to_scene(mock_scene)
        
        # Verify FPS was overridden
        self.assertEqual(mock_scene.target_fps, 60)

    def test_scene_manager_switch_to_scene_logging_lines_157_160(self):
        """Test SceneManager switch_to_scene logging (covers lines 157-160)."""
        scene_manager = SceneManager()
        scene_manager.target_fps = 60
        
        # Create a mock scene
        mock_scene = Mock()
        mock_scene.target_fps = 30
        mock_scene.NAME = "TestScene"
        mock_scene.load_resources = Mock()
        mock_scene.setup = Mock()
        mock_scene.background = self.mock_surface
        
        # Test switch_to_scene with logging
        with patch.object(scene_manager, "log") as mock_log:
            scene_manager.switch_to_scene(mock_scene)
            
            # Verify logging was called
            mock_log.info.assert_called()

    def test_scene_manager_switch_to_scene_proxies_lines_163_164(self):
        """Test SceneManager switch_to_scene proxies (covers lines 163-164)."""
        scene_manager = SceneManager()
        
        # Create a mock scene
        mock_scene = Mock()
        mock_scene.target_fps = 30
        mock_scene.NAME = "TestScene"
        mock_scene.load_resources = Mock()
        mock_scene.setup = Mock()
        mock_scene.background = self.mock_surface
        
        # Test switch_to_scene
        scene_manager.switch_to_scene(mock_scene)
        
        # Verify proxies were set
        self.assertEqual(len(scene_manager.proxies), 2)
        self.assertIn(scene_manager, scene_manager.proxies)
        self.assertIn(mock_scene, scene_manager.proxies)

    def test_scene_manager_switch_to_scene_dirty_flag_lines_166_167(self):
        """Test SceneManager switch_to_scene dirty flag (covers lines 166-167)."""
        scene_manager = SceneManager()
        
        # Create a mock scene
        mock_scene = Mock()
        mock_scene.target_fps = 30
        mock_scene.NAME = "TestScene"
        mock_scene.load_resources = Mock()
        mock_scene.setup = Mock()
        mock_scene.background = self.mock_surface
        
        # Test switch_to_scene
        scene_manager.switch_to_scene(mock_scene)
        
        # Verify dirty flag was set
        self.assertEqual(mock_scene.dirty, 1)

    def test_scene_manager_switch_to_scene_background_blit_lines_169_170(self):
        """Test SceneManager switch_to_scene background blit (covers lines 169-170)."""
        scene_manager = SceneManager()
        
        # Create a mock scene
        mock_scene = Mock()
        mock_scene.target_fps = 30
        mock_scene.NAME = "TestScene"
        mock_scene.load_resources = Mock()
        mock_scene.setup = Mock()
        mock_scene.background = self.mock_surface
        
        # Test switch_to_scene
        scene_manager.switch_to_scene(mock_scene)
        
        # Verify background blit was called
        self.mock_surface.blit.assert_called_with(mock_scene.background, (0, 0))

    def test_scene_manager_switch_to_scene_fps_override_line_172(self):
        """Test SceneManager switch_to_scene FPS override (covers line 172)."""
        scene_manager = SceneManager()
        scene_manager.target_fps = 30  # Initial FPS
        
        # Create a mock scene with specific FPS
        mock_scene = Mock()
        mock_scene.target_fps = 60  # Scene-specific FPS
        mock_scene.NAME = "TestScene"
        mock_scene.load_resources = Mock()
        mock_scene.setup = Mock()
        mock_scene.background = self.mock_surface
        
        # Test switch_to_scene
        scene_manager.switch_to_scene(mock_scene)
        
        # Verify FPS was overridden by scene
        self.assertEqual(scene_manager.target_fps, 60)

    def test_scene_key_down_event_with_focused_sprites_lines_904_905(self):
        """Test Scene key_down_event with focused sprites (covers lines 904-905)."""
        # Create a scene with proper mocking
        scene = Scene()
        
        # Add a focused sprite
        mock_sprite = Mock()
        mock_sprite.active = True
        scene.all_sprites = [mock_sprite]
        
        # Create a mock event for quit key
        mock_event = Mock()
        mock_event.key = 113  # pygame.K_q
        
        # Mock pygame.event.post
        with patch("pygame.event.post") as mock_post:
            scene.on_key_down_event(mock_event)
            
            # Verify quit event was NOT posted (focused sprites prevent quit)
            mock_post.assert_not_called()

    def test_scene_key_down_event_quit_keys_lines_905_907(self):
        """Test Scene key_down_event with quit keys (covers lines 905-907)."""
        # Create a scene with proper mocking
        scene = Scene()
        
        # Create a mock event for quit key
        mock_event = Mock()
        mock_event.key = 113  # pygame.K_q
        
        # Mock pygame.event.post
        with patch("pygame.event.post") as mock_post:
            scene.on_key_down_event(mock_event)
            
            # Verify quit event was posted
            mock_post.assert_called()

    def test_scene_key_down_event_escape_key_lines_905_907(self):
        """Test Scene key_down_event with escape key (covers lines 905-907)."""
        # Create a scene with proper mocking
        scene = Scene()
        
        # Create a mock event for escape key
        mock_event = Mock()
        mock_event.key = 27  # pygame.K_ESCAPE
        
        # Mock pygame.event.post
        with patch("pygame.event.post") as mock_post:
            scene.on_key_down_event(mock_event)
            
            # Verify quit event was posted
            mock_post.assert_called()

    def test_scene_manager_should_post_fps_event(self):
        """Test SceneManager _should_post_fps_event method."""
        scene_manager = SceneManager()
        
        # Test when FPS event should be posted
        current_time = 1.0
        previous_fps_time = 0.0
        scene_manager.OPTIONS["fps_refresh_rate"] = 1000  # 1 second
        
        result = scene_manager._should_post_fps_event(current_time, previous_fps_time)
        self.assertTrue(result)
        
        # Test when FPS event should NOT be posted
        current_time = 0.5
        previous_fps_time = 0.0
        
        result = scene_manager._should_post_fps_event(current_time, previous_fps_time)
        self.assertFalse(result)

    def test_scene_manager_post_fps_event(self):
        """Test SceneManager _post_fps_event method."""
        scene_manager = SceneManager()
        
        # Mock the clock and event posting
        with patch("pygame.event.post") as mock_post, \
             patch.object(scene_manager, "clock") as mock_clock:
            
            mock_clock.get_fps.return_value = 60.0
            
            # Test posting FPS event
            scene_manager._post_fps_event()
            
            # Verify FPS event was posted
            mock_post.assert_called_once()

    def test_scene_manager_play_method_simple_approach(self):
        """Test SceneManager play method with simple approach."""
        scene_manager = SceneManager()
        
        # Create a mock scene
        mock_scene = Mock()
        mock_scene.target_fps = 60
        mock_scene.rects = []
        mock_scene.dirty = 1
        mock_scene.background = self.mock_surface
        mock_scene.dt_tick = Mock()
        mock_scene.update = Mock()
        mock_scene.render = Mock()
        mock_scene.next_scene = None  # No next scene
        
        scene_manager.active_scene = mock_scene
        scene_manager.target_fps = 60
        scene_manager.quit_requested = False
        
        # Mock the main loop components with proper OPTIONS
        with patch("time.perf_counter") as mock_time, \
             patch("pygame.time.Clock") as mock_clock_class, \
             patch.object(scene_manager, "game_engine") as mock_game_engine, \
             patch("pygame.display.update") as mock_display_update, \
             patch("pygame.event.post") as mock_event_post:
            
            # Set up OPTIONS to avoid the comparison error
            scene_manager.OPTIONS["fps_refresh_rate"] = 1000  # 1 second
            
            # Mock time progression
            mock_time.side_effect = [0.0, 0.016, 0.032, 0.048]  # Simulate 60 FPS
            mock_clock_instance = Mock()
            mock_clock_instance.get_fps.return_value = 60.0
            mock_clock_class.return_value = mock_clock_instance
            mock_game_engine.process_events = Mock()
            
            # Mock the loop to exit after one iteration
            def mock_quit():
                scene_manager.quit_requested = True
            scene_manager.quit = mock_quit
            
            # Test the play method
            try:
                scene_manager.play()
            except SystemExit:
                pass  # Expected when quit is called
        
        # Verify scene methods were called
        mock_scene.dt_tick.assert_called()
        mock_scene.update.assert_called()
        mock_scene.render.assert_called()

    def test_scene_manager_play_method_with_dirty_rects(self):
        """Test SceneManager play method with dirty rects."""
        scene_manager = SceneManager()
        
        # Create a mock scene with dirty rects
        mock_scene = Mock()
        mock_scene.target_fps = 60
        mock_scene.rects = [Mock(), Mock()]  # Non-empty rects
        mock_scene.dirty = 1
        mock_scene.background = self.mock_surface
        mock_scene.dt_tick = Mock()
        mock_scene.update = Mock()
        mock_scene.render = Mock()
        mock_scene.next_scene = None  # No next scene
        
        scene_manager.active_scene = mock_scene
        scene_manager.target_fps = 60
        scene_manager.quit_requested = False
        
        # Mock the main loop components with proper OPTIONS
        with patch("time.perf_counter") as mock_time, \
             patch("pygame.time.Clock") as mock_clock_class, \
             patch.object(scene_manager, "game_engine") as mock_game_engine, \
             patch("pygame.display.update") as mock_display_update, \
             patch("pygame.event.post") as mock_event_post:
            
            # Set up OPTIONS to avoid the comparison error
            scene_manager.OPTIONS["fps_refresh_rate"] = 1000  # 1 second
            
            # Mock time progression
            mock_time.side_effect = [0.0, 0.016, 0.032, 0.048]  # Simulate 60 FPS
            mock_clock_instance = Mock()
            mock_clock_instance.get_fps.return_value = 60.0
            mock_clock_class.return_value = mock_clock_instance
            mock_game_engine.process_events = Mock()
            
            # Mock the loop to exit after one iteration
            def mock_quit():
                scene_manager.quit_requested = True
            scene_manager.quit = mock_quit
            
            # Test the play method
            try:
                scene_manager.play()
            except SystemExit:
                pass  # Expected when quit is called
        
        # Verify scene methods were called
        mock_scene.dt_tick.assert_called()
        mock_scene.update.assert_called()
        mock_scene.render.assert_called()

    def test_scene_manager_play_method_flip_update_type(self):
        """Test SceneManager play method with flip update type."""
        scene_manager = SceneManager()
        scene_manager.update_type = "flip"  # Set to flip mode
        
        # Create a mock scene
        mock_scene = Mock()
        mock_scene.target_fps = 60
        mock_scene.rects = []
        mock_scene.dirty = 1
        mock_scene.background = self.mock_surface
        mock_scene.dt_tick = Mock()
        mock_scene.update = Mock()
        mock_scene.render = Mock()
        mock_scene.next_scene = None  # No next scene
        
        scene_manager.active_scene = mock_scene
        scene_manager.target_fps = 60
        scene_manager.quit_requested = False
        
        # Mock the main loop components with proper OPTIONS
        with patch("time.perf_counter") as mock_time, \
             patch("pygame.time.Clock") as mock_clock_class, \
             patch.object(scene_manager, "game_engine") as mock_game_engine, \
             patch("pygame.display.flip") as mock_display_flip, \
             patch("pygame.event.post") as mock_event_post:
            
            # Set up OPTIONS to avoid the comparison error
            scene_manager.OPTIONS["fps_refresh_rate"] = 1000  # 1 second
            
            # Mock time progression
            mock_time.side_effect = [0.0, 0.016, 0.032, 0.048]  # Simulate 60 FPS
            mock_clock_instance = Mock()
            mock_clock_instance.get_fps.return_value = 60.0
            mock_clock_class.return_value = mock_clock_instance
            mock_game_engine.process_events = Mock()
            
            # Mock the loop to exit after one iteration
            def mock_quit():
                scene_manager.quit_requested = True
            scene_manager.quit = mock_quit
            
            # Test the play method
            try:
                scene_manager.play()
            except SystemExit:
                pass  # Expected when quit is called
        
        # Verify flip was called instead of update
        mock_display_flip.assert_called()


if __name__ == "__main__":
    unittest.main()
