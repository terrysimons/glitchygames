"""A scene that accepts every gamepad event it doesn't use, so pads never trip it up.

The engine sends a scene every device event (a pad plugged in, remapped or unplugged) and every
stick, hat, trackball, touchpad and sensor movement. Those it leaves unhandled raise under
``--no-unhandled-events``, which every test runs with (src/glitchygames/events/
input_event_interfaces.py). This game's screens learn about devices from the engine's
``on_input_device_added`` and ``on_input_device_removed`` hooks instead, and use only buttons,
so each of these is deliberately ignored. A screen that uses one overrides it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from glitchygames.scenes import Scene

if TYPE_CHECKING:
    from glitchygames.events.base import (
        ControllerAxisEvent,
        ControllerDeviceAddedEvent,
        ControllerDeviceEvent,
        ControllerTouchpadEvent,
        HashableEvent,
        JoyAxisEvent,
        JoyBallEvent,
        JoyDeviceAddedEvent,
        JoyDeviceRemovedEvent,
        JoyHatEvent,
    )


class PadTolerantScene(Scene):
    """A scene that ignores the pad events this game's screens don't use."""

    @override
    def on_joy_device_added_event(self, event: JoyDeviceAddedEvent) -> None:
        """Ignore it: devices arrive through ``on_input_device_added``."""

    @override
    def on_joy_device_removed_event(self, event: JoyDeviceRemovedEvent) -> None:
        """Ignore it: devices leave through ``on_input_device_removed``."""

    @override
    def on_controller_device_added_event(self, event: ControllerDeviceAddedEvent) -> None:
        """Ignore it: devices arrive through ``on_input_device_added``."""

    @override
    def on_controller_device_removed_event(self, event: ControllerDeviceEvent) -> None:
        """Ignore it: devices leave through ``on_input_device_removed``."""

    @override
    def on_controller_device_remapped_event(self, event: ControllerDeviceEvent) -> None:
        """Ignore it: a remapped pad keeps its instance id, so its slot is unchanged."""

    @override
    def on_joy_axis_motion_event(self, event: JoyAxisEvent) -> None:
        """Ignore it: the screens use buttons only."""

    @override
    def on_joy_ball_motion_event(self, event: JoyBallEvent) -> None:
        """Ignore it: the screens use buttons only."""

    @override
    def on_joy_hat_motion_event(self, event: JoyHatEvent) -> None:
        """Ignore it: the screens use buttons only."""

    @override
    def on_controller_axis_motion_event(self, event: ControllerAxisEvent) -> None:
        """Ignore it: the screens use buttons only."""

    @override
    def on_controller_touchpad_down_event(self, event: ControllerTouchpadEvent) -> None:
        """Ignore it: the screens use buttons only."""

    @override
    def on_controller_touchpad_motion_event(self, event: ControllerTouchpadEvent) -> None:
        """Ignore it: the screens use buttons only."""

    @override
    def on_controller_touchpad_up_event(self, event: ControllerTouchpadEvent) -> None:
        """Ignore it: the screens use buttons only."""

    @override
    def on_controller_sensor_update_event(self, event: HashableEvent) -> None:
        """Ignore it: the screens use buttons only."""
