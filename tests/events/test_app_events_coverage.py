"""Additional coverage tests for app event handling.

Tests cover: AppEventProxy forwarding methods, AppEventManager initialization
with pygame error, and proxy forwarding when game lacks handlers.
"""

import pygame
import pytest

from glitchygames.events import HashableEvent
from glitchygames.events.app import AppEventManager

pytestmark = pytest.mark.usefixtures('mock_pygame_patches')


class TestAppEventProxyForwarding:
    """Test AppEventProxy forwarding to game objects."""

    def test_proxy_forwards_did_enter_background(self, mocker):
        """Test proxy forwards on_app_did_enter_background_event."""
        mock_game = mocker.Mock()
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_DIDENTERBACKGROUND)
        proxy.on_app_did_enter_background_event(event)

        mock_game.on_app_did_enter_background_event.assert_called_once_with(event)

    def test_proxy_forwards_did_enter_foreground(self, mocker):
        """Test proxy forwards on_app_did_enter_foreground_event."""
        mock_game = mocker.Mock()
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_DIDENTERFOREGROUND)
        proxy.on_app_did_enter_foreground_event(event)

        mock_game.on_app_did_enter_foreground_event.assert_called_once_with(event)

    def test_proxy_forwards_will_enter_background(self, mocker):
        """Test proxy forwards on_app_will_enter_background_event."""
        mock_game = mocker.Mock()
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_WILLENTERBACKGROUND)
        proxy.on_app_will_enter_background_event(event)

        mock_game.on_app_will_enter_background_event.assert_called_once_with(event)

    def test_proxy_forwards_will_enter_foreground(self, mocker):
        """Test proxy forwards on_app_will_enter_foreground_event."""
        mock_game = mocker.Mock()
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_WILLENTERFOREGROUND)
        proxy.on_app_will_enter_foreground_event(event)

        mock_game.on_app_will_enter_foreground_event.assert_called_once_with(event)

    def test_proxy_forwards_low_memory(self, mocker):
        """Test proxy forwards on_app_low_memory_event."""
        mock_game = mocker.Mock()
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_LOWMEMORY)
        proxy.on_app_low_memory_event(event)

        mock_game.on_app_low_memory_event.assert_called_once_with(event)

    def test_proxy_forwards_terminating(self, mocker):
        """Test proxy forwards on_app_terminating_event."""
        mock_game = mocker.Mock()
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_TERMINATING)
        proxy.on_app_terminating_event(event)

        mock_game.on_app_terminating_event.assert_called_once_with(event)


class TestAppEventProxyMissingHandlers:
    """Test AppEventProxy when game object lacks handler methods."""

    def test_proxy_skips_missing_did_enter_background(self, mocker):
        """Test proxy does nothing when game lacks on_app_did_enter_background_event."""
        mock_game = mocker.Mock(spec=[])  # Empty spec, no methods
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_DIDENTERBACKGROUND)

        # Should not raise
        proxy.on_app_did_enter_background_event(event)

    def test_proxy_skips_missing_did_enter_foreground(self, mocker):
        """Test proxy does nothing when game lacks on_app_did_enter_foreground_event."""
        mock_game = mocker.Mock(spec=[])
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_DIDENTERFOREGROUND)
        proxy.on_app_did_enter_foreground_event(event)

    def test_proxy_skips_missing_will_enter_background(self, mocker):
        """Test proxy does nothing when game lacks on_app_will_enter_background_event."""
        mock_game = mocker.Mock(spec=[])
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_WILLENTERBACKGROUND)
        proxy.on_app_will_enter_background_event(event)

    def test_proxy_skips_missing_will_enter_foreground(self, mocker):
        """Test proxy does nothing when game lacks on_app_will_enter_foreground_event."""
        mock_game = mocker.Mock(spec=[])
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_WILLENTERFOREGROUND)
        proxy.on_app_will_enter_foreground_event(event)

    def test_proxy_skips_missing_low_memory(self, mocker):
        """Test proxy does nothing when game lacks on_app_low_memory_event."""
        mock_game = mocker.Mock(spec=[])
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_LOWMEMORY)
        proxy.on_app_low_memory_event(event)

    def test_proxy_skips_missing_terminating(self, mocker):
        """Test proxy does nothing when game lacks on_app_terminating_event."""
        mock_game = mocker.Mock(spec=[])
        manager = AppEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.APP_TERMINATING)
        proxy.on_app_terminating_event(event)


class TestAppEventManagerInit:
    """Test AppEventManager initialization edge cases."""

    def test_init_handles_pygame_error(self, mocker):
        """Test that init handles pygame.error when setting allowed events."""
        mocker.patch('pygame.event.set_allowed', side_effect=pygame.error('not initialized'))
        mock_game = mocker.Mock()

        # Should not raise despite pygame.error
        manager = AppEventManager(game=mock_game)

        assert manager.game is mock_game
        assert len(manager.proxies) == 1
