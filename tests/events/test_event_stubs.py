"""Coverage tests for event stub classes in glitchygames/events/core.py.

This module tests all event stub classes that raise UnhandledEventError
when their methods are invoked, covering all EventStubs classes.
"""

import abc
import logging
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import HashableEvent, UnhandledEventError
from glitchygames.events.core import (
    AppEventStubs,
    AudioEventStubs,
    ControllerEventStubs,
    DropEventStubs,
    FontEventStubs,
    GameEventStubs,
    JoystickEventStubs,
    KeyboardEventStubs,
    MidiEventStubs,
    MouseEventStubs,
    TextEventStubs,
    TouchEventStubs,
    WindowEventStubs,
)


def _create_stub_with_options(stub_class):
    """Create a stub instance and attach options needed by unhandled_event.

    Args:
        stub_class: The stub class to instantiate.

    Returns:
        An instance of the stub class with options configured.

    """
    stub = stub_class()
    # unhandled_event accesses game.options, so the stub itself needs options
    if not hasattr(stub, 'options'):
        stub.options = {'debug_events': False, 'no_unhandled_events': True}
    return stub


class TestWindowEventStubs:
    """Test all WindowEventStubs methods raise UnhandledEventError."""

    def test_on_window_close_event_raises(self, mock_pygame_patches, mocker):
        """on_window_close_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWCLOSE)
        with pytest.raises(UnhandledEventError):
            stub.on_window_close_event(event)

    def test_on_window_enter_event_raises(self, mock_pygame_patches, mocker):
        """on_window_enter_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWENTER)
        with pytest.raises(UnhandledEventError):
            stub.on_window_enter_event(event)

    def test_on_window_exposed_event_raises(self, mock_pygame_patches, mocker):
        """on_window_exposed_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWEXPOSED)
        with pytest.raises(UnhandledEventError):
            stub.on_window_exposed_event(event)

    def test_on_window_focus_gained_event_raises(self, mock_pygame_patches, mocker):
        """on_window_focus_gained_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWFOCUSGAINED)
        with pytest.raises(UnhandledEventError):
            stub.on_window_focus_gained_event(event)

    def test_on_window_focus_lost_event_raises(self, mock_pygame_patches, mocker):
        """on_window_focus_lost_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWFOCUSLOST)
        with pytest.raises(UnhandledEventError):
            stub.on_window_focus_lost_event(event)

    def test_on_window_hidden_event_raises(self, mock_pygame_patches, mocker):
        """on_window_hidden_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWHIDDEN)
        with pytest.raises(UnhandledEventError):
            stub.on_window_hidden_event(event)

    def test_on_window_hit_test_event_raises(self, mock_pygame_patches, mocker):
        """on_window_hit_test_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWHITTEST)
        with pytest.raises(UnhandledEventError):
            stub.on_window_hit_test_event(event)

    def test_on_window_leave_event_raises(self, mock_pygame_patches, mocker):
        """on_window_leave_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWLEAVE)
        with pytest.raises(UnhandledEventError):
            stub.on_window_leave_event(event)

    def test_on_window_maximized_event_raises(self, mock_pygame_patches, mocker):
        """on_window_maximized_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWMAXIMIZED)
        with pytest.raises(UnhandledEventError):
            stub.on_window_maximized_event(event)

    def test_on_window_minimized_event_raises(self, mock_pygame_patches, mocker):
        """on_window_minimized_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWMINIMIZED)
        with pytest.raises(UnhandledEventError):
            stub.on_window_minimized_event(event)

    def test_on_window_moved_event_raises(self, mock_pygame_patches, mocker):
        """on_window_moved_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWMOVED)
        with pytest.raises(UnhandledEventError):
            stub.on_window_moved_event(event)

    def test_on_window_resized_event_raises(self, mock_pygame_patches, mocker):
        """on_window_resized_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWRESIZED, size=(800, 600), w=800, h=600)
        with pytest.raises(UnhandledEventError):
            stub.on_window_resized_event(event)

    def test_on_window_restored_event_raises(self, mock_pygame_patches, mocker):
        """on_window_restored_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWRESTORED)
        with pytest.raises(UnhandledEventError):
            stub.on_window_restored_event(event)

    def test_on_window_shown_event_raises(self, mock_pygame_patches, mocker):
        """on_window_shown_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWSHOWN)
        with pytest.raises(UnhandledEventError):
            stub.on_window_shown_event(event)

    def test_on_window_size_changed_event_raises(self, mock_pygame_patches, mocker):
        """on_window_size_changed_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWSIZECHANGED, size=(1024, 768), w=1024, h=768)
        with pytest.raises(UnhandledEventError):
            stub.on_window_size_changed_event(event)

    def test_on_window_take_focus_event_raises(self, mock_pygame_patches, mocker):
        """on_window_take_focus_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(WindowEventStubs)
        event = HashableEvent(pygame.WINDOWTAKEFOCUS)
        with pytest.raises(UnhandledEventError):
            stub.on_window_take_focus_event(event)


class TestJoystickEventStubs:
    """Test all JoystickEventStubs methods raise UnhandledEventError."""

    def test_on_joy_axis_motion_event_raises(self, mock_pygame_patches, mocker):
        """on_joy_axis_motion_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(JoystickEventStubs)
        event = HashableEvent(pygame.JOYAXISMOTION, joy=0, axis=0, value=0.5)
        with pytest.raises(UnhandledEventError):
            stub.on_joy_axis_motion_event(event)

    def test_on_joy_button_down_event_raises(self, mock_pygame_patches, mocker):
        """on_joy_button_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(JoystickEventStubs)
        event = HashableEvent(pygame.JOYBUTTONDOWN, joy=0, button=0)
        with pytest.raises(UnhandledEventError):
            stub.on_joy_button_down_event(event)

    def test_on_joy_button_up_event_raises(self, mock_pygame_patches, mocker):
        """on_joy_button_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(JoystickEventStubs)
        event = HashableEvent(pygame.JOYBUTTONUP, joy=0, button=0)
        with pytest.raises(UnhandledEventError):
            stub.on_joy_button_up_event(event)

    def test_on_joy_hat_motion_event_raises(self, mock_pygame_patches, mocker):
        """on_joy_hat_motion_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(JoystickEventStubs)
        event = HashableEvent(pygame.JOYHATMOTION, joy=0, hat=0, value=(0, 1))
        with pytest.raises(UnhandledEventError):
            stub.on_joy_hat_motion_event(event)

    def test_on_joy_ball_motion_event_raises(self, mock_pygame_patches, mocker):
        """on_joy_ball_motion_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(JoystickEventStubs)
        event = HashableEvent(pygame.JOYBALLMOTION, joy=0, ball=0, rel=(1, 0))
        with pytest.raises(UnhandledEventError):
            stub.on_joy_ball_motion_event(event)

    def test_on_joy_device_added_event_raises(self, mock_pygame_patches, mocker):
        """on_joy_device_added_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(JoystickEventStubs)
        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=0, guid='test-guid')
        with pytest.raises(UnhandledEventError):
            stub.on_joy_device_added_event(event)

    def test_on_joy_device_removed_event_raises(self, mock_pygame_patches, mocker):
        """on_joy_device_removed_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(JoystickEventStubs)
        event = HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=0)
        with pytest.raises(UnhandledEventError):
            stub.on_joy_device_removed_event(event)


class TestAppEventStubs:
    """Test all AppEventStubs methods raise UnhandledEventError."""

    def test_on_app_did_enter_background_event_raises(self, mock_pygame_patches, mocker):
        """on_app_did_enter_background_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(AppEventStubs)
        event = HashableEvent(pygame.APP_DIDENTERBACKGROUND)
        with pytest.raises(UnhandledEventError):
            stub.on_app_did_enter_background_event(event)

    def test_on_app_did_enter_foreground_event_raises(self, mock_pygame_patches, mocker):
        """on_app_did_enter_foreground_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(AppEventStubs)
        event = HashableEvent(pygame.APP_DIDENTERFOREGROUND)
        with pytest.raises(UnhandledEventError):
            stub.on_app_did_enter_foreground_event(event)

    def test_on_app_will_enter_background_event_raises(self, mock_pygame_patches, mocker):
        """on_app_will_enter_background_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(AppEventStubs)
        event = HashableEvent(pygame.APP_WILLENTERBACKGROUND)
        with pytest.raises(UnhandledEventError):
            stub.on_app_will_enter_background_event(event)

    def test_on_app_will_enter_foreground_event_raises(self, mock_pygame_patches, mocker):
        """on_app_will_enter_foreground_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(AppEventStubs)
        event = HashableEvent(pygame.APP_WILLENTERFOREGROUND)
        with pytest.raises(UnhandledEventError):
            stub.on_app_will_enter_foreground_event(event)

    def test_on_app_low_memory_event_raises(self, mock_pygame_patches, mocker):
        """on_app_low_memory_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(AppEventStubs)
        event = HashableEvent(pygame.APP_LOWMEMORY)
        with pytest.raises(UnhandledEventError):
            stub.on_app_low_memory_event(event)

    def test_on_app_terminating_event_raises(self, mock_pygame_patches, mocker):
        """on_app_terminating_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(AppEventStubs)
        event = HashableEvent(pygame.APP_TERMINATING)
        with pytest.raises(UnhandledEventError):
            stub.on_app_terminating_event(event)


class TestFontEventStubs:
    """Test FontEventStubs methods raise UnhandledEventError."""

    def test_on_font_changed_event_raises(self, mock_pygame_patches, mocker):
        """on_font_changed_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(FontEventStubs)
        event = HashableEvent(pygame.USEREVENT, action='font_changed')
        with pytest.raises(UnhandledEventError):
            stub.on_font_changed_event(event)


class TestMidiEventStubs:
    """Test MidiEventStubs methods raise UnhandledEventError."""

    def test_on_midi_in_event_raises(self, mock_pygame_patches, mocker):
        """on_midi_in_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MidiEventStubs)
        event = HashableEvent(pygame.USEREVENT, device_id=0, status=144, data1=60, data2=100)
        with pytest.raises(UnhandledEventError):
            stub.on_midi_in_event(event)

    def test_on_midi_out_event_raises(self, mock_pygame_patches, mocker):
        """on_midi_out_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MidiEventStubs)
        event = HashableEvent(pygame.USEREVENT, device_id=1, status=128, data1=60, data2=0)
        with pytest.raises(UnhandledEventError):
            stub.on_midi_out_event(event)


class TestMouseEventStubsFocusUnfocus:
    """Test MouseEventStubs focus/unfocus methods raise UnhandledEventError."""

    def test_on_mouse_focus_event_raises(self, mock_pygame_patches, mocker):
        """on_mouse_focus_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(50, 50))
        entering_focus_object = mocker.Mock()
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_focus_event(event, entering_focus_object)

    def test_on_mouse_unfocus_event_raises(self, mock_pygame_patches, mocker):
        """on_mouse_unfocus_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(50, 50), rel=(0, 0))
        leaving_focus_object = mocker.Mock()
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_unfocus_event(event, leaving_focus_object)

    def test_on_mouse_motion_event_raises(self, mock_pygame_patches, mocker):
        """on_mouse_motion_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 200), rel=(5, 3), buttons=(0, 0, 0))
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_motion_event(event)

    def test_on_mouse_button_down_event_raises(self, mock_pygame_patches, mocker):
        """on_mouse_button_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=1)
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_button_down_event(event)

    def test_on_mouse_button_up_event_raises(self, mock_pygame_patches, mocker):
        """on_mouse_button_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(100, 200), button=1)
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_button_up_event(event)

    def test_on_mouse_drag_event_raises(self, mock_pygame_patches, mocker):
        """on_mouse_drag_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(110, 210), rel=(10, 10))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=1)
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_drag_event(event, trigger)

    def test_on_mouse_drop_event_raises(self, mock_pygame_patches, mocker):
        """on_mouse_drop_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(120, 220), button=1)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=1)
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_drop_event(event, trigger)

    def test_on_left_mouse_drag_event_raises(self, mock_pygame_patches, mocker):
        """on_left_mouse_drag_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(110, 210), rel=(10, 10), buttons=(1, 0, 0))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=1)
        with pytest.raises(UnhandledEventError):
            stub.on_left_mouse_drag_event(event, trigger)

    def test_on_left_mouse_drop_event_raises(self, mock_pygame_patches, mocker):
        """on_left_mouse_drop_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(120, 220), button=1)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=1)
        with pytest.raises(UnhandledEventError):
            stub.on_left_mouse_drop_event(event, trigger)

    def test_on_middle_mouse_drag_event_raises(self, mock_pygame_patches, mocker):
        """on_middle_mouse_drag_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(110, 210), rel=(10, 10), buttons=(0, 1, 0))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=2)
        with pytest.raises(UnhandledEventError):
            stub.on_middle_mouse_drag_event(event, trigger)

    def test_on_middle_mouse_drop_event_raises(self, mock_pygame_patches, mocker):
        """on_middle_mouse_drop_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(120, 220), button=2)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=2)
        with pytest.raises(UnhandledEventError):
            stub.on_middle_mouse_drop_event(event, trigger)

    def test_on_right_mouse_drag_event_raises(self, mock_pygame_patches, mocker):
        """on_right_mouse_drag_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEMOTION, pos=(110, 210), rel=(10, 10), buttons=(0, 0, 1))
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=3)
        with pytest.raises(UnhandledEventError):
            stub.on_right_mouse_drag_event(event, trigger)

    def test_on_right_mouse_drop_event_raises(self, mock_pygame_patches, mocker):
        """on_right_mouse_drop_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(120, 220), button=3)
        trigger = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=3)
        with pytest.raises(UnhandledEventError):
            stub.on_right_mouse_drop_event(event, trigger)

    def test_on_left_mouse_button_up_event_raises(self, mock_pygame_patches, mocker):
        """on_left_mouse_button_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(100, 200), button=1)
        with pytest.raises(UnhandledEventError):
            stub.on_left_mouse_button_up_event(event)

    def test_on_middle_mouse_button_up_event_raises(self, mock_pygame_patches, mocker):
        """on_middle_mouse_button_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(100, 200), button=2)
        with pytest.raises(UnhandledEventError):
            stub.on_middle_mouse_button_up_event(event)

    def test_on_right_mouse_button_up_event_raises(self, mock_pygame_patches, mocker):
        """on_right_mouse_button_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(100, 200), button=3)
        with pytest.raises(UnhandledEventError):
            stub.on_right_mouse_button_up_event(event)

    def test_on_left_mouse_button_down_event_raises(self, mock_pygame_patches, mocker):
        """on_left_mouse_button_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=1)
        with pytest.raises(UnhandledEventError):
            stub.on_left_mouse_button_down_event(event)

    def test_on_middle_mouse_button_down_event_raises(self, mock_pygame_patches, mocker):
        """on_middle_mouse_button_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=2)
        with pytest.raises(UnhandledEventError):
            stub.on_middle_mouse_button_down_event(event)

    def test_on_right_mouse_button_down_event_raises(self, mock_pygame_patches, mocker):
        """on_right_mouse_button_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 200), button=3)
        with pytest.raises(UnhandledEventError):
            stub.on_right_mouse_button_down_event(event)

    def test_on_mouse_scroll_down_event_raises(self, mock_pygame_patches, mocker):
        """on_mouse_scroll_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEWHEEL, y=-1)
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_scroll_down_event(event)

    def test_on_mouse_scroll_up_event_raises(self, mock_pygame_patches, mocker):
        """on_mouse_scroll_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEWHEEL, y=1)
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_scroll_up_event(event)

    def test_on_mouse_wheel_event_raises(self, mock_pygame_patches, mocker):
        """on_mouse_wheel_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(MouseEventStubs)
        event = HashableEvent(pygame.MOUSEWHEEL, y=1, x=0, flipped=False)
        with pytest.raises(UnhandledEventError):
            stub.on_mouse_wheel_event(event)


class TestAudioEventStubs:
    """Test AudioEventStubs methods raise UnhandledEventError."""

    def test_on_audio_device_added_event_raises(self, mock_pygame_patches, mocker):
        """on_audio_device_added_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(AudioEventStubs)
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=0, iscapture=0)
        with pytest.raises(UnhandledEventError):
            stub.on_audio_device_added_event(event)

    def test_on_audio_device_removed_event_raises(self, mock_pygame_patches, mocker):
        """on_audio_device_removed_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(AudioEventStubs)
        event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=0, iscapture=0)
        with pytest.raises(UnhandledEventError):
            stub.on_audio_device_removed_event(event)


class TestControllerEventStubs:
    """Test ControllerEventStubs methods raise UnhandledEventError."""

    def test_on_controller_axis_motion_event_raises(self, mock_pygame_patches, mocker):
        """on_controller_axis_motion_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(ControllerEventStubs)
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, joy=0, axis=0, value=100)
        with pytest.raises(UnhandledEventError):
            stub.on_controller_axis_motion_event(event)

    def test_on_controller_button_down_event_raises(self, mock_pygame_patches, mocker):
        """on_controller_button_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(ControllerEventStubs)
        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, joy=0, button=0)
        with pytest.raises(UnhandledEventError):
            stub.on_controller_button_down_event(event)

    def test_on_controller_button_up_event_raises(self, mock_pygame_patches, mocker):
        """on_controller_button_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(ControllerEventStubs)
        event = HashableEvent(pygame.CONTROLLERBUTTONUP, joy=0, button=0)
        with pytest.raises(UnhandledEventError):
            stub.on_controller_button_up_event(event)

    def test_on_controller_device_added_event_raises(self, mock_pygame_patches, mocker):
        """on_controller_device_added_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(ControllerEventStubs)
        event = HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=0, guid='guid')
        with pytest.raises(UnhandledEventError):
            stub.on_controller_device_added_event(event)

    def test_on_controller_device_remapped_event_raises(self, mock_pygame_patches, mocker):
        """on_controller_device_remapped_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(ControllerEventStubs)
        event = HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, device_index=0)
        with pytest.raises(UnhandledEventError):
            stub.on_controller_device_remapped_event(event)

    def test_on_controller_device_removed_event_raises(self, mock_pygame_patches, mocker):
        """on_controller_device_removed_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(ControllerEventStubs)
        event = HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=0)
        with pytest.raises(UnhandledEventError):
            stub.on_controller_device_removed_event(event)

    def test_on_controller_touchpad_down_event_raises(self, mock_pygame_patches, mocker):
        """on_controller_touchpad_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(ControllerEventStubs)
        event = HashableEvent(pygame.CONTROLLERTOUCHPADDOWN, instance_id=0)
        with pytest.raises(UnhandledEventError):
            stub.on_controller_touchpad_down_event(event)

    def test_on_controller_touchpad_motion_event_raises(self, mock_pygame_patches, mocker):
        """on_controller_touchpad_motion_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(ControllerEventStubs)
        event = HashableEvent(pygame.CONTROLLERTOUCHPADMOTION, instance_id=0)
        with pytest.raises(UnhandledEventError):
            stub.on_controller_touchpad_motion_event(event)

    def test_on_controller_touchpad_up_event_raises(self, mock_pygame_patches, mocker):
        """on_controller_touchpad_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(ControllerEventStubs)
        event = HashableEvent(pygame.CONTROLLERTOUCHPADUP, instance_id=0)
        with pytest.raises(UnhandledEventError):
            stub.on_controller_touchpad_up_event(event)


class TestDropEventStubs:
    """Test DropEventStubs methods raise UnhandledEventError."""

    def test_on_drop_begin_event_raises(self, mock_pygame_patches, mocker):
        """on_drop_begin_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(DropEventStubs)
        event = HashableEvent(pygame.DROPBEGIN)
        with pytest.raises(UnhandledEventError):
            stub.on_drop_begin_event(event)

    def test_on_drop_file_event_raises(self, mock_pygame_patches, mocker):
        """on_drop_file_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(DropEventStubs)
        event = HashableEvent(pygame.DROPFILE, file='test.txt')
        with pytest.raises(UnhandledEventError):
            stub.on_drop_file_event(event)

    def test_on_drop_text_event_raises(self, mock_pygame_patches, mocker):
        """on_drop_text_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(DropEventStubs)
        event = HashableEvent(pygame.DROPTEXT, text='hello')
        with pytest.raises(UnhandledEventError):
            stub.on_drop_text_event(event)

    def test_on_drop_complete_event_raises(self, mock_pygame_patches, mocker):
        """on_drop_complete_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(DropEventStubs)
        event = HashableEvent(pygame.DROPCOMPLETE)
        with pytest.raises(UnhandledEventError):
            stub.on_drop_complete_event(event)


class TestTouchEventStubs:
    """Test TouchEventStubs methods raise UnhandledEventError."""

    def test_on_touch_down_event_raises(self, mock_pygame_patches, mocker):
        """on_touch_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(TouchEventStubs)
        event = HashableEvent(pygame.FINGERDOWN, finger_id=0, x=0.5, y=0.5)
        with pytest.raises(UnhandledEventError):
            stub.on_touch_down_event(event)

    def test_on_touch_motion_event_raises(self, mock_pygame_patches, mocker):
        """on_touch_motion_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(TouchEventStubs)
        event = HashableEvent(pygame.FINGERMOTION, finger_id=0, x=0.5, y=0.5)
        with pytest.raises(UnhandledEventError):
            stub.on_touch_motion_event(event)

    def test_on_touch_up_event_raises(self, mock_pygame_patches, mocker):
        """on_touch_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(TouchEventStubs)
        event = HashableEvent(pygame.FINGERUP, finger_id=0, x=0.5, y=0.5)
        with pytest.raises(UnhandledEventError):
            stub.on_touch_up_event(event)

    def test_on_multi_touch_down_event_raises(self, mock_pygame_patches, mocker):
        """on_multi_touch_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(TouchEventStubs)
        event = HashableEvent(pygame.FINGERDOWN, touch_id=0, x=0.5, y=0.5)
        with pytest.raises(UnhandledEventError):
            stub.on_multi_touch_down_event(event)

    def test_on_multi_touch_motion_event_raises(self, mock_pygame_patches, mocker):
        """on_multi_touch_motion_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(TouchEventStubs)
        event = HashableEvent(pygame.FINGERMOTION, touch_id=0, x=0.5, y=0.5)
        with pytest.raises(UnhandledEventError):
            stub.on_multi_touch_motion_event(event)

    def test_on_multi_touch_up_event_raises(self, mock_pygame_patches, mocker):
        """on_multi_touch_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(TouchEventStubs)
        event = HashableEvent(pygame.FINGERUP, touch_id=0, x=0.5, y=0.5)
        with pytest.raises(UnhandledEventError):
            stub.on_multi_touch_up_event(event)


class TestGameEventStubs:
    """Test GameEventStubs methods raise UnhandledEventError."""

    def test_on_active_event_raises(self, mock_pygame_patches, mocker):
        """on_active_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.ACTIVEEVENT, gain=1, state=1)
        with pytest.raises(UnhandledEventError):
            stub.on_active_event(event)

    def test_on_fps_event_raises(self, mock_pygame_patches, mocker):
        """on_fps_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.USEREVENT + 1, fps=60)
        with pytest.raises(UnhandledEventError):
            stub.on_fps_event(event)

    def test_on_game_event_raises(self, mock_pygame_patches, mocker):
        """on_game_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.USEREVENT + 2, action='test')
        with pytest.raises(UnhandledEventError):
            stub.on_game_event(event)

    def test_on_menu_item_event_raises(self, mock_pygame_patches, mocker):
        """on_menu_item_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.USEREVENT + 3, menu_item='test')
        with pytest.raises(UnhandledEventError):
            stub.on_menu_item_event(event)

    def test_on_sys_wm_event_raises(self, mock_pygame_patches, mocker):
        """on_sys_wm_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.SYSWMEVENT)
        with pytest.raises(UnhandledEventError):
            stub.on_sys_wm_event(event)

    def test_on_user_event_raises(self, mock_pygame_patches, mocker):
        """on_user_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.USEREVENT, code=1)
        with pytest.raises(UnhandledEventError):
            stub.on_user_event(event)

    def test_on_video_expose_event_raises(self, mock_pygame_patches, mocker):
        """on_video_expose_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.VIDEOEXPOSE)
        with pytest.raises(UnhandledEventError):
            stub.on_video_expose_event(event)

    def test_on_video_resize_event_raises(self, mock_pygame_patches, mocker):
        """on_video_resize_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.VIDEORESIZE, size=(800, 600), w=800, h=600)
        with pytest.raises(UnhandledEventError):
            stub.on_video_resize_event(event)

    def test_on_quit_event_raises(self, mock_pygame_patches, mocker):
        """on_quit_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.QUIT)
        with pytest.raises(UnhandledEventError):
            stub.on_quit_event(event)

    def test_on_render_device_reset_event_raises(self, mock_pygame_patches, mocker):
        """on_render_device_reset_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.RENDER_DEVICE_RESET)
        with pytest.raises(UnhandledEventError):
            stub.on_render_device_reset_event(event)

    def test_on_render_targets_reset_event_raises(self, mock_pygame_patches, mocker):
        """on_render_targets_reset_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.RENDER_TARGETS_RESET)
        with pytest.raises(UnhandledEventError):
            stub.on_render_targets_reset_event(event)

    def test_on_clipboard_update_event_raises(self, mock_pygame_patches, mocker):
        """on_clipboard_update_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.CLIPBOARDUPDATE)
        with pytest.raises(UnhandledEventError):
            stub.on_clipboard_update_event(event)

    def test_on_locale_changed_event_raises(self, mock_pygame_patches, mocker):
        """on_locale_changed_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(GameEventStubs)
        event = HashableEvent(pygame.LOCALECHANGED)
        with pytest.raises(UnhandledEventError):
            stub.on_locale_changed_event(event)


class TestKeyboardEventStubs:
    """Test KeyboardEventStubs methods raise UnhandledEventError."""

    def test_on_key_down_event_raises(self, mock_pygame_patches, mocker):
        """on_key_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(KeyboardEventStubs)
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        with pytest.raises(UnhandledEventError):
            stub.on_key_down_event(event)

    def test_on_key_up_event_raises(self, mock_pygame_patches, mocker):
        """on_key_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(KeyboardEventStubs)
        event = HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0)
        with pytest.raises(UnhandledEventError):
            stub.on_key_up_event(event)

    def test_on_key_chord_up_event_raises(self, mock_pygame_patches, mocker):
        """on_key_chord_up_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(KeyboardEventStubs)
        event = HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0)
        keys = [pygame.K_LCTRL, pygame.K_a]
        with pytest.raises(UnhandledEventError):
            stub.on_key_chord_up_event(event, tuple(keys))

    def test_on_key_chord_down_event_raises(self, mock_pygame_patches, mocker):
        """on_key_chord_down_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(KeyboardEventStubs)
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        keys = [pygame.K_LCTRL, pygame.K_a]
        with pytest.raises(UnhandledEventError):
            stub.on_key_chord_down_event(event, tuple(keys))


class TestTextEventStubs:
    """Test TextEventStubs methods raise UnhandledEventError."""

    def test_on_text_editing_event_raises(self, mock_pygame_patches, mocker):
        """on_text_editing_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(TextEventStubs)
        event = HashableEvent(pygame.TEXTEDITING, text='hello', start=0, length=5)
        with pytest.raises(UnhandledEventError):
            stub.on_text_editing_event(event)

    def test_on_text_input_event_raises(self, mock_pygame_patches, mocker):
        """on_text_input_event should raise UnhandledEventError."""
        mocker.patch('glitchygames.events.core.LOG.error')
        stub = _create_stub_with_options(TextEventStubs)
        event = HashableEvent(pygame.TEXTINPUT, text='a')
        with pytest.raises(UnhandledEventError):
            stub.on_text_input_event(event)


class TestEventInterfaceSubclassHook:
    """Test EventInterface.__subclasshook__ edge cases."""

    def test_subclasshook_with_non_callable_attribute(self, mock_pygame_patches, mocker):
        """Test __subclasshook__ when attribute exists but is not callable (line 511)."""
        from glitchygames.events.core import EventInterface

        # Create a concrete ABC subclass with a non-callable attribute
        class TestInterface(EventInterface):
            log = logging.getLogger('test')

            @abc.abstractmethod
            def test_method(self):
                pass

        class ConcreteClass(abc.ABC):  # noqa: B024
            test_method = 42  # Non-callable attribute

        # __subclasshook__ is called internally by issubclass
        result = TestInterface.__subclasshook__(ConcreteClass)
        assert result is True  # Attribute exists, counts as implemented

    def test_subclasshook_with_unimplemented_method(self, mock_pygame_patches, mocker):
        """Test __subclasshook__ when abstract method is NOT implemented (lines 514-515)."""
        from glitchygames.events.core import EventInterface

        class TestInterface(EventInterface):
            log = logging.getLogger('test')

            @abc.abstractmethod
            def required_method(self):
                pass

        class IncompleteClass(abc.ABC):
            @abc.abstractmethod
            def required_method(self):
                pass

        # IncompleteClass still has required_method as abstract
        result = TestInterface.__subclasshook__(IncompleteClass)
        assert result is False
