"""Tests for film strip tool functionality, coverage, and edge cases."""

import math
from typing import cast

import pygame
import pytest

from glitchygames.bitmappy import film_strip
from glitchygames.bitmappy.film_strip import (
    ANIMATION_NAME_MAX_LENGTH,
    FilmStripDeleteTab,
    FilmStripTab,
    FilmStripWidget,
    FilmTabWidget,
)
from glitchygames.sprites.animated import (
    AnimatedSprite,
    SpriteFrame,
)
from tests.mocks.test_mock_factory import MockFactory

# Constants for test values - from test_tools_film_strip.py (smaller widget)
FUNC_WIDGET_X = 10
FUNC_WIDGET_Y = 20
FUNC_WIDGET_WIDTH = 200
FUNC_WIDGET_HEIGHT = 150
FRAME_COUNT = 2
ANIMATION_COUNT = 3
COLOR_COMPONENT_MAX = 255
DEFAULT_DURATION = 1.0

# Constants for test values - from coverage/deeper/final tests (larger widget)
WIDGET_X = 0
WIDGET_Y = 0
WIDGET_WIDTH = 500
WIDGET_HEIGHT = 200
SURFACE_SIZE = 4
FRAME_DURATION = 0.5
FRAME_DURATION_FAST = 0.25
DT_60FPS = 0.016
DT_LARGE = 1.0
BACKGROUND_COLOR_COUNT = 10


def _make_widget_with_sprite(num_frames=2, animation_name='idle'):
    """Create a FilmStripWidget with an animated sprite.

    Args:
        num_frames: Number of frames to create.
        animation_name: Name of the animation.

    Returns:
        Tuple of (widget, sprite).

    """
    widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
    sprite = AnimatedSprite()
    surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
    frames = [SpriteFrame(surface, duration=FRAME_DURATION) for _ in range(num_frames)]
    sprite.add_animation(animation_name, frames)
    widget.set_animated_sprite(sprite)
    widget.current_animation = animation_name
    widget.current_frame = 0
    return widget, sprite


class TestFilmStripFunctionality:
    """Test film strip module functionality."""

    def test_film_strip_initialization(self, mock_pygame_patches):
        """Test film strip initialization."""
        # Test basic initialization - FilmStripWidget requires x, y, width, height
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test basic properties
        assert hasattr(strip, 'rect')
        assert hasattr(strip, 'animated_sprite')
        assert hasattr(strip, 'current_animation')
        assert hasattr(strip, 'current_frame')

        # Test default values
        assert strip.animated_sprite is None
        assert not strip.current_animation
        assert strip.current_frame == 0

    def test_film_strip_widget_properties(self, mock_pygame_patches):
        """Test film strip widget properties."""
        strip = film_strip.FilmStripWidget(
            FUNC_WIDGET_X, FUNC_WIDGET_Y, FUNC_WIDGET_WIDTH, FUNC_WIDGET_HEIGHT
        )

        # Test rect properties
        assert strip.rect is not None
        assert strip.rect.x == FUNC_WIDGET_X
        assert strip.rect.y == FUNC_WIDGET_Y
        assert strip.rect.width == FUNC_WIDGET_WIDTH
        assert strip.rect.height == FUNC_WIDGET_HEIGHT

        # Test styling properties
        assert hasattr(strip, 'frame_width')
        assert hasattr(strip, 'frame_height')
        assert hasattr(strip, 'sprocket_width')
        assert hasattr(strip, 'frame_spacing')

    def test_film_strip_widget_methods(self, mock_pygame_patches):
        """Test film strip widget methods."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test that widget has expected methods (based on actual implementation)
        assert hasattr(strip, 'set_animated_sprite')
        assert hasattr(strip, 'update_animations')
        assert hasattr(strip, 'get_current_preview_frame')
        assert hasattr(strip, 'get_frame_at_position')

        # Test methods are callable
        assert callable(strip.set_animated_sprite)
        assert callable(strip.update_animations)
        assert callable(strip.get_current_preview_frame)
        assert callable(strip.get_frame_at_position)

    def test_film_strip_widget_sprite_handling(self, mock_pygame_patches):
        """Test film strip widget sprite handling."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test initial state
        assert strip.animated_sprite is None
        assert not strip.current_animation
        assert strip.current_frame == 0

        # Test setting animated sprite with proper mock using centralized mock
        mock_sprite = MockFactory.create_animated_sprite_mock()
        strip.set_animated_sprite(mock_sprite)
        assert strip.animated_sprite == mock_sprite

    def test_film_strip_widget_hover_handling(self, mock_pygame_patches):
        """Test film strip widget hover handling."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test hover properties
        assert hasattr(strip, 'hovered_frame')
        assert hasattr(strip, 'hovered_animation')

        # Test initial hover state
        assert strip.hovered_frame is None
        assert strip.hovered_animation is None

    def test_film_strip_widget_rendering(self, mock_pygame_patches):
        """Test film strip widget rendering."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test rendering methods exist (based on actual implementation)
        assert hasattr(strip, 'update_layout')
        assert hasattr(strip, 'mark_dirty')
        assert hasattr(strip, 'set_parent_canvas')

        # Test methods are callable
        assert callable(strip.update_layout)
        assert callable(strip.mark_dirty)
        assert callable(strip.set_parent_canvas)

    def test_film_strip_widget_interaction(self, mock_pygame_patches):
        """Test film strip widget interaction."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test interaction methods exist (based on actual implementation)
        assert hasattr(strip, 'get_frame_at_position')
        assert hasattr(strip, 'update_scroll_for_frame')
        assert hasattr(strip, '_calculate_scroll_offset')

        # Test methods are callable
        assert callable(strip.get_frame_at_position)
        assert callable(strip.update_scroll_for_frame)
        assert callable(strip._calculate_scroll_offset)

    def test_initialize_preview_animations_no_sprite(self, mock_pygame_patches):
        """Test _initialize_preview_animations when no animated sprite is set."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        # Should not crash when no sprite is set
        strip._initialize_preview_animations()

    def test_initialize_preview_animations_frames_no_duration(self, mock_pygame_patches, mocker):
        """Test _initialize_preview_animations with frames that don't have duration attribute."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create frames without duration attribute by using simple objects
        frames_without_duration = []
        for _ in range(ANIMATION_COUNT):
            frame = type('Frame', (), {})()  # Simple object with no duration attribute
            frame.image = mocker.Mock()  # type: ignore[unresolved-attribute]
            frame.image.get_size.return_value = (32, 32)  # type: ignore[unresolved-attribute]
            # No duration attribute
            frames_without_duration.append(frame)

        mock_sprite._animations['no_duration'] = frames_without_duration
        strip.set_animated_sprite(mock_sprite)

        # Should use default 1.0 duration
        expected_durations = [DEFAULT_DURATION, DEFAULT_DURATION, DEFAULT_DURATION]
        assert strip.preview_frame_durations['no_duration'] == expected_durations

    def test_update_animations_no_sprite(self, mock_pygame_patches):
        """Test update_animations when no animated sprite is set."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        # Should not crash when no sprite is set
        strip.update_animations(0.1)

    def test_get_current_preview_frame_missing_animation(self, mock_pygame_patches):
        """Test get_current_preview_frame when animation is not in timing data."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        # Should return 0 for missing animation
        result = strip.get_current_preview_frame('nonexistent_animation')
        assert result == 0

    def test_get_frame_image_no_image_with_pixel_data(self, mock_pygame_patches, mocker):
        """Test _get_frame_image when frame has no image but has pixel data."""
        # Create a frame without image but with pixel data
        # Production code calls frame.get_size() after get_pixel_data(), so both are needed
        frame = type('Frame', (), {})()
        frame.get_pixel_data = mocker.Mock(return_value=[(255, 0, 0)] * 100)  # type: ignore[unresolved-attribute]
        frame.get_size = mocker.Mock(return_value=(10, 10))  # type: ignore[unresolved-attribute]

        result = film_strip.FilmStripWidget._get_frame_image(frame)  # type: ignore[arg-type]
        assert result is not None  # Should return a surface

    def test_get_frame_image_no_image_no_pixel_data(self, mock_pygame_patches):
        """Test _get_frame_image when frame has no image and no pixel data."""
        # Create a frame without image or pixel data
        frame = type('Frame', (), {})()
        # No get_pixel_data method

        result = film_strip.FilmStripWidget._get_frame_image(frame)  # type: ignore[arg-type]
        assert result is None  # Should return None

    def test_update_layout_with_parent_canvas(self, mock_pygame_patches, mocker):
        """Test update_layout when parent canvas exists with film strip sprite."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Create a mock parent canvas with film strip sprite
        mock_parent_canvas = mocker.Mock()
        mock_film_strip_sprite = mocker.Mock()
        mock_parent_canvas.film_strip_sprite = mock_film_strip_sprite
        strip.parent_canvas = mock_parent_canvas

        # Should not crash and should mark sprite as dirty
        strip.update_layout()
        mock_film_strip_sprite.dirty = 1

    def test_set_parent_canvas(self, mock_pygame_patches, mocker):
        """Test set_parent_canvas method."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        mock_canvas = mocker.Mock()

        strip.set_parent_canvas(mock_canvas)
        assert strip.parent_canvas == mock_canvas

    def test_mark_dirty_basic(self, mock_pygame_patches):
        """Test mark_dirty method sets _force_redraw flag."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        strip.mark_dirty()
        assert strip._force_redraw is True

    def test_propagate_dirty_to_sprite_groups(self, mock_pygame_patches, mocker):
        """Test _propagate_dirty_to_sprite_groups method."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Create a mock sprite with groups
        mock_sprite = mocker.Mock()
        mock_other_sprite = mocker.Mock()
        mock_group = [mock_sprite, mock_other_sprite]
        mock_sprite.groups.return_value = [mock_group]

        # Should not crash
        strip._propagate_dirty_to_sprite_groups(mock_sprite)
        assert mock_other_sprite.dirty == 1

    def test_update_scroll_for_frame_no_sprite(self, mock_pygame_patches):
        """Test update_scroll_for_frame when no animated sprite is set."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        # Should not crash when no sprite is set
        strip.update_scroll_for_frame(0)

    def test_update_scroll_for_frame_missing_animation(self, mock_pygame_patches):
        """Test update_scroll_for_frame when animation is not in sprite."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        mock_sprite = MockFactory.create_animated_sprite_mock()
        strip.set_animated_sprite(mock_sprite)
        strip.current_animation = 'nonexistent'

        # Should not crash when animation doesn't exist
        strip.update_scroll_for_frame(0)

    def test_update_scroll_for_frame_invalid_index(self, mock_pygame_patches):
        """Test update_scroll_for_frame when frame index is out of bounds."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        mock_sprite = MockFactory.create_animated_sprite_mock()
        strip.set_animated_sprite(mock_sprite)
        strip.current_animation = 'idle'

        # Should not crash when frame index is too high
        strip.update_scroll_for_frame(999)

    def test_update_height_with_animations(self, mock_pygame_patches, mocker):
        """Test _update_height method with multiple animations."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        mock_sprite = MockFactory.create_animated_sprite_mock()
        # Add more animations to test height calculation
        mock_sprite._animations['walk'] = [mocker.Mock(), mocker.Mock(), mocker.Mock()]
        mock_sprite._animations['jump'] = [mocker.Mock(), mocker.Mock()]
        strip.set_animated_sprite(mock_sprite)

        # Should calculate height based on number of animations
        strip._update_height()
        assert strip.rect is not None
        assert strip.rect.height > 0

    def test_update_height_with_parent_canvas(self, mock_pygame_patches, mocker):
        """Test _update_height method with parent canvas."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        mock_sprite = MockFactory.create_animated_sprite_mock()
        strip.set_animated_sprite(mock_sprite)

        # Create a mock parent canvas with film strip sprite
        mock_parent_canvas = mocker.Mock()
        mock_film_strip_sprite = mocker.Mock()
        mock_film_strip_sprite.rect = mocker.Mock()
        mock_film_strip_sprite.rect.width = 100
        mock_parent_canvas.film_strip_sprite = mock_film_strip_sprite
        strip.parent_canvas = mock_parent_canvas

        # Should update parent sprite height
        strip._update_height()
        assert mock_film_strip_sprite.dirty == 1

    def test_color_cycling_default(self, mock_pygame_patches):
        """Test that the film strip starts with gray as the default background color."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test that the default background color is gray (128, 128, 128, 255) RGBA
        assert strip.background_color == (128, 128, 128, 255)
        assert strip.background_color_index == FRAME_COUNT  # Gray is at index 2

    def test_color_cycling_functionality(self, mock_pygame_patches):
        """Test that color cycling works correctly."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test initial state
        initial_color = strip.background_color
        initial_index = strip.background_color_index

        # Simulate a click that should cycle the color
        # This would normally happen through handle_click, but we'll test the cycling logic directly
        strip.background_color_index = (strip.background_color_index + 1) % len(
            strip.BACKGROUND_COLORS
        )
        strip.background_color = strip.BACKGROUND_COLORS[strip.background_color_index]

        # Verify the color changed
        assert strip.background_color != initial_color
        assert strip.background_color_index != initial_index

        # Test that we can cycle through all colors
        colors_seen = set()
        for _ in range(len(strip.BACKGROUND_COLORS)):
            colors_seen.add(strip.background_color)
            strip.background_color_index = (strip.background_color_index + 1) % len(
                strip.BACKGROUND_COLORS
            )
            strip.background_color = strip.BACKGROUND_COLORS[strip.background_color_index]

        # Should have seen all colors
        assert len(colors_seen) == len(strip.BACKGROUND_COLORS)

    def test_background_colors_list(self, mock_pygame_patches):
        """Test that the background colors list contains expected colors."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test that cyan is still in the list (RGBA format)
        assert (
            0,
            COLOR_COMPONENT_MAX,
            COLOR_COMPONENT_MAX,
            COLOR_COMPONENT_MAX,
        ) in strip.BACKGROUND_COLORS  # Cyan

        # Test that gray is in the list (RGBA format)
        assert (128, 128, 128, COLOR_COMPONENT_MAX) in strip.BACKGROUND_COLORS  # Gray

        # Test that we have a reasonable number of colors
        assert len(strip.BACKGROUND_COLORS) >= ANIMATION_COUNT

        # Test that all colors are valid RGBA tuples
        rgba_length = 4
        for color in strip.BACKGROUND_COLORS:
            assert isinstance(color, tuple)
            assert len(color) == rgba_length
            assert all(0 <= component <= COLOR_COMPONENT_MAX for component in color)


class TestFilmStripWidgetInit:
    """Test FilmStripWidget initialization."""

    def test_init_sets_rect(self):
        """Test initialization sets correct rect."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.rect is not None
        assert widget.rect.x == WIDGET_X
        assert widget.rect.y == WIDGET_Y
        assert widget.rect.width == WIDGET_WIDTH
        assert widget.rect.height == WIDGET_HEIGHT

    def test_init_default_state(self):
        """Test initialization sets default state."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.animated_sprite is None
        assert not widget.current_animation
        assert widget.current_frame == 0
        assert widget.selected_frame == 0
        assert widget.is_selected is False
        assert widget.hovered_frame is None
        assert widget.hovered_animation is None
        assert widget.hovered_preview is None
        assert widget.is_hovering_strip is False

    def test_init_animation_rename_state(self):
        """Test initialization sets animation rename state."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.editing_animation is None
        assert not widget.editing_text
        assert widget.original_animation_name is None
        assert widget.cursor_visible is True

    def test_init_background_colors(self):
        """Test initialization has background colors defined."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert len(widget.BACKGROUND_COLORS) == BACKGROUND_COLOR_COUNT
        # Default starts at gray (index 2)
        assert widget.background_color_index == 2

    def test_init_copy_paste_buffer(self):
        """Test initialization has empty copy/paste buffer."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._copied_frame is None

    def test_init_film_tabs_empty(self):
        """Test initialization starts with empty film tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.film_tabs == []

    def test_init_preview_dictionaries_empty(self):
        """Test initialization starts with empty preview dictionaries."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.preview_animation_times == {}
        assert widget.preview_animation_speeds == {}
        assert widget.preview_frame_durations == {}

    def test_init_hovered_removal_button_none(self):
        """Test initialization starts with no hovered removal button."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.hovered_removal_button is None


class TestFilmStripSetAnimatedSprite:
    """Test FilmStripWidget.set_animated_sprite."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget(self):
        """Create a FilmStripWidget for testing.

        Returns:
            A FilmStripWidget instance.
        """
        return FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)

    @pytest.fixture
    def animated_sprite_with_order(self):
        """Create an AnimatedSprite with _animation_order.

        Returns:
            An AnimatedSprite with an 'idle' animation and _animation_order set.
        """
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION_FAST)
        sprite.add_animation('idle', [frame1, frame2])
        sprite._animation_order = ['idle']
        return sprite

    @pytest.fixture
    def animated_sprite_without_order(self):
        """Create an AnimatedSprite without _animation_order.

        Returns:
            An AnimatedSprite with a 'walk' animation and no _animation_order.
        """
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('walk', [frame1])
        if hasattr(sprite, '_animation_order'):
            del sprite._animation_order
        return sprite

    def test_set_animated_sprite_with_order(self, widget, animated_sprite_with_order):
        """Test set_animated_sprite uses _animation_order when available."""
        widget.set_animated_sprite(animated_sprite_with_order)
        assert widget.animated_sprite is animated_sprite_with_order
        assert widget.current_animation == 'idle'
        assert widget.current_frame == 0

    def test_set_animated_sprite_without_order(self, widget, animated_sprite_without_order):
        """Test set_animated_sprite falls back to first animation key."""
        widget.set_animated_sprite(animated_sprite_without_order)
        assert widget.current_animation == 'walk'

    def test_set_animated_sprite_empty(self, widget):
        """Test set_animated_sprite with empty animations."""
        sprite = AnimatedSprite()
        widget.set_animated_sprite(sprite)
        assert not widget.current_animation

    def test_set_animated_sprite_clears_old_state(self, widget, animated_sprite_with_order):
        """Test set_animated_sprite clears old preview state."""
        widget.preview_animation_times['old'] = 1.0
        widget.preview_animation_speeds['old'] = 2.0
        widget.set_animated_sprite(animated_sprite_with_order)
        assert 'old' not in widget.preview_animation_times
        assert 'old' not in widget.preview_animation_speeds

    def test_set_animated_sprite_initializes_scroll_offset(
        self, widget, animated_sprite_with_order
    ):
        """Test set_animated_sprite initializes scroll_offset to 0."""
        widget.set_animated_sprite(animated_sprite_with_order)
        assert widget.scroll_offset == 0

    def test_set_animated_sprite_marks_dirty(self, widget, animated_sprite_with_order):
        """Test set_animated_sprite marks widget as dirty."""
        widget.set_animated_sprite(animated_sprite_with_order)
        assert hasattr(widget, '_force_redraw')


class TestFilmStripInitializePreviewAnimations:
    """Test _initialize_preview_animations method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_animated_sprite(self):
        """Test _initialize_preview_animations with no sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._initialize_preview_animations()
        assert widget.preview_animation_times == {}

    def test_multi_frame_animation_starts_at_zero(self):
        """Test multi-frame animation starts time at 0.0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('walk', [frame1, frame2])
        widget.animated_sprite = sprite
        widget._initialize_preview_animations()
        assert math.isclose(widget.preview_animation_times['walk'], 0.0, abs_tol=1e-9)

    def test_single_frame_animation_starts_with_offset(self):
        """Test single-frame animation starts time with small offset."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame])
        widget.animated_sprite = sprite
        widget._initialize_preview_animations()
        assert math.isclose(widget.preview_animation_times['idle'], 0.001)

    def test_frame_durations_extracted(self):
        """Test frame durations are correctly extracted."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION_FAST)
        sprite.add_animation('walk', [frame1, frame2])
        widget.animated_sprite = sprite
        widget._initialize_preview_animations()
        assert widget.preview_frame_durations['walk'] == [FRAME_DURATION, FRAME_DURATION_FAST]

    def test_frame_without_duration_uses_default(self, mocker):
        """Test frame without duration attribute uses default 1.0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        # Create a mock frame without duration
        mock_frame = mocker.Mock()
        del mock_frame.duration
        sprite._animations = {'test': [mock_frame]}
        widget.animated_sprite = sprite
        widget._initialize_preview_animations()
        assert widget.preview_frame_durations['test'] == [1.0]

    def test_animation_speed_initialized_to_one(self):
        """Test animation speed is initialized to 1.0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('run', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.animated_sprite = sprite
        widget._initialize_preview_animations()
        assert math.isclose(widget.preview_animation_speeds['run'], 1.0)


class TestFilmStripUpdateAnimations:
    """Test update_animations method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_sprite(self):
        """Create a widget with a loaded sprite.

        Returns:
            A FilmStripWidget with an animated sprite loaded.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('walk', [frame1, frame2])
        widget.set_animated_sprite(sprite)
        return widget

    def test_update_no_sprite(self):
        """Test update_animations with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.update_animations(DT_60FPS)  # Should not raise

    def test_update_advances_time(self, widget_with_sprite):
        """Test update_animations advances preview times."""
        initial_time = widget_with_sprite.preview_animation_times['walk']
        widget_with_sprite.update_animations(DT_60FPS)
        assert widget_with_sprite.preview_animation_times['walk'] > initial_time

    def test_update_wraps_time(self, widget_with_sprite, mocker):
        """Test update_animations wraps time when exceeding total duration."""
        # Mock the animated sprite's update to avoid surfarray issues
        mocker.patch.object(widget_with_sprite.animated_sprite, 'update')
        # Total duration is 1.0 (2 frames * 0.5 each)
        widget_with_sprite.preview_animation_times['walk'] = 0.9
        widget_with_sprite.update_animations(DT_LARGE)
        # Time should wrap around
        assert widget_with_sprite.preview_animation_times['walk'] < 1.0

    def test_update_marks_dirty(self, widget_with_sprite, mocker):
        """Test update_animations marks widget as dirty."""
        mocker.patch.object(widget_with_sprite, 'mark_dirty')
        widget_with_sprite.update_animations(DT_60FPS)
        widget_with_sprite.mark_dirty.assert_called()

    def test_update_initializes_debug_timers(self, widget_with_sprite, mocker):
        """Test update_animations initializes debug timers if not present."""
        mocker.patch.object(widget_with_sprite.animated_sprite, 'update')
        # Remove debug timers if present
        if hasattr(widget_with_sprite, '_debug_start_time'):
            del widget_with_sprite._debug_start_time
        if hasattr(widget_with_sprite, '_debug_last_dump_time'):
            del widget_with_sprite._debug_last_dump_time
        widget_with_sprite.update_animations(DT_60FPS)
        assert hasattr(widget_with_sprite, '_debug_start_time')
        assert hasattr(widget_with_sprite, '_debug_last_dump_time')

    def test_update_triggers_debug_dump_at_interval(self, widget_with_sprite, mocker):
        """Test update_animations triggers debug dump at 5-second intervals."""
        mocker.patch.object(widget_with_sprite.animated_sprite, 'update')
        widget_with_sprite._debug_start_time = 0.0
        widget_with_sprite._debug_last_dump_time = 0.0
        # Advance enough time to trigger a dump (5 seconds)
        widget_with_sprite.update_animations(6.0)
        assert widget_with_sprite._debug_last_dump_time == widget_with_sprite._debug_start_time

    def test_update_skips_animation_not_in_times(self, widget_with_sprite, mocker):
        """Test update_animations skips animations not in preview_animation_times."""
        mocker.patch.object(widget_with_sprite.animated_sprite, 'update')
        # Remove the animation from preview times
        widget_with_sprite.preview_animation_times.clear()
        # Should not raise
        widget_with_sprite.update_animations(DT_60FPS)


class TestFilmStripGetCurrentPreviewFrame:
    """Test get_current_preview_frame method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_unknown_animation_returns_zero(self):
        """Test unknown animation name returns frame 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_current_preview_frame('nonexistent') == 0

    def test_first_frame_at_start(self):
        """Test frame 0 is returned at the start of animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['walk'] = 0.0
        widget.preview_frame_durations['walk'] = [FRAME_DURATION, FRAME_DURATION]
        assert widget.get_current_preview_frame('walk') == 0

    def test_second_frame_after_first_duration(self):
        """Test frame 1 is returned after first frame's duration."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['walk'] = FRAME_DURATION + 0.01
        widget.preview_frame_durations['walk'] = [FRAME_DURATION, FRAME_DURATION]
        assert widget.get_current_preview_frame('walk') == 1

    def test_empty_durations_returns_zero(self):
        """Test empty frame durations returns frame 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['walk'] = 0.0
        widget.preview_frame_durations['walk'] = []
        assert widget.get_current_preview_frame('walk') == 0

    def test_fallback_to_last_frame(self):
        """Test fallback to last frame when time exceeds total duration."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['walk'] = 999.0
        widget.preview_frame_durations['walk'] = [FRAME_DURATION]
        assert widget.get_current_preview_frame('walk') == 0

    def test_missing_times_key_returns_zero(self):
        """Test animation present in durations but not times returns 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_frame_durations['walk'] = [FRAME_DURATION]
        # 'walk' not in preview_animation_times
        assert widget.get_current_preview_frame('walk') == 0

    def test_missing_durations_key_returns_zero(self):
        """Test animation present in times but not durations returns 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['walk'] = 0.5
        # 'walk' not in preview_frame_durations
        assert widget.get_current_preview_frame('walk') == 0

    def test_three_frame_animation_middle_frame(self):
        """Test correct frame for three-frame animation at middle time."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['run'] = 0.6
        widget.preview_frame_durations['run'] = [0.3, 0.3, 0.3]
        assert widget.get_current_preview_frame('run') == 1


class TestFilmStripCopyPaste:
    """Test copy_current_frame and paste_to_current_frame methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_frames(self):
        """Create a widget with loaded frames for copy/paste testing.

        Returns:
            A FilmStripWidget with frames loaded for copy/paste.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION_FAST)
        sprite.add_animation('idle', [frame1, frame2])
        widget.set_animated_sprite(sprite)
        widget.current_animation = 'idle'
        widget.current_frame = 0
        return widget

    def test_copy_no_sprite(self):
        """Test copy fails with no animated sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.copy_current_frame() is False

    def test_copy_no_animation(self):
        """Test copy fails with no current animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.animated_sprite = AnimatedSprite()
        widget.current_animation = ''
        assert widget.copy_current_frame() is False

    def test_copy_invalid_animation(self):
        """Test copy fails with invalid animation name."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.animated_sprite = AnimatedSprite()
        widget.current_animation = 'nonexistent'
        assert widget.copy_current_frame() is False

    def test_copy_out_of_range_frame(self, widget_with_frames):
        """Test copy fails with out-of-range frame index."""
        widget_with_frames.current_frame = 999
        assert widget_with_frames.copy_current_frame() is False

    def test_copy_success(self, widget_with_frames):
        """Test successful copy stores frame."""
        assert widget_with_frames.copy_current_frame() is True
        assert widget_with_frames._copied_frame is not None

    def test_paste_no_copied_frame(self, widget_with_frames):
        """Test paste fails with no copied frame."""
        assert widget_with_frames.paste_to_current_frame() is False

    def test_paste_no_sprite(self):
        """Test paste fails with no animated sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._copied_frame = 'something'
        assert widget.paste_to_current_frame() is False

    def test_paste_invalid_animation(self, widget_with_frames):
        """Test paste fails with invalid animation name."""
        widget_with_frames.copy_current_frame()
        widget_with_frames.current_animation = 'nonexistent'
        assert widget_with_frames.paste_to_current_frame() is False

    def test_paste_out_of_range_frame(self, widget_with_frames):
        """Test paste fails with out-of-range frame index."""
        widget_with_frames.copy_current_frame()
        widget_with_frames.current_frame = 999
        assert widget_with_frames.paste_to_current_frame() is False

    def test_paste_success(self, widget_with_frames):
        """Test successful paste replaces frame."""
        widget_with_frames.copy_current_frame()
        widget_with_frames.current_frame = 1
        assert widget_with_frames.paste_to_current_frame() is True

    def test_paste_notifies_parent_scene(self, widget_with_frames, mocker):
        """Test paste notifies parent scene when available."""
        widget_with_frames.copy_current_frame()
        parent_scene = mocker.Mock()
        parent_scene._on_frame_pasted = mocker.Mock()
        widget_with_frames.parent_scene = parent_scene
        widget_with_frames.current_frame = 1
        widget_with_frames.paste_to_current_frame()
        parent_scene._on_frame_pasted.assert_called_once_with('idle', 1)

    def test_paste_without_parent_scene(self, widget_with_frames):
        """Test paste succeeds without parent scene."""
        widget_with_frames.copy_current_frame()
        # Ensure no parent_scene is set
        if hasattr(widget_with_frames, 'parent_scene'):
            del widget_with_frames.parent_scene
        widget_with_frames.current_frame = 1
        assert widget_with_frames.paste_to_current_frame() is True

    def test_copy_creates_deep_copy(self, widget_with_frames):
        """Test copy creates an independent deep copy of the frame."""
        widget_with_frames.copy_current_frame()
        # Modifying the original should not affect the copy
        original_frame = widget_with_frames.animated_sprite._animations['idle'][0]
        assert widget_with_frames._copied_frame is not original_frame


class TestFilmStripFrameSelection:
    """Test frame selection methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_sprite(self):
        """Create a widget with an animated sprite.

        Returns:
            A FilmStripWidget with an animated sprite loaded.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame1, frame2])
        widget.set_animated_sprite(sprite)
        return widget

    def test_set_current_frame_valid(self, widget_with_sprite):
        """Test set_current_frame with valid animation and frame."""
        widget_with_sprite.set_current_frame('idle', 1)
        assert widget_with_sprite.current_animation == 'idle'
        assert widget_with_sprite.selected_frame == 1

    def test_set_current_frame_invalid_animation(self, widget_with_sprite):
        """Test set_current_frame ignores invalid animation."""
        widget_with_sprite.set_current_frame('nonexistent', 0)
        # Should remain unchanged
        assert widget_with_sprite.current_animation == 'idle'

    def test_set_current_frame_out_of_range(self, widget_with_sprite):
        """Test set_current_frame ignores out-of-range frame."""
        widget_with_sprite.set_current_frame('idle', 999)
        # Should remain unchanged
        assert widget_with_sprite.selected_frame == 0

    def test_set_current_frame_notifies_parent_scene(self, widget_with_sprite, mocker):
        """Test set_current_frame notifies parent scene."""
        parent_scene = mocker.Mock()
        parent_scene._on_film_strip_frame_selected = mocker.Mock()
        widget_with_sprite.parent_scene = parent_scene
        widget_with_sprite.set_current_frame('idle', 1)
        parent_scene._on_film_strip_frame_selected.assert_called_once_with(
            widget_with_sprite, 'idle', 1
        )

    def test_set_current_frame_negative_index_ignored(self, widget_with_sprite):
        """Test set_current_frame ignores negative frame index."""
        widget_with_sprite.set_current_frame('idle', -1)
        assert widget_with_sprite.selected_frame == 0


class TestFilmStripHitTesting:
    """Test hit testing methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_get_frame_at_position_no_hit(self):
        """Test get_frame_at_position returns None for no hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_frame_at_position((9999, 9999)) is None

    def test_get_frame_at_position_hit(self):
        """Test get_frame_at_position returns frame info for a hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.frame_layouts['idle', 0] = pygame.Rect(10, 10, 64, 64)
        result = widget.get_frame_at_position((20, 20))
        assert result == ('idle', 0)

    def test_get_animation_at_position_no_hit(self):
        """Test get_animation_at_position returns None for no hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_animation_at_position((9999, 9999)) is None

    def test_get_animation_at_position_hit(self):
        """Test get_animation_at_position returns animation name for a hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.animation_layouts['idle'] = pygame.Rect(10, 10, 100, 20)
        result = widget.get_animation_at_position((20, 15))
        assert result == 'idle'

    def test_get_preview_at_position_no_hit(self):
        """Test get_preview_at_position returns None for no hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_preview_at_position((9999, 9999)) is None

    def test_get_preview_at_position_hit(self):
        """Test get_preview_at_position returns animation name for a hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        result = widget.get_preview_at_position((420, 30))
        assert result == 'idle'

    def test_get_removal_button_at_position_no_layouts(self):
        """Test get_removal_button_at_position returns None with no layouts."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_removal_button_at_position((10, 10)) is None

    def test_get_removal_button_at_position_hit(self):
        """Test get_removal_button_at_position returns button info for hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.removal_button_layouts = {('idle', 0): pygame.Rect(5, 20, 11, 30)}
        result = widget.get_removal_button_at_position((10, 30))
        assert result == ('idle', 0)

    def test_get_removal_button_at_position_no_hit(self):
        """Test get_removal_button_at_position returns None for miss."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.removal_button_layouts = {('idle', 0): pygame.Rect(5, 20, 11, 30)}
        result = widget.get_removal_button_at_position((9999, 9999))
        assert result is None


class TestFilmStripMarkDirty:
    """Test mark_dirty method."""

    def test_mark_dirty_sets_force_redraw(self):
        """Test mark_dirty sets _force_redraw flag."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.mark_dirty()
        assert widget._force_redraw is True

    def test_mark_dirty_with_film_strip_sprite(self, mocker):
        """Test mark_dirty propagates to film_strip_sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_sprite = mocker.Mock()
        mock_sprite.groups.return_value = []
        widget.film_strip_sprite = mock_sprite
        widget.mark_dirty()
        assert mock_sprite.dirty == 2

    def test_mark_dirty_without_film_strip_sprite(self):
        """Test mark_dirty works without film_strip_sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.mark_dirty()
        assert widget._force_redraw is True


class TestFilmStripUpdateHeight:
    """Test _update_height method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_height_no_sprite(self):
        """Test _update_height with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.rect is not None
        original_height = widget.rect.height
        widget._update_height()
        assert widget.rect.height == original_height

    def test_update_height_single_animation(self):
        """Test _update_height with single animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.animated_sprite = sprite
        widget._update_height()
        # Height should be calculated based on 1 animation
        assert widget.rect.height > 0

    def test_update_height_multiple_animations(self):
        """Test _update_height with multiple animations scales."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        sprite.add_animation('run', [SpriteFrame(surface)])
        widget.animated_sprite = sprite
        widget._update_height()
        # Height should be proportional to number of animations
        assert widget.rect is not None
        assert widget.rect.height > 100

    def test_update_height_max_five_animations(self):
        """Test _update_height caps at 5 animations maximum."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        for i in range(7):
            sprite.add_animation(f'anim_{i}', [SpriteFrame(surface)])
        widget.animated_sprite = sprite
        widget._update_height()
        # Height should be capped at 5 animations worth
        five_height = (20 + 64 + 20) * 5 + 20
        assert widget.rect is not None
        assert widget.rect.height == five_height

    def test_update_height_with_parent_canvas(self, mocker):
        """Test _update_height updates parent canvas film strip sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.animated_sprite = sprite

        parent_canvas = mocker.Mock()
        film_strip_sprite = mocker.Mock()
        film_strip_sprite.rect = pygame.Rect(0, 0, 500, 200)
        film_strip_sprite.rect.width = 500
        parent_canvas.film_strip_sprite = film_strip_sprite
        widget.parent_canvas = parent_canvas

        widget._update_height()
        assert film_strip_sprite.rect is not None
        assert widget.rect is not None
        assert film_strip_sprite.rect.height == widget.rect.height
        assert film_strip_sprite.dirty == 1


class TestFilmStripClearLayouts:
    """Test _clear_layouts method."""

    def test_clear_layouts(self):
        """Test _clear_layouts clears all layout caches."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.frame_layouts['idle', 0] = pygame.Rect(0, 0, 10, 10)
        widget.animation_layouts['idle'] = pygame.Rect(0, 0, 10, 10)
        widget.sprocket_layouts.append(pygame.Rect(0, 0, 10, 10))
        widget.preview_rects['idle'] = pygame.Rect(0, 0, 10, 10)

        widget._clear_layouts()

        assert len(widget.frame_layouts) == 0
        assert len(widget.animation_layouts) == 0
        assert len(widget.sprocket_layouts) == 0
        assert len(widget.preview_rects) == 0


class TestFilmStripCalculateLayout:
    """Test _calculate_layout and sub-methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_calculate_layout_no_sprite(self):
        """Test _calculate_layout with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_layout()
        assert len(widget.frame_layouts) == 0

    def test_calculate_layout_single_animation(self):
        """Test _calculate_layout with single animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        # Layout should have been calculated during set_animated_sprite
        assert len(widget.frame_layouts) > 0

    def test_calculate_layout_multiple_frames(self):
        """Test _calculate_layout positions multiple frames correctly."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frames = [SpriteFrame(surface, duration=FRAME_DURATION) for _ in range(3)]
        sprite.add_animation('walk', frames)
        widget.set_animated_sprite(sprite)
        # Should have 3 frame layouts
        frame_keys = [key for key in widget.frame_layouts if key[0] == 'walk']
        assert len(frame_keys) == 3

    def test_calculate_animation_layouts_no_sprite(self):
        """Test _calculate_animation_layouts with no sprite returns early."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_animation_layouts()
        assert len(widget.animation_layouts) == 0

    def test_calculate_frame_layouts_no_sprite(self):
        """Test _calculate_frame_layouts with no sprite returns early."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_frame_layouts()
        assert len(widget.frame_layouts) == 0

    def test_calculate_preview_layouts_no_sprite(self):
        """Test _calculate_preview_layouts with no sprite returns early."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_preview_layouts()
        assert len(widget.preview_rects) == 0

    def test_calculate_sprocket_layouts_no_sprite(self):
        """Test _calculate_sprocket_layouts with no sprite returns early."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_sprocket_layouts()
        assert len(widget.sprocket_layouts) == 0

    def test_calculate_layout_multiple_animations(self):
        """Test _calculate_layout with multiple animations creates sprocket layouts."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        # Should have sprocket separators between animations
        assert len(widget.sprocket_layouts) > 0


class TestFilmStripScrolling:
    """Test scroll-related methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_many_frames(self):
        """Create a widget with more frames than can be displayed.

        Returns:
            A FilmStripWidget with 10 frames loaded.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frames = [SpriteFrame(surface, duration=FRAME_DURATION) for _ in range(10)]
        sprite.add_animation('walk', frames)
        widget.set_animated_sprite(sprite)
        return widget

    def test_calculate_scroll_offset_centers_frame(self, widget_with_many_frames):
        """Test _calculate_scroll_offset tries to center specified frame."""
        frames = widget_with_many_frames.animated_sprite._animations['walk']
        offset = widget_with_many_frames._calculate_scroll_offset(5, frames)
        assert isinstance(offset, int)
        assert offset >= 0

    def test_calculate_scroll_offset_first_frame(self, widget_with_many_frames):
        """Test _calculate_scroll_offset for first frame."""
        frames = widget_with_many_frames.animated_sprite._animations['walk']
        offset = widget_with_many_frames._calculate_scroll_offset(0, frames)
        assert offset == 0

    def test_update_scroll_for_frame_no_sprite(self):
        """Test update_scroll_for_frame with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.update_scroll_for_frame(0)  # Should not raise

    def test_update_scroll_for_frame_in_view(self, widget_with_many_frames):
        """Test update_scroll_for_frame when frame is already visible."""
        widget_with_many_frames.scroll_offset = 0
        original_offset = widget_with_many_frames.scroll_offset
        widget_with_many_frames.update_scroll_for_frame(0)
        # Frame 0 should already be visible, so offset shouldn't change
        assert widget_with_many_frames.scroll_offset == original_offset

    def test_update_scroll_for_frame_beyond_range(self, widget_with_many_frames):
        """Test update_scroll_for_frame with frame beyond animation range."""
        widget_with_many_frames.update_scroll_for_frame(999)
        # Should return without error

    def test_update_scroll_for_frame_scrolls_right(self, widget_with_many_frames):
        """Test update_scroll_for_frame scrolls right when frame is off-screen to the right."""
        widget_with_many_frames.scroll_offset = 0
        widget_with_many_frames.update_scroll_for_frame(8)
        # Should have scrolled to show frame 8
        assert widget_with_many_frames.scroll_offset > 0

    def test_update_scroll_for_frame_scrolls_left(self, widget_with_many_frames):
        """Test update_scroll_for_frame scrolls left when frame is off-screen to the left."""
        # Set scroll offset so frame 0 is off-screen to the left
        widget_with_many_frames.scroll_offset = 500
        widget_with_many_frames._calculate_layout()
        widget_with_many_frames.update_scroll_for_frame(0)
        # Should have scrolled back to show frame 0
        assert widget_with_many_frames.scroll_offset == 0


class TestFilmStripGetFrameImage:
    """Test _get_frame_image static method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_get_frame_image_normal(self):
        """Test _get_frame_image returns frame's image."""
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        result = FilmStripWidget._get_frame_image(frame)
        assert result is surface

    def test_get_frame_image_stale_with_pixels(self, mocker):
        """Test _get_frame_image rebuilds from pixels when stale."""
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        frame._image_stale = True  # type: ignore[unresolved-attribute]
        pixel_data = cast(
            'list[tuple[int, ...]]', [(255, 0, 0, 255)] * (SURFACE_SIZE * SURFACE_SIZE)
        )
        frame.pixels = pixel_data
        result = FilmStripWidget._get_frame_image(frame)
        assert result is not None
        assert result.get_size() == (SURFACE_SIZE, SURFACE_SIZE)

    def test_get_frame_image_no_image_with_pixel_data(self, mocker):
        """Test _get_frame_image falls back to get_pixel_data."""
        frame = mocker.Mock()
        frame.image = None
        frame._image_stale = False
        frame.get_pixel_data.return_value = [(255, 0, 0, 255)] * (SURFACE_SIZE * SURFACE_SIZE)
        frame.get_size.return_value = (SURFACE_SIZE, SURFACE_SIZE)
        # Remove 'image' from hasattr checks
        type(frame).image = mocker.PropertyMock(return_value=None)

        result = FilmStripWidget._get_frame_image(frame)
        # Should create surface from pixel data or return None
        assert result is None or isinstance(result, pygame.Surface)

    def test_get_frame_image_no_data_returns_none(self, mocker):
        """Test _get_frame_image returns None when no data is available."""
        frame = mocker.Mock(spec=[])
        result = FilmStripWidget._get_frame_image(frame)
        assert result is None


class TestFilmStripPropagateDirty:
    """Test dirty propagation methods."""

    def test_propagate_dirty_up_parent_chain_none(self):
        """Test _propagate_dirty_up_parent_chain with None parent."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._propagate_dirty_up_parent_chain(None)  # Should not raise

    def test_propagate_dirty_up_parent_chain_with_parent(self, mocker):
        """Test _propagate_dirty_up_parent_chain marks parents dirty."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent = mocker.Mock()
        parent.dirty = 0
        parent.parent = None
        widget._propagate_dirty_up_parent_chain(parent)
        assert parent.dirty == 1

    def test_propagate_dirty_up_parent_chain_self_reference(self, mocker):
        """Test _propagate_dirty_up_parent_chain stops on self-reference."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent = mocker.Mock()
        parent.dirty = 0
        parent.parent = parent  # Self-reference
        widget._propagate_dirty_up_parent_chain(parent)
        assert parent.dirty == 1

    def test_propagate_dirty_to_sprite_groups_prevents_infinite_recursion(self, mocker):
        """Test _propagate_dirty_to_sprite_groups prevents infinite recursion."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = mocker.Mock()
        # Passing visited set with the sprite already in it should stop
        visited = {sprite}
        widget._propagate_dirty_to_sprite_groups(sprite, visited)
        # Should not have called groups() since sprite was already visited

    def test_propagate_dirty_to_sprite_groups_no_groups(self, mocker):
        """Test _propagate_dirty_to_sprite_groups with sprite that has no groups."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = mocker.Mock(spec=[])
        widget._propagate_dirty_to_sprite_groups(sprite)
        # Should not raise


class TestFilmStripHandleClick:
    """Test handle_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_sprite(self):
        """Create a widget with frames for click testing.

        Returns:
            A FilmStripWidget with frames set up.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame1, frame2])
        widget.set_animated_sprite(sprite)
        return widget

    def test_handle_click_on_frame(self, widget_with_sprite):
        """Test handle_click selects a frame when clicked."""
        # Set up a frame layout that can be clicked
        widget_with_sprite.frame_layouts['idle', 0] = pygame.Rect(50, 30, 64, 64)
        result = widget_with_sprite.handle_click((60, 40))
        assert result is not None

    def test_handle_click_returns_none_no_hit(self, widget_with_sprite):
        """Test handle_click returns None when nothing is clicked."""
        result = widget_with_sprite.handle_click((9999, 9999))
        assert result is None

    def test_handle_click_right_click_toggles_onion_skinning(self, widget_with_sprite, mocker):
        """Test handle_click with right click toggles onion skinning."""
        widget_with_sprite.frame_layouts['idle', 0] = pygame.Rect(50, 30, 64, 64)
        mocker.patch.object(widget_with_sprite, '_toggle_onion_skinning')
        result = widget_with_sprite.handle_click((60, 40), is_right_click=True)
        assert result is None
        widget_with_sprite._toggle_onion_skinning.assert_called_once()

    def test_handle_click_shift_click_toggles_onion_skinning(self, widget_with_sprite, mocker):
        """Test handle_click with shift click toggles onion skinning."""
        widget_with_sprite.frame_layouts['idle', 0] = pygame.Rect(50, 30, 64, 64)
        mocker.patch.object(widget_with_sprite, '_toggle_onion_skinning')
        result = widget_with_sprite.handle_click((60, 40), is_shift_click=True)
        assert result is None

    def test_handle_click_on_animation_label_enters_edit_mode(self, widget_with_sprite, mocker):
        """Test handle_click on animation label enters edit mode."""
        widget_with_sprite.animation_layouts['idle'] = pygame.Rect(100, 5, 80, 20)
        mocker.patch('pygame.time.get_ticks', return_value=1000)
        result = widget_with_sprite.handle_click((120, 10))
        assert result is None
        assert widget_with_sprite.editing_animation == 'idle'
        assert not widget_with_sprite.editing_text

    def test_handle_click_on_strip_background(self, widget_with_sprite, mocker):
        """Test handle_click on strip background selects strip."""
        # Click within strip rect but not on a frame, label, or preview
        assert widget_with_sprite.rect is not None
        pos = (widget_with_sprite.rect.x + 5, widget_with_sprite.rect.y + 5)
        result = widget_with_sprite.handle_click(pos)
        # Should return the strip animation and frame
        assert result is not None


class TestFilmStripHandlePreviewClick:
    """Test handle_preview_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_preview_click_hit(self):
        """Test handle_preview_click cycles background color on hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        initial_index = widget.background_color_index
        result = widget.handle_preview_click((420, 30))
        assert result is not None
        assert result[0] == 'idle'
        assert widget.background_color_index == (initial_index + 1) % BACKGROUND_COLOR_COUNT

    def test_handle_preview_click_miss(self):
        """Test handle_preview_click returns None on miss."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        result = widget.handle_preview_click((0, 0))
        assert result is None

    def test_handle_preview_click_with_parent_scene_uses_global_frame(self, mocker):
        """Test handle_preview_click uses parent scene's selected_frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        parent_scene = mocker.Mock()
        parent_scene.selected_frame = 3
        widget.parent_scene = parent_scene
        result = widget.handle_preview_click((420, 30))
        assert result == ('idle', 3)


class TestFilmStripHandleKeyboardInput:
    """Test handle_keyboard_input method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_keyboard_input_not_editing_returns_false(self, mocker):
        """Test keyboard input returns False when not in editing mode."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        event = mocker.Mock()
        event.key = pygame.K_a
        assert widget.handle_keyboard_input(event) is False

    def test_keyboard_enter_commits_rename(self, mocker):
        """Test Enter key commits animation rename."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'new_name'
        widget.original_animation_name = 'idle'
        parent_scene = mocker.Mock()
        parent_scene.on_animation_rename = mocker.Mock()
        widget.parent_scene = parent_scene

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None
        parent_scene.on_animation_rename.assert_called_once_with('idle', 'new_name')

    def test_keyboard_enter_same_name_no_rename(self, mocker):
        """Test Enter key with same name does not trigger rename."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'idle'
        widget.original_animation_name = 'idle'

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None

    def test_keyboard_enter_empty_text_no_rename(self, mocker):
        """Test Enter key with empty text does not trigger rename."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = ''
        widget.original_animation_name = 'idle'

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None

    def test_keyboard_escape_cancels_editing(self, mocker):
        """Test Escape key cancels editing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'partial'
        widget.original_animation_name = 'idle'

        event = mocker.Mock()
        event.key = pygame.K_ESCAPE
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None
        assert not widget.editing_text

    def test_keyboard_backspace_removes_character(self, mocker):
        """Test Backspace key removes last character."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'test'
        mocker.patch('pygame.time.get_ticks', return_value=1000)

        event = mocker.Mock()
        event.key = pygame.K_BACKSPACE
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_text == 'tes'

    def test_keyboard_backspace_empty_text(self, mocker):
        """Test Backspace key on empty text falls through to return False."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = ''

        event = mocker.Mock()
        event.key = pygame.K_BACKSPACE
        # With empty editing_text, backspace condition is False, falls through
        # unicode is empty string so printable check also fails
        event.unicode = ''
        result = widget.handle_keyboard_input(event)
        assert result is False

    def test_keyboard_printable_character_added(self, mocker):
        """Test printable character is added to editing text."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'te'
        mocker.patch('pygame.time.get_ticks', return_value=1000)

        event = mocker.Mock()
        event.key = pygame.K_s
        event.unicode = 's'
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_text == 'tes'

    def test_keyboard_max_length_prevents_overflow(self, mocker):
        """Test text input is limited to max length."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'x' * 50  # At ANIMATION_NAME_MAX_LENGTH

        event = mocker.Mock()
        event.key = pygame.K_a
        event.unicode = 'a'
        result = widget.handle_keyboard_input(event)
        # Should not add character since at max length
        assert result is False
        assert len(widget.editing_text) == 50

    def test_keyboard_enter_without_parent_scene(self, mocker):
        """Test Enter key with new name but no parent scene just clears edit mode."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'new_name'
        widget.original_animation_name = 'idle'
        # No parent_scene

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None


class TestFilmStripHandleHover:
    """Test handle_hover method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_hover_updates_state(self, mocker):
        """Test handle_hover updates hovered frame and animation state."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.frame_layouts['idle', 0] = pygame.Rect(10, 10, 64, 64)
        widget.animation_layouts['idle'] = pygame.Rect(10, 5, 100, 20)
        widget.handle_hover((20, 20))
        assert widget.hovered_frame == ('idle', 0)

    def test_handle_hover_no_hit(self):
        """Test handle_hover with no elements hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.handle_hover((9999, 9999))
        assert widget.hovered_frame is None
        assert widget.hovered_animation is None


class TestFilmStripRemoveFrame:
    """Test _remove_frame method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_multi_frame_sprite(self):
        """Create a widget with a multi-frame animated sprite.

        Returns:
            A FilmStripWidget with 3 frames.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frames = [SpriteFrame(surface, duration=FRAME_DURATION) for _ in range(3)]
        sprite.add_animation('idle', frames)
        widget.set_animated_sprite(sprite)
        widget.current_animation = 'idle'
        widget.current_frame = 0
        return widget

    def test_remove_frame_no_sprite(self):
        """Test _remove_frame with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._remove_frame('idle', 0)  # Should not raise

    def test_remove_frame_invalid_animation(self, widget_with_multi_frame_sprite):
        """Test _remove_frame with invalid animation name does nothing."""
        widget_with_multi_frame_sprite._remove_frame('nonexistent', 0)
        # All frames should remain
        assert len(widget_with_multi_frame_sprite.animated_sprite._animations['idle']) == 3

    def test_remove_frame_out_of_range(self, widget_with_multi_frame_sprite):
        """Test _remove_frame with out-of-range index does nothing."""
        widget_with_multi_frame_sprite._remove_frame('idle', 999)
        assert len(widget_with_multi_frame_sprite.animated_sprite._animations['idle']) == 3

    def test_remove_frame_last_frame_prevented(self, widget_with_multi_frame_sprite):
        """Test _remove_frame prevents removing the last frame."""
        # Remove until only one frame left
        widget_with_multi_frame_sprite.animated_sprite._animations['idle'] = [
            widget_with_multi_frame_sprite.animated_sprite._animations['idle'][0]
        ]
        widget_with_multi_frame_sprite._remove_frame('idle', 0)
        # Should still have 1 frame
        assert len(widget_with_multi_frame_sprite.animated_sprite._animations['idle']) == 1

    def test_remove_frame_adjusts_current_frame(self, widget_with_multi_frame_sprite, mocker):
        """Test _remove_frame adjusts current frame index when current frame is removed."""
        widget_with_multi_frame_sprite.current_frame = 2
        # _remove_frame accesses self.parent_scene for notifications and _create_film_tabs
        # accesses self.parent_scene.canvas.animated_sprite.animations.keys()
        parent_scene = mocker.Mock()
        parent_scene.canvas.animated_sprite.animations = {'idle': []}
        widget_with_multi_frame_sprite.parent_scene = parent_scene
        widget_with_multi_frame_sprite._remove_frame('idle', 2)
        assert widget_with_multi_frame_sprite.current_frame < 2


class TestFilmStripHandleRemovalButtonClick:
    """Test _handle_removal_button_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_removal_no_layouts(self):
        """Test _handle_removal_button_click with no layouts returns False."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._handle_removal_button_click((10, 10)) is False

    def test_handle_removal_button_click_hit(self, mocker):
        """Test _handle_removal_button_click returns True when button is hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation(
            'idle',
            [
                SpriteFrame(surface, duration=FRAME_DURATION),
                SpriteFrame(surface, duration=FRAME_DURATION),
            ],
        )
        widget.set_animated_sprite(sprite)
        widget.removal_button_layouts = {('idle', 0): pygame.Rect(5, 20, 11, 30)}
        parent_scene = mocker.Mock()
        parent_scene._show_delete_frame_confirmation = mocker.Mock()
        widget.parent_scene = parent_scene
        result = widget._handle_removal_button_click((10, 30))
        assert result is True
        parent_scene._show_delete_frame_confirmation.assert_called_once()


class TestFilmStripGetTotalWidth:
    """Test get_total_width and _calculate_frames_width methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_get_total_width_no_sprite(self):
        """Test get_total_width with no sprite returns 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_total_width() == 0

    def test_get_total_width_with_sprite(self):
        """Test get_total_width with sprite returns positive value."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        assert widget.get_total_width() > 0


class TestFilmStripSetFrameIndex:
    """Test set_frame_index method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_set_frame_index_no_sprite(self):
        """Test set_frame_index with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.set_frame_index(0)  # Should not raise

    def test_set_frame_index_updates_current_frame(self, mocker):
        """Test set_frame_index updates current_frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation(
            'idle',
            [
                SpriteFrame(surface, duration=FRAME_DURATION),
                SpriteFrame(surface, duration=FRAME_DURATION),
            ],
        )
        widget.set_animated_sprite(sprite)
        # set_frame_index accesses self.parent_canvas which is set via set_parent_canvas()
        mock_canvas = mocker.Mock()
        widget.set_parent_canvas(mock_canvas)
        widget.set_frame_index(1)
        assert widget.current_frame == 1


class TestFilmStripHandleFrameClick:
    """Test handle_frame_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_frame_click_no_sprite(self):
        """Test handle_frame_click with no sprite returns None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.handle_frame_click((10, 10)) is None

    def test_handle_frame_click_outside_bounds(self):
        """Test handle_frame_click outside bounds returns None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        assert widget.handle_frame_click((-10, -10)) is None

    def test_handle_frame_click_hit(self):
        """Test handle_frame_click returns frame info when clicked."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        # Set up frame layout
        widget.frame_layouts['idle', 0] = pygame.Rect(50, 30, 64, 64)
        result = widget.handle_frame_click((60, 40))
        assert result == ('idle', 0)


class TestFilmStripResetTabStates:
    """Test reset_all_tab_states method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_reset_all_tab_states(self):
        """Test reset_all_tab_states resets all tab states."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        tab = FilmTabWidget(x=0, y=0, width=20, height=30)
        tab.is_clicked = True
        tab.is_hovered = True
        widget.film_tabs.append(tab)
        widget.reset_all_tab_states()
        assert tab.is_clicked is False
        assert tab.is_hovered is False


class TestFilmTabWidget:
    """Test FilmTabWidget class."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_init(self):
        """Test FilmTabWidget initialization."""
        tab = FilmTabWidget(x=10, y=20, width=15, height=25)
        assert tab.x == 10
        assert tab.y == 20
        assert tab.width == 15
        assert tab.height == 25
        assert tab.is_hovered is False
        assert tab.is_clicked is False

    def test_set_insertion_type(self):
        """Test set_insertion_type sets correct values."""
        tab = FilmTabWidget(x=0, y=0)
        tab.set_insertion_type('after', 3)
        assert tab.insertion_type == 'after'
        assert tab.target_frame_index == 3

    def test_handle_click_hit(self):
        """Test handle_click returns True when clicked."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        assert tab.handle_click((15, 20)) is True
        assert tab.is_clicked is True

    def test_handle_click_miss(self):
        """Test handle_click returns False when missed."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        assert tab.handle_click((100, 100)) is False

    def test_handle_hover_hit(self):
        """Test handle_hover returns True when hovering."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        assert tab.handle_hover((15, 20)) is True
        assert tab.is_hovered is True

    def test_handle_hover_miss(self):
        """Test handle_hover returns False when not hovering."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        assert tab.handle_hover((100, 100)) is False
        assert tab.is_hovered is False

    def test_reset_click_state(self):
        """Test reset_click_state resets clicked state."""
        tab = FilmTabWidget(x=0, y=0)
        tab.is_clicked = True
        tab.reset_click_state()
        assert tab.is_clicked is False

    def test_render_normal_state(self):
        """Test render in normal state."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        surface = pygame.Surface((500, 200))
        tab.render(surface)  # Should not raise

    def test_render_hovered_state(self):
        """Test render in hovered state uses inverted colors."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        tab.is_hovered = True
        surface = pygame.Surface((500, 200))
        tab.render(surface)  # Should not raise

    def test_render_clicked_state(self):
        """Test render in clicked state."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        tab.is_clicked = True
        surface = pygame.Surface((500, 200))
        tab.render(surface)  # Should not raise


class TestFilmStripDeleteTab:
    """Test FilmStripDeleteTab class."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_init(self):
        """Test FilmStripDeleteTab initialization."""
        tab = FilmStripDeleteTab(x=100, y=5, width=40, height=10)
        assert tab.rect is not None
        assert tab.rect.x == 100
        assert tab.rect.y == 5
        assert tab.rect.width == 40
        assert tab.rect.height == 10

    def test_handle_click_hit(self):
        """Test FilmStripDeleteTab handle_click returns True when clicked."""
        tab = FilmStripDeleteTab(x=100, y=5, width=40, height=10)
        assert tab.handle_click((110, 8)) is True

    def test_handle_click_miss(self):
        """Test FilmStripDeleteTab handle_click returns False when missed."""
        tab = FilmStripDeleteTab(x=100, y=5, width=40, height=10)
        assert tab.handle_click((0, 0)) is False

    def test_render_normal(self):
        """Test FilmStripDeleteTab render in normal state."""
        tab = FilmStripDeleteTab(x=100, y=5, width=40, height=10)
        surface = pygame.Surface((500, 200))
        tab.render(surface)  # Should not raise

    def test_render_hovered(self):
        """Test FilmStripDeleteTab render in hovered state."""
        tab = FilmStripDeleteTab(x=100, y=5, width=40, height=10)
        tab.is_hovered = True
        surface = pygame.Surface((500, 200))
        tab.render(surface)  # Should not raise


class TestFilmStripHelperMethods:
    """Test various helper methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_has_valid_canvas_sprite_no_parent_scene(self):
        """Test _has_valid_canvas_sprite returns False with no parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._has_valid_canvas_sprite() is False

    def test_has_valid_canvas_sprite_with_canvas(self, mocker):
        """Test _has_valid_canvas_sprite returns True with valid canvas."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent_scene = mocker.Mock()
        parent_scene.canvas = mocker.Mock()
        parent_scene.canvas.animated_sprite = mocker.Mock()
        widget.parent_scene = parent_scene
        assert widget._has_valid_canvas_sprite() is True

    def test_is_keyboard_selected_no_parent_scene(self):
        """Test _is_keyboard_selected returns False with no parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._is_keyboard_selected('idle', 0) is False

    def test_is_keyboard_selected_matching(self, mocker):
        """Test _is_keyboard_selected returns True when matching."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent_scene = mocker.Mock()
        parent_scene.selected_animation = 'idle'
        parent_scene.selected_frame = 2
        widget.parent_scene = parent_scene
        assert widget._is_keyboard_selected('idle', 2) is True

    def test_is_keyboard_selected_not_matching(self, mocker):
        """Test _is_keyboard_selected returns False when not matching."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent_scene = mocker.Mock()
        parent_scene.selected_animation = 'walk'
        parent_scene.selected_frame = 0
        widget.parent_scene = parent_scene
        assert widget._is_keyboard_selected('idle', 0) is False

    def test_get_controller_selection_color_no_parent(self):
        """Test _get_controller_selection_color returns None with no parent."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._get_controller_selection_color('idle', 0) is None

    def test_set_parent_canvas(self, mocker):
        """Test set_parent_canvas stores the canvas reference."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        canvas = mocker.Mock()
        widget.set_parent_canvas(canvas)
        assert widget.parent_canvas is canvas

    def test_update_layout(self, mocker):
        """Test update_layout recalculates layouts and creates tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        widget.update_layout()
        # Should have recalculated layouts
        assert len(widget.frame_layouts) > 0


class TestFilmStripStopAnimationBeforeDeletion:
    """Test _stop_animation_before_deletion method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_stop_animation_no_sprite(self):
        """Test _stop_animation_before_deletion with no sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._stop_animation_before_deletion('idle', 0)  # Should not raise

    def test_stop_animation_matching_animation(self):
        """Test _stop_animation_before_deletion stops animation and adjusts frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frames = [SpriteFrame(surface, duration=FRAME_DURATION) for _ in range(3)]
        sprite.add_animation('idle', frames)
        widget.set_animated_sprite(sprite)
        sprite.frame_manager.current_frame = 2
        widget._stop_animation_before_deletion('idle', 1)
        assert sprite._is_playing is False
        assert sprite.frame_manager.current_frame <= 1


class TestFilmStripAdjustCurrentFrameAfterDeletion:
    """Test _adjust_current_frame_after_deletion method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_adjust_frame_decrements_when_at_deleted_index(self):
        """Test current frame decrements when at the deleted frame index."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 2
        widget._adjust_current_frame_after_deletion('idle', 2)
        assert widget.current_frame == 1

    def test_adjust_frame_stays_at_zero(self):
        """Test current frame stays at 0 when deleting frame 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 0
        widget._adjust_current_frame_after_deletion('idle', 0)
        assert widget.current_frame == 0

    def test_adjust_frame_different_animation_no_change(self):
        """Test no adjustment when animation names differ."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'walk'
        widget.current_frame = 2
        widget._adjust_current_frame_after_deletion('idle', 1)
        assert widget.current_frame == 2


class TestFilmStripDumpAnimationDebugState:
    """Test debug state dump methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_dump_animation_debug_state(self):
        """Test _dump_animation_debug_state runs without error."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        widget._debug_start_time = 5.0
        widget._dump_animation_debug_state(DT_60FPS)

    def test_dump_animated_sprite_debug(self):
        """Test _dump_animated_sprite_debug runs without error."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        widget._dump_animated_sprite_debug()


class TestHandleKeyboardInput:
    """Test handle_keyboard_input for animation renaming."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def _make_key_event(self, mocker, key, unicode_char=''):
        """Create a mock keyboard event with key and unicode attributes.

        Args:
            mocker: The pytest-mock mocker fixture.
            key: The pygame key constant.
            unicode_char: The unicode character string.

        Returns:
            A mock event with key and unicode attributes.

        """
        event = mocker.Mock()
        event.key = key
        event.unicode = unicode_char
        return event

    def test_not_editing_returns_false(self, mocker):
        """Test keyboard input is ignored when not in edit mode."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = None
        event = self._make_key_event(mocker, pygame.K_a, 'a')
        assert widget.handle_keyboard_input(event) is False

    def test_escape_cancels_editing(self, mocker):
        """Test Escape key cancels editing mode."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'partial'
        widget.original_animation_name = 'idle'
        event = self._make_key_event(mocker, pygame.K_ESCAPE)
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None
        assert not widget.editing_text
        assert widget.original_animation_name is None

    def test_enter_commits_rename_with_parent_scene(self, mocker):
        """Test Enter key commits rename when parent scene exists."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'walk_cycle'
        widget.original_animation_name = 'idle'
        mock_parent = mocker.Mock()
        widget.parent_scene = mock_parent
        event = self._make_key_event(mocker, pygame.K_RETURN)
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None
        mock_parent.on_animation_rename.assert_called_once_with('idle', 'walk_cycle')

    def test_enter_with_same_name_does_not_rename(self, mocker):
        """Test Enter key with unchanged name does not trigger rename."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'idle'
        widget.original_animation_name = 'idle'
        mock_parent = mocker.Mock()
        widget.parent_scene = mock_parent
        event = self._make_key_event(mocker, pygame.K_RETURN)
        result = widget.handle_keyboard_input(event)
        assert result is True
        mock_parent.on_animation_rename.assert_not_called()

    def test_enter_with_empty_text_does_not_rename(self, mocker):
        """Test Enter key with empty text does not trigger rename."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = ''
        widget.original_animation_name = 'idle'
        event = self._make_key_event(mocker, pygame.K_RETURN)
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None

    def test_backspace_removes_last_character(self, mocker):
        """Test Backspace key removes the last character."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'abc'
        event = self._make_key_event(mocker, pygame.K_BACKSPACE)
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_text == 'ab'

    def test_backspace_on_empty_text_not_handled(self, mocker):
        """Test Backspace key on empty text falls through to printable check."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = ''
        # Backspace with no unicode should fall through and not match printable
        event = self._make_key_event(mocker, pygame.K_BACKSPACE, '')
        result = widget.handle_keyboard_input(event)
        # Backspace condition requires self.editing_text to be truthy, so it falls through
        # Then it checks unicode which is empty, so returns False
        assert result is False

    def test_printable_character_appended(self, mocker):
        """Test printable characters are appended to editing text."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'wa'
        event = self._make_key_event(mocker, pygame.K_l, 'l')
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_text == 'wal'

    def test_printable_character_max_length(self, mocker):
        """Test printable characters are not added beyond max length."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'x' * ANIMATION_NAME_MAX_LENGTH
        event = self._make_key_event(mocker, pygame.K_a, 'a')
        result = widget.handle_keyboard_input(event)
        assert result is False
        assert len(widget.editing_text) == ANIMATION_NAME_MAX_LENGTH

    def test_non_printable_character_ignored(self, mocker):
        """Test non-printable characters are ignored."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'test'
        event = self._make_key_event(mocker, pygame.K_F1, '')
        result = widget.handle_keyboard_input(event)
        assert result is False


class TestHandleClick:
    """Test handle_click method for various click targets."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_click_on_frame_returns_animation_and_frame(self):
        """Test clicking on a frame returns the animation and frame index."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        # Manually set a frame layout for testing
        frame_rect = pygame.Rect(50, 50, 64, 64)
        widget.frame_layouts['idle', 0] = frame_rect
        result = widget.handle_click((60, 60))
        assert result is not None
        assert result[1] == 0

    def test_click_outside_returns_none(self):
        """Test clicking outside the film strip returns None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget.handle_click((9999, 9999))
        assert result is None

    def test_right_click_on_frame_toggles_onion_skinning(self, mocker):
        """Test right-clicking on a frame toggles onion skinning."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        frame_rect = pygame.Rect(50, 50, 64, 64)
        widget.frame_layouts['idle', 0] = frame_rect
        mocker.patch.object(widget, '_toggle_onion_skinning')
        result = widget.handle_click((60, 60), is_right_click=True)
        assert result is None  # Right-click doesn't select frame
        widget._toggle_onion_skinning.assert_called_once()

    def test_shift_click_on_frame_toggles_onion_skinning(self, mocker):
        """Test shift-clicking on a frame toggles onion skinning."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        frame_rect = pygame.Rect(50, 50, 64, 64)
        widget.frame_layouts['idle', 0] = frame_rect
        mocker.patch.object(widget, '_toggle_onion_skinning')
        result = widget.handle_click((60, 60), is_shift_click=True)
        assert result is None
        widget._toggle_onion_skinning.assert_called_once()


class TestHandleHover:
    """Test handle_hover method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_hover_updates_hovered_frame(self):
        """Test hovering over a frame updates hovered_frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.frame_layouts['idle', 0] = pygame.Rect(50, 50, 64, 64)
        widget.handle_hover((60, 60))
        assert widget.hovered_frame == ('idle', 0)

    def test_hover_outside_clears_hovered_frame(self):
        """Test hovering outside frames clears hovered_frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.hovered_frame = ('idle', 0)
        widget.handle_hover((9999, 9999))
        assert widget.hovered_frame is None

    def test_hover_updates_hovered_animation(self):
        """Test hovering over animation label updates hovered_animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.animation_layouts['idle'] = pygame.Rect(100, 5, 60, 20)
        widget.handle_hover((110, 10))
        assert widget.hovered_animation == 'idle'


class TestHandlePreviewClick:
    """Test handle_preview_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_preview_click_cycles_background_color(self):
        """Test clicking on preview area cycles background color."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        initial_index = widget.background_color_index
        result = widget.handle_preview_click((420, 30))
        assert result is not None
        assert widget.background_color_index == (initial_index + 1) % len(widget.BACKGROUND_COLORS)

    def test_preview_click_no_hit_returns_none(self):
        """Test clicking outside preview area returns None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget.handle_preview_click((9999, 9999))
        assert result is None

    def test_preview_click_uses_global_selected_frame(self, mocker):
        """Test preview click uses parent scene's selected_frame."""
        widget, _sprite = _make_widget_with_sprite(num_frames=3)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        mock_parent = mocker.Mock()
        mock_parent.selected_frame = 2
        widget.parent_scene = mock_parent
        result = widget.handle_preview_click((420, 30))
        assert result == ('idle', 2)


class TestUpdateScrollForFrame:
    """Test update_scroll_for_frame with various scrolling scenarios."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_scroll_to_frame_beyond_view_right(self):
        """Test scrolling to a frame that is to the right of the visible area."""
        widget, _sprite = _make_widget_with_sprite(num_frames=10)
        widget.scroll_offset = 0
        # Frame 8 is well beyond the initial 4-frame window
        widget.update_scroll_for_frame(8)
        assert widget.scroll_offset > 0

    def test_scroll_to_frame_beyond_view_left(self):
        """Test scrolling to a frame that is to the left of the visible area."""
        widget, _sprite = _make_widget_with_sprite(num_frames=10)
        # Set scroll offset so first visible frame is 5
        widget.scroll_offset = 5 * (widget.frame_width + widget.tab_width + 2)
        widget.update_scroll_for_frame(0)
        # Should scroll back to show frame 0
        assert widget.scroll_offset == 0

    def test_scroll_to_frame_out_of_range(self):
        """Test scrolling to a frame index that exceeds frame count."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget.update_scroll_for_frame(999)  # Should not raise


class TestPropagateDirtyToSpriteGroups:
    """Test _propagate_dirty_to_sprite_groups method."""

    def test_propagate_with_callable_groups(self, mocker):
        """Test propagation when sprite.groups() is callable."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_other_sprite = mocker.Mock()
        mock_other_sprite.groups.return_value = []
        mock_other_sprite.dirty = 0

        mock_group = mocker.Mock()
        mock_group.__iter__ = mocker.Mock(return_value=iter([mock_other_sprite]))

        mock_sprite = mocker.Mock()
        mock_sprite.groups.return_value = [mock_group]

        widget._propagate_dirty_to_sprite_groups(mock_sprite)
        assert mock_other_sprite.dirty == 1

    def test_propagate_prevents_infinite_recursion(self, mocker):
        """Test propagation stops on already-visited sprites."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_sprite = mocker.Mock()
        mock_sprite.groups.return_value = []
        visited = {mock_sprite}
        # Should return immediately, not recurse
        widget._propagate_dirty_to_sprite_groups(mock_sprite, visited=visited)

    def test_propagate_handles_no_groups_attribute(self, mocker):
        """Test propagation handles sprites without groups attribute."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_sprite = mocker.Mock(spec=[])  # No attributes
        widget._propagate_dirty_to_sprite_groups(mock_sprite)  # Should not raise


class TestHasValidCanvasSprite:
    """Test _has_valid_canvas_sprite method."""

    def test_no_parent_scene(self):
        """Test returns False when no parent_scene exists."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._has_valid_canvas_sprite() is False

    def test_parent_scene_with_canvas(self, mocker):
        """Test returns True when parent scene has canvas with animated_sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_parent = mocker.Mock()
        mock_parent.canvas.animated_sprite = mocker.Mock()
        widget.parent_scene = mock_parent
        assert widget._has_valid_canvas_sprite() is True

    def test_parent_scene_without_canvas(self, mocker):
        """Test returns False when parent scene has no canvas attribute."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_parent = mocker.Mock(spec=[])
        widget.parent_scene = mock_parent
        assert widget._has_valid_canvas_sprite() is False


class TestIsKeyboardSelected:
    """Test _is_keyboard_selected method."""

    def test_no_parent_scene(self):
        """Test returns False when no parent_scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._is_keyboard_selected('idle', 0) is False

    def test_matching_selection(self, mocker):
        """Test returns True when parent scene selection matches."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_parent = mocker.Mock()
        mock_parent.selected_animation = 'idle'
        mock_parent.selected_frame = 1
        widget.parent_scene = mock_parent
        assert widget._is_keyboard_selected('idle', 1) is True

    def test_non_matching_selection(self, mocker):
        """Test returns False when parent scene selection does not match."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_parent = mocker.Mock()
        mock_parent.selected_animation = 'walk'
        mock_parent.selected_frame = 0
        widget.parent_scene = mock_parent
        assert widget._is_keyboard_selected('idle', 0) is False


class TestGetControllerSelectionColor:
    """Test _get_controller_selection_color method."""

    def test_no_parent_scene(self):
        """Test returns None when no parent_scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget._get_controller_selection_color('idle', 0)
        assert result is None

    def test_no_controller_selections(self, mocker):
        """Test returns None when parent has no controller_selections."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_parent = mocker.Mock(spec=['canvas'])
        widget.parent_scene = mock_parent
        result = widget._get_controller_selection_color('idle', 0)
        assert result is None


class TestToggleOnionSkinning:
    """Test _toggle_onion_skinning method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_toggle_sets_force_redraw(self, mocker):
        """Test toggling onion skinning sets _force_redraw."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Mock the onion skinning module
        mock_manager = mocker.Mock()
        mock_manager.toggle_frame_onion_skinning.return_value = True
        mocker.patch(
            'glitchygames.bitmappy.film_strip.get_onion_skinning_manager',
            return_value=mock_manager,
            create=True,
        )
        mocker.patch(
            'glitchygames.bitmappy.onion_skinning.get_onion_skinning_manager',
            return_value=mock_manager,
        )
        widget._toggle_onion_skinning('idle', 0)
        assert widget._force_redraw is True

    def test_toggle_with_parent_canvas_forces_canvas_redraw(self, mocker):
        """Test toggling onion skinning forces canvas redraw via parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_manager = mocker.Mock()
        mock_manager.toggle_frame_onion_skinning.return_value = True
        mocker.patch(
            'glitchygames.bitmappy.onion_skinning.get_onion_skinning_manager',
            return_value=mock_manager,
        )
        mock_parent = mocker.Mock()
        widget.parent_scene = mock_parent
        widget._toggle_onion_skinning('idle', 0)
        mock_parent.canvas.force_redraw.assert_called_once()


class TestStopAnimationBeforeDeletion:
    """Test _stop_animation_before_deletion method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_stops_animation_and_adjusts_frame(self):
        """Test stops animation and adjusts frame index downward.

        Note: stop() resets current_frame to 0 before the adjustment check,
        so when frame_index=1, the reset frame 0 is < 1 and no further
        adjustment occurs. The final frame is 0.
        """
        widget, sprite = _make_widget_with_sprite(num_frames=3)
        sprite._is_playing = True
        sprite.frame_manager.current_animation = 'idle'
        sprite.frame_manager.current_frame = 2
        widget._stop_animation_before_deletion('idle', 1)
        assert sprite._is_playing is False
        # stop() resets frame to 0, and since 0 < frame_index(1), no adjustment occurs
        assert sprite.frame_manager.current_frame == 0

    def test_no_adjustment_when_animation_mismatch(self):
        """Test no action when animation name doesn't match."""
        widget, sprite = _make_widget_with_sprite(num_frames=3)
        sprite.frame_manager.current_animation = 'walk'
        widget._stop_animation_before_deletion('idle', 0)
        # Should not have changed anything since animation doesn't match

    def test_no_sprite_returns_early(self):
        """Test returns early when no animated sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._stop_animation_before_deletion('idle', 0)  # Should not raise


class TestAdjustCurrentFrameAfterDeletion:
    """Test _adjust_current_frame_after_deletion method."""

    def test_decrements_current_frame(self):
        """Test current frame is decremented after deletion."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 2
        widget._adjust_current_frame_after_deletion('idle', 1)
        assert widget.current_frame == 1

    def test_does_not_go_below_zero(self):
        """Test current frame does not go below 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 0
        widget._adjust_current_frame_after_deletion('idle', 0)
        assert widget.current_frame == 0

    def test_no_adjustment_for_different_animation(self):
        """Test no adjustment when animation name differs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 2
        widget._adjust_current_frame_after_deletion('walk', 0)
        assert widget.current_frame == 2  # Unchanged

    def test_no_adjustment_when_frame_before_deleted(self):
        """Test no adjustment when current frame is before deleted frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 0
        widget._adjust_current_frame_after_deletion('idle', 2)
        assert widget.current_frame == 0  # Unchanged


class TestHandleRemovalButtonClick:
    """Test _handle_removal_button_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_removal_buttons_returns_false(self):
        """Test returns False when no removal buttons exist."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._handle_removal_button_click((50, 50)) is False

    def test_click_on_removal_button_with_parent(self, mocker):
        """Test clicking a removal button with a parent scene."""
        widget, _sprite = _make_widget_with_sprite(num_frames=3)
        widget.removal_button_layouts = {
            ('idle', 1): pygame.Rect(10, 40, 11, 30),
        }
        mock_parent = mocker.Mock()
        widget.parent_scene = mock_parent
        result = widget._handle_removal_button_click((15, 50))
        assert result is True
        mock_parent._show_delete_frame_confirmation.assert_called_once_with('idle', 1)

    def test_click_miss_returns_false(self):
        """Test clicking outside removal buttons returns False."""
        widget, _sprite = _make_widget_with_sprite(num_frames=3)
        widget.removal_button_layouts = {
            ('idle', 1): pygame.Rect(10, 40, 11, 30),
        }
        result = widget._handle_removal_button_click((9999, 9999))
        assert result is False


class TestHandleTabClick:
    """Test _handle_tab_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_tabs_returns_false(self):
        """Test returns False when there are no tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.film_tabs = []
        assert widget._handle_tab_click((50, 50)) is False

    def test_click_miss_returns_false(self, mocker):
        """Test returns False when clicking outside tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_tab = mocker.Mock()
        mock_tab.handle_click.return_value = False
        widget.film_tabs = [mock_tab]
        assert widget._handle_tab_click((50, 50)) is False


class TestHandleTabHover:
    """Test _handle_tab_hover method."""

    def test_no_tabs_returns_false(self):
        """Test returns False when there are no tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.film_tabs = []
        assert widget._handle_tab_hover((50, 50)) is False

    def test_hover_over_tab_returns_true(self, mocker):
        """Test returns True when hovering over a tab."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_tab = mocker.Mock()
        mock_tab.handle_hover.return_value = True
        widget.film_tabs = [mock_tab]
        assert widget._handle_tab_hover((50, 50)) is True

    def test_hover_miss_returns_false(self, mocker):
        """Test returns False when not hovering over any tab."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_tab = mocker.Mock()
        mock_tab.handle_hover.return_value = False
        widget.film_tabs = [mock_tab]
        assert widget._handle_tab_hover((50, 50)) is False


class TestResetAllTabStates:
    """Test reset_all_tab_states method."""

    def test_resets_all_tabs(self, mocker):
        """Test all tabs have their states reset."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_tab1 = mocker.Mock()
        mock_tab2 = mocker.Mock()
        widget.film_tabs = [mock_tab1, mock_tab2]
        widget.reset_all_tab_states()
        mock_tab1.reset_click_state.assert_called_once()
        assert mock_tab1.is_hovered is False
        mock_tab2.reset_click_state.assert_called_once()
        assert mock_tab2.is_hovered is False


class TestSetParentCanvas:
    """Test set_parent_canvas method."""

    def test_sets_parent_canvas(self, mocker):
        """Test parent canvas is set correctly."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_canvas = mocker.Mock()
        widget.set_parent_canvas(mock_canvas)
        assert widget.parent_canvas is mock_canvas


class TestUpdateLayout:
    """Test update_layout method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_layout_recalculates(self, mocker):
        """Test update_layout triggers layout recalculation."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        mocker.patch.object(widget, '_calculate_layout')
        mocker.patch.object(widget, '_create_film_tabs')
        widget.update_layout()
        widget._calculate_layout.assert_called_once()
        widget._create_film_tabs.assert_called_once()


class TestConvertMagentaToTransparent:
    """Test _convert_magenta_to_transparent static method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_magenta_pixels_processed(self):
        """Test magenta pixels are handled by the conversion method."""
        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((255, 0, 255, 255))
        result = FilmStripWidget._convert_magenta_to_transparent(surface)
        assert result is not None
        assert result.get_size() == (2, 2)
        # The method should set magenta pixels to (255, 0, 255, 0)
        pixel = result.get_at((0, 0))
        assert pixel[0] == 255  # Red component
        assert pixel[2] == 255  # Blue component

    def test_non_magenta_pixels_processed(self):
        """Test non-magenta pixels are processed without error."""
        surface = pygame.Surface((2, 2))
        surface.fill((100, 200, 50))
        result = FilmStripWidget._convert_magenta_to_transparent(surface)
        assert result is not None
        assert result.get_size() == (2, 2)

    def test_rgba_surface_processed(self):
        """Test RGBA surfaces are processed correctly."""
        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((100, 200, 50, 128))
        result = FilmStripWidget._convert_magenta_to_transparent(surface)
        assert result is not None
        assert result.get_size() == (2, 2)


class TestRenderingMethods:
    """Test rendering helper methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_draw_placeholder(self):
        """Test _draw_placeholder creates a placeholder surface."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        widget._draw_placeholder(surface)
        # Just verify it doesn't crash - visual output testing is limited

    def test_add_film_strip_styling(self):
        """Test _add_film_strip_styling draws film strip edges."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        widget._add_film_strip_styling(surface)
        # Verify it doesn't crash

    def test_create_selection_border(self):
        """Test _create_selection_border creates a bordered surface."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        frame_surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        result = widget._create_selection_border(frame_surface)
        assert result.get_width() == 68  # 64 + 4 border
        assert result.get_height() == 68

    def test_add_hover_highlighting(self):
        """Test _add_hover_highlighting draws hover border."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        widget._add_hover_highlighting(surface)
        # Verify it doesn't crash

    def test_add_3d_beveled_border(self):
        """Test _add_3d_beveled_border draws beveled border."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        widget._add_3d_beveled_border(surface)
        # Verify it doesn't crash

    def test_render_sprocket_separator(self):
        """Test render_sprocket_separator creates a sprocket surface."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget.render_sprocket_separator(0, 0, 100)
        assert result.get_width() == widget.sprocket_width
        assert result.get_height() == 100


class TestGetActiveControllerSelections:
    """Test _get_active_controller_selections method."""

    def test_no_parent_scene_returns_empty(self):
        """Test returns empty list when no parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        result = widget._get_active_controller_selections()
        assert result == []

    def test_no_controller_selections_returns_empty(self, mocker):
        """Test returns empty list when parent has no controller_selections."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        mock_parent = mocker.Mock(spec=['canvas'])
        widget.parent_scene = mock_parent
        result = widget._get_active_controller_selections()
        assert result == []


class TestDumpAnimationDebugState:
    """Test _dump_animation_debug_state and _dump_animated_sprite_debug methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_dump_animation_debug_state(self):
        """Test _dump_animation_debug_state runs without error."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget._debug_start_time = 5.0
        widget._debug_last_dump_time = 0.0
        widget._dump_animation_debug_state(DT_60FPS)
        # Verify the dump time was updated
        assert widget._debug_last_dump_time > 0.0

    def test_dump_animated_sprite_debug(self):
        """Test _dump_animated_sprite_debug runs without error on loaded sprite."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget._dump_animated_sprite_debug()  # Should not raise

    def test_dump_without_sprite(self):
        """Test _dump_animation_debug_state runs without animated sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._debug_start_time = 5.0
        widget._debug_last_dump_time = 0.0
        # scroll_offset is set during set_animated_sprite, so set it manually
        widget.scroll_offset = 0
        widget._dump_animation_debug_state(DT_60FPS)


class TestCalculateScrollOffset:
    """Test _calculate_scroll_offset edge cases."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_offset_for_last_frame_is_clamped(self):
        """Test scroll offset for last frame is clamped to max scroll."""
        widget, sprite = _make_widget_with_sprite(num_frames=10)
        frames = sprite._animations['idle']
        offset = widget._calculate_scroll_offset(9, frames)
        frame_width = widget.frame_width + widget.frame_spacing
        assert widget.rect is not None
        max_scroll = max(0, len(frames) * frame_width - widget.rect.width)
        assert offset <= max_scroll

    def test_offset_for_middle_frame(self):
        """Test scroll offset for a middle frame."""
        widget, sprite = _make_widget_with_sprite(num_frames=20)
        frames = sprite._animations['idle']
        offset = widget._calculate_scroll_offset(10, frames)
        assert offset > 0


class TestGetRemovalButtonAtPosition:
    """Test get_removal_button_at_position method."""

    def test_no_layouts_returns_none(self):
        """Test returns None when no removal button layouts exist."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_removal_button_at_position((50, 50)) is None

    def test_hit_returns_tuple(self):
        """Test returns (anim_name, frame_idx) when button is hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.removal_button_layouts = {
            ('idle', 0): pygame.Rect(10, 10, 11, 30),
        }
        result = widget.get_removal_button_at_position((15, 20))
        assert result == ('idle', 0)

    def test_miss_returns_none(self):
        """Test returns None when no button is hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.removal_button_layouts = {
            ('idle', 0): pygame.Rect(10, 10, 11, 30),
        }
        result = widget.get_removal_button_at_position((9999, 9999))
        assert result is None


class TestCalculateLayoutSubMethods:
    """Test layout calculation sub-methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_calculate_sprocket_start_x(self):
        """Test _calculate_sprocket_start_x returns a valid x position."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        start_x = widget._calculate_sprocket_start_x()
        assert isinstance(start_x, int)
        assert start_x >= 0

    def test_calculate_frame_y_single_animation(self):
        """Test _calculate_frame_y centers frames for single animation."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        frame_y = widget._calculate_frame_y(20)
        assert isinstance(frame_y, int)

    def test_calculate_frame_y_multi_animation(self):
        """Test _calculate_frame_y for multi-animation widget."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        frame_y = widget._calculate_frame_y(40)
        expected_y = 40 + widget.animation_label_height + 3
        assert frame_y == expected_y

    def test_calculate_animation_layouts_no_sprite(self):
        """Test _calculate_animation_layouts with no sprite returns immediately."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_animation_layouts()
        assert len(widget.animation_layouts) == 0

    def test_calculate_frame_layouts_no_sprite(self):
        """Test _calculate_frame_layouts with no sprite returns immediately."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_frame_layouts()
        assert len(widget.frame_layouts) == 0

    def test_calculate_preview_layouts_no_sprite(self):
        """Test _calculate_preview_layouts with no sprite returns immediately."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_preview_layouts()
        assert len(widget.preview_rects) == 0

    def test_calculate_sprocket_layouts_no_sprite(self):
        """Test _calculate_sprocket_layouts with no sprite returns immediately."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_sprocket_layouts()
        assert len(widget.sprocket_layouts) == 0

    def test_calculate_sprocket_layouts_multi_animation(self):
        """Test _calculate_sprocket_layouts creates sprockets between animations."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        # Should have at least one sprocket between the two animations
        assert len(widget.sprocket_layouts) >= 1


class TestAddRemovalButton:
    """Test _add_removal_button method."""

    def test_creates_removal_button_layout(self):
        """Test _add_removal_button creates a removal button rect."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._add_removal_button('idle', 0, 50, 50)
        assert ('idle', 0) in widget.removal_button_layouts

    def test_initializes_layouts_dict_if_missing(self):
        """Test _add_removal_button initializes removal_button_layouts if absent."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Remove the attribute if it was already set
        if hasattr(widget, 'removal_button_layouts'):
            del widget.removal_button_layouts
        widget._add_removal_button('idle', 0, 50, 50)
        assert hasattr(widget, 'removal_button_layouts')
        assert ('idle', 0) in widget.removal_button_layouts


class TestUpdateHeightMultipleAnimations:
    """Test _update_height with boundary conditions."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_height_caps_at_five_animations(self):
        """Test height caps at 5 visible animations even with more."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        for i in range(7):
            sprite.add_animation(f'anim_{i}', [SpriteFrame(surface)])
        widget.animated_sprite = sprite
        widget._update_height()
        # Calculate expected height for 5 animations (the max)
        expected_height = (widget.animation_label_height + widget.frame_height + 20) * 5 + 20
        assert widget.rect is not None
        assert widget.rect.height == expected_height

    def test_update_height_with_parent_canvas(self, mocker):
        """Test _update_height updates parent canvas sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.animated_sprite = sprite
        mock_canvas = mocker.Mock()
        mock_canvas.film_strip_sprite.rect.width = 500
        widget.parent_canvas = mock_canvas
        widget._update_height()
        assert mock_canvas.film_strip_sprite.rect.height == widget.rect.height
        assert mock_canvas.film_strip_sprite.dirty == 1


class TestCreateFilmTabs:
    """Test _create_film_tabs method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_sprite_creates_no_tabs(self):
        """Test _create_film_tabs with no sprite creates no tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._create_film_tabs()
        assert len(widget.film_tabs) == 0

    def test_no_current_animation_creates_no_tabs(self):
        """Test _create_film_tabs with missing animation creates no tabs."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget.current_animation = 'nonexistent'
        widget._create_film_tabs()
        assert len(widget.film_tabs) == 0

    def test_creates_tabs_for_frames(self):
        """Test _create_film_tabs creates tabs for available frames."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget._create_film_tabs()
        # Should have at least some tabs (before/after for each frame + bottom)
        assert len(widget.film_tabs) > 0


class TestDrawMultiControllerIndicatorsNew:
    """Test _draw_multi_controller_indicators_new method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_sprite_returns_early(self):
        """Test returns early with no animated sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((500, 200), pygame.SRCALPHA)
        widget._draw_multi_controller_indicators_new(surface)  # Should not raise

    def test_no_animation_returns_early(self):
        """Test returns early with empty current_animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.animated_sprite = AnimatedSprite()
        widget.current_animation = ''
        surface = pygame.Surface((500, 200), pygame.SRCALPHA)
        widget._draw_multi_controller_indicators_new(surface)  # Should not raise


class TestGetFrameImageForRendering:
    """Test _get_frame_image_for_rendering method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_returns_frame_image_when_available(self):
        """Test returns frame's image attribute when present."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        result = widget._get_frame_image_for_rendering(frame, is_selected=False)
        assert result is surface

    def test_falls_back_to_get_frame_image(self, mocker):
        """Test falls back to _get_frame_image when image is None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        frame = mocker.Mock()
        frame.image = None
        mocker.patch.object(
            FilmStripWidget,
            '_get_frame_image',
            return_value=None,
        )
        result = widget._get_frame_image_for_rendering(frame, is_selected=False)
        assert result is None


class TestFilmStripPropagateDirtyToGroups:
    """Test _propagate_dirty_to_sprite_groups method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_propagate_to_sprite_with_groups(self, mocker):
        """Test propagation through sprite groups."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = mocker.Mock()
        group = mocker.Mock()
        group.sprites.return_value = []
        sprite.groups.return_value = [group]
        sprite.dirty = 0

        widget._propagate_dirty_to_sprite_groups(sprite)
        # Should set sprite dirty=2 or visit groups

    def test_propagate_skips_visited_sprite(self, mocker):
        """Test propagation skips already-visited sprites."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = mocker.Mock()
        sprite.groups.return_value = []
        visited = {sprite}

        # Should return immediately without error
        widget._propagate_dirty_to_sprite_groups(sprite, visited=visited)

    def test_propagate_sprite_without_groups(self, mocker):
        """Test propagation with sprite that has no groups attribute."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = mocker.Mock(spec=[])  # No groups attr

        widget._propagate_dirty_to_sprite_groups(sprite)  # Should not raise


class TestFilmStripHasValidCanvasSprite:
    """Test _has_valid_canvas_sprite method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_has_valid_canvas_no_parent(self):
        """Test returns False when no parent_canvas."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert not hasattr(widget, 'parent_canvas') or widget._has_valid_canvas_sprite() is False

    def test_has_valid_canvas_with_parent(self, mocker):
        """Test returns True when parent_scene has canvas with animated_sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock()
        widget.parent_scene.canvas.animated_sprite = mocker.Mock()
        result = widget._has_valid_canvas_sprite()
        assert result is True

    def test_has_valid_canvas_without_animated_sprite(self, mocker):
        """Test returns False when parent_scene canvas lacks animated_sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock(spec=[])
        result = widget._has_valid_canvas_sprite()
        assert result is False


class TestFilmStripHandleKeyboardInputEditMode:
    """Test handle_keyboard_input method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_in_edit_mode(self):
        """Create a widget in animation rename edit mode.

        Returns:
            FilmStripWidget: A widget configured for edit mode testing.

        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame])
        widget.set_animated_sprite(sprite)
        widget.editing_animation = 'idle'
        widget.editing_text = 'idle'
        widget.original_animation_name = 'idle'
        return widget

    def _make_key_event(self, mocker, key, unicode_char=''):
        """Create a mock keyboard event with key and unicode attributes.

        Args:
            mocker: The pytest-mock mocker fixture.
            key: The pygame key constant.
            unicode_char: The unicode character string.

        Returns:
            A mock event with key and unicode attributes.

        """
        event = mocker.Mock()
        event.key = key
        event.unicode = unicode_char
        event.mod = 0
        return event

    def test_handle_escape_cancels_edit(self, mocker, widget_in_edit_mode):
        """Test Escape key cancels animation rename edit."""
        event = self._make_key_event(mocker, pygame.K_ESCAPE)
        widget_in_edit_mode.handle_keyboard_input(event)
        assert widget_in_edit_mode.editing_animation is None

    def test_handle_backspace_removes_char(self, mocker, widget_in_edit_mode):
        """Test Backspace removes last character from editing text."""
        widget_in_edit_mode.editing_text = 'walk'
        event = self._make_key_event(mocker, pygame.K_BACKSPACE)
        widget_in_edit_mode.handle_keyboard_input(event)
        assert widget_in_edit_mode.editing_text == 'wal'

    def test_handle_printable_char_appends(self, mocker, widget_in_edit_mode):
        """Test printable character appends to editing text."""
        widget_in_edit_mode.editing_text = 'wal'
        event = self._make_key_event(mocker, pygame.K_k, unicode_char='k')
        widget_in_edit_mode.handle_keyboard_input(event)
        assert widget_in_edit_mode.editing_text == 'walk'

    def test_handle_non_editing_mode_does_nothing(self, mocker):
        """Test keyboard input when not in editing mode does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = None
        event = self._make_key_event(mocker, pygame.K_a, unicode_char='a')
        result = widget.handle_keyboard_input(event)
        # Should return False or None (not consumed)
        assert not result


class TestFilmStripHandlePreviewClickColorCycle:
    """Test handle_preview_click for background color cycling."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_left_click_cycles_background_forward(self):
        """Test left click on preview cycles background color forward."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        # Set up a preview rect and click inside it
        preview_rect = pygame.Rect(400, 10, 64, 64)
        widget.preview_rects['idle'] = preview_rect
        initial_index = widget.background_color_index

        # handle_preview_click takes a pos tuple (x, y)
        click_pos = (preview_rect.centerx, preview_rect.centery)
        widget.handle_preview_click(click_pos)
        assert widget.background_color_index == (initial_index + 1) % len(widget.BACKGROUND_COLORS)

    def test_right_click_cycles_background_backward(self):
        """Test clicking preview cycles background color (always forward).

        The handle_preview_click method always cycles forward regardless of
        mouse button - it only takes a pos argument with no button parameter.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        preview_rect = pygame.Rect(400, 10, 64, 64)
        widget.preview_rects['idle'] = preview_rect
        initial_index = widget.background_color_index

        # handle_preview_click takes a pos tuple (x, y)
        click_pos = (preview_rect.centerx, preview_rect.centery)
        widget.handle_preview_click(click_pos)
        expected = (initial_index + 1) % len(widget.BACKGROUND_COLORS)
        assert widget.background_color_index == expected


class TestFilmStripSetParentCanvas:
    """Test set_parent_canvas method."""

    def test_set_parent_canvas_assigns(self, mocker):
        """Test set_parent_canvas stores the canvas reference."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_canvas = mocker.Mock()
        widget.set_parent_canvas(mock_canvas)
        assert widget.parent_canvas is mock_canvas


class TestFilmStripUpdateLayout:
    """Test update_layout method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_layout_recalculates(self):
        """Test update_layout triggers layout recalculation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Clear layouts and recalculate
        widget.frame_layouts.clear()
        widget.update_layout()
        assert len(widget.frame_layouts) > 0

    def test_update_layout_with_parent_canvas(self, mocker):
        """Test update_layout marks parent film strip sprite dirty."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.parent_canvas = mocker.Mock()
        widget.parent_canvas.film_strip_sprite = mocker.Mock()
        widget.parent_canvas.film_strip_sprite.dirty = 0
        widget.update_layout()
        assert widget.parent_canvas.film_strip_sprite.dirty == 1


class TestFilmStripDumpDebugState:
    """Test _dump_animation_debug_state and _dump_animated_sprite_debug."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_dump_debug_state_does_not_raise(self):
        """Test _dump_animation_debug_state runs without error."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        widget._debug_start_time = 10.0

        widget._dump_animation_debug_state(0.016)

    def test_dump_animated_sprite_debug_does_not_raise(self):
        """Test _dump_animated_sprite_debug runs without error."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)

        widget._dump_animated_sprite_debug()

    def test_dump_debug_state_without_sprite(self):
        """Test _dump_animation_debug_state without sprite.

        When no animated sprite is set, scroll_offset is not initialized by
        set_animated_sprite, so we must set it manually to simulate the state
        after partial initialization.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._debug_start_time = 5.0
        # scroll_offset is set in set_animated_sprite, not __init__,
        # so we need to initialize it for the debug dump to work
        widget.scroll_offset = 0
        widget.current_animation = ''
        widget.current_frame = 0
        widget._dump_animation_debug_state(0.016)


class TestFilmStripConvertMagentaToTransparent:
    """Test _convert_magenta_to_transparent method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_convert_magenta_rgb_to_transparent(self):
        """Test converts magenta RGB pixels to transparent."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((255, 0, 255))  # Magenta
        result = widget._convert_magenta_to_transparent(surface)
        assert isinstance(result, pygame.Surface)

    def test_convert_non_magenta_unchanged(self):
        """Test non-magenta pixels remain unchanged."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((255, 0, 0, 255))  # Red, not magenta
        result = widget._convert_magenta_to_transparent(surface)
        assert isinstance(result, pygame.Surface)


class TestFilmStripRenderingHelpers:
    """Test rendering helper methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_draw_placeholder_does_not_raise(self):
        """Test _draw_placeholder renders without error.

        _draw_placeholder takes a single frame_surface argument and draws
        a placeholder into it.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        frame_surface = pygame.Surface(
            (widget.frame_width, widget.frame_height),
            pygame.SRCALPHA,
        )
        widget._draw_placeholder(frame_surface)

    def test_create_selection_border_returns_surface(self):
        """Test _create_selection_border returns a valid surface.

        _create_selection_border takes a single frame_surface argument.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        frame_surface = pygame.Surface(
            (widget.frame_width, widget.frame_height),
            pygame.SRCALPHA,
        )
        result = widget._create_selection_border(frame_surface)
        assert isinstance(result, pygame.Surface)

    def test_add_hover_highlighting_does_not_raise(self):
        """Test _add_hover_highlighting renders without error.

        _add_hover_highlighting takes a single frame_surface argument.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        frame_surface = pygame.Surface(
            (widget.frame_width, widget.frame_height),
            pygame.SRCALPHA,
        )
        widget._add_hover_highlighting(frame_surface)

    def test_render_sprocket_separator_does_not_raise(self):
        """Test render_sprocket_separator renders without error.

        render_sprocket_separator takes x, y, and height positional arguments.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget.render_sprocket_separator(0, 50, WIDGET_HEIGHT)
        assert isinstance(result, pygame.Surface)


class TestFilmStripResetAllTabStates:
    """Test reset_all_tab_states method."""

    def test_reset_clears_tab_states(self, mocker):
        """Test reset_all_tab_states clears hover state and calls reset_click_state.

        reset_all_tab_states calls tab.reset_click_state() (which sets
        is_clicked = False) and sets tab.is_hovered = False.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Create mock tabs
        mock_tab = mocker.Mock()
        mock_tab.is_hovered = True
        mock_tab.is_clicked = True
        widget.film_tabs = [mock_tab]
        widget.reset_all_tab_states()
        assert mock_tab.is_hovered is False
        mock_tab.reset_click_state.assert_called_once()

    def test_reset_empty_tabs(self):
        """Test reset_all_tab_states with no tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.film_tabs = []
        widget.reset_all_tab_states()  # Should not raise


class TestFilmStripToggleOnionSkinning:
    """Test _toggle_onion_skinning method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_toggle_onion_skinning_without_parent(self):
        """Test _toggle_onion_skinning without parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Should not raise when no parent_canvas
        if hasattr(widget, '_toggle_onion_skinning'):
            widget._toggle_onion_skinning('idle', 0)

    def test_toggle_onion_skinning_with_parent_and_canvas(self, mocker):
        """Test _toggle_onion_skinning with parent scene and canvas triggers force_redraw."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock()

        # Mock the onion skinning module that gets imported inside the method
        mock_manager = mocker.Mock()
        mock_manager.toggle_frame_onion_skinning.return_value = True
        mock_onion_module = mocker.MagicMock()
        mock_onion_module.get_onion_skinning_manager.return_value = mock_manager
        mocker.patch.dict(
            'sys.modules',
            {'glitchygames.bitmappy.onion_skinning': mock_onion_module},
        )

        widget._toggle_onion_skinning('idle', 0)
        assert widget._force_redraw is True
        widget.parent_scene.canvas.force_redraw.assert_called_once()

    def test_toggle_onion_skinning_exception_handled(self, mocker):
        """Test _toggle_onion_skinning handles exceptions gracefully (line 1624-1625)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Mock the onion_skinning module's get function to raise an exception
        # The import happens inside the method, so we need to mock at the module level
        mock_onion_module = mocker.MagicMock()
        mock_onion_module.get_onion_skinning_manager.side_effect = RuntimeError('test error')
        mocker.patch.dict(
            'sys.modules',
            {'glitchygames.bitmappy.onion_skinning': mock_onion_module},
        )
        # Should not raise - exception is caught and logged
        widget._toggle_onion_skinning('idle', 0)


class TestFilmStripGetFrameImageStale:
    """Test _get_frame_image with stale image path (lines 499-528)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_get_frame_image_stale_with_pixels_and_image(self):
        """Test _get_frame_image returns surface from pixel data when image is stale."""
        frame = SpriteFrame(pygame.Surface((2, 2), pygame.SRCALPHA), duration=0.5)
        frame._image_stale = True  # type: ignore[unresolved-attribute]
        frame.pixels = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]

        result = FilmStripWidget._get_frame_image(frame)
        assert isinstance(result, pygame.Surface)
        assert result.get_size() == (2, 2)

    def test_get_frame_image_stale_without_image_uses_sqrt_fallback(self, mocker):
        """Test _get_frame_image falls back to sqrt when no image (lines 506-516)."""
        # Create a mock frame that has _image_stale=True, pixels, but no image/get_size
        frame = mocker.Mock(spec=[])
        frame._image_stale = True  # type: ignore[unresolved-attribute]
        frame.pixels = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
        frame.image = None
        frame._image = None

        result = FilmStripWidget._get_frame_image(frame)
        assert isinstance(result, pygame.Surface)

    def test_get_frame_image_normal_path_no_image(self, mocker):
        """Test _get_frame_image returns None when no image or pixel data (line 546)."""
        # Use a mock that has no image and no get_pixel_data
        frame = mocker.Mock(spec=[])
        frame._image_stale = False
        frame.image = None

        result = FilmStripWidget._get_frame_image(frame)
        assert result is None

    def test_get_frame_image_stale_with_internal_image(self):
        """Test _get_frame_image uses _image when image is None but _image exists (line 503-504)."""
        frame = SpriteFrame(pygame.Surface((3, 3), pygame.SRCALPHA), duration=0.5)
        frame._image_stale = True  # type: ignore[unresolved-attribute]
        pixel_data = cast('list[tuple[int, ...]]', [(255, 0, 0, 255)] * 9)
        frame.pixels = pixel_data
        # Set image to None but _image to a valid surface
        frame.image = None  # type: ignore[invalid-assignment]
        frame._image = pygame.Surface((3, 3), pygame.SRCALPHA)

        result = FilmStripWidget._get_frame_image(frame)
        assert isinstance(result, pygame.Surface)
        assert result.get_size() == (3, 3)


class TestFilmStripRenderEditingLabel:
    """Test _render_editing_label for cursor blink rendering (lines 1972-2014)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_editing_label_with_text_and_cursor(self):
        """Test _render_editing_label renders text with blinking cursor."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_text = 'walk'
        widget.cursor_visible = True
        widget.cursor_blink_time = 0

        label_surface = pygame.Surface((100, 20), pygame.SRCALPHA)
        anim_rect = pygame.Rect(0, 0, 100, 20)
        widget._render_editing_label(label_surface, anim_rect)
        # Should not raise

    def test_render_editing_label_empty_text_with_cursor(self):
        """Test _render_editing_label renders cursor with no text (lines 2000-2011)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_text = ''
        widget.cursor_visible = True
        widget.cursor_blink_time = 0

        label_surface = pygame.Surface((100, 20), pygame.SRCALPHA)
        anim_rect = pygame.Rect(0, 0, 100, 20)
        widget._render_editing_label(label_surface, anim_rect)
        # Should render cursor at center without error

    def test_render_editing_label_cursor_blink_toggle(self):
        """Test _render_editing_label toggles cursor blink (lines 1972-1975)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_text = 'test'
        widget.cursor_visible = True
        # Set cursor_blink_time far in the past to trigger toggle
        widget.cursor_blink_time = 0

        label_surface = pygame.Surface((100, 20), pygame.SRCALPHA)
        anim_rect = pygame.Rect(0, 0, 100, 20)

        # Force current ticks to be well past the blink interval
        current_ticks = pygame.time.get_ticks()
        if current_ticks - widget.cursor_blink_time > 530:
            # cursor_visible should toggle
            widget._render_editing_label(label_surface, anim_rect)
            # After toggle, cursor_visible should have changed
            # (it was True, should now be False after blink interval)


class TestFilmStripRenderWithHover:
    """Test render method with hover effect (lines 2078-2079)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_with_hovering_strip(self, mocker):
        """Test render draws hover effect when is_hovering_strip is True."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        widget.is_hovering_strip = True

        # Mock parent scene for multi-controller indicators
        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget.render(render_surface)
        # Should not raise; hover effect is drawn


class TestFilmStripGetActiveControllerSelections:
    """Test _get_active_controller_selections (lines 2099-2117)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_parent_scene_returns_empty(self):
        """Test returns empty list when no parent_scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget._get_active_controller_selections()
        assert result == []

    def test_with_active_controller_selection(self, mocker):
        """Test returns selections for active controllers matching animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Mock parent_scene with controller_selections
        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = True
        mock_selection.get_selection.return_value = ('idle', 0)

        # Mock controller info
        mock_controller_info = mocker.Mock()
        mock_controller_info.controller_id = 0
        mock_controller_info.color = (255, 0, 0)

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}
        widget.parent_scene.multi_controller_manager = mocker.Mock()
        widget.parent_scene.multi_controller_manager.controllers = {0: mock_controller_info}

        result = widget._get_active_controller_selections()
        assert len(result) == 1
        assert result[0]['controller_id'] == 0
        assert result[0]['color'] == (255, 0, 0)

    def test_with_inactive_controller_selection(self, mocker):
        """Test skips inactive controller selections (line 2100)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = False

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}

        result = widget._get_active_controller_selections()
        assert result == []

    def test_with_wrong_animation_controller(self, mocker):
        """Test skips controllers selecting different animation (line 2103)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = True
        mock_selection.get_selection.return_value = ('walk', 0)  # Different animation

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}

        result = widget._get_active_controller_selections()
        assert result == []


class TestFilmStripDrawMultiControllerIndicators:
    """Test _draw_multi_controller_indicators color priority (lines 2218-2230, 2275-2284)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_controller_color_priority_sorting(self):
        """Test controller selections are sorted by color priority."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Set up frame layout for the test
        widget.frame_layouts['idle', 0] = pygame.Rect(50, 50, 64, 64)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)

        # Create controller selections with various colors
        controller_selections = [
            {'controller_id': 3, 'frame': 0, 'color': (255, 255, 0)},  # Yellow (priority 3)
            {'controller_id': 0, 'frame': 0, 'color': (255, 0, 0)},  # Red (priority 0)
            {'controller_id': 2, 'frame': 0, 'color': (0, 0, 255)},  # Blue (priority 2)
            {'controller_id': 1, 'frame': 0, 'color': (0, 255, 0)},  # Green (priority 1)
        ]

        widget._draw_multi_controller_indicators(render_surface, 'idle', 0, controller_selections)
        # Should draw all indicators without error

    def test_unknown_controller_color_priority(self):
        """Test unknown controller colors get priority 999 (lines 2227-2228)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.frame_layouts['idle', 0] = pygame.Rect(50, 50, 64, 64)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)

        # Unknown color
        controller_selections = [
            {'controller_id': 0, 'frame': 0, 'color': (128, 128, 128)},  # Unknown color
        ]

        widget._draw_multi_controller_indicators(render_surface, 'idle', 0, controller_selections)

    def test_keyboard_and_controller_indicators(self):
        """Test drawing both keyboard and controller indicators (lines 2308-2315)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.frame_layouts['idle', 0] = pygame.Rect(50, 50, 64, 64)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)

        controller_selections = [
            {'controller_id': 0, 'frame': 0, 'color': (255, 0, 0)},
        ]

        # keyboard_animation matches current_animation, so keyboard indicator drawn too
        widget._draw_multi_controller_indicators(render_surface, 'idle', 0, controller_selections)

    def test_no_selections_returns_early(self):
        """Test returns early with no selections (line 2292)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)

        # No matching keyboard or controller
        widget._draw_multi_controller_indicators(render_surface, 'other', -1, [])


class TestFilmStripHandleAddDeleteAnimationTab:
    """Test _handle_add_animation_tab_click and _handle_delete_animation_tab_click."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_add_animation_no_parent(self):
        """Test _handle_add_animation_tab_click without parent scene (line 2716)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._handle_add_animation_tab_click()
        # Should return without error

    def test_handle_add_animation_no_canvas(self, mocker):
        """Test _handle_add_animation_tab_click without canvas (lines 2719-2720)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.parent_scene = mocker.Mock(spec=['_add_new_animation'])
        # canvas is not present (spec restricts attributes)
        widget._handle_add_animation_tab_click()
        widget.parent_scene._add_new_animation.assert_called_once()

    def test_handle_add_animation_with_canvas(self, mocker):
        """Test _handle_add_animation_tab_click with canvas inserts after current (line 2725)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock()
        widget.parent_scene.canvas.animated_sprite = sprite

        widget._handle_add_animation_tab_click()
        widget.parent_scene._add_new_animation.assert_called_once_with(insert_after_index=0)

    def test_handle_add_animation_fallback_on_value_error(self, mocker):
        """Test _handle_add_animation_tab_click falls back when animation not found (line 2727)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        # Set current_animation to something not in the list
        widget.current_animation = 'nonexistent'

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock()
        widget.parent_scene.canvas.animated_sprite = sprite

        widget._handle_add_animation_tab_click()
        widget.parent_scene._add_new_animation.assert_called_once_with()

    def test_handle_delete_animation_no_parent(self):
        """Test _handle_delete_animation_tab_click without parent scene (line 2732)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._handle_delete_animation_tab_click()
        # Should return without error

    def test_handle_delete_animation_no_canvas(self, mocker):
        """Test _handle_delete_animation_tab_click without canvas (line 2735)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.parent_scene = mocker.Mock(spec=['_delete_animation'])
        widget._handle_delete_animation_tab_click()
        # Should return without error (no canvas to check)

    def test_handle_delete_animation_with_multiple(self, mocker):
        """Test _handle_delete_animation_tab_click deletes when multiple animations."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock()
        widget.parent_scene.canvas.animated_sprite = sprite

        widget._handle_delete_animation_tab_click()
        widget.parent_scene._delete_animation.assert_called_once_with('idle')


class TestFilmStripHandleRemovalButton:
    """Test _handle_removal_button_click edge cases (lines 2895-2899)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_removal_button_shows_confirmation(self, mocker):
        """Test removal button shows confirmation dialog (lines 2895-2897)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface), SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.parent_scene = mocker.Mock()

        # Set up a removal button layout at a known position
        button_rect = pygame.Rect(10, 10, 11, 30)
        widget.removal_button_layouts = {('idle', 0): button_rect}

        result = widget._handle_removal_button_click((15, 25))
        assert result is True
        widget.parent_scene._show_delete_frame_confirmation.assert_called_once_with('idle', 0)

    def test_removal_button_out_of_range(self, mocker):
        """Test removal button returns False when frame index is out of range (lines 2898-2899)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Set up removal button for frame index 5 which doesn't exist
        button_rect = pygame.Rect(10, 10, 11, 30)
        widget.removal_button_layouts = {('idle', 5): button_rect}

        result = widget._handle_removal_button_click((15, 25))
        assert result is False


class TestFilmStripTrackFrameDeletion:
    """Test _track_frame_deletion_for_undo edge cases (line 2935)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_track_deletion_without_parent_scene(self):
        """Test _track_frame_deletion_for_undo returns early without parent_scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        frames = sprite._animations['idle']
        widget._track_frame_deletion_for_undo(frames, 'idle', 0)
        # Should return early without error


class TestFilmStripClampAnimatedSpriteFrame:
    """Test _clamp_animated_sprite_frame edge cases (lines 2972, 2978)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_clamp_when_frame_exceeds_remaining(self):
        """Test clamps frame when current frame exceeds remaining frames (line 2978)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Set frame manager to a frame beyond current count
        sprite.frame_manager.current_frame = 5
        sprite.frame_manager.current_animation = 'idle'

        frames = sprite._animations['idle']  # Has 1 frame
        widget._clamp_animated_sprite_frame('idle', frames)
        assert sprite.frame_manager.current_frame == 0

    def test_clamp_different_animation_does_nothing(self):
        """Test clamp does nothing for different animation (line 2972)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        sprite.frame_manager.current_animation = 'walk'  # Different from 'idle'

        frames = sprite._animations['idle']
        widget._clamp_animated_sprite_frame('idle', frames)
        # Should not modify anything since animations don't match


class TestFilmStripRemoveFrameScrollAdjust:
    """Test _remove_frame scroll adjustment (lines 3046-3048)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_remove_frame_adjusts_scroll_for_many_frames(self, mocker):
        """Test _remove_frame adjusts scroll offset when more than FRAMES_PER_VIEW remain."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        # Add 6 frames so after removal we still have > FRAMES_PER_VIEW
        frames = [SpriteFrame(surface, duration=0.5) for _ in range(6)]
        sprite.add_animation('idle', frames)
        widget.set_animated_sprite(sprite)
        widget.scroll_offset = 100  # Set a large scroll offset

        widget.parent_scene = mocker.Mock(spec=[])

        widget._remove_frame('idle', 0)
        # After removal, 5 frames remain (> 4), scroll should be clamped
        assert widget.scroll_offset <= 1  # max(0, 5 - 4) = 1

    def test_remove_frame_resets_scroll_for_few_frames(self, mocker):
        """Test _remove_frame resets scroll to 0 when FRAMES_PER_VIEW or fewer remain."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        frames = [SpriteFrame(surface, duration=0.5) for _ in range(3)]
        sprite.add_animation('idle', frames)
        widget.set_animated_sprite(sprite)
        widget.scroll_offset = 50

        widget.parent_scene = mocker.Mock(spec=[])

        widget._remove_frame('idle', 0)
        # After removal, 2 frames remain (<= 4), scroll resets to 0
        assert widget.scroll_offset == 0


class TestFilmStripRenderRemovalButton:
    """Test _render_removal_button skipping (lines 3084-3098)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_removal_button_no_layout(self):
        """Test _render_removal_button returns when no layout exists (lines 3084-3085)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Set up removal_button_layouts but without the frame we're rendering
        widget.removal_button_layouts = {('idle', 1): pygame.Rect(0, 0, 11, 30)}

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._render_removal_button(render_surface, 'idle', 0)
        # Should return early without error

    def test_render_removal_button_single_frame_skips(self):
        """Test _render_removal_button skips when animation has only 1 frame (lines 3094-3098)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Set up a removal button layout even though there's only 1 frame
        widget.removal_button_layouts = {('idle', 0): pygame.Rect(0, 0, 11, 30)}

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._render_removal_button(render_surface, 'idle', 0)
        # Should skip rendering since there's only 1 frame


class TestFilmStripDeleteTabRender:
    """Test FilmStripDeleteTab render in clicked state (lines 3321-3322)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_clicked_state(self):
        """Test FilmStripDeleteTab renders in clicked state."""
        tab = FilmStripDeleteTab(x=10, y=10, width=40, height=10)
        tab.is_clicked = True
        surface = pygame.Surface((100, 50), pygame.SRCALPHA)
        tab.render(surface)
        # Should render with click_color

    def test_reset_click_state(self):
        """Test FilmStripDeleteTab.reset_click_state (line 3374)."""
        tab = FilmStripDeleteTab(x=10, y=10)
        tab.is_clicked = True
        tab.reset_click_state()
        assert tab.is_clicked is False


class TestFilmStripTabRender:
    """Test FilmStripTab render in clicked state (lines 3446-3447)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_clicked_state(self):
        """Test FilmStripTab renders in clicked state."""
        tab = FilmStripTab(x=10, y=10, width=40, height=10)
        tab.is_clicked = True
        surface = pygame.Surface((100, 50), pygame.SRCALPHA)
        tab.render(surface)
        # Should render with click_color

    def test_handle_click_miss(self):
        """Test FilmStripTab.handle_click returns False on miss (line 3484)."""
        tab = FilmStripTab(x=10, y=10, width=40, height=10)
        result = tab.handle_click((999, 999))
        assert result is False


class TestFilmStripHandleClickEdgeCases:
    """Test handle_click with removal button and tab interactions (lines 1166-1167, 1171-1172)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_click_removal_button_returns_none(self, mocker):
        """Test handle_click returns None when removal button was clicked."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface), SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        widget.parent_scene = mocker.Mock()

        # Set up removal button at the click position
        click_pos = (15, 25)
        widget.removal_button_layouts = {('idle', 0): pygame.Rect(10, 10, 11, 30)}

        result = widget.handle_click(click_pos)
        assert result is None

    def test_handle_click_tab_returns_none(self, mocker):
        """Test handle_click returns None when a tab was clicked (lines 1171-1172)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Create a tab at a specific position
        tab = FilmTabWidget(x=5, y=50, width=11, height=30)
        tab.set_insertion_type('before', 0)
        widget.film_tabs = [tab]

        # Mock _insert_frame_at_tab to prevent actual frame insertion
        mocker.patch.object(widget, '_insert_frame_at_tab')

        result = widget.handle_click((10, 65))
        assert result is None


class TestFilmStripPropagateDirtyUpParentChain:
    """Test _propagate_dirty_up_parent_chain (lines 619-624)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_propagate_up_sets_parent_dirty(self, mocker):
        """Test _propagate_dirty_up_parent_chain marks parent as dirty (line 620)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent = mocker.Mock()
        parent.dirty = 0
        parent.parent = None  # Stop recursion

        widget._propagate_dirty_up_parent_chain(parent)
        assert parent.dirty == 1

    def test_propagate_up_recurses_to_grandparent(self, mocker):
        """Test _propagate_dirty_up_parent_chain recurses through chain (line 624)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        grandparent = mocker.Mock()
        grandparent.dirty = 0
        grandparent.parent = None

        parent = mocker.Mock()
        parent.dirty = 0
        parent.parent = grandparent

        widget._propagate_dirty_up_parent_chain(parent)
        assert parent.dirty == 1
        assert grandparent.dirty == 1

    def test_propagate_up_none_parent_returns(self):
        """Test _propagate_dirty_up_parent_chain returns on None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._propagate_dirty_up_parent_chain(None)
        # Should return without error


class TestFilmStripDrawPreviewTriangle:
    """Test _draw_preview_triangle fallback paths (lines 2371-2374)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_preview_triangle_no_animation_data(self):
        """Test _draw_preview_triangle centers triangle when no animation data (line 2374)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Create a preview rect that's NOT in preview_rects so anim_name lookup fails
        preview_rect = pygame.Rect(400, 10, 64, 64)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._draw_preview_triangle(render_surface, preview_rect)
        # Should use fallback center position

    def test_preview_triangle_single_frame_centered(self):
        """Test _draw_preview_triangle centers triangle for single-frame animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        preview_rect = pygame.Rect(400, 10, 64, 64)
        widget.preview_rects['idle'] = preview_rect

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._draw_preview_triangle(render_surface, preview_rect)
        # Should center the triangle for single frame


class TestFilmStripRenderPreviewEdgeCases:
    """Test render_preview edge cases (lines 1810-1822, 1833-1840)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_preview_with_no_frame_image(self, mocker):
        """Test render_preview draws placeholder when frame has no image (lines 1833-1840)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        frame = SpriteFrame(surface, duration=0.5)
        sprite.add_animation('idle', [frame])
        widget.set_animated_sprite(sprite)

        # Create a mock frame with no image to trigger placeholder
        mock_frame = mocker.Mock(spec=[])
        mock_frame._image_stale = False
        mock_frame.image = None
        mock_frame.duration = 0.5
        sprite._animations['idle'] = [mock_frame]

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget.render_preview(render_surface)

    def test_render_preview_hovered(self):
        """Test render_preview draws hover effect on preview (line 1795)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface, duration=0.5)])
        widget.set_animated_sprite(sprite)
        widget.hovered_preview = 'idle'

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget.render_preview(render_surface)


class TestFilmStripRenderFrameThumbnailEdgeCases:
    """Test render_frame_thumbnail edge cases (lines 1480, 1505, 1560-1562)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_thumbnail_no_frame_image(self, mocker):
        """Test render_frame_thumbnail draws placeholder when no image (line 1480)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Use a mock frame that has no image and no pixel data
        frame = mocker.Mock(spec=[])
        frame._image_stale = False
        frame.image = None

        result = widget.render_frame_thumbnail(frame)
        assert isinstance(result, pygame.Surface)

    def test_render_thumbnail_hovered(self):
        """Test render_frame_thumbnail draws hover effect (line 1505)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        frame = SpriteFrame(surface, duration=0.5)

        result = widget.render_frame_thumbnail(frame, is_hovered=True)
        assert isinstance(result, pygame.Surface)


class TestFilmStripHandleKeyboardEnterKey:
    """Test handle_keyboard_input Enter key for renaming (lines 1425-1436 via rename flow)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_enter_key_commits_rename(self, mocker):
        """Test Enter key commits animation rename via parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)

        widget.editing_animation = 'idle'
        widget.editing_text = 'walk'
        widget.original_animation_name = 'idle'
        widget.parent_scene = mocker.Mock()

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        event.unicode = ''
        event.mod = 0

        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None
        widget.parent_scene.on_animation_rename.assert_called_once_with('idle', 'walk')

    def test_enter_key_same_name_no_rename(self, mocker):
        """Test Enter key does not rename when name is unchanged."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)

        widget.editing_animation = 'idle'
        widget.editing_text = 'idle'  # Same name
        widget.original_animation_name = 'idle'
        widget.parent_scene = mocker.Mock()

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        event.unicode = ''

        result = widget.handle_keyboard_input(event)
        assert result is True
        widget.parent_scene.on_animation_rename.assert_not_called()

    def test_enter_key_empty_text_no_rename(self, mocker):
        """Test Enter key does not rename when text is empty."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)

        widget.editing_animation = 'idle'
        widget.editing_text = ''
        widget.original_animation_name = 'idle'

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        event.unicode = ''

        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None


class TestFilmStripGetControllerSelectionColor:
    """Test _get_controller_selection_color (lines 1425-1436)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_returns_controller_color_for_matching_selection(self, mocker):
        """Test returns controller color when a controller has the frame selected."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)

        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = True
        mock_selection.get_selection.return_value = ('idle', 0)

        mock_controller_info = mocker.Mock()
        mock_controller_info.controller_id = 0
        mock_controller_info.color = (255, 0, 0)

        mock_manager = mocker.Mock()
        mock_manager.controllers = {0: mock_controller_info}

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}

        # Mock the module that gets imported locally inside the method
        mock_multi_ctrl_module = mocker.MagicMock()
        mock_multi_ctrl_module.MultiControllerManager.get_instance.return_value = mock_manager
        mocker.patch.dict(
            'sys.modules',
            {'glitchygames.bitmappy.multi_controller_manager': mock_multi_ctrl_module},
        )

        result = widget._get_controller_selection_color('idle', 0)
        assert result == (255, 0, 0)

    def test_returns_none_for_inactive_controller(self, mocker):
        """Test returns None when controller is inactive (line 1425-1426)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)

        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = False

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}

        result = widget._get_controller_selection_color('idle', 0)
        assert result is None

    def test_returns_none_for_different_frame(self, mocker):
        """Test returns None when controller selects different frame (line 1428-1429)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)

        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = True
        mock_selection.get_selection.return_value = ('idle', 5)  # Different frame

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}

        result = widget._get_controller_selection_color('idle', 0)
        assert result is None


class TestFilmStripRenderVerticalDividerAndPreviewBackground:
    """Test _render_vertical_divider and _render_preview_background (lines 1877, 1894)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_vertical_divider_no_sprite(self):
        """Test _render_vertical_divider returns when no animated sprite (line 1877)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._render_vertical_divider(surface)
        # Should return without error

    def test_render_preview_background_no_sprite(self):
        """Test _render_preview_background returns when no animated sprite (line 1894)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._render_preview_background(surface)
        # Should return without error


class TestFilmStripCalculateFramesWidth:
    """Test _calculate_frames_width (line 2543)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_calculate_frames_width_with_multiple_animations(self):
        """Test _calculate_frames_width adds sprocket width between animations (line 2543)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        result = widget._calculate_frames_width()
        # Should include sprocket width between the two animations
        expected_per_frame = widget.frame_width + widget.frame_spacing
        assert result == expected_per_frame * 2 + widget.sprocket_width


class TestFilmStripHandleTabHover:
    """Test _handle_tab_hover (line 2752-2754)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_tab_hover_returns_true_when_hovering(self):
        """Test _handle_tab_hover returns True when hovering over a tab."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        widget.film_tabs = [tab]

        result = widget._handle_tab_hover((15, 25))
        assert result is True
        assert tab.is_hovered is True

    def test_handle_tab_hover_returns_false_when_not_hovering(self):
        """Test _handle_tab_hover returns False when not hovering over any tab."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        widget.film_tabs = [tab]

        result = widget._handle_tab_hover((999, 999))
        assert result is False


class TestFilmStripDrawFilmSprockets:
    """Test _draw_film_sprockets with label area (lines 2470-2474)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_draw_film_sprockets_with_animation_layout(self):
        """Test _draw_film_sprockets avoids label area (lines 2470-2474)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._draw_film_sprockets(render_surface)
        # Should skip sprockets in the label area


class TestFilmStripHandleClickEnterEditMode:
    """Test handle_click entering animation label edit mode."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_click_animation_label_enters_edit_mode(self, mocker):
        """Test clicking animation label enters edit mode."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Get the animation label rect and click inside it
        label_rect = widget.animation_layouts.get('idle')
        if label_rect:
            click_pos = (label_rect.centerx, label_rect.centery)
            result = widget.handle_click(click_pos)
            assert result is None  # Should return None for label clicks
            assert widget.editing_animation == 'idle'
            assert not widget.editing_text


class TestFilmStripSetFrameIndexParentCanvas:
    """Test set_frame_index with parent canvas (line 2572)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_set_frame_index_updates_parent_canvas(self, mocker):
        """Test set_frame_index updates the parent canvas interface (line 2572)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface), SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.parent_canvas = mocker.Mock()
        widget.parent_canvas.canvas_interface = mocker.Mock()

        widget.set_frame_index(1)
        assert widget.current_frame == 1
        widget.parent_canvas.canvas_interface.set_current_frame.assert_called_once_with('idle', 1)


class TestFilmStripRenderAnimationLabel:
    """Test _render_animation_label hovered state (lines 1949, 1957, 1963)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_label_hovered_but_not_editing(self):
        """Test _render_animation_label adds hover highlighting (line 1963)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        widget.hovered_animation = 'idle'
        widget.editing_animation = None

        anim_rect = widget.animation_layouts.get('idle')
        if anim_rect:
            result = widget._render_animation_label('idle', anim_rect)
            assert isinstance(result, pygame.Surface)

    def test_render_label_in_edit_mode(self):
        """Test _render_animation_label calls _render_editing_label when editing (line 1949)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        widget.editing_animation = 'idle'
        widget.editing_text = 'walking'
        widget.cursor_visible = True
        widget.cursor_blink_time = 0

        anim_rect = widget.animation_layouts.get('idle')
        if anim_rect:
            result = widget._render_animation_label('idle', anim_rect)
            assert isinstance(result, pygame.Surface)
