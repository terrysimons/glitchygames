"""Simple test coverage for the scenes module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene, SceneManager

# Constants for test values
FPS_REFRESH_RATE = 1000
TARGET_FPS = 0
DT_VALUE = 0
TIMER_VALUE = 0


class TestSceneManagerSimple(unittest.TestCase):
    """Test SceneManager basic functionality."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("pygame.display.get_surface") as mock_get_surface:
            mock_surface = Mock()
            mock_surface.get_size.return_value = (800, 600)
            mock_surface.get_width.return_value = 800
            mock_surface.get_height.return_value = 600
            mock_get_surface.return_value = mock_surface

            self.scene_manager = SceneManager()

    def test_scene_manager_initialization(self):
        """Test SceneManager initialization."""
        assert self.scene_manager is not None
        assert self.scene_manager.update_type == "update"
        assert self.scene_manager.fps_refresh_rate == FPS_REFRESH_RATE
        assert self.scene_manager.target_fps == 0
        assert self.scene_manager.dt == 0
        assert self.scene_manager.timer == 0
        assert self.scene_manager._game_engine is None
        assert self.scene_manager.active_scene is None
        assert self.scene_manager.next_scene is None
        assert self.scene_manager.previous_scene is None
        assert not self.scene_manager.quit_requested
        assert isinstance(self.scene_manager.clock, pygame.time.Clock)

    def test_game_engine_property(self):
        """Test game_engine property getter and setter."""
        mock_engine = Mock()
        mock_engine.OPTIONS = {
            "update_type": "flip",
            "fps_refresh_rate": 1000,
            "target_fps": 60
        }
        self.scene_manager.game_engine = mock_engine
        assert self.scene_manager.game_engine == mock_engine

    def test_all_sprites_property_with_active_scene(self):
        """Test all_sprites property when there's an active scene."""
        mock_scene = Mock()
        mock_scene.all_sprites = Mock()
        self.scene_manager.active_scene = mock_scene

        result = self.scene_manager.all_sprites
        assert result == mock_scene.all_sprites

    def test_all_sprites_property_without_active_scene(self):
        """Test all_sprites property when there's no active scene."""
        self.scene_manager.active_scene = None
        result = self.scene_manager.all_sprites
        assert result is None

    def test_switch_to_scene_same_scene(self):
        """Test switching to the same scene (no change)."""
        mock_scene = Mock()
        self.scene_manager.active_scene = mock_scene

        with patch.object(self.scene_manager, "log") as mock_log:
            self.scene_manager.switch_to_scene(mock_scene)
            # Should not log scene switching since it's the same scene
            mock_log.info.assert_not_called()

    def test_switch_to_scene_none(self):
        """Test switching to None scene."""
        mock_scene = Mock()
        self.scene_manager.active_scene = mock_scene

        with patch.object(self.scene_manager, "log"):
            self.scene_manager.switch_to_scene(None)

            # Should call cleanup on old scene
            mock_scene.cleanup.assert_called_once()

            # Should set active scene to None
            assert self.scene_manager.active_scene is None

    def test_handle_event_with_focused_sprites(self):
        """Test event handling with focused sprites."""
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

    def test_handle_event_quit_event(self):
        """Test handling QUIT event."""
        mock_scene = Mock()
        mock_scene.all_sprites = []  # Empty list to avoid iteration issues
        self.scene_manager.active_scene = mock_scene

        mock_event = Mock()
        mock_event.type = pygame.QUIT

        with patch.object(self.scene_manager, "log") as mock_log:
            self.scene_manager.handle_event(mock_event)

            # Should log quit event and set quit_requested
            mock_log.info.assert_called_with("POSTING QUIT EVENT")
            assert self.scene_manager.quit_requested

            # QUIT events don't get passed to active scene in the current implementation
            mock_scene.handle_event.assert_not_called()

    def test_handle_event_other_event(self):
        """Test handling other events."""
        mock_scene = Mock()
        mock_scene.all_sprites = []  # Empty list to avoid iteration issues
        self.scene_manager.active_scene = mock_scene

        mock_event = Mock()
        mock_event.type = pygame.KEYDOWN

        self.scene_manager.handle_event(mock_event)

        # Should pass event to active scene
        mock_scene.handle_event.assert_called_once_with(mock_event)

    def test_handle_event_no_active_scene(self):
        """Test handling events when no active scene."""
        self.scene_manager.active_scene = None

        mock_event = Mock()
        mock_event.type = pygame.KEYDOWN

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


class TestSceneSimple(unittest.TestCase):
    """Test Scene basic functionality."""

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

    def test_scene_initialization_default(self):
        """Test Scene initialization with default parameters."""
        assert self.scene.FPS == 0
        assert self.scene.NAME == "Scene"  # Should be class name
        assert self.scene.VERSION == "0.0"
        assert self.scene.target_fps == 0
        assert self.scene.fps == 0
        assert self.scene.dt == 0
        assert self.scene.dt_timer == 0
        assert self.scene.dirty == 1
        assert self.scene.options == {}
        assert isinstance(self.scene.scene_manager, SceneManager)
        assert self.scene.name is type(self.scene)
        # Background color is set to BLACK during initialization
        assert self.scene._background_color == (0, 0, 0, 0)
        assert self.scene.next_scene == self.scene
        assert self.scene.rects is None

    def test_scene_initialization_with_options(self):  # noqa: PLR6301
        """Test Scene initialization with options."""
        options = {"test": "value"}
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

            scene = Scene(options=options)
            assert scene.options == options

    def test_scene_initialization_with_groups(self):  # noqa: PLR6301
        """Test Scene initialization with sprite groups."""
        mock_groups = Mock()
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

            scene = Scene(groups=mock_groups)
            assert scene.all_sprites == mock_groups

    def test_screenshot_property(self):
        """Test screenshot property."""
        with patch("pygame.Surface") as mock_surface_class:
            mock_screenshot = Mock()
            mock_screenshot.convert.return_value = mock_screenshot
            mock_surface_class.return_value = mock_screenshot

            screenshot = self.scene.screenshot
            assert screenshot == mock_screenshot

    def test_background_color_property(self):
        """Test background_color property getter and setter."""
        # Test getter - background color is set to BLACK during initialization
        assert self.scene.background_color == (0, 0, 0, 0)

        # Test setter
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

    def test_update_method(self):
        """Test update method."""
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


if __name__ == "__main__":
    unittest.main()
