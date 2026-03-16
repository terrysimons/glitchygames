"""Additional coverage tests for MIDI event handling.

Tests cover: MidiEventProxy forwarding when game lacks handlers,
MidiEventManager initialization with pygame.error, and
the args() class method.
"""

import argparse

import pygame
import pytest

from glitchygames.events import HashableEvent
from glitchygames.events.midi import MidiEventManager

pytestmark = pytest.mark.usefixtures('mock_pygame_patches')


class TestMidiEventProxyForwarding:
    """Test MidiEventProxy forwarding to game objects."""

    def test_proxy_forwards_midi_in_event(self, mocker):
        """Test proxy forwards on_midi_in_event to game."""
        mock_game = mocker.Mock()
        manager = MidiEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)
        proxy.on_midi_in_event(event)

        mock_game.on_midi_in_event.assert_called_once_with(event)

    def test_proxy_forwards_midi_out_event(self, mocker):
        """Test proxy forwards on_midi_out_event to game."""
        mock_game = mocker.Mock()
        manager = MidiEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MIDIOUT, device_id=1, status=144, data1=60, data2=127)
        proxy.on_midi_out_event(event)

        mock_game.on_midi_out_event.assert_called_once_with(event)


class TestMidiEventProxyMissingHandlers:
    """Test MidiEventProxy when game object lacks handler methods."""

    def test_proxy_skips_missing_midi_in_handler(self, mocker):
        """Test proxy does nothing when game lacks on_midi_in_event."""
        mock_game = mocker.Mock(spec=[])  # Empty spec, no methods
        manager = MidiEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)

        # Should not raise
        proxy.on_midi_in_event(event)

    def test_proxy_skips_missing_midi_out_handler(self, mocker):
        """Test proxy does nothing when game lacks on_midi_out_event."""
        mock_game = mocker.Mock(spec=[])
        manager = MidiEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MIDIOUT, device_id=1, status=144, data1=60, data2=127)

        # Should not raise
        proxy.on_midi_out_event(event)


class TestMidiEventManagerInit:
    """Test MidiEventManager initialization edge cases."""

    def test_init_handles_pygame_error(self, mocker):
        """Test that init handles pygame.error when setting allowed events."""
        mocker.patch('pygame.event.set_allowed', side_effect=pygame.error('not initialized'))
        mock_game = mocker.Mock()

        # Should not raise despite pygame.error
        manager = MidiEventManager(game=mock_game)

        assert manager.game is mock_game
        assert len(manager.proxies) == 1

    def test_init_with_none_game(self):
        """Test MidiEventManager can be initialized with game=None."""
        manager = MidiEventManager(game=None)

        assert manager.game is None
        assert len(manager.proxies) == 1


class TestMidiEventManagerArgs:
    """Test MidiEventManager.args class method."""

    def test_args_adds_midi_group(self):
        """Test that args() adds a 'Midi Options' argument group."""
        parser = argparse.ArgumentParser()
        result = MidiEventManager.args(parser)

        assert result is parser

        # Verify the group was added by checking the action groups
        group_titles = [group.title for group in parser._action_groups]
        assert 'Midi Options' in group_titles
