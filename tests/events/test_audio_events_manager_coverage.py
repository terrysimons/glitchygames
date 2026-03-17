"""Tests for glitchygames.events.audio module - AudioEventManager."""

import pygame
import pytest

from glitchygames.events.audio import AudioEventManager


@pytest.fixture
def mock_game(mocker):
    """Create a mock game object with all required event handlers."""
    return mocker.Mock()


@pytest.fixture
def mock_event(mocker):
    """Create a mock pygame event."""
    return mocker.Mock(spec=pygame.event.Event)


class TestAudioEventProxy:
    """Test AudioEventProxy event delegation."""

    def test_proxy_init(self, mock_game):
        proxy = AudioEventManager.AudioEventProxy(game=mock_game)
        assert proxy.game is mock_game
        assert mock_game in proxy.proxies

    def test_on_audio_device_added_event(self, mock_game, mock_event):
        proxy = AudioEventManager.AudioEventProxy(game=mock_game)
        proxy.on_audio_device_added_event(mock_event)
        mock_game.on_audio_device_added_event.assert_called_once_with(mock_event)

    def test_on_audio_device_removed_event(self, mock_game, mock_event):
        proxy = AudioEventManager.AudioEventProxy(game=mock_game)
        proxy.on_audio_device_removed_event(mock_event)
        mock_game.on_audio_device_removed_event.assert_called_once_with(mock_event)


class TestAudioEventManager:
    """Test AudioEventManager initialization."""

    def test_init(self, mock_game):
        manager = AudioEventManager(game=mock_game)
        assert len(manager.proxies) == 1

    def test_args(self):
        import argparse

        parser = argparse.ArgumentParser()
        result = AudioEventManager.args(parser)
        assert result is parser
