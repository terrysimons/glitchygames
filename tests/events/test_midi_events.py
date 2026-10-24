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
import pygame.midi
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    MidiEvents,
    MidiEventStubs,
    UnhandledEventError,
)
from glitchygames.events.midi import MidiEventManager, import_midi_module
from glitchygames.scenes import Scene

EVENT_TEST_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}


class MidiRecordingScene(Scene):
    """A real scene that records the MIDI events it receives, tagged with a label."""

    def __init__(self, options=None, groups=None, *, label_in='midi_in', label_out='midi_out'):
        """Create the scene with no MIDI events received yet.

        Args:
            options: The scene options (strict unhandled-event options by default).
            groups: The sprite groups.
            label_in: The label recorded with each MIDI input event.
            label_out: The label recorded with each MIDI output event.

        """
        super().__init__(
            options=options if options is not None else dict(EVENT_TEST_OPTIONS),
            groups=groups,
        )
        self.label_in = label_in
        self.label_out = label_out
        self.midi_events_received: list[tuple[str, HashableEvent]] = []

    def on_midi_in_event(self, event):
        """Record a MIDI input event."""
        self.midi_events_received.append((self.label_in, event))

    def on_midi_out_event(self, event):
        """Record a MIDI output event."""
        self.midi_events_received.append((self.label_out, event))


class GameWithoutMidiHandlers:
    """A game object with no MIDI handlers at all (the proxy must skip it)."""


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
        # A real Scene without MIDI handlers falls back to the MIDI stubs
        scene = Scene(options=dict(EVENT_TEST_OPTIONS))
        manager = MidiEventManager(game=scene)

        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)
        # Should raise UnhandledEventError (no logging before raise)
        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            manager.on_midi_in_event(event)
        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            manager.on_midi_out_event(
                HashableEvent(pygame.MIDIOUT, device_id=1, status=144, data1=60, data2=127),
            )

    def test_midi_in_event(self):
        """Test MIDI input event handling."""
        scene = MidiRecordingScene(label_in='midi_in')
        manager = MidiEventManager(game=scene)

        # Test MIDI input
        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)
        manager.on_midi_in_event(event)
        assert len(scene.midi_events_received) == 1
        assert scene.midi_events_received[0][0] == 'midi_in'
        assert scene.midi_events_received[0][1].type == pygame.MIDIIN
        assert scene.midi_events_received[0][1].device_id == 1
        assert scene.midi_events_received[0][1].status == 144
        assert scene.midi_events_received[0][1].data1 == 60
        assert scene.midi_events_received[0][1].data2 == 127

    def test_midi_out_event(self):
        """Test MIDI output event handling."""
        scene = MidiRecordingScene(label_out='midi_out')
        manager = MidiEventManager(game=scene)

        # Test MIDI output
        event = HashableEvent(pygame.MIDIOUT, device_id=1, status=144, data1=60, data2=127)
        manager.on_midi_out_event(event)
        assert len(scene.midi_events_received) == 1
        assert scene.midi_events_received[0][0] == 'midi_out'
        assert scene.midi_events_received[0][1].type == pygame.MIDIOUT
        assert scene.midi_events_received[0][1].device_id == 1
        assert scene.midi_events_received[0][1].status == 144
        assert scene.midi_events_received[0][1].data1 == 60
        assert scene.midi_events_received[0][1].data2 == 127

    def test_midi_note_on_events(self):
        """Test MIDI note on events."""
        scene = MidiRecordingScene(label_in='note_on')
        manager = MidiEventManager(game=scene)

        # Test note on events (status 144 = 0x90)
        for note in range(60, 72):  # C4 to C5
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=note, data2=127)
            manager.on_midi_in_event(event)
            assert len(scene.midi_events_received) == 1
            assert scene.midi_events_received[0][0] == 'note_on'
            assert scene.midi_events_received[0][1].status == 144
            assert scene.midi_events_received[0][1].data1 == note
            assert scene.midi_events_received[0][1].data2 == 127
            scene.midi_events_received.clear()

    def test_midi_note_off_events(self):
        """Test MIDI note off events."""
        scene = MidiRecordingScene(label_in='note_off')
        manager = MidiEventManager(game=scene)

        # Test note off events (status 128 = 0x80)
        for note in range(60, 72):  # C4 to C5
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=128, data1=note, data2=0)
            manager.on_midi_in_event(event)
            assert len(scene.midi_events_received) == 1
            assert scene.midi_events_received[0][0] == 'note_off'
            assert scene.midi_events_received[0][1].status == 128
            assert scene.midi_events_received[0][1].data1 == note
            assert scene.midi_events_received[0][1].data2 == 0
            scene.midi_events_received.clear()

    def test_midi_control_change_events(self, mocker):
        """Test MIDI control change events."""
        stub = MidiEventStubs()
        self._give_stub_strict_options(stub)

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
        self._give_stub_strict_options(stub)

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
        self._give_stub_strict_options(stub)

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
        self._give_stub_strict_options(stub)

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
        self._give_stub_strict_options(stub)

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
        self._give_stub_strict_options(stub)

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
        self._give_stub_strict_options(stub)

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
        self._give_stub_strict_options(stub)

        # Test different velocity values
        velocities = [0, 32, 64, 96, 127]  # Various velocity levels

        mocker.patch('glitchygames.events.base.LOG.error')  # Suppress log messages
        for velocity in velocities:
            # Test note on with different velocities
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=velocity)
            with pytest.raises(UnhandledEventError):
                stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    @staticmethod
    def _give_stub_strict_options(stub):
        """Give the stubs options that make unhandled events raise UnhandledEventError."""
        stub.options = dict(EVENT_TEST_OPTIONS)


# ---------------------------------------------------------------------------
# MidiEventProxy forwarding tests (from test_midi_coverage.py)
# ---------------------------------------------------------------------------


class TestMidiEventProxyForwarding:
    """Test MidiEventProxy forwarding to game objects."""

    def test_proxy_forwards_midi_in_event(self):
        """Test proxy forwards on_midi_in_event to game."""
        game = MidiRecordingScene()
        manager = MidiEventManager(game=game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)
        proxy.on_midi_in_event(event)

        assert game.midi_events_received == [('midi_in', event)]

    def test_proxy_forwards_midi_out_event(self):
        """Test proxy forwards on_midi_out_event to game."""
        game = MidiRecordingScene()
        manager = MidiEventManager(game=game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MIDIOUT, device_id=1, status=144, data1=60, data2=127)
        proxy.on_midi_out_event(event)

        assert game.midi_events_received == [('midi_out', event)]


class TestMidiEventProxyMissingHandlers:
    """Test MidiEventProxy when game object lacks handler methods."""

    def test_proxy_skips_missing_midi_in_handler(self):
        """Test proxy does nothing when game lacks on_midi_in_event."""
        manager = MidiEventManager(game=GameWithoutMidiHandlers())
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)

        # Should not raise
        proxy.on_midi_in_event(event)

    def test_proxy_skips_missing_midi_out_handler(self):
        """Test proxy does nothing when game lacks on_midi_out_event."""
        manager = MidiEventManager(game=GameWithoutMidiHandlers())
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
        # The video system is up in every test: simulate set_allowed failing before it is
        mocker.patch('pygame.event.set_allowed', side_effect=pygame.error('not initialized'))
        game = MidiRecordingScene()

        # Should not raise despite pygame.error
        manager = MidiEventManager(game=game)

        assert manager.game is game
        assert len(manager.proxies) == 1

    def test_init_with_none_game(self):
        """Test MidiEventManager can be initialized with game=None."""
        manager = MidiEventManager(game=None)

        assert manager.game is None
        assert len(manager.proxies) == 1


class TestMidiEventManagerCoverage:
    """Test coverage for MIDI manager functionality."""

    def test_midi_manager_initialization(self):
        """Test MidiEventManager initialization."""
        game = MidiRecordingScene()
        manager = MidiEventManager(game=game)

        assert manager.game is game
        assert len(manager.proxies) == 1
        # The proxy asks the game first, then pygame.midi (the real module)
        assert manager.proxies[0].proxies == [game, pygame.midi]

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


# ---------------------------------------------------------------------------
# pygame.midi is optional (WebAssembly pygame builds have no PortMidi)
# ---------------------------------------------------------------------------


class TestOptionalMidiModule:
    """pygame.midi is proxied where pygame has it and left out where it does not."""

    def test_proxy_includes_pygame_midi_when_available(self):
        """Desktop pygame has PortMidi: the proxy asks pygame.midi after the game."""
        game = GameWithoutMidiHandlers()
        proxy = MidiEventManager(game=game).proxies[0]

        assert proxy.proxies == [game, pygame.midi]

    def test_proxy_has_only_the_game_without_pygame_midi(self, mocker):
        """Without pygame.midi (a WebAssembly build) the proxy forwards to the game only."""
        mocker.patch('glitchygames.events.midi.MIDI_MODULE', None)
        game = GameWithoutMidiHandlers()
        proxy = MidiEventManager(game=game).proxies[0]

        assert proxy.proxies == [game]

    def test_import_midi_module_returns_pygame_midi(self):
        """The import helper returns pygame.midi where it imports."""
        assert import_midi_module() is pygame.midi

    def test_import_midi_module_is_none_when_pygame_midi_cannot_import(self, mocker, caplog):
        """A pygame build without PortMidi (no pygame.pypm) gives None, logged once."""
        mocker.patch(
            'glitchygames.events.midi.importlib.import_module',
            side_effect=ModuleNotFoundError("No module named 'pygame.pypm'"),
        )
        with caplog.at_level('INFO', logger='game.midi'):
            assert import_midi_module() is None

        assert 'pygame.midi is unavailable' in caplog.text
