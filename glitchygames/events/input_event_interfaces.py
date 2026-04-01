#!/usr/bin/env python3
"""Glitchy Games input event interfaces.

This module contains the abstract event interfaces and default stub
implementations for all input-related events: keyboard, mouse, joystick,
controller, touch, text, and MIDI.
"""

from __future__ import annotations

import abc
from typing import Self

from glitchygames.events.base import EventInterface, HashableEvent, unhandled_event


# Mixin
class KeyboardEvents(EventInterface):
    """Mixin for keyboard events."""

    @abc.abstractmethod
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Handle key down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # KEYDOWN          unicode, key, mod

    @abc.abstractmethod
    def on_key_up_event(self: Self, event: HashableEvent) -> None:
        """Handle key up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # KEYUP            key, mod

    @abc.abstractmethod
    def on_key_chord_up_event(self: Self, event: HashableEvent, keys: list[int]) -> None:
        """Handle key chord up events.

        Args:
            event (HashableEvent): The event to handle.
            keys (list): The keys in the chord.

        """
        # Synthesized event.

    @abc.abstractmethod
    def on_key_chord_down_event(self: Self, event: HashableEvent, keys: list[int]) -> None:
        """Handle key chord down events.

        Args:
            event (HashableEvent): The event to handle.
            keys (list): The keys in the chord.

        """
        # Synthesized event.


# Mixin
class KeyboardEventStubs(EventInterface):
    """Mixin for keyboard events."""

    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Handle key down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # KEYDOWN          unicode, key, mod
        unhandled_event(self, event)

    def on_key_up_event(self: Self, event: HashableEvent) -> None:
        """Handle key up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # KEYUP            key, mod
        unhandled_event(self, event)

    def on_key_chord_up_event(self: Self, event: HashableEvent, keys: list[int]) -> None:
        """Handle key chord up events.

        Args:
            event (HashableEvent): The event to handle.
            keys (list): The keys in the chord.

        """
        # Synthesized event.
        unhandled_event(self, event, keys)

    def on_key_chord_down_event(self: Self, event: HashableEvent, keys: list[int]) -> None:
        """Handle key chord down events.

        Args:
            event (HashableEvent): The event to handle.
            keys (list): The keys in the chord.

        """
        # Synthesized event.
        unhandled_event(self, event, keys)


# Mixin
class MouseEvents(EventInterface):  # noqa: PLR0904
    """Mixin for mouse events."""

    @abc.abstractmethod
    def on_mouse_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEMOTION      pos, rel, buttons

    @abc.abstractmethod
    def on_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.

    @abc.abstractmethod
    def on_left_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle left mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.

    @abc.abstractmethod
    def on_left_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle left mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.

    @abc.abstractmethod
    def on_middle_mouse_drag_event(
        self: Self,
        event: HashableEvent,
        trigger: HashableEvent,
    ) -> None:
        """Handle middle mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drag.

        """
        # Synthesized event.

    @abc.abstractmethod
    def on_middle_mouse_drop_event(
        self: Self,
        event: HashableEvent,
        trigger: HashableEvent,
    ) -> None:
        """Handle middle mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drop.

        """
        # Synthesized event.

    @abc.abstractmethod
    def on_right_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle right mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.

    @abc.abstractmethod
    def on_right_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle right mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_focus_event(self: Self, event: HashableEvent, entering_focus: object) -> None:
        """Handle mouse focus events.

        Args:
            event (HashableEvent): The event to handle.
            entering_focus (object): The object that is entering focus.

        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_unfocus_event(self: Self, event: HashableEvent, leaving_focus: object) -> None:
        """Handle mouse unfocus events.

        Args:
            event (HashableEvent): The event to handle.
            leaving_focus (object): The object that is leaving focus.

        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button

    @abc.abstractmethod
    def on_left_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Left Mouse Button Up pos, button

    @abc.abstractmethod
    def on_middle_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle middle mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Middle Mouse Button Up pos, button

    @abc.abstractmethod
    def on_right_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle right mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Right Mouse Button Up pos, button

    @abc.abstractmethod
    def on_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button

    @abc.abstractmethod
    def on_left_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Left Mouse Button Down pos, button

    @abc.abstractmethod
    def on_middle_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle middle mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Middle Mouse Button Down pos, button

    @abc.abstractmethod
    def on_right_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle right mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Right Mouse Button Down pos, button

    @abc.abstractmethod
    def on_mouse_scroll_down_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse scroll down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # This is a synthesized event.

    @abc.abstractmethod
    def on_mouse_scroll_up_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse scroll up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # This is a synthesized event.

    @abc.abstractmethod
    def on_mouse_wheel_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse wheel events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEWHEEL flipped, y, x, touch, window


# Mixin
class MouseEventStubs(EventInterface):  # noqa: PLR0904
    """Mixin for mouse events."""

    def on_mouse_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEMOTION      pos, rel, buttons
        unhandled_event(self, event)

    def on_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    def on_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    def on_left_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle left mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    def on_left_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle left mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    def on_middle_mouse_drag_event(
        self: Self,
        event: HashableEvent,
        trigger: HashableEvent,
    ) -> None:
        """Handle middle mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drag.

        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    def on_middle_mouse_drop_event(
        self: Self,
        event: HashableEvent,
        trigger: HashableEvent,
    ) -> None:
        """Handle middle mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drop.

        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    def on_right_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle right mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    def on_right_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle right mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    def on_mouse_focus_event(self: Self, event: HashableEvent, entering_focus: object) -> None:
        """Handle mouse focus events.

        Args:
            event (HashableEvent): The event to handle.
            entering_focus (object): The object that is entering focus.

        """
        # Synthesized event.
        unhandled_event(self, event, entering_focus)

    def on_mouse_unfocus_event(self: Self, event: HashableEvent, leaving_focus: object) -> None:
        """Handle mouse unfocus events.

        Args:
            event (HashableEvent): The event to handle.
            leaving_focus (object): The object that is leaving focus.

        """
        # Synthesized event.
        unhandled_event(self, event, leaving_focus)

    def on_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        unhandled_event(self, event)

    def on_left_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Left Mouse Button Up pos, button
        unhandled_event(self, event)

    def on_middle_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle middle mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Middle Mouse Button Up pos, button
        unhandled_event(self, event)

    def on_right_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle right mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Right Mouse Button Up pos, button
        unhandled_event(self, event)

    def on_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        unhandled_event(self, event)

    def on_left_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Left Mouse Button Down pos, button
        unhandled_event(self, event)

    def on_middle_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle middle mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Middle Mouse Button Down pos, button
        unhandled_event(self, event)

    def on_right_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle right mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # Right Mouse Button Down pos, button
        unhandled_event(self, event)

    def on_mouse_scroll_down_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse scroll down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # This is a synthesized event.
        unhandled_event(self, event)

    def on_mouse_scroll_up_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse scroll up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # This is a synthesized event.
        unhandled_event(self, event)

    def on_mouse_wheel_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse wheel events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEWHEEL flipped, y, x, touch, window
        unhandled_event(self, event)


# Mixin
class JoystickEvents(EventInterface):
    """Mixin for joystick events."""

    @abc.abstractmethod
    def on_joy_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick axis motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYAXISMOTION    joy, axis, value

    @abc.abstractmethod
    def on_joy_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYBUTTONDOWN    joy, button

    @abc.abstractmethod
    def on_joy_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYBUTTONUP      joy, button

    @abc.abstractmethod
    def on_joy_hat_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick hat motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYHATMOTION     joy, hat, value

    @abc.abstractmethod
    def on_joy_ball_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick ball motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYBALLMOTION    joy, ball, rel

    @abc.abstractmethod
    def on_joy_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick device added events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYDEVICEADDED device_index, guid

    @abc.abstractmethod
    def on_joy_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick device removed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYDEVICEREMOVED device_index


# Mixin
class JoystickEventStubs(EventInterface):
    """Mixin for joystick events."""

    def on_joy_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick axis motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYAXISMOTION    joy, axis, value
        unhandled_event(self, event)

    def on_joy_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYBUTTONDOWN    joy, button
        unhandled_event(self, event)

    def on_joy_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYBUTTONUP      joy, button
        unhandled_event(self, event)

    def on_joy_hat_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick hat motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYHATMOTION     joy, hat, value
        unhandled_event(self, event)

    def on_joy_ball_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick ball motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYBALLMOTION    joy, ball, rel
        unhandled_event(self, event)

    def on_joy_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick device added events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYDEVICEADDED device_index, guid
        unhandled_event(self, event)

    def on_joy_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick device removed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # JOYDEVICEREMOVED device_index
        unhandled_event(self, event)


# Mixin
class ControllerEvents(EventInterface):
    """Mixin for controller events."""

    @abc.abstractmethod
    def on_controller_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle controller axis motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERAXISMOTION joy, axis, value

    @abc.abstractmethod
    def on_controller_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle controller button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERBUTTONDOWN joy, button

    @abc.abstractmethod
    def on_controller_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle controller button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERBUTTONUP   joy, button

    @abc.abstractmethod
    def on_controller_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device added events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERDEVICEADDED device_index, guid

    @abc.abstractmethod
    def on_controller_device_remapped_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device remapped events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERDEVICEREMAPPED device_index

    @abc.abstractmethod
    def on_controller_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device removed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERDEVICEREMOVED device_index

    @abc.abstractmethod
    def on_controller_touchpad_down_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERTOUCHPADDOWN joy, touchpad

    @abc.abstractmethod
    def on_controller_touchpad_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERTOUCHPADMOTION joy, touchpad

    @abc.abstractmethod
    def on_controller_touchpad_up_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERTOUCHPADUP joy, touchpad

    @abc.abstractmethod
    def on_controller_sensor_update_event(self: Self, event: HashableEvent) -> None:
        """Handle controller sensor update events (gyroscope, accelerometer).

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERSENSORUPDATE instance_id, sensor, data


class ControllerEventStubs(ControllerEvents):
    """Mixin for controller events."""

    def on_controller_axis_motion_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle controller axis motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERAXISMOTION joy, axis, value
        unhandled_event(self, event)

    def on_controller_button_down_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle controller button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERBUTTONDOWN joy, button
        unhandled_event(self, event)

    def on_controller_button_up_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle controller button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERBUTTONUP   joy, button
        unhandled_event(self, event)

    def on_controller_device_added_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle controller device added events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERDEVICEADDED device_index, guid
        unhandled_event(self, event)

    def on_controller_device_remapped_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle controller device remapped events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERDEVICEREMAPPED device_index
        unhandled_event(self, event)

    def on_controller_device_removed_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle controller device removed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERDEVICEREMOVED device_index
        unhandled_event(self, event)

    def on_controller_touchpad_down_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle controller touchpad down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERTOUCHPADDOWN joy, touchpad
        unhandled_event(self, event)

    def on_controller_touchpad_motion_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle controller touchpad motion events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERTOUCHPADMOTION joy, touchpad
        unhandled_event(self, event)

    def on_controller_touchpad_up_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle controller touchpad up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERTOUCHPADUP joy, touchpad
        unhandled_event(self, event)

    def on_controller_sensor_update_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle controller sensor update events (gyroscope, accelerometer).

        Args:
            event (HashableEvent): The event to handle.

        """
        # CONTROLLERSENSORUPDATE instance_id, sensor, data
        unhandled_event(self, event)


# Mixin
class TouchEvents(EventInterface):
    """Mixin for touch events."""

    @abc.abstractmethod
    def on_touch_down_event(self: Self, event: HashableEvent) -> None:
        """Handle finger down event.

        Args:
            event: The pygame event.

        """
        # FINGERDOWN       finger_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_touch_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle finger motion event.

        Args:
            event: The pygame event.

        """
        # FINGERMOTION     finger_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_touch_up_event(self: Self, event: HashableEvent) -> None:
        """Handle finger up event.

        Args:
            event: The pygame event.

        """
        # FINGERUP         finger_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_multi_touch_down_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger down event.

        Args:
            event: The pygame event.

        """
        # MULTIFINGERDOWN  touch_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_multi_touch_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger motion event.

        Args:
            event: The pygame event.

        """
        # MULTIFINGERMOTION touch_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_multi_touch_up_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger up event.

        Args:
            event: The pygame event.

        """
        # MULTIFINGERUP    touch_id, x, y, dx, dy, pressure


# Mixin
class TouchEventStubs(EventInterface):
    """Mixin for touch events."""

    def on_touch_down_event(self: Self, event: HashableEvent) -> None:
        """Handle finger down event.

        Args:
            event: The pygame event.

        """
        # FINGERDOWN       finger_id, x, y, dx, dy, pressure
        unhandled_event(self, event)

    def on_touch_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle finger motion event.

        Args:
            event: The pygame event.

        """
        # FINGERMOTION     finger_id, x, y, dx, dy, pressure
        unhandled_event(self, event)

    def on_touch_up_event(self: Self, event: HashableEvent) -> None:
        """Handle finger up event.

        Args:
            event: The pygame event.

        """
        # FINGERUP         finger_id, x, y, dx, dy, pressure
        unhandled_event(self, event)

    def on_multi_touch_down_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger down event.

        Args:
            event: The pygame event.

        """
        # MULTIFINGERDOWN  touch_id, x, y, dx, dy, pressure
        unhandled_event(self, event)

    def on_multi_touch_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger motion event.

        Args:
            event: The pygame event.

        """
        # MULTIFINGERMOTION touch_id, x, y, dx, dy, pressure
        unhandled_event(self, event)

    def on_multi_touch_up_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger up event.

        Args:
            event: The pygame event.

        """
        # MULTIFINGERUP    touch_id, x, y, dx, dy, pressure
        unhandled_event(self, event)


class TextEvents(EventInterface):
    """Mixin for text events."""

    @abc.abstractmethod
    def on_text_editing_event(self: Self, event: HashableEvent) -> None:
        """Handle text editing events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # TEXTEDITING      text, start, length

    @abc.abstractmethod
    def on_text_input_event(self: Self, event: HashableEvent) -> None:
        """Handle text input events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # TEXTINPUT        text


class TextEventStubs(EventInterface):
    """Mixin for text events."""

    def on_text_editing_event(self: Self, event: HashableEvent) -> None:
        """Handle text editing events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # TEXTEDITING      text, start, length
        unhandled_event(self, event)

    def on_text_input_event(self: Self, event: HashableEvent) -> None:
        """Handle text input events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # TEXTINPUT        text
        unhandled_event(self, event)


# Mixin
class MidiEvents(EventInterface):
    """Mixin for midi events."""

    @abc.abstractmethod
    def on_midi_in_event(self: Self, event: HashableEvent) -> None:
        """Handle midi input events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MIDIIN           device_id, status, data1, data2

    @abc.abstractmethod
    def on_midi_out_event(self: Self, event: HashableEvent) -> None:
        """Handle midi output events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MIDIOUT          device_id, status, data1, data2


# Mixin
class MidiEventStubs(EventInterface):
    """Mixin for midi events."""

    def on_midi_in_event(self: Self, event: HashableEvent) -> None:
        """Handle midi input events.

        Args:
            event (HashableEvent): The event to handle.

        """
        unhandled_event(self, event)

    def on_midi_out_event(self: Self, event: HashableEvent) -> None:
        """Handle midi output events.

        Args:
            event (HashableEvent): The event to handle.

        """
        unhandled_event(self, event)
