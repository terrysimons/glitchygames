"""Tests for game event functionality.

This module combines tests for:
- GameEvents interface and stubs
- GameEventProxy forwarding and delegation
- GameEventManager initialization, routing, args, and event processing

Events are real HashableEvents, the managers and proxies are the real ones, and the games they
forward to are real objects that record what they receive (a real Scene where the scene's own
behaviour matters).
"""

import argparse

import pygame
import pytest

from glitchygames.engine import GameEventManager
from glitchygames.events import (
    GameEvents,
    GameEventStubs,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.scenes import Scene

STRICT_EVENT_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}

# Each game event handler and an event of the type it handles
GAME_EVENT_HANDLERS_AND_TYPES = [
    ('on_active_event', pygame.ACTIVEEVENT),
    ('on_fps_event', pygame.USEREVENT + 1),
    ('on_game_event', pygame.USEREVENT + 2),
    ('on_menu_item_event', pygame.USEREVENT + 3),
    ('on_sys_wm_event', pygame.SYSWMEVENT),
    ('on_user_event', pygame.USEREVENT),
    ('on_video_expose_event', pygame.VIDEOEXPOSE),
    ('on_video_resize_event', pygame.VIDEORESIZE),
    ('on_quit_event', pygame.QUIT),
    ('on_render_device_reset_event', pygame.RENDER_DEVICE_RESET),
    ('on_render_targets_reset_event', pygame.RENDER_TARGETS_RESET),
    ('on_clipboard_update_event', pygame.CLIPBOARDUPDATE),
    ('on_locale_changed_event', pygame.LOCALECHANGED),
]
GAME_EVENT_HANDLER_NAMES = [handler_name for handler_name, _ in GAME_EVENT_HANDLERS_AND_TYPES]


def _keyword_recording_handler(handler_name):
    """Make a handler that records (handler name, event); the event must come by keyword.

    GameEventProxy calls the game with ``event=event``, so a positional call fails here.

    Returns:
        The handler function.

    """

    def handler(self, *, event):
        self.received.append((handler_name, event))

    handler.__name__ = handler_name
    return handler


class GameEventRecorder:
    """A game that records every game event handler call as (handler name, event)."""

    def __init__(self):
        """Create the game with nothing received yet."""
        self.received = []
        self.processed_batches = []

    on_active_event = _keyword_recording_handler('on_active_event')
    on_fps_event = _keyword_recording_handler('on_fps_event')
    on_game_event = _keyword_recording_handler('on_game_event')
    on_menu_item_event = _keyword_recording_handler('on_menu_item_event')
    on_sys_wm_event = _keyword_recording_handler('on_sys_wm_event')
    on_user_event = _keyword_recording_handler('on_user_event')
    on_video_expose_event = _keyword_recording_handler('on_video_expose_event')
    on_video_resize_event = _keyword_recording_handler('on_video_resize_event')
    on_quit_event = _keyword_recording_handler('on_quit_event')
    on_render_device_reset_event = _keyword_recording_handler('on_render_device_reset_event')
    on_render_targets_reset_event = _keyword_recording_handler('on_render_targets_reset_event')
    on_clipboard_update_event = _keyword_recording_handler('on_clipboard_update_event')
    on_locale_changed_event = _keyword_recording_handler('on_locale_changed_event')

    def process_events(self, events):
        """Record a batch of events (reached through the proxy's attribute delegation)."""
        self.processed_batches.append(events)


class GameEventRecordingScene(Scene):
    """A real Scene whose game event handlers record (tag, event) in game_events_received."""

    def __init__(self, options=None, groups=None):
        """Create the scene with strict unhandled-event options and nothing received yet."""
        super().__init__(options=options or dict(STRICT_EVENT_OPTIONS), groups=groups)
        self.game_events_received = []

    def on_active_event(self, event):
        self.game_events_received.append(('active', event))

    def on_fps_event(self, event):
        self.game_events_received.append(('fps', event))

    def on_game_event(self, event):
        self.game_events_received.append(('game', event))

    def on_menu_item_event(self, event):
        self.game_events_received.append(('menu_item', event))

    def on_sys_wm_event(self, event):
        self.game_events_received.append(('sys_wm', event))

    def on_user_event(self, event):
        self.game_events_received.append(('user', event))

    def on_video_expose_event(self, event):
        self.game_events_received.append(('video_expose', event))

    def on_video_resize_event(self, event):
        self.game_events_received.append(('video_resize', event))

    def on_quit_event(self, event):
        self.game_events_received.append(('quit', event))

    def on_render_device_reset_event(self, event):
        self.game_events_received.append(('render_device_reset', event))

    def on_render_targets_reset_event(self, event):
        self.game_events_received.append(('render_targets_reset', event))

    def on_clipboard_update_event(self, event):
        self.game_events_received.append(('clipboard_update', event))

    def on_locale_changed_event(self, event):
        self.game_events_received.append(('locale_changed', event))


class GameEventStubsGame(GameEventStubs):
    """A game with only the game event stubs, and strict unhandled-event options."""

    def __init__(self):
        """Create the game with strict options."""
        self.options = dict(STRICT_EVENT_OPTIONS)


def _route_through_manager(scene, handler_name, event):
    """Send an event through a real GameEventManager (and its proxy) to the scene."""
    manager = GameEventManager(game=scene)
    getattr(manager, handler_name)(event)


class TestGameEventProxy:
    """Test GameEventProxy event delegation."""

    @pytest.mark.parametrize(('handler_name', 'event_type'), GAME_EVENT_HANDLERS_AND_TYPES)
    def test_proxy_forwards_the_event_by_keyword(self, handler_name, event_type):
        """Each proxy handler calls the game's handler once, passing the event as event=."""
        game = GameEventRecorder()
        proxy = GameEventManager.GameEventProxy(game=game)
        event = HashableEvent(event_type)

        getattr(proxy, handler_name)(event)

        assert game.received == [(handler_name, event)]

    def test_proxy_keeps_the_game_as_its_only_proxy(self):
        game = GameEventRecorder()
        proxy = GameEventManager.GameEventProxy(game=game)
        assert proxy.game is game
        assert proxy.proxies == [game]


class TestGameEventManager:
    """Test GameEventManager event routing."""

    def test_init(self):
        game = GameEventRecorder()
        manager = GameEventManager(game=game)
        assert len(manager.proxies) == 1
        assert isinstance(manager.proxies[0], GameEventManager.GameEventProxy)
        assert manager.proxies[0].game is game

    @pytest.mark.parametrize(('handler_name', 'event_type'), GAME_EVENT_HANDLERS_AND_TYPES)
    def test_manager_routes_through_its_proxy_to_the_game(self, handler_name, event_type):
        """Each manager handler reaches the game's handler through the real proxy."""
        game = GameEventRecorder()
        manager = GameEventManager(game=game)
        event = HashableEvent(event_type)

        getattr(manager, handler_name)(event)

        assert game.received == [(handler_name, event)]

    @pytest.mark.parametrize('handler_name', GAME_EVENT_HANDLER_NAMES)
    def test_manager_forwards_to_every_proxy(self, handler_name):
        """With several proxies, the manager forwards the event to each of them in turn."""
        first_game = GameEventRecorder()
        second_game = GameEventRecorder()
        manager = GameEventManager(game=first_game)
        first_proxy = manager.proxies[0]
        # GameEventProxy is a singleton (ResourceManager), so the second proxy is a plain
        # object with the same forwarding contract
        second_proxy = _ForwardingProxy(game=second_game)
        manager.proxies = [first_proxy, second_proxy]
        event = HashableEvent(pygame.USEREVENT)

        getattr(manager, handler_name)(event)

        assert first_game.received == [(handler_name, event)]
        assert second_game.received == [(handler_name, event)]

    def test_args(self):
        parser = argparse.ArgumentParser()
        result = GameEventManager.args(parser)
        assert result is parser


class _ForwardingProxy:
    """A proxy that forwards any game event handler call to its game by keyword."""

    def __init__(self, *, game):
        """Wrap the game."""
        self.game = game

    def __getattr__(self, attribute_name):
        if attribute_name in GAME_EVENT_HANDLER_NAMES:

            def forward(event):
                getattr(self.game, attribute_name)(event=event)

            return forward
        raise AttributeError(attribute_name)


class TestGameEventManagerArgs:
    """Tests for GameEventManager.args classmethod."""

    def test_args_adds_log_level_argument(self):
        """Test that args adds the --log-level argument."""
        parser = argparse.ArgumentParser()
        result = GameEventManager.args(parser)

        assert result is parser
        args = parser.parse_args(['--log-level', 'debug'])
        assert args.log_level == 'debug'

    def test_args_log_level_choices(self):
        """Test that --log-level accepts valid choices."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        for level in ['debug', 'info', 'warning', 'error', 'critical']:
            args = parser.parse_args(['--log-level', level])
            assert args.log_level == level

    def test_args_log_level_case_insensitive(self):
        """Test that --log-level accepts uppercase input via type=str.lower."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['--log-level', 'DEBUG'])
        assert args.log_level == 'debug'

    def test_args_adds_no_unhandled_events_flag(self):
        """Test that args adds the --no-unhandled-events flag."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['--no-unhandled-events'])
        assert args.no_unhandled_events is True

    def test_args_no_unhandled_events_default_false(self):
        """Test that --no-unhandled-events defaults to False."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args([])
        assert args.no_unhandled_events is False

    def test_args_adds_profile_flag(self):
        """Test that args adds the --profile flag."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['--profile'])
        assert args.profile is True

    def test_args_profile_short_flag(self):
        """Test that -p is the short form for --profile."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['-p'])
        assert args.profile is True

    def test_args_profile_default_false(self):
        """Test that --profile defaults to False."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args([])
        assert args.profile is False

    def test_args_log_level_short_flag(self):
        """Test that -l is the short form for --log-level."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['-l', 'warning'])
        assert args.log_level == 'warning'

    def test_args_defaults_all(self):
        """Test all default values from args."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args([])
        assert args.log_level == 'warning'
        assert args.no_unhandled_events is False
        assert args.profile is False

    def test_a_game_logs_at_warning_by_default(self):
        """--log-level defaults to warning, the tools' level (the owner, 2026-10-28).

        A bug report asks for ``--log-level info`` instead (``exit_codes.BUG_REPORT_HINT``).
        """
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        assert parser.get_default('log_level') == 'warning'


class TestGameManager:
    """Test GameEventManager functionality."""

    def test_game_manager_init(self):
        """GameEventProxy wraps the game as its only proxy."""
        game = GameEventRecorder()

        manager = GameEventManager.GameEventProxy(game=game)

        assert manager.game is game
        assert manager.proxies == [game]

    def test_game_manager_process_events(self):
        """Attributes the proxy lacks are looked up on the game (ResourceManager.__getattr__)."""
        game = GameEventRecorder()
        manager = GameEventManager.GameEventProxy(game=game)
        events = [
            HashableEvent(pygame.QUIT),
            HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE),
            HashableEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100)),
        ]

        manager.process_events(events)

        assert game.processed_batches == [events]

    def test_game_manager_missing_attribute_raises(self, caplog):
        """An attribute neither the proxy nor the game has raises AttributeError, logged."""
        manager = GameEventManager.GameEventProxy(game=GameEventRecorder())

        with pytest.raises(AttributeError):
            manager.no_such_handler  # ruff: ignore[useless-expression]

        assert 'No proxies for' in caplog.text

    def test_game_manager_event_handlers(self):
        """Each handler delivers its real event to the game."""
        game = GameEventRecorder()
        manager = GameEventManager.GameEventProxy(game=game)
        active_event = HashableEvent(pygame.ACTIVEEVENT, gain=1, state=1)
        fps_event = HashableEvent(pygame.USEREVENT + 1)  # FPSEVENT
        game_event = HashableEvent(pygame.USEREVENT + 2)  # GAMEEVENT
        menu_event = HashableEvent(pygame.USEREVENT + 3)  # MENUEVENT
        sys_wm_event = HashableEvent(pygame.SYSWMEVENT)

        manager.on_active_event(active_event)
        manager.on_fps_event(fps_event)
        manager.on_game_event(game_event)
        manager.on_menu_item_event(menu_event)
        manager.on_sys_wm_event(sys_wm_event)

        assert game.received == [
            ('on_active_event', active_event),
            ('on_fps_event', fps_event),
            ('on_game_event', game_event),
            ('on_menu_item_event', menu_event),
            ('on_sys_wm_event', sys_wm_event),
        ]

    def test_game_manager_initialization(self):
        """GameEventProxy keeps the scene manager it was given as its game."""
        from glitchygames.scenes import SceneManager

        scene_manager = SceneManager()

        game_manager = GameEventManager.GameEventProxy(game=scene_manager)

        assert game_manager.game is scene_manager

    def test_game_manager_args(self):
        """Test GameEventManager.args method."""
        parser = argparse.ArgumentParser()

        # Test that args method returns the parser
        result = GameEventManager.args(parser)

        assert result is parser

        # Test that we can parse the arguments
        args = parser.parse_args([])
        assert hasattr(args, 'profile')  # Should have profile option


# ---------------------------------------------------------------------------
# GameEvents interface tests (from test_events_game_events.py)
# ---------------------------------------------------------------------------


class TestGameEvents:
    """Test GameEvents interface functionality."""

    def test_game_events_interface(self):
        """Test GameEvents interface methods."""
        for handler_name in GAME_EVENT_HANDLER_NAMES:
            assert hasattr(GameEvents, handler_name)

    @pytest.mark.parametrize(('handler_name', 'event_type'), GAME_EVENT_HANDLERS_AND_TYPES)
    def test_game_event_stubs_raise_through_the_manager(self, handler_name, event_type):
        """A game with only the stubs raises UnhandledEventError for every game event."""
        game = GameEventStubsGame()

        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            _route_through_manager(game, handler_name, HashableEvent(event_type))

    def test_clipboard_update_event_stub(self):
        """A real Scene leaves clipboard updates to the stub, which raises when strict."""
        scene = Scene(options=dict(STRICT_EVENT_OPTIONS))

        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            _route_through_manager(
                scene, 'on_clipboard_update_event', HashableEvent(pygame.CLIPBOARDUPDATE)
            )

    def test_locale_changed_event_stub(self):
        """A real Scene leaves locale changes to the stub, which raises when strict."""
        scene = Scene(options=dict(STRICT_EVENT_OPTIONS))

        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            _route_through_manager(
                scene, 'on_locale_changed_event', HashableEvent(pygame.LOCALECHANGED)
            )

    def test_scene_handles_quit_event(self, caplog):
        """A real Scene handles QUIT itself: no UnhandledEventError, just a debug log line."""
        scene = Scene(options=dict(STRICT_EVENT_OPTIONS))

        quit_event = HashableEvent(pygame.QUIT)

        with caplog.at_level('DEBUG', logger='game.scenes'):
            _route_through_manager(scene, 'on_quit_event', quit_event)

        assert f'{Scene}: {quit_event}' in caplog.messages

    @pytest.mark.parametrize(
        ('handler_name', 'tag', 'event'),
        [
            ('on_quit_event', 'quit', HashableEvent(pygame.QUIT)),
            ('on_active_event', 'active', HashableEvent(pygame.ACTIVEEVENT, gain=1, state=1)),
            ('on_fps_event', 'fps', HashableEvent(pygame.USEREVENT + 1)),
            ('on_game_event', 'game', HashableEvent(pygame.USEREVENT + 2)),
            ('on_menu_item_event', 'menu_item', HashableEvent(pygame.USEREVENT + 3)),
            ('on_sys_wm_event', 'sys_wm', HashableEvent(pygame.SYSWMEVENT)),
            ('on_user_event', 'user', HashableEvent(pygame.USEREVENT, code=1)),
            ('on_video_expose_event', 'video_expose', HashableEvent(pygame.VIDEOEXPOSE)),
            (
                'on_video_resize_event',
                'video_resize',
                HashableEvent(pygame.VIDEORESIZE, w=800, h=600),
            ),
            (
                'on_render_device_reset_event',
                'render_device_reset',
                HashableEvent(pygame.RENDER_DEVICE_RESET),
            ),
            (
                'on_render_targets_reset_event',
                'render_targets_reset',
                HashableEvent(pygame.RENDER_TARGETS_RESET),
            ),
            (
                'on_clipboard_update_event',
                'clipboard_update',
                HashableEvent(pygame.CLIPBOARDUPDATE),
            ),
            ('on_locale_changed_event', 'locale_changed', HashableEvent(pygame.LOCALECHANGED)),
        ],
    )
    def test_scene_receives_the_event_through_the_manager(self, handler_name, tag, event):
        """The manager delivers each game event, attributes intact, to the scene's handler."""
        scene = GameEventRecordingScene()

        _route_through_manager(scene, handler_name, event)

        assert scene.game_events_received == [(tag, event)]
        received_event = scene.game_events_received[0][1]
        assert received_event.type == event.type
        assert dict(received_event) == dict(event)

    def test_active_event_gain_states(self):
        """Test active event with different gain states."""
        scene = GameEventRecordingScene()
        gain_states = [
            (1, 1),  # Gained focus
            (0, 1),  # Lost focus
            (1, 2),  # Gained mouse
            (0, 2),  # Lost mouse
            (1, 4),  # Gained keyboard
            (0, 4),  # Lost keyboard
        ]

        for gain, state in gain_states:
            event = HashableEvent(pygame.ACTIVEEVENT, gain=gain, state=state)
            _route_through_manager(scene, 'on_active_event', event)

            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == 'active'
            assert scene.game_events_received[0][1].type == pygame.ACTIVEEVENT
            assert scene.game_events_received[0][1].gain == gain
            assert scene.game_events_received[0][1].state == state
            scene.game_events_received.clear()

    def test_user_events_with_different_codes(self):
        """Test user events with different codes."""
        scene = GameEventRecordingScene()

        for code in range(10):
            event = HashableEvent(pygame.USEREVENT, code=code)
            _route_through_manager(scene, 'on_user_event', event)

            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == 'user'
            assert scene.game_events_received[0][1].type == pygame.USEREVENT
            assert scene.game_events_received[0][1].code == code
            scene.game_events_received.clear()

    def test_video_resize_with_different_dimensions(self):
        """Test video resize events with different dimensions."""
        scene = GameEventRecordingScene()
        dimensions = [
            (640, 480),  # VGA
            (800, 600),  # SVGA
            (1024, 768),  # XGA
            (1280, 720),  # HD
            (1920, 1080),  # Full HD
            (2560, 1440),  # 2K
            (3840, 2160),  # 4K
        ]

        for width, height in dimensions:
            event = HashableEvent(pygame.VIDEORESIZE, w=width, h=height)
            _route_through_manager(scene, 'on_video_resize_event', event)

            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == 'video_resize'
            assert scene.game_events_received[0][1].type == pygame.VIDEORESIZE
            assert scene.game_events_received[0][1].w == width
            assert scene.game_events_received[0][1].h == height
            scene.game_events_received.clear()

    def test_custom_game_events(self):
        """Test custom game events."""
        scene = GameEventRecordingScene()
        custom_events = [
            HashableEvent(pygame.USEREVENT + 10, event_type='level_complete'),
            HashableEvent(pygame.USEREVENT + 11, event_type='player_died'),
            HashableEvent(pygame.USEREVENT + 12, event_type='power_up_collected'),
            HashableEvent(pygame.USEREVENT + 13, event_type='enemy_spawned'),
            HashableEvent(pygame.USEREVENT + 14, event_type='score_updated'),
        ]

        for event in custom_events:
            _route_through_manager(scene, 'on_game_event', event)

            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == 'game'
            assert scene.game_events_received[0][1].type == event.type
            assert scene.game_events_received[0][1].event_type == event.event_type
            scene.game_events_received.clear()

    def test_menu_events_with_different_items(self):
        """Test menu events with different menu items."""
        scene = GameEventRecordingScene()
        menu_items = ['New Game', 'Load Game', 'Save Game', 'Settings', 'Help', 'About', 'Exit']

        for item in menu_items:
            event = HashableEvent(pygame.USEREVENT + 3, menu_item=item)
            _route_through_manager(scene, 'on_menu_item_event', event)

            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == 'menu_item'
            assert scene.game_events_received[0][1].type == pygame.USEREVENT + 3
            assert scene.game_events_received[0][1].menu_item == item
            scene.game_events_received.clear()
