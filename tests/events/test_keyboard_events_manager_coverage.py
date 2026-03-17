"""Tests for glitchygames.events.keyboard module - KeyboardEventManager."""

import pygame
import pytest

from glitchygames.events.keyboard import KeyboardEventManager


@pytest.fixture
def mock_game(mocker):
    """Create a mock game object with all required event handlers."""
    return mocker.Mock()


class TestKeyboardEventProxy:
    """Test KeyboardEventProxy event delegation."""

    def test_proxy_init(self, mock_game):
        proxy = KeyboardEventManager.KeyboardEventProxy(game=mock_game)
        assert proxy.game is mock_game
        assert proxy.keys == {}

    def test_on_key_down_event(self, mock_game, mocker):
        proxy = KeyboardEventManager.KeyboardEventProxy(game=mock_game)
        # Use a mock event that supports item assignment like HashableEvent does
        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.dict = {
            'type': pygame.KEYDOWN,
            'key': pygame.K_a,
            'mod': 0,
            'unicode': 'a',
            'scancode': 30,
        }
        event.__setitem__ = mocker.Mock()
        proxy.on_key_down_event(event)
        mock_game.on_key_down_event.assert_called_once_with(event)
        mock_game.on_key_chord_down_event.assert_called_once()

    def test_on_key_up_event(self, mock_game, mocker):
        proxy = KeyboardEventManager.KeyboardEventProxy(game=mock_game)
        event = mocker.Mock()
        event.type = pygame.KEYUP
        event.dict = {'type': pygame.KEYUP, 'key': pygame.K_a, 'mod': 0, 'scancode': 30}
        proxy.on_key_up_event(event)
        mock_game.on_key_up_event.assert_called_once_with(event)
        mock_game.on_key_chord_up_event.assert_called_once()

    def test_on_key_chord_down_event_tracks_keys(self, mock_game, mocker):
        proxy = KeyboardEventManager.KeyboardEventProxy(game=mock_game)
        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.dict = {
            'type': pygame.KEYDOWN,
            'key': pygame.K_a,
            'mod': 0,
            'unicode': 'a',
            'scancode': 30,
        }
        event.__setitem__ = mocker.Mock()
        proxy.on_key_down_event(event)
        assert len(proxy.keys) > 0

    def test_on_key_chord_up_event_after_down(self, mock_game, mocker):
        proxy = KeyboardEventManager.KeyboardEventProxy(game=mock_game)
        down_event = mocker.Mock()
        down_event.type = pygame.KEYDOWN
        down_event.dict = {
            'type': pygame.KEYDOWN,
            'key': pygame.K_a,
            'mod': 0,
            'unicode': 'a',
            'scancode': 30,
        }
        down_event.__setitem__ = mocker.Mock()
        proxy.on_key_down_event(down_event)

        up_event = mocker.Mock()
        up_event.type = pygame.KEYUP
        up_event.dict = {'type': pygame.KEYUP, 'key': pygame.K_a, 'mod': 0, 'scancode': 30}
        proxy.on_key_up_event(up_event)
        assert mock_game.on_key_chord_up_event.call_count == 1


class TestKeyboardEventManager:
    """Test KeyboardEventManager initialization."""

    def test_init(self, mock_game):
        manager = KeyboardEventManager(game=mock_game)
        assert len(manager.proxies) == 1

    def test_args(self):
        import argparse

        parser = argparse.ArgumentParser()
        result = KeyboardEventManager.args(parser)
        assert result is parser
