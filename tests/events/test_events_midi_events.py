"""Tests for MIDI event functionality.

This module tests MIDI event interfaces, stubs, and event handling.
"""

import argparse
import sys
from pathlib import Path
from unittest.mock import Mock

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
from glitchygames.events.midi import MidiManager

from tests.mocks.test_mock_factory import MockFactory


class TestMidiEvents:
    """Test MidiEvents interface functionality."""

    def test_midi_events_interface(self, mock_pygame_patches):
        """Test MidiEvents interface methods."""
        # Test that MidiEvents has required abstract methods
        assert hasattr(MidiEvents, "on_midi_in_event")
        assert hasattr(MidiEvents, "on_midi_out_event")

    def test_midi_event_stubs_implementation(self, mock_pygame_patches):
        """Test MidiEventStubs implementation."""
        # Use centralized mock for scene without event handlers (stub behavior)
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={}  # No event handlers - will fall back to stubs
        )

        # Test that stub methods can be called
        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)
        with pytest.raises(UnhandledEventError):
            scene.on_midi_in_event(event)
        # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_in_event(self, mock_pygame_patches):
        """Test MIDI input event handling."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_midi_in_event": lambda event: (scene.midi_events_received.append(("midi_in", event)), True)[1]
            }
        )

        # Test MIDI input
        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)
        result = scene.on_midi_in_event(event)
        assert result is True
        assert len(scene.midi_events_received) == 1
        assert scene.midi_events_received[0][0] == "midi_in"
        assert scene.midi_events_received[0][1].type == pygame.MIDIIN
        assert scene.midi_events_received[0][1].device_id == 1
        assert scene.midi_events_received[0][1].status == 144
        assert scene.midi_events_received[0][1].data1 == 60
        assert scene.midi_events_received[0][1].data2 == 127

    def test_midi_out_event(self, mock_pygame_patches):
        """Test MIDI output event handling."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_midi_out_event": lambda event: (scene.midi_events_received.append(("midi_out", event)), True)[1]
            }
        )

        # Test MIDI output
        event = HashableEvent(pygame.MIDIOUT, device_id=1, status=144, data1=60, data2=127)
        result = scene.on_midi_out_event(event)
        assert result is True
        assert len(scene.midi_events_received) == 1
        assert scene.midi_events_received[0][0] == "midi_out"
        assert scene.midi_events_received[0][1].type == pygame.MIDIOUT
        assert scene.midi_events_received[0][1].device_id == 1
        assert scene.midi_events_received[0][1].status == 144
        assert scene.midi_events_received[0][1].data1 == 60
        assert scene.midi_events_received[0][1].data2 == 127

    def test_midi_note_on_events(self, mock_pygame_patches):
        """Test MIDI note on events."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_midi_in_event": lambda event: (scene.midi_events_received.append(("note_on", event)), True)[1]
            }
        )

        # Test note on events (status 144 = 0x90)
        for note in range(60, 72):  # C4 to C5
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=note, data2=127)
            result = scene.on_midi_in_event(event)
            assert result is True
            assert len(scene.midi_events_received) == 1
            assert scene.midi_events_received[0][0] == "note_on"
            assert scene.midi_events_received[0][1].status == 144
            assert scene.midi_events_received[0][1].data1 == note
            assert scene.midi_events_received[0][1].data2 == 127
            scene.midi_events_received.clear()

    def test_midi_note_off_events(self, mock_pygame_patches):
        """Test MIDI note off events."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_midi_in_event": lambda event: (scene.midi_events_received.append(("note_off", event)), True)[1]
            }
        )

        # Test note off events (status 128 = 0x80)
        for note in range(60, 72):  # C4 to C5
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=128, data1=note, data2=0)
            result = scene.on_midi_in_event(event)
            assert result is True
            assert len(scene.midi_events_received) == 1
            assert scene.midi_events_received[0][0] == "note_off"
            assert scene.midi_events_received[0][1].status == 128
            assert scene.midi_events_received[0][1].data1 == note
            assert scene.midi_events_received[0][1].data2 == 0
            scene.midi_events_received.clear()

    def test_midi_control_change_events(self, mock_pygame_patches):
        """Test MIDI control change events."""
        from unittest.mock import patch
        
        stub = MidiEventStubs()
        scene_mock = self._setup_mock_scene_for_stub(stub)

        # Test control change events (status 176 = 0xB0)
        for controller in range(1, 128):  # All MIDI controllers
            event = HashableEvent(
                pygame.MIDIIN, device_id=1, status=176, data1=controller, data2=64
            )
            with patch("glitchygames.events.LOG.error"):  # Suppress log messages
                with pytest.raises(UnhandledEventError):
                    stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_program_change_events(self, mock_pygame_patches):
        """Test MIDI program change events."""
        from unittest.mock import patch
        
        stub = MidiEventStubs()
        scene_mock = self._setup_mock_scene_for_stub(stub)

        # Test program change events (status 192 = 0xC0)
        for program in range(128):  # All MIDI programs
            event = HashableEvent(
                pygame.MIDIIN, device_id=1, status=192, data1=program, data2=0
            )
            with patch("glitchygames.events.LOG.error"):  # Suppress log messages
                with pytest.raises(UnhandledEventError):
                    stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_pitch_bend_events(self, mock_pygame_patches):
        """Test MIDI pitch bend events."""
        from unittest.mock import patch
        
        stub = MidiEventStubs()
        scene_mock = self._setup_mock_scene_for_stub(stub)

        # Test pitch bend events (status 224 = 0xE0)
        for bend in range(0, 16384, 1024):  # Various pitch bend values
            event = HashableEvent(
                pygame.MIDIIN,
                device_id=1,
                status=224,
                data1=bend & 0x7F,
                data2=(bend >> 7) & 0x7F,
            )
            with patch("glitchygames.events.LOG.error"):  # Suppress log messages
                with pytest.raises(UnhandledEventError):
                    stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_aftertouch_events(self, mock_pygame_patches):
        """Test MIDI aftertouch events."""
        from unittest.mock import patch
        
        stub = MidiEventStubs()
        scene_mock = self._setup_mock_scene_for_stub(stub)

        # Test aftertouch events (status 208 = 0xD0)
        for pressure in range(128):  # All pressure values
            event = HashableEvent(
                pygame.MIDIIN, device_id=1, status=208, data1=pressure, data2=0
            )
            with patch("glitchygames.events.LOG.error"):  # Suppress log messages
                with pytest.raises(UnhandledEventError):
                    stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_polyphonic_aftertouch_events(self, mock_pygame_patches):
        """Test MIDI polyphonic aftertouch events."""
        from unittest.mock import patch
        
        stub = MidiEventStubs()
        scene_mock = self._setup_mock_scene_for_stub(stub)

        # Test polyphonic aftertouch events (status 160 = 0xA0)
        for note in range(60, 72):  # C4 to C5
            for pressure in range(0, 128, 16):  # Various pressure values
                event = HashableEvent(
                    pygame.MIDIIN, device_id=1, status=160, data1=note, data2=pressure
                )
                with patch("glitchygames.events.LOG.error"):  # Suppress log messages
                    with pytest.raises(UnhandledEventError):
                        stub.on_midi_in_event(event)
                # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_system_events(self, mock_pygame_patches):
        """Test MIDI system events."""
        from unittest.mock import patch
        
        stub = MidiEventStubs()
        scene_mock = self._setup_mock_scene_for_stub(stub)

        # Test system events (status 240-255 = 0xF0-0xFF)
        system_events = [
            (240, 0, 0),    # System Exclusive start
            (247, 0, 0),    # System Exclusive end
            (248, 0, 0),    # Timing Clock
            (249, 0, 0),    # Undefined
            (250, 0, 0),    # Start
            (251, 0, 0),    # Continue
            (252, 0, 0),    # Stop
            (253, 0, 0),    # Undefined
            (254, 0, 0),    # Active Sensing
            (255, 0, 0),    # System Reset
        ]

        for status, data1, data2 in system_events:
            event = HashableEvent(
                pygame.MIDIIN, device_id=1, status=status, data1=data1, data2=data2
            )
            with patch("glitchygames.events.LOG.error"):  # Suppress log messages
                with pytest.raises(UnhandledEventError):
                    stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_multiple_devices(self, mock_pygame_patches):
        """Test MIDI events with multiple devices."""
        from unittest.mock import patch
        
        stub = MidiEventStubs()
        scene_mock = self._setup_mock_scene_for_stub(stub)

        # Test multiple MIDI devices
        for device_id in range(5):
            # Test MIDI input
            event = HashableEvent(
                pygame.MIDIIN, device_id=device_id, status=144, data1=60, data2=127
            )
            with patch("glitchygames.events.LOG.error"):  # Suppress log messages
                with pytest.raises(UnhandledEventError):
                    stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

            # Test MIDI output
            event = HashableEvent(
                pygame.MIDIOUT, device_id=device_id, status=144, data1=60, data2=127
            )
            with patch("glitchygames.events.LOG.error"):  # Suppress log messages
                with pytest.raises(UnhandledEventError):
                    stub.on_midi_out_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_midi_velocity_variations(self, mock_pygame_patches):
        """Test MIDI events with different velocity values."""
        from unittest.mock import patch
        
        stub = MidiEventStubs()
        scene_mock = self._setup_mock_scene_for_stub(stub)

        # Test different velocity values
        velocities = [0, 32, 64, 96, 127]  # Various velocity levels

        for velocity in velocities:
            # Test note on with different velocities
            event = HashableEvent(
                pygame.MIDIIN, device_id=1, status=144, data1=60, data2=velocity
            )
            with patch("glitchygames.events.LOG.error"):  # Suppress log messages
                with pytest.raises(UnhandledEventError):
                    stub.on_midi_in_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def _setup_mock_scene_for_stub(self, stub):
        """Set up mock scene object for event stubs using centralized mocks."""
        # Create a scene mock with proper event handling configuration
        scene_mock = MockFactory.create_event_test_scene_mock(
            options={
                "debug_events": False,
                "no_unhandled_events": True  # This will cause UnhandledEventError to be raised
            },
            event_handlers={}  # Empty handlers to trigger unhandled_event fallback
        )
        
        # Set the options on the stub so unhandled_event can access them
        stub.options = scene_mock.options
        return scene_mock


class TestMidiManagerCoverage:
    """Test coverage for MIDI manager functionality."""

    def test_midi_manager_initialization(self, mock_pygame_patches):
        """Test MidiManager initialization."""
        mock_game = Mock()
        manager = MidiManager(game=mock_game)
        
        assert manager.game == mock_game
        assert hasattr(manager, "proxies")
        assert isinstance(manager.proxies, list)

    def test_midi_manager_initialization_no_game(self, mock_pygame_patches):
        """Test MidiManager initialization without game."""
        manager = MidiManager(game=None)
        # Test that manager was created successfully
        assert manager is not None

    def test_midi_manager_args(self, mock_pygame_patches):
        """Test MidiManager args method."""
        parser = argparse.ArgumentParser()
        result = MidiManager.args(parser)

        assert result is parser
