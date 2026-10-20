"""The devices door: joysticks and controllers are enumerated and opened only here.

Live play enumerates and opens real pygame devices (``LiveDeviceRegistry``), remembering every
enumeration answer and a descriptor of each opened device for the recorder, and polls the opened
devices once per frame for the input snapshot (glitchygames/input/state.py). A replay answers with
stand-ins built from those descriptors (``ReplayJoystick``, ``ReplayController``), whose positions
come from the frame's snapshot and whose rumble is accepted and dropped, and answers enumeration
calls from the recorded answers. So a replay never needs the recorded hardware and never sees a
device that happens to be plugged in.
"""

from __future__ import annotations

import collections
import dataclasses
import logging
from typing import TYPE_CHECKING, Any, Protocol, Self

import pygame
import pygame._sdl2.controller

from glitchygames.input.state import current_input

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.input.state import DeviceAxes, DeviceButtons, DeviceHats

LOG = logging.getLogger('game.input.devices')
LOG.addHandler(logging.NullHandler())

JOYSTICK_KIND = 'joystick'
CONTROLLER_KIND = 'controller'
JOYSTICK_COUNT_CALL = 'joystick_count'
CONTROLLER_COUNT_CALL = 'controller_count'
IS_CONTROLLER_CALL = 'is_controller'
NAME_FOR_INDEX_CALL = 'name_for_index'

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

        Returns:
            The descriptor.

        """
        return cls(**record)


@dataclasses.dataclass(frozen=True)
class EnumerationAnswer:
    """One answered enumeration call (recorded so a replay gives the same answer).

    Attributes:
        call: JOYSTICK_COUNT_CALL, CONTROLLER_COUNT_CALL, IS_CONTROLLER_CALL or
            NAME_FOR_INDEX_CALL.
        device_index: The device index asked about (None for the counts).
        value: The answer given.

    """

    call: str
    device_index: int | None
    value: EnumerationValue

    def to_json(self: Self) -> dict[str, Any]:
        """Return the answer as a JSON-safe dict.

        Returns:
            The fields by name.

        """
        return dataclasses.asdict(self)

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> EnumerationAnswer:
        """Read an answer written by ``to_json``.

        Returns:
            The answer.

        """
        return cls(**record)


class DeviceRegistry(Protocol):
    """Enumerates and opens devices for the engine and games (see the module docstring)."""

    def joystick_count(self) -> int:
        """Return how many joysticks there are."""
        ...

    def controller_count(self) -> int:
        """Return how many game controllers there are."""
        ...

    def is_controller(self, *, device_index: int) -> bool:
        """Return whether the device at ``device_index`` is a game controller."""
        ...

    def name_for_index(self, *, device_index: int) -> str | None:
        """Return the controller name at ``device_index`` (None when there is none)."""
        ...

    def open_joystick(self, *, device_index: int) -> Any:
        """Open the joystick at ``device_index``."""
        ...

    def open_controller(self, *, device_index: int) -> Any:
        """Open the game controller at ``device_index``."""
        ...

    def joystick_for_instance(self, *, instance_id: int) -> Any | None:
        """Return an opened device by instance id, or None."""
        ...

    def take_opened_descriptors(self) -> list[DeviceDescriptor]:
        """Return the descriptors of devices opened since the last call (the recorder's)."""
        ...

    def take_enumeration_answers(self) -> list[EnumerationAnswer]:
        """Return the enumeration answers given since the last call (the recorder's)."""
        ...


class LiveDeviceRegistry:
    """Enumerates and opens real devices, remembers them, and polls them for the snapshot."""

    def __init__(self: Self) -> None:
        """Start with no devices opened and nothing asked."""
        self._devices_by_instance: dict[int, Any] = {}
        self._new_descriptors: list[DeviceDescriptor] = []
        self._new_answers: list[EnumerationAnswer] = []

    def joystick_count(self: Self) -> int:
        """Return how many joysticks SDL reports (remembered for the recorder).

        Returns:
            The count.

        """
        count = int(pygame.joystick.get_count())
        self._remember_answer(call=JOYSTICK_COUNT_CALL, device_index=None, value=count)
        return count

    def controller_count(self: Self) -> int:
        """Return how many game controllers SDL reports (remembered for the recorder).

        Returns:
            The count.

        """
        count = int(pygame._sdl2.controller.get_count())
        self._remember_answer(call=CONTROLLER_COUNT_CALL, device_index=None, value=count)
        return count

    def is_controller(self: Self, *, device_index: int) -> bool:
        """Return whether the device at ``device_index`` is a game controller.

        Returns:
            True for a game controller.

        """
        flag = bool(pygame._sdl2.controller.is_controller(device_index))
        self._remember_answer(call=IS_CONTROLLER_CALL, device_index=device_index, value=flag)
        return flag

    def name_for_index(self: Self, *, device_index: int) -> str | None:
        """Return the controller name at ``device_index`` (None when SDL has none).

        pygame-ce (2.5.8 at least) has no ``pygame._sdl2.controller.name_forindex``, so there
        the answer is always None; it is still remembered, so a replay answers the same.

        Returns:
            The name, or None.

        """
        name_lookup: Callable[[int], object] | None = getattr(
            pygame._sdl2.controller, 'name_forindex', None
        )
        sdl_name = None if name_lookup is None else name_lookup(device_index)
        name = None if sdl_name is None else str(sdl_name)
        self._remember_answer(call=NAME_FOR_INDEX_CALL, device_index=device_index, value=name)
        return name

    def open_joystick(self: Self, *, device_index: int) -> Any:
        """Open the joystick at ``device_index`` and remember it.

        Returns:
            The pygame joystick.

        """
        joystick = pygame.joystick.Joystick(device_index)
        self._remember_device(kind=JOYSTICK_KIND, device_index=device_index, device=joystick)
        return joystick

    def open_controller(self: Self, *, device_index: int) -> Any:
        """Open the game controller at ``device_index`` and remember it.

        Its joystick view is what is remembered and polled (the controller has no instance id
        or counts of its own).

        Returns:
            The pygame controller.

        """
        controller = pygame._sdl2.controller.Controller(device_index)
        self._remember_device(
            kind=CONTROLLER_KIND, device_index=device_index, device=controller.as_joystick()
        )
        return controller

    def joystick_for_instance(self: Self, *, instance_id: int) -> Any | None:
        """Return an opened device by instance id, or None.

        Returns:
            The device (a controller's joystick view), or None.

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

    def poll(self: Self) -> tuple[DeviceAxes, DeviceButtons, DeviceHats]:
        """Read every opened device's axes, buttons and hats (once per frame, at the pump).

        Returns:
            Axes, buttons and hats by instance id.

        """
        axes: dict[int, tuple[float, ...]] = {}
        buttons: dict[int, tuple[bool, ...]] = {}
        hats: dict[int, tuple[tuple[int, int], ...]] = {}
        for instance_id, device in self._devices_by_instance.items():
            try:
                device_axes = tuple(
                    float(device.get_axis(index)) for index in range(device.get_numaxes())
                )
                device_buttons = tuple(
                    bool(device.get_button(index)) for index in range(device.get_numbuttons())
                )
                device_hats = tuple(
                    (int(hat_x), int(hat_y))
                    for hat_x, hat_y in (
                        device.get_hat(index) for index in range(device.get_numhats())
                    )
                )
            except pygame.error:
                # Unplugged since it was opened: it reads as absent this frame (all three
                # mappings, so a device is never half present)
                LOG.debug('Device %d vanished while polling', instance_id, exc_info=True)
                continue
            axes[instance_id] = device_axes
            buttons[instance_id] = device_buttons
            hats[instance_id] = device_hats
        return axes, buttons, hats

    def _remember_answer(
        self: Self, *, call: str, device_index: int | None, value: EnumerationValue
    ) -> None:
        self._new_answers.append(
            EnumerationAnswer(call=call, device_index=device_index, value=value)
        )

    def _remember_device(self: Self, *, kind: str, device_index: int, device: Any) -> None:
        instance_id = int(device.get_instance_id())
        self._devices_by_instance[instance_id] = device
        try:
            guid = device.get_guid()
        except AttributeError:
            guid = None
        self._new_descriptors.append(
            DeviceDescriptor(
                kind=kind,
                device_index=device_index,
                instance_id=instance_id,
                name=str(device.get_name()),
                guid=guid,
                axis_count=int(device.get_numaxes()),
                button_count=int(device.get_numbuttons()),
                hat_count=int(device.get_numhats()),
                ball_count=int(device.get_numballs()),
            )
        )


class ReplayJoystick:
    """A recorded joystick: answers from its descriptor and the frame's input snapshot.

    A drop-in for pygame.joystick.JoystickType: its methods keep pygame's positional signatures
    (interface conformance), unlike the engine's keyword-only API.
    """

    def __init__(self: Self, *, descriptor: DeviceDescriptor) -> None:
        """Create the stand-in."""
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

        Returns:
            The position.

        """
        return current_input().axis(device_id=self._descriptor.instance_id, axis=axis)

    def get_button(self: Self, button: int) -> bool:
        """Return the button state from the frame's snapshot (positional: pygame's signature).

        Returns:
            True when held.

        """
        return current_input().button(device_id=self._descriptor.instance_id, button=button)

    def get_hat(self: Self, hat: int) -> tuple[int, int]:
        """Return the hat position from the frame's snapshot (positional: pygame's signature).

        Returns:
            The hat position.

        """
        return current_input().hat(device_id=self._descriptor.instance_id, hat=hat)

    def get_ball(self: Self, ball: int) -> tuple[int, int]:
        """Balls are not recorded; they read as still (positional: pygame's signature).

        Returns:
            (0, 0).

        """
        del ball
        return (0, 0)

    def rumble(self: Self, low_frequency: float, high_frequency: float, duration: int) -> bool:
        """Accept and drop a rumble request (positional: pygame's signature; no hardware).

        Returns:
            True, as pygame does for an accepted request.

        """
        del low_frequency, high_frequency, duration
        return True

    def stop_rumble(self: Self) -> None:
        """Nothing to stop."""

    def set_led(self: Self, color: Any, /) -> bool:
        """Ignore an LED colour (positional-only: pygame's signature; no hardware).

        Returns:
            False, as pygame does for a device without an LED.

        """
        del color
        return False


class ReplayController(ReplayJoystick):
    """A recorded game controller (the pygame._sdl2.controller.Controller surface used).

    A drop-in for pygame._sdl2.controller.Controller (interface conformance, as ReplayJoystick).
    """

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

    def get_mapping(self: Self) -> dict[str, str]:
        """Stand-ins have the default mapping.

        Returns:
            An empty mapping.

        """
        return {}

    def as_joystick(self: Self) -> ReplayJoystick:
        """Return a joystick view of the same descriptor.

        Returns:
            The joystick stand-in.

        """
        return ReplayJoystick(descriptor=self._descriptor)


class ReplayDeviceRegistry:
    """Stand-ins and recorded enumeration answers (glitchygames/replay/driver.py builds it)."""

    def __init__(
        self: Self,
        *,
        descriptors: list[DeviceDescriptor],
        enumeration_answers: list[EnumerationAnswer],
    ) -> None:
        """Index the recorded descriptors and queue the recorded answers by call."""
        self._descriptors_by_index = {
            descriptor.device_index: descriptor for descriptor in descriptors
        }
        self._opened_by_instance: dict[int, ReplayJoystick] = {}
        self._answers: dict[tuple[str, int | None], collections.deque[EnumerationAnswer]] = {}
        self._last_answers: dict[tuple[str, int | None], EnumerationAnswer] = {}
        self._learned_descriptors: list[DeviceDescriptor] = []
        self._warned_keys: set[tuple[str, int | None]] = set()
        self.add_enumeration_answers(answers=enumeration_answers)

    def add_descriptors(self: Self, *, descriptors: list[DeviceDescriptor]) -> None:
        """Learn devices the recording opened later (``devices_opened`` frame fields)."""
        for descriptor in descriptors:
            self._descriptors_by_index[descriptor.device_index] = descriptor
        self._learned_descriptors.extend(descriptors)

    def add_enumeration_answers(self: Self, *, answers: list[EnumerationAnswer]) -> None:
        """Queue answers the recording gave later (``device_enumeration`` frame fields)."""
        for answer in answers:
            self._answers.setdefault(
                (answer.call, answer.device_index), collections.deque()
            ).append(answer)

    def joystick_count(self: Self) -> int:
        """Answer from the recording (else the recorded device count).

        Returns:
            The count.

        """
        fallback = len(self._descriptors_by_index)
        count = self._recorded(call=JOYSTICK_COUNT_CALL, device_index=None, fallback=fallback)
        return count if isinstance(count, int) else fallback

    def controller_count(self: Self) -> int:
        """Answer from the recording (else the recorded controller count).

        Returns:
            The count.

        """
        fallback = sum(
            1
            for descriptor in self._descriptors_by_index.values()
            if descriptor.kind == CONTROLLER_KIND
        )
        count = self._recorded(call=CONTROLLER_COUNT_CALL, device_index=None, fallback=fallback)
        return count if isinstance(count, int) else fallback

    def is_controller(self: Self, *, device_index: int) -> bool:
        """Answer from the recording (else whether the recorded device is a controller).

        Returns:
            True for a game controller.

        """
        descriptor = self._descriptors_by_index.get(device_index)
        fallback = descriptor is not None and descriptor.kind == CONTROLLER_KIND
        return bool(
            self._recorded(call=IS_CONTROLLER_CALL, device_index=device_index, fallback=fallback)
        )

    def name_for_index(self: Self, *, device_index: int) -> str | None:
        """Answer from the recording (else the recorded device's name, or None).

        Returns:
            The name, or None.

        """
        descriptor = self._descriptors_by_index.get(device_index)
        fallback = None if descriptor is None else descriptor.name
        value = self._recorded(
            call=NAME_FOR_INDEX_CALL, device_index=device_index, fallback=fallback
        )
        return None if value is None else str(value)

    def open_joystick(self: Self, *, device_index: int) -> ReplayJoystick:
        """Return a stand-in for the recorded joystick at ``device_index``.

        Returns:
            The stand-in.

        """
        joystick = ReplayJoystick(
            descriptor=self._descriptor(device_index=device_index, kind=JOYSTICK_KIND)
        )
        self._opened_by_instance[joystick.get_instance_id()] = joystick
        return joystick

    def open_controller(self: Self, *, device_index: int) -> ReplayController:
        """Return a stand-in for the recorded controller at ``device_index``.

        Returns:
            The stand-in.

        """
        controller = ReplayController(
            descriptor=self._descriptor(device_index=device_index, kind=CONTROLLER_KIND)
        )
        self._opened_by_instance[controller.get_instance_id()] = controller
        return controller

    def joystick_for_instance(self: Self, *, instance_id: int) -> ReplayJoystick | None:
        """Return an opened stand-in by instance id, or None.

        Returns:
            The stand-in, or None.

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

    def _recorded(
        self: Self, *, call: str, device_index: int | None, fallback: EnumerationValue
    ) -> EnumerationValue:
        key = (call, device_index)
        queued = self._answers.get(key)
        if queued:
            self._last_answers[key] = queued.popleft()
            return self._last_answers[key].value
        if key in self._last_answers:
            # A count asked every frame stays at its last recorded answer
            return self._last_answers[key].value
        if key not in self._warned_keys:
            self._warned_keys.add(key)
            LOG.warning(
                'Device enumeration %s(%s) is not in the recording; answering %r',
                call,
                device_index,
                fallback,
            )
        return fallback

    def _descriptor(self: Self, *, device_index: int, kind: str) -> DeviceDescriptor:
        descriptor = self._descriptors_by_index.get(device_index)
        if descriptor is not None:
            return descriptor
        LOG.warning('Device %d is not in the recording; using a named stand-in', device_index)
        # A negative instance id never collides with a real SDL instance id
        return DeviceDescriptor(
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
