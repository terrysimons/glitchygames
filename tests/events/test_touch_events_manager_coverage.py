"""Tests for glitchygames.events.touch module - TouchEventManager."""

import pygame
import pytest

from glitchygames.events.touch import TouchEventManager


@pytest.fixture
def mock_game(mocker):
    """Create a mock game object with all required event handlers."""
    return mocker.Mock()


@pytest.fixture
def mock_event(mocker):
    """Create a mock pygame event."""
    return mocker.Mock(spec=pygame.event.Event)


class TestTouchEventProxy:
    """Test TouchEventProxy event delegation."""

    def test_proxy_init(self, mock_game):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game)
        assert proxy.game is mock_game
        assert mock_game in proxy.proxies

    def test_on_touch_down_event(self, mock_game, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game)
        proxy.on_touch_down_event(mock_event)
        mock_game.on_touch_down_event.assert_called_once_with(mock_event)

    def test_on_touch_motion_event(self, mock_game, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game)
        proxy.on_touch_motion_event(mock_event)
        mock_game.on_touch_motion_event.assert_called_once_with(mock_event)

    def test_on_touch_up_event(self, mock_game, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game)
        proxy.on_touch_up_event(mock_event)
        mock_game.on_touch_up_event.assert_called_once_with(mock_event)

    def test_on_multi_touch_down_event(self, mock_game, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game)
        proxy.on_multi_touch_down_event(mock_event)
        mock_game.on_multi_touch_down_event.assert_called_once_with(mock_event)

    def test_on_multi_touch_motion_event(self, mock_game, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game)
        proxy.on_multi_touch_motion_event(mock_event)
        mock_game.on_multi_touch_motion_event.assert_called_once_with(mock_event)

    def test_on_multi_touch_up_event(self, mock_game, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game)
        proxy.on_multi_touch_up_event(mock_event)
        mock_game.on_multi_touch_up_event.assert_called_once_with(mock_event)


class TestTouchEventManager:
    """Test TouchEventManager initialization."""

    def test_init(self, mock_game):
        manager = TouchEventManager(game=mock_game)
        assert len(manager.proxies) == 1
