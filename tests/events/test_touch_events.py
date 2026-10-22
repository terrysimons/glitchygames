"""Tests for touch event functionality.

This module combines tests for:
- TouchEvents interface and TouchEventStubs
- TouchEventProxy forwarding and delegation
- TouchEventManager initialization and event routing
"""

import sys
from pathlib import Path

import pygame
import pygame._sdl2.touch
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    TouchEvents,
    TouchEventStubs,
    UnhandledEventError,
)
from glitchygames.events.touch import TouchEventManager
from glitchygames.scenes import Scene

# Options of a strict game: unhandled events raise UnhandledEventError
STRICT_EVENT_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}


class TouchRecordingScene(Scene):
    """A real scene that records each touch event it receives as (handler tag, event)."""

    def __init__(self, options=None, groups=None):
        """Create the scene with strict event options and no touch events received yet."""
        super().__init__(
            options=dict(STRICT_EVENT_OPTIONS) if options is None else options, groups=groups
        )
        self.touch_events_received = []

    def on_touch_down_event(self, event):
        """Record the touch down event."""
        self.touch_events_received.append(('touch_down', event))

    def on_touch_motion_event(self, event):
        """Record the touch motion event."""
        self.touch_events_received.append(('touch_motion', event))

    def on_touch_up_event(self, event):
        """Record the touch up event."""
        self.touch_events_received.append(('touch_up', event))

    def on_multi_touch_down_event(self, event):
        """Record the multi-touch down event."""
        self.touch_events_received.append(('multi_touch_down', event))

    def on_multi_touch_motion_event(self, event):
        """Record the multi-touch motion event."""
        self.touch_events_received.append(('multi_touch_motion', event))

    def on_multi_touch_up_event(self, event):
        """Record the multi-touch up event."""
        self.touch_events_received.append(('multi_touch_up', event))


@pytest.fixture
def touch_scene():
    """A real scene that records the touch events it receives.

    Returns:
        TouchRecordingScene: The scene.

    """
    return TouchRecordingScene()


@pytest.fixture
def finger_down_event():
    """A real finger down event.

    Returns:
        HashableEvent: The event.

    """
    return HashableEvent(pygame.FINGERDOWN, touch_id=1, finger_id=1, x=0.5, y=0.5, pressure=1.0)


# ---------------------------------------------------------------------------
# TouchEvents interface tests (from test_events_touch_events.py)
# ---------------------------------------------------------------------------


class TestTouchEvents:
    """Test TouchEvents interface functionality."""

    def test_touch_events_interface(self):
        """Test TouchEvents interface methods."""
        # Test that TouchEvents has required abstract methods
        assert hasattr(TouchEvents, 'on_touch_down_event')
        assert hasattr(TouchEvents, 'on_touch_motion_event')
        assert hasattr(TouchEvents, 'on_touch_up_event')
        assert hasattr(TouchEvents, 'on_multi_touch_down_event')
        assert hasattr(TouchEvents, 'on_multi_touch_motion_event')
        assert hasattr(TouchEvents, 'on_multi_touch_up_event')

    def test_touch_event_stubs_implementation(self):
        """Test TouchEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = TouchEventStubs()
        assert hasattr(stub, 'on_touch_down_event')
        assert hasattr(stub, 'on_touch_motion_event')
        assert hasattr(stub, 'on_touch_up_event')

        # Test that stub methods can be called with proper game object
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test method calls — should raise UnhandledEventError (no logging before raise)
        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100)
        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            stub.on_touch_down_event(event)

    def test_touch_down_event(self):
        """Test touch down event handling."""
        scene = TouchRecordingScene()
        manager = TouchEventManager(game=scene)

        # Test touch down
        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100)
        manager.on_touch_down_event(event)

        # Verify the event was handled
        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'touch_down'
        assert scene.touch_events_received[0][1].type == pygame.FINGERDOWN

    def test_touch_motion_event(self):
        """Test touch motion event handling."""
        scene = TouchRecordingScene()
        manager = TouchEventManager(game=scene)

        # Test touch motion
        event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=100, y=100, dx=10, dy=10)
        manager.on_touch_motion_event(event)

        # Verify the event was handled
        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'touch_motion'
        assert scene.touch_events_received[0][1].type == pygame.FINGERMOTION

    def test_touch_up_event(self):
        """Test touch up event handling."""
        scene = TouchRecordingScene()
        manager = TouchEventManager(game=scene)

        # Test touch up
        event = HashableEvent(pygame.FINGERUP, finger_id=1, x=100, y=100)
        manager.on_touch_up_event(event)

        # Verify the event was handled
        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'touch_up'
        assert scene.touch_events_received[0][1].type == pygame.FINGERUP

    def test_multi_touch_down_event(self):
        """Test multi touch down event handling."""
        scene = TouchRecordingScene()
        manager = TouchEventManager(game=scene)

        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100)
        manager.on_multi_touch_down_event(event)

        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'multi_touch_down'
        assert scene.touch_events_received[0][1].type == pygame.FINGERDOWN

    def test_multi_touch_motion_event(self):
        """Test multi touch motion event handling."""
        scene = TouchRecordingScene()
        manager = TouchEventManager(game=scene)

        event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=100, y=100, dx=10, dy=10)
        manager.on_multi_touch_motion_event(event)

        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'multi_touch_motion'
        assert scene.touch_events_received[0][1].type == pygame.FINGERMOTION

    def test_multi_touch_up_event(self):
        """Test multi touch up event handling."""
        scene = TouchRecordingScene()
        manager = TouchEventManager(game=scene)

        event = HashableEvent(pygame.FINGERUP, finger_id=1, x=100, y=100)
        manager.on_multi_touch_up_event(event)

        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'multi_touch_up'
        assert scene.touch_events_received[0][1].type == pygame.FINGERUP

    def test_multiple_finger_events(self):
        """Test multiple finger touch events."""
        scene = TouchRecordingScene()
        manager = TouchEventManager(game=scene)

        for finger_id in range(5):
            event = HashableEvent(pygame.FINGERDOWN, finger_id=finger_id, x=100, y=100)
            manager.on_touch_down_event(event)
            event = HashableEvent(
                pygame.FINGERMOTION,
                finger_id=finger_id,
                x=100,
                y=100,
                dx=10,
                dy=10,
            )
            manager.on_touch_motion_event(event)
            event = HashableEvent(pygame.FINGERUP, finger_id=finger_id, x=100, y=100)
            manager.on_touch_up_event(event)

        assert len(scene.touch_events_received) == 15

    def test_touch_events_with_pressure(self):
        """Test touch events with pressure values."""
        scene = TouchRecordingScene()
        manager = TouchEventManager(game=scene)

        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100, pressure=0.8)
        manager.on_touch_down_event(event)
        event = HashableEvent(
            pygame.FINGERMOTION,
            finger_id=1,
            x=100,
            y=100,
            dx=10,
            dy=10,
            pressure=0.6,
        )
        manager.on_touch_motion_event(event)
        event = HashableEvent(pygame.FINGERUP, finger_id=1, x=100, y=100, pressure=0.0)
        manager.on_touch_up_event(event)

        assert len(scene.touch_events_received) == 3
        assert scene.touch_events_received[0][0] == 'touch_down'
        assert scene.touch_events_received[1][0] == 'touch_motion'
        assert scene.touch_events_received[2][0] == 'touch_up'

    def test_touch_events_with_different_positions(self):
        """Test touch events with different positions."""
        scene = TouchRecordingScene()
        manager = TouchEventManager(game=scene)

        positions = [(0, 0), (100, 100), (200, 200), (50, 150), (150, 50)]

        for x, y in positions:
            event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=x, y=y)
            manager.on_touch_down_event(event)
            event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=x, y=y, dx=5, dy=5)
            manager.on_touch_motion_event(event)
            event = HashableEvent(pygame.FINGERUP, finger_id=1, x=x, y=y)
            manager.on_touch_up_event(event)

        assert len(scene.touch_events_received) == 15


# ---------------------------------------------------------------------------
# TouchEventProxy forwarding tests (from test_touch_events_coverage.py)
# ---------------------------------------------------------------------------


class TestTouchEventProxyForwarding:
    """Test each TouchEventProxy forwarding method individually."""

    def test_proxy_on_touch_down_event(self, touch_scene):
        """Touch down event should forward to the game."""
        manager = TouchEventManager(game=touch_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100)
        proxy.on_touch_down_event(event)

        assert touch_scene.touch_events_received == [('touch_down', event)]

    def test_proxy_on_touch_motion_event(self, touch_scene):
        """Touch motion event should forward to the game."""
        manager = TouchEventManager(game=touch_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=110, y=110, dx=10, dy=10)
        proxy.on_touch_motion_event(event)

        assert touch_scene.touch_events_received == [('touch_motion', event)]

    def test_proxy_on_touch_up_event(self, touch_scene):
        """Touch up event should forward to the game."""
        manager = TouchEventManager(game=touch_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERUP, finger_id=1, x=100, y=100)
        proxy.on_touch_up_event(event)

        assert touch_scene.touch_events_received == [('touch_up', event)]

    def test_proxy_on_multi_touch_down_event(self, touch_scene):
        """Multi-touch down event should forward to the game."""
        manager = TouchEventManager(game=touch_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERDOWN, finger_id=2, x=200, y=200)
        proxy.on_multi_touch_down_event(event)

        assert touch_scene.touch_events_received == [('multi_touch_down', event)]

    def test_proxy_on_multi_touch_motion_event(self, touch_scene):
        """Multi-touch motion event should forward to the game."""
        manager = TouchEventManager(game=touch_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERMOTION, finger_id=2, x=210, y=210, dx=10, dy=10)
        proxy.on_multi_touch_motion_event(event)

        assert touch_scene.touch_events_received == [('multi_touch_motion', event)]

    def test_proxy_on_multi_touch_up_event(self, touch_scene):
        """Multi-touch up event should forward to the game."""
        manager = TouchEventManager(game=touch_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERUP, finger_id=2, x=200, y=200)
        proxy.on_multi_touch_up_event(event)

        assert touch_scene.touch_events_received == [('multi_touch_up', event)]

    def test_proxy_init_without_sdl2_touch(self, mocker, touch_scene):
        """TouchEventProxy should handle missing pygame._sdl2.touch gracefully."""
        # Simulates a pygame build without the SDL2 touch module
        mocker.patch.object(pygame, '_sdl2', object())

        manager = TouchEventManager(game=touch_scene)
        proxy = manager.proxies[0]

        assert proxy.game is touch_scene
        assert proxy.proxies == [touch_scene]

    def test_proxy_init_with_sdl2_touch_proxies_the_touch_module(self, touch_scene):
        """With pygame._sdl2.touch present, the proxy falls back to it after the game."""
        proxy = TouchEventManager(game=touch_scene).proxies[0]

        assert proxy.proxies == [touch_scene, pygame._sdl2.touch]


# ---------------------------------------------------------------------------
# TouchEventProxy delegation tests (from test_touch_events_manager_coverage.py)
# ---------------------------------------------------------------------------


class TestTouchEventProxy:
    """Test TouchEventProxy event delegation."""

    def test_proxy_init(self, touch_scene):
        proxy = TouchEventManager.TouchEventProxy(game=touch_scene)
        assert proxy.game is touch_scene
        assert touch_scene in proxy.proxies

    def test_on_touch_down_event(self, touch_scene, finger_down_event):
        proxy = TouchEventManager.TouchEventProxy(game=touch_scene)
        proxy.on_touch_down_event(finger_down_event)
        assert touch_scene.touch_events_received == [('touch_down', finger_down_event)]

    def test_on_touch_motion_event(self, touch_scene, finger_down_event):
        proxy = TouchEventManager.TouchEventProxy(game=touch_scene)
        proxy.on_touch_motion_event(finger_down_event)
        assert touch_scene.touch_events_received == [('touch_motion', finger_down_event)]

    def test_on_touch_up_event(self, touch_scene, finger_down_event):
        proxy = TouchEventManager.TouchEventProxy(game=touch_scene)
        proxy.on_touch_up_event(finger_down_event)
        assert touch_scene.touch_events_received == [('touch_up', finger_down_event)]

    def test_on_multi_touch_down_event(self, touch_scene, finger_down_event):
        proxy = TouchEventManager.TouchEventProxy(game=touch_scene)
        proxy.on_multi_touch_down_event(finger_down_event)
        assert touch_scene.touch_events_received == [('multi_touch_down', finger_down_event)]

    def test_on_multi_touch_motion_event(self, touch_scene, finger_down_event):
        proxy = TouchEventManager.TouchEventProxy(game=touch_scene)
        proxy.on_multi_touch_motion_event(finger_down_event)
        assert touch_scene.touch_events_received == [('multi_touch_motion', finger_down_event)]

    def test_on_multi_touch_up_event(self, touch_scene, finger_down_event):
        proxy = TouchEventManager.TouchEventProxy(game=touch_scene)
        proxy.on_multi_touch_up_event(finger_down_event)
        assert touch_scene.touch_events_received == [('multi_touch_up', finger_down_event)]


# ---------------------------------------------------------------------------
# TouchEventManager tests (from test_touch_events_manager_coverage.py + test_events_touch_events.py)
# ---------------------------------------------------------------------------


class TestTouchEventManager:
    """Test TouchEventManager initialization."""

    def test_init(self, touch_scene):
        manager = TouchEventManager(game=touch_scene)
        assert len(manager.proxies) == 1


class TestTouchManager:
    """Test TouchEventManager in isolation."""

    def test_touch_manager_initialization(self, touch_scene):
        """Test TouchEventManager initializes correctly."""
        manager = TouchEventManager(game=touch_scene)

        assert manager.game is touch_scene
        assert isinstance(manager.proxies, list)
        assert isinstance(manager.proxies[0], TouchEventManager.TouchEventProxy)

    def test_touch_manager_events(self, touch_scene):
        """Finger down, up and motion given to the manager reach the scene's touch handlers.

        These are the handlers GameEngine.process_touch_event calls for FINGERDOWN, FINGERUP
        and FINGERMOTION.
        """
        manager = TouchEventManager(game=touch_scene)

        touch_down_event = HashableEvent(
            pygame.FINGERDOWN,
            touch_id=1,
            finger_id=1,
            x=100,
            y=100,
            dx=0,
            dy=0,
        )
        manager.on_touch_down_event(touch_down_event)

        touch_up_event = HashableEvent(
            pygame.FINGERUP,
            touch_id=1,
            finger_id=1,
            x=100,
            y=100,
            dx=0,
            dy=0,
        )
        manager.on_touch_up_event(touch_up_event)

        touch_motion_event = HashableEvent(
            pygame.FINGERMOTION,
            touch_id=1,
            finger_id=1,
            x=110,
            y=110,
            dx=10,
            dy=10,
        )
        manager.on_touch_motion_event(touch_motion_event)

        assert touch_scene.touch_events_received == [
            ('touch_down', touch_down_event),
            ('touch_up', touch_up_event),
            ('touch_motion', touch_motion_event),
        ]


class TestTouchEventManagerWithoutVideo:
    """Constructing the manager before pygame's video system is up."""

    def test_unallowed_events_are_logged_and_the_manager_still_works(self, mocker, caplog):
        """set_allowed raises 'video system not initialized' before pygame.display.init()."""
        mocker.patch(
            'pygame.event.set_allowed',
            side_effect=pygame.error('video system not initialized'),
        )
        game = TouchRecordingScene()

        with caplog.at_level('DEBUG', logger='game.touch'):
            manager = TouchEventManager(game=game)

        assert len(manager.proxies) == 1
        assert 'Failed to set allowed touch events: pygame not fully initialized' in caplog.text
