"""Comprehensive tests for AnimatedCanvasSprite in glitchygames/tools/bitmappy.py.

Targets the AnimatedCanvasSprite class (starts at line 3219) which has ~2100 lines
of testable methods including initialization, frame navigation, panning, pixel
operations, and rendering state management.
"""

from typing import NamedTuple, cast

import pygame
import pytest

from bitmappy.animated_canvas import AnimatedCanvasSprite
from bitmappy.canvas_interfaces import (
    AnimatedCanvasInterface,
    AnimatedCanvasRenderer,
    AnimatedSpriteSerializer,
)
from bitmappy.file_io import FileIOManager
from bitmappy.frame_operations import FrameOperationManager
from bitmappy.pixel_sprite import BitmapPixelSprite
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

# Constants
CANVAS_SIZE = 4
PIXEL_COUNT = 16  # 4x4
PIXEL_WIDTH = 16
PIXEL_HEIGHT = 16
MAGENTA_RGBA = (255, 0, 255, 255)
MAGENTA_RGB = (255, 0, 255)
RED_RGBA = (255, 0, 0, 255)
GREEN_RGBA = (0, 255, 0, 255)
BLUE_RGBA = (0, 0, 255, 255)
BLACK_RGBA = (0, 0, 0, 255)
RED_RGB = (255, 0, 0)


@pytest.fixture
def restore_mouse_cursor():
    """Show the real mouse cursor again after a test that hovers the canvas (it hides it).

    Yields:
        None: Control returns to the test while the cursor may be hidden.

    """
    yield
    pygame.mouse.set_visible(True)


class CanvasConfig(NamedTuple):
    """Configuration for creating an AnimatedCanvasSprite in tests."""

    pixels_across: int = CANVAS_SIZE
    pixels_tall: int = CANVAS_SIZE
    pixel_width: int = PIXEL_WIDTH
    pixel_height: int = PIXEL_HEIGHT
    animation_name: str = 'idle'
    frame_count: int = 3


DEFAULT_CANVAS_CONFIG = CanvasConfig()


def _make_animated_sprite_with_frames(animation_name='idle', frame_count=3, frame_size=CANVAS_SIZE):
    """Create an AnimatedSprite with the given number of frames.

    Args:
        animation_name: Name of the animation to create.
        frame_count: Number of frames to add.
        frame_size: Width and height of each frame.

    Returns:
        AnimatedSprite with frames added and animation set.

    """
    animated_sprite = AnimatedSprite()
    frames = []
    pixel_count = frame_size * frame_size
    for frame_index in range(frame_count):
        surface = pygame.Surface((frame_size, frame_size))
        frame = SpriteFrame(surface)
        # Each frame gets a slightly different color to distinguish them
        color = (frame_index * 50, frame_index * 30, frame_index * 20, 255)
        frame_pixels = cast('list[tuple[int, ...]]', [color] * pixel_count)
        frame.set_pixel_data(frame_pixels)
        frames.append(frame)
    animated_sprite.add_animation(animation_name, frames)
    animated_sprite.set_animation(animation_name)
    return animated_sprite


def _make_canvas(mocker, config=DEFAULT_CANVAS_CONFIG):
    """Create an AnimatedCanvasSprite with minimal mocked dependencies.

    Args:
        mocker: The pytest-mock mocker fixture.
        config: Canvas configuration parameters.

    Returns:
        A tuple of (AnimatedCanvasSprite, AnimatedSprite).

    """
    animated_sprite = _make_animated_sprite_with_frames(
        animation_name=config.animation_name,
        frame_count=config.frame_count,
        frame_size=config.pixels_across,
    )

    canvas = AnimatedCanvasSprite(
        animated_sprite=animated_sprite,
        name='Test Canvas',
        x=0,
        y=0,
        pixels_across=config.pixels_across,
        pixels_tall=config.pixels_tall,
        pixel_width=config.pixel_width,
        pixel_height=config.pixel_height,
    )

    return canvas, animated_sprite


class TestInitializeDimensions:
    """Test _initialize_dimensions pure math method."""

    def test_initialize_dimensions_basic(self, mocker):
        """Test basic dimension initialization returns correct width and height."""
        canvas, _ = _make_canvas(
            mocker,
            config=CanvasConfig(
                pixels_across=8,
                pixels_tall=8,
                pixel_width=10,
                pixel_height=10,
            ),
        )
        assert canvas.pixels_across == 8
        assert canvas.pixels_tall == 8
        assert canvas.pixel_width == 10
        assert canvas.pixel_height == 10

    def test_initialize_dimensions_rectangular(self, mocker):
        """Test dimensions for a non-square canvas."""
        canvas, _ = _make_canvas(
            mocker,
            config=CanvasConfig(
                pixels_across=16,
                pixels_tall=8,
                pixel_width=4,
                pixel_height=8,
            ),
        )
        assert canvas.pixels_across == 16
        assert canvas.pixels_tall == 8
        assert canvas.pixel_width == 4
        assert canvas.pixel_height == 8

    def test_initialize_dimensions_computes_canvas_size(self, mocker):
        """Test that canvas surface dimensions are pixels_across * pixel_width."""
        canvas, _ = _make_canvas(
            mocker,
            config=CanvasConfig(
                pixels_across=4,
                pixels_tall=4,
                pixel_width=16,
                pixel_height=16,
            ),
        )
        # The image should be pixels_across * pixel_width by pixels_tall * pixel_height
        expected_width = 4 * 16
        expected_height = 4 * 16
        assert canvas.image.get_width() == expected_width
        assert canvas.image.get_height() == expected_height

    def test_initialize_dimensions_small_pixel_size(self, mocker):
        """Test dimensions with pixel size of 1."""
        canvas, _ = _make_canvas(
            mocker,
            config=CanvasConfig(
                pixels_across=32,
                pixels_tall=32,
                pixel_width=1,
                pixel_height=1,
            ),
        )
        assert canvas.pixel_width == 1
        assert canvas.pixel_height == 1


class TestInitializePixelArrays:
    """Test _initialize_pixel_arrays method."""

    def test_pixel_array_length(self, mocker):
        """Test pixel array has correct length for canvas size."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(pixels_across=4, pixels_tall=4))
        # Pixels are updated from animated sprite frame data during init,
        # but dirty_pixels should match the expected count
        assert len(canvas.dirty_pixels) == PIXEL_COUNT

    def test_dirty_pixels_initialized_true(self, mocker):
        """Test all dirty pixels start as True after initialization."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(pixels_across=4, pixels_tall=4))
        assert all(canvas.dirty_pixels)

    def test_background_color_set(self, mocker):
        """Test background color is set to gray."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(pixels_across=4, pixels_tall=4))
        assert canvas.background_color == (128, 128, 128)

    def test_active_color_set(self, mocker):
        """Test active color is set to black RGBA."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(pixels_across=4, pixels_tall=4))
        assert canvas.active_color == BLACK_RGBA


class TestUpdateBorderThickness:
    """Test _update_border_thickness method."""

    def test_normal_pixel_size_has_border(self, mocker):
        """Test border thickness is 1 for normal pixel sizes."""
        canvas, _ = _make_canvas(
            mocker,
            config=CanvasConfig(
                pixels_across=4,
                pixels_tall=4,
                pixel_width=16,
                pixel_height=16,
            ),
        )
        assert canvas.border_thickness == 1

    def test_small_pixel_size_disables_border(self, mocker):
        """Test border is disabled for pixel size <= 2."""
        canvas, _ = _make_canvas(
            mocker,
            config=CanvasConfig(
                pixels_across=4,
                pixels_tall=4,
                pixel_width=2,
                pixel_height=2,
            ),
        )
        assert canvas.border_thickness == 0

    def test_large_sprite_disables_border(self, mocker):
        """Test border is disabled for sprites >= 128 pixels across."""
        canvas, _ = _make_canvas(
            mocker,
            config=CanvasConfig(
                pixels_across=128,
                pixels_tall=128,
                pixel_width=4,
                pixel_height=4,
                frame_count=1,
            ),
        )
        assert canvas.border_thickness == 0

    def test_border_thickness_change_clears_pixel_cache(self, mocker):
        """Test that changing border thickness clears BitmapPixelSprite.PIXEL_CACHE."""
        # Set up initial cache entry
        BitmapPixelSprite.PIXEL_CACHE['test_key'] = 'test_value'  # type: ignore[invalid-assignment]

        canvas, _ = _make_canvas(
            mocker,
            config=CanvasConfig(
                pixels_across=4,
                pixels_tall=4,
                pixel_width=16,
                pixel_height=16,
            ),
        )
        # Manually trigger a border thickness change
        canvas.pixel_width = 2
        canvas.pixel_height = 2
        canvas._update_border_thickness()
        # Cache should be cleared on thickness change
        assert 'test_key' not in BitmapPixelSprite.PIXEL_CACHE


class TestSetFrame:
    """Test set_frame method."""

    def test_set_frame_updates_current_frame(self, mocker):
        """Test set_frame changes current_frame."""
        canvas, _ = _make_canvas(mocker)
        canvas.set_frame(2)
        assert canvas.current_frame == 2

    def test_set_frame_marks_manual_selection(self, mocker):
        """Test set_frame sets _manual_frame_selected flag."""
        canvas, _ = _make_canvas(mocker)
        canvas.set_frame(1)
        # When animation was not playing, should stay True
        assert canvas._manual_frame_selected is True

    def test_set_frame_pauses_animation(self, mocker):
        """Test set_frame pauses the animated sprite."""
        canvas, animated_sprite = _make_canvas(mocker)
        animated_sprite.play()
        assert animated_sprite.is_playing is True
        canvas.set_frame(1)
        # After set_frame, animation should be restarted since it was playing
        assert animated_sprite.is_playing is True

    def test_set_frame_out_of_range_does_nothing(self, mocker):
        """Test set_frame with invalid index does not change frame."""
        canvas, _ = _make_canvas(mocker)
        original_frame = canvas.current_frame
        canvas.set_frame(99)  # Out of range
        assert canvas.current_frame == original_frame

    def test_set_frame_negative_index_does_nothing(self, mocker):
        """Test set_frame with negative index does not change frame."""
        canvas, _ = _make_canvas(mocker)
        original_frame = canvas.current_frame
        canvas.set_frame(-1)  # Negative
        assert canvas.current_frame == original_frame

    def test_set_frame_marks_dirty(self, mocker):
        """Test set_frame marks canvas as dirty."""
        canvas, _ = _make_canvas(mocker)
        canvas.dirty = 0
        canvas.set_frame(1)
        assert canvas.dirty == 1

    def test_set_frame_updates_canvas_interface(self, mocker):
        """Test set_frame updates the canvas interface frame."""
        canvas, _ = _make_canvas(mocker)
        canvas.set_frame(2)
        _animation_name, frame_index = canvas.canvas_interface.get_current_frame()
        assert frame_index == 2


class TestNextFrame:
    """Test next_frame method."""

    def test_next_frame_increments(self, mocker):
        """Test next_frame moves to the next frame."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(frame_count=3))
        canvas.current_frame = 0
        canvas.next_frame()
        assert canvas.current_frame == 1

    def test_next_frame_wraps_around(self, mocker):
        """Test next_frame wraps to frame 0 at the end."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(frame_count=3))
        canvas.current_frame = 2
        canvas.next_frame()
        assert canvas.current_frame == 0


class TestPreviousFrame:
    """Test previous_frame method."""

    def test_previous_frame_decrements(self, mocker):
        """Test previous_frame moves to the previous frame."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(frame_count=3))
        canvas.current_frame = 2
        canvas.previous_frame()
        assert canvas.current_frame == 1

    def test_previous_frame_wraps_around(self, mocker):
        """Test previous_frame wraps to last frame from frame 0."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(frame_count=3))
        canvas.current_frame = 0
        canvas.previous_frame()
        assert canvas.current_frame == 2


class TestNextAnimation:
    """Test next_animation method."""

    def test_next_animation_cycles(self, mocker):
        """Test next_animation moves to the next animation."""
        canvas, animated_sprite = _make_canvas(mocker, config=CanvasConfig(animation_name='idle'))
        # Add a second animation
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        red_rgba_pixels = cast('list[tuple[int, ...]]', [RED_RGBA] * PIXEL_COUNT)
        frame.set_pixel_data(red_rgba_pixels)
        animated_sprite.add_animation('walk', [frame])

        canvas.current_animation = 'idle'
        canvas.next_animation()
        assert canvas.current_animation == 'walk'

    def test_next_animation_wraps_around(self, mocker):
        """Test next_animation wraps from last to first animation."""
        canvas, animated_sprite = _make_canvas(mocker, config=CanvasConfig(animation_name='idle'))
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        red_rgba_pixels = cast('list[tuple[int, ...]]', [RED_RGBA] * PIXEL_COUNT)
        frame.set_pixel_data(red_rgba_pixels)
        animated_sprite.add_animation('walk', [frame])

        canvas.current_animation = 'walk'
        canvas.next_animation()
        assert canvas.current_animation == 'idle'

    def test_next_animation_preserves_frame(self, mocker):
        """Test next_animation preserves frame index when within bounds."""
        canvas, animated_sprite = _make_canvas(
            mocker,
            config=CanvasConfig(animation_name='idle', frame_count=3),
        )
        # Add second animation with 3 frames
        frames = []
        for _ in range(3):
            surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
            frame = SpriteFrame(surface)
            red_rgba_pixels = cast('list[tuple[int, ...]]', [RED_RGBA] * PIXEL_COUNT)
            frame.set_pixel_data(red_rgba_pixels)
            frames.append(frame)
        animated_sprite.add_animation('walk', frames)

        canvas.current_frame = 2
        canvas.next_animation()
        assert canvas.current_frame == 2

    def test_next_animation_clamps_frame_to_max(self, mocker):
        """Test next_animation clamps frame index when target has fewer frames."""
        canvas, animated_sprite = _make_canvas(
            mocker,
            config=CanvasConfig(animation_name='idle', frame_count=5),
        )
        # Add a second animation with only 2 frames
        frames = []
        for _ in range(2):
            surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
            frame = SpriteFrame(surface)
            red_rgba_pixels = cast('list[tuple[int, ...]]', [RED_RGBA] * PIXEL_COUNT)
            frame.set_pixel_data(red_rgba_pixels)
            frames.append(frame)
        animated_sprite.add_animation('walk', frames)

        canvas.current_frame = 4  # Frame 4 doesn't exist in 'walk'
        canvas.next_animation()
        assert canvas.current_frame == 1  # Should clamp to max_frame (len-1)


class TestPreviousAnimation:
    """Test previous_animation method."""

    def test_previous_animation_cycles(self, mocker):
        """Test previous_animation moves to the previous animation."""
        canvas, animated_sprite = _make_canvas(mocker, config=CanvasConfig(animation_name='idle'))
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        red_rgba_pixels = cast('list[tuple[int, ...]]', [RED_RGBA] * PIXEL_COUNT)
        frame.set_pixel_data(red_rgba_pixels)
        animated_sprite.add_animation('walk', [frame])

        canvas.current_animation = 'walk'
        canvas.previous_animation()
        assert canvas.current_animation == 'idle'

    def test_previous_animation_wraps_around(self, mocker):
        """Test previous_animation wraps from first to last animation."""
        canvas, animated_sprite = _make_canvas(mocker, config=CanvasConfig(animation_name='idle'))
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        red_rgba_pixels = cast('list[tuple[int, ...]]', [RED_RGBA] * PIXEL_COUNT)
        frame.set_pixel_data(red_rgba_pixels)
        animated_sprite.add_animation('walk', [frame])

        canvas.current_animation = 'idle'
        canvas.previous_animation()
        assert canvas.current_animation == 'walk'


class TestShouldTrackFrameSelection:
    """Test _should_track_frame_selection method."""

    def test_returns_false_without_parent_scene(self, mocker):
        """Test returns False when no parent_scene."""
        canvas, _ = _make_canvas(mocker)
        canvas.parent_scene = None
        assert canvas._should_track_frame_selection() is False

    def test_returns_false_without_undo_redo_manager(self, mocker):
        """Test returns False when parent has no undo_redo_manager."""
        canvas, _ = _make_canvas(mocker)
        parent = mocker.Mock(spec=[])
        canvas.parent_scene = parent
        assert canvas._should_track_frame_selection() is False

    def test_returns_false_when_applying_undo_redo(self, mocker):
        """Test returns False when applying_undo_redo is True."""
        canvas, _ = _make_canvas(mocker)
        parent = mocker.Mock()
        parent.undo_redo_manager = mocker.Mock()
        parent.applying_undo_redo = True
        parent._creating_frame = False
        parent._creating_animation = False
        canvas.parent_scene = parent
        assert canvas._should_track_frame_selection() is False

    def test_returns_false_when_creating_frame(self, mocker):
        """Test returns False when _creating_frame is True."""
        canvas, _ = _make_canvas(mocker)
        parent = mocker.Mock()
        parent.undo_redo_manager = mocker.Mock()
        parent.applying_undo_redo = False
        parent._creating_frame = True
        parent._creating_animation = False
        canvas.parent_scene = parent
        assert canvas._should_track_frame_selection() is False

    def test_returns_false_when_creating_animation(self, mocker):
        """Test returns False when _creating_animation is True."""
        canvas, _ = _make_canvas(mocker)
        parent = mocker.Mock()
        parent.undo_redo_manager = mocker.Mock()
        parent.applying_undo_redo = False
        parent._creating_frame = False
        parent._creating_animation = True
        canvas.parent_scene = parent
        assert canvas._should_track_frame_selection() is False

    def test_returns_true_when_all_conditions_met(self, mocker):
        """Test returns True when parent has undo manager and no flags set."""
        canvas, _ = _make_canvas(mocker)
        parent = mocker.Mock()
        parent.undo_redo_manager = mocker.Mock()
        parent.applying_undo_redo = False
        parent._creating_frame = False
        parent._creating_animation = False
        canvas.parent_scene = parent
        assert canvas._should_track_frame_selection() is True


class TestGetCurrentFramePixels:
    """Test _get_current_frame_pixels method."""

    def test_returns_rgba_pixels_from_frame(self, mocker):
        """Test returns RGBA pixel data from current frame."""
        canvas, _ = _make_canvas(mocker)
        pixels = canvas._get_current_frame_pixels()
        assert len(pixels) == PIXEL_COUNT
        # All pixels should be RGBA (4 components)
        for pixel in pixels:
            assert len(pixel) == 4

    def test_converts_rgb_to_rgba(self, mocker):
        """Test RGB pixels are converted to RGBA with full opacity."""
        canvas, animated_sprite = _make_canvas(mocker, config=CanvasConfig(frame_count=1))
        # Set frame pixels as RGB
        frame = animated_sprite._animations['idle'][0]
        red_rgb_pixels = cast('list[tuple[int, ...]]', [RED_RGB] * PIXEL_COUNT)
        frame.set_pixel_data(red_rgb_pixels)
        canvas.current_frame = 0

        pixels = canvas._get_current_frame_pixels()
        for pixel in pixels:
            assert len(pixel) == 4
            assert pixel[3] == 255  # Full opacity

    def test_fallback_to_canvas_pixels(self, mocker):
        """Test falls back to canvas pixels when no animated sprite data."""
        canvas, _ = _make_canvas(mocker)
        # Remove animations to trigger fallback
        canvas.animated_sprite._animations = {}
        canvas.pixels = [BLUE_RGBA] * PIXEL_COUNT

        pixels = canvas._get_current_frame_pixels()
        assert len(pixels) == PIXEL_COUNT

    def test_returns_correct_frame_data(self, mocker):
        """Test returns data from the correct frame index."""
        canvas, animated_sprite = _make_canvas(mocker, config=CanvasConfig(frame_count=3))
        # Set frame 1 with a distinct color
        frame = animated_sprite._animations['idle'][1]
        green_rgba_pixels = cast('list[tuple[int, ...]]', [GREEN_RGBA] * PIXEL_COUNT)
        frame.set_pixel_data(green_rgba_pixels)

        canvas.current_frame = 1
        pixels = canvas._get_current_frame_pixels()
        assert pixels[0] == GREEN_RGBA


def _paint_frame_pixel(animated_sprite, *, frame_index, pixel_index, color):
    """Set one pixel of a frame of the 'idle' animation."""
    frame = animated_sprite._animations['idle'][frame_index]
    frame_pixels = list(frame.get_pixel_data())
    frame_pixels[pixel_index] = color
    frame.set_pixel_data(frame_pixels)


def _rgb_at(surface, x, y):
    """Read the RGB colour of one surface pixel, ignoring alpha and the pixel format.

    Returns:
        tuple[int, int, int]: The red, green and blue components.

    """
    return tuple(surface.get_at((x, y)))[:3]


FRAME_ZERO_RGB = (0, 0, 0)  # _make_animated_sprite_with_frames colours frame 0 black


class TestForceRedraw:
    """Test force_redraw method."""

    def test_force_redraw_updates_image(self, mocker):
        """force_redraw draws the current frame's pixels into the canvas image."""
        canvas, animated_sprite = _make_canvas(mocker)
        _paint_frame_pixel(animated_sprite, frame_index=0, pixel_index=0, color=RED_RGBA)

        canvas.force_redraw()

        # 16x16 cells: pixel 0 is red, pixel 1 keeps frame 0's black, cell borders are grey
        assert canvas.image.get_size() == (CANVAS_SIZE * PIXEL_WIDTH, CANVAS_SIZE * PIXEL_HEIGHT)
        assert _rgb_at(canvas.image, 8, 8) == RED_RGB
        assert _rgb_at(canvas.image, 24, 8) == FRAME_ZERO_RGB
        assert _rgb_at(canvas.image, 0, 0) == (64, 64, 64)

    def test_force_redraw_uses_renderer(self, mocker):
        """force_redraw replaces the canvas image with the surface its renderer draws."""
        canvas, _ = _make_canvas(mocker)
        canvas.image = pygame.Surface((1, 1))

        canvas.force_redraw()

        assert canvas.image.get_size() == (CANVAS_SIZE * PIXEL_WIDTH, CANVAS_SIZE * PIXEL_HEIGHT)
        assert _rgb_at(canvas.image, 8, 8) == FRAME_ZERO_RGB

    def test_force_redraw_shows_the_current_frame(self, mocker):
        """After selecting another frame, force_redraw draws that frame's colours."""
        canvas, _ = _make_canvas(mocker)
        canvas.show_frame('idle', 1)

        canvas.force_redraw()

        # _make_animated_sprite_with_frames colours frame 1 (50, 30, 20)
        assert _rgb_at(canvas.image, 8, 8) == (50, 30, 20)


class TestUpdate:
    """Test update method."""

    def test_update_redraws_when_dirty(self, mocker):
        """A dirty canvas redraws on update, so a changed frame pixel shows."""
        canvas, animated_sprite = _make_canvas(mocker)
        _paint_frame_pixel(animated_sprite, frame_index=0, pixel_index=5, color=RED_RGBA)
        canvas.dirty = 1

        canvas.update()

        # Pixel 5 is cell (1, 1): x/y 16..31
        assert _rgb_at(canvas.image, 24, 24) == RED_RGB

    def test_update_clears_dirty_flag(self, mocker):
        """Test update clears dirty flag after redraw."""
        canvas, _ = _make_canvas(mocker)
        canvas.dirty = 1
        canvas.update()
        assert canvas.dirty == 0

    def test_update_does_nothing_when_clean(self, mocker):
        """A clean canvas keeps its image on update, even when the frame changed."""
        canvas, animated_sprite = _make_canvas(mocker)
        canvas.dirty = 1
        canvas.update()
        image_before = canvas.image
        _paint_frame_pixel(animated_sprite, frame_index=0, pixel_index=5, color=RED_RGBA)
        canvas.dirty = 0

        canvas.update()

        assert canvas.image is image_before
        assert _rgb_at(canvas.image, 24, 24) == FRAME_ZERO_RGB


class TestShowFrame:
    """Test show_frame method."""

    def test_show_frame_updates_current_animation(self, mocker):
        """Test show_frame sets current_animation."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(animation_name='idle', frame_count=3))
        canvas.show_frame('idle', 2)
        assert canvas.current_animation == 'idle'
        assert canvas.current_frame == 2

    def test_show_frame_marks_dirty(self, mocker):
        """Test show_frame marks canvas as dirty."""
        canvas, _ = _make_canvas(mocker)
        canvas.dirty = 0
        canvas.show_frame('idle', 1)
        assert canvas.dirty == 1

    def test_show_frame_invalid_animation_does_nothing(self, mocker):
        """Test show_frame with invalid animation name preserves state."""
        canvas, _ = _make_canvas(mocker)
        original_animation = canvas.current_animation
        original_frame = canvas.current_frame
        canvas.show_frame('nonexistent', 0)
        assert canvas.current_animation == original_animation
        assert canvas.current_frame == original_frame


class TestHandleKeyboardEvent:
    """Test handle_keyboard_event method."""

    def test_left_arrow_calls_previous_frame(self, mocker):
        """Test LEFT arrow key calls previous_frame."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(frame_count=3))
        canvas.current_frame = 1
        canvas.handle_keyboard_event(pygame.K_LEFT)
        assert canvas.current_frame == 0

    def test_right_arrow_calls_next_frame(self, mocker):
        """Test RIGHT arrow key calls next_frame."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(frame_count=3))
        canvas.current_frame = 0
        canvas.handle_keyboard_event(pygame.K_RIGHT)
        assert canvas.current_frame == 1

    def test_number_key_sets_frame(self, mocker):
        """Test number key sets frame directly."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(frame_count=3))
        canvas.handle_keyboard_event(pygame.K_2)
        assert canvas.current_frame == 2

    def test_space_toggles_play_pause(self, mocker):
        """Test SPACE key toggles play/pause."""
        canvas, animated_sprite = _make_canvas(mocker)
        animated_sprite._is_playing = False
        canvas.handle_keyboard_event(pygame.K_SPACE)
        assert animated_sprite.is_playing is True

    def test_space_pauses_playing_animation(self, mocker):
        """Test SPACE key pauses a playing animation."""
        canvas, animated_sprite = _make_canvas(mocker)
        animated_sprite.play()
        assert animated_sprite.is_playing is True
        canvas.handle_keyboard_event(pygame.K_SPACE)
        assert animated_sprite.is_playing is False


class TestCopyPasteFrame:
    """Test copy_current_frame and paste_to_current_frame methods."""

    def test_copy_stores_pixel_data(self, mocker):
        """Test copy_current_frame stores pixel data in clipboard."""
        canvas, animated_sprite = _make_canvas(mocker, config=CanvasConfig(frame_count=1))
        frame = animated_sprite._animations['idle'][0]
        red_rgba_pixels = cast('list[tuple[int, ...]]', [RED_RGBA] * PIXEL_COUNT)
        frame.set_pixel_data(red_rgba_pixels)

        canvas.copy_current_frame()
        assert hasattr(canvas, '_clipboard')
        assert len(canvas._clipboard) == PIXEL_COUNT

    def test_paste_applies_clipboard_data(self, mocker):
        """Test paste_to_current_frame applies clipboard to current frame."""
        canvas, animated_sprite = _make_canvas(mocker, config=CanvasConfig(frame_count=2))
        # Set frame 0 to red
        frame_0 = animated_sprite._animations['idle'][0]
        frame_0_pixels = cast('list[tuple[int, ...]]', [RED_RGBA] * PIXEL_COUNT)
        frame_0.set_pixel_data(frame_0_pixels)

        # Copy frame 0
        canvas.current_frame = 0
        canvas.copy_current_frame()

        # Paste to frame 1
        canvas.current_frame = 1
        canvas.paste_to_current_frame()

        frame_1 = animated_sprite._animations['idle'][1]
        pasted_pixels = frame_1.get_pixel_data()
        assert pasted_pixels[0] == RED_RGBA

    def test_paste_without_clipboard_does_nothing(self, mocker):
        """Test paste without prior copy does not crash."""
        canvas, _ = _make_canvas(mocker)
        # No clipboard set - should not raise
        canvas.paste_to_current_frame()


class TestIsSingleFrameAnimation:
    """Test _is_single_frame_animation method."""

    def test_single_frame_returns_true(self, mocker):
        """Test returns True for single animation with single frame."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(frame_count=1))
        assert canvas._is_single_frame_animation() is True

    def test_multiple_frames_returns_false(self, mocker):
        """Test returns False for animation with multiple frames."""
        canvas, _ = _make_canvas(mocker, config=CanvasConfig(frame_count=3))
        assert canvas._is_single_frame_animation() is False

    def test_multiple_animations_returns_false(self, mocker):
        """Test returns False when there are multiple animations."""
        canvas, animated_sprite = _make_canvas(mocker, config=CanvasConfig(frame_count=1))
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        red_rgba_pixels = cast('list[tuple[int, ...]]', [RED_RGBA] * PIXEL_COUNT)
        frame.set_pixel_data(red_rgba_pixels)
        animated_sprite.add_animation('walk', [frame])
        assert canvas._is_single_frame_animation() is False

    def test_no_animated_sprite_returns_false(self, mocker):
        """Test returns False when no animated sprite."""
        canvas, _ = _make_canvas(mocker)
        canvas.animated_sprite = None
        assert canvas._is_single_frame_animation() is False


class TestGetCanvasAccessors:
    """Test get_canvas_interface, get_sprite_serializer, get_canvas_renderer."""

    def test_get_canvas_interface(self, mocker):
        """Test get_canvas_interface returns AnimatedCanvasInterface."""
        canvas, _ = _make_canvas(mocker)
        interface = canvas.get_canvas_interface()
        assert isinstance(interface, AnimatedCanvasInterface)

    def test_get_sprite_serializer(self, mocker):
        """Test get_sprite_serializer returns AnimatedSpriteSerializer."""
        canvas, _ = _make_canvas(mocker)
        serializer = canvas.get_sprite_serializer()
        assert isinstance(serializer, AnimatedSpriteSerializer)

    def test_get_canvas_renderer(self, mocker):
        """Test get_canvas_renderer returns AnimatedCanvasRenderer."""
        canvas, _ = _make_canvas(mocker)
        renderer = canvas.get_canvas_renderer()
        assert isinstance(renderer, AnimatedCanvasRenderer)


class TestOnPixelUpdateEvent:
    """Test on_pixel_update_event method."""

    def test_pixel_update_modifies_pixel(self, mocker):
        """Test on_pixel_update_event updates the pixel at the given index."""
        canvas, _ = _make_canvas(mocker)
        event = mocker.Mock()
        trigger = mocker.Mock()
        trigger.pixel_number = 5
        trigger.pixel_color = RED_RGBA

        canvas.on_pixel_update_event(event, trigger)
        assert canvas.pixels[5] == RED_RGBA
        assert canvas.dirty_pixels[5] is True
        assert canvas.dirty == 1

    def test_pixel_update_without_pixel_number_does_nothing(self, mocker):
        """Test on_pixel_update_event ignores trigger without pixel_number."""
        canvas, _ = _make_canvas(mocker)
        event = mocker.Mock()
        trigger = mocker.Mock(spec=[])  # No pixel_number attribute

        original_pixels = canvas.pixels.copy()
        canvas.on_pixel_update_event(event, trigger)
        assert canvas.pixels == original_pixels


class TestUpdateAnimation:
    """Test update_animation method."""

    def test_update_animation_delegates_to_sprite(self, mocker):
        """Test update_animation calls animated_sprite.update with dt."""
        canvas, animated_sprite = _make_canvas(mocker)
        mocker.patch.object(animated_sprite, 'update')
        canvas.update_animation(0.016)
        animated_sprite.update.assert_called_once_with(0.016)


class TestClearSurfaceCache:
    """Test _clear_surface_cache method."""

    def test_clears_matching_cache_key(self, mocker):
        """Test _clear_surface_cache removes the current frame's cache entry."""
        canvas, animated_sprite = _make_canvas(mocker)
        cache_key = f'{canvas.current_animation}_{canvas.current_frame}'
        animated_sprite._surface_cache[cache_key] = pygame.Surface((4, 4))
        canvas._clear_surface_cache()
        assert cache_key not in animated_sprite._surface_cache

    def test_does_not_clear_other_cache_keys(self, mocker):
        """Test _clear_surface_cache preserves other cache entries."""
        canvas, animated_sprite = _make_canvas(mocker)
        animated_sprite._surface_cache['other_key'] = pygame.Surface((4, 4))
        canvas._clear_surface_cache()
        assert 'other_key' in animated_sprite._surface_cache


class TestCleanupDragState:
    """Test _cleanup_drag_state method."""

    def test_cleanup_clears_drag_active(self, mocker):
        """Test _cleanup_drag_state sets _drag_active to False."""
        canvas, _ = _make_canvas(mocker)
        canvas._drag_active = True
        canvas._drag_pixels = {(0, 0): (0, 0, RED_RGBA, BLUE_RGBA)}
        canvas._cleanup_drag_state()
        assert canvas._drag_active is False

    def test_cleanup_clears_drag_pixels(self, mocker):
        """Test _cleanup_drag_state clears _drag_pixels dict."""
        canvas, _ = _make_canvas(mocker)
        canvas._drag_active = True
        canvas._drag_pixels = {(0, 0): (0, 0, RED_RGBA, BLUE_RGBA)}
        canvas._cleanup_drag_state()
        assert canvas._drag_pixels == {}

    def test_cleanup_removes_redraw_counter(self, mocker):
        """Test _cleanup_drag_state removes _drag_redraw_counter."""
        canvas, _ = _make_canvas(mocker)
        canvas._drag_active = True
        canvas._drag_pixels = {}
        canvas._drag_redraw_counter = 5
        canvas._cleanup_drag_state()
        assert not hasattr(canvas, '_drag_redraw_counter')


class TestGetCanvasSurface:
    """Test get_canvas_surface method."""

    def test_returns_surface_of_correct_size(self, mocker):
        """Test get_canvas_surface returns surface with canvas dimensions."""
        canvas, _ = _make_canvas(mocker)
        surface = canvas.get_canvas_surface()
        assert surface.get_width() == CANVAS_SIZE
        assert surface.get_height() == CANVAS_SIZE

    def test_magenta_pixels_produce_surface(self, mocker):
        """Test get_canvas_surface handles magenta pixels without error."""
        canvas, _ = _make_canvas(mocker)
        canvas.pixels = [MAGENTA_RGBA] * PIXEL_COUNT
        canvas.pixels[1] = RED_RGBA
        surface = canvas.get_canvas_surface()
        assert surface.get_width() == CANVAS_SIZE
        # Magenta becomes fully transparent for the film strip; other colours stay
        assert surface.get_at((0, 0)).a == 0
        assert tuple(surface.get_at((1, 0))) == RED_RGBA


class TestHoverTracking:
    """Test hover-related initialization."""

    def test_hovered_pixel_starts_none(self, mocker):
        """Test hovered_pixel is initialized to None."""
        canvas, _ = _make_canvas(mocker)
        assert canvas.hovered_pixel is None

    def test_is_hovered_starts_false(self, mocker):
        """Test is_hovered is initialized to False."""
        canvas, _ = _make_canvas(mocker)
        assert canvas.is_hovered is False


class TestBuildSurfaceFromCanvasPixels:
    """Test _build_surface_from_canvas_pixels method."""

    def test_builds_surface_with_correct_dimensions(self, mocker):
        """Test surface has correct dimensions."""
        canvas, _ = _make_canvas(mocker)
        surface = canvas._build_surface_from_canvas_pixels()
        assert surface.get_width() == CANVAS_SIZE
        assert surface.get_height() == CANVAS_SIZE

    def test_non_magenta_pixels_preserved(self, mocker):
        """Test non-magenta pixels are preserved in the surface."""
        canvas, _ = _make_canvas(mocker)
        canvas.pixels = [RED_RGBA] * PIXEL_COUNT
        surface = canvas._build_surface_from_canvas_pixels()
        pixel_color = surface.get_at((0, 0))
        assert pixel_color[0] == 255  # Red
        assert pixel_color[1] == 0
        assert pixel_color[2] == 0

    def test_magenta_pixels_stay_opaque(self, mocker):
        """Test magenta pixels remain opaque in built surface (unlike get_canvas_surface)."""
        canvas, _ = _make_canvas(mocker)
        canvas.pixels = [MAGENTA_RGBA] * PIXEL_COUNT
        surface = canvas._build_surface_from_canvas_pixels()
        pixel_color = surface.get_at((0, 0))
        assert pixel_color[3] == 255  # Opaque magenta


# ---------------------------------------------------------------------------
# Behaviour of the real canvas (no pygame mocks)
# ---------------------------------------------------------------------------

STATIC_SPRITE_TOML = """[sprite]
name = "dot"
description = "A tiny red dot"
pixels = \"\"\"
#.
.#
\"\"\"

[colors."#"]
red = 255
green = 0
blue = 0

[colors."."]
red = 0
green = 0
blue = 255
"""

ANIMATED_SPRITE_TOML = """[sprite]
name = "blinker"

[[animation]]
namespace = "blink"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "blink"
frame_index = 0
pixels = \"\"\"
##
##
\"\"\"

[[animation.frame]]
namespace = "blink"
frame_index = 1
pixels = \"\"\"
..
..
\"\"\"

[colors."#"]
red = 255
green = 0
blue = 0

[colors."."]
red = 0
green = 0
blue = 255
"""


class RecordingFilmStripCoordinator:
    """Film strip coordinator stand-in that records the notifications it receives."""

    def __init__(self) -> None:
        """Start with no notifications."""
        self.notifications: list[tuple[str, tuple[object, ...]]] = []

    def update_film_strips_for_frame(self, animation: str, frame: int) -> None:
        """Record a frame change notification."""
        self.notifications.append(('update_film_strips_for_frame', (animation, frame)))

    def switch_to_film_strip(self, animation: str, frame: int) -> None:
        """Record a film strip switch."""
        self.notifications.append(('switch_to_film_strip', (animation, frame)))

    def _update_film_strips_for_pixel_update(self) -> None:
        """Record a pixel update notification."""
        self.notifications.append(('pixel_update', ()))

    def update_film_strips_for_animated_sprite_update(self) -> None:
        """Record an animated sprite update notification."""
        self.notifications.append(('animated_sprite_update', ()))

    def on_sprite_loaded(self, sprite: AnimatedSprite) -> None:
        """Record a sprite load notification."""
        self.notifications.append(('on_sprite_loaded', (sprite,)))

    def names(self) -> list[str]:
        """Return the names of the notifications received, in order.

        Returns:
            The notification names.

        """
        return [name for name, _arguments in self.notifications]


class FrameSelectionRecorder:
    """Film strip operation tracker stand-in that records frame selections."""

    def __init__(self) -> None:
        """Start with no selections."""
        self.selections: list[tuple[str, int]] = []

    def add_frame_selection(self, animation: str, frame: int) -> None:
        """Record a frame selection."""
        self.selections.append((animation, frame))


class UndoFrameRecorder:
    """Undo/redo manager stand-in that records the current frame it is told about."""

    def __init__(self) -> None:
        """Start with no current frame."""
        self.current_frames: list[tuple[str, int]] = []

    def set_current_frame(self, animation: str, frame: int) -> None:
        """Record the current frame."""
        self.current_frames.append((animation, frame))


class StrokeRecorder:
    """Canvas operation tracker stand-in that records the pixel strokes submitted for undo."""

    def __init__(self) -> None:
        """Start with no strokes."""
        self.strokes: list[tuple[str, int, list[tuple[object, ...]]]] = []

    def add_frame_pixel_changes(self, animation: str, frame: int, pixels: list) -> None:
        """Record a stroke on a frame."""
        self.strokes.append((animation, frame, list(pixels)))


class ParentSceneStandIn:
    """The parts of BitmapEditorScene the canvas talks to."""

    def __init__(self) -> None:
        """Create the recording collaborators."""
        self.film_strip_coordinator = RecordingFilmStripCoordinator()
        self.film_strip_operation_tracker = FrameSelectionRecorder()
        self.undo_redo_manager = UndoFrameRecorder()
        self.debug_text = type('DebugText', (), {'text': ''})()
        self.ai_sprite_position_updates = 0
        self.new_undo_histories = 0

    def _update_ai_sprite_position(self) -> None:
        """Count AI sprite position updates."""
        self.ai_sprite_position_updates += 1

    def start_new_undo_history(self) -> None:
        """Count the new undo histories started (each load starts one)."""
        self.new_undo_histories += 1


def _make_real_canvas(frame_count=3, animation_name='idle'):
    """Create a canvas on a real (unmocked) animated sprite.

    Args:
        frame_count: Number of frames in the animation.
        animation_name: Name of the animation.

    Returns:
        A tuple of (AnimatedCanvasSprite, AnimatedSprite).

    """
    animated_sprite = _make_animated_sprite_with_frames(
        animation_name=animation_name,
        frame_count=frame_count,
    )
    canvas = AnimatedCanvasSprite(
        animated_sprite=animated_sprite,
        name='Real Canvas',
        x=10,
        y=20,
        pixels_across=CANVAS_SIZE,
        pixels_tall=CANVAS_SIZE,
        pixel_width=PIXEL_WIDTH,
        pixel_height=PIXEL_HEIGHT,
    )
    return canvas, animated_sprite


def _event_at(*, x, y):
    """Build a mouse event at a screen position.

    Args:
        x: Screen x.
        y: Screen y.

    Returns:
        The event.

    """
    return pygame.event.Event(pygame.MOUSEMOTION, pos=(x, y))


def _canvas_position(canvas, *, pixel_x, pixel_y):
    """Return the screen position of the centre of a canvas pixel.

    Args:
        canvas: The canvas.
        pixel_x: Pixel column.
        pixel_y: Pixel row.

    Returns:
        The (x, y) screen position.

    """
    return (
        canvas.rect.x + pixel_x * canvas.pixel_width + canvas.pixel_width // 2,
        canvas.rect.y + pixel_y * canvas.pixel_height + canvas.pixel_height // 2,
    )


class TestNavigationWithParentScene:
    """Test that frame and animation navigation keeps the parent scene informed."""

    def test_show_frame_reports_selection_and_film_strip_update(self):
        """Showing a frame records the selection for undo and updates the film strips."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene

        canvas.show_frame('idle', 2)

        assert canvas.current_frame == 2
        assert parent_scene.film_strip_operation_tracker.selections == [('idle', 2)]
        assert parent_scene.film_strip_coordinator.names() == [
            'update_film_strips_for_frame',
            'update_film_strips_for_frame',
        ]

    def test_show_frame_while_applying_undo_is_not_recorded(self):
        """Frame changes made by an undo are not recorded as new selections."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        parent_scene.applying_undo_redo = True
        canvas.parent_scene = parent_scene

        canvas.show_frame('idle', 1)

        assert parent_scene.film_strip_operation_tracker.selections == []

    def test_show_frame_of_another_animation_switches_the_sprite(self):
        """Showing a frame of a different animation switches the sprite's animation."""
        canvas, animated_sprite = _make_real_canvas()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        animated_sprite.add_animation('walk', [SpriteFrame(surface)])

        canvas.show_frame('walk', 0)

        assert animated_sprite.current_animation == 'walk'
        assert canvas.current_animation == 'walk'

    def test_show_frame_uses_pixels_of_a_frame_without_pixel_data_method(self):
        """A frame object without get_pixel_data supplies its pixels attribute instead."""
        canvas, animated_sprite = _make_real_canvas()
        frame_without_method = type('BareFrame', (), {'pixels': [GREEN_RGBA] * PIXEL_COUNT})()
        animated_sprite._animations['idle'][1] = frame_without_method
        canvas.animated_sprite.set_frame = lambda frame_index: None

        canvas.show_frame('idle', 1)

        assert canvas.pixels == [GREEN_RGBA] * PIXEL_COUNT

    def test_next_and_previous_frame_switch_film_strips(self):
        """Stepping frames tells the parent scene which film strip frame to select."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene

        canvas.next_frame()
        canvas.previous_frame()

        switches = [
            arguments
            for name, arguments in parent_scene.film_strip_coordinator.notifications
            if name == 'switch_to_film_strip'
        ]
        assert switches == [('idle', 1), ('idle', 0)]

    def test_next_and_previous_animation_switch_film_strips(self):
        """Changing animation tells the parent scene to switch film strips."""
        canvas, animated_sprite = _make_real_canvas()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        animated_sprite.add_animation('walk', [SpriteFrame(surface)])
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene

        canvas.next_animation()
        canvas.previous_animation()

        switches = [
            arguments
            for name, arguments in parent_scene.film_strip_coordinator.notifications
            if name == 'switch_to_film_strip'
        ]
        assert switches == [('walk', 0), ('idle', 0)]

    def test_switching_to_an_empty_animation_uses_frame_zero(self, mocker):
        """An animation with no frames is entered at frame 0."""
        canvas, animated_sprite = _make_real_canvas()
        animated_sprite._animations['empty'] = []
        canvas.current_frame = 2
        show_frame = mocker.spy(canvas, 'show_frame')

        canvas.next_animation()
        canvas.current_animation = 'empty'
        canvas.current_frame = 2
        canvas.previous_animation()

        assert show_frame.call_args_list[0].args == ('empty', 0)
        assert show_frame.call_args_list[1].args == ('idle', 2)

    def test_set_frame_tells_the_undo_manager_and_resumes_playback(self):
        """Selecting a frame while playing updates the undo manager and keeps playing."""
        canvas, animated_sprite = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        animated_sprite.play()

        canvas.set_frame(2)

        assert parent_scene.undo_redo_manager.current_frames == [('idle', 2)]
        assert animated_sprite.is_playing
        assert canvas._manual_frame_selected is False


class TestKeyboardShortcuts:
    """Test handle_keyboard_event key bindings."""

    def test_space_toggles_playback(self):
        """Space pauses a playing animation and plays a paused one."""
        canvas, animated_sprite = _make_real_canvas()
        animated_sprite.play()

        canvas.handle_keyboard_event(pygame.K_SPACE)
        assert not animated_sprite.is_playing

        canvas.handle_keyboard_event(pygame.K_SPACE)
        assert animated_sprite.is_playing

    def test_number_key_selects_that_frame(self):
        """A number key selects the frame with that index."""
        canvas, _ = _make_real_canvas()

        canvas.handle_keyboard_event(pygame.K_2)

        assert canvas.current_frame == 2

    def test_up_and_down_change_animation(self):
        """Up and down arrows move between animations."""
        canvas, animated_sprite = _make_real_canvas()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        animated_sprite.add_animation('walk', [SpriteFrame(surface)])

        canvas.handle_keyboard_event(pygame.K_DOWN)
        assert canvas.current_animation == 'walk'

        canvas.handle_keyboard_event(pygame.K_UP)
        assert canvas.current_animation == 'idle'

    def test_unbound_key_changes_nothing(self):
        """A key with no binding leaves the frame and animation alone."""
        canvas, _ = _make_real_canvas()

        canvas.handle_keyboard_event(pygame.K_q)

        assert (canvas.current_animation, canvas.current_frame) == ('idle', 0)


class TestFromFile:
    """Test AnimatedCanvasSprite.from_file."""

    def test_loads_an_animated_sprite_file(self, tmp_path):
        """A TOML animation file becomes a canvas on its first frame."""
        sprite_path = tmp_path / 'blinker.toml'
        sprite_path.write_text(ANIMATED_SPRITE_TOML)

        canvas = AnimatedCanvasSprite.from_file(
            str(sprite_path),
            pixels_across=2,
            pixels_tall=2,
            pixel_width=8,
            pixel_height=8,
        )

        assert canvas.current_animation == 'blink'
        assert canvas.rect.size == (16, 16)

    def test_file_without_frames_is_refused(self, mocker):
        """A loaded object without frames raises ValueError."""
        mocker.patch(
            'bitmappy.animated_canvas.SpriteFactory.load_sprite',
            return_value=object(),
        )

        with pytest.raises(ValueError, match='does not contain animated sprite data'):
            AnimatedCanvasSprite.from_file('not_animated.toml')


class TestMouseEditing:
    """Test clicking, flood fill, dragging and hovering on the canvas."""

    def test_click_paints_the_pixel_under_the_mouse(self):
        """A click paints the clicked pixel with the active colour."""
        canvas, _ = _make_real_canvas()
        canvas.active_color = RED_RGBA

        canvas.on_left_mouse_button_down_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                pos=_canvas_position(canvas, pixel_x=1, pixel_y=2),
            ),
        )

        assert canvas.pixels[2 * CANVAS_SIZE + 1] == RED_RGBA
        assert canvas._manual_frame_selected is True

    def test_click_outside_the_canvas_paints_nothing(self):
        """A click outside the canvas leaves every pixel alone."""
        canvas, _ = _make_real_canvas()
        original_pixels = list(canvas.pixels)

        canvas.on_left_mouse_button_down_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(0, 0)),
        )

        assert canvas.pixels == original_pixels

    def test_control_click_flood_fills_the_region(self):
        """A control-click fills every connected pixel of the clicked colour."""
        from glitchygames.input.state import InputSnapshot, set_current_input

        canvas, _ = _make_real_canvas()
        canvas.active_color = RED_RGBA
        set_current_input(
            snapshot=InputSnapshot(
                pressed_scancodes=frozenset(),
                modifiers=pygame.KMOD_LCTRL,
                mouse_position=(0, 0),
                mouse_buttons=(True, False, False),
                mouse_focused=True,
                held_key_codes=frozenset({pygame.K_LCTRL}),
            ),
        )

        canvas.on_left_mouse_button_down_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                pos=_canvas_position(canvas, pixel_x=0, pixel_y=0),
            ),
        )

        assert all(
            tuple(canvas.canvas_interface.get_pixel_at(x, y)) == RED_RGBA
            for x in range(CANVAS_SIZE)
            for y in range(CANVAS_SIZE)
        )

    def test_flood_fill_out_of_bounds_and_same_colour_change_nothing(self):
        """Flood fill outside the canvas, or with the colour already there, does nothing."""
        canvas, _ = _make_real_canvas()
        current_color = tuple(canvas.canvas_interface.get_pixel_at(0, 0))
        original_pixels = list(canvas.pixels)

        canvas._flood_fill(-1, 0, RED_RGBA)
        canvas._flood_fill(0, 0, current_color)

        assert canvas.pixels == original_pixels

    def test_drag_paints_pixels_and_release_writes_them_to_the_frame(self):
        """Dragging paints each pixel once and release flushes them into the frame."""
        canvas, animated_sprite = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        canvas.active_color = RED_RGBA
        canvas.on_left_mouse_button_down_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(0, 0)),
        )

        for pixel_x in (0, 1, 2, 2):
            canvas.on_left_mouse_drag_event(
                pygame.event.Event(
                    pygame.MOUSEMOTION,
                    pos=_canvas_position(canvas, pixel_x=pixel_x, pixel_y=0),
                ),
                None,
            )

        assert set(canvas._drag_pixels) == {(0, 0), (1, 0), (2, 0)}
        # Every third drag event redraws and tells the film strips
        assert parent_scene.film_strip_coordinator.names() == ['pixel_update']

        canvas.on_left_mouse_button_up_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(0, 0)))

        frame_pixels = animated_sprite._animations['idle'][0].get_pixel_data()
        assert frame_pixels[:3] == [RED_RGBA] * 3
        assert canvas._drag_active is False
        assert canvas._drag_pixels == {}
        assert not hasattr(canvas, '_drag_frame')

    def test_drag_stroke_reaches_undo(self):
        """A real click-and-drag stroke is recorded for undo, every pixel of it (BUGS.md #101).

        The release submitted drag pixels only when there were none, and the scene's submit
        used the click's pixel alone, so the dragged pixels never reached undo.
        """
        canvas, animated_sprite = _make_real_canvas()
        original_pixels = animated_sprite._animations['idle'][0].get_pixel_data()
        parent_scene = ParentSceneStandIn()
        parent_scene.canvas = canvas
        parent_scene.canvas_operation_tracker = StrokeRecorder()
        frame_operations = FrameOperationManager(parent_scene)
        parent_scene._submit_pixel_changes_if_ready = frame_operations.submit_pixel_changes_if_ready
        canvas.parent_scene = parent_scene
        canvas.active_color = RED_RGBA

        canvas.on_left_mouse_button_down_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                pos=_canvas_position(canvas, pixel_x=0, pixel_y=0),
            ),
        )
        for pixel_x in (1, 2):
            canvas.on_left_mouse_drag_event(
                pygame.event.Event(
                    pygame.MOUSEMOTION,
                    pos=_canvas_position(canvas, pixel_x=pixel_x, pixel_y=0),
                ),
                None,
            )
        canvas.on_left_mouse_button_up_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONUP,
                pos=_canvas_position(canvas, pixel_x=2, pixel_y=0),
            ),
        )
        # The editor's generic button-up handler submits whatever is still pending
        frame_operations.submit_pixel_changes_if_ready()

        recorded_changes = {
            (x, y): (old_color, new_color)
            for _animation, _frame, pixels in parent_scene.canvas_operation_tracker.strokes
            for x, y, old_color, new_color in pixels
        }
        assert recorded_changes == {
            (pixel_x, 0): (original_pixels[pixel_x], RED_RGBA) for pixel_x in (0, 1, 2)
        }
        assert all(
            animation == 'idle' and frame == 0
            for animation, frame, _pixels in parent_scene.canvas_operation_tracker.strokes
        )

    def test_drag_outside_the_canvas_is_ignored(self):
        """Drag events outside the canvas paint nothing and start no drag."""
        canvas, _ = _make_real_canvas()
        canvas.on_left_mouse_drag_event(_event_at(x=0, y=0), None)

        assert not getattr(canvas, '_drag_active', False)

    def test_drag_on_the_canvas_edge_outside_the_grid_is_ignored(self):
        """A drag inside the rect but outside the pixel grid paints nothing."""
        canvas, _ = _make_real_canvas()
        canvas.rect.width += PIXEL_WIDTH

        canvas.on_left_mouse_drag_event(
            _event_at(x=canvas.rect.right - 1, y=canvas.rect.y + 1),
            None,
        )

        assert not getattr(canvas, '_drag_active', False)

    def test_drag_without_a_button_down_starts_its_own_drag(self):
        """A drag with no preceding button-down still tracks its pixels."""
        canvas, _ = _make_real_canvas()
        canvas.active_color = BLUE_RGBA

        canvas.on_left_mouse_drag_event(
            _event_at(x=canvas.rect.x + 1, y=canvas.rect.y + 1),
            None,
        )

        assert canvas._drag_pixels[0, 0][3] == BLUE_RGBA

    def test_release_without_a_drag_does_nothing(self):
        """A button release with no active drag leaves the canvas untouched."""
        canvas, _ = _make_real_canvas()
        canvas.dirty = 0

        canvas.on_left_mouse_button_up_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(0, 0)))

        assert canvas.dirty == 0

    def test_release_of_an_empty_drag_syncs_and_notifies(self):
        """Releasing a drag that tracked no pixels syncs the frame and tells the film strips."""
        canvas, animated_sprite = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        frame = animated_sprite._animations['idle'][0]
        canvas._drag_active = True
        canvas._drag_pixels = {}
        canvas._drag_frame = frame
        # A fast-path edit changed the frame's pixel list but not yet its image
        frame.pixels[0] = GREEN_RGBA
        canvas.pixels[0] = GREEN_RGBA

        canvas.on_left_mouse_button_up_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(0, 0)))

        assert tuple(frame.image.get_at((0, 0))) == GREEN_RGBA
        assert 'pixel_update' in parent_scene.film_strip_coordinator.names()
        assert 'animated_sprite_update' in parent_scene.film_strip_coordinator.names()
        assert canvas.dirty == 1

    def test_mouse_motion_tracks_hover_in_and_out(self, restore_mouse_cursor):
        """Hovering shows the pixel under the mouse and hides the cursor until leaving."""
        canvas, _ = _make_real_canvas()

        canvas.on_mouse_motion_event(
            _event_at(x=canvas.rect.x + PIXEL_WIDTH + 1, y=canvas.rect.y + 1),
        )
        assert canvas.is_hovered
        assert canvas.hovered_pixel == (1, 0)
        assert pygame.mouse.get_visible() is False

        canvas.rect.width += PIXEL_WIDTH
        canvas.on_mouse_motion_event(_event_at(x=canvas.rect.right - 1, y=canvas.rect.y + 1))
        assert canvas.hovered_pixel is None

        canvas.hovered_pixel = (0, 0)
        canvas.on_mouse_motion_event(_event_at(x=0, y=0))
        assert not canvas.is_hovered
        assert canvas.hovered_pixel is None
        assert pygame.mouse.get_visible() is True


class TestDragFrameHelpers:
    """Test the drag fast-path helpers on frames with and without pixel lists."""

    def test_old_colour_comes_from_canvas_without_a_drag_frame(self):
        """With no drag frame, the old colour is the canvas pixel."""
        canvas, _ = _make_real_canvas()
        canvas._drag_frame = None
        canvas.pixels[0] = GREEN_RGBA

        assert canvas._get_old_pixel_color(0) == GREEN_RGBA

    def test_old_colour_falls_back_to_frame_pixel_data(self):
        """A frame without a pixel list supplies the old colour from its pixel data."""
        canvas, _ = _make_real_canvas()
        bare_frame = type(
            'BareFrame',
            (),
            {'get_pixel_data': lambda self: [BLUE_RGBA]},
        )()
        canvas._drag_frame = bare_frame

        assert canvas._get_old_pixel_color(0) == BLUE_RGBA
        assert canvas._get_old_pixel_color(5) == MAGENTA_RGBA

    def test_update_falls_back_to_set_pixel_data(self):
        """A frame without a pixel list is updated through get/set_pixel_data."""
        canvas, animated_sprite = _make_real_canvas()
        stored_pixels = [BLACK_RGBA, BLACK_RGBA]

        class BareFrame:
            """A frame with only get/set_pixel_data."""

            def get_pixel_data(self):
                """Return a copy of the stored pixels."""
                return list(stored_pixels)

            def set_pixel_data(self, pixels):
                """Replace the stored pixels."""
                stored_pixels[:] = pixels

        canvas._drag_frame = BareFrame()
        animated_sprite._surface_cache = {'idle_0': 'cached'}

        canvas._update_drag_frame_pixel(1, RED_RGBA)
        canvas._update_drag_frame_pixel(9, RED_RGBA)

        assert stored_pixels == [BLACK_RGBA, RED_RGBA]
        assert 'idle_0' not in animated_sprite._surface_cache

    def test_update_without_a_drag_frame_does_nothing(self):
        """With no drag frame there is nothing to update."""
        canvas, _ = _make_real_canvas()
        canvas._drag_frame = None

        canvas._update_drag_frame_pixel(0, RED_RGBA)

        assert canvas._drag_frame is None

    def test_update_marks_the_frame_image_stale_until_rebuilt(self):
        """A fast-path update marks the image stale; rebuilding redraws it and clears the flag."""
        canvas, animated_sprite = _make_real_canvas()
        frame = animated_sprite._animations['idle'][0]
        canvas._drag_frame = frame

        canvas._update_drag_frame_pixel(0, RED_RGBA)
        canvas._update_drag_frame_pixel(PIXEL_COUNT + 1, RED_RGBA)
        assert frame._image_stale is True

        canvas._rebuild_frame_image_from_pixels(frame)

        assert tuple(frame.image.get_at((0, 0))) == RED_RGBA
        assert not hasattr(frame, '_image_stale')

    def test_cache_drag_frame_without_the_animation_is_none(self):
        """Caching the drag frame of a missing animation stores None."""
        canvas, _ = _make_real_canvas()
        canvas.current_animation = 'missing'

        canvas._cache_drag_frame()

        assert canvas._drag_frame is None

    def test_flush_skips_a_missing_animation(self):
        """Flushing drag pixels for a missing animation changes no frame."""
        canvas, animated_sprite = _make_real_canvas()
        canvas._drag_pixels = {(0, 0): (0, 0, BLACK_RGBA, RED_RGBA)}
        canvas.current_animation = 'missing'

        canvas._flush_batched_drag_pixels()

        assert animated_sprite._animations['idle'][0].get_pixel_data()[0] != RED_RGBA

    def test_flush_skips_pixels_outside_the_frame(self):
        """Drag pixels beyond the frame are not written."""
        canvas, animated_sprite = _make_real_canvas()
        canvas._drag_pixels = {(0, 9): (0, 9, BLACK_RGBA, RED_RGBA)}

        canvas._flush_batched_drag_pixels()

        assert RED_RGBA not in animated_sprite._animations['idle'][0].get_pixel_data()

    def test_sync_failure_is_tolerated(self):
        """A frame that cannot take its own pixels back is left as it is."""
        canvas, _ = _make_real_canvas()

        class RefusingFrame:
            """A frame whose set_pixel_data fails."""

            pixels = (RED_RGBA,)

            def set_pixel_data(self, pixels):
                """Refuse the pixels.

                Raises:
                    ValueError: Always.

                """
                raise ValueError(pixels)

        canvas._drag_frame = RefusingFrame()

        canvas._sync_drag_frame_surface()

        assert canvas._drag_frame.pixels == (RED_RGBA,)

    def test_submit_to_undo_queues_changes_for_the_scene(self):
        """Drag changes are added to the scene's pending pixel changes and submitted."""
        canvas, _ = _make_real_canvas()
        submitted = []
        parent_scene = ParentSceneStandIn()
        parent_scene.canvas_operation_tracker = object()
        parent_scene._submit_pixel_changes_if_ready = lambda: submitted.append(True)
        canvas.parent_scene = parent_scene
        canvas._drag_pixels = {(0, 0): (0, 0, BLACK_RGBA, RED_RGBA)}

        canvas._submit_drag_pixel_changes_to_undo()

        assert parent_scene.current_pixel_changes_dict == {(0, 0): (0, 0, BLACK_RGBA, RED_RGBA)}
        assert submitted == [True]

    def test_submit_to_undo_keeps_the_first_old_colour_of_a_clicked_pixel(self):
        """A pixel the click already changed keeps the colour it had before the click."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        parent_scene.canvas_operation_tracker = object()
        parent_scene.current_pixel_changes_dict = {(0, 0): (0, 0, BLACK_RGBA, GREEN_RGBA)}
        canvas.parent_scene = parent_scene
        canvas._drag_pixels = {
            (0, 0): (0, 0, GREEN_RGBA, RED_RGBA),
            (1, 0): (1, 0, BLACK_RGBA, RED_RGBA),
        }

        canvas._submit_drag_pixel_changes_to_undo()

        assert parent_scene.current_pixel_changes_dict == {
            (0, 0): (0, 0, BLACK_RGBA, RED_RGBA),
            (1, 0): (1, 0, BLACK_RGBA, RED_RGBA),
        }

    def test_submit_to_undo_without_changes_queues_nothing(self):
        """With no drag changes nothing is queued."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        parent_scene.canvas_operation_tracker = object()
        canvas.parent_scene = parent_scene
        canvas._drag_pixels = {}

        canvas._submit_drag_pixel_changes_to_undo()

        assert not hasattr(parent_scene, 'current_pixel_changes_dict')


class TestPixelUpdateAndFrameSync:
    """Test on_pixel_update_event and _update_animated_sprite_frame."""

    def test_pixel_update_writes_the_frame_and_notifies(self):
        """A pixel update paints the canvas, rebuilds the frame image and tells the strips."""
        canvas, animated_sprite = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        trigger = type('Trigger', (), {'pixel_number': 5, 'pixel_color': RED_RGBA})()

        canvas.on_pixel_update_event(None, trigger)

        assert canvas.pixels[5] == RED_RGBA
        assert tuple(animated_sprite._animations['idle'][0].image.get_at((1, 1))) == RED_RGBA
        assert parent_scene.film_strip_coordinator.names() == [
            'pixel_update',
            'animated_sprite_update',
        ]

    def test_frame_sync_skips_an_unknown_frame(self):
        """Syncing a frame index past the end of the animation changes nothing."""
        canvas, animated_sprite = _make_real_canvas()
        canvas.current_frame = 99
        original_image = animated_sprite._animations['idle'][0].image

        canvas._update_animated_sprite_frame()

        assert animated_sprite._animations['idle'][0].image is original_image


class TestSaving:
    """Test on_save_file_event and _save_as_static_sprite."""

    def test_single_frame_animation_is_saved_as_a_static_sprite(self, tmp_path):
        """A one-frame animation saves as a static sprite that loads back with its pixels."""
        canvas, _ = _make_real_canvas(frame_count=1)
        canvas.animated_sprite._animations['idle'][0].set_pixel_data([RED_RGBA] * PIXEL_COUNT)
        save_path = tmp_path / 'single.toml'

        canvas.on_save_file_event(str(save_path))

        saved_text = save_path.read_text()
        assert '[[animation]]' not in saved_text
        loaded = AnimatedSprite()
        loaded.load(str(save_path))
        first_animation = next(iter(loaded._animations.values()))
        assert first_animation[0].get_pixel_data()[0][:3] == RED_RGB

    def test_multi_frame_animation_is_saved_as_an_animation(self, tmp_path):
        """A multi-frame animation saves every frame."""
        canvas, _ = _make_real_canvas(frame_count=2)
        save_path = tmp_path / 'multi.toml'

        canvas.on_save_file_event(str(save_path))

        loaded = AnimatedSprite()
        loaded.load(str(save_path))
        assert len(loaded._animations['idle']) == 2

    def test_save_failure_is_raised(self, tmp_path):
        """A save into a missing directory raises the OSError."""
        canvas, _ = _make_real_canvas(frame_count=2)

        with pytest.raises(OSError, match='missing'):
            canvas.on_save_file_event(str(tmp_path / 'missing' / 'sprite.toml'))

    def test_sync_tolerates_frames_that_refuse_pixels(self):
        """Frames that cannot take their pixels back are skipped during the save sync."""
        canvas, animated_sprite = _make_real_canvas(frame_count=1)

        class RefusingFrame:
            """A frame whose set_pixel_data fails."""

            pixels = (RED_RGBA,)

            def set_pixel_data(self, pixels):
                """Refuse the pixels.

                Raises:
                    TypeError: Always.

                """
                raise TypeError(pixels)

        animated_sprite._animations['idle'].append(RefusingFrame())

        canvas._sync_all_frames_pixel_data()

        assert animated_sprite._animations['idle'][1].pixels == (RED_RGBA,)

    def test_sync_tolerates_a_broken_animation_table(self):
        """An animation table that cannot be read is skipped during the save sync."""
        canvas, animated_sprite = _make_real_canvas(frame_count=1)
        animated_sprite._animations = {'idle': None}

        canvas._sync_all_frames_pixel_data()

        assert animated_sprite._animations == {'idle': None}

    @pytest.mark.parametrize(
        ('animations', 'message'),
        [({}, 'No animations found'), ({'idle': []}, 'No frames found in animation')],
    )
    def test_static_save_without_frames_is_refused(self, animations, message):
        """Saving a static sprite with no animation or no frame raises ValueError."""
        canvas, animated_sprite = _make_real_canvas(frame_count=1)
        animated_sprite._animations = animations

        with pytest.raises(ValueError, match=message):
            canvas._save_as_static_sprite('unused.toml', 'toml')

    def test_static_save_without_a_sprite_is_refused(self):
        """Saving a static sprite with no animated sprite raises ValueError."""
        canvas, _ = _make_real_canvas(frame_count=1)
        canvas.animated_sprite = None

        with pytest.raises(ValueError, match='No animated sprite to save'):
            canvas._save_as_static_sprite('unused.toml', 'toml')
        assert canvas._is_single_frame_animation() is False


class TestLoading:
    """Test on_load_file_event and its helpers."""

    def test_loading_an_animation_shows_its_first_frame_and_notifies(self, tmp_path):
        """Loading a file replaces the sprite, plays it and tells the scene."""
        canvas, _ = _make_real_canvas()
        canvas.pixels_across = 2
        canvas.pixels_tall = 2
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        sprite_path = tmp_path / 'blinker.toml'
        sprite_path.write_text(ANIMATED_SPRITE_TOML)

        canvas.on_load_file_event(str(sprite_path))

        assert canvas.current_animation == 'blink'
        assert canvas.animated_sprite.is_playing
        assert canvas.pixels[0][:3] == (255, 0, 0)
        assert parent_scene.film_strip_coordinator.names()[0] == 'on_sprite_loaded'
        assert parent_scene.debug_text.text == (
            'Enter a description of the sprite you want to create:'
        )
        assert parent_scene.new_undo_histories == 1

    def test_loading_a_described_sprite_shows_its_description(self, tmp_path):
        """A sprite with a description puts it in the AI text box."""
        canvas, _ = _make_real_canvas()
        canvas.pixels_across = 2
        canvas.pixels_tall = 2
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        sprite_path = tmp_path / 'dot.toml'
        sprite_path.write_text(STATIC_SPRITE_TOML)
        load_event = type('LoadEvent', (), {'text': str(sprite_path)})()

        canvas.on_load_file_event(load_event)

        assert parent_scene.debug_text.text == 'A tiny red dot'

    def test_load_with_repairs_shows_the_notice(self, tmp_path):
        """A file whose pixel rows needed repair says so below the AI text box's text."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        sprite_path = tmp_path / 'ragged.toml'
        sprite_path.write_text(
            '[sprite]\nname = "ragged"\npixels = """\n##\n#\n\n##\n"""\n\n'
            '[colors."#"]\nred = 255\ngreen = 0\nblue = 0\n'
        )

        canvas.on_load_file_event(str(sprite_path))

        assert parent_scene.debug_text.text == (
            'Enter a description of the sprite you want to create:'
            '\nRepaired the pixel rows of 1 block(s) while loading (details in the log). '
            'Saving writes the repaired rows.'
        )

    def test_loading_a_blank_static_sprite_does_not_crash(self, tmp_path):
        """A sprite with no pixels to draw is reported as a load error, not a crash."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        sprite_path = tmp_path / 'blank.toml'
        sprite_path.write_text(
            '[sprite]\nname = "blank"\npixels = """\n\n"""\n\n'
            '[colors."#"]\nred = 255\ngreen = 0\nblue = 0\n'
        )

        canvas.on_load_file_event(str(sprite_path))

        assert parent_scene.debug_text.text.startswith('Error loading sprite:')

    def test_clean_load_shows_no_notice(self, tmp_path):
        """A file that needed no repair shows only the usual text."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        sprite_path = tmp_path / 'blinker.toml'
        sprite_path.write_text(ANIMATED_SPRITE_TOML)

        canvas.on_load_file_event(str(sprite_path))

        assert 'Repaired' not in parent_scene.debug_text.text

    def test_loading_a_different_size_resizes_the_canvas(self, tmp_path):
        """A sprite of another size resizes the canvas to fit it."""
        # The size math depends on the 800x600 display the conftest opens
        assert pygame.display.get_surface().get_size() == (800, 600)
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        sprite_path = tmp_path / 'blinker.toml'
        sprite_path.write_text(ANIMATED_SPRITE_TOML)

        canvas.on_load_file_event(str(sprite_path))

        # min(496 // 2, 400 // 2, 320 // 2) = 160 screen pixels per sprite pixel
        assert (canvas.pixels_across, canvas.pixels_tall) == (2, 2)
        assert (canvas.pixel_width, canvas.pixel_height) == (160, 160)
        assert canvas.rect.size == (320, 320)
        assert parent_scene.ai_sprite_position_updates == 1

    def test_resize_changes_only_its_own_canvas(self):
        """A resize sets the canvas's own size, never class-wide state (BUGS.md #110 item 2)."""
        # The size math depends on the 800x600 display the conftest opens
        assert pygame.display.get_surface().get_size() == (800, 600)
        resized_canvas, _ = _make_real_canvas()
        other_canvas, _ = _make_real_canvas()

        resized_canvas._resize_canvas_to_sprite_size(8, 6)

        assert (resized_canvas.pixels_across, resized_canvas.pixels_tall) == (8, 6)
        assert (other_canvas.pixels_across, other_canvas.pixels_tall) == (
            CANVAS_SIZE,
            CANVAS_SIZE,
        )
        assert 'WIDTH' not in vars(AnimatedCanvasSprite)
        assert 'HEIGHT' not in vars(AnimatedCanvasSprite)

    def test_large_sprite_gets_the_minimum_pixel_size(self):
        """A 128x128 sprite is drawn with the minimum pixel size."""
        # The size math depends on the 800x600 display the conftest opens
        assert pygame.display.get_surface().get_size() == (800, 600)
        canvas, _ = _make_real_canvas()

        canvas._resize_canvas_to_sprite_size(128, 128)

        assert canvas.pixel_width == 2
        assert canvas.rect.size == (256, 256)

    def test_missing_file_is_reported_without_raising(self, tmp_path):
        """A missing file is reported in the editor's debug text, where a load reports too."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene

        canvas.on_load_file_event(str(tmp_path / 'missing.toml'))

        assert parent_scene.debug_text.text.startswith('Error: File not found')

    def test_unreadable_file_is_reported_without_raising(self, tmp_path):
        """A malformed file is reported in the editor's debug text instead of raising."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        sprite_path = tmp_path / 'broken.toml'
        sprite_path.write_text('[sprite\nname = = "broken"\n')

        canvas.on_load_file_event(str(sprite_path))

        assert parent_scene.debug_text.text.startswith('Error loading sprite')

    def test_load_error_without_an_editor_is_only_logged(self, tmp_path):
        """With no editor to show it in, a load error is logged and nothing raises."""
        canvas, _ = _make_real_canvas()
        canvas.parent_scene = None

        canvas.on_load_file_event(str(tmp_path / 'missing.toml'))

        assert canvas.parent_scene is None

    def test_png_that_cannot_convert_is_refused(self, mocker):
        """A PNG that does not convert raises ValueError from the loader."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        parent_scene._file_io = mocker.Mock(spec=FileIOManager)
        parent_scene._file_io._convert_png_to_bitmappy.return_value = None
        canvas.parent_scene = parent_scene

        with pytest.raises(ValueError, match='Failed to convert PNG'):
            canvas._load_sprite_from_file('picture.png')

    def test_png_without_an_editor_is_refused(self):
        """A canvas with no editor has no file I/O to convert a PNG with: ValueError."""
        canvas, _ = _make_real_canvas()
        canvas.parent_scene = None

        with pytest.raises(ValueError, match='no editor'):
            canvas._load_sprite_from_file('picture.png')

    def test_png_is_converted_before_loading(self, tmp_path, mocker):
        """A PNG is loaded from the TOML file the editor's file I/O converted it to."""
        canvas, _ = _make_real_canvas()
        sprite_path = tmp_path / 'blinker.toml'
        sprite_path.write_text(ANIMATED_SPRITE_TOML)
        parent_scene = ParentSceneStandIn()
        parent_scene._file_io = mocker.Mock(spec=FileIOManager)
        parent_scene._file_io._convert_png_to_bitmappy.return_value = str(sprite_path)
        canvas.parent_scene = parent_scene

        loaded_sprite = canvas._load_sprite_from_file('picture.png')

        assert list(loaded_sprite._animations) == ['blink']
        assert parent_scene._file_io._convert_png_to_bitmappy.call_args.args == ('picture.png',)

    def test_png_loads_through_the_load_dialog(self, tmp_path):
        """A real PNG loaded through on_load_file_event ends on the canvas (BUGS.md #89)."""
        canvas, _ = _make_real_canvas()
        parent_scene = ParentSceneStandIn()
        parent_scene.canvas = canvas
        parent_scene._file_io = FileIOManager(parent_scene)
        canvas.parent_scene = parent_scene
        image = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        image.fill(RED_RGB)
        image_path = tmp_path / 'red.png'
        pygame.image.save(image, str(image_path))

        canvas.on_load_file_event(str(image_path))

        assert not parent_scene.debug_text.text.startswith('Error')
        assert canvas.pixels[0][:3] == RED_RGB
        assert parent_scene.film_strip_coordinator.names()[0] == 'on_sprite_loaded'

    def test_sprite_load_callback_is_used_without_a_parent_scene(self):
        """Without a parent scene, the canvas's own on_sprite_loaded callback is called."""
        canvas, animated_sprite = _make_real_canvas()
        loaded_sprites = []
        canvas.on_sprite_loaded = loaded_sprites.append

        canvas._update_ui_components(animated_sprite)

        assert loaded_sprites == [animated_sprite]

    def test_sprite_without_animations_is_resized_by_its_size(self, mocker):
        """A loaded sprite with no animations is sized by its own get_size."""
        canvas, _ = _make_real_canvas()
        resize = mocker.patch.object(canvas, '_resize_canvas_to_sprite_size')
        static_sprite = type(
            'StaticSprite', (), {'_animations': {}, 'get_size': lambda self: (8, 6)}
        )()

        canvas._check_and_resize_canvas(static_sprite)

        assert resize.call_args.args == (8, 6)

    def test_finalize_without_a_parent_scene_keeps_going(self):
        """Finalizing a load with no parent scene still copies the frame to the canvas."""
        canvas, animated_sprite = _make_real_canvas()
        canvas.pixels = [GREEN_RGBA] * PIXEL_COUNT
        del canvas.parent_scene

        canvas._finalize_sprite_loading(animated_sprite, 'sprite.toml')

        assert canvas.pixels == animated_sprite._animations['idle'][0].get_pixel_data()


class TestCurrentFramePixels:
    """Test _get_current_frame_pixels fallbacks."""

    def test_sprite_without_animations_supplies_its_own_pixels(self):
        """A sprite with no animations supplies its pixel data directly."""
        canvas, _ = _make_real_canvas()
        canvas.animated_sprite = type(
            'StaticSprite',
            (),
            {'_animations': {}, 'get_pixel_data': lambda self: [RED_RGB]},
        )()

        assert canvas._get_current_frame_pixels() == [RED_RGBA]

    def test_sprite_without_animations_supplies_its_pixel_list(self):
        """A sprite with no animations and no get_pixel_data supplies its pixels list."""
        canvas, _ = _make_real_canvas()
        canvas.animated_sprite = type(
            'StaticSprite', (), {'_animations': {}, 'pixels': [RED_RGBA]}
        )()

        assert canvas._get_current_frame_pixels() == [RED_RGBA]

    def test_frame_without_pixel_data_falls_back_to_canvas_pixels(self):
        """A frame without get_pixel_data leaves the canvas pixels as the answer."""
        canvas, animated_sprite = _make_real_canvas()
        animated_sprite._animations['idle'][0] = object()
        canvas.pixels = [GREEN_RGBA] * PIXEL_COUNT

        assert canvas._get_current_frame_pixels() == [GREEN_RGBA] * PIXEL_COUNT

    def test_copy_without_frame_pixels_keeps_the_canvas(self, mocker):
        """When there are no frame pixels, the canvas keeps what it has."""
        canvas, _ = _make_real_canvas()
        mocker.patch.object(canvas, '_get_current_frame_pixels', return_value=[])
        canvas.pixels = [GREEN_RGBA] * PIXEL_COUNT

        canvas._copy_sprite_to_canvas()

        assert canvas.pixels == [GREEN_RGBA] * PIXEL_COUNT


class TestNavigationEdges:
    """Test frame and animation navigation where there is nothing to move to."""

    def test_frame_steps_on_an_unknown_animation_change_nothing(self):
        """next_frame and previous_frame keep the frame for an animation not in the sprite."""
        canvas, _ = _make_real_canvas()
        canvas.current_animation = 'missing'
        canvas.current_frame = 1

        canvas.next_frame()
        canvas.previous_frame()

        assert (canvas.current_animation, canvas.current_frame) == ('missing', 1)

    def test_animation_steps_without_animations_change_nothing(self):
        """next_animation and previous_animation do nothing when the sprite has no animations."""
        canvas, animated_sprite = _make_real_canvas()
        animated_sprite._animations = {}
        canvas.current_frame = 1

        canvas.next_animation()
        canvas.previous_animation()

        assert (canvas.current_animation, canvas.current_frame) == ('idle', 1)

    def test_previous_animation_without_frames_asks_for_frame_zero(self):
        """Stepping back to an animation with no frames tells the scene to show its frame 0."""
        canvas, animated_sprite = _make_real_canvas()
        animated_sprite._animations = {'empty': [], **animated_sprite._animations}
        parent_scene = ParentSceneStandIn()
        canvas.parent_scene = parent_scene
        canvas.current_frame = 2

        canvas.previous_animation()

        assert parent_scene.film_strip_coordinator.notifications[-1] == (
            'switch_to_film_strip',
            ('empty', 0),
        )
        assert (canvas.current_animation, canvas.current_frame) == ('idle', 2)

    def test_set_frame_out_of_range_changes_nothing(self):
        """A frame index past the end of the animation is ignored."""
        canvas, animated_sprite = _make_real_canvas()
        canvas.current_frame = 1

        canvas.set_frame(7)

        assert canvas.current_frame == 1
        assert animated_sprite.current_frame == 0


class TestCopyPasteOutOfRange:
    """Test frame copy and paste when the current frame does not exist."""

    def test_copy_of_a_missing_frame_fills_no_clipboard(self):
        """Copying a frame index past the end leaves the clipboard empty."""
        canvas, _ = _make_real_canvas()
        canvas.current_frame = 9

        canvas.copy_current_frame()

        assert not hasattr(canvas, '_clipboard')

    def test_paste_onto_a_missing_frame_changes_no_frame(self):
        """Pasting with a frame index past the end writes nowhere."""
        canvas, animated_sprite = _make_real_canvas()
        canvas._clipboard = [RED_RGBA] * PIXEL_COUNT
        canvas.current_frame = 9

        canvas.paste_to_current_frame()

        for frame in animated_sprite._animations['idle']:
            assert RED_RGBA not in frame.get_pixel_data()


class TestDragEdges:
    """Test drag handling with no drag frame, no scene or extra pixels."""

    def test_rebuild_ignores_pixels_past_the_image(self):
        """Pixels beyond width x height are not drawn into the frame image."""
        canvas, animated_sprite = _make_real_canvas()
        frame = animated_sprite._animations['idle'][0]
        frame.pixels = [RED_RGBA] * PIXEL_COUNT + [GREEN_RGBA] * 3

        canvas._rebuild_frame_image_from_pixels(frame)

        image = frame.image
        assert all(
            tuple(image.get_at((pixel_x, pixel_y))) == RED_RGBA
            for pixel_y in range(CANVAS_SIZE)
            for pixel_x in range(CANVAS_SIZE)
        )

    def test_drag_on_an_unknown_animation_without_a_scene_still_paints_the_canvas(self):
        """A drag with no frame to cache and no scene paints the canvas and redraws every third."""
        canvas, _ = _make_real_canvas()
        canvas.current_animation = 'missing'
        canvas.parent_scene = None
        canvas.active_color = RED_RGBA

        for pixel_x in range(3):
            canvas.dirty = 0
            screen_x, screen_y = _canvas_position(canvas, pixel_x=pixel_x, pixel_y=0)
            canvas.on_left_mouse_drag_event(_event_at(x=screen_x, y=screen_y), None)

        assert canvas._drag_frame is None
        assert canvas.pixels[:3] == [RED_RGBA] * 3
        assert canvas.dirty == 1

    def test_sync_of_a_frame_without_pixels_changes_nothing(self):
        """A drag frame with an empty pixel list is not synced."""
        canvas, _ = _make_real_canvas()
        synced = []
        canvas._drag_frame = type(
            'EmptyFrame',
            (),
            {'pixels': [], 'set_pixel_data': lambda self, pixels: synced.append(pixels)},
        )()

        canvas._sync_drag_frame_surface()

        assert synced == []

    def test_cleanup_with_no_drag_frame_forgets_it(self):
        """Cleaning up after a drag with no frame drops the drag frame reference."""
        canvas, _ = _make_real_canvas()
        canvas._drag_active = True
        canvas._drag_frame = None

        canvas._cleanup_drag_state()

        assert canvas._drag_active is False
        assert not hasattr(canvas, '_drag_frame')

    def test_cleanup_redraws_a_stale_frame_and_clears_the_flag(self):
        """A stale drag frame is redrawn from its pixels and stops being stale."""
        canvas, animated_sprite = _make_real_canvas()
        frame = animated_sprite._animations['idle'][0]
        frame.pixels[0] = RED_RGBA
        frame._image_stale = True
        canvas._drag_frame = frame
        canvas._drag_redraw_counter = 2

        canvas._cleanup_drag_state()

        assert tuple(frame.image.get_at((0, 0))) == RED_RGBA
        assert not hasattr(frame, '_image_stale')
        assert not hasattr(canvas, '_drag_redraw_counter')

    def test_mouse_up_without_drag_pixels_or_scene_syncs_the_frame(self):
        """Releasing a drag with no batched pixels and no scene still updates the frame image."""
        canvas, animated_sprite = _make_real_canvas()
        frame = animated_sprite._animations['idle'][0]
        canvas.parent_scene = None
        canvas._drag_active = True
        canvas._drag_pixels = {}
        canvas._drag_frame = frame
        canvas.pixels[0] = GREEN_RGBA
        frame.pixels[0] = GREEN_RGBA

        canvas.on_left_mouse_button_up_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(0, 0)))

        assert tuple(frame.image.get_at((0, 0))) == GREEN_RGBA
        assert canvas._drag_active is False


class TestHoverEdges:
    """Test mouse motion that changes no hover state."""

    def test_moving_over_the_border_without_a_hovered_pixel_keeps_it_clear(
        self,
        restore_mouse_cursor,
    ):
        """Over the canvas but off the pixel grid, with no hovered pixel, nothing is redrawn."""
        canvas, _ = _make_real_canvas()
        canvas.is_hovered = True
        canvas.rect.width += PIXEL_WIDTH
        canvas.dirty = 0

        canvas.on_mouse_motion_event(_event_at(x=canvas.rect.right - 1, y=canvas.rect.y + 1))

        assert canvas.hovered_pixel is None
        assert canvas.dirty == 0

    def test_moving_elsewhere_while_not_hovering_changes_nothing(self, restore_mouse_cursor):
        """Outside the canvas, with no hover state to clear, nothing is redrawn."""
        canvas, _ = _make_real_canvas()
        canvas.dirty = 0
        # A cursor hidden by something else stays hidden: the canvas does not show it
        pygame.mouse.set_visible(False)

        canvas.on_mouse_motion_event(_event_at(x=0, y=0))

        assert canvas.is_hovered is False
        assert canvas.dirty == 0
        assert pygame.mouse.get_visible() is False


class TestCanvasSurfacesWithShortPixels:
    """Test the canvas surfaces when the pixel list is shorter than the grid."""

    def test_build_surface_leaves_missing_pixels_transparent(self):
        """Grid cells with no pixel stay fully transparent in the built surface."""
        canvas, _ = _make_real_canvas()
        canvas.pixels = [RED_RGBA] * 2

        surface = canvas._build_surface_from_canvas_pixels()

        assert tuple(surface.get_at((1, 0))) == RED_RGBA
        assert tuple(surface.get_at((2, 0)))[3] == 0

    def test_canvas_surface_leaves_missing_pixels_transparent(self):
        """Grid cells with no pixel stay fully transparent in the film strip surface."""
        canvas, _ = _make_real_canvas()
        canvas.pixels = [BLUE_RGBA] * 2

        surface = canvas.get_canvas_surface()

        assert tuple(surface.get_at((1, 0))) == BLUE_RGBA
        assert tuple(surface.get_at((3, 3)))[3] == 0


class TestSpriteStateEdges:
    """Test loading and saving helpers on sprites with little data."""

    def test_sprite_without_animations_is_not_single_frame(self):
        """A sprite with no animations is not a single-frame animation."""
        canvas, animated_sprite = _make_real_canvas()
        animated_sprite._animations = {}

        assert canvas._is_single_frame_animation() is False

    def test_frames_without_pixel_lists_are_left_alone_by_the_save_sync(self):
        """A frame with no pixel list keeps its image when frames are synced before saving."""
        canvas, animated_sprite = _make_real_canvas()
        frame = animated_sprite._animations['idle'][0]
        frame.pixels = []
        frame.image.fill(GREEN_RGBA)

        canvas._sync_all_frames_pixel_data()

        assert frame.pixels == []
        assert tuple(frame.image.get_at((0, 0))) == GREEN_RGBA

    def test_loaded_sprite_without_animations_or_size_keeps_the_canvas_size(self, mocker):
        """A loaded sprite with no animations and no get_size does not resize the canvas."""
        canvas, _ = _make_real_canvas()
        resize = mocker.patch.object(canvas, '_resize_canvas_to_sprite_size')

        canvas._check_and_resize_canvas(AnimatedSprite())

        resize.assert_not_called()

    def test_static_sprite_of_the_canvas_size_is_not_resized(self, mocker):
        """A static sprite already the canvas size leaves the canvas as it is."""
        canvas, _ = _make_real_canvas()
        resize = mocker.patch.object(canvas, '_resize_canvas_to_sprite_size')
        static_sprite = type(
            'StaticSprite',
            (),
            {'_animations': {}, 'get_size': lambda self: (CANVAS_SIZE, CANVAS_SIZE)},
        )()

        canvas._check_and_resize_canvas(static_sprite)

        resize.assert_not_called()

    def test_sprite_without_a_current_animation_is_not_started(self):
        """A loaded sprite with no current animation is not played."""
        canvas, _ = _make_real_canvas()
        loaded_sprite = AnimatedSprite()

        canvas._setup_animation_state(loaded_sprite)

        assert not canvas.current_animation
        assert loaded_sprite.is_playing is False
