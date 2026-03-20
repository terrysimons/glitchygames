"""Deeper coverage tests for glitchygames/tools/canvas_interfaces.py.

Targets uncovered areas NOT covered by test_canvas_interfaces_coverage.py:
- AnimatedCanvasInterface.get_pixel_at with animated sprite and frame data
- AnimatedCanvasInterface._get_old_pixel_color with animated sprite
- AnimatedCanvasInterface._collect_pixel_change (deduplication and timer)
- AnimatedCanvasInterface._update_frame_pixel_data with animated sprite
- AnimatedCanvasInterface.set_pixel_at full path (not skip_drag_ops)
- AnimatedCanvasInterface._should_track_color_change with operation tracker
- AnimatedCanvasRenderer render, force_redraw, get_pixel_size
- StaticCanvasInterface load returns None
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


class TestAnimatedCanvasInterfaceGetPixelAtAnimated:
    """Test AnimatedCanvasInterface.get_pixel_at with animated sprite frames."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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
            0: {'active': True, 'pixels_drawn': [(1, 2, RED, GREEN)]}
        }
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface.set_pixel_at(0, 0, RED)
        # Should still update pixel data even with drag active
        assert canvas_sprite.pixels[0] == RED


class TestAnimatedCanvasInterfaceShouldTrackWithTracker:
    """Test _should_track_color_change with canvas_operation_tracker."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_collect_first_pixel_change_starts_timer(self, mocker):
        """Test collecting first pixel change starts a timer."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene._current_pixel_changes = []
        canvas_sprite.parent_scene._current_pixel_changes_dict = {}
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface._collect_pixel_change(0, 0, MAGENTA, RED)

        assert (0, 0) in canvas_sprite.parent_scene._current_pixel_changes_dict
        assert hasattr(canvas_sprite.parent_scene, '_pixel_change_timer')

    def test_collect_duplicate_pixel_updates_existing(self, mocker):
        """Test collecting same pixel again updates new_color, keeps old_color."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.parent_scene._current_pixel_changes = []
        canvas_sprite.parent_scene._current_pixel_changes_dict = {
            (0, 0): (0, 0, MAGENTA, RED),
        }
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface._collect_pixel_change(0, 0, RED, GREEN)

        entry = canvas_sprite.parent_scene._current_pixel_changes_dict[0, 0]
        # Original old_color (MAGENTA) should be preserved, new_color updated to GREEN
        assert entry == (0, 0, MAGENTA, GREEN)

    def test_collect_initializes_tracking_structures(self, mocker):
        """Test _collect_pixel_change initializes structures if missing."""
        canvas_sprite = mocker.Mock(spec=[])
        canvas_sprite.parent_scene = mocker.Mock(spec=[])
        del canvas_sprite.animated_sprite

        interface = AnimatedCanvasInterface(canvas_sprite)
        interface._collect_pixel_change(1, 1, MAGENTA, BLUE)

        assert hasattr(canvas_sprite.parent_scene, '_current_pixel_changes')
        assert hasattr(canvas_sprite.parent_scene, '_current_pixel_changes_dict')


class TestAnimatedCanvasRendererMethods:
    """Test AnimatedCanvasRenderer render and force_redraw methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_delegates_to_force_redraw(self, mocker):
        """Test render calls force_redraw."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.width = CANVAS_SIZE * 8
        canvas_sprite.height = CANVAS_SIZE * 8
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.image = pygame.Surface((CANVAS_SIZE * 8, CANVAS_SIZE * 8))
        del canvas_sprite.animated_sprite

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        mocker.patch.object(renderer, '_redraw_static_pixels')
        mocker.patch.object(renderer, '_draw_hover_effects')

        result = renderer.render(canvas_sprite)
        assert result is canvas_sprite.image

    def test_force_redraw_static_fallback(self, mocker):
        """Test force_redraw falls back to static rendering."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.width = CANVAS_SIZE * 8
        canvas_sprite.height = CANVAS_SIZE * 8
        canvas_sprite.pixels_across = CANVAS_SIZE
        canvas_sprite.pixels_tall = CANVAS_SIZE
        canvas_sprite.pixels = [MAGENTA] * PIXEL_COUNT
        canvas_sprite.image = pygame.Surface((CANVAS_SIZE * 8, CANVAS_SIZE * 8))
        del canvas_sprite.animated_sprite

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        mocker.patch.object(renderer, '_redraw_static_pixels')
        mocker.patch.object(renderer, '_draw_hover_effects')

        result = renderer.force_redraw(canvas_sprite)
        renderer._redraw_static_pixels.assert_called_once()  # type: ignore[unresolved-attribute]
        assert result is canvas_sprite.image

    def test_get_pixel_size_returns_tuple(self, mocker):
        """Test get_pixel_size returns pixel dimensions."""
        canvas_sprite = mocker.Mock()
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        del canvas_sprite.animated_sprite

        renderer = AnimatedCanvasRenderer(canvas_sprite)
        result = renderer.get_pixel_size()
        assert result == (8, 8)
