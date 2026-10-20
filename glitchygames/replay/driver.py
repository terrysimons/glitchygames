"""Exact replay of a ``--record-trace`` recording through the real engine (``--replay-trace``).

``ReplaySources`` are the doors (glitchygames/sources.py) a replay installs: everything the
recorded run took in is served from the recording, so the real engine and game code run the
session again, and every frame's sprites are compared with the recorded frame. The rules
(plans/2026-10-19-gameplay-replay.md, sections 3.1-3.3):

1. Startup, in one place (``GameEngine.__init__``): once the options are parsed,
   ``start_replay`` reads the recording, refuses a recording of another game
   (``ReplayRefusedError``; the engine logs it and exits with ``ExitCode.UNUSABLE_INPUT``, as
   for an unreadable file, or ``ExitCode.MISSING_INPUT`` for a missing one;
   glitchygames/exit_codes.py), warns once about a different engine version, applies the
   recorded options (all but ``REPLAY_LOCAL_OPTIONS``) and seeds the random streams with the
   recorded seed. The engine installs the sources before the first frame; while installed they
   own the internal-post tracker (glitchygames/recording.py).
2. Pump: the real queue is drained (through the live doors' pump) and each event classified
   with the internal-post tracker. From the first drain on, real input, device and window
   events are blocked at SDL (``REAL_INPUT_EVENT_TYPES``, glitchygames/replay/input_blocking.py),
   so they never enter the queue (each drain blocks them again, as an event manager made mid-run
   allows its types); the blocked state each type had before comes back when the
   replay ends (``finish_run``, normally or after an error) or is uninstalled. QUIT, the
   window's close event and the custom range are never blocked, nor, in a watched replay, are
   KEYDOWN and KEYUP (``WATCHED_REAL_KEY_EVENT_TYPES``: the viewer's keys, rule 14). Blocking
   also refuses posts of those types: game code that fakes input by posting, say, KEYDOWN loses
   the post, which shows as a missing internal event divergence (the engine's own posts are
   QUIT and custom types). So game code posting KEYDOWN or KEYUP replays differently watched
   and headless: watched, the keys are not blocked, the post arrives and matches its recorded
   internal record; headless (and so ``--audit``), it is refused and diverges. A recording of
   such a game can match watched and diverge headless. What external events still arrive
   (queued before the first drain, the close event, app lifecycle and system notifications)
   never reach the game: a watched replay's real key presses and releases go to its controls
   (rule 14), the rest are dropped, except the window's QUIT, kept last so closing the window
   ends the replay. A control tick of a held frame (rule 14) drains the queue the same way; the
   internal events it finds wait for the next pump. Pump N serves the recording's batch N in
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
   present, ``rect``, ``visible``). The first difference stops a headless replay, as does
   the last recorded frame; a watched replay pauses there instead (rule 14).
9. Clocks: the wall clock is the recording's ``recorded_at`` plus the frame clock; elapsed
   seconds are the frame clock, live and replayed alike (glitchygames/clock.py).
10. ``recorded_frame_fields`` hands a recording made over the replay (Part 2's rebaseline) the
    frame's recorded saves and device fields.
11. ``GameEngine._shutdown`` calls ``finish_run`` and reports the result (``ReplayResult.report``:
    printed to stdout under ``--headless``, logged otherwise); ``GameEngine.start`` then ends the
    run with ``ReplayResult.exit_code(policy=options.exit_policy)``.
    The report of a sprite divergence lists the sprite in the last ``REPORT_HISTORY_FRAMES``
    frames before it, recorded and replayed (kept by ``end_frame``).
12. Digests (``--replay-digest PATH``, for ``--audit``: glitchygames/replay/audit.py): each
    compared frame's ``frame_digest`` (of the frame as sampled for rule 8) is kept, and
    ``finish_run`` writes them with the divergence summary to the digest file.
13. Pacing: the scene manager never paces a replay (``paced_frame_seconds`` is 0.0). A
    headless replay (``--headless``) is not paced at all, as its frame times come from the
    recording. A watched replay is paced by its viewer (glitchygames/replay/viewer.py, whose
    docstring is the contract): an outer tick 60 times a second of real time
    (``glitchygames.clock.measured_seconds``, never replayed: it only decides when frames run,
    never what they do) runs the inner recorded frames its accumulator pays for (real time
    times the speed, consumed by each frame's recorded duration, bounded per tick in frames and
    real time, never owing more than one tick's worth).
14. Watching (not ``--headless``): ``ReplayControls`` (glitchygames/replay/controls.py) take
    the viewer's real key presses and releases; none reaches the game. ``hold_frame`` drives
    the viewer: with no outer tick open it sleeps until the next one, drains the real queue
    and acts on the keys read since the last tick (once per press; a key already down when
    the replay starts acts only after its release); it then answers False for each inner frame
    the open tick runs and True when the tick closes, refreshing the status line (showing the
    real speed while the viewer cannot keep up); the scene manager then presents that frame.
    Inner frames are not presented (``presents_frames`` is False). The start screen
    (``ReplayOptions.wait_for_start``) holds the loop after frame 0, so the first frame's
    picture is behind the message (frame 0's sounds play before Space, and a one-frame
    recording reaches its end at the start screen). The loop is also
    held while paused (until a step) and once the recording is used up. At a divergence or the
    end the replay pauses with the debug overlay on (``ReplayControls.debug_overlay``, the
    scene manager's, handed over by the engine) and a banner (``ReplayControls.banner``)
    instead of stopping; Esc stops it (a run that already ended keeps its end reason, else
    ``'quit'``). The status bar is drawn by ``draw_overlay``. A headless replay never holds and
    has no controls' keys: its KEYDOWN and KEYUP stay blocked.
15. Step back (``,``), Home and D restart the replay (glitchygames/replay/rebuild.py, whose
    docstring is the contract): a control tick that takes the controls' restart request
    (``ReplayControls.take_restart_request``) stops the replay with ``ReplayResult.restart_frame``
    set and the end reason ``'restart'``, and the engine relaunches it once torn down. A replay
    given ``ReplayOptions.pause_at_frame`` N (watched only: a headless replay ignores it, as
    nobody could unpause it) rebuilds: without its start screen, frames run unpresented and
    unpaced in silence (``Rebuild.silence_frame`` after each; ``hold_frame`` never holds, except
    every ``REBUILD_PROGRESS_INTERVAL_SECONDS`` of real time to present the progress line and read
    the viewer's keys), until frame ``max(N, FIRST_PAUSED_FRAME)`` is the next to run; there it
    pauses. A divergence or the end of the recording on the way pauses it there instead (rule
    14). ``ReplayOptions.viewer_state`` restores the viewer's speed, debug panel and the
    divergence frame an earlier run found.
"""

from __future__ import annotations

import collections
import dataclasses
import enum
import importlib.metadata
import itertools
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, Literal, Self

import pygame
from pydantic import BaseModel, ConfigDict, Field

from glitchygames.clock import measured_seconds
from glitchygames.events import FPSEVENT
from glitchygames.exit_codes import ExitCode
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
from glitchygames.replay.audit import frame_digest, write_digest_file
from glitchygames.replay.controls import FIRST_PAUSED_FRAME, ReplayControls
from glitchygames.replay.input_blocking import REAL_INPUT_EVENT_TYPES, EventTypeBlock
from glitchygames.replay.rebuild import Rebuild, ViewerState
from glitchygames.replay.viewer import ReplayViewer
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

    from glitchygames.input.state import InputSnapshot
    from glitchygames.scenes import Scene
    from glitchygames.state.manager import SaveManager

LOG = logging.getLogger('game.replay')
LOG.addHandler(logging.NullHandler())

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
    'replay_restart_handoff',
    'replay_viewer_state',
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

# How many frames before a sprite divergence its report lists (with the divergent frame itself)
REPORT_HISTORY_FRAMES = 20

# --replay-fps values: FPS events (and the performance statistics) from the recorded frame times
# (exact, compared) or from this machine's measured frame times (not compared)
RECORDED_REPLAY_FPS: Final = 'recorded'
REAL_REPLAY_FPS: Final = 'real'
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
RESTART_END_REASON = 'restart'

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

# The viewer's keys: left unblocked at SDL during a watched replay and handed to its controls
# (rule 14), never to the game
WATCHED_REAL_KEY_EVENT_TYPES: frozenset[int] = frozenset({pygame.KEYDOWN, pygame.KEYUP})

# A watched replay's banner once the recording is used up (rule 14)
END_OF_RECORDING_BANNER = 'End of recording'
TRUNCATED_RECORDING_BANNER = 'End of recording (the file is truncated)'

# The frame fields a recording made over a replay copies from it (recorded_frame_fields)
REBASELINE_FRAME_FIELDS = (SAVES_OPENED_FIELD, DEVICES_OPENED_FIELD, DEVICE_ENUMERATION_FIELD)

VERSION_TWO_INPUT_WARNING = (
    'The recording is format version %d, recorded before input-state capture; polled input '
    'will read as idle'
)


class ReplayRefusedError(RuntimeError):
    """The recording cannot be replayed by this game (a recording of another game)."""


class ReplayExitPolicy(enum.Enum):
    """What a replay's run exits with once it is over (``ReplayResult.exit_code``)."""

    # ReplayResult.exit_code: SUCCESS when matched, REPLAY_DIVERGED, UNUSABLE_INPUT when truncated
    RESULT = 'result'
    # ExitCode.SUCCESS whatever the result (--rebaseline: the new recording is the outcome)
    SUCCESS_AFTER_WRITING = 'success'


class ReplayOptions(BaseModel):
    """How a replay is run: everything ``ReplaySources`` is configured with but the recording.

    Read-only; ``start_replay`` builds it from the run's local options (``REPLAY_LOCAL_OPTIONS``,
    never the recording's). Later replay tasks add their fields here (a playback start frame,
    whether a divergence stops the replay).

    Attributes:
        headless: True under ``--headless``: frames are not paced (rule 13) and the engine prints
            the report to stdout (rule 11).
        exit_policy: What the run exits with once it is over (``ReplayResult.exit_code``).
        fps_source: ``RECORDED_REPLAY_FPS`` or ``REAL_REPLAY_FPS`` (``--replay-fps``; rule 4).
        digest_path: Where ``finish_run`` writes the frame digests (``--replay-digest``; rule
            12), or None.
        use_fastevents: Drain the real queue with pygame.fastevent when pygame has it
            (``GameEngine.USE_FASTEVENTS``), as the live doors would.
        wait_for_start: True to hold a watched replay at its start screen before frame 0 until
            the viewer presses Space (rule 14); ``start_replay`` sets it for every watched
            replay. A headless replay never waits, whatever this says.
        pause_at_frame: The frame a restarted watched replay rebuilds up to and pauses at
            (``--replay-pause-at-frame``; rule 15), or None. A headless replay ignores it.
        restart_handoff_path: Where a restarted replay hands its own restart to the
            supervising process (``--replay-restart-handoff``; glitchygames/replay/rebuild.py),
            or None in the first replay process.
        viewer_state: The viewer's state a restarted replay starts with
            (``--replay-viewer-state``: speed, debug panel, divergence frame), or None.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    headless: bool = False
    exit_policy: ReplayExitPolicy = ReplayExitPolicy.RESULT
    fps_source: Literal['recorded', 'real'] = RECORDED_REPLAY_FPS
    digest_path: Path | None = None
    use_fastevents: bool = False
    wait_for_start: bool = False
    pause_at_frame: int | None = Field(default=None, ge=0)
    restart_handoff_path: Path | None = None
    viewer_state: ViewerState | None = None


# The options of a replay given none (a test's, a tool's): watched without the start screen,
# recorded FPS, no digests
DEFAULT_REPLAY_OPTIONS = ReplayOptions()


class RecordedFrames:
    """The recording's complete frames, read by index (``ReplaySources.recording``).

    Attributes:
        is_truncated: True when the file was cut off (a killed recorder).

    """

    def __init__(self: Self, *, frames: Sequence[dict[str, Any]], is_truncated: bool) -> None:
        """Keep the decoded frames.

        Args:
            frames: Every complete recorded frame, decoded (glitchygames/tracing.py).
            is_truncated: True when the file was cut off after the last of them.

        """
        self._frames = frames
        self.is_truncated = is_truncated

    @property
    def frame_count(self: Self) -> int:
        """How many complete frames the recording holds."""
        return len(self._frames)

    def frame(self: Self, *, frame_index: int) -> dict[str, Any] | None:
        """Return a recorded frame, or None past the end of the recording.

        Args:
            frame_index: The recording's frame index (not negative).

        Returns:
            The decoded frame, or None.

        """
        if frame_index < len(self._frames):
            return self._frames[frame_index]
        return None

    def recorded_dt(self: Self, *, frame_index: int) -> float:
        """Return a frame's recorded ``dt``: the duration of the frame before it (rule 4).

        Args:
            frame_index: The recording's frame index.

        Returns:
            Seconds.

        """
        return float(self._frames[frame_index][DT_FIELD])

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


def _new_frame_history() -> collections.deque[tuple[int, list[dict[str, Any]]]]:
    """Return an empty history of the last compared frames (``REPORT_HISTORY_FRAMES`` + 1).

    Returns:
        A deque of (recording frame index, sampled sprites) that keeps the newest entries.

    """
    return collections.deque(maxlen=REPORT_HISTORY_FRAMES + 1)


def _describe_history_sprite(*, sprites: list[dict[str, Any]], sprite_id: str) -> str:
    """Describe one sprite of a frame for the divergence report.

    Returns:
        ``[x, y, width, height] visible`` (or ``hidden``), or ``absent`` when the frame does
        not have the sprite.

    """
    for sprite in sprites:
        if sprite[SPRITE_ID_FIELD] == sprite_id:
            visibility = 'visible' if sprite[VISIBLE_FIELD] else 'hidden'
            return f'{sprite[RECT_FIELD]} {visibility}'
    return 'absent'


@dataclasses.dataclass
class ReplayResult:
    """How a replay went so far.

    Attributes:
        frames_replayed: How many recorded frames were run and compared.
        divergence: The first difference, or None.
        end_reason: ``'running'``, ``'end_of_recording'``, ``'diverged'``, ``'truncated'``
            (the last complete frame of a cut-off file was replayed), ``'quit'`` (the
            window was closed, or Esc was pressed in a watched replay, before the end) or
            ``'restart'`` (the viewer stepped back before the end: rule 15).
        restart_frame: The frame the replay restarts at (rule 15), or None. Set by a step back
            even after the replay ended (a divergence keeps its end reason).
        recorded_history: The last compared frames as recorded: (recording frame index, its
            sprites), up to ``REPORT_HISTORY_FRAMES`` + 1, ending with the divergent frame once
            the replay diverged (``ReplaySources.end_frame`` adds each compared frame).
        replayed_history: The same frames as the replay sampled them.

    """

    frames_replayed: int = 0
    divergence: Divergence | None = None
    end_reason: str = RUNNING_END_REASON
    restart_frame: int | None = None
    recorded_history: collections.deque[tuple[int, list[dict[str, Any]]]] = dataclasses.field(
        default_factory=_new_frame_history, repr=False
    )
    replayed_history: collections.deque[tuple[int, list[dict[str, Any]]]] = dataclasses.field(
        default_factory=_new_frame_history, repr=False
    )

    def exit_code(self: Self, *, policy: ReplayExitPolicy) -> ExitCode:
        """Return the exit code the replay's run ends with (glitchygames/exit_codes.py).

        Args:
            policy: The replay's exit policy (``ReplayOptions.exit_policy``).

        Returns:
            ``SUCCESS`` under ``ReplayExitPolicy.SUCCESS_AFTER_WRITING``. Under
            ``ReplayExitPolicy.RESULT``: ``SUCCESS`` when the replay matched to the end of the
            recording or was quit or restarted before it; ``UNUSABLE_INPUT`` when it matched up
            to the cut-off of a truncated recording; ``REPLAY_DIVERGED`` when it diverged, or is
            still running (``finish_run`` turns a run that ended early into a length divergence).

        """
        if policy == ReplayExitPolicy.SUCCESS_AFTER_WRITING:
            return ExitCode.SUCCESS
        if self.divergence is not None:
            return ExitCode.REPLAY_DIVERGED
        if self.end_reason in {END_OF_RECORDING_END_REASON, QUIT_END_REASON, RESTART_END_REASON}:
            return ExitCode.SUCCESS
        if self.end_reason == TRUNCATED_END_REASON:
            return ExitCode.UNUSABLE_INPUT
        return ExitCode.REPLAY_DIVERGED

    def report(self: Self) -> str:
        """Describe how the replay went, for stdout (``--headless``) or the log.

        Returns:
            One line, e.g. ``Replay matched 9800 frames (end of recording)`` or ``Replay ended
            early at frame 4312: the recording is truncated``; for a sprite divergence, its line
            (``Replay diverged at frame 6120: sprite Ball#2 rect expected [412, 300, 16, 16],
            got [412, 301, 16, 16]``) followed by ``Ball#2, last 20 frames (expected | got):``
            and one ``  6100: [400, 290, 16, 16] visible | [400, 290, 16, 16] visible`` line per
            frame up to the divergent one.

        """
        divergence = self.divergence
        if divergence is not None:
            lines = [f'Replay diverged at {divergence.describe()}']
            if divergence.kind == SPRITE_DIVERGENCE:
                sprite_id = divergence.subject
                lines.append(f'{sprite_id}, last {REPORT_HISTORY_FRAMES} frames (expected | got):')
                for (frame_index, recorded_sprites), (_, replayed_sprites) in zip(
                    self.recorded_history, self.replayed_history, strict=True
                ):
                    expected = _describe_history_sprite(
                        sprites=recorded_sprites, sprite_id=sprite_id
                    )
                    got = _describe_history_sprite(sprites=replayed_sprites, sprite_id=sprite_id)
                    lines.append(f'  {frame_index}: {expected} | {got}')
            return '\n'.join(lines)
        if self.end_reason == END_OF_RECORDING_END_REASON:
            return f'Replay matched {self.frames_replayed} frames (end of recording)'
        if self.end_reason == QUIT_END_REASON:
            return f'Replay matched {self.frames_replayed} frames (quit before the end)'
        if self.end_reason == RESTART_END_REASON:
            return (
                f'Replay matched {self.frames_replayed} frames (restarting at frame '
                f'{self.restart_frame})'
            )
        if self.end_reason == TRUNCATED_END_REASON:
            return f'Replay ended early at frame {self.frames_replayed}: the recording is truncated'
        return f'Replay still running after {self.frames_replayed} frames'


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
        matches = (live_record == record) if is_compared else (live_event.type == recorded_type)
        if matches:
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
        recording: The recorded frames.
        options: How the replay is run (``ReplayOptions``).
        result: How the replay went so far.
        random_seed: The recorded master seed.
        controls: The watched replay's controls (rule 14; unused by a headless replay).
        viewer: The watched replay's outer loop (rule 14, glitchygames/replay/viewer.py).
        draws_overlay: True for a watched replay, which draws its status bar
            (``draw_overlay``).
        presents_frames: False for a watched replay, whose viewer presents the latest frame
            once per outer tick.

    """

    def __init__(
        self: Self,
        *,
        header: dict[str, Any],
        frames: Sequence[dict[str, Any]],
        format_version: int,
        is_truncated: bool = False,
        options: ReplayOptions = DEFAULT_REPLAY_OPTIONS,
    ) -> None:
        """Prepare to serve the recording from its first frame.

        Args:
            header: The header fields.
            frames: Every complete recorded frame, decoded (glitchygames/tracing.py).
            format_version: The file's format version (2 or 3).
            is_truncated: True when the file was cut off (a killed recorder): the replay then
                ends with ``'truncated'`` after the last complete frame.
            options: How the replay is run.

        """
        self.header = header
        self.options = options
        self.result = ReplayResult()
        self.random_seed = _recorded_seed(header=header)
        self._recorded_at = _recorded_start(header=header)
        self.recording = RecordedFrames(frames=frames, is_truncated=is_truncated)
        self.draws_overlay = not options.headless
        # Watched, inner frames are not presented: the viewer's outer tick presents the latest
        self.presents_frames = options.headless
        self.controls = ReplayControls(
            total_frames=self.recording.frame_count,
            awaiting_start=options.wait_for_start and not options.headless,
        )
        self.viewer = ReplayViewer(controls=self.controls)
        # A restarted watched replay rebuilds up to its pause frame (rule 15)
        self._rebuild: Rebuild | None = None
        if options.pause_at_frame is not None and not options.headless:
            self._rebuild = Rebuild(target_frame=max(options.pause_at_frame, FIRST_PAUSED_FRAME))
            self.controls.rebuild_target_frame = self._rebuild.target_frame
        if options.viewer_state is not None:
            # What the viewer had set before the restart (the engine carries the panel over to
            # the scene manager's debug overlay with the controls')
            self.controls.speed = options.viewer_state.speed
            self.controls.debug_overlay.panel = options.viewer_state.debug_panel
            self.controls.divergence_frame = options.viewer_state.divergence_frame
        self._compares_control_events = format_version >= CONTROL_EVENTS_FORMAT_VERSION
        # Frames ended so far (end_frame calls): the index of the frame being served
        self._frame_index = 0
        # Pumps so far in the current frame: the index of the batch the next pump serves
        self._pump_index = 0
        self._stop_requested = False
        self._window_was_closed = False
        self._last_batch_origins: list[str] = []
        # Internal events a held frame drained from the real queue, for the next pump (rule 14)
        self._held_internal_events: list[pygame.event.Event] = []
        # The first difference the current frame's pumps found (reported at end_frame)
        self._frame_divergence: Divergence | None = None
        # One frame_digest per compared frame, kept only when digest_path is set (rule 12)
        self._frame_digests: list[str] = []
        # Joystick instance ids without a stand-in already warned about, and unrepresentable
        # types already logged
        self._warned_joystick_instances: set[int] = set()
        self._logged_unrepresentable_types: set[str] = set()
        # Only its event pump is used: the one place the real queue is read (rule 2)
        self._live_queue = LiveSources(
            random_seed=self.random_seed, use_fastevents=options.use_fastevents
        )
        # Real input blocked at SDL from the first drain of the queue until the replay ends or
        # is uninstalled (rule 2); the snapshot is taken once, so a drain after the end does not
        # block again. A watched replay leaves the viewer's keys unblocked (rule 14)
        blocked_event_types = (
            REAL_INPUT_EVENT_TYPES
            if options.headless
            else tuple(
                event_type
                for event_type in REAL_INPUT_EVENT_TYPES
                if event_type not in WATCHED_REAL_KEY_EVENT_TYPES
            )
        )
        self._real_input_block = EventTypeBlock(event_types=blocked_event_types)
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
    def from_path(
        cls,
        *,
        path: Path,
        options: ReplayOptions = DEFAULT_REPLAY_OPTIONS,
    ) -> ReplaySources:
        """Read a recording file into replay sources.

        A file cut off part way (a killed recorder) replays up to its last complete frame
        (``recording.is_truncated``; ``announce_replay`` says so once the run will replay it). A
        file that is not a readable recording raises TraceFormatError (from reading it, or from
        a header without the seed or start time), a missing one OSError.

        Args:
            path: The recording.
            options: How the replay is run.

        Returns:
            The sources.

        """
        read_result = read_trace_result(path=path)
        frames = read_result.trace[FRAMES_FIELD]
        is_truncated = not read_result.is_complete or read_result.dropped_partial_line is not None
        header = {name: value for name, value in read_result.trace.items() if name != FRAMES_FIELD}
        return cls(
            header=header,
            frames=frames,
            format_version=read_result.format_version,
            is_truncated=is_truncated,
            options=options,
        )

    @property
    def opened_save_namespaces(self: Self) -> Mapping[str, SaveManager]:
        """Every memory store opened so far, by namespace (read-only)."""
        return MappingProxyType(self._opened_save_namespaces)

    @property
    def stop_requested(self: Self) -> bool:
        """True once the replay should end the run.

        A headless replay stops once it diverged or reached its last frame; any replay stops
        once the window was closed or (watched) Esc was pressed.
        """
        return self._stop_requested

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

        The first drain of the real queue blocks real input at SDL (rule 2), and every later one
        blocks it again (event managers made mid-run allow their types); a pump given
        ``real_events`` does not own the queue, so it blocks nothing. A watched replay's real
        key presses go to its controls (rule 14).

        Args:
            real_events: The real batch to filter instead of draining the real queue (a Part 3
                playback scope passes the base pump's batch).

        Returns:
            The recorded batch in its order (external events from the recording, internal ones
            as the replayed code posted them again), then any live internal event the
            recording does not have, then the window's QUIT if it was closed.

        """
        is_first_drain = real_events is None and not self._has_blocked_real_input
        live_events = self._drain_real_queue() if real_events is None else real_events
        live_internal_events, window_closes = self._sort_live_events(
            live_events=live_events, is_first_drain=is_first_drain
        )
        # Posted but not returned: the queue was cleared or the type is blocked
        pending_internal_posts().clear()
        # Posts a held frame found come first: they were queued before this drain (rule 14)
        live_internal_events = [*self._held_internal_events, *live_internal_events]
        self._held_internal_events = []
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
        if self.options.fps_source == REAL_REPLAY_FPS:
            return measured
        return frame_seconds

    def paced_frame_seconds(self: Self) -> float | None:
        """Return how the frame starting now is paced (rule 13).

        Returns:
            0.0: a headless replay is not paced, and a watched one paces itself in
            ``hold_frame`` (holding the loop until the frame is due), so the scene manager
            never waits for it.

        """
        return 0.0

    def hold_frame(self: Self) -> bool:
        """Drive the viewer's outer loop: say whether the next inner frame waits (rule 14).

        Opens the viewer's next outer tick when none is open (sleeping until it is due, then
        reading the viewer's keys and refreshing the status line), and runs inner frames from
        the viewer's accumulator (glitchygames/replay/viewer.py).

        While a restarted replay rebuilds (rule 15) no outer tick opens: frames run unheld,
        but for one hold every ``REBUILD_PROGRESS_INTERVAL_SECONDS`` of real time, which reads
        the viewer's keys (Esc and the window's close still end the replay) and presents the
        progress line.

        Returns:
            False when headless (a headless replay never holds), while rebuilding (but at its
            progress) or when the viewer runs one more inner frame in its open tick; True when
            the tick closes or the rebuild shows its progress (the loop presents the outer frame
            and asks again).

        """
        if self.options.headless:
            return False
        if self._rebuild is not None:
            now = measured_seconds()
            if not self._rebuild.progress_is_due(frame_index=self._frame_index, now=now):
                return False
            self._run_control_tick(now=now)
            return True
        # Nothing has run since the last tick closed: its state decides how the viewer waits
        now = self.viewer.begin_tick(is_inner_running=self._is_inner_running())
        if now is not None:
            self._run_control_tick(now=now)
            self.viewer.accrue(now=now, is_inner_running=self._is_inner_running())
        runs_inner_frame = self.viewer.should_run_inner_frame(
            inner_frame_seconds=self._inner_frame_seconds(),
            is_inner_over=self._is_inner_over(),
            is_first_inner_frame=self._frame_index == 0,
        )
        if not runs_inner_frame:
            # The tick closed: the status line describes the frame about to be presented
            self._refresh_status_line()
        return not runs_inner_frame

    def draw_overlay(self: Self, *, surface: pygame.Surface) -> None:
        """Draw the watched replay's status bar, banner and start screen (rule 14).

        What is drawn changes once per control tick (``hold_frame``); it is drawn on every
        presented frame.

        Args:
            surface: The presented frame (never a screenshot or a traced frame).

        """
        self.controls.draw(surface=surface)

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
        # Compared until the replay ended (a watched replay may run on after its end, rule 14)
        if frame is not None and self.result.end_reason == RUNNING_END_REASON:
            # Sampled exactly as the recorder samples a recorded frame
            replayed = sample_scene_frame(
                frame_number=self._frame_index, scene=scene, sprite_ids=self._sprite_ids
            )
            if self.options.digest_path is not None:
                self._frame_digests.append(frame_digest(frame_record=replayed))
            # For the divergence report (rule 11)
            self.result.recorded_history.append((self._frame_index, frame[SPRITES_FIELD]))
            self.result.replayed_history.append((self._frame_index, replayed[SPRITES_FIELD]))
            divergence = self._frame_difference(
                frame=frame, replayed=replayed, control_events=control_events
            )
            self.result.frames_replayed = self._frame_index + 1
            if divergence is not None:
                LOG.debug(
                    'Replay diverged at recorded frame %d (run frame %d)',
                    divergence.frame_number,
                    frame_number,
                )
                self.result.divergence = divergence
                self.controls.divergence_frame = divergence.frame_number
                self._end_replay(
                    end_reason=DIVERGED_END_REASON,
                    banner=f'Diverged at {divergence.describe()}',
                )
            elif self._frame_index == self.recording.frame_count - 1:
                self._end_replay(
                    end_reason=TRUNCATED_END_REASON
                    if self.recording.is_truncated
                    else END_OF_RECORDING_END_REASON,
                    banner=TRUNCATED_RECORDING_BANNER
                    if self.recording.is_truncated
                    else END_OF_RECORDING_BANNER,
                )
        if self._window_was_closed or self.controls.quit_requested:
            self._stop(end_reason=QUIT_END_REASON)
        self._frame_index += 1
        self._pump_index = 0
        self._frame_divergence = None
        self.controls.current_frame = self._frame_index
        if self._rebuild is not None:
            self._rebuild.silence_frame()
            if (
                self._frame_index >= self._rebuild.target_frame
                or self.controls.paused
                or self._stop_requested
            ):
                self._finish_rebuild()
        self._begin_frame()

    def finish_run(self: Self) -> None:
        """Settle the result when the run ends (``GameEngine._shutdown``).

        A run that ended while the replay was still running (the game quit or failed before
        the recording's last frame) diverged in length. Either way the blocked state of real
        input is restored (rule 2), and the digest file written when asked for (rule 12).
        """
        self._real_input_block.restore()
        if self.result.end_reason == RUNNING_END_REASON:
            self.result.divergence = Divergence(
                frame_number=self.result.frames_replayed,
                kind=LENGTH_DIVERGENCE,
                subject=RECORDING_SUBJECT,
                field=FRAME_COUNT_FIELD,
                expected=self.recording.frame_count,
                actual=self.result.frames_replayed,
            )
            self._stop(end_reason=DIVERGED_END_REASON)
        if self.options.digest_path is not None:
            divergence = self.result.divergence
            write_digest_file(
                path=self.options.digest_path,
                digests=self._frame_digests,
                divergence=None if divergence is None else divergence.describe(),
            )

    def _current_frame(self: Self) -> dict[str, Any] | None:
        return self.recording.frame(frame_index=self._frame_index)

    def _frame_difference(
        self: Self,
        *,
        frame: dict[str, Any],
        replayed: dict[str, Any],
        control_events: list[ControlEvent],
    ) -> Divergence | None:
        """Return the frame's first difference: its pumps', its markers', then its sprites'.

        Args:
            frame: The recorded frame.
            replayed: The replayed frame, sampled by ``sample_scene_frame``.
            control_events: The control events recorded in the frame.

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
            frozenset({FPSEVENT}) if self.options.fps_source == REAL_REPLAY_FPS else frozenset()
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

    def _drain_real_queue(self: Self) -> list[pygame.event.Event]:
        """Take every event from SDL's queue, blocking real input at SDL from the first (rule 2).

        Returns:
            The real batch, in queue order.

        """
        live_events = self._live_queue.pump_events()
        # After the drain, so the replayed code's posts made before the first drain are kept
        if not self._has_blocked_real_input:
            self._has_blocked_real_input = True
            self._real_input_block.block()
        else:
            # An event manager made since the last drain (a scene's widgets) called
            # set_allowed; block again without a new snapshot
            self._real_input_block.reassert()
        return live_events

    def _sort_live_events(
        self: Self, *, live_events: list[pygame.event.Event], is_first_drain: bool
    ) -> tuple[list[pygame.event.Event], list[pygame.event.Event]]:
        """Split a real batch into internal events and window closes; nothing else reaches the game.

        Classified with the internal-post tracker (its matched posts are consumed). A watched
        replay keeps its real key presses and releases for the next control tick (rule 14),
        except the presses of the first drain: stale ones, queued before the replay.

        Args:
            live_events: The real batch.
            is_first_drain: True for the replay's first drain of the real queue.

        Returns:
            The internal events and the window's QUIT events, each in queue order.

        """
        pending = pending_internal_posts()
        live_internal_events: list[pygame.event.Event] = []
        window_closes: list[pygame.event.Event] = []
        for event in live_events:
            if event_origin(event=event, pending=pending) == INTERNAL_ORIGIN:
                live_internal_events.append(event)
            elif event.type == pygame.QUIT:
                window_closes.append(event)
            elif event.type in WATCHED_REAL_KEY_EVENT_TYPES and not self.options.headless:
                if is_first_drain:
                    # Stale, pressed before the replay: not acted on, but followed in order, so
                    # a key still down is held (its operating-system repeats are not new
                    # presses until it is released)
                    if event.type == pygame.KEYDOWN:
                        self.controls.note_key_already_down(key=event.key)
                    else:
                        self.controls.release_key(key=event.key)
                else:
                    self.viewer.queue_key_event(event_type=event.type, key=event.key)
            # Every other real external event is dropped: real input is blocked at SDL, so
            # these are events queued before the first drain, the window's close event (its
            # QUIT follows) and app lifecycle and system notifications
        return live_internal_events, window_closes

    def _run_control_tick(self: Self, *, now: float) -> None:
        """Read the real queue and act on the viewer's keys, at an outer tick's start (rule 14).

        Args:
            now: The measured time of the tick.

        """
        is_first_drain = not self._has_blocked_real_input
        live_internal_events, window_closes = self._sort_live_events(
            live_events=self._drain_real_queue(), is_first_drain=is_first_drain
        )
        self._held_internal_events.extend(live_internal_events)
        self.viewer.apply_key_events(now=now)
        if window_closes or self.controls.quit_requested:
            self._stop(end_reason=QUIT_END_REASON)
            return
        restart_frame = self.controls.take_restart_request()
        if restart_frame is not None:
            # The engine relaunches the replay at the frame once the run is torn down (rule 15)
            self.result.restart_frame = restart_frame
            self._stop(end_reason=RESTART_END_REASON)

    def _refresh_status_line(self: Self) -> None:
        """Give the controls the status line of the frame the closing outer tick presents."""
        divergence = self.result.divergence
        self.controls.update_status(
            status_line=self.controls.status_line(
                frame_number=self._frame_index,
                seconds=frame_clock_seconds(),
                divergence_frame=None if divergence is None else divergence.frame_number,
                effective_speed=self.viewer.real_speed_if_behind(),
            )
        )

    def _finish_rebuild(self: Self) -> None:
        """End a restarted replay's rebuild: pause it where it is, its music resumed (rule 15)."""
        if self._rebuild is not None:
            self._rebuild.finish()
        self._rebuild = None
        self.controls.rebuild_target_frame = None
        self.controls.paused = True
        self.controls.step_requested = False

    def _is_inner_over(self: Self) -> bool:
        """Report whether no inner frame can run: the replay stopped or its recording is used up.

        Returns:
            True when over.

        """
        return self._stop_requested or self._current_frame() is None

    def _is_inner_running(self: Self) -> bool:
        """Report whether the inner game is running (not over, at the start screen or paused).

        Returns:
            True when the viewer's accumulator should fill.

        """
        return not (self._is_inner_over() or self.controls.awaiting_start or self.controls.paused)

    def _inner_frame_seconds(self: Self) -> float:
        """Return how long the inner frame starting now lasted when recorded (rule 4).

        Returns:
            The next frame's recorded ``dt`` (the duration of this one), or this frame's own
            for the last recorded frame; 0.0 past the end.

        """
        for frame_index in (self._frame_index + 1, self._frame_index):
            if self.recording.frame(frame_index=frame_index) is not None:
                return self.recording.recorded_dt(frame_index=frame_index)
        return 0.0

    def _end_replay(self: Self, *, end_reason: str, banner: str) -> None:
        """End the comparison: stop a headless replay, pause a watched one there (rule 14).

        Args:
            end_reason: The result's end reason.
            banner: The watched replay's banner line (a divergence or the end).

        """
        if self.options.headless:
            self._stop(end_reason=end_reason)
            return
        self.result.end_reason = end_reason
        self.controls.paused = True
        self.controls.banner = banner
        self.controls.debug_overlay.is_visible = True

    def _stop(self: Self, *, end_reason: str) -> None:
        """Stop the replay; a replay that already ended keeps its end reason."""
        if self.result.end_reason == RUNNING_END_REASON:
            self.result.end_reason = end_reason
        self._stop_requested = True


def _installed_engine_version() -> str | None:
    try:
        return importlib.metadata.version('glitchygames')
    except importlib.metadata.PackageNotFoundError:
        return None


def check_recorded_game(*, header: Mapping[str, Any], game_class_name: str) -> None:
    """Refuse a recording of another game.

    Args:
        header: The recording's header fields.
        game_class_name: The class name of the game being started.

    Raises:
        ReplayRefusedError: If the recording's ``game_class`` is a different game.

    """
    recorded_game = header.get(GAME_CLASS_HEADER_FIELD)
    if recorded_game != game_class_name:
        message = (
            f'The recording is of the game {recorded_game!r}, not {game_class_name!r}; '
            'refusing to replay it'
        )
        raise ReplayRefusedError(message)


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

    A recording of another game raises ReplayRefusedError (``check_recorded_game``); an
    unreadable file raises TraceFormatError or OSError (``ReplaySources.from_path``). The engine
    exits with ``ExitCode.UNUSABLE_INPUT`` on each, or ``ExitCode.MISSING_INPUT`` for a missing
    file.

    Args:
        path: The recording.
        game_class_name: The class name of the game being started.
        options: The run's options, given the recorded ones in place; ``replay_fps`` (local, so
            never the recording's) picks the FPS source, ``RECORDED_REPLAY_FPS`` when unset, and
            ``replay_digest`` (local) the digest file (rule 12), none when unset, and
            ``headless`` (local) whether frames are paced (rule 13) and whether the replay is
            watched, starting at its start screen (rule 14) unless ``replay_pause_at_frame``
            (local) restarts it at a pause frame (rule 15; ignored, with a warning, when
            headless), ``replay_restart_handoff`` (local) where a supervised restart hands its
            own restart over (glitchygames/replay/rebuild.py), and ``replay_viewer_state``
            (local) the viewer state it starts with.
        use_fastevents: Drain the real queue with pygame.fastevent (``GameEngine.USE_FASTEVENTS``).

    Returns:
        The replay's sources, not yet installed.

    """
    # Local options (REPLAY_LOCAL_OPTIONS): the recorded ones applied below never replace them
    replay_digest = options.get('replay_digest')
    headless = bool(options.get('headless'))
    pause_at_frame = options.get('replay_pause_at_frame')
    if pause_at_frame is not None and headless:
        LOG.warning(
            '--replay-pause-at-frame is ignored with --headless: nobody could unpause the replay'
        )
        pause_at_frame = None
    restart_handoff = options.get('replay_restart_handoff')
    replay_options = ReplayOptions(
        headless=headless,
        fps_source=options.get('replay_fps') or RECORDED_REPLAY_FPS,
        digest_path=None if replay_digest is None else Path(replay_digest),
        use_fastevents=use_fastevents,
        # Every watched replay starts at its start screen (rule 14), but a restart: the viewer
        # already started it (rule 15)
        wait_for_start=not headless and pause_at_frame is None,
        pause_at_frame=pause_at_frame,
        restart_handoff_path=None if restart_handoff is None else Path(restart_handoff),
        viewer_state=options.get('replay_viewer_state'),
    )
    sources = ReplaySources.from_path(path=path, options=replay_options)
    check_recorded_game(header=sources.header, game_class_name=game_class_name)
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
    if replay_options.fps_source == REAL_REPLAY_FPS:
        LOG.warning(REAL_REPLAY_FPS_NOTICE)
    return sources


def announce_replay(*, path: Path, sources: ReplaySources) -> None:
    """Log that the run replays the recording (and where a truncated one stops).

    Called by the engine once it is sure to replay (``--audit`` replays in child processes
    instead, and refuses a truncated recording), so nothing announces a replay that will not
    happen.

    Args:
        path: The recording.
        sources: Its replay sources.

    """
    if sources.recording.is_truncated:
        LOG.warning(
            '%s is cut off after %d complete frames; replaying up to there',
            path,
            sources.recording.frame_count,
        )
    LOG.info(
        'Replaying %s (%d frames, random seed %d)',
        path,
        sources.recording.frame_count,
        sources.random_seed,
    )
