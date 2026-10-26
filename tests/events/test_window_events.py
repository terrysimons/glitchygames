"""Tests for window event functionality.

This module combines tests for:
- WindowEvents interface and WindowEventStubs
- WindowEventProxy forwarding and delegation
- WindowEventManager initialization, args, and event routing
"""

import argparse

import pygame
import pytest

from glitchygames.events import (
    HashableEvent,
    UnhandledEventError,
    WindowEvents,
    WindowEventStubs,
)
from glitchygames.events.window import WindowEventManager
from glitchygames.scenes import Scene

EVENT_TEST_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}


class WindowRecordingScene(Scene):
    """A real scene that records every window event it receives as (label, event)."""

    def __init__(self, options=None, groups=None):
        """Create the scene with no window events received yet."""
        super().__init__(
            options=options if options is not None else dict(EVENT_TEST_OPTIONS),
            groups=groups,
        )
        self.window_events_received: list[tuple[str, HashableEvent]] = []

    def on_window_close_event(self, event):
        """Record a window close event."""
        self.window_events_received.append(('window_close', event))

    def on_window_enter_event(self, event):
        """Record a window enter event."""
        self.window_events_received.append(('window_enter', event))

    def on_window_exposed_event(self, event):
        """Record a window exposed event."""
        self.window_events_received.append(('window_exposed', event))

    def on_window_focus_gained_event(self, event):
        """Record a window focus gained event."""
        self.window_events_received.append(('window_focus_gained', event))

    def on_window_focus_lost_event(self, event):
        """Record a window focus lost event."""
        self.window_events_received.append(('window_focus_lost', event))

    def on_window_hidden_event(self, event):
        """Record a window hidden event."""
        self.window_events_received.append(('window_hidden', event))

    def on_window_hit_test_event(self, event):
        """Record a window hit test event."""
        self.window_events_received.append(('window_hit_test', event))

    def on_window_leave_event(self, event):
        """Record a window leave event."""
        self.window_events_received.append(('window_leave', event))

    def on_window_maximized_event(self, event):
        """Record a window maximized event."""
        self.window_events_received.append(('window_maximized', event))

    def on_window_minimized_event(self, event):
        """Record a window minimized event."""
        self.window_events_received.append(('window_minimized', event))

    def on_window_moved_event(self, event):
        """Record a window moved event."""
        self.window_events_received.append(('window_moved', event))

    def on_window_resized_event(self, event):
        """Record a window resized event."""
        self.window_events_received.append(('window_resized', event))

    def on_window_restored_event(self, event):
        """Record a window restored event."""
        self.window_events_received.append(('window_restored', event))

    def on_window_shown_event(self, event):
        """Record a window shown event."""
        self.window_events_received.append(('window_shown', event))

    def on_window_size_changed_event(self, event):
        """Record a window size changed event."""
        self.window_events_received.append(('window_size_changed', event))

    def on_window_take_focus_event(self, event):
        """Record a window take focus event."""
        self.window_events_received.append(('window_take_focus', event))


def window_scene_and_manager():
    """Create a recording scene and a real WindowEventManager delivering to it.

    Returns:
        tuple[WindowRecordingScene, WindowEventManager]: The scene and its manager.

    """
    scene = WindowRecordingScene()
    return scene, WindowEventManager(game=scene)


class TestWindowEventProxy:
    """Test WindowEventProxy event delegation."""

    def test_proxy_init(self):
        game = WindowRecordingScene()
        proxy = WindowEventManager.WindowEventProxy(game=game)
        assert proxy.game is game
        assert proxy.proxies == [game]

    def test_on_window_close_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWCLOSE)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_close_event(event)
        assert game.window_events_received == [('window_close', event)]

    def test_on_window_enter_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWENTER)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_enter_event(event)
        assert game.window_events_received == [('window_enter', event)]

    def test_on_window_exposed_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWEXPOSED)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_exposed_event(event)
        assert game.window_events_received == [('window_exposed', event)]

    def test_on_window_focus_gained_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWFOCUSGAINED)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_focus_gained_event(event)
        assert game.window_events_received == [('window_focus_gained', event)]

    def test_on_window_focus_lost_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWFOCUSLOST)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_focus_lost_event(event)
        assert game.window_events_received == [('window_focus_lost', event)]

    def test_on_window_hidden_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWHIDDEN)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_hidden_event(event)
        assert game.window_events_received == [('window_hidden', event)]

    def test_on_window_hit_test_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWHITTEST)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_hit_test_event(event)
        assert game.window_events_received == [('window_hit_test', event)]

    def test_on_window_leave_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWLEAVE)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_leave_event(event)
        assert game.window_events_received == [('window_leave', event)]

    def test_on_window_maximized_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWMAXIMIZED)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_maximized_event(event)
        assert game.window_events_received == [('window_maximized', event)]

    def test_on_window_minimized_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWMINIMIZED)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_minimized_event(event)
        assert game.window_events_received == [('window_minimized', event)]

    def test_on_window_moved_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWMOVED)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_moved_event(event)
        assert game.window_events_received == [('window_moved', event)]

    def test_on_window_resized_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWRESIZED)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_resized_event(event)
        assert game.window_events_received == [('window_resized', event)]

    def test_on_window_restored_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWRESTORED)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_restored_event(event)
        assert game.window_events_received == [('window_restored', event)]

    def test_on_window_shown_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWSHOWN)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_shown_event(event)
        assert game.window_events_received == [('window_shown', event)]

    def test_on_window_size_changed_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWSIZECHANGED)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_size_changed_event(event)
        assert game.window_events_received == [('window_size_changed', event)]

    def test_on_window_take_focus_event(self):
        game = WindowRecordingScene()
        event = HashableEvent(pygame.WINDOWTAKEFOCUS)
        proxy = WindowEventManager.WindowEventProxy(game=game)
        proxy.on_window_take_focus_event(event)
        assert game.window_events_received == [('window_take_focus', event)]


class TestWindowEventManager:
    """Test WindowEventManager initialization."""

    def test_init(self):
        scene, manager = window_scene_and_manager()
        assert len(manager.proxies) == 1
        assert manager.proxies[0].game is scene

    def test_args(self):

        parser = argparse.ArgumentParser()
        result = WindowEventManager.args(parser)
        assert result is parser


# ---------------------------------------------------------------------------
# WindowEventProxy forwarding tests (from test_window_events_coverage.py)
# ---------------------------------------------------------------------------


class TestWindowEventProxyForwarding:
    """Test each WindowEventProxy forwarding method individually."""

    def test_proxy_on_window_hidden_event(self):
        """Window hidden event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWHIDDEN)
        manager.on_window_hidden_event(event)

        assert scene.window_events_received == [('window_hidden', event)]

    def test_proxy_on_window_hit_test_event(self):
        """Window hit test event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWHITTEST)
        manager.on_window_hit_test_event(event)

        assert scene.window_events_received == [('window_hit_test', event)]

    def test_proxy_on_window_maximized_event(self):
        """Window maximized event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWMAXIMIZED)
        manager.on_window_maximized_event(event)

        assert scene.window_events_received == [('window_maximized', event)]

    def test_proxy_on_window_minimized_event(self):
        """Window minimized event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWMINIMIZED)
        manager.on_window_minimized_event(event)

        assert scene.window_events_received == [('window_minimized', event)]

    def test_proxy_on_window_moved_event(self):
        """Window moved event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWMOVED, x=100, y=200)
        manager.on_window_moved_event(event)

        assert scene.window_events_received == [('window_moved', event)]

    def test_proxy_on_window_resized_event(self):
        """Window resized event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWRESIZED, x=1024, y=768)
        manager.on_window_resized_event(event)

        assert scene.window_events_received == [('window_resized', event)]

    def test_proxy_on_window_restored_event(self):
        """Window restored event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWRESTORED)
        manager.on_window_restored_event(event)

        assert scene.window_events_received == [('window_restored', event)]

    def test_proxy_on_window_shown_event(self):
        """Window shown event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWSHOWN)
        manager.on_window_shown_event(event)

        assert scene.window_events_received == [('window_shown', event)]

    def test_proxy_on_window_size_changed_event(self):
        """Window size changed event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWSIZECHANGED, x=800, y=600)
        manager.on_window_size_changed_event(event)

        assert scene.window_events_received == [('window_size_changed', event)]

    def test_proxy_on_window_take_focus_event(self):
        """Window take focus event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWTAKEFOCUS)
        manager.on_window_take_focus_event(event)

        assert scene.window_events_received == [('window_take_focus', event)]

    def test_proxy_on_window_exposed_event(self):
        """Window exposed event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWEXPOSED)
        manager.on_window_exposed_event(event)

        assert scene.window_events_received == [('window_exposed', event)]

    def test_proxy_on_window_leave_event(self):
        """Window leave event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWLEAVE)
        manager.on_window_leave_event(event)

        assert scene.window_events_received == [('window_leave', event)]

    def test_proxy_on_window_focus_lost_event(self):
        """Window focus lost event should forward to game."""
        scene, manager = window_scene_and_manager()

        event = HashableEvent(pygame.WINDOWFOCUSLOST)
        manager.on_window_focus_lost_event(event)

        assert scene.window_events_received == [('window_focus_lost', event)]

    def test_manager_args_classmethod(self):
        """args() classmethod should return the parser with Window Options group."""
        parser = argparse.ArgumentParser()
        result = WindowEventManager.args(parser)
        assert result is parser
        assert any(group.title == 'Window Options' for group in parser._action_groups)


# ---------------------------------------------------------------------------
# WindowEvents interface and manager tests (from test_events_window_events.py)
# ---------------------------------------------------------------------------


class TestWindowEvents:
    """Test WindowEvents interface functionality."""

    def test_window_events_interface(self):
        """Test WindowEvents interface methods."""
        # Test that WindowEvents has required abstract methods
        assert hasattr(WindowEvents, 'on_window_close_event')
        assert hasattr(WindowEvents, 'on_window_enter_event')
        assert hasattr(WindowEvents, 'on_window_exposed_event')
        assert hasattr(WindowEvents, 'on_window_focus_gained_event')
        assert hasattr(WindowEvents, 'on_window_focus_lost_event')
        assert hasattr(WindowEvents, 'on_window_hidden_event')
        assert hasattr(WindowEvents, 'on_window_hit_test_event')
        assert hasattr(WindowEvents, 'on_window_leave_event')
        assert hasattr(WindowEvents, 'on_window_maximized_event')
        assert hasattr(WindowEvents, 'on_window_minimized_event')
        assert hasattr(WindowEvents, 'on_window_moved_event')
        assert hasattr(WindowEvents, 'on_window_resized_event')
        assert hasattr(WindowEvents, 'on_window_restored_event')
        assert hasattr(WindowEvents, 'on_window_shown_event')
        assert hasattr(WindowEvents, 'on_window_size_changed_event')
        assert hasattr(WindowEvents, 'on_window_take_focus_event')

    def test_window_event_stubs_implementation(self, mocker):
        """Test WindowEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = WindowEventStubs()
        assert hasattr(stub, 'on_window_close_event')
        assert hasattr(stub, 'on_window_enter_event')
        assert hasattr(stub, 'on_window_exposed_event')
        assert hasattr(stub, 'on_window_focus_gained_event')
        assert hasattr(stub, 'on_window_focus_lost_event')

        # Unhandled events raise with these options
        self._give_stub_strict_options(stub)

        # Test method calls
        event = HashableEvent(pygame.WINDOWCLOSE)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_window_close_event(event)

    def test_window_close_event(self):
        """Test window close event handling."""
        scene, manager = window_scene_and_manager()

        # Test window close
        event = HashableEvent(pygame.WINDOWCLOSE)
        manager.on_window_close_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_close'
        assert scene.window_events_received[0][1].type == pygame.WINDOWCLOSE

    def test_window_enter_event(self):
        """Test window enter event handling."""
        scene, manager = window_scene_and_manager()

        # Test window enter
        event = HashableEvent(pygame.WINDOWENTER)
        manager.on_window_enter_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_enter'
        assert scene.window_events_received[0][1].type == pygame.WINDOWENTER

    def test_window_leave_event(self):
        """Test window leave event handling."""
        scene, manager = window_scene_and_manager()

        # Test window leave
        event = HashableEvent(pygame.WINDOWLEAVE)
        manager.on_window_leave_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_leave'
        assert scene.window_events_received[0][1].type == pygame.WINDOWLEAVE

    def test_window_focus_gained_event(self):
        """Test window focus gained event handling."""
        scene, manager = window_scene_and_manager()

        # Test window focus gained
        event = HashableEvent(pygame.WINDOWFOCUSGAINED)
        manager.on_window_focus_gained_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_focus_gained'
        assert scene.window_events_received[0][1].type == pygame.WINDOWFOCUSGAINED

    def test_window_focus_lost_event(self):
        """Test window focus lost event handling."""
        scene, manager = window_scene_and_manager()

        # Test window focus lost
        event = HashableEvent(pygame.WINDOWFOCUSLOST)
        manager.on_window_focus_lost_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_focus_lost'
        assert scene.window_events_received[0][1].type == pygame.WINDOWFOCUSLOST

    def test_window_resized_event(self):
        """Test window resized event handling."""
        scene, manager = window_scene_and_manager()

        # Test window resized
        event = HashableEvent(pygame.WINDOWRESIZED, x=800, y=600)
        manager.on_window_resized_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_resized'
        assert scene.window_events_received[0][1].type == pygame.WINDOWRESIZED
        assert scene.window_events_received[0][1].x == 800
        assert scene.window_events_received[0][1].y == 600

    def test_window_moved_event(self):
        """Test window moved event handling."""
        scene, manager = window_scene_and_manager()

        # Test window moved
        event = HashableEvent(pygame.WINDOWMOVED, x=100, y=100)
        manager.on_window_moved_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_moved'
        assert scene.window_events_received[0][1].type == pygame.WINDOWMOVED
        assert scene.window_events_received[0][1].x == 100
        assert scene.window_events_received[0][1].y == 100

    def test_window_minimized_event(self):
        """Test window minimized event handling."""
        scene, manager = window_scene_and_manager()

        # Test window minimized
        event = HashableEvent(pygame.WINDOWMINIMIZED)
        manager.on_window_minimized_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_minimized'
        assert scene.window_events_received[0][1].type == pygame.WINDOWMINIMIZED

    def test_window_maximized_event(self):
        """Test window maximized event handling."""
        scene, manager = window_scene_and_manager()

        # Test window maximized
        event = HashableEvent(pygame.WINDOWMAXIMIZED)
        manager.on_window_maximized_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_maximized'
        assert scene.window_events_received[0][1].type == pygame.WINDOWMAXIMIZED

    def test_window_restored_event(self):
        """Test window restored event handling."""
        scene, manager = window_scene_and_manager()

        # Test window restored
        event = HashableEvent(pygame.WINDOWRESTORED)
        manager.on_window_restored_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_restored'
        assert scene.window_events_received[0][1].type == pygame.WINDOWRESTORED

    def test_window_shown_event(self):
        """Test window shown event handling."""
        scene, manager = window_scene_and_manager()

        # Test window shown
        event = HashableEvent(pygame.WINDOWSHOWN)
        manager.on_window_shown_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_shown'
        assert scene.window_events_received[0][1].type == pygame.WINDOWSHOWN

    def test_window_hidden_event(self):
        """Test window hidden event handling."""
        scene, manager = window_scene_and_manager()

        # Test window hidden
        event = HashableEvent(pygame.WINDOWHIDDEN)
        manager.on_window_hidden_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_hidden'
        assert scene.window_events_received[0][1].type == pygame.WINDOWHIDDEN

    def test_window_exposed_event(self):
        """Test window exposed event handling."""
        scene, manager = window_scene_and_manager()

        # Test window exposed
        event = HashableEvent(pygame.WINDOWEXPOSED)
        manager.on_window_exposed_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_exposed'
        assert scene.window_events_received[0][1].type == pygame.WINDOWEXPOSED

    def test_window_take_focus_event(self):
        """Test window take focus event handling."""
        scene, manager = window_scene_and_manager()

        # Test window take focus
        event = HashableEvent(pygame.WINDOWTAKEFOCUS)
        manager.on_window_take_focus_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_take_focus'
        assert scene.window_events_received[0][1].type == pygame.WINDOWTAKEFOCUS

    def test_window_size_changed_event(self):
        """Test window size changed event handling."""
        scene, manager = window_scene_and_manager()

        # Test window size changed
        event = HashableEvent(pygame.WINDOWSIZECHANGED, x=1024, y=768)
        manager.on_window_size_changed_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_size_changed'
        assert scene.window_events_received[0][1].type == pygame.WINDOWSIZECHANGED
        assert scene.window_events_received[0][1].x == 1024
        assert scene.window_events_received[0][1].y == 768

    def test_window_hit_test_event(self):
        """Test window hit test event handling."""
        scene, manager = window_scene_and_manager()

        # Test window hit test
        event = HashableEvent(pygame.WINDOWHITTEST)
        manager.on_window_hit_test_event(event)

        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_hit_test'
        assert scene.window_events_received[0][1].type == pygame.WINDOWHITTEST

    def test_window_manager_initialization(self):
        """Test WindowEventManager initializes correctly."""
        scene, manager = window_scene_and_manager()

        assert manager.game is scene
        assert hasattr(manager, 'on_window_close_event')
        assert hasattr(manager, 'on_window_enter_event')

    def test_window_manager_events(self):
        """Test window event handling through manager."""
        scene, manager = window_scene_and_manager()

        # Test window close
        close_event = HashableEvent(pygame.WINDOWCLOSE)
        manager.on_window_close_event(close_event)

        # Test window enter
        enter_event = HashableEvent(pygame.WINDOWENTER)
        manager.on_window_enter_event(enter_event)

        # Test window focus gained
        focus_event = HashableEvent(pygame.WINDOWFOCUSGAINED)
        manager.on_window_focus_gained_event(focus_event)

        assert scene.window_events_received == [
            ('window_close', close_event),
            ('window_enter', enter_event),
            ('window_focus_gained', focus_event),
        ]

    @staticmethod
    def _give_stub_strict_options(stub):
        """Give the stubs options that make unhandled events raise."""
        stub.options = dict(EVENT_TEST_OPTIONS)


class TestWindowEventManagerWithoutVideo:
    """Constructing the manager before pygame's video system is up."""

    def test_unallowed_events_are_logged_and_the_manager_still_works(self, mocker, caplog):
        """set_allowed raises 'video system not initialized' before pygame.display.init()."""
        # The video system is up in every test: simulate set_allowed failing before it is
        mocker.patch(
            'pygame.event.set_allowed',
            side_effect=pygame.error('video system not initialized'),
        )
        game = WindowRecordingScene()

        with caplog.at_level('DEBUG', logger='game.window'):
            manager = WindowEventManager(game=game)

        assert len(manager.proxies) == 1
        assert 'Failed to set allowed window events: pygame not fully initialized' in caplog.text
