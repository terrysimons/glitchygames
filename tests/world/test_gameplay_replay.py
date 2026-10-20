"""Replays through the real engine: record a session, replay it, compare every frame."""

from __future__ import annotations

import gzip
import json
import zlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pygame
import pytest
from scripts.record_golden_traces import (
    GAME_SCENES,
    GoldenTraceEngine,
    record_trace,
    replay_golden_recording,
)

from glitchygames.engine import GameEngine
from glitchygames.engine import game_engine as game_engine_module
from glitchygames.events import FPSEVENT
from glitchygames.live_sources import LiveSources
from glitchygames.recording import (
    INTERNAL_ORIGIN,
    RECORDING_FORMAT_THREE_FIELDS,
    GameplayRecorder,
    RecordingSources,
    pending_internal_posts,
    post_event,
)
from glitchygames.replay.driver import (
    EVENT_DIVERGENCE,
    LENGTH_DIVERGENCE,
    REAL_REPLAY_FPS,
    RECORDED_REPLAY_FPS,
    REPLAY_LOCAL_OPTIONS,
    REPLAY_UNUSABLE_EXIT_CODE,
    SCENE_DIVERGENCE,
    SPRITE_DIVERGENCE,
    Divergence,
    ReplaySources,
    apply_recorded_options,
)
from glitchygames.replay.input_blocking import REAL_INPUT_EVENT_TYPES, EventTypeBlock
from glitchygames.scenes import SceneManager
from glitchygames.sources import frame_clock_seconds, install_sources, reset_sources
from glitchygames.tracing import GZIP_WINDOW_BITS, read_trace_result, write_trace
from tests.world import test_gameplay_recording as recording_test_module
from tests.world.test_gameplay_recording import (
    FAKE_CLOCK_STEP_SECONDS,
    RANDOM_SEED,
    Script,
    _key,
    _schedule_quit_in_arrival,
    constructed_engine,
    engine_run_environment,
    run_engine,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

GOLDEN_SCRIPT_FRAMES = 300
# A golden recording of this many frames, replayed by a harness stopped after the frame limit
EARLY_STOP_RECORDED_FRAMES = 30
EARLY_STOP_FRAME_LIMIT = 10
# The departure scene's marker is placed from the clocks in this frame; the scene is still
# active at the frame's end (its transition starts in frame 3), so the placement is compared
CLOCK_ACTION_FRAME = 2

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
    """Replay through the real engine.

    The test scenes post their scripted input with raw pygame.event.post, so the recording holds
    it as external events and the replay serves it from the recording: by default the scenes post
    nothing during the replay. `events_by_frame` makes them post real events anyway (they must be
    dropped); `action` repeats a scripted action that is not input (a save write, a clock read).

    Returns:
        The engine, after the replay ran.

    """
    with engine_run_environment(mocker):
        Script.events_by_frame = events_by_frame or {}
        Script.action, Script.action_frame = action, action_frame
        engine = run_engine('--replay-trace', str(recording_path))
    return engine


def rewrite_recording(*, recording_path: Path, change: Callable[[dict[str, Any]], None]) -> None:
    """Read a recording, let `change` edit the in-memory trace, write it back (format 3)."""
    trace = read_trace_result(path=recording_path).trace
    change(trace)
    write_trace(trace=trace, path=recording_path)


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


def tamper_first_sprite_rect(*, recording_path: Path, frame_number: int) -> None:
    """Move the first sprite 1 px down from `frame_number` on."""

    def move(trace: dict[str, Any]) -> None:
        for frame in trace['frames'][frame_number:]:
            if frame['sprites']:
                frame['sprites'][0]['rect'][1] += 1

    rewrite_recording(recording_path=recording_path, change=move)


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


def minimal_sources(*, frames: list[dict[str, Any]], is_truncated: bool = False) -> ReplaySources:
    """Build replay sources over in-memory frames (no file).

    Returns:
        The sources.

    """
    header = {
        'game_class': 'SomeGame',
        'random_seed': RANDOM_SEED,
        'recorded_at': '2026-10-19T12:00:00',
        'options': {},
    }
    return ReplaySources(header=header, frames=frames, format_version=3, is_truncated=is_truncated)


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

    def test_divergence_is_logged_at_shutdown(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        divergence = engine.replay_sources.result.divergence
        assert divergence is not None
        assert divergence.describe().startswith('frame 3: sprite ')
        assert f'Replay diverged: {divergence.describe()}' in caplog.text

    def test_matching_replay_is_logged_at_shutdown(self, mocker, tmp_path, caplog):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        caplog.set_level('INFO', logger='game.engine')
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        frames_replayed = engine.replay_sources.result.frames_replayed
        assert f'Replay matched {frames_replayed} frames' in caplog.text

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
        assert sources.recorded_frame_fields(frame_index=0) == {}
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
        assert sources.recorded_frame_fields(frame_index=0) == {
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


class TestReplayFps:
    """--replay-fps: FPS events from the recorded frame times (default) or this machine's."""

    def test_the_default_is_recorded(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.fps_source == RECORDED_REPLAY_FPS
        assert minimal_sources(frames=[recorded_frame(frame_number=0)]).fps_source == (
            RECORDED_REPLAY_FPS
        )

    def test_the_performance_frame_time_door_serves_each_mode(self):
        recorded_sources = minimal_sources(frames=[recorded_frame(frame_number=0)])
        real_sources = minimal_sources(frames=[recorded_frame(frame_number=0)])
        real_sources.fps_source = REAL_REPLAY_FPS
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
        with engine_run_environment(mocker):
            engine = run_engine(
                '--replay-trace', str(recording_path), '--replay-fps', REAL_REPLAY_FPS
            )
        assert engine.replay_sources is not None
        assert engine.replay_sources.fps_source == REAL_REPLAY_FPS
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
        assert exit_info.value.code == REPLAY_UNUSABLE_EXIT_CODE
        assert 'SomeOtherGame' in caplog.text

    def test_missing_file_is_refused(self, mocker, tmp_path):
        with pytest.raises(SystemExit) as exit_info:
            replay_session(recording_path=tmp_path / 'missing.jsonl.gz', mocker=mocker)
        assert exit_info.value.code == REPLAY_UNUSABLE_EXIT_CODE

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
        assert exit_info.value.code == REPLAY_UNUSABLE_EXIT_CODE
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
        assert exit_info.value.code == REPLAY_UNUSABLE_EXIT_CODE
        assert 'recording over a replay is not supported yet' in caplog.text
        assert not (tmp_path / 'over-the-replay.jsonl.gz').exists()

    def test_truncated_recording_replays_to_the_cut_off(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        cut_off_after_frame(recording_path=recording_path, frame_number=2)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.end_reason == 'truncated'
        assert engine.replay_sources.result.frames_replayed == 3
        assert engine.replay_sources.result.divergence is None

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
        engine = replay_session(
            recording_path=recording_path, mocker=mocker, action=fail, action_frame=ACTION_FRAME
        )
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
