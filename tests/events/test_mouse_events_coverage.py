"""Coverage tests for glitchygames/events/mouse.py.

This module targets uncovered proxy/forwarding methods in MouseEventProxy,
MousePointer properties, and the collided_sprites helper function.
"""

import sys
from pathlib import Path

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from collections import UserDict

from glitchygames.events import HashableEvent
from glitchygames.events.mouse import (
    MOUSE_BUTTON_LEFT,
    MOUSE_BUTTON_RIGHT,
    MOUSE_BUTTON_WHEEL,
    MOUSE_WHEEL_SCROLL_DOWN,
    MOUSE_WHEEL_SCROLL_UP,
    MouseEventManager,
    MousePointer,
    collided_sprites,
)
from tests.mocks.test_mock_factory import MockFactory


class TestMouseEventProxyDropEvent:
    """Test MouseEventProxy.on_mouse_drop_event and button-specific drop handlers."""

    def test_drop_event_left_button_forwards_to_game(self, mock_pygame_patches, mocker):
        """Left-button drop should forward to game and call left-specific drop."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drop_event = mocker.Mock(return_value=True)
        scene.on_left_mouse_drag_up_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_BUTTON_LEFT)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_LEFT)
        proxy.on_mouse_drop_event(event, trigger)

        scene.on_mouse_drop_event.assert_called_once_with(event, trigger)
        scene.on_left_mouse_drag_up_event.assert_called_once_with(event, trigger)
        assert proxy.mouse_dropping is False

    def test_drop_event_middle_button_forwards_to_game(self, mock_pygame_patches, mocker):
        """Middle-button drop should forward to game and call middle-specific drop."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drop_event = mocker.Mock(return_value=True)
        scene.on_middle_mouse_drag_up_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_BUTTON_WHEEL)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_WHEEL)
        proxy.on_mouse_drop_event(event, trigger)

        scene.on_mouse_drop_event.assert_called_once_with(event, trigger)
        scene.on_middle_mouse_drag_up_event.assert_called_once_with(event, trigger)

    def test_drop_event_right_button_forwards_to_game(self, mock_pygame_patches, mocker):
        """Right-button drop should forward to game and call right-specific drop."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drop_event = mocker.Mock(return_value=True)
        scene.on_right_mouse_drag_up_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_BUTTON_RIGHT)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_RIGHT)
        proxy.on_mouse_drop_event(event, trigger)

        scene.on_mouse_drop_event.assert_called_once_with(event, trigger)
        scene.on_right_mouse_drag_up_event.assert_called_once_with(event, trigger)

    def test_drop_event_scroll_up_button_is_noop(self, mock_pygame_patches, mocker):
        """Scroll-up button drop should still forward generic drop but not crash."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drop_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_WHEEL_SCROLL_UP)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_WHEEL_SCROLL_UP)
        proxy.on_mouse_drop_event(event, trigger)

        scene.on_mouse_drop_event.assert_called_once_with(event, trigger)

    def test_drop_event_scroll_down_button_is_noop(self, mock_pygame_patches, mocker):
        """Scroll-down button drop should still forward generic drop but not crash."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drop_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_WHEEL_SCROLL_DOWN)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_WHEEL_SCROLL_DOWN)
        proxy.on_mouse_drop_event(event, trigger)

        scene.on_mouse_drop_event.assert_called_once_with(event, trigger)


class TestMouseEventProxyDragEvent:
    """Test MouseEventProxy.on_mouse_drag_event button routing."""

    def test_drag_event_left_button(self, mock_pygame_patches, mocker):
        """Left-button drag should forward to game and call left-specific drag."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drag_event = mocker.Mock(return_value=True)
        scene.on_left_mouse_drag_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 10), rel=(1, 1))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_LEFT)
        proxy.on_mouse_drag_event(event, trigger)

        scene.on_mouse_drag_event.assert_called_once_with(event, trigger)
        scene.on_left_mouse_drag_event.assert_called_once_with(event, trigger)

    def test_drag_event_middle_button(self, mock_pygame_patches, mocker):
        """Middle-button drag should forward to middle-specific drag."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drag_event = mocker.Mock(return_value=True)
        scene.on_middle_mouse_drag_down_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 10), rel=(1, 1))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_WHEEL)
        proxy.on_mouse_drag_event(event, trigger)

        scene.on_mouse_drag_event.assert_called_once_with(event, trigger)
        scene.on_middle_mouse_drag_down_event.assert_called_once_with(event, trigger)

    def test_drag_event_right_button(self, mock_pygame_patches, mocker):
        """Right-button drag should forward to right-specific drag."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drag_event = mocker.Mock(return_value=True)
        scene.on_right_mouse_drag_down_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 10), rel=(1, 1))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_RIGHT)
        proxy.on_mouse_drag_event(event, trigger)

        scene.on_mouse_drag_event.assert_called_once_with(event, trigger)
        scene.on_right_mouse_drag_down_event.assert_called_once_with(event, trigger)

    def test_drag_event_scroll_up_is_noop(self, mock_pygame_patches, mocker):
        """Scroll-up button drag should still forward generic drag."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drag_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 10), rel=(1, 1))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_WHEEL_SCROLL_UP)
        proxy.on_mouse_drag_event(event, trigger)

        scene.on_mouse_drag_event.assert_called_once_with(event, trigger)

    def test_drag_event_scroll_down_is_noop(self, mock_pygame_patches, mocker):
        """Scroll-down button drag should still forward generic drag."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drag_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 10), rel=(1, 1))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_WHEEL_SCROLL_DOWN)
        proxy.on_mouse_drag_event(event, trigger)

        scene.on_mouse_drag_event.assert_called_once_with(event, trigger)


class TestMouseEventProxyMotionWithCollision:
    """Test MouseEventProxy.on_mouse_motion_event with sprite collision."""

    def test_motion_with_collided_sprite_forwards_to_sprite(self, mock_pygame_patches, mocker):
        """When a sprite collides, motion event should be forwarded to the sprite."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_motion_event = mocker.Mock(return_value=True)

        mock_sprite = mocker.Mock()
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[mock_sprite])

        manager = MouseEventManager(game=scene)

        motion_event = HashableEvent(
            pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10), buttons=(0, 0, 0)
        )
        manager.on_mouse_motion_event(motion_event)

        scene.on_mouse_motion_event.assert_called_once_with(motion_event)
        mock_sprite.on_mouse_motion_event.assert_called_once_with(motion_event)

    def test_motion_runtime_error_in_mouse_state_iteration(self, mock_pygame_patches, mocker):
        """RuntimeError during mouse_state iteration should be caught gracefully."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_motion_event = mocker.Mock(return_value=True)
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        # Use a custom dict that raises RuntimeError on values() to simulate
        # the "dictionary changed size during iteration" RuntimeError path.
        class RaisingDict(UserDict):
            """Dict subclass that raises RuntimeError on first values() call."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._raise_on_values = True

            def values(self):
                if self._raise_on_values:
                    self._raise_on_values = False
                    raise RuntimeError('dictionary changed size during iteration')
                return super().values()

        proxy.mouse_state = RaisingDict()

        motion_event = HashableEvent(
            pygame.MOUSEMOTION, pos=(50, 50), rel=(5, 5), buttons=(0, 0, 0)
        )
        # Should not raise
        proxy.on_mouse_motion_event(motion_event)

        scene.on_mouse_motion_event.assert_called_once_with(motion_event)


class TestMouseEventProxyButtonUpScrollWheel:
    """Test scroll-wheel pass-through on button up events."""

    def test_button_up_scroll_up_passes(self, mock_pygame_patches, mocker):
        """Button up with scroll-up button should pass without error."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_button_up_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(0, 0), button=MOUSE_WHEEL_SCROLL_UP)
        manager.on_mouse_button_up_event(event)

        scene.on_mouse_button_up_event.assert_called_once_with(event)

    def test_button_up_scroll_down_passes(self, mock_pygame_patches, mocker):
        """Button up with scroll-down button should pass without error."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_button_up_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(0, 0), button=MOUSE_WHEEL_SCROLL_DOWN)
        manager.on_mouse_button_up_event(event)

        scene.on_mouse_button_up_event.assert_called_once_with(event)


class TestMouseEventProxyButtonDownRuntimeError:
    """Test RuntimeError handling during on_mouse_button_down_event."""

    def test_button_down_runtime_error_in_state_keys(self, mock_pygame_patches, mocker):
        """RuntimeError when listing mouse_state keys should be caught."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_button_down_event = mocker.Mock(return_value=True)
        scene.on_left_mouse_button_down_event = mocker.Mock(return_value=True)
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        # Use a custom dict that raises RuntimeError on keys()
        class RaisingDict(UserDict):
            """Dict subclass that raises RuntimeError on first keys() call."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._raise_on_keys = True

            def keys(self):
                if self._raise_on_keys:
                    self._raise_on_keys = False
                    raise RuntimeError('dictionary changed size during iteration')
                return super().keys()

        proxy.mouse_state = RaisingDict()

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=MOUSE_BUTTON_LEFT)
        # Should not raise
        proxy.on_mouse_button_down_event(event)

        scene.on_mouse_button_down_event.assert_called_once_with(event)


class TestMouseEventProxyLeftButtonDownRuntimeError:
    """Test RuntimeError handling during on_left_mouse_button_down_event."""

    def test_left_button_down_runtime_error_in_state_keys(self, mock_pygame_patches, mocker):
        """RuntimeError when listing mouse_state keys should be caught."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_left_mouse_button_down_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        # Use a custom dict that raises RuntimeError on keys()
        class RaisingDict(UserDict):
            """Dict subclass that raises RuntimeError on first keys() call."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._raise_on_keys = True

            def keys(self):
                if self._raise_on_keys:
                    self._raise_on_keys = False
                    raise RuntimeError('dictionary changed size during iteration')
                return super().keys()

        proxy.mouse_state = RaisingDict()

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=MOUSE_BUTTON_LEFT)
        # Should not raise
        proxy.on_left_mouse_button_down_event(event)

        scene.on_left_mouse_button_down_event.assert_called_once_with(event)


class TestMouseEventProxyMiddleButtonHandlers:
    """Test middle button up and down handlers."""

    def test_middle_mouse_button_up_forwards_to_game(self, mock_pygame_patches, mocker):
        """Middle button up should forward to game."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_middle_mouse_button_up_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_BUTTON_WHEEL)
        proxy.on_middle_mouse_button_up_event(event)

        scene.on_middle_mouse_button_up_event.assert_called_once_with(event)

    def test_middle_mouse_button_down_forwards_to_game(self, mock_pygame_patches, mocker):
        """Middle button down should forward to game."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_middle_mouse_button_down_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=MOUSE_BUTTON_WHEEL)
        proxy.on_middle_mouse_button_down_event(event)

        scene.on_middle_mouse_button_down_event.assert_called_once_with(event)


class TestMouseEventProxyRightButtonHandlers:
    """Test right button up and down handlers."""

    def test_right_mouse_button_up_forwards_to_game(self, mock_pygame_patches, mocker):
        """Right button up should forward to game."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_right_mouse_button_up_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_BUTTON_RIGHT)
        proxy.on_right_mouse_button_up_event(event)

        scene.on_right_mouse_button_up_event.assert_called_once_with(event)

    def test_right_mouse_button_down_forwards_to_game(self, mock_pygame_patches, mocker):
        """Right button down should forward to game."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_right_mouse_button_down_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=MOUSE_BUTTON_RIGHT)
        proxy.on_right_mouse_button_down_event(event)

        scene.on_right_mouse_button_down_event.assert_called_once_with(event)


class TestMousePointerProperties:
    """Test MousePointer x and y properties."""

    def test_mouse_pointer_x_getter(self, mock_pygame_patches):
        """MousePointer.x should return the x coordinate from pos."""
        pointer = MousePointer(pos=(50, 75))
        assert pointer.x == 50

    def test_mouse_pointer_x_setter(self, mock_pygame_patches):
        """MousePointer.x setter should update the x coordinate in pos."""
        pointer = MousePointer(pos=(50, 75))
        pointer.x = 100
        assert pointer.pos[0] == 100
        assert pointer.x == 100

    def test_mouse_pointer_y_getter(self, mock_pygame_patches):
        """MousePointer.y should return the y coordinate from pos."""
        pointer = MousePointer(pos=(50, 75))
        assert pointer.y == 75

    def test_mouse_pointer_y_setter(self, mock_pygame_patches):
        """MousePointer.y setter should update the y coordinate in pos."""
        pointer = MousePointer(pos=(50, 75))
        pointer.y = 200
        assert pointer.pos[1] == 200
        assert pointer.y == 200


class TestCollisionHelper:
    """Test the collided_sprites helper function."""

    def test_collided_sprites_with_no_collisions(self, mock_pygame_patches, mocker):
        """collided_sprites should return empty list when no sprites collide."""
        scene = mocker.Mock()
        scene.all_sprites = mocker.Mock()
        mocker.patch('glitchygames.events.mouse.pygame.sprite.spritecollide', return_value=[])

        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(0, 0))
        result = collided_sprites(scene, event=event, index=-1)

        assert result == []

    def test_collided_sprites_with_collisions_and_index(self, mock_pygame_patches, mocker):
        """collided_sprites with index should return list with single sprite."""
        mock_sprite_a = mocker.Mock()
        mock_sprite_b = mocker.Mock()
        scene = mocker.Mock()
        scene.all_sprites = mocker.Mock()
        mocker.patch(
            'glitchygames.events.mouse.pygame.sprite.spritecollide',
            return_value=[mock_sprite_a, mock_sprite_b],
        )

        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(0, 0))
        result = collided_sprites(scene, event=event, index=-1)

        assert result == [mock_sprite_b]

    def test_collided_sprites_with_collisions_no_index(self, mock_pygame_patches, mocker):
        """collided_sprites with index=None should return the full list."""
        mock_sprite_a = mocker.Mock()
        mock_sprite_b = mocker.Mock()
        scene = mocker.Mock()
        scene.all_sprites = mocker.Mock()
        mocker.patch(
            'glitchygames.events.mouse.pygame.sprite.spritecollide',
            return_value=[mock_sprite_a, mock_sprite_b],
        )

        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(0, 0))
        result = collided_sprites(scene, event=event, index=None)

        assert result == [mock_sprite_a, mock_sprite_b]
