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

from typing import TYPE_CHECKING, Any, Self, override

from glitchygames.input.devices import (
    CONTROLLER_COUNT_CALL,
    CONTROLLER_KIND,
    IS_CONTROLLER_CALL,
    JOYSTICK_COUNT_CALL,
    NAME_FOR_INDEX_CALL,
    DeviceDescriptor,
    EnumerationAnswer,
    EnumerationValue,
    ReplayDeviceRegistry,
)
from glitchygames.live_sources import LiveSources
from glitchygames.sources import install_sources

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.audio.accounting import AudioFrameAccount
    from glitchygames.scenes import Scene
    from glitchygames.supervision import ControlEvent

# The master seed of the doors ``install_stand_in_devices`` installs (a test's doors: nothing
# it runs draws from them unless the test says so)
STAND_IN_DOORS_RANDOM_SEED = 1


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
    ) -> None:
        """Index the stand-ins and queue their answers, with nothing given yet.

        Args:
            descriptors: The stand-in devices.
            enumeration_answers: The answers SDL would give for them.

        """
        super().__init__(descriptors=descriptors, enumeration_answers=enumeration_answers)
        self._given_answers: list[EnumerationAnswer] = []
        self._opened_descriptors: list[DeviceDescriptor] = []

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
    *, descriptors: Sequence[DeviceDescriptor], plugged_in_at_start: bool = True
) -> StandInDeviceRegistry:
    """Return a registry of stand-in devices, answering enumeration as SDL would for them.

    Args:
        descriptors: The devices; a CONTROLLER_KIND one is a mapped game controller.
        plugged_in_at_start: False counts no devices (they are to be hot-plugged).

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
    return StandInDeviceRegistry(descriptors=list(descriptors), enumeration_answers=answers)


def install_stand_in_devices(
    *, descriptors: Sequence[DeviceDescriptor], plugged_in_at_start: bool = True
) -> StandInDeviceRegistry:
    """Install doors whose devices are stand-ins (see ``stand_in_registry``).

    Args:
        descriptors: The devices; a CONTROLLER_KIND one is a mapped game controller.
        plugged_in_at_start: False counts no devices (they are to be hot-plugged).

    Returns:
        The installed registry.

    """
    registry = stand_in_registry(descriptors=descriptors, plugged_in_at_start=plugged_in_at_start)
    install_sources(
        sources=StandInDeviceSources(registry=registry, random_seed=STAND_IN_DOORS_RANDOM_SEED)
    )
    return registry
