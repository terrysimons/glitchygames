"""Replays through the real engine: record a session, replay it, compare every frame."""

from __future__ import annotations

import argparse
import collections
import gzip
import importlib.metadata
import json
import os
import re
import signal
import sys
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pygame
import pytest
from pydantic import ValidationError
from scripts.record_golden_traces import (
    GAME_SCENES,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    record_trace,
    replay_golden_recording,
)
from scripts.record_scripted_session import REPLAY_FIXTURE_DIRECTORY, REPLAY_FIXTURE_SUFFIX

from glitchygames.debug import DebugPanel
from glitchygames.engine import GameEngine
from glitchygames.engine import game_engine as game_engine_module
from glitchygames.events import FPSEVENT
from glitchygames.exit_codes import ExitCode
from glitchygames.live_sources import LiveSources
from glitchygames.process import run_command
from glitchygames.recording import (
    INTERNAL_ORIGIN,
    RECORDING_FORMAT_THREE_FIELDS,
    SCENE_START_FIELD,
    GameplayRecorder,
    RecordingSources,
    pending_internal_posts,
    post_event,
)
from glitchygames.replay import audit
from glitchygames.replay import driver as driver_module
from glitchygames.replay import viewer as viewer_module
from glitchygames.replay.audit import (
    AUDIT_HASH_SEEDS,
    AuditRunError,
    ReplayDigestRun,
    audit_command,
    compare_runs,
    environment_reaches_children,
    frame_digest,
    read_digest_file,
)
from glitchygames.replay.controls import CONTROL_TICK_SECONDS, FIRST_PAUSED_FRAME
from glitchygames.replay.driver import (
    DEFAULT_REPLAY_OPTIONS,
    EVENT_DIVERGENCE,
    LENGTH_DIVERGENCE,
    REAL_REPLAY_FPS,
    RECORDED_REPLAY_FPS,
    REPLAY_LOCAL_OPTIONS,
    REPORT_HISTORY_FRAMES,
    SCENE_DIVERGENCE,
    SPRITE_DIVERGENCE,
    WATCHED_REAL_KEY_EVENT_TYPES,
    Divergence,
    ReplayExitPolicy,
    ReplayOptions,
    ReplayRefusedError,
    ReplayResult,
    ReplaySources,
    apply_recorded_options,
    bookmarked_copy_path,
    check_recorded_game,
    write_bookmarked_copy,
)
from glitchygames.replay.input_blocking import REAL_INPUT_EVENT_TYPES, EventTypeBlock
from glitchygames.replay.rebuild import REBUILD_PROGRESS_INTERVAL_SECONDS, Rebuild, ViewerState
from glitchygames.replay.viewer import MAX_INNER_FRAMES_PER_TICK
from glitchygames.scenes import SceneManager
from glitchygames.sources import (
    active_sources,
    frame_clock_seconds,
    install_sources,
    reset_sources,
)
from glitchygames.timing import FastTimer
from glitchygames.tracing import GZIP_WINDOW_BITS, read_trace_result, write_trace
from tests.replay.replay_helpers import rewrite_recording, tamper_first_sprite_rect
from tests.world import test_gameplay_recording as recording_test_module
from tests.world.test_gameplay_recording import (
    FAKE_CLOCK_STEP_SECONDS,
    RANDOM_SEED,
    RUN_ENGINE_ARGUMENTS,
    DepartureRecordedScene,
    Script,
    _key,
    _schedule_quit_in_arrival,
    build_engine,
    constructed_engine,
    engine_run_environment,
    run_engine,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

# Part 1's replay: stops at the first divergence or the last frame (a watched replay pauses)
HEADLESS_REPLAY_OPTIONS = ReplayOptions(headless=True)

GOLDEN_SCRIPT_FRAMES = 300
# A golden recording of this many frames, replayed by a harness stopped after the frame limit
EARLY_STOP_RECORDED_FRAMES = 30
EARLY_STOP_FRAME_LIMIT = 10
# The departure scene's marker is placed from the clocks in this frame; the scene is still
# active at the frame's end (its transition starts in frame 3), so the placement is compared
CLOCK_ACTION_FRAME = 2

# Child processes of the end-to-end audit tests are killed if they hang
RECORD_TIMEOUT_SECONDS = 120.0
AUDIT_TIMEOUT_SECONDS = 240.0

# A game whose sprite moves by an unseeded random amount (the guard test forbids this inside the
# package; a game file outside it can still do it, which is what --audit is for). It quits
# itself after FRAMES_BEFORE_QUIT frames.
UNSEEDED_GAME_SOURCE = """\
import random

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

FRAMES_BEFORE_QUIT = 20


class Mover(pygame.sprite.DirtySprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface((4, 4))
        self.rect = self.image.get_rect()
        self.dirty = 2

    def update_nested_sprites(self):
        pass


class UnseededGame(Scene):
    NAME = 'UnseededGame'

    def __init__(self, options=None, groups=None):
        super().__init__(options=options, groups=groups)
        self.mover = Mover()
        self.all_sprites.add(self.mover)
        self.frames = 0

    def dt_tick(self, dt):
        self.frames += 1
        self.mover.rect.x += int(random.SystemRandom().random() * 10)
        if self.frames == FRAMES_BEFORE_QUIT:
            GameEngine.quit_game()


if __name__ == '__main__':
    GameEngine(game=UnseededGame).start()
"""

# A stand-in replay child for _run_replay_subprocess: writes its PYTHONHASHSEED as its one
# digest to the --replay-digest path (the last argument), then a clean summary line
DIGEST_WRITING_CHILD_SOURCE = """\
import json
import os
import sys

with open(sys.argv[-1], 'w', encoding='utf-8') as digest_file:
    digest_file.write(json.dumps({'frame': 0, 'digest': os.environ['PYTHONHASHSEED']}) + '\\n')
    digest_file.write(json.dumps({'divergence': None}) + '\\n')
"""


def digest_writing_child_source(*, divergence: str | None, exit_status: int) -> str:
    """Python source for a child that writes a one-frame digest file and exits with a status.

    Returns:
        The source, run with ``python -c``; the digest file is its last argument.

    """
    return (
        'import json, sys\n'
        "with open(sys.argv[-1], 'w', encoding='utf-8') as digest_file:\n"
        "    digest_file.write(json.dumps({'frame': 0, 'digest': 'a'}) + '\\n')\n"
        f"    digest_file.write(json.dumps({{'divergence': {divergence!r}}}) + '\\n')\n"
        f'raise SystemExit({exit_status})\n'
    )


# The live wall clock's reading when a paced recording starts (clocks_paced_by_frames)
PACED_RECORDING_START = datetime(2026, 10, 19, 12, 0, 0, 250000, tzinfo=UTC)

# Post an FPS event every frame (the interval is halved, and every frame is longer than 0.5 ms)
EVERY_FRAME_FPS_ARGUMENTS = ('--fps-log-interval-ms', '1')
# A replay machine whose fake clock runs at another speed than the recording's, so its measured
# frame times (and FPS) differ from the recorded ones
REPLAY_MACHINE_CLOCK_STEP_SECONDS = FAKE_CLOCK_STEP_SECONDS * 2.5
# A recorded FPS value the replay never posts
TAMPERED_FPS = 12345.0
# The frame of the scripted session a test action runs in
ACTION_FRAME = 2
# An exit status no engine path uses, for fake children that fail in a way the audit cannot read
UNLISTED_EXIT_STATUS = 9
# The status a probe child exits with when its interpreter ignores the environment
ENVIRONMENT_IGNORED_EXIT_STATUS = 7


def record_session(
    *,
    tmp_path: Path,
    mocker,
    action: Callable[[], None] | None = None,
    action_frame: int = 1,
    extra_arguments: Sequence[str] = (),
) -> Path:
    """Record the departure/arrival scripted session (with an optional scripted action).

    `extra_arguments` are added to the recording run's command line.

    Returns:
        The recording's path.

    """
    recording_path = tmp_path / 'session.jsonl.gz'
    # engine_run_environment resets Script, so the script is set inside it
    with engine_run_environment(mocker):
        Script.events_by_frame = {
            1: [_key(pygame.KEYDOWN, pygame.K_a, unicode='a')],
            2: [_key(pygame.KEYUP, pygame.K_a)],
        }
        Script.action, Script.action_frame = action, action_frame
        _schedule_quit_in_arrival()
        run_engine(
            '--record-trace',
            str(recording_path),
            '--random-seed',
            str(RANDOM_SEED),
            *extra_arguments,
        )
    return recording_path


def replay_session(
    *,
    recording_path: Path,
    mocker,
    events_by_frame: dict[int, list[pygame.event.Event]] | None = None,
    action: Callable[[], None] | None = None,
    action_frame: int = 1,
) -> GoldenTraceEngine:
    """Replay headless (``--headless``) through the real engine.

    The test scenes post their scripted input with raw pygame.event.post, so the recording holds
    it as external events and the replay serves it from the recording: by default the scenes post
    nothing during the replay. `events_by_frame` makes them post real events anyway (they must be
    dropped); `action` repeats a scripted action that is not input (a save write, a clock read).

    Every replay ends GameEngine.start() with SystemExit carrying its own exit code
    (``ReplayResult.exit_code`` under its exit policy); that exit is expected here. Any other
    exit (a crash's ``ExitCode.INTERNAL_ERROR``, a refusal in ``__init__``) propagates.

    Returns:
        The engine, after the replay ran.

    Raises:
        SystemExit: A refusal, or an exit other than the replay's own.

    """
    with engine_run_environment(mocker):
        Script.events_by_frame = events_by_frame or {}
        Script.action, Script.action_frame = action, action_frame
        engine = build_engine(
            scene_class=DepartureRecordedScene,
            arguments=(*RUN_ENGINE_ARGUMENTS, '--replay-trace', str(recording_path), '--headless'),
        )
        try:
            engine.start()
        except SystemExit as exit_request:
            assert engine.replay_sources is not None
            sources = engine.replay_sources
            if exit_request.code != sources.result.exit_code(policy=sources.options.exit_policy):
                raise
        else:
            pytest.fail('A replay must end GameEngine.start() with SystemExit')
    return engine


def replay_session_with_arguments(
    *,
    recording_path: Path,
    mocker,
    arguments: tuple[str, ...],
    action: Callable[[], None] | None = None,
    action_frame: int = 1,
) -> GoldenTraceEngine:
    """Replay through the real engine with extra command-line arguments; the exit propagates.

    Returns:
        The engine (only if start() returned, which a replay never does).

    """
    with engine_run_environment(mocker):
        Script.action, Script.action_frame = action, action_frame
        return run_engine('--replay-trace', str(recording_path), *arguments)


def add_recorded_internal_event(*, recording_path: Path, frame_number: int) -> None:
    """Add an internal event the replayed code never posts to the frame's first batch."""

    def add(trace: dict[str, Any]) -> None:
        trace['frames'][frame_number]['event_batches'][0].append({
            'type': pygame.USEREVENT + 41,
            'name': 'UserEvent',
            'origin': 'internal',
            'attributes': {},
        })

    rewrite_recording(recording_path=recording_path, change=add)


def add_recorded_external_event(
    *, recording_path: Path, frame_number: int, record: dict[str, Any]
) -> None:
    """Append an external event record to the frame's first batch."""

    def add(trace: dict[str, Any]) -> None:
        trace['frames'][frame_number]['event_batches'][0].append(record)

    rewrite_recording(recording_path=recording_path, change=add)


def tamper_first_recorded_fps(*, recording_path: Path) -> None:
    """Change the value of the first recorded FPS event to TAMPERED_FPS."""

    def tamper(trace: dict[str, Any]) -> None:
        for frame in trace['frames']:
            for batch in frame['event_batches']:
                for record in batch:
                    if record['type'] == FPSEVENT:
                        record['attributes']['fps'] = TAMPERED_FPS
                        return
        message = 'The recording has no FPS event'
        raise AssertionError(message)

    rewrite_recording(recording_path=recording_path, change=tamper)


def recorded_fps_values(*, recording_path: Path) -> list[float]:
    """Return every recorded FPS event's value, in order.

    Returns:
        The values.

    """
    frames = read_trace_result(path=recording_path).trace['frames']
    return [
        record['attributes']['fps']
        for frame in frames
        for batch in frame['event_batches']
        for record in batch
        if record['type'] == FPSEVENT
    ]


def delivered_events(*, pump_spy) -> list[pygame.event.Event]:
    """Return every event the engine's pump returned, in order.

    Returns:
        The events.

    """
    return [event for batch in pump_spy.spy_return_list for event in batch]


def blocked_states() -> dict[int, bool]:
    """Return whether SDL blocks each of REAL_INPUT_EVENT_TYPES now.

    Returns:
        Event type -> blocked.

    """
    return {
        event_type: pygame.event.get_blocked(event_type) for event_type in REAL_INPUT_EVENT_TYPES
    }


def gzip_lines(*, recording_path: Path) -> list[bytes]:
    """Return the recording's decompressed lines (header first).

    Returns:
        The lines, each with its newline.

    """
    with gzip.open(recording_path, 'rb') as recording_file:
        return recording_file.readlines()


def cut_off_after_frame(*, recording_path: Path, frame_number: int) -> None:
    """Keep the header and frames 0..frame_number, then half of the next line.

    With no gzip end-of-stream: what a killed recorder leaves.
    """
    lines = gzip_lines(recording_path=recording_path)
    partial_line = lines[frame_number + 2]
    kept = b''.join(lines[: frame_number + 2]) + partial_line[: len(partial_line) // 2]
    compressor = zlib.compressobj(wbits=GZIP_WINDOW_BITS)
    recording_path.write_bytes(compressor.compress(kept) + compressor.flush(zlib.Z_SYNC_FLUSH))


def downgrade_to_version_two(*, recording_path: Path) -> None:
    """Drop the format-3 fields and write the file as format version 2."""
    trace = read_trace_result(path=recording_path).trace
    for frame in trace['frames']:
        for field_name in RECORDING_FORMAT_THREE_FIELDS:
            frame.pop(field_name, None)
    write_trace(trace=trace, path=recording_path)
    lines = gzip_lines(recording_path=recording_path)
    header = json.loads(lines[0])
    header['format_version'] = 2
    for field_name in ('saves', 'devices', 'device_enumeration'):
        header.pop(field_name, None)
    with gzip.open(recording_path, 'wb') as recording_file:
        recording_file.write((json.dumps(header) + '\n').encode('utf-8'))
        recording_file.writelines(lines[1:])


def clocks_paced_by_frames(mocker) -> None:
    """Make the live clocks read as a perfectly paced run (what a replay serves).

    A recording made with the real wall clock reads real time, which no replay can serve (the
    replay's wall clock is the recording's start plus the frame clock). With the live wall clock
    at PACED_RECORDING_START plus the frame clock, a session that reads the clocks is replayable
    exactly (elapsed seconds are the frame clock live too, so they need no pacing).
    """
    mocker.patch.object(
        game_engine_module,
        'datetime',
        mocker.Mock(now=mocker.Mock(return_value=PACED_RECORDING_START)),
    )

    def paced_wall_clock_time(_sources: LiveSources) -> datetime:
        return PACED_RECORDING_START + timedelta(seconds=frame_clock_seconds())

    mocker.patch.object(LiveSources, 'wall_clock_time', new=paced_wall_clock_time)


def minimal_sources(
    *,
    frames: list[dict[str, Any]],
    is_truncated: bool = False,
    options: ReplayOptions = HEADLESS_REPLAY_OPTIONS,
) -> ReplaySources:
    """Build replay sources over in-memory frames (no file), headless unless told otherwise.

    Returns:
        The sources.

    """
    header = {
        'game_class': 'SomeGame',
        'random_seed': RANDOM_SEED,
        'recorded_at': '2026-10-19T12:00:00',
        'options': {},
    }
    return ReplaySources(
        header=header,
        frames=frames,
        format_version=3,
        is_truncated=is_truncated,
        options=options,
    )


def start_replay_in_harness(
    *, recording_path: Path, extra_arguments: tuple[str, ...] = ()
) -> GoldenTraceSceneManager:
    """Build the replay engine in the harness and return the manager, without start().

    A watched replay unless ``extra_arguments`` say ``--headless``. The caller steps frames
    (``run_frame``) or starts the loop, and uninstalls the manager afterwards. The test scenes'
    script is reset first: a recording made just before leaves its frame count in it.

    Returns:
        The scene manager, with the game scene active and the replay's sources installed.

    """
    Script.reset()
    manager = GoldenTraceSceneManager.install()
    engine = build_engine(
        scene_class=DepartureRecordedScene,
        arguments=(
            *RUN_ENGINE_ARGUMENTS,
            '--replay-trace',
            str(recording_path),
            *extra_arguments,
        ),
    )
    engine.install_game(scene_class=DepartureRecordedScene)
    return manager


def harness_replay_sources(*, manager: GoldenTraceSceneManager) -> ReplaySources:
    """Return the replay sources of a harness started by ``start_replay_in_harness``.

    Returns:
        The sources.

    """
    engine = manager.game_engine
    assert engine is not None
    assert engine.replay_sources is not None
    return engine.replay_sources


class FakeMeasuredClock:
    """The watched replay's measured clock, advanced only by its sleeps or by the test.

    Patches ``glitchygames.replay.viewer.measured_seconds``, ``sleep_for`` and
    ``sleep_coarsely`` (the viewer's sleeps until its next outer tick), so a watched replay's
    outer ticks run in no real time.

    Attributes:
        now: The measured time, in seconds.

    """

    def __init__(self, *, mocker, on_wait: Callable[[], None] | None = None) -> None:
        """Install the fake clock (undone with the test's mocker).

        Args:
            mocker: pytest-mock's fixture.
            on_wait: Called after each sleep has advanced the clock.

        """
        self.now = 1000.0
        self._on_wait = on_wait
        mocker.patch.object(viewer_module, 'measured_seconds', side_effect=self.read)
        mocker.patch.object(viewer_module, 'sleep_for', side_effect=self.wait)
        mocker.patch.object(viewer_module, 'sleep_coarsely', side_effect=self.wait)

    def read(self) -> float:
        """Return the fake time.

        Returns:
            Seconds.

        """
        return self.now

    def advance(self, *, seconds: float) -> None:
        """Move the fake time on."""
        self.now += seconds

    def wait(self, *, seconds: float) -> None:
        """Sleep: move the fake time on by ``seconds`` (sleep_for's signature)."""
        self.now += seconds
        if self._on_wait is not None:
            self._on_wait()


def press_keys_while_held(
    *,
    mocker,
    keys: Sequence[int],
    before_each_press: Callable[[], None] | None = None,
) -> FakeMeasuredClock:
    """Act as a watched replay's viewer: press the next key whenever the replay waits for one.

    Installs a ``FakeMeasuredClock``. Each time the replay sleeps while it waits for the viewer
    (at its start screen, or paused), one real key press (KEYDOWN, then KEYUP) is posted, which
    the next control tick reads. Sleeps until a frame is due press nothing. A replay that waits
    for the viewer after every key was pressed fails the test instead of waiting forever.

    Args:
        mocker: pytest-mock's fixture.
        keys: The keys, in order.
        before_each_press: Called before each press (to note what the viewer sees).

    Returns:
        The fake clock.

    """
    remaining_keys = list(keys)

    def press_next_key() -> None:
        sources = active_sources()
        assert isinstance(sources, ReplaySources)
        if not (sources.controls.awaiting_start or sources.controls.paused):
            return
        if before_each_press is not None:
            before_each_press()
        if not remaining_keys:
            message = 'the replay waited for the viewer after every key was pressed'
            raise AssertionError(message)
        key = remaining_keys.pop(0)
        pygame.event.post(_key(pygame.KEYDOWN, key))
        pygame.event.post(_key(pygame.KEYUP, key))

    return FakeMeasuredClock(mocker=mocker, on_wait=press_next_key)


def run_next_viewer_tick(*, sources: ReplaySources) -> None:
    """Close the viewer's open outer tick, if any, then run the next tick until it closes.

    The inner frames the ticks would run are not run (the frame index stays), so this only
    reads the viewer's keys once more.

    """
    while not sources.hold_frame():
        pass
    while not sources.hold_frame():
        pass


def inner_frames_per_tick(
    *, sources: ReplaySources, clock: FakeMeasuredClock, status_spy, seconds: float
) -> list[int]:
    """Run a watched replay's outer loop as the scene manager would, on the fake clock.

    Each inner frame ends at the doors (compared) and takes a tenth of a millisecond of real
    time.

    Args:
        sources: The watched replay.
        clock: Its fake measured clock.
        status_spy: A spy on ``sources.controls.update_status`` (called once per outer tick).
        seconds: How long to run, in fake measured seconds.

    Returns:
        How many inner frames each outer tick opened meanwhile ran, in order.

    """
    first_tick = status_spy.call_count + 1
    frames_by_tick: collections.Counter[int] = collections.Counter()
    end_seconds = clock.now + seconds
    while clock.now < end_seconds:
        if sources.hold_frame():
            continue
        frames_by_tick[status_spy.call_count] += 1
        sources.end_frame(frame_number=0, dt=0.0, scene=None, control_events=[])
        clock.advance(seconds=0.0001)
    return [frames_by_tick[tick] for tick in range(first_tick, status_spy.call_count + 1)]


def watched_minimal_sources(*, recorded_dt: float, frame_count: int = 5000) -> ReplaySources:
    """Installed watched replay sources over in-memory frames of one recorded dt.

    Returns:
        The sources.

    """
    sources = minimal_sources(
        frames=[recorded_frame(frame_number=index, dt=recorded_dt) for index in range(frame_count)],
        options=DEFAULT_REPLAY_OPTIONS,
    )
    install_sources(sources=sources)
    return sources


def recorded_frame(*, frame_number: int, dt: float = 0.25) -> dict[str, Any]:
    """Return a recorded frame with no scene, no sprites and no event batch (never pumped).

    Returns:
        The frame record.

    """
    return {
        'frame': frame_number,
        'scene': None,
        'sprites': [],
        'dt': dt,
        'event_batches': [],
    }


class TestRoundTrip:
    """A recorded session replays without divergence."""

    def test_scripted_session_replays_without_divergence(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        result = engine.replay_sources.result
        assert result.divergence is None
        assert result.end_reason == 'end_of_recording'
        assert result.frames_replayed == len(read_trace_result(path=recording_path).trace['frames'])

    @pytest.mark.parametrize('game_key', sorted(GAME_SCENES))
    def test_golden_script_recording_replays_without_divergence(self, game_key, tmp_path):
        recording_path = tmp_path / f'{game_key}.jsonl.gz'
        record_trace(game_key, frame_count=GOLDEN_SCRIPT_FRAMES, recording_path=recording_path)
        result = replay_golden_recording(game_key=game_key, path=recording_path)
        assert result.divergence is None
        assert result.frames_replayed == GOLDEN_SCRIPT_FRAMES

    def test_golden_harness_stopped_early_reports_a_length_divergence(self, tmp_path):
        recording_path = tmp_path / 'paddleslap.jsonl.gz'
        record_trace(
            'paddleslap', frame_count=EARLY_STOP_RECORDED_FRAMES, recording_path=recording_path
        )
        result = replay_golden_recording(
            game_key='paddleslap', path=recording_path, frame_limit=EARLY_STOP_FRAME_LIMIT
        )
        assert result.end_reason == 'diverged'
        divergence = result.divergence
        assert divergence is not None
        assert (divergence.kind, divergence.expected, divergence.actual) == (
            LENGTH_DIVERGENCE,
            EARLY_STOP_RECORDED_FRAMES,
            EARLY_STOP_FRAME_LIMIT,
        )

    def test_clock_reads_replay_exactly(self, mocker, tmp_path):
        from glitchygames.clock import elapsed_seconds, wall_clock_epoch_seconds

        def place_marker_from_clocks() -> None:
            scene = SceneManager().active_scene
            marker = scene.marker
            marker.rect.x = int(wall_clock_epoch_seconds() * 1000) % 1000
            marker.rect.y = int(elapsed_seconds() * 1000) % 1000

        clocks_paced_by_frames(mocker)
        recording_path = record_session(
            tmp_path=tmp_path,
            mocker=mocker,
            action=place_marker_from_clocks,
            action_frame=CLOCK_ACTION_FRAME,
        )
        mocker.stopall()
        # The replay must not read real time: the live wall clock is a mock from here on
        mocker.patch('glitchygames.live_sources.datetime')
        engine = replay_session(
            recording_path=recording_path,
            mocker=mocker,
            action=place_marker_from_clocks,
            action_frame=CLOCK_ACTION_FRAME,
        )
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        assert engine.replay_sources.result.end_reason == 'end_of_recording'


class TestDivergence:
    """The first difference is found, reported and logged."""

    def test_a_one_pixel_change_is_reported_at_its_frame(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        result = engine.replay_sources.result
        divergence = result.divergence
        assert divergence is not None
        assert (divergence.frame_number, divergence.kind, divergence.field) == (
            3,
            SPRITE_DIVERGENCE,
            'rect',
        )
        assert result.end_reason == 'diverged'
        assert result.frames_replayed == 4

    def test_a_watched_divergence_is_logged_and_exits_as_diverged(
        self, mocker, tmp_path, caplog, capsys
    ):
        """A replay without --headless logs its report (stdout stays clean) and still exits."""
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        shutdown_spy = mocker.spy(GoldenTraceEngine, '_shutdown')
        # Space starts the replay; it pauses at the divergence, and Esc ends it
        press_keys_while_held(mocker=mocker, keys=(pygame.K_SPACE, pygame.K_ESCAPE))
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path, mocker=mocker, arguments=()
            )
        assert exit_info.value.code == ExitCode.REPLAY_DIVERGED
        engine = shutdown_spy.call_args.args[0]
        assert engine.replay_sources is not None
        divergence = engine.replay_sources.result.divergence
        assert divergence is not None
        assert divergence.describe().startswith('frame 3: sprite ')
        assert engine.replay_sources.result.report() in caplog.text
        assert f'Replay diverged at {divergence.describe()}' in caplog.text
        assert f'Exiting with {ExitCode.REPLAY_DIVERGED.describe()}' in caplog.text
        assert 'Replay diverged' not in capsys.readouterr().out

    def test_a_watched_match_is_logged_and_exits_as_success(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        recorded_frame_count = len(read_trace_result(path=recording_path).trace['frames'])
        caplog.set_level('INFO', logger='game.engine')
        # The recorded game quits itself in its last frame, so Space is the only key needed
        press_keys_while_held(mocker=mocker, keys=(pygame.K_SPACE,))
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path, mocker=mocker, arguments=()
            )
        assert exit_info.value.code == ExitCode.SUCCESS
        assert f'Replay matched {recorded_frame_count} frames (end of recording)' in caplog.text

    def test_describe_format(self):
        divergence = Divergence(
            frame_number=6120,
            kind=SPRITE_DIVERGENCE,
            subject='Ball#2',
            field='rect',
            expected=[412, 300, 16, 16],
            actual=[412, 301, 16, 16],
        )
        assert divergence.describe() == (
            'frame 6120: sprite Ball#2 rect expected [412, 300, 16, 16], got [412, 301, 16, 16]'
        )

    def test_a_different_scene_is_a_scene_divergence(self, mocker):
        frame = recorded_frame(frame_number=0)
        frame['scene'] = 'TitleScene'
        sources = minimal_sources(frames=[frame])
        scene = mocker.Mock()
        scene.all_sprites.sprites.return_value = []
        sources.end_frame(frame_number=0, dt=0.25, scene=scene, control_events=[])
        divergence = sources.result.divergence
        assert divergence is not None
        assert divergence.kind == SCENE_DIVERGENCE
        assert divergence.describe() == 'frame 0: scene expected TitleScene, got Mock'

    def test_missing_and_extra_sprites_diverge_as_present(self, mocker):
        frame = recorded_frame(frame_number=0)
        # The scene stand-in below is a Mock, so its class name is 'Mock'
        frame['scene'] = 'Mock'
        sources = minimal_sources(frames=[frame])
        assert sources.recording.recorded_frame_fields(frame_index=0) == {}
        scene = mocker.Mock()
        scene.all_sprites.sprites.return_value = [
            mocker.Mock(rect=pygame.Rect(1, 2, 3, 4), visible=True)
        ]
        sources.end_frame(frame_number=0, dt=0.25, scene=scene, control_events=[])
        divergence = sources.result.divergence
        assert divergence is not None
        assert (divergence.kind, divergence.field, divergence.expected, divergence.actual) == (
            SPRITE_DIVERGENCE,
            'present',
            False,
            True,
        )

    def test_a_run_that_ends_early_is_a_length_divergence(self):
        sources = minimal_sources(
            frames=[recorded_frame(frame_number=0), recorded_frame(frame_number=1)]
        )
        sources.end_frame(frame_number=0, dt=0.25, scene=None, control_events=[])
        sources.finish_run()
        divergence = sources.result.divergence
        assert divergence is not None
        assert (divergence.kind, divergence.expected, divergence.actual) == (
            LENGTH_DIVERGENCE,
            2,
            1,
        )
        assert sources.result.end_reason == 'diverged'


class TestReplayDoors:
    """What each replay door serves."""

    def test_frame_time_serves_each_recorded_dt_then_the_measurement(self):
        sources = minimal_sources(
            frames=[recorded_frame(frame_number=0, dt=0.5), recorded_frame(frame_number=1, dt=0.75)]
        )
        assert sources.frame_seconds(measured=9.0) == 0.5
        sources.end_frame(frame_number=0, dt=0.5, scene=None, control_events=[])
        assert sources.frame_seconds(measured=9.0) == 0.75
        sources.end_frame(frame_number=1, dt=0.75, scene=None, control_events=[])
        assert sources.frame_seconds(measured=9.0) == 9.0
        assert sources.stop_requested
        assert sources.result.end_reason == 'end_of_recording'

    def test_frames_are_indexed_by_the_sources_own_count(self):
        """The scene manager's frame numbers (a playback scope's) never pick a recorded frame."""
        sources = minimal_sources(
            frames=[recorded_frame(frame_number=0, dt=0.5), recorded_frame(frame_number=1, dt=0.75)]
        )
        sources.end_frame(frame_number=500, dt=0.5, scene=None, control_events=[])
        assert sources.frame_seconds(measured=9.0) == 0.75

    def test_wall_clock_is_recorded_start_plus_frame_clock(self):
        from glitchygames.sources import advance_frame_clock

        sources = minimal_sources(frames=[recorded_frame(frame_number=0)])
        advance_frame_clock(seconds=1.5)
        assert sources.wall_clock_time() == datetime(2026, 10, 19, 12, 0, 1, 500000, tzinfo=UTC)

    def test_recorded_frame_fields_for_a_rebaseline(self):
        frame = recorded_frame(frame_number=0)
        frame['saves_opened'] = {'game': {}}
        frame['device_enumeration'] = [
            {'call': 'joystick_count', 'device_index': None, 'value': 0, 'error': None}
        ]
        sources = minimal_sources(frames=[frame])
        assert sources.recording.recorded_frame_fields(frame_index=0) == {
            'saves_opened': {'game': {}},
            'device_enumeration': frame['device_enumeration'],
        }

    def test_recorded_options_override_all_but_the_local_ones(self):
        options = {'resolution': '640x480', 'log_level': 'debug', 'replay_trace': 'here'}
        apply_recorded_options(
            options=options,
            recorded={
                'resolution': '320x240',
                'log_level': 'warning',
                'replay_trace': None,
                'input_mode': 'joystick',
                'pair': [1, 2],
            },
        )
        assert options == {
            'resolution': '320x240',
            'log_level': 'debug',
            'replay_trace': 'here',
            'input_mode': 'joystick',
            'pair': (1, 2),
        }
        assert {'replay_trace', 'record_trace', 'log_level'} <= REPLAY_LOCAL_OPTIONS

    def test_debug_events_stays_local(self):
        """debug_events follows this run's log level, never the recording's."""
        options = {'debug_events': True}
        apply_recorded_options(options=options, recorded={'debug_events': False})
        assert options == {'debug_events': True}

    def test_the_real_queue_is_drained_with_the_engines_fastevents_setting(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        mocker.patch.object(GameEngine, 'USE_FASTEVENTS', new=True)
        live_sources_spy = mocker.spy(LiveSources, '__init__')
        replay_session(recording_path=recording_path, mocker=mocker)
        assert live_sources_spy.call_args_list
        assert all(
            call.kwargs['use_fastevents'] is True for call in live_sources_spy.call_args_list
        )

    def test_tracking_survives_a_recording_wrapping_the_replay(self, tmp_path):
        """install_sources tells the replay it is replaced, then installed again inside."""
        sources = minimal_sources(frames=[recorded_frame(frame_number=0)])
        install_sources(sources=sources)
        recorder = GameplayRecorder(path=tmp_path / 'rebaseline.jsonl.gz', header={})
        try:
            install_sources(sources=RecordingSources(inner=sources, recorder=recorder))
            recorder.close()
            # The recorder gave up its ownership; the replay, installed inside, still holds one
            post_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
            assert len(pending_internal_posts()) == 1
            batch = sources.pump_events()
        finally:
            recorder.close()
        assert [(event.type, event.key) for event in batch] == [(pygame.KEYDOWN, pygame.K_z)]
        assert sources.last_batch_origins() == [INTERNAL_ORIGIN]

    def test_a_recording_over_a_replay_copies_its_origins_and_frame_fields(self, mocker, tmp_path):
        """Over a replay, origins come from its merge and saves/device fields from its frames."""
        enumeration = [{'call': 'joystick_count', 'device_index': None, 'value': 0, 'error': None}]
        frame = {
            **recorded_frame(frame_number=0),
            'saves_opened': {'game': {}},
            'device_enumeration': enumeration,
        }
        sources = minimal_sources(frames=[frame])
        install_sources(sources=sources)
        key_press = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z)
        mocker.patch.object(sources, 'pump_events', return_value=[key_press])
        # The replay served the press as a recorded external event
        mocker.patch.object(sources, 'last_batch_origins', return_value=['external'])
        recording_path = tmp_path / 'rebaseline.jsonl.gz'
        recorder = GameplayRecorder(path=recording_path, header={})
        recording_sources = RecordingSources(inner=sources, recorder=recorder, replayed=sources)
        try:
            # The live tracker would call it internal
            post_event(key_press)
            recording_sources.pump_events()
            # Not snapshotted: the frame's recorded saves_opened is copied instead
            recording_sources.saves(namespace='other')
            recording_sources.end_frame(frame_number=0, dt=0.25, scene=None, control_events=[])
        finally:
            recorder.close()
            pygame.event.clear()
        (recorded,) = read_trace_result(path=recording_path).trace['frames']
        assert [record['origin'] for record in recorded['event_batches'][0]] == ['external']
        assert recorded['saves_opened'] == {'game': {}}
        assert recorded['device_enumeration'] == enumeration
        assert 'devices_opened' not in recorded


class TestReplayFps:
    """--replay-fps: FPS events from the recorded frame times (default) or this machine's."""

    def test_the_default_is_recorded(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.options.fps_source == RECORDED_REPLAY_FPS
        assert minimal_sources(frames=[recorded_frame(frame_number=0)]).options.fps_source == (
            RECORDED_REPLAY_FPS
        )

    def test_the_performance_frame_time_door_serves_each_mode(self):
        recorded_sources = minimal_sources(frames=[recorded_frame(frame_number=0)])
        real_sources = minimal_sources(
            frames=[recorded_frame(frame_number=0)],
            options=ReplayOptions(fps_source=REAL_REPLAY_FPS),
        )
        assert recorded_sources.performance_frame_seconds(measured=9.0, frame_seconds=0.5) == 0.5
        assert real_sources.performance_frame_seconds(measured=9.0, frame_seconds=0.5) == 9.0
        live_sources = LiveSources(random_seed=RANDOM_SEED)
        assert live_sources.performance_frame_seconds(measured=9.0, frame_seconds=0.5) == 0.5

    def test_recorded_posts_the_recorded_fps_on_another_machine(self, mocker, tmp_path):
        recording_path = record_session(
            tmp_path=tmp_path, mocker=mocker, extra_arguments=EVERY_FRAME_FPS_ARGUMENTS
        )
        expected_fps_values = recorded_fps_values(recording_path=recording_path)
        assert expected_fps_values
        mocker.patch.object(
            recording_test_module, 'FAKE_CLOCK_STEP_SECONDS', REPLAY_MACHINE_CLOCK_STEP_SECONDS
        )
        pump_spy = mocker.spy(GoldenTraceEngine, '_pump_events')
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        delivered_fps_values = [
            event.fps for event in delivered_events(pump_spy=pump_spy) if event.type == FPSEVENT
        ]
        assert delivered_fps_values == expected_fps_values

    def test_recorded_compares_the_fps_events(self, mocker, tmp_path):
        recording_path = record_session(
            tmp_path=tmp_path, mocker=mocker, extra_arguments=EVERY_FRAME_FPS_ARGUMENTS
        )
        tamper_first_recorded_fps(recording_path=recording_path)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        divergence = engine.replay_sources.result.divergence
        assert divergence is not None
        assert (divergence.kind, divergence.field) == (EVENT_DIVERGENCE, 'missing internal event')
        assert isinstance(divergence.expected, dict)
        assert divergence.expected['attributes']['fps'] == TAMPERED_FPS

    def test_real_posts_measured_fps_and_does_not_compare_it(self, mocker, tmp_path, caplog):
        recording_path = record_session(
            tmp_path=tmp_path, mocker=mocker, extra_arguments=EVERY_FRAME_FPS_ARGUMENTS
        )
        tamper_first_recorded_fps(recording_path=recording_path)
        recorded_dts = {
            frame['dt'] for frame in read_trace_result(path=recording_path).trace['frames']
        }
        mocker.patch.object(
            recording_test_module, 'FAKE_CLOCK_STEP_SECONDS', REPLAY_MACHINE_CLOCK_STEP_SECONDS
        )
        pump_spy = mocker.spy(GoldenTraceEngine, '_pump_events')
        performance_spy = mocker.spy(ReplaySources, 'performance_frame_seconds')
        shutdown_spy = mocker.spy(GoldenTraceEngine, '_shutdown')
        press_keys_while_held(mocker=mocker, keys=(pygame.K_SPACE,))
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path,
                mocker=mocker,
                arguments=('--replay-fps', REAL_REPLAY_FPS),
            )
        assert exit_info.value.code == ExitCode.SUCCESS
        engine = shutdown_spy.call_args.args[0]
        assert engine.replay_sources is not None
        assert engine.replay_sources.options.fps_source == REAL_REPLAY_FPS
        assert engine.replay_sources.result.divergence is None
        assert engine.replay_sources.result.end_reason == 'end_of_recording'
        measured_frame_seconds = [
            call.kwargs['measured'] for call in performance_spy.call_args_list
        ]
        assert measured_frame_seconds
        assert not recorded_dts & set(measured_frame_seconds)
        delivered_fps_values = [
            event.fps for event in delivered_events(pump_spy=pump_spy) if event.type == FPSEVENT
        ]
        assert delivered_fps_values
        measured_fps_values = {1.0 / seconds for seconds in measured_frame_seconds}
        assert set(delivered_fps_values) <= measured_fps_values
        # The debug overlay's performance panel follows the measured frame times too
        overlay_frame_times = engine.scene_manager.debug_overlay.frame_times()
        assert overlay_frame_times
        assert set(overlay_frame_times) <= set(measured_frame_seconds)
        notices = [
            record
            for record in caplog.records
            if record.getMessage().startswith('--replay-fps real: FPS events follow this machine')
        ]
        assert len(notices) == 1

    def test_without_replay_trace_it_warns_and_is_ignored(self, caplog):
        with constructed_engine('--replay-fps', REAL_REPLAY_FPS) as engine:
            assert engine.replay_sources is None
        warnings_logged = [
            record
            for record in caplog.records
            if '--replay-fps is ignored without --replay-trace' in record.getMessage()
        ]
        assert len(warnings_logged) == 1

    def test_a_recording_cannot_override_it(self):
        assert 'replay_fps' in REPLAY_LOCAL_OPTIONS
        options = {'replay_fps': REAL_REPLAY_FPS}
        apply_recorded_options(options=options, recorded={'replay_fps': RECORDED_REPLAY_FPS})
        assert options == {'replay_fps': REAL_REPLAY_FPS}


class TestRefusals:
    """Recordings that cannot be replayed, or only in part."""

    def test_wrong_game_is_refused(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        rewrite_recording(
            recording_path=recording_path,
            change=lambda trace: trace.update(game_class='SomeOtherGame'),
        )
        with pytest.raises(SystemExit) as exit_info:
            replay_session(recording_path=recording_path, mocker=mocker)
        assert exit_info.value.code == ExitCode.UNUSABLE_INPUT
        assert 'SomeOtherGame' in caplog.text

    def test_a_same_named_game_from_another_module_is_refused(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        rewrite_recording(
            recording_path=recording_path,
            change=lambda trace: trace.update(game_module='some_other_package.game'),
        )
        with pytest.raises(SystemExit) as exit_info:
            replay_session(recording_path=recording_path, mocker=mocker)
        assert exit_info.value.code == ExitCode.UNUSABLE_INPUT
        assert 'some_other_package.game' in caplog.text

    def test_the_recorded_games_module_and_name_are_accepted(self):
        check_recorded_game(
            header={'game_class': 'Game', 'game_module': 'glitchygames.examples.paddleslap'},
            game_class_name='Game',
            game_module='glitchygames.examples.paddleslap',
        )

    def test_another_game_of_the_same_name_is_refused(self):
        with pytest.raises(ReplayRefusedError, match=r'glitchygames\.examples\.joystick_demo'):
            check_recorded_game(
                header={'game_class': 'Game', 'game_module': 'glitchygames.examples.joystick_demo'},
                game_class_name='Game',
                game_module='glitchygames.examples.paddleslap',
            )

    @pytest.mark.parametrize(
        ('header', 'game_module'),
        [
            # Recorded before headers held the module
            ({'game_class': 'Game'}, 'glitchygames.examples.paddleslap'),
            # The same game file run as a script (python paddleslap.py), either way round
            ({'game_class': 'Game', 'game_module': '__main__'}, 'glitchygames.examples.paddleslap'),
            ({'game_class': 'Game', 'game_module': 'glitchygames.examples.paddleslap'}, '__main__'),
        ],
    )
    def test_without_both_modules_the_name_alone_is_checked(self, header, game_module):
        check_recorded_game(header=header, game_class_name='Game', game_module=game_module)
        with pytest.raises(ReplayRefusedError):
            check_recorded_game(header=header, game_class_name='Other', game_module=game_module)

    def test_missing_file_is_refused(self, mocker, tmp_path):
        with pytest.raises(SystemExit) as exit_info:
            replay_session(recording_path=tmp_path / 'missing.jsonl.gz', mocker=mocker)
        assert exit_info.value.code == ExitCode.MISSING_INPUT

    @pytest.mark.parametrize('kind', ['plain text', 'directory'])
    def test_a_file_that_is_not_a_readable_recording_is_unusable_data(
        self, mocker, tmp_path, caplog, kind
    ):
        """A path that exists but is not a gzip recording is unusable data, not missing input."""
        recording_path = tmp_path / 'not-a-recording.jsonl.gz'
        if kind == 'directory':
            recording_path.mkdir()
        else:
            recording_path.write_text('this is not a recording\n', encoding='utf-8')
        with pytest.raises(SystemExit) as exit_info:
            replay_session(recording_path=recording_path, mocker=mocker)
        assert exit_info.value.code == ExitCode.UNUSABLE_INPUT
        assert f'Cannot replay {recording_path}' in caplog.text

    def test_unsupported_format_version_is_refused_without_a_traceback(
        self, mocker, tmp_path, caplog
    ):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        lines = gzip_lines(recording_path=recording_path)
        header = json.loads(lines[0])
        header['format_version'] = 99
        with gzip.open(recording_path, 'wb') as recording_file:
            recording_file.write((json.dumps(header) + '\n').encode('utf-8'))
            recording_file.writelines(lines[1:])
        caplog.clear()
        with pytest.raises(SystemExit) as exit_info:
            replay_session(recording_path=recording_path, mocker=mocker)
        assert exit_info.value.code == ExitCode.UNUSABLE_INPUT
        refusals = [record for record in caplog.records if 'Cannot replay' in record.getMessage()]
        assert len(refusals) == 1
        assert 'format_version 99' in refusals[0].getMessage()
        assert refusals[0].exc_info is None

    def test_recording_over_a_replay_is_refused(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        with engine_run_environment(mocker), pytest.raises(SystemExit) as exit_info:
            run_engine(
                '--replay-trace',
                str(recording_path),
                '--record-trace',
                str(tmp_path / 'over-the-replay.jsonl.gz'),
            )
        assert exit_info.value.code == ExitCode.OPTIONS_REFUSED
        assert 'record over a replay with --rebaseline NEW --headless' in caplog.text
        assert not (tmp_path / 'over-the-replay.jsonl.gz').exists()

    def test_truncated_recording_replays_to_the_cut_off(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        cut_off_after_frame(recording_path=recording_path, frame_number=2)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.end_reason == 'truncated'
        assert engine.replay_sources.result.frames_replayed == 3
        assert engine.replay_sources.result.divergence is None
        assert f'{recording_path} is cut off after 3 complete frames; replaying up to there' in (
            caplog.text
        )

    def test_version_two_recording_replays_every_frame_with_the_pump_count_check(
        self, mocker, tmp_path
    ):
        """Version-2 frames have event batches but no input or control fields: still exact."""
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        downgrade_to_version_two(recording_path=recording_path)
        frames = read_trace_result(path=recording_path).trace['frames']
        assert all('event_batches' in frame for frame in frames)
        assert not any(
            field_name in frame for frame in frames for field_name in RECORDING_FORMAT_THREE_FIELDS
        )
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        result = engine.replay_sources.result
        assert result.divergence is None
        assert result.end_reason == 'end_of_recording'
        assert result.frames_replayed == len(frames)

    def test_version_two_recording_replays_with_a_warning(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        downgrade_to_version_two(recording_path=recording_path)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        warnings = [
            record
            for record in caplog.records
            if 'polled input will read as idle' in record.getMessage()
        ]
        assert len(warnings) == 1

    def test_different_engine_version_warns_once(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        rewrite_recording(
            recording_path=recording_path,
            change=lambda trace: trace.update(engine_version='0.0.1'),
        )
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        warnings = [record for record in caplog.records if '0.0.1' in record.getMessage()]
        assert len(warnings) == 1


# A live headless run's target: a period of exactly 15_625_000 ns
LIVE_HEADLESS_TARGET_FPS = 64

# SDL driver names no SDL has: what the driver variables hold before the engine starts, in tests
# whose pygame.init is a stub (pygame is already started on the worker, so nothing reads them)
UNUSED_VIDEO_DRIVER = 'unused-video-driver'
UNUSED_AUDIO_DRIVER = 'unused-audio-driver'


def pygame_init_noting_drivers(mocker) -> list[tuple[str | None, str | None]]:
    """Replace pygame.init with a stub that notes the SDL driver variables when called.

    pygame is already started on the test worker (tests/conftest.py), so the stub starts nothing:
    the variables it notes are never read by SDL.

    Returns:
        The (SDL_VIDEODRIVER, SDL_AUDIODRIVER) pairs seen, one per call, filled in as it is called.

    """
    drivers_at_init: list[tuple[str | None, str | None]] = []

    def init_noting_drivers() -> tuple[int, int]:
        drivers_at_init.append((
            os.environ.get('SDL_VIDEODRIVER'),
            os.environ.get('SDL_AUDIODRIVER'),
        ))
        return (0, 0)

    mocker.patch.object(pygame, 'init', side_effect=init_noting_drivers)
    return drivers_at_init


class QuittingSupervisor:
    """Quits the game at frame ``quit_frame``'s supervisor slot, noting the video driver.

    A glitchygames.supervision.Supervisor.
    """

    def __init__(self, *, quit_frame: int) -> None:
        """Quit at the slot of frame ``quit_frame``."""
        self.quit_frame = quit_frame
        self.frames_seen: list[int] = []
        self.video_drivers: set[str] = set()

    def on_frame(self, *, frame_number: int, scene: object) -> None:
        """Note the frame and the video driver; post QUIT at ``quit_frame``."""
        del scene
        self.frames_seen.append(frame_number)
        self.video_drivers.add(pygame.display.get_driver())
        if frame_number == self.quit_frame:
            GameEngine.quit_game()


class TestHeadless:
    """--headless: dummy SDL drivers for any run; replays then run unpaced and print a report."""

    def test_matching_replay_exits_zero_and_reports(self, mocker, tmp_path, capsys):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        recorded_frame_count = len(read_trace_result(path=recording_path).trace['frames'])
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path, mocker=mocker, arguments=('--headless',)
            )
        assert exit_info.value.code == ExitCode.SUCCESS
        assert capsys.readouterr().out == (
            f'Replay matched {recorded_frame_count} frames (end of recording)\n'
        )

    def test_divergence_exits_one_with_the_sprite_history(self, mocker, tmp_path, capsys):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path, mocker=mocker, arguments=('--headless',)
            )
        output_lines = capsys.readouterr().out.splitlines()
        assert exit_info.value.code == ExitCode.REPLAY_DIVERGED
        assert output_lines[0].startswith('Replay diverged at frame 3: sprite ')
        sprite_id = output_lines[0].split()[6]
        assert output_lines[1] == (
            f'{sprite_id}, last {REPORT_HISTORY_FRAMES} frames (expected | got):'
        )
        # Frames 0 to 3 (fewer than REPORT_HISTORY_FRAMES were replayed); the last one differs
        assert [line.split(':')[0] for line in output_lines[2:]] == ['  0', '  1', '  2', '  3']
        expected_part, got_part = output_lines[-1].split(': ', 1)[1].split(' | ')
        assert expected_part != got_part
        for line in output_lines[2:-1]:
            expected_part, got_part = line.split(': ', 1)[1].split(' | ')
            assert expected_part == got_part

    def test_truncated_recording_exits_as_unusable_input(self, mocker, tmp_path, capsys):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        cut_off_after_frame(recording_path=recording_path, frame_number=2)
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path, mocker=mocker, arguments=('--headless',)
            )
        assert exit_info.value.code == ExitCode.UNUSABLE_INPUT
        assert capsys.readouterr().out == (
            'Replay ended early at frame 3: the recording is truncated\n'
        )

    def test_headless_never_sleeps(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        engine_sources = ReplaySources.from_path(
            path=recording_path, options=ReplayOptions(headless=True)
        )
        assert engine_sources.paced_frame_seconds() == 0.0
        # A watched replay paces itself by holding the loop (TestWatched)
        assert ReplaySources.from_path(path=recording_path).paced_frame_seconds() == 0.0
        assert LiveSources(random_seed=RANDOM_SEED).paced_frame_seconds() is None

    def test_a_headless_replay_runs_every_frame_unpaced(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        pacing_spy = mocker.spy(SceneManager, '_handle_frame_pacing')
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.options.headless
        paced_seconds = {call.kwargs['paced_seconds'] for call in pacing_spy.call_args_list}
        assert paced_seconds == {0.0}
        assert len(pacing_spy.call_args_list) == engine.replay_sources.result.frames_replayed

    def test_a_live_headless_run_starts_runs_paced_and_quits(self, mocker, tmp_path, capsys):
        """--headless without a replay: dummy drivers, normal pacing, and the game's own end."""
        pacing_spy = mocker.spy(SceneManager, '_handle_frame_pacing')
        deadline_spy = mocker.spy(FastTimer, 'compute_deadline')
        sleep_spy = mocker.spy(FastTimer, 'sleep_until_next')
        supervisor = QuittingSupervisor(quit_frame=3)
        with engine_run_environment(mocker):
            engine = build_engine(
                scene_class=DepartureRecordedScene,
                # The last --target-fps wins over RUN_ENGINE_ARGUMENTS' uncapped 0
                arguments=(
                    *RUN_ENGINE_ARGUMENTS,
                    '--target-fps',
                    str(LIVE_HEADLESS_TARGET_FPS),
                    '--headless',
                ),
            )
            assert (os.environ['SDL_VIDEODRIVER'], os.environ['SDL_AUDIODRIVER']) == (
                'dummy',
                'dummy',
            )
            engine.scene_manager.add_supervisor(supervisor=supervisor)
            # A live run ends however the game ends: here start() returns
            engine.start()
        assert engine.replay_sources is None
        assert supervisor.frames_seen[:4] == [0, 1, 2, 3]
        assert supervisor.video_drivers == {'dummy'}
        paced_seconds = {call.kwargs['paced_seconds'] for call in pacing_spy.call_args_list}
        assert paced_seconds == {None}
        # Every frame waited for its deadline on the timer backend, one target period apart
        assert len(deadline_spy.call_args_list) == len(pacing_spy.call_args_list)
        assert {call.args[2] for call in deadline_spy.call_args_list} == {
            round(1_000_000_000 / LIVE_HEADLESS_TARGET_FPS)
        }
        assert len(sleep_spy.call_args_list) == len(pacing_spy.call_args_list)
        assert not capsys.readouterr().out

    def test_headless_sets_the_dummy_drivers_before_pygame_starts(self, mocker, monkeypatch):
        monkeypatch.setenv('SDL_VIDEODRIVER', UNUSED_VIDEO_DRIVER)
        monkeypatch.setenv('SDL_AUDIODRIVER', UNUSED_AUDIO_DRIVER)
        drivers_at_init = pygame_init_noting_drivers(mocker)
        with constructed_engine('--headless'):
            pass
        assert drivers_at_init == [('dummy', 'dummy')]

    def test_without_headless_the_drivers_are_left_alone(self, mocker, monkeypatch):
        monkeypatch.setenv('SDL_VIDEODRIVER', UNUSED_VIDEO_DRIVER)
        monkeypatch.setenv('SDL_AUDIODRIVER', UNUSED_AUDIO_DRIVER)
        drivers_at_init = pygame_init_noting_drivers(mocker)
        with constructed_engine():
            pass
        assert drivers_at_init == [(UNUSED_VIDEO_DRIVER, UNUSED_AUDIO_DRIVER)]

    def test_headless_restarts_a_display_and_mixer_pygame_already_started(
        self, mocker, monkeypatch, caplog
    ):
        """Pygame started before the engine on real drivers: both restart on the dummy ones."""
        monkeypatch.setenv('SDL_VIDEODRIVER', UNUSED_VIDEO_DRIVER)
        monkeypatch.setenv('SDL_AUDIODRIVER', UNUSED_AUDIO_DRIVER)
        pygame_init_noting_drivers(mocker)
        mocker.patch.object(pygame.display, 'get_init', return_value=True)
        mocker.patch.object(pygame.display, 'get_driver', return_value='cocoa')
        display_quit = mocker.patch.object(pygame.display, 'quit')
        mocker.patch.object(pygame.mixer, 'get_init', return_value=(22050, 8, 1))
        mocker.patch.object(pygame.mixer, 'get_num_channels', return_value=16)
        mocker.patch.object(pygame.mixer, 'get_driver', return_value='coreaudio')
        mixer_calls = mocker.Mock()
        mocker.patch.object(pygame.mixer, 'quit', new=mixer_calls.quit)
        mocker.patch.object(pygame.mixer, 'init', new=mixer_calls.init)
        mocker.patch.object(pygame.mixer, 'set_num_channels', new=mixer_calls.set_num_channels)
        with constructed_engine('--headless'):
            pass
        display_quit.assert_called_once_with()
        # The mixer comes back on the dummy driver with the game's format and channel count
        assert mixer_calls.mock_calls == [
            mocker.call.quit(),
            mocker.call.init(frequency=22050, size=8, channels=1),
            mocker.call.set_num_channels(16),
        ]
        restarts = [
            record.getMessage()
            for record in caplog.records
            if record.getMessage().startswith('--headless: pygame was started before the engine')
        ]
        assert len(restarts) == 1
        assert "video driver 'cocoa'" in restarts[0]
        assert "audio driver 'coreaudio'" in restarts[0]
        assert '22050 Hz, size 8, 1 output channels, 16 mixing channels' in restarts[0]

    def test_a_crashed_headless_replay_reports_where_it_stopped(self, mocker, tmp_path, capsys):
        """A crash ends the replay early: the report says so, not that the replay diverged."""

        def fail() -> None:
            message = 'game code failed mid-replay'
            raise RuntimeError(message)

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path,
                mocker=mocker,
                arguments=('--headless',),
                action=fail,
                action_frame=ACTION_FRAME,
            )
        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        assert capsys.readouterr().out == (
            f'Replay stopped at frame {ACTION_FRAME}: the run ended with '
            f'{ExitCode.INTERNAL_ERROR.describe()}\n'
        )

    def test_the_diagnostic_options_share_one_group(self):
        """--headless and the other ways of watching or diagnosing a run; game settings stay put."""
        parser = argparse.ArgumentParser()
        GameEngine.args(parser)
        groups_by_option = {
            action.dest: group.title
            for group in parser._action_groups
            for action in group._group_actions
        }
        diagnostic_options = {
            'headless',
            'debug_overlay',
            'record_trace',
            'replay_trace',
            'replay_fps',
            'audit',
            'replay_digest',
            'log_timer_jitter',
            'fps_histogram',
            'perf_trim_percent',
        }
        assert {option: groups_by_option[option] for option in diagnostic_options} == dict.fromkeys(
            diagnostic_options, 'Diagnostics Options'
        )
        for option in ('target_fps', 'random_seed', 'timer_backend', 'live_voice_pool'):
            assert groups_by_option[option] == 'Graphics Options'

    def test_a_late_end_after_the_replay_finished_reports_its_result_first(
        self, mocker, tmp_path, capsys
    ):
        """The replay reached its result, then something else ended the run: both are said."""
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        recorded_frame_count = len(read_trace_result(path=recording_path).trace['frames'])
        with constructed_engine('--replay-trace', str(recording_path), '--headless') as engine:
            sources = engine.replay_sources
            assert sources is not None
            sources.result.frames_replayed = recorded_frame_count
            sources.result.end_reason = 'end_of_recording'
            engine._report_replay_result(run_ended_by=ExitCode.TERMINATED.describe())
            sources.on_uninstalled()
        assert capsys.readouterr().out == (
            f'Replay matched {recorded_frame_count} frames (end of recording)\n'
            f'then the run ended with {ExitCode.TERMINATED.describe()}\n'
        )

    def test_headless_runs_without_audio_when_the_dummy_mixer_cannot_start(
        self, mocker, monkeypatch, caplog
    ):
        monkeypatch.setenv('SDL_VIDEODRIVER', UNUSED_VIDEO_DRIVER)
        monkeypatch.setenv('SDL_AUDIODRIVER', UNUSED_AUDIO_DRIVER)
        pygame_init_noting_drivers(mocker)
        mocker.patch.object(pygame.mixer, 'get_init', return_value=(22050, 8, 1))
        mocker.patch.object(pygame.mixer, 'get_num_channels', return_value=16)
        mocker.patch.object(pygame.mixer, 'get_driver', return_value='coreaudio')
        mocker.patch.object(pygame.mixer, 'quit')
        mocker.patch.object(pygame.mixer, 'init', side_effect=pygame.error('no audio device'))
        set_num_channels = mocker.patch.object(pygame.mixer, 'set_num_channels')
        with constructed_engine('--headless'):
            pass
        set_num_channels.assert_not_called()
        assert (
            '--headless: the mixer could not start on the dummy audio driver (no audio device); '
            'running without audio'
        ) in caplog.text

    def test_headless_leaves_a_display_and_mixer_already_on_dummy_drivers(self, mocker, caplog):
        # --headless sets the SDL driver variables; the test's own values come back afterwards
        mocker.patch.dict(os.environ)
        mocker.patch.object(pygame.display, 'get_init', return_value=True)
        mocker.patch.object(pygame.display, 'get_driver', return_value='dummy')
        display_quit = mocker.patch.object(pygame.display, 'quit')
        mocker.patch.object(pygame.mixer, 'get_init', return_value=(44100, -16, 2))
        mocker.patch.object(pygame.mixer, 'get_driver', return_value='dummy')
        mixer_quit = mocker.patch.object(pygame.mixer, 'quit')
        with constructed_engine('--headless'):
            pass
        display_quit.assert_not_called()
        mixer_quit.assert_not_called()
        assert '--headless: pygame was started before the engine' not in caplog.text


def sprite_frame(*, frame_number: int, rect: list[int]) -> dict[str, Any]:
    """Return a recorded frame of a Mock scene holding one sprite, Mock#0, at ``rect``.

    Returns:
        The frame record.

    """
    frame = recorded_frame(frame_number=frame_number)
    frame['scene'] = 'Mock'
    frame['sprites'] = [{'id': 'Mock#0', 'rect': rect, 'visible': True}]
    return frame


class TestReplayReport:
    """ReplayResult.report() and exit_code(), and ReplayOptions."""

    def test_a_sprite_divergence_lists_the_last_frames_of_that_sprite(self, mocker):
        diverging_frame = REPORT_HISTORY_FRAMES + 5
        frames = [
            sprite_frame(frame_number=frame_number, rect=[frame_number, 0, 4, 4])
            for frame_number in range(diverging_frame + 1)
        ]
        sources = minimal_sources(frames=frames)
        sprite = mocker.Mock(visible=True)
        scene = mocker.Mock()
        scene.all_sprites.sprites.return_value = [sprite]
        for frame_number in range(diverging_frame + 1):
            # One pixel down in the last frame only
            sprite.rect = pygame.Rect(frame_number, int(frame_number == diverging_frame), 4, 4)
            sources.end_frame(frame_number=frame_number, dt=0.25, scene=scene, control_events=[])
        result = sources.result
        first_history_frame = diverging_frame - REPORT_HISTORY_FRAMES
        assert result.report().splitlines() == [
            (
                f'Replay diverged at frame {diverging_frame}: sprite Mock#0 rect expected '
                f'[{diverging_frame}, 0, 4, 4], got [{diverging_frame}, 1, 4, 4]'
            ),
            f'Mock#0, last {REPORT_HISTORY_FRAMES} frames (expected | got):',
            *[
                f'  {frame_number}: [{frame_number}, 0, 4, 4] visible | '
                f'[{frame_number}, 0, 4, 4] visible'
                for frame_number in range(first_history_frame, diverging_frame)
            ],
            (
                f'  {diverging_frame}: [{diverging_frame}, 0, 4, 4] visible | '
                f'[{diverging_frame}, 1, 4, 4] visible'
            ),
        ]
        assert result.exit_code(policy=ReplayExitPolicy.RESULT) == ExitCode.REPLAY_DIVERGED

    def test_hidden_and_absent_sprites_are_named_in_the_history(self, mocker):
        frames = [
            sprite_frame(frame_number=0, rect=[0, 0, 4, 4]),
            sprite_frame(frame_number=1, rect=[0, 0, 4, 4]),
        ]
        frames[0]['sprites'][0]['visible'] = False
        sources = minimal_sources(frames=frames)
        scene = mocker.Mock()
        scene.all_sprites.sprites.return_value = [
            mocker.Mock(rect=pygame.Rect(0, 0, 4, 4), visible=False)
        ]
        sources.end_frame(frame_number=0, dt=0.25, scene=scene, control_events=[])
        scene.all_sprites.sprites.return_value = []
        sources.end_frame(frame_number=1, dt=0.25, scene=scene, control_events=[])
        assert sources.result.report().splitlines()[2:] == [
            '  0: [0, 0, 4, 4] hidden | [0, 0, 4, 4] hidden',
            '  1: [0, 0, 4, 4] visible | absent',
        ]

    def test_a_divergence_that_is_not_a_sprite_has_no_history(self):
        sources = minimal_sources(
            frames=[recorded_frame(frame_number=0), recorded_frame(frame_number=1)]
        )
        sources.end_frame(frame_number=0, dt=0.25, scene=None, control_events=[])
        sources.finish_run()
        assert sources.result.report() == (
            'Replay diverged at frame 1: length recording frames expected 2, got 1'
        )
        assert sources.result.exit_code(policy=ReplayExitPolicy.RESULT) == (
            ExitCode.REPLAY_DIVERGED
        )

    @pytest.mark.parametrize(
        ('end_reason', 'report', 'exit_code'),
        [
            ('end_of_recording', 'Replay matched 7 frames (end of recording)', ExitCode.SUCCESS),
            ('quit', 'Replay matched 7 frames (quit before the end)', ExitCode.SUCCESS),
            (
                'truncated',
                'Replay ended early at frame 7: the recording is truncated',
                ExitCode.UNUSABLE_INPUT,
            ),
            (
                'running',
                'Replay still running after 7 frames',
                ExitCode.REPLAY_DIVERGED,
            ),
        ],
    )
    def test_each_ending_without_a_divergence(self, end_reason, report, exit_code):
        result = ReplayResult(frames_replayed=7, end_reason=end_reason)
        assert result.report() == report
        assert result.exit_code(policy=ReplayExitPolicy.RESULT) == exit_code
        # A rebaseline exits SUCCESS once it has written, whatever the result
        assert result.exit_code(policy=ReplayExitPolicy.SUCCESS_AFTER_WRITING) == (ExitCode.SUCCESS)

    def test_the_options_are_read_only_typed_and_closed(self):
        options = ReplayOptions(headless=True, digest_path='digests.jsonl')
        assert options.digest_path == Path('digests.jsonl')
        assert options.exit_policy is ReplayExitPolicy.RESULT
        with pytest.raises(ValidationError):
            options.headless = False
        with pytest.raises(ValidationError):
            ReplayOptions(fps_source='sometimes')
        with pytest.raises(ValidationError):
            ReplayOptions(no_such_option=3)

    def test_the_sources_keep_the_options_they_were_given(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        options = ReplayOptions(exit_policy=ReplayExitPolicy.SUCCESS_AFTER_WRITING)
        sources = ReplaySources.from_path(path=recording_path, options=options)
        assert sources.options is options
        assert sources.recording.frame_count == len(
            read_trace_result(path=recording_path).trace['frames']
        )
        assert ReplaySources.from_path(path=recording_path).options == ReplayOptions()


class TestRealInput:
    """Real input during a replay: dropped, except the window's close button."""

    def test_real_input_during_replay_never_reaches_the_game(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        pump_spy = mocker.spy(GoldenTraceEngine, '_pump_events')
        real_events = [
            _key(pygame.KEYDOWN, pygame.K_b, unicode='b'),
            pygame.event.Event(pygame.MOUSEMOTION, pos=(5, 5), rel=(1, 1), buttons=(0, 0, 0)),
            pygame.event.Event(pygame.WINDOWFOCUSLOST, window=None),
        ]
        engine = replay_session(
            recording_path=recording_path,
            mocker=mocker,
            events_by_frame={frame_number: list(real_events) for frame_number in range(6)},
        )
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        delivered = [event for batch in pump_spy.spy_return_list for event in batch]
        # The recorded key press reached the game; none of the real events did
        assert any(event.type == pygame.KEYDOWN and event.key == pygame.K_a for event in delivered)
        assert not any(
            event.type == pygame.KEYDOWN and event.key == pygame.K_b for event in delivered
        )
        assert not any(event.type == pygame.MOUSEMOTION for event in delivered)
        assert not any(
            event.type == pygame.WINDOWFOCUSLOST and event.dict == {'window': None}
            for event in delivered
        )

    def test_closing_the_window_ends_the_replay(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        engine = replay_session(
            recording_path=recording_path,
            mocker=mocker,
            events_by_frame={1: [pygame.event.Event(pygame.QUIT)]},
        )
        assert engine.replay_sources is not None
        result = engine.replay_sources.result
        assert result.end_reason == 'quit'
        assert result.divergence is None
        assert result.frames_replayed == 2


class TestRealInputBlocking:
    """Real input is blocked at SDL while a replay drains the queue; the prior state comes back."""

    def test_the_blocked_types_are_real_input_device_and_window_events(self):
        blocked_types = set(REAL_INPUT_EVENT_TYPES)
        assert {
            pygame.KEYDOWN,
            pygame.TEXTINPUT,
            pygame.TEXTEDITING,
            pygame.MOUSEMOTION,
            pygame.MOUSEWHEEL,
            pygame.FINGERDOWN,
            pygame.MULTIGESTURE,
            pygame.JOYAXISMOTION,
            pygame.JOYDEVICEADDED,
            pygame.CONTROLLERDEVICEREMAPPED,
            pygame.CONTROLLERSENSORUPDATE,
            pygame.AUDIODEVICEADDED,
            pygame.DROPFILE,
            pygame.WINDOWFOCUSLOST,
            pygame.WINDOWRESIZED,
        } <= blocked_types
        assert pygame.QUIT not in blocked_types
        assert pygame.WINDOWCLOSE not in blocked_types
        assert all(event_type < pygame.USEREVENT for event_type in blocked_types)
        assert len(blocked_types) == len(REAL_INPUT_EVENT_TYPES)

    def test_real_input_is_blocked_during_the_replay(self, mocker, tmp_path):
        custom_event_type = pygame.event.custom_type()
        observed: dict[str, Any] = {}

        def observe_blocking() -> None:
            observed['blocked'] = {
                event_type: pygame.event.get_blocked(event_type)
                for event_type in (
                    pygame.KEYDOWN,
                    pygame.MOUSEMOTION,
                    pygame.JOYAXISMOTION,
                    pygame.QUIT,
                    pygame.WINDOWCLOSE,
                    FPSEVENT,
                    custom_event_type,
                )
            }
            observed['posted'] = [
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q)),
                pygame.event.post(
                    pygame.event.Event(
                        pygame.MOUSEMOTION, pos=(1, 1), rel=(1, 1), buttons=(0, 0, 0)
                    )
                ),
                pygame.event.post(
                    pygame.event.Event(pygame.JOYAXISMOTION, instance_id=0, axis=0, value=0.5)
                ),
            ]

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        pump_spy = mocker.spy(GoldenTraceEngine, '_pump_events')
        engine = replay_session(
            recording_path=recording_path,
            mocker=mocker,
            action=observe_blocking,
            action_frame=ACTION_FRAME,
        )
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        assert observed['blocked'] == {
            pygame.KEYDOWN: True,
            pygame.MOUSEMOTION: True,
            pygame.JOYAXISMOTION: True,
            pygame.QUIT: False,
            pygame.WINDOWCLOSE: False,
            FPSEVENT: False,
            custom_event_type: False,
        }
        # SDL refused the posts: nothing of those types entered the queue
        assert observed['posted'] == [False, False, False]
        delivered = delivered_events(pump_spy=pump_spy)
        assert not any(
            event.type == pygame.KEYDOWN and event.key == pygame.K_q for event in delivered
        )
        assert not any(
            event.type in {pygame.MOUSEMOTION, pygame.JOYAXISMOTION} for event in delivered
        )

    def test_the_blocked_state_comes_back_after_the_replay(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        states_before = blocked_states()
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.end_reason == 'end_of_recording'
        assert blocked_states() == states_before

    def test_the_blocked_state_comes_back_after_an_error_mid_replay(self, mocker, tmp_path):
        observed: dict[str, bool] = {}

        def fail() -> None:
            observed['keys_blocked'] = pygame.event.get_blocked(pygame.KEYDOWN)
            message = 'game code failed mid-replay'
            raise RuntimeError(message)

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        states_before = blocked_states()
        # The crash ends start() with SystemExit, so the engine is taken from its teardown call
        shutdown_spy = mocker.spy(GoldenTraceEngine, '_shutdown')
        with pytest.raises(SystemExit) as exit_info:
            replay_session(
                recording_path=recording_path,
                mocker=mocker,
                action=fail,
                action_frame=ACTION_FRAME,
            )
        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        engine = shutdown_spy.call_args.args[0]
        assert observed == {'keys_blocked': True}
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is not None
        assert blocked_states() == states_before

    def test_an_event_manager_made_mid_replay_does_not_unblock_input(self, mocker, tmp_path):
        """Event managers call set_allowed when made (a scene's widgets make them mid-run)."""
        from glitchygames.events.joystick import JoystickEventManager

        observed: dict[str, Any] = {'after_pumps': []}
        original_pump_events = ReplaySources.pump_events

        def observing_pump_events(
            sources: ReplaySources, *, real_events: list[pygame.event.Event] | None = None
        ) -> list[pygame.event.Event]:
            batch = original_pump_events(sources, real_events=real_events)
            observed['after_pumps'].append(pygame.event.get_blocked(pygame.JOYAXISMOTION))
            return batch

        def make_event_manager() -> None:
            JoystickEventManager(game=SceneManager().active_scene)
            observed['right_after_manager'] = pygame.event.get_blocked(pygame.JOYAXISMOTION)
            observed['pumps_before_manager'] = len(observed['after_pumps'])

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        states_before = blocked_states()
        mocker.patch.object(ReplaySources, 'pump_events', new=observing_pump_events)
        engine = replay_session(
            recording_path=recording_path,
            mocker=mocker,
            action=make_event_manager,
            action_frame=ACTION_FRAME,
        )
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        # The manager allowed joystick events again; the next pump blocked them again
        assert observed['right_after_manager'] is False
        pumps_after_manager = observed['after_pumps'][observed['pumps_before_manager'] :]
        assert pumps_after_manager
        assert all(pumps_after_manager)
        assert blocked_states() == states_before

    def test_a_type_blocked_before_the_replay_stays_blocked(self):
        pygame.event.set_blocked(pygame.MOUSEWHEEL)
        try:
            states_before = blocked_states()
            assert states_before[pygame.MOUSEWHEEL]
            assert not states_before[pygame.KEYDOWN]
            sources = minimal_sources(frames=[recorded_frame(frame_number=0)])
            install_sources(sources=sources)
            sources.pump_events()
            assert all(blocked_states().values())
            sources.finish_run()
            assert blocked_states() == states_before
        finally:
            pygame.event.set_allowed(pygame.MOUSEWHEEL)

    def test_uninstalling_the_replay_restores_the_blocked_state(self):
        states_before = blocked_states()
        sources = minimal_sources(frames=[recorded_frame(frame_number=0)])
        install_sources(sources=sources)
        sources.pump_events()
        assert pygame.event.get_blocked(pygame.KEYDOWN)
        reset_sources()
        assert blocked_states() == states_before

    def test_a_pump_given_the_real_batch_does_not_block(self):
        """A playback scope's pump filters the base pump's batch; it does not own SDL's queue."""
        sources = minimal_sources(frames=[recorded_frame(frame_number=0)])
        install_sources(sources=sources)
        sources.pump_events(real_events=[])
        assert not pygame.event.get_blocked(pygame.KEYDOWN)

    def test_the_block_restores_exactly_the_recorded_prior_state(self):
        block = EventTypeBlock(event_types=(pygame.KEYDOWN, pygame.KEYUP))
        pygame.event.set_blocked(pygame.KEYUP)
        try:
            block.block()
            assert block.is_active
            assert pygame.event.get_blocked(pygame.KEYDOWN)
            assert pygame.event.get_blocked(pygame.KEYUP)
            block.restore()
            assert not block.is_active
            assert not pygame.event.get_blocked(pygame.KEYDOWN)
            assert pygame.event.get_blocked(pygame.KEYUP)
            # A second restore changes nothing
            pygame.event.set_blocked(pygame.KEYDOWN)
            block.restore()
            assert pygame.event.get_blocked(pygame.KEYDOWN)
        finally:
            pygame.event.set_allowed([pygame.KEYDOWN, pygame.KEYUP])

    def test_reasserting_blocks_again_and_keeps_the_first_snapshot(self):
        block = EventTypeBlock(event_types=(pygame.KEYDOWN, pygame.KEYUP))
        pygame.event.set_blocked(pygame.KEYUP)
        try:
            block.block()
            # Something allows both in between (an event manager made mid-replay)
            pygame.event.set_allowed([pygame.KEYDOWN, pygame.KEYUP])
            block.reassert()
            assert pygame.event.get_blocked(pygame.KEYDOWN)
            assert pygame.event.get_blocked(pygame.KEYUP)
            block.restore()
            # The state at block() time: KEYUP was blocked then, KEYDOWN was not
            assert not pygame.event.get_blocked(pygame.KEYDOWN)
            assert pygame.event.get_blocked(pygame.KEYUP)
            # Not active: reassert changes nothing
            block.reassert()
            assert not pygame.event.get_blocked(pygame.KEYDOWN)
        finally:
            pygame.event.set_allowed([pygame.KEYDOWN, pygame.KEYUP])


class TestWatched:
    """A watched replay: recorded pacing, the viewer's keys, pauses and the start screen."""

    def test_escape_ends_a_watched_replay_as_quit(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(recording_path=recording_path)
        sources = harness_replay_sources(manager=manager)
        manager.dt = sources.frame_seconds(measured=0.0)
        manager.run_frame()
        sources.controls.handle_key(key=pygame.K_ESCAPE)
        manager.dt = sources.frame_seconds(measured=0.0)
        manager.run_frame()
        assert sources.stop_requested
        assert sources.result.end_reason == 'quit'
        assert sources.result.divergence is None
        GoldenTraceSceneManager.uninstall()

    @pytest.mark.parametrize(
        ('speed', 'allowed_per_tick'),
        [(1.0, {1, 2}), (8.0, {13, 14}), (0.25, {0, 1})],
        ids=['normal', 'eight_times', 'quarter_speed'],
    )
    def test_inner_frames_follow_the_accumulator(self, mocker, speed, allowed_per_tick):
        """Real time times speed, consumed by each inner frame's recorded duration (0.01 s)."""
        clock = FakeMeasuredClock(mocker=mocker)
        sources = watched_minimal_sources(recorded_dt=0.01)
        sources.controls.speed = speed
        assert sources.paced_frame_seconds() == 0.0
        assert not sources.presents_frames
        status_spy = mocker.spy(sources.controls, 'update_status')
        frames_per_tick = inner_frames_per_tick(
            sources=sources, clock=clock, status_spy=status_spy, seconds=2.0
        )
        # The first tick owes nothing yet (no time has passed) and the run stops part way
        # through the last; exact over time
        assert set(frames_per_tick[1:-1]) <= allowed_per_tick
        # Within one tick's worth: the owed remainder of the run's last tick
        assert abs(sum(frames_per_tick) - 2.0 * speed / 0.01) <= (
            speed * CONTROL_TICK_SECONDS / 0.01 + 2
        )
        assert sources.result.divergence is None

    def test_a_stall_runs_one_bounded_burst_and_drops_the_rest(self, mocker):
        clock = FakeMeasuredClock(mocker=mocker)
        sources = watched_minimal_sources(recorded_dt=0.01)
        status_spy = mocker.spy(sources.controls, 'update_status')
        inner_frames_per_tick(sources=sources, clock=clock, status_spy=status_spy, seconds=0.1)
        clock.advance(seconds=2.0)  # a two-second stall: 200 frames owed at 1x
        frames_per_tick = inner_frames_per_tick(
            sources=sources, clock=clock, status_spy=status_spy, seconds=0.5
        )
        # One tick's worth is kept and run at once; the rest is dropped
        assert frames_per_tick[0] == MAX_INNER_FRAMES_PER_TICK
        assert max(frames_per_tick[1:]) <= 2
        assert abs(sum(frames_per_tick) - (MAX_INNER_FRAMES_PER_TICK + 0.5 / 0.01)) <= 3
        assert sources.viewer.is_behind

    @pytest.mark.parametrize(
        ('speed', 'recorded_dt', 'paused'),
        [(8.0, 0.002, False), (0.25, 0.01, False), (1.0, 0.25, True)],
        ids=['eight_times', 'quarter_speed', 'paused'],
    )
    def test_the_controls_tick_sixty_times_a_second_at_any_speed(
        self, mocker, speed, recorded_dt, paused
    ):
        clock = FakeMeasuredClock(mocker=mocker)
        sources = watched_minimal_sources(recorded_dt=recorded_dt)
        sources.controls.speed = speed
        sources.controls.paused = paused
        tick_spy = mocker.spy(sources.controls, 'update_status')
        end_seconds = clock.now + 1.0
        while clock.now < end_seconds:
            if not sources.hold_frame():
                sources.end_frame(frame_number=0, dt=recorded_dt, scene=None, control_events=[])
                # Each frame takes a tenth of a millisecond of real time
                clock.advance(seconds=0.0001)
        # 60 a second; the one-second window can catch a tick at each end
        assert 59 <= tick_spy.call_count <= 62
        assert sources.result.divergence is None

    def test_paused_replay_holds_until_a_step(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        sources = ReplaySources.from_path(path=recording_path)
        # Installed (over the recording run's doors), so the reset after the test restores the
        # input hold_frame blocks
        reset_sources()
        install_sources(sources=sources)
        FakeMeasuredClock(mocker=mocker)
        sources.controls.handle_key(key=pygame.K_SPACE)
        assert sources.hold_frame()
        assert sources.hold_frame()  # paused: no inner frame, tick after tick
        sources.controls.handle_key(key=pygame.K_PERIOD)
        assert not sources.hold_frame()  # one frame runs
        assert sources.hold_frame()  # then it holds again

    def test_watched_replay_pauses_at_the_divergence_with_the_overlay_on(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        manager = start_replay_in_harness(recording_path=recording_path)
        sources = harness_replay_sources(manager=manager)
        for _ in range(4):
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
        assert sources.controls.paused
        assert not sources.stop_requested
        assert manager.debug_overlay.is_visible
        assert sources.controls.banner is not None
        assert sources.controls.banner.startswith('Diverged at frame 3')
        assert sources.result.end_reason == 'diverged'
        GoldenTraceSceneManager.uninstall()

    def test_watched_replay_pauses_at_the_end(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(recording_path=recording_path)
        sources = harness_replay_sources(manager=manager)
        while not sources.controls.paused:
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
        assert sources.controls.banner == 'End of recording'
        assert not sources.stop_requested
        assert sources.result.end_reason == 'end_of_recording'
        assert sources.result.frames_replayed == sources.recording.frame_count
        GoldenTraceSceneManager.uninstall()

    def test_stepping_or_resuming_past_the_end_does_nothing(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(recording_path=recording_path)
        sources = harness_replay_sources(manager=manager)
        while not sources.controls.paused:
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
        sources.controls.handle_key(key=pygame.K_PERIOD)
        assert sources.hold_frame()
        sources.controls.handle_key(key=pygame.K_SPACE)
        assert sources.hold_frame()
        sources.controls.handle_key(key=pygame.K_ESCAPE)
        assert sources.hold_frame()
        assert sources.stop_requested
        # Quitting after the end keeps the end reason
        assert sources.result.end_reason == 'end_of_recording'
        GoldenTraceSceneManager.uninstall()

    def test_a_headless_replay_never_holds_and_keeps_keys_blocked(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        sources = ReplaySources.from_path(
            path=recording_path, options=ReplayOptions(headless=True, wait_for_start=True)
        )
        reset_sources()
        install_sources(sources=sources)
        assert not sources.controls.awaiting_start
        assert not sources.draws_overlay
        sources.controls.handle_key(key=pygame.K_SPACE)
        assert not sources.hold_frame()
        sources.pump_events()
        assert pygame.event.get_blocked(pygame.KEYDOWN)

    def test_only_a_watched_replay_waits_for_start(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(recording_path=recording_path)
        assert harness_replay_sources(manager=manager).options.wait_for_start
        GoldenTraceSceneManager.uninstall()
        manager = start_replay_in_harness(
            recording_path=recording_path, extra_arguments=('--headless',)
        )
        assert not harness_replay_sources(manager=manager).options.wait_for_start
        GoldenTraceSceneManager.uninstall()

    def test_a_watched_replay_waits_at_the_start_screen_until_space(self, mocker, tmp_path):
        """Only frame 0 runs before Space (its picture behind the message); F3 works while held."""
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(recording_path=recording_path)
        sources = harness_replay_sources(manager=manager)
        assert sources.controls.awaiting_start
        run_frame_spy = mocker.spy(manager, '_run_frame')
        status_spy = mocker.spy(sources.controls, 'update_status')
        seen_while_held: list[tuple[int, int, bool]] = []
        status_lines_while_held: list[str] = []

        def note_what_the_viewer_sees() -> None:
            seen_while_held.append((
                run_frame_spy.call_count,
                sources.result.frames_replayed,
                manager.debug_overlay.is_visible,
            ))
            status_lines_while_held.append(status_spy.call_args.kwargs['status_line'])

        press_keys_while_held(
            mocker=mocker,
            keys=(pygame.K_F3, pygame.K_SPACE),
            before_each_press=note_what_the_viewer_sees,
        )
        manager.start()
        # Held twice after frame 0 (F3, then Space); the recorded game quits itself at its end
        assert seen_while_held == [(1, 1, False), (1, 1, True)]
        assert status_lines_while_held[0].startswith('frame 1 / ')
        assert not sources.controls.awaiting_start
        assert sources.result.divergence is None
        assert sources.result.frames_replayed == sources.recording.frame_count
        GoldenTraceSceneManager.uninstall()

    def test_closing_the_window_while_held_quits(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        sources = ReplaySources.from_path(
            path=recording_path, options=ReplayOptions(wait_for_start=True)
        )
        reset_sources()
        install_sources(sources=sources)
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        assert sources.hold_frame()
        assert sources.stop_requested
        assert sources.result.end_reason == 'quit'

    def test_internal_events_found_while_held_reach_the_next_pump(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        sources = ReplaySources.from_path(path=recording_path)
        reset_sources()
        install_sources(sources=sources)
        custom_event_type = pygame.event.custom_type()
        post_event(pygame.event.Event(custom_event_type, value=7))
        FakeMeasuredClock(mocker=mocker)
        sources.controls.handle_key(key=pygame.K_SPACE)
        assert sources.hold_frame()
        sources.controls.handle_key(key=pygame.K_SPACE)
        # Running again: ticks pass until the accumulator owes the next frame
        while sources.hold_frame():
            pass
        batch = sources.pump_events()
        assert [event.dict for event in batch if event.type == custom_event_type] == [{'value': 7}]

    def test_a_one_frame_recording_reaches_its_end_at_the_start_screen(self):
        sources = minimal_sources(
            frames=[recorded_frame(frame_number=0)], options=ReplayOptions(wait_for_start=True)
        )
        install_sources(sources=sources)
        assert not sources.hold_frame()  # frame 0 runs before the start screen holds
        sources.end_frame(frame_number=0, dt=0.25, scene=None, control_events=[])
        assert sources.hold_frame()
        assert sources.controls.awaiting_start
        assert sources.controls.banner == 'End of recording'
        assert sources.result.end_reason == 'end_of_recording'

    def test_mid_run_controls_keep_the_replay_exact(self, mocker, tmp_path):
        """Pause at a pump, step, change speed and resume: nothing changes what is replayed."""
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(recording_path=recording_path)
        sources = harness_replay_sources(manager=manager)
        # The viewer presses Space during logic frame 2: the next frame's pump reads it
        Script.events_by_frame = {
            2: [_key(pygame.KEYDOWN, pygame.K_SPACE), _key(pygame.KEYUP, pygame.K_SPACE)]
        }
        seen_while_held: list[tuple[int, float, float, float]] = []

        def note_what_the_viewer_sees() -> None:
            scene = manager.active_scene
            assert scene is not None
            seen_while_held.append((
                sources.result.frames_replayed,
                frame_clock_seconds(),
                scene.game_time,
                sources.controls.speed,
            ))

        press_keys_while_held(
            mocker=mocker,
            keys=(
                pygame.K_SPACE,
                pygame.K_PERIOD,
                pygame.K_PERIOD,
                pygame.K_RIGHTBRACKET,
                pygame.K_LEFTBRACKET,
                pygame.K_SPACE,
            ),
            before_each_press=note_what_the_viewer_sees,
        )
        manager.start()
        frames_seen = [seen[0] for seen in seen_while_held]
        paused_at = frames_seen[1]
        assert frames_seen == [
            1,
            paused_at,
            paused_at + 1,
            paused_at + 2,
            paused_at + 2,
            paused_at + 2,
        ]
        # Held iterations of one frame leave the clocks alone
        assert len({seen[1:3] for seen in seen_while_held[3:]}) == 1
        assert [seen[3] for seen in seen_while_held[3:]] == [1.0, 2.0, 1.0]
        assert sources.result.divergence is None
        assert sources.result.frames_replayed == sources.recording.frame_count
        GoldenTraceSceneManager.uninstall()

    def test_the_status_bar_is_drawn_on_the_presented_frame_only(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(recording_path=recording_path)
        sources = harness_replay_sources(manager=manager)
        assert sources.draws_overlay
        assert manager.screen is not None
        draw_spy = mocker.spy(ReplaySources, 'draw_overlay')
        clean_frame = pygame.image.tobytes(manager.screen, 'RGB')
        # Inner frames are not presented; the viewer's outer tick presents the latest
        manager._present_frame(full_update=False)
        assert draw_spy.call_count == 0
        manager._present_held_frame()
        assert draw_spy.call_count == 1
        assert pygame.image.tobytes(manager.screen, 'RGB') == clean_frame
        assert not LiveSources(random_seed=RANDOM_SEED).draws_overlay
        GoldenTraceSceneManager.uninstall()


class TestWatchedViewerKeys:
    """A watched replay's real keys: read by the viewer, once per press, never by the game."""

    def test_the_viewers_keys_reach_the_controls_never_the_game(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(recording_path=recording_path)
        sources = harness_replay_sources(manager=manager)
        FakeMeasuredClock(mocker=mocker)
        pump_spy = mocker.spy(GoldenTraceEngine, '_pump_events')
        # The first drain (a control tick) drops presses queued before the replay
        assert not sources.hold_frame()
        pygame.event.post(_key(pygame.KEYDOWN, pygame.K_RIGHTBRACKET))
        pygame.event.post(_key(pygame.KEYUP, pygame.K_RIGHTBRACKET))
        manager.dt = sources.frame_seconds(measured=0.0)
        manager.run_frame()
        # The frame's pump read the keys; the viewer's next tick acts on them
        run_next_viewer_tick(sources=sources)
        assert sources.controls.speed == 2.0
        # The viewer's keys stay unblocked at SDL; the rest of real input is blocked
        assert not pygame.event.get_blocked(pygame.KEYDOWN)
        assert not pygame.event.get_blocked(pygame.KEYUP)
        assert pygame.event.get_blocked(pygame.MOUSEMOTION)
        for key in (pygame.K_LEFTBRACKET, pygame.K_F3, pygame.K_F4):
            assert pygame.event.post(_key(pygame.KEYDOWN, key))
            assert pygame.event.post(_key(pygame.KEYUP, key))
        manager.dt = sources.frame_seconds(measured=0.0)
        manager.run_frame()
        run_next_viewer_tick(sources=sources)
        assert sources.controls.speed == 1.0
        assert manager.debug_overlay.is_visible
        assert manager.debug_overlay.panel is DebugPanel.COLLISION
        viewer_keys = {pygame.K_RIGHTBRACKET, pygame.K_LEFTBRACKET, pygame.K_F3, pygame.K_F4}
        assert not any(
            event.type in WATCHED_REAL_KEY_EVENT_TYPES and event.key in viewer_keys
            for event in delivered_events(pump_spy=pump_spy)
        )
        assert sources.result.divergence is None
        GoldenTraceSceneManager.uninstall()

    def test_a_repeating_viewer_key_acts_once_per_press(self, mocker, tmp_path):
        """Games turn key repeat on (PaddleSlap: set_repeat(1)): a held key acts once."""
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        FakeMeasuredClock(mocker=mocker)
        sources = ReplaySources.from_path(path=recording_path)
        reset_sources()
        install_sources(sources=sources)
        sources.hold_frame()  # the first tick: the first drain
        for key in (pygame.K_SPACE, pygame.K_F3):
            pygame.event.post(_key(pygame.KEYDOWN, key))
            pygame.event.post(_key(pygame.KEYDOWN, key))  # a repeat
            pygame.event.post(_key(pygame.KEYUP, key))
        run_next_viewer_tick(sources=sources)
        assert sources.controls.paused
        assert sources.controls.debug_overlay.is_visible
        # Released, so the next press acts again
        pygame.event.post(_key(pygame.KEYDOWN, pygame.K_SPACE))
        run_next_viewer_tick(sources=sources)
        assert not sources.controls.paused

    def test_presses_queued_before_the_replay_are_dropped(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        sources = ReplaySources.from_path(path=recording_path)
        reset_sources()
        install_sources(sources=sources)
        pygame.event.post(_key(pygame.KEYDOWN, pygame.K_SPACE))
        sources.hold_frame()
        assert not sources.controls.paused

    def test_a_key_held_when_the_replay_starts_acts_only_after_its_release(self, mocker, tmp_path):
        """Its queued press is dropped and its OS repeats are not new presses."""
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        FakeMeasuredClock(mocker=mocker)
        sources = ReplaySources.from_path(path=recording_path)
        reset_sources()
        install_sources(sources=sources)
        pygame.event.post(_key(pygame.KEYDOWN, pygame.K_SPACE))
        sources.hold_frame()  # the first drain
        pygame.event.post(_key(pygame.KEYDOWN, pygame.K_SPACE))  # the OS repeating it
        run_next_viewer_tick(sources=sources)
        assert not sources.controls.paused
        pygame.event.post(_key(pygame.KEYUP, pygame.K_SPACE))
        pygame.event.post(_key(pygame.KEYDOWN, pygame.K_SPACE))
        run_next_viewer_tick(sources=sources)
        assert sources.controls.paused

    def test_a_press_release_press_in_the_first_drain_leaves_the_key_held(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        FakeMeasuredClock(mocker=mocker)
        sources = ReplaySources.from_path(path=recording_path)
        reset_sources()
        install_sources(sources=sources)
        for event_type in (pygame.KEYDOWN, pygame.KEYUP, pygame.KEYDOWN):
            pygame.event.post(_key(event_type, pygame.K_SPACE))
        sources.hold_frame()  # the first drain
        pygame.event.post(_key(pygame.KEYDOWN, pygame.K_SPACE))  # the OS repeating it
        run_next_viewer_tick(sources=sources)
        assert not sources.controls.paused

    def test_the_debug_overlay_is_the_scene_managers(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(recording_path=recording_path)
        sources = harness_replay_sources(manager=manager)
        assert sources.controls.debug_overlay is manager.debug_overlay
        GoldenTraceSceneManager.uninstall()


def run_until_paused(*, sources: ReplaySources) -> int:
    """Run a watched replay's loop as the scene manager would until it pauses.

    Returns:
        How many times the loop was held (each hold presents a frame).

    """
    holds = 0
    while not sources.controls.paused:
        if sources.hold_frame():
            holds += 1
            continue
        sources.end_frame(frame_number=0, dt=0.0, scene=None, control_events=[])
    return holds


class TestStepBack:
    """Step back, Home and D: the replay restarts and rebuilds up to a pause frame."""

    def test_pause_at_frame_fast_forwards_without_presenting(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(
            recording_path=recording_path, extra_arguments=('--replay-pause-at-frame', '3')
        )
        sources = harness_replay_sources(manager=manager)
        assert sources.options.pause_at_frame == 3
        shown = mocker.spy(manager, '_show_frame')
        for _ in range(3):
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
        assert shown.call_count == 0  # frames 0-2 fast-forwarded
        assert sources.controls.paused  # paused on arriving at frame 3
        # The viewer had already started this replay before the restart
        assert not sources.controls.awaiting_start
        assert sources.controls.rebuild_target_frame is None
        assert sources.result.divergence is None
        GoldenTraceSceneManager.uninstall()

    def test_headless_pause_at_frame_does_not_pause(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path,
                mocker=mocker,
                arguments=('--replay-pause-at-frame', '3', '--headless'),
            )
        # Nobody can unpause a headless replay
        assert exit_info.value.code == ExitCode.SUCCESS
        assert '--replay-pause-at-frame is ignored with --headless' in caplog.text

    def test_pause_at_frame_without_a_replay_is_ignored_with_a_warning(self, caplog):
        with constructed_engine('--replay-pause-at-frame', '3'):
            pass
        assert '--replay-pause-at-frame is ignored without --replay-trace' in caplog.text

    def test_a_negative_pause_frame_is_refused(self):
        with pytest.raises(ValidationError):
            ReplayOptions(pause_at_frame=-1)

    def test_a_rebuild_shows_its_progress_by_real_time_then_pauses_silently(self, mocker, capsys):
        FakeMeasuredClock(mocker=mocker)
        silence = mocker.spy(Rebuild, 'silence_frame')
        finish = mocker.spy(Rebuild, 'finish')
        sources = minimal_sources(
            frames=[recorded_frame(frame_number=index, dt=0.01) for index in range(200)],
            options=ReplayOptions(pause_at_frame=130),
        )
        install_sources(sources=sources)
        # Each rebuild frame takes 0.025 s of real time
        mocker.patch.object(
            driver_module,
            'measured_seconds',
            side_effect=lambda: sources.controls.current_frame * 0.025,
        )
        assert sources.controls.rebuild_target_frame == 130
        holds = run_until_paused(sources=sources)
        # Held (presented) every REBUILD_PROGRESS_INTERVAL_SECONDS, never paced
        rebuild_seconds = 129 * 0.025
        assert abs(holds - rebuild_seconds / REBUILD_PROGRESS_INTERVAL_SECONDS) <= 1
        assert sources.paced_frame_seconds() == 0.0
        assert not sources.presents_frames
        assert sources.controls.current_frame == 130
        assert sources.controls.rebuild_target_frame is None
        printed = capsys.readouterr().out.splitlines()
        assert len(printed) == 3  # once a second
        assert all(re.fullmatch(r'Rebuilding: frame \d+ / 130', line) for line in printed)
        # Every rebuild frame's sounds are stopped after it
        assert silence.call_count == 130
        assert finish.call_count == 1
        # Arrived: held while paused, as a paused replay is
        assert sources.hold_frame()
        assert sources.hold_frame()
        assert sources.controls.current_frame == 130

    def test_a_rebuilt_replay_resumes_exactly_to_the_end(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        manager = start_replay_in_harness(
            recording_path=recording_path, extra_arguments=('--replay-pause-at-frame', '3')
        )
        sources = harness_replay_sources(manager=manager)
        while not sources.controls.paused:
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
        assert sources.controls.current_frame == 3
        sources.controls.handle_key(key=pygame.K_SPACE)  # resume
        while not sources.controls.paused:
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
        assert sources.result.divergence is None
        assert sources.result.end_reason == 'end_of_recording'
        assert sources.result.frames_replayed == sources.recording.frame_count
        GoldenTraceSceneManager.uninstall()

    def test_the_viewer_state_is_restored(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        viewer_state = ViewerState(speed=4.0, debug_panel=DebugPanel.CAMERA, divergence_frame=3)
        manager = start_replay_in_harness(
            recording_path=recording_path,
            extra_arguments=(
                '--replay-pause-at-frame',
                '5',
                '--replay-viewer-state',
                viewer_state.model_dump_json(),
            ),
        )
        sources = harness_replay_sources(manager=manager)
        assert sources.controls.speed == 4.0
        assert manager.debug_overlay.panel is DebugPanel.CAMERA
        while not sources.controls.paused:
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
        # D works at once: the divergence the earlier run found
        sources.controls.handle_key(key=pygame.K_d)
        assert sources.controls.restart_request == 3
        GoldenTraceSceneManager.uninstall()

    def test_a_pause_frame_of_zero_still_runs_frame_zero(self, mocker):
        FakeMeasuredClock(mocker=mocker)
        sources = minimal_sources(
            frames=[recorded_frame(frame_number=index, dt=0.01) for index in range(5)],
            options=ReplayOptions(pause_at_frame=0),
        )
        install_sources(sources=sources)
        run_until_paused(sources=sources)
        assert sources.controls.current_frame == FIRST_PAUSED_FRAME

    def test_step_back_ends_the_run_with_a_restart_at_the_previous_frame(self, mocker):
        FakeMeasuredClock(mocker=mocker)
        sources = minimal_sources(
            frames=[recorded_frame(frame_number=index, dt=0.01) for index in range(20)],
            options=ReplayOptions(pause_at_frame=10),
        )
        install_sources(sources=sources)
        run_until_paused(sources=sources)
        sources.hold_frame()  # the first drain
        pygame.event.post(_key(pygame.KEYDOWN, pygame.K_COMMA))
        pygame.event.post(_key(pygame.KEYUP, pygame.K_COMMA))
        run_next_viewer_tick(sources=sources)
        assert sources.stop_requested
        assert sources.result.restart_frame == 9
        assert sources.result.end_reason == 'restart'
        sources.finish_run()
        assert sources.result.divergence is None
        assert sources.result.exit_code(policy=sources.options.exit_policy) == ExitCode.SUCCESS
        assert sources.result.report() == 'Replay matched 10 frames (restarting at frame 9)'

    def test_a_held_step_back_restarts_once_on_release(self, mocker):
        FakeMeasuredClock(mocker=mocker)
        sources = minimal_sources(
            frames=[recorded_frame(frame_number=index, dt=0.01) for index in range(20)],
            options=ReplayOptions(pause_at_frame=10),
        )
        install_sources(sources=sources)
        run_until_paused(sources=sources)
        sources.hold_frame()  # the first drain
        pygame.event.post(_key(pygame.KEYDOWN, pygame.K_COMMA))
        for _ in range(3):
            run_next_viewer_tick(sources=sources)
        assert not sources.stop_requested
        pygame.event.post(_key(pygame.KEYUP, pygame.K_COMMA))
        run_next_viewer_tick(sources=sources)
        assert sources.stop_requested
        assert sources.result.restart_frame == 9

    def test_step_back_from_a_divergence_relaunches_the_replay(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        shutdown_spy = mocker.spy(GoldenTraceEngine, '_shutdown')
        unhandled_report = mocker.spy(GoldenTraceEngine, '_log_unhandled_event_report')
        installed_while_relaunching: list[object] = []

        def relaunch_replay(*, command, handoff_path, result_exit_code):
            del command, handoff_path, result_exit_code
            installed_while_relaunching.append(signal.getsignal(signal.SIGTERM))
            return ExitCode.REPLAY_DIVERGED

        relaunch = mocker.patch.object(
            game_engine_module, 'relaunch_replay', side_effect=relaunch_replay
        )
        # Space starts the replay; it pauses after the divergent frame 3, and , steps back
        press_keys_while_held(mocker=mocker, keys=(pygame.K_SPACE, pygame.K_COMMA))
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path, mocker=mocker, arguments=()
            )
        # The run exits with the status of the restarted replays
        assert exit_info.value.code == ExitCode.REPLAY_DIVERGED
        engine = shutdown_spy.call_args.args[0]
        assert engine.replay_sources is not None
        assert engine.replay_sources.controls.divergence_frame == 3
        assert engine.replay_sources.result.restart_frame == 3
        command = relaunch.call_args.kwargs['command']
        # The debug overlay was on (the divergence shows it), so the restart shows it too, with
        # the viewer's speed, panel and the divergence found
        assert command[-7:] == [
            '--debug-overlay',
            '--replay-viewer-state',
            ViewerState(
                speed=1.0, debug_panel=DebugPanel.ALL, divergence_frame=3
            ).model_dump_json(),
            '--replay-trace',
            str(recording_path),
            '--replay-pause-at-frame',
            '3',
        ]
        assert relaunch.call_args.kwargs['handoff_path'] is None
        # This run diverged: the supervisor keeps that status
        assert relaunch.call_args.kwargs['result_exit_code'] == ExitCode.REPLAY_DIVERGED
        # A signal while supervising ends the run through the engine's handler
        assert installed_while_relaunching == [game_engine_module.exit_on_signal]
        assert signal.getsignal(signal.SIGTERM) == signal.SIG_DFL
        # A restart is not the end of a run: no end-of-run reports
        unhandled_report.assert_not_called()

    def test_a_supervised_replay_hands_over_its_handoff_path(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        handoff_path = tmp_path / 'restart.json'
        manager = start_replay_in_harness(
            recording_path=recording_path,
            extra_arguments=('--replay-restart-handoff', str(handoff_path)),
        )
        sources = harness_replay_sources(manager=manager)
        assert sources.options.restart_handoff_path == handoff_path
        GoldenTraceSceneManager.uninstall()


BOOKMARK_RECORD = {'kind': 'breakpoint', 'label': 'bookmark'}


class TestBookmarkedCopy:
    """S saves the bookmarks as breakpoints in a copy that replays as its source does."""

    def test_saving_with_no_bookmarks_writes_nothing_and_says_so(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        sources = ReplaySources.from_path(path=recording_path)
        assert sources.bookmarks.save() is None
        assert not bookmarked_copy_path(recording_path=recording_path).exists()
        assert sources.controls.message_for_control_tick() == 'no bookmarks to save'

    @pytest.mark.parametrize(
        ('name', 'copy_name'),
        [
            ('session.jsonl.gz', 'session.bookmarked.jsonl.gz'),
            ('my.session.jsonl.gz', 'my.session.bookmarked.jsonl.gz'),
            ('session.trace', 'session.bookmarked.trace'),
            # Only a file marked as a copy is its own copy, never one merely named like one
            ('session.bookmarked.jsonl.gz', 'session.bookmarked.bookmarked.jsonl.gz'),
        ],
    )
    def test_the_bookmarked_copy_path(self, tmp_path, name, copy_name):
        assert bookmarked_copy_path(recording_path=tmp_path / name) == tmp_path / copy_name

    def test_bookmarked_copy_adds_breakpoints(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        original_bytes = recording_path.read_bytes()
        destination = bookmarked_copy_path(recording_path=recording_path)
        # Bookmark 3 pauses with frame 3 next: the breakpoint is in frame 2, the one shown
        write_bookmarked_copy(recording_path=recording_path, bookmarks=[3], destination=destination)
        original = read_trace_result(path=recording_path).trace
        copy = read_trace_result(path=destination).trace
        # The session records no control events of its own
        assert 'control_events' not in original['frames'][2]
        assert copy['frames'][2].pop('control_events') == [BOOKMARK_RECORD]
        assert copy.pop('bookmarked_copy_of') == 'session.jsonl.gz'
        assert copy == original
        assert destination.name == 'session.bookmarked.jsonl.gz'
        # The original recording is never written
        assert recording_path.read_bytes() == original_bytes

    def test_a_copy_is_marked_and_is_its_own_copy(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        destination = bookmarked_copy_path(recording_path=recording_path)
        write_bookmarked_copy(recording_path=recording_path, bookmarks=[3], destination=destination)
        header = read_trace_result(path=destination).trace
        assert header['bookmarked_copy_of'] == 'session.jsonl.gz'
        # Saving again from the copy (a restart replays it) updates it in place
        assert bookmarked_copy_path(recording_path=destination) == destination
        write_bookmarked_copy(recording_path=destination, bookmarks=[4], destination=destination)
        assert read_trace_result(path=destination).trace['bookmarked_copy_of'] == (
            'session.jsonl.gz'
        )

    def test_an_original_named_like_a_copy_is_never_written(self, mocker, tmp_path):
        recorded_path = record_session(tmp_path=tmp_path, mocker=mocker)
        original_path = tmp_path / 'mine.bookmarked.jsonl.gz'
        original_path.write_bytes(recorded_path.read_bytes())
        original_bytes = original_path.read_bytes()
        destination = bookmarked_copy_path(recording_path=original_path)
        assert destination == tmp_path / 'mine.bookmarked.bookmarked.jsonl.gz'
        with pytest.raises(ValueError, match='not a bookmarked copy'):
            write_bookmarked_copy(
                recording_path=original_path, bookmarks=[3], destination=original_path
            )
        assert original_path.read_bytes() == original_bytes

    def test_a_truncated_recordings_copy_still_ends_truncated(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        cut_off_after_frame(recording_path=recording_path, frame_number=2)
        destination = bookmarked_copy_path(recording_path=recording_path)
        write_bookmarked_copy(recording_path=recording_path, bookmarks=[2], destination=destination)
        assert read_trace_result(path=destination).trace['source_truncated'] is True
        engine = replay_session(recording_path=destination, mocker=mocker)
        assert engine.replay_sources is not None
        result = engine.replay_sources.result
        assert result.end_reason == 'truncated'
        assert result.frames_replayed == 3
        assert result.exit_code(policy=ReplayExitPolicy.RESULT) == ExitCode.UNUSABLE_INPUT
        # ...and a copy of the copy too
        write_bookmarked_copy(recording_path=destination, bookmarks=[3], destination=destination)
        assert read_trace_result(path=destination).trace['source_truncated'] is True

    def test_a_restart_onto_a_truncated_recordings_copy_keeps_the_banner(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        cut_off_after_frame(recording_path=recording_path, frame_number=2)
        destination = bookmarked_copy_path(recording_path=recording_path)
        write_bookmarked_copy(recording_path=recording_path, bookmarks=[2], destination=destination)
        manager = start_replay_in_harness(
            recording_path=destination, extra_arguments=('--replay-pause-at-frame', '2')
        )
        sources = harness_replay_sources(manager=manager)
        while not sources.controls.paused:
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
        sources.controls.handle_key(key=pygame.K_SPACE)  # resume to the end
        while not sources.controls.paused:
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
        assert sources.controls.banner == 'End of recording (the file is truncated)'
        assert sources.result.end_reason == 'truncated'
        GoldenTraceSceneManager.uninstall()

    def test_a_version_two_recordings_copy_replays_as_version_two(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        downgrade_to_version_two(recording_path=recording_path)
        destination = bookmarked_copy_path(recording_path=recording_path)
        write_bookmarked_copy(recording_path=recording_path, bookmarks=[3], destination=destination)
        assert read_trace_result(path=destination).trace['input_capture_format_version'] == 2
        engine = replay_session(recording_path=destination, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        warnings = [
            record
            for record in caplog.records
            if 'polled input will read as idle' in record.getMessage()
        ]
        assert len(warnings) == 1

    def test_a_version_two_copy_compares_no_markers(self):
        frame = recorded_frame(frame_number=0)
        frame['control_events'] = [{'kind': 'playback', 'scope': 'demo'}]
        sources = ReplaySources(
            header={
                'game_class': 'SomeGame',
                'random_seed': RANDOM_SEED,
                'recorded_at': '2026-10-19T12:00:00',
                'input_capture_format_version': 2,
            },
            frames=[frame, recorded_frame(frame_number=1)],
            format_version=3,
            options=HEADLESS_REPLAY_OPTIONS,
        )
        # The marker is not recorded again by the replayed code, yet nothing diverges
        sources.end_frame(frame_number=0, dt=0.0, scene=None, control_events=[])
        assert sources.result.divergence is None

    def test_a_copys_bookmarks_are_loaded_and_count_as_saved(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        destination = bookmarked_copy_path(recording_path=recording_path)
        write_bookmarked_copy(
            recording_path=recording_path, bookmarks=[2, 4], destination=destination
        )
        write = mocker.spy(driver_module, 'write_bookmarked_copy')
        sources = ReplaySources.from_path(
            path=destination, options=ReplayOptions(recording_path=destination)
        )
        assert sources.controls.bookmarks == [2, 4]
        assert sources.bookmarks.save() == destination
        write.assert_not_called()
        sources.controls.current_frame = 3
        sources.controls.handle_key(key=pygame.K_b)
        assert sources.bookmarks.save() == destination
        assert write.call_count == 1
        breakpoint_frames = [
            index
            for index, frame in enumerate(read_trace_result(path=destination).trace['frames'])
            if BOOKMARK_RECORD in frame.get('control_events', [])
        ]
        assert breakpoint_frames == [1, 2, 3]

    def test_saving_unchanged_bookmarks_again_writes_nothing(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        write = mocker.spy(driver_module, 'write_bookmarked_copy')
        sources = ReplaySources.from_path(
            path=recording_path, options=ReplayOptions(recording_path=recording_path)
        )
        sources.controls.current_frame = 3
        sources.controls.handle_key(key=pygame.K_b)
        copy_path = sources.bookmarks.save()
        assert copy_path == bookmarked_copy_path(recording_path=recording_path)
        sources.controls.message_for_control_tick()
        assert sources.bookmarks.save() == copy_path
        assert write.call_count == 1
        assert sources.controls.message_for_control_tick() == (
            'bookmarks already saved to session.bookmarked.jsonl.gz'
        )

    def test_existing_control_events_are_kept_and_a_bookmark_is_added_once(self, tmp_path):
        recording_path = tmp_path / 'session.jsonl.gz'
        marker = {'kind': 'playback', 'scope': 'demo'}
        frames = [recorded_frame(frame_number=index) for index in range(4)]
        frames[1]['control_events'] = [marker]
        write_trace(trace={'game_class': 'SomeGame', 'frames': frames}, path=recording_path)
        destination = bookmarked_copy_path(recording_path=recording_path)
        write_bookmarked_copy(
            recording_path=recording_path, bookmarks=[2, 4], destination=destination
        )
        # The copy saved again from itself, with one more bookmark
        write_bookmarked_copy(
            recording_path=destination, bookmarks=[1, 2, 4], destination=destination
        )
        copy_frames = read_trace_result(path=destination).trace['frames']
        assert [frame.get('control_events') for frame in copy_frames] == [
            [BOOKMARK_RECORD],
            [marker, BOOKMARK_RECORD],
            None,
            [BOOKMARK_RECORD],
        ]
        assert not list(tmp_path.glob('*.partial'))

    @pytest.mark.parametrize('bookmark', [0, 5])
    def test_a_bookmark_outside_the_recording_is_refused(self, tmp_path, bookmark):
        recording_path = tmp_path / 'session.jsonl.gz'
        frames = [recorded_frame(frame_number=index) for index in range(4)]
        write_trace(trace={'game_class': 'SomeGame', 'frames': frames}, path=recording_path)
        destination = bookmarked_copy_path(recording_path=recording_path)
        with pytest.raises(ValueError, match='outside the recording'):
            write_bookmarked_copy(
                recording_path=recording_path, bookmarks=[bookmark], destination=destination
            )
        assert not destination.exists()

    def test_a_bookmarked_copy_replays_without_divergence(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        frame_count = len(read_trace_result(path=recording_path).trace['frames'])
        destination = bookmarked_copy_path(recording_path=recording_path)
        write_bookmarked_copy(
            recording_path=recording_path,
            bookmarks=[1, 3, frame_count],
            destination=destination,
        )
        engine = replay_session(recording_path=destination, mocker=mocker)
        assert engine.replay_sources is not None
        result = engine.replay_sources.result
        assert result.divergence is None
        assert result.end_reason == 'end_of_recording'
        assert result.frames_replayed == frame_count


class TestBookmarks:
    """B and S in a watched replay, breakpoints pausing it, and restarts keeping bookmarks."""

    def test_watched_replay_pauses_at_a_recorded_breakpoint(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        bookmarked_path = tmp_path / 'bookmarked.jsonl.gz'
        write_bookmarked_copy(
            recording_path=recording_path, bookmarks=[3], destination=bookmarked_path
        )
        manager = start_replay_in_harness(recording_path=bookmarked_path)
        sources = harness_replay_sources(manager=manager)
        frame_number = 0
        while not sources.controls.paused:
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
            frame_number += 1
        # Frame 2 ran and its breakpoint paused the replay: paused at bookmark 3
        assert frame_number == 3
        assert sources.controls.current_frame == 3
        assert sources.result.divergence is None
        GoldenTraceSceneManager.uninstall()

    def test_a_rebuild_runs_past_a_recorded_breakpoint(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        bookmarked_path = tmp_path / 'bookmarked.jsonl.gz'
        write_bookmarked_copy(
            recording_path=recording_path, bookmarks=[2], destination=bookmarked_path
        )
        manager = start_replay_in_harness(
            recording_path=bookmarked_path, extra_arguments=('--replay-pause-at-frame', '4')
        )
        sources = harness_replay_sources(manager=manager)
        while not sources.controls.paused:
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
        assert sources.controls.current_frame == 4
        GoldenTraceSceneManager.uninstall()

    def test_b_then_s_writes_the_copy_and_says_where(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        FakeMeasuredClock(mocker=mocker)
        sources = ReplaySources.from_path(
            path=recording_path, options=ReplayOptions(recording_path=recording_path)
        )
        reset_sources()
        install_sources(sources=sources)
        sources.hold_frame()  # the first drain
        sources.controls.current_frame = 3
        for key in (pygame.K_b, pygame.K_s):
            pygame.event.post(_key(pygame.KEYDOWN, key))
            pygame.event.post(_key(pygame.KEYUP, key))
        caplog.set_level('INFO', logger='game.replay')
        run_next_viewer_tick(sources=sources)
        copy_path = bookmarked_copy_path(recording_path=recording_path)
        assert read_trace_result(path=copy_path).trace['frames'][2]['control_events'] == [
            BOOKMARK_RECORD
        ]
        assert f'Saved bookmarks [3] to {copy_path}' in caplog.text
        assert sources.controls.message_for_control_tick() == (
            'bookmarks saved to session.bookmarked.jsonl.gz'
        )

    def test_without_a_recording_file_nothing_is_saved(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        sources = ReplaySources.from_path(path=recording_path)
        sources.controls.current_frame = 3
        sources.controls.handle_key(key=pygame.K_b)
        sources.controls.message_for_control_tick()
        assert sources.bookmarks.save() is None
        assert not bookmarked_copy_path(recording_path=recording_path).exists()
        assert sources.controls.message_for_control_tick() == (
            'no recording file to copy the bookmarks into'
        )

    def test_a_save_that_cannot_be_written_says_so(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        mocker.patch.object(
            driver_module, 'write_bookmarked_copy', side_effect=OSError('disk full')
        )
        sources = ReplaySources.from_path(
            path=recording_path, options=ReplayOptions(recording_path=recording_path)
        )
        sources.controls.current_frame = 3
        sources.controls.handle_key(key=pygame.K_b)
        sources.controls.message_for_control_tick()
        assert sources.bookmarks.save() is None
        assert sources.controls.message_for_control_tick() == (
            'could not save bookmarks: disk full'
        )
        assert 'Could not save bookmarks' in caplog.text

    def test_restart_carries_unsaved_bookmarks(self, mocker, tmp_path):
        relaunch = mocker.patch.object(
            game_engine_module, 'relaunch_replay', return_value=ExitCode.SUCCESS
        )
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        # Space starts; paused after the divergent frame 3, B bookmarks frame 4, , steps back
        press_keys_while_held(mocker=mocker, keys=(pygame.K_SPACE, pygame.K_b, pygame.K_COMMA))
        with pytest.raises(SystemExit):
            replay_session_with_arguments(
                recording_path=recording_path, mocker=mocker, arguments=()
            )
        copy_path = bookmarked_copy_path(recording_path=recording_path)
        assert read_trace_result(path=copy_path).trace['frames'][3]['control_events'] == [
            BOOKMARK_RECORD
        ]
        command = relaunch.call_args.kwargs['command']
        assert command[-4:] == ['--replay-trace', str(copy_path), '--replay-pause-at-frame', '3']

    def test_a_restart_whose_copy_cannot_be_saved_warns_about_the_lost_bookmarks(
        self, mocker, tmp_path, caplog
    ):
        relaunch = mocker.patch.object(
            game_engine_module, 'relaunch_replay', return_value=ExitCode.SUCCESS
        )
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        mocker.patch.object(
            driver_module, 'write_bookmarked_copy', side_effect=OSError('disk full')
        )
        press_keys_while_held(mocker=mocker, keys=(pygame.K_SPACE, pygame.K_b, pygame.K_COMMA))
        with pytest.raises(SystemExit):
            replay_session_with_arguments(
                recording_path=recording_path, mocker=mocker, arguments=()
            )
        command = relaunch.call_args.kwargs['command']
        assert command[-4:] == [
            '--replay-trace',
            str(recording_path),
            '--replay-pause-at-frame',
            '3',
        ]
        warnings = [
            record.getMessage() for record in caplog.records if record.levelname == 'WARNING'
        ]
        assert any('without the bookmarks [4]' in message for message in warnings)


class TestSaves:
    """A replay reads recorded saves and never writes real ones."""

    def test_replay_never_writes_real_saves(self, mocker, tmp_path):
        from glitchygames.state import DiskSaveManager
        from glitchygames.state.sandbox import open_saves

        save_directory = tmp_path / 'saves'
        mocker.patch(
            'glitchygames.state.manager.get_save_directory',
            side_effect=lambda app_name: save_directory / app_name,
        )
        DiskSaveManager(app_name='replay-test').save('slot', {'value': 1})

        def write_slot() -> None:
            open_saves(app_name='replay-test').save('slot', {'value': 2})

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker, action=write_slot)
        DiskSaveManager(app_name='replay-test').save('slot', {'value': 1})  # undo the live write
        slot_file = next((save_directory / 'replay-test').iterdir())
        bytes_before = slot_file.read_bytes()
        engine = replay_session(recording_path=recording_path, mocker=mocker, action=write_slot)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        assert slot_file.read_bytes() == bytes_before
        replayed_store = engine.replay_sources.opened_save_namespaces['replay-test']
        assert replayed_store.load('slot') == {'value': 2}


class TestEventMerge:
    """Recorded external events plus the replayed code's own posts, checked against the record."""

    def test_missing_internal_event_is_a_divergence(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        add_recorded_internal_event(recording_path=recording_path, frame_number=2)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        divergence = engine.replay_sources.result.divergence
        assert divergence is not None
        assert (divergence.kind, divergence.field, divergence.frame_number) == (
            EVENT_DIVERGENCE,
            'missing internal event',
            2,
        )
        assert divergence.subject == 'UserEvent'
        assert divergence.actual is None

    def test_extra_internal_event_is_a_divergence(self, mocker, tmp_path):
        def post_extra() -> None:
            post_event(pygame.event.Event(pygame.USEREVENT + 42, {}))

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        engine = replay_session(
            recording_path=recording_path, mocker=mocker, action=post_extra, action_frame=2
        )
        assert engine.replay_sources is not None
        divergence = engine.replay_sources.result.divergence
        assert divergence is not None
        # The scripted action runs in frame 2's dt_tick, before that frame's pump returns it
        assert (divergence.kind, divergence.field, divergence.frame_number) == (
            EVENT_DIVERGENCE,
            'unexpected internal event',
            2,
        )
        assert divergence.expected is None
        assert divergence.actual['type'] == pygame.USEREVENT + 42

    def test_internal_events_posted_again_match(self, mocker, tmp_path):
        def post_marker_event() -> None:
            post_event(pygame.event.Event(pygame.USEREVENT + 43, {'pair': (1, 2)}))

        recording_path = record_session(
            tmp_path=tmp_path, mocker=mocker, action=post_marker_event, action_frame=2
        )
        pump_spy = mocker.spy(GoldenTraceEngine, '_pump_events')
        engine = replay_session(
            recording_path=recording_path, mocker=mocker, action=post_marker_event, action_frame=2
        )
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        delivered = [event for batch in pump_spy.spy_return_list for event in batch]
        assert [event.pair for event in delivered if event.type == pygame.USEREVENT + 43] == [
            (1, 2)
        ]

    @pytest.mark.parametrize(
        ('recorded_pump_count', 'replayed_pump_count'), [(1, 2), (2, 1)], ids=['more', 'fewer']
    )
    def test_a_different_pump_count_is_a_length_divergence(
        self, recorded_pump_count, replayed_pump_count
    ):
        frame = recorded_frame(frame_number=0)
        frame['event_batches'] = [[] for _ in range(recorded_pump_count)]
        sources = minimal_sources(frames=[frame])
        for _ in range(replayed_pump_count):
            sources.pump_events(real_events=[])
        sources.end_frame(frame_number=0, dt=0.25, scene=None, control_events=[])
        divergence = sources.result.divergence
        assert divergence is not None
        assert (divergence.kind, divergence.field, divergence.expected, divergence.actual) == (
            LENGTH_DIVERGENCE,
            'pump count',
            recorded_pump_count,
            replayed_pump_count,
        )
        assert sources.result.end_reason == 'diverged'

    def test_real_input_during_replay_never_reaches_the_game(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        pump_spy = mocker.spy(GoldenTraceEngine, '_pump_events')
        # A real key press, and the window losing focus, arrive during the replay: both dropped
        engine = replay_session(
            recording_path=recording_path,
            mocker=mocker,
            events_by_frame={
                1: [
                    _key(pygame.KEYDOWN, pygame.K_z, unicode='z'),
                    pygame.event.Event(pygame.WINDOWFOCUSLOST, {}),
                ]
            },
        )
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        delivered = [event for batch in pump_spy.spy_return_list for event in batch]
        assert not any(
            event.type == pygame.KEYDOWN and event.key == pygame.K_z for event in delivered
        )
        assert not any(event.type == pygame.WINDOWFOCUSLOST for event in delivered)


class TestReferences:
    """Recorded references to pygame objects map back to live objects."""

    def test_window_reference_maps_to_none_like_live_display_window_events(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        add_recorded_external_event(
            recording_path=recording_path,
            frame_number=1,
            record={
                'type': pygame.WINDOWFOCUSGAINED,
                'name': 'WindowFocusGained',
                'origin': 'external',
                'attributes': {'window': {'__ref__': 'window', 'id': 1}, 'test_marker': 1},
            },
        )
        # Window events reach the game through GameEngine.process_window_event (EVENT_HANDLERS
        # binds it when the engine starts), not SceneManager.handle_event
        delivered = mocker.spy(GameEngine, 'process_window_event')
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        # Live display-window events carry window=None (the engine never makes a pygame.Window
        # of the display), so the injected event's reference is delivered as None
        windows = [
            call.args[1].window
            for call in delivered.call_args_list
            if call.args[1].type == pygame.WINDOWFOCUSGAINED
            and getattr(call.args[1], 'test_marker', None) == 1
        ]
        assert windows == [None]
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None

    def test_unmappable_joystick_event_is_dropped_with_a_warning(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        for frame_number in (1, 2):
            add_recorded_external_event(
                recording_path=recording_path,
                frame_number=frame_number,
                record={
                    'type': pygame.JOYBUTTONDOWN,
                    'name': 'JoyButtonDown',
                    'origin': 'external',
                    'attributes': {
                        'instance_id': 5,
                        'button': 0,
                        'joy': {'__ref__': 'joystick', 'instance_id': 5},
                    },
                },
            )
        pump_spy = mocker.spy(GoldenTraceEngine, '_pump_events')
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        warnings_logged = [
            record
            for record in caplog.records
            if 'instance 5 has no device; dropped' in record.getMessage()
        ]
        assert len(warnings_logged) == 1
        delivered = [event for batch in pump_spy.spy_return_list for event in batch]
        assert not any(event.type == pygame.JOYBUTTONDOWN for event in delivered)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None


class TestControlEventMarkers:
    """Markers the replayed code records again are compared with the recording's."""

    def test_markers_recorded_again_by_the_code_match(self, mocker, tmp_path):
        def mark() -> None:
            SceneManager().record_control_event(kind='test-marker', data={'note': 'n'})

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker, action=mark)
        engine = replay_session(recording_path=recording_path, mocker=mocker, action=mark)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None

    def test_a_marker_with_integer_keys_matches_its_recording(self, mocker, tmp_path):
        """JSON turns integer keys into strings; the replayed marker is compared in that form."""

        def mark() -> None:
            SceneManager().record_control_event(
                kind='test-marker', data={'scores': {1: 'first'}, 'pair': (1, 2)}
            )

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker, action=mark)
        engine = replay_session(recording_path=recording_path, mocker=mocker, action=mark)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None

    def test_a_missing_marker_is_a_divergence(self, mocker, tmp_path):
        def mark() -> None:
            SceneManager().record_control_event(kind='test-marker', data={'note': 'n'})

        recording_path = record_session(tmp_path=tmp_path, mocker=mocker, action=mark)
        engine = replay_session(recording_path=recording_path, mocker=mocker)  # no marker now
        assert engine.replay_sources is not None
        divergence = engine.replay_sources.result.divergence
        assert divergence is not None
        assert (divergence.kind, divergence.field, divergence.frame_number) == (
            EVENT_DIVERGENCE,
            'control event',
            1,
        )
        assert (divergence.expected, divergence.actual) == (
            {'kind': 'test-marker', 'note': 'n'},
            None,
        )


def fake_run(*, digests: list[str], divergence: str | None) -> ReplayDigestRun:
    """A finished replay subprocess, without running one."""
    return ReplayDigestRun(digests=digests, divergence=divergence)


def run_child(*, command: list[str], timeout_seconds: float):
    """Run a command through the audit's launcher, capturing stdout and stderr together.

    Commands that start the engine pass ``--headless`` themselves.

    Returns:
        The finished process (subprocess.CompletedProcess).

    """
    return run_command(
        command=command,
        environment=os.environ,
        timeout_seconds=timeout_seconds,
        capture_output=True,
    )


def sampled_part(*, frame: dict[str, Any]) -> dict[str, Any]:
    """Return the fields of a recorded frame that the replay samples (sample_scene_frame)."""
    return {'frame': frame['frame'], 'scene': frame['scene'], 'sprites': frame['sprites']}


class TestAudit:
    """--audit's comparison: per-frame digests of two replays, and their summaries."""

    def test_frame_digest_is_canonical(self):
        first = frame_digest(frame_record={'b': 1, 'a': [1, 2]})
        second = frame_digest(frame_record={'a': [1, 2], 'b': 1})
        assert first == second
        assert first != frame_digest(frame_record={'a': [2, 1], 'b': 1})

    def test_identical_runs_are_deterministic(self, tmp_path, mocker):
        mocker.patch.object(
            audit,
            '_run_replay_subprocess',
            side_effect=[
                fake_run(digests=['a', 'b'], divergence=None),
                fake_run(digests=['a', 'b'], divergence=None),
            ],
        )
        result = audit.audit_recording(command=['game'], path=tmp_path / 'r.jsonl.gz')
        assert result.is_deterministic()
        assert result.first_mismatch_frame is None
        assert result.summary().startswith('Audit passed')

    def test_runs_that_differ_report_the_first_frame(self, tmp_path, mocker):
        mocker.patch.object(
            audit,
            '_run_replay_subprocess',
            side_effect=[
                fake_run(digests=['a', 'b', 'c'], divergence=None),
                fake_run(digests=['a', 'x', 'c'], divergence=None),
            ],
        )
        result = audit.audit_recording(command=['game'], path=tmp_path / 'r.jsonl.gz')
        assert result.first_mismatch_frame == 1
        assert not result.is_deterministic()
        assert 'differ first at frame 1' in result.summary()

    def test_runs_of_different_lengths_differ_where_the_shorter_one_ends(self):
        result = compare_runs(
            first_run=fake_run(digests=['a', 'b'], divergence=None),
            second_run=fake_run(digests=['a'], divergence=None),
        )
        assert result.first_mismatch_frame == 1
        assert not result.is_deterministic()

    def test_a_run_that_diverged_from_the_recording_fails_the_audit(self, tmp_path, mocker):
        diverged = 'frame 1: sprite Marker#0 rect expected [0, 0, 4, 4], got [3, 0, 4, 4]'
        mocker.patch.object(
            audit,
            '_run_replay_subprocess',
            side_effect=[
                fake_run(digests=['a', 'b'], divergence=diverged),
                fake_run(digests=['a', 'b'], divergence=diverged),
            ],
        )
        result = audit.audit_recording(command=['game'], path=tmp_path / 'r.jsonl.gz')
        assert result.first_mismatch_frame is None
        assert not result.is_deterministic()
        assert 'diverged' in result.summary()
        assert diverged in result.summary()


class TestAuditReplayRuns:
    """The audit's replay children: their command, environment and digest files."""

    def test_each_run_gets_its_own_hash_seed_and_digest_file(self, tmp_path, mocker):
        run_spy = mocker.patch.object(
            audit,
            '_run_replay_subprocess',
            side_effect=[
                fake_run(digests=['a'], divergence=None),
                fake_run(digests=['a'], divergence=None),
            ],
        )
        audit.audit_recording(command=['game'], path=tmp_path / 'r.jsonl.gz')
        calls = run_spy.call_args_list
        assert [call.kwargs['hash_seed'] for call in calls] == list(AUDIT_HASH_SEEDS)
        assert [call.kwargs['command'] for call in calls] == [['game'], ['game']]
        assert calls[0].kwargs['digest_path'] != calls[1].kwargs['digest_path']

    def test_a_replay_subprocess_runs_with_its_hash_seed(self, tmp_path):
        """The child's environment is set before its interpreter starts (PYTHONHASHSEED)."""
        run = audit._run_replay_subprocess(
            command=[sys.executable, '-c', DIGEST_WRITING_CHILD_SOURCE],
            hash_seed='7',
            digest_path=tmp_path / 'digests.jsonl',
        )
        assert run == ReplayDigestRun(digests=['7'], divergence=None)

    @pytest.mark.parametrize(
        'exit_status',
        [ExitCode.INTERNAL_ERROR, UNLISTED_EXIT_STATUS, ExitCode.REPLAY_DIVERGED],
        ids=['internal error', 'unlisted status', 'diverged without a divergence'],
    )
    def test_a_replay_subprocess_that_crashed_after_its_digests_is_an_audit_error(
        self, tmp_path, exit_status
    ):
        """A child that wrote its digests but then failed did not finish its replay cleanly."""
        expected_message = f'exited with status {ExitCode.describe_status(exit_status)}'
        with pytest.raises(AuditRunError, match=re.escape(expected_message)):
            audit._run_replay_subprocess(
                command=[
                    sys.executable,
                    '-c',
                    digest_writing_child_source(divergence=None, exit_status=exit_status),
                ],
                hash_seed='1',
                digest_path=tmp_path / 'digests.jsonl',
            )

    def test_a_replay_subprocess_that_diverged_may_exit_as_replay_diverged(self, tmp_path):
        """A replay that diverged exits ExitCode.REPLAY_DIVERGED; the audit reads its divergence."""
        run = audit._run_replay_subprocess(
            command=[
                sys.executable,
                '-c',
                digest_writing_child_source(
                    divergence='frame 1: sprite moved', exit_status=ExitCode.REPLAY_DIVERGED
                ),
            ],
            hash_seed='1',
            digest_path=tmp_path / 'digests.jsonl',
        )
        assert run.divergence == 'frame 1: sprite moved'

    def test_a_replay_subprocess_that_writes_no_digests_is_an_audit_error(self, tmp_path):
        with pytest.raises(AuditRunError, match=f'status {UNLISTED_EXIT_STATUS}'):
            audit._run_replay_subprocess(
                command=[sys.executable, '-c', f'raise SystemExit({UNLISTED_EXIT_STATUS})'],
                hash_seed='1',
                digest_path=tmp_path / 'digests.jsonl',
            )

    def test_a_replay_subprocess_that_runs_too_long_is_killed_and_an_audit_error(self, tmp_path):
        with pytest.raises(AuditRunError, match=r'still running after 0\.5 seconds'):
            audit._run_replay_subprocess(
                command=[sys.executable, '-c', 'import time; time.sleep(60)'],
                hash_seed='1',
                digest_path=tmp_path / 'digests.jsonl',
                timeout_seconds=0.5,
            )

    def test_a_replay_subprocess_that_cannot_start_is_an_audit_error(self, tmp_path):
        with pytest.raises(AuditRunError, match='could not be started'):
            audit._run_replay_subprocess(
                command=[str(tmp_path / 'no-such-program')],
                hash_seed='1',
                digest_path=tmp_path / 'digests.jsonl',
            )

    def test_an_audit_run_error_names_the_recording(self, tmp_path, mocker):
        mocker.patch.object(
            audit, '_run_replay_subprocess', side_effect=AuditRunError('the replay hung')
        )
        with pytest.raises(AuditRunError, match=r'r\.jsonl\.gz: the replay hung'):
            audit.audit_recording(command=['game'], path=tmp_path / 'r.jsonl.gz')

    @pytest.mark.parametrize(
        'lines',
        [
            ['{"frame": 0, "digest": "a"}'],
            ['{"frame": 1, "digest": "a"}', '{"divergence": null}'],
            ['{"frame": 0}', '{"divergence": null}'],
            ['not json', '{"divergence": null}'],
            [],
            None,
        ],
        ids=[
            'no divergence line',
            'frames out of order',
            'no digest',
            'not JSON',
            'empty',
            'missing file',
        ],
    )
    def test_an_incomplete_digest_file_is_refused(self, tmp_path, lines):
        digest_path = tmp_path / 'digests.jsonl'
        if lines is not None:
            digest_path.write_text(''.join(f'{line}\n' for line in lines), encoding='utf-8')
        with pytest.raises(ValueError, match=r'digests\.jsonl'):
            read_digest_file(path=digest_path)

    @pytest.mark.parametrize(
        ('interpreter_options', 'reaches'),
        [((), True), (('-E',), False), (('-I',), False)],
        ids=['plain', '-E', '-I'],
    )
    def test_the_environment_reaches_children_unless_python_ignores_it(
        self, interpreter_options, reaches
    ):
        """Asked in a real interpreter started with each option (sys.flags cannot be faked)."""
        child = run_child(
            command=[
                sys.executable,
                *interpreter_options,
                '-c',
                (
                    'from glitchygames.replay.audit import environment_reaches_children; '
                    f'raise SystemExit({ExitCode.SUCCESS} if environment_reaches_children() '
                    f'else {ENVIRONMENT_IGNORED_EXIT_STATUS})'
                ),
            ],
            timeout_seconds=RECORD_TIMEOUT_SECONDS,
        )
        expected_status = ExitCode.SUCCESS if reaches else ENVIRONMENT_IGNORED_EXIT_STATUS
        assert child.returncode == expected_status, child.stdout
        assert environment_reaches_children()

    def test_the_audit_command_is_the_same_command_replayed_headless_without_the_audit(self):
        command = audit_command(
            original_argv=['python3', 'game.py', '--replay-trace', 'r.jsonl.gz', '--audit']
        )
        assert command == [
            sys.executable,
            'game.py',
            '--replay-trace',
            'r.jsonl.gz',
            '--audit',
            '--no-audit',
            '--headless',
        ]

    def test_the_digest_file_lists_every_replayed_frame_then_no_divergence(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        digest_path = tmp_path / 'digests.jsonl'
        press_keys_while_held(mocker=mocker, keys=(pygame.K_SPACE,))
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path,
                mocker=mocker,
                arguments=('--replay-digest', str(digest_path)),
            )
        assert exit_info.value.code == ExitCode.SUCCESS
        digests, divergence = read_digest_file(path=digest_path)
        recorded_frames = read_trace_result(path=recording_path).trace['frames']
        assert digests == [
            frame_digest(frame_record=sampled_part(frame=frame)) for frame in recorded_frames
        ]
        assert divergence is None

    def test_the_digest_file_of_a_diverged_replay_ends_with_its_divergence(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=1)
        digest_path = tmp_path / 'digests.jsonl'
        shutdown_spy = mocker.spy(GoldenTraceEngine, '_shutdown')
        # The replay pauses at the divergence; Esc ends it
        press_keys_while_held(mocker=mocker, keys=(pygame.K_SPACE, pygame.K_ESCAPE))
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path,
                mocker=mocker,
                arguments=('--replay-digest', str(digest_path)),
            )
        assert exit_info.value.code == ExitCode.REPLAY_DIVERGED
        engine = shutdown_spy.call_args.args[0]
        assert engine.replay_sources is not None
        expected_divergence = engine.replay_sources.result.divergence
        assert expected_divergence is not None
        digests, divergence = read_digest_file(path=digest_path)
        assert len(digests) == expected_divergence.frame_number + 1
        assert divergence == expected_divergence.describe()


class TestAuditOption:
    """--audit on the engine's command line, unit and end to end."""

    def test_the_audit_option_runs_the_audit_instead_of_the_replay(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        audit_spy = mocker.patch.object(
            game_engine_module,
            'audit_recording',
            return_value=compare_runs(
                first_run=fake_run(digests=['a'], divergence=None),
                second_run=fake_run(digests=['a'], divergence=None),
            ),
        )
        with (
            pytest.raises(SystemExit) as exit_info,
            constructed_engine('--replay-trace', str(recording_path), '--audit'),
        ):
            pass
        assert exit_info.value.code == ExitCode.SUCCESS
        audit_spy.assert_called_once_with(
            command=audit_command(original_argv=sys.orig_argv), path=recording_path
        )

    def test_a_nondeterministic_audit_exits_as_audit_nondeterministic_and_logs_why(
        self, mocker, tmp_path, caplog
    ):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        mocker.patch.object(
            game_engine_module,
            'audit_recording',
            return_value=compare_runs(
                first_run=fake_run(digests=['a', 'b'], divergence=None),
                second_run=fake_run(digests=['a', 'c'], divergence=None),
            ),
        )
        with (
            pytest.raises(SystemExit) as exit_info,
            constructed_engine('--replay-trace', str(recording_path), '--audit'),
        ):
            pass
        assert exit_info.value.code == ExitCode.AUDIT_NONDETERMINISTIC
        assert 'differ first at frame 1' in caplog.text

    def test_an_audit_run_error_exits_with_an_internal_error_and_logs_it(
        self, mocker, tmp_path, caplog
    ):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        mocker.patch.object(
            game_engine_module,
            'audit_recording',
            side_effect=AuditRunError('replay run 1 crashed without its digests'),
        )
        with (
            pytest.raises(SystemExit) as exit_info,
            constructed_engine('--replay-trace', str(recording_path), '--audit'),
        ):
            pass
        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        assert 'without its digests' in caplog.text

    def test_audit_without_replay_trace_is_refused(self, caplog):
        with pytest.raises(SystemExit) as exit_info, constructed_engine('--audit'):
            pass
        assert exit_info.value.code == ExitCode.OPTIONS_REFUSED
        assert '--audit needs --replay-trace' in caplog.text

    def test_audit_with_real_replay_fps_is_refused(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        audit_spy = mocker.patch.object(game_engine_module, 'audit_recording')
        with (
            pytest.raises(SystemExit) as exit_info,
            constructed_engine(
                '--replay-trace', str(recording_path), '--audit', '--replay-fps', REAL_REPLAY_FPS
            ),
        ):
            pass
        assert exit_info.value.code == ExitCode.OPTIONS_REFUSED
        assert '--audit compares recorded FPS events' in caplog.text
        audit_spy.assert_not_called()

    def test_replay_digest_without_replay_trace_warns_and_is_ignored(self, caplog):
        with constructed_engine('--replay-digest', 'digests.jsonl') as engine:
            assert engine.replay_sources is None
        assert '--replay-digest is ignored without --replay-trace' in caplog.text

    def test_a_recording_cannot_override_the_audit_options(self):
        assert {'audit', 'replay_digest', 'headless'} <= REPLAY_LOCAL_OPTIONS

    def test_a_truncated_recording_is_refused_before_the_audit_starts(
        self, mocker, tmp_path, caplog
    ):
        """An audit needs the whole recording: its children would only replay to the cut-off."""
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        cut_off_after_frame(recording_path=recording_path, frame_number=2)
        audit_spy = mocker.patch.object(game_engine_module, 'audit_recording')
        with (
            pytest.raises(SystemExit) as exit_info,
            constructed_engine('--replay-trace', str(recording_path), '--audit'),
        ):
            pass
        assert exit_info.value.code == ExitCode.UNUSABLE_INPUT
        assert (
            f'Cannot audit {recording_path}: the recording is truncated after 3 complete frames'
            in caplog.text
        )
        # Nothing announces a replay that will not happen
        assert 'replaying up to there' not in caplog.text
        assert f'Replaying {recording_path}' not in caplog.text
        audit_spy.assert_not_called()

    def test_audit_under_an_interpreter_that_ignores_the_environment_is_refused(
        self, mocker, tmp_path, caplog
    ):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        mocker.patch.object(game_engine_module, 'environment_reaches_children', return_value=False)
        audit_spy = mocker.patch.object(game_engine_module, 'audit_recording')
        with (
            pytest.raises(SystemExit) as exit_info,
            constructed_engine('--replay-trace', str(recording_path), '--audit'),
        ):
            pass
        assert exit_info.value.code == ExitCode.OPTIONS_REFUSED
        assert 'started with -E or -I' in caplog.text
        audit_spy.assert_not_called()

    def test_a_golden_recording_passes_the_real_audit(self):
        """End to end: a deterministic game's recording passes --audit (two child replays)."""
        recording_path = REPLAY_FIXTURE_DIRECTORY / 'paddleslap' / f'golden{REPLAY_FIXTURE_SUFFIX}'
        audit_run = run_child(
            command=[
                sys.executable,
                '-m',
                'glitchygames.examples.paddleslap',
                '--log-level',
                'error',
                '--replay-trace',
                str(recording_path),
                '--audit',
                '--headless',
            ],
            timeout_seconds=AUDIT_TIMEOUT_SECONDS,
        )
        assert audit_run.returncode == ExitCode.SUCCESS, audit_run.stdout

    def test_unseeded_randomness_makes_the_real_audit_fail(self, tmp_path):
        """End to end: a game drawing from an unseeded source is caught by --audit."""
        game_file = tmp_path / 'unseeded_game.py'
        game_file.write_text(UNSEEDED_GAME_SOURCE, encoding='utf-8')
        recording_path = tmp_path / 'unseeded.jsonl.gz'
        common = [
            sys.executable,
            str(game_file),
            '--target-fps',
            '0',
            '--log-level',
            'error',
            '--resolution',
            '320x240',
            '--headless',
        ]
        record_run = run_child(
            command=[*common, '--record-trace', str(recording_path)],
            timeout_seconds=RECORD_TIMEOUT_SECONDS,
        )
        assert record_run.returncode == ExitCode.SUCCESS, record_run.stdout
        audit_run = run_child(
            command=[*common, '--replay-trace', str(recording_path), '--audit'],
            timeout_seconds=AUDIT_TIMEOUT_SECONDS,
        )
        assert audit_run.returncode == ExitCode.AUDIT_NONDETERMINISTIC, audit_run.stdout
        assert 'diverged' in audit_run.stdout


def rebaseline_session(
    *,
    recording_path: Path,
    new_path: Path,
    mocker,
    action: Callable[[], None] | None = None,
    action_frame: int = 1,
) -> object:
    """Rebaseline the scripted session (``--rebaseline NEW --headless``) through the engine.

    Returns:
        The status the run exited with.

    """
    with pytest.raises(SystemExit) as exit_info:
        replay_session_with_arguments(
            recording_path=recording_path,
            mocker=mocker,
            arguments=('--rebaseline', str(new_path), '--headless'),
            action=action,
            action_frame=action_frame,
        )
    return exit_info.value.code


class TestRebaseline:
    """--replay-trace OLD --rebaseline NEW: OLD's inputs on the current code, written to NEW."""

    def test_rebaseline_writes_a_recording_that_then_matches(self, mocker, tmp_path, capsys):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        new_path = tmp_path / 'rebaselined.jsonl.gz'
        exit_status = rebaseline_session(
            recording_path=recording_path, new_path=new_path, mocker=mocker
        )
        assert exit_status == ExitCode.SUCCESS
        output = capsys.readouterr().out
        frames = read_trace_result(path=recording_path).trace['frames']
        frame_count = len(frames)
        assert output.startswith(f'Rebaselined {frame_count} frames to {new_path}: ')
        # Every tampered frame differs: those from frame 3 on that have a sprite to move
        tampered_frame_count = sum(1 for frame in frames[3:] if frame['sprites'])
        assert f'{tampered_frame_count} frames differ (first at 3: sprite ' in output
        assert 'sprites affected: ' in output
        assert not new_path.with_name(new_path.name + '.partial').exists()
        engine = replay_session(recording_path=new_path, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None
        assert engine.replay_sources.result.end_reason == 'end_of_recording'

    def test_an_unchanged_recording_rebaselines_to_the_same_frames(self, mocker, tmp_path, capsys):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        new_path = tmp_path / 'rebaselined.jsonl.gz'
        exit_status = rebaseline_session(
            recording_path=recording_path, new_path=new_path, mocker=mocker
        )
        assert exit_status == ExitCode.SUCCESS
        assert capsys.readouterr().out.rstrip().endswith(': no frames differ')
        old_trace = read_trace_result(path=recording_path).trace
        new_trace = read_trace_result(path=new_path).trace
        # Same inputs (batches with their origins, dt, input changes, control events), sprites
        # and scene starts (the replayed code captures its own, frame 0's included)
        assert new_trace['frames'] == old_trace['frames']
        assert SCENE_START_FIELD in new_trace['frames'][0]
        assert new_trace['rebaselined_from'] == str(recording_path)
        for field_name in ('random_seed', 'recorded_at', 'options', 'saves', 'devices'):
            assert new_trace[field_name] == old_trace[field_name]

    def test_rebaselined_header_keeps_the_seed_and_names_the_original(self, tmp_path):
        from glitchygames.replay.rebaseline import rebaseline_header

        header = rebaseline_header(
            original_header={'random_seed': 5, 'engine_version': 'old'},
            original_path=tmp_path / 'old.jsonl.gz',
        )
        assert header['random_seed'] == 5
        assert header['rebaselined_from'] == str(tmp_path / 'old.jsonl.gz')
        assert header['engine_version'] == importlib.metadata.version('glitchygames')
        assert 'source_truncated' not in header

    def test_a_rebaselined_header_marks_a_cut_off_source_and_drops_the_v2_marker(self, tmp_path):
        from glitchygames.replay.rebaseline import rebaseline_header

        header = rebaseline_header(
            original_header={'random_seed': 5, 'input_capture_format_version': 2},
            original_path=tmp_path / 'old.jsonl.gz',
            source_truncated=True,
        )
        assert header['source_truncated'] is True
        # The new recording captures polled input and markers itself (format 3)
        assert 'input_capture_format_version' not in header

    def test_rebaseline_keeps_internal_origins_and_late_saves(self, mocker, tmp_path):
        from glitchygames.state.sandbox import open_saves

        save_directory = tmp_path / 'saves'
        mocker.patch(
            'glitchygames.state.manager.get_save_directory',
            side_effect=lambda app_name: save_directory / app_name,
        )

        def post_and_save() -> None:
            post_event(pygame.event.Event(pygame.USEREVENT + 43, {}))
            open_saves(app_name='rebaseline-late').save('slot', {'value': 1})

        recording_path = record_session(
            tmp_path=tmp_path, mocker=mocker, action=post_and_save, action_frame=1
        )
        new_path = tmp_path / 'rebaselined.jsonl.gz'
        exit_status = rebaseline_session(
            recording_path=recording_path,
            new_path=new_path,
            mocker=mocker,
            action=post_and_save,
            action_frame=1,
        )
        assert exit_status == ExitCode.SUCCESS
        old_frames = read_trace_result(path=recording_path).trace['frames']
        new_frames = read_trace_result(path=new_path).trace['frames']
        assert old_frames[1].get('saves_opened') is not None
        assert new_frames[1].get('saves_opened') == old_frames[1].get('saves_opened')

        def posted_origins(frames: list[dict[str, Any]]) -> list[tuple[int, str]]:
            return [
                (frame_index, record['origin'])
                for frame_index, frame in enumerate(frames)
                for batch in frame['event_batches']
                for record in batch
                if record['type'] == pygame.USEREVENT + 43
            ]

        # Posted by the action in frame 1, before that frame's pump
        assert posted_origins(old_frames) == [(1, 'internal')]
        assert posted_origins(new_frames) == [(1, 'internal')]
        engine = replay_session(
            recording_path=new_path, mocker=mocker, action=post_and_save, action_frame=1
        )
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.divergence is None

    def test_a_crashed_rebaseline_writes_nothing(self, mocker, tmp_path, capsys):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        new_path = tmp_path / 'rebaselined.jsonl.gz'

        def crash() -> None:
            message = 'the game broke'
            raise RuntimeError(message)

        exit_status = rebaseline_session(
            recording_path=recording_path, new_path=new_path, mocker=mocker, action=crash
        )
        assert exit_status == ExitCode.INTERNAL_ERROR
        assert not new_path.exists()
        assert not new_path.with_name(new_path.name + '.partial').exists()
        output = capsys.readouterr().out
        assert 'Replay stopped at frame 1' in output
        assert f'{new_path} was not written' in output

    @pytest.mark.parametrize(
        ('arguments', 'message'),
        [
            (('--rebaseline', '{new}'), 'needs --headless'),
            (('--rebaseline', '{old}', '--headless'), 'would overwrite the recording'),
            (
                ('--rebaseline', '{new}', '--headless', '--record-trace', '{other}'),
                'not with --record-trace',
            ),
            (('--rebaseline', '{new}', '--headless', '--audit'), 'not with --audit'),
            (
                ('--rebaseline', '{new}', '--headless', '--replay-fps', 'real'),
                'not with --replay-fps real',
            ),
            (
                ('--rebaseline', '{new}', '--headless', '--replay-digest', '{other}'),
                'not with --replay-digest',
            ),
        ],
    )
    def test_an_unsound_rebaseline_is_refused(self, mocker, tmp_path, caplog, arguments, message):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        recording_bytes = recording_path.read_bytes()
        new_path = tmp_path / 'rebaselined.jsonl.gz'
        other_path = tmp_path / 'other.jsonl.gz'
        filled_arguments = tuple(
            argument.format(new=new_path, old=recording_path, other=other_path)
            for argument in arguments
        )
        with pytest.raises(SystemExit) as exit_info:
            replay_session_with_arguments(
                recording_path=recording_path, mocker=mocker, arguments=filled_arguments
            )
        assert exit_info.value.code == ExitCode.OPTIONS_REFUSED
        assert message in caplog.text
        assert not new_path.exists()
        assert not other_path.exists()
        assert recording_path.read_bytes() == recording_bytes

    def test_rebaseline_needs_a_recording_to_replay(self, mocker, tmp_path, caplog):
        new_path = tmp_path / 'rebaselined.jsonl.gz'
        with engine_run_environment(mocker), pytest.raises(SystemExit) as exit_info:
            run_engine('--rebaseline', str(new_path), '--headless')
        assert exit_info.value.code == ExitCode.OPTIONS_REFUSED
        assert '--rebaseline needs --replay-trace' in caplog.text
        assert not new_path.exists()

    def test_an_unusable_recording_is_refused(self, mocker, tmp_path):
        recording_path = tmp_path / 'not-a-recording.jsonl.gz'
        recording_path.write_text('nonsense', encoding='utf-8')
        new_path = tmp_path / 'rebaselined.jsonl.gz'
        exit_status = rebaseline_session(
            recording_path=recording_path, new_path=new_path, mocker=mocker
        )
        assert exit_status == ExitCode.UNUSABLE_INPUT
        assert not new_path.exists()

    def test_a_replay_that_does_not_stop_compares_every_frame(self):
        frames = [{**recorded_frame(frame_number=index), 'scene': 'Recorded'} for index in range(3)]
        sources = minimal_sources(
            frames=frames, options=ReplayOptions(headless=True, stop_on_divergence=False)
        )
        for frame_number in range(3):
            sources.end_frame(frame_number=frame_number, dt=0.25, scene=None, control_events=[])
            assert not sources.stop_requested or frame_number == 2
        result = sources.result
        assert result.frames_replayed == 3
        assert result.differing_frame_count == 3
        assert result.divergence is not None
        assert result.divergence.frame_number == 0
        assert result.divergence.kind == SCENE_DIVERGENCE
        assert result.end_reason == 'end_of_recording'

    def test_a_run_that_ends_early_keeps_the_first_divergence(self):
        frames = [
            {**recorded_frame(frame_number=0), 'scene': 'Recorded'},
            recorded_frame(frame_number=1),
            recorded_frame(frame_number=2),
        ]
        sources = minimal_sources(
            frames=frames, options=ReplayOptions(headless=True, stop_on_divergence=False)
        )
        sources.end_frame(frame_number=0, dt=0.25, scene=None, control_events=[])
        sources.finish_run()
        divergence = sources.result.divergence
        assert divergence is not None
        assert divergence.kind == SCENE_DIVERGENCE
        assert sources.result.end_reason == 'diverged'

    def test_every_differing_sprite_of_a_frame_is_named(self):
        recorded = {
            'scene': 'Game',
            'sprites': [
                {'id': 'Ball#1', 'rect': [0, 0, 4, 4], 'visible': True},
                {'id': 'Ball#2', 'rect': [8, 0, 4, 4], 'visible': True},
                {'id': 'Paddle#1', 'rect': [0, 9, 4, 4], 'visible': True},
            ],
        }
        replayed = {
            'scene': 'Game',
            'sprites': [
                {'id': 'Ball#1', 'rect': [0, 1, 4, 4], 'visible': True},
                {'id': 'Paddle#1', 'rect': [0, 9, 4, 4], 'visible': False},
                {'id': 'Spark#1', 'rect': [3, 3, 1, 1], 'visible': True},
            ],
        }
        assert driver_module.differing_sprite_ids(recorded=recorded, replayed=replayed) == [
            'Ball#1',
            'Ball#2',
            'Paddle#1',
            'Spark#1',
        ]

    def test_the_summary_describes_what_changed(self, tmp_path):
        from glitchygames.replay.rebaseline import RebaselineSummary

        new_path = tmp_path / 'new.jsonl.gz'
        divergence = Divergence(
            frame_number=6120,
            kind=SPRITE_DIVERGENCE,
            subject='Ball#2',
            field='rect',
            expected=[412, 300, 16, 16],
            actual=[412, 301, 16, 16],
        )
        summary = RebaselineSummary(
            path=new_path,
            first_divergence=divergence,
            frames_differing=412,
            sprites_affected=['Ball#2', 'Ball#3'],
            frames_replayed=9800,
            frames_recorded=9800,
            undelivered_input_count=0,
            first_undelivered_input_frame=None,
        )
        assert summary.describe() == (
            f'Rebaselined 9800 frames to {new_path}: 412 frames differ (first at 6120: sprite '
            'Ball#2 rect expected [412, 300, 16, 16], got [412, 301, 16, 16]); sprites '
            'affected: Ball#2, Ball#3'
        )
        one_frame = summary.model_copy(update={'frames_differing': 1})
        assert '1 frame differs (first at 6120' in one_frame.describe()
        unchanged = RebaselineSummary(
            path=new_path,
            first_divergence=None,
            frames_differing=0,
            sprites_affected=[],
            frames_replayed=9800,
            frames_recorded=9800,
            undelivered_input_count=0,
            first_undelivered_input_frame=None,
        )
        assert unchanged.describe() == f'Rebaselined 9800 frames to {new_path}: no frames differ'
        ended_early = RebaselineSummary(
            path=new_path,
            first_divergence=Divergence(
                frame_number=7,
                kind=LENGTH_DIVERGENCE,
                subject='recording',
                field='frames',
                expected=10,
                actual=7,
            ),
            frames_differing=0,
            sprites_affected=[],
            frames_replayed=7,
            frames_recorded=7,
            undelivered_input_count=0,
            first_undelivered_input_frame=None,
        )
        assert ended_early.describe() == (
            f'Rebaselined 7 frames to {new_path}: the run differs (at 7: length recording '
            'frames expected 10, got 7)'
        )
        with pytest.raises(ValidationError):
            summary.frames_differing = 3

    def test_a_partial_file_that_is_the_recording_is_refused(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        new_path = tmp_path / 'x.jsonl.gz'
        old_path = tmp_path / 'x.jsonl.gz.partial'
        recording_path.rename(old_path)
        recording_bytes = old_path.read_bytes()
        exit_status = rebaseline_session(recording_path=old_path, new_path=new_path, mocker=mocker)
        assert exit_status == ExitCode.OPTIONS_REFUSED
        assert 'its partial file' in caplog.text
        assert old_path.read_bytes() == recording_bytes
        assert not new_path.exists()

    def test_a_failed_final_move_keeps_the_partial_file(self, mocker, tmp_path, caplog, capsys):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        new_path = tmp_path / 'rebaselined.jsonl.gz'
        # A directory where NEW goes: the partial file cannot be moved over it
        new_path.mkdir()
        exit_status = rebaseline_session(
            recording_path=recording_path, new_path=new_path, mocker=mocker
        )
        assert exit_status == ExitCode.CANNOT_WRITE_OUTPUT
        partial_path = new_path.with_name(new_path.name + '.partial')
        assert partial_path.is_file()
        assert read_trace_result(path=partial_path).trace['frames']
        assert str(partial_path) in caplog.text
        assert f'could not be moved to {new_path}' in capsys.readouterr().out

    def test_recorded_input_the_run_never_pumped_is_reported(
        self, mocker, tmp_path, capsys, caplog
    ):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        frame_count = len(read_trace_result(path=recording_path).trace['frames'])

        def add_unpumped_batch(trace: dict[str, Any]) -> None:
            # A second batch in frame 2, which the run pumps once: its press is never served
            trace['frames'][2]['event_batches'].append([
                {
                    'type': pygame.KEYDOWN,
                    'name': 'KeyDown',
                    'origin': 'external',
                    'attributes': {'key': pygame.K_b, 'mod': 0, 'unicode': 'b', 'scancode': 5},
                }
            ])

        rewrite_recording(recording_path=recording_path, change=add_unpumped_batch)
        new_path = tmp_path / 'rebaselined.jsonl.gz'
        exit_status = rebaseline_session(
            recording_path=recording_path, new_path=new_path, mocker=mocker
        )
        # The summary is what the user reviews; the rebaseline is still written
        assert exit_status == ExitCode.SUCCESS
        output = capsys.readouterr().out
        assert '; 1 recorded input event not delivered (first at frame 2)' in output
        assert 'ended at frame' not in output
        assert '1 recorded input event not delivered' in caplog.text
        assert len(read_trace_result(path=new_path).trace['frames']) == frame_count

    def test_a_run_that_ends_before_the_recording_does_is_reported(
        self, mocker, tmp_path, capsys, caplog
    ):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        frame_count = len(read_trace_result(path=recording_path).trace['frames'])
        new_path = tmp_path / 'rebaselined.jsonl.gz'
        exit_status = rebaseline_session(
            recording_path=recording_path,
            new_path=new_path,
            mocker=mocker,
            # The current code ends the game early
            action=lambda: SceneManager().quit_game(),
            action_frame=1,
        )
        assert exit_status == ExitCode.SUCCESS
        output = capsys.readouterr().out
        new_frame_count = len(read_trace_result(path=new_path).trace['frames'])
        assert new_frame_count < frame_count
        assert f'; ended at frame {new_frame_count} of {frame_count}' in output
        assert f'ended at frame {new_frame_count} of {frame_count}' in caplog.text

    def test_the_report_history_ends_at_the_first_divergence(self):
        matching_frames = [recorded_frame(frame_number=index) for index in range(25)]
        differing_frames = [
            {**recorded_frame(frame_number=index), 'scene': 'Recorded'} for index in range(25, 40)
        ]
        sources = minimal_sources(
            frames=[*matching_frames, *differing_frames],
            options=ReplayOptions(headless=True, stop_on_divergence=False),
        )
        for frame_number in range(40):
            sources.end_frame(frame_number=frame_number, dt=0.25, scene=None, control_events=[])
        result = sources.result
        assert result.differing_frame_count == 15
        assert [frame_index for frame_index, _ in result.recorded_history] == list(range(5, 26))
        assert [frame_index for frame_index, _ in result.replayed_history] == list(range(5, 26))

    def test_the_summary_names_undelivered_input_and_an_early_end(self, tmp_path):
        from glitchygames.replay.rebaseline import RebaselineSummary

        new_path = tmp_path / 'new.jsonl.gz'
        summary = RebaselineSummary(
            path=new_path,
            first_divergence=None,
            frames_differing=0,
            sprites_affected=[],
            frames_replayed=500,
            frames_recorded=9800,
            undelivered_input_count=3,
            first_undelivered_input_frame=812,
        )
        assert summary.describe() == (
            f'Rebaselined 500 frames to {new_path}: no frames differ; 3 recorded input events '
            'not delivered (first at frame 812); ended at frame 500 of 9800'
        )
