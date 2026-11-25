"""Tests for MIDI event functionality.

This module combines tests for:
- MIDI event interfaces, stubs, and event handling
- MidiEventProxy forwarding and missing handler paths
- MidiEventManager initialization and args
"""

import argparse
import operator

import pygame
import pygame.midi
import pytest

from glitchygames.events import (
    HashableEvent,
    MidiEvents,
    MidiEventStubs,
    UnhandledEventError,
)
from glitchygames.events.midi import MidiEventManager
from glitchygames.input.devices import (
    MIDI_INPUT_KIND,
    MIDI_OUTPUT_KIND,
    MidiPortInfo,
    import_midi_module,
)
from glitchygames.live_sources import LiveSources
from glitchygames.scenes import Scene
from tests.input.stand_in_devices import install_stand_in_devices

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

        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)
        manager.on_midi_in_event(event)

        assert game.midi_events_received == [('midi_in', event)]

    def test_proxy_forwards_midi_out_event(self):
        """Test proxy forwards on_midi_out_event to game."""
        game = MidiRecordingScene()
        manager = MidiEventManager(game=game)

        event = HashableEvent(pygame.MIDIOUT, device_id=1, status=144, data1=60, data2=127)
        manager.on_midi_out_event(event)

        assert game.midi_events_received == [('midi_out', event)]


class TestMidiEventProxyMissingHandlers:
    """Test MidiEventProxy when game object lacks handler methods."""

    def test_proxy_skips_missing_midi_in_handler(self):
        """Test proxy does nothing when game lacks on_midi_in_event."""
        manager = MidiEventManager(game=GameWithoutMidiHandlers())

        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)

        # Should not raise
        manager.on_midi_in_event(event)

    def test_proxy_skips_missing_midi_out_handler(self):
        """Test proxy does nothing when game lacks on_midi_out_event."""
        manager = MidiEventManager(game=GameWithoutMidiHandlers())

        event = HashableEvent(pygame.MIDIOUT, device_id=1, status=144, data1=60, data2=127)

        # Should not raise
        manager.on_midi_out_event(event)


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
        assert manager.proxies == [game]
        assert manager.ports == {}

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
    """pygame.midi is optional: where pygame has no PortMidi the import helper says so."""

    def test_import_midi_module_returns_pygame_midi(self):
        """The import helper returns pygame.midi where it imports."""
        assert import_midi_module() is pygame.midi

    def test_import_midi_module_is_none_when_pygame_midi_cannot_import(self, mocker, caplog):
        """A pygame build without PortMidi (no pygame.pypm) gives None, logged once."""
        mocker.patch(
            'glitchygames.input.devices.importlib.import_module',
            side_effect=ModuleNotFoundError("No module named 'pygame.pypm'"),
        )
        with caplog.at_level('INFO', logger='game.input.devices'):
            assert import_midi_module() is None

        assert 'pygame.midi is unavailable' in caplog.text


# ---------------------------------------------------------------------------
# Named ports: one proxy per opened port (plans/2026-11-24-midi-devices.md)
# ---------------------------------------------------------------------------

KEYS_INPUT = MidiPortInfo(interface='CoreMIDI', name='Keys', is_input=True, is_output=False)
SYNTH_OUTPUT = MidiPortInfo(interface='CoreMIDI', name='Synth', is_input=False, is_output=True)


class TestNamedMidiPorts:
    """A named port opens through the devices door, and nothing else asks about MIDI."""

    def test_a_named_input_port_opens_one_proxy(self):
        """--midi-input Keys gives one proxy keyed (MIDI_INPUT_KIND, 0) that reaches the port."""
        devices = install_stand_in_devices(descriptors=[], midi_ports=[KEYS_INPUT])
        manager = MidiEventManager(game=MidiRecordingScene(), input_names=['Keys'])

        assert list(manager.ports) == [(MIDI_INPUT_KIND, 0)]
        proxy = manager.ports[MIDI_INPUT_KIND, 0]
        assert proxy.proxies[1] is devices.midi_input_for_port(port_id=0)
        # The port's own method, through the proxy
        assert proxy.poll() is False
        assert proxy.get_device_info() == (b'CoreMIDI', b'Keys', 1, 0, 1)

    def test_a_named_output_port_opens_one_proxy(self):
        """--midi-output Synth gives one proxy keyed (MIDI_OUTPUT_KIND, 1); writes are dropped."""
        devices = install_stand_in_devices(descriptors=[], midi_ports=[KEYS_INPUT, SYNTH_OUTPUT])
        manager = MidiEventManager(game=MidiRecordingScene(), output_names=['Synth'])

        assert list(manager.ports) == [(MIDI_OUTPUT_KIND, 1)]
        proxy = manager.ports[MIDI_OUTPUT_KIND, 1]
        assert proxy.proxies[1] is devices.midi_output_for_port(port_id=1)
        proxy.write_short(0x90, 60, 100)
        assert proxy.get_device_info() == (b'CoreMIDI', b'Synth', 0, 1, 1)

    def test_a_named_port_that_is_absent_is_logged_and_skipped(self, caplog):
        """--midi-input Nope: no proxy, one warning naming it, the other port still opens."""
        devices = install_stand_in_devices(descriptors=[], midi_ports=[KEYS_INPUT])
        with caplog.at_level('WARNING', logger='game.midi'):
            manager = MidiEventManager(game=MidiRecordingScene(), input_names=['Nope', 'Keys'])

        warnings = [record.getMessage() for record in caplog.records if record.name == 'game.midi']
        assert len(warnings) == 1
        assert 'Nope' in warnings[0]
        assert list(manager.ports) == [(MIDI_INPUT_KIND, 0)]
        # The absence is an ordinary answer, recorded
        assert devices.take_enumeration_answers()

    def test_an_input_name_does_not_match_an_output_only_port(self, caplog):
        """The kind decides: an output port is not found as an input."""
        install_stand_in_devices(descriptors=[], midi_ports=[SYNTH_OUTPUT])
        with caplog.at_level('WARNING', logger='game.midi'):
            manager = MidiEventManager(game=MidiRecordingScene(), input_names=['Synth'])

        assert manager.ports == {}
        assert 'Synth' in caplog.text

    def test_a_port_that_fails_to_open_is_logged_and_skipped(self, mocker, caplog):
        """A pygame.error from the open is treated as an absent port."""
        devices = install_stand_in_devices(descriptors=[], midi_ports=[KEYS_INPUT])
        mocker.patch.object(
            devices, 'open_midi_input', side_effect=pygame.error('PortMidi: cannot open')
        )
        with caplog.at_level('WARNING', logger='game.midi'):
            manager = MidiEventManager(game=MidiRecordingScene(), input_names=['Keys'])

        assert manager.ports == {}
        assert 'Keys' in caplog.text
        assert 'cannot open' in caplog.text

    def test_a_port_that_cannot_be_looked_up_is_logged_and_skipped(self, mocker, caplog):
        """A pygame.error from the door while listing ports is logged, naming the port."""
        devices = install_stand_in_devices(descriptors=[], midi_ports=[KEYS_INPUT])
        mocker.patch.object(
            devices, 'midi_port_count', side_effect=pygame.error('PortMidi is gone')
        )
        with caplog.at_level('WARNING', logger='game.midi'):
            manager = MidiEventManager(game=MidiRecordingScene(), input_names=['Keys'])

        assert manager.ports == {}
        assert 'Keys' in caplog.text
        assert 'PortMidi is gone' in caplog.text

    def test_a_portmidi_constructor_failure_is_skipped_and_recorded(self, mocker, caplog):
        """PortMidi's Input raises a plain Exception (bytes): skipped, logged, answer recorded."""
        midi_module = mocker.Mock()
        mocker.patch('glitchygames.input.devices.import_midi_module', return_value=midi_module)
        midi_module.get_device_info.side_effect = lambda port_id: (b'CoreMIDI', b'Keys', 1, 0, 0)
        midi_module.get_count.return_value = 1
        midi_module.Input.side_effect = Exception(b'PortMidi: Device already open')
        sources = LiveSources(random_seed=1)
        mocker.patch('glitchygames.events.midi.active_sources', return_value=sources)

        with caplog.at_level('WARNING', logger='game.midi'):
            manager = MidiEventManager(game=MidiRecordingScene(), input_names=['Keys'])

        assert manager.ports == {}
        assert 'PortMidi: Device already open' in caplog.text
        errors = [a.error for a in sources.devices().take_enumeration_answers() if a.error]
        assert errors == ['PortMidi: Device already open']

    def test_naming_a_port_twice_opens_it_once(self):
        """The same name twice is one proxy."""
        install_stand_in_devices(descriptors=[], midi_ports=[KEYS_INPUT])
        manager = MidiEventManager(game=MidiRecordingScene(), input_names=['Keys', 'Keys'])

        assert list(manager.ports) == [(MIDI_INPUT_KIND, 0)]

    def test_no_named_port_asks_the_door_nothing_about_midi(self):
        """With no name the manager makes no MIDI call, so nothing is recorded."""
        devices = install_stand_in_devices(descriptors=[], midi_ports=[KEYS_INPUT])
        manager = MidiEventManager(game=MidiRecordingScene())

        assert manager.ports == {}
        assert devices.take_enumeration_answers() == []

    def test_the_proxy_no_longer_reaches_pygame_midi(self):
        """A game cannot go around the door through a proxy to pygame.midi."""
        install_stand_in_devices(descriptors=[], midi_ports=[KEYS_INPUT])
        manager = MidiEventManager(game=MidiRecordingScene(), input_names=['Keys'])
        proxy = manager.ports[MIDI_INPUT_KIND, 0]

        with pytest.raises(AttributeError):
            operator.attrgetter('Input')(proxy)

    def test_a_proxy_forwards_events_to_the_game(self):
        """A port proxy forwards MIDI events to the game, as the old proxy did."""
        install_stand_in_devices(descriptors=[], midi_ports=[KEYS_INPUT])
        game = MidiRecordingScene()
        manager = MidiEventManager(game=game, input_names=['Keys'])
        proxy = manager.ports[MIDI_INPUT_KIND, 0]
        event = HashableEvent(pygame.MIDIIN, device_id=0, status=144, data1=60, data2=127)

        proxy.on_midi_in_event(event)
        proxy.on_midi_out_event(event)

        assert [label for label, _ in game.midi_events_received] == ['midi_in', 'midi_out']

    def test_a_proxy_for_a_game_without_handlers_skips_events(self):
        """A game with no MIDI handlers is skipped, not raised on."""
        install_stand_in_devices(descriptors=[], midi_ports=[KEYS_INPUT])
        manager = MidiEventManager(game=GameWithoutMidiHandlers(), input_names=['Keys'])
        proxy = manager.ports[MIDI_INPUT_KIND, 0]
        event = HashableEvent(pygame.MIDIIN, device_id=0, status=144, data1=60, data2=127)

        proxy.on_midi_in_event(event)
        proxy.on_midi_out_event(event)


class TestMidiOptions:
    """--midi-input and --midi-output are repeatable and empty by default."""

    def test_the_options_default_to_empty_and_repeat(self):
        """Each flag appends; neither given gives an empty list."""
        parser = MidiEventManager.args(argparse.ArgumentParser())

        empty = parser.parse_args([])
        named = parser.parse_args([
            '--midi-input',
            'Keys',
            '--midi-input',
            'Pads',
            '--midi-output',
            'Synth',
        ])

        assert (empty.midi_input, empty.midi_output) == ([], [])
        assert (named.midi_input, named.midi_output) == (['Keys', 'Pads'], ['Synth'])
