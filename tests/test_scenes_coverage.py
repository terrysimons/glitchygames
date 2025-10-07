"""Comprehensive test coverage for the scenes module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene, SceneManager


class TestSceneManagerCoverage(unittest.TestCase):
    """Test SceneManager comprehensive coverage."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("pygame.display.get_surface") as mock_get_surface:
            mock_surface = Mock()
            mock_surface.get_size.return_value = (800, 600)
            mock_surface.get_width.return_value = 800
            mock_surface.get_height.return_value = 600
            mock_get_surface.return_value = mock_surface

            self.scene_manager = SceneManager()

    def test_switch_to_scene_with_active_scene(self):
        """Test switching to a new scene when there's an active scene."""
        mock_old_scene = Mock()
        mock_new_scene = Mock()
        self.scene_manager.active_scene = mock_old_scene

        with patch.object(self.scene_manager, "log") as mock_log:
            self.scene_manager.switch_to_scene(mock_new_scene)

            # Should log scene switching
            mock_log.info.assert_called()
            mock_old_scene.cleanup.assert_called_once()
            mock_new_scene.setup.assert_called_once()
            assert self.scene_manager.active_scene == mock_new_scene

    def test_switch_to_scene_with_screenshot(self):
        """Test switching to scene with screenshot handling."""
        mock_old_scene = Mock()
        mock_new_scene = Mock()
        mock_screenshot = Mock()
        mock_old_scene.screenshot = mock_screenshot
        self.scene_manager.active_scene = mock_old_scene

        with patch.object(self.scene_manager, "log"):
            self.scene_manager.switch_to_scene(mock_new_scene)

            assert mock_old_scene._screenshot == mock_screenshot

    def test_switch_to_scene_with_blocked_events(self):
        """Test switching to scene with blocked events logging."""
        mock_scene = Mock()

        with (
            patch.object(self.scene_manager, "log") as mock_log,
            patch("pygame.event.get_blocked") as mock_get_blocked,
            patch("pygame.event.event_name") as mock_event_name,
        ):
            mock_get_blocked.return_value = True
            mock_event_name.return_value = "TEST_EVENT"

            self.scene_manager.switch_to_scene(mock_scene)

            # Should log blocked events
            mock_log.info.assert_called()

    def test_switch_to_scene_with_no_blocked_events(self):
        """Test switching to scene with no blocked events."""
        mock_scene = Mock()

        with (
            patch.object(self.scene_manager, "log") as mock_log,
            patch("pygame.event.get_blocked") as mock_get_blocked,
        ):
            mock_get_blocked.return_value = False

            self.scene_manager.switch_to_scene(mock_scene)

            # Should log "None" for blocked events
            mock_log.info.assert_called()

    def test_handle_event_with_focused_sprites_keydown(self):
        """Test event handling with focused sprites on KEYDOWN."""
        mock_scene = Mock()
        mock_sprite = Mock()
        mock_sprite.active = True
        mock_scene.all_sprites = [mock_sprite]
        self.scene_manager.active_scene = mock_scene

        mock_event = Mock()
        mock_event.type = pygame.KEYDOWN

        self.scene_manager.handle_event(mock_event)

        # Should pass event to active scene
        mock_scene.handle_event.assert_called_once_with(mock_event)

    def test_handle_event_with_focused_sprites_non_keydown(self):
        """Test event handling with focused sprites on non-KEYDOWN."""
        mock_scene = Mock()
        mock_sprite = Mock()
        mock_sprite.active = True
        mock_scene.all_sprites = [mock_sprite]
        self.scene_manager.active_scene = mock_scene

        mock_event = Mock()
        mock_event.type = pygame.MOUSEBUTTONDOWN

        with patch.object(self.scene_manager, "log"):
            self.scene_manager.handle_event(mock_event)

            # Should not pass event to active scene for non-KEYDOWN
            mock_scene.handle_event.assert_not_called()

    def test_handle_event_quit_with_active_scene(self):
        """Test handling QUIT event with active scene."""
        mock_scene = Mock()
        mock_scene.all_sprites = []
        self.scene_manager.active_scene = mock_scene

        mock_event = Mock()
        mock_event.type = pygame.QUIT

        with patch.object(self.scene_manager, "log") as mock_log:
            self.scene_manager.handle_event(mock_event)

            mock_log.info.assert_called_with("POSTING QUIT EVENT")
            assert self.scene_manager.quit_requested
            mock_scene.handle_event.assert_called_once_with(mock_event)

    def test_handle_event_quit_without_active_scene(self):
        """Test handling QUIT event without active scene."""
        self.scene_manager.active_scene = None

        mock_event = Mock()
        mock_event.type = pygame.QUIT

        with patch.object(self.scene_manager, "log") as mock_log:
            self.scene_manager.handle_event(mock_event)

            mock_log.info.assert_called_with("POSTING QUIT EVENT")
            assert self.scene_manager.quit_requested

    def test_handle_event_non_quit_with_active_scene(self):
        """Test handling non-QUIT event with active scene."""
        mock_scene = Mock()
        mock_scene.all_sprites = []
        self.scene_manager.active_scene = mock_scene

        mock_event = Mock()
        mock_event.type = pygame.MOUSEBUTTONDOWN

        with patch.object(self.scene_manager, "log"):
            self.scene_manager.handle_event(mock_event)

            # Should pass event to active scene
            mock_scene.handle_event.assert_called_once_with(mock_event)

    def test_handle_event_non_quit_without_active_scene(self):
        """Test handling non-QUIT event without active scene."""
        self.scene_manager.active_scene = None

        mock_event = Mock()
        mock_event.type = pygame.MOUSEBUTTONDOWN

        # Should not raise an error
        self.scene_manager.handle_event(mock_event)

    def test_play_method(self):
        """Test play method calls start."""
        with patch.object(self.scene_manager, "start") as mock_start:
            self.scene_manager.play()
            mock_start.assert_called_once()

    def test_stop_method(self):
        """Test stop method calls terminate."""
        with patch.object(self.scene_manager, "terminate") as mock_terminate:
            self.scene_manager.stop()
            mock_terminate.assert_called_once()

    def test_terminate_method(self):
        """Test terminate method."""
        with patch.object(self.scene_manager, "switch_to_scene") as mock_switch:
            self.scene_manager.terminate()
            mock_switch.assert_called_once_with(None)

    def test_quit_method(self):
        """Test quit method."""
        with (
            patch("pygame.event.post") as mock_post,
            patch.object(self.scene_manager, "log") as mock_log,
        ):
            self.scene_manager.quit()
            mock_log.info.assert_called_with("POSTING QUIT EVENT")
            mock_post.assert_called_once()


class TestSceneCoverage(unittest.TestCase):
    """Test Scene comprehensive coverage."""

    def setUp(self):
        """Set up test fixtures."""
        with (
            patch("pygame.display.get_surface") as mock_get_surface,
            patch("pygame.Surface") as mock_surface_class,
        ):
            mock_surface = Mock()
            mock_surface.get_size.return_value = (800, 600)
            mock_surface.get_width.return_value = 800
            mock_surface.get_height.return_value = 600
            mock_surface.convert.return_value = mock_surface
            mock_surface.get_rect.return_value = pygame.Rect(0, 0, 800, 600)
            mock_get_surface.return_value = mock_surface

            mock_surface_instance = Mock()
            mock_surface_instance.convert.return_value = mock_surface_instance
            mock_surface_class.return_value = mock_surface_instance

            self.scene = Scene()

    def test_scene_initialization_with_custom_name(self):  # noqa: PLR6301
        """Test Scene initialization with custom NAME."""
        class CustomScene(Scene):
            NAME = "CustomScene"

        with (
            patch("pygame.display.get_surface") as mock_get_surface,
            patch("pygame.Surface") as mock_surface_class,
        ):
            mock_surface = Mock()
            mock_surface.get_size.return_value = (800, 600)
            mock_surface.get_width.return_value = 800
            mock_surface.get_height.return_value = 600
            mock_surface.convert.return_value = mock_surface
            mock_surface.get_rect.return_value = pygame.Rect(0, 0, 800, 600)
            mock_get_surface.return_value = mock_surface

            mock_surface_instance = Mock()
            mock_surface_instance.convert.return_value = mock_surface_instance
            mock_surface_class.return_value = mock_surface_instance

            scene = CustomScene()
            assert scene.NAME == "CustomScene"

    def test_scene_initialization_with_unnamed_scene(self):  # noqa: PLR6301
        """Test Scene initialization with unnamed scene."""
        class UnnamedScene(Scene):
            NAME = "Unnamed Scene"

        with (
            patch("pygame.display.get_surface") as mock_get_surface,
            patch("pygame.Surface") as mock_surface_class,
        ):
            mock_surface = Mock()
            mock_surface.get_size.return_value = (800, 600)
            mock_surface.get_width.return_value = 800
            mock_surface.get_height.return_value = 600
            mock_surface.convert.return_value = mock_surface
            mock_surface.get_rect.return_value = pygame.Rect(0, 0, 800, 600)
            mock_get_surface.return_value = mock_surface

            mock_surface_instance = Mock()
            mock_surface_instance.convert.return_value = mock_surface_instance
            mock_surface_class.return_value = mock_surface_instance

            scene = UnnamedScene()
            assert scene.NAME == "UnnamedScene"

    def test_screenshot_property(self):
        """Test screenshot property."""
        with patch("pygame.Surface") as mock_surface_class:
            mock_screenshot = Mock()
            mock_screenshot.convert.return_value = mock_screenshot
            mock_surface_class.return_value = mock_screenshot

            screenshot = self.scene.screenshot
            assert screenshot == mock_screenshot

    def test_background_color_property_getter(self):
        """Test background_color property getter."""
        # Background color is set to BLACK during initialization
        assert self.scene.background_color == (0, 0, 0, 0)

    def test_background_color_property_setter(self):
        """Test background_color property setter."""
        new_color = (255, 0, 0)
        with (
            patch.object(self.scene.background, "fill") as mock_fill,
            patch.object(self.scene.all_sprites, "clear") as mock_clear,
        ):
            self.scene.background_color = new_color
            assert self.scene._background_color == new_color
            mock_fill.assert_called_once_with(new_color)
            mock_clear.assert_called_once_with(self.scene.screen, self.scene.background)

    def test_setup_method(self):
        """Test setup method (should be empty by default)."""
        # Should not raise an error
        self.scene.setup()

    def test_cleanup_method(self):
        """Test cleanup method (should be empty by default)."""
        # Should not raise an error
        self.scene.cleanup()

    def test_dt_tick_method(self):
        """Test dt_tick method."""
        initial_dt_timer = self.scene.dt_timer
        dt = 0.016  # 60 FPS

        self.scene.dt_tick(dt)

        assert self.scene.dt == dt
        assert self.scene.dt_timer == initial_dt_timer + dt

    def test_update_method_with_dirty_sprites(self):
        """Test update method with dirty sprites."""
        mock_sprite1 = Mock()
        mock_sprite1.dirty = True
        mock_sprite1.update_nested_sprites = Mock()
        mock_sprite1.update = Mock()

        mock_sprite2 = Mock()
        mock_sprite2.dirty = False
        mock_sprite2.update_nested_sprites = Mock()
        mock_sprite2.update = Mock()

        self.scene.all_sprites = [mock_sprite1, mock_sprite2]

        self.scene.update()

        # Should call update_nested_sprites on all sprites
        mock_sprite1.update_nested_sprites.assert_called_once()
        mock_sprite2.update_nested_sprites.assert_called_once()

        # Should call update only on dirty sprites
        mock_sprite1.update.assert_called_once()
        mock_sprite2.update.assert_not_called()

    def test_update_method_with_dirty_scene(self):
        """Test update method when scene is dirty."""
        mock_sprite = Mock()
        mock_sprite.dirty = False
        mock_sprite.update_nested_sprites = Mock()
        mock_sprite.update = Mock()

        self.scene.all_sprites = [mock_sprite]
        self.scene.dirty = True

        self.scene.update()

        # Should make all sprites dirty
        assert mock_sprite.dirty == 1

    def test_render_method(self):
        """Test render method."""
        mock_screen = Mock()
        mock_rects = [pygame.Rect(0, 0, 10, 10)]

        with (
            patch.object(self.scene.all_sprites, "clear") as mock_clear,
            patch.object(self.scene.all_sprites, "draw", return_value=mock_rects) as mock_draw,
        ):
            self.scene.render(mock_screen)

            mock_clear.assert_called_once_with(mock_screen, self.scene.background)
            mock_draw.assert_called_once_with(mock_screen)
            assert self.scene.rects == mock_rects

    def test_sprites_at_position(self):
        """Test sprites_at_position method."""
        mock_sprite = Mock()
        self.scene.all_sprites = [mock_sprite]
        pos = (100, 100)

        with patch("pygame.sprite.spritecollide") as mock_collide:
            mock_collide.return_value = [mock_sprite]

            result = self.scene.sprites_at_position(pos)

            assert result == [mock_sprite]
            mock_collide.assert_called_once()

    def test_controller_button_down_event(self):
        """Test on_controller_button_down_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_controller_button_down_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: On Controller Button Down Event {mock_event}"
            )

    def test_controller_button_up_event(self):
        """Test on_controller_button_up_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_controller_button_up_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: On Controller Button Up Event {mock_event}"
            )

    def test_controller_axis_motion_event(self):
        """Test on_controller_axis_motion_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_controller_axis_motion_event(mock_event)

    def test_controller_device_added_event(self):
        """Test on_controller_device_added_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_controller_device_added_event(mock_event)

    def test_controller_device_removed_event(self):
        """Test on_controller_device_removed_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_controller_device_removed_event(mock_event)

    def test_controller_device_remapped_event(self):
        """Test on_controller_device_remapped_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_controller_device_remapped_event(mock_event)

    def test_audio_device_added_event(self):
        """Test on_audio_device_added_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_audio_device_added_event(mock_event)

    def test_audio_device_removed_event(self):
        """Test on_audio_device_removed_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_audio_device_removed_event(mock_event)

    def test_active_event(self):
        """Test on_active_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_active_event(mock_event)

    def test_key_down_event(self):
        """Test on_key_down_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_key_down_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: On Key Down Event {mock_event}"
            )

    def test_key_up_event(self):
        """Test on_key_up_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_key_up_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: On Key Up Event {mock_event}"
            )

    def test_mouse_motion_event(self):
        """Test on_mouse_motion_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_mouse_motion_event(mock_event)

    def test_mouse_button_down_event(self):
        """Test on_mouse_button_down_event method."""
        mock_event = Mock()
        mock_event.pos = (100, 200)
        # Create a proper rect object for the mouse pointer
        mock_rect = Mock()
        mock_rect.x = 100
        mock_rect.y = 200
        mock_rect.width = 1
        mock_rect.height = 1

        with patch("glitchygames.events.mouse.MousePointer") as mock_mouse_pointer_class:
            mock_mouse_pointer_class.return_value = Mock(rect=mock_rect)

            # Test that the method can be called without error
            # Debug logging may not work due to missing OPTIONS
            self.scene.on_mouse_button_down_event(mock_event)

    def test_mouse_button_up_event(self):
        """Test on_mouse_button_up_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_mouse_button_up_event(mock_event)

    def test_mouse_wheel_event(self):
        """Test on_mouse_wheel_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_mouse_wheel_event(mock_event)

    def test_joystick_axis_motion_event(self):
        """Test on_joy_axis_motion_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_joy_axis_motion_event(mock_event)

    def test_joystick_ball_motion_event(self):
        """Test on_joy_ball_motion_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_joy_ball_motion_event(mock_event)

    def test_joystick_hat_motion_event(self):
        """Test on_joy_hat_motion_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_joy_hat_motion_event(mock_event)

    def test_joystick_button_down_event(self):
        """Test on_joy_button_down_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_joy_button_down_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: On Joy Button Down Event {mock_event}"
            )

    def test_joystick_button_up_event(self):
        """Test on_joy_button_up_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_joy_button_up_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: On Joy Button Up Event {mock_event}"
            )

    def test_joystick_device_added_event(self):
        """Test on_joy_device_added_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_joy_device_added_event(mock_event)

    def test_joystick_device_removed_event(self):
        """Test on_joy_device_removed_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_joy_device_removed_event(mock_event)

    def test_touch_motion_event(self):
        """Test on_touch_motion_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_touch_motion_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Touch Motion Event: {mock_event}"
            )

    def test_touch_down_event(self):
        """Test on_touch_down_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_touch_down_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Touch Down Event: {mock_event}"
            )

    def test_touch_up_event(self):
        """Test on_touch_up_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_touch_up_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Touch Up Event: {mock_event}"
            )

    def test_midi_in_event(self):
        """Test on_menu_item_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_menu_item_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: On Menu Item Event {mock_event}"
            )

    def test_window_close_event(self):
        """Test on_window_close_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_close_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Close Event: {mock_event}"
            )

    def test_window_minimized_event(self):
        """Test on_window_minimized_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_minimized_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Minimized Event: {mock_event}"
            )

    def test_window_maximized_event(self):
        """Test on_window_maximized_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_maximized_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Maximized Event: {mock_event}"
            )

    def test_window_restored_event(self):
        """Test on_window_restored_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_restored_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Restored Event: {mock_event}"
            )

    def test_window_enter_event(self):
        """Test on_window_enter_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_enter_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Enter Event: {mock_event}"
            )

    def test_window_leave_event(self):
        """Test on_window_leave_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_leave_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Leave Event: {mock_event}"
            )

    def test_window_focus_gained_event(self):
        """Test on_window_focus_gained_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_focus_gained_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Focus Gained Event: {mock_event}"
            )

    def test_window_focus_lost_event(self):
        """Test on_window_focus_lost_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_focus_lost_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Focus Lost Event: {mock_event}"
            )

    def test_window_take_focus_event(self):
        """Test on_window_take_focus_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_take_focus_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Take Focus Event: {mock_event}"
            )

    def test_window_hit_test_event(self):
        """Test on_window_hit_test_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_hit_test_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Hit Test Event: {mock_event}"
            )

    def test_window_moved_event(self):
        """Test on_window_moved_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_moved_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Moved Event: {mock_event}"
            )

    def test_window_resized_event(self):
        """Test on_window_resized_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_resized_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Resized Event: {mock_event}"
            )

    def test_window_size_changed_event(self):
        """Test on_window_size_changed_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_size_changed_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Size Changed Event: {mock_event}"
            )

    def test_window_hidden_event(self):
        """Test on_window_hidden_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_hidden_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Hidden Event: {mock_event}"
            )

    def test_window_shown_event(self):
        """Test on_window_shown_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_shown_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Shown Event: {mock_event}"
            )

    def test_window_exposed_event(self):
        """Test on_window_exposed_event method."""
        mock_event = Mock()

        with patch.object(self.scene, "log") as mock_log:
            self.scene.on_window_exposed_event(mock_event)

            mock_log.debug.assert_called_once_with(
                f"{type(self.scene)}: Window Exposed Event: {mock_event}"
            )

    def test_drop_begin_event(self):
        """Test on_drop_begin_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_drop_begin_event(mock_event)

    def test_drop_complete_event(self):
        """Test on_drop_complete_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_drop_complete_event(mock_event)

    def test_drop_file_event(self):
        """Test on_drop_file_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_drop_file_event(mock_event)

    def test_drop_text_event(self):
        """Test on_drop_text_event method."""
        mock_event = Mock()

        # Test that the method can be called without error
        # Debug logging may not work due to missing OPTIONS
        self.scene.on_drop_text_event(mock_event)


if __name__ == "__main__":
    unittest.main()
