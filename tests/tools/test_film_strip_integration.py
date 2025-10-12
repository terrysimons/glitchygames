"""Film strip integration tests with animated canvas."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import bitmappy
from glitchygames.tools import film_strip

from mocks.test_mock_factory import MockFactory


class TestFilmStripIntegration(unittest.TestCase):
    """Test film strip integration with animated canvas."""

    @classmethod
    def setUpClass(cls):
        """Set up pygame mocks for all tests."""
        cls.patchers = MockFactory.setup_pygame_mocks()
        for patcher in cls.patchers:
            patcher.start()

    @classmethod
    def tearDownClass(cls):
        """Tear down pygame mocks."""
        MockFactory.teardown_pygame_mocks(cls.patchers)

    def test_film_strip_canvas_integration(self):
        """Test film strip integration with animated canvas."""
        # Create mock animated sprite
        mock_sprite = MockFactory.create_animated_sprite_mock()
        
        # Create animated canvas sprite
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test that film strip is created
        assert hasattr(canvas, "film_strip")
        assert isinstance(canvas.film_strip, film_strip.FilmStripWidget)
        
        # Test that film strip has the animated sprite
        assert canvas.film_strip.animated_sprite == mock_sprite

    def test_film_strip_sprite_creation(self):
        """Test film strip sprite creation in animated canvas."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test that film strip sprite is created
        assert hasattr(canvas, "film_strip_sprite")
        assert isinstance(canvas.film_strip_sprite, bitmappy.FilmStripSprite)
        
        # Test that film strip sprite has the widget
        assert canvas.film_strip_sprite.film_strip_widget == canvas.film_strip

    def test_film_strip_positioning(self):
        """Test film strip positioning relative to canvas."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=100, y=200, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test film strip positioning
        film_strip = canvas.film_strip
        assert film_strip.rect.x == canvas.rect.right + 20  # 20px to the right
        assert film_strip.rect.y == canvas.rect.y  # Same vertical position
        
        # Test film strip sprite positioning
        film_strip_sprite = canvas.film_strip_sprite
        assert film_strip_sprite.rect.x == film_strip.rect.x
        assert film_strip_sprite.rect.y == film_strip.rect.y

    def test_film_strip_width_calculation(self):
        """Test film strip width calculation."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test that film strip has appropriate width
        film_strip = canvas.film_strip
        assert film_strip.rect.width >= 300  # Minimum width
        assert film_strip.rect.width > 0

    def test_film_strip_height_calculation(self):
        """Test film strip height calculation."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test that film strip height is calculated based on animations
        film_strip = canvas.film_strip
        assert film_strip.rect.height > 0
        
        # Height should be based on number of animations
        num_animations = len(mock_sprite._animations)
        expected_height = (film_strip.animation_label_height + film_strip.frame_height + 10) * min(num_animations, 5) + 20
        assert film_strip.rect.height == expected_height

    def test_film_strip_frame_selection_integration(self):
        """Test film strip frame selection integration with canvas."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test initial state
        assert canvas.current_animation == ""
        assert canvas.current_frame == 0
        
        # Test setting current frame through film strip
        if mock_sprite._animations:
            anim_name = list(mock_sprite._animations.keys())[0]
            canvas.show_frame(anim_name, 0)
            assert canvas.current_animation == anim_name
            assert canvas.current_frame == 0

    def test_film_strip_click_integration(self):
        """Test film strip click integration with canvas."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Create mock click event
        mock_event = Mock()
        mock_event.pos = (canvas.film_strip_sprite.rect.x + 50, canvas.film_strip_sprite.rect.y + 50)
        
        # Test click handling
        with patch.object(canvas.film_strip, 'handle_click', return_value=("idle", 1)):
            canvas.film_strip_sprite.on_left_mouse_button_down_event(mock_event)
            
            # Should update canvas to show the selected frame
            assert canvas.current_animation == "idle"
            assert canvas.current_frame == 1

    def test_film_strip_animation_preview_integration(self):
        """Test film strip animation preview integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test that preview animations are initialized
        film_strip = canvas.film_strip
        assert len(film_strip.preview_animation_times) > 0
        assert len(film_strip.preview_animation_speeds) > 0
        assert len(film_strip.preview_frame_durations) > 0
        
        # Test animation timing update
        film_strip.update_animations(0.1)
        
        # Test getting current preview frame for each animation
        for anim_name in film_strip.preview_animation_times.keys():
            frame_idx = film_strip.get_current_preview_frame(anim_name)
            assert isinstance(frame_idx, int)
            assert frame_idx >= 0

    def test_film_strip_layout_calculation_integration(self):
        """Test film strip layout calculation integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test that layouts are calculated
        film_strip = canvas.film_strip
        assert len(film_strip.frame_layouts) > 0
        assert len(film_strip.animation_layouts) > 0
        assert len(film_strip.preview_rects) > 0
        
        # Test layout calculation methods
        film_strip._calculate_layout()
        assert len(film_strip.frame_layouts) > 0
        assert len(film_strip.animation_layouts) > 0
        assert len(film_strip.preview_rects) > 0

    def test_film_strip_scroll_integration(self):
        """Test film strip scroll integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test scroll functionality
        film_strip = canvas.film_strip
        film_strip.update_scroll_for_frame(2)
        
        # Should update scroll offset
        assert hasattr(film_strip, "scroll_offset")
        assert film_strip.scroll_offset >= 0

    def test_film_strip_rendering_integration(self):
        """Test film strip rendering integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test rendering methods
        film_strip = canvas.film_strip
        assert callable(film_strip.render)
        assert callable(film_strip.render_frame_thumbnail)
        assert callable(film_strip.render_sprocket_separator)
        assert callable(film_strip.render_preview)

    def test_film_strip_parent_canvas_integration(self):
        """Test film strip parent canvas integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test that film strip has parent canvas
        film_strip = canvas.film_strip
        assert hasattr(film_strip, "parent_canvas")
        
        # Test that film strip sprite has parent canvas
        film_strip_sprite = canvas.film_strip_sprite
        assert hasattr(film_strip_sprite, "parent_canvas")

    def test_film_strip_dirty_flag_integration(self):
        """Test film strip dirty flag integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test dirty flag handling
        film_strip_sprite = canvas.film_strip_sprite
        assert film_strip_sprite.dirty == 1  # Should be dirty initially
        
        # Test mark_dirty functionality
        canvas.film_strip.mark_dirty()
        assert hasattr(canvas.film_strip, "_force_redraw")
        assert canvas.film_strip._force_redraw is True

    def test_film_strip_multiple_animations_integration(self):
        """Test film strip with multiple animations."""
        # Create mock sprite with multiple animations
        mock_sprite = MockFactory.create_animated_sprite_mock()
        # Add more animations to the mock
        mock_sprite._animations["walk"] = [Mock() for _ in range(3)]
        mock_sprite._animations["jump"] = [Mock() for _ in range(2)]
        mock_sprite._animations["idle"] = [Mock() for _ in range(4)]
        
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test that film strip handles multiple animations
        film_strip = canvas.film_strip
        assert len(film_strip.animation_layouts) == 3
        assert len(film_strip.preview_rects) == 3
        
        # Test layout calculation with multiple animations
        film_strip._calculate_layout()
        assert len(film_strip.frame_layouts) > 0

    def test_film_strip_edge_cases_integration(self):
        """Test film strip edge cases integration."""
        # Test with empty sprite
        empty_sprite = Mock()
        empty_sprite._animations = {}
        empty_sprite._animation_order = []
        empty_sprite.frames = {}  # Add frames attribute
        # Add get_pixel_data method for empty sprite
        empty_sprite.get_pixel_data.return_value = [(0, 0, 0)] * (32 * 32)
        
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=empty_sprite,
            x=0, y=0, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Should handle empty sprite gracefully
        film_strip = canvas.film_strip
        assert film_strip.animated_sprite == empty_sprite
        assert len(film_strip.frame_layouts) == 0
        assert len(film_strip.animation_layouts) == 0

    def test_film_strip_coordinate_conversion_integration(self):
        """Test film strip coordinate conversion integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=100, y=200, 
            pixels_across=32, pixels_tall=32,
            pixel_width=16, pixel_height=16
        )
        
        # Test coordinate conversion
        film_strip_sprite = canvas.film_strip_sprite
        film_strip_widget = canvas.film_strip
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (film_strip_sprite.rect.x + 50, film_strip_sprite.rect.y + 50)
        
        # Test coordinate conversion
        with patch.object(film_strip_widget, 'handle_click', return_value=("idle", 1)) as mock_handle_click:
            film_strip_sprite.on_left_mouse_button_down_event(mock_event)
            
            # Should convert screen coordinates to film strip coordinates
            expected_x = mock_event.pos[0] - film_strip_sprite.rect.x
            expected_y = mock_event.pos[1] - film_strip_sprite.rect.y
            mock_handle_click.assert_called_once_with((expected_x, expected_y))


if __name__ == "__main__":
    unittest.main()
