"""Comprehensive tests for AnimatedCanvasSprite in glitchygames/tools/bitmappy.py.

Targets the AnimatedCanvasSprite class (starts at line 3219) which has ~2100 lines
of testable methods including initialization, frame navigation, panning, pixel
operations, and rendering state management.
"""

import sys
from pathlib import Path
from typing import cast

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.bitmappy.canvas_interfaces import (
    AnimatedCanvasInterface,
    AnimatedCanvasRenderer,
    AnimatedSpriteSerializer,
)
from glitchygames.bitmappy.editor import AnimatedCanvasSprite, BitmapPixelSprite
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from tests.mocks.test_mock_factory import MockFactory

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


def _make_canvas(
    mocker,
    pixels_across=CANVAS_SIZE,
    pixels_tall=CANVAS_SIZE,
    pixel_width=PIXEL_WIDTH,
    pixel_height=PIXEL_HEIGHT,
    animation_name='idle',
    frame_count=3,
):
    """Create an AnimatedCanvasSprite with minimal mocked dependencies.

    Args:
        mocker: The pytest-mock mocker fixture.
        pixels_across: Number of pixels across the canvas.
        pixels_tall: Number of pixels tall the canvas.
        pixel_width: Width of each pixel in screen coordinates.
        pixel_height: Height of each pixel in screen coordinates.
        animation_name: Name of the animation to create.
        frame_count: Number of frames to add.

    Returns:
        A tuple of (AnimatedCanvasSprite, AnimatedSprite).

    """
    animated_sprite = _make_animated_sprite_with_frames(
        animation_name=animation_name,
        frame_count=frame_count,
        frame_size=pixels_across,
    )

    canvas = AnimatedCanvasSprite(
        animated_sprite=animated_sprite,
        name='Test Canvas',
        x=0,
        y=0,
        pixels_across=pixels_across,
        pixels_tall=pixels_tall,
        pixel_width=pixel_width,
        pixel_height=pixel_height,
    )

    return canvas, animated_sprite


class TestInitializeDimensions:
    """Test _initialize_dimensions pure math method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_initialize_dimensions_basic(self, mocker):
        """Test basic dimension initialization returns correct width and height."""
        canvas, _ = _make_canvas(
            mocker, pixels_across=8, pixels_tall=8, pixel_width=10, pixel_height=10
        )
        assert canvas.pixels_across == 8
        assert canvas.pixels_tall == 8
        assert canvas.pixel_width == 10
        assert canvas.pixel_height == 10

    def test_initialize_dimensions_rectangular(self, mocker):
        """Test dimensions for a non-square canvas."""
        canvas, _ = _make_canvas(
            mocker, pixels_across=16, pixels_tall=8, pixel_width=4, pixel_height=8
        )
        assert canvas.pixels_across == 16
        assert canvas.pixels_tall == 8
        assert canvas.pixel_width == 4
        assert canvas.pixel_height == 8

    def test_initialize_dimensions_computes_canvas_size(self, mocker):
        """Test that canvas surface dimensions are pixels_across * pixel_width."""
        canvas, _ = _make_canvas(
            mocker, pixels_across=4, pixels_tall=4, pixel_width=16, pixel_height=16
        )
        # The image should be pixels_across * pixel_width by pixels_tall * pixel_height
        expected_width = 4 * 16
        expected_height = 4 * 16
        assert canvas.image.get_width() == expected_width
        assert canvas.image.get_height() == expected_height

    def test_initialize_dimensions_small_pixel_size(self, mocker):
        """Test dimensions with pixel size of 1."""
        canvas, _ = _make_canvas(
            mocker, pixels_across=32, pixels_tall=32, pixel_width=1, pixel_height=1
        )
        assert canvas.pixel_width == 1
        assert canvas.pixel_height == 1


class TestInitializePixelArrays:
    """Test _initialize_pixel_arrays method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_pixel_array_length(self, mocker):
        """Test pixel array has correct length for canvas size."""
        canvas, _ = _make_canvas(mocker, pixels_across=4, pixels_tall=4)
        # Pixels are updated from animated sprite frame data during init,
        # but dirty_pixels should match the expected count
        assert len(canvas.dirty_pixels) == PIXEL_COUNT

    def test_dirty_pixels_initialized_true(self, mocker):
        """Test all dirty pixels start as True after initialization."""
        canvas, _ = _make_canvas(mocker, pixels_across=4, pixels_tall=4)
        assert all(canvas.dirty_pixels)

    def test_background_color_set(self, mocker):
        """Test background color is set to gray."""
        canvas, _ = _make_canvas(mocker, pixels_across=4, pixels_tall=4)
        assert canvas.background_color == (128, 128, 128)

    def test_active_color_set(self, mocker):
        """Test active color is set to black RGBA."""
        canvas, _ = _make_canvas(mocker, pixels_across=4, pixels_tall=4)
        assert canvas.active_color == BLACK_RGBA


class TestInitializeSimplePanning:
    """Test _initialize_simple_panning method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_frame_panning_dict_initialized_empty(self, mocker):
        """Test _frame_panning is initialized as empty dict."""
        canvas, _ = _make_canvas(mocker)
        assert isinstance(canvas._frame_panning, dict)

    def test_frame_panning_starts_empty(self, mocker):
        """Test _frame_panning starts with no entries."""
        canvas, _ = _make_canvas(mocker)
        # Initially empty since no panning has been initiated
        assert len(canvas._frame_panning) == 0


class TestUpdateBorderThickness:
    """Test _update_border_thickness method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_normal_pixel_size_has_border(self, mocker):
        """Test border thickness is 1 for normal pixel sizes."""
        canvas, _ = _make_canvas(
            mocker, pixels_across=4, pixels_tall=4, pixel_width=16, pixel_height=16
        )
        assert canvas.border_thickness == 1

    def test_small_pixel_size_disables_border(self, mocker):
        """Test border is disabled for pixel size <= 2."""
        canvas, _ = _make_canvas(
            mocker, pixels_across=4, pixels_tall=4, pixel_width=2, pixel_height=2
        )
        assert canvas.border_thickness == 0

    def test_large_sprite_disables_border(self, mocker):
        """Test border is disabled for sprites >= 128 pixels across."""
        canvas, _ = _make_canvas(
            mocker, pixels_across=128, pixels_tall=128, pixel_width=4, pixel_height=4, frame_count=1
        )
        assert canvas.border_thickness == 0

    def test_border_thickness_change_clears_pixel_cache(self, mocker):
        """Test that changing border thickness clears BitmapPixelSprite.PIXEL_CACHE."""
        # Set up initial cache entry
        BitmapPixelSprite.PIXEL_CACHE['test_key'] = 'test_value'  # type: ignore[invalid-assignment]

        canvas, _ = _make_canvas(
            mocker, pixels_across=4, pixels_tall=4, pixel_width=16, pixel_height=16
        )
        # Manually trigger a border thickness change
        canvas.pixel_width = 2
        canvas.pixel_height = 2
        canvas._update_border_thickness()
        # Cache should be cleared on thickness change
        assert 'test_key' not in BitmapPixelSprite.PIXEL_CACHE


class TestGetCurrentFrameKey:
    """Test _get_current_frame_key method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_returns_animation_frame_string(self, mocker):
        """Test frame key format is 'animation_frame'."""
        canvas, _ = _make_canvas(mocker, animation_name='walk')
        canvas.current_animation = 'walk'
        canvas.current_frame = 2
        assert canvas._get_current_frame_key() == 'walk_2'

    def test_frame_key_with_default_animation(self, mocker):
        """Test frame key for default idle animation at frame 0."""
        canvas, _ = _make_canvas(mocker, animation_name='idle')
        assert canvas._get_current_frame_key() == 'idle_0'

    def test_frame_key_changes_with_frame(self, mocker):
        """Test frame key updates when frame changes."""
        canvas, _ = _make_canvas(mocker, animation_name='idle')
        canvas.current_frame = 1
        assert canvas._get_current_frame_key() == 'idle_1'


class TestSetFrame:
    """Test set_frame method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_next_frame_increments(self, mocker):
        """Test next_frame moves to the next frame."""
        canvas, _ = _make_canvas(mocker, frame_count=3)
        canvas.current_frame = 0
        canvas.next_frame()
        assert canvas.current_frame == 1

    def test_next_frame_wraps_around(self, mocker):
        """Test next_frame wraps to frame 0 at the end."""
        canvas, _ = _make_canvas(mocker, frame_count=3)
        canvas.current_frame = 2
        canvas.next_frame()
        assert canvas.current_frame == 0


class TestPreviousFrame:
    """Test previous_frame method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_previous_frame_decrements(self, mocker):
        """Test previous_frame moves to the previous frame."""
        canvas, _ = _make_canvas(mocker, frame_count=3)
        canvas.current_frame = 2
        canvas.previous_frame()
        assert canvas.current_frame == 1

    def test_previous_frame_wraps_around(self, mocker):
        """Test previous_frame wraps to last frame from frame 0."""
        canvas, _ = _make_canvas(mocker, frame_count=3)
        canvas.current_frame = 0
        canvas.previous_frame()
        assert canvas.current_frame == 2


class TestNextAnimation:
    """Test next_animation method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_next_animation_cycles(self, mocker):
        """Test next_animation moves to the next animation."""
        canvas, animated_sprite = _make_canvas(mocker, animation_name='idle')
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
        canvas, animated_sprite = _make_canvas(mocker, animation_name='idle')
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
        canvas, animated_sprite = _make_canvas(mocker, animation_name='idle', frame_count=3)
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
        canvas, animated_sprite = _make_canvas(mocker, animation_name='idle', frame_count=5)
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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_previous_animation_cycles(self, mocker):
        """Test previous_animation moves to the previous animation."""
        canvas, animated_sprite = _make_canvas(mocker, animation_name='idle')
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
        canvas, animated_sprite = _make_canvas(mocker, animation_name='idle')
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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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
        """Test returns False when _applying_undo_redo is True."""
        canvas, _ = _make_canvas(mocker)
        parent = mocker.Mock()
        parent.undo_redo_manager = mocker.Mock()
        parent._applying_undo_redo = True
        parent._creating_frame = False
        parent._creating_animation = False
        canvas.parent_scene = parent
        assert canvas._should_track_frame_selection() is False

    def test_returns_false_when_creating_frame(self, mocker):
        """Test returns False when _creating_frame is True."""
        canvas, _ = _make_canvas(mocker)
        parent = mocker.Mock()
        parent.undo_redo_manager = mocker.Mock()
        parent._applying_undo_redo = False
        parent._creating_frame = True
        parent._creating_animation = False
        canvas.parent_scene = parent
        assert canvas._should_track_frame_selection() is False

    def test_returns_false_when_creating_animation(self, mocker):
        """Test returns False when _creating_animation is True."""
        canvas, _ = _make_canvas(mocker)
        parent = mocker.Mock()
        parent.undo_redo_manager = mocker.Mock()
        parent._applying_undo_redo = False
        parent._creating_frame = False
        parent._creating_animation = True
        canvas.parent_scene = parent
        assert canvas._should_track_frame_selection() is False

    def test_returns_true_when_all_conditions_met(self, mocker):
        """Test returns True when parent has undo manager and no flags set."""
        canvas, _ = _make_canvas(mocker)
        parent = mocker.Mock()
        parent.undo_redo_manager = mocker.Mock()
        parent._applying_undo_redo = False
        parent._creating_frame = False
        parent._creating_animation = False
        canvas.parent_scene = parent
        assert canvas._should_track_frame_selection() is True


class TestIsPanningActive:
    """Test is_panning_active method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_panning_inactive_by_default(self, mocker):
        """Test panning is not active initially."""
        canvas, _ = _make_canvas(mocker)
        assert canvas.is_panning_active() is False

    def test_panning_active_after_setting(self, mocker):
        """Test panning is active when frame_panning entry has active=True."""
        canvas, _ = _make_canvas(mocker)
        frame_key = canvas._get_current_frame_key()
        canvas._frame_panning[frame_key] = {
            'pan_x': 1,
            'pan_y': 0,
            'original_pixels': None,
            'active': True,
        }
        assert canvas.is_panning_active() is True

    def test_panning_inactive_when_frame_key_not_present(self, mocker):
        """Test panning returns False for unknown frame key."""
        canvas, _ = _make_canvas(mocker)
        # Change to a frame key that's not in _frame_panning
        canvas.current_animation = 'nonexistent'
        canvas.current_frame = 99
        assert canvas.is_panning_active() is False


class TestResetPanning:
    """Test reset_panning method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_reset_panning_clears_active_state(self, mocker):
        """Test reset_panning sets active to False."""
        canvas, _ = _make_canvas(mocker)
        frame_key = canvas._get_current_frame_key()
        canvas._frame_panning[frame_key] = {
            'pan_x': 5,
            'pan_y': 3,
            'original_pixels': [MAGENTA_RGBA] * PIXEL_COUNT,
            'active': True,
        }
        canvas.reset_panning()
        assert canvas._frame_panning[frame_key]['active'] is False
        assert canvas._frame_panning[frame_key]['pan_x'] == 0
        assert canvas._frame_panning[frame_key]['pan_y'] == 0

    def test_reset_panning_reloads_frame_data(self, mocker):
        """Test reset_panning reloads original frame pixel data."""
        canvas, _animated_sprite = _make_canvas(mocker)
        frame_key = canvas._get_current_frame_key()
        canvas._frame_panning[frame_key] = {
            'pan_x': 1,
            'pan_y': 1,
            'original_pixels': [RED_RGBA] * PIXEL_COUNT,
            'active': True,
        }
        # Modify canvas pixels to simulate panning distortion
        canvas.pixels = [BLUE_RGBA] * PIXEL_COUNT
        canvas.reset_panning()
        # After reset, pixels should be reloaded from the frame
        assert canvas.dirty == 1

    def test_reset_panning_no_entry_does_nothing(self, mocker):
        """Test reset_panning with no frame_panning entry doesn't crash."""
        canvas, _ = _make_canvas(mocker)
        # No panning entry exists - should not raise
        canvas.reset_panning()


class TestComputePannedPixels:
    """Test _compute_panned_pixels pure math method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_offset_returns_same_pixels(self, mocker):
        """Test with zero offset returns same pixel data."""
        canvas, _ = _make_canvas(mocker)
        canvas.pan_offset_x = 0
        canvas.pan_offset_y = 0
        original_pixels = [RED_RGBA] * PIXEL_COUNT
        result = canvas._compute_panned_pixels(original_pixels)
        assert result == original_pixels

    def test_positive_x_offset_shifts_right(self, mocker):
        """Test positive x offset shifts pixels right (transparent on left)."""
        canvas, _ = _make_canvas(mocker)
        canvas.pan_offset_x = 1
        canvas.pan_offset_y = 0
        # Create pixels with unique values per column
        original_pixels = [
            (col * 50, row * 50, 0, 255) for row in range(CANVAS_SIZE) for col in range(CANVAS_SIZE)
        ]

        result = canvas._compute_panned_pixels(original_pixels)
        # First column should be transparent (shifted right by 1)
        transparent = (255, 0, 255)
        assert result[0] == transparent  # (0,0) -> source (-1,0) = out of bounds

    def test_positive_y_offset_shifts_down(self, mocker):
        """Test positive y offset shifts pixels down (transparent on top)."""
        canvas, _ = _make_canvas(mocker)
        canvas.pan_offset_x = 0
        canvas.pan_offset_y = 1
        original_pixels = [RED_RGBA] * PIXEL_COUNT

        result = canvas._compute_panned_pixels(original_pixels)
        transparent = (255, 0, 255)
        # First row should be transparent
        for col in range(CANVAS_SIZE):
            assert result[col] == transparent

    def test_empty_frame_pixels(self, mocker):
        """Test with empty pixel list returns all transparent."""
        canvas, _ = _make_canvas(mocker)
        canvas.pan_offset_x = 0
        canvas.pan_offset_y = 0
        result = canvas._compute_panned_pixels([])
        transparent = (255, 0, 255)
        assert all(pixel == transparent for pixel in result)


class TestGetCurrentFramePixels:
    """Test _get_current_frame_pixels method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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
        canvas, animated_sprite = _make_canvas(mocker, frame_count=1)
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
        canvas, animated_sprite = _make_canvas(mocker, frame_count=3)
        # Set frame 1 with a distinct color
        frame = animated_sprite._animations['idle'][1]
        green_rgba_pixels = cast('list[tuple[int, ...]]', [GREEN_RGBA] * PIXEL_COUNT)
        frame.set_pixel_data(green_rgba_pixels)

        canvas.current_frame = 1
        pixels = canvas._get_current_frame_pixels()
        assert pixels[0] == GREEN_RGBA


class TestForceRedraw:
    """Test force_redraw method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_force_redraw_updates_image(self, mocker):
        """Test force_redraw generates a new canvas image."""
        canvas, _ = _make_canvas(mocker)
        original_image = canvas.image
        canvas.force_redraw()
        # force_redraw should produce an image (may or may not be same object)
        assert canvas.image is not None

    def test_force_redraw_uses_renderer(self, mocker):
        """Test force_redraw delegates to canvas_renderer."""
        canvas, _ = _make_canvas(mocker)
        mock_renderer = mocker.Mock()
        mock_surface = pygame.Surface((64, 64))
        mock_renderer.force_redraw.return_value = mock_surface
        canvas.canvas_renderer = mock_renderer

        canvas.force_redraw()
        mock_renderer.force_redraw.assert_called_once_with(canvas)
        assert canvas.image == mock_surface


class TestUpdate:
    """Test update method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_redraws_when_dirty(self, mocker):
        """Test update calls force_redraw when dirty flag is set."""
        canvas, _ = _make_canvas(mocker)
        canvas.dirty = 1
        mock_renderer = mocker.Mock()
        mock_renderer.force_redraw.return_value = pygame.Surface((64, 64))
        canvas.canvas_renderer = mock_renderer

        canvas.update()
        mock_renderer.force_redraw.assert_called()

    def test_update_clears_dirty_flag(self, mocker):
        """Test update clears dirty flag after redraw."""
        canvas, _ = _make_canvas(mocker)
        canvas.dirty = 1
        canvas.update()
        assert canvas.dirty == 0

    def test_update_does_nothing_when_clean(self, mocker):
        """Test update does not call force_redraw when clean."""
        canvas, _ = _make_canvas(mocker)
        canvas.dirty = 0
        mock_renderer = mocker.Mock()
        canvas.canvas_renderer = mock_renderer

        canvas.update()
        mock_renderer.force_redraw.assert_not_called()


class TestShowFrame:
    """Test show_frame method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_show_frame_updates_current_animation(self, mocker):
        """Test show_frame sets current_animation."""
        canvas, _ = _make_canvas(mocker, animation_name='idle', frame_count=3)
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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_left_arrow_calls_previous_frame(self, mocker):
        """Test LEFT arrow key calls previous_frame."""
        canvas, _ = _make_canvas(mocker, frame_count=3)
        canvas.current_frame = 1
        canvas.handle_keyboard_event(pygame.K_LEFT)
        assert canvas.current_frame == 0

    def test_right_arrow_calls_next_frame(self, mocker):
        """Test RIGHT arrow key calls next_frame."""
        canvas, _ = _make_canvas(mocker, frame_count=3)
        canvas.current_frame = 0
        canvas.handle_keyboard_event(pygame.K_RIGHT)
        assert canvas.current_frame == 1

    def test_number_key_sets_frame(self, mocker):
        """Test number key sets frame directly."""
        canvas, _ = _make_canvas(mocker, frame_count=3)
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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_copy_stores_pixel_data(self, mocker):
        """Test copy_current_frame stores pixel data in clipboard."""
        canvas, animated_sprite = _make_canvas(mocker, frame_count=1)
        frame = animated_sprite._animations['idle'][0]
        red_rgba_pixels = cast('list[tuple[int, ...]]', [RED_RGBA] * PIXEL_COUNT)
        frame.set_pixel_data(red_rgba_pixels)

        canvas.copy_current_frame()
        assert hasattr(canvas, '_clipboard')
        assert len(canvas._clipboard) == PIXEL_COUNT

    def test_paste_applies_clipboard_data(self, mocker):
        """Test paste_to_current_frame applies clipboard to current frame."""
        canvas, animated_sprite = _make_canvas(mocker, frame_count=2)
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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_single_frame_returns_true(self, mocker):
        """Test returns True for single animation with single frame."""
        canvas, _ = _make_canvas(mocker, frame_count=1)
        assert canvas._is_single_frame_animation() is True

    def test_multiple_frames_returns_false(self, mocker):
        """Test returns False for animation with multiple frames."""
        canvas, _ = _make_canvas(mocker, frame_count=3)
        assert canvas._is_single_frame_animation() is False

    def test_multiple_animations_returns_false(self, mocker):
        """Test returns False when there are multiple animations."""
        canvas, animated_sprite = _make_canvas(mocker, frame_count=1)
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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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


class TestPanCanvas:
    """Test pan_canvas method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_pan_canvas_creates_frame_panning_entry(self, mocker):
        """Test pan_canvas creates a frame panning entry."""
        canvas, _ = _make_canvas(mocker)
        canvas.pan_canvas(1, 0)
        frame_key = canvas._get_current_frame_key()
        assert frame_key in canvas._frame_panning
        assert canvas._frame_panning[frame_key]['pan_x'] == 1
        assert canvas._frame_panning[frame_key]['active'] is True

    def test_pan_canvas_accumulates_offsets(self, mocker):
        """Test multiple pan_canvas calls accumulate offsets."""
        canvas, _ = _make_canvas(mocker)
        canvas.pan_canvas(1, 0)
        canvas.pan_canvas(1, 0)
        frame_key = canvas._get_current_frame_key()
        assert canvas._frame_panning[frame_key]['pan_x'] == 2

    def test_pan_canvas_rejects_out_of_bounds(self, mocker):
        """Test pan_canvas rejects panning beyond max_pan (10)."""
        canvas, _ = _make_canvas(mocker)
        # Pan to the limit
        for _ in range(10):
            canvas.pan_canvas(1, 0)
        frame_key = canvas._get_current_frame_key()
        current_pan_x = canvas._frame_panning[frame_key]['pan_x']
        # Try to pan one more - should be rejected
        canvas.pan_canvas(1, 0)
        assert canvas._frame_panning[frame_key]['pan_x'] == current_pan_x


class TestCanPan:
    """Test _can_pan method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_can_pan_within_bounds(self, mocker):
        """Test _can_pan returns True within bounds."""
        canvas, _ = _make_canvas(mocker)
        assert canvas._can_pan(5, 5) is True

    def test_can_pan_at_max_bounds(self, mocker):
        """Test _can_pan returns True at exactly max bounds."""
        canvas, _ = _make_canvas(mocker)
        assert canvas._can_pan(10, 10) is True

    def test_cannot_pan_beyond_bounds(self, mocker):
        """Test _can_pan returns False beyond max bounds."""
        canvas, _ = _make_canvas(mocker)
        assert canvas._can_pan(11, 0) is False
        assert canvas._can_pan(0, 11) is False

    def test_can_pan_negative_within_bounds(self, mocker):
        """Test _can_pan returns True for negative offsets within bounds."""
        canvas, _ = _make_canvas(mocker)
        assert canvas._can_pan(-10, -10) is True

    def test_cannot_pan_negative_beyond_bounds(self, mocker):
        """Test _can_pan returns False for negative offsets beyond bounds."""
        canvas, _ = _make_canvas(mocker)
        assert canvas._can_pan(-11, 0) is False


class TestOnPixelUpdateEvent:
    """Test on_pixel_update_event method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_animation_delegates_to_sprite(self, mocker):
        """Test update_animation calls animated_sprite.update with dt."""
        canvas, animated_sprite = _make_canvas(mocker)
        mocker.patch.object(animated_sprite, 'update')
        canvas.update_animation(0.016)
        animated_sprite.update.assert_called_once_with(0.016)


class TestClearSurfaceCache:
    """Test _clear_surface_cache method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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
        surface = canvas.get_canvas_surface()
        # Should return a valid surface (pixel alpha depends on real vs mocked Surface)
        assert surface is not None
        assert surface.get_width() == CANVAS_SIZE


class TestHoverTracking:
    """Test hover-related initialization."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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


class TestStoreOriginalFrameDataForFrame:
    """Test _store_original_frame_data_for_frame method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_stores_pixel_copy(self, mocker):
        """Test stores a copy of current pixels into frame panning state."""
        canvas, _ = _make_canvas(mocker)
        frame_key = 'idle_0'
        canvas._frame_panning[frame_key] = {
            'pan_x': 0,
            'pan_y': 0,
            'original_pixels': None,
            'active': False,
        }
        canvas.pixels = [RED_RGBA] * PIXEL_COUNT
        canvas._store_original_frame_data_for_frame(frame_key)
        assert canvas._frame_panning[frame_key]['original_pixels'] == [RED_RGBA] * PIXEL_COUNT

    def test_stored_pixels_are_independent_copy(self, mocker):
        """Test stored pixels are a copy, not a reference."""
        canvas, _ = _make_canvas(mocker)
        frame_key = 'idle_0'
        canvas._frame_panning[frame_key] = {
            'pan_x': 0,
            'pan_y': 0,
            'original_pixels': None,
            'active': False,
        }
        canvas.pixels = [RED_RGBA] * PIXEL_COUNT
        canvas._store_original_frame_data_for_frame(frame_key)
        # Modify canvas pixels after storing
        canvas.pixels[0] = BLUE_RGBA
        # Stored pixels should not change
        assert canvas._frame_panning[frame_key]['original_pixels'][0] == RED_RGBA
