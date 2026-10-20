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

from glitchygames.engine import game_engine as game_engine_module
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
    LENGTH_DIVERGENCE,
    REPLAY_LOCAL_OPTIONS,
    REPLAY_UNUSABLE_EXIT_CODE,
    SPRITE_DIVERGENCE,
    Divergence,
    ReplaySources,
    apply_recorded_options,
)
from glitchygames.scenes import SceneManager
from glitchygames.sources import frame_clock_seconds, install_sources
from glitchygames.tracing import GZIP_WINDOW_BITS, read_trace_result, write_trace
from tests.world.test_gameplay_recording import (
    RANDOM_SEED,
    Script,
    _key,
    _schedule_quit_in_arrival,
    engine_run_environment,
    run_engine,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

GOLDEN_SCRIPT_FRAMES = 300
# The departure scene's marker is placed from the clocks in this frame; the scene is still
# active at the frame's end (its transition starts in frame 3), so the placement is compared
CLOCK_ACTION_FRAME = 2

# The live wall clock's reading when a paced recording starts (clocks_paced_by_frames)
PACED_RECORDING_START = datetime(2026, 10, 19, 12, 0, 0, 250000, tzinfo=UTC)


def record_session(
    *,
    tmp_path: Path,
    mocker,
    action: Callable[[], None] | None = None,
    action_frame: int = 1,
) -> Path:
    """Record the departure/arrival scripted session (with an optional scripted action).

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
        run_engine('--record-trace', str(recording_path), '--random-seed', str(RANDOM_SEED))
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

    A recording made with real clocks reads real time, which no replay can serve (the replay's
    wall clock is the recording's start plus the frame clock). With the live wall clock at
    PACED_RECORDING_START plus the frame clock, and live elapsed seconds equal to the frame
    clock, a session that reads the clocks is replayable exactly.
    """
    mocker.patch.object(
        game_engine_module,
        'datetime',
        mocker.Mock(now=mocker.Mock(return_value=PACED_RECORDING_START)),
    )

    def paced_wall_clock_time(_sources: LiveSources) -> datetime:
        return PACED_RECORDING_START + timedelta(seconds=frame_clock_seconds())

    def paced_elapsed_seconds(_sources: LiveSources) -> float:
        return frame_clock_seconds()

    mocker.patch.object(LiveSources, 'wall_clock_time', new=paced_wall_clock_time)
    mocker.patch.object(LiveSources, 'elapsed_seconds', new=paced_elapsed_seconds)


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
    """Return a recorded frame with no scene, no sprites and one empty event batch.

    Returns:
        The frame record.

    """
    return {
        'frame': frame_number,
        'scene': None,
        'sprites': [],
        'dt': dt,
        'event_batches': [[]],
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
        assert sources.elapsed_seconds() == 1.5

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

    def test_truncated_recording_replays_to_the_cut_off(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        cut_off_after_frame(recording_path=recording_path, frame_number=2)
        engine = replay_session(recording_path=recording_path, mocker=mocker)
        assert engine.replay_sources is not None
        assert engine.replay_sources.result.end_reason == 'truncated'
        assert engine.replay_sources.result.frames_replayed == 3
        assert engine.replay_sources.result.divergence is None

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
