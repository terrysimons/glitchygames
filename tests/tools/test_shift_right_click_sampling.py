"""Test right-click colour sampling: shift samples the real screen, plain samples pixel data.

Every test runs on a real BitmapEditorScene on the real display: the film strip, the canvas
and the screen are the editor's own, and a sample is observed in the editor's real sliders.
"""

import pygame
import pytest

from glitchygames import events
from glitchygames.bitmappy.controllers.manager import MultiControllerManager
from glitchygames.bitmappy.editor import BitmapEditorScene
from glitchygames.input.state import InputSnapshot, set_current_input

FRAME_COLOR = (10, 20, 30, 200)
SCREEN_COLOR = (128, 64, 192)


@pytest.fixture
def editor(mocker):
    """Build a real Bitmappy editor on the real display, with a fresh controller manager.

    Returns:
        BitmapEditorScene: The editor, with one animation of one blank 32x32 frame.

    """
    mocker.patch.object(MultiControllerManager, '_instance', None)
    return BitmapEditorScene(options={})


def _hold_keys(*, scancodes=frozenset()):
    """Install this frame's polled input: the given keys held, the mouse idle.

    The autouse ``reset_engine_sources`` fixture (tests/conftest.py) resets it after the test.
    """
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(scancodes),
            modifiers=0,
            mouse_position=(0, 0),
            mouse_buttons=(False, False, False),
            mouse_focused=True,
        ),
    )


def _right_click_up(position):
    """Build a real right-button-up event at a screen position.

    Returns:
        events.HashableEvent: The event.

    """
    return events.HashableEvent(pygame.MOUSEBUTTONUP, pos=position, button=3)


def _slider_color(editor):
    """Read the editor's colour from its four real sliders.

    Returns:
        tuple[int, int, int, int]: Red, green, blue and alpha.

    """
    return (
        editor.red_slider.value,
        editor.green_slider.value,
        editor.blue_slider.value,
        editor.alpha_slider.value,
    )


def _film_strip_and_first_frame_center(editor):
    """Find the editor's film strip sprite and the screen position of its first frame.

    Returns:
        tuple: (FilmStripSprite, animation name, (x, y) screen position of frame 0's center).

    """
    strip_name = next(iter(editor.film_strip_sprites))
    film_strip_sprite = editor.film_strip_sprites[strip_name]
    (animation, _frame_index), frame_layout = next(
        iter(editor.film_strips[strip_name].frame_layouts.items()),
    )
    center = (
        film_strip_sprite.rect.x + frame_layout.centerx,
        film_strip_sprite.rect.y + frame_layout.centery,
    )
    return film_strip_sprite, animation, center


def _paint_first_frame(editor, animation, color):
    """Paint every pixel of the animation's first frame in one colour."""
    frame = editor.canvas.animated_sprite._animations[animation][0]
    width, height = frame.get_size()
    frame.set_pixel_data([color] * (width * height))


class TestShiftRightClickSampling:
    """Test shift-right-click screen sampling against plain right-click pixel sampling."""

    def test_regular_right_click_samples_pixel_data(self, editor):
        """A plain right-click on a film strip frame samples the frame's pixel (RGBA)."""
        film_strip_sprite, animation, frame_center = _film_strip_and_first_frame_center(editor)
        _paint_first_frame(editor, animation, FRAME_COLOR)
        # The screen under the click holds another colour, which must not be sampled
        editor.screen.set_at(frame_center, SCREEN_COLOR)
        _hold_keys()

        result = film_strip_sprite.on_right_mouse_button_up_event(_right_click_up(frame_center))

        assert result, 'Regular right-click should be handled'
        assert _slider_color(editor) == FRAME_COLOR

    def test_shift_right_click_samples_screen(self, editor):
        """A shift-right-click on a film strip frame samples the screen there (RGB, opaque)."""
        film_strip_sprite, animation, frame_center = _film_strip_and_first_frame_center(editor)
        _paint_first_frame(editor, animation, FRAME_COLOR)
        editor.screen.set_at(frame_center, SCREEN_COLOR)
        _hold_keys(scancodes={pygame.KSCAN_LSHIFT})

        result = film_strip_sprite.on_right_mouse_button_up_event(_right_click_up(frame_center))

        assert result, 'Shift-right-click should be handled'
        assert _slider_color(editor) == (*SCREEN_COLOR, 255)

    def test_shift_right_click_samples_screen_rgb_only(self, editor):
        """Sampling the screen takes its RGB and sets the alpha slider to opaque."""
        editor.screen.set_at((100, 100), SCREEN_COLOR)
        editor.alpha_slider.value = 7

        editor._slider_manager.sample_color_from_screen((100, 100))

        assert _slider_color(editor) == (*SCREEN_COLOR, 255)

    def test_regular_right_click_canvas_samples_pixel_data(self, editor):
        """A plain right-click on the canvas samples the canvas pixel there (RGBA)."""
        canvas = editor.canvas
        # The top-left corner of canvas pixel (5, 5)
        click_position = (
            canvas.rect.x + 5 * canvas.pixel_width,
            canvas.rect.y + 5 * canvas.pixel_height,
        )
        canvas.pixels[5 * canvas.pixels_across + 5] = (255, 128, 64, 200)
        editor.screen.set_at(click_position, SCREEN_COLOR)
        _hold_keys()

        editor.on_right_mouse_button_up_event(_right_click_up(click_position))

        assert _slider_color(editor) == (255, 128, 64, 200)

    def test_shift_right_click_canvas_samples_screen(self, editor):
        """A shift-right-click on the canvas samples the screen there, not the pixel data."""
        canvas = editor.canvas
        click_position = (canvas.rect.x + 50, canvas.rect.y + 50)
        canvas.pixels[5 * canvas.pixels_across + 5] = (255, 128, 64, 200)
        editor.screen.set_at(click_position, SCREEN_COLOR)
        _hold_keys(scancodes={pygame.KSCAN_LSHIFT})

        editor.on_right_mouse_button_up_event(_right_click_up(click_position))

        assert _slider_color(editor) == (*SCREEN_COLOR, 255)

    def test_screen_sampling_handles_rgb_format(self, editor):
        """A screen without an alpha channel (24-bit) is sampled the same way."""
        editor.screen = pygame.Surface((800, 600), depth=24)
        editor.screen.set_at((100, 100), SCREEN_COLOR)

        editor._slider_manager.sample_color_from_screen((100, 100))

        assert _slider_color(editor) == (*SCREEN_COLOR, 255)

    def test_screen_sampling_handles_rgba_format(self, editor):
        """A screen with per-pixel alpha is sampled for its RGB."""
        editor.screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        editor.screen.set_at((100, 100), (*SCREEN_COLOR, 128))

        editor._slider_manager.sample_color_from_screen((100, 100))

        assert _slider_color(editor)[:3] == SCREEN_COLOR

    def test_screen_sampling_ignores_alpha_from_screen(self, editor):
        """The screen's own alpha is ignored: the sampled colour is always opaque."""
        editor.screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        editor.screen.set_at((100, 100), (*SCREEN_COLOR, 128))

        editor._slider_manager.sample_color_from_screen((100, 100))

        assert editor.alpha_slider.value == 255

    def test_shift_right_click_outside_bounds_not_handled(self, editor):
        """A shift-right-click outside the film strip is not handled and samples nothing."""
        film_strip_sprite, _animation, _frame_center = _film_strip_and_first_frame_center(editor)
        outside = (film_strip_sprite.rect.x - 10, film_strip_sprite.rect.y - 10)
        color_before = _slider_color(editor)
        _hold_keys(scancodes={pygame.KSCAN_LSHIFT})

        result = film_strip_sprite.on_right_mouse_button_up_event(_right_click_up(outside))

        assert not result, 'Shift-right-click outside bounds should not be handled'
        assert _slider_color(editor) == color_before

    def test_regular_right_click_outside_bounds_not_handled(self, editor):
        """A plain right-click outside the film strip is not handled and samples nothing."""
        film_strip_sprite, _animation, _frame_center = _film_strip_and_first_frame_center(editor)
        outside = (film_strip_sprite.rect.x - 10, film_strip_sprite.rect.y - 10)
        color_before = _slider_color(editor)
        _hold_keys()

        result = film_strip_sprite.on_right_mouse_button_up_event(_right_click_up(outside))

        assert not result, 'Regular right-click outside bounds should not be handled'
        assert _slider_color(editor) == color_before

    def test_shift_right_click_without_parent_scene_handles_gracefully(self, editor):
        """Without a parent scene a shift-right-click is still handled, but samples nothing."""
        film_strip_sprite, _animation, frame_center = _film_strip_and_first_frame_center(editor)
        film_strip_sprite.parent_scene = None
        editor.screen.set_at(frame_center, SCREEN_COLOR)
        color_before = _slider_color(editor)
        _hold_keys(scancodes={pygame.KSCAN_LSHIFT})

        result = film_strip_sprite.on_right_mouse_button_up_event(_right_click_up(frame_center))

        assert result, 'Shift-right-click should be handled even without parent scene'
        assert _slider_color(editor) == color_before
