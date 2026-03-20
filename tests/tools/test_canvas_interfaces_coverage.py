"""Coverage tests for glitchygames/tools/canvas_interfaces.py.

Targets uncovered areas: _collect_pixel_change dictionary trimming,
_get_current_frame_pixels default frame handling, _draw_visible_frame_pixels
controller indicator drawing, _draw_controller_indicators_only,
_has_active_controllers_in_canvas_mode, _get_controller_indicator_for_pixel,
AnimatedCanvasRenderer force_redraw paths, and renderer helper methods.
"""

import sys
from pathlib import Path
from typing import cast

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.tools.canvas_interfaces import (
    AnimatedCanvasInterface,
    AnimatedCanvasRenderer,
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


class TestCollectPixelChangeDictionaryTrimming:
    """Test _collect_pixel_change dictionary trimming when exceeding max entries."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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
        parent_scene._current_pixel_changes = []
        parent_scene._current_pixel_changes_dict = {
            (i, 0): (i, 0, MAGENTA, RED) for i in range(2001)
        }
        parent_scene._pixel_changes_list_dirty = True
        canvas_sprite.parent_scene = parent_scene

        interface = AnimatedCanvasInterface(canvas_sprite)

        # Call _collect_pixel_change - dict already over 2000, should trigger trimming
        interface._collect_pixel_change(50, 50, MAGENTA, GREEN)

        # Should be trimmed to around 1500 entries (plus the new one)
        dict_size = len(parent_scene._current_pixel_changes_dict)
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
        parent_scene._current_pixel_changes = []
        parent_scene._current_pixel_changes_dict = {
            (1, 1): (1, 1, MAGENTA, RED)  # Existing entry
        }
        parent_scene._pixel_changes_list_dirty = True
        canvas_sprite.parent_scene = parent_scene

        interface = AnimatedCanvasInterface(canvas_sprite)

        # Update same pixel with new color
        interface._collect_pixel_change(1, 1, RED, GREEN)

        # Should keep original old_color (MAGENTA), but update new_color to GREEN
        assert parent_scene._current_pixel_changes_dict[1, 1] == (1, 1, MAGENTA, GREEN)

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

        assert hasattr(parent_scene, '_current_pixel_changes')
        assert hasattr(parent_scene, '_current_pixel_changes_dict')
        assert (0, 0) in parent_scene._current_pixel_changes_dict

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

        assert hasattr(parent_scene, '_pixel_change_timer')


class TestGetCurrentFramePixelsDefaultHandling:
    """Test AnimatedCanvasRenderer._get_current_frame_pixels default frame handling."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_get_current_frame_pixels_with_get_pixel_data(self, mocker):
        """Test _get_current_frame_pixels uses get_pixel_data when available."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.image = pygame.Surface((CANVAS_SIZE * 10, CANVAS_SIZE * 10))
        canvas_sprite.pixel_width = 10
        canvas_sprite.pixel_height = 10
        canvas_sprite._panning_active = False

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
        canvas_sprite._panning_active = False

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
        canvas_sprite._panning_active = False

        # Frame without get_pixel_data or pixels
        frame = mocker.Mock(spec=[])

        frames = {'idle': [frame]}

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_current_frame_pixels(frames, 'idle', 0)

        assert len(result) == PIXEL_COUNT
        assert result[0] == (255, 0, 255)

    def test_get_current_frame_pixels_uses_panned_pixels_when_active(self, mocker):
        """Test _get_current_frame_pixels uses panned canvas pixels when panning active."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [BLUE] * PIXEL_COUNT
        canvas_sprite.image = pygame.Surface((CANVAS_SIZE * 10, CANVAS_SIZE * 10))
        canvas_sprite.pixel_width = 10
        canvas_sprite.pixel_height = 10
        canvas_sprite._panning_active = True

        frame = mocker.Mock()
        frame.get_pixel_data.return_value = [RED] * PIXEL_COUNT

        frames = {'idle': [frame]}

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_current_frame_pixels(frames, 'idle', 0)

        # Should use canvas_sprite.pixels (panned), not frame data
        assert result == [BLUE] * PIXEL_COUNT


class TestHasActiveControllersInCanvasMode:
    """Test AnimatedCanvasRenderer._has_active_controllers_in_canvas_mode."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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
        mock_scene.multi_controller_manager.get_controller_info.return_value = mock_controller_info

        canvas_sprite.parent_scene = mock_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_indicator_for_pixel(1)  # pixel_index 1

        assert result == (255, 0, 0)

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

    def test_controller_without_multi_controller_manager_returns_none(self, mocker):
        """Test returns None when scene has no multi_controller_manager."""
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

        del mock_scene.multi_controller_manager

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

        mock_scene.multi_controller_manager.get_controller_info.return_value = None

        canvas_sprite.parent_scene = mock_scene

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer._get_controller_indicator_for_pixel(0)

        assert result is None


class TestAnimatedCanvasRendererForceRedraw:
    """Test AnimatedCanvasRenderer force_redraw paths."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_force_redraw_static_fallback(self, mocker):
        """Test force_redraw falls back to static rendering when no animated_sprite."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [RED] * PIXEL_COUNT
        canvas_sprite.pixel_width = 10
        canvas_sprite.pixel_height = 10
        canvas_sprite.border_thickness = 0
        canvas_sprite.background_color = (0, 0, 0)
        canvas_sprite.image = pygame.Surface((40, 40))
        canvas_sprite.hovered_pixel = None
        canvas_sprite.is_hovered = False
        canvas_sprite.parent_scene = None
        del canvas_sprite.animated_sprite

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer.force_redraw(canvas_sprite)

        assert result is canvas_sprite.image

    def test_render_delegates_to_force_redraw(self, mocker):
        """Test render method delegates to force_redraw."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [RED] * PIXEL_COUNT
        canvas_sprite.pixel_width = 10
        canvas_sprite.pixel_height = 10
        canvas_sprite.border_thickness = 0
        canvas_sprite.background_color = (0, 0, 0)
        canvas_sprite.image = pygame.Surface((40, 40))
        canvas_sprite.hovered_pixel = None
        canvas_sprite.is_hovered = False
        canvas_sprite.parent_scene = None
        del canvas_sprite.animated_sprite

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        mock_force_redraw = mocker.patch.object(
            renderer, 'force_redraw', return_value=canvas_sprite.image
        )

        result = renderer.render(canvas_sprite)

        mock_force_redraw.assert_called_once_with(canvas_sprite)


class TestAnimatedCanvasRendererHelpers:
    """Test AnimatedCanvasRenderer helper methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    def test_draw_pixel_on_canvas_rgba(self, mocker):
        """Test _draw_pixel_on_canvas draws RGBA pixel correctly."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixel_width = 10
        canvas_sprite.pixel_height = 10
        canvas_sprite.image = pygame.Surface((40, 40), pygame.SRCALPHA)

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        # Should not raise for RGBA pixel (4 components)
        renderer._draw_pixel_on_canvas((255, 0, 0, 128), 0, 0)

    def test_draw_pixel_on_canvas_rgb(self, mocker):
        """Test _draw_pixel_on_canvas converts RGB to RGBA and draws."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixel_width = 10
        canvas_sprite.pixel_height = 10
        canvas_sprite.image = pygame.Surface((40, 40), pygame.SRCALPHA)

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        # Should not raise for RGB pixel (3 components)
        renderer._draw_pixel_on_canvas((255, 0, 0), 0, 0)

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


class TestCanvasRendererDrawIndicatorsOnly:
    """Test _draw_controller_indicators_only rendering (lines 679, 887-898)."""

    def test_draw_controller_indicators_only(self, mocker):
        """Test that _draw_controller_indicators_only draws indicators.

        Covers line 679 (call path when selected_frame_visible is False)
        and lines 887-898 (the method body).
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 2
        canvas_sprite.pixels_tall = 2
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        canvas_sprite.image = mocker.Mock()

        renderer = AnimatedCanvasRenderer(canvas_sprite)

        # Mock _has_active_controllers_in_canvas_mode to return True
        mocker.patch.object(renderer, '_has_active_controllers_in_canvas_mode', return_value=True)
        # Mock _get_controller_indicator_for_pixel to return a color for pixel 0
        mocker.patch.object(
            renderer,
            '_get_controller_indicator_for_pixel',
            side_effect=lambda i: (255, 0, 0) if i == 0 else None,
        )
        # Mock _draw_plus_indicator
        mock_draw_plus = mocker.patch.object(renderer, '_draw_plus_indicator')

        frame_pixels = cast(
            'list[tuple[int, ...]]', [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        )

        renderer._draw_controller_indicators_only(frame_pixels)

        # Should have drawn an indicator for pixel 0 only
        mock_draw_plus.assert_called_once()


class TestCanvasRendererVisibleFrameWithControllerIndicator:
    """Test _draw_visible_frame_pixels controller indicator path (line 876)."""

    def test_draw_visible_frame_pixels_with_controller_indicator(self, mocker):
        """Test drawing visible frame with controller indicator on a non-transparent pixel.

        Covers line 876 where controller_indicator_color is truthy on a
        non-magenta pixel.
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 2
        canvas_sprite.pixels_tall = 2
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        canvas_sprite.image = mocker.Mock()

        renderer = AnimatedCanvasRenderer(canvas_sprite)

        mocker.patch.object(renderer, '_has_active_controllers_in_canvas_mode', return_value=True)
        mocker.patch.object(
            renderer,
            '_get_controller_indicator_for_pixel',
            side_effect=lambda i: (0, 255, 0) if i == 1 else None,
        )
        mock_draw_pixel = mocker.patch.object(renderer, '_draw_pixel_on_canvas')
        mock_draw_plus = mocker.patch.object(renderer, '_draw_plus_indicator')

        frame_pixels = cast(
            'list[tuple[int, ...]]', [(100, 100, 100), (200, 200, 200), (50, 50, 50), (10, 10, 10)]
        )

        renderer._draw_visible_frame_pixels(frame_pixels)

        # Pixel 1 should have drawn both the pixel and the indicator
        assert mock_draw_pixel.call_count >= 1
        mock_draw_plus.assert_called_once()


class TestCanvasRendererStaticPixelsWithController:
    """Test _redraw_static_pixels with controller indicator (lines 936, 939-945)."""

    def test_static_pixels_with_controller_indicator(self, mocker):
        """Test that _redraw_static_pixels draws controller indicator when present.

        Covers lines 936, 939-945 where a controller is active on a pixel
        during static redraw.
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 2
        canvas_sprite.pixels_tall = 2
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        canvas_sprite.border_thickness = 1
        canvas_sprite.background_color = (0, 0, 0)
        canvas_sprite.image = mocker.Mock()

        renderer = AnimatedCanvasRenderer(canvas_sprite)

        mocker.patch.object(renderer, '_has_active_controllers_in_canvas_mode', return_value=True)
        mocker.patch.object(
            renderer,
            '_get_controller_indicator_for_pixel',
            side_effect=lambda i: (255, 0, 0) if i == 0 else None,
        )
        mock_draw_plus = mocker.patch.object(renderer, '_draw_plus_indicator')
        mock_draw_rect = mocker.patch('pygame.draw.rect')

        pixels: list[tuple[int, int, int] | tuple[int, int, int, int]] = [
            (100, 100, 100),
            (200, 200, 200),
            (50, 50, 50),
            (10, 10, 10),
        ]

        renderer._redraw_static_pixels(pixels)

        # Should have drawn the indicator for pixel 0
        mock_draw_plus.assert_called_once()
        # pygame.draw.rect should have been called for pixels and borders
        assert mock_draw_rect.call_count >= 1


class TestCanvasRendererHoverEffects:
    """Test _draw_hover_effects (lines 977-983, 993)."""

    def test_draw_hover_effects_with_hovered_pixel(self, mocker):
        """Test that hover effects draw a white border around hovered pixel.

        Covers lines 977-983 where hovered_pixel is set and the white
        border rect is drawn.
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 4
        canvas_sprite.pixels_tall = 4
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        canvas_sprite.image = mocker.Mock()
        canvas_sprite.hovered_pixel = (1, 2)

        renderer = AnimatedCanvasRenderer(canvas_sprite)

        mock_draw_rect = mocker.patch('pygame.draw.rect')

        renderer._draw_hover_effects()

        # pygame.draw.rect should be called for the hover border
        mock_draw_rect.assert_called()
        # Check it was called with white color and the correct rect
        call_args = mock_draw_rect.call_args
        assert call_args[0][1] == (255, 255, 255)  # White color


class TestCanvasRendererDrawIndicatorsOnlyPath:
    """Test _redraw_animated_sprite path calling _draw_controller_indicators_only."""

    def test_redraw_animated_sprite_with_hidden_selected_frame(self, mocker):
        """Test that _redraw_animated_sprite calls _draw_controller_indicators_only when hidden.

        Covers line 679 where selected_frame_visible is False.
        force_redraw calls _redraw_animated_sprite which eventually calls
        _draw_controller_indicators_only when selected_frame_visible is False.
        """
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 2
        canvas_sprite.pixels_tall = 2
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        # width/height in pixels needed for pygame.Surface creation in _redraw_animated_sprite
        canvas_sprite.width = 16  # pixels_across * pixel_width
        canvas_sprite.height = 16  # pixels_tall * pixel_height
        canvas_sprite.border_thickness = 0
        canvas_sprite.image = mocker.Mock()
        canvas_sprite.current_animation = 'idle'
        canvas_sprite.current_frame = 0
        # Disable panning so _get_current_frame_pixels uses frame.get_pixel_data() instead
        canvas_sprite._panning_active = False

        # Set up parent_scene with selected_frame_visible = False
        parent_scene = mocker.Mock()
        parent_scene.selected_frame_visible = False
        canvas_sprite.parent_scene = parent_scene

        # Set up animated_sprite with frames
        mock_frame = mocker.Mock()
        mock_frame.get_pixel_data.return_value = [
            (100, 100, 100),
            (200, 200, 200),
            (50, 50, 50),
            (10, 10, 10),
        ]
        canvas_sprite.animated_sprite.frames = {'idle': [mock_frame]}

        renderer = AnimatedCanvasRenderer(canvas_sprite)

        # Mock internal methods
        mocker.patch.object(renderer, '_render_onion_layers')
        mock_draw_indicators = mocker.patch.object(renderer, '_draw_controller_indicators_only')
        mocker.patch.object(renderer, '_draw_hover_effects')

        renderer.force_redraw(canvas_sprite)

        mock_draw_indicators.assert_called_once()


class TestCanvasRendererOnionSkinRGBA:
    """Test onion skin RGBA pixel handling (lines 767-769)."""

    def test_render_onion_layer_rgba_pixels(self, mocker):
        """Test that RGBA pixels combine alpha with onion transparency.

        Covers lines 767-769 where a pixel has 4 components (RGBA)
        and the combined alpha is calculated.
        """
        # Need real width/height for pygame.Surface creation
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixels_across = 2
        canvas_sprite.pixels_tall = 2
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        canvas_sprite.width = 16  # 2 * 8
        canvas_sprite.height = 16  # 2 * 8
        canvas_sprite.image = pygame.Surface((16, 16), pygame.SRCALPHA)

        renderer = AnimatedCanvasRenderer(canvas_sprite)

        # Call _render_onion_frame with RGBA pixels
        frame_pixels = cast(
            'list[tuple[int, ...]]',
            [(255, 0, 0, 128), (0, 255, 0, 255), (0, 0, 255, 64), (255, 255, 0, 200)],
        )
        alpha = 128  # 50% onion transparency

        result = renderer._render_onion_frame(frame_pixels, alpha)

        # Should return a Surface
        assert isinstance(result, pygame.Surface)


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

        # Configure animated_sprite so AnimatedCanvasInterface.__init__ can subscript
        # _animation_order[0] without a TypeError (Mock objects are not subscriptable).
        # Also set .frames as a dict so _get_old_pixel_color can use 'in' operator on it.
        mock_frame = mocker.Mock()
        mock_frame.get_pixel_data.return_value = [(0, 0, 0)] * 16
        canvas_sprite.animated_sprite._animations = {'idle': [mock_frame]}
        canvas_sprite.animated_sprite._animation_order = ['idle']
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
