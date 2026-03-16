"""Coverage tests for glitchygames/tools/canvas_interfaces.py.

Targets uncovered areas: StaticCanvasInterface, AnimatedCanvasInterface,
MockPixelEvent, MockTrigger, serializers, and renderers.
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.tools.canvas_interfaces import (
    AnimatedCanvasInterface,
    AnimatedSpriteSerializer,
    MockPixelEvent,
    MockTrigger,
    StaticCanvasInterface,
    StaticSpriteSerializer,
)
from tests.mocks.test_mock_factory import MockFactory

# Constants for test values
CANVAS_SIZE = 4
PIXEL_COUNT = 16  # 4x4 = 16 pixels
MAGENTA = (255, 0, 255, 255)
RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
RED_RGB = (255, 0, 0)
GREEN_RGB = (0, 255, 0)


class TestMockPixelEvent:
    """Test MockPixelEvent pydantic model."""

    def test_create_mock_pixel_event(self):
        """Test MockPixelEvent can be created."""
        event = MockPixelEvent()
        assert event is not None


class TestMockTrigger:
    """Test MockTrigger pydantic model."""

    def test_create_mock_trigger_rgb(self):
        """Test MockTrigger with RGB color."""
        trigger = MockTrigger(pixel_number=42, pixel_color=(255, 0, 0))
        assert trigger.pixel_number == 42
        assert trigger.pixel_color == (255, 0, 0)

    def test_create_mock_trigger_rgba(self):
        """Test MockTrigger with RGBA color."""
        trigger = MockTrigger(pixel_number=10, pixel_color=(255, 0, 0, 128))
        assert trigger.pixel_number == 10
        assert trigger.pixel_color == (255, 0, 0, 128)


class TestStaticCanvasInterface:
    """Test StaticCanvasInterface methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def canvas_sprite(self, mocker):
        """Create a mock canvas sprite for testing.

        Returns:
            A mock canvas sprite with pixel data.
        """
        sprite = mocker.Mock()
        sprite.pixels = [MAGENTA] * PIXEL_COUNT
        sprite.pixels_across = CANVAS_SIZE
        sprite.pixels_tall = CANVAS_SIZE
        sprite.dirty = 0
        sprite.dirty_pixels = [False] * PIXEL_COUNT
        sprite.image = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        return sprite

    def test_get_pixel_data(self, canvas_sprite):
        """Test get_pixel_data returns a copy of pixels."""
        interface = StaticCanvasInterface(canvas_sprite)
        result = interface.get_pixel_data()
        assert result == canvas_sprite.pixels
        # Should be a copy, not the same list
        assert result is not canvas_sprite.pixels

    def test_set_pixel_data(self, canvas_sprite):
        """Test set_pixel_data updates pixels and marks dirty."""
        interface = StaticCanvasInterface(canvas_sprite)
        new_pixels = [RED] * PIXEL_COUNT
        interface.set_pixel_data(new_pixels)
        assert canvas_sprite.pixels == new_pixels
        assert canvas_sprite.dirty == 1
        assert all(canvas_sprite.dirty_pixels)

    def test_get_dimensions(self, canvas_sprite):
        """Test get_dimensions returns width and height."""
        interface = StaticCanvasInterface(canvas_sprite)
        assert interface.get_dimensions() == (CANVAS_SIZE, CANVAS_SIZE)

    def test_get_pixel_at_valid(self, canvas_sprite):
        """Test get_pixel_at returns pixel at valid coordinates."""
        canvas_sprite.pixels[0] = RED
        interface = StaticCanvasInterface(canvas_sprite)
        result = interface.get_pixel_at(0, 0)
        assert result == RED

    def test_get_pixel_at_rgb_converts_to_rgba(self, canvas_sprite):
        """Test get_pixel_at converts RGB pixel to RGBA."""
        canvas_sprite.pixels[0] = RED_RGB
        interface = StaticCanvasInterface(canvas_sprite)
        result = interface.get_pixel_at(0, 0)
        assert result == (255, 0, 0, 255)

    def test_get_pixel_at_out_of_bounds(self, canvas_sprite):
        """Test get_pixel_at returns magenta for out-of-bounds coordinates."""
        interface = StaticCanvasInterface(canvas_sprite)
        result = interface.get_pixel_at(-1, -1)
        assert result == MAGENTA

    def test_get_pixel_at_out_of_bounds_high(self, canvas_sprite):
        """Test get_pixel_at returns magenta for too-large coordinates."""
        interface = StaticCanvasInterface(canvas_sprite)
        result = interface.get_pixel_at(CANVAS_SIZE, CANVAS_SIZE)
        assert result == MAGENTA

    def test_set_pixel_at_valid(self, canvas_sprite):
        """Test set_pixel_at updates pixel at valid coordinates."""
        interface = StaticCanvasInterface(canvas_sprite)
        interface.set_pixel_at(0, 0, RED)
        assert canvas_sprite.pixels[0] == RED
        assert canvas_sprite.dirty_pixels[0] is True
        assert canvas_sprite.dirty == 1

    def test_set_pixel_at_out_of_bounds(self, canvas_sprite):
        """Test set_pixel_at ignores out-of-bounds coordinates."""
        interface = StaticCanvasInterface(canvas_sprite)
        original = canvas_sprite.pixels.copy()
        interface.set_pixel_at(-1, -1, RED)
        assert canvas_sprite.pixels == original

    def test_get_surface(self, canvas_sprite):
        """Test get_surface returns the sprite's image."""
        interface = StaticCanvasInterface(canvas_sprite)
        result = interface.get_surface()
        assert result is canvas_sprite.image

    def test_mark_dirty(self, canvas_sprite):
        """Test mark_dirty sets dirty flag."""
        interface = StaticCanvasInterface(canvas_sprite)
        interface.mark_dirty()
        assert canvas_sprite.dirty == 1


class TestStaticSpriteSerializer:
    """Test StaticSpriteSerializer."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_save_delegates_to_sprite(self, mocker):
        """Test save delegates to the sprite's save method."""
        sprite = mocker.Mock()
        StaticSpriteSerializer.save(sprite, 'test.toml', 'toml')
        sprite.save.assert_called_once_with('test.toml', 'toml')

    def test_load_returns_none(self):
        """Test load returns None (handled by CanvasSprite)."""
        serializer = StaticSpriteSerializer()
        result = serializer.load('test.toml')
        assert result is None


class TestAnimatedCanvasInterfaceInit:
    """Test AnimatedCanvasInterface initialization."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_init_with_animated_sprite_using_animation_order(self, mocker):
        """Test initialization when canvas sprite has animated_sprite with _animation_order."""
        canvas_sprite = mocker.Mock()
        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        animated_sprite.add_animation('idle', [SpriteFrame(surface)])
        animated_sprite._animation_order = ['idle']
        canvas_sprite.animated_sprite = animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        assert interface.current_animation == 'idle'
        assert interface.current_frame == 0

    def test_init_with_animated_sprite_no_order(self, mocker):
        """Test initialization when canvas sprite has animated_sprite without _animation_order."""
        canvas_sprite = mocker.Mock()
        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        animated_sprite.add_animation('walk', [SpriteFrame(surface)])
        # Remove _animation_order if it exists
        if hasattr(animated_sprite, '_animation_order'):
            del animated_sprite._animation_order
        canvas_sprite.animated_sprite = animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        assert interface.current_animation == 'walk'

    def test_init_with_no_animated_sprite(self, mocker):
        """Test initialization when canvas sprite has no animated_sprite."""
        canvas_sprite = mocker.Mock(spec=[])
        interface = AnimatedCanvasInterface(canvas_sprite)
        assert not interface.current_animation

    def test_init_with_empty_animations(self, mocker):
        """Test initialization when animated sprite has no animations."""
        canvas_sprite = mocker.Mock()
        animated_sprite = AnimatedSprite()
        canvas_sprite.animated_sprite = animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        assert not interface.current_animation


class TestAnimatedCanvasInterfacePixelOps:
    """Test AnimatedCanvasInterface pixel operations."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def animated_interface(self, mocker):
        """Create an AnimatedCanvasInterface with test data.

        Returns:
            An AnimatedCanvasInterface instance.
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.image = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))

        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        frame.set_pixel_data([MAGENTA] * PIXEL_COUNT)
        animated_sprite.add_animation('idle', [frame])
        animated_sprite.set_animation('idle')

        canvas_sprite.animated_sprite = animated_sprite
        canvas_sprite.current_animation = 'idle'
        canvas_sprite.current_frame = 0

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface.current_animation = 'idle'
        interface.current_frame = 0
        return interface

    def test_get_pixel_data_from_animated_sprite(self, animated_interface):
        """Test get_pixel_data retrieves from animated sprite frame."""
        result = animated_interface.get_pixel_data()
        assert len(result) == PIXEL_COUNT
        # All pixels should be RGBA
        assert all(len(p) == 4 for p in result)

    def test_get_pixel_data_ensures_rgba(self, mocker):
        """Test get_pixel_data converts RGB pixels to RGBA."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels = [RED_RGB] * PIXEL_COUNT
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        # Simulate no animated_sprite attribute
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface.get_pixel_data()
        assert all(len(p) == 4 for p in result)
        assert result[0] == (255, 0, 0, 255)

    def test_set_pixel_data_on_animated_sprite(self, animated_interface):
        """Test set_pixel_data updates animated sprite frame."""
        new_pixels = [RED] * PIXEL_COUNT
        animated_interface.set_pixel_data(new_pixels)
        # Verify the frame was updated
        frame = animated_interface.canvas_sprite.animated_sprite._animations['idle'][0]
        stored_pixels = frame.get_pixel_data()
        assert stored_pixels[0] == RED

    def test_set_pixel_data_on_static_sprite(self, mocker):
        """Test set_pixel_data falls back to static sprite."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        new_pixels = [RED] * PIXEL_COUNT
        interface.set_pixel_data(new_pixels)
        assert canvas_sprite.pixels == new_pixels
        assert canvas_sprite.dirty == 1

    def test_get_dimensions(self, animated_interface):
        """Test get_dimensions returns canvas dimensions."""
        assert animated_interface.get_dimensions() == (CANVAS_SIZE, CANVAS_SIZE)

    def test_get_surface(self, animated_interface):
        """Test get_surface returns canvas image."""
        result = animated_interface.get_surface()
        assert result is animated_interface.canvas_sprite.image

    def test_mark_dirty(self, animated_interface):
        """Test mark_dirty sets canvas dirty flag."""
        animated_interface.mark_dirty()
        assert animated_interface.canvas_sprite.dirty == 1


class TestAnimatedCanvasInterfaceSetPixelAt:
    """Test AnimatedCanvasInterface set_pixel_at with various scenarios."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_set_pixel_at_out_of_bounds(self, mocker):
        """Test set_pixel_at ignores out-of-bounds coordinates."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        # Should not raise or modify anything
        interface.set_pixel_at(-1, -1, RED)

    def test_set_pixel_at_skip_drag_ops(self, mocker):
        """Test set_pixel_at with skip_drag_ops fast path."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface.set_pixel_at(0, 0, RED, skip_drag_ops=True)
        assert canvas_sprite.pixels[0] == RED
        assert canvas_sprite.dirty == 1


class TestAnimatedCanvasInterfaceShouldTrackColorChange:
    """Test AnimatedCanvasInterface _should_track_color_change."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_same_color_not_tracked(self, mocker):
        """Test same color change is not tracked."""
        canvas_sprite = mocker.Mock()
        del canvas_sprite.animated_sprite
        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._should_track_color_change(RED, RED, controller_drag_active=False)
        assert result is False

    def test_controller_drag_active_not_tracked(self, mocker):
        """Test color change during controller drag is not tracked."""
        canvas_sprite = mocker.Mock()
        del canvas_sprite.animated_sprite
        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._should_track_color_change(RED, GREEN, controller_drag_active=True)
        assert result is False

    def test_no_parent_scene_not_tracked(self, mocker):
        """Test color change without parent scene is not tracked."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = None
        del canvas_sprite.animated_sprite
        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._should_track_color_change(RED, GREEN, controller_drag_active=False)
        assert result is False


class TestAnimatedCanvasInterfaceIsControllerDragActive:
    """Test AnimatedCanvasInterface _is_controller_drag_active."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_parent_scene(self, mocker):
        """Test returns False when no parent scene."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = None
        del canvas_sprite.animated_sprite
        interface = AnimatedCanvasInterface(canvas_sprite)
        assert interface._is_controller_drag_active() is False

    def test_no_controller_drags(self, mocker):
        """Test returns False when no controller_drags attribute."""
        canvas_sprite = mocker.Mock()
        del canvas_sprite.animated_sprite
        del canvas_sprite.parent_scene.controller_drags
        interface = AnimatedCanvasInterface(canvas_sprite)
        assert interface._is_controller_drag_active() is False

    def test_active_drag_with_pixels(self, mocker):
        """Test returns True when controller has active drag with pixels."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene.controller_drags = {
            0: {'active': True, 'pixels_drawn': [(1, 2, RED, GREEN)]}
        }
        del canvas_sprite.animated_sprite
        interface = AnimatedCanvasInterface(canvas_sprite)
        assert interface._is_controller_drag_active() is True

    def test_active_drag_without_pixels(self, mocker):
        """Test returns False when controller has active drag without pixels."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene.controller_drags = {0: {'active': True, 'pixels_drawn': []}}
        del canvas_sprite.animated_sprite
        interface = AnimatedCanvasInterface(canvas_sprite)
        assert interface._is_controller_drag_active() is False


class TestAnimatedCanvasInterfaceSetCurrentFrame:
    """Test AnimatedCanvasInterface set_current_frame and get_current_frame."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_set_current_frame(self, mocker):
        """Test set_current_frame updates animation and frame."""
        canvas_sprite = mocker.Mock(spec=[])
        interface = AnimatedCanvasInterface(canvas_sprite)
        interface.set_current_frame('walk', 2)
        assert interface.current_animation == 'walk'
        assert interface.current_frame == 2

    def test_get_current_frame(self, mocker):
        """Test get_current_frame returns tuple of animation and frame."""
        canvas_sprite = mocker.Mock(spec=[])
        interface = AnimatedCanvasInterface(canvas_sprite)
        interface.current_animation = 'idle'
        interface.current_frame = 3
        result = interface.get_current_frame()
        assert result == ('idle', 3)


class TestAnimatedSpriteSerializer:
    """Test AnimatedSpriteSerializer."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_save_delegates_to_sprite(self, mocker):
        """Test save delegates to the sprite's save method."""
        sprite = mocker.Mock()
        AnimatedSpriteSerializer.save(sprite, 'test.toml', 'toml')
        sprite.save.assert_called_once_with('test.toml', 'toml')

    def test_load_returns_none(self):
        """Test load returns None (handled by CanvasSprite)."""
        serializer = AnimatedSpriteSerializer()
        result = serializer.load('test.toml')
        assert result is None
