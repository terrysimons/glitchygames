"""Deeper coverage tests for glitchygames/sprites/animated.py.

Targets areas NOT covered by test_animated_coverage.py:
- AnimatedSprite.update() method with animation timing
- AnimatedSprite.save() method
- AnimatedSprite._update_surface_and_mark_dirty
- AnimatedSprite._get_current_surface caching
- AnimatedSprite._create_optimized_surface with pixel data
- AnimatedSprite.get_animation_metadata
- AnimatedSprite.set_animation_metadata
- AnimatedSprite.load() with TOML files
- AnimatedSprite._build_color_map
- AnimatedSprite._convert_static_sprite
- AnimatedSprite._set_initial_animation
- SpriteFrame edge cases
- FrameManager edge cases with set_frame returning True/False
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites.animated import (
    AnimatedSprite,
    SpriteFrame,
)
from tests.mocks.test_mock_factory import MockFactory

# Constants
SURFACE_SIZE = 4
FRAME_DURATION = 0.5
FRAME_DURATION_FAST = 0.1


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
            }
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
            }
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
            }
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
        large_pixels = [(255, 0, 0, 255)] * 8
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
