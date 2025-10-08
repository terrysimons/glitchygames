"""Final tests for missing Scenes functionality to reach 80%+ coverage.

This module tests specific missing lines to achieve 80%+ coverage.
Focuses on the remaining 9 lines needed to reach 80%.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene, SceneManager

from test_mock_factory import MockFactory


class TestScenesFinalCoverage(unittest.TestCase):
    """Test coverage for final missing Scenes functionality."""

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

    def test_scene_manager_play_method_main_loop_lines_185_228(self):
        """Test SceneManager play method main loop (covers lines 185-228)."""
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
        
        scene_manager.active_scene = mock_scene
        scene_manager.target_fps = 60
        scene_manager.quit_requested = False
        
        # Mock the main loop components
        with patch("time.perf_counter") as mock_time, \
             patch("pygame.clock.Clock") as mock_clock_class, \
             patch.object(scene_manager, "game_engine") as mock_game_engine:
            
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            mock_clock_instance = Mock()
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

    def test_scene_manager_play_method_with_dirty_rects_lines_204_209(self):
        """Test SceneManager play method with dirty rects (covers lines 204-209)."""
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
        
        scene_manager.active_scene = mock_scene
        scene_manager.target_fps = 60
        scene_manager.quit_requested = False
        
        # Mock the main loop components
        with patch("time.perf_counter") as mock_time, \
             patch("pygame.clock.Clock") as mock_clock_class, \
             patch.object(scene_manager, "game_engine") as mock_game_engine, \
             patch("pygame.display.update") as mock_display_update:
            
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            mock_clock_instance = Mock()
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

    def test_scene_manager_play_method_dt_calculation_lines_192_194(self):
        """Test SceneManager play method dt calculation (covers lines 192-194)."""
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
        
        scene_manager.active_scene = mock_scene
        scene_manager.target_fps = 60
        scene_manager.quit_requested = False
        
        # Mock the main loop components
        with patch("time.perf_counter") as mock_time, \
             patch("pygame.clock.Clock") as mock_clock_class, \
             patch.object(scene_manager, "game_engine") as mock_game_engine:
            
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            mock_clock_instance = Mock()
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
        
        # Verify dt was calculated and passed to scene
        mock_scene.dt_tick.assert_called()
        call_args = mock_scene.dt_tick.call_args[0]
        self.assertGreater(call_args[0], 0)  # dt should be positive

    def test_scene_manager_play_method_event_processing_lines_198_199(self):
        """Test SceneManager play method event processing (covers lines 198-199)."""
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
        
        scene_manager.active_scene = mock_scene
        scene_manager.target_fps = 60
        scene_manager.quit_requested = False
        
        # Mock the main loop components
        with patch("time.perf_counter") as mock_time, \
             patch("pygame.clock.Clock") as mock_clock_class, \
             patch.object(scene_manager, "game_engine") as mock_game_engine:
            
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            mock_clock_instance = Mock()
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
        
        # Verify event processing was called
        mock_game_engine.process_events.assert_called()

    def test_scene_manager_play_method_scene_update_lines_200_201(self):
        """Test SceneManager play method scene update (covers lines 200-201)."""
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
        
        scene_manager.active_scene = mock_scene
        scene_manager.target_fps = 60
        scene_manager.quit_requested = False
        
        # Mock the main loop components
        with patch("time.perf_counter") as mock_time, \
             patch("pygame.clock.Clock") as mock_clock_class, \
             patch.object(scene_manager, "game_engine") as mock_game_engine:
            
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            mock_clock_instance = Mock()
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
        
        # Verify scene update was called
        mock_scene.update.assert_called()

    def test_scene_manager_play_method_scene_render_lines_202_203(self):
        """Test SceneManager play method scene render (covers lines 202-203)."""
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
        
        scene_manager.active_scene = mock_scene
        scene_manager.target_fps = 60
        scene_manager.quit_requested = False
        
        # Mock the main loop components
        with patch("time.perf_counter") as mock_time, \
             patch("pygame.clock.Clock") as mock_clock_class, \
             patch.object(scene_manager, "game_engine") as mock_game_engine:
            
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            mock_clock_instance = Mock()
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
        
        # Verify scene render was called
        mock_scene.render.assert_called_with(scene_manager.screen)


if __name__ == "__main__":
    unittest.main()
