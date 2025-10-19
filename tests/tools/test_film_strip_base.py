"""Base test class for film strip tests with performance optimizations."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import bitmappy, film_strip

from tests.mocks.test_mock_factory import MockFactory

# Test constants to avoid magic values
MIN_FILM_STRIP_WIDTH = 300
FRAME_INDEX_2 = 2
FRAME_SIZE = 32
MAGENTA_PIXELS = (255, 0, 255)
FRAME_DURATION = 0.5
UPDATE_ITERATIONS = 10
CLICK_OFFSET = 50
PIXEL_SIZE = 16
PIXELS_ACROSS = 32
PIXELS_TALL = 32
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 600
CANVAS_OFFSET = 20
MIN_HEIGHT_OFFSET = 20


class FilmStripTestBase:
    """Base class for film strip tests with optimized setup and caching."""
    
    @classmethod
    def setup_class(cls):
        """Set up pygame mocks and cached objects for all tests."""
        cls.patchers = MockFactory.setup_pygame_mocks()
        for patcher in cls.patchers:
            patcher.start()
        
        # Pre-create commonly used objects for performance
        cls._setup_cached_objects()
    
    @classmethod
    def teardown_class(cls):
        """Tear down pygame mocks and clear cache."""
        MockFactory.teardown_pygame_mocks(cls.patchers)
        MockFactory.clear_cache()
    
    @classmethod
    def _setup_cached_objects(cls):
        """Pre-create commonly used objects to improve test performance."""
        # Create cached animated sprite
        cls.cached_sprite = MockFactory.create_animated_sprite_mock(
            animation_name="idle",
            frame_size=(FRAME_SIZE, FRAME_SIZE),
            pixel_color=MAGENTA_PIXELS,
            use_cache=True
        )
        
        # Create cached scene mock
        cls.cached_scene_mock = MockFactory.create_optimized_scene_mock(
            pixels_across=PIXELS_ACROSS,
            pixels_tall=PIXELS_TALL,
            pixel_size=PIXEL_SIZE,
            use_cache=True
        )
    
    def create_optimized_scene(self, options=None):
        """Create an optimized scene with minimal overhead."""
        if options is None:
            options = {
                "pixels_across": PIXELS_ACROSS, 
                "pixels_tall": PIXELS_TALL,
                "pixel_size": PIXEL_SIZE
            }
        
        with patch("pygame.display.get_surface") as mock_display:
            mock_display.return_value = Mock()
            mock_display.return_value.get_width.return_value = DISPLAY_WIDTH
            mock_display.return_value.get_height.return_value = DISPLAY_HEIGHT
            
            return bitmappy.BitmapEditorScene(options=options)
    
    def create_optimized_sprite(self, animation_name="idle", **kwargs):
        """Create an optimized sprite using cached objects."""
        return MockFactory.create_animated_sprite_mock(
            animation_name=animation_name,
            frame_size=(FRAME_SIZE, FRAME_SIZE),
            pixel_color=MAGENTA_PIXELS,
            use_cache=True,
            **kwargs
        )
    
    def setup_scene_with_sprite(self, sprite=None, options=None):
        """Set up a scene with a sprite loaded, optimized for performance."""
        if sprite is None:
            sprite = self.cached_sprite
        
        scene = self.create_optimized_scene(options)
        scene._on_sprite_loaded(sprite)
        return scene, sprite
