"""Tests for app event functionality.

This module tests app event interfaces, stubs, event handling, AppEventProxy
forwarding methods, AppEventManager initialization, and proxy behavior when
the game object lacks handler methods.

Every game here is a real Scene and every event a real HashableEvent; app events reach the
scene through the real AppEventManager (and, in TestAppEventFlow, through the real engine).
"""

import pygame
import pytest

from glitchygames.events import (
    AppEvents,
    AppEventStubs,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.events.app import AppEventManager
from glitchygames.live_sources import LiveSources
from glitchygames.replay.tools.golden_traces import (
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
)
from glitchygames.scenes import Scene
from glitchygames.sources import install_sources

STRICT_EVENT_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}

# (handler name, event type) for every app event
APP_EVENT_HANDLERS = (
    ('on_app_did_enter_background_event', pygame.APP_DIDENTERBACKGROUND),
    ('on_app_did_enter_foreground_event', pygame.APP_DIDENTERFOREGROUND),
    ('on_app_will_enter_background_event', pygame.APP_WILLENTERBACKGROUND),
    ('on_app_will_enter_foreground_event', pygame.APP_WILLENTERFOREGROUND),
    ('on_app_low_memory_event', pygame.APP_LOWMEMORY),
    ('on_app_terminating_event', pygame.APP_TERMINATING),
)


class AppEventRecordingScene(Scene):
    """A real scene that records each app event it receives as (handler name, event)."""

    def __init__(self, options=None, groups=None):
        """Create the scene with no app events received yet."""
        super().__init__(options=options, groups=groups)
        self.app_events_received = []

    def on_app_did_enter_background_event(self, event):
        """Record the event."""
        self.app_events_received.append(('on_app_did_enter_background_event', event))

    def on_app_did_enter_foreground_event(self, event):
        """Record the event."""
        self.app_events_received.append(('on_app_did_enter_foreground_event', event))

    def on_app_will_enter_background_event(self, event):
        """Record the event."""
        self.app_events_received.append(('on_app_will_enter_background_event', event))

    def on_app_will_enter_foreground_event(self, event):
        """Record the event."""
        self.app_events_received.append(('on_app_will_enter_foreground_event', event))

    def on_app_low_memory_event(self, event):
        """Record the event."""
        self.app_events_received.append(('on_app_low_memory_event', event))

    def on_app_terminating_event(self, event):
        """Record the event."""
        self.app_events_received.append(('on_app_terminating_event', event))


class GameWithoutAppHandlers:
    """A game object that has none of the app event handlers."""


class ScriptedBatchSources(LiveSources):
    """Live doors whose first pump returns a scripted batch (the real queue is drained too)."""

    def __init__(self, *, batch):
        """Create the doors with the batch their first pump returns."""
        super().__init__(random_seed=1)
        self.pending_batches = [batch]

    def pump_events(self):
        """Drain SDL's queue, then return the scripted batch once and empty batches after.

        Returns:
            list[pygame.event.Event]: The batch.

        """
        pygame.event.get()
        return self.pending_batches.pop(0) if self.pending_batches else []


def start_engine_with_scene(*, scene_class):
    """Start the real engine with ``scene_class`` active, as GameEngine.start() would.

    Returns:
        tuple: The engine and its active scene.

    """
    manager = GoldenTraceSceneManager.install()
    with command_line([
        '--windowed',
        '--resolution',
        '800x600',
        '--log-level',
        'warning',
        '--no-unhandled-events',
    ]):
        engine = GoldenTraceEngine(game=scene_class)
    engine.install_game(scene_class=scene_class)
    return engine, manager.active_scene


class TestAppEventProxy:
    """Test AppEventProxy event delegation."""

    def test_proxy_init(self):
        game = AppEventRecordingScene(options=STRICT_EVENT_OPTIONS)
        proxy = AppEventManager.AppEventProxy(game=game)
        assert proxy.game is game
        assert proxy.proxies == [game]

    @pytest.mark.parametrize(('handler_name', 'event_type'), APP_EVENT_HANDLERS)
    def test_proxy_forwards_each_app_event_to_the_game(self, handler_name, event_type):
        """Each proxy handler hands the very same event to the game's handler of that name."""
        game = AppEventRecordingScene(options=STRICT_EVENT_OPTIONS)
        proxy = AppEventManager.AppEventProxy(game=game)
        event = HashableEvent(event_type)

        getattr(proxy, handler_name)(event)

        assert game.app_events_received == [(handler_name, event)]
        assert game.app_events_received[0][1] is event


class TestAppEventManager:
    """Test AppEventManager initialization."""

    def test_init(self):
        game = AppEventRecordingScene(options=STRICT_EVENT_OPTIONS)
        manager = AppEventManager(game=game)
        assert manager.game is game
        assert len(manager.proxies) == 1
        assert isinstance(manager.proxies[0], AppEventManager.AppEventProxy)

    def test_init_allows_every_app_event_type(self):
        """The manager lets SDL deliver app events, even if they were blocked before."""
        app_event_types = [event_type for _handler_name, event_type in APP_EVENT_HANDLERS]
        blocked_before = {
            event_type: pygame.event.get_blocked(event_type) for event_type in app_event_types
        }
        pygame.event.set_blocked(app_event_types)
        try:
            AppEventManager(game=AppEventRecordingScene(options=STRICT_EVENT_OPTIONS))

            assert not any(pygame.event.get_blocked(event_type) for event_type in app_event_types)
        finally:
            for event_type, was_blocked in blocked_before.items():
                if was_blocked:
                    pygame.event.set_blocked(event_type)
                else:
                    pygame.event.set_allowed(event_type)


class TestAppEventProxyForwarding:
    """Test the manager's proxy forwarding to a real scene using HashableEvent."""

    @pytest.mark.parametrize(('handler_name', 'event_type'), APP_EVENT_HANDLERS)
    def test_manager_proxy_forwards_each_app_event(self, handler_name, event_type):
        """The manager's own proxy forwards each app event to the scene."""
        game = AppEventRecordingScene(options=STRICT_EVENT_OPTIONS)
        manager = AppEventManager(game=game)
        proxy = manager.proxies[0]

        event = HashableEvent(event_type)
        getattr(proxy, handler_name)(event)

        assert game.app_events_received == [(handler_name, event)]


class TestAppEventProxyMissingHandlers:
    """Test AppEventProxy when game object lacks handler methods."""

    @pytest.mark.parametrize(('handler_name', 'event_type'), APP_EVENT_HANDLERS)
    def test_proxy_skips_a_missing_handler(self, handler_name, event_type):
        """The proxy does nothing (and does not raise) when the game lacks the handler."""
        game = GameWithoutAppHandlers()
        manager = AppEventManager(game=game)
        proxy = manager.proxies[0]

        event = HashableEvent(event_type)

        # Should not raise
        result = getattr(proxy, handler_name)(event)

        assert result is None
        assert vars(game) == {}


class TestAppEventManagerInit:
    """Test AppEventManager initialization edge cases."""

    def test_init_handles_pygame_error(self, mocker):
        """Test that init handles pygame.error when setting allowed events."""
        # Simulated failure: SDL refusing set_allowed cannot be produced on demand
        mocker.patch('pygame.event.set_allowed', side_effect=pygame.error('not initialized'))
        game = AppEventRecordingScene(options=STRICT_EVENT_OPTIONS)

        # Should not raise despite pygame.error
        manager = AppEventManager(game=game)

        assert manager.game is game
        assert len(manager.proxies) == 1


class TestAppEvents:
    """Test AppEvents interface functionality."""

    def test_app_events_interface(self):
        """Test AppEvents interface methods."""
        # Test that AppEvents has required abstract methods
        for handler_name, _event_type in APP_EVENT_HANDLERS:
            assert handler_name in AppEvents.__abstractmethods__

    @pytest.mark.parametrize(('handler_name', 'event_type'), APP_EVENT_HANDLERS)
    def test_app_event_stubs_raise_for_an_unhandled_event(self, mocker, handler_name, event_type):
        """Each AppEventStubs handler reports the event as unhandled (strict options raise)."""
        stub = AppEventStubs()
        event = HashableEvent(event_type)
        # Silence the expected error log
        mocker.patch('glitchygames.events.base.LOG.error')

        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            getattr(stub, handler_name)(event)

    @pytest.mark.parametrize(('handler_name', 'event_type'), APP_EVENT_HANDLERS)
    def test_app_event_reaches_the_scene_through_the_manager(self, handler_name, event_type):
        """Each app event given to the manager reaches the scene's handler of the same name."""
        scene = AppEventRecordingScene(options=STRICT_EVENT_OPTIONS)
        manager = AppEventManager(game=scene)

        event = HashableEvent(event_type)
        result = getattr(manager, handler_name)(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.app_events_received) == 1
        assert scene.app_events_received[0][0] == handler_name
        assert scene.app_events_received[0][1].type == event_type


class TestAppEventFlow:
    """Test app event flow through the engine."""

    def test_app_event_through_engine(self):
        """An app event pumped by the engine reaches the active scene's handler."""
        engine, scene = start_engine_with_scene(scene_class=AppEventRecordingScene)
        install_sources(
            sources=ScriptedBatchSources(batch=[pygame.event.Event(pygame.APP_DIDENTERBACKGROUND)])
        )

        result = engine.process_events()

        # Verify the event was processed
        assert result is True
        assert len(scene.app_events_received) == 1
        assert scene.app_events_received[0][0] == 'on_app_did_enter_background_event'
        assert scene.app_events_received[0][1].type == pygame.APP_DIDENTERBACKGROUND

    def test_app_event_falls_back_to_stubs(self, mocker):
        """A scene without app event handlers falls back to the stubs, which raise."""
        # A plain Scene implements no app event handler: AllEventStubs' stub handles it
        scene = Scene(options=STRICT_EVENT_OPTIONS)
        manager = AppEventManager(game=scene)

        event = HashableEvent(pygame.APP_DIDENTERBACKGROUND)
        # Silence the expected error log
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            manager.on_app_did_enter_background_event(event)

    def test_app_manager_directly(self):
        """Test app manager directly."""
        scene = AppEventRecordingScene(options=STRICT_EVENT_OPTIONS)
        manager = AppEventManager(game=scene)

        event = HashableEvent(pygame.APP_DIDENTERBACKGROUND)
        result = manager.on_app_did_enter_background_event(event)

        # Verify the event was processed
        assert result is None
        assert scene.app_events_received == [('on_app_did_enter_background_event', event)]
