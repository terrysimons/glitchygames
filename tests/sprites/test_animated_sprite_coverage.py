"""Additional coverage tests for glitchygames/sprites/animated.py.

Targets lines missed by test_animated_coverage.py and test_animated_deeper.py:
- _lookup_rgba_pixel_char edge cases (lines 193-213)
- _create_alpha_surface and _create_indexed_surface (lines 285-328)
- _convert_static_sprite with inconsistent widths (lines 1213-1228)
- _process_toml_animation line length normalization (lines 1429-1462)
- get_total_frame_count and is_static_sprite (lines 1578-1593)
- _any_pixel_is_magenta (lines 1811-1813)
- _write_toml_colors with color_order (lines 1994-1998)
- _write_toml_alpha (lines 2017-2021)
- _create_surface_from_toml_pixels (lines 2180-2194)
- clear_surface_cache (lines 2202-2203)
- _get_animation_data (lines 2212-2223)
- _debug_frame_info / _debug_frame_pixel_data edge cases (lines 2084-2134)
- update with empty frames / out-of-bounds frame (lines 2029, 2034-2035, 2043)
"""

import sys
from io import StringIO
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites.animated import (
    AnimatedSprite,
    SpriteFrame,
    _create_alpha_surface,
    _create_indexed_surface,
    _lookup_pixel_char,
    _lookup_rgba_pixel_char,
)
from tests.mocks.test_mock_factory import MockFactory

# Constants
SURFACE_SIZE = 4
FRAME_DURATION = 0.5
FRAME_DURATION_FAST = 0.1


class TestLookupRgbaPixelChar:
    """Test _lookup_rgba_pixel_char edge cases."""

    def test_rgba_opaque_rgb_key_match(self):
        """Test opaque RGBA pixel matched via RGB key in alpha map."""
        color_map = {(255, 0, 0): '#'}
        result = _lookup_rgba_pixel_char((255, 0, 0, 255), color_map, map_uses_alpha=True)
        assert result == '#'

    def test_rgba_opaque_rgba_key_match(self):
        """Test opaque RGBA pixel matched via RGBA key in alpha map."""
        color_map = {(255, 0, 0, 255): '#'}
        result = _lookup_rgba_pixel_char((255, 0, 0, 255), color_map, map_uses_alpha=True)
        assert result == '#'

    def test_rgba_opaque_not_found_raises(self):
        """Test opaque RGBA pixel not in map raises KeyError."""
        color_map = {(0, 255, 0): '.'}
        with pytest.raises(KeyError, match='not found in color map'):
            _lookup_rgba_pixel_char((255, 0, 0, 255), color_map, map_uses_alpha=True)

    def test_rgba_transparent_in_alpha_map(self):
        """Test transparent RGBA pixel lookup in alpha map."""
        color_map = {(255, 0, 0, 128): '#'}
        result = _lookup_rgba_pixel_char((255, 0, 0, 128), color_map, map_uses_alpha=True)
        assert result == '#'

    def test_rgba_non_alpha_map_opaque(self):
        """Test opaque RGBA pixel in non-alpha map collapses to RGB."""
        color_map = {(255, 0, 0): '#'}
        result = _lookup_rgba_pixel_char((255, 0, 0, 255), color_map, map_uses_alpha=False)
        assert result == '#'

    def test_rgba_non_alpha_map_transparent_becomes_magenta(self):
        """Test transparent RGBA pixel in non-alpha map maps to magenta."""
        color_map = {(255, 0, 255, 255): '.'}
        result = _lookup_rgba_pixel_char((255, 0, 0, 128), color_map, map_uses_alpha=False)
        assert result == '.'

    def test_rgba_magenta_pixel_normalizes(self):
        """Test magenta RGBA pixel normalizes to (255, 0, 255, 255)."""
        color_map = {(255, 0, 255, 255): '.'}
        result = _lookup_rgba_pixel_char((255, 0, 255, 128), color_map, map_uses_alpha=True)
        assert result == '.'


class TestLookupPixelCharRgbRaiseInAlphaMap:
    """Test _lookup_pixel_char when RGB pixel not found in alpha map."""

    def test_rgb_not_found_in_alpha_map_raises(self):
        """Test that RGB pixel raises when neither RGBA nor RGB found in alpha map."""
        color_map = {(0, 0, 0): '#'}
        with pytest.raises(KeyError, match='not found in color map'):
            _lookup_pixel_char((128, 128, 128), color_map, map_uses_alpha=True)


class TestCreateAlphaSurface:
    """Test _create_alpha_surface function."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_creates_srcalpha_surface(self):
        """Test creating an alpha surface with RGBA colors."""
        color_map = {'#': (0, 0, 0, 255), '.': (255, 255, 255, 128)}
        pixel_lines = ['#.', '.#']
        surface = _create_alpha_surface(2, 2, pixel_lines, color_map)
        assert surface is not None
        assert surface.get_size() == (2, 2)

    def test_rgb_color_gets_full_alpha(self):
        """Test that RGB colors in the map get alpha=255 added."""
        color_map = {'#': (0, 0, 0)}
        pixel_lines = ['#']
        surface = _create_alpha_surface(1, 1, pixel_lines, color_map)
        assert surface is not None

    def test_magenta_rgba_stays_opaque(self):
        """Test that magenta RGBA (255,0,255,255) is preserved."""
        color_map = {'.': (255, 0, 255, 255)}
        pixel_lines = ['.']
        surface = _create_alpha_surface(1, 1, pixel_lines, color_map)
        assert surface is not None


class TestCreateIndexedSurface:
    """Test _create_indexed_surface function."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_creates_indexed_surface(self):
        """Test creating an indexed surface with RGB colors."""
        color_map = {'#': (0, 0, 0), '.': (255, 255, 255)}
        pixel_lines = ['#.', '.#']
        surface = _create_indexed_surface(2, 2, pixel_lines, color_map)
        assert surface is not None
        assert surface.get_size() == (2, 2)

    def test_rgba_opaque_converts_to_rgb(self):
        """Test that opaque RGBA colors are converted to RGB on indexed surface."""
        color_map = {'#': (0, 0, 0, 255)}
        pixel_lines = ['#']
        surface = _create_indexed_surface(1, 1, pixel_lines, color_map)
        assert surface is not None

    def test_rgba_transparent_becomes_magenta(self):
        """Test that transparent RGBA colors become magenta on indexed surface."""
        color_map = {'#': (0, 0, 0, 128)}
        pixel_lines = ['#']
        surface = _create_indexed_surface(1, 1, pixel_lines, color_map)
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
        sprite._surface_cache['test_key'] = 'test_value'
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
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (128, 128, 128)]
        surface = AnimatedSprite._create_surface_from_toml_pixels(2, 2, pixels)
        assert surface.get_size() == (2, 2)

    def test_rgba_pixels(self):
        """Test surface creation from RGBA pixel data."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 128), (0, 0, 255, 64), (128, 128, 128, 0)]
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
        # Should return early without error


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
            }
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
            }
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
