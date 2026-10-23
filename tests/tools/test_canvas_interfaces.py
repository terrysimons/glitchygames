"""Tests for canvas interface functionality, coverage, and edge cases."""

import hashlib
import sys
from types import SimpleNamespace
from typing import cast

import pygame
import pytest

from glitchygames.bitmappy import onion_skinning
from glitchygames.bitmappy.canvas_interfaces import (
    AnimatedCanvasInterface,
    AnimatedCanvasRenderer,
    AnimatedSpriteSerializer,
    MockPixelEvent,
    MockTrigger,
    StaticCanvasInterface,
    StaticSpriteSerializer,
)
from glitchygames.bitmappy.controllers.event_handler import ControllerEventHandler
from glitchygames.bitmappy.editor import AnimatedCanvasSprite
from glitchygames.sprites.animated import (
    AnimatedSprite,
    SpriteFrame,
)

# Constants for test values - large canvas (8x8)
LARGE_CANVAS_SIZE = 8
LARGE_CANVAS_PIXEL_COUNT = 64  # 8x8 = 64 pixels
PIXEL_SIZE = 16

# Constants for test values - small canvas (4x4)
CANVAS_SIZE = 4
SMALL_CANVAS_SIZE = 4
CANVAS_PIXEL_COUNT = LARGE_CANVAS_PIXEL_COUNT
SMALL_CANVAS_PIXEL_COUNT = 16  # 4x4 = 16 pixels
PIXEL_COUNT = 16  # 4x4 = 16 pixels

# Color constants
MAGENTA = (255, 0, 255, 255)
RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
RED_RGB = (255, 0, 0)
GREEN_RGB = (0, 255, 0)
BLUE_RGB = (0, 0, 255)
WHITE_RGB = (255, 255, 255)
BORDER_GRAY_RGB = (64, 64, 64)


def _rgb_at(surface, x, y):
    """Read the RGB colour of one surface pixel, ignoring alpha and the pixel format.

    Returns:
        tuple[int, int, int]: The red, green and blue components.

    """
    return tuple(surface.get_at((x, y)))[:3]


def _every_pixel_rgb(surface):
    """Collect the distinct RGB colours on a surface, read in bulk.

    Returns:
        set[tuple[int, int, int]]: Every distinct RGB colour on the surface.

    """
    rgb_rows = pygame.surfarray.array3d(surface).reshape(-1, 3)
    return {tuple(int(component) for component in row) for row in rgb_rows}


def _static_canvas_stand_in(*, pixels, pixel_size, image, **attributes):
    """Build the attributes AnimatedCanvasRenderer reads from a canvas without an animated sprite.

    The renderer draws into ``image``, a real surface, so a test reads what was drawn.

    Returns:
        SimpleNamespace: The canvas stand-in.

    """
    canvas_attributes = {
        'pixels_across': CANVAS_SIZE,
        'pixels_tall': len(pixels) // CANVAS_SIZE,
        'pixels': pixels,
        'pixel_width': pixel_size,
        'pixel_height': pixel_size,
        'border_thickness': 0,
        'background_color': (0, 0, 0),
        'image': image,
        'hovered_pixel': None,
        'is_hovered': False,
        'parent_scene': None,
    }
    canvas_attributes.update(attributes)
    return SimpleNamespace(**canvas_attributes)


class TestAnimatedCanvasInterfaces:
    """Test suite for animated canvas interface functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up test fixtures using centralized mocks."""
        self._mocker = mocker

        # Create a test animated sprite
        self.animated_sprite = AnimatedSprite()

        # Create a SpriteFrame with pixel data
        surface = pygame.Surface((8, 8))
        frame = SpriteFrame(surface)
        # Set pixel data for the frame
        pixel_data: list[tuple[int, ...]] = [
            (255, 0, 0) if i % 2 == 0 else (0, 255, 0) for i in range(64)
        ]  # Red/Green pattern
        frame.set_pixel_data(pixel_data)

        # Add a simple animation with the SpriteFrame
        self.animated_sprite.add_animation('idle', [frame])

        # Create a test animated canvas
        self.canvas = AnimatedCanvasSprite(
            animated_sprite=self.animated_sprite,
            name='Test Animated Canvas',
            x=0,
            y=0,
            pixels_across=8,
            pixels_tall=8,
            pixel_width=16,
            pixel_height=16,
        )

    def test_animated_canvas_interface_creation(self):
        """Test that animated canvas interface is created correctly."""
        interface = self.canvas.get_canvas_interface()
        assert isinstance(interface, AnimatedCanvasInterface)

    def test_animated_canvas_interface_dimensions(self):
        """Test animated canvas interface dimension methods."""
        interface = self.canvas.get_canvas_interface()

        # Test getting dimensions
        width, height = interface.get_dimensions()
        assert width == LARGE_CANVAS_SIZE
        assert height == LARGE_CANVAS_SIZE

    def test_animated_canvas_interface_pixel_operations(self):
        """Test animated canvas interface pixel manipulation."""
        interface = self.canvas.get_canvas_interface()

        # Test setting and getting individual pixels
        interface.set_pixel_at(0, 0, (255, 0, 0))  # Red pixel
        interface.set_pixel_at(1, 1, (0, 255, 0))  # Green pixel

        red_pixel = interface.get_pixel_at(0, 0)
        green_pixel = interface.get_pixel_at(1, 1)

        assert red_pixel == (255, 0, 0, 255)
        assert green_pixel == (0, 255, 0, 255)

    def test_animated_sprite_serializer_creation(self):
        """Test that animated sprite serializer is created correctly."""
        serializer = self.canvas.get_sprite_serializer()
        assert isinstance(serializer, AnimatedSpriteSerializer)

    def test_animated_canvas_renderer_creation(self):
        """Test that animated canvas renderer is created correctly."""
        renderer = self.canvas.get_canvas_renderer()
        assert isinstance(renderer, AnimatedCanvasRenderer)

    def test_animated_canvas_renderer_pixel_size(self):
        """Test animated canvas renderer pixel size method."""
        renderer = self.canvas.get_canvas_renderer()
        pixel_width, pixel_height = renderer.get_pixel_size()

        assert pixel_width == PIXEL_SIZE
        assert pixel_height == PIXEL_SIZE

    def test_animated_canvas_renderer_rendering(self):
        """Test animated canvas renderer rendering methods."""
        renderer = self.canvas.get_canvas_renderer()

        # Test rendering
        surface = renderer.render(self.canvas)
        assert surface.get_size() == (128, 128)  # 8*16 x 8*16

        # The frame's red/green pattern is drawn, one 16x16 cell per pixel
        assert _rgb_at(surface, 8, 8) == RED_RGB
        assert _rgb_at(surface, 24, 8) == GREEN_RGB
        assert _rgb_at(surface, 8, 24) == RED_RGB

        # Test force redraw
        redraw_surface = renderer.force_redraw(self.canvas)
        assert redraw_surface.get_size() == (128, 128)
        assert _rgb_at(redraw_surface, 120, 120) == GREEN_RGB

    def test_animated_canvas_functionality(self):
        """Test that AnimatedCanvasSprite functionality works."""
        # Test that animated canvas attributes exist
        assert hasattr(self.canvas, 'animated_sprite')
        assert hasattr(self.canvas, 'current_animation')
        assert hasattr(self.canvas, 'current_frame')
        assert hasattr(self.canvas, 'pixels')
        assert hasattr(self.canvas, 'pixels_across')
        assert hasattr(self.canvas, 'pixels_tall')

        # Test that animated canvas methods exist
        assert hasattr(self.canvas, 'force_redraw')
        assert hasattr(self.canvas, 'show_frame')
        assert hasattr(self.canvas, 'update_animation')

        # Test setting pixels
        self.canvas.pixels[0] = (255, 0, 0)  # Red pixel
        self.canvas.pixels[1] = (0, 255, 0)  # Green pixel

        # Test that the interface reflects the changes
        interface = self.canvas.get_canvas_interface()
        red_pixel = interface.get_pixel_at(0, 0)
        green_pixel = interface.get_pixel_at(1, 0)

        assert red_pixel == (255, 0, 0, 255)
        assert green_pixel == (0, 255, 0, 255)

    def test_interface_integration(self):
        """Test that all animated interfaces work together correctly."""
        # Get all interface components
        interface = self.canvas.get_canvas_interface()
        renderer = self.canvas.get_canvas_renderer()

        # Test that they all work together
        interface.set_pixel_at(2, 2, (0, 0, 255))  # Blue pixel
        surface = renderer.render(self.canvas)

        # Verify the pixel was set correctly, and drawn in its 16x16 cell
        blue_pixel = interface.get_pixel_at(2, 2)
        assert blue_pixel == (0, 0, 255, 255)
        assert _rgb_at(surface, 2 * 16 + 8, 2 * 16 + 8) == BLUE_RGB

        # Verify the surface was rendered
        assert surface is not None
        assert surface.get_size() == (128, 128)


class TestAnimatedCanvasInterfaceEdgeCases:
    """Test edge cases for animated canvas interfaces."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up test fixtures using centralized mocks."""
        self._mocker = mocker

        # Create a test animated sprite
        self.animated_sprite = AnimatedSprite()

        # Create a SpriteFrame with pixel data
        surface = pygame.Surface((4, 4))
        frame = SpriteFrame(surface)
        # Set pixel data for the frame
        pixel_data: list[tuple[int, ...]] = [
            (255, 0, 0) if i % 2 == 0 else (0, 255, 0) for i in range(16)
        ]  # Red/Green pattern
        frame.set_pixel_data(pixel_data)

        # Add a simple animation with the SpriteFrame
        self.animated_sprite.add_animation('idle', [frame])

        self.canvas = AnimatedCanvasSprite(
            animated_sprite=self.animated_sprite,
            name='Test Animated Canvas',
            x=0,
            y=0,
            pixels_across=4,
            pixels_tall=4,
            pixel_width=16,
            pixel_height=16,
        )

    def test_out_of_bounds_pixel_access(self):
        """Test accessing pixels outside canvas bounds."""
        interface = self.canvas.get_canvas_interface()

        # Test out-of-bounds access
        out_of_bounds_pixel = interface.get_pixel_at(10, 10)
        assert out_of_bounds_pixel == (255, 0, 255, 255)  # Should return magenta

    def test_out_of_bounds_pixel_setting(self):
        """Test setting pixels outside canvas bounds."""
        interface = self.canvas.get_canvas_interface()

        # Test setting out-of-bounds pixel (should not crash)
        interface.set_pixel_at(10, 10, (255, 0, 0))

        # Verify the canvas wasn't corrupted
        assert len(self.canvas.pixels) == SMALL_CANVAS_PIXEL_COUNT  # 4x4 = 16 pixels


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))


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

    def test_save_delegates_to_sprite(self, mocker):
        """Test save delegates to the sprite's save method."""
        sprite = mocker.Mock()
        serializer = StaticSpriteSerializer()
        serializer.save(sprite, 'test.toml', 'toml')
        sprite.save.assert_called_once_with('test.toml', 'toml')

    def test_load_returns_none(self):
        """Test load returns None (handled by CanvasSprite)."""
        serializer = StaticSpriteSerializer()
        result = serializer.load('test.toml')
        assert result is None


class TestAnimatedCanvasInterfaceInit:
    """Test AnimatedCanvasInterface initialization."""

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
        # Never loaded from a file: its animation order is its animations' order
        assert not animated_sprite.has_own_animation_order
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
        magenta_pixels = cast('list[tuple[int, ...]]', [MAGENTA] * PIXEL_COUNT)
        frame.set_pixel_data(magenta_pixels)
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

    def test_tracked_when_parent_has_tracker(self, mocker):
        """Test color change is tracked when parent has canvas_operation_tracker."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = mocker.Mock()
        canvas_sprite.parent_scene.canvas_operation_tracker = mocker.Mock()
        canvas_sprite.parent_scene._applying_undo_redo = False
        del canvas_sprite.animated_sprite
        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._should_track_color_change(RED, GREEN, controller_drag_active=False)
        assert result is True

    def test_not_tracked_during_undo_redo(self, mocker):
        """Test color change is not tracked when undo/redo is being applied."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = mocker.Mock()
        canvas_sprite.parent_scene.canvas_operation_tracker = mocker.Mock()
        canvas_sprite.parent_scene._applying_undo_redo = True
        del canvas_sprite.animated_sprite
        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._should_track_color_change(RED, GREEN, controller_drag_active=False)
        assert result is False


class TestAnimatedCanvasInterfaceIsControllerDragActive:
    """Test AnimatedCanvasInterface _is_controller_drag_active."""

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
            0: {'active': True, 'pixels_drawn': [(1, 2, RED, GREEN)]},
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

    def test_save_delegates_to_sprite(self, mocker):
        """Test save delegates to the sprite's save method."""
        sprite = mocker.Mock()
        serializer = AnimatedSpriteSerializer()
        serializer.save(sprite, 'test.toml', 'toml')
        sprite.save.assert_called_once_with('test.toml', 'toml')

    def test_load_returns_none(self):
        """Test load returns None (handled by CanvasSprite)."""
        serializer = AnimatedSpriteSerializer()
        result = serializer.load('test.toml')
        assert result is None


class TestCollectPixelChangeDictionaryTrimming:
    """Test _collect_pixel_change dictionary trimming when exceeding max entries."""

    def test_collect_pixel_change_trims_dict_beyond_max(self, mocker):
        """Test that _collect_pixel_change trims dict when exceeding 2000 entries."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 100
        canvas_sprite.pixels_tall = 100
        canvas_sprite.pixels = [MAGENTA] * 10000
        canvas_sprite.dirty_pixels = [False] * 10000
        canvas_sprite.dirty = 0
        del canvas_sprite.animated_sprite

        parent_scene = mocker.Mock()
        # Pre-populate with 2001 unique pixel changes to trigger trimming
        parent_scene.current_pixel_changes = []
        parent_scene.current_pixel_changes_dict = {
            (i, 0): (i, 0, MAGENTA, RED) for i in range(2001)
        }
        parent_scene._pixel_changes_list_dirty = True
        canvas_sprite.parent_scene = parent_scene

        interface = AnimatedCanvasInterface(canvas_sprite)

        # Call _collect_pixel_change - dict already over 2000, should trigger trimming
        interface._collect_pixel_change(50, 50, MAGENTA, GREEN)

        # Should be trimmed to around 1500 entries (plus the new one)
        dict_size = len(parent_scene.current_pixel_changes_dict)
        assert dict_size <= 1501

    def test_collect_pixel_change_updates_existing_entry(self, mocker):
        """Test that _collect_pixel_change updates existing entry keeping original old_color."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        del canvas_sprite.animated_sprite

        parent_scene = mocker.Mock()
        parent_scene.current_pixel_changes = []
        parent_scene.current_pixel_changes_dict = {
            (1, 1): (1, 1, MAGENTA, RED),  # Existing entry
        }
        parent_scene._pixel_changes_list_dirty = True
        canvas_sprite.parent_scene = parent_scene

        interface = AnimatedCanvasInterface(canvas_sprite)

        # Update same pixel with new color
        interface._collect_pixel_change(1, 1, RED, GREEN)

        # Should keep original old_color (MAGENTA), but update new_color to GREEN
        assert parent_scene.current_pixel_changes_dict[1, 1] == (1, 1, MAGENTA, GREEN)

    def test_collect_pixel_change_initializes_structures(self, mocker):
        """Test _collect_pixel_change creates tracking structures if missing."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        del canvas_sprite.animated_sprite

        parent_scene = mocker.Mock(spec=['some_other_attr'])
        canvas_sprite.parent_scene = parent_scene

        interface = AnimatedCanvasInterface(canvas_sprite)

        interface._collect_pixel_change(0, 0, MAGENTA, RED)

        assert hasattr(parent_scene, 'current_pixel_changes')
        assert hasattr(parent_scene, 'current_pixel_changes_dict')
        assert (0, 0) in parent_scene.current_pixel_changes_dict

    def test_collect_pixel_change_starts_timer_on_first_pixel(self, mocker):
        """Test _collect_pixel_change starts timer on first pixel change."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        del canvas_sprite.animated_sprite

        parent_scene = mocker.Mock(spec=['some_other_attr'])
        canvas_sprite.parent_scene = parent_scene

        interface = AnimatedCanvasInterface(canvas_sprite)

        interface._collect_pixel_change(2, 3, MAGENTA, RED)

        assert hasattr(parent_scene, 'pixel_change_timer')


class TestGetCurrentFramePixelsDefaultHandling:
    """Test AnimatedCanvasRenderer._get_current_frame_pixels default frame handling."""

    def test_get_current_frame_pixels_with_get_pixel_data(self, mocker):
        """Test _get_current_frame_pixels uses get_pixel_data when available."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.image = pygame.Surface((CANVAS_SIZE * 10, CANVAS_SIZE * 10))
        canvas_sprite.pixel_width = 10
        canvas_sprite.pixel_height = 10

        frame = mocker.Mock()
        frame.get_pixel_data.return_value = [RED] * PIXEL_COUNT

        frames = {'idle': [frame]}

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_current_frame_pixels(frames, 'idle', 0)

        assert result == [RED] * PIXEL_COUNT
        frame.get_pixel_data.assert_called_once()

    def test_get_current_frame_pixels_fallback_to_pixels_attr(self, mocker):
        """Test _get_current_frame_pixels falls back to pixels attribute."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.image = pygame.Surface((CANVAS_SIZE * 10, CANVAS_SIZE * 10))
        canvas_sprite.pixel_width = 10
        canvas_sprite.pixel_height = 10

        # Frame without get_pixel_data but with pixels attribute
        frame = mocker.Mock(spec=['pixels'])
        frame.pixels = [GREEN] * PIXEL_COUNT

        frames = {'idle': [frame]}

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_current_frame_pixels(frames, 'idle', 0)

        assert result == [GREEN] * PIXEL_COUNT

    def test_get_current_frame_pixels_fallback_to_magenta_default(self, mocker):
        """Test _get_current_frame_pixels falls back to magenta when frame has no pixel data."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.image = pygame.Surface((CANVAS_SIZE * 10, CANVAS_SIZE * 10))
        canvas_sprite.pixel_width = 10
        canvas_sprite.pixel_height = 10

        # Frame without get_pixel_data or pixels
        frame = mocker.Mock(spec=[])

        frames = {'idle': [frame]}

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_current_frame_pixels(frames, 'idle', 0)

        assert len(result) == PIXEL_COUNT
        assert result[0] == (255, 0, 255)


class TestHasActiveControllersInCanvasMode:
    """Test AnimatedCanvasRenderer._has_active_controllers_in_canvas_mode."""

    def test_no_parent_scene_returns_false(self, mocker):
        """Test returns False when no parent scene."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = None
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        assert renderer._has_active_controllers_in_canvas_mode() is False

    def test_no_controller_selections_returns_false(self, mocker):
        """Test returns False when parent scene lacks controller_selections."""
        canvas_sprite = mocker.Mock()
        del canvas_sprite.parent_scene.controller_selections
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        assert renderer._has_active_controllers_in_canvas_mode() is False

    def test_controller_in_canvas_mode_within_bounds(self, mocker):
        """Test returns True when controller is in canvas mode within bounds."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        mock_scene = mocker.Mock()
        mock_scene.controller_selections = {0: mocker.Mock()}

        mock_mode = mocker.Mock()
        mock_mode.value = 'canvas'
        mock_scene.mode_switcher.get_controller_mode.return_value = mock_mode

        mock_position = mocker.Mock()
        mock_position.is_valid = True
        mock_position.position = (1, 1)
        mock_scene.mode_switcher.get_controller_position.return_value = mock_position

        canvas_sprite.parent_scene = mock_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        assert renderer._has_active_controllers_in_canvas_mode() is True

    def test_controller_not_in_canvas_mode_returns_false(self, mocker):
        """Test returns False when controller is not in canvas mode."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        mock_scene = mocker.Mock()
        mock_scene.controller_selections = {0: mocker.Mock()}

        mock_mode = mocker.Mock()
        mock_mode.value = 'film_strip'  # Not canvas mode
        mock_scene.mode_switcher.get_controller_mode.return_value = mock_mode

        canvas_sprite.parent_scene = mock_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        assert renderer._has_active_controllers_in_canvas_mode() is False

    def test_controller_position_invalid_returns_false(self, mocker):
        """Test returns False when controller position is not valid."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        mock_scene = mocker.Mock()
        mock_scene.controller_selections = {0: mocker.Mock()}

        mock_mode = mocker.Mock()
        mock_mode.value = 'canvas'
        mock_scene.mode_switcher.get_controller_mode.return_value = mock_mode

        mock_position = mocker.Mock()
        mock_position.is_valid = False
        mock_scene.mode_switcher.get_controller_position.return_value = mock_position

        canvas_sprite.parent_scene = mock_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        assert renderer._has_active_controllers_in_canvas_mode() is False

    def test_controller_position_out_of_bounds_returns_false(self, mocker):
        """Test returns False when controller position is out of canvas bounds."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        mock_scene = mocker.Mock()
        mock_scene.controller_selections = {0: mocker.Mock()}

        mock_mode = mocker.Mock()
        mock_mode.value = 'canvas'
        mock_scene.mode_switcher.get_controller_mode.return_value = mock_mode

        mock_position = mocker.Mock()
        mock_position.is_valid = True
        mock_position.position = (100, 100)  # Out of bounds for 4x4 canvas
        mock_scene.mode_switcher.get_controller_position.return_value = mock_position

        canvas_sprite.parent_scene = mock_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        assert renderer._has_active_controllers_in_canvas_mode() is False


class TestGetControllerIndicatorForPixel:
    """Test AnimatedCanvasRenderer._get_controller_indicator_for_pixel."""

    def test_no_controller_scene_returns_none(self, mocker):
        """Test returns None when no controller scene."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = None
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_indicator_for_pixel(0)
        assert result is None

    def test_controller_on_matching_pixel_returns_color(self, mocker):
        """Test returns controller color when controller is on the matching pixel."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        mock_scene = mocker.Mock()
        mock_scene.controller_selections = {0: mocker.Mock()}

        mock_mode = mocker.Mock()
        mock_mode.value = 'canvas'
        mock_scene.mode_switcher.get_controller_mode.return_value = mock_mode

        mock_position = mocker.Mock()
        mock_position.is_valid = True
        mock_position.position = (1, 0)  # Pixel index = 0*4 + 1 = 1
        mock_scene.mode_switcher.get_controller_position.return_value = mock_position

        mock_controller_info = mocker.Mock()
        mock_controller_info.color = (255, 0, 0)
        mock_scene.controller_handler.find_controller_info.return_value = mock_controller_info

        canvas_sprite.parent_scene = mock_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_indicator_for_pixel(1)  # pixel_index 1

        assert result == (255, 0, 0)
        mock_scene.controller_handler.find_controller_info.assert_called_once_with(0)

    def test_controller_on_different_pixel_returns_none(self, mocker):
        """Test returns None when controller is on a different pixel."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        mock_scene = mocker.Mock()
        mock_scene.controller_selections = {0: mocker.Mock()}

        mock_mode = mocker.Mock()
        mock_mode.value = 'canvas'
        mock_scene.mode_switcher.get_controller_mode.return_value = mock_mode

        mock_position = mocker.Mock()
        mock_position.is_valid = True
        mock_position.position = (0, 0)  # Pixel index = 0
        mock_scene.mode_switcher.get_controller_position.return_value = mock_position

        canvas_sprite.parent_scene = mock_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_indicator_for_pixel(5)  # Different pixel

        assert result is None

    def test_controller_without_controller_handler_returns_none(self, mocker):
        """Test returns None when scene has no controller handler to look controllers up."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        mock_scene = mocker.Mock()
        mock_scene.controller_selections = {0: mocker.Mock()}

        mock_mode = mocker.Mock()
        mock_mode.value = 'canvas'
        mock_scene.mode_switcher.get_controller_mode.return_value = mock_mode

        mock_position = mocker.Mock()
        mock_position.is_valid = True
        mock_position.position = (0, 0)
        mock_scene.mode_switcher.get_controller_position.return_value = mock_position

        del mock_scene.controller_handler

        canvas_sprite.parent_scene = mock_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_indicator_for_pixel(0)

        assert result is None

    def test_controller_info_none_returns_none(self, mocker):
        """Test returns None when controller info is None."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        mock_scene = mocker.Mock()
        mock_scene.controller_selections = {0: mocker.Mock()}

        mock_mode = mocker.Mock()
        mock_mode.value = 'canvas'
        mock_scene.mode_switcher.get_controller_mode.return_value = mock_mode

        mock_position = mocker.Mock()
        mock_position.is_valid = True
        mock_position.position = (0, 0)
        mock_scene.mode_switcher.get_controller_position.return_value = mock_position

        mock_scene.controller_handler.find_controller_info.return_value = None

        canvas_sprite.parent_scene = mock_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_indicator_for_pixel(0)

        assert result is None

    def test_controllers_with_swapped_instance_ids_get_their_own_color(self, mocker):
        """The indicator uses the info found by controller id, not by instance id (#96).

        Controller 0 has SDL instance id 1 and controller 1 has instance id 0, so looking
        controller 0 up by instance id finds controller 1's info and colour.
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        red_controller_info = SimpleNamespace(controller_id=0, instance_id=1, color=(255, 0, 0))
        blue_controller_info = SimpleNamespace(controller_id=1, instance_id=0, color=(0, 0, 255))
        controllers_by_instance_id = {1: red_controller_info, 0: blue_controller_info}
        scene = mocker.Mock()
        scene.controller_selections = {0: mocker.Mock()}
        scene.mode_switcher.get_controller_mode.return_value = SimpleNamespace(value='canvas')
        scene.mode_switcher.get_controller_position.return_value = SimpleNamespace(
            is_valid=True, position=(0, 0)
        )
        scene.multi_controller_manager = SimpleNamespace(
            controllers=controllers_by_instance_id,
            get_controller_info=controllers_by_instance_id.get,
        )
        scene.controller_handler = ControllerEventHandler(scene)
        canvas_sprite.parent_scene = scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)

        assert renderer._get_controller_indicator_for_pixel(0) == (255, 0, 0)


class TestAnimatedCanvasRendererForceRedraw:
    """Test AnimatedCanvasRenderer force_redraw paths."""

    def test_force_redraw_static_fallback(self):
        """Without an animated_sprite, force_redraw draws the static pixels into the image."""
        canvas_sprite = _static_canvas_stand_in(
            pixels=[RED] * PIXEL_COUNT,
            pixel_size=10,
            image=pygame.Surface((40, 40)),
        )

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer.force_redraw(canvas_sprite)

        assert result is canvas_sprite.image
        assert _every_pixel_rgb(result) == {RED_RGB}

    def test_render_draws_like_force_redraw(self):
        """Render draws the canvas exactly as force_redraw does."""
        pixels = [RED, GREEN, BLUE, MAGENTA] * CANVAS_SIZE
        rendered_sprite = _static_canvas_stand_in(
            pixels=pixels,
            pixel_size=10,
            image=pygame.Surface((40, 40)),
        )
        redrawn_sprite = _static_canvas_stand_in(
            pixels=pixels,
            pixel_size=10,
            image=pygame.Surface((40, 40)),
        )

        rendered = AnimatedCanvasRenderer(rendered_sprite).render(rendered_sprite)
        redrawn = AnimatedCanvasRenderer(redrawn_sprite).force_redraw(redrawn_sprite)

        assert rendered is rendered_sprite.image
        assert _rgb_at(rendered, 5, 5) == RED_RGB
        assert _rgb_at(rendered, 15, 5) == GREEN_RGB
        assert (pygame.surfarray.array3d(rendered) == pygame.surfarray.array3d(redrawn)).all()


class TestAnimatedCanvasRendererHelpers:
    """Test AnimatedCanvasRenderer helper methods."""

    def test_get_pixel_size(self, mocker):
        """Test get_pixel_size returns the pixel dimensions."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixel_width = 10
        canvas_sprite.pixel_height = 10

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer.get_pixel_size()
        assert result == (10, 10)

    def test_get_controller_scene_with_no_parent(self, mocker):
        """Test _get_controller_scene returns None when no parent scene."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = None

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_scene()
        assert result is None

    def test_get_controller_scene_with_missing_attrs(self, mocker):
        """Test _get_controller_scene returns None when scene lacks required attrs."""
        canvas_sprite = mocker.Mock()
        del canvas_sprite.parent_scene.controller_selections

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_scene()
        assert result is None

    def test_get_controller_scene_returns_scene(self, mocker):
        """Test _get_controller_scene returns scene when it has required attrs."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene.controller_selections = {}
        canvas_sprite.parent_scene.mode_switcher = mocker.Mock()

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_scene()
        assert result is canvas_sprite.parent_scene

    def test_get_inverse_color(self, mocker):
        """Test _get_inverse_color returns the inverted RGB values."""
        canvas_sprite = mocker.Mock()

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_inverse_color((255, 0, 128))
        assert result == (0, 255, 127)

    def test_get_pixel_color_at_position_valid(self, mocker):
        """Test _get_pixel_color_at_position returns correct pixel color."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [RED_RGB] * PIXEL_COUNT
        canvas_sprite.pixels[5] = GREEN_RGB

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_pixel_color_at_position(1, 1)  # pixel_index = 1*4 + 1 = 5
        assert result == GREEN_RGB

    def test_get_pixel_color_at_position_out_of_bounds(self, mocker):
        """Test _get_pixel_color_at_position returns black for out-of-bounds."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [RED_RGB] * PIXEL_COUNT

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_pixel_color_at_position(100, 100)
        assert result == (0, 0, 0)

    def test_draw_pixel_cell_rgba(self):
        """Test _draw_pixel_cell draws an RGBA pixel correctly."""
        image = pygame.Surface((40, 40), pygame.SRCALPHA)

        AnimatedCanvasRenderer._draw_pixel_cell(image, (255, 0, 0, 128), (10, 0, 10, 10))

        # The RGBA colour is written as is (alpha included) over the pixel's 10x10 cell only
        assert tuple(image.get_at((10, 0))) == (255, 0, 0, 128)
        assert tuple(image.get_at((19, 9))) == (255, 0, 0, 128)
        assert tuple(image.get_at((9, 0))) == (0, 0, 0, 0)
        assert tuple(image.get_at((20, 0))) == (0, 0, 0, 0)
        assert tuple(image.get_at((10, 10))) == (0, 0, 0, 0)

    def test_draw_pixel_cell_rgb(self):
        """Test _draw_pixel_cell converts RGB to RGBA and draws."""
        image = pygame.Surface((40, 40), pygame.SRCALPHA)

        AnimatedCanvasRenderer._draw_pixel_cell(image, (255, 0, 0), (0, 10, 10, 10))

        # An RGB colour is drawn fully opaque
        assert tuple(image.get_at((0, 10))) == (255, 0, 0, 255)
        assert tuple(image.get_at((9, 19))) == (255, 0, 0, 255)
        assert tuple(image.get_at((0, 9))) == (0, 0, 0, 0)
        assert tuple(image.get_at((10, 10))) == (0, 0, 0, 0)

    def test_get_frame_pixel_data_with_get_pixel_data(self, mocker):
        """Test _get_frame_pixel_data uses get_pixel_data when available."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        frame = mocker.Mock()
        frame.get_pixel_data.return_value = [RED] * PIXEL_COUNT

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_frame_pixel_data(frame)
        assert result == [RED] * PIXEL_COUNT

    def test_get_frame_pixel_data_fallback_to_pixels_attr(self, mocker):
        """Test _get_frame_pixel_data falls back to pixels attribute."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        frame = mocker.Mock(spec=['pixels'])
        frame.pixels = [GREEN] * PIXEL_COUNT

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_frame_pixel_data(frame)
        assert result == [GREEN] * PIXEL_COUNT

    def test_get_frame_pixel_data_fallback_to_magenta(self, mocker):
        """Test _get_frame_pixel_data falls back to magenta fill when no data available."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE

        frame = mocker.Mock(spec=[])

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_frame_pixel_data(frame)
        assert len(result) == PIXEL_COUNT
        assert result[0] == (255, 0, 255)


def _scene_with_canvas_controller(*, position, color):
    """Build a scene with one controller in canvas mode at ``position``, drawn in ``color``.

    Returns:
        SimpleNamespace: The scene stand-in AnimatedCanvasRenderer reads controllers from.

    """
    controller_info = SimpleNamespace(controller_id=0, color=color)
    return SimpleNamespace(
        controller_selections={0: SimpleNamespace()},
        mode_switcher=SimpleNamespace(
            get_controller_mode=lambda controller_id: SimpleNamespace(value='canvas'),
            get_controller_position=lambda controller_id: SimpleNamespace(
                is_valid=True,
                position=position,
            ),
        ),
        controller_handler=SimpleNamespace(
            find_controller_info=lambda controller_id: controller_info,
        ),
        selected_frame_visible=True,
    )


def _two_by_two_canvas_stand_in(*, pixels, parent_scene=None, **attributes):
    """Build a 2x2 canvas of 8x8 cells drawing into a real transparent 16x16 surface.

    Returns:
        SimpleNamespace: The canvas stand-in.

    """
    canvas_attributes = {
        'pixels_across': 2,
        'pixels_tall': 2,
        'pixel_width': 8,
        'pixel_height': 8,
        'width': 16,
        'height': 16,
        'pixels': pixels,
        'border_thickness': 0,
        'background_color': (0, 0, 0),
        'image': pygame.Surface((16, 16), pygame.SRCALPHA),
        'hovered_pixel': None,
        'is_hovered': False,
        'parent_scene': parent_scene,
    }
    canvas_attributes.update(attributes)
    return SimpleNamespace(**canvas_attributes)


INDICATOR_RED_RGB = (255, 0, 0)
TWO_BY_TWO_PIXELS = [(100, 100, 100), (200, 200, 200), (50, 50, 50), (10, 10, 10)]


class TestCanvasRendererDrawIndicatorsOnly:
    """Test _draw_controller_indicators_only rendering."""

    def test_draw_controller_indicators_only(self):
        """With the frame hidden, only the controller's box is drawn, over its own pixel."""
        canvas_sprite = _two_by_two_canvas_stand_in(
            pixels=TWO_BY_TWO_PIXELS,
            parent_scene=_scene_with_canvas_controller(position=(0, 0), color=INDICATOR_RED_RGB),
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        renderer._draw_controller_indicators_only(
            cast('list[tuple[int, ...]]', TWO_BY_TWO_PIXELS),
        )

        image = canvas_sprite.image
        # Outer 1px box in the controller colour at (1, 1)..(6, 6)
        assert _rgb_at(image, 1, 1) == INDICATOR_RED_RGB
        assert _rgb_at(image, 6, 6) == INDICATOR_RED_RGB
        # Inner box in the inverse of the pixel's colour (100, 100, 100)
        assert _rgb_at(image, 3, 3) == (155, 155, 155)
        # The pixel itself and every other cell stay undrawn (transparent)
        assert image.get_at((0, 0)).a == 0
        assert image.get_at((12, 4)).a == 0
        assert image.get_at((4, 12)).a == 0
        assert image.get_at((12, 12)).a == 0

    def test_controller_past_a_short_frame_is_not_drawn(self):
        """A controller on a pixel the (short) frame does not have draws no box."""
        canvas_sprite = _two_by_two_canvas_stand_in(
            pixels=TWO_BY_TWO_PIXELS,
            parent_scene=_scene_with_canvas_controller(position=(0, 1), color=INDICATOR_RED_RGB),
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        renderer._draw_controller_indicators_only(
            cast('list[tuple[int, ...]]', TWO_BY_TWO_PIXELS[:2]),
        )

        assert _every_pixel_rgb(canvas_sprite.image) == {(0, 0, 0)}
        assert canvas_sprite.image.get_at((1, 9)).a == 0


class TestCanvasRendererVisibleFrameWithControllerIndicator:
    """Test _draw_visible_frame_pixels with a controller indicator."""

    def test_draw_visible_frame_pixels_with_controller_indicator(self):
        """Every pixel is drawn, and the controller's box is drawn over pixel 1 only."""
        canvas_sprite = _two_by_two_canvas_stand_in(
            pixels=TWO_BY_TWO_PIXELS,
            parent_scene=_scene_with_canvas_controller(position=(1, 0), color=(0, 255, 0)),
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        renderer._draw_visible_frame_pixels(cast('list[tuple[int, ...]]', TWO_BY_TWO_PIXELS))

        image = canvas_sprite.image
        # Pixel cells are drawn opaque in their colours (cell corners are outside any box)
        assert tuple(image.get_at((0, 0))) == (100, 100, 100, 255)
        assert tuple(image.get_at((8, 0))) == (200, 200, 200, 255)
        assert tuple(image.get_at((0, 8))) == (50, 50, 50, 255)
        assert tuple(image.get_at((8, 8))) == (10, 10, 10, 255)
        # Pixel 1 (cell at x 8..15) carries the green box and the inverse of (200, 200, 200)
        assert _rgb_at(image, 9, 1) == (0, 255, 0)
        assert _rgb_at(image, 11, 3) == (55, 55, 55)
        # Pixel 0 has no box
        assert _rgb_at(image, 1, 1) == (100, 100, 100)
        assert _rgb_at(image, 3, 3) == (100, 100, 100)

    def test_transparent_pixel_keeps_background_but_shows_the_indicator(self):
        """A magenta (transparent) pixel is not drawn, yet a controller on it still shows."""
        pixels = [(255, 0, 255), (200, 200, 200), (50, 50, 50), (10, 10, 10)]
        canvas_sprite = _two_by_two_canvas_stand_in(
            pixels=pixels,
            parent_scene=_scene_with_canvas_controller(position=(0, 0), color=INDICATOR_RED_RGB),
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        renderer._draw_visible_frame_pixels(cast('list[tuple[int, ...]]', pixels))

        image = canvas_sprite.image
        assert image.get_at((0, 0)).a == 0
        assert _rgb_at(image, 1, 1) == INDICATOR_RED_RGB
        # Inverse of magenta (255, 0, 255)
        assert _rgb_at(image, 3, 3) == (0, 255, 0)


class TestCanvasRendererStaticPixelsWithController:
    """Test _redraw_static_pixels with a controller indicator."""

    def test_static_pixels_with_controller_indicator(self):
        """Static redraw fills the background, draws every pixel, borders and the indicator."""
        canvas_sprite = _two_by_two_canvas_stand_in(
            pixels=TWO_BY_TWO_PIXELS,
            parent_scene=_scene_with_canvas_controller(position=(0, 0), color=INDICATOR_RED_RGB),
            border_thickness=1,
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        renderer._redraw_static_pixels(TWO_BY_TWO_PIXELS)

        image = canvas_sprite.image
        # Each cell's 1px border is grey; the cell inside is the pixel colour
        assert _rgb_at(image, 0, 0) == BORDER_GRAY_RGB
        assert _rgb_at(image, 8, 8) == BORDER_GRAY_RGB
        assert _rgb_at(image, 12, 4) == (200, 200, 200)
        assert _rgb_at(image, 4, 12) == (50, 50, 50)
        assert _rgb_at(image, 12, 12) == (10, 10, 10)
        # Pixel 0 carries the controller's box: red ring, then the inverse of (100, 100, 100)
        assert _rgb_at(image, 1, 1) == INDICATOR_RED_RGB
        assert _rgb_at(image, 3, 3) == (155, 155, 155)


class TestCanvasRendererHoverEffects:
    """Test _draw_hover_effects."""

    def test_draw_hover_effects_with_hovered_pixel(self):
        """A hovered pixel gets a 2px white border around its cell, and nothing else changes."""
        image = pygame.Surface((32, 32))
        image.fill((0, 0, 0))
        canvas_sprite = SimpleNamespace(
            pixels_across=4,
            pixels_tall=4,
            pixel_width=8,
            pixel_height=8,
            image=image,
            hovered_pixel=(1, 2),
            is_hovered=False,
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        renderer._draw_hover_effects()

        # Cell (1, 2) spans x 8..15, y 16..23; the border is its outer 2 pixels
        assert _rgb_at(image, 8, 16) == WHITE_RGB
        assert _rgb_at(image, 9, 17) == WHITE_RGB
        assert _rgb_at(image, 15, 23) == WHITE_RGB
        assert _rgb_at(image, 10, 18) == (0, 0, 0)
        # Outside the cell, and the canvas edge (not hovered), stay black
        assert _rgb_at(image, 7, 16) == (0, 0, 0)
        assert _rgb_at(image, 0, 0) == (0, 0, 0)

    def test_draw_hover_effects_with_hovered_canvas(self):
        """A hovered canvas gets a 1px white border around its whole edge."""
        image = pygame.Surface((32, 32))
        image.fill((0, 0, 0))
        canvas_sprite = SimpleNamespace(
            pixels_across=4,
            pixels_tall=4,
            pixel_width=8,
            pixel_height=8,
            image=image,
            hovered_pixel=None,
            is_hovered=True,
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        renderer._draw_hover_effects()

        assert _rgb_at(image, 0, 0) == WHITE_RGB
        assert _rgb_at(image, 31, 31) == WHITE_RGB
        assert _rgb_at(image, 16, 0) == WHITE_RGB
        assert _rgb_at(image, 1, 1) == (0, 0, 0)


class TestCanvasRendererDrawIndicatorsOnlyPath:
    """Test the _redraw_animated_sprite path when the selected frame is hidden."""

    def test_redraw_animated_sprite_with_hidden_selected_frame(self):
        """With the selected frame hidden, only the magenta background and indicators show."""
        animated_sprite = AnimatedSprite()
        frame = SpriteFrame(pygame.Surface((2, 2)))
        frame.set_pixel_data(cast('list[tuple[int, ...]]', TWO_BY_TWO_PIXELS))
        animated_sprite.add_animation('idle', [frame])
        parent_scene = _scene_with_canvas_controller(position=(1, 1), color=INDICATOR_RED_RGB)
        parent_scene.selected_frame_visible = False
        canvas_sprite = _two_by_two_canvas_stand_in(
            pixels=TWO_BY_TWO_PIXELS,
            parent_scene=parent_scene,
            animated_sprite=animated_sprite,
            current_animation='idle',
            current_frame=0,
            border_thickness=1,
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        result = renderer.force_redraw(canvas_sprite)

        assert result is canvas_sprite.image
        # The frame's pixels and the grid borders are not drawn: magenta shows through
        assert _rgb_at(result, 0, 0) == (255, 0, 255)
        assert _rgb_at(result, 4, 4) == (255, 0, 255)
        assert _rgb_at(result, 12, 4) == (255, 0, 255)
        # The controller's box at pixel (1, 1) is drawn: inverse of (10, 10, 10) inside
        assert _rgb_at(result, 9, 9) == INDICATOR_RED_RGB
        assert _rgb_at(result, 11, 11) == (245, 245, 245)

    def test_redraw_animated_sprite_with_visible_selected_frame(self):
        """With the selected frame visible, its pixels and the grid borders are drawn."""
        animated_sprite = AnimatedSprite()
        frame = SpriteFrame(pygame.Surface((2, 2)))
        frame.set_pixel_data(cast('list[tuple[int, ...]]', TWO_BY_TWO_PIXELS))
        animated_sprite.add_animation('idle', [frame])
        canvas_sprite = _two_by_two_canvas_stand_in(
            pixels=TWO_BY_TWO_PIXELS,
            animated_sprite=animated_sprite,
            current_animation='idle',
            current_frame=0,
            border_thickness=1,
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        result = renderer.force_redraw(canvas_sprite)

        assert _rgb_at(result, 0, 0) == BORDER_GRAY_RGB
        assert _rgb_at(result, 4, 4) == (100, 100, 100)
        assert _rgb_at(result, 12, 4) == (200, 200, 200)
        assert _rgb_at(result, 4, 12) == (50, 50, 50)
        assert _rgb_at(result, 12, 12) == (10, 10, 10)


class TestCanvasRendererOnionSkinRGBA:
    """Test onion skin pixel transparency."""

    def test_render_onion_layer_rgba_pixels(self):
        """Onion pixels combine their own alpha with the onion alpha; magenta is skipped."""
        canvas_sprite = _two_by_two_canvas_stand_in(pixels=TWO_BY_TWO_PIXELS)
        renderer = AnimatedCanvasRenderer(canvas_sprite)
        frame_pixels = cast(
            'list[tuple[int, ...]]',
            [(255, 0, 0, 128), (0, 255, 0), (255, 0, 255), (255, 255, 0, 200)],
        )
        alpha = 128  # 50% onion transparency

        result = renderer._render_onion_frame(frame_pixels, alpha)

        assert result.get_size() == (16, 16)
        # RGBA pixel: 128 * 128 / 255 = 64
        assert tuple(result.get_at((4, 4))) == (255, 0, 0, 64)
        # RGB pixel: takes the onion alpha
        assert tuple(result.get_at((12, 4))) == (0, 255, 0, 128)
        # Magenta pixel: left fully transparent
        assert result.get_at((4, 12)).a == 0
        # 200 * 128 / 255 = 100
        assert tuple(result.get_at((12, 12))) == (255, 255, 0, 100)


class TestCanvasControllerIndicatorForPixelSkipPaths:
    """Test _get_controller_indicator_for_pixel skip paths (lines 1065, 1068, 1074)."""

    def test_controller_not_in_canvas_mode_skipped(self, mocker):
        """Test that controllers not in canvas mode are skipped (line 1065).

        When controller_mode.value != 'canvas', the continue is hit.
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 4
        canvas_sprite.pixels_tall = 4
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8

        parent_scene = mocker.Mock()

        # Controller in film_strip mode, not canvas
        mock_mode = mocker.Mock()
        mock_mode.value = 'film_strip'
        parent_scene.mode_switcher.get_controller_mode.return_value = mock_mode
        parent_scene.controller_selections = {0: mocker.Mock()}

        canvas_sprite.parent_scene = parent_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_indicator_for_pixel(0)

        assert result is None

    def test_controller_position_invalid_skipped(self, mocker):
        """Test that controllers with invalid positions are skipped (line 1068).

        When position.is_valid is False, the continue is hit.
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 4
        canvas_sprite.pixels_tall = 4
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8

        parent_scene = mocker.Mock()

        mock_mode = mocker.Mock()
        mock_mode.value = 'canvas'
        parent_scene.mode_switcher.get_controller_mode.return_value = mock_mode

        mock_position = mocker.Mock()
        mock_position.is_valid = False
        parent_scene.mode_switcher.get_controller_position.return_value = mock_position
        parent_scene.controller_selections = {0: mocker.Mock()}

        canvas_sprite.parent_scene = parent_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_indicator_for_pixel(0)

        assert result is None

    def test_controller_position_out_of_bounds_skipped(self, mocker):
        """Test that controllers with out-of-bounds positions are skipped (line 1074).

        When the position x or y is outside canvas bounds, the continue is hit.
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 4
        canvas_sprite.pixels_tall = 4
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8

        parent_scene = mocker.Mock()

        mock_mode = mocker.Mock()
        mock_mode.value = 'canvas'
        parent_scene.mode_switcher.get_controller_mode.return_value = mock_mode

        mock_position = mocker.Mock()
        mock_position.is_valid = True
        mock_position.position = (10, 10)  # Out of bounds for 4x4 canvas
        parent_scene.mode_switcher.get_controller_position.return_value = mock_position
        parent_scene.controller_selections = {0: mocker.Mock()}

        canvas_sprite.parent_scene = parent_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_indicator_for_pixel(0)

        assert result is None


class TestCanvasGetPixelColorOutOfRange:
    """Test _get_pixel_color_at_position with out-of-range index (line 1129)."""

    def test_pixel_index_out_of_range(self, mocker):
        """Test that pixel index beyond pixels list returns black (line 1129).

        When coordinates are valid but the pixel index exceeds the
        length of the pixels list, the method logs a debug message
        and returns black.
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 4
        canvas_sprite.pixels_tall = 4
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        # Only 4 pixels in the list, but canvas is 4x4 = 16
        canvas_sprite.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]

        renderer = AnimatedCanvasRenderer(canvas_sprite)

        # Request pixel at (3, 3) = index 15, but only 4 pixels exist
        result = renderer._get_pixel_color_at_position(3, 3)

        assert result == (0, 0, 0)


class TestCanvasSetPixelControllerDragPath:
    """Test set_pixel_at controller drag active path (line 397)."""

    def test_set_pixel_at_controller_drag_active_collects_pixel(self, mocker):
        """Test that controller drag active path skips pixel collection (line 397).

        When _is_controller_drag_active returns True and _should_track_color_change
        returns False, the code enters the elif branch at line 397-398.
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 4
        canvas_sprite.pixels_tall = 4
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        canvas_sprite.border_thickness = 1
        canvas_sprite.pixels = [(0, 0, 0)] * 16

        # Configure animated_sprite so AnimatedCanvasInterface.__init__ can access
        # .animations and .animation_order properties without TypeError.
        # Also set .frames as a dict so _get_old_pixel_color can use 'in' operator on it.
        mock_frame = mocker.Mock()
        mock_frame.get_pixel_data.return_value = [(0, 0, 0)] * 16
        animations_data = {'idle': [mock_frame]}
        canvas_sprite.animated_sprite._animations = animations_data
        canvas_sprite.animated_sprite.animations = animations_data
        canvas_sprite.animated_sprite._animation_order = ['idle']
        canvas_sprite.animated_sprite.animation_order = ['idle']
        canvas_sprite.animated_sprite.frames = {'idle': [mock_frame]}

        # Mock parent_scene for the interface
        parent_scene = mocker.Mock()
        parent_scene.undo_redo_manager = mocker.Mock()
        parent_scene.undo_redo_manager.is_undoing = False
        parent_scene.undo_redo_manager.is_redoing = False
        parent_scene.canvas_operation_tracker = mocker.Mock()
        canvas_sprite.parent_scene = parent_scene

        interface = AnimatedCanvasInterface(canvas_sprite)

        # Mock to return controller drag is active
        mocker.patch.object(interface, '_is_controller_drag_active', return_value=True)
        # Mock to return should NOT track (triggers the elif at line 397)
        mocker.patch.object(interface, '_should_track_color_change', return_value=False)
        mocker.patch.object(interface, '_collect_pixel_change')

        # The pixel should still be set on the frame data
        interface.set_pixel_at(0, 0, (255, 0, 0))

        # _collect_pixel_change should NOT be called since _should_track returns False
        interface._collect_pixel_change.assert_not_called()  # type: ignore[unresolved-attribute]


class TestAnimatedCanvasInterfaceGetPixelAtAnimated:
    """Test AnimatedCanvasInterface.get_pixel_at with animated sprite frames."""

    def test_get_pixel_at_from_animated_frame(self, mocker):
        """Test get_pixel_at retrieves pixel from animated sprite frame."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.current_animation = 'idle'
        canvas_sprite.current_frame = 0

        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        pixel_data = cast('list[tuple[int, ...]]', [RED] * PIXEL_COUNT)
        frame.set_pixel_data(pixel_data)
        animated_sprite.add_animation('idle', [frame])
        canvas_sprite.animated_sprite = animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface.get_pixel_at(0, 0)
        assert result == RED

    def test_get_pixel_at_rgb_frame_converts_to_rgba(self, mocker):
        """Test get_pixel_at converts RGB frame pixel to RGBA."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.current_animation = 'idle'
        canvas_sprite.current_frame = 0

        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        pixel_data = cast('list[tuple[int, ...]]', [RED_RGB] * PIXEL_COUNT)
        frame.set_pixel_data(pixel_data)
        animated_sprite.add_animation('idle', [frame])
        canvas_sprite.animated_sprite = animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface.get_pixel_at(0, 0)
        assert len(result) == 4
        assert result[3] == 255  # Alpha should be 255

    def test_get_pixel_at_falls_back_to_static(self, mocker):
        """Test get_pixel_at falls back to static pixel when no animation match."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [BLUE] * PIXEL_COUNT
        canvas_sprite.current_animation = 'nonexistent'
        canvas_sprite.current_frame = 0

        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        animated_sprite.add_animation('idle', [frame])
        canvas_sprite.animated_sprite = animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface.get_pixel_at(0, 0)
        assert result == BLUE


class TestAnimatedCanvasInterfaceGetOldPixelColor:
    """Test AnimatedCanvasInterface._get_old_pixel_color."""

    def test_get_old_color_from_animated_frame(self, mocker):
        """Test _get_old_pixel_color retrieves from animated frame."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.current_animation = 'idle'
        canvas_sprite.current_frame = 0

        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        pixel_data = cast('list[tuple[int, ...]]', [GREEN] * PIXEL_COUNT)
        frame.set_pixel_data(pixel_data)
        animated_sprite.add_animation('idle', [frame])
        canvas_sprite.animated_sprite = animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._get_old_pixel_color(0)
        assert result == GREEN

    def test_get_old_color_animation_not_in_frames(self, mocker):
        """Test _get_old_pixel_color returns None when animation not found."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.current_animation = 'nonexistent'
        canvas_sprite.current_frame = 0

        animated_sprite = AnimatedSprite()
        canvas_sprite.animated_sprite = animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._get_old_pixel_color(0)
        assert result is None

    def test_get_old_color_from_static(self, mocker):
        """Test _get_old_pixel_color retrieves from static pixels."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels = [RED] * PIXEL_COUNT
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._get_old_pixel_color(0)
        assert result == RED


class TestAnimatedCanvasInterfaceUpdateFramePixelData:
    """Test AnimatedCanvasInterface._update_frame_pixel_data."""

    def test_update_frame_data_in_animated_sprite(self, mocker):
        """Test _update_frame_pixel_data updates animated frame pixel."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.current_animation = 'idle'
        canvas_sprite.current_frame = 0

        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        magenta_pixels = cast('list[tuple[int, ...]]', [MAGENTA] * PIXEL_COUNT)
        frame.set_pixel_data(magenta_pixels)
        animated_sprite.add_animation('idle', [frame])
        canvas_sprite.animated_sprite = animated_sprite
        del canvas_sprite.on_pixel_update_event  # Remove to test without event

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface._update_frame_pixel_data(0, RED)
        # Frame data should be updated
        updated_pixels = frame.get_pixel_data()
        assert updated_pixels[0] == RED
        assert canvas_sprite.dirty == 1

    def test_update_frame_data_triggers_pixel_event(self, mocker):
        """Test _update_frame_pixel_data triggers pixel update event."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.current_animation = 'idle'
        canvas_sprite.current_frame = 0

        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        magenta_pixels = cast('list[tuple[int, ...]]', [MAGENTA] * PIXEL_COUNT)
        frame.set_pixel_data(magenta_pixels)
        animated_sprite.add_animation('idle', [frame])
        canvas_sprite.animated_sprite = animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface._update_frame_pixel_data(0, RED)
        canvas_sprite.on_pixel_update_event.assert_called_once()

    def test_update_frame_data_static_fallback(self, mocker):
        """Test _update_frame_pixel_data falls back to static pixels."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface._update_frame_pixel_data(0, RED)
        assert canvas_sprite.pixels[0] == RED
        assert canvas_sprite.dirty == 1


class TestAnimatedCanvasInterfaceSetPixelAtFullPath:
    """Test AnimatedCanvasInterface.set_pixel_at non-skip path."""

    def test_set_pixel_at_with_controller_drag_active(self, mocker):
        """Test set_pixel_at logs when controller drag is active."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        canvas_sprite.current_animation = 'idle'
        canvas_sprite.current_frame = 0
        canvas_sprite.parent_scene.controller_drags = {
            0: {'active': True, 'pixels_drawn': [(1, 2, RED, GREEN)]},
        }
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface.set_pixel_at(0, 0, RED)
        # Should still update pixel data even with drag active
        assert canvas_sprite.pixels[0] == RED


class TestAnimatedCanvasInterfaceShouldTrackWithTracker:
    """Test _should_track_color_change with canvas_operation_tracker."""

    def test_should_track_with_operation_tracker(self, mocker):
        """Test color change is tracked when operation tracker exists."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene.canvas_operation_tracker = mocker.Mock()
        canvas_sprite.parent_scene._applying_undo_redo = False
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._should_track_color_change(
            RED,
            GREEN,
            controller_drag_active=False,
        )
        assert result is True

    def test_should_not_track_during_undo_redo(self, mocker):
        """Test color change not tracked during undo/redo application."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene.canvas_operation_tracker = mocker.Mock()
        canvas_sprite.parent_scene._applying_undo_redo = True
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._should_track_color_change(
            RED,
            GREEN,
            controller_drag_active=False,
        )
        assert result is False


class TestAnimatedCanvasInterfaceCollectPixelChange:
    """Test AnimatedCanvasInterface._collect_pixel_change."""

    def test_collect_first_pixel_change_starts_timer(self, mocker):
        """Test collecting first pixel change starts a timer."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene.current_pixel_changes = []
        canvas_sprite.parent_scene.current_pixel_changes_dict = {}
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface._collect_pixel_change(0, 0, MAGENTA, RED)

        assert (0, 0) in canvas_sprite.parent_scene.current_pixel_changes_dict
        assert hasattr(canvas_sprite.parent_scene, 'pixel_change_timer')

    def test_collect_duplicate_pixel_updates_existing(self, mocker):
        """Test collecting same pixel again updates new_color, keeps old_color."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene.current_pixel_changes = []
        canvas_sprite.parent_scene.current_pixel_changes_dict = {
            (0, 0): (0, 0, MAGENTA, RED),
        }
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface._collect_pixel_change(0, 0, RED, GREEN)

        entry = canvas_sprite.parent_scene.current_pixel_changes_dict[0, 0]
        # Original old_color (MAGENTA) should be preserved, new_color updated to GREEN
        assert entry == (0, 0, MAGENTA, GREEN)

    def test_collect_initializes_tracking_structures(self, mocker):
        """Test _collect_pixel_change initializes structures if missing."""
        canvas_sprite = mocker.Mock(spec=[])
        canvas_sprite.parent_scene = mocker.Mock(spec=[])
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface._collect_pixel_change(1, 1, MAGENTA, BLUE)

        assert hasattr(canvas_sprite.parent_scene, 'current_pixel_changes')
        assert hasattr(canvas_sprite.parent_scene, 'current_pixel_changes_dict')


class TestAnimatedCanvasRendererMethods:
    """Test AnimatedCanvasRenderer render and force_redraw methods."""

    def test_render_draws_static_pixels_with_borders_and_hover(self):
        """Render without an animated sprite draws the pixels, their borders and the hover."""
        canvas_sprite = _static_canvas_stand_in(
            pixels=[MAGENTA] * PIXEL_COUNT,
            pixel_size=8,
            image=pygame.Surface((CANVAS_SIZE * 8, CANVAS_SIZE * 8)),
            border_thickness=1,
            hovered_pixel=(3, 3),
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        result = renderer.render(canvas_sprite)

        assert result is canvas_sprite.image
        assert _rgb_at(result, 4, 4) == (255, 0, 255)
        assert _rgb_at(result, 0, 0) == BORDER_GRAY_RGB
        # The hovered cell (3, 3) at x/y 24..31 is outlined in white
        assert _rgb_at(result, 24, 24) == WHITE_RGB
        assert _rgb_at(result, 25, 25) == WHITE_RGB
        assert _rgb_at(result, 28, 28) == (255, 0, 255)

    def test_force_redraw_static_fallback_fills_background_first(self):
        """A static redraw clears the old image to the background before drawing pixels."""
        image = pygame.Surface((CANVAS_SIZE * 8, CANVAS_SIZE * 8 + 8))
        image.fill((9, 9, 9))
        canvas_sprite = _static_canvas_stand_in(
            pixels=[MAGENTA] * PIXEL_COUNT,
            pixel_size=8,
            image=image,
            background_color=(1, 2, 3),
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        result = renderer.force_redraw(canvas_sprite)

        assert result is canvas_sprite.image
        # The extra row below the pixels shows the background, not the old fill
        assert _rgb_at(result, 0, CANVAS_SIZE * 8) == (1, 2, 3)
        assert _rgb_at(result, 0, 0) == (255, 0, 255)

    def test_get_pixel_size_returns_tuple(self, mocker):
        """Test get_pixel_size returns pixel dimensions."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        del canvas_sprite.animated_sprite

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer.get_pixel_size()
        assert result == (8, 8)


class TestAnimatedCanvasInterfaceInitWithEmptyOrder:
    """Test AnimatedCanvasInterface initialization when the load order is empty."""

    def test_empty_animation_order_falls_back_to_the_first_animation(self):
        """Animations with an empty recorded order start on the first animation key."""
        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        animated_sprite._animations = {
            'run': [SpriteFrame(surface)],
            'idle': [SpriteFrame(surface)],
        }
        animated_sprite._animation_order = []
        canvas_sprite = SimpleNamespace(animated_sprite=animated_sprite)

        interface = AnimatedCanvasInterface(canvas_sprite)

        assert interface.current_animation == 'run'


class TestDrawControllerIndicatorsOnlyWithoutControllers:
    """Test _draw_controller_indicators_only when no controller is in canvas mode."""

    def test_hidden_frame_without_controllers_draws_nothing(self):
        """With the frame hidden and no controller scene, the canvas image is left as it was."""
        image = pygame.Surface((16, 16), pygame.SRCALPHA)
        image.fill((1, 2, 3, 255))
        canvas_sprite = SimpleNamespace(
            pixels_across=2,
            pixels_tall=2,
            pixel_width=8,
            pixel_height=8,
            image=image,
            parent_scene=None,
        )
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        renderer._draw_controller_indicators_only([RED, GREEN, BLUE, MAGENTA])

        width, height = image.get_size()
        assert all(
            tuple(image.get_at((pixel_x, pixel_y))) == (1, 2, 3, 255)
            for pixel_y in range(height)
            for pixel_x in range(width)
        )


class TestGetPixelColorWithoutCanvas:
    """Test _get_pixel_color_at_position when the renderer has no canvas."""

    def test_missing_canvas_reads_as_black(self):
        """Without a canvas sprite every position reads as black."""
        renderer = AnimatedCanvasRenderer(None)

        assert renderer._get_pixel_color_at_position(0, 0) == (0, 0, 0)


# ---------------------------------------------------------------------------
# Rendered canvas goldens: a real AnimatedCanvasSprite redrawn in many states
# ---------------------------------------------------------------------------


def _golden_pattern_pixel(*, index, shift):
    """Pick a pattern pixel covering every kind of pixel the canvas draws.

    Magenta RGB and opaque magenta RGBA are skipped (the background shows); magenta with alpha
    0 is not skipped (it is drawn, clearing the cell); the rest are RGB, opaque RGBA and
    translucent RGBA.

    Returns:
        tuple[int, ...]: The pixel at ``index``.

    """
    kind = (index + shift) % 7
    pattern_pixels = (
        (255, 0, 255),
        ((index * 37) % 256, (index * 91) % 256, (index * 13) % 256),
        (255, 0, 255, 255),
        (10, 200, 30, 128),
        (200, 40, index % 256, 255),
        (255, 0, 255, 0),
        (0, 0, 0),
    )
    return pattern_pixels[kind]


def _golden_canvas(*, pixels_across, pixels_tall, pixel_width, pixel_height, frame_count=1):
    """Build a real animated canvas whose frames hold shifted copies of the golden pattern.

    Returns:
        AnimatedCanvasSprite: The canvas, on frame 0 of animation 'golden'.

    """
    frames = []
    for frame_index in range(frame_count):
        frame = SpriteFrame(pygame.Surface((pixels_across, pixels_tall)))
        frame.pixels = [
            _golden_pattern_pixel(index=pixel_index, shift=frame_index * 3)
            for pixel_index in range(pixels_across * pixels_tall)
        ]
        frames.append(frame)
    animated_sprite = AnimatedSprite()
    animated_sprite._animations = {'golden': frames}
    animated_sprite.frame_manager.current_animation = 'golden'
    return AnimatedCanvasSprite(
        animated_sprite=animated_sprite,
        pixels_across=pixels_across,
        pixels_tall=pixels_tall,
        pixel_width=pixel_width,
        pixel_height=pixel_height,
    )


def _golden_controller_scene(*, controllers, selected_frame_visible=True):
    """Build a scene stand-in holding controllers, each (mode, position, colour or None).

    Returns:
        SimpleNamespace: The scene stand-in AnimatedCanvasRenderer reads controllers from.

    """
    controller_ids = list(range(len(controllers)))
    return SimpleNamespace(
        controller_selections={
            controller_id: SimpleNamespace() for controller_id in controller_ids
        },
        mode_switcher=SimpleNamespace(
            get_controller_mode=lambda controller_id: SimpleNamespace(
                value=controllers[controller_id][0],
            ),
            get_controller_position=lambda controller_id: SimpleNamespace(
                is_valid=True,
                position=controllers[controller_id][1],
            ),
        ),
        controller_handler=SimpleNamespace(
            find_controller_info=lambda controller_id: (
                None
                if controllers[controller_id][2] is None
                else SimpleNamespace(
                    controller_id=controller_id, color=controllers[controller_id][2]
                )
            ),
        ),
        selected_frame_visible=selected_frame_visible,
    )


def _golden_canvas_8_by_8():
    """Build the 8x8 canvas of 16x16 cells most golden states start from.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    return _golden_canvas(pixels_across=8, pixels_tall=8, pixel_width=16, pixel_height=16)


def _golden_state_empty():
    """Build an 8x8 canvas whose frame is all magenta (nothing painted).

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    canvas = _golden_canvas_8_by_8()
    frame = canvas.animated_sprite._animations['golden'][0]
    frame.pixels = [(255, 0, 255)] * 64
    return canvas


def _golden_state_painted():
    """Build an 8x8 canvas painted with the golden pattern.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    return _golden_canvas_8_by_8()


def _golden_state_hovered():
    """Build the painted 8x8 canvas with a hovered pixel and the canvas hover border.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    canvas = _golden_canvas_8_by_8()
    canvas.hovered_pixel = (2, 3)
    canvas.is_hovered = True
    return canvas


def _golden_state_non_square_cells():
    """Build a 16x12 canvas of 6x10 cells (border on).

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    return _golden_canvas(pixels_across=16, pixels_tall=12, pixel_width=6, pixel_height=10)


def _golden_state_narrow_cells():
    """Build a 12x5 canvas of 2x8 cells: border on, each cell's outline covers its width.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    return _golden_canvas(pixels_across=12, pixels_tall=5, pixel_width=2, pixel_height=8)


def _golden_state_single_column_cells():
    """Build a 9x4 canvas of 1x7 cells: border on, outlines one pixel wide.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    return _golden_canvas(pixels_across=9, pixels_tall=4, pixel_width=1, pixel_height=7)


def _golden_state_without_grid():
    """Build a 20x20 canvas of 2x2 cells, where the grid is turned off.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    canvas = _golden_canvas(pixels_across=20, pixels_tall=20, pixel_width=2, pixel_height=2)
    assert canvas.border_thickness == 0
    return canvas


def _golden_state_onion_skinned():
    """Build an 8x8 canvas on frame 0 of 3 with frames 1 and 2 onion skinned.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    canvas = _golden_canvas(
        pixels_across=8, pixels_tall=8, pixel_width=16, pixel_height=16, frame_count=3
    )
    onion_manager = onion_skinning.get_onion_skinning_manager()
    onion_manager.onion_skinning_enabled = {'golden': {0: True, 1: True, 2: True}}
    onion_manager.onion_transparency = 0.3
    return canvas


def _golden_state_onion_skinning_off():
    """Build the onion skinned canvas with global onion skinning turned off.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    canvas = _golden_state_onion_skinned()
    onion_skinning.get_onion_skinning_manager().global_onion_skinning_enabled = False
    return canvas


GOLDEN_CONTROLLERS = [
    # No controller info: a later controller on the same pixel draws instead
    ('canvas', (2, 2), None),
    ('canvas', (2, 2), (255, 0, 0)),
    # A later controller on a pixel that already shows one is not drawn
    ('canvas', (2, 2), (255, 0, 128)),
    # On a magenta (skipped) pixel
    ('canvas', (0, 0), (0, 0, 255)),
    # On a translucent pixel
    ('canvas', (3, 0), (255, 255, 0)),
    # Not in canvas mode, and out of bounds: not drawn
    ('film_strip', (4, 4), (0, 255, 0)),
    ('canvas', (9, 1), (0, 255, 255)),
]


def _golden_state_controllers():
    """Build the painted 8x8 canvas with controllers on it.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    canvas = _golden_canvas_8_by_8()
    canvas.parent_scene = _golden_controller_scene(controllers=GOLDEN_CONTROLLERS)
    return canvas


def _golden_state_frame_hidden():
    """Build the 8x8 canvas with the selected frame hidden: only controller boxes are drawn.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    canvas = _golden_canvas_8_by_8()
    canvas.parent_scene = _golden_controller_scene(
        controllers=GOLDEN_CONTROLLERS,
        selected_frame_visible=False,
    )
    return canvas


def _golden_state_static_fallback():
    """Build the 8x8 canvas showing an animation it does not have: the static pixels draw.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    canvas = _golden_canvas_8_by_8()
    canvas.parent_scene = _golden_controller_scene(controllers=GOLDEN_CONTROLLERS)
    canvas.pixels = [
        _golden_pattern_pixel(index=pixel_index, shift=0)[:3] for pixel_index in range(64)
    ]
    canvas.current_animation = 'missing'
    return canvas


def _golden_state_controllers_on_small_cells():
    """Build a 6x6 canvas of 3x3 cells with controllers: their boxes reach past their cells.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    canvas = _golden_canvas(pixels_across=6, pixels_tall=6, pixel_width=3, pixel_height=3)
    canvas.parent_scene = _golden_controller_scene(controllers=GOLDEN_CONTROLLERS)
    return canvas


def _golden_state_static_fallback_on_small_cells():
    """Build the static fallback on a 6x6 canvas of 3x3 cells with controllers.

    Returns:
        AnimatedCanvasSprite: The canvas.

    """
    canvas = _golden_state_controllers_on_small_cells()
    canvas.pixels = [
        _golden_pattern_pixel(index=pixel_index, shift=0)[:3] for pixel_index in range(36)
    ]
    canvas.current_animation = 'missing'
    return canvas


# SHA-256 of each state's redrawn canvas image as RGBA bytes, recorded from the renderer before
# its redraw was optimized: the optimized redraw must draw exactly the same pixels
CANVAS_REDRAW_GOLDEN_DIGESTS = {
    'empty': ('6dfc34df6951040e72fc07cd49fe459a88cf221b90ed3fd6f346867f4080727d'),
    'painted': ('b0ea66872f1f2815d27aedaedcd095180bacb5c5c4b024fa41f58381e737274d'),
    'hovered': ('9b4647c7812c10863d7d56735cfa2e4c66e0f65b8f77cbcb2c311ced8e955df6'),
    'non_square_cells': ('e2fc4b54b93878d14c9b6f39270693ea6471739c7def69dce68e935eff08b1ca'),
    'narrow_cells': ('4aaf7a89e2a4a3cf1f73f191aa38e115cacd7970e6fcaab6545f8d19f8ec4b68'),
    'single_column_cells': ('5ad241ae8ec60f52ae011a795007f54da32ed408c6d2022e26e2a116df8fe8e2'),
    'without_grid': ('8b771cd06d9df890febedb7a9e6379ba426f042889c0ec95faec642698ed123e'),
    'onion_skinned': ('43b7e20e84d29da3affd1591d23706ee09004912efbf9de572e7d338abace532'),
    'onion_skinning_off': ('b0ea66872f1f2815d27aedaedcd095180bacb5c5c4b024fa41f58381e737274d'),
    'controllers': ('00e32736e8d35646b1f8a22ebb834338e7ea27ade88d3ac3ecad9eb0082c78d6'),
    'frame_hidden': ('47d4ed25f4b5358aa1e6b4c4e345560b873dba96afbd25b6eca205de319d8cd2'),
    'static_fallback': ('992943b379283d59b18526400f7c7206ece2675f83e2f44a072b59b7ad14d1be'),
    'controllers_on_small_cells': (
        '53108b99813659a869841083da777ed12dbde23b4fb92b4d22c9f82f1f2efc05'
    ),
    'static_fallback_on_small_cells': (
        '82c2611ccc93ba73a8725ab372bf28cada9919022dae9da1ee62fcf2611a2ac1'
    ),
}

CANVAS_REDRAW_GOLDEN_STATES = {
    'empty': _golden_state_empty,
    'painted': _golden_state_painted,
    'hovered': _golden_state_hovered,
    'non_square_cells': _golden_state_non_square_cells,
    'narrow_cells': _golden_state_narrow_cells,
    'single_column_cells': _golden_state_single_column_cells,
    'without_grid': _golden_state_without_grid,
    'onion_skinned': _golden_state_onion_skinned,
    'onion_skinning_off': _golden_state_onion_skinning_off,
    'controllers': _golden_state_controllers,
    'frame_hidden': _golden_state_frame_hidden,
    'static_fallback': _golden_state_static_fallback,
    'controllers_on_small_cells': _golden_state_controllers_on_small_cells,
    'static_fallback_on_small_cells': _golden_state_static_fallback_on_small_cells,
}


@pytest.fixture
def isolated_onion_skinning(monkeypatch):
    """Give the global onion skinning manager its startup state, restored after the test."""
    onion_manager = onion_skinning.get_onion_skinning_manager()
    monkeypatch.setattr(onion_manager, 'onion_skinning_enabled', {})
    monkeypatch.setattr(onion_manager, 'global_onion_skinning_enabled', True)
    monkeypatch.setattr(onion_manager, 'onion_transparency', 0.5)


def _redrawn_canvas_digest(canvas):
    """Redraw a canvas and digest its image's pixels, independent of the display's format.

    Returns:
        str: The SHA-256 hex digest of the image as RGBA bytes.

    """
    canvas.force_redraw()
    return hashlib.sha256(pygame.image.tobytes(canvas.image, 'RGBA')).hexdigest()


@pytest.mark.usefixtures('isolated_onion_skinning')
class TestCanvasRedrawGoldens:
    """A real canvas redraws exactly the recorded pixels in every state."""

    @pytest.mark.parametrize('state_name', list(CANVAS_REDRAW_GOLDEN_STATES))
    def test_redraw_matches_golden(self, state_name):
        """The redrawn image matches the golden digest recorded for the state."""
        canvas = CANVAS_REDRAW_GOLDEN_STATES[state_name]()

        assert _redrawn_canvas_digest(canvas) == CANVAS_REDRAW_GOLDEN_DIGESTS[state_name]

    def test_redraw_is_repeatable(self):
        """Redrawing twice in a row draws the same pixels (nothing carries over wrongly)."""
        canvas = _golden_state_controllers()

        first_digest = _redrawn_canvas_digest(canvas)

        assert _redrawn_canvas_digest(canvas) == first_digest

    def test_redraw_draws_the_grid_as_lines_not_cell_outlines(self, mocker):
        """A 32x32 canvas redraw draws one rect per painted pixel and fills each grid line once.

        Before, every pixel's cell got its own outline (1,024 draw.rect calls per redraw).
        """
        canvas = _golden_canvas(pixels_across=32, pixels_tall=32, pixel_width=10, pixel_height=10)
        assert canvas.border_thickness == 1
        frame_pixels = canvas.animated_sprite._animations['golden'][0].pixels
        painted_pixel_count = sum(
            1 for pixel in frame_pixels if pixel not in {(255, 0, 255), (255, 0, 255, 255)}
        )
        draw_rect_spy = mocker.spy(pygame.draw, 'rect')

        canvas.force_redraw()

        assert draw_rect_spy.call_count == painted_pixel_count

    def test_redraw_looks_controllers_up_once_not_per_pixel(self, mocker):
        """The controller scene is looked up a fixed number of times per redraw, not per pixel."""
        canvas = _golden_state_controllers()
        controller_scene_spy = mocker.spy(canvas.canvas_renderer, '_get_controller_scene')

        canvas.force_redraw()

        # Once, to map the controllers' pixels (before, once per pixel and per controller)
        assert controller_scene_spy.call_count == 1
