"""Film strip tool functionality tests."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import film_strip
from mocks.test_mock_factory import MockFactory


class TestFilmStripFunctionality(unittest.TestCase):
    """Test film strip module functionality."""

    def test_film_strip_initialization(self):
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
        assert strip.current_animation == ""
        assert strip.current_frame == 0

    def test_film_strip_widget_properties(self):
        """Test film strip widget properties."""
        strip = film_strip.FilmStripWidget(10, 20, 200, 150)
        
        # Test rect properties
        assert strip.rect.x == 10
        assert strip.rect.y == 20
        assert strip.rect.width == 200
        assert strip.rect.height == 150
        
        # Test styling properties
        assert hasattr(strip, 'frame_width')
        assert hasattr(strip, 'frame_height')
        assert hasattr(strip, 'sprocket_width')
        assert hasattr(strip, 'frame_spacing')

    def test_film_strip_widget_methods(self):
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

    def test_film_strip_widget_sprite_handling(self):
        """Test film strip widget sprite handling."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        
        # Test initial state
        assert strip.animated_sprite is None
        assert strip.current_animation == ""
        assert strip.current_frame == 0
        
        # Test setting animated sprite with proper mock using centralized mock
        from mocks.test_mock_factory import MockFactory
        mock_sprite = MockFactory.create_animated_sprite_mock()
        strip.set_animated_sprite(mock_sprite)
        assert strip.animated_sprite == mock_sprite

    def test_film_strip_widget_hover_handling(self):
        """Test film strip widget hover handling."""
        strip = film_strip.FilmStripWidget(0, 0, 100, 100)
        
        # Test hover properties
        assert hasattr(strip, 'hovered_frame')
        assert hasattr(strip, 'hovered_animation')
        
        # Test initial hover state
        assert strip.hovered_frame is None
        assert strip.hovered_animation is None

    def test_film_strip_widget_rendering(self):
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

    def test_film_strip_widget_interaction(self):
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


if __name__ == "__main__":
    unittest.main()
