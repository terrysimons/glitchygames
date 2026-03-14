"""Base test class for film strip tests with performance optimizations."""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import bitmappy

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        # Use real pygame initialization since BitmapEditorScene requires it
        pygame.init()
        pygame.display.set_mode((DISPLAY_WIDTH, DISPLAY_HEIGHT))

        # Pre-create commonly used objects for performance
        self._setup_cached_objects()
        # Store mocker for use in subclasses
        self._mocker = mocker

        yield

        pygame.quit()

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

        # Replace mock frame images with real pygame Surfaces so that
        # film strip rendering (pygame.transform.scale, etc.) works correctly
        cls._replace_mock_images_with_real_surfaces(cls.cached_sprite)

        # Create cached scene mock
        cls.cached_scene_mock = MockFactory.create_optimized_scene_mock(
            pixels_across=PIXELS_ACROSS,
            pixels_tall=PIXELS_TALL,
            pixel_size=PIXEL_SIZE,
            use_cache=True
        )

    @staticmethod
    def _replace_mock_images_with_real_surfaces(mock_sprite):
        """Replace mock frame images with real pygame Surfaces.

        The MockFactory creates Mock() objects for frame images, but film strip
        rendering needs real pygame Surfaces for operations like
        pygame.transform.scale(). This method replaces them after pygame.init().
        """
        for animation_name, frames in mock_sprite._animations.items():
            for frame in frames:
                frame_size = frame.get_size()
                real_surface = pygame.Surface(frame_size, pygame.SRCALPHA)
                # Fill with the frame's pixel color if available
                pixel_data = frame.get_pixel_data()
                if pixel_data:
                    real_surface.fill(pixel_data[0][:3])
                frame.image = real_surface

    def create_optimized_scene(self, options=None, mocker=None):
        """Create an optimized scene with minimal overhead."""
        if options is None:
            options = {
                "pixels_across": PIXELS_ACROSS,
                "pixels_tall": PIXELS_TALL,
                "pixel_size": PIXEL_SIZE
            }

        return bitmappy.BitmapEditorScene(options=options)

    def create_optimized_sprite(self, animation_name="idle", **kwargs):
        """Create an optimized sprite using cached objects."""
        sprite = MockFactory.create_animated_sprite_mock(
            animation_name=animation_name,
            frame_size=(FRAME_SIZE, FRAME_SIZE),
            pixel_color=MAGENTA_PIXELS,
            use_cache=True,
            **kwargs
        )
        self._replace_mock_images_with_real_surfaces(sprite)
        return sprite

    def setup_scene_with_sprite(self, sprite=None, options=None):
        """Set up a scene with a sprite loaded, optimized for performance."""
        if sprite is None:
            sprite = self.cached_sprite

        scene = self.create_optimized_scene(options)
        scene._on_sprite_loaded(sprite)
        return scene, sprite
