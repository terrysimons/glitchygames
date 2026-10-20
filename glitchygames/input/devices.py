"""The devices door: joysticks and controllers are enumerated and opened only here.

Live play enumerates and opens real pygame devices (``LiveDeviceRegistry``), remembering every
enumeration answer (failures included) and a descriptor of each opened device for the recorder,
and polls the opened devices once per frame for the input snapshot (glitchygames/input/state.py).
A replay answers with stand-ins built from those descriptors (``ReplayJoystick``,
``ReplayController``), whose positions come from the frame's snapshot and whose rumble is
accepted and dropped, and answers enumeration calls from the recorded answers. So a replay never
needs the recorded hardware and never sees a device that happens to be plugged in.

A game controller is read on two layers, both polled every frame: its joystick view
(``Controller.as_joystick()``: float axes, buttons and hats by SDL joystick index, in the
snapshot's ``device_*`` fields) and the controller layer (``Controller.get_axis`` /
``get_button`` by ``pygame.CONTROLLER_AXIS_*`` / ``CONTROLLER_BUTTON_*`` id, axes on pygame's
int scale, in the snapshot's ``controller_*`` fields). Each stand-in reads the layer its live
counterpart reads, so live and replay answer the same.
"""

from __future__ import annotations

import collections
import dataclasses
import logging
from typing import TYPE_CHECKING, Any, Protocol, Self

import pygame
import pygame._sdl2.controller

from glitchygames.input.state import (
    ControllerAxes,
    ControllerButtons,
    DeviceAxes,
    DeviceButtons,
    DeviceHats,
    current_input,
)

if TYPE_CHECKING:
    from collections.abc import Callable

LOG = logging.getLogger('game.input.devices')
LOG.addHandler(logging.NullHandler())

JOYSTICK_KIND = 'joystick'
CONTROLLER_KIND = 'controller'
JOYSTICK_COUNT_CALL = 'joystick_count'
CONTROLLER_COUNT_CALL = 'controller_count'
IS_CONTROLLER_CALL = 'is_controller'
NAME_FOR_INDEX_CALL = 'name_for_index'
# Opens are answers too: the instance id on success, the error when the device was gone
OPEN_JOYSTICK_CALL = 'open_joystick'
OPEN_CONTROLLER_CALL = 'open_controller'

type EnumerationValue = int | bool | str | None


@dataclasses.dataclass(frozen=True)
class DeviceDescriptor:
    """What a recording knows about a device it saw opened.

    Attributes:
        kind: JOYSTICK_KIND or CONTROLLER_KIND.
        device_index: The SDL device index it was opened with.
        instance_id: The SDL instance id its events carry.
        name: The device name.
        guid: The device GUID (None when the device could not say).
        axis_count: Number of axes.
        button_count: Number of buttons.
        hat_count: Number of hats.
        ball_count: Number of trackballs.

    """

    kind: str
    device_index: int
    instance_id: int
    name: str
    guid: str | None
    axis_count: int
    button_count: int
    hat_count: int
    ball_count: int

    def to_json(self: Self) -> dict[str, Any]:
        """Return the descriptor as a JSON-safe dict.

        Returns:
            The fields by name.

        """
        return dataclasses.asdict(self)

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> DeviceDescriptor:
        """Read a descriptor written by ``to_json``.

        Args:
            record: The dict ``to_json`` wrote.

        Returns:
            The descriptor.

        """
        return cls(**record)


@dataclasses.dataclass(frozen=True)
class EnumerationAnswer:
    """One answered enumeration or open call (recorded so a replay gives the same answer).

    Attributes:
        call: One of the ``*_CALL`` constants.
        device_index: The device index asked about (None for the counts).
        value: The answer given (an open's is the opened instance id).
        error: The pygame.error message when the call raised (``value`` is None then).

    """

    call: str
    device_index: int | None
    value: EnumerationValue
    error: str | None = None

    def to_json(self: Self) -> dict[str, Any]:
        """Return the answer as a JSON-safe dict.

        Returns:
            The fields by name.

        """
        return dataclasses.asdict(self)

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> EnumerationAnswer:
        """Read an answer written by ``to_json``.

        Args:
            record: The dict ``to_json`` wrote.

        Returns:
            The answer.

        """
        return cls(**record)


@dataclasses.dataclass(frozen=True)
class PolledDevices:
    """One frame's positions of every opened device, by instance id (the snapshot's fields).

    Attributes:
        axes: Joystick-layer axes.
        buttons: Joystick-layer buttons.
        hats: Joystick-layer hats.
        controller_axes: Controller-layer axes (game controllers only).
        controller_buttons: Controller-layer buttons (game controllers only).

    """

    axes: DeviceAxes
    buttons: DeviceButtons
    hats: DeviceHats
    controller_axes: ControllerAxes
    controller_buttons: ControllerButtons


class DeviceRegistry(Protocol):
    """Enumerates and opens devices for the engine and games (see the module docstring)."""

    def joystick_count(self) -> int:
        """Return how many joysticks there are."""
        ...

    def controller_count(self) -> int:
        """Return how many game controllers there are."""
        ...

    def is_controller(self, *, device_index: int) -> bool:
        """Return whether the device at ``device_index`` is a game controller.

        Args:
            device_index: The SDL device index.

        """
        ...

    def name_for_index(self, *, device_index: int) -> str | None:
        """Return the controller name at ``device_index`` (None when there is none).

        Args:
            device_index: The SDL device index.

        """
        ...

    def open_joystick(self, *, device_index: int) -> Any:
        """Open the joystick at ``device_index``.

        Args:
            device_index: The SDL device index.

        """
        ...

    def open_controller(self, *, device_index: int) -> Any:
        """Open the game controller at ``device_index``.

        Args:
            device_index: The SDL device index.

        """
        ...

    def joystick_for_instance(self, *, instance_id: int) -> Any | None:
        """Return an opened device's joystick view by instance id, or None.

        Args:
            instance_id: The SDL instance id.

        """
        ...

    def take_opened_descriptors(self) -> list[DeviceDescriptor]:
        """Return the descriptors of devices opened since the last call (the recorder's)."""
        ...

    def take_enumeration_answers(self) -> list[EnumerationAnswer]:
        """Return the enumeration answers given since the last call (the recorder's)."""
        ...


def _describe(*, kind: str, device_index: int, device: Any) -> DeviceDescriptor:
    """Return the descriptor of an opened device (its joystick view).

    Returns:
        The descriptor.

    """
    try:
        guid = device.get_guid()
    except AttributeError:
        guid = None
    return DeviceDescriptor(
        kind=kind,
        device_index=device_index,
        instance_id=int(device.get_instance_id()),
        name=str(device.get_name()),
        guid=guid,
        axis_count=int(device.get_numaxes()),
        button_count=int(device.get_numbuttons()),
        hat_count=int(device.get_numhats()),
        ball_count=int(device.get_numballs()),
    )


def _poll_joystick_layer(
    *, device: Any
) -> tuple[tuple[float, ...], tuple[bool, ...], tuple[tuple[int, int], ...]]:
    """Read a device's joystick-layer axes, buttons and hats.

    Returns:
        Axes, buttons and hats.

    """
    axes = tuple(float(device.get_axis(index)) for index in range(device.get_numaxes()))
    buttons = tuple(bool(device.get_button(index)) for index in range(device.get_numbuttons()))
    hats = tuple(
        (int(hat_x), int(hat_y))
        for hat_x, hat_y in (device.get_hat(index) for index in range(device.get_numhats()))
    )
    return axes, buttons, hats


def _poll_controller_layer(*, controller: Any) -> tuple[tuple[int, ...], tuple[bool, ...]]:
    """Read a game controller's axes and buttons by every CONTROLLER_AXIS_*/BUTTON_* id.

    Returns:
        Axes (pygame's int scale) and buttons.

    """
    axes = tuple(int(controller.get_axis(axis)) for axis in range(pygame.CONTROLLER_AXIS_MAX))
    buttons = tuple(
        bool(controller.get_button(button)) for button in range(pygame.CONTROLLER_BUTTON_MAX)
    )
    return axes, buttons


class LiveDeviceRegistry:
    """Enumerates and opens real devices, remembers them, and polls them for the snapshot."""

    def __init__(self: Self) -> None:
        """Start with no devices opened and nothing asked."""
        # Joystick views by instance id (a controller's is its as_joystick())
        self._devices_by_instance: dict[int, Any] = {}
        self._controllers_by_instance: dict[int, Any] = {}
        self._new_descriptors: list[DeviceDescriptor] = []
        self._new_answers: list[EnumerationAnswer] = []

    def joystick_count(self: Self) -> int:
        """Return how many joysticks SDL reports (remembered for the recorder).

        Returns:
            The count.

        Raises:
            pygame.error: If SDL cannot answer (remembered too).

        """
        try:
            count = int(pygame.joystick.get_count())
        except pygame.error as error:
            self._remember_failure(call=JOYSTICK_COUNT_CALL, device_index=None, error=error)
            raise
        self._remember_answer(call=JOYSTICK_COUNT_CALL, device_index=None, value=count)
        return count

    def controller_count(self: Self) -> int:
        """Return how many game controllers SDL reports (remembered for the recorder).

        Returns:
            The count.

        Raises:
            pygame.error: If SDL cannot answer (remembered too).

        """
        try:
            count = int(pygame._sdl2.controller.get_count())
        except pygame.error as error:
            self._remember_failure(call=CONTROLLER_COUNT_CALL, device_index=None, error=error)
            raise
        self._remember_answer(call=CONTROLLER_COUNT_CALL, device_index=None, value=count)
        return count

    def is_controller(self: Self, *, device_index: int) -> bool:
        """Return whether the device at ``device_index`` is a game controller.

        Args:
            device_index: The SDL device index.

        Returns:
            True for a game controller.

        Raises:
            pygame.error: If SDL cannot answer (remembered too).

        """
        try:
            flag = bool(pygame._sdl2.controller.is_controller(device_index))
        except pygame.error as error:
            self._remember_failure(call=IS_CONTROLLER_CALL, device_index=device_index, error=error)
            raise
        self._remember_answer(call=IS_CONTROLLER_CALL, device_index=device_index, value=flag)
        return flag

    def name_for_index(self: Self, *, device_index: int) -> str | None:
        """Return the controller name at ``device_index`` (None when SDL has none).

        pygame-ce (2.5.8 at least) has no ``pygame._sdl2.controller.name_forindex``, so there
        the answer is always None; it is still remembered, so a replay answers the same.

        Args:
            device_index: The SDL device index.

        Returns:
            The name, or None.

        Raises:
            pygame.error: If SDL cannot answer (remembered too).

        """
        name_lookup: Callable[[int], object] | None = getattr(
            pygame._sdl2.controller, 'name_forindex', None
        )
        try:
            sdl_name = None if name_lookup is None else name_lookup(device_index)
        except pygame.error as error:
            self._remember_failure(call=NAME_FOR_INDEX_CALL, device_index=device_index, error=error)
            raise
        name = None if sdl_name is None else str(sdl_name)
        self._remember_answer(call=NAME_FOR_INDEX_CALL, device_index=device_index, value=name)
        return name

    def open_joystick(self: Self, *, device_index: int) -> Any:
        """Open the joystick at ``device_index`` and remember it.

        Args:
            device_index: The SDL device index.

        Returns:
            The pygame joystick.

        Raises:
            pygame.error: If the device is gone (unplugged since it was counted; remembered).

        """
        try:
            joystick = pygame.joystick.Joystick(device_index)
            descriptor = _describe(kind=JOYSTICK_KIND, device_index=device_index, device=joystick)
        except pygame.error as error:
            self._remember_failure(call=OPEN_JOYSTICK_CALL, device_index=device_index, error=error)
            raise
        self._remember_opened(
            call=OPEN_JOYSTICK_CALL, descriptor=descriptor, joystick_view=joystick, controller=None
        )
        return joystick

    def open_controller(self: Self, *, device_index: int) -> Any:
        """Open the game controller at ``device_index`` and remember it.

        Its joystick view is described and polled on the joystick layer, and the controller
        itself on the controller layer (see the module docstring).

        Args:
            device_index: The SDL device index.

        Returns:
            The pygame controller.

        Raises:
            pygame.error: If the device is gone (unplugged since it was counted; remembered).

        """
        try:
            controller = pygame._sdl2.controller.Controller(device_index)
            joystick_view = controller.as_joystick()
            descriptor = _describe(
                kind=CONTROLLER_KIND, device_index=device_index, device=joystick_view
            )
        except pygame.error as error:
            self._remember_failure(
                call=OPEN_CONTROLLER_CALL, device_index=device_index, error=error
            )
            raise
        self._remember_opened(
            call=OPEN_CONTROLLER_CALL,
            descriptor=descriptor,
            joystick_view=joystick_view,
            controller=controller,
        )
        return controller

    def joystick_for_instance(self: Self, *, instance_id: int) -> Any | None:
        """Return an opened device's joystick view by instance id, or None.

        Args:
            instance_id: The SDL instance id.

        Returns:
            The joystick (a controller's joystick view), or None.

        """
        return self._devices_by_instance.get(instance_id)

    def take_opened_descriptors(self: Self) -> list[DeviceDescriptor]:
        """Return the descriptors of devices opened since the last call (the recorder's).

        Returns:
            The descriptors, in opening order.

        """
        descriptors, self._new_descriptors = self._new_descriptors, []
        return descriptors

    def take_enumeration_answers(self: Self) -> list[EnumerationAnswer]:
        """Return the enumeration answers given since the last call (the recorder's).

        Returns:
            The answers, in the order given.

        """
        answers, self._new_answers = self._new_answers, []
        return answers

    def poll(self: Self) -> PolledDevices:
        """Read every opened device on both layers (once per frame, at the pump).

        Returns:
            The positions by instance id.

        """
        axes: dict[int, tuple[float, ...]] = {}
        buttons: dict[int, tuple[bool, ...]] = {}
        hats: dict[int, tuple[tuple[int, int], ...]] = {}
        controller_axes: dict[int, tuple[int, ...]] = {}
        controller_buttons: dict[int, tuple[bool, ...]] = {}
        for instance_id, joystick_view in self._devices_by_instance.items():
            controller = self._controllers_by_instance.get(instance_id)
            try:
                device_axes, device_buttons, device_hats = _poll_joystick_layer(
                    device=joystick_view
                )
                controller_layer = (
                    None if controller is None else _poll_controller_layer(controller=controller)
                )
            except pygame.error:
                # Unplugged since it was opened: it reads as absent this frame (every
                # mapping, so a device is never half present)
                LOG.debug('Device %d vanished while polling', instance_id, exc_info=True)
                continue
            axes[instance_id] = device_axes
            buttons[instance_id] = device_buttons
            hats[instance_id] = device_hats
            if controller_layer is not None:
                controller_axes[instance_id], controller_buttons[instance_id] = controller_layer
        return PolledDevices(
            axes=axes,
            buttons=buttons,
            hats=hats,
            controller_axes=controller_axes,
            controller_buttons=controller_buttons,
        )

    def _remember_answer(
        self: Self, *, call: str, device_index: int | None, value: EnumerationValue
    ) -> None:
        self._new_answers.append(
            EnumerationAnswer(call=call, device_index=device_index, value=value)
        )

    def _remember_failure(
        self: Self, *, call: str, device_index: int | None, error: pygame.error
    ) -> None:
        self._new_answers.append(
            EnumerationAnswer(call=call, device_index=device_index, value=None, error=str(error))
        )

    def _remember_opened(
        self: Self,
        *,
        call: str,
        descriptor: DeviceDescriptor,
        joystick_view: Any,
        controller: Any | None,
    ) -> None:
        self._devices_by_instance[descriptor.instance_id] = joystick_view
        if controller is not None:
            self._controllers_by_instance[descriptor.instance_id] = controller
        self._new_descriptors.append(descriptor)
        self._remember_answer(
            call=call, device_index=descriptor.device_index, value=descriptor.instance_id
        )


class ReplayJoystick:
    """A recorded joystick: answers from its descriptor and the frame's input snapshot.

    A drop-in for pygame.joystick.JoystickType: its methods keep pygame's positional signatures
    (interface conformance), unlike the engine's keyword-only API. Positions come from the
    snapshot's joystick layer (``device_*`` fields).
    """

    def __init__(self: Self, *, descriptor: DeviceDescriptor) -> None:
        """Create the stand-in.

        Args:
            descriptor: The recorded device.

        """
        self._descriptor = descriptor
        self._initialized = False

    def init(self: Self) -> None:
        """Mark initialized (no hardware)."""
        self._initialized = True

    def quit(self: Self) -> None:
        """Mark uninitialized."""
        self._initialized = False

    def get_init(self: Self) -> bool:
        """Return whether init() was called.

        Returns:
            True after init().

        """
        return self._initialized

    def get_instance_id(self: Self) -> int:
        """Return the recorded instance id.

        Returns:
            The instance id.

        """
        return self._descriptor.instance_id

    def get_id(self: Self) -> int:
        """Return the recorded device index.

        Returns:
            The device index.

        """
        return self._descriptor.device_index

    def get_name(self: Self) -> str:
        """Return the recorded name.

        Returns:
            The name.

        """
        return self._descriptor.name

    def get_guid(self: Self) -> str | None:
        """Return the recorded GUID.

        Returns:
            The GUID, or None.

        """
        return self._descriptor.guid

    def get_power_level(self: Self) -> str:
        """Stand-ins have no battery.

        Returns:
            'unknown'.

        """
        return 'unknown'

    def get_numaxes(self: Self) -> int:
        """Return the recorded axis count.

        Returns:
            The count.

        """
        return self._descriptor.axis_count

    def get_numbuttons(self: Self) -> int:
        """Return the recorded button count.

        Returns:
            The count.

        """
        return self._descriptor.button_count

    def get_numhats(self: Self) -> int:
        """Return the recorded hat count.

        Returns:
            The count.

        """
        return self._descriptor.hat_count

    def get_numballs(self: Self) -> int:
        """Return the recorded ball count.

        Returns:
            The count.

        """
        return self._descriptor.ball_count

    def get_axis(self: Self, axis: int) -> float:
        """Return the axis position from the frame's snapshot (positional: pygame's signature).

        Args:
            axis: The SDL joystick axis index.

        Returns:
            The position.

        """
        return current_input().axis(device_id=self._descriptor.instance_id, axis=axis)

    def get_button(self: Self, button: int) -> bool:
        """Return the button state from the frame's snapshot (positional: pygame's signature).

        Args:
            button: The SDL joystick button index.

        Returns:
            True when held.

        """
        return current_input().button(device_id=self._descriptor.instance_id, button=button)

    def get_hat(self: Self, hat: int) -> tuple[int, int]:
        """Return the hat position from the frame's snapshot (positional: pygame's signature).

        Args:
            hat: The SDL joystick hat index.

        Returns:
            The hat position.

        """
        return current_input().hat(device_id=self._descriptor.instance_id, hat=hat)

    def get_ball(self: Self, ball: int) -> tuple[int, int]:
        """Balls are not recorded; they read as still (positional: pygame's signature).

        Args:
            ball: The SDL joystick ball index (ignored).

        Returns:
            (0, 0).

        """
        del ball
        return (0, 0)

    def rumble(self: Self, low_frequency: float, high_frequency: float, duration: int) -> bool:
        """Accept and drop a rumble request (positional: pygame's signature; no hardware).

        Args:
            low_frequency: Low-frequency motor strength (ignored).
            high_frequency: High-frequency motor strength (ignored).
            duration: Milliseconds (ignored).

        Returns:
            True, as pygame does for an accepted request.

        """
        del low_frequency, high_frequency, duration
        return True

    def stop_rumble(self: Self) -> None:
        """Nothing to stop."""

    def set_led(self: Self, color: Any, /) -> bool:
        """Ignore an LED colour (positional-only: pygame's signature; no hardware).

        Args:
            color: The colour (ignored).

        Returns:
            False, as pygame does for a device without an LED.

        """
        del color
        return False


class ReplayController:
    """A recorded game controller: the pygame._sdl2.controller.Controller surface the engine uses.

    A drop-in for pygame's Controller: its methods keep pygame's positional signatures
    (interface conformance). ``get_axis`` / ``get_button`` read the snapshot's controller layer
    (``controller_*`` fields, by CONTROLLER_AXIS_* / CONTROLLER_BUTTON_* id, axes on pygame's
    int scale); ``as_joystick()`` is the joystick-layer view.
    """

    def __init__(self: Self, *, descriptor: DeviceDescriptor) -> None:
        """Create the stand-in and its joystick view.

        Args:
            descriptor: The recorded device.

        """
        self._descriptor = descriptor
        self._joystick_view = ReplayJoystick(descriptor=descriptor)
        self._initialized = False

    def init(self: Self) -> None:
        """Mark initialized (no hardware)."""
        self._initialized = True

    def quit(self: Self) -> None:
        """Mark uninitialized."""
        self._initialized = False

    def get_init(self: Self) -> bool:
        """Return whether init() was called.

        Returns:
            True after init().

        """
        return self._initialized

    @property
    def name(self: Self) -> str:
        """The recorded name."""
        return self._descriptor.name

    @property
    def id(self: Self) -> int:
        """The recorded device index (pygame's ``Controller.id``)."""
        return self._descriptor.device_index

    def attached(self: Self) -> bool:
        """A recorded controller counts as attached.

        Returns:
            True.

        """
        return True

    def as_joystick(self: Self) -> ReplayJoystick:
        """Return the joystick view of the same device (always the same object).

        Returns:
            The joystick stand-in.

        """
        return self._joystick_view

    def get_axis(self: Self, axis: int) -> int:
        """Return a controller axis from the frame's snapshot (positional: pygame's signature).

        Args:
            axis: A pygame.CONTROLLER_AXIS_* id.

        Returns:
            The value on pygame's int scale.

        """
        return current_input().controller_axis(device_id=self._descriptor.instance_id, axis=axis)

    def get_button(self: Self, button: int) -> bool:
        """Return a controller button from the frame's snapshot (positional: pygame's signature).

        Args:
            button: A pygame.CONTROLLER_BUTTON_* id.

        Returns:
            True when held.

        """
        return current_input().controller_button(
            device_id=self._descriptor.instance_id, button=button
        )

    def get_mapping(self: Self) -> dict[str, str]:
        """Stand-ins have the default mapping.

        Returns:
            An empty mapping.

        """
        return {}

    def rumble(self: Self, low_frequency: float, high_frequency: float, duration: int) -> bool:
        """Accept and drop a rumble request (positional: pygame's signature; no hardware).

        Args:
            low_frequency: Low-frequency motor strength (ignored).
            high_frequency: High-frequency motor strength (ignored).
            duration: Milliseconds (ignored).

        Returns:
            True, as pygame does for an accepted request.

        """
        del low_frequency, high_frequency, duration
        return True

    def stop_rumble(self: Self) -> None:
        """Nothing to stop."""

    def set_led(self: Self, color: Any, /) -> bool:
        """Ignore an LED colour (positional-only: pygame's signature; no hardware).

        Args:
            color: The colour (ignored).

        Returns:
            False, as pygame does for a device without an LED.

        """
        del color
        return False


class ReplayDeviceRegistry:
    """Stand-ins and recorded enumeration answers (glitchygames/replay/driver.py builds it)."""

    def __init__(
        self: Self,
        *,
        descriptors: list[DeviceDescriptor],
        enumeration_answers: list[EnumerationAnswer],
    ) -> None:
        """Index the recorded descriptors and queue the recorded answers by call.

        Args:
            descriptors: Devices the recording opened before it started (header).
            enumeration_answers: Answers the recording gave before it started (header).

        """
        # In recording order; a device index can recur (a device unplugged and another plugged
        # in), so descriptors are never keyed by index alone
        self._descriptors: list[DeviceDescriptor] = []
        self._descriptors_by_instance: dict[int, DeviceDescriptor] = {}
        self._opened_instances: set[int] = set()
        self._opened_by_instance: dict[int, ReplayJoystick] = {}
        self._answers: dict[tuple[str, int | None], collections.deque[EnumerationAnswer]] = {}
        self._last_answers: dict[tuple[str, int | None], EnumerationAnswer] = {}
        self._learned_descriptors: list[DeviceDescriptor] = []
        self._warned_keys: set[tuple[str, int | None]] = set()
        self._index_descriptors(descriptors=descriptors)
        self.add_enumeration_answers(answers=enumeration_answers)

    def add_descriptors(self: Self, *, descriptors: list[DeviceDescriptor]) -> None:
        """Learn devices the recording opened later (``devices_opened`` frame fields).

        Args:
            descriptors: The frame's opened devices, in order.

        """
        self._index_descriptors(descriptors=descriptors)
        self._learned_descriptors.extend(descriptors)

    def add_enumeration_answers(self: Self, *, answers: list[EnumerationAnswer]) -> None:
        """Queue answers the recording gave later (``device_enumeration`` frame fields).

        Args:
            answers: The frame's answers, in order.

        """
        for answer in answers:
            self._answers.setdefault(
                (answer.call, answer.device_index), collections.deque()
            ).append(answer)

    def joystick_count(self: Self) -> int:
        """Answer from the recording (else the number of recorded devices).

        Returns:
            The count.

        """
        fallback = len(self._descriptors_by_instance)
        count = self._recorded(call=JOYSTICK_COUNT_CALL, device_index=None, fallback=fallback)
        return count if isinstance(count, int) else fallback

    def controller_count(self: Self) -> int:
        """Answer from the recording (else the number of recorded controllers).

        Returns:
            The count.

        """
        fallback = sum(
            1
            for descriptor in self._descriptors_by_instance.values()
            if descriptor.kind == CONTROLLER_KIND
        )
        count = self._recorded(call=CONTROLLER_COUNT_CALL, device_index=None, fallback=fallback)
        return count if isinstance(count, int) else fallback

    def is_controller(self: Self, *, device_index: int) -> bool:
        """Answer from the recording (else whether the recorded device is a controller).

        Args:
            device_index: The SDL device index.

        Returns:
            True for a game controller.

        """
        descriptor = self._descriptor_for_index(device_index=device_index)
        fallback = descriptor is not None and descriptor.kind == CONTROLLER_KIND
        return bool(
            self._recorded(call=IS_CONTROLLER_CALL, device_index=device_index, fallback=fallback)
        )

    def name_for_index(self: Self, *, device_index: int) -> str | None:
        """Answer from the recording (else the recorded device's name, or None).

        Args:
            device_index: The SDL device index.

        Returns:
            The name, or None.

        """
        descriptor = self._descriptor_for_index(device_index=device_index)
        fallback = None if descriptor is None else descriptor.name
        value = self._recorded(
            call=NAME_FOR_INDEX_CALL, device_index=device_index, fallback=fallback
        )
        return None if value is None else str(value)

    def open_joystick(self: Self, *, device_index: int) -> ReplayJoystick:
        """Return a stand-in for the recorded joystick at ``device_index``.

        Args:
            device_index: The SDL device index.

        Returns:
            The stand-in.

        """
        descriptor = self._descriptor_to_open(
            call=OPEN_JOYSTICK_CALL, device_index=device_index, kind=JOYSTICK_KIND
        )
        joystick = ReplayJoystick(descriptor=descriptor)
        self._opened_by_instance[descriptor.instance_id] = joystick
        return joystick

    def open_controller(self: Self, *, device_index: int) -> ReplayController:
        """Return a stand-in for the recorded controller at ``device_index``.

        Args:
            device_index: The SDL device index.

        Returns:
            The stand-in.

        """
        descriptor = self._descriptor_to_open(
            call=OPEN_CONTROLLER_CALL, device_index=device_index, kind=CONTROLLER_KIND
        )
        controller = ReplayController(descriptor=descriptor)
        # Live play hands back a controller's joystick view by instance id; so does a replay
        self._opened_by_instance[descriptor.instance_id] = controller.as_joystick()
        return controller

    def joystick_for_instance(self: Self, *, instance_id: int) -> ReplayJoystick | None:
        """Return an opened stand-in's joystick view by instance id, or None.

        Args:
            instance_id: The recorded SDL instance id.

        Returns:
            The joystick stand-in (a controller's joystick view), or None.

        """
        return self._opened_by_instance.get(instance_id)

    def take_opened_descriptors(self: Self) -> list[DeviceDescriptor]:
        """Return the descriptors learned from the recording since the last call, once each.

        A recording made over a replay (--rebaseline) writes them in the same frames.

        Returns:
            The descriptors, in the order learned.

        """
        descriptors, self._learned_descriptors = self._learned_descriptors, []
        return descriptors

    def take_enumeration_answers(self: Self) -> list[EnumerationAnswer]:
        """A rebaseline copies answers from the source recording (Task 12), not from here.

        Returns:
            An empty list.

        """
        return []

    def _index_descriptors(self: Self, *, descriptors: list[DeviceDescriptor]) -> None:
        for descriptor in descriptors:
            if any(
                known.device_index == descriptor.device_index
                and known.instance_id != descriptor.instance_id
                for known in self._descriptors
            ):
                LOG.warning(
                    'The recording opened a device at device index %d again (instance %d, %r);'
                    ' keeping both, in order',
                    descriptor.device_index,
                    descriptor.instance_id,
                    descriptor.name,
                )
            self._descriptors.append(descriptor)
            self._descriptors_by_instance[descriptor.instance_id] = descriptor

    def _descriptor_for_index(self: Self, *, device_index: int) -> DeviceDescriptor | None:
        """Return the first recorded device at ``device_index`` not opened yet, else the last.

        Returns:
            The descriptor, or None when the recording has no device there.

        """
        at_index = [
            descriptor
            for descriptor in self._descriptors
            if descriptor.device_index == device_index
        ]
        for descriptor in at_index:
            if descriptor.instance_id not in self._opened_instances:
                return descriptor
        return at_index[-1] if at_index else None

    def _next_answer(
        self: Self, *, call: str, device_index: int | None
    ) -> EnumerationAnswer | None:
        """Return the next recorded answer for the call, the last one once used up, else None.

        Returns:
            The answer, or None when the call was never recorded.

        """
        key = (call, device_index)
        queued = self._answers.get(key)
        if queued:
            self._last_answers[key] = queued.popleft()
        return self._last_answers.get(key)

    def _recorded(
        self: Self, *, call: str, device_index: int | None, fallback: EnumerationValue
    ) -> EnumerationValue:
        """Return the recorded answer, raising a recorded failure again.

        Returns:
            The recorded value, or ``fallback`` (with one warning per call and index).

        Raises:
            pygame.error: If the recorded call raised.

        """
        answer = self._next_answer(call=call, device_index=device_index)
        if answer is not None:
            if answer.error is not None:
                raise pygame.error(answer.error)
            return answer.value
        key = (call, device_index)
        if key not in self._warned_keys:
            self._warned_keys.add(key)
            LOG.warning(
                'Device enumeration %s(%s) is not in the recording; answering %r',
                call,
                device_index,
                fallback,
            )
        return fallback

    def _descriptor_to_open(
        self: Self, *, call: str, device_index: int, kind: str
    ) -> DeviceDescriptor:
        """Return the recorded device an open at ``device_index`` gets, as the recording did.

        Returns:
            The descriptor (a named stand-in's when the recording has no device there).

        Raises:
            pygame.error: If the recorded open failed (the device was gone).

        """
        answer = self._next_answer(call=call, device_index=device_index)
        if answer is not None and answer.error is not None:
            raise pygame.error(answer.error)
        descriptor = None
        if answer is not None and isinstance(answer.value, int):
            descriptor = self._descriptors_by_instance.get(answer.value)
        if descriptor is None:
            descriptor = self._descriptor_for_index(device_index=device_index)
        if descriptor is None:
            LOG.warning('Device %d is not in the recording; using a named stand-in', device_index)
            # A negative instance id never collides with a real SDL instance id
            descriptor = DeviceDescriptor(
                kind=kind,
                device_index=device_index,
                instance_id=-1 - device_index,
                name=f'Unrecorded device {device_index}',
                guid=None,
                axis_count=0,
                button_count=0,
                hat_count=0,
                ball_count=0,
            )
        self._opened_instances.add(descriptor.instance_id)
        return descriptor
