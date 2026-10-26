"""Bitmappy's sprite library: its TOML sprites load, draw, animate and survive a save.

The sprite library (AI training data, and the sprites the editor's dialogs open) is package
data, read through ``bitmappy.SPRITE_CONFIG_DIR``. Moved with Bitmappy from the engine's
glitchygames.testing.sprite_files (the engine runs them on its own sprites in
tests/sprites/test_engine_sprite_files.py);
those checks run here on every sprite in the library too, as Papyrus's do on its sprites.
"""

import logging
import time

import numpy as np
import pygame
import pytest

from bitmappy import SPRITE_CONFIG_DIR
from glitchygames.display_mode import set_display_mode
from glitchygames.sprites import SpriteFactory
from glitchygames.testing import sprite_files

# Constants for test thresholds
PIXEL_INTEGRITY_THRESHOLD = 100.0  # every pixel draws exactly as expected
MAX_REASONABLE_DIMENSION = 1000
MAX_ASPECT_RATIO = 10.0
MIN_ASPECT_RATIO = 0.1
MAX_LOAD_TIME = 1.0
MAX_RENDER_TIME = 0.1
# The library's size when it moved with Bitmappy (2026-10-26)
SPRITE_LIBRARY_FILE_COUNT = 71

LOG = logging.getLogger(__name__)

SPRITE_LIBRARY_FILES = sorted(SPRITE_CONFIG_DIR.glob('*.toml'))
ANIMATED_SPRITE_LIBRARY_FILES = [
    sprite_file
    for sprite_file in SPRITE_LIBRARY_FILES
    if '[[animation]]' in sprite_file.read_text(encoding='utf-8')
]


def sprite_file_id(sprite_file):
    """Name a sprite file by its file name (``battle_axe.toml``).

    Returns:
        The file's name.

    """
    return sprite_file.name


def _load_example_sprite(sprite_file):
    """Load a library sprite: the library is shipped data, so every sprite must load.

    Returns:
        The sprite. Any load error fails the test, naming the sprite.

    """
    try:
        sprite = SpriteFactory.load_sprite(filename=str(sprite_file))
    except (ValueError, FileNotFoundError, AttributeError, TypeError, KeyError, OSError) as error:
        pytest.fail(f'Library sprite {sprite_file.name} failed to load: {error!r}')
    return sprite


class TestBitmappySpriteLibrary:
    """Bitmappy's sprite library (bitmappy/resources/sprites) loads, draws and animates."""

    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        set_display_mode(size=(800, 600))

        # Bitmappy's sprite library, package data
        self.sprites_dir = SPRITE_CONFIG_DIR

    def test_sprite_pixel_integrity(self):
        """Test pixel data integrity for a sample of sprites."""
        # Test a sample of sprites for pixel integrity
        test_sprites = [
            'battle_axe.toml',
            'berry_bush.toml',
            'big_heart.toml',
            'book.toml',
            'colors.toml',
        ]

        for sprite_name in test_sprites:
            sprite_file = self.sprites_dir / sprite_name
            assert sprite_file.exists(), f'The named sample {sprite_name} is not in the library'

            # Load sprite
            sprite = _load_example_sprite(sprite_file)

            # Test pixel integrity: every visible pixel is drawn as it is, and transparent
            # pixels (magenta keyed out, alpha 0) show the background (BUGS.md #133)
            assert sprite.image is not None
            background_color = (0, 0, 0)
            original_pixels = self._expected_drawn_pixels(
                surface=sprite.image, background_color=background_color
            )

            # Draw to a test surface: 32-bit without per-pixel alpha, so the result does not
            # depend on the display's pixel format
            test_surface = pygame.Surface(sprite.image.get_size(), depth=32)
            test_surface.fill(background_color)
            test_surface.blit(sprite.image, (0, 0))

            drawn_pixels = self._extract_pixel_data(test_surface)

            # Calculate match percentage
            pixel_matches = np.all(original_pixels == drawn_pixels, axis=2)
            match_percentage = float(pixel_matches.mean()) * 100

            assert match_percentage >= PIXEL_INTEGRITY_THRESHOLD, (
                f'Pixel integrity too low for {sprite_name}: {match_percentage:.1f}%'
            )

    def test_sprite_dimensions_consistency(self):
        """Test that sprite dimensions are consistent and reasonable."""
        # Test a sample of sprites
        test_sprites = [
            'battle_axe.toml',
            'berry_bush.toml',
            'big_heart.toml',
            'book.toml',
            'colors.toml',
            'dirt.toml',
            'grass1.toml',
            'key.toml',
            'sword.toml',
        ]

        for sprite_name in test_sprites:
            sprite_file = self.sprites_dir / sprite_name
            assert sprite_file.exists(), f'The named sample {sprite_name} is not in the library'

            sprite = _load_example_sprite(sprite_file)
            assert sprite.image is not None
            width, height = sprite.image.get_size()

            # Check dimensions are reasonable
            assert width > 0, f'{sprite_name} width should be positive'
            assert height > 0, f'{sprite_name} height should be positive'
            assert width < MAX_REASONABLE_DIMENSION, f'{sprite_name} width should be reasonable'
            assert height < MAX_REASONABLE_DIMENSION, f'{sprite_name} height should be reasonable'

            # Check aspect ratio is reasonable
            aspect_ratio = width / height if height > 0 else 1
            assert aspect_ratio < MAX_ASPECT_RATIO, f'{sprite_name} aspect ratio too wide'
            assert aspect_ratio > MIN_ASPECT_RATIO, f'{sprite_name} aspect ratio too tall'

    def test_animated_sprites(self):
        """Test animated sprites in the examples directory."""
        # Look for animated sprites (colors.toml is known to be animated)
        animated_sprites = ['colors.toml']

        for sprite_name in animated_sprites:
            sprite_file = self.sprites_dir / sprite_name
            assert sprite_file.exists(), f'The named sample {sprite_name} is not in the library'

            sprite = _load_example_sprite(sprite_file)

            # Check if it's an animated sprite
            if hasattr(sprite, 'animations'):
                assert sprite.animations is not None, (
                    f'Animated sprite {sprite_name} should have animations'
                )
                assert len(sprite.animations) > 0, (
                    f'Animated sprite {sprite_name} should have at least one animation'
                )

                # Check each animation
                for anim_name, frames in sprite.animations.items():
                    assert frames is not None, f'Animation {anim_name} should have frames'
                    assert len(frames) > 0, f'Animation {anim_name} should have at least one frame'

                    # Check each frame
                    for i, frame in enumerate(frames):
                        assert frame.image is not None, (
                            f'Frame {i} in {anim_name} should have an image'
                        )
                        assert isinstance(frame.image, pygame.Surface), (
                            f'Frame {i} in {anim_name} should be a Surface'
                        )

    def test_sprite_performance(self):
        """Test sprite loading and rendering performance."""
        # Test a sample of sprites for performance
        test_sprites = [
            'battle_axe.toml',
            'berry_bush.toml',
            'big_heart.toml',
            'book.toml',
            'colors.toml',
        ]

        for sprite_name in test_sprites:
            sprite_file = self.sprites_dir / sprite_name
            assert sprite_file.exists(), f'The named sample {sprite_name} is not in the library'

            # Time the loading
            start_time = time.time()
            sprite = _load_example_sprite(sprite_file)
            load_time = time.time() - start_time

            # Time the rendering
            assert sprite.image is not None
            start_time = time.time()
            test_surface = pygame.Surface(sprite.image.get_size(), depth=32)
            test_surface.blit(sprite.image, (0, 0))
            render_time = time.time() - start_time

            # Verify performance is reasonable
            assert load_time < MAX_LOAD_TIME, f'{sprite_name} loading too slow: {load_time:.3f}s'
            assert render_time < MAX_RENDER_TIME, (
                f'{sprite_name} rendering too slow: {render_time:.3f}s'
            )

    @staticmethod
    def _expected_drawn_pixels(*, surface, background_color):
        """Return the RGB pixels a surface should draw over an opaque background.

        A fully transparent pixel (alpha 0, or the surface's colorkey) shows the background;
        any other pixel keeps its own RGB (the sampled sprites have no translucent colors).

        Returns:
            np.ndarray: The expected pixels, a (width, height, 3) array.

        """
        rgb_pixels = pygame.surfarray.array3d(surface)
        is_transparent = np.zeros(surface.get_size(), dtype=bool)
        if surface.get_flags() & pygame.SRCALPHA:
            is_transparent |= pygame.surfarray.array_alpha(surface) == 0
        colorkey = surface.get_colorkey()
        if colorkey is not None:
            is_transparent |= np.all(rgb_pixels == colorkey[:3], axis=2)
        rgb_pixels[is_transparent] = background_color
        return rgb_pixels

    @staticmethod
    def _extract_pixel_data(surface):
        """Extract a surface's RGB pixels in bulk.

        Returns:
            np.ndarray: A (width, height, 3) array.

        """
        return pygame.surfarray.array3d(surface)


@pytest.fixture
def display():
    """Give AnimatedSprite a real display for loading and saving."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(96, 64))


def test_every_library_sprite_is_checked():
    """The checks below run on the whole library, its animated sprites among them."""
    assert len(SPRITE_LIBRARY_FILES) == SPRITE_LIBRARY_FILE_COUNT
    assert ANIMATED_SPRITE_LIBRARY_FILES


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', SPRITE_LIBRARY_FILES, ids=sprite_file_id)
def test_every_library_sprite_loads(sprite_file):
    """Each sprite in the library loads, with a drawable image (a failure names the sprite)."""
    sprite = _load_example_sprite(sprite_file)

    assert isinstance(sprite.image, pygame.Surface), f'{sprite_file.name} should have an image'
    width, height = sprite.image.get_size()
    assert width > 0, f'{sprite_file.name} width should be positive'
    assert height > 0, f'{sprite_file.name} height should be positive'


@pytest.mark.parametrize('sprite_file', SPRITE_LIBRARY_FILES, ids=sprite_file_id)
def test_rows_have_equal_lengths(sprite_file):
    """Every pixel row of a library sprite is the same width."""
    sprite_files.check_rows_have_equal_lengths(sprite_file=sprite_file)


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', ANIMATED_SPRITE_LIBRARY_FILES, ids=sprite_file_id)
def test_animation_timings_survive_a_save_round_trip(sprite_file, tmp_path):
    """Save writes each animation's timing back."""
    sprite_files.check_animation_timings_survive_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', SPRITE_LIBRARY_FILES, ids=sprite_file_id)
def test_hitboxes_survive_a_save_round_trip_unchanged(sprite_file, tmp_path):
    """Save writes exactly the hitboxes the file defined."""
    sprite_files.check_hitboxes_survive_a_save_round_trip_unchanged(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', SPRITE_LIBRARY_FILES, ids=sprite_file_id)
def test_pixels_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load, save and reload give every frame the same pixels."""
    sprite_files.check_pixels_survive_a_save_round_trip(sprite_file=sprite_file, directory=tmp_path)


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', SPRITE_LIBRARY_FILES, ids=sprite_file_id)
def test_metadata_survives_a_save_round_trip(sprite_file, tmp_path):
    """Name, description, frame_anchor and hitbox survive a save."""
    sprite_files.check_metadata_survives_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', SPRITE_LIBRARY_FILES, ids=sprite_file_id)
def test_transitions_survive_a_save_round_trip(sprite_file, tmp_path):
    """Every [[transition]] is written back in order."""
    sprite_files.check_transitions_survive_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )
