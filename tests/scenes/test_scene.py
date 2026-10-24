"""Tests for Scene class functionality."""

import contextlib
import gc
import sys
import weakref
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.backgrounds import (
    BackgroundPattern,
    background_pattern_surface,
    set_active_default_background_pattern,
)
from glitchygames.color import BLUE, RED
from glitchygames.events import ALL_EVENTS, FPSEVENT
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.interfaces import SceneInterface
from glitchygames.opacity import OPAQUE, has_per_pixel_alpha
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes.scene import JITTER_SAMPLE_BUFFER_MAX_SIZE
from glitchygames.sources import advance_frame_clock
from tests.display_canvas import CANVAS_PATTERN
from tests.logged_messages import logged_message

if TYPE_CHECKING:
    from collections.abc import Generator

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _install_frame_input(*, mouse_position: tuple[int, int], mouse_focused: bool) -> None:
    """Make a snapshot with this mouse this frame's polled input (``current_input()``).

    The autouse ``reset_engine_sources`` fixture (tests/conftest.py) resets it after the test.
    """
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=0,
            mouse_position=mouse_position,
            mouse_buttons=(False, False, False),
            mouse_focused=mouse_focused,
        )
    )


@contextlib.contextmanager
def _only_these_event_types_blocked(blocked_types: set[int]) -> Generator[None]:
    """Block exactly ``blocked_types`` at SDL's real queue, then restore each type's state.

    Yields:
        None: While only those types are blocked.

    """
    previously_blocked = {
        event_type: pygame.event.get_blocked(event_type) for event_type in ALL_EVENTS
    }
    pygame.event.set_allowed(None)
    for event_type in blocked_types:
        pygame.event.set_blocked(event_type)
    try:
        yield
    finally:
        for event_type, was_blocked in previously_blocked.items():
            if was_blocked:
                pygame.event.set_blocked(event_type)
            else:
                pygame.event.set_allowed(event_type)


class RecordingSprite(pygame.sprite.DirtySprite):
    """A real 8x8 sprite for a real sprite group that notes what the scene asks of it."""

    def __init__(self, *, dirty: int = 0, is_active: bool = False, name: str = 'test') -> None:
        """Make the sprite: red, at the origin, with no calls noted yet.

        Args:
            dirty: Its dirty flag (a group marks a sprite dirty when it is added).
            is_active: Whether it has keyboard focus.
            name: Its name.

        """
        super().__init__()
        self.image = pygame.Surface((8, 8))
        self.image.fill(RED)
        self.rect = self.image.get_rect()
        self.dirty = dirty
        self.is_active = is_active
        self.name = name
        self.key_down_events: list[object] = []
        self.update_count = 0
        self.nested_update_count = 0
        self.focus_lost_count = 0

    def update_nested_sprites(self) -> None:
        """Note that the scene asked for its nested sprites to be updated."""
        self.nested_update_count += 1

    def update(self, *args: object, **kwargs: object) -> None:
        """Note that the scene updated it."""
        self.update_count += 1

    def on_key_down_event(self, event: object) -> None:
        """Note a key-down the scene gave it."""
        self.key_down_events.append(event)

    def on_focus_lost(self) -> None:
        """Note that the scene took its focus away."""
        self.focus_lost_count += 1


class TestScene:
    """Test Scene class functionality."""

    def test_scene_initialization_default(self, mocker):
        """Test Scene initialization with default parameters."""
        scene = Scene()

        # Check basic attributes
        assert scene.target_fps == 0
        assert scene.fps == 0
        assert scene.dt == 0
        assert scene.dt_timer == 0
        assert scene.dirty == 1
        assert scene.options == {'debug_events': False, 'no_unhandled_events': False}
        assert scene.name is type(scene)
        # No colour set: the background shows the default pattern (glitchygames/backgrounds.py)
        assert scene.background_color is None
        assert scene.background_pattern is CANVAS_PATTERN
        # No switch pending
        assert scene.next_scene is None
        assert scene.rects is None
        assert scene.screen is not None
        assert scene.screen_width > 0
        assert scene.screen_height > 0
        assert scene.all_sprites is not None
        assert scene.background is not None
        assert scene.image is not None
        assert scene.rect is not None

    def test_scene_initialization_with_options(self, mocker):
        """Test Scene initialization with options."""
        options = {'test': 'value'}
        scene = Scene(options=options)

        assert scene.options == options

    def test_scene_initialization_with_groups(self, mocker):
        """Test Scene initialization with sprite groups."""
        mock_groups = mocker.Mock()
        scene = Scene(groups=mock_groups)

        assert scene.all_sprites == mock_groups

    def test_scene_screenshot_property(self):
        """The screenshot is a copy of what is on the display, not the display itself."""
        scene = Scene()
        assert scene.screen is not None
        scene.screen.fill(BLUE)

        screenshot = scene.screenshot
        scene.screen.fill(RED)  # a later frame must not change the screenshot

        assert screenshot is not scene.screen
        assert screenshot.get_size() == scene.screen.get_size()
        # RGB: the display's pixel format may or may not carry alpha
        screenshot_pixels = pygame.surfarray.pixels3d(screenshot)
        assert (screenshot_pixels == BLUE[:3]).all()
        del screenshot_pixels  # release the screenshot's pixel lock

    def test_scene_background_color_property(self, mocker):
        """Test Scene background_color property."""
        scene = Scene()

        # No colour until one is set: the background shows the default pattern
        assert scene.background_color is None

        # An RGB colour is normalized to opaque RGBA
        scene.background_color = RED
        assert scene.background_color == (*RED, OPAQUE)
        # A colour replaces the pattern
        assert scene.background_pattern is None
        # The background surface is filled with it, opaque (alpha 0 showed black on cocoa,
        # BUGS.md #142)
        background_pixels = pygame.surfarray.pixels3d(scene.background)
        assert (background_pixels == RED[:3]).all()
        del background_pixels  # release the background's pixel lock
        assert scene.background.get_at((0, 0)) == (*RED, OPAQUE)

    def test_scene_background_color_setter(self, mocker):
        """Test Scene background_color setter."""
        scene = Scene()

        # An RGB colour is normalized to opaque RGBA
        scene.background_color = BLUE
        assert scene.background_color == (*BLUE, OPAQUE)

    def test_scene_setup_method(self, mocker):
        """Test Scene setup method."""
        scene = Scene()

        # Test setup method (should not raise exceptions)
        scene.setup()

    def test_scene_update_method(self, mocker):
        """Test Scene update method."""
        scene = Scene()

        # Test update method (should not raise exceptions)
        scene.update()

    def test_scene_render_method(self):
        """render() clears the given surface to the scene's background."""
        scene = Scene()
        scene.background_color = BLUE
        target = pygame.Surface(scene.background.get_size())
        target.fill(RED)

        scene.render(target)

        # An empty group's first draw puts the whole background down (RGB compare)
        target_pixels = pygame.surfarray.pixels3d(target)
        assert (target_pixels == BLUE[:3]).all()
        del target_pixels  # release the target's pixel lock
        assert scene.rects is not None

    def test_scene_cleanup_method(self, mocker):
        """Test Scene cleanup method."""
        scene = Scene()

        # Test cleanup method (should not raise exceptions)
        scene.cleanup()

    def test_scene_on_user_event(self, mocker):
        """Test Scene on_user_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test user event handling
        scene.on_user_event(mock_event)

    def test_scene_on_quit_event(self, mocker):
        """Test Scene on_quit_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test quit event handling
        scene.on_quit_event(mock_event)

    def test_scene_on_fps_event(self, mocker):
        """Test Scene on_fps_event method."""
        scene = Scene()
        mock_event = mocker.Mock()
        mock_event.fps = 60

        # Test FPS event handling
        scene.on_fps_event(mock_event)

    def test_scene_on_game_event(self, mocker):
        """Test Scene on_game_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test game event handling
        scene.on_game_event(mock_event)

    def test_scene_on_key_down_event(self, mocker):
        """Test Scene on_key_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test key down event handling
        scene.on_key_down_event(mock_event)

    def test_scene_on_key_up_event(self, mocker):
        """Test Scene on_key_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test key up event handling
        scene.on_key_up_event(mock_event)

    def test_scene_on_mouse_button_down_event(self, mocker):
        """Test Scene on_mouse_button_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()
        mock_event.pos = (100, 100)  # Provide proper position

        # Test mouse button down event handling
        scene.on_mouse_button_down_event(mock_event)

    def test_scene_on_mouse_button_up_event(self, mocker):
        """Test Scene on_mouse_button_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test mouse button up event handling
        scene.on_mouse_button_up_event(mock_event)

    def test_scene_on_mouse_motion_event(self, mocker):
        """Test Scene on_mouse_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test mouse motion event handling
        scene.on_mouse_motion_event(mock_event)

    def test_scene_on_mouse_wheel_event(self, mocker):
        """Test Scene on_mouse_wheel_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test mouse wheel event handling
        scene.on_mouse_wheel_event(mock_event)


class TestSceneLifetime:
    """When a scene's memory is given back."""

    def test_a_scene_no_longer_referenced_is_freed_at_once(self):
        """A scene is not in a reference cycle with itself, so the last reference frees it.

        A scene in a cycle waits for the cycle collector, which counts objects, not bytes, so
        a few finished scenes holding megabytes of surfaces piled up (the Linux CI test job ran
        out of memory).
        """
        scene = Scene()
        scene_reference = weakref.ref(scene)
        gc.disable()
        try:
            del scene
            assert scene_reference() is None
        finally:
            gc.enable()


class TestSceneJoystickControllerEvents:
    """Test Scene joystick and controller event methods."""

    def test_scene_on_joy_axis_motion_event(self, mocker):
        """Test Scene on_joy_axis_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick axis motion event handling
        scene.on_joy_axis_motion_event(mock_event)

    def test_scene_on_joy_button_down_event(self, mocker):
        """Test Scene on_joy_button_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick button down event handling
        scene.on_joy_button_down_event(mock_event)

    def test_scene_on_joy_button_up_event(self, mocker):
        """Test Scene on_joy_button_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick button up event handling
        scene.on_joy_button_up_event(mock_event)

    def test_scene_on_joy_hat_motion_event(self, mocker):
        """Test Scene on_joy_hat_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick hat motion event handling
        scene.on_joy_hat_motion_event(mock_event)

    def test_scene_on_joy_ball_motion_event(self, mocker):
        """Test Scene on_joy_ball_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick ball motion event handling
        scene.on_joy_ball_motion_event(mock_event)

    def test_scene_on_joy_device_added_event(self, mocker):
        """Test Scene on_joy_device_added_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick device added event handling
        scene.on_joy_device_added_event(mock_event)

    def test_scene_on_joy_device_removed_event(self, mocker):
        """Test Scene on_joy_device_removed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick device removed event handling
        scene.on_joy_device_removed_event(mock_event)

    def test_scene_on_controller_axis_motion_event(self, mocker):
        """Test Scene on_controller_axis_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller axis motion event handling
        scene.on_controller_axis_motion_event(mock_event)

    def test_scene_on_controller_button_down_event(self, mocker):
        """Test Scene on_controller_button_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller button down event handling
        scene.on_controller_button_down_event(mock_event)

    def test_scene_on_controller_button_up_event(self, mocker):
        """Test Scene on_controller_button_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller button up event handling
        scene.on_controller_button_up_event(mock_event)

    def test_scene_on_controller_device_added_event(self, mocker):
        """Test Scene on_controller_device_added_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller device added event handling
        scene.on_controller_device_added_event(mock_event)

    def test_scene_on_controller_device_removed_event(self, mocker):
        """Test Scene on_controller_device_removed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller device removed event handling
        scene.on_controller_device_removed_event(mock_event)

    def test_scene_on_controller_device_remapped_event(self, mocker):
        """Test Scene on_controller_device_remapped_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller device remapped event handling
        scene.on_controller_device_remapped_event(mock_event)

    def test_scene_on_controller_touchpad_down_event(self, mocker):
        """Test Scene on_controller_touchpad_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller touchpad down event handling
        scene.on_controller_touchpad_down_event(mock_event)

    def test_scene_on_controller_touchpad_motion_event(self, mocker):
        """Test Scene on_controller_touchpad_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller touchpad motion event handling
        scene.on_controller_touchpad_motion_event(mock_event)

    def test_scene_on_controller_touchpad_up_event(self, mocker):
        """Test Scene on_controller_touchpad_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller touchpad up event handling
        scene.on_controller_touchpad_up_event(mock_event)


class TestSceneWindowEvents:
    """Test Scene window and audio device event methods."""

    def test_scene_on_audio_device_added_event(self, mocker):
        """Test Scene on_audio_device_added_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test audio device added event handling
        scene.on_audio_device_added_event(mock_event)

    def test_scene_on_audio_device_removed_event(self, mocker):
        """Test Scene on_audio_device_removed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test audio device removed event handling
        scene.on_audio_device_removed_event(mock_event)

    def test_scene_on_window_close_event(self, mocker):
        """Test Scene on_window_close_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window close event handling
        scene.on_window_close_event(mock_event)

    def test_scene_on_window_enter_event(self, mocker):
        """Test Scene on_window_enter_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window enter event handling
        scene.on_window_enter_event(mock_event)

    def test_scene_on_window_leave_event(self, mocker):
        """Test Scene on_window_leave_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window leave event handling
        scene.on_window_leave_event(mock_event)

    def test_scene_on_window_focus_gained_event(self, mocker):
        """Test Scene on_window_focus_gained_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window focus gained event handling
        scene.on_window_focus_gained_event(mock_event)

    def test_scene_on_window_focus_lost_event(self, mocker):
        """Test Scene on_window_focus_lost_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window focus lost event handling
        scene.on_window_focus_lost_event(mock_event)

    def test_scene_on_window_resized_event(self, mocker):
        """Test Scene on_window_resized_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window resized event handling
        scene.on_window_resized_event(mock_event)

    def test_scene_on_window_moved_event(self, mocker):
        """Test Scene on_window_moved_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window moved event handling
        scene.on_window_moved_event(mock_event)

    def test_scene_on_window_minimized_event(self, mocker):
        """Test Scene on_window_minimized_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window minimized event handling
        scene.on_window_minimized_event(mock_event)

    def test_scene_on_window_maximized_event(self, mocker):
        """Test Scene on_window_maximized_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window maximized event handling
        scene.on_window_maximized_event(mock_event)

    def test_scene_on_window_restored_event(self, mocker):
        """Test Scene on_window_restored_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window restored event handling
        scene.on_window_restored_event(mock_event)

    def test_scene_on_window_shown_event(self, mocker):
        """Test Scene on_window_shown_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window shown event handling
        scene.on_window_shown_event(mock_event)

    def test_scene_on_window_hidden_event(self, mocker):
        """Test Scene on_window_hidden_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window hidden event handling
        scene.on_window_hidden_event(mock_event)

    def test_scene_on_window_exposed_event(self, mocker):
        """Test Scene on_window_exposed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window exposed event handling
        scene.on_window_exposed_event(mock_event)

    def test_scene_on_window_take_focus_event(self, mocker):
        """Test Scene on_window_take_focus_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window take focus event handling
        scene.on_window_take_focus_event(mock_event)

    def test_scene_on_window_size_changed_event(self, mocker):
        """Test Scene on_window_size_changed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window size changed event handling
        scene.on_window_size_changed_event(mock_event)

    def test_scene_on_window_hit_test_event(self, mocker):
        """Test Scene on_window_hit_test_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window hit test event handling
        scene.on_window_hit_test_event(mock_event)


class TestSceneInputEvents:
    """Test Scene touch, drop, text, MIDI, and font event methods."""

    def test_scene_on_touch_down_event(self, mocker):
        """Test Scene on_touch_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test touch down event handling
        scene.on_touch_down_event(mock_event)

    def test_scene_on_touch_motion_event(self, mocker):
        """Test Scene on_touch_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test touch motion event handling
        scene.on_touch_motion_event(mock_event)

    def test_scene_on_touch_up_event(self, mocker):
        """Test Scene on_touch_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test touch up event handling
        scene.on_touch_up_event(mock_event)

    def test_scene_on_multi_touch_down_event(self, mocker):
        """Test Scene on_multi_touch_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test multi touch down event handling
        scene.on_multi_touch_down_event(mock_event)

    def test_scene_on_multi_touch_motion_event(self, mocker):
        """Test Scene on_multi_touch_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test multi touch motion event handling
        scene.on_multi_touch_motion_event(mock_event)

    def test_scene_on_multi_touch_up_event(self, mocker):
        """Test Scene on_multi_touch_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test multi touch up event handling
        scene.on_multi_touch_up_event(mock_event)

    def test_scene_on_drop_begin_event(self, mocker):
        """Test Scene on_drop_begin_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test drop begin event handling
        scene.on_drop_begin_event(mock_event)

    def test_scene_on_drop_file_event(self, mocker):
        """Test Scene on_drop_file_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test drop file event handling
        scene.on_drop_file_event(mock_event)

    def test_scene_on_drop_text_event(self, mocker):
        """Test Scene on_drop_text_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test drop text event handling
        scene.on_drop_text_event(mock_event)

    def test_scene_on_drop_complete_event(self, mocker):
        """Test Scene on_drop_complete_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test drop complete event handling
        scene.on_drop_complete_event(mock_event)

    def test_scene_on_text_input_event(self, mocker):
        """Test Scene on_text_input_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test text input event handling
        scene.on_text_input_event(mock_event)

    def test_scene_on_text_editing_event(self, mocker):
        """Test Scene on_text_editing_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test text editing event handling
        scene.on_text_editing_event(mock_event)

    def test_scene_on_midi_in_event(self, mocker):
        """Test Scene on_midi_in_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test MIDI in event handling
        scene.on_midi_in_event(mock_event)

    def test_scene_on_midi_out_event(self, mocker):
        """Test Scene on_midi_out_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test MIDI out event handling
        scene.on_midi_out_event(mock_event)

    def test_scene_on_font_changed_event(self, mocker):
        """Test Scene on_font_changed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test font changed event handling
        scene.on_font_changed_event(mock_event)


class TestSceneDtTick:
    """Test Scene.dt_tick() method."""

    def test_dt_tick_updates_dt_and_timer(self):
        """Test dt_tick accumulates delta time."""
        scene = Scene()
        assert scene.dt == 0
        assert scene.dt_timer == 0

        scene.dt_tick(0.016)
        assert abs(scene.dt - 0.016) < 1e-9
        assert abs(scene.dt_timer - 0.016) < 1e-9

        scene.dt_tick(0.017)
        assert abs(scene.dt - 0.017) < 1e-9
        assert abs(scene.dt_timer - 0.033) < 0.001


class TestSceneCleanup:
    """Test Scene.cleanup() method."""

    def test_cleanup_runs_without_error(self):
        """Test cleanup() can be called without error."""
        scene = Scene()
        scene.cleanup()  # Base implementation is a no-op


class TestSceneLoadResources:
    """Test Scene.load_resources() method."""

    def test_load_resources_runs_without_error(self):
        """Test load_resources() can be called without error."""
        scene = Scene()
        scene.load_resources()  # Base implementation logs a debug message


class TestSceneSpritesAtPosition:
    """Test Scene.sprites_at_position() method."""

    def test_sprites_at_position_returns_list(self):
        """Test sprites_at_position returns a list."""
        scene = Scene()
        result = scene.sprites_at_position((100, 100))
        assert isinstance(result, list)

    def test_sprites_at_position_empty(self):
        """Test sprites_at_position returns empty list when no sprites."""
        scene = Scene()
        result = scene.sprites_at_position((100, 100))
        assert result == []


class TestSceneFocusManagement:
    """Test Scene focus management helper methods."""

    def test_get_collided_sprites(self):
        """Test _get_collided_sprites delegates to sprites_at_position."""
        scene = Scene()
        result = scene._get_collided_sprites((100, 100))
        assert isinstance(result, list)

    def test_get_focusable_sprites_empty(self):
        """Test _get_focusable_sprites with no focusable sprites."""
        scene = Scene()
        result = scene._get_focusable_sprites([])
        assert result == []

    def test_get_focusable_sprites_filters(self, mocker):
        """Test _get_focusable_sprites filters correctly."""
        scene = Scene()

        focusable = mocker.Mock()
        focusable.focusable = True

        non_focusable = mocker.Mock(spec=[])  # No focusable attribute

        result = scene._get_focusable_sprites([focusable, non_focusable])
        assert len(result) == 1
        assert result[0] == focusable

    def test_get_focused_sprites_empty(self):
        """Test _get_focused_sprites with no focused sprites."""
        scene = Scene()
        result = scene._get_focused_sprites()
        assert result == []

    def test_has_focusable_sprites_false(self):
        """Test _has_focusable_sprites returns False for empty list."""
        scene = Scene()
        assert scene._has_focusable_sprites([]) is False

    def test_has_focusable_sprites_true(self, mocker):
        """Test _has_focusable_sprites returns True when focusable present."""
        scene = Scene()
        sprite = mocker.Mock()
        sprite.focusable = True
        assert scene._has_focusable_sprites([sprite]) is True

    def test_unfocus_sprites(self, mocker):
        """Test _unfocus_sprites deactivates sprites."""
        scene = Scene()

        sprite = mocker.Mock()
        sprite.is_active = True
        sprite.on_focus_lost = mocker.Mock()

        scene._unfocus_sprites([sprite])

        assert sprite.is_active is False
        sprite.on_focus_lost.assert_called_once()

    def test_unfocus_sprites_without_on_focus_lost(self, mocker):
        """Test _unfocus_sprites with sprite that lacks on_focus_lost."""
        scene = Scene()

        sprite = mocker.Mock(spec=['active'])
        sprite.is_active = True

        scene._unfocus_sprites([sprite])
        assert sprite.is_active is False

    def test_handle_focus_management_unfocuses_when_no_focusable(self, mocker):
        """Test _handle_focus_management unfocuses when no focusable sprites."""
        scene = Scene()

        # A focused sprite in the scene's real sprite group
        focused_sprite = RecordingSprite(is_active=True)
        scene.all_sprites.add(focused_sprite)

        # Click on non-focusable sprites
        scene._handle_focus_management([])

        assert focused_sprite.is_active is False
        assert focused_sprite.focus_lost_count == 1


class TestSceneHandleQuitKeyPress:
    """Test Scene._handle_quit_key_press() method."""

    def test_handle_quit_key_press_posts_quit_event(self, mocker):
        """Test quit key press posts a QUIT event."""
        scene = Scene()

        pygame.event.clear()  # the real queue: only this test's posts
        scene._handle_quit_key_press()
        assert len(pygame.event.get(eventtype=pygame.QUIT)) == 1


class TestSceneKeyUpEvent:
    """Test Scene.on_key_up_event() method."""

    def test_key_up_q_quits_when_no_focused_sprites(self, mocker):
        """Test 'q' key up triggers quit when no sprites are focused."""
        scene = Scene()
        pygame.event.clear()  # the real queue: only this test's posts

        scene.record_key_press(key=pygame.K_q)
        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_up_event(event)

        assert len(pygame.event.get(eventtype=pygame.QUIT)) == 1

    def test_key_up_escape_quits_when_no_focused_sprites(self, mocker):
        """Test escape key up triggers quit when no sprites are focused."""
        scene = Scene()
        pygame.event.clear()  # the real queue: only this test's posts

        scene.record_key_press(key=pygame.K_ESCAPE)
        event = mocker.Mock()
        event.key = pygame.K_ESCAPE

        scene.on_key_up_event(event)

        assert len(pygame.event.get(eventtype=pygame.QUIT)) == 1

    def test_key_up_q_does_not_quit_without_a_press_in_this_scene(self, mocker):
        """A Q release whose press this scene never received does not quit.

        For example, a Q pressed during a transition or in the previous scene.
        """
        scene = Scene()
        pygame.event.clear()  # the real queue: only this test's posts

        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_up_event(event)

        assert pygame.event.get(eventtype=pygame.QUIT) == []

    def test_each_quit_key_press_allows_one_quit_release(self, mocker):
        """A recorded press is consumed by its release."""
        scene = Scene()
        pygame.event.clear()  # the real queue: only this test's posts
        scene.record_key_press(key=pygame.K_ESCAPE)
        event = mocker.Mock()
        event.key = pygame.K_ESCAPE

        scene.on_key_up_event(event)
        scene.on_key_up_event(event)

        assert len(pygame.event.get(eventtype=pygame.QUIT)) == 1

    def test_key_up_does_not_quit_when_sprites_focused(self, mocker):
        """Test key up does not quit when sprites are focused."""
        scene = Scene()
        pygame.event.clear()  # the real queue: only this test's posts

        # Add a focused sprite
        scene.all_sprites.add(RecordingSprite(is_active=True))
        scene.record_key_press(key=pygame.K_q)

        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_up_event(event)

        assert pygame.event.get(eventtype=pygame.QUIT) == []


class TestSceneKeyDownEvent:
    """Test Scene.on_key_down_event() method."""

    def test_key_down_q_does_not_quit_on_the_press(self, mocker):
        """Q's press posts no QUIT and sets no flag: Q quits on its release (BUGS.md #203)."""
        scene = Scene()
        pygame.event.clear(eventtype=pygame.QUIT)

        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_down_event(event)

        assert pygame.event.get(eventtype=pygame.QUIT) == []
        assert not hasattr(scene, 'quit_requested')

    def test_key_down_handled_by_focused_sprite(self, mocker):
        """Test key down is handled by focused sprite first."""
        scene = Scene()

        focused_sprite = RecordingSprite(is_active=True)
        scene.all_sprites.add(focused_sprite)

        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_down_event(event)

        assert focused_sprite.key_down_events == [event]


class TestSceneEventHandlers:
    """Test various Scene event handler stubs."""

    def test_on_audio_device_added_event(self, mocker):
        """Test audio device added event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_audio_device_added_event(event)  # Should not raise

    def test_on_audio_device_removed_event(self, mocker):
        """Test audio device removed event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_audio_device_removed_event(event)

    def test_on_controller_button_down_event(self, mocker):
        """Test controller button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_controller_button_down_event(event)

    def test_on_controller_button_up_event(self, mocker):
        """Test controller button up event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_controller_button_up_event(event)

    def test_on_joy_button_down_event(self, mocker):
        """Test joy button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_joy_button_down_event(event)

    def test_on_joy_button_up_event(self, mocker):
        """Test joy button up event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_joy_button_up_event(event)

    def test_on_menu_item_event(self, mocker):
        """Test menu item event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_menu_item_event(event)

    def test_on_sys_wm_event(self, mocker):
        """Test sys wm event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_sys_wm_event(event)

    def test_on_text_editing_event(self, mocker):
        """Test text editing event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_text_editing_event(event)

    def test_on_text_input_event(self, mocker):
        """Test text input event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_text_input_event(event)

    def test_on_touch_down_event(self, mocker):
        """Test touch down event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_touch_down_event(event)

    def test_on_touch_motion_event(self, mocker):
        """Test touch motion event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_touch_motion_event(event)

    def test_on_touch_up_event(self, mocker):
        """Test touch up event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_touch_up_event(event)

    def test_on_user_event(self, mocker):
        """Test user event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_user_event(event)

    def test_on_video_expose_event(self, mocker):
        """Test video expose event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_video_expose_event(event)

    def test_on_video_resize_event(self, mocker):
        """Test video resize event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_video_resize_event(event)

    def test_on_window_close_event(self, mocker):
        """Test window close event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_window_close_event(event)

    def test_on_window_enter_event(self, mocker):
        """Test window enter event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_window_enter_event(event)

    def test_on_window_exposed_event(self, mocker):
        """Test window exposed event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_window_exposed_event(event)

    def test_on_window_focus_gained_event(self, mocker):
        """Test window focus gained event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_window_focus_gained_event(event)


class TestSceneMouseEventHandlers:
    """Test mouse-related event handlers on Scene."""

    def test_on_mouse_button_down_event(self, mocker):
        """Test mouse button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_mouse_button_down_event(event)

    def test_on_mouse_drag_event(self, mocker):
        """Test mouse drag event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_mouse_drag_event(event, trigger)

    def test_on_mouse_drop_event(self, mocker):
        """Test mouse drop event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_mouse_drop_event(event, trigger)

    def test_on_left_mouse_drag_event(self, mocker):
        """Test left mouse drag event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_left_mouse_drag_event(event, trigger)

    def test_on_left_mouse_drop_event(self, mocker):
        """Test left mouse drop event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_left_mouse_drop_event(event, trigger)

    def test_on_middle_mouse_drag_event(self, mocker):
        """Test middle mouse drag event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_middle_mouse_drag_event(event, trigger)

    def test_on_middle_mouse_drop_event(self, mocker):
        """Test middle mouse drop event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_middle_mouse_drop_event(event, trigger)

    def test_on_right_mouse_drag_event(self, mocker):
        """Test right mouse drag event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_right_mouse_drag_event(event, trigger)

    def test_on_right_mouse_drop_event(self, mocker):
        """Test right mouse drop event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_right_mouse_drop_event(event, trigger)

    def test_on_left_mouse_button_up_event(self, mocker):
        """Test left mouse button up event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_left_mouse_button_up_event(event)

    def test_on_middle_mouse_button_up_event(self, mocker):
        """Test middle mouse button up event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_middle_mouse_button_up_event(event)

    def test_on_right_mouse_button_up_event(self, mocker):
        """Test right mouse button up event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_right_mouse_button_up_event(event)

    def test_on_left_mouse_button_down_event(self, mocker):
        """Test left mouse button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_left_mouse_button_down_event(event)

    def test_on_middle_mouse_button_down_event(self, mocker):
        """Test middle mouse button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_middle_mouse_button_down_event(event)

    def test_on_right_mouse_button_down_event(self, mocker):
        """Test right mouse button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_right_mouse_button_down_event(event)


class TestScenePauseAndResume:
    """Test Scene pause/resume/game_over methods."""

    def test_pause_requests_a_pause_scene_after_this_frame(self, mocker):
        """pause() sets next_scene instead of switching mid-frame.

        Switching during event processing would freeze the screenshot of the previous render
        while sprites have already moved this frame, so the paused picture and game state
        would disagree by one frame.
        """
        from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene

        scene = Scene()
        scene.scene_manager.switch_to_scene = mocker.Mock()

        scene.pause()

        assert isinstance(scene.next_scene, PauseScene)
        scene.scene_manager.switch_to_scene.assert_not_called()

    def test_bootstrap_scene_reaches_the_scene_its_init_requests(self, mocker):
        """A scene whose __init__ sets next_scene hands over at the end of its first frame.

        Bootstrap scenes (joystick_demo, scripts/cached_fonts.py) request their real scene in
        __init__; activating them must not wipe that request.
        """
        scene_manager = SceneManager()
        first_real_scene = Scene()

        class BootstrapScene(Scene):
            def __init__(self) -> None:
                super().__init__()
                self.next_scene = first_real_scene

        bootstrap_scene = BootstrapScene()

        scene_manager.switch_to_scene(bootstrap_scene)
        scene_manager._switch_to_requested_scene()

        assert scene_manager.active_scene is first_real_scene

    def test_resumed_scene_does_not_switch_back_to_the_old_pause_scene(self, mocker):
        """After pause -> resume, the game scene has no pending switch left over.

        A game that paused by setting next_scene would otherwise pause again one frame after
        resuming, because its next_scene still pointed at the old pause scene.
        """
        scene_manager = SceneManager()
        game_scene = Scene()
        pause_scene = Scene()
        scene_manager.switch_to_scene(game_scene)

        game_scene.next_scene = pause_scene  # the game requests a pause
        scene_manager._switch_to_requested_scene()
        assert scene_manager.active_scene is pause_scene

        scene_manager.switch_to_scene(scene_manager.previous_scene)  # resume
        scene_manager._switch_to_requested_scene()

        assert scene_manager.active_scene is game_scene
        assert game_scene.next_scene is None

    def test_a_scene_naming_itself_next_is_reset_to_none(self):
        """next_scene = self (an older way to say "stay") stays put, and the cycle is broken."""
        scene_manager = SceneManager()
        game_scene = Scene()
        scene_manager.switch_to_scene(game_scene)
        game_scene.next_scene = game_scene

        scene_manager._switch_to_requested_scene()

        assert scene_manager.active_scene is game_scene
        assert game_scene.next_scene is None

    def test_scene_left_through_a_transition_does_not_switch_back_on_return(self, mocker):
        """A next_scene left on a scene that leaves via a transition is cleared.

        Otherwise returning to that scene later would switch straight back to the stale
        next_scene (e.g. an old pause scene) at the end of the first frame.
        """
        scene_manager = SceneManager()
        game_scene = Scene()
        stale_pause_scene = Scene()
        next_floor_scene = Scene()
        scene_manager.switch_to_scene(game_scene)
        game_scene.next_scene = stale_pause_scene  # left over, then the game transitions

        scene_manager._start_transition(next_floor_scene, mocker.Mock())
        assert game_scene.next_scene is None

        scene_manager.switch_to_scene(game_scene)  # the game is returned to later
        scene_manager._switch_to_requested_scene()

        assert scene_manager.active_scene is game_scene

    def test_bootstrap_scene_reached_through_a_transition_still_hands_over(self, mocker):
        """A transition into a scene whose __init__ sets next_scene keeps that request."""
        scene_manager = SceneManager()
        first_real_scene = Scene()

        class BootstrapScene(Scene):
            def __init__(self) -> None:
                super().__init__()
                self.next_scene = first_real_scene

        scene_manager.switch_to_scene(Scene())
        scene_manager._start_transition(BootstrapScene(), mocker.Mock())
        scene_manager._switch_to_requested_scene()

        assert scene_manager.active_scene is first_real_scene

    def test_resume_switches_to_previous_scene(self, mocker):
        """Test resume() switches back to the previous scene."""
        scene = Scene()
        previous = Scene()
        scene.scene_manager.previous_scene = previous
        scene.scene_manager.switch_to_scene = mocker.Mock()

        scene.resume()

        scene.scene_manager.switch_to_scene.assert_called_once_with(previous)

    def test_resume_without_previous_scene(self, mocker):
        """Test resume() when no previous scene exists."""
        scene = Scene()
        scene.scene_manager.previous_scene = None
        scene.scene_manager.switch_to_scene = mocker.Mock()

        scene.resume()

        scene.scene_manager.switch_to_scene.assert_not_called()

    def test_game_over_creates_game_over_scene(self, mocker):
        """Test game_over() creates and switches to GameOverScene."""
        scene = Scene()
        scene.scene_manager.switch_to_scene = mocker.Mock()

        scene.game_over()

        scene.scene_manager.switch_to_scene.assert_called_once()


class TestSceneOnFpsEvent:
    """Test Scene.on_fps_event() method."""

    def test_on_fps_event_updates_fps(self, mocker):
        """Test FPS event updates the scene's fps attribute."""
        scene = Scene()
        event = mocker.Mock()
        event.fps = 59.5

        scene.on_fps_event(event)

        assert abs(scene.fps - 59.5) < 1e-9

    def test_on_fps_event_logs_once_per_interval_of_the_frame_clock(self, mocker):
        """The FPS log interval is measured on the frame clock, which a replay serves."""
        scene = Scene()
        scene.scene_manager.fps_log_interval_ms = 1000
        log_info = mocker.patch.object(scene.log, 'info')
        event = mocker.Mock()
        event.fps = 60.0

        advance_frame_clock(seconds=1.0)
        scene.on_fps_event(event)  # one interval since the scene started: logs
        scene.on_fps_event(event)  # no frame time since: silent
        advance_frame_clock(seconds=0.5)
        scene.on_fps_event(event)  # half an interval: silent
        advance_frame_clock(seconds=0.5)
        scene.on_fps_event(event)  # a full interval since the last log: logs

        assert log_info.call_count == 2


class TestSceneOnTextSubmitEvent:
    """Test Scene.on_text_submit_event() method."""

    def test_on_text_submit_event_logs(self, mocker):
        """Test text submit event is handled."""
        scene = Scene()
        scene.on_text_submit_event('Hello World')


class TestSceneManagerHelpers:
    """Test SceneManager helper methods."""

    def test_a_scene_that_terminates_in_its_logic_finishes_the_frame(self, mocker):
        """terminate() from dt_tick leaves no active scene; the frame still runs to its end."""
        manager = SceneManager()

        class TerminatingScene(Scene):
            def dt_tick(self, dt: float) -> None:
                super().dt_tick(dt)
                self.scene_manager.terminate()

        manager.switch_to_scene(TerminatingScene())
        for frame_step in ('update_screen', '_render_scene', '_present_frame'):
            mocker.patch.object(manager, frame_step)

        manager._run_scene_frame()

        assert manager.active_scene is None

    def test_without_an_active_scene_the_scene_reads_answer_none(self):
        """No active scene (the run ended): no scene start, no presented scene, the raw dt."""
        manager = SceneManager()
        manager.switch_to_scene(None)
        manager.dt = 0.25

        assert manager.active_scene_start is None
        assert manager._presented_scene() is None
        assert manager._active_camera() is None
        assert manager._scene_frame_seconds() == manager.dt
        manager._begin_scene_logic_frame()  # nothing to begin

        assert manager.active_scene is None

    def test_a_scene_switched_to_without_an_engine_gets_none(self):
        """A bare SceneManager (no GameEngine) sets a scene up without handing it an engine."""
        manager = SceneManager()
        manager.game_engine = None
        scene = Scene()

        manager.switch_to_scene(scene)

        assert manager.active_scene is scene
        assert getattr(scene, 'game_engine', None) is None

    def test_a_scene_interface_stand_in_is_refused_and_the_active_scene_kept(self, mocker):
        """A SceneInterface that is not a Scene is refused before anything is torn down or set up.

        The scene manager reads the attributes Scene declares (its key-press records, camera,
        scene start), so a stand-in without them never becomes the active scene.
        """
        manager = SceneManager()
        active_scene = Scene()
        manager.switch_to_scene(active_scene)
        cleanup = mocker.spy(active_scene, 'cleanup')

        with pytest.raises(TypeError, match='must be a Scene or None, not SceneInterface'):
            manager.switch_to_scene(SceneInterface())

        assert manager.active_scene is active_scene
        cleanup.assert_not_called()

    def test_a_transition_frame_without_an_engine_has_no_events_to_process(self, mocker):
        """With no GameEngine (a bare SceneManager), a transition frame still plays."""
        manager = SceneManager()
        manager.game_engine = None
        transition = mocker.Mock()
        transition.update.return_value = False
        manager._active_transition = transition
        for frame_step in ('_update_frame_services', '_present_frame'):
            mocker.patch.object(manager, frame_step)

        manager._run_frame_contents()

        transition.render.assert_called_once_with(manager.screen)
        assert manager._active_transition is transition

    def test_debug_overlay_mouse_position_comes_from_the_frame_input(self, mocker):
        """The debug overlay shows the frame's polled mouse position, None without focus."""
        manager = SceneManager()

        _install_frame_input(mouse_position=(12, 34), mouse_focused=True)
        focused_info = manager._debug_frame_info(
            shake_offset=(0.0, 0.0), inspected_scene_label=None
        )
        _install_frame_input(mouse_position=(12, 34), mouse_focused=False)
        unfocused_info = manager._debug_frame_info(
            shake_offset=(0.0, 0.0), inspected_scene_label=None
        )

        assert focused_info.mouse_position == (12, 34)
        assert unfocused_info.mouse_position is None

    def test_scene_manager_stop(self, mocker):
        """Test SceneManager.stop() calls terminate."""
        manager = SceneManager()
        manager.switch_to_scene = mocker.Mock()
        manager.stop()
        manager.switch_to_scene.assert_called_once_with(None)

    def test_scene_manager_quit(self, mocker):
        """Test SceneManager.quit() posts QUIT event."""
        manager = SceneManager()
        pygame.event.clear()  # the real queue: only this test's posts
        manager.quit()
        assert len(pygame.event.get(eventtype=pygame.QUIT)) == 1

    def test_scene_manager_on_quit_event(self, mocker):
        """Test SceneManager.on_quit_event sets quit_requested."""
        manager = SceneManager()
        event = mocker.Mock()

        manager.on_quit_event(event)

        assert manager.quit_requested is True

    def test_scene_manager_all_sprites_with_active_scene(self, mocker):
        """Test SceneManager.all_sprites returns active scene's sprites."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene

        assert manager.all_sprites == scene.all_sprites

    def test_scene_manager_all_sprites_without_active_scene(self):
        """Test SceneManager.all_sprites returns None without active scene."""
        manager = SceneManager()
        manager.active_scene = None

        assert manager.all_sprites is None


class TestLogJitterStats:
    """Test SceneManager._log_jitter_stats() method."""

    def test_log_jitter_stats_initializes_buffer_on_first_call(self, mocker):
        """Test that _log_jitter_stats initializes jitter buffer on first call."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 1000

        mock_timer = mocker.Mock()
        mock_timer.ns_now.return_value = 1_000_000_000

        # First call should create _jitter_samples
        manager._log_jitter_stats(mock_timer, wake_ns=1_000_100, deadline_ns=1_000_000)

        assert hasattr(manager, '_jitter_samples')
        assert len(manager._jitter_samples) == 1
        assert manager._jitter_samples[0] == 100  # jitter_ns = wake - deadline

    def test_log_jitter_stats_accumulates_samples(self, mocker):
        """Test that _log_jitter_stats accumulates jitter samples."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 1000

        mock_timer = mocker.Mock()
        # Return increasing timestamps, but not enough to trigger interval log
        mock_timer.ns_now.return_value = 100_000_000

        for i in range(5):
            manager._log_jitter_stats(mock_timer, wake_ns=1000 + i * 50, deadline_ns=1000)

        assert len(manager._jitter_samples) == 5

    def test_log_jitter_stats_trims_buffer_when_exceeds_max(self, mocker):
        """Test that _log_jitter_stats trims buffer when it exceeds max size."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 100_000  # Large interval to avoid triggering log

        mock_timer = mocker.Mock()
        mock_timer.ns_now.return_value = 100_000_000

        # Pre-fill the buffer beyond max
        manager._jitter_samples = list(range(JITTER_SAMPLE_BUFFER_MAX_SIZE + 100))
        manager._jitter_last_log_ns = 0
        manager._jitter_interval_start_ns = 0
        manager._jitter_late_frames = 0

        manager._log_jitter_stats(mock_timer, wake_ns=2000, deadline_ns=1000)

        # Buffer should be trimmed to max size
        assert len(manager._jitter_samples) <= JITTER_SAMPLE_BUFFER_MAX_SIZE

    def test_log_jitter_stats_counts_late_frames(self, mocker):
        """Test that _log_jitter_stats counts late frames when jitter > 0."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 100_000  # Large to avoid triggering log

        mock_timer = mocker.Mock()
        mock_timer.ns_now.return_value = 100_000_000

        # Call with positive jitter
        manager._log_jitter_stats(mock_timer, wake_ns=2000, deadline_ns=1000)
        manager._log_jitter_stats(mock_timer, wake_ns=3000, deadline_ns=1000)

        assert manager._jitter_late_frames == 2

    def test_log_jitter_stats_zero_jitter_not_late(self, mocker):
        """Test that _log_jitter_stats does not count zero jitter as late."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 100_000

        mock_timer = mocker.Mock()
        mock_timer.ns_now.return_value = 100_000_000

        # Call with zero jitter (wake == deadline)
        manager._log_jitter_stats(mock_timer, wake_ns=1000, deadline_ns=1000)

        assert manager._jitter_late_frames == 0

    def test_log_jitter_stats_triggers_interval_log(self, mocker):
        """Test that _log_jitter_stats triggers interval log when time exceeds interval."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 1  # 1ms interval (very short)

        mock_timer = mocker.Mock()
        # First call initializes
        mock_timer.ns_now.return_value = 0
        manager._log_jitter_stats(mock_timer, wake_ns=100, deadline_ns=0)

        # Second call exceeds interval (2ms later = 2_000_000 ns)
        mock_timer.ns_now.return_value = 2_000_000
        mock_log = mocker.patch.object(manager, 'log')
        manager._log_jitter_stats(mock_timer, wake_ns=2_000_100, deadline_ns=2_000_000)

        mock_log.info.assert_called()

    def test_log_jitter_stats_handles_exception_gracefully(self, mocker):
        """Test that _log_jitter_stats handles exceptions without crashing."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 'invalid'  # type: ignore[invalid-assignment]  # Will cause ValueError in float()

        mock_timer = mocker.Mock()
        mock_timer.ns_now.return_value = 1_000_000_000

        # Should not raise
        manager._log_jitter_stats(mock_timer, wake_ns=2000, deadline_ns=1000)


class TestLogJitterInterval:
    """Test SceneManager._log_jitter_interval() method."""

    def test_log_jitter_interval_with_data(self, mocker):
        """Test _log_jitter_interval logs percentile statistics."""
        manager = SceneManager()
        manager._jitter_interval_start_ns = 0
        manager._jitter_late_frames = 5

        mock_log = mocker.patch.object(manager, 'log')

        buffer = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        manager._log_jitter_interval(buffer, now_ns=1_000_000_000)

        mock_log.info.assert_called_once()
        call_args = mock_log.info.call_args[0][0]
        assert 'p50=' in call_args
        assert 'p95=' in call_args
        assert 'p99=' in call_args
        assert 'max=' in call_args
        assert 'avg_fps=' in call_args
        assert 'late=' in call_args

    def test_log_jitter_interval_resets_counters(self, mocker):
        """Test _log_jitter_interval resets counters after logging."""
        manager = SceneManager()
        manager._jitter_interval_start_ns = 0
        manager._jitter_late_frames = 10
        mocker.patch.object(manager, 'log')

        now_ns = 5_000_000_000
        manager._log_jitter_interval([100, 200], now_ns=now_ns)

        assert manager._jitter_last_log_ns == now_ns
        assert manager._jitter_interval_start_ns == now_ns
        assert manager._jitter_late_frames == 0

    def test_log_jitter_interval_empty_buffer(self, mocker):
        """Test _log_jitter_interval with empty buffer does not log."""
        manager = SceneManager()
        manager._jitter_interval_start_ns = 0
        manager._jitter_late_frames = 0

        mock_log = mocker.patch.object(manager, 'log')
        manager._log_jitter_interval([], now_ns=1_000_000_000)

        # info should not be called since count is 0
        mock_log.info.assert_not_called()


class TestHandleFramePacing:
    """Test SceneManager._handle_frame_pacing() method."""

    def test_handle_frame_pacing_with_timer(self, mocker):
        """Test frame pacing delegates to timer when available."""
        manager = SceneManager()
        type(manager).OPTIONS = {'log_timer_jitter': False}

        mock_timer = mocker.Mock()
        mock_timer.compute_deadline.return_value = 2_000_000
        mock_timer.sleep_until_next.return_value = 2_000_100

        manager._handle_frame_pacing(
            timer=mock_timer,
            period_ns=16_666_667,
            prev_deadline_ns=1_000_000,
            paced_seconds=None,
        )

        mock_timer.compute_deadline.assert_called_once()
        mock_timer.sleep_until_next.assert_called_once()
        assert manager._timer_prev_deadline_ns == 2_000_000

    def test_handle_frame_pacing_with_timer_and_jitter_logging(self, mocker):
        """Test frame pacing calls jitter logging when enabled."""
        manager = SceneManager()
        type(manager).OPTIONS = {'log_timer_jitter': True}
        manager.fps_log_interval_ms = 100_000

        mock_timer = mocker.Mock()
        mock_timer.compute_deadline.return_value = 2_000_000
        mock_timer.sleep_until_next.return_value = 2_000_100
        mock_timer.ns_now.return_value = 100_000

        mock_log_jitter = mocker.patch.object(manager, '_log_jitter_stats')

        manager._handle_frame_pacing(
            timer=mock_timer,
            period_ns=16_666_667,
            prev_deadline_ns=1_000_000,
            paced_seconds=None,
        )

        mock_log_jitter.assert_called_once_with(mock_timer, 2_000_100, 2_000_000)

    def test_handle_frame_pacing_fallback_with_target_fps(self, mocker):
        """Test frame pacing falls back to clock.tick when no timer but target_fps > 0."""
        manager = SceneManager()
        manager.target_fps = 60

        # The pacing clock is real time: a stand-in records the tick it is asked for
        manager.clock = mocker.Mock(spec=pygame.time.Clock)
        mock_clock_tick = manager.clock.tick

        manager._handle_frame_pacing(
            timer=None,
            period_ns=0,
            prev_deadline_ns=None,
            paced_seconds=None,
        )

        mock_clock_tick.assert_called_once_with(60)

    def test_handle_frame_pacing_fallback_unlimited_fps(self, mocker):
        """Test frame pacing falls back to clock.tick() when no timer and target_fps is 0."""
        manager = SceneManager()
        manager.target_fps = 0

        # The pacing clock is real time: a stand-in records the tick it is asked for
        manager.clock = mocker.Mock(spec=pygame.time.Clock)
        mock_clock_tick = manager.clock.tick

        manager._handle_frame_pacing(
            timer=None,
            period_ns=0,
            prev_deadline_ns=None,
            paced_seconds=None,
        )

        mock_clock_tick.assert_called_once_with()

    def test_handle_frame_pacing_never_waits_for_an_unpaced_frame(self, mocker):
        """paced_seconds 0.0 (a headless replay): no timer deadline and no clock tick."""
        manager = SceneManager()
        manager.target_fps = 60
        mock_timer = mocker.Mock()
        # The pacing clock is real time: a stand-in records the tick it is asked for
        manager.clock = mocker.Mock(spec=pygame.time.Clock)
        mock_clock_tick = manager.clock.tick

        manager._handle_frame_pacing(
            timer=mock_timer,
            period_ns=0,
            prev_deadline_ns=1_000_000,
            paced_seconds=0.0,
        )
        manager._handle_frame_pacing(
            timer=None, period_ns=0, prev_deadline_ns=None, paced_seconds=0.0
        )

        mock_timer.compute_deadline.assert_not_called()
        mock_timer.sleep_until_next.assert_not_called()
        mock_clock_tick.assert_not_called()

    def test_handle_frame_pacing_never_mixes_backends_for_a_sub_nanosecond_period(self, mocker):
        """A positive period that rounds to 0 ns with a timer: no deadline and no clock tick."""
        manager = SceneManager()
        manager.target_fps = 60
        mock_timer = mocker.Mock()
        # The pacing clock is real time: a stand-in records the tick it is asked for
        manager.clock = mocker.Mock(spec=pygame.time.Clock)
        mock_clock_tick = manager.clock.tick

        manager._handle_frame_pacing(
            timer=mock_timer, period_ns=0, prev_deadline_ns=None, paced_seconds=1e-10
        )

        mock_timer.compute_deadline.assert_not_called()
        mock_timer.sleep_until_next.assert_not_called()
        mock_clock_tick.assert_not_called()

    def test_handle_frame_pacing_without_a_timer_ticks_at_the_paced_period(self, mocker):
        """A positive paced period replaces the target FPS for the pygame clock."""
        manager = SceneManager()
        manager.target_fps = 60
        # The pacing clock is real time: a stand-in records the tick it is asked for
        manager.clock = mocker.Mock(spec=pygame.time.Clock)
        mock_clock_tick = manager.clock.tick

        manager._handle_frame_pacing(
            timer=None, period_ns=0, prev_deadline_ns=None, paced_seconds=0.25
        )

        mock_clock_tick.assert_called_once_with(4.0)


class TestFinishFrameMeasurement:
    """SceneManager._finish_frame() measures frames with perf_counter, never the timer's clock."""

    def _patch_frame_bookkeeping(self, mocker):
        mocker.patch.object(
            SceneManager, 'OPTIONS', {'log_timer_jitter': False, 'fps_log_interval_ms': 1000}
        )
        mocker.patch('glitchygames.scenes.scene.post_event')
        mock_performance_manager = mocker.Mock()
        mocker.patch(
            'glitchygames.performance.performance_manager', mock_performance_manager, create=True
        )
        return mock_performance_manager

    def test_finish_frame_measures_dt_with_perf_counter_not_timer_clock(self, mocker):
        """Paced dt comes from perf_counter, so a whole-millisecond timer cannot quantize it."""
        manager = SceneManager()
        self._patch_frame_bookkeeping(mocker)
        frame_seconds = 1.0 / 60.0
        mocker.patch(
            'glitchygames.scenes.scene.time',
            mocker.Mock(perf_counter=mocker.Mock(return_value=10.0 + frame_seconds)),
        )

        mock_timer = mocker.Mock()
        mock_timer.compute_deadline.return_value = 2_000_000
        # The timer reports a whole 17 ms wake, which would give dt = 1/0.017 = 58.8 FPS.
        mock_timer.sleep_until_next.return_value = 17_000_000

        closing_reading = manager._finish_frame(
            frame_start_seconds=10.0,
            timer=mock_timer,
            period_ns=16_666_667,
            paced_seconds=None,
            processing_seconds=0.001,
        )

        assert abs(1.0 / manager.dt - 60.0) < 0.01
        assert closing_reading == 10.0 + frame_seconds

    def test_whole_millisecond_timer_steps_record_steady_fps(self, mocker):
        """A 17/17/16 ms timer cadence over true 16.67 ms frames records ~60 FPS each frame."""
        manager = SceneManager()
        mock_performance_manager = self._patch_frame_bookkeeping(mocker)
        frame_seconds = 1.0 / 60.0
        whole_millisecond_wakes = [17_000_000, 34_000_000, 50_000_000]
        mock_perf_counter = mocker.Mock()
        mocker.patch('glitchygames.scenes.scene.time', mocker.Mock(perf_counter=mock_perf_counter))
        mock_timer = mocker.Mock()
        mock_timer.compute_deadline.return_value = 0

        frame_start_seconds = 0.0
        for frame_index, wake_ns in enumerate(whole_millisecond_wakes):
            mock_timer.sleep_until_next.return_value = wake_ns
            mock_perf_counter.return_value = (frame_index + 1) * frame_seconds
            frame_start_seconds = manager._finish_frame(
                frame_start_seconds=frame_start_seconds,
                timer=mock_timer,
                period_ns=16_666_667,
                paced_seconds=None,
                processing_seconds=0.001,
            )

        recorded_values = [
            call.args[0] for call in mock_performance_manager.track_fps_from_event.call_args_list
        ]
        assert len(recorded_values) == 3
        for recorded_fps in recorded_values:
            assert abs(recorded_fps - 60.0) < 0.01

    def test_paced_frame_of_fractional_target_records_exact_fps(self, mocker):
        """A paced frame lasting exactly 1/60.5 s records 60.5 FPS."""
        manager = SceneManager()
        self._patch_frame_bookkeeping(mocker)
        mocker.patch(
            'glitchygames.scenes.scene.time',
            mocker.Mock(perf_counter=mocker.Mock(return_value=5.0 + 1.0 / 60.5)),
        )
        mock_timer = mocker.Mock()
        mock_timer.compute_deadline.return_value = 0
        mock_timer.sleep_until_next.return_value = 17_000_000

        manager._finish_frame(
            frame_start_seconds=5.0,
            timer=mock_timer,
            period_ns=16_528_926,
            paced_seconds=None,
            processing_seconds=0.001,
        )

        assert abs(1.0 / manager.dt - 60.5) < 1e-6

    def test_handle_frame_pacing_does_not_write_dt(self, mocker):
        """Pacing only paces: the frame time is set once, by _finish_frame."""
        manager = SceneManager()
        mocker.patch.object(SceneManager, 'OPTIONS', {'log_timer_jitter': False})
        manager.dt = 0.25
        mock_timer = mocker.Mock()
        mock_timer.compute_deadline.return_value = 2_000_000
        mock_timer.sleep_until_next.return_value = 2_000_100

        manager._handle_frame_pacing(
            timer=mock_timer, period_ns=16_666_667, prev_deadline_ns=None, paced_seconds=None
        )

        assert manager.dt == 0.25


class TestPostFpsEvent:
    """Test SceneManager._post_fps_event() method."""

    def test_post_fps_event_uses_dt_when_available(self):
        """Test _post_fps_event computes FPS from dt when dt > 0."""
        manager = SceneManager()
        manager.dt = 0.016  # ~62.5 FPS

        pygame.event.clear()  # the real queue: only this test's posts

        manager._post_fps_event()

        posted = pygame.event.get(eventtype=FPSEVENT)
        assert len(posted) == 1
        assert posted[0].fps == pytest.approx(1.0 / 0.016)

    def test_post_fps_event_never_falls_back_to_the_clock(self, mocker):
        """A zero frame time posts 0 FPS: pygame's pacing clock is never consulted.

        The clock is real time a replay cannot serve (see SceneManager._post_fps_event).
        """
        manager = SceneManager()
        manager.dt = 0  # dt is zero: no frame time to measure FPS from

        manager.clock = mocker.Mock(spec=pygame.time.Clock)
        manager.clock.get_fps.return_value = 60.0
        pygame.event.clear()  # the real queue: only this test's posts

        manager._post_fps_event()

        posted = pygame.event.get(eventtype=FPSEVENT)
        assert len(posted) == 1
        assert posted[0].fps == 0.0
        manager.clock.get_fps.assert_not_called()


class TestTrackPerformance:
    """Test SceneManager._track_performance() method."""

    def _patch_performance_manager(self, mocker):
        mock_performance_manager = mocker.Mock()
        mocker.patch(
            'glitchygames.performance.performance_manager',
            mock_performance_manager,
            create=True,
        )
        return mock_performance_manager

    def test_track_performance_records_fps_from_measured_frame_time(self, mocker):
        """FPS is 1/dt exactly, not a quantized 10000/N value from pygame's clock."""
        manager = SceneManager()
        manager.dt = 1.0 / 437.3
        mock_performance_manager = self._patch_performance_manager(mocker)

        manager._track_performance(processing_time=0.008)

        recorded_fps = mock_performance_manager.track_fps_from_event.call_args.args[0]
        assert abs(recorded_fps - 437.3) < 1e-6

    def test_track_performance_consecutive_frames_record_different_values(self, mocker):
        """Two frames with different dt are not repeated samples of one value."""
        manager = SceneManager()
        mock_performance_manager = self._patch_performance_manager(mocker)

        manager.dt = 1.0 / 400.0
        manager._track_performance(processing_time=0.001)
        manager.dt = 1.0 / 412.5
        manager._track_performance(processing_time=0.001)

        recorded_values = [
            call.args[0] for call in mock_performance_manager.track_fps_from_event.call_args_list
        ]
        assert len(recorded_values) == 2
        assert recorded_values[0] != recorded_values[1]
        assert abs(recorded_values[0] - 400.0) < 1e-6
        assert abs(recorded_values[1] - 412.5) < 1e-6

    def test_track_performance_does_not_call_clock_get_fps(self, mocker):
        """Pygame's 10-frame clock counter is never consulted."""
        manager = SceneManager()
        manager.dt = 0.016
        manager.clock = mocker.Mock(spec=pygame.time.Clock)
        manager.clock.get_fps.return_value = 999.0
        mock_get_fps = manager.clock.get_fps
        mock_performance_manager = self._patch_performance_manager(mocker)

        manager._track_performance(processing_time=0.008)

        mock_get_fps.assert_not_called()
        recorded_fps = mock_performance_manager.track_fps_from_event.call_args.args[0]
        assert abs(recorded_fps - 62.5) < 1e-6

    def test_track_performance_zero_dt_records_zero(self, mocker):
        """A zero dt records 0.0 rather than dividing by zero."""
        manager = SceneManager()
        manager.dt = 0.0
        mock_performance_manager = self._patch_performance_manager(mocker)

        manager._track_performance(processing_time=0.008)

        recorded_fps = mock_performance_manager.track_fps_from_event.call_args.args[0]
        assert recorded_fps == 0.0


class TestSceneManagerOnFpsEvent:
    """Test SceneManager.on_fps_event() method."""

    def test_on_fps_event_delegates_to_active_scene(self, mocker):
        """Test on_fps_event delegates to active scene."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene
        mock_on_fps = mocker.patch.object(scene, 'on_fps_event')

        event = mocker.Mock()
        event.fps = 60.0

        manager.on_fps_event(event)

        mock_on_fps.assert_called_once_with(event)

    def test_on_fps_event_no_active_scene(self, mocker):
        """Test on_fps_event does nothing when no active scene."""
        manager = SceneManager()
        manager.active_scene = None

        event = mocker.Mock()
        event.fps = 60.0

        # Should not raise
        manager.on_fps_event(event)


class TestSceneManagerOnGameEvent:
    """Test SceneManager.on_game_event() method."""

    def test_on_game_event_calls_registered_callback(self, mocker):
        """Test on_game_event calls the registered callback."""
        manager = SceneManager()
        mock_engine = mocker.Mock()
        callback = mocker.Mock()
        mock_engine.registered_events = {'my_event': callback}
        manager._game_engine = mock_engine

        event = mocker.Mock()
        event.subtype = 'my_event'

        manager.on_game_event(event)

        callback.assert_called_once_with(event)

    def test_on_game_event_unregistered_logs_error(self, mocker):
        """Test on_game_event logs error for unregistered event."""
        manager = SceneManager()
        mock_engine = mocker.Mock()
        mock_engine.registered_events = {}
        manager._game_engine = mock_engine

        event = mocker.Mock()
        event.subtype = 'unknown_event'

        mock_log = mocker.patch.object(manager, 'log')

        manager.on_game_event(event)

        mock_log.error.assert_called_once()


class TestSceneManagerHandleEvent:
    """Test SceneManager.handle_event() method."""

    def test_handle_event_quit(self, mocker):
        """Test handle_event sets quit_requested for QUIT events."""
        manager = SceneManager()
        mock_log = mocker.patch.object(manager, 'log')

        event = mocker.Mock()
        event.type = pygame.QUIT

        manager.handle_event(event)

        assert manager.quit_requested is True

    def test_handle_event_with_focused_sprite_keydown(self, mocker):
        """Test handle_event returns early when focused sprite gets KEYDOWN."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene

        scene.all_sprites.add(RecordingSprite(is_active=True))

        event = mocker.Mock()
        event.type = pygame.KEYDOWN

        # Should return early without setting quit_requested
        manager.handle_event(event)
        assert manager.quit_requested is False

    def test_handle_event_no_active_scene(self, mocker):
        """Test handle_event does not crash when no active scene."""
        manager = SceneManager()
        manager.active_scene = None

        event = mocker.Mock()
        event.type = pygame.KEYDOWN

        # Should not raise
        manager.handle_event(event)


class TestSceneManagerGetattr:
    """Test SceneManager.__getattr__() proxy method."""

    def test_getattr_proxies_event_to_active_scene(self, mocker):
        """Test __getattr__ proxies on_*_event calls to active scene."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene

        # This should resolve to the scene's method
        method = manager.on_key_down_event
        assert callable(method)

    def test_getattr_raises_for_non_event_attrs(self, mocker):
        """Test __getattr__ raises AttributeError for non-event attributes."""
        manager = SceneManager()

        with pytest.raises(AttributeError, match='object has no attribute'):
            _ = manager.nonexistent_attribute

    def test_getattr_falls_back_to_game_engine(self, mocker):
        """Test __getattr__ falls back to game engine when scene doesn't have method."""
        manager = SceneManager()
        manager.active_scene = None

        mock_engine = mocker.Mock()
        mock_engine.on_custom_event = mocker.Mock()
        manager._game_engine = mock_engine

        # When active_scene is None, getattr on it raises AttributeError,
        # so it falls through to game_engine
        method = manager.on_custom_event
        assert callable(method)


class TestSceneManagerShouldPostFpsEvent:
    """Test SceneManager._should_post_fps_event() method."""

    def test_should_post_fps_event_true(self, mocker):
        """Test returns True when time exceeds half the log interval."""
        manager = SceneManager()
        type(manager).OPTIONS = {'fps_log_interval_ms': 1000}

        # 600ms has passed, half of 1000ms = 500ms
        result = manager._should_post_fps_event(current_time=1.0, previous_fps_time=0.4)
        assert result is True

    def test_should_post_fps_event_false(self, mocker):
        """Test returns False when time does not exceed half the log interval."""
        manager = SceneManager()
        type(manager).OPTIONS = {'fps_log_interval_ms': 1000}

        # Only 100ms has passed, half of 1000ms = 500ms
        result = manager._should_post_fps_event(current_time=1.0, previous_fps_time=0.9)
        assert result is False


class TestSceneManagerPlay:
    """Test SceneManager.play() method."""

    def test_play_delegates_to_start(self, mocker):
        """Test play() calls start()."""
        manager = SceneManager()
        mock_start = mocker.patch.object(manager, 'start')

        manager.play()

        mock_start.assert_called_once()


class TestSceneManagerQuitGame:
    """Test SceneManager.quit_game() method."""

    def test_quit_game_posts_quit_event(self, mocker):
        """Test quit_game() posts a QUIT event to the pygame event queue."""
        manager = SceneManager()
        pygame.event.clear()  # the real queue: only this test's posts

        manager.quit_game()

        assert len(pygame.event.get(eventtype=pygame.QUIT)) == 1


class TestSceneManagerGetattrDeeper:
    """Test SceneManager.__getattr__ proxy method."""

    def test_getattr_proxies_event_method_to_active_scene(self, mocker):
        """Test __getattr__ proxies on_*_event calls to active scene."""
        manager = SceneManager()
        scene = Scene()
        scene.on_custom_test_event = mocker.Mock()  # type: ignore[unresolved-attribute]
        manager.active_scene = scene

        handler = manager.on_custom_test_event
        assert handler is scene.on_custom_test_event  # type: ignore[unresolved-attribute]

    def test_getattr_raises_for_non_event_attributes(self, mocker):
        """Test __getattr__ raises AttributeError for non-event attributes."""
        manager = SceneManager()
        with pytest.raises(AttributeError):
            _ = manager.some_random_attribute

    def test_getattr_falls_back_to_game_engine(self, mocker):
        """Test __getattr__ falls back to game_engine when scene has no handler."""
        manager = SceneManager()
        # Create a scene mock that raises AttributeError for on_some_obscure_event
        scene = mocker.Mock()
        del scene.on_some_obscure_event  # Force AttributeError on this attribute
        manager.active_scene = scene

        # Set _game_engine directly to avoid the setter's OPTIONS subscription
        mock_engine = mocker.Mock()
        mock_handler = mocker.Mock()
        mock_engine.on_some_obscure_event = mock_handler
        manager._game_engine = mock_engine

        handler = manager.on_some_obscure_event
        assert handler is mock_handler


class TestSceneManagerHandleEventDeeper:
    """Test SceneManager.handle_event method."""

    def test_handle_event_quit_sets_flag(self, mocker):
        """Test handle_event with QUIT event sets quit_requested."""
        manager = SceneManager()
        manager.active_scene = mocker.Mock()
        manager.active_scene.all_sprites = []

        event = mocker.Mock()
        event.type = pygame.QUIT

        manager.handle_event(event)
        assert manager.quit_requested is True

    def test_handle_event_keydown_with_focused_sprites(self, mocker):
        """Test handle_event KEYDOWN routes through to scene when sprites are focused."""
        manager = SceneManager()
        scene = Scene()
        scene.all_sprites.add(RecordingSprite(is_active=True))
        manager.active_scene = scene

        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_a

        # This should not quit since there are focused sprites
        manager.handle_event(event)
        # quit_requested should remain False (not a quit event)
        assert manager.quit_requested is not True


class TestSceneManagerShouldPostFpsEventDeeper:
    """Test SceneManager._should_post_fps_event method."""

    def test_should_post_fps_event_true(self, mocker):
        """Test returns True when enough time has elapsed."""
        manager = SceneManager()
        type(manager).OPTIONS = {'fps_log_interval_ms': 1000}

        # 1 second elapsed, interval is 500ms (half of 1000)
        result = manager._should_post_fps_event(current_time=2.0, previous_fps_time=1.0)
        assert result is True

    def test_should_post_fps_event_false(self, mocker):
        """Test returns False when not enough time has elapsed."""
        manager = SceneManager()
        type(manager).OPTIONS = {'fps_log_interval_ms': 1000}

        # 0.1 second elapsed, interval is 500ms
        result = manager._should_post_fps_event(current_time=1.1, previous_fps_time=1.0)
        assert result is False


class TestSceneManagerPostFpsEvent:
    """Test SceneManager._post_fps_event method."""

    def test_post_fps_event_with_dt(self):
        """Test _post_fps_event posts event based on dt."""
        manager = SceneManager()
        manager.dt = 0.016  # ~60 FPS

        pygame.event.clear()  # the real queue: only this test's posts
        manager._post_fps_event()
        posted = pygame.event.get(eventtype=FPSEVENT)
        assert len(posted) == 1
        assert posted[0].fps == pytest.approx(62.5)

    def test_post_fps_event_with_zero_dt(self, mocker):
        """With a zero dt _post_fps_event posts 0 FPS, never pygame's clock.get_fps."""
        manager = SceneManager()
        manager.dt = 0
        manager.clock = mocker.Mock(spec=pygame.time.Clock)
        manager.clock.get_fps.return_value = 60.0

        pygame.event.clear()  # the real queue: only this test's posts
        manager._post_fps_event()
        posted = pygame.event.get(eventtype=FPSEVENT)
        assert len(posted) == 1
        assert posted[0].fps == 0.0
        manager.clock.get_fps.assert_not_called()


class TestSceneManagerUpdateDisplay:
    """Test SceneManager._update_display method."""

    def test_update_display_update_with_rects(self, mocker):
        """Test _update_display with 'update' type and rects."""
        manager = SceneManager()
        manager.update_type = 'update'
        rects = [pygame.Rect(0, 0, 100, 100)]
        manager.active_scene = mocker.Mock()
        manager.active_scene.rects = rects

        # Should not raise
        manager._update_display()

    def test_update_display_update_without_rects(self, mocker):
        """Test _update_display with 'update' type and no rects."""
        manager = SceneManager()
        manager.update_type = 'update'
        manager.active_scene = mocker.Mock()
        manager.active_scene.rects = []

        # Empty rects triggers full display update
        manager._update_display()

    def test_update_display_flip(self, mocker):
        """Test _update_display with 'flip' type."""
        manager = SceneManager()
        manager.update_type = 'flip'
        manager.active_scene = mocker.Mock()

        # Should not raise
        manager._update_display()


class TestSceneManagerLogQuitInfo:
    """Test SceneManager._log_quit_info method."""

    def test_log_quit_info_does_not_raise(self, mocker):
        """Test _log_quit_info runs without error."""
        manager = SceneManager()
        manager.active_scene = mocker.Mock()
        manager.quit_requested = False
        # Should not raise
        manager._log_quit_info()


class TestSceneManagerTerminate:
    """Test SceneManager.terminate method."""

    def test_terminate_calls_switch_to_none(self, mocker):
        """Test terminate switches to None scene."""
        manager = SceneManager()
        manager.switch_to_scene = mocker.Mock()
        manager.terminate()
        manager.switch_to_scene.assert_called_once_with(None)


class TestSceneManagerQuitGameDeeper:
    """Test SceneManager.quit_game method."""

    def test_quit_game_posts_quit_event(self, mocker):
        """Test quit_game posts a QUIT event."""
        manager = SceneManager()
        pygame.event.clear()  # the real queue: only this test's posts
        manager.quit_game()
        assert len(pygame.event.get(eventtype=pygame.QUIT)) == 1

    def test_quit_alias_calls_quit_game(self, mocker):
        """Test quit() is an alias for quit_game."""
        manager = SceneManager()
        pygame.event.clear()  # the real queue: only this test's posts
        manager.quit()
        assert len(pygame.event.get(eventtype=pygame.QUIT)) == 1


class TestSceneManagerOnFpsEventDeeper:
    """Test SceneManager.on_fps_event method."""

    def test_on_fps_event_with_active_scene(self, mocker):
        """Test on_fps_event delegates to active scene."""
        manager = SceneManager()
        scene = mocker.Mock()
        manager.active_scene = scene

        event = mocker.Mock()
        event.fps = 60.0

        manager.on_fps_event(event)
        scene.on_fps_event.assert_called_once_with(event)

    def test_on_fps_event_without_active_scene(self, mocker):
        """Test on_fps_event does nothing without active scene."""
        manager = SceneManager()
        manager.active_scene = None

        event = mocker.Mock()
        event.fps = 60.0

        # Should not raise
        manager.on_fps_event(event)


class TestSceneScreenshotProperty:
    """Test Scene.screenshot property."""

    def test_screenshot_returns_surface(self):
        """Test screenshot returns a pygame Surface."""
        scene = Scene()
        screenshot = scene.screenshot
        assert isinstance(screenshot, pygame.Surface)

    def test_screenshot_has_correct_size(self):
        """Test screenshot has the same size as the screen."""
        scene = Scene()
        screenshot = scene.screenshot
        assert screenshot.get_width() == scene.screen_width
        assert screenshot.get_height() == scene.screen_height


class TestSceneBackgroundPattern:
    """A scene that sets no background shows the default pattern; a pattern can be chosen."""

    def test_a_new_scene_shows_the_active_default_pattern(self):
        """The background surface holds the default pattern, drawn at the screen's size."""
        scene = Scene()

        expected = background_pattern_surface(
            pattern=CANVAS_PATTERN, size=scene.background.get_size()
        )
        assert pygame.image.tobytes(scene.background, 'RGB') == pygame.image.tobytes(
            expected, 'RGB'
        )

    def test_the_default_follows_the_active_default_pattern(self):
        """A scene made after the default changes gets the new default."""
        set_active_default_background_pattern(pattern=BackgroundPattern.CHANNEL_THREE)

        assert Scene().background_pattern is BackgroundPattern.CHANNEL_THREE

    def test_choosing_a_pattern_replaces_a_colour(self):
        """Setting background_pattern draws the pattern and clears background_color."""
        scene = Scene()
        scene.background_color = RED

        scene.background_pattern = BackgroundPattern.CHANNEL_THREE

        assert scene.background_color is None
        assert scene.background_pattern is BackgroundPattern.CHANNEL_THREE
        expected = background_pattern_surface(
            pattern=BackgroundPattern.CHANNEL_THREE, size=scene.background.get_size()
        )
        assert pygame.image.tobytes(scene.background, 'RGB') == pygame.image.tobytes(
            expected, 'RGB'
        )


class TestSceneScreenshot:
    """Scene.screenshot: what the presented frame shows."""

    def test_the_screenshot_of_a_screen_with_per_pixel_alpha_is_opaque(self):
        """Transparent and translucent screen pixels keep their colours, opaque (BUGS.md #142).

        The screenshot shows what the presented frame shows (the display is made opaque
        before each present, glitchygames/opacity.py), never alpha 0 (black on cocoa). The
        screen is a per-pixel-alpha surface built explicitly, so this holds on dummy too.
        """
        scene = Scene()
        screen_with_alpha = pygame.Surface(
            (scene.screen_width, scene.screen_height), pygame.SRCALPHA
        )
        screen_with_alpha.fill((*BLUE, 0))
        screen_with_alpha.set_at((1, 1), (200, 100, 50, 128))
        scene.screen = screen_with_alpha

        screenshot = scene.screenshot

        assert screenshot.get_at((0, 0)) == (*BLUE, OPAQUE)
        assert screenshot.get_at((1, 1)) == (200, 100, 50, OPAQUE)
        if has_per_pixel_alpha(surface=screenshot):
            assert (pygame.surfarray.array_alpha(screenshot) == OPAQUE).all()


class TestSceneBackgroundColor:
    """Test Scene.background_color property."""

    def test_background_color_getter(self):
        """background_color is None by default (a pattern), and the colour once one is set."""
        scene = Scene()
        assert scene.background_color is None
        scene.background_color = BLUE
        assert scene.background_color == (*BLUE, OPAQUE)

    def test_background_color_setter(self):
        """Test background_color setter updates the color."""
        scene = Scene()
        # RGB gets normalized to opaque RGBA
        scene.background_color = (255, 0, 0)
        assert scene.background_color == (255, 0, 0, OPAQUE)

    def test_an_opaque_rgba_background_color_is_kept(self):
        """An RGBA colour with alpha 255 is kept as given."""
        scene = Scene()
        scene.background_color = (*RED, OPAQUE)
        assert scene.background_color == (*RED, OPAQUE)

    @pytest.mark.parametrize('alpha', [0, 128, 254])
    def test_a_translucent_background_color_is_refused(self, alpha):
        """The background is the frame's bottom layer: nothing is under it to show through.

        A translucent colour would be shown opaque by the dummy and x11 drivers and as black
        (alpha 0) or darkened on cocoa, so it is refused and the background is left as it was.
        """
        scene = Scene()
        scene.background_color = BLUE

        with pytest.raises(ValueError, match=f'must be opaque: .* has alpha {alpha},'):
            scene.background_color = (*RED, alpha)

        assert scene.background_color == (*BLUE, OPAQUE)
        assert scene.background.get_at((0, 0)) == (*BLUE, OPAQUE)

    def test_a_background_color_that_is_not_rgb_or_rgba_is_refused(self):
        """A colour of neither three nor four components is refused with its value."""
        scene = Scene()

        with pytest.raises(ValueError, match=r'\(1, 2\)'):
            scene.background_color = (1, 2)

    def test_the_background_copies_opaque_onto_a_surface_with_per_pixel_alpha(self):
        """Rendering onto a transparent per-pixel-alpha surface leaves it opaque (BUGS.md #142).

        Built explicitly so the rule holds on the dummy driver too, whose display has no alpha.
        """
        scene = Scene()
        scene.background_color = BLUE
        target = pygame.Surface(scene.background.get_size(), pygame.SRCALPHA)
        target.fill((0, 0, 0, 0))

        scene.render(target)

        assert target.get_at((0, 0)) == (*BLUE, OPAQUE)
        assert (pygame.surfarray.array_alpha(target) == OPAQUE).all()


class TestSceneUpdate:
    """Test Scene.update() method."""

    def test_update_with_dirty_sprites(self, mocker):
        """Test update calls update on dirty sprites."""
        scene = Scene()
        scene.dirty = 0
        dirty_sprite = RecordingSprite(dirty=1)
        clean_sprite = RecordingSprite()
        scene.all_sprites.add(dirty_sprite, clean_sprite)
        clean_sprite.dirty = 0  # LayeredDirty marks a sprite dirty when it is added

        scene.update()

        # Every sprite updates its nested sprites; only the dirty one is updated
        assert dirty_sprite.nested_update_count == 1
        assert clean_sprite.nested_update_count == 1
        assert dirty_sprite.update_count == 1
        assert clean_sprite.update_count == 0

    def test_update_forces_redraw_when_scene_dirty(self, mocker):
        """Test update forces redraw on all sprites when scene is dirty."""
        scene = Scene()
        scene.dirty = 1
        clean_sprite = RecordingSprite()
        always_dirty_sprite = RecordingSprite()
        scene.all_sprites.add(clean_sprite, always_dirty_sprite)
        # LayeredDirty marks a sprite dirty when it is added
        clean_sprite.dirty = 0
        always_dirty_sprite.dirty = 2

        scene.update()
        # The clean sprite is marked dirty once; an always-dirty sprite stays always dirty
        assert clean_sprite.dirty == 1
        assert always_dirty_sprite.dirty == 2


class TestSceneRender:
    """Test Scene.render() method."""

    def test_render_draws_the_sprites_onto_the_screen(self):
        """render() clears to the background, draws the sprites, and keeps the changed rects."""
        scene = Scene()
        sprite = RecordingSprite(dirty=1)
        sprite.rect.topleft = (40, 30)
        scene.all_sprites.add(sprite)
        screen = pygame.display.get_surface()
        assert screen is not None
        screen.fill(BLUE)

        scene.render(screen)

        # The sprite's pixels on the real display are its color (RGB: the display's pixel
        # format may or may not carry alpha)
        drawn_pixels = pygame.surfarray.pixels3d(screen)[40:48, 30:38]
        assert (drawn_pixels == RED[:3]).all()
        del drawn_pixels  # release the display's pixel lock
        # The changed rects cover the sprite (a group's first draw reports the whole screen)
        assert scene.rects is not None
        assert any(pygame.Rect(rect).contains(sprite.rect) for rect in scene.rects)


class TestSceneOnKeyDownEventDeeper:
    """Test Scene.on_key_down_event with non-quit keys."""

    def test_key_down_q_posts_no_quit(self, mocker):
        """Q's press with no focused sprite posts no QUIT (it quits on release)."""
        scene = Scene()
        pygame.event.clear(eventtype=pygame.QUIT)
        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_down_event(event)
        assert pygame.event.get(eventtype=pygame.QUIT) == []

    def test_key_down_non_quit_key(self, mocker):
        """Test non-quit key does not set quit_requested when no focused sprites."""
        scene = Scene()
        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_down_event(event)


class TestSceneOnKeyUpEventDeeper:
    """Test Scene.on_key_up_event with non-quit keys."""

    def test_key_up_non_quit_key_no_effect(self, mocker):
        """Test non-quit key up has no quit effect."""
        scene = Scene()
        pygame.event.clear()  # the real queue: only this test's posts
        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_up_event(event)
        assert pygame.event.get(eventtype=pygame.QUIT) == []


class TestSceneHandleFocusManagementWithFocusable:
    """Test Scene._handle_focus_management with focusable sprites."""

    def test_handle_focus_management_keeps_focused_when_focusable_clicked(
        self,
        mocker,
    ):
        """Test focus is maintained when clicking on a focusable sprite."""
        scene = Scene()

        focused_sprite = RecordingSprite(is_active=True)
        scene.all_sprites.add(focused_sprite)

        focusable_sprite = mocker.Mock()
        focusable_sprite.focusable = True

        # Click on a focusable sprite - should NOT unfocus existing sprites
        scene._handle_focus_management([focusable_sprite])
        assert focused_sprite.is_active is True
        assert focused_sprite.focus_lost_count == 0


class TestSceneOnMouseButtonDownEventDeeper:
    """Test Scene.on_mouse_button_down_event with sprite collisions."""

    def test_mouse_button_down_logs_collision_info(self, mocker):
        """Test mouse button down logs collision info."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (50, 50)

        # Should not raise even with no sprites
        scene.on_mouse_button_down_event(event)


class TestSceneManagerAllSprites:
    """Test SceneManager.all_sprites property edge cases."""

    def test_all_sprites_with_scene(self, mocker):
        """Test all_sprites returns scene's sprites."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene
        assert manager.all_sprites is scene.all_sprites

    def test_all_sprites_without_scene(self):
        """Test all_sprites returns None without active scene."""
        manager = SceneManager()
        manager.active_scene = None
        assert manager.all_sprites is None


class TestSceneSetup:
    """Test Scene.setup() method."""

    def test_setup_does_not_raise(self):
        """Test setup() can be called without error."""
        scene = Scene()
        scene.setup()  # Base implementation is a no-op


class TestSceneManagerSwitchToScene:
    """Test SceneManager.switch_to_scene full lifecycle."""

    def test_switch_to_scene_tracks_previous(self, mocker):
        """Test switch_to_scene records previous scene."""
        manager = SceneManager()
        first_scene = Scene()
        manager.active_scene = first_scene

        second_scene = Scene()
        second_scene.NAME = 'SecondScene'
        second_scene.VERSION = '2.0'

        # Mock sub-methods to prevent side effects
        manager._game_engine = mocker.Mock()
        manager._game_engine.OPTIONS = {
            'update_type': 'update',
            'fps_log_interval_ms': 1000,
            'target_fps': 60,
        }
        type(manager).OPTIONS = manager._game_engine.OPTIONS
        manager.target_fps = 60

        manager.switch_to_scene(second_scene)

        assert manager.previous_scene is first_scene
        assert manager.active_scene is second_scene

    def test_switch_to_same_scene_does_nothing(self, mocker):
        """Test switch_to_scene with same scene is a no-op."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene
        old_previous = manager.previous_scene

        manager.switch_to_scene(scene)
        # previous_scene should not change
        assert manager.previous_scene is old_previous

    def test_switch_to_none_terminates(self, mocker):
        """Test switch_to_scene with None sets active_scene to None."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene

        manager.switch_to_scene(None)
        assert manager.active_scene is None


class TestSceneManagerCleanupAndSetup:
    """Test SceneManager cleanup and setup helper methods."""

    def test_cleanup_current_scene_calls_cleanup(self, mocker):
        """Test _cleanup_current_scene calls active scene cleanup."""
        manager = SceneManager()
        scene = Scene()
        scene.cleanup = mocker.Mock()
        manager.active_scene = scene

        manager._cleanup_current_scene()
        scene.cleanup.assert_called_once()

    def test_cleanup_current_scene_none(self):
        """Test _cleanup_current_scene does nothing with None scene."""
        manager = SceneManager()
        manager.active_scene = None
        manager._cleanup_current_scene()  # Should not raise

    def test_setup_new_scene_calls_setup(self, mocker):
        """Test _setup_new_scene calls new scene setup."""
        manager = SceneManager()
        scene = Scene()
        scene.setup = mocker.Mock()
        manager._game_engine = mocker.Mock()

        manager._setup_new_scene(scene)
        scene.setup.assert_called_once()
        assert scene.game_engine is manager._game_engine  # type: ignore[unresolved-attribute]

    def test_setup_new_scene_none(self):
        """Test _setup_new_scene does nothing with None scene."""
        manager = SceneManager()
        manager._setup_new_scene(None)  # Should not raise


class TestSceneManagerConfigureActiveScene:
    """Test SceneManager._configure_active_scene and sub-methods."""

    def test_configure_active_scene_sets_caption(self, mocker):
        """Test _configure_active_scene sets display caption."""
        manager = SceneManager()
        scene = Scene()
        scene.NAME = 'TestGame'
        scene.VERSION = '1.0'
        scene.dirty = 0
        scene.background.fill(BLUE)
        manager.active_scene = scene
        manager.target_fps = 60
        screen = pygame.display.get_surface()
        assert screen is not None
        screen.fill(RED)

        pygame.display.set_caption('before')
        manager._configure_active_scene()

        # The real window's title (and its icon title)
        assert pygame.display.get_caption() == ('TestGame v1.0', 'TestGame v1.0')
        # The new scene's background replaced the old frame on the display (RGB: the
        # display's pixel format may or may not carry alpha), and the scene is marked dirty
        screen_pixels = pygame.surfarray.pixels3d(screen)
        assert (screen_pixels == BLUE[:3]).all()
        del screen_pixels  # release the display's pixel lock
        assert scene.dirty == 1
        assert scene.target_fps == 60

    def test_configure_active_scene_none(self):
        """Test _configure_active_scene does nothing with None scene."""
        manager = SceneManager()
        manager.active_scene = None
        manager._configure_active_scene()  # Should not raise

    def test_set_display_caption_name_only(self, mocker):
        """Test _set_display_caption with NAME but no VERSION."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.NAME = 'MyGame'
        scene.VERSION = ''
        manager.active_scene = scene

        pygame.display.set_caption('before')
        manager._set_display_caption()

        assert pygame.display.get_caption() == ('MyGame', 'MyGame')

    def test_configure_scene_fps(self, mocker):
        """Test _configure_scene_fps sets target_fps on scene."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.target_fps = 0
        manager.active_scene = scene
        manager.target_fps = 120

        manager._configure_scene_fps()
        assert scene.target_fps == 120

    def test_log_scene_rendering_info_unlimited_fps(self, mocker):
        """Test _log_scene_rendering_info with unlimited FPS."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.NAME = 'UnlimitedGame'
        scene.target_fps = 0
        manager.active_scene = scene

        # Should not raise
        manager._log_scene_rendering_info()

    def test_log_scene_rendering_info_fixed_fps(self, mocker):
        """Test _log_scene_rendering_info with fixed FPS."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.NAME = 'FixedGame'
        scene.target_fps = 60
        manager.active_scene = scene

        manager._log_scene_rendering_info()

    def test_setup_event_proxies(self, mocker):
        """Test _setup_event_proxies sets proxies list."""
        manager = SceneManager()
        scene = mocker.Mock()
        manager.active_scene = scene

        manager._setup_event_proxies()
        assert len(manager.proxies) == 2
        assert manager.proxies[0] is manager
        assert manager.proxies[1] is scene

    def test_force_scene_redraw(self, mocker):
        """Test _force_scene_redraw marks scene dirty."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.dirty = 0
        manager.active_scene = scene

        manager._force_scene_redraw()
        assert scene.dirty == 1

    def test_apply_scene_fps_is_noop(self, mocker):
        """Test _apply_scene_fps is a no-op (intentionally)."""
        manager = SceneManager()
        scene = mocker.Mock()
        manager.active_scene = scene

        # Should not raise or modify anything
        manager._apply_scene_fps()


class TestSceneManagerLogBlockedEvents:
    """Test SceneManager._log_blocked_events."""

    def test_log_blocked_events_with_scene(self, mocker):
        """Test _log_blocked_events logs for active scene."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.name = 'TestScene'
        manager._log_blocked_events(scene)  # Should not raise

    def test_blocked_events_are_logged_on_one_line(self, mocker):
        """A replay blocks dozens of types: one INFO line names them all, not one line each."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.name = 'TestScene'
        blocked_types = {pygame.KEYDOWN, pygame.MOUSEMOTION}
        info = mocker.patch.object(manager.log, 'info')
        with _only_these_event_types_blocked(blocked_types):
            manager._log_blocked_events(scene)
        # In ALL_EVENTS order
        expected_names = [
            pygame.event.event_name(event_type)
            for event_type in ALL_EVENTS
            if event_type in blocked_types
        ]
        assert len(expected_names) == len(blocked_types)
        (blocked_events_call,) = info.call_args_list
        assert logged_message(blocked_events_call) == (
            f'Scene TestScene blocked events: {", ".join(expected_names)}'
        )

    def test_no_blocked_events_are_logged_as_none(self, mocker):
        manager = SceneManager()
        scene = mocker.Mock()
        scene.name = 'TestScene'
        info = mocker.patch.object(manager.log, 'info')
        with _only_these_event_types_blocked(set()):
            manager._log_blocked_events(scene)
        (blocked_events_call,) = info.call_args_list
        assert logged_message(blocked_events_call) == 'Scene TestScene blocked events: None'

    def test_log_blocked_events_none(self):
        """Test _log_blocked_events with None scene does nothing."""
        manager = SceneManager()
        manager._log_blocked_events(None)  # Should not raise


class TestSceneManagerGameEvents:
    """Test SceneManager game event handling."""

    def test_on_game_event_registered(self, mocker):
        """Test on_game_event calls registered callback."""
        manager = SceneManager()
        manager._game_engine = mocker.Mock()
        callback = mocker.Mock()
        manager._game_engine.registered_events = {42: callback}

        event = mocker.Mock()
        event.subtype = 42

        manager.on_game_event(event)
        callback.assert_called_once_with(event)

    def test_on_game_event_unregistered(self, mocker):
        """Test on_game_event logs error for unregistered event."""
        manager = SceneManager()
        manager._game_engine = mocker.Mock()
        manager._game_engine.registered_events = {}

        event = mocker.Mock()
        event.subtype = 999

        # Should not raise, logs error
        manager.on_game_event(event)

    def test_register_game_event_delegates(self, mocker):
        """Test register_game_event delegates to game engine."""
        manager = SceneManager()
        manager._game_engine = mocker.Mock()

        callback = mocker.Mock()
        manager.register_game_event(42, callback)
        manager._game_engine.register_game_event.assert_called_once_with(
            event_type=42,
            callback=callback,
        )


class TestSceneManagerUpdateScreen:
    """Test SceneManager.update_screen."""

    def test_update_screen_when_none(self, mocker):
        """Test update_screen gets surface when screen is None."""
        manager = SceneManager()
        manager.screen = None

        manager.update_screen()
        assert manager.screen is not None

    def test_update_screen_when_already_set(self, mocker):
        """Test update_screen does nothing when screen exists."""
        manager = SceneManager()
        original_screen = manager.screen

        manager.update_screen()
        assert manager.screen is original_screen


class TestSceneOnKeyDownWithFocusedSprites:
    """Test Scene.on_key_down_event with focused sprites for non-quit keys."""

    def test_key_down_q_with_no_focused_sprite_posts_no_quit(self, mocker):
        """Q's press posts no QUIT: Scene acts on no key press (BUGS.md #203)."""
        scene = Scene()
        pygame.event.clear(eventtype=pygame.QUIT)
        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_down_event(event)
        assert pygame.event.get(eventtype=pygame.QUIT) == []

    def test_key_down_non_quit_with_focused_sprite(self, mocker):
        """Test non-quit key is dispatched to focused sprite."""
        scene = Scene()
        focused_sprite = RecordingSprite(is_active=True)
        scene.all_sprites.add(focused_sprite)

        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_down_event(event)
        assert focused_sprite.key_down_events == [event]

    def test_key_down_non_quit_no_focused_sprites(self, mocker):
        """Test non-quit key with no focused sprites does not quit."""
        scene = Scene()
        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_down_event(event)
        # No quit state on the scene (BUGS.md #203: Scene has no quit_requested)
        assert not hasattr(scene, 'quit_requested')


class TestSceneUpdateWithFilmStrip:
    """Test Scene.update with Film Strip sprite — updated via the normal dirty-sprite path."""

    def test_update_with_dirty_film_strip_sprite(self, mocker):
        """Test dirty Film Strip sprites get updated via the normal dirty-sprite path."""
        scene = Scene()
        scene.dt = 0.016

        film_strip = RecordingSprite(dirty=1, name='Film Strip')

        scene.all_sprites.add(film_strip)
        scene.update()

        # Film strip should be updated via the dirty sprite loop, once
        assert film_strip.update_count == 1


class TestSceneManagerResetSceneTimers:
    """Test SceneManager._reset_scene_timers."""

    def test_reset_scene_timers(self):
        """_reset_scene_timers zeroes the timer and leaves the manager's frame time alone."""
        manager = SceneManager()
        manager.dt = 0.5
        manager.timer = 10.0

        manager._reset_scene_timers()
        assert manager.dt == 0.5
        assert manager.timer == 0


class TestSceneManagerLogSceneSwitch:
    """Test SceneManager._log_scene_switch."""

    def test_log_scene_switch_does_not_raise(self, mocker):
        """Test _log_scene_switch runs without error."""
        manager = SceneManager()
        scene = mocker.Mock()
        manager._log_scene_switch(scene)  # Should not raise


class TestSceneManagerPlayDeeperCoverage:
    """Test SceneManager.play delegates to start."""

    def test_play_calls_start(self, mocker):
        """Test play() delegates to start()."""
        manager = SceneManager()
        manager.start = mocker.Mock()
        manager.play()
        manager.start.assert_called_once()
