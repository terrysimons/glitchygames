"""Tests for glitchygames.events.window module - WindowEventManager."""

import pygame
import pytest

from glitchygames.events.window import WindowEventManager


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
        import argparse

        parser = argparse.ArgumentParser()
        result = WindowEventManager.args(parser)
        assert result is parser
