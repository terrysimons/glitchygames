"""Every connected joystick and game controller as one device, read on one or two layers.

SDL sees a mapped gamepad as one device (one instance id) read on two layers: the raw joystick
layer (axes, buttons and hats by index) and the controller layer (``CONTROLLER_AXIS_*`` /
``CONTROLLER_BUTTON_*`` ids, the same on every mapped pad). A joystick SDL has no mapping for
has the joystick layer only. ``InputDevices`` (engine-owned: ``GameEngine.input_devices``,
``Scene.input_devices``) lists the devices a game sees, by instance id, as ``InputDevice`` objects:

- ``descriptor``: the ``DeviceDescriptor`` the devices door recorded when it opened the device
  (name, GUID, device index, instance id, counts);
- ``joystick``: the joystick layer, always present;
- ``controller``: the controller layer, or None for a device SDL does not map;
- ``event_layer``: the layer whose events reach ``on_*_event`` handlers (below).

Both layers read the frame's input snapshot (glitchygames/input/state.py), never the device, so
live play and a replay answer the same; ``rumble`` goes to the device (a replay's stand-ins drop
it).

Rules:

1. Dispatch: a device's input events reach handlers from one layer only, its ``event_layer``:
   the controller layer when it has one, else the joystick layer (``dispatches``). So each press
   arrives once, as ``on_controller_button_down_event`` from a mapped pad and as
   ``on_joy_button_down_event`` from anything else. Polling either layer always works. Device
   events (added, removed, remapped) are not input events: they always pass.
2. Input mode (``--input-mode``, ``InputMode``) filters what a game sees. ``auto`` (the
   default): every device, mapped pads with their controller layer. ``joystick``: every device,
   on the joystick layer only (the engine blocks controller events at SDL). ``controller``:
   mapped pads only; other devices are hidden and their events dropped.
3. Following the managers: the registry opens nothing. The joystick and controller event
   managers open devices through the devices door, and ``synchronize`` follows what they hold
   (at startup and after every device event), returning the devices added and removed. A
   device is removed once neither manager holds it (a mapped pad's two removal events).
4. A mapped pad arrives twice (JOYDEVICEADDED, then CONTROLLERDEVICEADDED). In ``auto`` mode a
   joystick the controller manager does not hold yet is asked about through the door
   (``is_controller``, recorded like every answer): a mapped one waits for its controller, so
   it is added once, with both layers; an unmapped one is added on the joystick layer.
"""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING, Protocol, Self

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.input.state import current_input
from glitchygames.sources import active_sources

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from glitchygames.input.devices import DeviceDescriptor, OpenedController, OpenedJoystick

LOG = logging.getLogger('game.input.input_devices')
LOG.addHandler(logging.NullHandler())

# The input events each layer dispatches (device events are not input: they always pass)
JOYSTICK_INPUT_EVENT_TYPES: frozenset[int] = frozenset({
    pygame.JOYAXISMOTION,
    pygame.JOYBALLMOTION,
    pygame.JOYHATMOTION,
    pygame.JOYBUTTONDOWN,
    pygame.JOYBUTTONUP,
})
CONTROLLER_INPUT_EVENT_TYPES: frozenset[int] = frozenset({
    pygame.CONTROLLERAXISMOTION,
    pygame.CONTROLLERBUTTONDOWN,
    pygame.CONTROLLERBUTTONUP,
    pygame.CONTROLLERTOUCHPADDOWN,
    pygame.CONTROLLERTOUCHPADMOTION,
    pygame.CONTROLLERTOUCHPADUP,
    pygame.CONTROLLERSENSORUPDATE,
})


class InputMode(enum.StrEnum):
    """Which devices and events a game sees (``--input-mode``; rule 2 of the module docstring)."""

    AUTO = 'auto'
    JOYSTICK = 'joystick'
    CONTROLLER = 'controller'


class DeviceLayer(enum.StrEnum):
    """The two ways SDL reads a device."""

    JOYSTICK = 'joystick'
    CONTROLLER = 'controller'


class InputLayer(Protocol):
    """What both layers offer: every position at once, from the frame's snapshot."""

    @property
    def kind(self) -> DeviceLayer:
        """Which layer this is."""
        ...

    @property
    def axes(self) -> tuple[float, ...]:
        """Every axis position, by index (the controller layer's on pygame's int scale)."""
        ...

    @property
    def buttons(self) -> tuple[bool, ...]:
        """Every button, by index: True when held."""
        ...

    @property
    def hats(self) -> tuple[tuple[int, int], ...]:
        """Every hat position, by index (the controller layer has none)."""
        ...


class JoystickLayer:
    """A device's joystick layer: axes, buttons and hats by SDL joystick index."""

    def __init__(self: Self, *, descriptor: DeviceDescriptor) -> None:
        """Read the device the descriptor describes.

        Args:
            descriptor: The device (its instance id keys the snapshot, its counts the layer).

        """
        self._descriptor = descriptor

    @property
    def kind(self: Self) -> DeviceLayer:
        """DeviceLayer.JOYSTICK."""
        return DeviceLayer.JOYSTICK

    @property
    def axis_count(self: Self) -> int:
        """The number of axes."""
        return self._descriptor.axis_count

    @property
    def button_count(self: Self) -> int:
        """The number of buttons."""
        return self._descriptor.button_count

    @property
    def hat_count(self: Self) -> int:
        """The number of hats."""
        return self._descriptor.hat_count

    @property
    def ball_count(self: Self) -> int:
        """The number of trackballs (their motion arrives only as events)."""
        return self._descriptor.ball_count

    def axis(self: Self, *, axis: int) -> float:
        """Return an axis position (-1.0..1.0); 0.0 for an unknown axis.

        Args:
            axis: The SDL joystick axis index.

        Returns:
            The position this frame.

        """
        return current_input().axis(device_id=self._descriptor.instance_id, axis=axis)

    def button(self: Self, *, button: int) -> bool:
        """Return whether a button is held; False for an unknown button.

        Args:
            button: The SDL joystick button index.

        Returns:
            True when held this frame.

        """
        return current_input().button(device_id=self._descriptor.instance_id, button=button)

    def hat(self: Self, *, hat: int) -> tuple[int, int]:
        """Return a hat position; (0, 0) for an unknown hat.

        Args:
            hat: The SDL joystick hat index.

        Returns:
            The (x, y) position this frame.

        """
        return current_input().hat(device_id=self._descriptor.instance_id, hat=hat)

    @property
    def axes(self: Self) -> tuple[float, ...]:
        """Every axis position, by index."""
        return tuple(self.axis(axis=axis) for axis in range(self.axis_count))

    @property
    def buttons(self: Self) -> tuple[bool, ...]:
        """Every button, by index."""
        return tuple(self.button(button=button) for button in range(self.button_count))

    @property
    def hats(self: Self) -> tuple[tuple[int, int], ...]:
        """Every hat position, by index."""
        return tuple(self.hat(hat=hat) for hat in range(self.hat_count))


class ControllerLayer:
    """A mapped pad's controller layer: by ``CONTROLLER_AXIS_*`` / ``CONTROLLER_BUTTON_*`` id."""

    # Every id SDL defines is polled (glitchygames/input/devices.py), so every id reads
    axis_count: int = pygame.CONTROLLER_AXIS_MAX
    button_count: int = pygame.CONTROLLER_BUTTON_MAX

    def __init__(self: Self, *, instance_id: int) -> None:
        """Read the mapped pad with this instance id.

        Args:
            instance_id: The SDL instance id (it keys the snapshot).

        """
        self._instance_id = instance_id

    @property
    def kind(self: Self) -> DeviceLayer:
        """DeviceLayer.CONTROLLER."""
        return DeviceLayer.CONTROLLER

    def axis(self: Self, *, axis: int) -> int:
        """Return an axis value on pygame's int scale (-32768..32767; triggers 0..32767).

        Args:
            axis: A pygame.CONTROLLER_AXIS_* id.

        Returns:
            The value this frame; 0 for an unknown axis.

        """
        return current_input().controller_axis(device_id=self._instance_id, axis=axis)

    def button(self: Self, *, button: int) -> bool:
        """Return whether a button is held.

        Args:
            button: A pygame.CONTROLLER_BUTTON_* id.

        Returns:
            True when held this frame; False for an unknown button.

        """
        return current_input().controller_button(device_id=self._instance_id, button=button)

    @property
    def axes(self: Self) -> tuple[int, ...]:
        """Every axis value, by CONTROLLER_AXIS_* id."""
        return tuple(self.axis(axis=axis) for axis in range(self.axis_count))

    @property
    def buttons(self: Self) -> tuple[bool, ...]:
        """Every button, by CONTROLLER_BUTTON_* id."""
        return tuple(self.button(button=button) for button in range(self.button_count))

    @property
    def hats(self: Self) -> tuple[tuple[int, int], ...]:
        """None: the controller layer reads the d-pad as buttons."""
        return ()


class InputDevice(Protocol):
    """One connected joystick or game controller, as a game reads it."""

    @property
    def descriptor(self) -> DeviceDescriptor:
        """What the devices door recorded about the device when it opened it."""
        ...

    @property
    def instance_id(self) -> int:
        """The SDL instance id every event of the device carries."""
        ...

    @property
    def name(self) -> str:
        """The device's name."""
        ...

    @property
    def joystick(self) -> JoystickLayer:
        """The joystick layer (always present)."""
        ...

    @property
    def controller(self) -> ControllerLayer | None:
        """The controller layer, or None when SDL does not map the device (or in joystick mode)."""
        ...

    @property
    def event_layer(self) -> InputLayer:
        """The layer whose events reach ``on_*_event`` handlers (the controller layer if any)."""
        ...

    def rumble(
        self, *, low_frequency: float, high_frequency: float, duration_milliseconds: int
    ) -> bool:
        """Start the device's rumble motors; True when the device accepted it."""
        ...

    def stop_rumble(self) -> None:
        """Stop the device's rumble motors."""
        ...


class ConnectedInputDevice:
    """The one ``InputDevice`` class, live and in replays (the door's devices or stand-ins)."""

    def __init__(
        self: Self,
        *,
        descriptor: DeviceDescriptor,
        joystick: OpenedJoystick,
        controller: OpenedController | None,
    ) -> None:
        """Wrap a device the managers opened through the devices door.

        Args:
            descriptor: The door's descriptor of the device.
            joystick: The opened device's joystick view (rumbled when it has no controller).
            controller: The opened game controller, or None for the joystick layer only.

        """
        self._descriptor = descriptor
        self._joystick_device = joystick
        self._controller_device = controller
        self._joystick_layer = JoystickLayer(descriptor=descriptor)
        self._controller_layer = (
            None if controller is None else ControllerLayer(instance_id=descriptor.instance_id)
        )

    @property
    def descriptor(self: Self) -> DeviceDescriptor:
        """What the devices door recorded about the device when it opened it."""
        return self._descriptor

    @property
    def instance_id(self: Self) -> int:
        """The SDL instance id every event of the device carries."""
        return self._descriptor.instance_id

    @property
    def name(self: Self) -> str:
        """The device's name."""
        return self._descriptor.name

    @property
    def joystick(self: Self) -> JoystickLayer:
        """The joystick layer (always present)."""
        return self._joystick_layer

    @property
    def controller(self: Self) -> ControllerLayer | None:
        """The controller layer, or None."""
        return self._controller_layer

    @property
    def event_layer(self: Self) -> InputLayer:
        """The layer whose events reach handlers: the controller layer if any, else joystick."""
        if self._controller_layer is not None:
            return self._controller_layer
        return self._joystick_layer

    def attach_controller(self: Self, *, controller: OpenedController) -> None:
        """Give a device added on the joystick layer its controller layer (a late mapping).

        Args:
            controller: The opened game controller.

        """
        self._controller_device = controller
        self._controller_layer = ControllerLayer(instance_id=self._descriptor.instance_id)

    def rumble(
        self: Self, *, low_frequency: float, high_frequency: float, duration_milliseconds: int
    ) -> bool:
        """Start the rumble motors, through the controller when the device has one.

        Args:
            low_frequency: Low-frequency motor strength (0.0 to 1.0).
            high_frequency: High-frequency motor strength (0.0 to 1.0).
            duration_milliseconds: How long (0 = until stopped).

        Returns:
            True when the device accepted it; False when it cannot rumble or is gone.

        """
        try:
            if self._controller_device is not None:
                return bool(
                    self._controller_device.rumble(
                        low_frequency, high_frequency, duration_milliseconds
                    )
                )
            return bool(
                self._joystick_device.rumble(low_frequency, high_frequency, duration_milliseconds)
            )
        except pygame.error:
            LOG.debug('Device %d could not rumble', self.instance_id, exc_info=True)
            return False

    def stop_rumble(self: Self) -> None:
        """Stop the rumble motors (a device that is gone is ignored)."""
        try:
            if self._controller_device is not None:
                self._controller_device.stop_rumble()
            else:
                self._joystick_device.stop_rumble()
        except pygame.error:
            LOG.debug('Device %d could not stop rumbling', self.instance_id, exc_info=True)


class InputDeviceChanges(BaseModel):
    """The devices one ``InputDevices.synchronize`` added and removed, in order.

    Attributes:
        added: Devices the game sees from now on.
        removed: Devices the game no longer sees.

    """

    # Devices are live objects, held as they are
    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    added: tuple[ConnectedInputDevice, ...] = ()
    removed: tuple[ConnectedInputDevice, ...] = ()


class InputDevices:
    """The devices a game sees, by instance id (see the module docstring for the rules)."""

    def __init__(self: Self, *, input_mode: InputMode = InputMode.AUTO) -> None:
        """Start with no devices.

        Args:
            input_mode: Which devices and events the game sees (rule 2).

        """
        self._input_mode = input_mode
        self._devices: dict[int, ConnectedInputDevice] = {}

    @property
    def input_mode(self: Self) -> InputMode:
        """Which devices and events the game sees."""
        return self._input_mode

    def __iter__(self: Self) -> Iterator[InputDevice]:
        """Iterate over the devices, in the order they were added.

        Returns:
            The devices.

        """
        return iter(tuple(self._devices.values()))

    def __len__(self: Self) -> int:
        """Return how many devices the game sees.

        Returns:
            The count.

        """
        return len(self._devices)

    def get(self: Self, *, instance_id: int) -> InputDevice | None:
        """Return the device with this instance id, or None.

        Args:
            instance_id: The SDL instance id (every device event carries it).

        Returns:
            The device, or None when the game does not see it.

        """
        return self._devices.get(instance_id)

    def dispatches(self: Self, *, event_type: int, instance_id: int | None) -> bool:
        """Return whether an event of this device reaches the game's handlers (rules 1 and 2).

        Args:
            event_type: The pygame event type.
            instance_id: The event's instance id (None when it has none: an input event
                without one names no device the game sees).

        Returns:
            True for a device event (not an input event), and for an input event from the
            layer the device dispatches; False for the other layer's events and for the events
            of devices the game does not see.

        """
        if event_type in JOYSTICK_INPUT_EVENT_TYPES:
            dispatching_layer = DeviceLayer.JOYSTICK
        elif event_type in CONTROLLER_INPUT_EVENT_TYPES:
            dispatching_layer = DeviceLayer.CONTROLLER
        else:
            return True
        device = None if instance_id is None else self._devices.get(instance_id)
        return device is not None and device.event_layer.kind is dispatching_layer

    def synchronize(
        self: Self,
        *,
        joysticks: Mapping[int, OpenedJoystick],
        controllers: Mapping[int, OpenedController],
    ) -> InputDeviceChanges:
        """Follow the devices the joystick and controller managers hold (rules 2-4).

        Args:
            joysticks: The joystick manager's opened joysticks, by instance id.
            controllers: The controller manager's opened controllers, by instance id (empty in
                joystick mode, which has no controller manager).

        Returns:
            The devices added and removed.

        """
        if self._input_mode is InputMode.JOYSTICK:
            controllers = {}
        removed = [
            self._devices.pop(instance_id)
            for instance_id in tuple(self._devices)
            if instance_id not in joysticks and instance_id not in controllers
        ]
        added: list[ConnectedInputDevice] = []
        for instance_id, controller in controllers.items():
            known = self._devices.get(instance_id)
            if known is None:
                device = self._new_device(
                    instance_id=instance_id,
                    joystick=controller.as_joystick(),
                    controller=controller,
                )
                if device is not None:
                    added.append(device)
            elif known.controller is None:
                # Added on the joystick layer before SDL mapped it: from now on it dispatches
                # its controller events
                known.attach_controller(controller=controller)
        if self._input_mode is not InputMode.CONTROLLER:
            for instance_id, joystick in joysticks.items():
                if instance_id in self._devices or self._waits_for_its_controller(
                    instance_id=instance_id
                ):
                    continue
                device = self._new_device(
                    instance_id=instance_id, joystick=joystick, controller=None
                )
                if device is not None:
                    added.append(device)
        return InputDeviceChanges(added=tuple(added), removed=tuple(removed))

    def _waits_for_its_controller(self: Self, *, instance_id: int) -> bool:
        """Return whether a joystick is a mapped pad whose controller is not open yet (rule 4).

        Returns:
            True in auto mode for a device the door says is a game controller.

        """
        if self._input_mode is not InputMode.AUTO:
            return False
        devices = active_sources().devices()
        descriptor = devices.descriptor_for_instance(instance_id=instance_id)
        if descriptor is None:
            return False
        try:
            return devices.is_controller(device_index=descriptor.device_index)
        except pygame.error:
            # Gone, or SDL cannot say: it is read as the joystick it was opened as
            LOG.debug('Device %d: is_controller failed', instance_id, exc_info=True)
            return False

    def _new_device(
        self: Self,
        *,
        instance_id: int,
        joystick: OpenedJoystick,
        controller: OpenedController | None,
    ) -> ConnectedInputDevice | None:
        """Add a device the managers opened.

        Returns:
            The device, or None when the door has no descriptor of it (it was not opened
            through the door; logged).

        """
        descriptor = active_sources().devices().descriptor_for_instance(instance_id=instance_id)
        if descriptor is None:
            LOG.warning('Device %d was not opened through the devices door; ignored', instance_id)
            return None
        device = ConnectedInputDevice(
            descriptor=descriptor, joystick=joystick, controller=controller
        )
        self._devices[instance_id] = device
        return device
