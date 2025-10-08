"""Comprehensive tests for Scenes module to achieve 100% coverage.

This module tests all the refactored methods and remaining missing lines.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene, SceneManager

from test_mock_factory import MockFactory


class TestScenes100Coverage(unittest.TestCase):
    """Comprehensive tests for Scenes functionality to achieve 100% coverage."""

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

    def test_scene_manager_update_timing(self):
        """Test SceneManager _update_timing method."""
        scene_manager = SceneManager()
        scene_manager.dt = 0.0
        
        with patch("time.perf_counter") as mock_time:
            mock_time.return_value = 0.5
            
            previous_time = 0.0
            current_time = 0.1
            
            new_previous, new_current = scene_manager._update_timing(previous_time, current_time)
            
            self.assertEqual(new_previous, 0.1)
            self.assertEqual(new_current, 0.5)
            self.assertEqual(scene_manager.dt, 0.5)

    def test_scene_manager_get_collided_sprites(self):
        """Test SceneManager _get_collided_sprites method."""
        scene_manager = SceneManager()
        scene_manager.sprites_at_position = Mock(return_value=[Mock(), Mock()])
        
        position = (100, 200)
        result = scene_manager._get_collided_sprites(position)
        
        scene_manager.sprites_at_position.assert_called_once_with(pos=position)
        self.assertEqual(len(result), 2)

    def test_scene_manager_get_focusable_sprites(self):
        """Test SceneManager _get_focusable_sprites method."""
        scene_manager = SceneManager()
        
        # Create mock sprites
        focusable_sprite1 = Mock()
        focusable_sprite1.focusable = True
        
        focusable_sprite2 = Mock()
        focusable_sprite2.focusable = True
        
        non_focusable_sprite = Mock()
        non_focusable_sprite.focusable = False
        
        collided_sprites = [focusable_sprite1, non_focusable_sprite, focusable_sprite2]
        
        result = scene_manager._get_focusable_sprites(collided_sprites)
        
        self.assertEqual(len(result), 2)
        self.assertIn(focusable_sprite1, result)
        self.assertIn(focusable_sprite2, result)
        self.assertNotIn(non_focusable_sprite, result)

    def test_scene_manager_get_focused_sprites(self):
        """Test SceneManager _get_focused_sprites method."""
        scene_manager = SceneManager()
        
        # Create mock sprites
        focused_sprite1 = Mock()
        focused_sprite1.active = True
        
        focused_sprite2 = Mock()
        focused_sprite2.active = True
        
        inactive_sprite = Mock()
        inactive_sprite.active = False
        
        scene_manager.all_sprites = [focused_sprite1, inactive_sprite, focused_sprite2]
        
        result = scene_manager._get_focused_sprites()
        
        self.assertEqual(len(result), 2)
        self.assertIn(focused_sprite1, result)
        self.assertIn(focused_sprite2, result)
        self.assertNotIn(inactive_sprite, result)

    def test_scene_manager_has_focusable_sprites_true(self):
        """Test SceneManager _has_focusable_sprites with focusable sprites."""
        scene_manager = SceneManager()
        
        # Create mock sprites with focusable ones
        focusable_sprite = Mock()
        focusable_sprite.focusable = True
        
        non_focusable_sprite = Mock()
        non_focusable_sprite.focusable = False
        
        collided_sprites = [focusable_sprite, non_focusable_sprite]
        
        result = scene_manager._has_focusable_sprites(collided_sprites)
        
        self.assertTrue(result)

    def test_scene_manager_has_focusable_sprites_false(self):
        """Test SceneManager _has_focusable_sprites with no focusable sprites."""
        scene_manager = SceneManager()
        
        # Create mock sprites with no focusable ones
        non_focusable_sprite1 = Mock()
        non_focusable_sprite1.focusable = False
        
        non_focusable_sprite2 = Mock()
        non_focusable_sprite2.focusable = False
        
        collided_sprites = [non_focusable_sprite1, non_focusable_sprite2]
        
        result = scene_manager._has_focusable_sprites(collided_sprites)
        
        self.assertFalse(result)

    def test_scene_manager_unfocus_sprites(self):
        """Test SceneManager _unfocus_sprites method."""
        scene_manager = SceneManager()
        
        # Create mock sprites
        sprite1 = Mock()
        sprite1.active = True
        sprite1.on_focus_lost = Mock()
        
        sprite2 = Mock()
        sprite2.active = True
        # No on_focus_lost method
        
        focused_sprites = [sprite1, sprite2]
        
        with patch.object(scene_manager, "log") as mock_log:
            scene_manager._unfocus_sprites(focused_sprites)
            
            # Verify sprites were unfocused
            self.assertFalse(sprite1.active)
            self.assertFalse(sprite2.active)
            
            # Verify focus_lost was called for sprite1
            sprite1.on_focus_lost.assert_called_once()
            
            # Verify logging
            self.assertEqual(mock_log.debug.call_count, 2)

    def test_scene_manager_handle_focus_management_no_focusable(self):
        """Test SceneManager _handle_focus_management with no focusable sprites."""
        scene_manager = SceneManager()
        
        # Create mock sprites with no focusable ones
        non_focusable_sprite = Mock()
        non_focusable_sprite.focusable = False
        
        collided_sprites = [non_focusable_sprite]
        
        with patch.object(scene_manager, "_get_focused_sprites") as mock_get_focused, \
             patch.object(scene_manager, "_unfocus_sprites") as mock_unfocus, \
             patch.object(scene_manager, "log") as mock_log:
            
            mock_get_focused.return_value = [Mock(), Mock()]
            
            scene_manager._handle_focus_management(collided_sprites)
            
            # Verify methods were called
            mock_get_focused.assert_called_once()
            mock_unfocus.assert_called_once()
            mock_log.debug.assert_called_with("Click outside focusable sprites - unfocusing")

    def test_scene_manager_handle_focus_management_with_focusable(self):
        """Test SceneManager _handle_focus_management with focusable sprites."""
        scene_manager = SceneManager()
        
        # Create mock sprites with focusable ones
        focusable_sprite = Mock()
        focusable_sprite.focusable = True
        
        collided_sprites = [focusable_sprite]
        
        with patch.object(scene_manager, "_get_focused_sprites") as mock_get_focused, \
             patch.object(scene_manager, "_unfocus_sprites") as mock_unfocus, \
             patch.object(scene_manager, "log") as mock_log:
            
            mock_get_focused.return_value = [Mock(), Mock()]
            
            scene_manager._handle_focus_management(collided_sprites)
            
            # Verify methods were called
            mock_get_focused.assert_called_once()
            # Should not unfocus when there are focusable sprites
            mock_unfocus.assert_not_called()

    def test_scene_manager_getattr_event_proxy(self):
        """Test SceneManager __getattr__ with event method."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        scene_manager.game_engine = Mock()
        
        # Mock the event method on active scene
        mock_event_handler = Mock()
        scene_manager.active_scene.on_test_event = mock_event_handler
        
        # Test event method proxying
        result = scene_manager.__getattr__("on_test_event")
        
        self.assertEqual(result, mock_event_handler)

    def test_scene_manager_getattr_event_proxy_fallback(self):
        """Test SceneManager __getattr__ with event method fallback to game engine."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        scene_manager.game_engine = Mock()
        
        # Mock the event method on game engine (not on active scene)
        mock_event_handler = Mock()
        scene_manager.game_engine.on_test_event = mock_event_handler
        
        # Remove the method from active scene to trigger fallback
        del scene_manager.active_scene.on_test_event
        
        # Test event method proxying with fallback
        result = scene_manager.__getattr__("on_test_event")
        
        self.assertEqual(result, mock_event_handler)

    def test_scene_manager_getattr_non_event(self):
        """Test SceneManager __getattr__ with non-event method."""
        scene_manager = SceneManager()
        
        # Test non-event method should raise AttributeError
        with self.assertRaises(AttributeError) as context:
            scene_manager.__getattr__("non_event_method")
        
        self.assertIn("'SceneManager' object has no attribute 'non_event_method'", str(context.exception))

    def test_scene_left_mouse_button_down_event(self):
        """Test Scene on_left_mouse_button_down_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
        # Create mock sprites
        mock_sprite1 = Mock()
        mock_sprite1.focusable = True
        mock_sprite1.on_left_mouse_button_down_event = Mock()
        
        mock_sprite2 = Mock()
        mock_sprite2.focusable = False
        mock_sprite2.on_left_mouse_button_down_event = Mock()
        
        collided_sprites = [mock_sprite1, mock_sprite2]
        
        with patch.object(scene, "_get_collided_sprites") as mock_get_collided, \
             patch.object(scene, "_get_focusable_sprites") as mock_get_focusable, \
             patch.object(scene, "_get_focused_sprites") as mock_get_focused, \
             patch.object(scene, "_handle_focus_management") as mock_handle_focus, \
             patch.object(scene, "log") as mock_log:
            
            mock_get_collided.return_value = collided_sprites
            mock_get_focusable.return_value = [mock_sprite1]
            mock_get_focused.return_value = []
            
            scene.on_left_mouse_button_down_event(mock_event)
            
            # Verify methods were called
            mock_get_collided.assert_called_once_with((100, 200))
            mock_get_focusable.assert_called_once_with(collided_sprites)
            mock_get_focused.assert_called_once()
            mock_handle_focus.assert_called_once_with(collided_sprites)
            
            # Verify sprite event handlers were called
            mock_sprite1.on_left_mouse_button_down_event.assert_called_once_with(mock_event)
            mock_sprite2.on_left_mouse_button_down_event.assert_called_once_with(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_manager_start_method_timing(self):
        """Test SceneManager start method timing logic."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        scene_manager.quit_requested = False
        scene_manager.target_fps = 60
        scene_manager.clock = Mock()
        scene_manager.screen = Mock()
        scene_manager.update_type = "update"
        scene_manager.active_scene.rects = []
        scene_manager.active_scene.next_scene = None
        
        with patch("time.perf_counter") as mock_time, \
             patch.object(scene_manager, "_tick_clock") as mock_tick, \
             patch.object(scene_manager, "_update_scene") as mock_update, \
             patch.object(scene_manager, "_process_events") as mock_process, \
             patch.object(scene_manager, "_render_scene") as mock_render, \
             patch.object(scene_manager, "_update_display") as mock_display, \
             patch.object(scene_manager, "_should_post_fps_event") as mock_fps_check, \
             patch.object(scene_manager, "_post_fps_event") as mock_fps_post, \
             patch.object(scene_manager, "switch_to_scene") as mock_switch, \
             patch.object(scene_manager, "_log_quit_info") as mock_log, \
             patch.object(scene_manager, "terminate") as mock_terminate:
            
            # Mock time progression to exit after one iteration
            mock_time.side_effect = [0.0, 0.016, 0.032, 0.048]
            mock_fps_check.return_value = False
            mock_terminate.return_value = None
            
            # Mock the loop to exit
            def mock_quit():
                scene_manager.quit_requested = True
            scene_manager.quit = mock_quit
            
            # Test the start method
            try:
                scene_manager.start()
            except SystemExit:
                pass  # Expected when quit is called
        
        # Verify core methods were called
        mock_tick.assert_called()
        mock_update.assert_called()
        mock_process.assert_called()
        mock_render.assert_called()
        mock_display.assert_called()

    def test_scene_manager_start_method_fps_event(self):
        """Test SceneManager start method with FPS event posting."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        scene_manager.quit_requested = False
        scene_manager.target_fps = 60
        scene_manager.clock = Mock()
        scene_manager.screen = Mock()
        scene_manager.update_type = "update"
        scene_manager.active_scene.rects = []
        scene_manager.active_scene.next_scene = None
        
        with patch("time.perf_counter") as mock_time, \
             patch.object(scene_manager, "_tick_clock") as mock_tick, \
             patch.object(scene_manager, "_update_scene") as mock_update, \
             patch.object(scene_manager, "_process_events") as mock_process, \
             patch.object(scene_manager, "_render_scene") as mock_render, \
             patch.object(scene_manager, "_update_display") as mock_display, \
             patch.object(scene_manager, "_should_post_fps_event") as mock_fps_check, \
             patch.object(scene_manager, "_post_fps_event") as mock_fps_post, \
             patch.object(scene_manager, "switch_to_scene") as mock_switch, \
             patch.object(scene_manager, "_log_quit_info") as mock_log, \
             patch.object(scene_manager, "terminate") as mock_terminate:
            
            # Mock time progression
            mock_time.side_effect = [0.0, 0.016, 0.032, 0.048]
            mock_fps_check.return_value = True  # Should post FPS event
            mock_terminate.return_value = None
            
            # Mock the loop to exit
            def mock_quit():
                scene_manager.quit_requested = True
            scene_manager.quit = mock_quit
            
            # Test the start method
            try:
                scene_manager.start()
            except SystemExit:
                pass  # Expected when quit is called
        
        # Verify FPS event was posted
        mock_fps_post.assert_called()

    def test_scene_manager_start_method_scene_switch(self):
        """Test SceneManager start method with scene switching."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        scene_manager.quit_requested = False
        scene_manager.target_fps = 60
        scene_manager.clock = Mock()
        scene_manager.screen = Mock()
        scene_manager.update_type = "update"
        scene_manager.active_scene.rects = []
        
        # Create a next scene
        next_scene = Mock()
        scene_manager.active_scene.next_scene = next_scene
        
        with patch("time.perf_counter") as mock_time, \
             patch.object(scene_manager, "_tick_clock") as mock_tick, \
             patch.object(scene_manager, "_update_scene") as mock_update, \
             patch.object(scene_manager, "_process_events") as mock_process, \
             patch.object(scene_manager, "_render_scene") as mock_render, \
             patch.object(scene_manager, "_update_display") as mock_display, \
             patch.object(scene_manager, "_should_post_fps_event") as mock_fps_check, \
             patch.object(scene_manager, "_post_fps_event") as mock_fps_post, \
             patch.object(scene_manager, "switch_to_scene") as mock_switch, \
             patch.object(scene_manager, "_log_quit_info") as mock_log, \
             patch.object(scene_manager, "terminate") as mock_terminate:
            
            # Mock time progression
            mock_time.side_effect = [0.0, 0.016, 0.032, 0.048]
            mock_fps_check.return_value = False
            mock_terminate.return_value = None
            
            # Mock the loop to exit
            def mock_quit():
                scene_manager.quit_requested = True
            scene_manager.quit = mock_quit
            
            # Test the start method
            try:
                scene_manager.start()
            except SystemExit:
                pass  # Expected when quit is called
        
        # Verify scene switching was called
        mock_switch.assert_called_with(next_scene)


if __name__ == "__main__":
    unittest.main()
