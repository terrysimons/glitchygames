"""Tests for MIDI event functionality.

This module combines tests for:
- MIDI event interfaces, stubs, and event handling
- MidiEventProxy forwarding and missing handler paths
- MidiEventManager initialization and args
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
    MidiEvents,
    MidiEventStubs,
    UnhandledEventError,
)
from glitchygames.events.midi import MidiEventManager
from tests.mocks.test_mock_factory import MockFactory

pytestmark = pytest.mark.usefixtures('mock_pygame_patches')


# ---------------------------------------------------------------------------
# MidiEvents interface tests (from test_events_midi_events.py)
# ---------------------------------------------------------------------------


class TestMidiEvents:
    """Test MidiEvents interface functionality."""

    def test_midi_events_interface(self):
        """Test MidiEvents interface methods."""
        # Test that MidiEvents has required abstract methods
        assert hasattr(MidiEvents, 'on_midi_in_event')
        assert hasattr(MidiEvents, 'on_midi_out_event')

    def test_midi_event_stubs_implementation(self, mocker):
        """Test MidiEventStubs implementation."""
        # Use centralized mock for scene without event handlers (stub behavior)
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={},  # No event handlers - will fall back to stubs
        )

        # Test that stub methods can be called
        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)
        # Should raise UnhandledEventError (no logging before raise)
        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            scene.on_midi_in_event(event)

    def test_midi_in_event(self):
        """Test MIDI input event handling."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_midi_in_event': lambda event: (
                    scene.midi_events_received.append(('midi_in', event)),
                    True,
                )[1],
            },
        )

        # Test MIDI input
        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)
        result = scene.on_midi_in_event(event)
        assert result is True
        assert len(scene.midi_events_received) == 1
        assert scene.midi_events_received[0][0] == 'midi_in'
        assert scene.midi_events_received[0][1].type == pygame.MIDIIN
        assert scene.midi_events_received[0][1].device_id == 1
        assert scene.midi_events_received[0][1].status == 144
        assert scene.midi_events_received[0][1].data1 == 60
        assert scene.midi_events_received[0][1].data2 == 127

    def test_midi_out_event(self):
        """Test MIDI output event handling."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_midi_out_event': lambda event: (
                    scene.midi_events_received.append(('midi_out', event)),
                    True,
                )[1],
            },
        )

        # Test MIDI output
        event = HashableEvent(pygame.MIDIOUT, device_id=1, status=144, data1=60, data2=127)
        result = scene.on_midi_out_event(event)
        assert result is True
        assert len(scene.midi_events_received) == 1
        assert scene.midi_events_received[0][0] == 'midi_out'
        assert scene.midi_events_received[0][1].type == pygame.MIDIOUT
        assert scene.midi_events_received[0][1].device_id == 1
        assert scene.midi_events_received[0][1].status == 144
        assert scene.midi_events_received[0][1].data1 == 60
        assert scene.midi_events_received[0][1].data2 == 127

    def test_midi_note_on_events(self):
        """Test MIDI note on events."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_midi_in_event': lambda event: (
                    scene.midi_events_received.append(('note_on', event)),
                    True,
                )[1],
            },
        )

        # Test note on events (status 144 = 0x90)
        for note in range(60, 72):  # C4 to C5
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=note, data2=127)
            result = scene.on_midi_in_event(event)
            assert result is True
            assert len(scene.midi_events_received) == 1
            assert scene.midi_events_received[0][0] == 'note_on'
            assert scene.midi_events_received[0][1].status == 144
            assert scene.midi_events_received[0][1].data1 == note
            assert scene.midi_events_received[0][1].data2 == 127
            scene.midi_events_received.clear()

    def test_midi_note_off_events(self):
        """Test MIDI note off events."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_midi_in_event': lambda event: (
                    scene.midi_events_received.append(('note_off', event)),
                    True,
                )[1],
            },
        )

        # Test note off events (status 128 = 0x80)
        for note in range(60, 72):  # C4 to C5
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=128, data1=note, data2=0)
            result = scene.on_midi_in_event(event)
            assert result is True
            assert len(scene.midi_events_received) == 1
            assert scene.midi_events_received[0][0] == 'note_off'
            assert scene.midi_events_received[0][1].status == 128
            assert scene.midi_events_received[0][1].data1 == note
            assert scene.midi_events_received[0][1].data2 == 0
            scene.midi_events_received.clear()

    def test_midi_control_change_events(self, mocker):
        """Test MIDI control change events."""
        stub = MidiEventStubs()
        self._setup_mock_scene_for_stub(stub)

        # Test control change events (status 176 = 0xB0)
        mocker.patch('glitchygames.events.base.LOG.error')  # Suppress log messages
        for controller in range(1, 128):  # All MIDI controllers
            event = HashableEvent(
                pygame.MIDIIN,
                device_id=1,
                status=176,
                data1=controller,
                data2=64,
            )
            with pytest.raises(UnhandledEventError):
                stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_program_change_events(self, mocker):
        """Test MIDI program change events."""
        stub = MidiEventStubs()
        self._setup_mock_scene_for_stub(stub)

        # Test program change events (status 192 = 0xC0)
        mocker.patch('glitchygames.events.base.LOG.error')  # Suppress log messages
        for program in range(128):  # All MIDI programs
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=192, data1=program, data2=0)
            with pytest.raises(UnhandledEventError):
                stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_pitch_bend_events(self, mocker):
        """Test MIDI pitch bend events."""
        stub = MidiEventStubs()
        self._setup_mock_scene_for_stub(stub)

        # Test pitch bend events (status 224 = 0xE0)
        mocker.patch('glitchygames.events.base.LOG.error')  # Suppress log messages
        for bend in range(0, 16384, 1024):  # Various pitch bend values
            event = HashableEvent(
                pygame.MIDIIN,
                device_id=1,
                status=224,
                data1=bend & 0x7F,
                data2=(bend >> 7) & 0x7F,
            )
            with pytest.raises(UnhandledEventError):
                stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_aftertouch_events(self, mocker):
        """Test MIDI aftertouch events."""
        stub = MidiEventStubs()
        self._setup_mock_scene_for_stub(stub)

        # Test aftertouch events (status 208 = 0xD0)
        mocker.patch('glitchygames.events.base.LOG.error')  # Suppress log messages
        for pressure in range(128):  # All pressure values
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=208, data1=pressure, data2=0)
            with pytest.raises(UnhandledEventError):
                stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_polyphonic_aftertouch_events(self, mocker):
        """Test MIDI polyphonic aftertouch events."""
        stub = MidiEventStubs()
        self._setup_mock_scene_for_stub(stub)

        # Test polyphonic aftertouch events (status 160 = 0xA0)
        mocker.patch('glitchygames.events.base.LOG.error')  # Suppress log messages
        for note in range(60, 72):  # C4 to C5
            for pressure in range(0, 128, 16):  # Various pressure values
                event = HashableEvent(
                    pygame.MIDIIN,
                    device_id=1,
                    status=160,
                    data1=note,
                    data2=pressure,
                )
                with pytest.raises(UnhandledEventError):
                    stub.on_midi_in_event(event)
                # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_system_events(self, mocker):
        """Test MIDI system events."""
        stub = MidiEventStubs()
        self._setup_mock_scene_for_stub(stub)

        # Test system events (status 240-255 = 0xF0-0xFF)
        system_events = [
            (240, 0, 0),  # System Exclusive start
            (247, 0, 0),  # System Exclusive end
            (248, 0, 0),  # Timing Clock
            (249, 0, 0),  # Undefined
            (250, 0, 0),  # Start
            (251, 0, 0),  # Continue
            (252, 0, 0),  # Stop
            (253, 0, 0),  # Undefined
            (254, 0, 0),  # Active Sensing
            (255, 0, 0),  # System Reset
        ]

        mocker.patch('glitchygames.events.base.LOG.error')  # Suppress log messages
        for status, data1, data2 in system_events:
            event = HashableEvent(
                pygame.MIDIIN,
                device_id=1,
                status=status,
                data1=data1,
                data2=data2,
            )
            with pytest.raises(UnhandledEventError):
                stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_multiple_devices(self, mocker):
        """Test MIDI events with multiple devices."""
        stub = MidiEventStubs()
        self._setup_mock_scene_for_stub(stub)

        # Test multiple MIDI devices
        mocker.patch('glitchygames.events.base.LOG.error')  # Suppress log messages
        for device_id in range(5):
            # Test MIDI input
            event = HashableEvent(
                pygame.MIDIIN,
                device_id=device_id,
                status=144,
                data1=60,
                data2=127,
            )
            with pytest.raises(UnhandledEventError):
                stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

            # Test MIDI output
            event = HashableEvent(
                pygame.MIDIOUT,
                device_id=device_id,
                status=144,
                data1=60,
                data2=127,
            )
            with pytest.raises(UnhandledEventError):
                stub.on_midi_out_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_velocity_variations(self, mocker):
        """Test MIDI events with different velocity values."""
        stub = MidiEventStubs()
        self._setup_mock_scene_for_stub(stub)

        # Test different velocity values
        velocities = [0, 32, 64, 96, 127]  # Various velocity levels

        mocker.patch('glitchygames.events.base.LOG.error')  # Suppress log messages
        for velocity in velocities:
            # Test note on with different velocities
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=velocity)
            with pytest.raises(UnhandledEventError):
                stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def _setup_mock_scene_for_stub(self, stub):
        """Set up mock scene object for event stubs using centralized mocks.

        Returns:
            object: The result.

        """
        # Create a scene mock with proper event handling configuration
        scene_mock = MockFactory.create_event_test_scene_mock(
            options={
                'debug_events': False,
                'no_unhandled_events': True,  # This will cause UnhandledEventError to be raised
            },
            event_handlers={},  # Empty handlers to trigger unhandled_event fallback
        )

        # Set the options on the stub so unhandled_event can access them
        stub.options = scene_mock.options
        return scene_mock


# ---------------------------------------------------------------------------
# MidiEventProxy forwarding tests (from test_midi_coverage.py)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# MidiEventManager init tests (from test_midi_coverage.py + test_events_midi_events.py)
# ---------------------------------------------------------------------------


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


class TestMidiEventManagerCoverage:
    """Test coverage for MIDI manager functionality."""

    def test_midi_manager_initialization(self, mocker):
        """Test MidiEventManager initialization."""
        mock_game = mocker.Mock()
        manager = MidiEventManager(game=mock_game)

        assert manager.game == mock_game
        assert hasattr(manager, 'proxies')
        assert isinstance(manager.proxies, list)

    def test_midi_manager_initialization_no_game(self):
        """Test MidiEventManager initialization without game."""
        manager = MidiEventManager(game=None)
        # Test that manager was created successfully
        assert manager is not None


# ---------------------------------------------------------------------------
# MidiEventManager args tests (from test_midi_coverage.py + test_events_midi_events.py)
# ---------------------------------------------------------------------------


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

    def test_midi_manager_args(self):
        """Test MidiEventManager args method."""
        parser = argparse.ArgumentParser()
        result = MidiEventManager.args(parser)

        assert result is parser
