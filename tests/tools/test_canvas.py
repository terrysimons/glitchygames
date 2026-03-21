"""Tests for canvas functionality and deeper coverage."""

from typing import cast

import pygame
import pytest

from glitchygames.sprites.animated import (
    AnimatedSprite,
    SpriteFrame,
)
from glitchygames.tools import canvas_interfaces
from glitchygames.tools.canvas_interfaces import (
    AnimatedCanvasInterface,
    StaticCanvasInterface,
)
from tests.mocks.test_mock_factory import MockFactory


class TestCanvasInterfaces:
    """Test canvas interfaces functionality."""

    def _create_mock_sprite(self):
        """Create a mock sprite using MockFactory.

        Returns:
            object: The result.

        """
        return MockFactory.create_animated_sprite_mock()

    def test_canvas_interface_protocol(self, mock_pygame_patches):
        """Test canvas interface protocol."""
        # Test that CanvasInterface protocol is defined
        assert hasattr(canvas_interfaces, 'CanvasInterface')

        # Test protocol methods exist
        protocol = canvas_interfaces.CanvasInterface
        assert hasattr(protocol, '__abstractmethods__')

    def test_sprite_serializer_abstract_base(self, mock_pygame_patches):
        """Test sprite serializer abstract base."""
        # Test that SpriteSerializer is defined
        assert hasattr(canvas_interfaces, 'SpriteSerializer')

        # Test abstract methods exist
        serializer = canvas_interfaces.SpriteSerializer
        assert hasattr(serializer, '__abstractmethods__')

    def test_animated_canvas_interface_protocol(self, mock_pygame_patches):
        """Test animated canvas interface protocol."""
        # Test that AnimatedCanvasInterface protocol is defined
        assert hasattr(canvas_interfaces, 'AnimatedCanvasInterface')

        # Test that it's a class (not necessarily abstract)
        protocol = canvas_interfaces.AnimatedCanvasInterface
        assert callable(protocol)

    def test_animated_canvas_renderer_protocol(self, mock_pygame_patches):
        """Test animated canvas renderer protocol."""
        # Test that AnimatedCanvasRenderer protocol is defined
        assert hasattr(canvas_interfaces, 'AnimatedCanvasRenderer')

        # Test protocol methods exist
        protocol = canvas_interfaces.AnimatedCanvasRenderer
        assert hasattr(protocol, '__abstractmethods__')

    def test_animated_sprite_serializer_protocol(self, mock_pygame_patches):
        """Test animated sprite serializer protocol."""
        # Test that AnimatedSpriteSerializer protocol is defined
        assert hasattr(canvas_interfaces, 'AnimatedSpriteSerializer')

        # Test protocol methods exist
        protocol = canvas_interfaces.AnimatedSpriteSerializer
        assert hasattr(protocol, '__abstractmethods__')

    def test_static_canvas_interface_initialization(self, mock_pygame_patches):
        """Test static canvas interface initialization."""
        # Test StaticCanvasInterface initialization - requires canvas_sprite parameter
        mock_sprite = self._create_mock_sprite()
        interface = canvas_interfaces.StaticCanvasInterface(mock_sprite)

        # Test basic properties
        assert hasattr(interface, 'canvas_sprite')
        assert interface.canvas_sprite == mock_sprite

    def test_static_canvas_interface_pixel_operations(self, mock_pygame_patches):
        """Test static canvas interface pixel operations."""
        mock_sprite = self._create_mock_sprite()
        interface = canvas_interfaces.StaticCanvasInterface(mock_sprite)

        # Test that interface has expected methods
        assert hasattr(interface, 'get_pixel_data')
        assert hasattr(interface, 'set_pixel_data')
        assert hasattr(interface, 'get_dimensions')
        assert callable(interface.get_pixel_data)
        assert callable(interface.set_pixel_data)
        assert callable(interface.get_dimensions)

    def test_animated_canvas_interface_initialization(self, mock_pygame_patches, mocker):
        """Test animated canvas interface initialization."""
        # Test AnimatedCanvasInterface initialization - requires properly mocked canvas_sprite
        mock_sprite = self._create_mock_sprite()
        mock_animated_sprite = mocker.Mock()
        mock_animated_sprite._animation_order = ['idle']
        mock_animated_sprite.animation_order = ['idle']
        mock_animated_sprite._animations = {'idle': [mocker.Mock()]}
        mock_animated_sprite.animations = {'idle': [mocker.Mock()]}
        mock_sprite.animated_sprite = mock_animated_sprite

        interface = canvas_interfaces.AnimatedCanvasInterface(mock_sprite)

        # Test basic properties
        assert hasattr(interface, 'canvas_sprite')
        assert interface.canvas_sprite == mock_sprite

    def test_static_canvas_interface_comprehensive(self, mock_pygame_patches):
        """Test comprehensive static canvas interface functionality."""
        mock_sprite = self._create_mock_sprite()
        interface = canvas_interfaces.StaticCanvasInterface(mock_sprite)

        # Test that interface has expected methods
        assert hasattr(interface, 'get_pixel_data')
        assert hasattr(interface, 'set_pixel_data')
        assert hasattr(interface, 'get_dimensions')
        assert callable(interface.get_pixel_data)
        assert callable(interface.set_pixel_data)
        assert callable(interface.get_dimensions)

    def test_static_sprite_serializer(self, mock_pygame_patches):
        """Test static sprite serializer functionality."""
        # Test StaticSpriteSerializer initialization - takes no arguments
        serializer = canvas_interfaces.StaticSpriteSerializer()

        # Test basic properties - StaticSpriteSerializer doesn't have canvas_sprite attribute
        # It's an abstract base class, so we just verify it can be instantiated
        assert serializer is not None


CANVAS_SIZE = 4
PIXEL_COUNT = 16
MAGENTA = (255, 0, 255, 255)
RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
RED_RGB = (255, 0, 0)


class TestAnimatedCanvasInterfaceGetPixelAtWithAnimatedSprite:
    """Test AnimatedCanvasInterface.get_pixel_at with actual animated sprite data."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_get_pixel_at_from_animated_sprite_frame(self, mocker):
        """Test get_pixel_at retrieves pixel from animated sprite frame."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT

        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        pixels = cast('list[tuple[int, ...]]', [RED] * PIXEL_COUNT)
        pixels[0] = BLUE
        frame.set_pixel_data(pixels)
        animated_sprite.add_animation('idle', [frame])
        animated_sprite.set_animation('idle')

        canvas_sprite.animated_sprite = animated_sprite
        canvas_sprite.current_animation = 'idle'
        canvas_sprite.current_frame = 0

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface.get_pixel_at(0, 0)
        assert result == BLUE

    def test_get_pixel_at_out_of_bounds_returns_magenta(self, mocker):
        """Test get_pixel_at returns magenta for out-of-bounds."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface.get_pixel_at(100, 100)
        assert result == MAGENTA

    def test_get_pixel_at_rgb_pixel_converts_to_rgba(self, mocker):
        """Test get_pixel_at converts RGB pixel to RGBA."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [RED_RGB] * PIXEL_COUNT
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface.get_pixel_at(0, 0)
        assert result == (255, 0, 0, 255)


class TestAnimatedCanvasInterfaceSetPixelAtFullPath:
    """Test AnimatedCanvasInterface.set_pixel_at with full undo tracking path."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_set_pixel_at_with_animated_sprite(self, mocker):
        """Test set_pixel_at updates pixel in animated sprite frame."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        canvas_sprite.parent_scene = None  # No undo tracking

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
        interface.set_pixel_at(1, 1, RED)

        # Verify the frame pixel was updated
        updated_pixels = frame.get_pixel_data()
        pixel_index = 1 * CANVAS_SIZE + 1
        assert updated_pixels[pixel_index] == RED

    def test_set_pixel_at_clears_surface_cache(self, mocker):
        """Test set_pixel_at clears surface cache for the frame."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        canvas_sprite.parent_scene = None

        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        magenta_pixels = cast('list[tuple[int, ...]]', [MAGENTA] * PIXEL_COUNT)
        frame.set_pixel_data(magenta_pixels)
        animated_sprite.add_animation('idle', [frame])
        animated_sprite.set_animation('idle')
        # Pre-populate cache
        animated_sprite._surface_cache['idle_0'] = surface

        canvas_sprite.animated_sprite = animated_sprite
        canvas_sprite.current_animation = 'idle'
        canvas_sprite.current_frame = 0

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface.current_animation = 'idle'
        interface.current_frame = 0
        interface.set_pixel_at(0, 0, RED)

        # Cache should be cleared for this frame
        assert 'idle_0' not in animated_sprite._surface_cache

    def test_set_pixel_at_triggers_pixel_update_event(self, mocker):
        """Test set_pixel_at triggers on_pixel_update_event if available."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        canvas_sprite.parent_scene = None
        canvas_sprite.on_pixel_update_event = mocker.Mock()

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
        interface.set_pixel_at(0, 0, RED)

        canvas_sprite.on_pixel_update_event.assert_called_once()

    def test_set_pixel_at_static_sprite_fallback(self, mocker):
        """Test set_pixel_at falls back to static sprite when no animated_sprite."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.dirty_pixels = [False] * PIXEL_COUNT
        canvas_sprite.dirty = 0
        canvas_sprite.parent_scene = None
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface.set_pixel_at(0, 0, RED)
        assert canvas_sprite.pixels[0] == RED
        assert canvas_sprite.dirty == 1


class TestAnimatedCanvasInterfaceGetOldPixelColor:
    """Test AnimatedCanvasInterface._get_old_pixel_color method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_get_old_pixel_from_animated_sprite(self, mocker):
        """Test _get_old_pixel_color retrieves from animated sprite frame."""
        canvas_sprite = mocker.Mock()
        animated_sprite = AnimatedSprite()
        surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        frame = SpriteFrame(surface)
        blue_pixels = cast('list[tuple[int, ...]]', [BLUE] * PIXEL_COUNT)
        frame.set_pixel_data(blue_pixels)
        animated_sprite.add_animation('idle', [frame])
        animated_sprite.set_animation('idle')

        canvas_sprite.animated_sprite = animated_sprite
        canvas_sprite.current_animation = 'idle'
        canvas_sprite.current_frame = 0

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._get_old_pixel_color(0)
        assert result == BLUE

    def test_get_old_pixel_from_static_sprite(self, mocker):
        """Test _get_old_pixel_color retrieves from static sprite pixels."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels = [GREEN] * PIXEL_COUNT
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._get_old_pixel_color(5)
        assert result == GREEN

    def test_get_old_pixel_animation_not_in_frames(self, mocker):
        """Test _get_old_pixel_color returns None for missing animation."""
        canvas_sprite = mocker.Mock()
        animated_sprite = AnimatedSprite()
        canvas_sprite.animated_sprite = animated_sprite
        canvas_sprite.current_animation = 'nonexistent'
        canvas_sprite.current_frame = 0

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._get_old_pixel_color(0)
        assert result is None


class TestAnimatedCanvasInterfaceShouldTrackColorChangeDeeper:
    """Test AnimatedCanvasInterface._should_track_color_change with tracker present."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_tracks_when_tracker_present_and_not_applying_undo(self, mocker):
        """Test color change is tracked when canvas_operation_tracker exists."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = mocker.Mock()
        canvas_sprite.parent_scene.canvas_operation_tracker = mocker.Mock()
        canvas_sprite.parent_scene._applying_undo_redo = False
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._should_track_color_change(RED, GREEN, controller_drag_active=False)
        assert result is True

    def test_does_not_track_when_applying_undo_redo(self, mocker):
        """Test color change is not tracked when undo/redo is being applied."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = mocker.Mock()
        canvas_sprite.parent_scene.canvas_operation_tracker = mocker.Mock()
        canvas_sprite.parent_scene._applying_undo_redo = True
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._should_track_color_change(RED, GREEN, controller_drag_active=False)
        assert result is False

    def test_does_not_track_when_no_tracker(self, mocker):
        """Test color change is not tracked when no canvas_operation_tracker."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = mocker.Mock(spec=[])
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        result = interface._should_track_color_change(RED, GREEN, controller_drag_active=False)
        assert result is False


class TestAnimatedCanvasInterfaceCollectPixelChange:
    """Test AnimatedCanvasInterface._collect_pixel_change method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_collect_first_pixel_change(self, mocker):
        """Test collecting the first pixel change creates tracking structures."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = mocker.Mock(spec=['_current_pixel_changes_dict'])
        canvas_sprite.parent_scene._current_pixel_changes_dict = {}
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface._collect_pixel_change(1, 2, RED, GREEN)

        assert (1, 2) in canvas_sprite.parent_scene._current_pixel_changes_dict

    def test_collect_duplicate_pixel_keeps_original_old_color(self, mocker):
        """Test collecting duplicate pixel change preserves original old color."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene = mocker.Mock(spec=[])
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        # First change: old=RED, new=GREEN
        interface._collect_pixel_change(0, 0, RED, GREEN)
        # Second change at same pixel: old=GREEN, new=BLUE
        interface._collect_pixel_change(0, 0, GREEN, BLUE)

        change = canvas_sprite.parent_scene._current_pixel_changes_dict[0, 0]
        # Should keep original old_color (RED), update to latest new_color (BLUE)
        assert change[2] == RED
        assert change[3] == BLUE


class TestStaticCanvasInterfaceSetPixelAtDeeper:
    """Test StaticCanvasInterface set_pixel_at edge cases."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_set_pixel_at_high_y_coordinate(self, mocker):
        """Test set_pixel_at with high y coordinate is out of bounds."""
        sprite = mocker.Mock()
        sprite.pixels = [MAGENTA] * PIXEL_COUNT
        sprite.pixels_across = CANVAS_SIZE
        sprite.pixels_tall = CANVAS_SIZE
        sprite.dirty = 0
        sprite.dirty_pixels = [False] * PIXEL_COUNT
        sprite.image = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))

        interface = StaticCanvasInterface(sprite)
        original = sprite.pixels.copy()
        interface.set_pixel_at(0, CANVAS_SIZE, RED)  # y == height, out of bounds
        assert sprite.pixels == original

    def test_set_pixel_at_valid_interior_pixel(self, mocker):
        """Test set_pixel_at updates an interior pixel correctly."""
        sprite = mocker.Mock()
        sprite.pixels = [MAGENTA] * PIXEL_COUNT
        sprite.pixels_across = CANVAS_SIZE
        sprite.pixels_tall = CANVAS_SIZE
        sprite.dirty = 0
        sprite.dirty_pixels = [False] * PIXEL_COUNT
        sprite.image = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))

        interface = StaticCanvasInterface(sprite)
        interface.set_pixel_at(2, 3, BLUE)
        pixel_index = 3 * CANVAS_SIZE + 2
        assert sprite.pixels[pixel_index] == BLUE
        assert sprite.dirty_pixels[pixel_index] is True
        assert sprite.dirty == 1


class TestAnimatedCanvasInterfaceControllerDragActiveDeeper:
    """Test _is_controller_drag_active with multiple controllers."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_multiple_controllers_one_active(self, mocker):
        """Test returns True when one of multiple controllers has active drag."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene.controller_drags = {
            0: {'active': False, 'pixels_drawn': []},
            1: {'active': True, 'pixels_drawn': [(1, 2, RED, GREEN)]},
        }
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        assert interface._is_controller_drag_active() is True

    def test_all_controllers_inactive(self, mocker):
        """Test returns False when all controllers are inactive."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene.controller_drags = {
            0: {'active': False, 'pixels_drawn': []},
            1: {'active': False, 'pixels_drawn': []},
        }
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        assert interface._is_controller_drag_active() is False
