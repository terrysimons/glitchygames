"""Tests for MIDI event functionality.

This module tests MIDI event interfaces, stubs, and event handling.
"""

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
)

from mocks.test_mock_factory import MockFactory


class TestMidiEvents:
    """Test MidiEvents interface functionality."""

    def test_midi_events_interface(self, mock_pygame_patches):
        """Test MidiEvents interface methods."""
        # Test that MidiEvents has required abstract methods
        assert hasattr(MidiEvents, "on_midi_in_event")
        assert hasattr(MidiEvents, "on_midi_out_event")

    def test_midi_event_stubs_implementation(self, mock_pygame_patches):
        """Test MidiEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = MidiEventStubs()
        assert hasattr(stub, "on_midi_in_event")
        assert hasattr(stub, "on_midi_out_event")

        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)
        try:
            stub.on_midi_in_event(event)
        except Exception as e:
            # Expected to call unhandled_event
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_in_event(self, mock_pygame_patches):
        """Test MIDI input event handling."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test MIDI input
        event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=127)
        try:
            stub.on_midi_in_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_out_event(self, mock_pygame_patches):
        """Test MIDI output event handling."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test MIDI output
        event = HashableEvent(pygame.MIDIOUT, device_id=1, status=144, data1=60, data2=127)
        try:
            stub.on_midi_out_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_note_on_events(self, mock_pygame_patches):
        """Test MIDI note on events."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test note on events (status 144 = 0x90)
        for note in range(60, 72):  # C4 to C5
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=note, data2=127)
            try:
                stub.on_midi_in_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_note_off_events(self, mock_pygame_patches):
        """Test MIDI note off events."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test note off events (status 128 = 0x80)
        for note in range(60, 72):  # C4 to C5
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=128, data1=note, data2=0)
            try:
                stub.on_midi_in_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_control_change_events(self, mock_pygame_patches):
        """Test MIDI control change events."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test control change events (status 176 = 0xB0)
        for controller in range(1, 128):  # All MIDI controllers
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=176, data1=controller, data2=64)
            try:
                stub.on_midi_in_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_program_change_events(self, mock_pygame_patches):
        """Test MIDI program change events."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test program change events (status 192 = 0xC0)
        for program in range(128):  # All MIDI programs
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=192, data1=program, data2=0)
            try:
                stub.on_midi_in_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_pitch_bend_events(self, mock_pygame_patches):
        """Test MIDI pitch bend events."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test pitch bend events (status 224 = 0xE0)
        for bend in range(0, 16384, 1024):  # Various pitch bend values
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=224, data1=bend & 0x7F, data2=(bend >> 7) & 0x7F)
            try:
                stub.on_midi_in_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_aftertouch_events(self, mock_pygame_patches):
        """Test MIDI aftertouch events."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test aftertouch events (status 208 = 0xD0)
        for pressure in range(0, 128):  # All pressure values
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=208, data1=pressure, data2=0)
            try:
                stub.on_midi_in_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_polyphonic_aftertouch_events(self, mock_pygame_patches):
        """Test MIDI polyphonic aftertouch events."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test polyphonic aftertouch events (status 160 = 0xA0)
        for note in range(60, 72):  # C4 to C5
            for pressure in range(0, 128, 16):  # Various pressure values
                event = HashableEvent(pygame.MIDIIN, device_id=1, status=160, data1=note, data2=pressure)
                try:
                    stub.on_midi_in_event(event)
                except Exception as e:
                    assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_system_events(self, mock_pygame_patches):
        """Test MIDI system events."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

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
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=status, data1=data1, data2=data2)
            try:
                stub.on_midi_in_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_multiple_devices(self, mock_pygame_patches):
        """Test MIDI events with multiple devices."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test multiple MIDI devices
        for device_id in range(5):
            # Test MIDI input
            event = HashableEvent(pygame.MIDIIN, device_id=device_id, status=144, data1=60, data2=127)
            try:
                stub.on_midi_in_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

            # Test MIDI output
            event = HashableEvent(pygame.MIDIOUT, device_id=device_id, status=144, data1=60, data2=127)
            try:
                stub.on_midi_out_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_midi_velocity_variations(self, mock_pygame_patches):
        """Test MIDI events with different velocity values."""
        stub = MidiEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test different velocity values
        velocities = [0, 32, 64, 96, 127]  # Various velocity levels

        for velocity in velocities:
            # Test note on with different velocities
            event = HashableEvent(pygame.MIDIIN, device_id=1, status=144, data1=60, data2=velocity)
            try:
                stub.on_midi_in_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def _setup_mock_game_for_stub(self, stub):
        """Helper method to setup mock game object for event stubs."""
        mock_game = Mock()
        mock_game.options = {
            "debug_events": False,
            "no_unhandled_events": False
        }
        stub.options = mock_game.options
        return mock_game


class TestMidiManagerCoverage:
    """Test coverage for MIDI manager functionality."""

    def test_midi_manager_initialization(self, mock_pygame_patches):
        """Test MidiManager initialization."""
        from glitchygames.events.midi import MidiManager

        mock_game = Mock()
        manager = MidiManager(game=mock_game)

        # Test that manager was created successfully
        assert manager is not None

    def test_midi_manager_initialization_no_game(self, mock_pygame_patches):
        """Test MidiManager initialization without game."""
        from glitchygames.events.midi import MidiManager

        manager = MidiManager(game=None)
        # Test that manager was created successfully
        assert manager is not None

    def test_midi_manager_args(self, mock_pygame_patches):
        """Test MidiManager args method."""
        import argparse

        from glitchygames.events.midi import MidiManager

        parser = argparse.ArgumentParser()
        result = MidiManager.args(parser)

        assert result is parser
