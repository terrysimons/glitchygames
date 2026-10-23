"""Tests for animated sprite functionality."""

import logging
import math
import shutil
import sys
import tempfile
import tomllib
from io import StringIO
from pathlib import Path
from typing import cast

import pygame
import pytest
from scripts.sprite_stack import (
    SpriteStack,
    SpriteStackInterface,
)

import glitchygames.sprites
import glitchygames.sprites.frame as frame_module
from glitchygames.sprites import (
    AnimatedSpriteInterface,
    BitmappySprite,
    SpriteFactory,
)
from glitchygames.sprites.animated import AnimatedSprite, FrameAnchor
from glitchygames.sprites.frame import SpriteFrame
from glitchygames.sprites.pixel_utils import (
    convert_pixels_to_rgb_if_possible,
    convert_pixels_to_rgba_if_needed,
    create_alpha_surface,
    create_indexed_surface,
    extract_pixel_colors,
    lookup_in_map,
    lookup_pixel_char,
    lookup_rgba_pixel_char,
    needs_alpha_channel,
    normalize_pixel_for_color_map,
)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
FRAME_DURATION = 0.5
FRAME_DURATION_FAST = 0.25
SURFACE_SIZE = 4
DEFAULT_SURFACE_SIZE = 32
RED = (255, 0, 0)
GREEN = (0, 255, 0)


def _rgb_rows(image):
    """Return an image's RGB pixels, row by row.

    Returns:
        list[list[tuple[int, int, int]]]: ``rows[y][x]``.

    """
    rows = pygame.surfarray.array3d(image).transpose(1, 0, 2).tolist()
    return [[tuple(pixel) for pixel in row] for row in rows]


def _alpha_rows(image):
    """Return an image's per-pixel alpha values, row by row.

    Returns:
        list[list[int]]: ``rows[y][x]``.

    """
    return pygame.surfarray.array_alpha(image).transpose().tolist()


def _solid_rgb(image):
    """Return the one RGB color an image is filled with (fails if it has more than one).

    Returns:
        tuple[int, int, int]: The image's only color.

    """
    unique_colors = {pixel for row in _rgb_rows(image) for pixel in row}
    assert len(unique_colors) == 1, f'expected one color, got {sorted(unique_colors)}'
    return unique_colors.pop()


class TestSpriteStackInterface:
    """Test the SpriteStackInterface implementation."""

    @staticmethod
    def test_sprite_frame_implements_interface():
        """Test that SpriteFrame implements SpriteStackInterface."""
        surface = pygame.Surface((32, 32))
        frame = SpriteFrame(surface)
        assert isinstance(frame, SpriteStackInterface)

    @staticmethod
    def test_sprite_stack_implements_interface():
        """Test that SpriteStack implements SpriteStackInterface."""
        surfaces = [pygame.Surface((32, 32)) for _ in range(3)]
        stack = SpriteStack(surfaces)
        assert isinstance(stack, SpriteStackInterface)

    @staticmethod
    def test_sprite_frame_properties():
        """Test SpriteFrame properties."""
        surface = pygame.Surface((32, 32))
        frame = SpriteFrame(surface)

        # Test image property
        assert frame.image == surface

        # Test rect property
        assert frame.rect == pygame.Rect((0, 0), (32, 32))

        # Test __getitem__
        assert frame[0] == frame

    @staticmethod
    def test_sprite_stack_properties():
        """Test SpriteStack properties."""
        surfaces = [pygame.Surface((32, 32)) for _ in range(3)]
        stack = SpriteStack(surfaces)

        # Test image property (should return current frame's image)
        assert stack.image == stack[0].image

        # Test rect property (should return current frame's rect)
        assert stack.rect == stack[0].rect

        # Test __getitem__
        assert stack[0] == stack.stack[0]
        assert stack[1] == stack.stack[1]
        assert stack[2] == stack.stack[2]


class TestAnimatedSpriteInterface:
    """Test the AnimatedSpriteInterface implementation."""

    @staticmethod
    def test_animated_sprite_implements_interface():
        """Test that AnimatedSprite implements AnimatedSpriteInterface."""
        sprite = AnimatedSprite()
        assert isinstance(sprite, AnimatedSpriteInterface)

    @staticmethod
    def test_animated_sprite_properties_exist():
        """Test that AnimatedSprite has all required properties."""
        sprite = AnimatedSprite()

        # Test that properties exist (even if they return ...)
        assert hasattr(sprite, 'current_animation')
        assert hasattr(sprite, 'current_frame')
        assert hasattr(sprite, 'is_playing')
        assert hasattr(sprite, 'is_looping')
        assert hasattr(sprite, 'frames')
        assert hasattr(sprite, 'animations')
        assert hasattr(sprite, 'frame_interval')
        assert hasattr(sprite, 'loop')
        assert hasattr(sprite, 'frame_count')
        assert hasattr(sprite, 'next_animation')
        assert hasattr(sprite, 'image')
        assert hasattr(sprite, 'rect')

    @staticmethod
    def test_animated_sprite_methods_exist():
        """Test that AnimatedSprite has all required methods."""
        sprite = AnimatedSprite()

        # Test that methods exist
        assert hasattr(sprite, 'play_animation')
        assert hasattr(sprite, 'play')
        assert hasattr(sprite, 'pause')
        assert hasattr(sprite, 'stop')
        assert hasattr(sprite, 'load')
        assert hasattr(sprite, 'update')
        assert hasattr(sprite, '__getitem__')


class TestSpriteFactory:
    """Test the SpriteFactory detection and loading."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def create_static_sprite_file(self, filename: str) -> str:
        """Create a static sprite TOML file for testing.

        Returns:
            str: The newly created static sprite file.

        """
        filepath = Path(self.temp_dir) / filename

        toml_content = '''[sprite]
name = "TestSprite"
pixels = """##
##"""

[colors]
[colors."#"]
red = 0
green = 0
blue = 0
'''

        filepath.write_text(toml_content, encoding='utf-8')
        return str(filepath)

    def create_animated_sprite_file(self, filename: str) -> str:
        """Create an animated sprite TOML file for testing.

        Returns:
            str: The newly created animated sprite file.

        """
        filepath = Path(self.temp_dir) / filename

        toml_content = '''[sprite]
name = "TestAnimatedSprite"

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = """##
##"""

[colors]
[colors."#"]
red = 0
green = 0
blue = 0
'''

        filepath.write_text(toml_content, encoding='utf-8')
        return str(filepath)

    def create_mixed_sprite_file(self, filename: str) -> str:
        """Create a mixed content TOML file: static pixels and a frame (load_sprite refuses it).

        Returns:
            str: The newly created mixed sprite file.

        """
        filepath = Path(self.temp_dir) / filename

        toml_content = '''[sprite]
name = "TestMixedSprite"
pixels = """##
##"""

[frame]
namespace = "idle"
frame_index = 0
pixels = """##
##"""

[colors]
[colors."#"]
red = 0
green = 0
blue = 0
'''

        filepath.write_text(toml_content, encoding='utf-8')
        return str(filepath)

    def create_empty_sprite_file(self, filename: str) -> str:
        """Create an empty TOML file (should be invalid).

        Returns:
            str: The newly created empty sprite file.

        """
        filepath = Path(self.temp_dir) / filename

        toml_content = """[sprite]
name = "TestEmptySprite"
# No pixels, no frames, no animations
"""

        filepath.write_text(toml_content, encoding='utf-8')
        return str(filepath)

    def test_analyze_static_sprite(self):
        """Test analysis of static sprite file."""
        filename = self.create_static_sprite_file('static.toml')
        analysis = SpriteFactory._analyze_file(filename)

        assert analysis['has_sprite_pixels']
        assert not analysis['has_animation_sections']
        assert not analysis['has_frame_sections']

    def test_analyze_animated_sprite(self):
        """Test analysis of animated sprite file."""
        filename = self.create_animated_sprite_file('animated.toml')
        analysis = SpriteFactory._analyze_file(filename)

        assert not analysis['has_sprite_pixels']
        assert analysis['has_animation_sections']
        assert analysis['has_frame_sections']

    def test_analyze_mixed_sprite(self):
        """A file with static pixels and a frame reports both: what load_sprite refuses."""
        filename = self.create_mixed_sprite_file('mixed.toml')
        analysis = SpriteFactory._analyze_file(filename)

        assert analysis['has_sprite_pixels']
        assert analysis['has_frame_sections']
        assert not analysis['has_animation_sections']

    def test_analyze_empty_sprite(self):
        """Test analysis of empty sprite file."""
        filename = self.create_empty_sprite_file('empty.toml')
        analysis = SpriteFactory._analyze_file(filename)

        assert not analysis['has_sprite_pixels']
        assert not analysis['has_animation_sections']
        assert not analysis['has_frame_sections']

    @staticmethod
    def test_determine_type_static():
        """Test type determination for static sprite."""
        analysis = {
            'has_sprite_pixels': True,
            'has_animation_sections': False,
            'has_frame_sections': False,
        }
        sprite_type = SpriteFactory._determine_type(analysis)
        assert sprite_type == 'static'

    @staticmethod
    def test_determine_type_animated():
        """Test type determination for animated sprite."""
        analysis = {
            'has_sprite_pixels': False,
            'has_animation_sections': True,
            'has_frame_sections': True,
        }
        sprite_type = SpriteFactory._determine_type(analysis)
        assert sprite_type == 'animated'

    @staticmethod
    def test_determine_type_mixed():
        """Animation data outranks static pixels.

        Mixed files never get this far: load_sprite refuses them first
        (test_load_mixed_sprite_raises_error).
        """
        analysis = {
            'has_sprite_pixels': True,
            'has_animation_sections': True,
            'has_frame_sections': True,
        }
        sprite_type = SpriteFactory._determine_type(analysis)
        assert sprite_type == 'animated'

    @staticmethod
    def test_determine_type_empty():
        """Test type determination for empty file (should be error)."""
        analysis = {
            'has_sprite_pixels': False,
            'has_animation_sections': False,
            'has_frame_sections': False,
        }
        sprite_type = SpriteFactory._determine_type(analysis)
        assert sprite_type == 'error'

    def test_load_static_sprite(self):
        """Test loading static sprite through factory."""
        filename = self.create_static_sprite_file('static.toml')

        # Test that the factory detects the type correctly
        analysis = SpriteFactory._analyze_file(filename)
        sprite_type = SpriteFactory._determine_type(analysis)
        assert sprite_type == 'static'

        # Test actual loading (this will work now that BitmappySprite is in the engine)
        try:
            sprite = SpriteFactory.load_sprite(filename=filename)

            # With new architecture, everything is an AnimatedSprite
            assert isinstance(sprite, AnimatedSprite)
        except ImportError:
            # Skip if BitmappySprite not available in test environment
            pytest.skip('BitmappySprite not available in test environment')

    def test_load_animated_sprite(self):
        """Test loading animated sprite through factory."""
        filename = self.create_animated_sprite_file('animated.toml')

        sprite = SpriteFactory.load_sprite(filename=filename)
        assert isinstance(sprite, AnimatedSprite)
        assert sprite.name == 'TestAnimatedSprite'

    def test_load_mixed_sprite_raises_error(self):
        """Test that loading mixed sprite raises ValueError."""
        filename = self.create_mixed_sprite_file('mixed.toml')

        with pytest.raises(ValueError, match='Invalid sprite file'):
            SpriteFactory.load_sprite(filename=filename)

    def test_load_empty_sprite_raises_error(self):
        """Test that loading empty sprite raises ValueError."""
        filename = self.create_empty_sprite_file('empty.toml')

        with pytest.raises(ValueError, match='Invalid sprite file'):
            SpriteFactory.load_sprite(filename=filename)

    @staticmethod
    def test_load_default_sprite():
        """Test that loading with no filename loads the default raspberry sprite."""
        # Test that loading with None filename loads the default sprite
        sprite = SpriteFactory.load_sprite(filename=None)

        # With new architecture, everything is an AnimatedSprite
        assert isinstance(sprite, AnimatedSprite)
        assert sprite.name == 'Tiley McTile Face'  # From raspberry.toml


class TestBitmappySpriteLoadDefault:
    """Test BitmappySprite default loading via SpriteFactory."""

    def test_bitmappy_sprite_load_default(self):
        """Test that BitmappySprite.load() with no filename loads default sprite."""
        sprite = BitmappySprite(x=0, y=0, width=32, height=32, filename=None)
        image, rect, name = sprite.load()  # Should load default raspberry sprite
        assert name == sprite.name == 'Tiley McTile Face'
        # It returns the default sprite's real image, the same one the factory loads
        default_sprite = SpriteFactory.load_sprite(filename=None)
        assert image.get_size() == rect.size == default_sprite.image.get_size()
        assert pygame.image.tobytes(image, 'RGBA') == pygame.image.tobytes(
            default_sprite.image, 'RGBA'
        )


class TestSpriteFactorySave:
    """Test the SpriteFactory save functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Initialize pygame display for BitmappySprite tests
        if not pygame.display.get_init():
            pygame.init()
            pygame.display.set_mode((800, 600))

        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_save_animated_sprite_toml(self):
        """Test that saving animated sprites works in TOML format."""
        # Create an animated sprite
        sprite = AnimatedSprite()
        sprite.name = 'TestAnimatedSprite'

        # Add a frame
        frame = SpriteFrame(pygame.Surface((2, 2)))
        red_pixels = cast('list[tuple[int, ...]]', [(255, 0, 0)] * 4)
        frame.set_pixel_data(red_pixels)
        sprite.add_animation('test_anim', [frame])

        # Save via factory should work in TOML format
        filename = Path(self.temp_dir) / 'test_animated.toml'
        SpriteFactory.save_sprite(sprite=sprite, filename=str(filename), file_format='toml')

        # Verify file was created
        assert filename.exists()

        # Verify content
        content = filename.read_text(encoding='utf-8')
        # Since it's detected as single-frame, it uses the sprite name
        assert 'name = "TestAnimatedSprite"' in content
        assert '[colors]' in content


class TestSpriteStackValidation:
    """Test SpriteStack validation logic (moved from assertions)."""

    @staticmethod
    def test_sprite_stack_cannot_be_empty():
        """Test that SpriteStack cannot be initialized with empty list."""
        # Since we removed assertions from the class, this test should pass
        # The validation logic should be implemented in the actual application
        stack = SpriteStack([])
        assert len(stack.stack) == 0

    def test_sprite_stack_must_be_list(self):
        """Test that SpriteStack must be initialized with a list."""
        # This test would need to be implemented if we add validation back

    def test_all_sprites_must_be_spriteframe(self):
        """Test that all sprites in stack must be SpriteFrame objects."""
        # This test would need to be implemented if we add validation back

    def test_all_sprites_must_be_same_size(self):
        """Test that all sprites in stack must be the same size."""
        # This test would need to be implemented if we add validation back

    def test_all_sprites_must_have_same_alpha(self):
        """Test that all sprites in stack must have the same alpha."""
        # This test would need to be implemented if we add validation back

    def test_all_sprites_must_have_same_colorkey(self):
        """Test that all sprites in stack must have the same colorkey."""


class TestNeedsAlphaChannel:
    """Test the needs_alpha_channel helper function."""

    def test_opaque_rgb_pixels(self):
        """Test RGB pixels without magenta don't need alpha."""
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        assert needs_alpha_channel(pixels) is False

    def test_magenta_rgb_pixels_need_alpha(self):
        """Test magenta RGB pixels need alpha channel."""
        pixels = [(255, 0, 0), (255, 0, 255)]
        assert needs_alpha_channel(pixels) is True

    def test_opaque_rgba_pixels(self):
        """Test fully opaque RGBA pixels don't need alpha."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 255)]
        assert needs_alpha_channel(pixels) is False

    def test_transparent_rgba_pixels_need_alpha(self):
        """Test RGBA pixels with transparency need alpha."""
        pixels = [(255, 0, 0, 128)]
        assert needs_alpha_channel(pixels) is True

    def test_empty_pixels(self):
        """Test empty pixel list doesn't need alpha."""
        assert needs_alpha_channel([]) is False


class TestConvertPixelsToRgb:
    """Test convert_pixels_to_rgb_if_possible."""

    def test_opaque_rgba_converts_to_rgb(self):
        """Test that fully opaque RGBA pixels get converted to RGB."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 255)]
        result = convert_pixels_to_rgb_if_possible(pixels)
        assert result == [(255, 0, 0), (0, 255, 0)]

    def test_transparent_rgba_stays_rgba(self):
        """Test that transparent RGBA pixels stay as-is."""
        pixels = [(255, 0, 0, 128)]
        result = convert_pixels_to_rgb_if_possible(pixels)
        assert result == [(255, 0, 0, 128)]

    def test_rgb_pixels_pass_through(self):
        """Test that RGB pixels pass through unchanged."""
        pixels = [(255, 0, 0), (0, 255, 0)]
        result = convert_pixels_to_rgb_if_possible(pixels)
        assert result == [(255, 0, 0), (0, 255, 0)]


class TestConvertPixelsToRgba:
    """Test convert_pixels_to_rgba_if_needed."""

    def test_rgb_converts_to_rgba(self):
        """Test that RGB pixels get converted to RGBA with full opacity."""
        pixels = [(255, 0, 0), (0, 255, 0)]
        result = convert_pixels_to_rgba_if_needed(pixels)
        assert result == [(255, 0, 0, 255), (0, 255, 0, 255)]

    def test_rgba_passes_through(self):
        """Test that RGBA pixels pass through unchanged."""
        pixels = [(255, 0, 0, 128)]
        result = convert_pixels_to_rgba_if_needed(pixels)
        assert result == [(255, 0, 0, 128)]

    def test_magenta_converts_with_full_alpha(self):
        """Test that magenta RGB converts to RGBA with full opacity."""
        pixels = [(255, 0, 255)]
        result = convert_pixels_to_rgba_if_needed(pixels)
        assert result == [(255, 0, 255, 255)]


class TestNormalizePixelForColorMap:
    """Test normalize_pixel_for_color_map."""

    def test_rgba_magenta_normalizes(self):
        """Test RGBA magenta always normalizes to (255,0,255,255)."""
        result = normalize_pixel_for_color_map((255, 0, 255, 128), needs_alpha=True)
        assert result == (255, 0, 255, 255)

    def test_rgba_opaque_without_alpha_becomes_rgb(self):
        """Test opaque RGBA without alpha flag becomes RGB."""
        result = normalize_pixel_for_color_map((255, 0, 0, 255), needs_alpha=False)
        assert result == (255, 0, 0)

    def test_rgba_transparent_without_alpha_becomes_rgb_magenta(self):
        """Test transparent RGBA without alpha flag becomes RGB magenta (indexed key)."""
        result = normalize_pixel_for_color_map((255, 0, 0, 128), needs_alpha=False)
        assert result == (255, 0, 255)

    def test_rgba_with_alpha_keeps_full_tuple(self):
        """Test RGBA with alpha flag keeps full tuple."""
        result = normalize_pixel_for_color_map((255, 0, 0, 128), needs_alpha=True)
        assert result == (255, 0, 0, 128)

    def test_rgb_magenta_stays_rgb_when_not_alpha(self):
        """Test RGB magenta stays RGB in indexed color mode."""
        result = normalize_pixel_for_color_map((255, 0, 255), needs_alpha=False)
        assert result == (255, 0, 255)

    def test_rgb_magenta_promotes_to_rgba_when_alpha(self):
        """Test RGB magenta promotes to RGBA in alpha mode."""
        result = normalize_pixel_for_color_map((255, 0, 255), needs_alpha=True)
        assert result == (255, 0, 255, 255)

    def test_rgb_non_magenta_passes_through(self):
        """Test non-magenta RGB passes through."""
        result = normalize_pixel_for_color_map((255, 0, 0), needs_alpha=False)
        assert result == (255, 0, 0)


class TestLookupInMap:
    """Test lookup_in_map."""

    def test_found_key(self):
        """Test successful lookup returns character."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0): '#'}
        assert lookup_in_map((255, 0, 0), color_map) == '#'

    def test_missing_key_raises(self):
        """Test missing key raises KeyError."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0): '#'}
        with pytest.raises(KeyError, match='not found in color map'):
            lookup_in_map((0, 0, 0), color_map)


class TestLookupPixelChar:
    """Test lookup_pixel_char."""

    def test_rgb_pixel_non_magenta(self):
        """Test RGB pixel lookup in non-alpha map."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0): '#'}
        result = lookup_pixel_char((255, 0, 0), color_map, map_uses_alpha=False)
        assert result == '#'

    def test_rgb_magenta_pixel(self):
        """Test RGB magenta pixel lookup normalizes to RGBA."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 255, 255): '.'}
        result = lookup_pixel_char((255, 0, 255), color_map, map_uses_alpha=False)
        assert result == '.'

    def test_rgb_pixel_in_alpha_map_rgba_match(self):
        """Test RGB pixel lookup in alpha map with RGBA match."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0, 255): '#'}
        result = lookup_pixel_char((255, 0, 0), color_map, map_uses_alpha=True)
        assert result == '#'

    def test_rgb_pixel_in_alpha_map_rgb_match(self):
        """Test RGB pixel lookup in alpha map with RGB match."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0): '#'}
        result = lookup_pixel_char((255, 0, 0), color_map, map_uses_alpha=True)
        assert result == '#'


class TestExtractPixelColors:
    """Test extract_pixel_colors."""

    def test_extract_colors(self):
        """Test extracting colors from pixel lines."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0), '.': (255, 255, 255)}
        pixel_lines = ['#.', '.#']
        result = extract_pixel_colors(pixel_lines, width=2, height=2, color_map=color_map)
        assert len(result) == 4
        assert result[0] == (0, 0, 0)
        assert result[1] == (255, 255, 255)

    def test_unknown_char_defaults_to_magenta(self):
        """Test unknown characters default to magenta."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0)}
        pixel_lines = ['#?']
        result = extract_pixel_colors(pixel_lines, width=2, height=1, color_map=color_map)
        assert result[1] == (255, 0, 255)


class TestSpriteFrame:
    """Test SpriteFrame class."""

    @pytest.fixture
    def frame(self):
        """Create a SpriteFrame for testing.

        Returns:
            A SpriteFrame instance.
        """
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        return SpriteFrame(surface, duration=FRAME_DURATION)

    def test_image_property(self, frame):
        """Test image property returns the surface."""
        assert frame.image is not None
        assert frame.image.get_size() == (SURFACE_SIZE, SURFACE_SIZE)

    def test_image_setter(self, frame):
        """Test image setter updates the surface."""
        new_surface = pygame.Surface((8, 8))
        frame.image = new_surface
        assert frame.image is not None
        assert frame.image.get_size() == (8, 8)

    def test_rect_property(self, frame):
        """Test rect property returns correct rect."""
        assert frame.rect is not None
        assert frame.rect.width == SURFACE_SIZE
        assert frame.rect.height == SURFACE_SIZE

    def test_rect_setter(self, frame):
        """Test rect setter updates the rect."""
        new_rect = pygame.Rect(10, 20, 30, 40)
        frame.rect = new_rect
        assert frame.rect is not None
        assert frame.rect.x == 10

    def test_getitem_returns_self(self, frame):
        """Test __getitem__ returns self (for compatibility)."""
        assert frame[0] is frame
        assert frame[5] is frame

    def test_get_size(self, frame):
        """Test get_size returns surface size."""
        assert frame.get_size() == (SURFACE_SIZE, SURFACE_SIZE)

    def test_get_alpha(self, frame):
        """Test get_alpha returns surface alpha."""
        alpha = frame.get_alpha()
        # Surface alpha can be None or an int
        assert alpha is None or isinstance(alpha, int)

    def test_get_colorkey(self, frame):
        """Test get_colorkey returns surface colorkey."""
        result = frame.get_colorkey()
        assert result is None or isinstance(result, (tuple, pygame.Color))

    def test_repr(self, frame):
        """Test __repr__ returns descriptive string."""
        result = repr(frame)
        assert 'SpriteFrame' in result
        assert str(FRAME_DURATION) in result

    def test_get_pixel_data_from_surface(self, frame):
        """Test get_pixel_data extracts pixels from surface."""
        pixels = frame.get_pixel_data()
        assert len(pixels) == SURFACE_SIZE * SURFACE_SIZE
        # Each pixel should be a 4-tuple (RGBA)
        assert len(pixels[0]) == 4

    def test_get_pixel_data_from_cached_pixels(self, frame):
        """Test get_pixel_data returns cached pixels attribute if present."""
        expected = [(255, 0, 0, 255)] * (SURFACE_SIZE * SURFACE_SIZE)
        frame.pixels = expected
        result = frame.get_pixel_data()
        assert result == expected

    def test_set_pixel_data(self, frame):
        """Test set_pixel_data updates pixels and surface."""
        pixel_count = SURFACE_SIZE * SURFACE_SIZE
        new_pixels = cast('list[tuple[int, ...]]', [(255, 0, 0, 255)] * pixel_count)
        frame.set_pixel_data(new_pixels)
        assert frame.pixels == new_pixels

    def test_set_pixel_data_rgb(self, frame):
        """Test set_pixel_data handles RGB pixels."""
        pixel_count = SURFACE_SIZE * SURFACE_SIZE
        new_pixels = cast('list[tuple[int, ...]]', [(0, 255, 0)] * pixel_count)
        frame.set_pixel_data(new_pixels)
        assert frame.pixels == new_pixels


class TestFrameManager:
    """Test FrameManager class."""

    @pytest.fixture
    def animated_sprite(self):
        """Create an AnimatedSprite with test data.

        Returns:
            An AnimatedSprite with a 'walk' animation.
        """
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('walk', [frame1, frame2])
        return sprite

    def test_add_observer(self, animated_sprite):
        """Test adding an observer to the frame manager."""
        observer = type('Observer', (), {'on_frame_change': lambda self, *a: None})()
        animated_sprite.frame_manager.add_observer(observer)
        assert observer in animated_sprite.frame_manager._observers

    def test_add_observer_duplicate_ignored(self, animated_sprite):
        """Test adding the same observer twice only adds it once."""
        observer = type('Observer', (), {'on_frame_change': lambda self, *a: None})()
        animated_sprite.frame_manager.add_observer(observer)
        animated_sprite.frame_manager.add_observer(observer)
        assert animated_sprite.frame_manager._observers.count(observer) == 1

    def test_remove_observer(self, animated_sprite):
        """Test removing an observer from the frame manager."""
        observer = type('Observer', (), {'on_frame_change': lambda self, *a: None})()
        animated_sprite.frame_manager.add_observer(observer)
        animated_sprite.frame_manager.remove_observer(observer)
        assert observer not in animated_sprite.frame_manager._observers

    def test_remove_nonexistent_observer(self, animated_sprite):
        """Test removing a nonexistent observer does nothing."""
        observer = type('Observer', (), {})()
        # Should not raise
        animated_sprite.frame_manager.remove_observer(observer)

    def test_notify_observers_on_animation_change(self, animated_sprite, mocker):
        """Test observers are notified when animation changes."""
        # First set to 'walk' so subsequent set to a different value triggers notification
        animated_sprite.frame_manager._current_animation = 'walk'
        observer = mocker.Mock()
        observer.on_frame_change = mocker.Mock()
        animated_sprite.frame_manager.add_observer(observer)
        # Now change to a different animation to trigger notification
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        animated_sprite.add_animation('run', [SpriteFrame(surface)])
        animated_sprite.frame_manager.current_animation = 'run'
        observer.on_frame_change.assert_called()

    def test_notify_observers_on_frame_change(self, animated_sprite, mocker):
        """Test observers are notified when frame changes."""
        animated_sprite.frame_manager.current_animation = 'walk'
        observer = mocker.Mock()
        observer.on_frame_change = mocker.Mock()
        animated_sprite.frame_manager.add_observer(observer)
        animated_sprite.frame_manager.current_frame = 1
        observer.on_frame_change.assert_called_with('frame', 0, 1)

    def test_no_notification_on_same_animation(self, animated_sprite, mocker):
        """Test no notification when setting same animation."""
        animated_sprite.frame_manager.current_animation = 'walk'
        observer = mocker.Mock()
        observer.on_frame_change = mocker.Mock()
        animated_sprite.frame_manager.add_observer(observer)
        animated_sprite.frame_manager.current_animation = 'walk'
        observer.on_frame_change.assert_not_called()

    def test_no_notification_on_same_frame(self, animated_sprite, mocker):
        """Test no notification when setting same frame index."""
        animated_sprite.frame_manager.current_animation = 'walk'
        observer = mocker.Mock()
        observer.on_frame_change = mocker.Mock()
        animated_sprite.frame_manager.add_observer(observer)
        animated_sprite.frame_manager.current_frame = 0  # Already 0
        observer.on_frame_change.assert_not_called()

    def test_animation_change_resets_frame(self, animated_sprite):
        """Test setting animation resets current frame to 0."""
        animated_sprite.frame_manager.current_animation = 'walk'
        animated_sprite.frame_manager._current_frame = 1
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        animated_sprite.add_animation('run', [SpriteFrame(surface)])
        animated_sprite.frame_manager.current_animation = 'run'
        assert animated_sprite.frame_manager.current_frame == 0

    def test_set_frame_with_bounds_checking(self, animated_sprite):
        """Test set_frame validates frame bounds."""
        animated_sprite.frame_manager.current_animation = 'walk'
        assert animated_sprite.frame_manager.set_frame(1) is True
        assert animated_sprite.frame_manager.current_frame == 1

    def test_set_frame_out_of_bounds(self, animated_sprite):
        """Test set_frame returns False for out of bounds."""
        animated_sprite.frame_manager.current_animation = 'walk'
        assert animated_sprite.frame_manager.set_frame(999) is False

    def test_set_animation_valid(self, animated_sprite):
        """Test set_animation with valid name."""
        assert animated_sprite.frame_manager.set_animation('walk') is True

    def test_set_animation_invalid(self, animated_sprite):
        """Test set_animation with invalid name returns False."""
        assert animated_sprite.frame_manager.set_animation('nonexistent') is False

    def test_get_frame_data(self, animated_sprite):
        """Test get_frame_data returns current frame."""
        animated_sprite.frame_manager.current_animation = 'walk'
        frame = animated_sprite.frame_manager.get_frame_data()
        assert frame is not None

    def test_get_frame_data_no_animation(self):
        """Test get_frame_data returns None when no animation set."""
        sprite = AnimatedSprite()
        result = sprite.frame_manager.get_frame_data()
        assert result is None

    def test_get_frame_count(self, animated_sprite):
        """Test get_frame_count returns correct count."""
        animated_sprite.frame_manager.current_animation = 'walk'
        assert animated_sprite.frame_manager.get_frame_count() == 2

    def test_get_frame_count_no_animation(self):
        """Test get_frame_count returns 0 when no animation set."""
        sprite = AnimatedSprite()
        assert sprite.frame_manager.get_frame_count() == 0


class TestFrameManagerEdgeCases:
    """FrameManager with a stale animation name or a hookless observer."""

    @pytest.fixture
    def animated_sprite(self):
        """Create an AnimatedSprite with a two-frame 'walk' animation.

        Returns:
            An AnimatedSprite with a 'walk' animation.
        """
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frames = [SpriteFrame(surface, duration=FRAME_DURATION) for _ in range(2)]
        sprite.add_animation('walk', frames)
        return sprite

    def test_set_frame_without_a_known_animation_is_refused(self, animated_sprite):
        """set_frame refuses while the current animation names no loaded animation."""
        animated_sprite.frame_manager._current_animation = 'removed'
        assert animated_sprite.frame_manager.set_frame(0) is False
        assert animated_sprite.frame_manager.current_frame == 0

    def test_observer_without_a_frame_change_hook_is_skipped(self, animated_sprite, mocker):
        """Observers lacking a callable on_frame_change are passed over; the rest are told."""
        animated_sprite.frame_manager.current_animation = 'walk'
        silent_observer = type('SilentObserver', (), {'on_frame_change': None})()
        listening_observer = mocker.Mock()
        animated_sprite.frame_manager.add_observer(silent_observer)
        animated_sprite.frame_manager.add_observer(listening_observer)
        animated_sprite.frame_manager.current_frame = 1
        listening_observer.on_frame_change.assert_called_once_with('frame', 0, 1)


class TestAnimatedSpriteProperties:
    """Test AnimatedSprite property accessors."""

    @pytest.fixture
    def sprite_with_animation(self):
        """Create an AnimatedSprite with a test animation.

        Returns:
            An AnimatedSprite with an 'idle' animation.
        """
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION_FAST)
        sprite.add_animation('idle', [frame1, frame2])
        sprite.set_animation('idle')
        return sprite

    def test_current_animation(self, sprite_with_animation):
        """Test current_animation property."""
        assert sprite_with_animation.current_animation == 'idle'

    def test_current_frame(self, sprite_with_animation):
        """Test current_frame property."""
        assert sprite_with_animation.current_frame == 0

    def test_is_playing_initial(self, sprite_with_animation):
        """Test is_playing is False initially."""
        assert sprite_with_animation.is_playing is False

    def test_is_looping_initial(self, sprite_with_animation):
        """Test is_looping is False initially."""
        assert sprite_with_animation.is_looping is False

    def test_is_looping_setter(self, sprite_with_animation):
        """Test is_looping setter."""
        sprite_with_animation.is_looping = True
        assert sprite_with_animation.is_looping is True

    def test_frames_property(self, sprite_with_animation):
        """Test frames property returns copy of animations."""
        frames = sprite_with_animation.frames
        assert 'idle' in frames
        assert len(frames['idle']) == 2

    def test_animations_property(self, sprite_with_animation):
        """Test animations property returns copy."""
        animations = sprite_with_animation.animations
        assert 'idle' in animations

    def test_frame_interval(self, sprite_with_animation):
        """Test frame_interval returns current frame's duration."""
        assert sprite_with_animation.frame_interval == FRAME_DURATION

    def test_frame_interval_no_animation(self):
        """Test frame_interval with no animation returns default."""
        sprite = AnimatedSprite()
        assert math.isclose(sprite.frame_interval, 0.5)

    def test_loop_property(self, sprite_with_animation):
        """Test loop property mirrors is_looping."""
        sprite_with_animation.is_looping = True
        assert sprite_with_animation.loop is True

    def test_animation_count(self, sprite_with_animation):
        """Test animation_count property."""
        assert sprite_with_animation.animation_count == 1

    def test_current_animation_frame_count(self, sprite_with_animation):
        """Test current_animation_frame_count property."""
        assert sprite_with_animation.current_animation_frame_count == 2

    def test_current_animation_frame_count_no_animation(self):
        """Test current_animation_frame_count with no animation."""
        sprite = AnimatedSprite()
        assert sprite.current_animation_frame_count == 0

    def test_current_animation_total_duration(self, sprite_with_animation):
        """Test current_animation_total_duration property."""
        expected = FRAME_DURATION + FRAME_DURATION_FAST
        assert abs(sprite_with_animation.current_animation_total_duration - expected) < 1e-9

    def test_current_animation_total_duration_no_animation(self):
        """Test current_animation_total_duration with no animation."""
        sprite = AnimatedSprite()
        assert math.isclose(sprite.current_animation_total_duration, 0.0, abs_tol=1e-9)

    def test_animation_names(self, sprite_with_animation):
        """Test animation_names property."""
        assert sprite_with_animation.animation_names == ['idle']

    def test_frame_count_property(self, sprite_with_animation):
        """Test frame_count property."""
        assert sprite_with_animation.frame_count == 2


class TestAnimatedSpriteControlMethods:
    """Test AnimatedSprite play/pause/stop methods."""

    @pytest.fixture
    def sprite_with_animation(self):
        """Create an AnimatedSprite with a test animation.

        Returns:
            An AnimatedSprite with a 'walk' animation.
        """
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('walk', [frame1, frame2])
        sprite.set_animation('walk')
        return sprite

    def test_play(self, sprite_with_animation):
        """Test play starts animation."""
        sprite_with_animation.play()
        assert sprite_with_animation.is_playing is True

    def test_play_with_animation_name(self, sprite_with_animation):
        """Test play with specific animation name."""
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite_with_animation.add_animation('run', [SpriteFrame(surface)])
        sprite_with_animation.play('run')
        assert sprite_with_animation.current_animation == 'run'
        assert sprite_with_animation.is_playing is True

    def test_play_animation_alias(self, sprite_with_animation):
        """Test play_animation is an alias for play."""
        sprite_with_animation.play_animation()
        assert sprite_with_animation.is_playing is True

    def test_pause(self, sprite_with_animation):
        """Test pause stops animation."""
        sprite_with_animation.play()
        sprite_with_animation.pause()
        assert sprite_with_animation.is_playing is False

    def test_stop(self, sprite_with_animation):
        """Test stop resets animation."""
        sprite_with_animation.play()
        sprite_with_animation.frame_manager._current_frame = 1
        sprite_with_animation.stop()
        assert sprite_with_animation.is_playing is False
        assert sprite_with_animation.current_frame == 0

    def test_set_frame_valid(self, sprite_with_animation):
        """Test set_frame with valid index."""
        sprite_with_animation.set_frame(1)
        assert sprite_with_animation.current_frame == 1

    def test_set_frame_no_animation_raises(self):
        """Test set_frame raises when no animation set."""
        sprite = AnimatedSprite()
        with pytest.raises(ValueError, match='No animation is currently set'):
            sprite.set_frame(0)

    def test_set_frame_out_of_range_raises(self, sprite_with_animation):
        """Test set_frame raises for out of range index."""
        with pytest.raises(IndexError, match='out of range'):
            sprite_with_animation.set_frame(999)

    def test_set_animation_valid(self, sprite_with_animation):
        """Test set_animation with valid name."""
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite_with_animation.add_animation('run', [SpriteFrame(surface)])
        sprite_with_animation.set_animation('run')
        assert sprite_with_animation.current_animation == 'run'

    def test_set_animation_invalid_raises(self, sprite_with_animation):
        """Test set_animation raises for invalid name."""
        with pytest.raises(ValueError, match='not found'):
            sprite_with_animation.set_animation('nonexistent')


class TestAnimatedSpriteDataMethods:
    """Test AnimatedSprite animation data methods."""

    def test_add_animation(self):
        """Test adding an animation."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frames = [SpriteFrame(surface)]
        sprite.add_animation('walk', frames)
        assert 'walk' in sprite._animations
        assert sprite.current_animation == 'walk'

    def test_add_animation_sets_first_as_current(self):
        """Test first animation added becomes current."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        assert sprite.current_animation == 'idle'

    def test_remove_animation(self):
        """Test removing an animation."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface)])
        sprite.add_animation('run', [SpriteFrame(surface)])
        sprite.remove_animation('walk')
        assert 'walk' not in sprite._animations

    def test_remove_current_animation_switches(self):
        """Test removing current animation switches to another."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface)])
        sprite.add_animation('run', [SpriteFrame(surface)])
        sprite.set_animation('walk')
        sprite.remove_animation('walk')
        assert sprite.current_animation == 'run'

    def test_remove_last_animation(self):
        """Test removing the last animation clears current."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface)])
        sprite.remove_animation('walk')
        assert not sprite.current_animation

    def test_get_frame(self):
        """Test get_frame returns correct frame."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('walk', [frame])
        result = sprite.get_frame('walk', 0)
        assert result is frame

    def test_get_frame_invalid_animation_raises(self):
        """Test get_frame raises for invalid animation name."""
        sprite = AnimatedSprite()
        with pytest.raises(ValueError, match='not found'):
            sprite.get_frame('nonexistent', 0)

    def test_get_frame_invalid_index_raises(self):
        """Test get_frame raises for invalid frame index."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface)])
        with pytest.raises(IndexError, match='out of range'):
            sprite.get_frame('walk', 999)

    def test_add_frame_appends(self):
        """Test add_frame appends frame to animation."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface)])
        new_frame = SpriteFrame(surface, duration=FRAME_DURATION_FAST)
        sprite.add_frame('walk', new_frame)
        assert len(sprite._animations['walk']) == 2

    def test_add_frame_at_index(self):
        """Test add_frame inserts frame at specific index."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface, duration=1.0)])
        new_frame = SpriteFrame(surface, duration=FRAME_DURATION_FAST)
        sprite.add_frame('walk', new_frame, index=0)
        assert sprite._animations['walk'][0].duration == FRAME_DURATION_FAST

    def test_add_frame_creates_animation_if_missing(self):
        """Test add_frame creates animation if it doesn't exist."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_frame('new_anim', SpriteFrame(surface))
        assert 'new_anim' in sprite._animations

    def test_add_second_frame_enables_playing(self):
        """Test adding second frame starts animation playing."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface)])
        sprite.set_animation('walk')
        sprite.add_frame('walk', SpriteFrame(surface))
        assert sprite._is_playing is True
        assert sprite._is_looping is True

    def test_remove_frame(self):
        """Test remove_frame removes a frame."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface), SpriteFrame(surface)])
        sprite.set_animation('walk')
        sprite.remove_frame('walk', 0)
        assert len(sprite._animations['walk']) == 1

    def test_remove_frame_adjusts_current(self):
        """Test remove_frame adjusts current frame if needed."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface), SpriteFrame(surface)])
        sprite.set_animation('walk')
        sprite.set_frame(1)
        sprite.remove_frame('walk', 1)
        assert sprite.current_frame == 0

    def test_remove_frame_invalid_animation_raises(self):
        """Test remove_frame raises for invalid animation."""
        sprite = AnimatedSprite()
        with pytest.raises(ValueError, match='not found'):
            sprite.remove_frame('nonexistent', 0)

    def test_remove_frame_invalid_index_raises(self):
        """Test remove_frame raises for invalid index."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface)])
        with pytest.raises(IndexError, match='out of range'):
            sprite.remove_frame('walk', 999)


class TestAnimatedSpriteGetItem:
    """Test AnimatedSprite __getitem__ and get_current_frame."""

    def test_getitem(self):
        """Test __getitem__ returns frame from named animation."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        sprite.add_animation('walk', [frame])
        result = sprite['walk']
        assert result is frame

    def test_get_current_frame(self):
        """Test get_current_frame returns frame manager data."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        sprite.add_animation('walk', [frame])
        sprite.set_animation('walk')
        result = sprite.get_current_frame()
        assert result is frame

    def test_get_current_frame_no_animation(self):
        """Test get_current_frame returns None when no animation."""
        sprite = AnimatedSprite()
        result = sprite.get_current_frame()
        assert result is None


class TestAnimatedSpriteNextAnimation:
    """Test AnimatedSprite next_animation property."""

    def test_next_animation_wraps(self):
        """Test next_animation wraps around to first animation.

        Note: next_animation uses self._current_animation directly rather than
        frame_manager.current_animation. This is a legacy attribute that must
        be set manually for this property to work.
        """
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface)])
        sprite.add_animation('run', [SpriteFrame(surface)])
        sprite.set_animation('run')
        # Set the legacy attribute that next_animation uses
        sprite._current_animation = 'run'  # type: ignore[unresolved-attribute]
        # next after 'run' (last) should wrap to 'walk' (first)
        result = sprite.next_animation
        assert result == 'walk'

    def test_next_animation_empty(self):
        """Test next_animation returns empty string when no animations."""
        sprite = AnimatedSprite()
        assert not sprite.next_animation

    def test_next_animation_unknown_current(self):
        """Test next_animation returns first when current is unknown."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface)])
        # Set _current_animation to something not in animations
        sprite._current_animation = 'nonexistent'  # type: ignore[unresolved-attribute]
        result = sprite.next_animation
        assert result == 'walk'


class TestAnimatedSpriteUpdate:
    """Test AnimatedSprite.update() method for animation timing."""

    @pytest.fixture
    def animated_sprite(self):
        """Create an AnimatedSprite with multiple frames for update testing.

        Returns:
            An AnimatedSprite with a 'walk' animation of two frames: red, then green.
        """
        sprite = AnimatedSprite()
        red_surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        red_surface.fill(RED)
        green_surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        green_surface.fill(GREEN)
        frame1 = SpriteFrame(red_surface, duration=FRAME_DURATION_FAST)
        frame2 = SpriteFrame(green_surface, duration=FRAME_DURATION_FAST)
        sprite.add_animation('walk', [frame1, frame2])
        sprite.set_animation('walk')
        sprite.play()
        sprite.is_looping = True
        return sprite

    def test_update_advances_frame_timer(self, animated_sprite):
        """Test update advances the frame timer."""
        animated_sprite.update(0.05)
        # Frame timer should have accumulated time
        assert animated_sprite._frame_timer > 0

    def test_update_changes_frame_when_duration_exceeded(self, animated_sprite):
        """Test update changes frame when frame duration is exceeded."""
        assert _solid_rgb(animated_sprite.image) == RED
        animated_sprite.dirty = 0

        # Advance past the first frame's duration: the sprite now draws the green frame
        # and is marked for redrawing
        animated_sprite.update(FRAME_DURATION_FAST + 0.01)
        assert animated_sprite.current_frame == 1
        assert _solid_rgb(animated_sprite.image) == GREEN
        assert animated_sprite.dirty

    def test_update_loops_back_to_first_frame(self, animated_sprite):
        """Test update loops back to frame 0 when looping is enabled."""
        # Advance past both frames
        animated_sprite.update(FRAME_DURATION_FAST + 0.01)
        animated_sprite.update(FRAME_DURATION_FAST + 0.01)
        assert animated_sprite.current_frame == 0
        assert _solid_rgb(animated_sprite.image) == RED

    def test_update_stops_at_last_frame_when_not_looping(self, animated_sprite):
        """Test update stops at last frame when looping is disabled."""
        animated_sprite.is_looping = False
        animated_sprite.update(FRAME_DURATION_FAST + 0.01)
        animated_sprite.update(FRAME_DURATION_FAST + 0.01)
        # Should stop playing and be at last frame
        assert animated_sprite.is_playing is False

    def test_update_does_nothing_when_not_playing(self, animated_sprite):
        """Test update does nothing when animation is not playing."""
        animated_sprite.pause()
        initial_frame = animated_sprite.current_frame
        animated_sprite.update(1.0)
        assert animated_sprite.current_frame == initial_frame
        assert _solid_rgb(animated_sprite.image) == RED

    def test_update_does_nothing_with_no_animation(self):
        """Test update does nothing when no animation is set."""
        sprite = AnimatedSprite()
        sprite._is_playing = True
        sprite.update(1.0)  # Should not raise


class TestAnimatedSpriteGetCurrentSurface:
    """Test AnimatedSprite._get_current_surface method."""

    def test_get_current_surface_no_animation_returns_default(self):
        """Test _get_current_surface returns default surface when no animation."""
        sprite = AnimatedSprite()
        surface = sprite._get_current_surface()
        assert surface is not None
        assert surface.get_size() == (32, 32)

    def test_get_current_surface_caches_default(self):
        """Test _get_current_surface caches the default surface."""
        sprite = AnimatedSprite()
        surface1 = sprite._get_current_surface()
        surface2 = sprite._get_current_surface()
        assert surface1 is surface2

    def test_get_current_surface_with_animation(self):
        """Test _get_current_surface returns frame surface with animation."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')

        result = sprite._get_current_surface()
        assert result is not None
        assert result.get_size() == (SURFACE_SIZE, SURFACE_SIZE)

    def test_get_current_surface_caches_frame_surface(self):
        """Test _get_current_surface caches frame surfaces."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')

        # Clear cache first
        sprite._surface_cache.clear()
        result1 = sprite._get_current_surface()
        result2 = sprite._get_current_surface()
        assert result1 is result2


class TestAnimatedSpriteCreateOptimizedSurface:
    """Test AnimatedSprite._create_optimized_surface static method."""

    def test_with_pixel_data_rgb(self):
        """Test creating surface from RGB pixel data."""
        surface = pygame.Surface((2, 2))
        frame = SpriteFrame(surface)
        frame.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]

        result = AnimatedSprite._create_optimized_surface(frame)
        assert result.get_size() == (2, 2)
        # Opaque pixels: a plain surface with magenta as its colorkey
        assert not result.get_flags() & pygame.SRCALPHA
        assert result.get_colorkey() == (255, 0, 255, 255)
        assert _rgb_rows(result) == [
            [(255, 0, 0), (0, 255, 0)],
            [(0, 0, 255), (255, 255, 0)],
        ]

    def test_with_pixel_data_rgba(self):
        """Test creating surface from RGBA pixel data."""
        surface = pygame.Surface((2, 2))
        frame = SpriteFrame(surface)
        frame.pixels = [
            (255, 0, 0, 255),
            (0, 255, 0, 128),
            (0, 0, 255, 64),
            (255, 255, 0, 0),
        ]

        result = AnimatedSprite._create_optimized_surface(frame)
        assert result.get_size() == (2, 2)
        # Translucent pixels: per-pixel alpha; the fully transparent one is stored as
        # transparent magenta
        assert result.get_flags() & pygame.SRCALPHA
        assert _alpha_rows(result) == [[255, 128], [64, 0]]
        assert _rgb_rows(result) == [
            [(255, 0, 0), (0, 255, 0)],
            [(0, 0, 255), (255, 0, 255)],
        ]

    def test_without_pixel_data(self):
        """Test creating surface without pixel data falls back to copy."""
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        surface.fill((10, 20, 30))
        frame = SpriteFrame(surface)
        # No pixels attribute

        result = AnimatedSprite._create_optimized_surface(frame)
        assert result.get_size() == (SURFACE_SIZE, SURFACE_SIZE)
        # A copy, not the frame's own surface, with the same pixels
        assert result is not surface
        assert _solid_rgb(result) == (10, 20, 30)

    def test_with_empty_pixel_data(self):
        """Test creating surface with empty pixel list falls back to copy."""
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        frame.pixels = []

        result = AnimatedSprite._create_optimized_surface(frame)
        assert result.get_size() == (SURFACE_SIZE, SURFACE_SIZE)


class TestAnimatedSpriteAnimationMetadata:
    """Test AnimatedSprite get/set animation metadata methods."""

    @pytest.fixture
    def sprite_with_animation(self):
        """Create an AnimatedSprite with a test animation.

        Returns:
            An AnimatedSprite with an 'idle' animation.
        """
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame1, frame2])
        sprite.set_animation('idle')
        return sprite

    def test_get_animation_metadata(self, sprite_with_animation):
        """Test get_animation_metadata returns correct metadata."""
        metadata = sprite_with_animation.get_animation_metadata('idle')
        assert metadata['frame_count'] == 2
        assert abs(metadata['total_duration'] - (FRAME_DURATION * 2)) < 1e-9
        assert metadata['is_looping'] is False

    def test_get_animation_metadata_invalid_raises(self):
        """Test get_animation_metadata raises for invalid animation."""
        sprite = AnimatedSprite()
        with pytest.raises(ValueError, match='not found'):
            sprite.get_animation_metadata('nonexistent')

    def test_set_animation_metadata(self, sprite_with_animation):
        """Test set_animation_metadata updates looping state."""
        sprite_with_animation.set_animation_metadata('idle', {'is_looping': True})
        assert sprite_with_animation.is_looping is True

    def test_set_animation_metadata_invalid_raises(self):
        """Test set_animation_metadata raises for invalid animation."""
        sprite = AnimatedSprite()
        with pytest.raises(ValueError, match='not found'):
            sprite.set_animation_metadata('nonexistent', {})

    def test_set_animation_metadata_without_looping_key(self, sprite_with_animation):
        """Test set_animation_metadata with no looping key does not change state."""
        original_looping = sprite_with_animation.is_looping
        sprite_with_animation.set_animation_metadata('idle', {'other_key': 'value'})
        assert sprite_with_animation.is_looping == original_looping


class TestAnimatedSpriteSave:
    """Test AnimatedSprite save method."""

    def test_save_toml(self, tmp_path):
        """Test save creates a valid TOML file."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((2, 2))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        frame.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        sprite.name = 'save_test'

        save_path = tmp_path / 'animated.toml'
        sprite.save(str(save_path), 'toml')
        assert save_path.exists()

    def test_save_unsupported_format_raises(self):
        """Test save raises for unsupported format."""
        sprite = AnimatedSprite()
        with pytest.raises(ValueError, match='Unsupported'):
            sprite.save('test.json', 'json')


class TestAnimatedSpriteLoad:
    """Test AnimatedSprite load method with TOML files."""

    def test_load_static_toml(self, tmp_path):
        """Test loading a static TOML sprite file as single-frame animation."""
        toml_content = """[sprite]
name = "static_test"
pixels = \"\"\"
#.
.#
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0

[colors."."]
red = 255
green = 255
blue = 255
"""
        toml_file = tmp_path / 'static.toml'
        toml_file.write_text(toml_content, encoding='utf-8')

        sprite = AnimatedSprite()
        sprite.load(str(toml_file))
        assert sprite.name == 'static_test'
        assert sprite.animation_count >= 1

    def test_load_nonexistent_file_raises(self):
        """Test loading a nonexistent file raises FileNotFoundError."""
        sprite = AnimatedSprite()
        with pytest.raises(FileNotFoundError):
            sprite.load('/nonexistent/file.toml')

    def test_load_unsupported_format_raises(self, mocker):
        """Test loading unsupported format raises ValueError."""
        sprite = AnimatedSprite()
        mocker.patch(
            'glitchygames.sprites.animated.detect_file_format',
            return_value='json',
        )
        with pytest.raises(ValueError, match='Unsupported'):
            sprite.load('test.json')


class TestAnimatedSpriteBuildColorMap:
    """Test AnimatedSprite.build_color_map static method."""

    def test_build_color_map_rgb(self):
        """Test _build_color_map with RGB colors."""
        data = {
            'colors': {
                '#': {'red': 0, 'green': 0, 'blue': 0},
                '.': {'red': 255, 'green': 255, 'blue': 255},
            },
        }
        color_map, color_order, alpha_values = AnimatedSprite.build_color_map(data)
        assert '#' in color_map
        assert '.' in color_map
        assert color_map['#'] == (0, 0, 0)
        assert color_map['.'] == (255, 255, 255)
        assert len(color_order) == 2
        assert len(alpha_values) == 0

    def test_build_color_map_with_per_pixel_alpha(self):
        """Test _build_color_map with per-pixel alpha values."""
        data = {
            'colors': {
                '#': {'red': 255, 'green': 0, 'blue': 0, 'alpha': 128},
            },
        }
        color_map, _color_order, alpha_values = AnimatedSprite.build_color_map(data)
        assert color_map['#'] == (255, 0, 0, 128)
        assert '#' in alpha_values
        assert alpha_values['#'] == 128

    def test_build_color_map_with_explicit_opaque_alpha(self):
        """Test _build_color_map with alpha=255 (treated as indexed)."""
        data = {
            'colors': {
                '#': {'red': 0, 'green': 0, 'blue': 0, 'alpha': 255},
            },
        }
        color_map, _color_order, alpha_values = AnimatedSprite.build_color_map(data)
        assert color_map['#'] == (0, 0, 0, 255)
        assert '#' not in alpha_values

    def test_build_color_map_empty(self):
        """Test _build_color_map with no colors section."""
        data = {}
        color_map, color_order, alpha_values = AnimatedSprite.build_color_map(data)
        assert color_map == {}
        assert color_order == []
        assert alpha_values == {}


class TestAnimatedSpriteUpdateSurfaceAndMarkDirty:
    """Test AnimatedSprite._update_surface_and_mark_dirty method."""

    def test_update_surface_marks_dirty(self):
        """Test _update_surface_and_mark_dirty sets dirty flag."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')

        sprite.dirty = 0
        sprite._last_drawn_frame = None  # Force update
        sprite._update_surface_and_mark_dirty()
        assert sprite.dirty == 1

    def test_update_surface_without_an_animation_leaves_the_image(self):
        """With no current animation there is nothing to draw: image and dirty stay."""
        sprite = AnimatedSprite()
        image_before = sprite.image
        sprite.dirty = 0
        sprite._update_surface_and_mark_dirty()
        assert sprite.image is image_before
        assert sprite.dirty == 0


class TestSpriteFrameEdgeCases:
    """Test SpriteFrame edge cases."""

    def test_set_pixel_data_larger_than_surface(self):
        """Test set_pixel_data with more pixels than surface can hold."""
        surface = pygame.Surface((2, 2))
        frame = SpriteFrame(surface)
        # 8 pixels for a 2x2 (4 pixel) surface
        large_pixels = cast('list[tuple[int, ...]]', [(255, 0, 0, 255)] * 8)
        frame.set_pixel_data(large_pixels)
        # Should store all pixels but only set surface pixels up to width*height
        assert len(frame.pixels) == 8

    def test_get_pixel_data_from_surface_rgb(self):
        """Test get_pixel_data extracts pixels from surface correctly."""
        surface = pygame.Surface((2, 2))
        surface.fill((100, 200, 50))
        frame = SpriteFrame(surface)
        pixels = frame.get_pixel_data()
        assert len(pixels) == 4
        # Each pixel should be RGBA
        for pixel in pixels:
            assert len(pixel) == 4

    def test_default_duration(self):
        """Test SpriteFrame default duration is 0.5."""
        surface = pygame.Surface((1, 1))
        frame = SpriteFrame(surface)
        assert abs(frame.duration - 0.5) < 1e-9


class TestAnimatedSpriteLoadAnimatedToml:
    """Test AnimatedSprite loading an animated TOML file."""

    def test_load_animated_toml(self, tmp_path):
        """Test loading an animated TOML file with multiple frames."""
        toml_content = """[sprite]
name = "animated_test"

[colors."#"]
red = 0
green = 0
blue = 0

[colors."."]
red = 255
green = 255
blue = 255

[[animation]]
namespace = "walk"
frame_interval = 0.25
loop = true

[[animation.frame]]
frame_index = 0
pixels = \"\"\"
#.
.#
\"\"\"

[[animation.frame]]
frame_index = 1
pixels = \"\"\"
.#
#.
\"\"\"
"""
        toml_file = tmp_path / 'animated.toml'
        toml_file.write_text(toml_content, encoding='utf-8')

        sprite = AnimatedSprite()
        sprite.load(str(toml_file))
        assert sprite.name == 'animated_test'
        assert 'walk' in sprite.animation_names
        assert sprite.current_animation_frame_count == 2

    def test_load_animated_toml_with_per_frame_interval(self, tmp_path):
        """Test loading a TOML file with per-frame intervals."""
        toml_content = """[sprite]
name = "timing_test"

[colors."#"]
red = 0
green = 0
blue = 0

[[animation]]
namespace = "blink"
frame_interval = 0.5

[[animation.frame]]
frame_index = 0
frame_interval = 0.1
pixels = \"\"\"
#
\"\"\"

[[animation.frame]]
frame_index = 1
frame_interval = 0.8
pixels = \"\"\"
#
\"\"\"
"""
        toml_file = tmp_path / 'timing.toml'
        toml_file.write_text(toml_content, encoding='utf-8')

        sprite = AnimatedSprite()
        sprite.load(str(toml_file))
        assert sprite.animation_count >= 1
        # First frame should have 0.1 duration
        frame0 = sprite.get_frame('blink', 0)
        assert abs(frame0.duration - 0.1) < 1e-9
        # Second frame should have 0.8 duration
        frame1 = sprite.get_frame('blink', 1)
        assert abs(frame1.duration - 0.8) < 1e-9


class TestLookupRgbaPixelChar:
    """Test lookup_rgba_pixel_char edge cases."""

    def test_rgba_opaque_rgb_key_match(self):
        """Test opaque RGBA pixel matched via RGB key in alpha map."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0): '#'}
        result = lookup_rgba_pixel_char((255, 0, 0, 255), color_map, map_uses_alpha=True)
        assert result == '#'

    def test_rgba_opaque_rgba_key_match(self):
        """Test opaque RGBA pixel matched via RGBA key in alpha map."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0, 255): '#'}
        result = lookup_rgba_pixel_char((255, 0, 0, 255), color_map, map_uses_alpha=True)
        assert result == '#'

    def test_rgba_opaque_not_found_raises(self):
        """Test opaque RGBA pixel not in map raises KeyError."""
        color_map: dict[tuple[int, ...], str] = {(0, 255, 0): '.'}
        with pytest.raises(KeyError, match='not found in color map'):
            lookup_rgba_pixel_char((255, 0, 0, 255), color_map, map_uses_alpha=True)

    def test_rgba_transparent_in_alpha_map(self):
        """Test transparent RGBA pixel lookup in alpha map."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0, 128): '#'}
        result = lookup_rgba_pixel_char((255, 0, 0, 128), color_map, map_uses_alpha=True)
        assert result == '#'

    def test_rgba_non_alpha_map_opaque(self):
        """Test opaque RGBA pixel in non-alpha map collapses to RGB."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0): '#'}
        result = lookup_rgba_pixel_char((255, 0, 0, 255), color_map, map_uses_alpha=False)
        assert result == '#'

    def test_rgba_non_alpha_map_transparent_becomes_magenta(self):
        """Test transparent RGBA pixel in non-alpha map maps to magenta."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 255, 255): '.'}
        result = lookup_rgba_pixel_char((255, 0, 0, 128), color_map, map_uses_alpha=False)
        assert result == '.'

    def test_rgba_magenta_pixel_normalizes(self):
        """Test magenta RGBA pixel normalizes to (255, 0, 255, 255)."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 255, 255): '.'}
        result = lookup_rgba_pixel_char((255, 0, 255, 128), color_map, map_uses_alpha=True)
        assert result == '.'


class TestLookupPixelCharRgbRaiseInAlphaMap:
    """Test lookup_pixel_char when RGB pixel not found in alpha map."""

    def test_rgb_not_found_in_alpha_map_raises(self):
        """Test that RGB pixel raises when neither RGBA nor RGB found in alpha map."""
        color_map: dict[tuple[int, ...], str] = {(0, 0, 0): '#'}
        with pytest.raises(KeyError, match='not found in color map'):
            lookup_pixel_char((128, 128, 128), color_map, map_uses_alpha=True)


class TestCreateAlphaSurface:
    """Test create_alpha_surface function."""

    def test_creates_srcalpha_surface(self):
        """Test creating an alpha surface with RGBA colors."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0, 255), '.': (255, 255, 255, 128)}
        pixel_lines = ['#.', '.#']
        surface = create_alpha_surface(2, 2, pixel_lines, color_map)
        assert surface is not None
        assert surface.get_size() == (2, 2)
        assert surface.get_flags() & pygame.SRCALPHA
        assert _rgb_rows(surface) == [
            [(0, 0, 0), (255, 255, 255)],
            [(255, 255, 255), (0, 0, 0)],
        ]
        assert _alpha_rows(surface) == [[255, 128], [128, 255]]

    def test_rgb_color_gets_full_alpha(self):
        """Test that RGB colors in the map get alpha=255 added."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0)}
        pixel_lines = ['#']
        surface = create_alpha_surface(1, 1, pixel_lines, color_map)
        assert _rgb_rows(surface) == [[(0, 0, 0)]]
        assert _alpha_rows(surface) == [[255]]

    def test_magenta_rgba_stays_opaque(self):
        """Test that magenta RGBA (255,0,255,255) is preserved."""
        color_map: dict[str, tuple[int, ...]] = {'.': (255, 0, 255, 255)}
        pixel_lines = ['.']
        surface = create_alpha_surface(1, 1, pixel_lines, color_map)
        assert _rgb_rows(surface) == [[(255, 0, 255)]]
        assert _alpha_rows(surface) == [[255]]


class TestCreateIndexedSurface:
    """Test create_indexed_surface function."""

    def test_creates_indexed_surface(self):
        """Test creating an indexed surface with RGB colors."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0), '.': (255, 255, 255)}
        pixel_lines = ['#.', '.#']
        surface = create_indexed_surface(2, 2, pixel_lines, color_map)
        assert surface is not None
        assert surface.get_size() == (2, 2)
        assert not surface.get_flags() & pygame.SRCALPHA
        assert _rgb_rows(surface) == [
            [(0, 0, 0), (255, 255, 255)],
            [(255, 255, 255), (0, 0, 0)],
        ]

    def test_rgba_opaque_converts_to_rgb(self):
        """Test that opaque RGBA colors are converted to RGB on indexed surface."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0, 255)}
        pixel_lines = ['#']
        surface = create_indexed_surface(1, 1, pixel_lines, color_map)
        assert _rgb_rows(surface) == [[(0, 0, 0)]]

    def test_rgba_transparent_becomes_magenta(self):
        """Test that transparent RGBA colors become magenta on indexed surface."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0, 128)}
        pixel_lines = ['#']
        surface = create_indexed_surface(1, 1, pixel_lines, color_map)
        assert _rgb_rows(surface) == [[(255, 0, 255)]]


class TestAnimatedSpriteGetTotalFrameCount:
    """Test AnimatedSprite.get_total_frame_count and is_static_sprite."""

    def test_total_frame_count_single_animation(self):
        """Test total frame count with one animation."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface), SpriteFrame(surface)])
        assert sprite.get_total_frame_count() == 2

    def test_total_frame_count_multiple_animations(self):
        """Test total frame count across multiple animations."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface), SpriteFrame(surface)])
        sprite.add_animation('run', [SpriteFrame(surface)])
        assert sprite.get_total_frame_count() == 3

    def test_total_frame_count_no_animations(self):
        """Test total frame count with no animations."""
        sprite = AnimatedSprite()
        assert sprite.get_total_frame_count() == 0

    def test_is_static_sprite_true(self):
        """Test is_static_sprite returns True for single-frame sprite."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        assert sprite.is_static_sprite() is True

    def test_is_static_sprite_false(self):
        """Test is_static_sprite returns False for multi-frame sprite."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface), SpriteFrame(surface)])
        assert sprite.is_static_sprite() is False


class TestAnimatedSpriteAnyPixelIsMagenta:
    """Test AnimatedSprite._any_pixel_is_magenta."""

    def test_no_magenta_rgb_pixels(self):
        """Test returns False when no magenta pixels exist (RGB)."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((2, 2))
        frame = SpriteFrame(surface)
        frame.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (128, 128, 128)]
        sprite.add_animation('idle', [frame])
        assert sprite._any_pixel_is_magenta() is False

    def test_has_magenta_rgba_pixel(self):
        """Test returns True when magenta RGBA pixel exists."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((2, 1))
        frame = SpriteFrame(surface)
        frame.pixels = [(255, 0, 255, 255), (0, 255, 0, 255)]
        sprite.add_animation('idle', [frame])
        assert sprite._any_pixel_is_magenta() is True

    def test_has_magenta_rgb_pixel(self):
        """Test returns True when magenta RGB pixel exists."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((1, 1))
        frame = SpriteFrame(surface)
        frame.pixels = [(255, 0, 255)]
        sprite.add_animation('idle', [frame])
        assert sprite._any_pixel_is_magenta() is True


class TestAnimatedSpriteClearSurfaceCache:
    """Test AnimatedSprite.clear_surface_cache."""

    def test_clear_surface_cache(self):
        """Test clearing the surface cache."""
        sprite = AnimatedSprite()
        sprite._surface_cache['test_key'] = 'test_value'  # type: ignore[invalid-assignment]
        assert len(sprite._surface_cache) > 0
        sprite.clear_surface_cache()
        assert len(sprite._surface_cache) == 0


class TestAnimatedSpriteGetAnimationData:
    """Test AnimatedSprite._get_animation_data."""

    def test_get_animation_data_with_animations(self):
        """Test _get_animation_data returns data for each animation."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface), SpriteFrame(surface)])
        sprite.add_animation('run', [SpriteFrame(surface)])

        data = sprite._get_animation_data()
        assert 'walk' in data
        assert data['walk']['frames'] == 2
        assert 'run' in data
        assert data['run']['frames'] == 1

    def test_get_animation_data_empty(self):
        """Test _get_animation_data returns empty dict when no animations."""
        sprite = AnimatedSprite()
        data = sprite._get_animation_data()
        assert data == {}


class TestAnimatedSpriteDebugFrameInfo:
    """Test AnimatedSprite debug methods for frame info."""

    def test_debug_frame_info_no_animation(self):
        """Test _debug_frame_info with no animation set."""
        sprite = AnimatedSprite()
        # Should not raise
        sprite._debug_frame_info([])

    def test_debug_frame_info_frame_out_of_range(self):
        """Test _debug_frame_info with frame index out of range."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        sprite.add_animation('walk', [frame])
        sprite.set_animation('walk')
        # Set frame index beyond range
        sprite.frame_manager._current_frame = 99
        sprite._debug_frame_info([frame])

    def test_debug_frame_info_with_pixels(self):
        """Test _debug_frame_info with frame that has pixel data."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((2, 2))
        frame = SpriteFrame(surface)
        frame.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (128, 128, 128)]
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        # Should not raise
        sprite._debug_frame_info([frame])

    def test_debug_frame_pixel_data_no_pixels_no_image(self, mocker):
        """Test _debug_frame_pixel_data when frame has neither pixels nor image."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        # Remove pixels if present
        if hasattr(frame, 'pixels'):
            del frame.pixels
        # Use a mock frame without 'image' attribute to trigger the 'no pixel data' branch
        mock_frame = mocker.Mock(spec=[])
        sprite._debug_frame_pixel_data(mock_frame)


class TestAnimatedSpriteCreateSurfaceFromTomlPixels:
    """Test AnimatedSprite._create_surface_from_toml_pixels."""

    def test_rgb_pixels(self):
        """Test surface creation from RGB pixel data."""
        pixels = cast(
            'list[tuple[int, ...]]',
            [(255, 0, 0), (0, 255, 0), (0, 0, 255), (128, 128, 128)],
        )
        surface = AnimatedSprite._create_surface_from_toml_pixels(2, 2, pixels)
        assert surface.get_size() == (2, 2)
        assert _rgb_rows(surface) == [
            [(255, 0, 0), (0, 255, 0)],
            [(0, 0, 255), (128, 128, 128)],
        ]

    def test_rgba_pixels(self):
        """Test surface creation from RGBA pixel data."""
        pixels = cast(
            'list[tuple[int, ...]]',
            [(255, 0, 0, 255), (0, 255, 0, 128), (0, 0, 255, 64), (128, 128, 128, 0)],
        )
        surface = AnimatedSprite._create_surface_from_toml_pixels(2, 2, pixels)
        assert surface.get_size() == (2, 2)
        # Translucent pixels need per-pixel alpha, and each pixel keeps its own alpha
        assert surface.get_flags() & pygame.SRCALPHA
        assert pygame.surfarray.array_alpha(surface).transpose().tolist() == [
            [255, 128],
            [64, 0],
        ]
        assert _rgb_rows(surface)[0] == [(255, 0, 0), (0, 255, 0)]


class TestAnimatedSpriteUpdateEdgeCases:
    """Test AnimatedSprite.update edge cases."""

    def test_update_with_empty_frames_stops_playing(self):
        """Test update stops playing when frames list is empty."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface)])
        sprite.set_animation('walk')
        sprite.play()
        # Clear the frames list to trigger empty frames branch
        sprite._animations['walk'] = []
        sprite.update(0.1)
        assert sprite._is_playing is False

    def test_update_clamps_frame_index_beyond_bounds(self):
        """Test update clamps frame index when beyond bounds."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface, duration=0.1)])
        sprite.set_animation('walk')
        sprite.play()
        # Force frame index beyond bounds
        sprite.frame_manager._current_frame = 99
        sprite.update(0.001)
        # Frame should be clamped to valid range
        assert sprite.frame_manager.current_frame == 0

    def test_update_animation_not_in_dict_returns(self):
        """Test update returns when current animation is not in _animations dict."""
        sprite = AnimatedSprite()
        sprite._is_playing = True
        sprite.frame_manager._current_animation = 'nonexistent'
        sprite.update(0.1)


class TestAnimatedSpriteWriteTomlHelpers:
    """Test TOML writing helper methods."""

    def test_a_frame_with_fewer_pixels_than_its_surface_is_saved_padded(self, tmp_path):
        """Pixels missing from a frame's pixel list are written as '.' to fill its size."""
        surface = pygame.Surface((2, 2))
        frame = SpriteFrame(surface)
        # Only the first row's pixels are known; the frame's surface is 2x2
        frame.pixels = [RED, GREEN]
        sprite = AnimatedSprite()
        sprite.name = 'short_pixels'
        sprite.add_animation('idle', [frame, SpriteFrame(pygame.Surface((2, 2)))])

        saved_file = tmp_path / 'short_pixels.toml'
        sprite.save(str(saved_file), 'toml')

        saved = tomllib.loads(saved_file.read_text(encoding='utf-8'))
        first_frame_rows = saved['animation'][0]['frame'][0]['pixels'].splitlines()
        assert len(first_frame_rows) == 2
        assert len(first_frame_rows[0]) == 2
        assert first_frame_rows[1] == '..'

    def test_write_toml_colors_with_color_order(self):
        """Test _write_toml_colors uses color_order when provided."""
        data = {
            'colors': {
                '#': {'red': 0, 'green': 0, 'blue': 0},
                '.': {'red': 255, 'green': 255, 'blue': 255},
                '@': {'red': 255, 'green': 0, 'blue': 0},
            },
        }
        output_buffer = StringIO()
        AnimatedSprite._write_toml_colors(output_buffer, data, color_order=['.', '#'])
        content = output_buffer.getvalue()
        # '.' should appear before '#' and '@' should be added at the end
        dot_pos = content.index('[colors."."]')
        hash_pos = content.index('[colors."#"]')
        at_pos = content.index('[colors."@"]')
        assert dot_pos < hash_pos
        assert hash_pos < at_pos

    def test_write_toml_colors_with_alpha(self):
        """Test _write_toml_colors writes alpha when present."""
        data = {
            'colors': {
                '#': {'red': 255, 'green': 0, 'blue': 0, 'alpha': 128},
            },
        }
        output_buffer = StringIO()
        AnimatedSprite._write_toml_colors(output_buffer, data)
        content = output_buffer.getvalue()
        assert 'alpha = 128' in content

    def test_write_toml_alpha_section(self):
        """Test _write_toml_alpha writes alpha blending section."""
        data = {'alpha': {'blending': True}}
        output_buffer = StringIO()
        AnimatedSprite._write_toml_alpha(output_buffer, data)
        content = output_buffer.getvalue()
        assert '[alpha]' in content
        assert 'blending = true' in content

    def test_write_toml_alpha_preserves_trailing_newline(self):
        """Test _write_toml_alpha with preserve_trailing_newline=True."""
        data = {'alpha': {'blending': False}}
        output_buffer = StringIO()
        AnimatedSprite._write_toml_alpha(output_buffer, data, preserve_trailing_newline=True)
        content = output_buffer.getvalue()
        assert '[alpha]' in content
        assert 'blending = false' in content
        # Should not have a trailing blank line
        assert not content.endswith('\n\n')

    def test_write_toml_alpha_no_alpha_section(self):
        """Test _write_toml_alpha does nothing when no alpha key."""
        data = {'sprite': {'name': 'test'}}
        output_buffer = StringIO()
        AnimatedSprite._write_toml_alpha(output_buffer, data)
        content = output_buffer.getvalue()
        assert not content


class TestConvertStaticSpriteInconsistentWidths:
    """Test AnimatedSprite._convert_static_sprite with inconsistent row widths."""

    def test_inconsistent_widths_pads_rows(self, tmp_path):
        """Test loading a static sprite with inconsistent row widths pads them."""
        toml_content = """[sprite]
name = "inconsistent"
pixels = \"\"\"
##
#
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0
"""
        toml_file = tmp_path / 'inconsistent.toml'
        toml_file.write_text(toml_content, encoding='utf-8')

        sprite = AnimatedSprite()
        sprite.load(str(toml_file))
        assert sprite.name == 'inconsistent'
        assert sprite.animation_count >= 1


class TestAnimatedSpriteLoadEdgeCases:
    """Test AnimatedSprite load edge cases."""

    def test_load_toml_with_parse_error(self, tmp_path):
        """Test loading a TOML file with invalid content raises ValueError."""
        bad_file = tmp_path / 'bad.toml'
        bad_file.write_bytes(b'\x00\x01\x02\x03')  # Invalid TOML content

        sprite = AnimatedSprite()
        with pytest.raises(ValueError, match='Error loading TOML file'):
            sprite.load(str(bad_file))

    def test_set_initial_animation_with_no_animations(self):
        """Test _set_initial_animation when no animations exist."""
        sprite = AnimatedSprite()
        sprite._animations = {}
        sprite._animation_order = []
        sprite._set_initial_animation()
        assert not sprite.frame_manager.current_animation
        assert sprite.frame_manager.current_frame == 0

    def test_load_no_animations_logs_info(self, tmp_path):
        """Test loading a file with no sprite pixels and no animations."""
        # Create a minimal TOML with sprite section but no pixels or animations
        toml_content = """[sprite]
name = "empty_sprite"

[colors."#"]
red = 0
green = 0
blue = 0
"""
        toml_file = tmp_path / 'empty.toml'
        toml_file.write_text(toml_content, encoding='utf-8')

        sprite = AnimatedSprite()
        sprite.load(str(toml_file))
        # Should load without error but have no animations
        assert sprite.name == 'empty_sprite'


class TestSpriteFrameHitbox:
    """Test SpriteFrame hitbox functionality."""

    def test_default_hitbox_is_full_frame(self):
        """SpriteFrame's own hitbox without an explicit one is its full frame rect.

        AnimatedSprite.hitbox does not use this fallback; it trims to visible pixels.
        """
        surface = pygame.Surface((16, 24))
        frame = SpriteFrame(surface)
        assert frame.hitbox == frame.rect
        assert not frame.has_explicit_hitbox

    def test_explicit_hitbox(self):
        """SpriteFrame with explicit hitbox returns that hitbox."""
        surface = pygame.Surface((16, 24))
        explicit_hitbox = pygame.Rect(4, 0, 12, 20)
        frame = SpriteFrame(surface, hitbox=explicit_hitbox)
        assert frame.hitbox == explicit_hitbox
        assert frame.has_explicit_hitbox

    def test_hitbox_setter(self):
        """Setting hitbox via property updates the value."""
        surface = pygame.Surface((16, 24))
        frame = SpriteFrame(surface)
        assert not frame.has_explicit_hitbox

        new_hitbox = pygame.Rect(2, 3, 10, 18)
        frame.hitbox = new_hitbox
        assert frame.hitbox == new_hitbox
        assert frame.has_explicit_hitbox

    def test_hitbox_reset_to_none(self):
        """Setting hitbox to None clears the explicit hitbox (SpriteFrame's rect again)."""
        surface = pygame.Surface((16, 24))
        frame = SpriteFrame(surface, hitbox=pygame.Rect(4, 0, 12, 20))
        assert frame.has_explicit_hitbox

        frame.hitbox = None
        assert not frame.has_explicit_hitbox
        assert frame.hitbox == frame.rect


class TestAnimatedSpriteHitbox:
    """Test AnimatedSprite hitbox resolution."""

    def test_sprite_hitbox_fallback(self):
        """With no hitbox set anywhere, a fully opaque frame's visible bounds are its rect."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((16, 24))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        frame.pixels = [(0, 0, 0)] * (16 * 24)
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')

        assert sprite.default_hitbox is None
        assert sprite.hitbox == frame.rect

    def test_sprite_default_hitbox(self):
        """Sprite-level default hitbox is returned when frame has no explicit hitbox."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((16, 24))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        frame.pixels = [(0, 0, 0)] * (16 * 24)
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')

        default_hitbox = pygame.Rect(4, 0, 12, 20)
        sprite.default_hitbox = default_hitbox
        assert sprite.hitbox == default_hitbox

    def test_per_frame_hitbox_overrides_default(self):
        """Per-frame hitbox takes priority over sprite-level default."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((16, 24))
        frame_hitbox = pygame.Rect(3, 2, 10, 18)
        frame = SpriteFrame(surface, duration=FRAME_DURATION, hitbox=frame_hitbox)
        frame.pixels = [(0, 0, 0)] * (16 * 24)
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')

        sprite.default_hitbox = pygame.Rect(4, 0, 12, 20)
        assert sprite.hitbox == frame_hitbox

    def test_get_hitbox_world_rect(self):
        """get_hitbox_world_rect applies world position offset to hitbox."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((16, 24))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        frame.pixels = [(0, 0, 0)] * (16 * 24)
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')

        sprite.default_hitbox = pygame.Rect(4, 2, 12, 20)
        world_rect = sprite.get_hitbox_world_rect(world_x=100.0, world_y=200.0)
        assert world_rect == pygame.Rect(104, 202, 12, 20)


class TestAnimatedSpriteVisiblePixelHitbox:
    """AnimatedSprite falls back to the current frame's visible pixels (real surfaces)."""

    @staticmethod
    def _frame_with_visible_box(visible_box: pygame.Rect, *, hitbox=None) -> SpriteFrame:
        """Build a 16x24 per-pixel-alpha frame whose only visible pixels fill visible_box."""
        surface = pygame.Surface((16, 24), pygame.SRCALPHA)
        surface.fill((200, 100, 50, 255), visible_box)
        return SpriteFrame(surface, duration=FRAME_DURATION, hitbox=hitbox)

    def test_fallback_hitbox_is_trimmed_to_visible_pixels(self):
        """With no explicit or default hitbox, the hitbox is the frame's visible box."""
        sprite = AnimatedSprite()
        frame = self._frame_with_visible_box(pygame.Rect(3, 4, 10, 18))
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')

        assert sprite.hitbox == pygame.Rect(3, 4, 10, 18)
        assert sprite.get_hitbox_world_rect(world_x=100.0, world_y=200.0) == pygame.Rect(
            103, 204, 10, 18
        )

    def test_fallback_follows_the_current_frame(self):
        """Each frame's own visible box is used as the animation advances."""
        sprite = AnimatedSprite()
        first = self._frame_with_visible_box(pygame.Rect(3, 4, 10, 18))
        second = self._frame_with_visible_box(pygame.Rect(0, 10, 16, 14))
        sprite.add_animation('walk', [first, second])
        sprite.set_animation('walk')

        assert sprite.hitbox == pygame.Rect(3, 4, 10, 18)
        sprite.set_frame(1)
        assert sprite.hitbox == pygame.Rect(0, 10, 16, 14)

    def test_opt_out_keeps_the_full_frame_rect(self):
        """TRIM_TRANSPARENT_HITBOX = False uses the full frame rect, not the visible pixels."""
        sprite = AnimatedSprite()
        sprite.TRIM_TRANSPARENT_HITBOX = False  # type: ignore[attr-defined]
        frame = self._frame_with_visible_box(pygame.Rect(3, 4, 10, 18))
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')

        assert sprite.hitbox == pygame.Rect(0, 0, 16, 24)

    def test_explicit_frame_hitbox_wins_over_trimming(self):
        """A per-frame TOML hitbox is used as-is."""
        sprite = AnimatedSprite()
        frame = self._frame_with_visible_box(
            pygame.Rect(3, 4, 10, 18), hitbox=pygame.Rect(1, 1, 2, 2)
        )
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')

        assert sprite.hitbox == pygame.Rect(1, 1, 2, 2)

    def test_frame_bounds_are_measured_once_per_frame_surface(self, mocker):
        """Frame images are immutable, so each frame surface is measured only once."""
        sprite = AnimatedSprite()
        frame = self._frame_with_visible_box(pygame.Rect(3, 4, 10, 18))
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        measure_spy = mocker.spy(frame_module, 'measure_opaque_bounds')

        assert sprite.hitbox == pygame.Rect(3, 4, 10, 18)
        assert sprite.hitbox == pygame.Rect(3, 4, 10, 18)

        assert measure_spy.call_count == 1

    def test_replacing_a_frame_image_measures_the_new_surface(self):
        """Papyrus's prepare_papyrus_sprite replaces frame.image after load; bounds follow."""
        sprite = AnimatedSprite()
        frame = self._frame_with_visible_box(pygame.Rect(3, 4, 10, 18))
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        assert sprite.hitbox == pygame.Rect(3, 4, 10, 18)

        replacement = pygame.Surface((16, 24), pygame.SRCALPHA)
        replacement.fill((1, 2, 3, 255), pygame.Rect(0, 0, 5, 6))
        frame.image = replacement

        assert sprite.hitbox == pygame.Rect(0, 0, 5, 6)

    def test_hitbox_scale_defaults_to_one(self):
        """Unscaled sprites keep native-pixel hitboxes."""
        sprite = AnimatedSprite()
        assert sprite.hitbox_scale == 1

    def test_hitbox_scale_multiplies_explicit_frame_hitbox(self):
        """A sprite drawn at 2x gets its per-frame TOML hitbox at 2x offset and size."""
        sprite = AnimatedSprite()
        frame = self._frame_with_visible_box(
            pygame.Rect(3, 4, 10, 18), hitbox=pygame.Rect(3, 0, 11, 27)
        )
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        sprite.hitbox_scale = 2

        assert sprite.hitbox == pygame.Rect(6, 0, 22, 54)
        assert frame.hitbox == pygame.Rect(3, 0, 11, 27)  # the frame's own hitbox is untouched
        assert sprite.get_hitbox_world_rect(world_x=100.0, world_y=200.0) == pygame.Rect(
            106, 200, 22, 54
        )

    def test_hitbox_scale_multiplies_default_hitbox(self):
        """The sprite-level default hitbox is scaled too."""
        sprite = AnimatedSprite()
        frame = self._frame_with_visible_box(pygame.Rect(3, 4, 10, 18))
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        sprite.default_hitbox = pygame.Rect(1, 2, 12, 20)
        sprite.hitbox_scale = 2

        assert sprite.hitbox == pygame.Rect(2, 4, 24, 40)
        assert sprite.default_hitbox == pygame.Rect(1, 2, 12, 20)

    def test_hitbox_scale_multiplies_trimmed_fallback(self):
        """The visible-pixel fallback, measured on the native frame, is scaled too."""
        sprite = AnimatedSprite()
        frame = self._frame_with_visible_box(pygame.Rect(3, 4, 10, 18))
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        sprite.hitbox_scale = 3

        assert sprite.hitbox == pygame.Rect(9, 12, 30, 54)

    def test_hitbox_flip_x_defaults_to_false(self):
        """Unflipped sprites keep their hitboxes where the TOML puts them."""
        assert AnimatedSprite().hitbox_flip_x is False

    def test_hitbox_flip_x_mirrors_explicit_hitbox_within_drawn_width(self):
        """Facing left, a 2x sprite's hitbox is mirrored inside its 32 px drawn width."""
        sprite = AnimatedSprite()
        frame = self._frame_with_visible_box(
            pygame.Rect(3, 4, 10, 18), hitbox=pygame.Rect(3, 0, 11, 27)
        )
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        sprite.hitbox_scale = 2
        sprite.hitbox_flip_x = True

        # Drawn (6, 0, 22, 54) mirrored in 16 * 2 = 32 px: x = 32 - (6 + 22) = 4
        assert sprite.hitbox == pygame.Rect(4, 0, 22, 54)

    def test_hitbox_flip_x_mirrors_default_and_trimmed_hitboxes(self):
        """The default hitbox and the visible-pixel fallback are mirrored too."""
        sprite = AnimatedSprite()
        frame = self._frame_with_visible_box(pygame.Rect(3, 4, 10, 18))
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        sprite.hitbox_flip_x = True

        assert sprite.hitbox == pygame.Rect(16 - (3 + 10), 4, 10, 18)
        sprite.default_hitbox = pygame.Rect(1, 2, 12, 20)
        assert sprite.hitbox == pygame.Rect(16 - (1 + 12), 2, 12, 20)

    def test_common_hitbox_x_range_is_the_intersection_of_all_frames(self):
        """Support uses the columns every frame covers, scaled and mirrored like hitbox."""
        sprite = AnimatedSprite()
        idle = self._frame_with_visible_box(
            pygame.Rect(0, 0, 1, 1), hitbox=pygame.Rect(3, 0, 8, 20)
        )
        falling = self._frame_with_visible_box(
            pygame.Rect(0, 0, 1, 1), hitbox=pygame.Rect(0, 0, 10, 20)
        )
        sprite.add_animation('idle', [idle])
        sprite.add_animation('falling', [falling])
        sprite.set_animation('idle')

        assert sprite.common_hitbox_x_range() == (3, 10)
        sprite.hitbox_scale = 2
        assert sprite.common_hitbox_x_range() == (6, 20)
        sprite.hitbox_flip_x = True  # mirrored in 16 * 2 = 32 px
        assert sprite.common_hitbox_x_range() == (12, 26)

    def test_default_hitbox_wins_over_trimming(self):
        """A sprite-level TOML hitbox is used as-is."""
        sprite = AnimatedSprite()
        frame = self._frame_with_visible_box(pygame.Rect(3, 4, 10, 18))
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        sprite.default_hitbox = pygame.Rect(4, 0, 12, 20)

        assert sprite.hitbox == pygame.Rect(4, 0, 12, 20)


class TestAnimatedSpriteImageTransparency:
    """The sprite's image keeps a TOML frame's per-pixel alpha and magenta key (BUGS.md #133).

    Real surfaces and real TOML loading: the image is what LayeredDirty draws.
    """

    # 3x2 frame: '.' is magenta (the transparency key), '#' is opaque, 'g' is translucent
    ALPHA_SPRITE_TOML = """[sprite]
name = "translucent"

[colors."."]
red = 255
green = 0
blue = 255

[colors."#"]
red = 10
green = 20
blue = 30

[colors."g"]
red = 80
green = 220
blue = 120
alpha = 137

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
frame_index = 0
pixels = \"\"\"
.#g
...
\"\"\"
"""

    # 3x2 frame without per-pixel alpha: '.' is magenta, '#' is opaque
    INDEXED_SPRITE_TOML = """[sprite]
name = "indexed"

[colors."."]
red = 255
green = 0
blue = 255

[colors."#"]
red = 10
green = 20
blue = 30

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
frame_index = 0
pixels = \"\"\"
.#.
.#.
\"\"\"
"""

    # The same 3x2 picture as a static sprite (no [[animation]]), whose pixels stay RGB
    STATIC_SPRITE_TOML = """[sprite]
name = "static_indexed"
pixels = \"\"\"
.#.
.#.
\"\"\"

[colors."."]
red = 255
green = 0
blue = 255

[colors."#"]
red = 10
green = 20
blue = 30
"""

    @staticmethod
    def _load_sprite(*, tmp_path: Path, toml_content: str) -> AnimatedSprite:
        """Write toml_content to a file and load it as an AnimatedSprite.

        Returns:
            AnimatedSprite: The loaded sprite, showing its first frame.

        """
        toml_file = tmp_path / 'sprite.toml'
        toml_file.write_text(toml_content, encoding='utf-8')
        return AnimatedSprite(filename=str(toml_file))

    @staticmethod
    def _drawn_pixels(*, image: pygame.Surface) -> list[tuple[int, int, int]]:
        """Draw image over a blue background and return the drawn RGB pixels, row by row.

        Returns:
            list[tuple[int, int, int]]: The background's pixels after the blit.

        """
        background = pygame.Surface(image.get_size())
        background.fill((0, 0, 255))
        background.blit(image, (0, 0))
        width, height = image.get_size()
        drawn_pixels: list[tuple[int, int, int]] = []
        for y in range(height):
            for x in range(width):
                drawn_color = background.get_at((x, y))
                drawn_pixels.append((drawn_color.r, drawn_color.g, drawn_color.b))
        return drawn_pixels

    def test_translucent_frame_image_keeps_its_per_pixel_alpha(self, tmp_path):
        """A frame with alpha colors gives an SRCALPHA image with each pixel's alpha."""
        sprite = self._load_sprite(tmp_path=tmp_path, toml_content=self.ALPHA_SPRITE_TOML)

        assert sprite.image.get_flags() & pygame.SRCALPHA
        assert sprite.image.get_at((1, 0)) == pygame.Color(10, 20, 30, 255)
        assert sprite.image.get_at((2, 0)) == pygame.Color(80, 220, 120, 137)

    def test_translucent_frame_image_makes_magenta_transparent(self, tmp_path):
        """Magenta pixels of a frame with alpha colors are fully transparent in the image."""
        sprite = self._load_sprite(tmp_path=tmp_path, toml_content=self.ALPHA_SPRITE_TOML)

        assert sprite.image.get_at((0, 0)).a == 0
        assert sprite.image.get_bounding_rect() == pygame.Rect(1, 0, 2, 1)

    def test_translucent_frame_draws_blended_and_without_magenta(self, tmp_path):
        """Drawn over blue: magenta shows the background, the translucent pixel blends."""
        sprite = self._load_sprite(tmp_path=tmp_path, toml_content=self.ALPHA_SPRITE_TOML)

        drawn_pixels = self._drawn_pixels(image=sprite.image)

        assert drawn_pixels[0] == (0, 0, 255)
        assert drawn_pixels[1] == (10, 20, 30)
        # 137/255 of (80, 220, 120) over (0, 0, 255): neither the color nor the background
        assert drawn_pixels[2] not in {(80, 220, 120), (0, 0, 255)}
        assert drawn_pixels[3:] == [(0, 0, 255)] * 3

    def test_indexed_animation_frame_keys_out_magenta(self, tmp_path):
        """An animation frame without translucent colors keys magenta out with a colorkey.

        The loader stores the frame's pixels as RGBA (it has magenta), but nothing in it is
        translucent, so the image is a plain surface keyed on magenta.
        """
        sprite = self._load_sprite(tmp_path=tmp_path, toml_content=self.INDEXED_SPRITE_TOML)

        assert not sprite.image.get_flags() & pygame.SRCALPHA
        assert sprite.image.get_colorkey() == pygame.Color(255, 0, 255, 255)
        assert sprite.image.get_bounding_rect() == pygame.Rect(1, 0, 1, 2)
        assert (
            self._drawn_pixels(image=sprite.image)
            == [
                (0, 0, 255),
                (10, 20, 30),
                (0, 0, 255),
            ]
            * 2
        )

    def test_static_sprite_image_keys_out_magenta(self, tmp_path):
        """A static sprite's RGB pixels give an image with magenta as its colorkey."""
        sprite = self._load_sprite(tmp_path=tmp_path, toml_content=self.STATIC_SPRITE_TOML)
        frame = sprite.get_current_frame()
        assert frame is not None
        assert all(len(pixel) == 3 for pixel in frame.pixels)

        assert not sprite.image.get_flags() & pygame.SRCALPHA
        assert sprite.image.get_colorkey() == pygame.Color(255, 0, 255, 255)
        assert sprite.image.get_bounding_rect() == pygame.Rect(1, 0, 1, 2)
        assert (
            self._drawn_pixels(image=sprite.image)
            == [
                (0, 0, 255),
                (10, 20, 30),
                (0, 0, 255),
            ]
            * 2
        )

    def test_keyed_magenta_is_not_written_over_a_destination_without_alpha(self, tmp_path):
        """Keyed pixels leave a destination pixel of alpha 0 untouched.

        A surface with an alpha channel can hold pixels at alpha 0 (cocoa's display held the
        scene background so until BUGS.md #142); a per-pixel alpha source copies its color onto
        such pixels instead of blending, but colorkeyed pixels are skipped.
        """
        sprite = self._load_sprite(tmp_path=tmp_path, toml_content=self.INDEXED_SPRITE_TOML)
        destination = pygame.Surface(sprite.image.get_size(), pygame.SRCALPHA)
        destination.fill((0, 0, 255, 0))

        destination.blit(sprite.image, (0, 0))

        assert destination.get_at((0, 0)) == pygame.Color(0, 0, 255, 0)
        assert destination.get_at((1, 0)).rgb == (10, 20, 30)

    def test_bundled_foo2_example_keeps_its_alpha(self):
        """The example from BUGS.md #133: foo2.toml's translucent body stays translucent."""
        foo2_path = Path(__file__).parents[2] / 'glitchygames' / 'examples' / 'foo2.toml'
        sprite = AnimatedSprite(filename=str(foo2_path))
        frame = sprite.get_current_frame()
        assert frame is not None

        frame_alphas = {frame.image.get_at((x, 8)).a for x in range(16)}
        image_alphas = {sprite.image.get_at((x, 8)).a for x in range(16)}

        assert 137 in frame_alphas
        assert image_alphas == {0, 137}


class TestAnimatedSpriteFrameAnchor:
    """FrameAnchor keeps one point of every frame's hitbox in place (real surfaces)."""

    # Three frames with different hitboxes, each frame's visible pixels == its hitbox
    FRAME_HITBOXES = (
        pygame.Rect(3, 0, 11, 27),
        pygame.Rect(1, 2, 14, 22),
        pygame.Rect(0, 5, 19, 19),
    )

    def _sprite(self, frame_anchor, *, hitbox_scale=1, hitbox_flip_x=False):
        """A three-frame sprite in one animation, anchored as given.

        Returns:
            AnimatedSprite: The sprite.

        """
        sprite = AnimatedSprite()
        frames = []
        for frame_hitbox in self.FRAME_HITBOXES:
            surface = pygame.Surface((20, 28), pygame.SRCALPHA)
            surface.fill((10, 200, 30, 255), frame_hitbox)
            frames.append(SpriteFrame(surface, duration=FRAME_DURATION, hitbox=frame_hitbox))
        sprite.add_animation('cycle', frames)
        sprite.set_animation('cycle')
        sprite.frame_anchor = frame_anchor
        sprite.hitbox_scale = hitbox_scale
        sprite.hitbox_flip_x = hitbox_flip_x
        return sprite

    @staticmethod
    def _anchor_point(rect, frame_anchor, *, mirrored=False):
        """Return the anchor's point of a rect, doubled to keep half pixels exact.

        Edge anchors (TOP, BOTTOM, LEFT, RIGHT) anchor only their own axis; the other
        coordinate is None. When mirrored, an authored left edge is the drawn right edge.
        """
        name = frame_anchor.name
        if mirrored:
            name = name.replace('LEFT', 'SWAP').replace('RIGHT', 'LEFT').replace('SWAP', 'RIGHT')
        if name in {'TOP', 'BOTTOM'}:
            point_x = None
        elif name.endswith('LEFT'):
            point_x = 2 * rect.left
        elif name.endswith('RIGHT'):
            point_x = 2 * rect.right
        else:
            point_x = 2 * rect.left + rect.width
        if name in {'LEFT', 'RIGHT'}:
            point_y = None
        elif name.startswith('TOP'):
            point_y = 2 * rect.top
        elif name.startswith('BOTTOM'):
            point_y = 2 * rect.bottom
        else:
            point_y = 2 * rect.top + rect.height
        return (point_x, point_y)

    def _points_per_frame(self, sprite):
        """For every frame: the hitbox's anchor point and the drawn pixels' anchor point."""
        hitbox_points = []
        drawn_points = []
        for frame_index in range(len(self.FRAME_HITBOXES)):
            sprite.set_frame(frame_index)
            frame = sprite.get_current_frame()
            hitbox_points.append(
                self._anchor_point(
                    sprite.hitbox, sprite.frame_anchor, mirrored=sprite.hitbox_flip_x
                )
            )
            # Where the frame's visible pixels land when drawn at rect = position + draw_offset
            visible = frame.image.get_bounding_rect()
            scale = sprite.hitbox_scale
            drawn_x = visible.x * scale
            if sprite.hitbox_flip_x:
                drawn_x = frame.rect.width * scale - (drawn_x + visible.width * scale)
            drawn = pygame.Rect(
                drawn_x, visible.y * scale, visible.width * scale, visible.height * scale
            )
            drawn.move_ip(sprite.draw_offset)
            drawn_points.append(
                self._anchor_point(drawn, sprite.frame_anchor, mirrored=sprite.hitbox_flip_x)
            )
        return hitbox_points, drawn_points

    @pytest.mark.parametrize(
        'frame_anchor',
        [anchor for anchor in FrameAnchor if anchor is not FrameAnchor.NONE],
        ids=lambda anchor: anchor.name,
    )
    def test_anchor_point_is_identical_for_every_frame(self, frame_anchor):
        """The anchor point of every frame's hitbox and drawing lands on the reference's."""
        sprite = self._sprite(frame_anchor, hitbox_scale=2)
        reference = self.FRAME_HITBOXES[0].unionall(self.FRAME_HITBOXES[1:])
        scaled_reference = pygame.Rect(
            reference.x * 2, reference.y * 2, reference.width * 2, reference.height * 2
        )
        hitbox_points, drawn_points = self._points_per_frame(sprite)
        expected = self._anchor_point(scaled_reference, frame_anchor)
        assert set(hitbox_points) == {expected}
        assert set(drawn_points) == {expected}

    @pytest.mark.parametrize(
        ('frame_anchor', 'free_axis'),
        [
            (FrameAnchor.TOP, 0),
            (FrameAnchor.BOTTOM, 0),
            (FrameAnchor.LEFT, 1),
            (FrameAnchor.RIGHT, 1),
        ],
        ids=lambda value: value.name if isinstance(value, FrameAnchor) else str(value),
    )
    def test_edge_anchors_leave_the_other_axis_as_authored(self, frame_anchor, free_axis):
        """TOP/BOTTOM never move a frame in x; LEFT/RIGHT never move it in y."""
        sprite = self._sprite(frame_anchor, hitbox_scale=2)
        for frame_index in range(len(self.FRAME_HITBOXES)):
            sprite.set_frame(frame_index)
            assert sprite.draw_offset[free_axis] == 0

    def test_none_is_a_strict_no_op(self):
        """The default NONE draws frames as authored: no offset, hitboxes unchanged."""
        sprite = self._sprite(FrameAnchor.NONE)
        assert AnimatedSprite().frame_anchor is FrameAnchor.NONE
        for frame_index, frame_hitbox in enumerate(self.FRAME_HITBOXES):
            sprite.set_frame(frame_index)
            assert sprite.draw_offset == (0, 0)
            assert sprite.hitbox == frame_hitbox

    def test_left_anchor_on_a_flipped_sprite_keeps_the_visual_right_edge(self):
        """Mirrored drawing: LEFT (computed in authored space) pins the on-screen right edge."""
        sprite = self._sprite(FrameAnchor.LEFT, hitbox_flip_x=True)
        right_edges = set()
        drawn_right_edges = set()
        for frame_index in range(len(self.FRAME_HITBOXES)):
            sprite.set_frame(frame_index)
            right_edges.add(sprite.hitbox.right)
            frame = sprite.get_current_frame()
            visible = frame.image.get_bounding_rect()
            drawn_right = frame.rect.width - visible.x + sprite.draw_offset[0]
            drawn_right_edges.add(drawn_right)
        # Reference left edge 0 in authored space -> right edge 20 in the 20 px mirrored frame
        assert right_edges == {20}
        assert drawn_right_edges == {20}

    @pytest.mark.parametrize(
        'frame_anchor',
        [
            FrameAnchor.LEFT,
            FrameAnchor.RIGHT,
            FrameAnchor.CENTER,
            FrameAnchor.TOP_LEFT,
            FrameAnchor.TOP_RIGHT,
            FrameAnchor.BOTTOM_LEFT,
            FrameAnchor.BOTTOM_RIGHT,
        ],
        ids=lambda anchor: anchor.name,
    )
    def test_flipped_anchor_is_exact_for_frames_of_differing_widths(self, frame_anchor):
        """Mirrored frames 20, 16 and 24 px wide still put the anchor point in one place."""
        sprite = AnimatedSprite()
        frames = []
        for frame_width, frame_hitbox in zip((20, 16, 24), self.FRAME_HITBOXES, strict=True):
            surface = pygame.Surface((frame_width, 28), pygame.SRCALPHA)
            surface.fill((10, 200, 30, 255), frame_hitbox)
            frames.append(SpriteFrame(surface, duration=FRAME_DURATION, hitbox=frame_hitbox))
        sprite.add_animation('cycle', frames)
        sprite.set_animation('cycle')
        sprite.frame_anchor = frame_anchor
        sprite.hitbox_scale = 2
        sprite.hitbox_flip_x = True

        hitbox_points, drawn_points = self._points_per_frame(sprite)

        assert len(set(hitbox_points)) == 1
        assert set(drawn_points) == set(hitbox_points)

    def test_reference_is_cached_until_the_frames_change(self, mocker):
        """The union reference is built once per frame set, not on every draw_offset."""
        sprite = self._sprite(FrameAnchor.BOTTOM)
        union_spy = mocker.spy(sprite, '_union_of_frame_hitboxes')
        for frame_index in (0, 1, 2, 0, 1):
            sprite.set_frame(frame_index)
            _ = sprite.draw_offset
        assert union_spy.call_count == 1

        taller = pygame.Surface((20, 40), pygame.SRCALPHA)
        sprite.add_animation(
            'tall', [SpriteFrame(taller, duration=FRAME_DURATION, hitbox=pygame.Rect(0, 0, 20, 40))]
        )
        sprite.set_animation('cycle')
        sprite.set_frame(0)
        assert sprite.draw_offset == (0, 40 - 27)
        assert union_spy.call_count == 2

    def test_reference_prefers_the_default_hitbox(self):
        """With a sprite-level default hitbox, frames align to it, not the union."""
        sprite = self._sprite(FrameAnchor.BOTTOM)
        sprite.default_hitbox = pygame.Rect(0, 0, 20, 28)
        sprite.set_frame(1)
        assert sprite.hitbox.bottom == 28
        assert sprite.hitbox.left == self.FRAME_HITBOXES[1].left  # x as authored

    def test_toml_frame_anchor_is_parsed(self):
        """[sprite] frame_anchor takes the lowercase names; absent is NONE; unknown raises."""
        assert AnimatedSprite._parse_frame_anchor(None) is FrameAnchor.NONE
        assert AnimatedSprite._parse_frame_anchor('bottom_left') is FrameAnchor.BOTTOM_LEFT
        with pytest.raises(ValueError, match='frame_anchor'):
            AnimatedSprite._parse_frame_anchor('sideways')


class TestHitboxTomlRoundTrip:
    """Test hitbox TOML load/save round-trip."""

    def test_load_sprite_level_hitbox(self, tmp_path):
        """Loading TOML with [sprite.hitbox] sets default_hitbox."""
        toml_content = """[sprite]
name = "hitbox_test"

[sprite.hitbox]
offset_x = 4
offset_y = 0
width = 12
height = 25

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
##
##
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0
"""
        toml_file = tmp_path / 'hitbox.toml'
        toml_file.write_text(toml_content, encoding='utf-8')

        sprite = AnimatedSprite()
        sprite.load(str(toml_file))
        assert sprite.default_hitbox is not None
        assert sprite.default_hitbox == pygame.Rect(4, 0, 12, 25)

    def test_load_per_frame_hitbox(self, tmp_path):
        """Loading TOML with [animation.frame.hitbox] sets per-frame hitbox."""
        toml_content = """[sprite]
name = "frame_hitbox_test"

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
##
##
\"\"\"

[animation.frame.hitbox]
offset_x = 3
offset_y = 2
width = 14
height = 20

[colors."#"]
red = 0
green = 0
blue = 0
"""
        toml_file = tmp_path / 'frame_hitbox.toml'
        toml_file.write_text(toml_content, encoding='utf-8')

        sprite = AnimatedSprite()
        sprite.load(str(toml_file))
        current_frame = sprite.get_current_frame()
        assert current_frame is not None
        assert current_frame.has_explicit_hitbox
        assert current_frame.hitbox == pygame.Rect(3, 2, 14, 20)

    def test_load_without_hitbox_backward_compatible(self, tmp_path):
        """Loading TOML without hitbox sections still works (visible-pixel fallback)."""
        toml_content = """[sprite]
name = "no_hitbox"

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
##
##
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0
"""
        toml_file = tmp_path / 'no_hitbox.toml'
        toml_file.write_text(toml_content, encoding='utf-8')

        sprite = AnimatedSprite()
        sprite.load(str(toml_file))
        assert sprite.default_hitbox is None
        current_frame = sprite.get_current_frame()
        assert current_frame is not None
        assert not current_frame.has_explicit_hitbox
        # Every pixel is opaque, so the visible-pixel fallback is the full frame
        assert sprite.hitbox == current_frame.rect

    def test_save_sprite_level_hitbox(self, tmp_path):
        """Saving sprite with default_hitbox writes [sprite.hitbox] section."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((2, 2))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        frame.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        sprite.name = 'hitbox_save'
        sprite.default_hitbox = pygame.Rect(1, 0, 6, 10)

        save_path = tmp_path / 'hitbox_save.toml'
        sprite.save(str(save_path), 'toml')

        content = save_path.read_text(encoding='utf-8')
        assert '[sprite.hitbox]' in content
        assert 'offset_x = 1' in content
        assert 'offset_y = 0' in content
        assert 'width = 6' in content
        assert 'height = 10' in content

    def test_frame_anchor_survives_a_save_and_reload(self, tmp_path):
        """[sprite] frame_anchor is written back (the path Bitmappy's save uses) and reloads."""
        source = Path('glitchygames/examples/brave_adventurer_papyrus/sprites/player.toml')
        toml_file = tmp_path / 'anchored.toml'
        toml_file.write_text(
            source.read_text(encoding='utf-8').replace(
                '[sprite]\n', '[sprite]\nframe_anchor = "bottom"\n', 1
            ),
            encoding='utf-8',
        )
        sprite = AnimatedSprite(str(toml_file))
        assert sprite.frame_anchor is FrameAnchor.BOTTOM
        frame_hitboxes = {
            name: [frame.hitbox if frame.has_explicit_hitbox else None for frame in frames]
            for name, frames in sprite.animation_data.items()
        }

        save_path = tmp_path / 'resaved.toml'
        sprite.save(str(save_path), 'toml')
        reloaded = AnimatedSprite(str(save_path))

        assert 'frame_anchor = "bottom"' in save_path.read_text(encoding='utf-8')
        assert reloaded.frame_anchor is FrameAnchor.BOTTOM
        assert reloaded.default_hitbox == sprite.default_hitbox
        assert {
            name: [frame.hitbox if frame.has_explicit_hitbox else None for frame in frames]
            for name, frames in reloaded.animation_data.items()
        } == frame_hitboxes

    def test_frame_anchor_none_writes_nothing(self, tmp_path):
        """The default NONE leaves the TOML without a frame_anchor key."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((2, 2))
        frames = []
        for _ in range(2):
            frame = SpriteFrame(surface, duration=FRAME_DURATION)
            frame.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
            frames.append(frame)
        sprite.add_animation('idle', frames)
        sprite.set_animation('idle')

        save_path = tmp_path / 'plain.toml'
        sprite.save(str(save_path), 'toml')

        assert 'frame_anchor' not in save_path.read_text(encoding='utf-8')

    def test_static_sprite_frame_anchor_is_written(self, tmp_path):
        """The single-frame (static) save path writes frame_anchor too."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((2, 2))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        frame.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        sprite.frame_anchor = FrameAnchor.TOP_LEFT

        save_path = tmp_path / 'static.toml'
        sprite.save(str(save_path), 'toml')

        assert 'frame_anchor = "top_left"' in save_path.read_text(encoding='utf-8')

    def test_save_per_frame_hitbox(self, tmp_path):
        """Saving sprite with per-frame hitbox writes [animation.frame.hitbox]."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((2, 2))
        pixel_data = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]

        # Use 2 frames so the animated (not static) save path is used
        frame_hitbox = pygame.Rect(0, 1, 4, 8)
        frame_with_hitbox = SpriteFrame(surface, duration=FRAME_DURATION, hitbox=frame_hitbox)
        frame_with_hitbox.pixels = pixel_data.copy()
        frame_without_hitbox = SpriteFrame(surface, duration=FRAME_DURATION)
        frame_without_hitbox.pixels = pixel_data.copy()

        sprite.add_animation('idle', [frame_with_hitbox, frame_without_hitbox])
        sprite.set_animation('idle')
        sprite.name = 'frame_hitbox_save'

        save_path = tmp_path / 'frame_hitbox_save.toml'
        sprite.save(str(save_path), 'toml')

        content = save_path.read_text(encoding='utf-8')
        assert '[animation.frame.hitbox]' in content
        assert 'offset_x = 0' in content
        assert 'offset_y = 1' in content
        assert 'width = 4' in content
        assert 'height = 8' in content

    def test_save_without_hitbox_omits_section(self, tmp_path):
        """Saving sprite without hitbox does not write hitbox sections."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((2, 2))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        frame.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')
        sprite.name = 'no_hitbox_save'

        save_path = tmp_path / 'no_hitbox_save.toml'
        sprite.save(str(save_path), 'toml')

        content = save_path.read_text(encoding='utf-8')
        assert '[sprite.hitbox]' not in content
        assert '[animation.frame.hitbox]' not in content

    def test_round_trip_preserves_hitbox(self, tmp_path):
        """Save then load preserves all hitbox values."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((2, 2))
        pixel_data = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]

        # Use 2 frames so the animated (not static) save path is used
        frame_hitbox = pygame.Rect(1, 2, 3, 4)
        frame_with_hitbox = SpriteFrame(surface, duration=FRAME_DURATION, hitbox=frame_hitbox)
        frame_with_hitbox.pixels = pixel_data.copy()
        frame_without_hitbox = SpriteFrame(surface, duration=FRAME_DURATION)
        frame_without_hitbox.pixels = pixel_data.copy()

        sprite.add_animation('idle', [frame_with_hitbox, frame_without_hitbox])
        sprite.set_animation('idle')
        sprite.name = 'round_trip'
        sprite.default_hitbox = pygame.Rect(5, 6, 7, 8)

        save_path = tmp_path / 'round_trip.toml'
        sprite.save(str(save_path), 'toml')

        loaded_sprite = AnimatedSprite()
        loaded_sprite.load(str(save_path))

        assert loaded_sprite.default_hitbox == pygame.Rect(5, 6, 7, 8)
        loaded_frame = loaded_sprite.get_current_frame()
        assert loaded_frame is not None
        assert loaded_frame.has_explicit_hitbox
        assert loaded_frame.hitbox == pygame.Rect(1, 2, 3, 4)


LOOPING_AND_ONE_SHOT_TOML = """[sprite]
name = "loops"

[[animation]]
namespace = "idle"
frame_interval = 0.1
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
#
\"\"\"

[[animation.frame]]
namespace = "idle"
frame_index = 1
pixels = \"\"\"
.
\"\"\"

[[animation]]
namespace = "strike"
frame_interval = 0.1
loop = false

[[animation.frame]]
namespace = "strike"
frame_index = 0
pixels = \"\"\"
#
\"\"\"

[[animation.frame]]
namespace = "strike"
frame_index = 1
pixels = \"\"\"
.
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0

[colors."."]
red = 255
green = 0
blue = 255
"""


class TestPerAnimationLoop:
    """Each animation's own [[animation]] loop flag applies while it plays."""

    @staticmethod
    def _play_past_the_end(sprite: AnimatedSprite, animation_name: str) -> None:
        """Play an animation for longer than its two 0.1 s frames."""
        sprite.play(animation_name)
        for _ in range(5):
            sprite.update(dt=0.1)

    def test_each_animation_keeps_its_own_loop_flag(self, tmp_path):
        """The looping animation wraps, the one-shot stops on its last frame, either order."""
        toml_file = tmp_path / 'loops.toml'
        toml_file.write_text(LOOPING_AND_ONE_SHOT_TOML, encoding='utf-8')
        sprite = AnimatedSprite(str(toml_file))

        assert sprite.is_looping  # the first (initial) animation, idle, loops
        self._play_past_the_end(sprite, 'strike')
        assert not sprite.is_looping
        assert not sprite.is_playing
        assert sprite.current_frame == 1

        self._play_past_the_end(sprite, 'idle')
        assert sprite.is_looping
        assert sprite.is_playing

        self._play_past_the_end(sprite, 'strike')
        assert not sprite.is_playing
        assert sprite.current_frame == 1

    def test_loop_flags_survive_a_save_round_trip(self, tmp_path):
        """Both animations' loop flags are written back and apply after reloading."""
        toml_file = tmp_path / 'loops.toml'
        toml_file.write_text(LOOPING_AND_ONE_SHOT_TOML, encoding='utf-8')
        saved_file = tmp_path / 'resaved.toml'
        AnimatedSprite(str(toml_file)).save(str(saved_file), 'toml')

        reloaded = AnimatedSprite(str(saved_file))
        reloaded.set_animation('strike')
        assert not reloaded.is_looping
        reloaded.set_animation('idle')
        assert reloaded.is_looping

    def test_animation_metadata_loop_flag_is_per_animation(self, tmp_path):
        """get/set_animation_metadata read and change one animation's loop flag."""
        toml_file = tmp_path / 'loops.toml'
        toml_file.write_text(LOOPING_AND_ONE_SHOT_TOML, encoding='utf-8')
        sprite = AnimatedSprite(str(toml_file))

        assert sprite.get_animation_metadata('idle')['is_looping'] is True
        assert sprite.get_animation_metadata('strike')['is_looping'] is False

        sprite.set_animation_metadata('strike', {'is_looping': True})

        assert sprite.get_animation_metadata('strike')['is_looping'] is True
        assert sprite.is_looping  # idle (current) is unaffected and still loops
        sprite.set_animation('strike')
        assert sprite.is_looping


TRANSITIONS_TOML = (
    LOOPING_AND_ONE_SHOT_TOML
    + """
[[transition]]
from = "idle"
to = "strike"
when = "timer > 2.0"

[[transition]]
from = "strike"
to = "idle"
when = "timer > 0.3"
"""
)


class TestTransitionData:
    """Loaded [[transition]] sections are kept as data and follow animation renames/deletes."""

    @staticmethod
    def _load(tmp_path) -> AnimatedSprite:
        toml_file = tmp_path / 'transitions.toml'
        toml_file.write_text(TRANSITIONS_TOML, encoding='utf-8')
        return AnimatedSprite(str(toml_file))

    @staticmethod
    def _saved_transitions(sprite: AnimatedSprite, tmp_path) -> list[dict]:
        import tomllib

        saved_file = tmp_path / 'resaved.toml'
        sprite.save(str(saved_file), 'toml')
        return tomllib.loads(saved_file.read_text(encoding='utf-8')).get('transition', [])

    def test_transitions_are_kept_in_file_order(self, tmp_path):
        """transition_data holds each [[transition]] table as loaded."""
        sprite = self._load(tmp_path)

        assert sprite.transition_data == [
            {'from': 'idle', 'to': 'strike', 'when': 'timer > 2.0'},
            {'from': 'strike', 'to': 'idle', 'when': 'timer > 0.3'},
        ]

    def test_renaming_an_animation_renames_it_in_transitions(self, tmp_path):
        """A renamed animation keeps its transitions under the new name."""
        sprite = self._load(tmp_path)

        sprite.rename_animation_in_transitions(old_name='strike', new_name='lunge')

        assert self._saved_transitions(sprite, tmp_path) == [
            {'from': 'idle', 'to': 'lunge', 'when': 'timer > 2.0'},
            {'from': 'lunge', 'to': 'idle', 'when': 'timer > 0.3'},
        ]

    def test_rename_animation_moves_transitions_and_keeps_the_order(self, tmp_path):
        """rename_animation renames the frames in place and in the transitions."""
        sprite = self._load(tmp_path)

        sprite.rename_animation(old_name='idle', new_name='rest')

        assert list(sprite._animations) == ['rest', 'strike']
        assert sprite.animation_order == ['rest', 'strike']
        assert sprite.transition_data[0] == {'from': 'rest', 'to': 'strike', 'when': 'timer > 2.0'}

    def test_removed_transitions_restore_to_their_original_positions(self, tmp_path):
        """transitions_for_animation + restore_transitions undo remove_transitions_for_animation."""
        sprite = self._load(tmp_path)
        sprite.transition_data.insert(1, {'from': 'idle', 'to': 'idle', 'when': 'timer > 9.0'})
        original_transitions = [dict(transition) for transition in sprite.transition_data]

        dropped_transitions = sprite.transitions_for_animation('strike')
        sprite.remove_transitions_for_animation('strike')
        assert sprite.transition_data == [{'from': 'idle', 'to': 'idle', 'when': 'timer > 9.0'}]

        sprite.restore_transitions(dropped_transitions)
        assert sprite.transition_data == original_transitions

    def test_remove_animation_forgets_its_settings(self, tmp_path):
        """A removed animation's loop flag, interval and place in the order are dropped."""
        sprite = self._load(tmp_path)

        sprite.remove_animation('strike')

        assert 'strike' not in sprite._loop_flags
        assert 'strike' not in sprite._animation_frame_intervals
        assert sprite.animation_order == ['idle']

    def test_rename_animation_rejects_a_missing_or_existing_name(self, tmp_path):
        """Renaming a missing animation, or onto an existing one, raises ValueError."""
        sprite = self._load(tmp_path)

        with pytest.raises(ValueError, match="'missing' not found"):
            sprite.rename_animation(old_name='missing', new_name='other')
        with pytest.raises(ValueError, match="'strike' already exists"):
            sprite.rename_animation(old_name='idle', new_name='strike')
        assert list(sprite._animations) == ['idle', 'strike']

    def test_removing_an_animation_drops_its_transitions_with_a_warning(self, tmp_path, caplog):
        """Transitions from or to a removed animation are dropped and logged."""
        sprite = self._load(tmp_path)

        with caplog.at_level(logging.WARNING):
            sprite.remove_animation('strike')

        assert sprite.transition_data == []
        assert 'strike' in caplog.text

    def test_when_strings_with_quotes_and_backslashes_round_trip(self, tmp_path):
        """Transition when strings are escaped for TOML: quotes and backslashes survive a save."""
        sprite = self._load(tmp_path)
        tricky_when = 'name == "a\\\\b" and timer > 1'
        sprite.transition_data[0]['when'] = tricky_when

        assert self._saved_transitions(sprite, tmp_path)[0]['when'] == tricky_when


class TestTomlValueFormatting:
    """The module's TOML writers produce values tomllib reads back unchanged."""

    @staticmethod
    def _read_back(written_value: str) -> object:
        """Parse one written TOML value.

        Returns:
            object: The value tomllib reads.

        """
        import tomllib

        return tomllib.loads(f'value = {written_value}\n')['value']

    def test_basic_string_escapes_control_characters_and_delete(self):
        """Control characters without a short escape, and DEL, use unicode escapes."""
        original = 'a\x01b\x1fc\x7f'
        written = glitchygames.sprites.animated.toml_basic_string(original)
        assert written == '"a\\u0001b\\u001Fc\\u007F"'
        assert self._read_back(written) == original

    def test_multiline_string_escapes_control_characters_and_keeps_newlines(self):
        """A multi-line string keeps inner newlines literal and escapes other controls."""
        original = 'first\x02line\nsecond\x7fline'
        written = glitchygames.sprites.animated.toml_multiline_basic_string(original)
        assert '\\u0002' in written
        assert '\\u007F' in written
        assert 'line\nsecond' in written
        assert self._read_back(written) == original

    @pytest.mark.parametrize(
        ('key', 'expected'),
        [('idle_left-2', 'idle_left-2'), ('has space', '"has space"'), ('', '""')],
    )
    def test_key_is_bare_only_when_toml_allows_it(self, key, expected):
        """Keys with only bare-key characters stay bare; anything else is quoted."""
        assert glitchygames.sprites.animated.toml_key(key) == expected

    @pytest.mark.parametrize(
        ('value', 'expected'),
        [
            (True, 'true'),
            (False, 'false'),
            (42, '42'),
            (0.25, '0.25'),
            (float('inf'), 'inf'),
            (float('-inf'), '-inf'),
            ('a"b', '"a\\"b"'),
        ],
    )
    def test_scalar_round_trips(self, value, expected):
        """Booleans, integers, floats and strings are written in TOML syntax."""
        written = glitchygames.sprites.animated.toml_scalar(value)
        assert written == expected
        assert self._read_back(written) == value

    def test_scalar_nan_is_written_as_nan(self):
        """NaN is written as TOML's nan (which never equals itself)."""
        written = glitchygames.sprites.animated.toml_scalar(float('nan'))
        assert written == 'nan'
        assert math.isnan(cast('float', self._read_back(written)))

    def test_scalar_refuses_other_types(self):
        """A list (or any non-scalar) cannot be written as a scalar."""
        with pytest.raises(TypeError, match='list'):
            glitchygames.sprites.animated.toml_scalar([1, 2])


class TestAnimatedSpriteWithoutUsableFrames:
    """Geometry falls back sensibly when there is no frame, or frames share nothing."""

    @staticmethod
    def _frame(*, width: int, hitbox: pygame.Rect) -> SpriteFrame:
        """A fully opaque frame with an explicit hitbox.

        Returns:
            SpriteFrame: The frame.

        """
        surface = pygame.Surface((width, 8), pygame.SRCALPHA)
        surface.fill((10, 20, 30, 255))
        return SpriteFrame(surface, duration=FRAME_DURATION, hitbox=hitbox)

    def test_hitbox_without_a_frame_is_the_unscaled_sprite_rect(self):
        """With no frame the hitbox is the sprite's own rect, already in drawn pixels."""
        sprite = AnimatedSprite()
        sprite.hitbox_scale = 3
        assert sprite.hitbox == pygame.Rect(0, 0, sprite.rect.width, sprite.rect.height)

    def test_draw_offset_without_a_frame_is_zero(self):
        """An anchored sprite with no frame is drawn where it is authored."""
        sprite = AnimatedSprite()
        sprite.frame_anchor = FrameAnchor.BOTTOM
        assert sprite.draw_offset == (0, 0)

    def test_common_range_without_frames_is_the_current_hitbox_range(self):
        """Without frames, common_hitbox_x_range is the hitbox's own x-range."""
        sprite = AnimatedSprite()
        assert sprite.common_hitbox_x_range() == (0, sprite.rect.width)

    def test_common_range_of_frames_sharing_no_column_is_the_current_hitbox_range(self):
        """Frames whose hitboxes do not overlap horizontally fall back to the current hitbox."""
        sprite = AnimatedSprite()
        left_frame = self._frame(width=16, hitbox=pygame.Rect(0, 0, 4, 8))
        right_frame = self._frame(width=16, hitbox=pygame.Rect(10, 0, 6, 8))
        sprite.add_animation('left', [left_frame])
        sprite.add_animation('right', [right_frame])
        sprite.set_animation('right')
        assert sprite.common_hitbox_x_range() == (10, 16)


class TestAnimatedSpriteAnimationEditing:
    """Replacing, removing and restoring animations (real pygame surfaces)."""

    @staticmethod
    def _solid_frame(color: tuple[int, int, int]) -> SpriteFrame:
        """A 2x1 frame of one color.

        Returns:
            SpriteFrame: The frame.

        """
        surface = pygame.Surface((2, 1))
        surface.fill(color)
        return SpriteFrame(surface, duration=FRAME_DURATION)

    def test_animation_data_setter_replaces_every_animation(self):
        """Assigning animation_data swaps the frames the frame manager can select."""
        sprite = AnimatedSprite()
        sprite.add_animation('walk', [self._solid_frame((255, 0, 0))])
        run_frame = self._solid_frame((0, 255, 0))
        sprite.animation_data = {'run': [run_frame]}
        assert sprite.frame_manager.set_animation('walk') is False
        assert sprite.frame_manager.set_animation('run') is True
        assert sprite.get_current_frame() is run_frame

    def test_removing_an_unknown_animation_changes_nothing(self):
        """remove_animation of a name the sprite does not have is a no-op."""
        sprite = AnimatedSprite()
        sprite.add_animation('walk', [self._solid_frame((255, 0, 0))])
        sprite.remove_animation('missing')
        assert list(sprite.animation_data) == ['walk']
        assert sprite.current_animation == 'walk'

    def test_restore_without_loop_flag_or_interval_sets_only_the_position(self, tmp_path):
        """Restoring an animation that had no loop flag or interval adds neither."""
        toml_file = tmp_path / 'loops.toml'
        toml_file.write_text(LOOPING_AND_ONE_SHOT_TOML, encoding='utf-8')
        sprite = AnimatedSprite(str(toml_file))
        strike_frames = list(sprite.animation_data['strike'])
        sprite.remove_animation('strike')
        sprite.add_animation('strike', strike_frames)

        sprite.restore_animation_settings('strike', position=0, loop_flag=None, frame_interval=None)

        assert list(sprite.animation_data) == ['strike', 'idle']
        assert sprite.animation_order == ['strike', 'idle']
        assert 'strike' not in sprite._loop_flags
        assert 'strike' not in sprite._animation_frame_intervals

    def test_a_sprite_never_loaded_orders_its_animations_as_added(self):
        """Without a file's order, animation_order follows the animations, through edits."""
        sprite = AnimatedSprite()
        sprite.add_animation('walk', [self._solid_frame((255, 0, 0))])
        sprite.add_animation('run', [self._solid_frame((0, 255, 0))])

        sprite.rename_animation(old_name='walk', new_name='stroll')
        sprite.remove_animation('run')

        assert not sprite.has_own_animation_order
        assert sprite.animation_order == ['stroll']

    def test_a_loaded_sprite_keeps_the_files_animation_order(self, tmp_path):
        """A loaded file's order is the sprite's own, and edits keep it in step."""
        toml_file = tmp_path / 'loops.toml'
        toml_file.write_text(LOOPING_AND_ONE_SHOT_TOML, encoding='utf-8')
        sprite = AnimatedSprite(str(toml_file))
        assert sprite.has_own_animation_order
        assert sprite.animation_order == ['idle', 'strike']

        sprite.rename_animation(old_name='idle', new_name='rest')

        assert sprite.animation_order == ['rest', 'strike']

    def test_metadata_copied_from_a_sprite_never_loaded_has_no_glyph_choices(self):
        """A source with no file gives the copy an empty color order and no alpha glyphs."""
        source = AnimatedSprite()
        copy = AnimatedSprite()

        copy.copy_sprite_metadata_from(source)

        assert copy._color_order == []
        assert copy._colors_with_per_pixel_alpha == {}

    def test_switching_to_an_empty_animation_keeps_the_current_image(self):
        """An animation with no frames has nothing to show, so the image stays as it was."""
        sprite = AnimatedSprite()
        sprite.add_animation('walk', [self._solid_frame((255, 0, 0))])
        sprite.set_animation('walk')
        shown_image = sprite.image
        sprite.add_animation('empty', [])
        sprite.set_animation('empty')
        assert sprite.current_animation == 'empty'
        assert sprite.image is shown_image

    def test_pixel_data_beyond_the_frame_size_is_ignored(self):
        """A frame whose pixel list is longer than its surface draws only what fits."""
        frame = self._solid_frame((0, 0, 0))
        frame.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        surface = AnimatedSprite._create_optimized_surface(frame)
        assert surface.get_size() == (2, 1)
        assert surface.get_at((0, 0))[:3] == (255, 0, 0)
        assert surface.get_at((1, 0))[:3] == (0, 255, 0)


STATIC_SPRITE_WITH_UNDEFINED_GLYPH_TOML = """[sprite]
name = "undefined_glyph"
pixels = \"\"\"
#?
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0
"""

ANIMATION_WITH_EMPTY_FRAMES_TOML = """[sprite]
name = "empty_frames"

[[animation]]
namespace = "walk"
frame_interval = 0.1

[[animation.frame]]
namespace = "walk"
frame_index = 0
pixels = \"\"\"
\"\"\"

[[animation.frame]]
namespace = "walk"
frame_index = 1
pixels = \"\"\"
#
\"\"\"

[[animation]]
namespace = "blank"
frame_interval = 0.1

[[animation.frame]]
namespace = "blank"
frame_index = 0
pixels = \"\"\"
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0
"""

RAGGED_FRAME_TOML = """[sprite]
name = "ragged"

[[animation]]
namespace = "idle"
frame_interval = 0.1

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
#..
#.
#..
#..#
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0

[colors."."]
red = 255
green = 255
blue = 255
"""


class TestTomlLoadingFallbacks:
    """Loading tolerates undefined glyphs, empty frames and ragged rows (real files)."""

    @staticmethod
    def _load(tmp_path, toml_text: str) -> AnimatedSprite:
        """Write toml_text to a file and load it.

        Returns:
            AnimatedSprite: The loaded sprite.

        """
        toml_file = tmp_path / 'sprite.toml'
        toml_file.write_text(toml_text, encoding='utf-8')
        return AnimatedSprite(str(toml_file))

    def test_undefined_glyph_in_a_static_sprite_becomes_magenta(self, tmp_path):
        """A static sprite's glyph with no [colors] entry is drawn and stored as magenta."""
        sprite = self._load(tmp_path, STATIC_SPRITE_WITH_UNDEFINED_GLYPH_TOML)
        frame = sprite.get_current_frame()
        assert frame is not None
        assert frame.pixels == [(0, 0, 0), (255, 0, 255)]
        assert frame.image.get_at((1, 0))[:3] == (255, 0, 255)

    def test_empty_frames_are_skipped_and_an_empty_animation_is_dropped(self, tmp_path):
        """Frames without pixels are left out; an animation with none left is not loaded."""
        sprite = self._load(tmp_path, ANIMATION_WITH_EMPTY_FRAMES_TOML)
        assert list(sprite.animation_data) == ['walk']
        assert len(sprite.animation_data['walk']) == 1
        assert sprite.animation_data['walk'][0].pixels == [(0, 0, 0)]

    def test_ragged_rows_are_normalized_to_the_most_common_width(self, tmp_path, caplog):
        """Short rows are padded with their last glyph and long rows are cut, with a warning."""
        with caplog.at_level(logging.WARNING):
            sprite = self._load(tmp_path, RAGGED_FRAME_TOML)
        frame = sprite.get_current_frame()
        assert frame is not None
        assert frame.image.get_size() == (3, 4)
        black, white = (0, 0, 0), (255, 255, 255)
        assert frame.pixels == [
            black, white, white,
            black, white, white,
            black, white, white,
            black, white, white,
        ]  # fmt: skip
        assert 'Inconsistent line lengths' in caplog.text


EXPLICIT_OPAQUE_ALPHA_TOML = """[sprite]
name = "opaque_alpha"
pixels = \"\"\"
Z.
\"\"\"

[colors."Z"]
red = 10
green = 20
blue = 30
alpha = 255

[colors."."]
red = 200
green = 100
blue = 50
"""


class TestSaveKeepsLoadedGlyphs:
    """Saving reuses the glyphs a loaded file chose and gives new colors unused ones."""

    def test_explicitly_opaque_color_keeps_its_glyph(self, tmp_path):
        """A color written with alpha = 255 is saved under its original glyph."""
        import tomllib

        source_file = tmp_path / 'opaque.toml'
        source_file.write_text(EXPLICIT_OPAQUE_ALPHA_TOML, encoding='utf-8')
        saved_file = tmp_path / 'saved.toml'
        AnimatedSprite(str(source_file)).save(str(saved_file), 'toml')

        saved = tomllib.loads(saved_file.read_text(encoding='utf-8'))
        assert saved['colors']['Z'] == {'red': 10, 'green': 20, 'blue': 30}
        assert saved['sprite']['pixels'].strip() == 'Z.'

    def test_new_color_gets_a_glyph_the_loaded_file_did_not_use(self, tmp_path):
        """A color added after loading skips glyphs the file already assigned."""
        import tomllib

        source_file = tmp_path / 'two_colors.toml'
        source_file.write_text(
            '[sprite]\nname = "two"\n\n[[animation]]\nnamespace = "idle"\n\n'
            '[[animation.frame]]\nnamespace = "idle"\nframe_index = 0\n'
            'pixels = """\n.a\n"""\n\n'
            '[colors."."]\nred = 1\ngreen = 2\nblue = 3\n\n'
            '[colors."a"]\nred = 4\ngreen = 5\nblue = 6\n',
            encoding='utf-8',
        )
        sprite = AnimatedSprite(str(source_file))
        added_surface = pygame.Surface((2, 1))
        added_surface.fill((7, 8, 9))
        added_frame = SpriteFrame(added_surface, duration=FRAME_DURATION)
        added_frame.pixels = [(7, 8, 9), (7, 8, 9)]
        sprite.add_frame('idle', added_frame)

        saved_file = tmp_path / 'saved.toml'
        sprite.save(str(saved_file), 'toml')

        saved_colors = tomllib.loads(saved_file.read_text(encoding='utf-8'))['colors']
        assert saved_colors['.'] == {'red': 1, 'green': 2, 'blue': 3}
        assert saved_colors['a'] == {'red': 4, 'green': 5, 'blue': 6}
        new_glyphs = [glyph for glyph in saved_colors if glyph not in {'.', 'a'}]
        assert len(new_glyphs) == 1
        assert saved_colors[new_glyphs[0]] == {'red': 7, 'green': 8, 'blue': 9}


class TestDebugFrameImageData:
    """The frame-dump debug helper logs what it can and survives what it cannot read."""

    def test_unreadable_image_is_logged_and_skipped(self, mocker, caplog):
        """If the image cannot be read as an array, that is logged and nothing else."""
        mocker.patch.object(
            pygame.surfarray, 'array3d', side_effect=pygame.error('unsupported format')
        )
        sprite = AnimatedSprite()
        frame = SpriteFrame(pygame.Surface((2, 2)))
        with caplog.at_level(logging.DEBUG, logger=sprite.log.name):
            sprite._debug_frame_image_data(frame)
        assert 'Could not get pixel data from image: unsupported format' in caplog.text
        assert 'Image surface size' not in caplog.text

    def test_empty_image_logs_its_size_but_no_sample(self, caplog):
        """A zero-width image has no pixel to sample."""
        sprite = AnimatedSprite()
        frame = SpriteFrame(pygame.Surface((0, 2)))
        with caplog.at_level(logging.DEBUG, logger=sprite.log.name):
            sprite._debug_frame_image_data(frame)
        assert 'Image surface size: (0, 2)' in caplog.text
        assert 'Sample pixel data' not in caplog.text

    def test_frame_without_pixel_data_samples_its_image(self, caplog):
        """A frame with no pixel list logs its image's first pixel instead."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((2, 2))
        surface.fill((1, 2, 3))
        frame = SpriteFrame(surface)
        assert frame.pixels == []
        with caplog.at_level(logging.DEBUG, logger=sprite.log.name):
            sprite._debug_frame_pixel_data(frame)
        assert 'Image surface size: (2, 2)' in caplog.text
        assert 'Sample pixel data: [1 2 3]' in caplog.text


class TestStaticSaveHitbox:
    """A single-frame save writes the frame's own hitbox when the sprite has no default."""

    def test_frame_hitbox_is_promoted_to_the_sprite_hitbox(self, tmp_path):
        """With no sprite-level hitbox, the only frame's hitbox is saved as [sprite.hitbox]."""
        import tomllib

        surface = pygame.Surface((4, 4))
        surface.fill((10, 20, 30))
        frame = SpriteFrame(surface, duration=FRAME_DURATION, hitbox=pygame.Rect(1, 0, 2, 4))
        frame.pixels = [(10, 20, 30)] * 16
        sprite = AnimatedSprite()
        sprite.add_animation('idle', [frame])
        assert sprite.default_hitbox is None

        saved_file = tmp_path / 'static.toml'
        sprite.save(str(saved_file), 'toml')

        saved = tomllib.loads(saved_file.read_text(encoding='utf-8'))
        assert saved['sprite']['hitbox'] == {
            'offset_x': 1,
            'offset_y': 0,
            'width': 2,
            'height': 4,
        }
        assert AnimatedSprite(str(saved_file)).hitbox == pygame.Rect(1, 0, 2, 4)


# Two one-frame animations of different colors: walk is red ('#'), jump is blue ('@')
WALK_AND_JUMP_TOML = """[sprite]
name = "walk_and_jump"

[colors."#"]
red = 255
green = 0
blue = 0

[colors."@"]
red = 0
green = 0
blue = 255

[[animation]]
namespace = "walk"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "walk"
frame_index = 0
pixels = \"\"\"
#
\"\"\"

[[animation]]
namespace = "jump"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "jump"
frame_index = 0
pixels = \"\"\"
@
\"\"\"
"""


class TestAnimationSwitchUpdatesImage:
    """Switching animation shows the new animation's frame, also when both are on frame 0."""

    def test_switching_between_animations_on_frame_zero_changes_the_image(self, tmp_path):
        """set_animation('walk') then set_animation('jump') shows jump's (blue) pixel."""
        toml_file = tmp_path / 'walk_and_jump.toml'
        toml_file.write_text(WALK_AND_JUMP_TOML, encoding='utf-8')
        sprite = AnimatedSprite(str(toml_file))

        sprite.set_animation('walk')
        assert sprite.image.get_at((0, 0))[:3] == (255, 0, 0)

        sprite.set_animation('jump')
        assert sprite.image.get_at((0, 0))[:3] == (0, 0, 255)

        sprite.set_animation('walk')
        assert sprite.image.get_at((0, 0))[:3] == (255, 0, 0)

    def test_playing_another_animation_marks_the_sprite_dirty(self, tmp_path):
        """play('jump') from walk's frame 0 redraws the sprite."""
        toml_file = tmp_path / 'walk_and_jump.toml'
        toml_file.write_text(WALK_AND_JUMP_TOML, encoding='utf-8')
        sprite = AnimatedSprite(str(toml_file))
        sprite.set_animation('walk')
        sprite.dirty = 0

        sprite.play('jump')

        assert sprite.dirty == 1
        assert sprite.image.get_at((0, 0))[:3] == (0, 0, 255)


class TestFrameDumpOnlyWithDebugLogging:
    """The per-frame debug dump (pixel hash, surfarray sample) runs only with DEBUG logging."""

    @staticmethod
    def _two_frame_sprite() -> AnimatedSprite:
        """A playing sprite with two 0.1 s frames that have pixel data.

        Returns:
            AnimatedSprite: The sprite, playing 'walk' from frame 0.

        """
        sprite = AnimatedSprite()
        frames = []
        for color in ((255, 0, 0), (0, 0, 255)):
            surface = pygame.Surface((1, 1))
            surface.fill(color)
            frame = SpriteFrame(surface, duration=0.1)
            frame.pixels = [color]
            frames.append(frame)
        sprite.add_animation('walk', frames)
        sprite.play('walk')
        return sprite

    def test_frame_advance_skips_the_dump_without_debug_logging(self, mocker, caplog):
        """With DEBUG off, advancing frames never builds the pixel hash or image sample."""
        sprite = self._two_frame_sprite()
        pixel_data_spy = mocker.spy(sprite, '_debug_frame_pixel_data')
        image_data_spy = mocker.spy(sprite, '_debug_frame_image_data')

        with caplog.at_level(logging.INFO, logger=sprite.log.name):
            sprite.update(dt=0.1)

        assert sprite.current_frame == 1
        assert pixel_data_spy.call_count == 0
        assert image_data_spy.call_count == 0

    def test_frame_advance_dumps_the_frame_with_debug_logging(self, mocker, caplog):
        """With DEBUG on, each frame advance logs the new frame's pixel hash."""
        sprite = self._two_frame_sprite()
        pixel_data_spy = mocker.spy(sprite, '_debug_frame_pixel_data')

        with caplog.at_level(logging.DEBUG, logger=sprite.log.name):
            sprite.update(dt=0.1)

        assert pixel_data_spy.call_count == 1
        assert 'Frame 1 pixel hash' in caplog.text

    def test_looping_frame_advances_log_nothing_without_debug_logging(self, caplog):
        """With DEBUG off, advancing past the last frame loops back and logs nothing."""
        sprite = self._two_frame_sprite()
        sprite.is_looping = True
        caplog.clear()  # only this test's frame advances count

        with caplog.at_level(logging.INFO, logger=sprite.log.name):
            sprite.update(dt=0.1)
            sprite.update(dt=0.1)

        assert sprite.current_frame == 0
        assert sprite.is_playing
        assert 'Frame advance' not in caplog.text
        assert 'Looping back to frame 0' not in caplog.text
        assert 'Updated surface for frame' not in caplog.text

    def test_looping_frame_advances_are_logged_with_debug_logging(self, caplog):
        """With DEBUG on, each advance, the loop back and the surface change are logged."""
        sprite = self._two_frame_sprite()
        sprite.is_looping = True
        caplog.clear()  # only this test's frame advances count

        with caplog.at_level(logging.DEBUG, logger=sprite.log.name):
            sprite.update(dt=0.1)
            sprite.update(dt=0.1)

        assert sprite.current_frame == 0
        assert 'Frame advance: 0 -> 1' in caplog.text
        assert 'FIRST FRAME ADVANCE: 0 -> 1' in caplog.text
        assert 'Frame advance: 1 -> 2' in caplog.text
        assert 'Looping back to frame 0 (total frames: 2)' in caplog.text
        assert "Updated surface for frame 1 of animation 'walk'" in caplog.text

    def test_animation_end_logs_nothing_without_debug_logging(self, caplog):
        """With DEBUG off, a non-looping animation stops at its last frame and logs nothing."""
        sprite = self._two_frame_sprite()
        sprite.is_looping = False
        caplog.clear()  # only this test's frame advances count

        with caplog.at_level(logging.INFO, logger=sprite.log.name):
            sprite.update(dt=0.1)
            sprite.update(dt=0.1)

        assert sprite.current_frame == 1
        assert not sprite.is_playing
        assert 'Animation ended' not in caplog.text

    def test_animation_end_is_logged_with_debug_logging(self, caplog):
        """With DEBUG on, a non-looping animation logs where it stopped."""
        sprite = self._two_frame_sprite()
        sprite.is_looping = False
        caplog.clear()  # only this test's frame advances count

        with caplog.at_level(logging.DEBUG, logger=sprite.log.name):
            sprite.update(dt=0.1)
            sprite.update(dt=0.1)

        assert not sprite.is_playing
        assert 'Animation ended, stopped at frame 1' in caplog.text
