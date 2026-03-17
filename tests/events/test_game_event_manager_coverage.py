"""Tests for glitchygames.events.game module - GameEventManager."""

import pytest

from glitchygames.events import HashableEvent
from glitchygames.events.game import GameEventManager


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
