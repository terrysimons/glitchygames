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
2. Pump: the real queue is drained (through the live doors' pump) and each event classified
   with the internal-post tracker. From the first pump on, real input, device and window events
   are blocked at SDL (``REAL_INPUT_EVENT_TYPES``, glitchygames/replay/input_blocking.py), so
   they never enter the queue; the blocked state each type had before comes back when the
   replay ends (``finish_run``, normally or after an error) or is uninstalled. QUIT, the
   window's close event and the custom range are never blocked. Blocking also refuses posts of
   those types: game code that fakes input by posting, say, KEYDOWN loses the post, which
   shows as a missing internal event divergence (the engine's own posts are QUIT and custom
   types). What external events still arrive (queued before the first pump, the close event,
   app lifecycle and system notifications) are dropped, except the window's QUIT, kept last
   so closing the window ends the replay. Pump N serves the recording's batch N in
   its recorded order: each external record is rebuilt (recorded references mapped to live
   objects: a window to None, as live events of the display module's window carry it; a
   joystick to its opened stand-in, an event whose joystick has none being dropped with one
   warning per instance id), and each internal record is the live internal event the replayed
   code posted again (equal records). A recorded internal event nobody posted, a posted one the
   recording does not have, or a frame pumped more or fewer times than recorded is a
   divergence of the frame. Internal events are matched by encoded record
   (``event_to_record``), so one carrying a window or joystick reference would compare the
   recorded and live ids; none of the engine's posts carry one today.
3. Frame indexes: the sources count their own ``end_frame`` calls; every recorded frame they
   serve is picked by that count, never by the scene manager's frame number.
4. Frame time: the current frame's recorded ``dt``; past the end, the measurement. The FPS
   events and performance statistics (``performance_frame_seconds``) use it too under
   ``--replay-fps recorded`` (the default), so the FPS events are compared exactly; under
   ``--replay-fps real`` they use this machine's measured frame time, and FPS events are not
   compared (logic still receives the recorded ``dt``).
5. Input: the frame's snapshot, rebuilt by applying each frame's ``input_changes`` in order
   (a version-2 recording has none: polled input reads as idle, with one warning).
6. Devices: a ``ReplayDeviceRegistry`` from the header, learning each frame's opened devices
   and enumeration answers when the frame begins (before any open in it is answered).
7. Saves: a ``MemorySaveManager`` per namespace, seeded from the header's ``saves`` or the
   frame's ``saves_opened`` (an unknown namespace gets an empty store); real saves are never
   touched.
8. End of frame: a divergence found by the frame's pumps comes first; then the frame's
   control events that are not applied again (markers the replayed code records by itself)
   are compared with the recorded ones, in order; then the scene's sprites are sampled as the
   recorder samples them and compared with the recorded frame (scene class, then each sprite:
   present, ``rect``, ``visible``). The first difference stops the replay, as does the last
   recorded frame.
9. Clocks: the wall clock is the recording's ``recorded_at`` plus the frame clock; elapsed
   seconds are the frame clock, live and replayed alike (glitchygames/clock.py).
10. ``recorded_frame_fields`` hands a recording made over the replay (Part 2's rebaseline) the
    frame's recorded saves and device fields.
11. ``GameEngine._shutdown`` calls ``finish_run`` and logs the result.
"""

from __future__ import annotations

import dataclasses
import importlib.metadata
import itertools
import json
import logging
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

import pygame

from glitchygames.events import FPSEVENT
from glitchygames.input.devices import (
    DeviceDescriptor,
    EnumerationAnswer,
    ReplayDeviceRegistry,
    ReplayJoystick,
)
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
    EVENT_NAME_FIELD,
    EVENT_ORIGIN_FIELD,
    EVENT_TYPE_FIELD,
    EXTERNAL_ORIGIN,
    INPUT_CHANGES_FIELD,
    INTERNAL_ORIGIN,
    SAVES_HEADER_FIELD,
    SAVES_OPENED_FIELD,
    WINDOW_REFERENCE,
    RecordedReference,
    UnrepresentableValue,
    event_from_record,
    event_origin,
    event_to_record,
    pending_internal_posts,
    start_tracking_internal_posts,
    stop_tracking_internal_posts,
    value_from_json,
)
from glitchygames.replay.input_blocking import REAL_INPUT_EVENT_TYPES, EventTypeBlock
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
    'replay_fps',
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

# --replay-fps values: FPS events (and the performance statistics) from the recorded frame times
# (exact, compared) or from this machine's measured frame times (not compared)
RECORDED_REPLAY_FPS = 'recorded'
REAL_REPLAY_FPS = 'real'
REPLAY_FPS_CHOICES = (RECORDED_REPLAY_FPS, REAL_REPLAY_FPS)
REAL_REPLAY_FPS_NOTICE = (
    '--replay-fps real: FPS events follow this machine and are not compared; sprites that draw '
    'the FPS value may diverge'
)

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
PUMP_COUNT_FIELD = 'pump count'
MISSING_INTERNAL_EVENT_FIELD = 'missing internal event'
UNEXPECTED_INTERNAL_EVENT_FIELD = 'unexpected internal event'
CONTROL_EVENT_FIELD = 'control event'

# The first format version whose frames record control events (older ones have no markers to
# compare)
CONTROL_EVENTS_FORMAT_VERSION = 3

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
        subject: What differed: a sprite id, ``'scene'``, ``'recording'``, an event's name or
            a control event's kind.
        field: Which of its fields: ``'rect'``, ``'visible'``, ``'present'``, ``'class'``,
            ``'frames'``, ``'pump count'``, ``'missing internal event'``,
            ``'unexpected internal event'``, ``'control event'``.
        expected: The recorded value (None when the replay has something the recording has not).
        actual: The replayed value (None when the replay is missing something recorded).

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


def _take_live_match(
    *,
    unmatched: list[tuple[pygame.event.Event, dict[str, Any]]],
    record: dict[str, Any],
    is_compared: bool,
) -> pygame.event.Event | None:
    """Remove and return the first live internal event that stands for a recorded internal one.

    Args:
        unmatched: The live internal events not matched yet, each with its record (changed in
            place).
        record: The recorded internal event.
        is_compared: True to match equal records only; False (a type that is not compared) to
            match the first live event of the recorded type.

    Returns:
        The live event, or None when none matches.

    """
    recorded_type = record.get(EVENT_TYPE_FIELD)
    for index, (live_event, live_record) in enumerate(unmatched):
        if live_record == record if is_compared else live_event.type == recorded_type:
            del unmatched[index]
            return live_event
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
        fps_source: ``RECORDED_REPLAY_FPS`` or ``REAL_REPLAY_FPS`` (``--replay-fps``; rule 4).
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
        # start_replay sets it from --replay-fps
        self.fps_source = RECORDED_REPLAY_FPS
        self.result = ReplayResult()
        self.random_seed = _recorded_seed(header=header)
        self._recorded_at = _recorded_start(header=header)
        self._frames = frames
        self._is_truncated = is_truncated
        self._compares_control_events = format_version >= CONTROL_EVENTS_FORMAT_VERSION
        # Frames ended so far (end_frame calls): the index of the frame being served
        self._frame_index = 0
        # Pumps so far in the current frame: the index of the batch the next pump serves
        self._pump_index = 0
        self._stop_requested = False
        self._window_was_closed = False
        self._last_batch_origins: list[str] = []
        # The first difference the current frame's pumps found (reported at end_frame)
        self._frame_divergence: Divergence | None = None
        # Joystick instance ids without a stand-in already warned about, and unrepresentable
        # types already logged
        self._warned_joystick_instances: set[int] = set()
        self._logged_unrepresentable_types: set[str] = set()
        # Only its event pump is used: the one place the real queue is read (rule 2)
        self._live_queue = LiveSources(random_seed=self.random_seed, use_fastevents=use_fastevents)
        # Real input blocked at SDL from the first pump that drains the queue until the replay
        # ends or is uninstalled (rule 2); blocked once, so a pump after the end does not again
        self._real_input_block = EventTypeBlock(event_types=REAL_INPUT_EVENT_TYPES)
        self._has_blocked_real_input = False
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
        """Give up the internal-post tracker and restore the blocked state of real input."""
        stop_tracking_internal_posts()
        self._real_input_block.restore()

    def pump_events(
        self: Self, *, real_events: list[pygame.event.Event] | None = None
    ) -> list[pygame.event.Event]:
        """Serve the recording's batch for this pump, merged with live internal events (rule 2).

        The first pump that drains the real queue blocks real input at SDL (rule 2); a pump
        given ``real_events`` does not own the queue, so it blocks nothing.

        Args:
            real_events: The real batch to filter instead of draining the real queue (a Part 3
                playback scope passes the base pump's batch).

        Returns:
            The recorded batch in its order (external events from the recording, internal ones
            as the replayed code posted them again), then any live internal event the
            recording does not have, then the window's QUIT if it was closed.

        """
        if real_events is None:
            live_events = self._live_queue.pump_events()
            # After the drain, so the replayed code's posts made before the first pump are kept
            if not self._has_blocked_real_input:
                self._has_blocked_real_input = True
                self._real_input_block.block()
        else:
            live_events = real_events
        pending = pending_internal_posts()
        live_internal_events: list[pygame.event.Event] = []
        window_closes: list[pygame.event.Event] = []
        for event in live_events:
            if event_origin(event=event, pending=pending) == INTERNAL_ORIGIN:
                live_internal_events.append(event)
            elif event.type == pygame.QUIT:
                window_closes.append(event)
            # Every other real external event is dropped: real input is blocked at SDL, so
            # these are events queued before the first pump, the window's close event (its
            # QUIT follows) and app lifecycle and system notifications
        # Posted but not returned: the queue was cleared or the type is blocked
        pending.clear()
        batch, origins = self._merged_batch(live_internal_events=live_internal_events)
        self._pump_index += 1
        if window_closes:
            self._window_was_closed = True
            batch.append(window_closes[-1])
            origins.append(EXTERNAL_ORIGIN)
        self._last_batch_origins = origins
        return batch

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

    def performance_frame_seconds(self: Self, *, measured: float, frame_seconds: float) -> float:
        """Return the frame time FPS events and the performance statistics use (rule 4).

        Args:
            measured: The measured start-to-start time.
            frame_seconds: The frame time ``frame_seconds()`` returned (the recorded dt).

        Returns:
            ``frame_seconds`` under ``--replay-fps recorded``, ``measured`` under ``real``.

        """
        if self.fps_source == REAL_REPLAY_FPS:
            return measured
        return frame_seconds

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
        # dt is the recorded one by construction
        del dt
        frame = self._current_frame()
        if frame is not None and not self._stop_requested:
            divergence = self._frame_difference(
                frame=frame, scene=scene, control_events=control_events
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
        self._frame_divergence = None
        self._begin_frame()

    def finish_run(self: Self) -> None:
        """Settle the result when the run ends (``GameEngine._shutdown``).

        A run that ended while the replay was still running (the game quit or failed before
        the recording's last frame) diverged in length. Either way the blocked state of real
        input is restored (rule 2).
        """
        self._real_input_block.restore()
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

    def _frame_difference(
        self: Self,
        *,
        frame: dict[str, Any],
        scene: Scene | None,
        control_events: list[ControlEvent],
    ) -> Divergence | None:
        """Return the frame's first difference: its pumps', its markers', then its sprites'.

        Returns:
            The divergence, or None when the frame matches.

        """
        if self._frame_divergence is not None:
            return self._frame_divergence
        recorded_pump_count = len(frame.get(EVENT_BATCHES_FIELD, []))
        if self._pump_index < recorded_pump_count:
            # Fewer pumps than recorded (more are found by the extra pump itself)
            return Divergence(
                frame_number=self._frame_index,
                kind=LENGTH_DIVERGENCE,
                subject=RECORDING_SUBJECT,
                field=PUMP_COUNT_FIELD,
                expected=recorded_pump_count,
                actual=self._pump_index,
            )
        control_event_divergence = self._control_event_difference(
            frame=frame, control_events=control_events
        )
        if control_event_divergence is not None:
            return control_event_divergence
        # Sampled exactly as the recorder samples a recorded frame
        replayed = sample_scene_frame(
            frame_number=self._frame_index, scene=scene, sprite_ids=self._sprite_ids
        )
        return first_frame_difference(
            frame_index=self._frame_index, recorded=frame, replayed=replayed
        )

    def _control_event_difference(
        self: Self, *, frame: dict[str, Any], control_events: list[ControlEvent]
    ) -> Divergence | None:
        """Compare the markers the replayed code recorded with the frame's recorded ones (rule 8).

        Control events applied again (``REAPPLIED_CONTROL_EVENT_KINDS``) are left out on both
        sides: the replay records them itself from the recording.

        Returns:
            The first marker that differs (missing, extra or changed), or None.

        """
        if not self._compares_control_events:
            return None
        recorded_markers = [
            record
            for record in frame.get(CONTROL_EVENTS_FIELD, [])
            if record.get(KIND_FIELD) not in REAPPLIED_CONTROL_EVENT_KINDS
        ]
        # Through JSON, as the recording wrote them: an integer key becomes a string and a
        # tuple a list, so a marker is never compared with its recorded form falsely
        replayed_markers = [
            json.loads(json.dumps(control_event.to_json()))
            for control_event in control_events
            if control_event.kind not in REAPPLIED_CONTROL_EVENT_KINDS
        ]
        for expected, actual in itertools.zip_longest(recorded_markers, replayed_markers):
            if expected != actual:
                differing_marker = expected if expected is not None else actual
                return Divergence(
                    frame_number=self._frame_index,
                    kind=EVENT_DIVERGENCE,
                    subject=str(differing_marker[KIND_FIELD]),
                    field=CONTROL_EVENT_FIELD,
                    expected=expected,
                    actual=actual,
                )
        return None

    def _note_frame_divergence(
        self: Self, *, kind: str, subject: str, field: str, expected: object, actual: object
    ) -> None:
        """Keep the current frame's first difference found while pumping (end_frame reports it)."""
        if self._frame_divergence is None:
            self._frame_divergence = Divergence(
                frame_number=self._frame_index,
                kind=kind,
                subject=subject,
                field=field,
                expected=expected,
                actual=actual,
            )

    def _merged_batch(
        self: Self, *, live_internal_events: list[pygame.event.Event]
    ) -> tuple[list[pygame.event.Event], list[str]]:
        """Build this pump's batch in the recorded batch's order (rule 2).

        Under ``--replay-fps real`` FPS events are not compared (rule 4): a recorded one takes
        the next live FPS event in its place, if any, and a live one left over is delivered;
        neither is a divergence.

        Args:
            live_internal_events: The events the replayed code posted, in queue order.

        Returns:
            The batch and each event's origin. Past the end of the recording, or on a pump the
            frame did not record, the live internal events alone.

        """
        uncompared_event_types: frozenset[int] = (
            frozenset({FPSEVENT}) if self.fps_source == REAL_REPLAY_FPS else frozenset()
        )
        live_origins = [INTERNAL_ORIGIN] * len(live_internal_events)
        frame = self._current_frame()
        if frame is None:
            return list(live_internal_events), live_origins
        batches = frame.get(EVENT_BATCHES_FIELD, [])
        if self._pump_index >= len(batches):
            self._note_frame_divergence(
                kind=LENGTH_DIVERGENCE,
                subject=RECORDING_SUBJECT,
                field=PUMP_COUNT_FIELD,
                expected=len(batches),
                actual=self._pump_index + 1,
            )
            return list(live_internal_events), live_origins
        # Each live internal event with its record, compared with the recorded internal records
        unmatched = [
            (event, event_to_record(event=event, origin=INTERNAL_ORIGIN))
            for event in live_internal_events
        ]
        batch: list[pygame.event.Event] = []
        origins: list[str] = []
        for record in batches[self._pump_index]:
            if record.get(EVENT_ORIGIN_FIELD) == EXTERNAL_ORIGIN:
                event = self._live_event_from_record(record=record)
                if event is not None:
                    batch.append(event)
                    origins.append(EXTERNAL_ORIGIN)
                continue
            is_compared = record.get(EVENT_TYPE_FIELD) not in uncompared_event_types
            matched_event = _take_live_match(
                unmatched=unmatched, record=record, is_compared=is_compared
            )
            if matched_event is not None:
                batch.append(matched_event)
                origins.append(INTERNAL_ORIGIN)
            elif is_compared:
                self._note_frame_divergence(
                    kind=EVENT_DIVERGENCE,
                    subject=str(record.get(EVENT_NAME_FIELD)),
                    field=MISSING_INTERNAL_EVENT_FIELD,
                    expected=record,
                    actual=None,
                )
        # Posted again by the replayed code but not recorded: still delivered, and a divergence
        # (unless its type is not compared)
        for event, live_record in unmatched:
            batch.append(event)
            origins.append(INTERNAL_ORIGIN)
            if event.type in uncompared_event_types:
                continue
            self._note_frame_divergence(
                kind=EVENT_DIVERGENCE,
                subject=str(live_record[EVENT_NAME_FIELD]),
                field=UNEXPECTED_INTERNAL_EVENT_FIELD,
                expected=None,
                actual=live_record,
            )
        return batch, origins

    def _live_event_from_record(self: Self, *, record: dict[str, Any]) -> pygame.event.Event | None:
        """Rebuild a recorded external event with its references mapped to live objects.

        A window reference becomes None: the window is the display module's, and live play
        never calls ``pygame.Window.from_display_module()`` (deprecated, and calling it would
        make SDL's window events carry a Window from then on), so every live event of the
        current window carries ``window=None``. A joystick reference becomes the stand-in
        opened for its instance id.

        Returns:
            The event, or None when its joystick has no stand-in (dropped, with one warning
            per instance id).

        """
        recorded_event = event_from_record(record)
        attributes: dict[str, Any] = {}
        for name, value in recorded_event.dict.items():
            if isinstance(value, RecordedReference):
                if value.kind == WINDOW_REFERENCE:
                    attributes[name] = None
                    continue
                joystick = self._opened_joystick(instance_id=value.identifier)
                if joystick is None:
                    return None
                attributes[name] = joystick
                continue
            if (
                isinstance(value, UnrepresentableValue)
                and value.type_name not in self._logged_unrepresentable_types
            ):
                self._logged_unrepresentable_types.add(value.type_name)
                LOG.debug(
                    'Recorded events carry an unrepresentable %s; it is injected as recorded',
                    value.type_name,
                )
            attributes[name] = value
        return pygame.event.Event(recorded_event.type, attributes)

    def _opened_joystick(self: Self, *, instance_id: int) -> ReplayJoystick | None:
        """Return the stand-in opened for a recorded instance id, or None (warned once per id).

        Returns:
            The joystick stand-in, or None when no device was opened for ``instance_id``.

        """
        joystick = self._devices.joystick_for_instance(instance_id=instance_id)
        if joystick is None and instance_id not in self._warned_joystick_instances:
            self._warned_joystick_instances.add(instance_id)
            LOG.warning(
                'recorded joystick event for instance %d has no device; dropped', instance_id
            )
        return joystick

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
        options: The run's options, given the recorded ones in place; ``replay_fps`` (local, so
            never the recording's) picks the FPS source, ``RECORDED_REPLAY_FPS`` when unset.
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
    sources.fps_source = options.get('replay_fps') or RECORDED_REPLAY_FPS
    if sources.fps_source == REAL_REPLAY_FPS:
        LOG.warning(REAL_REPLAY_FPS_NOTICE)
    LOG.info(
        'Replaying %s (%d frames, random seed %d)', path, sources.frame_count, sources.random_seed
    )
    return sources
