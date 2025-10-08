"""Comprehensive test coverage for the tools module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.tools import charmap
from test_mock_factory import MockFactory


class TestCharmapCoverage(unittest.TestCase):
    """Test charmap module coverage."""

    def test_is_defined_non_whitespace_printable_basic(self):
        """Test basic character checking functionality."""
        # Test printable characters
        assert charmap.is_defined_non_whitespace_printable('A') is True
        assert charmap.is_defined_non_whitespace_printable('1') is True
        assert charmap.is_defined_non_whitespace_printable('@') is True
        
        # Test whitespace characters
        assert charmap.is_defined_non_whitespace_printable(' ') is False
        assert charmap.is_defined_non_whitespace_printable('\t') is False
        assert charmap.is_defined_non_whitespace_printable('\n') is False
        
        # Test non-printable characters
        assert charmap.is_defined_non_whitespace_printable('\x00') is False
        assert charmap.is_defined_non_whitespace_printable('\x1f') is False

    def test_is_defined_non_whitespace_printable_unicode(self):
        """Test Unicode character handling."""
        # Test Unicode characters
        assert charmap.is_defined_non_whitespace_printable('ñ') is True
        assert charmap.is_defined_non_whitespace_printable('€') is True
        assert charmap.is_defined_non_whitespace_printable('α') is True
        
        # Test undefined characters
        assert charmap.is_defined_non_whitespace_printable('\udc00') is False

    def test_is_emoji_basic(self):
        """Test emoji detection functionality."""
        # Test emoji characters
        assert charmap.is_emoji('😀') is True
        assert charmap.is_emoji('🚀') is True
        assert charmap.is_emoji('🎮') is True
        
        # Test non-emoji characters
        assert charmap.is_emoji('A') is False
        assert charmap.is_emoji('1') is False
        assert charmap.is_emoji('@') is False

    def test_is_emoji_edge_cases(self):
        """Test emoji detection edge cases."""
        # Test emoji ranges
        assert charmap.is_emoji('😊') is True  # Emoticons range
        assert charmap.is_emoji('🌍') is True  # Misc Symbols range
        assert charmap.is_emoji('🚗') is True  # Transport range
        assert charmap.is_emoji('🤖') is True  # Supplemental range
        assert charmap.is_emoji('⚡') is True  # Misc Symbols range
        # Skip complex emoji with modifiers for now
        # assert charmap.is_emoji('✈️') is True  # Dingbats range
        # assert charmap.is_emoji('🇺🇸') is True  # Regional Indicator range

    def test_emoji_ranges_constant(self):
        """Test that EMOJI_RANGES constant is properly defined."""
        assert hasattr(charmap, 'EMOJI_RANGES')
        assert isinstance(charmap.EMOJI_RANGES, list)
        assert len(charmap.EMOJI_RANGES) > 0

    def test_is_defined_non_whitespace_printable_valueerror(self):
        """Test ValueError handling in is_defined_non_whitespace_printable."""
        # Test with a character that causes ValueError in unicodedata.name()
        # This should trigger the except ValueError: return False path
        result = charmap.is_defined_non_whitespace_printable('\x00')  # NULL character
        assert result is False

    def test_unicode_generator_with_priority_function(self):
        """Test the unicode_generator_with_priority function."""
        from glitchygames.tools.charmap import unicode_generator_with_priority
        
        # Test that the function exists and is callable
        assert callable(unicode_generator_with_priority)
        
        # Test that it generates some characters
        chars = list(unicode_generator_with_priority())
        assert len(chars) > 0
        
        # Test that generated characters are valid
        for char in chars[:5]:  # Test first 5 characters
            assert isinstance(char, str)
            assert len(char) == 1
        
        # Test that the function handles duplicate characters correctly
        # This should trigger the continue statement on line 76
        chars_set = set(chars)
        assert len(chars_set) == len(chars), "Function should not generate duplicate characters"
        
        # Test that ranges are tuples of two integers
        for range_tuple in charmap.EMOJI_RANGES:
            assert isinstance(range_tuple, tuple)
            assert len(range_tuple) == 2
            assert isinstance(range_tuple[0], int)
            assert isinstance(range_tuple[1], int)
            assert range_tuple[0] < range_tuple[1]

    def test_max_chars_constant(self):
        """Test that MAX_CHARS_TO_DISPLAY constant is properly defined."""
        assert hasattr(charmap, 'MAX_CHARS_TO_DISPLAY')
        assert isinstance(charmap.MAX_CHARS_TO_DISPLAY, int)
        assert charmap.MAX_CHARS_TO_DISPLAY > 0


class TestCanvasInterfacesCoverage(unittest.TestCase):
    """Test canvas interfaces module coverage."""

    def test_canvas_interface_protocol(self):
        """Test that CanvasInterface protocol is properly defined."""
        from glitchygames.tools.canvas_interfaces import CanvasInterface
        
        # Test that the protocol exists and has expected methods
        assert hasattr(CanvasInterface, '__annotations__')
        
        # Test that required methods are in the protocol
        required_methods = ['get_pixel_at', 'set_pixel_at', 'get_dimensions', 'get_pixel_data']
        for method in required_methods:
            assert hasattr(CanvasInterface, method)

    def test_sprite_serializer_abstract_base(self):
        """Test that SpriteSerializer abstract base class is properly defined."""
        from glitchygames.tools.canvas_interfaces import SpriteSerializer
        
        # Test that it's an abstract base class
        assert hasattr(SpriteSerializer, '__abstractmethods__')
        
        # Test that required methods are abstract (actual method names from the code)
        required_methods = ['save', 'load']
        for method in required_methods:
            assert hasattr(SpriteSerializer, method)

    def test_animated_canvas_interface_protocol(self):
        """Test that AnimatedCanvasInterface protocol is properly defined."""
        from glitchygames.tools.canvas_interfaces import AnimatedCanvasInterface
        
        # Test that the protocol exists (protocols don't have __abstractmethods__)
        assert AnimatedCanvasInterface is not None
        
        # Test that required methods are in the protocol
        required_methods = ['get_current_frame', 'set_current_frame']
        for method in required_methods:
            assert hasattr(AnimatedCanvasInterface, method)

    def test_animated_canvas_renderer_protocol(self):
        """Test that AnimatedCanvasRenderer protocol is properly defined."""
        from glitchygames.tools.canvas_interfaces import AnimatedCanvasRenderer
        
        # Test that the protocol exists (protocols don't have __abstractmethods__)
        assert AnimatedCanvasRenderer is not None
        
        # Test that required methods are in the protocol
        required_methods = ['render', 'force_redraw']
        for method in required_methods:
            assert hasattr(AnimatedCanvasRenderer, method)

    def test_animated_sprite_serializer_protocol(self):
        """Test that AnimatedSpriteSerializer protocol is properly defined."""
        from glitchygames.tools.canvas_interfaces import AnimatedSpriteSerializer
        
        # Test that the protocol exists (protocols don't have __abstractmethods__)
        assert AnimatedSpriteSerializer is not None
        
        # Test that required methods are in the protocol
        required_methods = ['save', 'load']
        for method in required_methods:
            assert hasattr(AnimatedSpriteSerializer, method)


class TestFilmStripCoverage(unittest.TestCase):
    """Test film strip module coverage."""

    def test_film_strip_import(self):
        """Test that FilmStripWidget can be imported."""
        from glitchygames.tools.film_strip import FilmStripWidget
        
        # Test that the class exists
        assert FilmStripWidget is not None
        assert hasattr(FilmStripWidget, '__init__')

    def test_film_strip_basic_functionality(self):
        """Test basic FilmStripWidget functionality."""
        patchers = MockFactory.setup_pygame_mocks()
        try:
            from glitchygames.tools.film_strip import FilmStripWidget
            
            # Test that we can create an instance with required arguments
            film_strip = FilmStripWidget(x=10, y=20, width=100, height=50)
            assert film_strip is not None
            
            # Test basic properties
            assert hasattr(film_strip, 'rect')
            assert hasattr(film_strip, 'animated_sprite')
            assert hasattr(film_strip, 'current_animation')
            assert hasattr(film_strip, 'current_frame')
            
        finally:
            MockFactory.teardown_pygame_mocks(patchers)

    def test_film_strip_methods_exist(self):
        """Test that FilmStripWidget has expected methods."""
        patchers = MockFactory.setup_pygame_mocks()
        try:
            from glitchygames.tools.film_strip import FilmStripWidget
            
            film_strip = FilmStripWidget(x=10, y=20, width=100, height=50)
            
            # Test that expected methods exist
            expected_methods = ['render', 'handle_click', 'handle_hover', 'set_animated_sprite']
            for method in expected_methods:
                assert hasattr(film_strip, method)
                assert callable(getattr(film_strip, method))
                
        finally:
            MockFactory.teardown_pygame_mocks(patchers)


class TestBitmappyBasicCoverage(unittest.TestCase):
    """Test basic bitmappy module coverage."""

    def test_bitmappy_imports(self):
        """Test that bitmappy module can be imported."""
        from glitchygames.tools.bitmappy import BitmapEditorScene, AnimatedCanvasSprite
        
        # Test that main classes exist
        assert BitmapEditorScene is not None
        assert AnimatedCanvasSprite is not None

    def test_bitmappy_constants(self):
        """Test that bitmappy constants are properly defined."""
        from glitchygames.tools.bitmappy import (
            CONTENT_PREVIEW_LENGTH,
            MAX_PIXELS_ACROSS,
            MIN_PIXELS_ACROSS,
            MAX_PIXELS_TALL,
            MIN_PIXELS_TALL
        )
        
        # Test that constants exist and have expected values
        assert isinstance(CONTENT_PREVIEW_LENGTH, int)
        assert CONTENT_PREVIEW_LENGTH > 0
        
        assert isinstance(MAX_PIXELS_ACROSS, int)
        assert MAX_PIXELS_ACROSS > 0
        
        assert isinstance(MIN_PIXELS_ACROSS, int)
        assert MIN_PIXELS_ACROSS > 0
        
        assert isinstance(MAX_PIXELS_TALL, int)
        assert MAX_PIXELS_TALL > 0
        
        assert isinstance(MIN_PIXELS_TALL, int)
        assert MIN_PIXELS_TALL > 0

    def test_bitmappy_logging_setup(self):
        """Test that bitmappy logging is properly set up."""
        from glitchygames.tools.bitmappy import LOG
        
        # Test that LOG exists and is properly configured
        assert LOG is not None
        assert hasattr(LOG, 'debug')
        assert hasattr(LOG, 'info')
        assert hasattr(LOG, 'warning')
        assert hasattr(LOG, 'error')

    def test_bitmappy_ai_import_handling(self):
        """Test that AI import is handled gracefully."""
        from glitchygames.tools.bitmappy import ai
        
        # Test that ai is either imported or None
        assert ai is None or hasattr(ai, 'client')

    def test_bitmappy_sprite_debug_setting(self):
        """Test that BitmappySprite debug setting is configured."""
        from glitchygames.tools.bitmappy import BitmappySprite
        
        # Test that DEBUG is set
        assert hasattr(BitmappySprite, 'DEBUG')
        assert isinstance(BitmappySprite.DEBUG, bool)


if __name__ == "__main__":
    unittest.main()
