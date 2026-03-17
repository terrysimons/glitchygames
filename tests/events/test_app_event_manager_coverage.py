"""Tests for glitchygames.events.app module - AppEventManager."""

import pytest

from glitchygames.events.app import AppEventManager


@pytest.fixture
def mock_game(mocker):
    """Create a mock game object with all required event handlers."""
    return mocker.Mock()


@pytest.fixture
def mock_event(mocker):
    """Create a mock event."""
    return mocker.Mock()


class TestAppEventProxy:
    """Test AppEventProxy event delegation."""

    def test_proxy_init(self, mock_game):
        proxy = AppEventManager.AppEventProxy(game=mock_game)
        assert proxy.game is mock_game

    def test_on_app_did_enter_background_event(self, mock_game, mock_event):
        proxy = AppEventManager.AppEventProxy(game=mock_game)
        proxy.on_app_did_enter_background_event(mock_event)
        mock_game.on_app_did_enter_background_event.assert_called_once_with(mock_event)

    def test_on_app_did_enter_foreground_event(self, mock_game, mock_event):
        proxy = AppEventManager.AppEventProxy(game=mock_game)
        proxy.on_app_did_enter_foreground_event(mock_event)
        mock_game.on_app_did_enter_foreground_event.assert_called_once_with(mock_event)

    def test_on_app_will_enter_background_event(self, mock_game, mock_event):
        proxy = AppEventManager.AppEventProxy(game=mock_game)
        proxy.on_app_will_enter_background_event(mock_event)
        mock_game.on_app_will_enter_background_event.assert_called_once_with(mock_event)

    def test_on_app_will_enter_foreground_event(self, mock_game, mock_event):
        proxy = AppEventManager.AppEventProxy(game=mock_game)
        proxy.on_app_will_enter_foreground_event(mock_event)
        mock_game.on_app_will_enter_foreground_event.assert_called_once_with(mock_event)

    def test_on_app_low_memory_event(self, mock_game, mock_event):
        proxy = AppEventManager.AppEventProxy(game=mock_game)
        proxy.on_app_low_memory_event(mock_event)
        mock_game.on_app_low_memory_event.assert_called_once_with(mock_event)

    def test_on_app_terminating_event(self, mock_game, mock_event):
        proxy = AppEventManager.AppEventProxy(game=mock_game)
        proxy.on_app_terminating_event(mock_event)
        mock_game.on_app_terminating_event.assert_called_once_with(mock_event)


class TestAppEventManager:
    """Test AppEventManager initialization."""

    def test_init(self, mock_game):
        manager = AppEventManager(game=mock_game)
        assert manager.game is mock_game
        assert len(manager.proxies) == 1
