"""Stand-in joysticks and game controllers, served through the real devices door.

A stand-in device exists only in the run that installs it: no hardware is opened. The doors
(``StandInDeviceSources``) are live in every other way, and serve the replay stand-ins
(``ReplayJoystick``, ``ReplayController``, glitchygames/input/devices.py) from a
``StandInDeviceRegistry``: the objects a replay hands the engine. The enumeration answers are
the ones SDL gives for the devices: every device is counted as a joystick and as a possible
controller (pygame's controller count is SDL's joystick count), and ``is_controller`` says
which are mapped game controllers.

A stand-in's positions are read from the frame's snapshot, as a replay's are, so a run that
moves one posts its events and lays them into the snapshot (the scripted-session recorder's
``PostedPolledInput``, glitchygames/replay/tools/scripted_sessions.py).

Unlike a replay's registry, a stand-in registry is live input to a recorder: it hands the
devices it opened and the answers it gave to ``take_opened_descriptors`` and
``take_enumeration_answers``, as ``LiveDeviceRegistry`` does, so a recording made with
stand-ins (``--record-trace``, a scripted session) holds them in its header and frames, and
its replay opens the same devices.

Used by the tests (tests/input/stand_in_devices.py names their descriptors) and by the
golden-trace harness's engine (``GoldenTraceEngine(stand_in_devices=...)``,
glitchygames/replay/tools/golden_traces.py), so a scripted session can record a game played
on a pad no machine has. Moved here from tests/input/stand_in_devices.py (Arcade sub-plan 2,
Task 1).
"""

from __future__ import annotations

import collections
from typing import TYPE_CHECKING, Any, Self, override

from glitchygames.checks import required
from glitchygames.input.devices import (
    CONTROLLER_COUNT_CALL,
    CONTROLLER_KIND,
    DEFAULT_MIDI_INPUT_CALL,
    DEFAULT_MIDI_OUTPUT_CALL,
    IS_CONTROLLER_CALL,
    JOYSTICK_COUNT_CALL,
    MIDI_PORT_COUNT_CALL,
    MIDI_PORT_INFO_CALL,
    NAME_FOR_INDEX_CALL,
    DeviceDescriptor,
    EnumerationAnswer,
    EnumerationValue,
    MidiInputReader,
    MidiPortDescriptor,
    MidiPortInfo,
    ReplayDeviceRegistry,
    ReplayMidiInput,
    import_midi_module,
)
from glitchygames.live_sources import LiveSources
from glitchygames.sources import install_sources

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pygame

    from glitchygames.audio.accounting import AudioFrameAccount
    from glitchygames.scenes import Scene
    from glitchygames.supervision import ControlEvent

# The master seed of the doors ``install_stand_in_devices`` installs (a test's doors: nothing
# it runs draws from them unless the test says so)
STAND_IN_DOORS_RANDOM_SEED = 1
# What a failing stand-in MIDI port says (PortMidi's own text for a vanished device)
FAILING_PORT_MESSAGE = 'Host error'


class StandInMidiInput(ReplayMidiInput):
    """A stand-in MIDI input port that holds the messages a test queued for it.

    Its ``poll`` and ``read`` behave as ``pygame.midi.Input``'s do: ``read`` returns up to
    ``num_events`` messages, ``[[status, data1, data2, data3], timestamp]``, oldest first.
    """

    def __init__(
        self: Self,
        *,
        descriptor: MidiPortDescriptor,
        pending: collections.deque[tuple[list[int], int]],
        failing_port_ids: set[int],
    ) -> None:
        """Hold the queue the registry keeps for this port.

        Args:
            descriptor: The port.
            pending: The queued messages (shared with the registry, which fills it).
            failing_port_ids: The ports whose reads raise (shared with the registry).

        """
        super().__init__(descriptor=descriptor)
        self._pending = pending
        self._failing_port_ids = failing_port_ids

    @override
    def poll(self: Self) -> bool:
        """Say whether messages are waiting.

        A port made to fail (``fail_midi_input``) raises ``pygame.midi.MidiException`` here.

        Returns:
            True when a message is queued.

        """
        self._raise_when_failing()
        return bool(self._pending)

    @override
    def read(self: Self, num_events: int) -> list[Any]:
        """Return up to ``num_events`` queued messages, oldest first.

        Returns:
            The messages.

        """
        self._raise_when_failing()
        count = min(num_events, len(self._pending))
        return [self._pending.popleft() for _ in range(count)]

    def _raise_when_failing(self: Self) -> None:
        if self.descriptor.port_id in self._failing_port_ids:
            midi_module = required(import_midi_module(log_unavailable=False), what='pygame.midi')
            raise midi_module.MidiException(FAILING_PORT_MESSAGE)


class StandInDeviceRegistry(ReplayDeviceRegistry):
    """A replay registry of stand-ins that tells a recorder what it opened and answered.

    It answers and opens exactly as ``ReplayDeviceRegistry`` does, and also keeps each answer
    and each opened device's descriptor until a recorder takes them (or the frame ends without
    one: ``discard_untaken``), as ``LiveDeviceRegistry`` keeps a real device's.
    """

    def __init__(
        self: Self,
        *,
        descriptors: list[DeviceDescriptor],
        enumeration_answers: list[EnumerationAnswer],
        midi_ports: Sequence[MidiPortInfo] = (),
    ) -> None:
        """Index the stand-ins and queue their answers, with nothing given yet.

        Args:
            descriptors: The stand-in devices.
            enumeration_answers: The answers SDL would give for them.
            midi_ports: The MIDI ports PortMidi would list, a port's id being its position. The
                MIDI answers come from them (the first input and the first output port are the
                defaults), unless ``enumeration_answers`` records others.

        """
        super().__init__(descriptors=descriptors, enumeration_answers=enumeration_answers)
        # What the replay registry's MIDI calls answer when nothing is recorded for them
        self._midi_ports = tuple(midi_ports)
        self._given_answers: list[EnumerationAnswer] = []
        self._opened_descriptors: list[DeviceDescriptor] = []
        self._opened_midi_ports: list[MidiPortDescriptor] = []
        # MIDI messages queued per port id, and the ports that fail when read
        self._pending_midi_messages: dict[int, collections.deque[tuple[list[int], int]]] = {}
        self._failing_midi_port_ids: set[int] = set()
        self._midi_input_reader = MidiInputReader()

    @override
    def joystick_count(self: Self) -> int:
        """Answer as the replay registry does, and keep the answer for the recorder.

        Returns:
            The count.

        """
        count = super().joystick_count()
        self._keep_answer(call=JOYSTICK_COUNT_CALL, device_index=None, value=count)
        return count

    @override
    def controller_count(self: Self) -> int:
        """Answer as the replay registry does, and keep the answer for the recorder.

        Returns:
            The count.

        """
        count = super().controller_count()
        self._keep_answer(call=CONTROLLER_COUNT_CALL, device_index=None, value=count)
        return count

    @override
    def is_controller(self: Self, *, device_index: int) -> bool:
        """Answer as the replay registry does, and keep the answer for the recorder.

        Args:
            device_index: The SDL device index.

        Returns:
            True for a game controller.

        """
        flag = super().is_controller(device_index=device_index)
        self._keep_answer(call=IS_CONTROLLER_CALL, device_index=device_index, value=flag)
        return flag

    @override
    def name_for_index(self: Self, *, device_index: int) -> str | None:
        """Answer as the replay registry does, and keep the answer for the recorder.

        Args:
            device_index: The SDL device index.

        Returns:
            The name, or None.

        """
        name = super().name_for_index(device_index=device_index)
        self._keep_answer(call=NAME_FOR_INDEX_CALL, device_index=device_index, value=name)
        return name

    @override
    def midi_port_count(self: Self) -> int:
        """Answer with the stand-in ports' count, and keep the answer for the recorder.

        Returns:
            The count.

        """
        count = super().midi_port_count()
        self._keep_answer(call=MIDI_PORT_COUNT_CALL, device_index=None, value=count)
        return count

    @override
    def midi_port_info(self: Self, *, port_id: int) -> MidiPortInfo | None:
        """Answer with the stand-in port ``port_id``, and keep the answer for the recorder.

        Args:
            port_id: The port's position in ``midi_ports``.

        Returns:
            The port, or None when there is no such port.

        """
        info = super().midi_port_info(port_id=port_id)
        self._keep_answer(
            call=MIDI_PORT_INFO_CALL,
            device_index=port_id,
            value=None if info is None else info.to_answer_value(),
        )
        return info

    @override
    def default_midi_input_id(self: Self) -> int:
        """Answer with the first stand-in input port, and keep the answer for the recorder.

        Returns:
            The port id, -1 when no stand-in port is an input.

        """
        port_id = super().default_midi_input_id()
        self._keep_answer(call=DEFAULT_MIDI_INPUT_CALL, device_index=None, value=port_id)
        return port_id

    @override
    def default_midi_output_id(self: Self) -> int:
        """Answer with the first stand-in output port, and keep the answer for the recorder.

        Returns:
            The port id, -1 when no stand-in port is an output.

        """
        port_id = super().default_midi_output_id()
        self._keep_answer(call=DEFAULT_MIDI_OUTPUT_CALL, device_index=None, value=port_id)
        return port_id

    @override
    def _descriptor_to_open(
        self: Self, *, call: str, device_index: int, kind: str
    ) -> DeviceDescriptor:
        """Pick the stand-in an open gets, as the replay registry does, and keep it.

        Both opens (``open_joystick``, ``open_controller``) learn their device here, so this
        is the one place a stand-in opened is kept for the recorder, with the open's answer
        (its instance id), as ``LiveDeviceRegistry`` keeps a real device it opened.

        Args:
            call: ``OPEN_JOYSTICK_CALL`` or ``OPEN_CONTROLLER_CALL``.
            device_index: The SDL device index.
            kind: The kind of device opened.

        Returns:
            The descriptor.

        """
        descriptor = super()._descriptor_to_open(call=call, device_index=device_index, kind=kind)
        self._opened_descriptors.append(descriptor)
        self._keep_answer(call=call, device_index=device_index, value=descriptor.instance_id)
        return descriptor

    @override
    def _midi_port_to_open(self: Self, *, call: str, kind: str, port_id: int) -> MidiPortDescriptor:
        """Pick the stand-in port an open gets, as the replay registry does, and keep it.

        Both opens (``open_midi_input``, ``open_midi_output``) learn their port here, so this is
        the one place a stand-in port opened is kept for the recorder, with the open's answer
        (its port id), as ``LiveDeviceRegistry`` keeps a real port it opened.

        Args:
            call: ``OPEN_MIDI_INPUT_CALL`` or ``OPEN_MIDI_OUTPUT_CALL``.
            kind: ``MIDI_INPUT_KIND`` or ``MIDI_OUTPUT_KIND``.
            port_id: The port's position in ``midi_ports``.

        Returns:
            The descriptor.

        """
        descriptor = super()._midi_port_to_open(call=call, kind=kind, port_id=port_id)
        self._opened_midi_ports.append(descriptor)
        self._keep_answer(call=call, device_index=port_id, value=port_id)
        return descriptor

    @override
    def _new_midi_input(self: Self, *, descriptor: MidiPortDescriptor) -> ReplayMidiInput:
        """Return a stand-in input that serves the messages queued for its port.

        Returns:
            The stand-in.

        """
        return StandInMidiInput(
            descriptor=descriptor,
            pending=self._pending_for(port_id=descriptor.port_id),
            failing_port_ids=self._failing_midi_port_ids,
        )

    def _pending_for(self: Self, *, port_id: int) -> collections.deque[tuple[list[int], int]]:
        return self._pending_midi_messages.setdefault(port_id, collections.deque())

    def queue_midi_input(
        self: Self, *, port_id: int, messages: Sequence[tuple[list[int], int]]
    ) -> None:
        """Queue MIDI messages a port will hand the frame once it is opened and read.

        Args:
            port_id: The port's position in ``midi_ports``.
            messages: PortMidi's messages: ``([status, data1, data2, data3], timestamp)``.

        """
        self._pending_for(port_id=port_id).extend(messages)

    def fail_midi_input(self: Self, *, port_id: int) -> None:
        """Make a port raise ``pygame.midi.MidiException`` whenever it is read.

        Args:
            port_id: The port's position in ``midi_ports``.

        """
        self._failing_midi_port_ids.add(port_id)

    def read_midi_input(self: Self) -> list[pygame.event.Event]:
        """Return the MIDIIN events the opened stand-in input ports hold, as the live registry does.

        Returns:
            The events (``vice_id`` is the port id).

        """
        midi_module = import_midi_module(log_unavailable=False)
        if midi_module is None:  # pragma: no cover - a pygame build without PortMidi
            return []
        return self._midi_input_reader.read(
            midi_module=midi_module,
            inputs=self._midi_inputs,
            port_name=lambda port_id: self._midi_inputs[port_id].descriptor.name,
        )

    @override
    def take_opened_midi_ports(self: Self) -> list[MidiPortDescriptor]:
        """Return the stand-in MIDI ports opened since the last call (the recorder's).

        Returns:
            The descriptors, in opening order.

        """
        descriptors, self._opened_midi_ports = self._opened_midi_ports, []
        return descriptors

    @override
    def take_opened_descriptors(self: Self) -> list[DeviceDescriptor]:
        """Return the stand-ins opened since the last call (the recorder's).

        Returns:
            The descriptors, in opening order.

        """
        descriptors, self._opened_descriptors = self._opened_descriptors, []
        return descriptors

    @override
    def take_enumeration_answers(self: Self) -> list[EnumerationAnswer]:
        """Return the answers given since the last call (the recorder's).

        Returns:
            The answers, in the order given.

        """
        answers, self._given_answers = self._given_answers, []
        return answers

    def discard_untaken(self: Self) -> None:
        """Drop the answers and descriptors nobody took this frame (``StandInDeviceSources``).

        As ``LiveDeviceRegistry.discard_untaken``: without a recorder nothing takes them, and
        they would pile up for the whole run.
        """
        self._given_answers.clear()
        self._opened_descriptors.clear()
        self._opened_midi_ports.clear()

    def _keep_answer(
        self: Self, *, call: str, device_index: int | None, value: EnumerationValue
    ) -> None:
        self._given_answers.append(
            EnumerationAnswer(call=call, device_index=device_index, value=value)
        )


class StandInDeviceSources(LiveSources):
    """Live doors whose devices are a stand-in registry's (no hardware)."""

    def __init__(self: Self, *, registry: StandInDeviceRegistry, **live_options: Any) -> None:
        """Create the doors around the registry.

        Args:
            registry: The stand-in devices.
            **live_options: The live doors' options (``LiveSources``: ``random_seed`` and the
                others), by keyword.

        """
        super().__init__(**live_options)
        self.registry = registry

    @override
    def devices(self: Self) -> StandInDeviceRegistry:
        """Return the stand-in devices.

        Returns:
            The registry.

        """
        return self.registry

    @override
    def end_frame(
        self: Self,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
        processing_seconds: float | None = None,
        audio_frame: AudioFrameAccount | None = None,
    ) -> None:
        """End the frame as the live doors do, discarding what no recorder took of the stand-ins.

        A recorder (``RecordingSources``) takes the stand-ins' answers before this runs.
        """
        super().end_frame(
            frame_number=frame_number,
            dt=dt,
            scene=scene,
            control_events=control_events,
            processing_seconds=processing_seconds,
            audio_frame=audio_frame,
        )
        self.registry.discard_untaken()


def stand_in_registry(
    *,
    descriptors: Sequence[DeviceDescriptor],
    plugged_in_at_start: bool = True,
    midi_ports: Sequence[MidiPortInfo] = (),
) -> StandInDeviceRegistry:
    """Return a registry of stand-in devices, answering enumeration as SDL would for them.

    Args:
        descriptors: The devices; a CONTROLLER_KIND one is a mapped game controller.
        plugged_in_at_start: False counts no devices (they are to be hot-plugged).
        midi_ports: The MIDI ports PortMidi would list (a port's id is its position).

    Returns:
        The registry.

    """
    device_count = len(descriptors) if plugged_in_at_start else 0
    answers = [
        EnumerationAnswer(call=JOYSTICK_COUNT_CALL, device_index=None, value=device_count),
        EnumerationAnswer(call=CONTROLLER_COUNT_CALL, device_index=None, value=device_count),
    ]
    answers.extend(
        EnumerationAnswer(
            call=IS_CONTROLLER_CALL,
            device_index=descriptor.device_index,
            value=descriptor.kind == CONTROLLER_KIND,
        )
        for descriptor in descriptors
    )
    return StandInDeviceRegistry(
        descriptors=list(descriptors), enumeration_answers=answers, midi_ports=midi_ports
    )


def install_stand_in_devices(
    *,
    descriptors: Sequence[DeviceDescriptor],
    plugged_in_at_start: bool = True,
    midi_ports: Sequence[MidiPortInfo] = (),
) -> StandInDeviceRegistry:
    """Install doors whose devices are stand-ins (see ``stand_in_registry``).

    Args:
        descriptors: The devices; a CONTROLLER_KIND one is a mapped game controller.
        plugged_in_at_start: False counts no devices (they are to be hot-plugged).
        midi_ports: The MIDI ports PortMidi would list (a port's id is its position).

    Returns:
        The installed registry.

    """
    registry = stand_in_registry(
        descriptors=descriptors, plugged_in_at_start=plugged_in_at_start, midi_ports=midi_ports
    )
    install_sources(
        sources=StandInDeviceSources(registry=registry, random_seed=STAND_IN_DOORS_RANDOM_SEED)
    )
    return registry
