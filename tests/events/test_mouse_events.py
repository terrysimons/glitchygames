"""Tests for mouse event functionality.

This module combines tests for:
- MouseEventProxy forwarding/delegation (drop, drag, motion, button handlers)
- MousePointer properties
- collided_sprites helper
- MouseEventManager initialization and routing
- MouseEvents interface and MouseEventStubs
"""

import argparse
import sys
from collections import UserDict
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    MouseEvents,
    MouseEventStubs,
    UnhandledEventError,
)
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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_game(mocker):
    """Create a mock game object with all required event handlers."""
    game = mocker.Mock()
    game.all_sprites = pygame.sprite.Group()
    return game


# ---------------------------------------------------------------------------
# MouseEvents interface tests (from test_events_mouse_events.py)
# ---------------------------------------------------------------------------


class TestMouseEventsInterface:
    """Test MouseEvents interface functionality."""

    def test_mouse_events_interface(self, mock_pygame_patches):
        """Test MouseEvents interface methods."""
        # Test that MouseEvents has required abstract methods
        assert hasattr(MouseEvents, 'on_mouse_motion_event')
        assert hasattr(MouseEvents, 'on_mouse_drag_event')
        assert hasattr(MouseEvents, 'on_mouse_drop_event')
        assert hasattr(MouseEvents, 'on_left_mouse_drag_event')
        assert hasattr(MouseEvents, 'on_left_mouse_drop_event')
        assert hasattr(MouseEvents, 'on_middle_mouse_drag_event')
        assert hasattr(MouseEvents, 'on_middle_mouse_drop_event')
        assert hasattr(MouseEvents, 'on_right_mouse_drag_event')
        assert hasattr(MouseEvents, 'on_right_mouse_drop_event')
        assert hasattr(MouseEvents, 'on_mouse_button_down_event')
        assert hasattr(MouseEvents, 'on_mouse_button_up_event')
        assert hasattr(MouseEvents, 'on_mouse_wheel_event')

    def test_mouse_event_stubs_implementation(self, mock_pygame_patches, mocker):
        """Test MouseEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = MouseEventStubs()
        assert hasattr(stub, 'on_mouse_motion_event')
        assert hasattr(stub, 'on_mouse_drag_event')
        assert hasattr(stub, 'on_mouse_drop_event')
        assert hasattr(stub, 'on_mouse_button_down_event')
        assert hasattr(stub, 'on_mouse_button_up_event')
        assert hasattr(stub, 'on_mouse_wheel_event')

        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_motion_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_mouse_button_down_event(self, mock_pygame_patches):
        """Test mouse button down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_mouse_button_down_event': lambda event: (
                    scene.mouse_events_received.append(event) or True
                ),
            },
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
        result = scene.on_mouse_button_down_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.mouse_events_received) == 1
        assert scene.mouse_events_received[0].button == 1

    def test_mouse_button_up_event(self, mock_pygame_patches):
        """Test mouse button up event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_mouse_button_up_event': lambda event: (
                    scene.mouse_events_received.append(event) or True
                ),
            },
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        result = scene.on_mouse_button_up_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.mouse_events_received) == 1
        assert scene.mouse_events_received[0].button == 1

    def test_mouse_motion_event(self, mock_pygame_patches):
        """Test mouse motion event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_mouse_motion_event': lambda event: (
                    scene.mouse_events_received.append(event) or True
                ),
            },
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        result = scene.on_mouse_motion_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.mouse_events_received) == 1
        assert scene.mouse_events_received[0].pos == (100, 100)

    def test_mouse_wheel_event(self, mock_pygame_patches, mocker):
        """Test mouse wheel event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test mouse wheel
        event = HashableEvent(pygame.MOUSEWHEEL, x=0, y=1)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_wheel_event(event)
        # Exception was raised as expected

    def test_mouse_drag_event(self, mock_pygame_patches, mocker):
        """Test mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_drag_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_mouse_drop_event(self, mock_pygame_patches, mocker):
        """Test mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_drop_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_left_mouse_drag_event(self, mock_pygame_patches, mocker):
        """Test left mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test left mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_left_mouse_drag_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_left_mouse_drop_event(self, mock_pygame_patches, mocker):
        """Test left mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test left mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_left_mouse_drop_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_middle_mouse_drag_event(self, mock_pygame_patches, mocker):
        """Test middle mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test middle mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_middle_mouse_drag_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_middle_mouse_drop_event(self, mock_pygame_patches, mocker):
        """Test middle mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test middle mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=2, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_middle_mouse_drop_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_right_mouse_drag_event(self, mock_pygame_patches, mocker):
        """Test right mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test right mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_right_mouse_drag_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_right_mouse_drop_event(self, mock_pygame_patches, mocker):
        """Test right mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test right mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=3, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_right_mouse_drop_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def _setup_mock_game_for_stub(self, stub):
        """Set up mock game object for event stubs.

        Returns:
            object: The result.

        """
        scene_mock = MockFactory.create_event_test_scene_mock(
            options={'debug_events': False, 'no_unhandled_events': True},
        )
        stub.options = scene_mock.options
        return scene_mock


# ---------------------------------------------------------------------------
# MousePointer tests (from test_mouse_events_coverage.py + test_mouse_events_manager_coverage.py)
# ---------------------------------------------------------------------------


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


class TestMousePointerInit:
    """Test MousePointer initialization."""

    def test_init(self):
        pointer = MousePointer(pos=(100, 200))
        assert pointer.x == 100
        assert pointer.y == 200

    def test_init_with_size(self):
        pointer = MousePointer(pos=(50, 75), size=(2, 2))
        assert pointer.size == (2, 2)

    def test_x_property(self):
        pointer = MousePointer(pos=(100, 200))
        assert pointer.x == 100

    def test_x_setter(self):
        pointer = MousePointer(pos=(100, 200))
        pointer.x = 300
        assert pointer.x == 300
        assert pointer.pos[0] == 300

    def test_y_property(self):
        pointer = MousePointer(pos=(100, 200))
        assert pointer.y == 200

    def test_y_setter(self):
        pointer = MousePointer(pos=(100, 200))
        pointer.y = 400
        assert pointer.y == 400
        assert pointer.pos[1] == 400

    def test_rect_created(self):
        pointer = MousePointer(pos=(10, 20))
        assert pointer.rect is not None
        assert isinstance(pointer.rect, pygame.Rect)
        assert pointer.rect.x == 10
        assert pointer.rect.y == 20


# ---------------------------------------------------------------------------
# collided_sprites helper tests
# (from test_mouse_events_coverage.py + test_mouse_events_manager_coverage.py)
# ---------------------------------------------------------------------------


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


class TestCollidedSpritesNoCollision:
    """Test collided_sprites function with no collision."""

    def test_no_collision(self, mock_game):
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 200))
        result = collided_sprites(mock_game, event)
        assert result == []


# ---------------------------------------------------------------------------
# MouseEventProxy drop event tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# MouseEventProxy drag event tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# MouseEventProxy motion with collision tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


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
            pygame.MOUSEMOTION,
            pos=(100, 100),
            rel=(10, 10),
            buttons=(0, 0, 0),
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
                    msg = 'dictionary changed size during iteration'
                    raise RuntimeError(msg)
                return super().values()

        proxy.mouse_state = RaisingDict()

        motion_event = HashableEvent(
            pygame.MOUSEMOTION,
            pos=(50, 50),
            rel=(5, 5),
            buttons=(0, 0, 0),
        )
        # Should not raise
        proxy.on_mouse_motion_event(motion_event)

        scene.on_mouse_motion_event.assert_called_once_with(motion_event)


# ---------------------------------------------------------------------------
# MouseEventProxy button up scroll wheel tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# MouseEventProxy RuntimeError handling tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


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
                    msg = 'dictionary changed size during iteration'
                    raise RuntimeError(msg)
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
                    msg = 'dictionary changed size during iteration'
                    raise RuntimeError(msg)
                return super().keys()

        proxy.mouse_state = RaisingDict()

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=MOUSE_BUTTON_LEFT)
        # Should not raise
        proxy.on_left_mouse_button_down_event(event)

        scene.on_left_mouse_button_down_event.assert_called_once_with(event)


# ---------------------------------------------------------------------------
# MouseEventProxy button handler tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# MouseEventProxy delegation tests (from test_mouse_events_manager_coverage.py)
# ---------------------------------------------------------------------------


class TestMouseEventProxyDelegation:
    """Test MouseEventProxy event delegation."""

    def test_proxy_init(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        assert proxy.game is mock_game
        assert proxy.mouse_dragging is False
        assert proxy.mouse_dropping is False
        assert proxy.current_focus is None
        assert proxy.previous_focus is None

    def test_on_mouse_button_down_left(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_BUTTON_LEFT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        mock_game.on_mouse_button_down_event.assert_called_once()
        mock_game.on_left_mouse_button_down_event.assert_called_once()

    def test_on_mouse_button_down_right(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_BUTTON_RIGHT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        mock_game.on_right_mouse_button_down_event.assert_called_once()

    def test_on_mouse_button_down_middle(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_BUTTON_WHEEL,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        mock_game.on_middle_mouse_button_down_event.assert_called_once()

    def test_on_mouse_button_down_scroll_up(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_WHEEL_SCROLL_UP,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        mock_game.on_mouse_scroll_down_event.assert_called_once()

    def test_on_mouse_button_down_scroll_down(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_WHEEL_SCROLL_DOWN,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        mock_game.on_mouse_scroll_up_event.assert_called_once()

    def test_on_mouse_button_up_left(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_LEFT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        mock_game.on_left_mouse_button_up_event.assert_called_once()
        mock_game.on_mouse_button_up_event.assert_called_once()

    def test_on_mouse_button_up_right(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_RIGHT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        mock_game.on_right_mouse_button_up_event.assert_called_once()

    def test_on_mouse_button_up_middle(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_WHEEL,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        mock_game.on_middle_mouse_button_up_event.assert_called_once()

    def test_on_mouse_button_up_triggers_drop_if_dragging(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        proxy.mouse_dragging = True
        event = HashableEvent(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_LEFT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        mock_game.on_mouse_drop_event.assert_called_once()
        assert proxy.mouse_dragging is False

    def test_on_mouse_wheel_event(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(pygame.MOUSEWHEEL, x=0, y=1)
        proxy.on_mouse_wheel_event(event)
        mock_game.on_mouse_wheel_event.assert_called_once()

    def test_on_mouse_drag_event_left(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        motion_event = HashableEvent(
            pygame.MOUSEMOTION,
            pos=(150, 250),
            rel=(5, 5),
            buttons=(1, 0, 0),
        )
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_LEFT, pos=(100, 200))
        proxy.on_mouse_drag_event(motion_event, trigger)
        mock_game.on_mouse_drag_event.assert_called_once()
        mock_game.on_left_mouse_drag_event.assert_called_once()

    def test_on_mouse_drag_event_right(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        motion_event = HashableEvent(
            pygame.MOUSEMOTION,
            pos=(150, 250),
            rel=(5, 5),
            buttons=(0, 0, 1),
        )
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_RIGHT, pos=(100, 200))
        proxy.on_mouse_drag_event(motion_event, trigger)
        mock_game.on_right_mouse_drag_down_event.assert_called_once()

    def test_on_mouse_drag_event_middle(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        motion_event = HashableEvent(
            pygame.MOUSEMOTION,
            pos=(150, 250),
            rel=(5, 5),
            buttons=(0, 1, 0),
        )
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_WHEEL, pos=(100, 200))
        proxy.on_mouse_drag_event(motion_event, trigger)
        mock_game.on_middle_mouse_drag_down_event.assert_called_once()

    def test_on_mouse_drop_event_left(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=MOUSE_BUTTON_LEFT, pos=(100, 200))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_LEFT, pos=(90, 190))
        proxy.on_mouse_drop_event(event, trigger)
        mock_game.on_mouse_drop_event.assert_called_once()
        mock_game.on_left_mouse_drag_up_event.assert_called_once()
        assert proxy.mouse_dropping is False

    def test_on_mouse_drop_event_right(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=MOUSE_BUTTON_RIGHT, pos=(100, 200))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_RIGHT, pos=(90, 190))
        proxy.on_mouse_drop_event(event, trigger)
        mock_game.on_right_mouse_drag_up_event.assert_called_once()

    def test_on_mouse_drop_event_middle(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=MOUSE_BUTTON_WHEEL, pos=(100, 200))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_WHEEL, pos=(90, 190))
        proxy.on_mouse_drop_event(event, trigger)
        mock_game.on_middle_mouse_drag_up_event.assert_called_once()

    def test_on_mouse_focus_event(self, mock_game, mocker):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 200), rel=(1, 1), buttons=(0, 0, 0))
        mock_sprite = mocker.Mock()
        proxy.on_mouse_focus_event(event, mock_sprite)
        assert proxy.current_focus is mock_sprite

    def test_on_mouse_unfocus_event(self, mock_game, mocker):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 200), rel=(1, 1), buttons=(0, 0, 0))
        mock_sprite = mocker.Mock()
        proxy.current_focus = mock_sprite
        proxy.on_mouse_unfocus_event(event, mock_sprite)
        assert proxy.current_focus is None
        assert proxy.previous_focus is mock_sprite

    def test_on_mouse_unfocus_event_none(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 200), rel=(1, 1), buttons=(0, 0, 0))
        proxy.on_mouse_unfocus_event(event, None)
        assert proxy.previous_focus is None


# ---------------------------------------------------------------------------
# MouseEventManager tests (from test_mouse_events_manager_coverage.py)
# ---------------------------------------------------------------------------


class TestMouseEventManagerInit:
    """Test MouseEventManager initialization."""

    def test_init(self, mock_game):
        manager = MouseEventManager(game=mock_game)
        assert len(manager.proxies) == 1

    def test_args(self):
        parser = argparse.ArgumentParser()
        result = MouseEventManager.args(parser)
        assert result is parser


# ---------------------------------------------------------------------------
# MouseEventManager routing tests (from test_events_mouse_events.py)
# ---------------------------------------------------------------------------


class TestMouseEventManagerRouting:
    """Test MouseEventManager in isolation."""

    def test_mouse_manager_initialization(self, mock_pygame_patches, mocker):
        """Test MouseEventManager initializes correctly."""
        mock_game = mocker.Mock()
        manager = MouseEventManager(game=mock_game)

        assert manager.game == mock_game
        assert hasattr(manager, 'on_mouse_motion_event')
        assert hasattr(manager, 'on_mouse_button_down_event')

    def test_mouse_manager_events(self, mock_pygame_patches, mocker):
        """Test mouse event handling through manager."""
        # Create a proper scene mock with all_sprites that's iterable
        scene_mock = MockFactory.create_event_test_scene_mock()

        # Create a mock sprite group that's iterable
        mock_sprites = [mocker.Mock(), mocker.Mock(), mocker.Mock()]
        scene_mock.all_sprites = mock_sprites

        # Mock the scene's event handlers to prevent infinite loops
        scene_mock.on_mouse_motion_event = mocker.Mock()
        scene_mock.on_mouse_button_down_event = mocker.Mock()
        scene_mock.on_mouse_button_up_event = mocker.Mock()

        # self.game IS the scene, so we pass the scene directly
        manager = MouseEventManager(game=scene_mock)

        # Mock collided_sprites to prevent pygame.sprite.spritecollide calls
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])

        # Test mouse motion - use mocker.patch.object to prevent recursive calls
        mock_handler = mocker.patch.object(scene_mock, 'on_mouse_motion_event')
        motion_event = HashableEvent(
            pygame.MOUSEMOTION,
            pos=(100, 100),
            rel=(10, 10),
            buttons=(0, 0, 0),
        )
        manager.on_mouse_motion_event(motion_event)
        mock_handler.assert_called_once_with(motion_event)

        # Test mouse button down
        mock_handler = mocker.patch.object(scene_mock, 'on_mouse_button_down_event')
        down_event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 100), button=1)
        manager.on_mouse_button_down_event(down_event)
        mock_handler.assert_called_once_with(down_event)

        # Test mouse button up
        mock_handler = mocker.patch.object(scene_mock, 'on_mouse_button_up_event')
        up_event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(100, 100), button=1)
        manager.on_mouse_button_up_event(up_event)
        mock_handler.assert_called_once_with(up_event)

    def test_mouse_down_order_generic_then_specific(self, mock_pygame_patches, mocker):
        """Left down should call generic scene handler first, then left-specific."""
        scene = MockFactory.create_event_test_scene_mock()
        call_order = []

        def left_down(event):
            call_order.append('left')
            return True

        def generic_down(event):
            call_order.append('generic')
            return True

        scene.on_left_mouse_button_down_event = left_down
        scene.on_mouse_button_down_event = generic_down

        manager = MouseEventManager(game=scene)

        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1)
        manager.on_mouse_button_down_event(event)

        assert call_order == ['generic', 'left']

    def test_mouse_up_order_specific_then_generic(self, mock_pygame_patches, mocker):
        """Left up should call left-specific then generic scene handler."""
        scene = MockFactory.create_event_test_scene_mock()
        call_order = []

        def left_up(event):
            call_order.append('left')
            return True

        def generic_up(event):
            call_order.append('generic')
            return True

        scene.on_left_mouse_button_up_event = left_up
        scene.on_mouse_button_up_event = generic_up

        manager = MouseEventManager(game=scene)

        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])
        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=1)
        manager.on_mouse_button_up_event(event)

        assert call_order == ['left', 'generic']

    def test_right_button_down_routes_to_right_specific(self, mock_pygame_patches, mocker):
        """Right button down should hit right-specific, not middle."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_right_mouse_button_down_event = mocker.Mock(return_value=True)
        scene.on_middle_mouse_button_down_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)

        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=3)
        manager.on_mouse_button_down_event(event)

        scene.on_right_mouse_button_down_event.assert_called_once()
        scene.on_middle_mouse_button_down_event.assert_not_called()

    def test_middle_mouse_down_up_order_generic_then_specific(self, mock_pygame_patches, mocker):
        """Middle button down: generic then specific; up: specific then generic."""
        scene = MockFactory.create_event_test_scene_mock()
        down_order, up_order = [], []

        scene.on_middle_mouse_button_down_event = lambda e: down_order.append('middle') or True
        scene.on_mouse_button_down_event = lambda e: down_order.append('generic') or True
        scene.on_middle_mouse_button_up_event = lambda e: up_order.append('middle') or True
        scene.on_mouse_button_up_event = lambda e: up_order.append('generic') or True

        manager = MouseEventManager(game=scene)
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])
        md = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(1, 1), button=2)
        mu = HashableEvent(pygame.MOUSEBUTTONUP, pos=(1, 1), button=2)
        manager.on_mouse_button_down_event(md)
        manager.on_mouse_button_up_event(mu)

        assert down_order == ['generic', 'middle']
        assert up_order == ['middle', 'generic']

    def test_right_mouse_up_order_specific_then_generic(self, mock_pygame_patches, mocker):
        """Right button up should be specific then generic."""
        scene = MockFactory.create_event_test_scene_mock()
        order = []

        scene.on_right_mouse_button_up_event = lambda e: order.append('right') or True
        scene.on_mouse_button_up_event = lambda e: order.append('generic') or True

        manager = MouseEventManager(game=scene)
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])
        mu = HashableEvent(pygame.MOUSEBUTTONUP, pos=(2, 2), button=3)
        manager.on_mouse_button_up_event(mu)

        assert order == ['right', 'generic']

    def test_right_mouse_down_order_generic_then_specific(self, mock_pygame_patches, mocker):
        """Right button down should be generic then specific."""
        scene = MockFactory.create_event_test_scene_mock()
        order = []

        scene.on_right_mouse_button_down_event = lambda e: order.append('right') or True
        scene.on_mouse_button_down_event = lambda e: order.append('generic') or True

        manager = MouseEventManager(game=scene)
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])
        md = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(3, 3), button=3)
        manager.on_mouse_button_down_event(md)

        assert order == ['generic', 'right']

    def test_drag_drop_lifecycle_middle(self, mock_pygame_patches, mocker):
        """Middle button drag/drop lifecycle triggers generic drag/drop."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drag_event = mocker.Mock(return_value=True)
        scene.on_mouse_drop_event = mocker.Mock(return_value=True)
        scene.on_middle_mouse_button_down_event = mocker.Mock(return_value=True)
        scene.on_middle_mouse_button_up_event = mocker.Mock(return_value=True)
        scene.on_mouse_button_down_event = mocker.Mock(return_value=True)
        scene.on_mouse_button_up_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])
        down = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=2)
        motion = HashableEvent(pygame.MOUSEMOTION, pos=(6, 6), rel=(1, 1), buttons=(0, 1, 0))
        up = HashableEvent(pygame.MOUSEBUTTONUP, pos=(7, 7), button=2)
        manager.on_mouse_button_down_event(down)
        manager.on_mouse_motion_event(motion)
        manager.on_mouse_button_up_event(up)

        scene.on_middle_mouse_button_down_event.assert_called_once()
        scene.on_middle_mouse_button_up_event.assert_called_once()
        scene.on_mouse_drag_event.assert_called()
        scene.on_mouse_drop_event.assert_called()

    def test_drag_drop_lifecycle_right(self, mock_pygame_patches, mocker):
        """Right button drag/drop lifecycle triggers generic drag/drop."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drag_event = mocker.Mock(return_value=True)
        scene.on_mouse_drop_event = mocker.Mock(return_value=True)
        scene.on_right_mouse_button_down_event = mocker.Mock(return_value=True)
        scene.on_right_mouse_button_up_event = mocker.Mock(return_value=True)
        scene.on_mouse_button_down_event = mocker.Mock(return_value=True)
        scene.on_mouse_button_up_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])
        down = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=3)
        motion = HashableEvent(pygame.MOUSEMOTION, pos=(6, 6), rel=(1, 1), buttons=(0, 0, 1))
        up = HashableEvent(pygame.MOUSEBUTTONUP, pos=(7, 7), button=3)
        manager.on_mouse_button_down_event(down)
        manager.on_mouse_motion_event(motion)
        manager.on_mouse_button_up_event(up)

        scene.on_right_mouse_button_down_event.assert_called_once()
        scene.on_right_mouse_button_up_event.assert_called_once()
        scene.on_mouse_drag_event.assert_called()
        scene.on_mouse_drop_event.assert_called()

    def test_button4_5_scroll_mapping_on_mousedown(self, mock_pygame_patches, mocker):
        """Legacy scroll buttons 4/5 should route to scroll up/down handlers."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_scroll_up_event = mocker.Mock(return_value=True)
        scene.on_mouse_scroll_down_event = mocker.Mock(return_value=True)
        scene.on_mouse_button_down_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])
        btn4 = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=4)
        btn5 = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=5)
        manager.on_mouse_button_down_event(btn4)
        manager.on_mouse_button_down_event(btn5)

        # button 4 maps to scroll down in code
        scene.on_mouse_scroll_down_event.assert_called_once()
        # button 5 maps to scroll up in code
        scene.on_mouse_scroll_up_event.assert_called_once()

    def test_focus_enter_unfocus_sequence_updates_state(self, mock_pygame_patches, mocker):
        """Entering focus should unfocus old, set current to new, and call handlers."""
        scene = MockFactory.create_event_test_scene_mock()
        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        old_target = mocker.Mock()
        new_target = mocker.Mock()

        # Seed current focus
        proxy.current_focus = old_target
        event = HashableEvent(pygame.MOUSEMOTION, pos=(0, 0), rel=(0, 0))

        proxy.on_mouse_focus_event(event, entering_focus=new_target)

        # Old target should get unfocus
        old_target.on_mouse_unfocus_event.assert_called_once_with(event)
        # New target should get focus with current_focus passed
        new_target.on_mouse_focus_event.assert_called_once()
        # State updated
        assert proxy.current_focus is new_target
        assert proxy.previous_focus is old_target

    def test_unfocus_clears_current_and_sets_previous(self, mock_pygame_patches, mocker):
        """Unfocus should call target unfocus, clear current, and record previous."""
        scene = MockFactory.create_event_test_scene_mock()
        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        target = mocker.Mock()
        proxy.current_focus = target
        event = HashableEvent(pygame.MOUSEMOTION, pos=(0, 0), rel=(0, 0))

        proxy.on_mouse_unfocus_event(event, leaving_focus=target)

        target.on_mouse_unfocus_event.assert_called_once_with(event)
        assert proxy.current_focus is None
        assert proxy.previous_focus is target

    def test_unfocus_no_target_is_noop(self, mock_pygame_patches):
        """Unfocus with None should not crash or change state significantly."""
        scene = MockFactory.create_event_test_scene_mock()
        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        proxy.current_focus = None
        event = HashableEvent(pygame.MOUSEMOTION, pos=(0, 0), rel=(0, 0))

        # Should not raise
        proxy.on_mouse_unfocus_event(event, leaving_focus=None)

        assert proxy.current_focus is None

    def test_mouse_wheel_event_routes(self, mock_pygame_patches, mocker):
        """Wheel events should route to scene.on_mouse_wheel_event."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_wheel_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)

        # pygame.MOUSEWHEEL delivers x,y deltas
        event = HashableEvent(pygame.MOUSEWHEEL, x=0, y=1)
        manager.on_mouse_wheel_event(event)
        scene.on_mouse_wheel_event.assert_called_once_with(event)

    def test_drag_drop_lifecycle_left(self, mock_pygame_patches, mocker):
        """Down -> motion -> up should trigger drag then drop lifecycle."""
        scene = MockFactory.create_event_test_scene_mock()

        # Track calls to generic drag/drop (MouseEventManager emits generic drag/drop)
        scene.on_mouse_drag_event = mocker.Mock(return_value=True)
        scene.on_mouse_drop_event = mocker.Mock(return_value=True)
        scene.on_left_mouse_button_down_event = mocker.Mock(return_value=True)
        scene.on_left_mouse_button_up_event = mocker.Mock(return_value=True)
        scene.on_mouse_button_down_event = mocker.Mock(return_value=True)
        scene.on_mouse_button_up_event = mocker.Mock(return_value=True)

        manager = MouseEventManager(game=scene)

        mocker.patch('glitchygames.events.mouse.collided_sprites', return_value=[])
        down = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1)
        motion = HashableEvent(pygame.MOUSEMOTION, pos=(6, 6), rel=(1, 1), buttons=(1, 0, 0))
        up = HashableEvent(pygame.MOUSEBUTTONUP, pos=(7, 7), button=1)

        manager.on_mouse_button_down_event(down)
        manager.on_mouse_motion_event(motion)
        manager.on_mouse_button_up_event(up)

        # Specifics called
        scene.on_left_mouse_button_down_event.assert_called_once()
        scene.on_left_mouse_button_up_event.assert_called_once()
        # Generic drag and drop called
        scene.on_mouse_drag_event.assert_called()
        scene.on_mouse_drop_event.assert_called()
