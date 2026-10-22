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
from glitchygames.scenes import Scene

# Options of a strict game: unhandled events raise UnhandledEventError
STRICT_EVENT_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}

# Every handler MouseEventProxy calls on its game (glitchygames/events/mouse.py), including the
# drag/drop names only sprites define (on_*_mouse_drag_down_event, on_*_mouse_drag_up_event)
RECORDED_MOUSE_HANDLER_NAMES = (
    'on_mouse_motion_event',
    'on_mouse_drag_event',
    'on_mouse_drop_event',
    'on_left_mouse_drag_event',
    'on_left_mouse_drag_up_event',
    'on_middle_mouse_drag_down_event',
    'on_middle_mouse_drag_up_event',
    'on_right_mouse_drag_down_event',
    'on_right_mouse_drag_up_event',
    'on_mouse_button_down_event',
    'on_mouse_button_up_event',
    'on_left_mouse_button_down_event',
    'on_left_mouse_button_up_event',
    'on_middle_mouse_button_down_event',
    'on_middle_mouse_button_up_event',
    'on_right_mouse_button_down_event',
    'on_right_mouse_button_up_event',
    'on_mouse_scroll_down_event',
    'on_mouse_scroll_up_event',
    'on_mouse_wheel_event',
)


class MouseRecordingScene(Scene):
    """A real scene that records every mouse handler call it receives.

    Each call is recorded in handler_calls as (handler name, arguments): the positional
    arguments, then the keyword arguments' values in the order given. The scene's sprite group
    is a real LayeredDirty, so the proxy's collision checks run for real.
    """

    def __init__(self, options=None, groups=None):
        """Create the scene with strict event options and no handler calls yet."""
        super().__init__(
            options=dict(STRICT_EVENT_OPTIONS) if options is None else options, groups=groups
        )
        self.handler_calls = []

    def called_handler_names(self):
        """The names of the handlers called, in call order.

        Returns:
            list[str]: The handler names.

        """
        return [handler_name for handler_name, _arguments in self.handler_calls]

    def arguments_of(self, handler_name):
        """The arguments of each call to one handler, in call order.

        Returns:
            list[tuple]: The arguments of each call.

        """
        return [
            arguments
            for called_handler_name, arguments in self.handler_calls
            if called_handler_name == handler_name
        ]


def _recording_handler(handler_name):
    """Make a handler that records its call on the scene under handler_name.

    Returns:
        Callable: The handler.

    """

    def record_call(self, *arguments, **keyword_arguments):
        self.handler_calls.append((handler_name, (*arguments, *keyword_arguments.values())))

    record_call.__name__ = handler_name
    return record_call


for _handler_name in RECORDED_MOUSE_HANDLER_NAMES:
    setattr(MouseRecordingScene, _handler_name, _recording_handler(_handler_name))


class RecordingSprite(pygame.sprite.DirtySprite):
    """A real sprite at a real position that records the mouse and focus calls it receives."""

    def __init__(self, *, rect):
        """Create the sprite covering rect, with nothing received yet."""
        super().__init__()
        self.image = pygame.Surface(rect.size)
        self.rect = rect
        self.received = []

    def on_mouse_motion_event(self, event):
        """Record the motion event."""
        self.received.append(('motion', event))

    def on_mouse_focus_event(self, event, current_focus):
        """Record the focus event and the focus it was given."""
        self.received.append(('focus', event, current_focus))

    def on_mouse_unfocus_event(self, event):
        """Record the unfocus event."""
        self.received.append(('unfocus', event))


@pytest.fixture
def mouse_scene():
    """A real scene that records the mouse handler calls it receives.

    Returns:
        MouseRecordingScene: The scene.

    """
    return MouseRecordingScene()


# ---------------------------------------------------------------------------
# MouseEvents interface tests (from test_events_mouse_events.py)
# ---------------------------------------------------------------------------


class TestMouseEventsInterface:
    """Test MouseEvents interface functionality."""

    def test_mouse_events_interface(self):
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

    def test_mouse_event_stubs_implementation(self, mocker):
        """Test MouseEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = MouseEventStubs()
        assert hasattr(stub, 'on_mouse_motion_event')
        assert hasattr(stub, 'on_mouse_drag_event')
        assert hasattr(stub, 'on_mouse_drop_event')
        assert hasattr(stub, 'on_mouse_button_down_event')
        assert hasattr(stub, 'on_mouse_button_up_event')
        assert hasattr(stub, 'on_mouse_wheel_event')

        # The stub's options are a strict game's, so unhandled events raise
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test method calls
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_motion_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_mouse_button_down_event(self, mouse_scene):
        """A button down given to the manager reaches the scene's button down handler."""
        manager = MouseEventManager(game=mouse_scene)

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
        manager.on_mouse_button_down_event(event)

        assert mouse_scene.arguments_of('on_mouse_button_down_event') == [(event,)]
        assert mouse_scene.arguments_of('on_mouse_button_down_event')[0][0].button == 1

    def test_mouse_button_up_event(self, mouse_scene):
        """A button up given to the manager reaches the scene's button up handler."""
        manager = MouseEventManager(game=mouse_scene)

        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        manager.on_mouse_button_up_event(event)

        assert mouse_scene.arguments_of('on_mouse_button_up_event') == [(event,)]
        assert mouse_scene.arguments_of('on_mouse_button_up_event')[0][0].button == 1

    def test_mouse_motion_event(self, mouse_scene):
        """A motion given to the manager reaches the scene's motion handler."""
        manager = MouseEventManager(game=mouse_scene)

        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        manager.on_mouse_motion_event(event)

        assert mouse_scene.arguments_of('on_mouse_motion_event') == [(event,)]
        assert mouse_scene.arguments_of('on_mouse_motion_event')[0][0].pos == (100, 100)

    def test_mouse_wheel_event(self, mocker):
        """Test mouse wheel event handling."""
        stub = MouseEventStubs()
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test mouse wheel
        event = HashableEvent(pygame.MOUSEWHEEL, x=0, y=1)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_wheel_event(event)
        # Exception was raised as expected

    def test_mouse_drag_event(self, mocker):
        """Test mouse drag event handling."""
        stub = MouseEventStubs()
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_drag_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_mouse_drop_event(self, mocker):
        """Test mouse drop event handling."""
        stub = MouseEventStubs()
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_drop_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_left_mouse_drag_event(self, mocker):
        """Test left mouse drag event handling."""
        stub = MouseEventStubs()
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test left mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_left_mouse_drag_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_left_mouse_drop_event(self, mocker):
        """Test left mouse drop event handling."""
        stub = MouseEventStubs()
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test left mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_left_mouse_drop_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_middle_mouse_drag_event(self, mocker):
        """Test middle mouse drag event handling."""
        stub = MouseEventStubs()
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test middle mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_middle_mouse_drag_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_middle_mouse_drop_event(self, mocker):
        """Test middle mouse drop event handling."""
        stub = MouseEventStubs()
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test middle mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=2, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_middle_mouse_drop_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_right_mouse_drag_event(self, mocker):
        """Test right mouse drag event handling."""
        stub = MouseEventStubs()
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test right mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_right_mouse_drag_event(event, trigger='test_trigger')
        # Exception was raised as expected

    def test_right_mouse_drop_event(self, mocker):
        """Test right mouse drop event handling."""
        stub = MouseEventStubs()
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test right mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=3, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_right_mouse_drop_event(event, trigger='test_trigger')
        # Exception was raised as expected


# ---------------------------------------------------------------------------
# MousePointer tests (from test_mouse_events_coverage.py + test_mouse_events_manager_coverage.py)
# ---------------------------------------------------------------------------


class TestMousePointerProperties:
    """Test MousePointer x and y properties."""

    def test_mouse_pointer_x_getter(self):
        """MousePointer.x should return the x coordinate from pos."""
        pointer = MousePointer(pos=(50, 75))
        assert pointer.x == 50

    def test_mouse_pointer_x_setter(self):
        """MousePointer.x setter should update the x coordinate in pos."""
        pointer = MousePointer(pos=(50, 75))
        pointer.x = 100
        assert pointer.pos[0] == 100
        assert pointer.x == 100

    def test_mouse_pointer_y_getter(self):
        """MousePointer.y should return the y coordinate from pos."""
        pointer = MousePointer(pos=(50, 75))
        assert pointer.y == 75

    def test_mouse_pointer_y_setter(self):
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
    """Test the collided_sprites helper function with real sprites at real positions."""

    def test_collided_sprites_with_no_collisions(self, mouse_scene):
        """collided_sprites should return empty list when no sprites collide."""
        mouse_scene.all_sprites.add(RecordingSprite(rect=pygame.Rect(0, 0, 10, 10)))

        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(0, 0))
        result = collided_sprites(mouse_scene, event=event, index=-1)

        assert result == []

    def test_collided_sprites_with_collisions_and_index(self, mouse_scene):
        """collided_sprites with index should return list with single sprite."""
        lower_sprite = RecordingSprite(rect=pygame.Rect(90, 90, 20, 20))
        upper_sprite = RecordingSprite(rect=pygame.Rect(95, 95, 20, 20))
        elsewhere_sprite = RecordingSprite(rect=pygame.Rect(300, 300, 20, 20))
        mouse_scene.all_sprites.add(lower_sprite, upper_sprite, elsewhere_sprite)

        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(0, 0))
        result = collided_sprites(mouse_scene, event=event, index=-1)

        assert result == [upper_sprite]

    def test_collided_sprites_with_collisions_no_index(self, mouse_scene):
        """collided_sprites with index=None should return the full list."""
        lower_sprite = RecordingSprite(rect=pygame.Rect(90, 90, 20, 20))
        upper_sprite = RecordingSprite(rect=pygame.Rect(95, 95, 20, 20))
        elsewhere_sprite = RecordingSprite(rect=pygame.Rect(300, 300, 20, 20))
        mouse_scene.all_sprites.add(lower_sprite, upper_sprite, elsewhere_sprite)

        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(0, 0))
        result = collided_sprites(mouse_scene, event=event, index=None)

        assert result == [lower_sprite, upper_sprite]


class TestCollidedSpritesNoCollision:
    """Test collided_sprites function with no collision."""

    def test_no_collision(self, mouse_scene):
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 200))
        result = collided_sprites(mouse_scene, event)
        assert result == []


# ---------------------------------------------------------------------------
# MouseEventProxy drop event tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


class TestMouseEventProxyDropEvent:
    """Test MouseEventProxy.on_mouse_drop_event and button-specific drop handlers."""

    def test_drop_event_left_button_forwards_to_game(self, mouse_scene):
        """Left-button drop should forward to game and call left-specific drop."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_BUTTON_LEFT)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_LEFT)
        proxy.on_mouse_drop_event(event, trigger)

        assert mouse_scene.handler_calls == [
            ('on_mouse_drop_event', (event, trigger)),
            ('on_left_mouse_drag_up_event', (event, trigger)),
        ]
        assert proxy.mouse_dropping is False

    def test_drop_event_middle_button_forwards_to_game(self, mouse_scene):
        """Middle-button drop should forward to game and call middle-specific drop."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_BUTTON_WHEEL)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_WHEEL)
        proxy.on_mouse_drop_event(event, trigger)

        assert mouse_scene.handler_calls == [
            ('on_mouse_drop_event', (event, trigger)),
            ('on_middle_mouse_drag_up_event', (event, trigger)),
        ]

    def test_drop_event_right_button_forwards_to_game(self, mouse_scene):
        """Right-button drop should forward to game and call right-specific drop."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_BUTTON_RIGHT)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_RIGHT)
        proxy.on_mouse_drop_event(event, trigger)

        assert mouse_scene.handler_calls == [
            ('on_mouse_drop_event', (event, trigger)),
            ('on_right_mouse_drag_up_event', (event, trigger)),
        ]

    def test_drop_event_scroll_up_button_is_noop(self, mouse_scene):
        """Scroll-up button drop should still forward generic drop but not crash."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_WHEEL_SCROLL_UP)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_WHEEL_SCROLL_UP)
        proxy.on_mouse_drop_event(event, trigger)

        assert mouse_scene.handler_calls == [('on_mouse_drop_event', (event, trigger))]

    def test_drop_event_scroll_down_button_is_noop(self, mouse_scene):
        """Scroll-down button drop should still forward generic drop but not crash."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_WHEEL_SCROLL_DOWN)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_WHEEL_SCROLL_DOWN)
        proxy.on_mouse_drop_event(event, trigger)

        assert mouse_scene.handler_calls == [('on_mouse_drop_event', (event, trigger))]

    @pytest.mark.xfail(
        strict=True,
        raises=AttributeError,
        reason=(
            "MouseEventProxy.on_left_mouse_drop_event calls the game's "
            'on_left_mouse_drag_up_event, which Scene does not define: a Scene receives a '
            'left drop in on_left_mouse_drop_event, which the proxy never calls'
        ),
    )
    def test_left_drop_reaches_a_plain_scenes_left_drop_handler(self):
        """A left-button drop given to the proxy reaches Scene.on_left_mouse_drop_event."""

        class LeftDropScene(Scene):
            def __init__(self):
                super().__init__(options=dict(STRICT_EVENT_OPTIONS))
                self.left_drops = []

            def on_mouse_drop_event(self, event, trigger):
                """Accept the generic drop."""

            def on_left_mouse_drop_event(self, event, trigger):
                self.left_drops.append((event, trigger))

        scene = LeftDropScene()
        proxy = MouseEventManager(game=scene).proxies[0]
        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_BUTTON_LEFT)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_LEFT)

        proxy.on_mouse_drop_event(event, trigger)

        assert scene.left_drops == [(event, trigger)]


# ---------------------------------------------------------------------------
# MouseEventProxy drag event tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


class TestMouseEventProxyDragEvent:
    """Test MouseEventProxy.on_mouse_drag_event button routing."""

    def test_drag_event_left_button(self, mouse_scene):
        """Left-button drag should forward to game and call left-specific drag."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 10), rel=(1, 1))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_LEFT)
        proxy.on_mouse_drag_event(event, trigger)

        assert mouse_scene.handler_calls == [
            ('on_mouse_drag_event', (event, trigger)),
            ('on_left_mouse_drag_event', (event, trigger)),
        ]

    def test_drag_event_middle_button(self, mouse_scene):
        """Middle-button drag should forward to middle-specific drag."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 10), rel=(1, 1))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_WHEEL)
        proxy.on_mouse_drag_event(event, trigger)

        assert mouse_scene.handler_calls == [
            ('on_mouse_drag_event', (event, trigger)),
            ('on_middle_mouse_drag_down_event', (event, trigger)),
        ]

    def test_drag_event_right_button(self, mouse_scene):
        """Right-button drag should forward to right-specific drag."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 10), rel=(1, 1))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_BUTTON_RIGHT)
        proxy.on_mouse_drag_event(event, trigger)

        assert mouse_scene.handler_calls == [
            ('on_mouse_drag_event', (event, trigger)),
            ('on_right_mouse_drag_down_event', (event, trigger)),
        ]

    def test_drag_event_scroll_up_is_noop(self, mouse_scene):
        """Scroll-up button drag should still forward generic drag."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 10), rel=(1, 1))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_WHEEL_SCROLL_UP)
        proxy.on_mouse_drag_event(event, trigger)

        assert mouse_scene.handler_calls == [('on_mouse_drag_event', (event, trigger))]

    def test_drag_event_scroll_down_is_noop(self, mouse_scene):
        """Scroll-down button drag should still forward generic drag."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 10), rel=(1, 1))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=MOUSE_WHEEL_SCROLL_DOWN)
        proxy.on_mouse_drag_event(event, trigger)

        assert mouse_scene.handler_calls == [('on_mouse_drag_event', (event, trigger))]

    @pytest.mark.parametrize(
        ('button', 'scene_handler_name'),
        [
            (MOUSE_BUTTON_WHEEL, 'on_middle_mouse_drag_event'),
            (MOUSE_BUTTON_RIGHT, 'on_right_mouse_drag_event'),
        ],
    )
    @pytest.mark.xfail(
        strict=True,
        raises=AttributeError,
        reason=(
            "MouseEventProxy routes a middle or right drag to the game's "
            'on_middle_mouse_drag_down_event / on_right_mouse_drag_down_event, which Scene '
            'does not define: Scene.on_middle_mouse_drag_event and on_right_mouse_drag_event '
            '(which pass the drag to the sprites under the mouse) are never called. Through '
            "the engine the SceneManager hands the miss to GameEngine's missing_event"
        ),
    )
    def test_middle_and_right_drags_reach_a_plain_scenes_drag_handler(
        self, button, scene_handler_name
    ):
        """Pressing a button and moving the mouse reaches the scene's handler for that drag."""

        class DragScene(Scene):
            def __init__(self):
                super().__init__(options=dict(STRICT_EVENT_OPTIONS))
                self.drags = []

            def on_mouse_button_down_event(self, event):
                """Accept the generic button down."""

            def on_middle_mouse_button_down_event(self, event):
                """Accept the middle button down."""

            def on_right_mouse_button_down_event(self, event):
                """Accept the right button down."""

            def on_mouse_motion_event(self, event):
                """Accept the motion."""

            def on_mouse_drag_event(self, event, trigger):
                """Accept the generic drag."""

            def on_middle_mouse_drag_event(self, event, trigger):
                self.drags.append(('on_middle_mouse_drag_event', event))

            def on_right_mouse_drag_event(self, event, trigger):
                self.drags.append(('on_right_mouse_drag_event', event))

        scene = DragScene()
        manager = MouseEventManager(game=scene)
        motion = HashableEvent(pygame.MOUSEMOTION, pos=(6, 6), rel=(1, 1), buttons=(0, 1, 1))

        manager.on_mouse_button_down_event(
            HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=button)
        )
        manager.on_mouse_motion_event(motion)

        assert scene.drags == [(scene_handler_name, motion)]


# ---------------------------------------------------------------------------
# MouseEventProxy motion with collision tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


class TestMouseEventProxyMotionWithCollision:
    """Test MouseEventProxy.on_mouse_motion_event with sprite collision."""

    def test_motion_with_collided_sprite_forwards_to_sprite(self, mouse_scene):
        """When a sprite collides, motion event should be forwarded to the sprite."""
        sprite_under_mouse = RecordingSprite(rect=pygame.Rect(90, 90, 20, 20))
        sprite_elsewhere = RecordingSprite(rect=pygame.Rect(300, 300, 20, 20))
        mouse_scene.all_sprites.add(sprite_under_mouse, sprite_elsewhere)

        manager = MouseEventManager(game=mouse_scene)

        motion_event = HashableEvent(
            pygame.MOUSEMOTION,
            pos=(100, 100),
            rel=(10, 10),
            buttons=(0, 0, 0),
        )
        manager.on_mouse_motion_event(motion_event)

        assert mouse_scene.handler_calls == [('on_mouse_motion_event', (motion_event,))]
        assert sprite_under_mouse.received == [('motion', motion_event)]
        assert sprite_elsewhere.received == []

    def test_motion_forwards_only_to_the_topmost_collided_sprite(self, mouse_scene):
        """Of overlapping sprites under the mouse, only the last in the group gets the motion."""
        lower_sprite = RecordingSprite(rect=pygame.Rect(90, 90, 20, 20))
        upper_sprite = RecordingSprite(rect=pygame.Rect(95, 95, 20, 20))
        mouse_scene.all_sprites.add(lower_sprite, upper_sprite)

        manager = MouseEventManager(game=mouse_scene)
        motion_event = HashableEvent(
            pygame.MOUSEMOTION, pos=(100, 100), rel=(1, 1), buttons=(0, 0, 0)
        )
        manager.on_mouse_motion_event(motion_event)

        assert upper_sprite.received == [('motion', motion_event)]
        assert lower_sprite.received == []

    def test_motion_runtime_error_in_mouse_state_iteration(self, mouse_scene):
        """RuntimeError during mouse_state iteration should be caught gracefully."""
        manager = MouseEventManager(game=mouse_scene)
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

        assert mouse_scene.handler_calls == [('on_mouse_motion_event', (motion_event,))]


# ---------------------------------------------------------------------------
# MouseEventProxy button up scroll wheel tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


class TestMouseEventProxyButtonUpScrollWheel:
    """Test scroll-wheel pass-through on button up events."""

    def test_button_up_scroll_up_passes(self, mouse_scene):
        """Button up with scroll-up button should pass without error."""
        manager = MouseEventManager(game=mouse_scene)

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(0, 0), button=MOUSE_WHEEL_SCROLL_UP)
        manager.on_mouse_button_up_event(event)

        assert mouse_scene.handler_calls == [('on_mouse_button_up_event', (event,))]

    def test_button_up_scroll_down_passes(self, mouse_scene):
        """Button up with scroll-down button should pass without error."""
        manager = MouseEventManager(game=mouse_scene)

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(0, 0), button=MOUSE_WHEEL_SCROLL_DOWN)
        manager.on_mouse_button_up_event(event)

        assert mouse_scene.handler_calls == [('on_mouse_button_up_event', (event,))]


# ---------------------------------------------------------------------------
# MouseEventProxy RuntimeError handling tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


class RaisingKeysDict(UserDict):
    """Dict subclass that raises RuntimeError on its first keys() call."""

    def __init__(self, *args, **kwargs):
        """Create the dict, armed to raise on the first keys() call."""
        super().__init__(*args, **kwargs)
        self._raise_on_keys = True

    def keys(self):
        """Raise RuntimeError the first time, then return the keys.

        Returns:
            KeysView: The keys.

        Raises:
            RuntimeError: On the first call.

        """
        if self._raise_on_keys:
            self._raise_on_keys = False
            msg = 'dictionary changed size during iteration'
            raise RuntimeError(msg)
        return super().keys()


class TestMouseEventProxyButtonDownRuntimeError:
    """Test RuntimeError handling during on_mouse_button_down_event."""

    def test_button_down_runtime_error_in_state_keys(self, mouse_scene):
        """RuntimeError when listing mouse_state keys should be caught."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]
        proxy.mouse_state = RaisingKeysDict()

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=MOUSE_BUTTON_LEFT)
        # Should not raise
        proxy.on_mouse_button_down_event(event)

        assert mouse_scene.handler_calls == [
            ('on_mouse_button_down_event', (event,)),
            ('on_left_mouse_button_down_event', (event,)),
        ]
        assert proxy.mouse_state[MOUSE_BUTTON_LEFT] is event


class TestMouseEventProxyLeftButtonDownRuntimeError:
    """Test RuntimeError handling during on_left_mouse_button_down_event."""

    def test_left_button_down_runtime_error_in_state_keys(self, mouse_scene):
        """RuntimeError when listing mouse_state keys should be caught."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]
        proxy.mouse_state = RaisingKeysDict()

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=MOUSE_BUTTON_LEFT)
        # Should not raise
        proxy.on_left_mouse_button_down_event(event)

        assert mouse_scene.handler_calls == [('on_left_mouse_button_down_event', (event,))]


# ---------------------------------------------------------------------------
# MouseEventProxy button handler tests (from test_mouse_events_coverage.py)
# ---------------------------------------------------------------------------


class TestMouseEventProxyMiddleButtonHandlers:
    """Test middle button up and down handlers."""

    def test_middle_mouse_button_up_forwards_to_game(self, mouse_scene):
        """Middle button up should forward to game."""
        proxy = MouseEventManager(game=mouse_scene).proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_BUTTON_WHEEL)
        proxy.on_middle_mouse_button_up_event(event)

        assert mouse_scene.handler_calls == [('on_middle_mouse_button_up_event', (event,))]

    def test_middle_mouse_button_down_forwards_to_game(self, mouse_scene):
        """Middle button down should forward to game."""
        proxy = MouseEventManager(game=mouse_scene).proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=MOUSE_BUTTON_WHEEL)
        proxy.on_middle_mouse_button_down_event(event)

        assert mouse_scene.handler_calls == [('on_middle_mouse_button_down_event', (event,))]


class TestMouseEventProxyRightButtonHandlers:
    """Test right button up and down handlers."""

    def test_right_mouse_button_up_forwards_to_game(self, mouse_scene):
        """Right button up should forward to game."""
        proxy = MouseEventManager(game=mouse_scene).proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=MOUSE_BUTTON_RIGHT)
        proxy.on_right_mouse_button_up_event(event)

        assert mouse_scene.handler_calls == [('on_right_mouse_button_up_event', (event,))]

    def test_right_mouse_button_down_forwards_to_game(self, mouse_scene):
        """Right button down should forward to game."""
        proxy = MouseEventManager(game=mouse_scene).proxies[0]

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=MOUSE_BUTTON_RIGHT)
        proxy.on_right_mouse_button_down_event(event)

        assert mouse_scene.handler_calls == [('on_right_mouse_button_down_event', (event,))]


# ---------------------------------------------------------------------------
# MouseEventProxy delegation tests (from test_mouse_events_manager_coverage.py)
# ---------------------------------------------------------------------------


class TestMouseEventProxyDelegation:
    """Test MouseEventProxy event delegation."""

    def test_proxy_init(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        assert proxy.game is mouse_scene
        assert proxy.proxies == [mouse_scene, pygame.mouse]
        assert proxy.mouse_dragging is False
        assert proxy.mouse_dropping is False
        assert proxy.current_focus is None
        assert proxy.previous_focus is None

    def test_on_mouse_button_down_left(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_BUTTON_LEFT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        assert mouse_scene.called_handler_names() == [
            'on_mouse_button_down_event',
            'on_left_mouse_button_down_event',
        ]

    def test_on_mouse_button_down_right(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_BUTTON_RIGHT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        assert mouse_scene.called_handler_names() == [
            'on_mouse_button_down_event',
            'on_right_mouse_button_down_event',
        ]

    def test_on_mouse_button_down_middle(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_BUTTON_WHEEL,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        assert mouse_scene.called_handler_names() == [
            'on_mouse_button_down_event',
            'on_middle_mouse_button_down_event',
        ]

    def test_on_mouse_button_down_scroll_up(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_WHEEL_SCROLL_UP,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        # Button 4 (scroll up) is routed to the scroll down handler (as the code does)
        assert mouse_scene.called_handler_names() == [
            'on_mouse_button_down_event',
            'on_mouse_scroll_down_event',
        ]

    def test_on_mouse_button_down_scroll_down(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_WHEEL_SCROLL_DOWN,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        # Button 5 (scroll down) is routed to the scroll up handler (as the code does)
        assert mouse_scene.called_handler_names() == [
            'on_mouse_button_down_event',
            'on_mouse_scroll_up_event',
        ]

    def test_on_mouse_button_up_left(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_LEFT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        assert mouse_scene.called_handler_names() == [
            'on_left_mouse_button_up_event',
            'on_mouse_button_up_event',
        ]

    def test_on_mouse_button_up_right(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_RIGHT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        assert mouse_scene.called_handler_names() == [
            'on_right_mouse_button_up_event',
            'on_mouse_button_up_event',
        ]

    def test_on_mouse_button_up_middle(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_WHEEL,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        assert mouse_scene.called_handler_names() == [
            'on_middle_mouse_button_up_event',
            'on_mouse_button_up_event',
        ]

    def test_on_mouse_button_up_triggers_drop_if_dragging(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        proxy.mouse_dragging = True
        event = HashableEvent(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_LEFT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        # The mouse up is both the drop event and its trigger
        assert mouse_scene.arguments_of('on_mouse_drop_event') == [(event, event)]
        assert proxy.mouse_dragging is False

    def test_on_mouse_wheel_event(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(pygame.MOUSEWHEEL, x=0, y=1)
        proxy.on_mouse_wheel_event(event)
        assert mouse_scene.handler_calls == [('on_mouse_wheel_event', (event,))]

    def test_on_mouse_drag_event_left(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        motion_event = HashableEvent(
            pygame.MOUSEMOTION,
            pos=(150, 250),
            rel=(5, 5),
            buttons=(1, 0, 0),
        )
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_LEFT, pos=(100, 200))
        proxy.on_mouse_drag_event(motion_event, trigger)
        assert mouse_scene.called_handler_names() == [
            'on_mouse_drag_event',
            'on_left_mouse_drag_event',
        ]

    def test_on_mouse_drag_event_right(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        motion_event = HashableEvent(
            pygame.MOUSEMOTION,
            pos=(150, 250),
            rel=(5, 5),
            buttons=(0, 0, 1),
        )
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_RIGHT, pos=(100, 200))
        proxy.on_mouse_drag_event(motion_event, trigger)
        assert mouse_scene.arguments_of('on_right_mouse_drag_down_event') == [
            (motion_event, trigger)
        ]

    def test_on_mouse_drag_event_middle(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        motion_event = HashableEvent(
            pygame.MOUSEMOTION,
            pos=(150, 250),
            rel=(5, 5),
            buttons=(0, 1, 0),
        )
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_WHEEL, pos=(100, 200))
        proxy.on_mouse_drag_event(motion_event, trigger)
        assert mouse_scene.arguments_of('on_middle_mouse_drag_down_event') == [
            (motion_event, trigger)
        ]

    def test_on_mouse_drop_event_left(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=MOUSE_BUTTON_LEFT, pos=(100, 200))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_LEFT, pos=(90, 190))
        proxy.on_mouse_drop_event(event, trigger)
        assert mouse_scene.called_handler_names() == [
            'on_mouse_drop_event',
            'on_left_mouse_drag_up_event',
        ]
        assert proxy.mouse_dropping is False

    def test_on_mouse_drop_event_right(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=MOUSE_BUTTON_RIGHT, pos=(100, 200))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_RIGHT, pos=(90, 190))
        proxy.on_mouse_drop_event(event, trigger)
        assert mouse_scene.arguments_of('on_right_mouse_drag_up_event') == [(event, trigger)]

    def test_on_mouse_drop_event_middle(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=MOUSE_BUTTON_WHEEL, pos=(100, 200))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_WHEEL, pos=(90, 190))
        proxy.on_mouse_drop_event(event, trigger)
        assert mouse_scene.arguments_of('on_middle_mouse_drag_up_event') == [(event, trigger)]

    def test_on_mouse_focus_event(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 200), rel=(1, 1), buttons=(0, 0, 0))
        sprite = RecordingSprite(rect=pygame.Rect(90, 190, 20, 20))
        proxy.on_mouse_focus_event(event, sprite)
        assert proxy.current_focus is sprite
        # The sprite is told it has focus, and is given itself as the current focus
        assert sprite.received == [('focus', event, sprite)]

    def test_on_mouse_unfocus_event(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 200), rel=(1, 1), buttons=(0, 0, 0))
        sprite = RecordingSprite(rect=pygame.Rect(90, 190, 20, 20))
        proxy.current_focus = sprite
        proxy.on_mouse_unfocus_event(event, sprite)
        assert proxy.current_focus is None
        assert proxy.previous_focus is sprite
        assert sprite.received == [('unfocus', event)]

    def test_on_mouse_unfocus_event_none(self, mouse_scene):
        proxy = MouseEventManager.MouseEventProxy(game=mouse_scene)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 200), rel=(1, 1), buttons=(0, 0, 0))
        proxy.on_mouse_unfocus_event(event, None)
        assert proxy.previous_focus is None


# ---------------------------------------------------------------------------
# MouseEventManager tests (from test_mouse_events_manager_coverage.py)
# ---------------------------------------------------------------------------


class TestMouseEventManagerInit:
    """Test MouseEventManager initialization."""

    def test_init(self, mouse_scene):
        manager = MouseEventManager(game=mouse_scene)
        assert len(manager.proxies) == 1

    def test_init_allows_mouse_events(self, mouse_scene):
        """MouseEventManager unblocks the mouse events at SDL."""
        pygame.event.set_blocked(pygame.MOUSEMOTION)
        try:
            MouseEventManager(game=mouse_scene)
            assert not pygame.event.get_blocked(pygame.MOUSEMOTION)
        finally:
            pygame.event.set_allowed(pygame.MOUSEMOTION)

    def test_args(self):
        parser = argparse.ArgumentParser()
        result = MouseEventManager.args(parser)
        assert result is parser


# ---------------------------------------------------------------------------
# MouseEventManager routing tests (from test_events_mouse_events.py)
# ---------------------------------------------------------------------------


class TestMouseEventManagerRouting:
    """Test MouseEventManager in isolation."""

    def test_mouse_manager_initialization(self, mouse_scene):
        """Test MouseEventManager initializes correctly."""
        manager = MouseEventManager(game=mouse_scene)

        assert manager.game is mouse_scene
        assert hasattr(manager, 'on_mouse_motion_event')
        assert hasattr(manager, 'on_mouse_button_down_event')

    def test_mouse_manager_events(self, mouse_scene):
        """Test mouse event handling through manager."""
        # Real sprites in the scene's group, none under the mouse
        mouse_scene.all_sprites.add(
            RecordingSprite(rect=pygame.Rect(300, 300, 10, 10)),
            RecordingSprite(rect=pygame.Rect(400, 400, 10, 10)),
            RecordingSprite(rect=pygame.Rect(500, 500, 10, 10)),
        )
        manager = MouseEventManager(game=mouse_scene)

        motion_event = HashableEvent(
            pygame.MOUSEMOTION,
            pos=(100, 100),
            rel=(10, 10),
            buttons=(0, 0, 0),
        )
        manager.on_mouse_motion_event(motion_event)
        assert mouse_scene.arguments_of('on_mouse_motion_event') == [(motion_event,)]

        down_event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 100), button=1)
        manager.on_mouse_button_down_event(down_event)
        assert mouse_scene.arguments_of('on_mouse_button_down_event') == [(down_event,)]

        up_event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(100, 100), button=1)
        manager.on_mouse_button_up_event(up_event)
        assert mouse_scene.arguments_of('on_mouse_button_up_event') == [(up_event,)]
        # No motion came while the button was down, so nothing was dragged or dropped
        assert 'on_mouse_drag_event' not in mouse_scene.called_handler_names()
        assert 'on_mouse_drop_event' not in mouse_scene.called_handler_names()

    def test_mouse_down_order_generic_then_specific(self, mouse_scene):
        """Left down should call generic scene handler first, then left-specific."""
        manager = MouseEventManager(game=mouse_scene)

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1)
        manager.on_mouse_button_down_event(event)

        assert mouse_scene.called_handler_names() == [
            'on_mouse_button_down_event',
            'on_left_mouse_button_down_event',
        ]

    def test_mouse_up_order_specific_then_generic(self, mouse_scene):
        """Left up should call left-specific then generic scene handler."""
        manager = MouseEventManager(game=mouse_scene)

        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=1)
        manager.on_mouse_button_up_event(event)

        assert mouse_scene.called_handler_names() == [
            'on_left_mouse_button_up_event',
            'on_mouse_button_up_event',
        ]

    def test_right_button_down_routes_to_right_specific(self, mouse_scene):
        """Right button down should hit right-specific, not middle."""
        manager = MouseEventManager(game=mouse_scene)

        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=3)
        manager.on_mouse_button_down_event(event)

        assert mouse_scene.arguments_of('on_right_mouse_button_down_event') == [(event,)]
        assert mouse_scene.arguments_of('on_middle_mouse_button_down_event') == []

    def test_middle_mouse_down_up_order_generic_then_specific(self, mouse_scene):
        """Middle button down: generic then specific; up: specific then generic."""
        manager = MouseEventManager(game=mouse_scene)
        middle_down = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(1, 1), button=2)
        middle_up = HashableEvent(pygame.MOUSEBUTTONUP, pos=(1, 1), button=2)
        manager.on_mouse_button_down_event(middle_down)
        manager.on_mouse_button_up_event(middle_up)

        assert mouse_scene.called_handler_names() == [
            'on_mouse_button_down_event',
            'on_middle_mouse_button_down_event',
            'on_middle_mouse_button_up_event',
            'on_mouse_button_up_event',
        ]

    def test_right_mouse_up_order_specific_then_generic(self, mouse_scene):
        """Right button up should be specific then generic."""
        manager = MouseEventManager(game=mouse_scene)
        right_up = HashableEvent(pygame.MOUSEBUTTONUP, pos=(2, 2), button=3)
        manager.on_mouse_button_up_event(right_up)

        assert mouse_scene.called_handler_names() == [
            'on_right_mouse_button_up_event',
            'on_mouse_button_up_event',
        ]

    def test_right_mouse_down_order_generic_then_specific(self, mouse_scene):
        """Right button down should be generic then specific."""
        manager = MouseEventManager(game=mouse_scene)
        right_down = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(3, 3), button=3)
        manager.on_mouse_button_down_event(right_down)

        assert mouse_scene.called_handler_names() == [
            'on_mouse_button_down_event',
            'on_right_mouse_button_down_event',
        ]

    def test_drag_drop_lifecycle_middle(self, mouse_scene):
        """Middle button drag/drop lifecycle triggers generic drag/drop."""
        manager = MouseEventManager(game=mouse_scene)
        down = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=2)
        motion = HashableEvent(pygame.MOUSEMOTION, pos=(6, 6), rel=(1, 1), buttons=(0, 1, 0))
        up = HashableEvent(pygame.MOUSEBUTTONUP, pos=(7, 7), button=2)
        manager.on_mouse_button_down_event(down)
        manager.on_mouse_motion_event(motion)
        manager.on_mouse_button_up_event(up)

        assert mouse_scene.arguments_of('on_middle_mouse_button_down_event') == [(down,)]
        assert mouse_scene.arguments_of('on_middle_mouse_button_up_event') == [(up,)]
        assert mouse_scene.arguments_of('on_mouse_drag_event') == [(motion, down)]
        assert mouse_scene.arguments_of('on_mouse_drop_event') == [(up, up)]

    def test_drag_drop_lifecycle_right(self, mouse_scene):
        """Right button drag/drop lifecycle triggers generic drag/drop."""
        manager = MouseEventManager(game=mouse_scene)
        down = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=3)
        motion = HashableEvent(pygame.MOUSEMOTION, pos=(6, 6), rel=(1, 1), buttons=(0, 0, 1))
        up = HashableEvent(pygame.MOUSEBUTTONUP, pos=(7, 7), button=3)
        manager.on_mouse_button_down_event(down)
        manager.on_mouse_motion_event(motion)
        manager.on_mouse_button_up_event(up)

        assert mouse_scene.arguments_of('on_right_mouse_button_down_event') == [(down,)]
        assert mouse_scene.arguments_of('on_right_mouse_button_up_event') == [(up,)]
        assert mouse_scene.arguments_of('on_mouse_drag_event') == [(motion, down)]
        assert mouse_scene.arguments_of('on_mouse_drop_event') == [(up, up)]

    def test_button4_5_scroll_mapping_on_mousedown(self, mouse_scene):
        """Legacy scroll buttons 4/5 should route to scroll up/down handlers."""
        manager = MouseEventManager(game=mouse_scene)
        button_4 = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=4)
        button_5 = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=5)
        manager.on_mouse_button_down_event(button_4)
        manager.on_mouse_button_down_event(button_5)

        # button 4 maps to scroll down in code
        assert mouse_scene.arguments_of('on_mouse_scroll_down_event') == [(button_4,)]
        # button 5 maps to scroll up in code
        assert mouse_scene.arguments_of('on_mouse_scroll_up_event') == [(button_5,)]

    def test_focus_enter_unfocus_sequence_updates_state(self, mouse_scene):
        """Entering focus should unfocus old, set current to new, and call handlers."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        old_target = RecordingSprite(rect=pygame.Rect(0, 0, 10, 10))
        new_target = RecordingSprite(rect=pygame.Rect(20, 20, 10, 10))

        # Seed current focus
        proxy.current_focus = old_target
        event = HashableEvent(pygame.MOUSEMOTION, pos=(0, 0), rel=(0, 0))

        proxy.on_mouse_focus_event(event, entering_focus=new_target)

        # Old target should get unfocus
        assert old_target.received == [('unfocus', event)]
        # New target should get focus with current_focus passed
        assert new_target.received == [('focus', event, new_target)]
        # State updated
        assert proxy.current_focus is new_target
        assert proxy.previous_focus is old_target

    def test_unfocus_clears_current_and_sets_previous(self, mouse_scene):
        """Unfocus should call target unfocus, clear current, and record previous."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        target = RecordingSprite(rect=pygame.Rect(0, 0, 10, 10))
        proxy.current_focus = target
        event = HashableEvent(pygame.MOUSEMOTION, pos=(0, 0), rel=(0, 0))

        proxy.on_mouse_unfocus_event(event, leaving_focus=target)

        assert target.received == [('unfocus', event)]
        assert proxy.current_focus is None
        assert proxy.previous_focus is target

    def test_unfocus_no_target_is_noop(self, mouse_scene):
        """Unfocus with None should not crash or change state significantly."""
        manager = MouseEventManager(game=mouse_scene)
        proxy = manager.proxies[0]

        proxy.current_focus = None
        event = HashableEvent(pygame.MOUSEMOTION, pos=(0, 0), rel=(0, 0))

        # Should not raise
        proxy.on_mouse_unfocus_event(event, leaving_focus=None)

        assert proxy.current_focus is None
        assert mouse_scene.handler_calls == []

    def test_mouse_wheel_event_routes(self, mouse_scene):
        """Wheel events should route to scene.on_mouse_wheel_event."""
        manager = MouseEventManager(game=mouse_scene)

        # pygame.MOUSEWHEEL delivers x,y deltas
        event = HashableEvent(pygame.MOUSEWHEEL, x=0, y=1)
        manager.on_mouse_wheel_event(event)
        assert mouse_scene.handler_calls == [('on_mouse_wheel_event', (event,))]

    def test_drag_drop_lifecycle_left(self, mouse_scene):
        """Down -> motion -> up should trigger drag then drop lifecycle."""
        manager = MouseEventManager(game=mouse_scene)

        down = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1)
        motion = HashableEvent(pygame.MOUSEMOTION, pos=(6, 6), rel=(1, 1), buttons=(1, 0, 0))
        up = HashableEvent(pygame.MOUSEBUTTONUP, pos=(7, 7), button=1)

        manager.on_mouse_button_down_event(down)
        manager.on_mouse_motion_event(motion)
        manager.on_mouse_button_up_event(up)

        assert mouse_scene.handler_calls == [
            ('on_mouse_button_down_event', (down,)),
            ('on_left_mouse_button_down_event', (down,)),
            ('on_mouse_motion_event', (motion,)),
            ('on_mouse_drag_event', (motion, down)),
            ('on_left_mouse_drag_event', (motion, down)),
            ('on_left_mouse_button_up_event', (up,)),
            ('on_mouse_button_up_event', (up,)),
            ('on_mouse_drop_event', (up, up)),
        ]
