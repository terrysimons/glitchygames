"""Joystick Demo: every connected joystick and game controller, live.

Run it with ``joystick-demo`` or ``python -m joystick_demo`` and plug devices in and out. Each
device the engine sees (``Scene.input_devices``, glitchygames/input/input_devices.py) gets a
column: its name, GUID, instance id and device index (the devices door's descriptor), the layer
its events come from, then that layer's live axes, held buttons and hats. A mapped game pad
shows its controller layer (``CONTROLLER_AXIS_*`` / ``CONTROLLER_BUTTON_*`` ids, axes on
pygame's int scale); any other device its joystick layer. The readout is drawn from the frame's
input snapshot, so a replay of a recording shows exactly what the recorded run showed.

The header names the input mode (``--input-mode``: ``auto`` shows every device, ``joystick``
every device on its joystick layer, ``controller`` only mapped pads), the last device connected
or disconnected, and the last input event and the handler it reached: each press arrives once,
from the device's event layer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self, cast, override

from glitchygames.color import BLACK, WHITE, YELLOW
from glitchygames.engine import GameEngine
from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import DEFAULT_FONT_NAME
from glitchygames.scenes import Scene

if TYPE_CHECKING:
    import pygame

    from glitchygames.events.base import (
        ControllerAxisEvent,
        ControllerButtonEvent,
        ControllerDeviceAddedEvent,
        ControllerDeviceEvent,
        HashableEvent,
        JoyAxisEvent,
        JoyBallEvent,
        JoyButtonEvent,
        JoyDeviceAddedEvent,
        JoyDeviceRemovedEvent,
        JoyHatEvent,
    )
    from glitchygames.input.input_devices import InputDevice

LOG = logging.getLogger('game.joystick_demo')
LOG.addHandler(logging.NullHandler())

# The readout's text: the bundled font (never a system font scan, BUGS.md #156)
FONT_SIZE = 12
# Pixels between the screen edge and the text, and between a column's text and the next column
MARGIN = 4
# Wide enough for a 32-digit GUID at FONT_SIZE
COLUMN_WIDTH = 300
# Pixels between lines (a rendered line can be a pixel taller than the font's line size)
LINE_SPACING = 2
# Shown in the header until the first device comes or goes, and the first input event
NO_DEVICE_CHANGE = 'No device connected or disconnected yet'
NO_INPUT_EVENT = 'No input event yet'


def device_lines(device: InputDevice) -> list[str]:
    """Return the readout of one device: who it is, then its event layer's positions now.

    Args:
        device: The device.

    Returns:
        The lines, top to bottom (the first, the device's name, is drawn highlighted).

    """
    descriptor = device.descriptor
    layer = device.event_layer
    held_buttons = [str(button) for button, held in enumerate(layer.buttons) if held]
    return [
        device.name,
        f'GUID: {descriptor.guid or "unknown"}',
        f'Instance {descriptor.instance_id}, device index {descriptor.device_index}',
        f'Events: {layer.kind} layer',
        *(f'Axis {axis}: {value}' for axis, value in enumerate(layer.axes)),
        f'Buttons held: {", ".join(held_buttons) or "none"}',
        *(f'Hat {hat}: {value}' for hat, value in enumerate(layer.hats)),
    ]


class Game(Scene):
    """Shows every connected joystick and game controller with its live inputs."""

    NAME = 'Joystick Demo'
    VERSION = '1.0'

    def __init__(self: Self, options: dict[str, object]) -> None:
        """Create the demo with nothing reported yet.

        Args:
            options: The options passed to the game.

        """
        super().__init__(options=options)
        # A pygame.font font (FontManager caches it)
        self.font = cast(
            'pygame.font.Font',
            FontManager.pygame_font(
                font_config={'font_name': DEFAULT_FONT_NAME, 'font_size': FONT_SIZE}
            ),
        )
        self.last_device_change = NO_DEVICE_CHANGE
        self.last_input_event = NO_INPUT_EVENT

    def header_lines(self: Self) -> list[str]:
        """Return the header: the demo, the input mode, the device count and the last changes.

        Returns:
            The lines, top to bottom.

        """
        device_count = len(self.input_devices)
        return [
            f'{self.NAME} {self.VERSION}',
            f'Input mode: {self.input_devices.input_mode}',
            f'Devices: {device_count}' if device_count else 'No devices: plug one in',
            self.last_device_change,
            self.last_input_event,
        ]

    @override
    def update(self: Self) -> None:
        """Draw the header, then one column per device, from this frame's input snapshot."""
        assert self.screen is not None
        self.screen.fill(BLACK)
        line_height = self.font.get_linesize() + LINE_SPACING
        header = self.header_lines()
        for line_number, line in enumerate(header):
            self._draw_line(
                text=line, color=WHITE, position=(MARGIN, MARGIN + line_number * line_height)
            )
        columns_top = MARGIN + (len(header) + 1) * line_height
        for column, device in enumerate(self.input_devices):
            column_left = MARGIN + column * COLUMN_WIDTH
            for line_number, line in enumerate(device_lines(device)):
                self._draw_line(
                    text=line,
                    color=YELLOW if line_number == 0 else WHITE,
                    position=(column_left, columns_top + line_number * line_height),
                )

    def _draw_line(
        self: Self, *, text: str, color: tuple[int, int, int], position: tuple[int, int]
    ) -> None:
        """Draw one line of the readout.

        Args:
            text: The line.
            color: Its colour.
            position: Its top-left corner on the screen.

        """
        assert self.screen is not None
        rendered = self.font.render(text, antialias=False, color=color)
        self.screen.blit(rendered, position)

    @override
    def on_input_device_added(self: Self, *, device: InputDevice) -> None:
        """Report a device that was plugged in (its column appears with the next frame).

        Args:
            device: The device.

        """
        self.last_device_change = f'Connected: {device.name}'
        LOG.info('Connected: %s (instance %d)', device.name, device.instance_id)

    @override
    def on_input_device_removed(self: Self, *, device: InputDevice) -> None:
        """Report a device that was unplugged (its column goes with the next frame).

        Args:
            device: The device.

        """
        self.last_device_change = f'Disconnected: {device.name}'
        LOG.info('Disconnected: %s (instance %d)', device.name, device.instance_id)

    def _report_input_event(self: Self, *, handler_name: str, event: HashableEvent) -> None:
        """Show which handler an input event reached, from which device.

        Args:
            handler_name: The handler.
            event: The event (every joystick and controller input event has an instance id).

        """
        self.last_input_event = f'{handler_name} from instance {event.instance_id}'

    @override
    def on_joy_axis_motion_event(self: Self, event: JoyAxisEvent) -> None:
        """Report a joystick-layer axis motion.

        Args:
            event: The event.

        """
        self._report_input_event(handler_name='on_joy_axis_motion_event', event=event)

    @override
    def on_joy_ball_motion_event(self: Self, event: JoyBallEvent) -> None:
        """Report a joystick-layer trackball motion.

        Args:
            event: The event.

        """
        self._report_input_event(handler_name='on_joy_ball_motion_event', event=event)

    @override
    def on_joy_hat_motion_event(self: Self, event: JoyHatEvent) -> None:
        """Report a joystick-layer hat motion.

        Args:
            event: The event.

        """
        self._report_input_event(handler_name='on_joy_hat_motion_event', event=event)

    @override
    def on_joy_button_down_event(self: Self, event: JoyButtonEvent) -> None:
        """Report a joystick-layer button press.

        Args:
            event: The event.

        """
        self._report_input_event(handler_name='on_joy_button_down_event', event=event)

    @override
    def on_joy_button_up_event(self: Self, event: JoyButtonEvent) -> None:
        """Report a joystick-layer button release.

        Args:
            event: The event.

        """
        self._report_input_event(handler_name='on_joy_button_up_event', event=event)

    @override
    def on_controller_axis_motion_event(self: Self, event: ControllerAxisEvent) -> None:
        """Report a controller-layer axis motion.

        Args:
            event: The event.

        """
        self._report_input_event(handler_name='on_controller_axis_motion_event', event=event)

    @override
    def on_controller_button_down_event(self: Self, event: ControllerButtonEvent) -> None:
        """Report a controller-layer button press.

        Args:
            event: The event.

        """
        self._report_input_event(handler_name='on_controller_button_down_event', event=event)

    @override
    def on_controller_button_up_event(self: Self, event: ControllerButtonEvent) -> None:
        """Report a controller-layer button release.

        Args:
            event: The event.

        """
        self._report_input_event(handler_name='on_controller_button_up_event', event=event)

    # Device lifecycle events: the engine tracks the devices and reports them through
    # on_input_device_added / on_input_device_removed, so these need nothing more

    @override
    def on_joy_device_added_event(self: Self, event: JoyDeviceAddedEvent) -> None:
        """Nothing to do: see on_input_device_added.

        Args:
            event: The event.

        """

    @override
    def on_joy_device_removed_event(self: Self, event: JoyDeviceRemovedEvent) -> None:
        """Nothing to do: see on_input_device_removed.

        Args:
            event: The event.

        """

    @override
    def on_controller_device_added_event(self: Self, event: ControllerDeviceAddedEvent) -> None:
        """Nothing to do: see on_input_device_added.

        Args:
            event: The event.

        """

    @override
    def on_controller_device_removed_event(self: Self, event: ControllerDeviceEvent) -> None:
        """Nothing to do: see on_input_device_removed.

        Args:
            event: The event.

        """

    @override
    def on_controller_device_remapped_event(self: Self, event: ControllerDeviceEvent) -> None:
        """Nothing to do: the readout follows the device's mapping every frame.

        Args:
            event: The event.

        """


def main() -> None:
    """Run the demo."""
    GameEngine(game=Game).start()
