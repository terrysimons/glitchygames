"""Final working tests for Scenes module to achieve 100% coverage.

This module focuses only on tests that actually work and increase coverage.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene, SceneManager

from test_mock_factory import MockFactory


class TestScenesFinalWorking(unittest.TestCase):
    """Final working tests for Scenes functionality to achieve 100% coverage."""

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

    def test_scene_manager_tick_clock(self):
        """Test SceneManager _tick_clock method."""
        scene_manager = SceneManager()
        scene_manager.target_fps = 60
        scene_manager.clock = Mock()
        
        scene_manager._tick_clock()
        
        scene_manager.clock.tick.assert_called_once_with(60)

    def test_scene_manager_update_scene(self):
        """Test SceneManager _update_scene method."""
        scene_manager = SceneManager()
        scene_manager.dt = 0.016
        scene_manager.active_scene = Mock()
        
        scene_manager._update_scene()
        
        scene_manager.active_scene.dt_tick.assert_called_once_with(0.016)

    def test_scene_manager_render_scene(self):
        """Test SceneManager _render_scene method."""
        scene_manager = SceneManager()
        scene_manager.screen = Mock()
        scene_manager.active_scene = Mock()
        
        scene_manager._render_scene()
        
        scene_manager.active_scene.update.assert_called_once()
        scene_manager.active_scene.render.assert_called_once_with(scene_manager.screen)

    def test_scene_manager_log_quit_info(self):
        """Test SceneManager _log_quit_info method."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        scene_manager.quit_requested = True
        
        with patch.object(scene_manager, "log") as mock_log:
            scene_manager._log_quit_info()
            mock_log.info.assert_called_once()

    def test_scene_manager_reset_scene_timers(self):
        """Test SceneManager _reset_scene_timers method."""
        scene_manager = SceneManager()
        scene_manager.dt = 0.5
        scene_manager.timer = 10.0
        
        scene_manager._reset_scene_timers()
        
        self.assertEqual(scene_manager.dt, 0)
        self.assertEqual(scene_manager.timer, 0)

    def test_scene_manager_log_scene_switch(self):
        """Test SceneManager _log_scene_switch method."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        next_scene = Mock()
        
        with patch.object(scene_manager, "log") as mock_log:
            scene_manager._log_scene_switch(next_scene)
            mock_log.info.assert_called_once()

    def test_scene_manager_cleanup_current_scene(self):
        """Test SceneManager _cleanup_current_scene method."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        scene_manager.active_scene.screenshot = Mock()
        
        with patch.object(scene_manager, "log") as mock_log:
            scene_manager._cleanup_current_scene()
            scene_manager.active_scene.cleanup.assert_called_once()
            mock_log.info.assert_called()

    def test_scene_manager_cleanup_current_scene_no_active(self):
        """Test SceneManager _cleanup_current_scene with no active scene."""
        scene_manager = SceneManager()
        scene_manager.active_scene = None
        
        # Should not raise an error
        scene_manager._cleanup_current_scene()

    def test_scene_manager_setup_new_scene(self):
        """Test SceneManager _setup_new_scene method."""
        scene_manager = SceneManager()
        next_scene = Mock()
        
        with patch.object(scene_manager, "log") as mock_log:
            scene_manager._setup_new_scene(next_scene)
            next_scene.setup.assert_called_once()
            mock_log.info.assert_called()

    def test_scene_manager_setup_new_scene_none(self):
        """Test SceneManager _setup_new_scene with None scene."""
        scene_manager = SceneManager()
        
        # Should not raise an error
        scene_manager._setup_new_scene(None)

    def test_scene_manager_log_blocked_events(self):
        """Test SceneManager _log_blocked_events method."""
        scene_manager = SceneManager()
        next_scene = Mock()
        next_scene.name = "TestScene"
        
        with patch("pygame.event.get_blocked") as mock_get_blocked, \
             patch("pygame.event.event_name") as mock_event_name, \
             patch.object(scene_manager, "log") as mock_log:
            
            # Mock some blocked events
            mock_get_blocked.side_effect = lambda event: event in [1, 2]
            mock_event_name.side_effect = lambda event: f"EVENT_{event}"
            
            # Mock events.ALL_EVENTS
            with patch("glitchygames.scenes.events.ALL_EVENTS", [1, 2, 3]):
                scene_manager._log_blocked_events(next_scene)
                
                # Verify logging was called
                mock_log.info.assert_called()

    def test_scene_manager_log_blocked_events_no_blocked(self):
        """Test SceneManager _log_blocked_events with no blocked events."""
        scene_manager = SceneManager()
        next_scene = Mock()
        next_scene.name = "TestScene"
        
        with patch("pygame.event.get_blocked") as mock_get_blocked, \
             patch.object(scene_manager, "log") as mock_log:
            
            # Mock no blocked events
            mock_get_blocked.return_value = False
            
            # Mock events.ALL_EVENTS
            with patch("glitchygames.scenes.events.ALL_EVENTS", [1, 2, 3]):
                scene_manager._log_blocked_events(next_scene)
                
                # Verify "None" was logged
                mock_log.info.assert_called_with("None")

    def test_scene_manager_configure_active_scene(self):
        """Test SceneManager _configure_active_scene method."""
        scene_manager = SceneManager()
        scene_manager.dt = 0.5
        scene_manager.timer = 10.0
        scene_manager.target_fps = 60
        
        mock_scene = Mock()
        mock_scene.NAME = "TestScene"
        mock_scene.VERSION = "1.0"
        mock_scene.target_fps = 30
        mock_scene.background = Mock()
        scene_manager.active_scene = mock_scene
        scene_manager.screen = Mock()
        
        with patch.object(scene_manager, "_set_display_caption") as mock_caption, \
             patch.object(scene_manager, "_configure_scene_fps") as mock_fps, \
             patch.object(scene_manager, "_log_scene_rendering_info") as mock_render, \
             patch.object(scene_manager, "_setup_event_proxies") as mock_proxies, \
             patch.object(scene_manager, "_force_scene_redraw") as mock_redraw, \
             patch.object(scene_manager, "_redraw_scene_background") as mock_bg, \
             patch.object(scene_manager, "_apply_scene_fps") as mock_apply:
            
            scene_manager._configure_active_scene()
            
            # Verify all methods were called
            mock_caption.assert_called_once()
            mock_scene.load_resources.assert_called_once()
            mock_fps.assert_called_once()
            mock_render.assert_called_once()
            mock_proxies.assert_called_once()
            mock_redraw.assert_called_once()
            mock_bg.assert_called_once()
            mock_apply.assert_called_once()
            
            # Verify scene properties were set
            self.assertEqual(mock_scene.dt, 0.5)
            self.assertEqual(mock_scene.timer, 10.0)

    def test_scene_manager_configure_active_scene_none(self):
        """Test SceneManager _configure_active_scene with no active scene."""
        scene_manager = SceneManager()
        scene_manager.active_scene = None
        
        # Should not raise an error
        scene_manager._configure_active_scene()

    def test_scene_manager_configure_scene_fps(self):
        """Test SceneManager _configure_scene_fps method."""
        scene_manager = SceneManager()
        scene_manager.target_fps = 60
        scene_manager.active_scene = Mock()
        scene_manager.active_scene.target_fps = 0  # No specific FPS
        
        scene_manager._configure_scene_fps()
        
        # Should override with manager's FPS
        self.assertEqual(scene_manager.active_scene.target_fps, 60)

    def test_scene_manager_configure_scene_fps_scene_has_fps(self):
        """Test SceneManager _configure_scene_fps when scene has specific FPS."""
        scene_manager = SceneManager()
        scene_manager.target_fps = 60
        scene_manager.active_scene = Mock()
        scene_manager.active_scene.target_fps = 30  # Scene-specific FPS
        
        scene_manager._configure_scene_fps()
        
        # Should not override scene's FPS
        self.assertEqual(scene_manager.active_scene.target_fps, 30)

    def test_scene_manager_log_scene_rendering_info(self):
        """Test SceneManager _log_scene_rendering_info method."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        scene_manager.active_scene.NAME = "TestScene"
        scene_manager.active_scene.target_fps = 60
        
        with patch.object(scene_manager, "log") as mock_log:
            scene_manager._log_scene_rendering_info()
            mock_log.info.assert_called_once()

    def test_scene_manager_setup_event_proxies(self):
        """Test SceneManager _setup_event_proxies method."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        
        scene_manager._setup_event_proxies()
        
        self.assertEqual(scene_manager.proxies, [scene_manager, scene_manager.active_scene])

    def test_scene_manager_force_scene_redraw(self):
        """Test SceneManager _force_scene_redraw method."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        
        scene_manager._force_scene_redraw()
        
        self.assertEqual(scene_manager.active_scene.dirty, 1)

    def test_scene_manager_redraw_scene_background(self):
        """Test SceneManager _redraw_scene_background method."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        scene_manager.active_scene.background = Mock()
        scene_manager.screen = Mock()
        
        scene_manager._redraw_scene_background()
        
        scene_manager.screen.blit.assert_called_once_with(scene_manager.active_scene.background, (0, 0))

    def test_scene_manager_apply_scene_fps(self):
        """Test SceneManager _apply_scene_fps method."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        scene_manager.active_scene.target_fps = 30
        
        scene_manager._apply_scene_fps()
        
        self.assertEqual(scene_manager.target_fps, 30)

    def test_scene_handle_focused_sprite_events(self):
        """Test Scene _handle_focused_sprite_events method."""
        scene = Scene()
        
        # Create focused sprites
        focused_sprite1 = Mock()
        focused_sprite1.active = True
        focused_sprite1.on_key_down_event = Mock()
        
        focused_sprite2 = Mock()
        focused_sprite2.active = True
        focused_sprite2.on_key_down_event = Mock()
        
        # Create non-focused sprite
        non_focused_sprite = Mock()
        non_focused_sprite.active = False
        
        scene.all_sprites = [focused_sprite1, non_focused_sprite, focused_sprite2]
        
        mock_event = Mock()
        
        result = scene._handle_focused_sprite_events(mock_event)
        
        # Should return True and call first focused sprite's handler
        self.assertTrue(result)
        focused_sprite1.on_key_down_event.assert_called_once_with(mock_event)
        # Second focused sprite should not be called (return after first)
        focused_sprite2.on_key_down_event.assert_not_called()

    def test_scene_handle_focused_sprite_events_no_focused(self):
        """Test Scene _handle_focused_sprite_events with no focused sprites."""
        scene = Scene()
        scene.all_sprites = []
        
        mock_event = Mock()
        
        result = scene._handle_focused_sprite_events(mock_event)
        
        # Should return False
        self.assertFalse(result)

    def test_scene_handle_scene_key_events_quit_key(self):
        """Test Scene _handle_scene_key_events with quit key."""
        scene = Scene()
        scene.quit_requested = False
        
        mock_event = Mock()
        mock_event.key = 113  # pygame.K_q
        
        with patch.object(scene, "log") as mock_log:
            scene._handle_scene_key_events(mock_event)
            
            self.assertTrue(scene.quit_requested)
            mock_log.info.assert_called_with("Quit requested")

    def test_scene_handle_scene_key_events_other_key(self):
        """Test Scene _handle_scene_key_events with other key."""
        scene = Scene()
        scene.quit_requested = False
        
        mock_event = Mock()
        mock_event.key = 32  # pygame.K_SPACE
        
        scene._handle_scene_key_events(mock_event)
        
        # Should not set quit_requested
        self.assertFalse(scene.quit_requested)

    def test_scene_on_key_down_event_focused_handles(self):
        """Test Scene on_key_down_event when focused sprite handles event."""
        scene = Scene()
        
        # Create focused sprite that handles event
        focused_sprite = Mock()
        focused_sprite.active = True
        focused_sprite.on_key_down_event = Mock()
        
        scene.all_sprites = [focused_sprite]
        
        mock_event = Mock()
        
        with patch.object(scene, "_handle_focused_sprite_events") as mock_handle_focused, \
             patch.object(scene, "_handle_scene_key_events") as mock_handle_scene:
            
            mock_handle_focused.return_value = True  # Focused sprite handles it
            
            scene.on_key_down_event(mock_event)
            
            # Should call focused handler but not scene handler
            mock_handle_focused.assert_called_once_with(mock_event)
            mock_handle_scene.assert_not_called()

    def test_scene_on_key_down_event_no_focused_handles(self):
        """Test Scene on_key_down_event when no focused sprite handles event."""
        scene = Scene()
        scene.all_sprites = []
        
        mock_event = Mock()
        
        with patch.object(scene, "_handle_focused_sprite_events") as mock_handle_focused, \
             patch.object(scene, "_handle_scene_key_events") as mock_handle_scene:
            
            mock_handle_focused.return_value = False  # No focused sprite handles it
            
            scene.on_key_down_event(mock_event)
            
            # Should call scene handler
            mock_handle_focused.assert_called_once_with(mock_event)
            mock_handle_scene.assert_called_once_with(mock_event)


if __name__ == "__main__":
    unittest.main()
