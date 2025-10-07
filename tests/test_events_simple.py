"""Focused, low-friction tests for events module quick coverage wins."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.events import (
    AllEvents,
    AllEventStubs,
    AudioEvents,
    AudioEventStubs,
    ControllerEvents,
    ControllerEventStubs,
    DropEvents,
    DropEventStubs,
    EventManager,
    FontEvents,
    FontEventStubs,
    GameEvents,
    GameEventStubs,
    HashableEvent,
    JoystickEvents,
    JoystickEventStubs,
    KeyboardEvents,
    KeyboardEventStubs,
    MidiEvents,
    MidiEventStubs,
    MouseEvents,
    MouseEventStubs,
    TextEvents,
    TextEventStubs,
    TouchEvents,
    TouchEventStubs,
    WindowEvents,
    WindowEventStubs,
    supported_events,
)


class TestSupportedEvents(unittest.TestCase):
    """Test supported_events function."""

    def test_supported_events_default(self):  # noqa: PLR6301
        """Test supported_events with default pattern."""
        events = supported_events()
        assert isinstance(events, list)
        assert len(events) > 0

    def test_supported_events_with_pattern(self):  # noqa: PLR6301
        """Test supported_events with specific pattern."""
        events = supported_events("KEY")
        assert isinstance(events, list)
        # Should find keyboard events
        assert len(events) > 0

    def test_supported_events_no_matches(self):  # noqa: PLR6301
        """Test supported_events with pattern that matches nothing."""
        events = supported_events("NONEXISTENT")
        assert isinstance(events, list)
        assert len(events) == 0


class TestHashableEvent(unittest.TestCase):
    """Test HashableEvent class."""

    def test_hashable_event_creation(self):  # noqa: PLR6301
        """Test HashableEvent creation."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        assert isinstance(event, HashableEvent)
        assert event.type == pygame.KEYDOWN

    def test_hashable_event_with_attributes(self):  # noqa: PLR6301
        """Test HashableEvent with attributes."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=pygame.KMOD_CTRL)
        assert event.type == pygame.KEYDOWN
        assert event.key == pygame.K_SPACE
        assert event.mod == pygame.KMOD_CTRL

    def test_hashable_event_hash(self):  # noqa: PLR6301
        """Test HashableEvent hash functionality."""
        event1 = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        event2 = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        # Should be hashable
        assert isinstance(hash(event1), int)
        # Same data should produce same hash
        assert hash(event1) == hash(event2)


class TestEventManager(unittest.TestCase):
    """Test EventManager class."""

    def test_event_manager_initialization(self):  # noqa: PLR6301
        """Test EventManager initialization."""
        manager = EventManager()
        assert isinstance(manager, EventManager)

    def test_event_proxy_initialization(self):  # noqa: PLR6301
        """Test EventManager.EventProxy initialization."""
        mock_source = Mock()
        proxy = EventManager.EventProxy(mock_source)
        assert isinstance(proxy, EventManager.EventProxy)
        assert proxy.event_source == mock_source

    def test_event_proxy_unhandled_event(self):  # noqa: PLR6301
        """Test EventManager.EventProxy unhandled_event method."""
        mock_source = Mock()
        proxy = EventManager.EventProxy(mock_source)
        # Should not raise exception
        proxy.unhandled_event("test", arg1="value1")


class TestEventInterfaces(unittest.TestCase):
    """Test various event interface classes."""

    def test_audio_events_interface_abstract(self):  # noqa: PLR6301
        """Test AudioEvents interface is abstract."""
        # Should not be able to instantiate abstract class
        with pytest.raises(TypeError):
            AudioEvents()

    def test_controller_events_interface_abstract(self):  # noqa: PLR6301
        """Test ControllerEvents interface is abstract."""
        with pytest.raises(TypeError):
            ControllerEvents()

    def test_drop_events_interface_abstract(self):  # noqa: PLR6301
        """Test DropEvents interface is abstract."""
        with pytest.raises(TypeError):
            DropEvents()

    def test_touch_events_interface_abstract(self):  # noqa: PLR6301
        """Test TouchEvents interface is abstract."""
        with pytest.raises(TypeError):
            TouchEvents()

    def test_game_events_interface_abstract(self):  # noqa: PLR6301
        """Test GameEvents interface is abstract."""
        with pytest.raises(TypeError):
            GameEvents()

    def test_font_events_interface_abstract(self):  # noqa: PLR6301
        """Test FontEvents interface is abstract."""
        with pytest.raises(TypeError):
            FontEvents()

    def test_keyboard_events_interface_abstract(self):  # noqa: PLR6301
        """Test KeyboardEvents interface is abstract."""
        with pytest.raises(TypeError):
            KeyboardEvents()

    def test_joystick_events_interface_abstract(self):  # noqa: PLR6301
        """Test JoystickEvents interface is abstract."""
        with pytest.raises(TypeError):
            JoystickEvents()

    def test_midi_events_interface_abstract(self):  # noqa: PLR6301
        """Test MidiEvents interface is abstract."""
        with pytest.raises(TypeError):
            MidiEvents()

    def test_mouse_events_interface_abstract(self):  # noqa: PLR6301
        """Test MouseEvents interface is abstract."""
        with pytest.raises(TypeError):
            MouseEvents()

    def test_text_events_interface_abstract(self):  # noqa: PLR6301
        """Test TextEvents interface is abstract."""
        with pytest.raises(TypeError):
            TextEvents()

    def test_window_events_interface_abstract(self):  # noqa: PLR6301
        """Test WindowEvents interface is abstract."""
        with pytest.raises(TypeError):
            WindowEvents()


class TestAllEvents(unittest.TestCase):
    """Test AllEvents and AllEventStubs classes."""

    def test_all_events_abstract(self):  # noqa: PLR6301
        """Test AllEvents is abstract."""
        with pytest.raises(TypeError):
            AllEvents()

    def test_all_event_stubs_initialization(self):  # noqa: PLR6301
        """Test AllEventStubs initialization."""
        stubs = AllEventStubs()
        assert isinstance(stubs, AllEventStubs)


class TestEventStubs(unittest.TestCase):
    """Test event stub classes."""

    def test_audio_event_stubs(self):  # noqa: PLR6301
        """Test AudioEventStubs."""
        stubs = AudioEventStubs()
        assert isinstance(stubs, AudioEventStubs)

    def test_controller_event_stubs(self):  # noqa: PLR6301
        """Test ControllerEventStubs."""
        stubs = ControllerEventStubs()
        assert isinstance(stubs, ControllerEventStubs)

    def test_drop_event_stubs(self):  # noqa: PLR6301
        """Test DropEventStubs."""
        stubs = DropEventStubs()
        assert isinstance(stubs, DropEventStubs)

    def test_touch_event_stubs(self):  # noqa: PLR6301
        """Test TouchEventStubs."""
        stubs = TouchEventStubs()
        assert isinstance(stubs, TouchEventStubs)

    def test_game_event_stubs(self):  # noqa: PLR6301
        """Test GameEventStubs."""
        stubs = GameEventStubs()
        assert isinstance(stubs, GameEventStubs)

    def test_font_event_stubs(self):  # noqa: PLR6301
        """Test FontEventStubs."""
        stubs = FontEventStubs()
        assert isinstance(stubs, FontEventStubs)

    def test_keyboard_event_stubs(self):  # noqa: PLR6301
        """Test KeyboardEventStubs."""
        stubs = KeyboardEventStubs()
        assert isinstance(stubs, KeyboardEventStubs)

    def test_joystick_event_stubs(self):  # noqa: PLR6301
        """Test JoystickEventStubs."""
        stubs = JoystickEventStubs()
        assert isinstance(stubs, JoystickEventStubs)

    def test_midi_event_stubs(self):  # noqa: PLR6301
        """Test MidiEventStubs."""
        stubs = MidiEventStubs()
        assert isinstance(stubs, MidiEventStubs)

    def test_mouse_event_stubs(self):  # noqa: PLR6301
        """Test MouseEventStubs."""
        stubs = MouseEventStubs()
        assert isinstance(stubs, MouseEventStubs)

    def test_text_event_stubs(self):  # noqa: PLR6301
        """Test TextEventStubs."""
        stubs = TextEventStubs()
        assert isinstance(stubs, TextEventStubs)

    def test_window_event_stubs(self):  # noqa: PLR6301
        """Test WindowEventStubs."""
        stubs = WindowEventStubs()
        assert isinstance(stubs, WindowEventStubs)


if __name__ == "__main__":
    unittest.main()
