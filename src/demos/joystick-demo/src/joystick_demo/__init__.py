"""Joystick Demo: every connected joystick and game controller, live.

Run it with ``joystick-demo`` or ``python -m joystick_demo`` and plug devices in and out. Each
device the engine sees (``Scene.input_devices``, glitchygames/input/input_devices.py) gets a
column: its name, GUID, instance id and device index (the devices door's descriptor), the layer
its events come from, then that layer's live axes, held buttons and hats. A mapped game pad
shows its controller layer (``CONTROLLER_AXIS_*`` / ``CONTROLLER_BUTTON_*`` ids, axes on
pygame's int scale); any other device its joystick layer. Below the text, gauges: a marker on a
track per axis, a lamp per button (shown while held) and a dot per hat. The readout is drawn
from the frame's input snapshot, so a replay of a recording shows exactly what the recorded run
showed; everything is a sprite (``TextSprite`` lines, solid gauges), and a replay compares
sprites' rects and visibility, never pixels or text, so the values live in the gauges' geometry.

The header names the input mode (``--input-mode``: ``auto`` shows every device, ``joystick``
every device on its joystick layer, ``controller`` only mapped pads), the last device connected
or disconnected, and the last input event and the handler it reached: each press arrives once,
from the device's event layer.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any, Self, cast, override

from glitchygames.color import BLACK, WHITE, YELLOW
from glitchygames.engine import GameEngine
from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import DEFAULT_FONT_NAME
from glitchygames.input.input_devices import DeviceLayer
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite
from glitchygames.ui import TextSprite

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

# The gauges below each device's text. An axis: a marker on a track this many pixels wide, at
# the track's left for -1.0, its middle for 0 and its right for 1.0
AXIS_TRACK_WIDTH = 100
AXIS_TRACK_HEIGHT = 1
AXIS_MARKER_WIDTH = 3
AXIS_MARKER_HEIGHT = 7
# Pixels from one axis's gauge to the next
AXIS_ROW_HEIGHT = AXIS_MARKER_HEIGHT + 2
# A controller-layer axis is on pygame's int scale (-32768..32767; triggers 0..32767)
CONTROLLER_AXIS_FULL_SCALE = 32767
# A button: a lamp, shown while it is held, in rows across the column
BUTTON_LAMP_SIZE = 8
GAUGE_SPACING = 2
BUTTON_LAMPS_PER_ROW = (COLUMN_WIDTH - MARGIN) // (BUTTON_LAMP_SIZE + GAUGE_SPACING)
# A hat: a dot this many pixels from its centre toward each direction held
HAT_STEP = 8
HAT_DOT_SIZE = 5
HAT_AREA_SIZE = 2 * HAT_STEP + HAT_DOT_SIZE


def axis_marker_offset(*, value: float, layer_kind: DeviceLayer) -> int:
    """Return how far along its track an axis's marker sits.

    Args:
        value: The axis value (the joystick layer's -1.0..1.0, the controller layer's int scale).
        layer_kind: The layer the value comes from.

    Returns:
        Pixels from the track's left: 0 for -1.0, AXIS_TRACK_WIDTH for 1.0.

    """
    if layer_kind is DeviceLayer.CONTROLLER:
        value /= CONTROLLER_AXIS_FULL_SCALE
    # The int scale reaches -32768, a little past -1.0
    clamped = min(1.0, max(-1.0, value))
    return round((clamped + 1) / 2 * AXIS_TRACK_WIDTH)


def solid_sprite(
    *,
    width: int,
    height: int,
    color: tuple[int, int, int],
    name: str,
    groups: pygame.sprite.LayeredDirty[Any],
) -> Sprite:
    """Return a solid rectangle sprite, drawn every frame (the demo places it every frame).

    Args:
        width: Its width in pixels.
        height: Its height in pixels.
        color: Its colour.
        name: Its name.
        groups: The sprite group to add it to.

    Returns:
        The sprite.

    """
    sprite = Sprite(x=0, y=0, width=width, height=height, name=name, groups=groups)
    sprite.image.fill(color)
    sprite.dirty = 2
    return sprite


class TextLine(TextSprite):
    """One line of the readout: a TextSprite in the demo's font, exactly as big as its text.

    TextSprite draws the engine's default font centred in a box of fixed size; the readout's
    lines keep the font they were drawn in when they were blitted straight onto the screen,
    starting at their top-left corner, so the demo looks as it did. A replay compares the
    line's rect, so its width follows the text.
    """

    def __init__(
        self: Self,
        *,
        font: pygame.font.Font,
        text: str,
        color: tuple[int, int, int],
        name: str,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Show a line of text (placed with ``place``).

        Args:
            font: The font to draw the text in.
            text: The text.
            color: The text's colour.
            name: The sprite's name.
            groups: The sprite group to add it to.

        """
        # Set before TextSprite's __init__, which draws the text (update_text)
        self.line_font = font
        width, height = font.size(text)
        super().__init__(
            x=0,
            y=0,
            # A sprite is made at least a pixel wide (a device may have an empty name); the
            # drawn text then sets its size
            width=max(width, 1),
            height=height,
            name=name,
            text_color=color,
            text=text,
            groups=groups,
        )

    @override
    def update_text(self: Self, text: str) -> None:
        """Draw the text in the line's font; the sprite takes the text's size.

        Args:
            text: The text.

        """
        self.image = self.line_font.render(text, FontManager.antialias(), self.text_color)
        self.rect.size = self.image.get_size()

    def place(self: Self, *, topleft: tuple[int, int]) -> None:
        """Move the line's top-left corner to ``topleft`` (redrawn only when it moves).

        Args:
            topleft: Where the text starts on the screen.

        """
        if (self.x, self.y) != topleft:
            self.x, self.y = topleft


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


def layer_shape(*, device: InputDevice) -> tuple[DeviceLayer, int, int, int]:
    """Return what a device's column is made from: its event layer's kind and counts.

    Args:
        device: The device.

    Returns:
        The layer's kind and its numbers of axes, buttons and hats.

    """
    layer = device.event_layer
    return (layer.kind, len(layer.axes), len(layer.buttons), len(layer.hats))


class DeviceReadout:
    """One device's column: its lines of text, then gauges for its axes, buttons and hats.

    Every value that matters is in a sprite's geometry (a replay compares sprites' rects and
    visibility, never their pixels or text): an axis is its marker's x, a held button its
    lamp's visibility, a hat its dot's position.
    """

    def __init__(
        self: Self,
        *,
        device: InputDevice,
        font: pygame.font.Font,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Make the device's sprites.

        Args:
            device: The device.
            font: The font of its text.
            groups: The sprite group to add the sprites to.

        """
        instance_id = device.instance_id
        layer = device.event_layer
        # What the sprites were made for: a device's event layer can change after it arrived (a
        # pad SDL maps late moves to its controller layer, InputDevices.synchronize), and then
        # its column must be made again (fits)
        self.layer_shape = layer_shape(device=device)
        self.text_lines = [
            TextLine(
                font=font,
                text=line,
                color=YELLOW if line_number == 0 else WHITE,
                name=f'Device {instance_id} line {line_number}',
                groups=groups,
            )
            for line_number, line in enumerate(device_lines(device))
        ]
        self.axis_tracks = [
            solid_sprite(
                width=AXIS_TRACK_WIDTH,
                height=AXIS_TRACK_HEIGHT,
                color=WHITE,
                name=f'Device {instance_id} axis {axis} track',
                groups=groups,
            )
            for axis in range(len(layer.axes))
        ]
        self.axis_markers = [
            solid_sprite(
                width=AXIS_MARKER_WIDTH,
                height=AXIS_MARKER_HEIGHT,
                color=YELLOW,
                name=f'Device {instance_id} axis {axis} marker',
                groups=groups,
            )
            for axis in range(len(layer.axes))
        ]
        self.button_lamps = [
            solid_sprite(
                width=BUTTON_LAMP_SIZE,
                height=BUTTON_LAMP_SIZE,
                color=YELLOW,
                name=f'Device {instance_id} button {button} lamp',
                groups=groups,
            )
            for button in range(len(layer.buttons))
        ]
        self.hat_dots = [
            solid_sprite(
                width=HAT_DOT_SIZE,
                height=HAT_DOT_SIZE,
                color=YELLOW,
                name=f'Device {instance_id} hat {hat} dot',
                groups=groups,
            )
            for hat in range(len(layer.hats))
        ]

    def fits(self: Self, *, device: InputDevice) -> bool:
        """Return whether the column still fits the device's event layer.

        Args:
            device: The device.

        Returns:
            True when its layer is the kind, with the axis, button and hat counts, the column
            was made for.

        """
        return layer_shape(device=device) == self.layer_shape

    def sprites(self: Self) -> list[Sprite]:
        """Return every sprite of the column.

        Returns:
            The text lines, then the axes' tracks and markers, the lamps and the hats' dots.

        """
        return [
            *self.text_lines,
            *self.axis_tracks,
            *self.axis_markers,
            *self.button_lamps,
            *self.hat_dots,
        ]

    def show(self: Self, *, device: InputDevice, left: int, top: int, line_height: int) -> None:
        """Show the device's readout from this frame's input snapshot, its column at ``left``.

        Args:
            device: The device.
            left: The column's left edge.
            top: Where its first line starts.
            line_height: Pixels from one line to the next.

        """
        layer = device.event_layer
        for line_number, (text_line, line) in enumerate(
            zip(self.text_lines, device_lines(device), strict=True)
        ):
            text_line.text = line
            text_line.place(topleft=(left, top + line_number * line_height))
        gauges_top = top + len(self.text_lines) * line_height + GAUGE_SPACING

        # Inset so a marker at either end stays inside the column
        track_left = left + AXIS_MARKER_WIDTH // 2
        for axis, (track, marker, value) in enumerate(
            zip(self.axis_tracks, self.axis_markers, layer.axes, strict=True)
        ):
            row_top = gauges_top + axis * AXIS_ROW_HEIGHT
            track.rect.topleft = (track_left, row_top + AXIS_MARKER_HEIGHT // 2)
            marker.rect.top = row_top
            marker.rect.centerx = track_left + axis_marker_offset(
                value=value, layer_kind=layer.kind
            )

        lamps_top = gauges_top + len(self.axis_tracks) * AXIS_ROW_HEIGHT + GAUGE_SPACING
        lamp_pitch = BUTTON_LAMP_SIZE + GAUGE_SPACING
        for button, (lamp, held) in enumerate(zip(self.button_lamps, layer.buttons, strict=True)):
            row, place_in_row = divmod(button, BUTTON_LAMPS_PER_ROW)
            lamp.rect.topleft = (left + place_in_row * lamp_pitch, lamps_top + row * lamp_pitch)
            lamp.visible = held

        lamp_rows = math.ceil(len(self.button_lamps) / BUTTON_LAMPS_PER_ROW)
        hats_top = lamps_top + lamp_rows * lamp_pitch + GAUGE_SPACING
        for hat, (dot, (hat_x, hat_y)) in enumerate(zip(self.hat_dots, layer.hats, strict=True)):
            centre_x = left + hat * (HAT_AREA_SIZE + GAUGE_SPACING) + HAT_AREA_SIZE // 2
            centre_y = hats_top + HAT_AREA_SIZE // 2
            dot.rect.center = (centre_x + HAT_STEP * hat_x, centre_y - HAT_STEP * hat_y)

    def kill(self: Self) -> None:
        """Remove every sprite of the column from its groups."""
        for sprite in self.sprites():
            sprite.kill()


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
        # Everything shown is a sprite on black, so a replay compares what the demo shows
        self.background_color = BLACK
        self.header_text = [
            TextLine(
                font=self.font,
                text=line,
                color=WHITE,
                name=f'Header line {line_number}',
                groups=self.all_sprites,
            )
            for line_number, line in enumerate(self.header_lines())
        ]
        # Each device's column, by instance id
        self.device_readouts: dict[int, DeviceReadout] = {}

    @override
    def setup(self: Self) -> None:
        """Make a column for every device already connected (later ones come as they connect)."""
        for device in self.input_devices:
            self._add_readout(device=device)

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
        """Show the header, then one column per device, from this frame's input snapshot.

        Visual only: the sprite group draws them.
        """
        line_height = self.font.get_linesize() + LINE_SPACING
        for line_number, (text_line, line) in enumerate(
            zip(self.header_text, self.header_lines(), strict=True)
        ):
            text_line.text = line
            text_line.place(topleft=(MARGIN, MARGIN + line_number * line_height))
        columns_top = MARGIN + (len(self.header_text) + 1) * line_height
        for column, device in enumerate(self.input_devices):
            if not self.device_readouts[device.instance_id].fits(device=device):
                # Its event layer changed under it (a pad mapped after it arrived)
                self._add_readout(device=device)
            self.device_readouts[device.instance_id].show(
                device=device,
                left=MARGIN + column * COLUMN_WIDTH,
                top=columns_top,
                line_height=line_height,
            )
        super().update()

    def _add_readout(self: Self, *, device: InputDevice) -> None:
        """Make a device's column (replacing any it had).

        Args:
            device: The device.

        """
        self._remove_readout(instance_id=device.instance_id)
        self.device_readouts[device.instance_id] = DeviceReadout(
            device=device, font=self.font, groups=self.all_sprites
        )

    def _remove_readout(self: Self, *, instance_id: int) -> None:
        """Remove a device's column, if it has one.

        Args:
            instance_id: The device's instance id.

        """
        readout = self.device_readouts.pop(instance_id, None)
        if readout is not None:
            readout.kill()

    @override
    def on_input_device_added(self: Self, *, device: InputDevice) -> None:
        """Report a device that was plugged in and make its column.

        Args:
            device: The device.

        """
        self.last_device_change = f'Connected: {device.name}'
        LOG.info('Connected: %s (instance %d)', device.name, device.instance_id)
        self._add_readout(device=device)

    @override
    def on_input_device_removed(self: Self, *, device: InputDevice) -> None:
        """Report a device that was unplugged and remove its column.

        Args:
            device: The device.

        """
        self.last_device_change = f'Disconnected: {device.name}'
        LOG.info('Disconnected: %s (instance %d)', device.name, device.instance_id)
        self._remove_readout(instance_id=device.instance_id)

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
