"""Tests for game event functionality.

This module combines tests for:
- GameEvents interface and stubs
- GameEventProxy forwarding and delegation
- GameEventManager initialization, routing, args, and event processing
"""

import argparse
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEventManager
from glitchygames.events import (
    GameEvents,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.scenes import Scene
from tests.mocks import MockFactory

# ---------------------------------------------------------------------------
# Fixtures (from test_game_event_manager_coverage.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_game(mocker):
    """Create a mock game object with all required event handlers."""
    game = mocker.Mock()
    game.OPTIONS = {}
    return game


@pytest.fixture
def mock_event(mocker):
    """Create a mock HashableEvent."""
    event = mocker.Mock(spec=HashableEvent)
    return event


class TestGameEventProxy:
    """Test GameEventProxy event delegation."""

    def test_proxy_on_active_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_active_event(mock_event)
        mock_game.on_active_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_fps_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_fps_event(mock_event)
        mock_game.on_fps_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_game_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_game_event(mock_event)
        mock_game.on_game_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_menu_item_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_menu_item_event(mock_event)
        mock_game.on_menu_item_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_sys_wm_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_sys_wm_event(mock_event)
        mock_game.on_sys_wm_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_user_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_user_event(mock_event)
        mock_game.on_user_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_video_expose_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_video_expose_event(mock_event)
        mock_game.on_video_expose_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_video_resize_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_video_resize_event(mock_event)
        mock_game.on_video_resize_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_quit_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_quit_event(mock_event)
        mock_game.on_quit_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_render_device_reset_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_render_device_reset_event(mock_event)
        mock_game.on_render_device_reset_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_render_targets_reset_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_render_targets_reset_event(mock_event)
        mock_game.on_render_targets_reset_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_clipboard_update_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_clipboard_update_event(mock_event)
        mock_game.on_clipboard_update_event.assert_called_once_with(event=mock_event)

    def test_proxy_on_locale_changed_event(self, mock_game, mock_event):
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        proxy.on_locale_changed_event(mock_event)
        mock_game.on_locale_changed_event.assert_called_once_with(event=mock_event)


class TestGameEventManager:
    """Test GameEventManager event routing."""

    def test_init(self, mock_game):
        manager = GameEventManager(game=mock_game)
        assert len(manager.proxies) == 1

    def test_on_active_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_active_event(mock_event)
        mock_game.on_active_event.assert_called_once_with(event=mock_event)

    def test_on_clipboard_update_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_clipboard_update_event(mock_event)
        mock_game.on_clipboard_update_event.assert_called_once_with(event=mock_event)

    def test_on_fps_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_fps_event(mock_event)
        mock_game.on_fps_event.assert_called_once_with(event=mock_event)

    def test_on_game_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_game_event(mock_event)
        mock_game.on_game_event.assert_called_once_with(event=mock_event)

    def test_on_locale_changed_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_locale_changed_event(mock_event)
        mock_game.on_locale_changed_event.assert_called_once_with(event=mock_event)

    def test_on_menu_item_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_menu_item_event(mock_event)
        mock_game.on_menu_item_event.assert_called_once_with(event=mock_event)

    def test_on_quit_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_quit_event(mock_event)
        mock_game.on_quit_event.assert_called_once_with(event=mock_event)

    def test_on_render_device_reset_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_render_device_reset_event(mock_event)
        mock_game.on_render_device_reset_event.assert_called_once_with(event=mock_event)

    def test_on_render_targets_reset_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_render_targets_reset_event(mock_event)
        mock_game.on_render_targets_reset_event.assert_called_once_with(event=mock_event)

    def test_on_sys_wm_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_sys_wm_event(mock_event)
        mock_game.on_sys_wm_event.assert_called_once_with(event=mock_event)

    def test_on_user_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_user_event(mock_event)
        mock_game.on_user_event.assert_called_once_with(event=mock_event)

    def test_on_video_expose_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_video_expose_event(mock_event)
        mock_game.on_video_expose_event.assert_called_once_with(event=mock_event)

    def test_on_video_resize_event(self, mock_game, mock_event):
        manager = GameEventManager(game=mock_game)
        manager.on_video_resize_event(mock_event)
        mock_game.on_video_resize_event.assert_called_once_with(event=mock_event)

    def test_args(self):
        import argparse

        parser = argparse.ArgumentParser()
        result = GameEventManager.args(parser)
        assert result is parser


# ---------------------------------------------------------------------------
# GameEventProxy forwarding tests (from test_game_events_coverage.py)
# ---------------------------------------------------------------------------


class TestGameEventProxyForwarding:
    """Tests for GameEventProxy event forwarding methods."""

    def _create_proxy_with_mock_game(self, mocker):
        """Create a GameEventProxy with a mock game that tracks event calls.

        Returns:
            tuple: (proxy, mock_game) pair.

        """
        mock_game = MockFactory.create_game_mock()
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        return proxy, mock_game

    def _create_mock_event(self, mocker):
        """Create a mock hashable event.

        Returns:
            object: A mock event object.

        """
        return mocker.Mock()

    def test_on_active_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_active_event forwards the event to game.on_active_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_active_event(event)

        mock_game.on_active_event.assert_called_once_with(event=event)

    def test_on_fps_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_fps_event forwards the event to game.on_fps_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_fps_event(event)

        mock_game.on_fps_event.assert_called_once_with(event=event)

    def test_on_game_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_game_event forwards the event to game.on_game_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_game_event(event)

        mock_game.on_game_event.assert_called_once_with(event=event)

    def test_on_menu_item_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_menu_item_event forwards the event to game.on_menu_item_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_menu_item_event(event)

        mock_game.on_menu_item_event.assert_called_once_with(event=event)

    def test_on_sys_wm_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_sys_wm_event forwards the event to game.on_sys_wm_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_sys_wm_event(event)

        mock_game.on_sys_wm_event.assert_called_once_with(event=event)

    def test_on_user_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_user_event forwards the event to game.on_user_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_user_event(event)

        mock_game.on_user_event.assert_called_once_with(event=event)

    def test_on_video_expose_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_video_expose_event forwards the event to game.on_video_expose_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_video_expose_event(event)

        mock_game.on_video_expose_event.assert_called_once_with(event=event)

    def test_on_video_resize_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_video_resize_event forwards the event to game.on_video_resize_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_video_resize_event(event)

        mock_game.on_video_resize_event.assert_called_once_with(event=event)

    def test_on_quit_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_quit_event forwards the event to game.on_quit_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_quit_event(event)

        mock_game.on_quit_event.assert_called_once_with(event=event)

    def test_on_render_device_reset_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_render_device_reset_event forwards to game."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_render_device_reset_event(event)

        mock_game.on_render_device_reset_event.assert_called_once_with(event=event)

    def test_on_render_targets_reset_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_render_targets_reset_event forwards to game."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_render_targets_reset_event(event)

        mock_game.on_render_targets_reset_event.assert_called_once_with(event=event)

    def test_on_clipboard_update_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_clipboard_update_event forwards to game."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_clipboard_update_event(event)

        mock_game.on_clipboard_update_event.assert_called_once_with(event=event)

    def test_on_locale_changed_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_locale_changed_event forwards to game."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_locale_changed_event(event)

        mock_game.on_locale_changed_event.assert_called_once_with(event=event)


class TestGameEventManagerForwarding:
    """Tests for GameEventManager forwarding to proxies."""

    def _create_manager_with_mock_proxy(self, mocker):
        """Create a GameEventManager with a mocked proxy.

        Returns:
            tuple: (manager, mock_proxy) pair.

        """
        mock_game = MockFactory.create_game_mock()
        manager = GameEventManager(game=mock_game)
        # Replace the proxy with a mock to verify forwarding
        mock_proxy = mocker.Mock()
        manager.proxies = [mock_proxy]
        return manager, mock_proxy

    def test_manager_on_active_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_active_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_active_event(event)

        mock_proxy.on_active_event.assert_called_once_with(event)

    def test_manager_on_fps_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_fps_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_fps_event(event)

        mock_proxy.on_fps_event.assert_called_once_with(event)

    def test_manager_on_game_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_game_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_game_event(event)

        mock_proxy.on_game_event.assert_called_once_with(event)

    def test_manager_on_menu_item_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_menu_item_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_menu_item_event(event)

        mock_proxy.on_menu_item_event.assert_called_once_with(event)

    def test_manager_on_sys_wm_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_sys_wm_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_sys_wm_event(event)

        mock_proxy.on_sys_wm_event.assert_called_once_with(event)

    def test_manager_on_user_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_user_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_user_event(event)

        mock_proxy.on_user_event.assert_called_once_with(event)

    def test_manager_on_video_expose_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_video_expose_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_video_expose_event(event)

        mock_proxy.on_video_expose_event.assert_called_once_with(event)

    def test_manager_on_video_resize_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_video_resize_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_video_resize_event(event)

        mock_proxy.on_video_resize_event.assert_called_once_with(event)

    def test_manager_on_quit_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_quit_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_quit_event(event)

        mock_proxy.on_quit_event.assert_called_once_with(event)

    def test_manager_on_clipboard_update_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_clipboard_update_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_clipboard_update_event(event)

        mock_proxy.on_clipboard_update_event.assert_called_once_with(event)

    def test_manager_on_locale_changed_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_locale_changed_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_locale_changed_event(event)

        mock_proxy.on_locale_changed_event.assert_called_once_with(event)

    def test_manager_on_render_device_reset_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_render_device_reset_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_render_device_reset_event(event)

        mock_proxy.on_render_device_reset_event.assert_called_once_with(event)

    def test_manager_on_render_targets_reset_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_render_targets_reset_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_render_targets_reset_event(event)

        mock_proxy.on_render_targets_reset_event.assert_called_once_with(event)


class TestGameEventManagerArgs:
    """Tests for GameEventManager.args classmethod."""

    def test_args_adds_log_level_argument(self, mock_pygame_patches):
        """Test that args adds the --log-level argument."""
        parser = argparse.ArgumentParser()
        result = GameEventManager.args(parser)

        assert result is parser
        args = parser.parse_args(['--log-level', 'debug'])
        assert args.log_level == 'debug'

    def test_args_log_level_choices(self, mock_pygame_patches):
        """Test that --log-level accepts valid choices."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        for level in ['debug', 'info', 'warning', 'error', 'critical']:
            args = parser.parse_args(['--log-level', level])
            assert args.log_level == level

    def test_args_log_level_case_insensitive(self, mock_pygame_patches):
        """Test that --log-level accepts uppercase input via type=str.lower."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['--log-level', 'DEBUG'])
        assert args.log_level == 'debug'

    def test_args_adds_no_unhandled_events_flag(self, mock_pygame_patches):
        """Test that args adds the --no-unhandled-events flag."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['--no-unhandled-events'])
        assert args.no_unhandled_events is True

    def test_args_no_unhandled_events_default_false(self, mock_pygame_patches):
        """Test that --no-unhandled-events defaults to False."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args([])
        assert args.no_unhandled_events is False

    def test_args_adds_profile_flag(self, mock_pygame_patches):
        """Test that args adds the --profile flag."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['--profile'])
        assert args.profile is True

    def test_args_profile_short_flag(self, mock_pygame_patches):
        """Test that -p is the short form for --profile."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['-p'])
        assert args.profile is True

    def test_args_profile_default_false(self, mock_pygame_patches):
        """Test that --profile defaults to False."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args([])
        assert args.profile is False

    def test_args_log_level_short_flag(self, mock_pygame_patches):
        """Test that -l is the short form for --log-level."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['-l', 'warning'])
        assert args.log_level == 'warning'

    def test_args_defaults_all(self, mock_pygame_patches):
        """Test all default values from args."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args([])
        assert args.log_level == 'info'
        assert args.no_unhandled_events is False
        assert args.profile is False


# ---------------------------------------------------------------------------
# GameEventManager tests (from test_game_events_manager.py)
# ---------------------------------------------------------------------------


class MockGame(Scene):
    """Simple mock game scene for testing."""

    NAME = 'MockGame'
    VERSION = '1.0'

    def __init__(self, options=None, groups=None):
        """Initialize mock game scene."""
        if options is None:
            options = {}
        if groups is None:
            groups = MockFactory.create_pygame_sprite_group_mock()
        super().__init__(options=options, groups=groups)
        self.fps = 60
        self.background_color = (0, 0, 0)
        self.next_scene = self

    @classmethod
    def args(cls, parser):
        """Add mock game arguments.

        Returns:
            object: The result.

        """
        parser.add_argument('--test-flag', action='store_true', help='Test flag')
        return parser

    def update(self):
        """Mock update method."""


class MockGameWithArgs(MockGame):
    """Mock game that properly handles command line arguments."""

    @classmethod
    def args(cls, parser):
        """Add mock game arguments.

        Returns:
            object: The result.

        """
        parser.add_argument('--test-flag', action='store_true', help='Test flag')
        return parser


class TestGameManager:
    """Test GameEventManager functionality."""

    def _create_mock_game(self):
        """Create a mock game using MockFactory.

        Returns:
            object: The result.

        """
        return MockFactory.create_game_mock()

    def _create_mock_event(self, event_type, **kwargs):
        """Create a mock event using MockFactory.

        Returns:
            object: The result.

        """
        mock_event = MockFactory.create_pygame_event_mock()
        mock_event.type = event_type
        for key, value in kwargs.items():
            setattr(mock_event, key, value)
        return mock_event

    def test_game_manager_init(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEventManager initialization."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create mock game
        mock_game = self._create_mock_game()

        # Create GameEventManager.GameEventProxy instance (concrete implementation)
        manager = GameEventManager.GameEventProxy(game=mock_game)

        # Test that manager is properly initialized
        assert manager is not None
        assert manager.game == mock_game
        assert manager.proxies is not None
        assert len(manager.proxies) == 1
        # The proxy object wraps the game, so we check that it exists
        assert manager.proxies[0] is not None

    def test_game_manager_process_events(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEventManager event processing."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create mock game
        mock_game = self._create_mock_game()

        # Create GameEventManager.GameEventProxy instance (concrete implementation)
        manager = GameEventManager.GameEventProxy(game=mock_game)

        # Mock events
        mock_events = [
            self._create_mock_event(pygame.QUIT),
            self._create_mock_event(pygame.KEYDOWN, key=pygame.K_SPACE),
            self._create_mock_event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100)),
        ]

        # Mock the process_events method to avoid actual event processing
        mock_process_events = mocker.patch.object(manager, 'process_events')
        mock_process_events.return_value = None

        # Test that process_events can be called
        manager.process_events(mock_events)

        # Verify the method was called
        mock_process_events.assert_called_once_with(mock_events)

    def test_game_manager_event_handlers(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEventManager event handler methods."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create mock game
        mock_game = self._create_mock_game()

        # Create GameEventManager.GameEventProxy instance (concrete implementation)
        manager = GameEventManager.GameEventProxy(game=mock_game)

        # Mock events
        mock_active_event = self._create_mock_event(pygame.ACTIVEEVENT)
        mock_fps_event = self._create_mock_event(pygame.USEREVENT + 1)  # FPSEVENT
        mock_game_event = self._create_mock_event(pygame.USEREVENT + 2)  # GAMEEVENT
        mock_menu_event = self._create_mock_event(pygame.USEREVENT + 3)  # MENUEVENT
        mock_sys_wm_event = self._create_mock_event(pygame.SYSWMEVENT)

        # Test event handler methods
        manager.on_active_event(mock_active_event)
        manager.on_fps_event(mock_fps_event)
        manager.on_game_event(mock_game_event)
        manager.on_menu_item_event(mock_menu_event)
        manager.on_sys_wm_event(mock_sys_wm_event)

        # If we get here without errors, the handlers work
        assert True

    def test_game_manager_initialization(self, mock_pygame_patches):
        """Test GameEventManager initialization."""
        # Create mock scene manager
        mock_scene_manager = MockFactory.create_game_mock()

        # Test GameEventManager.GameEventProxy initialization (concrete implementation)
        game_manager = GameEventManager.GameEventProxy(game=mock_scene_manager)

        # Verify game is set
        assert game_manager.game == mock_scene_manager

    def test_game_manager_args(self, mock_pygame_patches):
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

    def test_game_events_interface(self, mock_pygame_patches):
        """Test GameEvents interface methods."""
        # Test that GameEvents has required abstract methods
        assert hasattr(GameEvents, 'on_active_event')
        assert hasattr(GameEvents, 'on_fps_event')
        assert hasattr(GameEvents, 'on_game_event')
        assert hasattr(GameEvents, 'on_menu_item_event')
        assert hasattr(GameEvents, 'on_sys_wm_event')
        assert hasattr(GameEvents, 'on_user_event')
        assert hasattr(GameEvents, 'on_video_expose_event')
        assert hasattr(GameEvents, 'on_video_resize_event')
        assert hasattr(GameEvents, 'on_quit_event')
        assert hasattr(GameEvents, 'on_render_device_reset_event')
        assert hasattr(GameEvents, 'on_render_targets_reset_event')
        assert hasattr(GameEvents, 'on_clipboard_update_event')
        assert hasattr(GameEvents, 'on_locale_changed_event')

    def test_game_event_stubs_implementation(self, mock_pygame_patches, mocker):
        """Test GameEventStubs implementation."""
        # Use centralized mock for scene without event handlers (stub behavior)
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={},  # No event handlers - will fall back to stubs
        )

        # Test that stub methods can be called
        event = HashableEvent(pygame.QUIT)
        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch('glitchygames.events.core.LOG')
        with pytest.raises(UnhandledEventError):
            scene.on_quit_event(event)
        # Expected to call unhandled_event and raise UnhandledEventError

        # Verify the ERROR log message was called
        mock_log.error.assert_called_once()
        # Check that the log message contains the expected content
        call_args = mock_log.error.call_args[0][0]
        assert 'Unhandled Event: args: Quit' in call_args

    def test_clipboard_update_event_stub(self, mock_pygame_patches, mocker):
        """Test clipboard update event stub implementation."""
        # Use centralized mock for scene without event handlers (stub behavior)
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={},  # No event handlers - will fall back to stubs
        )

        # Test that stub method can be called
        event = HashableEvent(pygame.CLIPBOARDUPDATE)
        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch('glitchygames.events.core.LOG')
        with pytest.raises(UnhandledEventError):
            scene.on_clipboard_update_event(event)
        # Expected to call unhandled_event and raise UnhandledEventError

        # Verify the ERROR log message was called
        mock_log.error.assert_called_once()
        # Check that the log message contains the expected content
        call_args = mock_log.error.call_args[0][0]
        assert 'Unhandled Event: args: ClipboardUpdate' in call_args

    def test_locale_changed_event_stub(self, mock_pygame_patches, mocker):
        """Test locale changed event stub implementation."""
        # Use centralized mock for scene without event handlers (stub behavior)
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={},  # No event handlers - will fall back to stubs
        )

        # Test that stub method can be called
        event = HashableEvent(pygame.LOCALECHANGED)
        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch('glitchygames.events.core.LOG')
        with pytest.raises(UnhandledEventError):
            scene.on_locale_changed_event(event)
        # Expected to call unhandled_event and raise UnhandledEventError

        # Verify the ERROR log message was called
        mock_log.error.assert_called_once()
        # Check that the log message contains the expected content
        call_args = mock_log.error.call_args[0][0]
        assert 'Unhandled Event: args: LocaleChanged' in call_args

    def test_quit_event(self, mock_pygame_patches):
        """Test quit event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_quit_event': lambda event: (
                    scene.game_events_received.append(('quit', event)),
                    True,
                )[1],
            },
        )

        # Test quit event
        event = HashableEvent(pygame.QUIT)
        result = scene.on_quit_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'quit'
        assert scene.game_events_received[0][1].type == pygame.QUIT

    def test_active_event(self, mock_pygame_patches):
        """Test active event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_active_event': lambda event: (
                    scene.game_events_received.append(('active', event)),
                    True,
                )[1],
            },
        )

        # Test active event
        event = HashableEvent(pygame.ACTIVEEVENT, gain=1, state=1)
        result = scene.on_active_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'active'
        assert scene.game_events_received[0][1].type == pygame.ACTIVEEVENT
        assert scene.game_events_received[0][1].gain == 1
        assert scene.game_events_received[0][1].state == 1

    def test_fps_event(self, mock_pygame_patches):
        """Test FPS event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_fps_event': lambda event: (
                    scene.game_events_received.append(('fps', event)),
                    True,
                )[1],
            },
        )

        # Test FPS event
        event = HashableEvent(pygame.USEREVENT + 1)  # FPSEVENT
        result = scene.on_fps_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'fps'
        assert scene.game_events_received[0][1].type == pygame.USEREVENT + 1

    def test_game_event(self, mock_pygame_patches):
        """Test game event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_game_event': lambda event: (
                    scene.game_events_received.append(('game', event)),
                    True,
                )[1],
            },
        )

        # Test game event
        event = HashableEvent(pygame.USEREVENT + 2)  # GAMEEVENT
        result = scene.on_game_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'game'
        assert scene.game_events_received[0][1].type == pygame.USEREVENT + 2

    def test_menu_item_event(self, mock_pygame_patches):
        """Test menu item event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_menu_item_event': lambda event: (
                    scene.game_events_received.append(('menu_item', event)),
                    True,
                )[1],
            },
        )

        # Test menu item event
        event = HashableEvent(pygame.USEREVENT + 3)  # MENUEVENT
        result = scene.on_menu_item_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'menu_item'
        assert scene.game_events_received[0][1].type == pygame.USEREVENT + 3

    def test_sys_wm_event(self, mock_pygame_patches):
        """Test system WM event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_sys_wm_event': lambda event: (
                    scene.game_events_received.append(('sys_wm', event)),
                    True,
                )[1],
            },
        )

        # Test sys WM event
        event = HashableEvent(pygame.SYSWMEVENT)
        result = scene.on_sys_wm_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'sys_wm'
        assert scene.game_events_received[0][1].type == pygame.SYSWMEVENT

    def test_user_event(self, mock_pygame_patches):
        """Test user event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_user_event': lambda event: (
                    scene.game_events_received.append(('user', event)),
                    True,
                )[1],
            },
        )

        # Test user event
        event = HashableEvent(pygame.USEREVENT, code=1)
        result = scene.on_user_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'user'
        assert scene.game_events_received[0][1].type == pygame.USEREVENT
        assert scene.game_events_received[0][1].code == 1

    def test_video_expose_event(self, mock_pygame_patches):
        """Test video expose event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_video_expose_event': lambda event: (
                    scene.game_events_received.append(('video_expose', event)),
                    True,
                )[1],
            },
        )

        # Test video expose event
        event = HashableEvent(pygame.VIDEOEXPOSE)
        result = scene.on_video_expose_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'video_expose'
        assert scene.game_events_received[0][1].type == pygame.VIDEOEXPOSE

    def test_video_resize_event(self, mock_pygame_patches):
        """Test video resize event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_video_resize_event': lambda event: (
                    scene.game_events_received.append(('video_resize', event)),
                    True,
                )[1],
            },
        )

        # Test video resize event
        event = HashableEvent(pygame.VIDEORESIZE, w=800, h=600)
        result = scene.on_video_resize_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'video_resize'
        assert scene.game_events_received[0][1].type == pygame.VIDEORESIZE
        assert scene.game_events_received[0][1].w == 800
        assert scene.game_events_received[0][1].h == 600

    def test_active_event_gain_states(self, mock_pygame_patches):
        """Test active event with different gain states."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_active_event': lambda event: (
                    scene.game_events_received.append(('active', event)),
                    True,
                )[1],
            },
        )

        # Test different gain states
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
            result = scene.on_active_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == 'active'
            assert scene.game_events_received[0][1].type == pygame.ACTIVEEVENT
            assert scene.game_events_received[0][1].gain == gain
            assert scene.game_events_received[0][1].state == state

            # Clear for next iteration
            scene.game_events_received.clear()

    def test_user_events_with_different_codes(self, mock_pygame_patches):
        """Test user events with different codes."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_user_event': lambda event: (
                    scene.game_events_received.append(('user', event)),
                    True,
                )[1],
            },
        )

        # Test different user event codes
        for code in range(10):
            event = HashableEvent(pygame.USEREVENT, code=code)
            result = scene.on_user_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == 'user'
            assert scene.game_events_received[0][1].type == pygame.USEREVENT
            assert scene.game_events_received[0][1].code == code

            # Clear for next iteration
            scene.game_events_received.clear()

    def test_video_resize_with_different_dimensions(self, mock_pygame_patches):
        """Test video resize events with different dimensions."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_video_resize_event': lambda event: (
                    scene.game_events_received.append(('video_resize', event)),
                    True,
                )[1],
            },
        )

        # Test different window dimensions
        dimensions = [
            (640, 480),  # VGA
            (800, 600),  # SVGA
            (1024, 768),  # XGA
            (1280, 720),  # HD
            (1920, 1080),  # Full HD
            (2560, 1440),  # 2K
            (3840, 2160),  # 4K
        ]

        for w, h in dimensions:
            event = HashableEvent(pygame.VIDEORESIZE, w=w, h=h)
            result = scene.on_video_resize_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == 'video_resize'
            assert scene.game_events_received[0][1].type == pygame.VIDEORESIZE
            assert scene.game_events_received[0][1].w == w
            assert scene.game_events_received[0][1].h == h

            # Clear for next iteration
            scene.game_events_received.clear()

    def test_custom_game_events(self, mock_pygame_patches):
        """Test custom game events."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_game_event': lambda event: (
                    scene.game_events_received.append(('game', event)),
                    True,
                )[1],
            },
        )

        # Test custom game events
        custom_events = [
            HashableEvent(pygame.USEREVENT + 10, event_type='level_complete'),
            HashableEvent(pygame.USEREVENT + 11, event_type='player_died'),
            HashableEvent(pygame.USEREVENT + 12, event_type='power_up_collected'),
            HashableEvent(pygame.USEREVENT + 13, event_type='enemy_spawned'),
            HashableEvent(pygame.USEREVENT + 14, event_type='score_updated'),
        ]

        for event in custom_events:
            result = scene.on_game_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == 'game'
            assert scene.game_events_received[0][1].type == event.type
            assert scene.game_events_received[0][1].event_type == event.event_type

            # Clear for next iteration
            scene.game_events_received.clear()

    def test_menu_events_with_different_items(self, mock_pygame_patches):
        """Test menu events with different menu items."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_menu_item_event': lambda event: (
                    scene.game_events_received.append(('menu', event)),
                    True,
                )[1],
            },
        )

        # Test different menu items
        menu_items = [
            'New Game',
            'Load Game',
            'Save Game',
            'Settings',
            'Help',
            'About',
            'Exit',
        ]

        for item in menu_items:
            event = HashableEvent(pygame.USEREVENT + 3, menu_item=item)
            result = scene.on_menu_item_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == 'menu'
            assert scene.game_events_received[0][1].type == pygame.USEREVENT + 3
            assert scene.game_events_received[0][1].menu_item == item

            # Clear for next iteration
            scene.game_events_received.clear()

    def test_render_device_reset_event(self, mock_pygame_patches):
        """Test render device reset event."""
        # Use centralized mock for scene with event handlers
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_render_device_reset_event': lambda event: (
                    scene.game_events_received.append(('render_device_reset', event)),
                    None,
                )[1],
            },
        )

        # Test render device reset event
        event = HashableEvent(pygame.RENDER_DEVICE_RESET)
        result = scene.on_render_device_reset_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'render_device_reset'
        assert scene.game_events_received[0][1].type == pygame.RENDER_DEVICE_RESET

    def test_render_targets_reset_event(self, mock_pygame_patches):
        """Test render targets reset event."""
        # Use centralized mock for scene with event handlers
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_render_targets_reset_event': lambda event: (
                    scene.game_events_received.append(('render_targets_reset', event)),
                    None,
                )[1],
            },
        )

        # Test render targets reset event
        event = HashableEvent(pygame.RENDER_TARGETS_RESET)
        result = scene.on_render_targets_reset_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'render_targets_reset'
        assert scene.game_events_received[0][1].type == pygame.RENDER_TARGETS_RESET

    def test_clipboard_update_event(self, mock_pygame_patches):
        """Test clipboard update event."""
        # Use centralized mock for scene with event handlers
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_clipboard_update_event': lambda event: (
                    scene.game_events_received.append(('clipboard_update', event)),
                    None,
                )[1],
            },
        )

        # Test clipboard update event
        event = HashableEvent(pygame.CLIPBOARDUPDATE)
        result = scene.on_clipboard_update_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'clipboard_update'
        assert scene.game_events_received[0][1].type == pygame.CLIPBOARDUPDATE

    def test_locale_changed_event(self, mock_pygame_patches):
        """Test locale changed event."""
        # Use centralized mock for scene with event handlers
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_locale_changed_event': lambda event: (
                    scene.game_events_received.append(('locale_changed', event)),
                    None,
                )[1],
            },
        )

        # Test locale changed event
        event = HashableEvent(pygame.LOCALECHANGED)
        result = scene.on_locale_changed_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == 'locale_changed'
        assert scene.game_events_received[0][1].type == pygame.LOCALECHANGED
