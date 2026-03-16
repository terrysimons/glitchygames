"""Tests for BitmapPixelSprite and ScrollArrowSprite classes from bitmappy.py."""

import pygame
import pytest

from glitchygames.tools.bitmappy import BitmapPixelSprite, ScrollArrowSprite
from tests.mocks import MockFactory


@pytest.fixture(autouse=True)
def clear_pixel_cache():
    """Clear the BitmapPixelSprite PIXEL_CACHE before and after each test."""
    BitmapPixelSprite.PIXEL_CACHE.clear()
    yield
    BitmapPixelSprite.PIXEL_CACHE.clear()


@pytest.fixture
def pygame_mocks(mocker):
    """Set up pygame mocks for sprite tests.

    Returns:
        dict: The pygame mock objects.

    """
    return MockFactory.setup_pygame_mocks_with_mocker(mocker)


@pytest.fixture
def mock_groups():
    """Create a mock LayeredDirty group for sprite initialization.

    Returns:
        pygame.sprite.LayeredDirty: A fresh sprite group.

    """
    return pygame.sprite.LayeredDirty()


@pytest.fixture
def default_pixel_sprite(pygame_mocks, mock_groups):
    """Create a BitmapPixelSprite with default parameters.

    Returns:
        BitmapPixelSprite: A 16x16 sprite at origin with border thickness 1.

    """
    return BitmapPixelSprite(
        x=0,
        y=0,
        width=16,
        height=16,
        name='test_pixel',
        pixel_number=0,
        border_thickness=1,
        groups=mock_groups,
    )


@pytest.fixture
def large_pixel_sprite(pygame_mocks, mock_groups):
    """Create a BitmapPixelSprite with larger dimensions.

    Returns:
        BitmapPixelSprite: A 32x32 sprite at (100, 200) with border thickness 2.

    """
    return BitmapPixelSprite(
        x=100,
        y=200,
        width=32,
        height=32,
        name='large_pixel',
        pixel_number=42,
        border_thickness=2,
        groups=mock_groups,
    )


@pytest.fixture
def default_scroll_arrow(pygame_mocks, mock_groups):
    """Create a ScrollArrowSprite with default (up) direction.

    Returns:
        ScrollArrowSprite: A 20x20 up-arrow sprite at origin.

    """
    return ScrollArrowSprite(
        x=0,
        y=0,
        width=20,
        height=20,
        groups=mock_groups,
        direction='up',
    )


class TestBitmapPixelSpriteInit:
    """Test BitmapPixelSprite initialization."""

    def test_init_default_parameters(self, default_pixel_sprite):
        """Test initialization with default parameters sets attributes correctly."""
        sprite = default_pixel_sprite
        assert sprite.pixel_number == 0
        assert sprite.pixel_width == 16
        assert sprite.pixel_height == 16
        assert sprite.border_thickness == 1
        assert sprite.color == (96, 96, 96)
        assert sprite.x == 0
        assert sprite.y == 0

    def test_init_custom_position(self, pygame_mocks, mock_groups):
        """Test initialization with custom x and y coordinates."""
        sprite = BitmapPixelSprite(
            x=50,
            y=75,
            width=8,
            height=8,
            name='positioned_pixel',
            pixel_number=5,
            border_thickness=1,
            groups=mock_groups,
        )
        assert sprite.x == 50
        assert sprite.y == 75

    def test_init_custom_pixel_number(self, pygame_mocks, mock_groups):
        """Test initialization with a specific pixel number."""
        sprite = BitmapPixelSprite(
            x=0,
            y=0,
            width=16,
            height=16,
            pixel_number=99,
            groups=mock_groups,
        )
        assert sprite.pixel_number == 99

    def test_init_zero_border_thickness(self, pygame_mocks, mock_groups):
        """Test initialization with zero border thickness."""
        sprite = BitmapPixelSprite(
            x=0,
            y=0,
            width=16,
            height=16,
            border_thickness=0,
            groups=mock_groups,
        )
        assert sprite.border_thickness == 0

    def test_init_sets_default_pixel_color_to_black_opaque(self, default_pixel_sprite):
        """Test that default pixel color is black with full alpha."""
        assert default_pixel_sprite.pixel_color == (0, 0, 0, 255)

    def test_init_creates_rect(self, default_pixel_sprite):
        """Test that initialization creates a valid rect."""
        assert default_pixel_sprite.rect is not None

    def test_init_with_name(self, default_pixel_sprite):
        """Test that the name attribute is set correctly."""
        assert default_pixel_sprite.name == 'test_pixel'

    def test_init_without_name(self, pygame_mocks, mock_groups):
        """Test initialization without a name argument."""
        sprite = BitmapPixelSprite(
            x=0,
            y=0,
            width=16,
            height=16,
            groups=mock_groups,
        )
        # Should not raise; name defaults to None
        assert sprite.pixel_number == 0


class TestBitmapPixelSpritePixelColor:
    """Test BitmapPixelSprite pixel_color property."""

    def test_pixel_color_getter_returns_rgba_tuple(self, default_pixel_sprite):
        """Test that pixel_color getter returns an RGBA tuple."""
        color = default_pixel_sprite.pixel_color
        assert isinstance(color, tuple)
        assert len(color) == 4

    def test_pixel_color_setter_with_rgba(self, default_pixel_sprite):
        """Test setting pixel_color with an RGBA tuple."""
        default_pixel_sprite.pixel_color = (255, 0, 0, 128)
        assert default_pixel_sprite.pixel_color == (255, 0, 0, 128)

    def test_pixel_color_setter_converts_rgb_to_rgba(self, default_pixel_sprite):
        """Test that setting an RGB tuple auto-appends alpha=255."""
        default_pixel_sprite.pixel_color = (0, 255, 0)
        assert default_pixel_sprite.pixel_color == (0, 255, 0, 255)

    def test_pixel_color_setter_sets_dirty_flag(self, default_pixel_sprite):
        """Test that setting pixel_color marks the sprite as dirty."""
        default_pixel_sprite.dirty = 0
        default_pixel_sprite.pixel_color = (100, 100, 100, 255)
        assert default_pixel_sprite.dirty == 1

    def test_pixel_color_setter_with_fully_transparent(self, default_pixel_sprite):
        """Test setting pixel_color with zero alpha."""
        default_pixel_sprite.pixel_color = (255, 255, 255, 0)
        assert default_pixel_sprite.pixel_color == (255, 255, 255, 0)

    def test_pixel_color_setter_rgb_preserves_all_channels(self, default_pixel_sprite):
        """Test that RGB to RGBA conversion preserves all three color channels."""
        default_pixel_sprite.pixel_color = (10, 20, 30)
        assert default_pixel_sprite.pixel_color[0] == 10
        assert default_pixel_sprite.pixel_color[1] == 20
        assert default_pixel_sprite.pixel_color[2] == 30
        assert default_pixel_sprite.pixel_color[3] == 255


class TestBitmapPixelSpriteUpdate:
    """Test BitmapPixelSprite update method."""

    def test_update_creates_surface_on_first_call(self, default_pixel_sprite):
        """Test that the first update creates a new surface and caches it."""
        default_pixel_sprite.pixel_color = (255, 0, 0, 255)
        default_pixel_sprite.update()
        cache_key = ((255, 0, 0, 255), 1)
        assert cache_key in BitmapPixelSprite.PIXEL_CACHE

    def test_update_uses_cache_on_second_call(self, default_pixel_sprite):
        """Test that the second update with same color uses cached surface."""
        default_pixel_sprite.pixel_color = (0, 255, 0, 255)
        default_pixel_sprite.update()
        cached_image = BitmapPixelSprite.PIXEL_CACHE[(0, 255, 0, 255), 1]

        # Second call should use the cached image
        default_pixel_sprite.update()
        assert default_pixel_sprite.image is cached_image

    def test_update_different_colors_create_different_cache_entries(
        self, default_pixel_sprite, pygame_mocks, mock_groups
    ):
        """Test that different pixel colors result in different cache entries."""
        default_pixel_sprite.pixel_color = (255, 0, 0, 255)
        default_pixel_sprite.update()

        second_sprite = BitmapPixelSprite(x=0, y=0, width=16, height=16, groups=mock_groups)
        second_sprite.pixel_color = (0, 0, 255, 255)
        second_sprite.update()

        assert len(BitmapPixelSprite.PIXEL_CACHE) == 2

    def test_update_same_color_different_border_creates_different_cache(
        self, pygame_mocks, mock_groups
    ):
        """Test that same color but different border thickness creates separate cache entries."""
        sprite_thin = BitmapPixelSprite(
            x=0, y=0, width=16, height=16, border_thickness=1, groups=mock_groups
        )
        sprite_thin.pixel_color = (255, 0, 0, 255)
        sprite_thin.update()

        sprite_thick = BitmapPixelSprite(
            x=0, y=0, width=16, height=16, border_thickness=3, groups=mock_groups
        )
        sprite_thick.pixel_color = (255, 0, 0, 255)
        sprite_thick.update()

        assert len(BitmapPixelSprite.PIXEL_CACHE) == 2

    def test_update_with_zero_border_thickness(self, pygame_mocks, mock_groups):
        """Test update with no border does not draw border rect."""
        sprite = BitmapPixelSprite(
            x=0, y=0, width=16, height=16, border_thickness=0, groups=mock_groups
        )
        sprite.pixel_color = (128, 128, 128, 255)
        sprite.update()
        cache_key = ((128, 128, 128, 255), 0)
        assert cache_key in BitmapPixelSprite.PIXEL_CACHE

    def test_update_preserves_rect_position(self, default_pixel_sprite):
        """Test that update preserves the sprite rect position."""
        default_pixel_sprite.rect.x = 50
        default_pixel_sprite.rect.y = 75
        default_pixel_sprite.pixel_color = (200, 100, 50, 255)
        default_pixel_sprite.update()
        assert default_pixel_sprite.rect.x == 50
        assert default_pixel_sprite.rect.y == 75

    def test_update_sets_image_attribute(self, default_pixel_sprite):
        """Test that update sets the image attribute to a valid surface."""
        default_pixel_sprite.pixel_color = (10, 20, 30, 255)
        default_pixel_sprite.update()
        assert default_pixel_sprite.image is not None


class TestBitmapPixelSpriteOnPixelUpdateEvent:
    """Test BitmapPixelSprite on_pixel_update_event method."""

    def test_on_pixel_update_event_with_callback(self, default_pixel_sprite, mocker):
        """Test that on_pixel_update_event dispatches to registered callback."""
        mock_callback = mocker.Mock()
        default_pixel_sprite.callbacks = {'on_pixel_update_event': mock_callback}
        mock_event = mocker.Mock(name='mock_event')

        default_pixel_sprite.on_pixel_update_event(mock_event)

        mock_callback.assert_called_once_with(event=mock_event, trigger=default_pixel_sprite)

    def test_on_pixel_update_event_without_callback(self, default_pixel_sprite, mocker):
        """Test that on_pixel_update_event does nothing when no callback is registered."""
        default_pixel_sprite.callbacks = {}
        mock_event = mocker.Mock(name='mock_event')

        # Should not raise
        default_pixel_sprite.on_pixel_update_event(mock_event)

    def test_on_pixel_update_event_with_empty_callbacks_dict(self, default_pixel_sprite, mocker):
        """Test on_pixel_update_event with callbacks dict but no matching key."""
        default_pixel_sprite.callbacks = {'some_other_event': mocker.Mock()}
        mock_event = mocker.Mock(name='mock_event')

        # Should not raise - the callback key doesn't match
        default_pixel_sprite.on_pixel_update_event(mock_event)

    def test_on_pixel_update_event_with_none_callback_value(self, default_pixel_sprite, mocker):
        """Test on_pixel_update_event when callback value is explicitly None."""
        default_pixel_sprite.callbacks = {'on_pixel_update_event': None}
        mock_event = mocker.Mock(name='mock_event')

        # Should not raise - callback is None so it won't be called
        default_pixel_sprite.on_pixel_update_event(mock_event)


class TestBitmapPixelSpriteOnLeftMouseButtonDownEvent:
    """Test BitmapPixelSprite on_left_mouse_button_down_event method."""

    def test_on_left_mouse_button_down_sets_dirty(self, default_pixel_sprite, mocker):
        """Test that left mouse button down sets dirty flag to 1."""
        default_pixel_sprite.dirty = 0
        mock_event = mocker.Mock(name='mock_event')
        default_pixel_sprite.callbacks = {}

        default_pixel_sprite.on_left_mouse_button_down_event(mock_event)

        assert default_pixel_sprite.dirty == 1

    def test_on_left_mouse_button_down_calls_pixel_update(self, default_pixel_sprite, mocker):
        """Test that left mouse button down triggers on_pixel_update_event."""
        mock_callback = mocker.Mock()
        default_pixel_sprite.callbacks = {'on_pixel_update_event': mock_callback}
        mock_event = mocker.Mock(name='mock_event')

        default_pixel_sprite.on_left_mouse_button_down_event(mock_event)

        mock_callback.assert_called_once_with(event=mock_event, trigger=default_pixel_sprite)

    def test_on_left_mouse_button_down_without_callbacks(self, default_pixel_sprite, mocker):
        """Test left mouse button down without any callbacks does not raise."""
        default_pixel_sprite.callbacks = {}
        mock_event = mocker.Mock(name='mock_event')

        # Should not raise
        default_pixel_sprite.on_left_mouse_button_down_event(mock_event)
        assert default_pixel_sprite.dirty == 1


class TestBitmapPixelSpriteCacheIsolation:
    """Test that PIXEL_CACHE is properly isolated between tests."""

    def test_cache_starts_empty(self):
        """Test that the pixel cache is empty at the start of each test."""
        assert len(BitmapPixelSprite.PIXEL_CACHE) == 0

    def test_cache_populated_after_update(self, default_pixel_sprite):
        """Test that cache is populated after a sprite update."""
        default_pixel_sprite.pixel_color = (50, 50, 50, 255)
        default_pixel_sprite.update()
        assert len(BitmapPixelSprite.PIXEL_CACHE) == 1

    def test_cache_empty_again_after_previous_test(self):
        """Verify the cache fixture clears between tests."""
        assert len(BitmapPixelSprite.PIXEL_CACHE) == 0


class TestScrollArrowSpriteInit:
    """Test ScrollArrowSprite initialization."""

    def test_init_up_direction(self, pygame_mocks, mock_groups):
        """Test initialization with 'up' direction."""
        sprite = ScrollArrowSprite(
            x=0, y=0, width=20, height=20, groups=mock_groups, direction='up'
        )
        assert sprite.direction == 'up'
        assert sprite.name == 'Scroll up Arrow'

    def test_init_down_direction(self, pygame_mocks, mock_groups):
        """Test initialization with 'down' direction."""
        sprite = ScrollArrowSprite(
            x=0, y=0, width=20, height=20, groups=mock_groups, direction='down'
        )
        assert sprite.direction == 'down'
        assert sprite.name == 'Scroll down Arrow'

    def test_init_plus_direction(self, pygame_mocks, mock_groups):
        """Test initialization with 'plus' direction."""
        sprite = ScrollArrowSprite(
            x=0, y=0, width=20, height=20, groups=mock_groups, direction='plus'
        )
        assert sprite.direction == 'plus'
        assert sprite.name == 'Scroll plus Arrow'

    def test_init_sets_visible_false(self, default_scroll_arrow):
        """Test that ScrollArrowSprite is initially invisible."""
        assert default_scroll_arrow.visible is False

    def test_init_sets_dirty_flag(self, default_scroll_arrow):
        """Test that ScrollArrowSprite starts with dirty=1."""
        assert default_scroll_arrow.dirty == 1

    def test_init_creates_image_surface(self, default_scroll_arrow):
        """Test that initialization creates an image surface."""
        assert default_scroll_arrow.image is not None

    def test_init_creates_rect(self, default_scroll_arrow):
        """Test that initialization creates a valid rect."""
        assert default_scroll_arrow.rect is not None

    def test_init_custom_position(self, pygame_mocks, mock_groups):
        """Test initialization with custom x and y coordinates."""
        sprite = ScrollArrowSprite(x=100, y=200, width=20, height=20, groups=mock_groups)
        assert sprite.rect.x == 100
        assert sprite.rect.y == 200

    def test_init_custom_dimensions(self, pygame_mocks, mock_groups):
        """Test initialization with custom width and height."""
        sprite = ScrollArrowSprite(x=0, y=0, width=30, height=40, groups=mock_groups)
        assert sprite.image.get_width() == 30
        assert sprite.image.get_height() == 40


class TestScrollArrowSpriteDrawArrow:
    """Test ScrollArrowSprite _draw_arrow method."""

    def test_draw_arrow_up_uses_polygon(self, pygame_mocks, mock_groups, mocker):
        """Test that 'up' direction draws a polygon."""
        mock_polygon = mocker.patch('pygame.draw.polygon')
        sprite = ScrollArrowSprite(
            x=0, y=0, width=20, height=20, groups=mock_groups, direction='up'
        )
        # _draw_arrow is called during __init__, so polygon should have been called
        assert mock_polygon.called

    def test_draw_arrow_down_uses_polygon(self, pygame_mocks, mock_groups, mocker):
        """Test that 'down' direction draws a polygon."""
        mock_polygon = mocker.patch('pygame.draw.polygon')
        sprite = ScrollArrowSprite(
            x=0, y=0, width=20, height=20, groups=mock_groups, direction='down'
        )
        assert mock_polygon.called

    def test_draw_arrow_plus_uses_lines(self, pygame_mocks, mock_groups, mocker):
        """Test that 'plus' direction draws lines instead of polygon."""
        mock_line = mocker.patch('pygame.draw.line')
        sprite = ScrollArrowSprite(
            x=0, y=0, width=20, height=20, groups=mock_groups, direction='plus'
        )
        # Plus sign draws two lines (vertical + horizontal)
        assert mock_line.call_count == 2

    def test_draw_arrow_fills_white_background(self, pygame_mocks, mock_groups, mocker):
        """Test that _draw_arrow fills with white background."""
        # We can verify by checking image pixel after init
        sprite = ScrollArrowSprite(
            x=0, y=0, width=20, height=20, groups=mock_groups, direction='up'
        )
        # Corner pixel should be white (255, 255, 255) since arrow doesn't cover it
        corner_color = sprite.image.get_at((0, 0))
        assert corner_color[0] == 255
        assert corner_color[1] == 255
        assert corner_color[2] == 255


class TestScrollArrowSpriteSetDirection:
    """Test ScrollArrowSprite set_direction method."""

    def test_set_direction_changes_direction(self, default_scroll_arrow):
        """Test that set_direction updates the direction attribute."""
        default_scroll_arrow.set_direction('down')
        assert default_scroll_arrow.direction == 'down'

    def test_set_direction_triggers_redraw(self, default_scroll_arrow, mocker):
        """Test that changing direction calls _draw_arrow."""
        mocker.patch.object(default_scroll_arrow, '_draw_arrow')
        default_scroll_arrow.set_direction('down')
        default_scroll_arrow._draw_arrow.assert_called_once()

    def test_set_direction_sets_dirty_flag(self, default_scroll_arrow):
        """Test that changing direction sets dirty=1."""
        default_scroll_arrow.dirty = 0
        default_scroll_arrow.set_direction('plus')
        assert default_scroll_arrow.dirty == 1

    def test_set_direction_same_direction_does_not_redraw(self, default_scroll_arrow, mocker):
        """Test that setting the same direction does not trigger a redraw."""
        mocker.patch.object(default_scroll_arrow, '_draw_arrow')
        default_scroll_arrow.set_direction('up')  # Same as initial direction
        default_scroll_arrow._draw_arrow.assert_not_called()

    def test_set_direction_same_direction_does_not_set_dirty(self, default_scroll_arrow):
        """Test that setting the same direction does not change dirty flag."""
        default_scroll_arrow.dirty = 0
        default_scroll_arrow.set_direction('up')  # Same as initial direction
        assert default_scroll_arrow.dirty == 0

    def test_set_direction_from_up_to_plus(self, default_scroll_arrow):
        """Test changing direction from up to plus."""
        default_scroll_arrow.set_direction('plus')
        assert default_scroll_arrow.direction == 'plus'

    def test_set_direction_multiple_changes(self, default_scroll_arrow):
        """Test multiple direction changes in sequence."""
        default_scroll_arrow.set_direction('down')
        assert default_scroll_arrow.direction == 'down'
        default_scroll_arrow.set_direction('plus')
        assert default_scroll_arrow.direction == 'plus'
        default_scroll_arrow.set_direction('up')
        assert default_scroll_arrow.direction == 'up'
