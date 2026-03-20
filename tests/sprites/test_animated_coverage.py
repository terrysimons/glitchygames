"""Coverage tests for glitchygames/sprites/animated.py.

Targets uncovered areas: FrameManager observer notifications,
AnimatedSprite lifecycle methods, SpriteFrame properties,
helper functions, and edge cases in frame management.
"""

import math
import sys
from pathlib import Path
from typing import cast

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites.animated import (
    AnimatedSprite,
    SpriteFrame,
    _convert_pixels_to_rgb_if_possible,
    _convert_pixels_to_rgba_if_needed,
    _extract_pixel_colors,
    _lookup_in_map,
    _lookup_pixel_char,
    _needs_alpha_channel,
    _normalize_pixel_for_color_map,
)
from tests.mocks.test_mock_factory import MockFactory

# Constants
FRAME_DURATION = 0.5
FRAME_DURATION_FAST = 0.25
SURFACE_SIZE = 4
DEFAULT_SURFACE_SIZE = 32


class TestNeedsAlphaChannel:
    """Test the _needs_alpha_channel helper function."""

    def test_opaque_rgb_pixels(self):
        """Test RGB pixels without magenta don't need alpha."""
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        assert _needs_alpha_channel(pixels) is False

    def test_magenta_rgb_pixels_need_alpha(self):
        """Test magenta RGB pixels need alpha channel."""
        pixels = [(255, 0, 0), (255, 0, 255)]
        assert _needs_alpha_channel(pixels) is True

    def test_opaque_rgba_pixels(self):
        """Test fully opaque RGBA pixels don't need alpha."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 255)]
        assert _needs_alpha_channel(pixels) is False

    def test_transparent_rgba_pixels_need_alpha(self):
        """Test RGBA pixels with transparency need alpha."""
        pixels = [(255, 0, 0, 128)]
        assert _needs_alpha_channel(pixels) is True

    def test_empty_pixels(self):
        """Test empty pixel list doesn't need alpha."""
        assert _needs_alpha_channel([]) is False


class TestConvertPixelsToRgb:
    """Test _convert_pixels_to_rgb_if_possible."""

    def test_opaque_rgba_converts_to_rgb(self):
        """Test that fully opaque RGBA pixels get converted to RGB."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 255)]
        result = _convert_pixels_to_rgb_if_possible(pixels)
        assert result == [(255, 0, 0), (0, 255, 0)]

    def test_transparent_rgba_stays_rgba(self):
        """Test that transparent RGBA pixels stay as-is."""
        pixels = [(255, 0, 0, 128)]
        result = _convert_pixels_to_rgb_if_possible(pixels)
        assert result == [(255, 0, 0, 128)]

    def test_rgb_pixels_pass_through(self):
        """Test that RGB pixels pass through unchanged."""
        pixels = [(255, 0, 0), (0, 255, 0)]
        result = _convert_pixels_to_rgb_if_possible(pixels)
        assert result == [(255, 0, 0), (0, 255, 0)]


class TestConvertPixelsToRgba:
    """Test _convert_pixels_to_rgba_if_needed."""

    def test_rgb_converts_to_rgba(self):
        """Test that RGB pixels get converted to RGBA with full opacity."""
        pixels = [(255, 0, 0), (0, 255, 0)]
        result = _convert_pixels_to_rgba_if_needed(pixels)
        assert result == [(255, 0, 0, 255), (0, 255, 0, 255)]

    def test_rgba_passes_through(self):
        """Test that RGBA pixels pass through unchanged."""
        pixels = [(255, 0, 0, 128)]
        result = _convert_pixels_to_rgba_if_needed(pixels)
        assert result == [(255, 0, 0, 128)]

    def test_magenta_converts_with_full_alpha(self):
        """Test that magenta RGB converts to RGBA with full opacity."""
        pixels = [(255, 0, 255)]
        result = _convert_pixels_to_rgba_if_needed(pixels)
        assert result == [(255, 0, 255, 255)]


class TestNormalizePixelForColorMap:
    """Test _normalize_pixel_for_color_map."""

    def test_rgba_magenta_normalizes(self):
        """Test RGBA magenta always normalizes to (255,0,255,255)."""
        result = _normalize_pixel_for_color_map((255, 0, 255, 128), needs_alpha=True)
        assert result == (255, 0, 255, 255)

    def test_rgba_opaque_without_alpha_becomes_rgb(self):
        """Test opaque RGBA without alpha flag becomes RGB."""
        result = _normalize_pixel_for_color_map((255, 0, 0, 255), needs_alpha=False)
        assert result == (255, 0, 0)

    def test_rgba_transparent_without_alpha_becomes_magenta(self):
        """Test transparent RGBA without alpha flag becomes magenta."""
        result = _normalize_pixel_for_color_map((255, 0, 0, 128), needs_alpha=False)
        assert result == (255, 0, 255, 255)

    def test_rgba_with_alpha_keeps_full_tuple(self):
        """Test RGBA with alpha flag keeps full tuple."""
        result = _normalize_pixel_for_color_map((255, 0, 0, 128), needs_alpha=True)
        assert result == (255, 0, 0, 128)

    def test_rgb_magenta_normalizes_to_rgba(self):
        """Test RGB magenta normalizes to RGBA."""
        result = _normalize_pixel_for_color_map((255, 0, 255), needs_alpha=False)
        assert result == (255, 0, 255, 255)

    def test_rgb_non_magenta_passes_through(self):
        """Test non-magenta RGB passes through."""
        result = _normalize_pixel_for_color_map((255, 0, 0), needs_alpha=False)
        assert result == (255, 0, 0)


class TestLookupInMap:
    """Test _lookup_in_map."""

    def test_found_key(self):
        """Test successful lookup returns character."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0): '#'}
        assert _lookup_in_map((255, 0, 0), color_map) == '#'

    def test_missing_key_raises(self):
        """Test missing key raises KeyError."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0): '#'}
        with pytest.raises(KeyError, match='not found in color map'):
            _lookup_in_map((0, 0, 0), color_map)


class TestLookupPixelChar:
    """Test _lookup_pixel_char."""

    def test_rgb_pixel_non_magenta(self):
        """Test RGB pixel lookup in non-alpha map."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0): '#'}
        result = _lookup_pixel_char((255, 0, 0), color_map, map_uses_alpha=False)
        assert result == '#'

    def test_rgb_magenta_pixel(self):
        """Test RGB magenta pixel lookup normalizes to RGBA."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 255, 255): '.'}
        result = _lookup_pixel_char((255, 0, 255), color_map, map_uses_alpha=False)
        assert result == '.'

    def test_rgb_pixel_in_alpha_map_rgba_match(self):
        """Test RGB pixel lookup in alpha map with RGBA match."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0, 255): '#'}
        result = _lookup_pixel_char((255, 0, 0), color_map, map_uses_alpha=True)
        assert result == '#'

    def test_rgb_pixel_in_alpha_map_rgb_match(self):
        """Test RGB pixel lookup in alpha map with RGB match."""
        color_map: dict[tuple[int, ...], str] = {(255, 0, 0): '#'}
        result = _lookup_pixel_char((255, 0, 0), color_map, map_uses_alpha=True)
        assert result == '#'


class TestExtractPixelColors:
    """Test _extract_pixel_colors."""

    def test_extract_colors(self):
        """Test extracting colors from pixel lines."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0), '.': (255, 255, 255)}
        pixel_lines = ['#.', '.#']
        result = _extract_pixel_colors(pixel_lines, width=2, height=2, color_map=color_map)
        assert len(result) == 4
        assert result[0] == (0, 0, 0)
        assert result[1] == (255, 255, 255)

    def test_unknown_char_defaults_to_magenta(self):
        """Test unknown characters default to magenta."""
        color_map: dict[str, tuple[int, ...]] = {'#': (0, 0, 0)}
        pixel_lines = ['#?']
        result = _extract_pixel_colors(pixel_lines, width=2, height=1, color_map=color_map)
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
        new_pixels = cast(list[tuple[int, ...]], [(255, 0, 0, 255)] * pixel_count)
        frame.set_pixel_data(new_pixels)
        assert frame.pixels == new_pixels

    def test_set_pixel_data_rgb(self, frame):
        """Test set_pixel_data handles RGB pixels."""
        pixel_count = SURFACE_SIZE * SURFACE_SIZE
        new_pixels = cast(list[tuple[int, ...]], [(0, 255, 0)] * pixel_count)
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
