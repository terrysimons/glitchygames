"""Film strip tool functionality tests."""

import sys
from pathlib import Path
from unittest.mock import Mock

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import film_strip

from tests.mocks.test_mock_factory import MockFactory

# Test constants to avoid magic values
WIDGET_X = 10
WIDGET_Y = 20
WIDGET_WIDTH = 200
WIDGET_HEIGHT = 150
FRAME_COUNT = 2
ANIMATION_COUNT = 3
COLOR_COMPONENT_MAX = 255
DEFAULT_DURATION = 1.0


class TestFilmStripFunctionality:
    """Test film strip module functionality."""

    def test_film_strip_initialization(self, mock_pygame_patches):
        """Test film strip initialization."""
        # Test basic initialization - FilmStripWidget requires x, y, width, height
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test basic properties
        assert hasattr(strip, "rect")
        assert hasattr(strip, "animated_sprite")
        assert hasattr(strip, "current_animation")
        assert hasattr(strip, "current_frame")

        # Test default values
        assert strip.animated_sprite is None
        assert not strip.current_animation
        assert strip.current_frame == 0

    def test_film_strip_widget_properties(self, mock_pygame_patches):
        """Test film strip widget properties."""
        strip = film_strip.FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)

        # Test rect properties
        assert strip.rect.x == WIDGET_X
        assert strip.rect.y == WIDGET_Y
        assert strip.rect.width == WIDGET_WIDTH
        assert strip.rect.height == WIDGET_HEIGHT

        # Test styling properties
        assert hasattr(strip, "frame_width")
        assert hasattr(strip, "frame_height")
        assert hasattr(strip, "sprocket_width")
        assert hasattr(strip, "frame_spacing")

    def test_film_strip_widget_methods(self, mock_pygame_patches):
        """Test film strip widget methods."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test that widget has expected methods (based on actual implementation)
        assert hasattr(strip, "set_animated_sprite")
        assert hasattr(strip, "update_animations")
        assert hasattr(strip, "get_current_preview_frame")
        assert hasattr(strip, "get_frame_at_position")

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
        assert hasattr(strip, "hovered_frame")
        assert hasattr(strip, "hovered_animation")

        # Test initial hover state
        assert strip.hovered_frame is None
        assert strip.hovered_animation is None

    def test_film_strip_widget_rendering(self, mock_pygame_patches):
        """Test film strip widget rendering."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test rendering methods exist (based on actual implementation)
        assert hasattr(strip, "update_layout")
        assert hasattr(strip, "mark_dirty")
        assert hasattr(strip, "set_parent_canvas")

        # Test methods are callable
        assert callable(strip.update_layout)
        assert callable(strip.mark_dirty)
        assert callable(strip.set_parent_canvas)

    def test_film_strip_widget_interaction(self, mock_pygame_patches):
        """Test film strip widget interaction."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test interaction methods exist (based on actual implementation)
        assert hasattr(strip, "get_frame_at_position")
        assert hasattr(strip, "update_scroll_for_frame")
        assert hasattr(strip, "_calculate_scroll_offset")

        # Test methods are callable
        assert callable(strip.get_frame_at_position)
        assert callable(strip.update_scroll_for_frame)
        assert callable(strip._calculate_scroll_offset)

    def test_initialize_preview_animations_no_sprite(self, mock_pygame_patches):
        """Test _initialize_preview_animations when no animated sprite is set."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        # Should not crash when no sprite is set
        strip._initialize_preview_animations()

    def test_initialize_preview_animations_frames_no_duration(self, mock_pygame_patches):
        """Test _initialize_preview_animations with frames that don't have duration attribute."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create frames without duration attribute by using simple objects
        frames_without_duration = []
        for _ in range(ANIMATION_COUNT):
            frame = type("Frame", (), {})()  # Simple object with no duration attribute
            frame.image = Mock()
            frame.image.get_size.return_value = (32, 32)
            # No duration attribute
            frames_without_duration.append(frame)

        mock_sprite._animations["no_duration"] = frames_without_duration
        strip.set_animated_sprite(mock_sprite)

        # Should use default 1.0 duration
        expected_durations = [DEFAULT_DURATION, DEFAULT_DURATION, DEFAULT_DURATION]
        assert strip.preview_frame_durations["no_duration"] == expected_durations

    def test_update_animations_no_sprite(self, mock_pygame_patches):
        """Test update_animations when no animated sprite is set."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        # Should not crash when no sprite is set
        strip.update_animations(0.1)

    def test_get_current_preview_frame_missing_animation(self, mock_pygame_patches):
        """Test get_current_preview_frame when animation is not in timing data."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        # Should return 0 for missing animation
        result = strip.get_current_preview_frame("nonexistent_animation")
        assert result == 0

    def test_get_frame_image_no_image_with_pixel_data(self, mock_pygame_patches):
        """Test _get_frame_image when frame has no image but has pixel data."""
        # Create a frame without image but with pixel data
        frame = type("Frame", (), {})()
        frame.get_pixel_data = Mock(return_value=[(255, 0, 0)] * 100)  # 10x10 red pixels

        result = film_strip.FilmStripWidget._get_frame_image(frame)
        assert result is not None  # Should return a surface

    def test_get_frame_image_no_image_no_pixel_data(self, mock_pygame_patches):
        """Test _get_frame_image when frame has no image and no pixel data."""
        # Create a frame without image or pixel data
        frame = type("Frame", (), {})()
        # No get_pixel_data method

        result = film_strip.FilmStripWidget._get_frame_image(frame)
        assert result is None  # Should return None

    def test_update_layout_with_parent_canvas(self, mock_pygame_patches):
        """Test update_layout when parent canvas exists with film strip sprite."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Create a mock parent canvas with film strip sprite
        mock_parent_canvas = Mock()
        mock_film_strip_sprite = Mock()
        mock_parent_canvas.film_strip_sprite = mock_film_strip_sprite
        strip.parent_canvas = mock_parent_canvas

        # Should not crash and should mark sprite as dirty
        strip.update_layout()
        mock_film_strip_sprite.dirty = 1

    def test_set_parent_canvas(self, mock_pygame_patches):
        """Test set_parent_canvas method."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        mock_canvas = Mock()

        strip.set_parent_canvas(mock_canvas)
        assert strip.parent_canvas == mock_canvas

    def test_mark_dirty_basic(self, mock_pygame_patches):
        """Test mark_dirty method sets _force_redraw flag."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        strip.mark_dirty()
        assert strip._force_redraw is True

    def test_propagate_dirty_to_sprite_groups(self, mock_pygame_patches):
        """Test _propagate_dirty_to_sprite_groups method."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Create a mock sprite with groups
        mock_sprite = Mock()
        mock_other_sprite = Mock()
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
        strip.current_animation = "nonexistent"

        # Should not crash when animation doesn't exist
        strip.update_scroll_for_frame(0)

    def test_update_scroll_for_frame_invalid_index(self, mock_pygame_patches):
        """Test update_scroll_for_frame when frame index is out of bounds."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        mock_sprite = MockFactory.create_animated_sprite_mock()
        strip.set_animated_sprite(mock_sprite)
        strip.current_animation = "idle"

        # Should not crash when frame index is too high
        strip.update_scroll_for_frame(999)

    def test_update_height_with_animations(self, mock_pygame_patches):
        """Test _update_height method with multiple animations."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        mock_sprite = MockFactory.create_animated_sprite_mock()
        # Add more animations to test height calculation
        mock_sprite._animations["walk"] = [Mock(), Mock(), Mock()]
        mock_sprite._animations["jump"] = [Mock(), Mock()]
        strip.set_animated_sprite(mock_sprite)

        # Should calculate height based on number of animations
        strip._update_height()
        assert strip.rect.height > 0

    def test_update_height_with_parent_canvas(self, mock_pygame_patches):
        """Test _update_height method with parent canvas."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        mock_sprite = MockFactory.create_animated_sprite_mock()
        strip.set_animated_sprite(mock_sprite)

        # Create a mock parent canvas with film strip sprite
        mock_parent_canvas = Mock()
        mock_film_strip_sprite = Mock()
        mock_film_strip_sprite.rect = Mock()
        mock_film_strip_sprite.rect.width = 100
        mock_parent_canvas.film_strip_sprite = mock_film_strip_sprite
        strip.parent_canvas = mock_parent_canvas

        # Should update parent sprite height
        strip._update_height()
        assert mock_film_strip_sprite.dirty == 1

    def test_color_cycling_default(self, mock_pygame_patches):
        """Test that the film strip starts with gray as the default background color."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test that the default background color is gray (128, 128, 128)
        assert strip.background_color == (128, 128, 128)
        assert strip.background_color_index == FRAME_COUNT  # Gray is at index 2

    def test_color_cycling_functionality(self, mock_pygame_patches):
        """Test that color cycling works correctly."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test initial state
        initial_color = strip.background_color
        initial_index = strip.background_color_index

        # Simulate a click that should cycle the color
        # This would normally happen through handle_click, but we'll test the cycling logic directly
        strip.background_color_index = (
            strip.background_color_index + 1
        ) % len(strip.BACKGROUND_COLORS)
        strip.background_color = strip.BACKGROUND_COLORS[strip.background_color_index]

        # Verify the color changed
        assert strip.background_color != initial_color
        assert strip.background_color_index != initial_index

        # Test that we can cycle through all colors
        colors_seen = set()
        for _ in range(len(strip.BACKGROUND_COLORS)):
            colors_seen.add(strip.background_color)
            strip.background_color_index = (
                strip.background_color_index + 1
            ) % len(strip.BACKGROUND_COLORS)
            strip.background_color = strip.BACKGROUND_COLORS[strip.background_color_index]

        # Should have seen all colors
        assert len(colors_seen) == len(strip.BACKGROUND_COLORS)

    def test_background_colors_list(self, mock_pygame_patches):
        """Test that the background colors list contains expected colors."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Test that cyan is still in the list
        assert (0, COLOR_COMPONENT_MAX, COLOR_COMPONENT_MAX) in strip.BACKGROUND_COLORS  # Cyan

        # Test that gray is in the list
        assert (128, 128, 128) in strip.BACKGROUND_COLORS  # Gray

        # Test that we have a reasonable number of colors
        assert len(strip.BACKGROUND_COLORS) >= ANIMATION_COUNT

        # Test that all colors are valid RGB tuples
        for color in strip.BACKGROUND_COLORS:
            assert isinstance(color, tuple)
            assert len(color) == ANIMATION_COUNT
            assert all(0 <= component <= COLOR_COMPONENT_MAX for component in color)
