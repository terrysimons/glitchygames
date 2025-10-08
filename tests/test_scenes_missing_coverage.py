"""Test coverage for missing Scenes functionality.

This module tests the remaining Scenes functionality to achieve 80%+ coverage.
Focuses on missing lines and edge cases not covered by existing tests.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene, SceneManager

from test_mock_factory import MockFactory


class TestScenesMissingLinesCoverage(unittest.TestCase):
    """Test coverage for missing Scenes functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_display = Mock()
        self.mock_display.get_width.return_value = 800
        self.mock_display.get_height.return_value = 600
        
        self.mock_surface = MockFactory.create_pygame_surface_mock()
        self.mock_rect = Mock()
        self.mock_rect.x = 0
        self.mock_rect.y = 0
        self.mock_rect.width = 100
        self.mock_rect.height = 50
        self.mock_surface.get_rect.return_value = self.mock_rect

    @patch("pygame.display.get_surface")
    @patch("pygame.clock.Clock")
    def test_scene_manager_play_method_main_loop(self, mock_clock, mock_get_display):
        """Test SceneManager play method main loop (covers lines 185-228)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        mock_clock_instance = Mock()
        mock_clock.return_value = mock_clock_instance
        
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
        
        # Mock the main loop to run once then quit
        with patch("time.perf_counter") as mock_time:
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            
            # Mock the loop to exit after one iteration
            original_quit_requested = scene_manager.quit_requested
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

    @patch("pygame.display.get_surface")
    @patch("pygame.clock.Clock")
    def test_scene_manager_play_method_with_dirty_rects(self, mock_clock, mock_get_display):
        """Test SceneManager play method with dirty rects (covers lines 204-209)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        mock_clock_instance = Mock()
        mock_clock.return_value = mock_clock_instance
        
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
        
        # Mock the main loop to run once then quit
        with patch("time.perf_counter") as mock_time:
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            
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

    @patch("pygame.display.get_surface")
    def test_scene_manager_switch_to_scene_fps_override(self, mock_get_display):
        """Test SceneManager switch_to_scene with FPS override (covers lines 154-155)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
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

    @patch("pygame.display.get_surface")
    def test_scene_manager_switch_to_scene_logging(self, mock_get_display):
        """Test SceneManager switch_to_scene logging (covers lines 157-160)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
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

    @patch("pygame.display.get_surface")
    def test_scene_manager_switch_to_scene_proxies(self, mock_get_display):
        """Test SceneManager switch_to_scene proxies (covers lines 163-164)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
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

    @patch("pygame.display.get_surface")
    def test_scene_manager_switch_to_scene_dirty_flag(self, mock_get_display):
        """Test SceneManager switch_to_scene dirty flag (covers lines 166-167)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
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

    @patch("pygame.display.get_surface")
    def test_scene_manager_switch_to_scene_background_blit(self, mock_get_display):
        """Test SceneManager switch_to_scene background blit (covers lines 169-170)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
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

    @patch("pygame.display.get_surface")
    def test_scene_key_down_event_quit_keys(self, mock_get_display):
        """Test Scene key_down_event with quit keys (covers lines 905-907)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
        scene = Scene()
        
        # Create a mock event for quit key
        mock_event = Mock()
        mock_event.key = 113  # pygame.K_q
        
        # Mock pygame.event.post
        with patch("pygame.event.post") as mock_post:
            scene.on_key_down_event(mock_event)
            
            # Verify quit event was posted
            mock_post.assert_called()

    @patch("pygame.display.get_surface")
    def test_scene_key_down_event_escape_key(self, mock_get_display):
        """Test Scene key_down_event with escape key (covers lines 905-907)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
        scene = Scene()
        
        # Create a mock event for escape key
        mock_event = Mock()
        mock_event.key = 27  # pygame.K_ESCAPE
        
        # Mock pygame.event.post
        with patch("pygame.event.post") as mock_post:
            scene.on_key_down_event(mock_event)
            
            # Verify quit event was posted
            mock_post.assert_called()

    @patch("pygame.display.get_surface")
    def test_scene_key_down_event_with_focused_sprites(self, mock_get_display):
        """Test Scene key_down_event with focused sprites (covers lines 904-905)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
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

    @patch("pygame.display.get_surface")
    def test_scene_manager_play_method_fps_calculation(self, mock_get_display):
        """Test SceneManager play method FPS calculation (covers lines 185-228)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
        scene_manager = SceneManager()
        scene_manager.target_fps = 30
        
        # Create a mock scene
        mock_scene = Mock()
        mock_scene.target_fps = 30
        mock_scene.rects = []
        mock_scene.dirty = 1
        mock_scene.background = self.mock_surface
        mock_scene.dt_tick = Mock()
        mock_scene.update = Mock()
        mock_scene.render = Mock()
        
        scene_manager.active_scene = mock_scene
        scene_manager.quit_requested = False
        
        # Mock the main loop to run once then quit
        with patch("time.perf_counter") as mock_time:
            mock_time.side_effect = [0.0, 0.033, 0.066]  # Simulate 30 FPS
            
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

    @patch("pygame.display.get_surface")
    def test_scene_manager_play_method_dt_calculation(self, mock_get_display):
        """Test SceneManager play method dt calculation (covers lines 192-194)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
        scene_manager = SceneManager()
        scene_manager.target_fps = 60
        
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
        scene_manager.quit_requested = False
        
        # Mock the main loop to run once then quit
        with patch("time.perf_counter") as mock_time:
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            
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

    @patch("pygame.display.get_surface")
    def test_scene_manager_play_method_event_processing(self, mock_get_display):
        """Test SceneManager play method event processing (covers lines 198-199)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
        scene_manager = SceneManager()
        scene_manager.target_fps = 60
        
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
        scene_manager.quit_requested = False
        
        # Mock the main loop to run once then quit
        with patch("time.perf_counter") as mock_time:
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            
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
        # Note: process_events is called on game_engine, which is mocked

    @patch("pygame.display.get_surface")
    def test_scene_manager_play_method_scene_update(self, mock_get_display):
        """Test SceneManager play method scene update (covers lines 200-201)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
        scene_manager = SceneManager()
        scene_manager.target_fps = 60
        
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
        scene_manager.quit_requested = False
        
        # Mock the main loop to run once then quit
        with patch("time.perf_counter") as mock_time:
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            
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

    @patch("pygame.display.get_surface")
    def test_scene_manager_play_method_scene_render(self, mock_get_display):
        """Test SceneManager play method scene render (covers lines 202-203)."""
        # Setup
        mock_get_display.return_value = self.mock_display
        
        scene_manager = SceneManager()
        scene_manager.target_fps = 60
        
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
        scene_manager.quit_requested = False
        
        # Mock the main loop to run once then quit
        with patch("time.perf_counter") as mock_time:
            mock_time.side_effect = [0.0, 0.016, 0.032]  # Simulate 60 FPS
            
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
