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

``pygame._sdl2.controller`` is optional (``sdl_controller_module``): a pygame-ce build without
it (stock Pyodide's WebAssembly build, which compiles it in but never registers it) answers
like SDL with no game controllers plugged in, and those answers are remembered as usual.

MIDI ports are enumerated here too (``midi_port_count``, ``midi_port_info``,
``default_midi_input_id``, ``default_midi_output_id``), the same way: every answer is remembered
for the recorder and a replay answers from the recording, never from the MIDI hardware plugged in.
``pygame.midi`` is optional (``import_midi_module``): a pygame build without PortMidi (the
WebAssembly builds) answers as zero ports, and those answers are remembered as usual. PortMidi is
initialized lazily, on the first MIDI call, so a game that never asks never starts it.

MIDI ports open here too (``open_midi_input``, ``open_midi_output``), once per registry: a second
open of the same port hands back the first one, and ``midi_input_for_port`` /
``midi_output_for_port`` look an opened one up. An open is an answer (the port id, or the error),
and the recorder takes the opened ports' descriptors (``take_opened_midi_ports``) into its own
fields, ``midi_ports`` in the header and ``midi_ports_opened`` on a frame, so a recording made
before MIDI existed loads unchanged. A replay hands out ``ReplayMidiInput`` / ``ReplayMidiOutput``:
an input never has anything to read (the recorded MIDI events are served by the event door), an
output drops what a game writes. A port is described to the game by the descriptor it was opened
with (a port proxy's ``get_device_info()`` asks no PortMidi), so live and replay answer alike.

Only live play reads MIDI. ``LiveSources.pump_events()`` appends ``read_midi_input()`` (the live
registry's and the stand-in registry's; a replay registry has none, as the recorded events are
served by the event door) to the frame's SDL events: every opened input port, in port-id order,
read until it has nothing left (``MidiInputReader``), as ``MIDIIN`` events whose ``vice_id`` is the
port id and whose ``timestamp`` is PortMidi's, which the recording keeps. A port is read, never
polled for waiting messages: a full PortMidi buffer reports its overflow only to a read, so an
overflow is lost input (logged, bounded), not a dead port, and a frame stops reading a port at
``MIDI_MESSAGES_PER_PORT_PER_FRAME`` messages, the rest waiting for the next frame. A port whose
read fails otherwise (PortMidi raises a plain ``Exception``, never ``pygame.midi.MidiException``)
is dropped for the rest of the run, and the others go on. Writes through an output port post no
event (``MIDIOUT`` has no producer) and are not recorded.

Ports close where their lifetime ends, at the engine's teardown (``close_midi_ports``): every
opened port is closed and PortMidi shut down with ``quit()``. The quit is what ends a port:
pygame-ce 2.5.8's own ``close()`` does not close a PortMidi port, so one closed any other way
cannot be opened again in the process. Ports are opened once per registry, one engine context's
live doors, not once per process (plans/future-work.md, "MIDI ports across live engine
contexts", for two live contexts).
"""

from __future__ import annotations

import collections
import dataclasses
import importlib
import logging
from typing import TYPE_CHECKING, Any, Protocol, Self, runtime_checkable

import pygame
from pydantic import BaseModel, ConfigDict, field_validator

from glitchygames.checks import required
from glitchygames.input.state import (
    ControllerAxes,
    ControllerButtons,
    DeviceAxes,
    DeviceButtons,
    DeviceHats,
    current_input,
)
from glitchygames.sources import notify_device_answer

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from types import ModuleType

    # Type only: the module is optional at runtime (sdl_controller_module). The lazily
    # evaluated `type OpenedController` alias below is what ruff counts as a runtime use
    import pygame._sdl2.controller  # ruff: ignore[runtime-import-in-type-checking-block] - see above
    from pygame.midi import Input as PygameMidiInput
    from pygame.midi import Output as PygameMidiOutput
    from pygame.typing import ColorLike

LOG = logging.getLogger('game.input.devices')
LOG.addHandler(logging.NullHandler())


def _import_sdl_controller_module() -> ModuleType | None:
    """Import pygame._sdl2.controller, or return None where this pygame build lacks it.

    Returns:
        The module, or None.

    """
    try:
        return importlib.import_module('pygame._sdl2.controller')
    except ImportError:
        LOG.info('pygame._sdl2.controller is unavailable: game controllers are not supported')
        return None


_SDL_CONTROLLER_MODULE = _import_sdl_controller_module()


def sdl_controller_module() -> ModuleType | None:
    """Return pygame._sdl2.controller, or None in a pygame build without it.

    Returns:
        The module, or None.

    """
    return _SDL_CONTROLLER_MODULE


def import_midi_module(*, log_unavailable: bool = True) -> ModuleType | None:
    """Import pygame.midi, or return None where this pygame build has no PortMidi.

    Args:
        log_unavailable: Whether to log (at INFO) that the module is unavailable. A registry asks
            for it once, so a game that asks about MIDI every frame does not log every frame.

    Returns:
        The module, or None.

    """
    try:
        return importlib.import_module('pygame.midi')
    except ImportError:
        if log_unavailable:
            LOG.info('pygame.midi is unavailable in this pygame build: no MIDI devices')
        return None


JOYSTICK_KIND = 'joystick'
CONTROLLER_KIND = 'controller'
JOYSTICK_COUNT_CALL = 'joystick_count'
CONTROLLER_COUNT_CALL = 'controller_count'
IS_CONTROLLER_CALL = 'is_controller'
NAME_FOR_INDEX_CALL = 'name_for_index'
# Opens are answers too: the instance id on success, the error when the device was gone
OPEN_JOYSTICK_CALL = 'open_joystick'
OPEN_CONTROLLER_CALL = 'open_controller'

MIDI_INPUT_KIND = 'midi_input'
MIDI_OUTPUT_KIND = 'midi_output'
MIDI_PORT_COUNT_CALL = 'midi_port_count'
MIDI_PORT_INFO_CALL = 'midi_port_info'
DEFAULT_MIDI_INPUT_CALL = 'default_midi_input_id'
DEFAULT_MIDI_OUTPUT_CALL = 'default_midi_output_id'
OPEN_MIDI_INPUT_CALL = 'open_midi_input'
OPEN_MIDI_OUTPUT_CALL = 'open_midi_output'
MIDI_UNAVAILABLE_MESSAGE = 'pygame.midi is unavailable in this pygame build'
# What PortMidi answers for "no default port"
NO_MIDI_PORT_ID = -1
# How many messages one read of a MIDI input asks for (a bigger burst takes several reads). It
# divides PortMidi's buffer (4096, pygame's default), so a full buffer read in these batches ends on
# a batch. A read that meets an overflow part way loses what it had taken (up to 63 messages), so
# a buffer that refills while it is being read can lose up to 63 messages more beside the overflow
MIDI_READ_BATCH = 64
# The most messages a frame stops reading a port at: 5120, a whole buffer (4096), its overflow and
# some of what came after it. Reads are whole batches, so a frame can take up to 63 more than this
# when a short batch (one with fewer than 64 messages) comes just before it; the rest waits for
# the next frame, in order
MIDI_MESSAGES_PER_PORT_PER_FRAME = 80 * MIDI_READ_BATCH
# How many frames an input is read without an overflow before a burst of them ends
MIDI_OVERFLOW_QUIET_READS = 60
# What PortMidi calls a full input buffer (_is_midi_buffer_overflow)
MIDI_BUFFER_OVERFLOW_TEXT = 'Buffer overflow'

type EnumerationValue = int | bool | str | list[str | int | bool] | None

# What the door hands out: real pygame devices live, the recorded stand-ins in a replay (their
# methods share pygame's signatures, so callers use the methods both have)
type OpenedJoystick = pygame.joystick.JoystickType | ReplayJoystick
type OpenedController = pygame._sdl2.controller.Controller | ReplayController
type OpenedMidiInput = PygameMidiInput | ReplayMidiInput
type OpenedMidiOutput = PygameMidiOutput | ReplayMidiOutput


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


class MidiPortInfo(BaseModel):
    """What PortMidi says about one port (recorded as ``[interface, name, is_input, is_output]``).

    Attributes:
        interface: The MIDI API the port belongs to (for example ``CoreMIDI``).
        name: The port's name.
        is_input: Whether the port receives MIDI from a device (the game reads it).
        is_output: Whether the port sends MIDI to a device (the game writes it).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    interface: str
    name: str
    is_input: bool
    is_output: bool

    def to_answer_value(self) -> list[str | int | bool]:
        """Return the port as the value an enumeration answer records.

        Returns:
            ``[interface, name, is_input, is_output]``.

        """
        return [self.interface, self.name, self.is_input, self.is_output]

    @classmethod
    def from_answer_value(cls, value: EnumerationValue) -> MidiPortInfo | None:
        """Read a port from a recorded answer value.

        Args:
            value: The value ``to_answer_value`` made (None for a port that does not exist).

        Returns:
            The port, or None when the value is not a recorded port.

        """
        if not isinstance(value, list) or len(value) != len(cls.model_fields):
            return None
        interface, name, is_input, is_output = value
        return cls(
            interface=str(interface),
            name=str(name),
            is_input=bool(is_input),
            is_output=bool(is_output),
        )


class MidiPortDescriptor(BaseModel):
    """A MIDI port a game opened (recorded, so a replay opens a stand-in for the same port).

    Attributes:
        kind: ``MIDI_INPUT_KIND`` (a port the game reads) or ``MIDI_OUTPUT_KIND`` (one it writes).
        port_id: The PortMidi port id it was opened by.
        name: The port's name.
        interface: The MIDI API the port belongs to (for example ``CoreMIDI``).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    kind: str
    port_id: int
    name: str
    interface: str

    @field_validator('kind')
    @classmethod
    def _kind_is_a_midi_kind(cls, kind: str) -> str:
        if kind not in {MIDI_INPUT_KIND, MIDI_OUTPUT_KIND}:
            message = f'A MIDI port is {MIDI_INPUT_KIND!r} or {MIDI_OUTPUT_KIND!r}, not {kind!r}'
            raise ValueError(message)
        return kind

    def to_json(self: Self) -> dict[str, Any]:
        """Return the descriptor as a JSON-safe dict.

        Returns:
            The fields by name.

        """
        return self.model_dump()

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> MidiPortDescriptor:
        """Read a descriptor written by ``to_json``.

        Args:
            record: The dict ``to_json`` wrote.

        Returns:
            The descriptor.

        """
        return cls.model_validate(record)


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

    def midi_port_count(self) -> int:
        """Return how many MIDI ports there are (zero where PortMidi is missing)."""
        ...

    def midi_port_info(self, *, port_id: int) -> MidiPortInfo | None:
        """Return what PortMidi says about the port ``port_id`` (None when there is none).

        Args:
            port_id: The PortMidi port id (a port's position, input and output ports alike).

        """
        ...

    def default_midi_input_id(self) -> int:
        """Return the default MIDI input port's id (-1 when there is none)."""
        ...

    def default_midi_output_id(self) -> int:
        """Return the default MIDI output port's id (-1 when there is none)."""
        ...

    def open_joystick(self, *, device_index: int) -> OpenedJoystick:
        """Open the joystick at ``device_index``.

        Args:
            device_index: The SDL device index.

        """
        ...

    def open_controller(self, *, device_index: int) -> OpenedController:
        """Open the game controller at ``device_index``.

        Args:
            device_index: The SDL device index.

        """
        ...

    def open_midi_input(self, *, port_id: int) -> OpenedMidiInput:
        """Open the MIDI input port ``port_id`` (once per registry: later opens return it).

        Args:
            port_id: The PortMidi port id.

        """
        ...

    def open_midi_output(self, *, port_id: int) -> OpenedMidiOutput:
        """Open the MIDI output port ``port_id`` (once per registry: later opens return it).

        Args:
            port_id: The PortMidi port id.

        """
        ...

    def midi_input_for_port(self, *, port_id: int) -> OpenedMidiInput | None:
        """Return the opened MIDI input port ``port_id``, or None when it was never opened.

        Args:
            port_id: The PortMidi port id.

        """
        ...

    def midi_output_for_port(self, *, port_id: int) -> OpenedMidiOutput | None:
        """Return the opened MIDI output port ``port_id``, or None when it was never opened.

        Args:
            port_id: The PortMidi port id.

        """
        ...

    def joystick_for_instance(self, *, instance_id: int) -> OpenedJoystick | None:
        """Return an opened device's joystick view by instance id, or None.

        Args:
            instance_id: The SDL instance id.

        """
        ...

    def descriptor_for_instance(self, *, instance_id: int) -> DeviceDescriptor | None:
        """Return the descriptor of an opened device by instance id, or None.

        A game controller opened on both layers keeps its controller descriptor.

        Args:
            instance_id: The SDL instance id.

        """
        ...

    def forget_device(self, *, instance_id: int) -> None:
        """Forget a removed device (its removal event's instance id); unknown ids are ignored.

        Args:
            instance_id: The SDL instance id.

        """
        ...

    def take_opened_descriptors(self) -> list[DeviceDescriptor]:
        """Return the descriptors of devices opened since the last call (the recorder's)."""
        ...

    def take_opened_midi_ports(self) -> list[MidiPortDescriptor]:
        """Return the descriptors of MIDI ports opened since the last call (the recorder's)."""
        ...

    def take_enumeration_answers(self) -> list[EnumerationAnswer]:
        """Return the enumeration answers given since the last call (the recorder's)."""
        ...


def _describe(*, kind: str, device_index: int, device: OpenedJoystick) -> DeviceDescriptor:
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


def _remember_descriptor(
    *, descriptors_by_instance: dict[int, DeviceDescriptor], descriptor: DeviceDescriptor
) -> None:
    """Remember an opened device's descriptor by instance id.

    A game controller is opened on both layers (the controller manager opens it as a
    controller, the joystick manager as a joystick, in either order): its controller descriptor
    is kept, so the descriptor says the device is a game controller.
    """
    known = descriptors_by_instance.get(descriptor.instance_id)
    if known is None or known.kind != CONTROLLER_KIND:
        descriptors_by_instance[descriptor.instance_id] = descriptor


def _poll_joystick_layer(
    *, device: OpenedJoystick
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


def _poll_controller_layer(
    *, controller: OpenedController
) -> tuple[tuple[int, ...], tuple[bool, ...]]:
    """Read a game controller's axes and buttons by every CONTROLLER_AXIS_*/BUTTON_* id.

    Returns:
        Axes (pygame's int scale) and buttons.

    """
    axes = tuple(int(controller.get_axis(axis)) for axis in range(pygame.CONTROLLER_AXIS_MAX))
    buttons = tuple(
        bool(controller.get_button(button)) for button in range(pygame.CONTROLLER_BUTTON_MAX)
    )
    return axes, buttons


def _portmidi_text(*, value: object) -> str:
    """Return a PortMidi name or message as text.

    pygame-ce 2.5.8 gives bytes, decoded here as UTF-8 with undecodable bytes replaced; it plans
    to give text, taken as it is.

    Args:
        value: What PortMidi gave.

    Returns:
        The text.

    """
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value)


def _read_midi_port_info(*, midi_module: ModuleType, port_id: int) -> MidiPortInfo | None:
    """Ask PortMidi about one port, without remembering the answer.

    PortMidi gives the interface and the name as bytes or text (``_portmidi_text``).

    Returns:
        The port, or None when PortMidi has no such port.

    """
    info = midi_module.get_device_info(port_id)
    if info is None:
        return None
    interface, name, is_input, is_output, _is_opened = info
    return MidiPortInfo(
        interface=_portmidi_text(value=interface),
        name=_portmidi_text(value=name),
        is_input=bool(is_input),
        is_output=bool(is_output),
    )


def _midi_port_descriptor(
    *, midi_module: ModuleType, kind: str, port_id: int
) -> MidiPortDescriptor:
    """Describe the port an open is about to open, refusing a port that cannot be opened so.

    Returns:
        The descriptor.

    Raises:
        pygame.error: If PortMidi has no such port, or it does not go the way ``kind`` says.

    """
    info = _read_midi_port_info(midi_module=midi_module, port_id=port_id)
    if info is None:
        message = f'There is no MIDI port {port_id}'
        raise pygame.error(message)
    goes_that_way = info.is_input if kind == MIDI_INPUT_KIND else info.is_output
    if not goes_that_way:
        message = f'MIDI port {port_id} ({info.name}) cannot be opened as a {kind}'
        raise pygame.error(message)
    return MidiPortDescriptor(kind=kind, port_id=port_id, name=info.name, interface=info.interface)


def _notify_midi_port_handed_back(*, call: str, descriptor: MidiPortDescriptor) -> None:
    """Tell the observers an open handed back a port that was open already.

    A port is opened once per registry, so a scene that opens one an earlier scene opened gets it
    back: its instant-replay journal must hold the port all the same (glitchygames/
    instant_replay.py, rule 2). Only observers are told: a recorder holds the first open, and a
    replay hands the port back as live play does.

    Args:
        call: ``OPEN_MIDI_INPUT_CALL`` or ``OPEN_MIDI_OUTPUT_CALL``.
        descriptor: The port.

    """
    notify_device_answer(
        answer=EnumerationAnswer(
            call=call, device_index=descriptor.port_id, value=descriptor.port_id
        ),
        opened=descriptor,
    )


class MidiPortReadable(Protocol):
    """What the frame reads of an opened MIDI input (pygame.midi.Input, ReplayMidiInput)."""

    def read(self: Self, num_events: int) -> list[Any]:
        """Return up to ``num_events`` waiting messages, ``[[status, data1, data2, data3], t]``."""
        ...


@runtime_checkable
class ReadsMidiInput(Protocol):
    """A device registry that can hand the frame the MIDI input its opened ports received.

    Not part of ``DeviceRegistry``: only the live and the stand-in registries have it. A replay
    registry has no MIDI to read, because the recorded MIDI events are served by the event door.
    """

    def read_midi_input(self: Self) -> list[pygame.event.Event]:
        """Return the MIDIIN events every opened input port received since the last call."""
        ...


def _midi_failure_message(*, error: Exception) -> str:
    """Return the text of a failure PortMidi raised (its messages may be bytes).

    Args:
        error: What a PortMidi call raised.

    Returns:
        The message as text.

    """
    # MidiException keeps its message as ``parameter`` (its str() is that message's repr)
    message = getattr(error, 'parameter', None)
    if message is None:
        message = error.args[0] if error.args else str(error)
    return _portmidi_text(value=message)


def _is_midi_buffer_overflow(*, error: Exception) -> bool:
    """Report whether a read failed because PortMidi's input buffer was full (input was lost).

    PortMidi raises it once, as a plain ``Exception`` told from others only by its text
    (``b'PortMidi: Buffer overflow'``, pygame-ce 2.5.8), and its next read works. Should that
    text change, an overflow is taken for any other failure: the port is dropped for the rest of
    the run, logged with the new text.

    Args:
        error: What PortMidi raised.

    Returns:
        True for an overflow.

    """
    return MIDI_BUFFER_OVERFLOW_TEXT in _midi_failure_message(error=error)


class MidiInputReader:
    """Reads opened MIDI input ports into MIDIIN events, dropping a port that fails.

    One reader per registry, so the live and the stand-in registries share this one code path.
    A port is read until a read returns nothing, never asked whether messages wait: a full PortMidi
    buffer (seen on a virtual port: PortMidi 2.0.7, pygame-ce 2.5.8) hands over what it holds, then
    ``poll`` is False and all further input is refused until a ``read`` raises the overflow, once
    (``_is_midi_buffer_overflow``: the game fell behind and input was lost); after that the port
    works. The port is read on in the same frame, but a second overflow ends its frame, as
    ``MIDI_MESSAGES_PER_PORT_PER_FRAME`` messages do. The loss is logged once per port per burst,
    a burst ending after ``MIDI_OVERFLOW_QUIET_READS`` frames of the port's without one, so a port
    logs at most once in that many frames.

    A port whose ``read`` raises anything else (PortMidi raises a plain ``Exception``) is dropped
    for the rest of the run: logged once with its port id and name, and never read again. It is
    not closed: a port that failed mid-run is a device that went away, and PortMidi's own close
    on it can raise too; it stays in the registry's opened ports, so the open-once rule still
    holds.
    """

    def __init__(self: Self) -> None:
        """Start with no port dropped and none overflowing."""
        self._dropped_port_ids: set[int] = set()
        # The ports in a burst of overflows, each with the quiet reads left until it ends
        self._quiet_reads_left: dict[int, int] = {}

    def read(
        self: Self,
        *,
        midi_module: ModuleType,
        inputs: Mapping[int, MidiPortReadable],
        port_names: Mapping[int, str],
    ) -> list[pygame.event.Event]:
        """Read every opened input, in port-id order, until each has nothing left (or its cap).

        Args:
            midi_module: ``pygame.midi`` (for ``midis2events``).
            inputs: The opened input ports by port id.
            port_names: Each port's name, kept from when it was opened (a vanished device
                cannot be asked).

        Returns:
            The MIDIIN events, ``vice_id`` being the port id. Timestamps are PortMidi's.

        """
        events: list[pygame.event.Event] = []
        for port_id in sorted(inputs):
            if port_id in self._dropped_port_ids:
                continue
            messages = self._waiting_messages(
                port_id=port_id, port=inputs[port_id], port_name=port_names[port_id]
            )
            if messages:
                # Outside the port's own failures: a defect in the conversion surfaces
                events.extend(midi_module.midis2events(messages, port_id))
        return events

    def _waiting_messages(
        self: Self, *, port_id: int, port: MidiPortReadable, port_name: str
    ) -> list[Any]:
        """Take what waits on a port, up to the frame's cap; what it gave before failing is kept.

        Returns:
            PortMidi's messages, oldest first.

        """
        messages: list[Any] = []
        overflowed = self._read_until_failure(
            port_id=port_id, port=port, port_name=port_name, messages=messages
        )
        if overflowed:
            # PortMidi raises an overflow once: what arrived after it is there to read. Read on
            # once only, so a port that keeps overflowing cannot hold the frame
            self._read_until_failure(
                port_id=port_id, port=port, port_name=port_name, messages=messages
            )
        self._note_overflow(port_id=port_id, port_name=port_name, overflowed=overflowed)
        return messages

    def _read_until_failure(
        self: Self, *, port_id: int, port: MidiPortReadable, port_name: str, messages: list[Any]
    ) -> bool:
        """Add what waits on a port to ``messages``, until nothing does, the cap or a failure.

        Returns:
            True when its buffer overflowed. Any other failure drops the port.

        """
        try:
            while len(messages) < MIDI_MESSAGES_PER_PORT_PER_FRAME:
                batch = port.read(MIDI_READ_BATCH)
                if not batch:
                    break
                messages.extend(batch)
        except Exception as error:
            # PortMidi's Read raises a plain Exception (pypm.pyx), not MidiException
            if _is_midi_buffer_overflow(error=error):
                return True
            self._dropped_port_ids.add(port_id)
            LOG.exception(
                'MIDI input port %d (%s) failed and is no longer read', port_id, port_name
            )
        return False

    def _note_overflow(self: Self, *, port_id: int, port_name: str, overflowed: bool) -> None:
        """Log the first overflow of a port's burst; count the quiet reads that end one."""
        if overflowed:
            if port_id not in self._quiet_reads_left:
                LOG.warning(
                    'MIDI input port %d (%s) overflowed: the game fell behind and input was lost',
                    port_id,
                    port_name,
                )
            self._quiet_reads_left[port_id] = MIDI_OVERFLOW_QUIET_READS
        elif port_id in self._quiet_reads_left:
            self._quiet_reads_left[port_id] -= 1
            if self._quiet_reads_left[port_id] == 0:
                del self._quiet_reads_left[port_id]


class LiveDeviceRegistry:  # ruff: ignore[too-many-public-methods] - every DeviceRegistry member
    """Enumerates and opens real devices, remembers them, and polls them for the snapshot."""

    def __init__(self: Self) -> None:
        """Start with no devices opened and nothing asked."""
        # Joystick views by instance id (a controller's is its as_joystick())
        self._devices_by_instance: dict[int, pygame.joystick.JoystickType] = {}
        self._controllers_by_instance: dict[int, pygame._sdl2.controller.Controller] = {}
        self._descriptors_by_instance: dict[int, DeviceDescriptor] = {}
        self._new_descriptors: list[DeviceDescriptor] = []
        self._new_answers: list[EnumerationAnswer] = []
        self._midi_initialized = False
        self._midi_unavailable_logged = False
        # Opened MIDI ports: one per port id and direction, for the life of the registry
        self._midi_inputs: dict[int, PygameMidiInput] = {}
        self._midi_outputs: dict[int, PygameMidiOutput] = {}
        self._new_midi_ports: list[MidiPortDescriptor] = []
        # What each opened port was opened as, by kind and port id (told when it is handed back)
        self._midi_port_descriptors: dict[tuple[str, int], MidiPortDescriptor] = {}
        self._midi_input_reader = MidiInputReader()
        # Each opened input port's name, kept from its open for the log if it fails
        self._midi_input_names: dict[int, str] = {}

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
        controller_module = sdl_controller_module()
        try:
            # No controller module: like SDL with no game controller plugged in
            count = 0 if controller_module is None else int(controller_module.get_count())
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
        controller_module = sdl_controller_module()
        try:
            flag = (
                False
                if controller_module is None
                else bool(controller_module.is_controller(device_index))
            )
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
            sdl_controller_module(), 'name_forindex', None
        )
        try:
            sdl_name = None if name_lookup is None else name_lookup(device_index)
        except pygame.error as error:
            self._remember_failure(call=NAME_FOR_INDEX_CALL, device_index=device_index, error=error)
            raise
        name = None if sdl_name is None else str(sdl_name)
        self._remember_answer(call=NAME_FOR_INDEX_CALL, device_index=device_index, value=name)
        return name

    def midi_port_count(self: Self) -> int:
        """Return how many MIDI ports PortMidi reports (remembered for the recorder).

        Returns:
            The count (0 without PortMidi).

        """
        count = self._ask_midi(
            call=MIDI_PORT_COUNT_CALL,
            device_index=None,
            ask=lambda midi_module: int(midi_module.get_count()),
            without_portmidi=0,
        )
        return count if isinstance(count, int) else 0

    def midi_port_info(self: Self, *, port_id: int) -> MidiPortInfo | None:
        """Return what PortMidi says about the port ``port_id`` (remembered for the recorder).

        PortMidi gives the interface and the name as bytes or text (``_portmidi_text``).

        Args:
            port_id: The PortMidi port id.

        Returns:
            The port, or None (no such port, or no PortMidi).

        """

        def ask(midi_module: ModuleType) -> EnumerationValue:
            info = _read_midi_port_info(midi_module=midi_module, port_id=port_id)
            return None if info is None else info.to_answer_value()

        value = self._ask_midi(
            call=MIDI_PORT_INFO_CALL, device_index=port_id, ask=ask, without_portmidi=None
        )
        return MidiPortInfo.from_answer_value(value)

    def default_midi_input_id(self: Self) -> int:
        """Return the default MIDI input port's id, -1 when there is none (remembered).

        Returns:
            The port id.

        """
        port_id = self._ask_midi(
            call=DEFAULT_MIDI_INPUT_CALL,
            device_index=None,
            ask=lambda midi_module: int(midi_module.get_default_input_id()),
            without_portmidi=NO_MIDI_PORT_ID,
        )
        return port_id if isinstance(port_id, int) else NO_MIDI_PORT_ID

    def default_midi_output_id(self: Self) -> int:
        """Return the default MIDI output port's id, -1 when there is none (remembered).

        Returns:
            The port id.

        """
        port_id = self._ask_midi(
            call=DEFAULT_MIDI_OUTPUT_CALL,
            device_index=None,
            ask=lambda midi_module: int(midi_module.get_default_output_id()),
            without_portmidi=NO_MIDI_PORT_ID,
        )
        return port_id if isinstance(port_id, int) else NO_MIDI_PORT_ID

    def open_joystick(self: Self, *, device_index: int) -> pygame.joystick.JoystickType:
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
            # Not quit, unlike open_controller's failure: pygame Joystick objects for one
            # device index share an SDL handle, so quitting this one could close a handle
            # another object still uses (the leak is the smaller harm)
            self._remember_failure(call=OPEN_JOYSTICK_CALL, device_index=device_index, error=error)
            raise
        self._remember_opened(
            call=OPEN_JOYSTICK_CALL, descriptor=descriptor, joystick_view=joystick, controller=None
        )
        return joystick

    def open_midi_input(self: Self, *, port_id: int) -> PygameMidiInput:
        """Open the MIDI input port ``port_id``, once: a second open returns the first.

        A port that is gone, is not an input or cannot be opened raises ``pygame.error``, and the
        failure is remembered, so a replay fails the same way.

        Args:
            port_id: The PortMidi port id.

        Returns:
            The pygame MIDI input.

        """
        opened = self._midi_inputs.get(port_id)
        if opened is not None:
            _notify_midi_port_handed_back(
                call=OPEN_MIDI_INPUT_CALL,
                descriptor=self._midi_port_descriptors[MIDI_INPUT_KIND, port_id],
            )
            return opened
        midi_module, descriptor = self._prepare_midi_open(
            call=OPEN_MIDI_INPUT_CALL, kind=MIDI_INPUT_KIND, port_id=port_id
        )
        midi_input = self._construct_midi_port(
            call=OPEN_MIDI_INPUT_CALL,
            port_id=port_id,
            construct=midi_module.Input,
        )
        self._midi_inputs[port_id] = midi_input
        self._midi_input_names[port_id] = descriptor.name
        self._remember_opened_midi_port(call=OPEN_MIDI_INPUT_CALL, descriptor=descriptor)
        return midi_input

    def open_midi_output(self: Self, *, port_id: int) -> PygameMidiOutput:
        """Open the MIDI output port ``port_id``, once: a second open returns the first.

        A port that is gone, is not an output or cannot be opened raises ``pygame.error``, and the
        failure is remembered, so a replay fails the same way.

        Args:
            port_id: The PortMidi port id.

        Returns:
            The pygame MIDI output.

        """
        opened = self._midi_outputs.get(port_id)
        if opened is not None:
            _notify_midi_port_handed_back(
                call=OPEN_MIDI_OUTPUT_CALL,
                descriptor=self._midi_port_descriptors[MIDI_OUTPUT_KIND, port_id],
            )
            return opened
        midi_module, descriptor = self._prepare_midi_open(
            call=OPEN_MIDI_OUTPUT_CALL, kind=MIDI_OUTPUT_KIND, port_id=port_id
        )
        midi_output = self._construct_midi_port(
            call=OPEN_MIDI_OUTPUT_CALL,
            port_id=port_id,
            construct=midi_module.Output,
        )
        self._midi_outputs[port_id] = midi_output
        self._remember_opened_midi_port(call=OPEN_MIDI_OUTPUT_CALL, descriptor=descriptor)
        return midi_output

    def midi_input_for_port(self: Self, *, port_id: int) -> PygameMidiInput | None:
        """Return the opened MIDI input port ``port_id``, or None when it was never opened.

        Args:
            port_id: The PortMidi port id.

        Returns:
            The input, or None.

        """
        return self._midi_inputs.get(port_id)

    def read_midi_input(self: Self) -> list[pygame.event.Event]:
        """Return the MIDIIN events every opened input port received since the last call.

        Ports are read in port-id order, each until nothing is waiting, so a burst larger than
        ``MIDI_READ_BATCH`` arrives whole, in one frame, up to
        ``MIDI_MESSAGES_PER_PORT_PER_FRAME`` (the rest the next frame). Only opened ports are
        read. A port that raises is dropped for the rest of the run, unless its buffer only
        overflowed (``MidiInputReader``).

        Returns:
            The events (``vice_id`` is the port id; timestamps are PortMidi's).

        """
        if not self._midi_inputs:
            # Nothing opened, so nothing to read, and PortMidi is not touched (a replay's own
            # live queue never opens a port)
            return []
        midi_module = import_midi_module(log_unavailable=False)
        if midi_module is None:  # pragma: no cover - ports are opened only where PortMidi is
            return []
        return self._midi_input_reader.read(
            midi_module=midi_module, inputs=self._midi_inputs, port_names=self._midi_input_names
        )

    def midi_output_for_port(self: Self, *, port_id: int) -> PygameMidiOutput | None:
        """Return the opened MIDI output port ``port_id``, or None when it was never opened.

        Args:
            port_id: The PortMidi port id.

        Returns:
            The output, or None.

        """
        return self._midi_outputs.get(port_id)

    def close_midi_ports(self: Self) -> None:
        """Close every MIDI port this registry opened, then shut PortMidi down.

        Where port lifetimes end (the engine's teardown). Nothing happens when PortMidi was
        never started here, and closing twice is safe: the ports are forgotten as they close.
        A port whose close raises (PortMidi raises a plain ``Exception``) is logged and the
        rest still close; PortMidi is shut down after them, whatever any of them did.

        Ports are opened once per registry, not once per process, and a registry belongs to one
        engine context. Only the outermost context runs live today (an inner game is a replay),
        so only it shuts PortMidi down; two live contexts are not supported (plans/
        future-work.md, "MIDI ports across live engine contexts").

        """
        if not self._midi_initialized:
            return
        midi_module = required(import_midi_module(log_unavailable=False), what='pygame.midi')
        try:
            for port_id, midi_input in self._midi_inputs.items():
                self._close_midi_port(
                    port=midi_input,
                    label=f'input port {port_id} ({self._midi_input_names.get(port_id)})',
                )
            for port_id, midi_output in self._midi_outputs.items():
                self._close_midi_port(port=midi_output, label=f'output port {port_id}')
        finally:
            self._midi_inputs.clear()
            self._midi_outputs.clear()
            self._midi_input_names.clear()
            self._midi_port_descriptors.clear()
            self._midi_initialized = False
            midi_module.quit()

    @staticmethod
    def _close_midi_port(*, port: PygameMidiInput | PygameMidiOutput, label: str) -> None:
        """Close one port, logging (not raising) a failure."""
        try:
            port.close()
        except Exception:
            # PortMidi's Close raises a plain Exception (pypm.pyx)
            LOG.warning('MIDI %s failed to close', label, exc_info=True)

    def open_controller(self: Self, *, device_index: int) -> pygame._sdl2.controller.Controller:
        """Open the game controller at ``device_index`` and remember it.

        Its joystick view is described and polled on the joystick layer, and the controller
        itself on the controller layer (see the module docstring).

        Args:
            device_index: The SDL device index.

        Returns:
            The pygame controller.

        Raises:
            pygame.error: If the device is gone (unplugged since it was counted; remembered),
                or this pygame build has no game controller module (remembered too).

        """
        controller_module = sdl_controller_module()
        if controller_module is None:
            unavailable = pygame.error('game controllers are unavailable in this pygame build')
            self._remember_failure(
                call=OPEN_CONTROLLER_CALL, device_index=device_index, error=unavailable
            )
            raise unavailable
        try:
            controller = controller_module.Controller(device_index)
        except pygame.error as error:
            self._remember_failure(
                call=OPEN_CONTROLLER_CALL, device_index=device_index, error=error
            )
            raise
        try:
            joystick_view = controller.as_joystick()
            descriptor = _describe(
                kind=CONTROLLER_KIND, device_index=device_index, device=joystick_view
            )
        except pygame.error as error:
            # Opened but unusable (gone in between): close it so no SDL handle leaks
            controller.quit()
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

    def joystick_for_instance(
        self: Self, *, instance_id: int
    ) -> pygame.joystick.JoystickType | None:
        """Return an opened device's joystick view by instance id, or None.

        Args:
            instance_id: The SDL instance id.

        Returns:
            The joystick (a controller's joystick view), or None.

        """
        return self._devices_by_instance.get(instance_id)

    def descriptor_for_instance(self: Self, *, instance_id: int) -> DeviceDescriptor | None:
        """Return the descriptor of an opened device by instance id, or None.

        Args:
            instance_id: The SDL instance id.

        Returns:
            The descriptor recorded when it was opened (a game controller's controller one).

        """
        return self._descriptors_by_instance.get(instance_id)

    def forget_device(self: Self, *, instance_id: int) -> None:
        """Stop polling and handing out a removed (or vanished) device.

        Called from the joystick and controller managers' device-removed handlers, and by
        ``poll`` for a device that is detached or raises. Unknown ids are ignored, so the
        joystick and controller removal events of one game controller can both call it.

        Args:
            instance_id: The SDL instance id.

        """
        self._devices_by_instance.pop(instance_id, None)
        self._controllers_by_instance.pop(instance_id, None)
        self._descriptors_by_instance.pop(instance_id, None)

    def discard_untaken(self: Self) -> None:
        """Drop the answers and descriptors nobody took this frame (``LiveSources.end_frame``).

        A recorder (Task 11 of the gameplay replay plan) takes them before ``end_frame``;
        without one, nothing would ever take them and they would pile up for the whole run.
        """
        self._new_answers.clear()
        self._new_descriptors.clear()
        self._new_midi_ports.clear()

    def take_opened_descriptors(self: Self) -> list[DeviceDescriptor]:
        """Return the descriptors of devices opened since the last call (the recorder's).

        Returns:
            The descriptors, in opening order.

        """
        descriptors, self._new_descriptors = self._new_descriptors, []
        return descriptors

    def take_opened_midi_ports(self: Self) -> list[MidiPortDescriptor]:
        """Return the descriptors of MIDI ports opened since the last call (the recorder's).

        Returns:
            The descriptors, in opening order.

        """
        descriptors, self._new_midi_ports = self._new_midi_ports, []
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

        A device that is detached (a controller's ``attached()``) or raises while read is
        forgotten (``forget_device``): it reads as absent from then on, and is logged once.

        Returns:
            The positions by instance id.

        """
        axes: dict[int, tuple[float, ...]] = {}
        buttons: dict[int, tuple[bool, ...]] = {}
        hats: dict[int, tuple[tuple[int, int], ...]] = {}
        controller_axes: dict[int, tuple[int, ...]] = {}
        controller_buttons: dict[int, tuple[bool, ...]] = {}
        vanished_instance_ids: list[int] = []
        for instance_id, joystick_view in self._devices_by_instance.items():
            controller = self._controllers_by_instance.get(instance_id)
            try:
                detached = controller is not None and not controller.attached()
                joystick_layer = None if detached else _poll_joystick_layer(device=joystick_view)
                controller_layer = (
                    None
                    if detached or controller is None
                    else _poll_controller_layer(controller=controller)
                )
            except pygame.error:
                # Unplugged since it was opened: it is absent from every mapping (a device is
                # never half present) and forgotten, so it is not polled or logged again
                LOG.debug(
                    'Device %d vanished while polling; forgetting it', instance_id, exc_info=True
                )
                vanished_instance_ids.append(instance_id)
                continue
            if joystick_layer is None:
                LOG.debug('Controller %d is detached; forgetting it', instance_id)
                vanished_instance_ids.append(instance_id)
                continue
            axes[instance_id], buttons[instance_id], hats[instance_id] = joystick_layer
            if controller_layer is not None:
                controller_axes[instance_id], controller_buttons[instance_id] = controller_layer
        for instance_id in vanished_instance_ids:
            self.forget_device(instance_id=instance_id)
        return PolledDevices(
            axes=axes,
            buttons=buttons,
            hats=hats,
            controller_axes=controller_axes,
            controller_buttons=controller_buttons,
        )

    def _ask_midi(
        self: Self,
        *,
        call: str,
        device_index: int | None,
        ask: Callable[[ModuleType], EnumerationValue],
        without_portmidi: EnumerationValue,
    ) -> EnumerationValue:
        """Ask PortMidi (started on the first ask) and remember the answer or the failure.

        Returns:
            The answer, or ``without_portmidi`` where this pygame build has no PortMidi.

        Raises:
            pygame.error: If PortMidi cannot answer (remembered too).

        """
        try:
            value = self._ask_started_midi(ask=ask, without_portmidi=without_portmidi)
        except pygame.error as error:
            self._remember_failure(call=call, device_index=device_index, error=error)
            raise
        self._remember_answer(call=call, device_index=device_index, value=value)
        return value

    def _ask_started_midi(
        self: Self,
        *,
        ask: Callable[[ModuleType], EnumerationValue],
        without_portmidi: EnumerationValue,
    ) -> EnumerationValue:
        midi_module = self._started_midi_module()
        if midi_module is None:
            return without_portmidi
        return ask(midi_module)

    def _started_midi_module(self: Self) -> ModuleType | None:
        """Return pygame.midi with PortMidi started (on the first call), None without PortMidi.

        Returns:
            The module, or None. Where it is missing, that is logged once per registry.

        """
        midi_module = import_midi_module(log_unavailable=not self._midi_unavailable_logged)
        if midi_module is None:
            self._midi_unavailable_logged = True
            return None
        if not self._midi_initialized:
            midi_module.init()
            self._midi_initialized = True
        return midi_module

    def _prepare_midi_open(
        self: Self, *, call: str, kind: str, port_id: int
    ) -> tuple[ModuleType, MidiPortDescriptor]:
        """Start PortMidi and describe the port an open is about to open.

        Returns:
            The module and the port's descriptor.

        Raises:
            pygame.error: If PortMidi is missing or cannot start, or the port is gone or goes the
                wrong way (remembered).

        """
        try:
            midi_module = self._started_midi_module()
        except pygame.error as error:
            # PortMidi could not start (the same remembered failure as an enumeration's)
            self._remember_failure(call=call, device_index=port_id, error=error)
            raise
        if midi_module is None:
            unavailable = pygame.error(MIDI_UNAVAILABLE_MESSAGE)
            self._remember_failure(call=call, device_index=port_id, error=unavailable)
            raise unavailable
        try:
            descriptor = _midi_port_descriptor(midi_module=midi_module, kind=kind, port_id=port_id)
        except pygame.error as error:
            self._remember_failure(call=call, device_index=port_id, error=error)
            raise
        return midi_module, descriptor

    def _construct_midi_port[PortT](
        self: Self,
        *,
        call: str,
        port_id: int,
        construct: Callable[[int], PortT],
    ) -> PortT:
        """Open the port with pygame's constructor; what PortMidi refuses is a pygame.error.

        Anything the constructor raises (``Exception``, not ``BaseException``) is raised as
        ``pygame.error`` (and remembered under ``call``), as every other door call fails, so a
        replay raises the same.

        Args:
            call: The open call to remember a failure under.
            port_id: The PortMidi port id.
            construct: ``midi_module.Input`` or ``midi_module.Output``.

        Returns:
            The port.

        """
        try:
            return construct(port_id)
        except Exception as error:
            # PortMidi's constructors raise a plain Exception whose message may be bytes
            # (pypm.pyx), and pygame.midi.MidiException is not a pygame.error: whatever the
            # constructor raises becomes the one remembered pygame.error
            failure = pygame.error(_midi_failure_message(error=error))
            self._remember_failure(call=call, device_index=port_id, error=failure)
            raise failure from error

    def _remember_opened_midi_port(
        self: Self, *, call: str, descriptor: MidiPortDescriptor
    ) -> None:
        self._new_midi_ports.append(descriptor)
        self._midi_port_descriptors[descriptor.kind, descriptor.port_id] = descriptor
        self._remember_answer(
            call=call,
            device_index=descriptor.port_id,
            value=descriptor.port_id,
            opened=descriptor,
        )

    def _remember_answer(
        self: Self,
        *,
        call: str,
        device_index: int | None,
        value: EnumerationValue,
        opened: DeviceDescriptor | MidiPortDescriptor | None = None,
    ) -> None:
        answer = EnumerationAnswer(call=call, device_index=device_index, value=value)
        self._new_answers.append(answer)
        notify_device_answer(answer=answer, opened=opened)

    def _remember_failure(
        self: Self, *, call: str, device_index: int | None, error: pygame.error
    ) -> None:
        answer = EnumerationAnswer(
            call=call, device_index=device_index, value=None, error=str(error)
        )
        self._new_answers.append(answer)
        notify_device_answer(answer=answer, opened=None)

    def _remember_opened(
        self: Self,
        *,
        call: str,
        descriptor: DeviceDescriptor,
        joystick_view: pygame.joystick.JoystickType,
        controller: pygame._sdl2.controller.Controller | None,
    ) -> None:
        self._devices_by_instance[descriptor.instance_id] = joystick_view
        if controller is not None:
            self._controllers_by_instance[descriptor.instance_id] = controller
        _remember_descriptor(
            descriptors_by_instance=self._descriptors_by_instance, descriptor=descriptor
        )
        self._new_descriptors.append(descriptor)
        self._remember_answer(
            call=call,
            device_index=descriptor.device_index,
            value=descriptor.instance_id,
            opened=descriptor,
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
        # Initialized on creation, as pygame-ce's devices are (its docs: "opened immediately on
        # creation"), so get_init() answers as live play does before any init() call
        self._initialized = True

    def init(self: Self) -> None:
        """Mark initialized (no hardware)."""
        self._initialized = True

    def quit(self: Self) -> None:
        """Mark uninitialized."""
        self._initialized = False

    def get_init(self: Self) -> bool:
        """Return whether the stand-in is initialized (from creation until quit()).

        Returns:
            True from creation, or after init(); False after quit().

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

    def set_led(self: Self, color: ColorLike, /) -> bool:
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
        # Initialized on creation, as pygame-ce's devices are (its docs: "opened immediately on
        # creation"), so get_init() answers as live play does before any init() call
        self._initialized = True

    def init(self: Self) -> None:
        """Mark initialized (no hardware)."""
        self._initialized = True

    def quit(self: Self) -> None:
        """Mark uninitialized."""
        self._initialized = False

    def get_init(self: Self) -> bool:
        """Return whether the stand-in is initialized (from creation until quit()).

        Returns:
            True from creation, or after init(); False after quit().

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

    def set_led(self: Self, color: ColorLike, /) -> bool:
        """Ignore an LED colour (positional-only: pygame's signature; no hardware).

        Args:
            color: The colour (ignored).

        Returns:
            False, as pygame does for a device without an LED.

        """
        del color
        return False


class ReplayMidiInput:
    """A recorded MIDI input port: never has anything to read.

    A drop-in for ``pygame.midi.Input``. A replay serves the recorded MIDI events through the
    event door, so a game polling its port finds nothing waiting, whatever is plugged in.
    """

    def __init__(self: Self, *, descriptor: MidiPortDescriptor) -> None:
        """Remember the port this stands in for.

        Args:
            descriptor: The recorded port.

        """
        self.descriptor = descriptor

    def poll(self: Self) -> bool:
        """Say there is nothing to read.

        Returns:
            False.

        """
        return False

    def read(self: Self, num_events: int) -> list[Any]:
        """Return no events.

        Args:
            num_events: How many events the game would read (ignored).

        Returns:
            An empty list.

        """
        del num_events
        return []

    def close(self: Self) -> None:
        """Close nothing."""


class ReplayMidiOutput:
    """A recorded MIDI output port: drops everything a game writes.

    A drop-in for ``pygame.midi.Output`` (the signatures are pygame's): no MIDI reaches a device
    in a replay.
    """

    def __init__(self: Self, *, descriptor: MidiPortDescriptor) -> None:
        """Remember the port this stands in for.

        Args:
            descriptor: The recorded port.

        """
        self.descriptor = descriptor

    def write_short(self: Self, status: int, data1: int = 0, data2: int = 0) -> None:
        """Drop a three-byte message.

        Args:
            status: The status byte (ignored).
            data1: The first data byte (ignored).
            data2: The second data byte (ignored).

        """
        del status, data1, data2

    def write(self: Self, data: list[Any]) -> None:
        """Drop a list of timestamped messages.

        Args:
            data: The messages (ignored).

        """
        del data

    def write_sys_ex(self: Self, when: int, msg: list[int] | str) -> None:
        """Drop a system-exclusive message.

        Args:
            when: The timestamp (ignored).
            msg: The message (ignored).

        """
        del when, msg

    def note_on(self: Self, note: int, velocity: int, channel: int = 0) -> None:
        """Drop a note-on.

        Args:
            note: The note (ignored).
            velocity: The velocity (ignored).
            channel: The channel (ignored).

        """
        del note, velocity, channel

    def note_off(self: Self, note: int, velocity: int = 0, channel: int = 0) -> None:
        """Drop a note-off.

        Args:
            note: The note (ignored).
            velocity: The velocity (ignored).
            channel: The channel (ignored).

        """
        del note, velocity, channel

    def set_instrument(self: Self, instrument_id: int, channel: int = 0) -> None:
        """Drop a program change.

        Args:
            instrument_id: The program (ignored).
            channel: The channel (ignored).

        """
        del instrument_id, channel

    def pitch_bend(self: Self, value: int = 0, channel: int = 0) -> None:
        """Drop a pitch bend.

        Args:
            value: The bend (ignored).
            channel: The channel (ignored).

        """
        del value, channel

    def close(self: Self) -> None:
        """Close nothing."""


class ReplayDeviceRegistry:  # ruff: ignore[too-many-public-methods] - every DeviceRegistry member
    """Stand-ins and recorded enumeration answers (glitchygames/replay/driver.py builds it)."""

    def __init__(
        self: Self,
        *,
        descriptors: list[DeviceDescriptor],
        enumeration_answers: list[EnumerationAnswer],
        midi_ports: list[MidiPortDescriptor] | None = None,
    ) -> None:
        """Index the recorded descriptors and queue the recorded answers by call.

        Args:
            descriptors: Devices the recording opened before it started (header).
            enumeration_answers: Answers the recording gave before it started (header).
            midi_ports: MIDI ports the recording opened before it started (header; a recording
                made before MIDI had none).

        """
        # In recording order; a device index can recur (a device unplugged and another plugged
        # in), so descriptors are never keyed by index alone
        self._descriptors: list[DeviceDescriptor] = []
        self._descriptors_by_instance: dict[int, DeviceDescriptor] = {}
        self._opened_instances: set[int] = set()
        self._opened_by_instance: dict[int, ReplayJoystick] = {}
        self._opened_descriptors_by_instance: dict[int, DeviceDescriptor] = {}
        self._answers: dict[tuple[str, int | None], collections.deque[EnumerationAnswer]] = {}
        self._last_answers: dict[tuple[str, int | None], EnumerationAnswer] = {}
        self._learned_descriptors: list[DeviceDescriptor] = []
        self._warned_keys: set[tuple[str, int | None]] = set()
        # The ports MIDI calls answer with when the recording has no answer (a subclass may
        # set some: the stand-in registry); a recording never has any without them
        self._midi_ports: tuple[MidiPortInfo, ...] = ()
        # The recorded ports by kind and port id (a later recording of the same port wins), the
        # stand-ins opened for them, and the ports learned from frames for a recorder to take
        self._recorded_midi_ports: dict[tuple[str, int], MidiPortDescriptor] = {}
        self._midi_inputs: dict[int, ReplayMidiInput] = {}
        self._midi_outputs: dict[int, ReplayMidiOutput] = {}
        self._learned_midi_ports: list[MidiPortDescriptor] = []
        self.add_midi_ports(descriptors=midi_ports or [], learned=False)
        self._index_descriptors(descriptors=descriptors)
        self.add_enumeration_answers(answers=enumeration_answers)

    def add_descriptors(self: Self, *, descriptors: list[DeviceDescriptor]) -> None:
        """Learn devices the recording opened later (``devices_opened`` frame fields).

        Args:
            descriptors: The frame's opened devices, in order.

        """
        self._index_descriptors(descriptors=descriptors)
        self._learned_descriptors.extend(descriptors)

    def add_midi_ports(
        self: Self, *, descriptors: list[MidiPortDescriptor], learned: bool = True
    ) -> None:
        """Learn MIDI ports the recording opened (header or ``midi_ports_opened`` frame field).

        Args:
            descriptors: The opened ports, in order.
            learned: True for a frame's ports, which a recording made over this replay writes in
                the same frames (``take_opened_midi_ports``); False for the header's.

        """
        for descriptor in descriptors:
            self._recorded_midi_ports[descriptor.kind, descriptor.port_id] = descriptor
        if learned:
            self._learned_midi_ports.extend(descriptors)

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

    def midi_port_count(self: Self) -> int:
        """Answer from the recording (else the count of ``_midi_ports``).

        Returns:
            The count.

        """
        fallback = len(self._midi_ports)
        count = self._recorded(call=MIDI_PORT_COUNT_CALL, device_index=None, fallback=fallback)
        return count if isinstance(count, int) else fallback

    def midi_port_info(self: Self, *, port_id: int) -> MidiPortInfo | None:
        """Answer from the recording (else the port of ``_midi_ports`` at that position).

        Args:
            port_id: The PortMidi port id.

        Returns:
            The port, or None.

        """
        known = 0 <= port_id < len(self._midi_ports)
        fallback = self._midi_ports[port_id].to_answer_value() if known else None
        value = self._recorded(call=MIDI_PORT_INFO_CALL, device_index=port_id, fallback=fallback)
        return MidiPortInfo.from_answer_value(value)

    def default_midi_input_id(self: Self) -> int:
        """Answer from the recording (else the first input of ``_midi_ports``, -1 for none).

        Returns:
            The port id.

        """
        fallback = self._first_midi_port_id(is_input=True)
        port_id = self._recorded(call=DEFAULT_MIDI_INPUT_CALL, device_index=None, fallback=fallback)
        return port_id if isinstance(port_id, int) else fallback

    def default_midi_output_id(self: Self) -> int:
        """Answer from the recording (else the first output of ``_midi_ports``, -1 for none).

        Returns:
            The port id.

        """
        fallback = self._first_midi_port_id(is_input=False)
        port_id = self._recorded(
            call=DEFAULT_MIDI_OUTPUT_CALL, device_index=None, fallback=fallback
        )
        return port_id if isinstance(port_id, int) else fallback

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
        _remember_descriptor(
            descriptors_by_instance=self._opened_descriptors_by_instance, descriptor=descriptor
        )
        return joystick

    def open_midi_input(self: Self, *, port_id: int) -> ReplayMidiInput:
        """Return the stand-in for the recorded MIDI input port ``port_id`` (one per port).

        Args:
            port_id: The PortMidi port id.

        Returns:
            The stand-in.

        """
        stand_in = self._midi_inputs.get(port_id)
        if stand_in is None:
            descriptor = self._midi_port_to_open(
                call=OPEN_MIDI_INPUT_CALL, kind=MIDI_INPUT_KIND, port_id=port_id
            )
            stand_in = self._midi_inputs[port_id] = self._new_midi_input(descriptor=descriptor)
        else:
            _notify_midi_port_handed_back(call=OPEN_MIDI_INPUT_CALL, descriptor=stand_in.descriptor)
        return stand_in

    def _new_midi_input(self: Self, *, descriptor: MidiPortDescriptor) -> ReplayMidiInput:
        """Return the stand-in for an input port being opened (a replay's has nothing to read).

        Returns:
            The stand-in.

        """
        return ReplayMidiInput(descriptor=descriptor)

    def open_midi_output(self: Self, *, port_id: int) -> ReplayMidiOutput:
        """Return the stand-in for the recorded MIDI output port ``port_id`` (one per port).

        Args:
            port_id: The PortMidi port id.

        Returns:
            The stand-in.

        """
        stand_in = self._midi_outputs.get(port_id)
        if stand_in is None:
            descriptor = self._midi_port_to_open(
                call=OPEN_MIDI_OUTPUT_CALL, kind=MIDI_OUTPUT_KIND, port_id=port_id
            )
            stand_in = self._midi_outputs[port_id] = ReplayMidiOutput(descriptor=descriptor)
        else:
            _notify_midi_port_handed_back(
                call=OPEN_MIDI_OUTPUT_CALL, descriptor=stand_in.descriptor
            )
        return stand_in

    def midi_input_for_port(self: Self, *, port_id: int) -> ReplayMidiInput | None:
        """Return the opened MIDI input stand-in ``port_id``, or None when it was never opened.

        Args:
            port_id: The PortMidi port id.

        Returns:
            The stand-in, or None.

        """
        return self._midi_inputs.get(port_id)

    def midi_output_for_port(self: Self, *, port_id: int) -> ReplayMidiOutput | None:
        """Return the opened MIDI output stand-in ``port_id``, or None when it was never opened.

        Args:
            port_id: The PortMidi port id.

        Returns:
            The stand-in, or None.

        """
        return self._midi_outputs.get(port_id)

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
        _remember_descriptor(
            descriptors_by_instance=self._opened_descriptors_by_instance, descriptor=descriptor
        )
        return controller

    def joystick_for_instance(self: Self, *, instance_id: int) -> ReplayJoystick | None:
        """Return an opened stand-in's joystick view by instance id, or None.

        Args:
            instance_id: The recorded SDL instance id.

        Returns:
            The joystick stand-in (a controller's joystick view), or None.

        """
        return self._opened_by_instance.get(instance_id)

    def adopt_device(
        self: Self, *, descriptor: DeviceDescriptor
    ) -> ReplayJoystick | ReplayController:
        """Make a stand-in for a device the recording held as it began, asking no answer.

        An instant replay's journal records the live devices as its scene started
        (glitchygames/instant_replay.py, rule 10); its playback scope adopts them
        (``GameEngine.enter_playback_devices``), so the played scene sees them without taking
        an answer the scene's own code is served. Later lookups by instance id find them.

        Args:
            descriptor: The device (a ``CONTROLLER_KIND`` one is a game controller).

        Returns:
            The stand-in: a ``ReplayController`` for a game controller, else a
            ``ReplayJoystick``.

        """
        device: ReplayJoystick | ReplayController
        if descriptor.kind == CONTROLLER_KIND:
            device = ReplayController(descriptor=descriptor)
            joystick = device.as_joystick()
        else:
            device = joystick = ReplayJoystick(descriptor=descriptor)
        self._opened_by_instance[descriptor.instance_id] = joystick
        self._opened_instances.add(descriptor.instance_id)
        _remember_descriptor(
            descriptors_by_instance=self._opened_descriptors_by_instance, descriptor=descriptor
        )
        return device

    def adopt_midi_port(
        self: Self, *, descriptor: MidiPortDescriptor
    ) -> ReplayMidiInput | ReplayMidiOutput:
        """Make a stand-in for a MIDI port the recording held as it began, asking no answer.

        As ``adopt_device`` does for a joystick: an instant replay's playback scope adopts its
        journal's ports (``MidiEventManager.adopt_midi_ports``). A later open of the port, or a
        lookup by its id, finds this stand-in.

        Args:
            descriptor: The port.

        Returns:
            The stand-in: a ``ReplayMidiInput`` or a ``ReplayMidiOutput``, by its kind.

        """
        if descriptor.kind == MIDI_INPUT_KIND:
            midi_input = self._new_midi_input(descriptor=descriptor)
            self._midi_inputs[descriptor.port_id] = midi_input
            return midi_input
        midi_output = ReplayMidiOutput(descriptor=descriptor)
        self._midi_outputs[descriptor.port_id] = midi_output
        return midi_output

    def descriptor_for_instance(self: Self, *, instance_id: int) -> DeviceDescriptor | None:
        """Return the recorded descriptor of an opened stand-in by instance id, or None.

        Args:
            instance_id: The recorded SDL instance id.

        Returns:
            The descriptor it was opened with (a game controller's controller one).

        """
        return self._opened_descriptors_by_instance.get(instance_id)

    def forget_device(self: Self, *, instance_id: int) -> None:
        """Forget a removed stand-in, as live play forgets the device (replayed removal events).

        Args:
            instance_id: The recorded SDL instance id.

        """
        self._opened_by_instance.pop(instance_id, None)
        self._opened_descriptors_by_instance.pop(instance_id, None)

    def take_opened_descriptors(self: Self) -> list[DeviceDescriptor]:
        """Return the descriptors learned from the recording since the last call, once each.

        A recording made over a replay (--rebaseline) writes them in the same frames.

        Returns:
            The descriptors, in the order learned.

        """
        descriptors, self._learned_descriptors = self._learned_descriptors, []
        return descriptors

    def take_opened_midi_ports(self: Self) -> list[MidiPortDescriptor]:
        """Return the MIDI ports learned from the recording since the last call, once each.

        Returns:
            The descriptors, in the order learned.

        """
        descriptors, self._learned_midi_ports = self._learned_midi_ports, []
        return descriptors

    def take_enumeration_answers(self: Self) -> list[EnumerationAnswer]:
        """A rebaseline copies answers from the source recording (Task 12), not from here.

        Returns:
            An empty list.

        """
        return []

    def _first_midi_port_id(self: Self, *, is_input: bool) -> int:
        for port_id, port in enumerate(self._midi_ports):
            if port.is_input if is_input else port.is_output:
                return port_id
        return NO_MIDI_PORT_ID

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

        Only the fallback for calls without a recorded answer (each of which already warned, or
        an open recorded before opens were answers): it describes the next unopened device at
        that index.

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

        Once a call's recorded answers are used up, the last one repeats, a recorded error
        included (so a device count asked every frame stays constant). Asking more often than
        the recording did only happens after a replay has already diverged.

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
            # Told as live play tells its answers (an instant-replay journal of a replayed
            # session keeps them)
            notify_device_answer(answer=answer, opened=None)
            if answer.error is not None:
                raise pygame.error(answer.error)
            return answer.value
        notify_device_answer(
            answer=EnumerationAnswer(call=call, device_index=device_index, value=fallback),
            opened=None,
        )
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

    def _midi_port_to_open(self: Self, *, call: str, kind: str, port_id: int) -> MidiPortDescriptor:
        """Return the recorded port an open of ``port_id`` gets, raising a recorded failure again.

        The port is the recording's, else the one ``_midi_ports`` lists at that position (the
        stand-in registry's), else a named stand-in with a warning.

        Returns:
            The descriptor.

        Raises:
            pygame.error: If the recorded open failed.

        """
        answer = self._next_answer(call=call, device_index=port_id)
        if answer is not None and answer.error is not None:
            notify_device_answer(answer=answer, opened=None)
            raise pygame.error(answer.error)
        descriptor = self._recorded_midi_ports.get((kind, port_id))
        if descriptor is None and 0 <= port_id < len(self._midi_ports):
            port = self._midi_ports[port_id]
            descriptor = MidiPortDescriptor(
                kind=kind, port_id=port_id, name=port.name, interface=port.interface
            )
        if descriptor is None:
            LOG.warning('MIDI port %d is not in the recording; using a named stand-in', port_id)
            descriptor = MidiPortDescriptor(
                kind=kind,
                port_id=port_id,
                name=f'Unrecorded MIDI port {port_id}',
                interface='Unrecorded',
            )
        notify_device_answer(
            answer=EnumerationAnswer(call=call, device_index=port_id, value=port_id),
            opened=descriptor,
        )
        return descriptor

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
            notify_device_answer(answer=answer, opened=None)
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
        notify_device_answer(
            answer=EnumerationAnswer(
                call=call, device_index=device_index, value=descriptor.instance_id
            ),
            opened=descriptor,
        )
        return descriptor


def find_midi_port(*, devices: DeviceRegistry, name: str, kind: str) -> int | None:
    """Return the id of the first MIDI port with this name that fits ``kind``.

    Args:
        devices: The devices door.
        name: The port name to find.
        kind: ``MIDI_INPUT_KIND`` (a port the game reads) or ``MIDI_OUTPUT_KIND`` (one it writes).

    Returns:
        The port id, or None when no port matches.

    """
    found = find_midi_port_with_info(devices=devices, name=name, kind=kind)
    return None if found is None else found[0]


def find_midi_port_with_info(
    *, devices: DeviceRegistry, name: str, kind: str
) -> tuple[int, MidiPortInfo] | None:
    """Return the id and PortMidi's description of the first port with this name that fits ``kind``.

    Args:
        devices: The devices door.
        name: The port name to find.
        kind: ``MIDI_INPUT_KIND`` (a port the game reads) or ``MIDI_OUTPUT_KIND`` (one it writes).

    Returns:
        The port id and its info, or None when no port matches.

    Raises:
        ValueError: If ``kind`` is neither ``MIDI_INPUT_KIND`` nor ``MIDI_OUTPUT_KIND``.

    """
    if kind not in {MIDI_INPUT_KIND, MIDI_OUTPUT_KIND}:
        message = f'kind must be {MIDI_INPUT_KIND!r} or {MIDI_OUTPUT_KIND!r}, not {kind!r}'
        raise ValueError(message)
    for port_id in range(devices.midi_port_count()):
        info = devices.midi_port_info(port_id=port_id)
        if info is None or info.name != name:
            continue
        if info.is_input if kind == MIDI_INPUT_KIND else info.is_output:
            return port_id, info
    return None
