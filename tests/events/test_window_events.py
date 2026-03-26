"""Tests for window event functionality.

This module combines tests for:
- WindowEvents interface and WindowEventStubs
- WindowEventProxy forwarding and delegation
- WindowEventManager initialization, args, and event routing
"""

import argparse
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    UnhandledEventError,
    WindowEvents,
    WindowEventStubs,
)
from glitchygames.events.window import WindowEventManager
from tests.mocks.test_mock_factory import MockFactory

# ---------------------------------------------------------------------------
# Fixtures (from test_window_events_manager_coverage.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_game(mocker):
    """Create a mock game object with all required event handlers."""
    return mocker.Mock()


@pytest.fixture
def mock_event(mocker):
    """Create a mock pygame event."""
    return mocker.Mock(spec=pygame.event.Event)


class TestWindowEventProxy:
    """Test WindowEventProxy event delegation."""

    def test_proxy_init(self, mock_game):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        assert proxy.game is mock_game
        assert mock_game in proxy.proxies

    def test_on_window_close_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_close_event(mock_event)
        mock_game.on_window_close_event.assert_called_once_with(mock_event)

    def test_on_window_enter_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_enter_event(mock_event)
        mock_game.on_window_enter_event.assert_called_once_with(mock_event)

    def test_on_window_exposed_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_exposed_event(mock_event)
        mock_game.on_window_exposed_event.assert_called_once_with(mock_event)

    def test_on_window_focus_gained_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_focus_gained_event(mock_event)
        mock_game.on_window_focus_gained_event.assert_called_once_with(mock_event)

    def test_on_window_focus_lost_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_focus_lost_event(mock_event)
        mock_game.on_window_focus_lost_event.assert_called_once_with(mock_event)

    def test_on_window_hidden_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_hidden_event(mock_event)
        mock_game.on_window_hidden_event.assert_called_once_with(mock_event)

    def test_on_window_hit_test_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_hit_test_event(mock_event)
        mock_game.on_window_hit_test_event.assert_called_once_with(mock_event)

    def test_on_window_leave_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_leave_event(mock_event)
        mock_game.on_window_leave_event.assert_called_once_with(mock_event)

    def test_on_window_maximized_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_maximized_event(mock_event)
        mock_game.on_window_maximized_event.assert_called_once_with(mock_event)

    def test_on_window_minimized_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_minimized_event(mock_event)
        mock_game.on_window_minimized_event.assert_called_once_with(mock_event)

    def test_on_window_moved_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_moved_event(mock_event)
        mock_game.on_window_moved_event.assert_called_once_with(mock_event)

    def test_on_window_resized_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_resized_event(mock_event)
        mock_game.on_window_resized_event.assert_called_once_with(mock_event)

    def test_on_window_restored_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_restored_event(mock_event)
        mock_game.on_window_restored_event.assert_called_once_with(mock_event)

    def test_on_window_shown_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_shown_event(mock_event)
        mock_game.on_window_shown_event.assert_called_once_with(mock_event)

    def test_on_window_size_changed_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_size_changed_event(mock_event)
        mock_game.on_window_size_changed_event.assert_called_once_with(mock_event)

    def test_on_window_take_focus_event(self, mock_game, mock_event):
        proxy = WindowEventManager.WindowEventProxy(game=mock_game)
        proxy.on_window_take_focus_event(mock_event)
        mock_game.on_window_take_focus_event.assert_called_once_with(mock_event)


class TestWindowEventManager:
    """Test WindowEventManager initialization."""

    def test_init(self, mock_game):
        manager = WindowEventManager(game=mock_game)
        assert len(manager.proxies) == 1

    def test_args(self):

        parser = argparse.ArgumentParser()
        result = WindowEventManager.args(parser)
        assert result is parser


# ---------------------------------------------------------------------------
# WindowEventProxy forwarding tests (from test_window_events_coverage.py)
# ---------------------------------------------------------------------------


class TestWindowEventProxyForwarding:
    """Test each WindowEventProxy forwarding method individually."""

    def _create_manager(self, mocker):
        """Create a WindowEventManager with a mock game.

        Returns:
            Tuple of (manager, mock_game).
        """
        mock_game = mocker.Mock()
        manager = WindowEventManager(game=mock_game)
        return manager, mock_game

    def test_proxy_on_window_hidden_event(self, mock_pygame_patches, mocker):
        """Window hidden event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWHIDDEN)
        manager.on_window_hidden_event(event)

        mock_game.on_window_hidden_event.assert_called_once_with(event)

    def test_proxy_on_window_hit_test_event(self, mock_pygame_patches, mocker):
        """Window hit test event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWHITTEST)
        manager.on_window_hit_test_event(event)

        mock_game.on_window_hit_test_event.assert_called_once_with(event)

    def test_proxy_on_window_maximized_event(self, mock_pygame_patches, mocker):
        """Window maximized event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWMAXIMIZED)
        manager.on_window_maximized_event(event)

        mock_game.on_window_maximized_event.assert_called_once_with(event)

    def test_proxy_on_window_minimized_event(self, mock_pygame_patches, mocker):
        """Window minimized event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWMINIMIZED)
        manager.on_window_minimized_event(event)

        mock_game.on_window_minimized_event.assert_called_once_with(event)

    def test_proxy_on_window_moved_event(self, mock_pygame_patches, mocker):
        """Window moved event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWMOVED, x=100, y=200)
        manager.on_window_moved_event(event)

        mock_game.on_window_moved_event.assert_called_once_with(event)

    def test_proxy_on_window_resized_event(self, mock_pygame_patches, mocker):
        """Window resized event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWRESIZED, x=1024, y=768)
        manager.on_window_resized_event(event)

        mock_game.on_window_resized_event.assert_called_once_with(event)

    def test_proxy_on_window_restored_event(self, mock_pygame_patches, mocker):
        """Window restored event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWRESTORED)
        manager.on_window_restored_event(event)

        mock_game.on_window_restored_event.assert_called_once_with(event)

    def test_proxy_on_window_shown_event(self, mock_pygame_patches, mocker):
        """Window shown event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWSHOWN)
        manager.on_window_shown_event(event)

        mock_game.on_window_shown_event.assert_called_once_with(event)

    def test_proxy_on_window_size_changed_event(self, mock_pygame_patches, mocker):
        """Window size changed event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWSIZECHANGED, x=800, y=600)
        manager.on_window_size_changed_event(event)

        mock_game.on_window_size_changed_event.assert_called_once_with(event)

    def test_proxy_on_window_take_focus_event(self, mock_pygame_patches, mocker):
        """Window take focus event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWTAKEFOCUS)
        manager.on_window_take_focus_event(event)

        mock_game.on_window_take_focus_event.assert_called_once_with(event)

    def test_proxy_on_window_exposed_event(self, mock_pygame_patches, mocker):
        """Window exposed event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWEXPOSED)
        manager.on_window_exposed_event(event)

        mock_game.on_window_exposed_event.assert_called_once_with(event)

    def test_proxy_on_window_leave_event(self, mock_pygame_patches, mocker):
        """Window leave event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWLEAVE)
        manager.on_window_leave_event(event)

        mock_game.on_window_leave_event.assert_called_once_with(event)

    def test_proxy_on_window_focus_lost_event(self, mock_pygame_patches, mocker):
        """Window focus lost event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWFOCUSLOST)
        manager.on_window_focus_lost_event(event)

        mock_game.on_window_focus_lost_event.assert_called_once_with(event)

    def test_manager_args_classmethod(self, mock_pygame_patches, mocker):
        """args() classmethod should return the parser with Window Options group."""
        parser = argparse.ArgumentParser()
        result = WindowEventManager.args(parser)
        assert result is parser


# ---------------------------------------------------------------------------
# WindowEvents interface and manager tests (from test_events_window_events.py)
# ---------------------------------------------------------------------------


class TestWindowEvents:
    """Test WindowEvents interface functionality."""

    def test_window_events_interface(self, mock_pygame_patches):
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

    def test_window_event_stubs_implementation(self, mock_pygame_patches, mocker):
        """Test WindowEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = WindowEventStubs()
        assert hasattr(stub, 'on_window_close_event')
        assert hasattr(stub, 'on_window_enter_event')
        assert hasattr(stub, 'on_window_exposed_event')
        assert hasattr(stub, 'on_window_focus_gained_event')
        assert hasattr(stub, 'on_window_focus_lost_event')

        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.WINDOWCLOSE)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.core.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_window_close_event(event)

    def test_window_close_event(self, mock_pygame_patches):
        """Test window close event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_close_event': lambda event: (
                    scene.window_events_received.append(('window_close', event)),
                    True,
                )[1],
            },
        )

        # Test window close
        event = HashableEvent(pygame.WINDOWCLOSE)
        result = scene.on_window_close_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_close'
        assert scene.window_events_received[0][1].type == pygame.WINDOWCLOSE

    def test_window_enter_event(self, mock_pygame_patches):
        """Test window enter event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_enter_event': lambda event: (
                    scene.window_events_received.append(('window_enter', event)),
                    True,
                )[1],
            },
        )

        # Test window enter
        event = HashableEvent(pygame.WINDOWENTER)
        result = scene.on_window_enter_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_enter'
        assert scene.window_events_received[0][1].type == pygame.WINDOWENTER

    def test_window_leave_event(self, mock_pygame_patches):
        """Test window leave event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_leave_event': lambda event: (
                    scene.window_events_received.append(('window_leave', event)),
                    True,
                )[1],
            },
        )

        # Test window leave
        event = HashableEvent(pygame.WINDOWLEAVE)
        result = scene.on_window_leave_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_leave'
        assert scene.window_events_received[0][1].type == pygame.WINDOWLEAVE

    def test_window_focus_gained_event(self, mock_pygame_patches):
        """Test window focus gained event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_focus_gained_event': lambda event: (
                    scene.window_events_received.append(('window_focus_gained', event)),
                    True,
                )[1],
            },
        )

        # Test window focus gained
        event = HashableEvent(pygame.WINDOWFOCUSGAINED)
        result = scene.on_window_focus_gained_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_focus_gained'
        assert scene.window_events_received[0][1].type == pygame.WINDOWFOCUSGAINED

    def test_window_focus_lost_event(self, mock_pygame_patches):
        """Test window focus lost event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_focus_lost_event': lambda event: (
                    scene.window_events_received.append(('window_focus_lost', event)),
                    True,
                )[1],
            },
        )

        # Test window focus lost
        event = HashableEvent(pygame.WINDOWFOCUSLOST)
        result = scene.on_window_focus_lost_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_focus_lost'
        assert scene.window_events_received[0][1].type == pygame.WINDOWFOCUSLOST

    def test_window_resized_event(self, mock_pygame_patches):
        """Test window resized event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_resized_event': lambda event: (
                    scene.window_events_received.append(('window_resized', event)),
                    True,
                )[1],
            },
        )

        # Test window resized
        event = HashableEvent(pygame.WINDOWRESIZED, x=800, y=600)
        result = scene.on_window_resized_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_resized'
        assert scene.window_events_received[0][1].type == pygame.WINDOWRESIZED
        assert scene.window_events_received[0][1].x == 800
        assert scene.window_events_received[0][1].y == 600

    def test_window_moved_event(self, mock_pygame_patches):
        """Test window moved event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_moved_event': lambda event: (
                    scene.window_events_received.append(('window_moved', event)),
                    True,
                )[1],
            },
        )

        # Test window moved
        event = HashableEvent(pygame.WINDOWMOVED, x=100, y=100)
        result = scene.on_window_moved_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_moved'
        assert scene.window_events_received[0][1].type == pygame.WINDOWMOVED
        assert scene.window_events_received[0][1].x == 100
        assert scene.window_events_received[0][1].y == 100

    def test_window_minimized_event(self, mock_pygame_patches):
        """Test window minimized event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_minimized_event': lambda event: (
                    scene.window_events_received.append(('window_minimized', event)),
                    True,
                )[1],
            },
        )

        # Test window minimized
        event = HashableEvent(pygame.WINDOWMINIMIZED)
        result = scene.on_window_minimized_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_minimized'
        assert scene.window_events_received[0][1].type == pygame.WINDOWMINIMIZED

    def test_window_maximized_event(self, mock_pygame_patches):
        """Test window maximized event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_maximized_event': lambda event: (
                    scene.window_events_received.append(('window_maximized', event)),
                    True,
                )[1],
            },
        )

        # Test window maximized
        event = HashableEvent(pygame.WINDOWMAXIMIZED)
        result = scene.on_window_maximized_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_maximized'
        assert scene.window_events_received[0][1].type == pygame.WINDOWMAXIMIZED

    def test_window_restored_event(self, mock_pygame_patches):
        """Test window restored event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_restored_event': lambda event: (
                    scene.window_events_received.append(('window_restored', event)),
                    True,
                )[1],
            },
        )

        # Test window restored
        event = HashableEvent(pygame.WINDOWRESTORED)
        result = scene.on_window_restored_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_restored'
        assert scene.window_events_received[0][1].type == pygame.WINDOWRESTORED

    def test_window_shown_event(self, mock_pygame_patches):
        """Test window shown event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_shown_event': lambda event: (
                    scene.window_events_received.append(('window_shown', event)),
                    True,
                )[1],
            },
        )

        # Test window shown
        event = HashableEvent(pygame.WINDOWSHOWN)
        result = scene.on_window_shown_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_shown'
        assert scene.window_events_received[0][1].type == pygame.WINDOWSHOWN

    def test_window_hidden_event(self, mock_pygame_patches):
        """Test window hidden event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_hidden_event': lambda event: (
                    scene.window_events_received.append(('window_hidden', event)),
                    True,
                )[1],
            },
        )

        # Test window hidden
        event = HashableEvent(pygame.WINDOWHIDDEN)
        result = scene.on_window_hidden_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_hidden'
        assert scene.window_events_received[0][1].type == pygame.WINDOWHIDDEN

    def test_window_exposed_event(self, mock_pygame_patches):
        """Test window exposed event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_exposed_event': lambda event: (
                    scene.window_events_received.append(('window_exposed', event)),
                    True,
                )[1],
            },
        )

        # Test window exposed
        event = HashableEvent(pygame.WINDOWEXPOSED)
        result = scene.on_window_exposed_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_exposed'
        assert scene.window_events_received[0][1].type == pygame.WINDOWEXPOSED

    def test_window_take_focus_event(self, mock_pygame_patches):
        """Test window take focus event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_take_focus_event': lambda event: (
                    scene.window_events_received.append(('window_take_focus', event)),
                    True,
                )[1],
            },
        )

        # Test window take focus
        event = HashableEvent(pygame.WINDOWTAKEFOCUS)
        result = scene.on_window_take_focus_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_take_focus'
        assert scene.window_events_received[0][1].type == pygame.WINDOWTAKEFOCUS

    def test_window_size_changed_event(self, mock_pygame_patches):
        """Test window size changed event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_size_changed_event': lambda event: (
                    scene.window_events_received.append(('window_size_changed', event)),
                    True,
                )[1],
            },
        )

        # Test window size changed
        event = HashableEvent(pygame.WINDOWSIZECHANGED, x=1024, y=768)
        result = scene.on_window_size_changed_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_size_changed'
        assert scene.window_events_received[0][1].type == pygame.WINDOWSIZECHANGED
        assert scene.window_events_received[0][1].x == 1024
        assert scene.window_events_received[0][1].y == 768

    def test_window_hit_test_event(self, mock_pygame_patches):
        """Test window hit test event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_window_hit_test_event': lambda event: (
                    scene.window_events_received.append(('window_hit_test', event)),
                    True,
                )[1],
            },
        )

        # Test window hit test
        event = HashableEvent(pygame.WINDOWHITTEST)
        result = scene.on_window_hit_test_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.window_events_received) == 1
        assert scene.window_events_received[0][0] == 'window_hit_test'
        assert scene.window_events_received[0][1].type == pygame.WINDOWHITTEST

    def test_window_manager_initialization(self, mock_pygame_patches, mocker):
        """Test WindowEventManager initializes correctly."""
        from glitchygames.events.window import WindowEventManager

        mock_game = mocker.Mock()
        manager = WindowEventManager(game=mock_game)

        assert manager.game == mock_game
        assert hasattr(manager, 'on_window_close_event')
        assert hasattr(manager, 'on_window_enter_event')

    def test_window_manager_events(self, mock_pygame_patches, mocker):
        """Test window event handling through manager."""
        from glitchygames.events.window import WindowEventManager

        mock_game = mocker.Mock()
        manager = WindowEventManager(game=mock_game)

        # Test window close
        close_event = HashableEvent(pygame.WINDOWCLOSE)
        manager.on_window_close_event(close_event)

        # Test window enter
        enter_event = HashableEvent(pygame.WINDOWENTER)
        manager.on_window_enter_event(enter_event)

        # Test window focus gained
        focus_event = HashableEvent(pygame.WINDOWFOCUSGAINED)
        manager.on_window_focus_gained_event(focus_event)

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
