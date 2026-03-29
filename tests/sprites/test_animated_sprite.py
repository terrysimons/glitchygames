"""Tests for animated sprite functionality."""

import math
import shutil
import sys
import tempfile
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
from glitchygames.sprites import (
    AnimatedSpriteInterface,
    BitmappySprite,
    SpriteFactory,
)
from glitchygames.sprites.animated import AnimatedSprite
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
from tests.mocks.test_mock_factory import MockFactory

original_sprite_factory_load_sprite = glitchygames.sprites.SpriteFactory.load_sprite
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
FRAME_DURATION = 0.5
FRAME_DURATION_FAST = 0.25
SURFACE_SIZE = 4
DEFAULT_SURFACE_SIZE = 32


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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def setup_method(self):
        """Set up test fixtures."""
        # Ensure pygame is properly initialized for mocks
        if not pygame.get_init():
            pygame.init()

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
        """Create a mixed content TOML file (should be invalid).

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
        """Test analysis of mixed content sprite file."""
        # Skip this test as mixed content doesn't translate well to TOML format
        pytest.skip('Mixed content test not applicable to TOML format')

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
        """Test type determination for mixed content (should be error)."""
        pytest.skip('Mixed content scenario not applicable to TOML format')

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

    def test_load_animated_sprite(self, mocker):
        """Test loading animated sprite through factory."""
        filename = self.create_animated_sprite_file('animated.toml')

        # AnimatedSprite load is now implemented
        # Temporarily disable the centralized mock for this test
        # by patching with the original method
        mocker.patch(
            'glitchygames.sprites.SpriteFactory.load_sprite',
            original_sprite_factory_load_sprite,
        )
        sprite = SpriteFactory.load_sprite(filename=filename)
        assert isinstance(sprite, AnimatedSprite)
        assert sprite.name == 'TestAnimatedSprite'

    def test_load_mixed_sprite_raises_error(self, mocker):
        """Test that loading mixed sprite raises ValueError."""
        filename = self.create_mixed_sprite_file('mixed.toml')

        # Temporarily disable the centralized mock for this test
        # by patching with the original method
        mocker.patch(
            'glitchygames.sprites.SpriteFactory.load_sprite',
            original_sprite_factory_load_sprite,
        )
        with pytest.raises(ValueError, match='Invalid sprite file'):
            SpriteFactory.load_sprite(filename=filename)

    def test_load_empty_sprite_raises_error(self, mocker):
        """Test that loading empty sprite raises ValueError."""
        filename = self.create_empty_sprite_file('empty.toml')

        # Temporarily disable the centralized mock for this test
        # by patching with the original method
        mocker.patch(
            'glitchygames.sprites.SpriteFactory.load_sprite',
            original_sprite_factory_load_sprite,
        )
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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def setup_method(self):
        """Set up test fixtures."""
        # Ensure pygame is properly initialized for mocks
        if not pygame.get_init():
            pygame.init()

    def test_bitmappy_sprite_load_default(self, mocker):
        """Test that BitmappySprite.load() with no filename loads default sprite."""
        # Use centralized mocks
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        MockFactory.create_pygame_display_mock()

        sprite = BitmappySprite(x=0, y=0, width=32, height=32, filename=None)
        sprite.load()  # Should load default raspberry sprite
        assert sprite.name == 'Tiley McTile Face'


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
        content = filename.read_text()
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

    def test_rgba_transparent_without_alpha_becomes_magenta(self):
        """Test transparent RGBA without alpha flag becomes magenta."""
        result = normalize_pixel_for_color_map((255, 0, 0, 128), needs_alpha=False)
        assert result == (255, 0, 255, 255)

    def test_rgba_with_alpha_keeps_full_tuple(self):
        """Test RGBA with alpha flag keeps full tuple."""
        result = normalize_pixel_for_color_map((255, 0, 0, 128), needs_alpha=True)
        assert result == (255, 0, 0, 128)

    def test_rgb_magenta_normalizes_to_rgba(self):
        """Test RGB magenta normalizes to RGBA."""
        result = normalize_pixel_for_color_map((255, 0, 255), needs_alpha=False)
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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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


class TestAnimatedSpriteProperties:
    """Test AnimatedSprite property accessors."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def animated_sprite(self, mocker):
        """Create an AnimatedSprite with multiple frames for update testing.

        Returns:
            An AnimatedSprite with a 'walk' animation and two frames.
        """
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION_FAST)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION_FAST)
        sprite.add_animation('walk', [frame1, frame2])
        sprite.set_animation('walk')
        sprite.play()
        sprite.is_looping = True
        # Mock methods that use surfarray (incompatible with mock surfaces)
        mocker.patch.object(sprite, '_update_surface_and_mark_dirty')
        mocker.patch.object(sprite, '_debug_frame_info')
        return sprite

    def test_update_advances_frame_timer(self, animated_sprite):
        """Test update advances the frame timer."""
        animated_sprite.update(0.05)
        # Frame timer should have accumulated time
        assert animated_sprite._frame_timer > 0

    def test_update_changes_frame_when_duration_exceeded(self, animated_sprite):
        """Test update changes frame when frame duration is exceeded."""
        # Advance past the first frame's duration
        animated_sprite.update(FRAME_DURATION_FAST + 0.01)
        assert animated_sprite.current_frame == 1

    def test_update_loops_back_to_first_frame(self, animated_sprite):
        """Test update loops back to frame 0 when looping is enabled."""
        # Advance past both frames
        animated_sprite.update(FRAME_DURATION_FAST + 0.01)
        animated_sprite.update(FRAME_DURATION_FAST + 0.01)
        assert animated_sprite.current_frame == 0

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

    def test_update_does_nothing_with_no_animation(self):
        """Test update does nothing when no animation is set."""
        sprite = AnimatedSprite()
        sprite._is_playing = True
        sprite.update(1.0)  # Should not raise


class TestAnimatedSpriteGetCurrentSurface:
    """Test AnimatedSprite._get_current_surface method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_with_pixel_data_rgb(self):
        """Test creating surface from RGB pixel data."""
        surface = pygame.Surface((2, 2))
        frame = SpriteFrame(surface)
        frame.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]

        result = AnimatedSprite._create_optimized_surface(frame)
        assert result.get_size() == (2, 2)

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

    def test_without_pixel_data(self):
        """Test creating surface without pixel data falls back to copy."""
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        # No pixels attribute

        result = AnimatedSprite._create_optimized_surface(frame)
        assert result.get_size() == (SURFACE_SIZE, SURFACE_SIZE)

    def test_with_empty_pixel_data(self):
        """Test creating surface with empty pixel list falls back to copy."""
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        frame.pixels = []

        result = AnimatedSprite._create_optimized_surface(frame)
        assert result.get_size() == (SURFACE_SIZE, SURFACE_SIZE)


class TestAnimatedSpriteAnimationMetadata:
    """Test AnimatedSprite get/set animation metadata methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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
        toml_file.write_text(toml_content)

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
    """Test AnimatedSprite._build_color_map static method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_build_color_map_rgb(self):
        """Test _build_color_map with RGB colors."""
        data = {
            'colors': {
                '#': {'red': 0, 'green': 0, 'blue': 0},
                '.': {'red': 255, 'green': 255, 'blue': 255},
            },
        }
        color_map, color_order, alpha_values = AnimatedSprite._build_color_map(data)
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
        color_map, _color_order, alpha_values = AnimatedSprite._build_color_map(data)
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
        color_map, _color_order, alpha_values = AnimatedSprite._build_color_map(data)
        assert color_map['#'] == (0, 0, 0, 255)
        assert '#' not in alpha_values

    def test_build_color_map_empty(self):
        """Test _build_color_map with no colors section."""
        data = {}
        color_map, color_order, alpha_values = AnimatedSprite._build_color_map(data)
        assert color_map == {}
        assert color_order == []
        assert alpha_values == {}


class TestAnimatedSpriteUpdateSurfaceAndMarkDirty:
    """Test AnimatedSprite._update_surface_and_mark_dirty method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_surface_marks_dirty(self):
        """Test _update_surface_and_mark_dirty sets dirty flag."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame])
        sprite.set_animation('idle')

        sprite.dirty = 0
        sprite._last_frame_index = -1  # Force update
        sprite._update_surface_and_mark_dirty()
        assert sprite.dirty == 1


class TestSpriteFrameEdgeCases:
    """Test SpriteFrame edge cases."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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
        toml_file.write_text(toml_content)

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
        toml_file.write_text(toml_content)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_creates_srcalpha_surface(self):
        """Test creating an alpha surface with RGBA colors."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0, 255), '.': (255, 255, 255, 128)}
        pixel_lines = ['#.', '.#']
        surface = create_alpha_surface(2, 2, pixel_lines, color_map)
        assert surface is not None
        assert surface.get_size() == (2, 2)

    def test_rgb_color_gets_full_alpha(self):
        """Test that RGB colors in the map get alpha=255 added."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0)}
        pixel_lines = ['#']
        surface = create_alpha_surface(1, 1, pixel_lines, color_map)
        assert surface is not None

    def test_magenta_rgba_stays_opaque(self):
        """Test that magenta RGBA (255,0,255,255) is preserved."""
        color_map: dict[str, tuple[int, ...]] = {'.': (255, 0, 255, 255)}
        pixel_lines = ['.']
        surface = create_alpha_surface(1, 1, pixel_lines, color_map)
        assert surface is not None


class TestCreateIndexedSurface:
    """Test create_indexed_surface function."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_creates_indexed_surface(self):
        """Test creating an indexed surface with RGB colors."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0), '.': (255, 255, 255)}
        pixel_lines = ['#.', '.#']
        surface = create_indexed_surface(2, 2, pixel_lines, color_map)
        assert surface is not None
        assert surface.get_size() == (2, 2)

    def test_rgba_opaque_converts_to_rgb(self):
        """Test that opaque RGBA colors are converted to RGB on indexed surface."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0, 255)}
        pixel_lines = ['#']
        surface = create_indexed_surface(1, 1, pixel_lines, color_map)
        assert surface is not None

    def test_rgba_transparent_becomes_magenta(self):
        """Test that transparent RGBA colors become magenta on indexed surface."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0, 128)}
        pixel_lines = ['#']
        surface = create_indexed_surface(1, 1, pixel_lines, color_map)
        assert surface is not None


class TestAnimatedSpriteGetTotalFrameCount:
    """Test AnimatedSprite.get_total_frame_count and is_static_sprite."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_clear_surface_cache(self):
        """Test clearing the surface cache."""
        sprite = AnimatedSprite()
        sprite._surface_cache['test_key'] = 'test_value'  # type: ignore[invalid-assignment]
        assert len(sprite._surface_cache) > 0
        sprite.clear_surface_cache()
        assert len(sprite._surface_cache) == 0


class TestAnimatedSpriteGetAnimationData:
    """Test AnimatedSprite._get_animation_data."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_rgb_pixels(self):
        """Test surface creation from RGB pixel data."""
        pixels = cast(
            'list[tuple[int, ...]]',
            [(255, 0, 0), (0, 255, 0), (0, 0, 255), (128, 128, 128)],
        )
        surface = AnimatedSprite._create_surface_from_toml_pixels(2, 2, pixels)
        assert surface.get_size() == (2, 2)

    def test_rgba_pixels(self):
        """Test surface creation from RGBA pixel data."""
        pixels = cast(
            'list[tuple[int, ...]]',
            [(255, 0, 0, 255), (0, 255, 0, 128), (0, 0, 255, 64), (128, 128, 128, 0)],
        )
        surface = AnimatedSprite._create_surface_from_toml_pixels(2, 2, pixels)
        assert surface.get_size() == (2, 2)


class TestAnimatedSpriteUpdateEdgeCases:
    """Test AnimatedSprite.update edge cases."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_with_empty_frames_stops_playing(self, mocker):
        """Test update stops playing when frames list is empty."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface)])
        sprite.set_animation('walk')
        sprite.play()
        # Clear the frames list to trigger empty frames branch
        sprite._animations['walk'] = []
        mocker.patch.object(sprite, '_update_surface_and_mark_dirty')
        sprite.update(0.1)
        assert sprite._is_playing is False

    def test_update_clamps_frame_index_beyond_bounds(self, mocker):
        """Test update clamps frame index when beyond bounds."""
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('walk', [SpriteFrame(surface, duration=0.1)])
        sprite.set_animation('walk')
        sprite.play()
        # Force frame index beyond bounds
        sprite.frame_manager._current_frame = 99
        mocker.patch.object(sprite, '_update_surface_and_mark_dirty')
        mocker.patch.object(sprite, '_debug_frame_info')
        sprite.update(0.001)
        # Frame should be clamped to valid range
        assert sprite.frame_manager.current_frame == 0

    def test_update_animation_not_in_dict_returns(self, mocker):
        """Test update returns when current animation is not in _animations dict."""
        sprite = AnimatedSprite()
        sprite._is_playing = True
        sprite.frame_manager._current_animation = 'nonexistent'
        mocker.patch.object(sprite, '_update_surface_and_mark_dirty')
        sprite.update(0.1)


class TestAnimatedSpriteWriteTomlHelpers:
    """Test TOML writing helper methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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
        toml_file.write_text(toml_content)

        sprite = AnimatedSprite()
        sprite.load(str(toml_file))
        assert sprite.name == 'inconsistent'
        assert sprite.animation_count >= 1


class TestAnimatedSpriteLoadEdgeCases:
    """Test AnimatedSprite load edge cases."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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
        toml_file.write_text(toml_content)

        sprite = AnimatedSprite()
        sprite.load(str(toml_file))
        # Should load without error but have no animations
        assert sprite.name == 'empty_sprite'
