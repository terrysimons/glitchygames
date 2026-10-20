"""Exact replay of a ``--record-trace`` recording through the real engine (``--replay-trace``).

``ReplaySources`` are the doors (glitchygames/sources.py) a replay installs: everything the
recorded run took in is served from the recording, so the real engine and game code run the
session again, and every frame's sprites are compared with the recorded frame. The rules
(plans/2026-10-19-gameplay-replay.md, sections 3.1-3.3):

1. Startup, in one place (``GameEngine.__init__``): once the options are parsed,
   ``start_replay`` reads the recording, refuses a recording of another game
   (``ReplayRefusedError``; the engine logs it and exits with ``REPLAY_UNUSABLE_EXIT_CODE``, as
   for an unreadable file), warns once about a different engine version, applies the recorded
   options (all but ``REPLAY_LOCAL_OPTIONS``) and seeds the random streams with the recorded
   seed. The engine installs the sources before the first frame; while installed they own the
   internal-post tracker (glitchygames/recording.py).
2. Pump: the real queue is drained (through the live doors' pump) and its external events are
   dropped, except the window's QUIT, kept last so closing the window ends the replay. The
   recording's external events for this pump are served, then the live internal events (which
   the replayed code posted again). Task 13 of the core plan makes the merge exact.
3. Frame indexes: the sources count their own ``end_frame`` calls; every recorded frame they
   serve is picked by that count, never by the scene manager's frame number.
4. Frame time: the current frame's recorded ``dt``; past the end, the measurement.
5. Input: the frame's snapshot, rebuilt by applying each frame's ``input_changes`` in order
   (a version-2 recording has none: polled input reads as idle, with one warning).
6. Devices: a ``ReplayDeviceRegistry`` from the header, learning each frame's opened devices
   and enumeration answers when the frame begins (before any open in it is answered).
7. Saves: a ``MemorySaveManager`` per namespace, seeded from the header's ``saves`` or the
   frame's ``saves_opened`` (an unknown namespace gets an empty store); real saves are never
   touched.
8. End of frame: the scene's sprites are sampled as the recorder samples them and compared
   with the recorded frame (scene class, then each sprite: present, ``rect``, ``visible``);
   the first difference stops the replay, as does the last recorded frame.
9. Clocks: the wall clock is the recording's ``recorded_at`` plus the frame clock; elapsed
   seconds are the frame clock.
10. ``recorded_frame_fields`` hands a recording made over the replay (Part 2's rebaseline) the
    frame's recorded saves and device fields.
11. ``GameEngine._shutdown`` calls ``finish_run`` and logs the result.
"""

from __future__ import annotations

import dataclasses
import importlib.metadata
import logging
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

import pygame

from glitchygames.input.devices import DeviceDescriptor, EnumerationAnswer, ReplayDeviceRegistry
from glitchygames.input.state import IDLE_INPUT, apply_snapshot_changes
from glitchygames.live_sources import LiveSources
from glitchygames.randomness import seed_engine_random
from glitchygames.recording import (
    CONTROL_EVENTS_FIELD,
    DEVICE_ENUMERATION_FIELD,
    DEVICES_HEADER_FIELD,
    DEVICES_OPENED_FIELD,
    DT_FIELD,
    EVENT_BATCHES_FIELD,
    EVENT_ORIGIN_FIELD,
    EXTERNAL_ORIGIN,
    INPUT_CHANGES_FIELD,
    INTERNAL_ORIGIN,
    SAVES_HEADER_FIELD,
    SAVES_OPENED_FIELD,
    event_from_record,
    event_origin,
    pending_internal_posts,
    start_tracking_internal_posts,
    stop_tracking_internal_posts,
    value_from_json,
)
from glitchygames.sources import frame_clock_seconds
from glitchygames.state.sandbox import MemorySaveManager
from glitchygames.supervision import KIND_FIELD, REAPPLIED_CONTROL_EVENT_KINDS, ControlEvent
from glitchygames.tracing import (
    FRAMES_FIELD,
    RECT_FIELD,
    SCENE_FIELD,
    SPRITE_ID_FIELD,
    SPRITES_FIELD,
    TRACE_FORMAT_VERSION,
    StableSpriteIds,
    TraceFormatError,
    read_trace_result,
    sample_scene_frame,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from glitchygames.input.state import InputSnapshot
    from glitchygames.scenes import Scene
    from glitchygames.state.manager import SaveManager

LOG = logging.getLogger('game.replay')
LOG.addHandler(logging.NullHandler())

# Exit status when a recording cannot be replayed (wrong game, unreadable file)
REPLAY_UNUSABLE_EXIT_CODE = 2

# Options the recording never overrides: how this run is watched, logged, paced and recorded,
# not what the game does
REPLAY_LOCAL_OPTIONS: frozenset[str] = frozenset({
    'replay_trace',
    'record_trace',
    'audit',
    'replay_digest',
    'headless',
    'rebaseline',
    'replay_pause_at_frame',
    'profile',
    'log_level',
    'windowed',
    'video_driver',
    'debug_overlay',
    'log_timer_jitter',
    'timer_backend',
    'sleep_granularity_ns',
    'windows_timer_1ms',
    'perf_trim_percent',
    'fps_histogram',
    # Derived from log_level: whether events are logged, not what the game does
    'debug_events',
})

# Divergence kinds
SPRITE_DIVERGENCE = 'sprite'
SCENE_DIVERGENCE = 'scene'
EVENT_DIVERGENCE = 'event'
LENGTH_DIVERGENCE = 'length'

# ReplayResult.end_reason values
RUNNING_END_REASON = 'running'
END_OF_RECORDING_END_REASON = 'end_of_recording'
DIVERGED_END_REASON = 'diverged'
TRUNCATED_END_REASON = 'truncated'
QUIT_END_REASON = 'quit'

# Divergence subjects and fields that are not a sprite id or a sprite field
SCENE_SUBJECT = 'scene'
SCENE_CLASS_FIELD = 'class'
PRESENT_FIELD = 'present'
VISIBLE_FIELD = 'visible'
RECORDING_SUBJECT = 'recording'
FRAME_COUNT_FIELD = 'frames'

# Header fields the replay reads
GAME_CLASS_HEADER_FIELD = 'game_class'
RANDOM_SEED_HEADER_FIELD = 'random_seed'
RECORDED_AT_HEADER_FIELD = 'recorded_at'
ENGINE_VERSION_HEADER_FIELD = 'engine_version'
OPTIONS_HEADER_FIELD = 'options'

# The frame fields a recording made over a replay copies from it (recorded_frame_fields)
REBASELINE_FRAME_FIELDS = (SAVES_OPENED_FIELD, DEVICES_OPENED_FIELD, DEVICE_ENUMERATION_FIELD)

VERSION_TWO_INPUT_WARNING = (
    'The recording is format version %d, recorded before input-state capture; polled input '
    'will read as idle'
)


class ReplayRefusedError(RuntimeError):
    """The recording cannot be replayed by this game (a recording of another game)."""


@dataclasses.dataclass(frozen=True)
class Divergence:
    """The first difference between the replay and the recording.

    Attributes:
        frame_number: The recording's frame index.
        kind: ``SCENE_DIVERGENCE``, ``SPRITE_DIVERGENCE``, ``EVENT_DIVERGENCE`` or
            ``LENGTH_DIVERGENCE``.
        subject: What differed: a sprite id, ``'scene'`` or ``'recording'``.
        field: Which of its fields: ``'rect'``, ``'visible'``, ``'present'``, ``'class'``,
            ``'frames'``.
        expected: The recorded value.
        actual: The replayed value.

    """

    frame_number: int
    kind: str
    subject: str
    field: str
    expected: object
    actual: object

    def describe(self: Self) -> str:
        """Describe the divergence on one line.

        Returns:
            For example ``frame 6120: sprite Ball#2 rect expected [412, 300, 16, 16], got
            [412, 301, 16, 16]``, or for a different active scene ``frame 40: scene expected
            ArrivalScene, got PauseScene``.

        """
        if self.kind == SCENE_DIVERGENCE:
            return f'frame {self.frame_number}: scene expected {self.expected}, got {self.actual}'
        return (
            f'frame {self.frame_number}: {self.kind} {self.subject} {self.field} '
            f'expected {self.expected}, got {self.actual}'
        )


@dataclasses.dataclass
class ReplayResult:
    """How a replay went so far.

    Attributes:
        frames_replayed: How many recorded frames were run and compared.
        divergence: The first difference, or None.
        end_reason: ``'running'``, ``'end_of_recording'``, ``'diverged'``, ``'truncated'``
            (the last complete frame of a cut-off file was replayed) or ``'quit'`` (the
            window was closed).

    """

    frames_replayed: int = 0
    divergence: Divergence | None = None
    end_reason: str = RUNNING_END_REASON


def _recorded_start(*, header: dict[str, Any]) -> datetime:
    """Return the header's ``recorded_at`` as an aware datetime (UTC when it has no offset).

    Raises:
        TraceFormatError: If the header has no readable ``recorded_at``.

    """
    recorded_at = header.get(RECORDED_AT_HEADER_FIELD)
    if not isinstance(recorded_at, str):
        message = f'The recording header has no recorded_at start time (found {recorded_at!r})'
        raise TraceFormatError(message)
    try:
        start = datetime.fromisoformat(recorded_at)
    except ValueError as error:
        message = f'The recording header recorded_at {recorded_at!r} is not ISO 8601'
        raise TraceFormatError(message) from error
    return start if start.tzinfo is not None else start.replace(tzinfo=UTC)


def _recorded_seed(*, header: dict[str, Any]) -> int:
    """Return the header's ``random_seed``.

    Raises:
        TraceFormatError: If the header has no integer seed.

    """
    random_seed = header.get(RANDOM_SEED_HEADER_FIELD)
    if isinstance(random_seed, bool) or not isinstance(random_seed, int):
        message = f'The recording header has no integer random_seed (found {random_seed!r})'
        raise TraceFormatError(message)
    return random_seed


def _sprite_difference(
    *, frame_index: int, recorded: dict[str, Any], replayed: dict[str, Any]
) -> Divergence | None:
    """Return the first sprite difference between two sampled frames, or None.

    Recorded sprites are checked in recorded (draw) order: a missing one first, else its rect,
    then its visibility; then a replayed sprite the recording does not have.
    """
    replayed_by_id = {sprite[SPRITE_ID_FIELD]: sprite for sprite in replayed[SPRITES_FIELD]}
    recorded_ids: set[str] = set()
    for recorded_sprite in recorded[SPRITES_FIELD]:
        sprite_id = recorded_sprite[SPRITE_ID_FIELD]
        recorded_ids.add(sprite_id)
        replayed_sprite = replayed_by_id.get(sprite_id)
        if replayed_sprite is None:
            return Divergence(
                frame_number=frame_index,
                kind=SPRITE_DIVERGENCE,
                subject=sprite_id,
                field=PRESENT_FIELD,
                expected=True,
                actual=False,
            )
        for field_name in (RECT_FIELD, VISIBLE_FIELD):
            if recorded_sprite[field_name] != replayed_sprite[field_name]:
                return Divergence(
                    frame_number=frame_index,
                    kind=SPRITE_DIVERGENCE,
                    subject=sprite_id,
                    field=field_name,
                    expected=recorded_sprite[field_name],
                    actual=replayed_sprite[field_name],
                )
    for replayed_sprite in replayed[SPRITES_FIELD]:
        sprite_id = replayed_sprite[SPRITE_ID_FIELD]
        if sprite_id not in recorded_ids:
            return Divergence(
                frame_number=frame_index,
                kind=SPRITE_DIVERGENCE,
                subject=sprite_id,
                field=PRESENT_FIELD,
                expected=False,
                actual=True,
            )
    return None


def first_frame_difference(
    *, frame_index: int, recorded: dict[str, Any], replayed: dict[str, Any]
) -> Divergence | None:
    """Compare a replayed frame with the recorded one (scene class, then sprites).

    Args:
        frame_index: The recording's frame index.
        recorded: The recorded frame (decoded: every sprite listed).
        replayed: The replayed frame, sampled by ``sample_scene_frame``.

    Returns:
        The first difference, or None when the frames match.

    """
    if recorded[SCENE_FIELD] != replayed[SCENE_FIELD]:
        return Divergence(
            frame_number=frame_index,
            kind=SCENE_DIVERGENCE,
            subject=SCENE_SUBJECT,
            field=SCENE_CLASS_FIELD,
            expected=recorded[SCENE_FIELD],
            actual=replayed[SCENE_FIELD],
        )
    return _sprite_difference(frame_index=frame_index, recorded=recorded, replayed=replayed)


class ReplaySources:
    """The replay's doors (implements glitchygames.sources.EngineSources; module docstring).

    Attributes:
        header: The recording's header fields (without ``format_version`` and ``frames``).
        result: How the replay went so far.
        random_seed: The recorded master seed.

    """

    def __init__(
        self: Self,
        *,
        header: dict[str, Any],
        frames: Sequence[dict[str, Any]],
        format_version: int,
        is_truncated: bool = False,
        use_fastevents: bool = False,
    ) -> None:
        """Prepare to serve the recording from its first frame.

        Args:
            header: The header fields.
            frames: Every complete recorded frame, decoded (glitchygames/tracing.py).
            format_version: The file's format version (2 or 3).
            is_truncated: True when the file was cut off (a killed recorder): the replay then
                ends with ``'truncated'`` after the last complete frame.
            use_fastevents: Drain the real queue with pygame.fastevent when pygame has it
                (``GameEngine.USE_FASTEVENTS``), as the live doors would.

        """
        self.header = header
        self.result = ReplayResult()
        self.random_seed = _recorded_seed(header=header)
        self._recorded_at = _recorded_start(header=header)
        self._frames = frames
        self._is_truncated = is_truncated
        # Frames ended so far (end_frame calls): the index of the frame being served
        self._frame_index = 0
        # Pumps so far in the current frame: the index of the batch the next pump serves
        self._pump_index = 0
        self._stop_requested = False
        self._window_was_closed = False
        self._last_batch_origins: list[str] = []
        # Only its event pump is used: the one place the real queue is read (rule 2)
        self._live_queue = LiveSources(random_seed=self.random_seed, use_fastevents=use_fastevents)
        self._sprite_ids = StableSpriteIds()
        self._snapshot: InputSnapshot = IDLE_INPUT
        self._devices = ReplayDeviceRegistry(
            descriptors=[
                DeviceDescriptor.from_json(record)
                for record in header.get(DEVICES_HEADER_FIELD, [])
            ],
            enumeration_answers=[
                EnumerationAnswer.from_json(record)
                for record in header.get(DEVICE_ENUMERATION_FIELD, [])
            ],
        )
        # Namespace -> the recorded snapshot a store opened for it starts from
        self._save_snapshots: dict[str, dict[str, Any]] = dict(header.get(SAVES_HEADER_FIELD, {}))
        self._opened_save_namespaces: dict[str, MemorySaveManager] = {}
        if format_version < TRACE_FORMAT_VERSION:
            LOG.warning(VERSION_TWO_INPUT_WARNING, format_version)
        self._begin_frame()

    @classmethod
    def from_path(cls, *, path: Path, use_fastevents: bool = False) -> ReplaySources:
        """Read a recording file into replay sources.

        A file cut off part way (a killed recorder) replays up to its last complete frame. A
        file that is not a readable recording raises TraceFormatError (from reading it, or from
        a header without the seed or start time), a missing one OSError.

        Args:
            path: The recording.
            use_fastevents: Drain the real queue with pygame.fastevent (see ``__init__``).

        Returns:
            The sources.

        """
        read_result = read_trace_result(path=path)
        frames = read_result.trace[FRAMES_FIELD]
        is_truncated = not read_result.is_complete or read_result.dropped_partial_line is not None
        if is_truncated:
            LOG.warning(
                '%s is cut off after %d complete frames; replaying up to there',
                path,
                len(frames),
            )
        header = {name: value for name, value in read_result.trace.items() if name != FRAMES_FIELD}
        return cls(
            header=header,
            frames=frames,
            format_version=read_result.format_version,
            is_truncated=is_truncated,
            use_fastevents=use_fastevents,
        )

    @property
    def opened_save_namespaces(self: Self) -> Mapping[str, SaveManager]:
        """Every memory store opened so far, by namespace (read-only)."""
        return MappingProxyType(self._opened_save_namespaces)

    @property
    def frame_count(self: Self) -> int:
        """How many complete frames the recording holds."""
        return len(self._frames)

    @property
    def stop_requested(self: Self) -> bool:
        """True once the replay diverged, reached its last frame, or the window was closed."""
        return self._stop_requested

    def check_game(self: Self, *, game_class_name: str) -> None:
        """Refuse a recording of another game.

        Args:
            game_class_name: The class name of the game being started.

        Raises:
            ReplayRefusedError: If the recording's ``game_class`` is a different game.

        """
        recorded_game = self.header.get(GAME_CLASS_HEADER_FIELD)
        if recorded_game != game_class_name:
            message = (
                f'The recording is of the game {recorded_game!r}, not {game_class_name!r}; '
                'refusing to replay it'
            )
            raise ReplayRefusedError(message)

    def on_installed(self: Self) -> None:
        """Own the internal-post tracker while installed (internal events pass through)."""
        start_tracking_internal_posts()

    def on_uninstalled(self: Self) -> None:
        """Give up the internal-post tracker."""
        stop_tracking_internal_posts()

    def pump_events(
        self: Self, *, real_events: list[pygame.event.Event] | None = None
    ) -> list[pygame.event.Event]:
        """Serve the recording's batch for this pump, plus live internal events (rule 2).

        Args:
            real_events: The real batch to filter instead of draining the real queue (a Part 3
                playback scope passes the base pump's batch).

        Returns:
            The recorded external events, then the live internal events, then the window's
            QUIT if it was closed.

        """
        live_events = self._live_queue.pump_events() if real_events is None else real_events
        pending = pending_internal_posts()
        passed_through: list[pygame.event.Event] = []
        window_closes: list[pygame.event.Event] = []
        for event in live_events:
            if event_origin(event=event, pending=pending) == INTERNAL_ORIGIN:
                passed_through.append(event)
            elif event.type == pygame.QUIT:
                window_closes.append(event)
            # Every other real external event (keyboard, mouse, window, devices) is dropped
        # Posted but not returned: the queue was cleared or the type is blocked
        pending.clear()
        recorded_events = [event_from_record(record) for record in self._recorded_batch()]
        self._pump_index += 1
        if window_closes:
            self._window_was_closed = True
        self._last_batch_origins = [
            *[EXTERNAL_ORIGIN] * len(recorded_events),
            *[INTERNAL_ORIGIN] * len(passed_through),
            *[EXTERNAL_ORIGIN] * len(window_closes[-1:]),
        ]
        return [*recorded_events, *passed_through, *window_closes[-1:]]

    def last_batch_origins(self: Self) -> list[str]:
        """Return each event's origin in the batch the last pump returned.

        For a recording made over the replay (Part 2's rebaseline), which must record these
        rather than classify the batch with the internal-post tracker (the pump above has
        already consumed its pending posts). RecordingSources does not ask for them yet.

        Returns:
            ``'external'`` for served recorded events and a window close, ``'internal'`` for
            passed-through live events.

        """
        return list(self._last_batch_origins)

    def frame_seconds(self: Self, *, measured: float) -> float:
        """Return the current frame's recorded dt (rule 4).

        The scene manager asks before frame 0 and after each frame ends, so the first call
        returns frame 0's dt and each later call the next frame's.

        Args:
            measured: The measured start-to-start time.

        Returns:
            The recorded dt; ``measured`` past the end of the recording.

        """
        frame = self._current_frame()
        if frame is None:
            return measured
        return float(frame[DT_FIELD])

    def input_snapshot(self: Self) -> InputSnapshot:
        """Return the current frame's recorded polled input (rule 5).

        Returns:
            The snapshot (the last recorded one past the end).

        """
        return self._snapshot

    def devices(self: Self) -> ReplayDeviceRegistry:
        """Return the registry of recorded devices (rule 6).

        Returns:
            The registry.

        """
        return self._devices

    def saves(self: Self, *, namespace: str) -> SaveManager:
        """Open (or return the already opened) memory store for ``namespace`` (rule 7).

        Args:
            namespace: The game's app name.

        Returns:
            A MemorySaveManager seeded from the recorded snapshot (empty when the recording has
            none for ``namespace``).

        """
        store = self._opened_save_namespaces.get(namespace)
        if store is None:
            store = MemorySaveManager(
                app_name=namespace, snapshot=self._save_snapshots.get(namespace, {})
            )
            self._opened_save_namespaces[namespace] = store
        return store

    def wall_clock_time(self: Self) -> datetime:
        """Return the recording's start time plus the frame clock (rule 9).

        Returns:
            Timezone-aware time.

        """
        return self._recorded_at + timedelta(seconds=frame_clock_seconds())

    def elapsed_seconds(self: Self) -> float:
        """Return the frame clock (rule 9).

        Returns:
            Seconds.

        """
        return frame_clock_seconds()

    def control_events_for_frame(self: Self, *, frame_number: int) -> list[ControlEvent]:
        """Return the current frame's recorded supervisor actions, to apply again.

        Args:
            frame_number: The scene manager's frame number (not used to pick the frame: rule 3).

        Returns:
            The recorded control events whose kind is applied again, in order (markers the
            replayed code records by itself are left out).

        """
        del frame_number
        frame = self._current_frame()
        if frame is None:
            return []
        return [
            ControlEvent.from_json(record)
            for record in frame.get(CONTROL_EVENTS_FIELD, [])
            if record.get(KIND_FIELD) in REAPPLIED_CONTROL_EVENT_KINDS
        ]

    def end_frame(
        self: Self,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
    ) -> None:
        """Compare the frame with the recorded one, then move on to the next (rule 8).

        Args:
            frame_number: The scene manager's frame number (log messages only: rule 3).
            dt: The frame's raw dt.
            scene: The active scene at the end of the frame.
            control_events: The control events recorded in the frame.

        """
        # Task 13 compares the frame's markers; dt is the recorded one by construction
        del dt, control_events
        frame = self._current_frame()
        if frame is not None and not self._stop_requested:
            # Sampled exactly as the recorder samples a recorded frame
            replayed = sample_scene_frame(
                frame_number=self._frame_index, scene=scene, sprite_ids=self._sprite_ids
            )
            divergence = first_frame_difference(
                frame_index=self._frame_index, recorded=frame, replayed=replayed
            )
            self.result.frames_replayed = self._frame_index + 1
            if divergence is not None:
                LOG.debug(
                    'Replay diverged at recorded frame %d (run frame %d)',
                    divergence.frame_number,
                    frame_number,
                )
                self.result.divergence = divergence
                self._stop(end_reason=DIVERGED_END_REASON)
            elif self._frame_index == len(self._frames) - 1:
                self._stop(
                    end_reason=TRUNCATED_END_REASON
                    if self._is_truncated
                    else END_OF_RECORDING_END_REASON
                )
        if self._window_was_closed and not self._stop_requested:
            self._stop(end_reason=QUIT_END_REASON)
        self._frame_index += 1
        self._pump_index = 0
        self._begin_frame()

    def finish_run(self: Self) -> None:
        """Settle the result when the run ends (``GameEngine._shutdown``).

        A run that ended while the replay was still running (the game quit or failed before
        the recording's last frame) diverged in length.
        """
        if self.result.end_reason != RUNNING_END_REASON:
            return
        self.result.divergence = Divergence(
            frame_number=self.result.frames_replayed,
            kind=LENGTH_DIVERGENCE,
            subject=RECORDING_SUBJECT,
            field=FRAME_COUNT_FIELD,
            expected=len(self._frames),
            actual=self.result.frames_replayed,
        )
        self._stop(end_reason=DIVERGED_END_REASON)

    def recorded_frame_fields(self: Self, *, frame_index: int) -> dict[str, Any]:
        """Return the recorded frame's save and device fields (rule 10; a rebaseline copies them).

        Args:
            frame_index: The recording's frame index.

        Returns:
            Whichever of ``saves_opened``, ``devices_opened`` and ``device_enumeration`` the
            frame has.

        """
        frame = self._frames[frame_index]
        return {
            field_name: frame[field_name]
            for field_name in REBASELINE_FRAME_FIELDS
            if field_name in frame
        }

    def _current_frame(self: Self) -> dict[str, Any] | None:
        if self._frame_index < len(self._frames):
            return self._frames[self._frame_index]
        return None

    def _recorded_batch(self: Self) -> list[dict[str, Any]]:
        """Return the external records of the batch this pump serves (none past the end)."""
        frame = self._current_frame()
        if frame is None:
            return []
        batches = frame.get(EVENT_BATCHES_FIELD, [])
        if self._pump_index >= len(batches):
            return []
        return [
            record
            for record in batches[self._pump_index]
            if record.get(EVENT_ORIGIN_FIELD) == EXTERNAL_ORIGIN
        ]

    def _begin_frame(self: Self) -> None:
        """Learn what the current frame took in, before any of its doors are asked.

        Its opened devices and enumeration answers, its newly opened save namespaces, and its
        polled input (applied to the previous frame's snapshot).
        """
        frame = self._current_frame()
        if frame is None:
            return
        self._devices.add_descriptors(
            descriptors=[
                DeviceDescriptor.from_json(record) for record in frame.get(DEVICES_OPENED_FIELD, [])
            ]
        )
        self._devices.add_enumeration_answers(
            answers=[
                EnumerationAnswer.from_json(record)
                for record in frame.get(DEVICE_ENUMERATION_FIELD, [])
            ]
        )
        for namespace, snapshot in frame.get(SAVES_OPENED_FIELD, {}).items():
            self._save_snapshots.setdefault(namespace, snapshot)
        self._snapshot = apply_snapshot_changes(
            previous=self._snapshot, changes=frame.get(INPUT_CHANGES_FIELD, {})
        )

    def _stop(self: Self, *, end_reason: str) -> None:
        self.result.end_reason = end_reason
        self._stop_requested = True


def _installed_engine_version() -> str | None:
    try:
        return importlib.metadata.version('glitchygames')
    except importlib.metadata.PackageNotFoundError:
        return None


def apply_recorded_options(*, options: dict[str, Any], recorded: dict[str, Any]) -> None:
    """Put every recorded option except ``REPLAY_LOCAL_OPTIONS`` into ``options``.

    Args:
        options: The run's options (``GameEngine.OPTIONS``), changed in place.
        recorded: The header's ``options`` (JSON-safe; read back with ``value_from_json``).

    """
    for name, value in recorded.items():
        if name not in REPLAY_LOCAL_OPTIONS:
            options[name] = value_from_json(value)


def start_replay(
    *, path: Path, game_class_name: str, options: dict[str, Any], use_fastevents: bool = False
) -> ReplaySources:
    """Read a recording and prepare the run to replay it (rule 1); the caller installs it.

    A recording of another game raises ReplayRefusedError (``check_game``); an unreadable file
    raises TraceFormatError or OSError (``ReplaySources.from_path``). The engine exits with
    ``REPLAY_UNUSABLE_EXIT_CODE`` on each.

    Args:
        path: The recording.
        game_class_name: The class name of the game being started.
        options: The run's options, given the recorded ones in place.
        use_fastevents: Drain the real queue with pygame.fastevent (``GameEngine.USE_FASTEVENTS``).

    Returns:
        The replay's sources, not yet installed.

    """
    sources = ReplaySources.from_path(path=path, use_fastevents=use_fastevents)
    sources.check_game(game_class_name=game_class_name)
    recorded_version = sources.header.get(ENGINE_VERSION_HEADER_FIELD)
    installed_version = _installed_engine_version()
    if recorded_version != installed_version:
        LOG.warning(
            'The recording was made with engine version %s; this is %s. The replay may diverge',
            recorded_version,
            installed_version,
        )
    apply_recorded_options(options=options, recorded=sources.header.get(OPTIONS_HEADER_FIELD, {}))
    seed_engine_random(seed=sources.random_seed)
    LOG.info(
        'Replaying %s (%d frames, random seed %d)', path, sources.frame_count, sources.random_seed
    )
    return sources
