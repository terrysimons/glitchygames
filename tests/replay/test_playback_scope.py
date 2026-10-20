"""The playback scope (glitchygames/replay/playback.py).

A rebuilt scene plays a recording on scoped sources while the live game waits untouched.
"""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import random
from typing import TYPE_CHECKING, Any

import pygame
import pytest
from scripts.record_golden_traces import FRAME_SECONDS, press, release

from glitchygames.events import FPSEVENT
from glitchygames.input.state import IDLE_INPUT, current_input
from glitchygames.live_sources import LiveSources
from glitchygames.randomness import random_stream
from glitchygames.recording import SCENE_START_FIELD, post_event
from glitchygames.replay.playback import (
    PlaybackOptions,
    PlaybackSources,
    find_scene_class,
    start_playback,
    start_playback_from_recording,
)
from glitchygames.sources import active_sources, has_scoped_sources, take_redelivered_events
from glitchygames.state import open_saves
from glitchygames.supervision import PLAYBACK_KIND
from glitchygames.tracing import read_trace_result
from glitchygames.transitions import FadeTransition
from tests.replay.playback_fixtures import (
    COUNTING_SAVE_NAMESPACE,
    COUNTING_SAVE_SLOT,
    COUNTING_STREAM_NAME,
    MARKER_TRAVEL,
    SAVING_TICK,
    SWITCHING_TICK,
    CountingScene,
    DemoLoopScene,
    InputReadingScene,
    KeyReleaseCountingScene,
    PostingCountingScene,
    QuittingCountingScene,
    SavingCountingScene,
    SwitchingCountingScene,
    TransitioningCountingScene,
    active_counting_scene,
    record_counting_scene,
    step_finishing,
    tamper_sprite_in_frame,
)
from tests.world.test_frame_integration import (
    TEST_FADE_SECONDS,
    CameraFreeScene,
    running_scene,
    step,
)
from tests.world.test_gameplay_replay import cut_off_after_frame

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

RECORDED_FRAMES = 10
SHORT_RECORDED_FRAMES = 6
LIVE_FRAMES_BEFORE = 3
LIVE_FRAMES_AFTER = 2
FAR_FROM_ZERO_FRAMES = 40
# The frame of a tampered recording whose marker moved
TAMPERED_FRAME = 3
# The live scene's slot, which a playback must never change
LIVE_SAVE_VALUE = 1
# The frame a second recorded scene begins on
LATER_SCENE_FRAME = 4
# What the live doors' scripted polled input says the mouse is at
SCRIPTED_MOUSE_POSITION = (123, 45)
# FPS events every other frame at 60 FPS (posted each half interval: 25 ms)
FPS_EVENT_INTERVAL_MILLISECONDS = 50


def recorded_trace(*, path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return a recording's header fields and frames.

    Returns:
        The header (without the frames) and the decoded frames.

    """
    trace = read_trace_result(path=path).trace
    return {name: value for name, value in trace.items() if name != 'frames'}, trace['frames']


def record_later_scene(*, tmp_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Record a scene, then a second one switched to between frames at LATER_SCENE_FRAME.

    Returns:
        The recording's header fields and frames.

    """
    recording_path = tmp_path / 'later.jsonl.gz'
    with running_scene(CountingScene) as manager:
        engine = manager.game_engine
        assert engine is not None
        engine.start_trace_recording(path=recording_path)
        # Built while recording: it captures its start, which the frame it begins holds
        manager.switch_to_scene(CountingScene(options=engine.OPTIONS))
        step(manager, frames=LATER_SCENE_FRAME)
        # Switched to between frames: its first whole frame is LATER_SCENE_FRAME
        manager.switch_to_scene(CountingScene(options=engine.OPTIONS))
        step(manager, frames=SHORT_RECORDED_FRAMES)
        engine.stop_trace_recording()
    return recorded_trace(path=recording_path)


def outcome_reason(manager: Any) -> str:
    """Return why the last playback scope ended.

    Returns:
        The outcome's reason.

    """
    outcome = manager.last_playback_outcome
    assert outcome is not None
    return outcome.reason


class TestPlaybackScope:
    """Entering, playing and leaving a playback scope."""

    def test_playback_returns_to_the_untouched_live_scene(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            step(manager, frames=LIVE_FRAMES_BEFORE)
            live_scene = active_counting_scene(manager)
            live_frames_ticked = live_scene.frames_ticked
            live_marker_rect = live_scene.marker.rect.copy()
            assert start_playback_from_recording(
                manager=manager, path=recording_path, then=live_scene
            )
            # Entered at the start of the next frame: the frame that asked ends live
            assert manager.playback_session is None
            step(manager)
            playback_scene = active_counting_scene(manager)
            assert playback_scene is not live_scene
            assert isinstance(active_sources(), PlaybackSources)
            step(manager, frames=RECORDED_FRAMES - 1)
            # The recording played to its end, then the scope ended with that frame
            assert manager.playback_session is None
            assert manager.active_scene is live_scene
            assert live_scene.frames_ticked == live_frames_ticked
            assert live_scene.setup_calls == 1
            assert live_scene.marker.rect == live_marker_rect
            assert playback_scene.frames_ticked == RECORDED_FRAMES
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None
            assert result.end_reason == 'end_of_recording'
            assert outcome_reason(manager) == 'end_of_recording'
            assert result.frames_replayed == RECORDED_FRAMES
            assert not has_scoped_sources()
            # The live game goes on where it was
            step(manager, frames=LIVE_FRAMES_AFTER)
            assert live_scene.frames_ticked == live_frames_ticked + LIVE_FRAMES_AFTER

    def test_random_streams_are_unchanged_by_a_playback(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            step(manager, frames=2)
            expected_state = random_stream(COUNTING_STREAM_NAME).getstate()
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            step(manager, frames=RECORDED_FRAMES)
            assert manager.playback_session is None
            assert random_stream(COUNTING_STREAM_NAME).getstate() == expected_state

    def test_any_key_ends_a_demo(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            start_playback_from_recording(
                manager=manager,
                path=recording_path,
                then=live_scene,
                options=PlaybackOptions(exit_on_input=True),
            )
            step(manager, frames=2)
            assert manager.playback_session is not None
            step(manager, press(pygame.K_SPACE))
            assert manager.playback_session is None
            assert manager.active_scene is live_scene
            # Left early: the comparison was still running, and matched so far
            result = manager.last_playback_result
            assert result is not None
            assert result.end_reason == 'running'
            assert outcome_reason(manager) == 'exit_input'
            assert result.divergence is None
            # The release reaches the live scene
            step(manager, release(pygame.K_SPACE))
            assert manager.active_scene is live_scene

    def test_input_never_reaches_the_playback_scene(self, tmp_path, mocker: MockerFixture):
        """Without exit_on_input a key press neither ends the scope nor reaches its scene."""
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        key_down = mocker.spy(CountingScene, 'on_key_down_event')
        with running_scene(CountingScene) as manager:
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            step(manager)
            step(manager, press(pygame.K_SPACE))
            step(manager, release(pygame.K_SPACE))
            assert manager.playback_session is not None
            key_down.assert_not_called()
            step(manager, frames=RECORDED_FRAMES)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None

    def test_then_another_scene_is_switched_to(self, tmp_path):
        """A demo can return to a scene other than the live one, which is then cleaned up."""
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            title_scene = CameraFreeScene(options=live_scene.options)
            start_playback_from_recording(manager=manager, path=recording_path, then=title_scene)
            step(manager, frames=SHORT_RECORDED_FRAMES)
            assert manager.active_scene is title_scene
            assert manager.previous_scene is live_scene

    def test_a_playback_requested_during_a_transition_waits_for_its_end(self, tmp_path):
        """The transition belongs to the live game: the scope begins once it is over."""
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            departing_scene = active_counting_scene(manager)
            arriving_scene = CountingScene(options=departing_scene.options)
            departing_scene.transition_to(
                arriving_scene, FadeTransition(duration=TEST_FADE_SECONDS)
            )
            step(manager)
            assert start_playback_from_recording(
                manager=manager, path=recording_path, then=arriving_scene
            )
            transition_frames = 0
            while manager.playback_session is None:
                step(manager)
                transition_frames += 1
                assert transition_frames <= TEST_FADE_SECONDS / FRAME_SECONDS + 2
            # The transition ran to its end first, then the scope began on its own frame
            assert transition_frames > 1
            assert active_counting_scene(manager) is not arriving_scene
            step(manager, frames=SHORT_RECORDED_FRAMES - 1)
            assert manager.active_scene is arriving_scene
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None

    def test_playback_frames_index_the_recording_from_its_start(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            # Session frame numbers are far from 0
            step(manager, frames=FAR_FROM_ZERO_FRAMES)
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            step(manager, frames=SHORT_RECORDED_FRAMES + LIVE_FRAMES_AFTER)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None
            assert result.frames_replayed == SHORT_RECORDED_FRAMES

    def test_a_scene_that_began_on_a_later_frame_plays_from_there(self, tmp_path):
        """start_frame: the frames before are learned, not served; sprite ids continue."""
        header, frames = record_later_scene(tmp_path=tmp_path)
        assert SCENE_START_FIELD in frames[LATER_SCENE_FRAME]
        with running_scene(CountingScene) as manager:
            assert start_playback(
                manager=manager,
                header=header,
                frames=frames,
                then=active_counting_scene(manager),
                options=PlaybackOptions(start_frame=LATER_SCENE_FRAME),
            )
            step(manager, frames=SHORT_RECORDED_FRAMES)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None
            assert result.end_reason == 'end_of_recording'
            assert result.frames_replayed == LATER_SCENE_FRAME + SHORT_RECORDED_FRAMES

    def test_a_divergence_ends_the_scope(self, tmp_path):
        """The recording no longer matches (the game changed): the scope ends there."""
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        header, frames = recorded_trace(path=recording_path)
        marker = next(
            sprite
            for sprite in frames[TAMPERED_FRAME]['sprites']
            if sprite['id'].startswith('ScreenSprite')
        )
        marker['rect'][0] += 1
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            start_playback(manager=manager, header=header, frames=frames, then=live_scene)
            step(manager, frames=TAMPERED_FRAME + 1)
            assert manager.playback_session is None
            assert manager.active_scene is live_scene
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is not None
            assert result.divergence.frame_number == TAMPERED_FRAME
            assert result.end_reason == 'diverged'
            assert outcome_reason(manager) == 'diverged'


class TestPlaybackErrors:
    """An error inside the scope ends it and restores the live game; bad requests start nothing."""

    def test_error_inside_scope_restores_the_live_game(
        self, tmp_path, mocker: MockerFixture, caplog
    ):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            step(manager, frames=2)
            live_scene = active_counting_scene(manager)
            expected_state = random_stream(COUNTING_STREAM_NAME).getstate()
            sources_before = active_sources()
            start_playback_from_recording(manager=manager, path=recording_path, then=live_scene)
            step(manager)
            playback_scene = active_counting_scene(manager)
            mocker.patch.object(playback_scene, 'dt_tick', side_effect=RuntimeError('boom'))
            step(manager)
            assert manager.playback_session is None
            assert manager.active_scene is live_scene
            assert active_sources() is sources_before
            assert random_stream(COUNTING_STREAM_NAME).getstate() == expected_state
            assert 'boom' in caplog.text
            assert outcome_reason(manager) == 'error'
            # The live game goes on
            step(manager)
            assert live_scene.frames_ticked == 3

    def test_error_while_entering_restores_the_live_game(
        self, tmp_path, mocker: MockerFixture, caplog
    ):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            expected_state = random_stream(COUNTING_STREAM_NAME).getstate()
            start_playback_from_recording(manager=manager, path=recording_path, then=live_scene)
            mocker.patch.object(CountingScene, 'setup', side_effect=RuntimeError('no setup'))
            step(manager)
            assert manager.playback_session is None
            assert manager.active_scene is live_scene
            assert not has_scoped_sources()
            # The frame ran live, its tick drawing from the streams as they were saved
            assert live_scene.frames_ticked == 1
            expected_stream = random.Random()
            expected_stream.setstate(expected_state)
            assert live_scene.marker.rect.x == int(expected_stream.random() * MARKER_TRAVEL)
            assert 'no setup' in caplog.text
            assert outcome_reason(manager) == 'error'

    def test_a_recording_without_a_scene_start_starts_nothing(self, tmp_path, caplog):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        header, frames = recorded_trace(path=recording_path)
        del frames[0][SCENE_START_FIELD]
        with running_scene(CountingScene) as manager:
            assert not start_playback(
                manager=manager, header=header, frames=frames, then=manager.active_scene
            )
            assert not start_playback(
                manager=manager,
                header=header,
                frames=frames,
                then=manager.active_scene,
                options=PlaybackOptions(start_frame=len(frames)),
            )
            step(manager)
            assert manager.playback_session is None
        assert 'holds no scene start' in caplog.text
        assert f'has no frame {len(frames)}' in caplog.text

    def test_an_unknown_scene_class_starts_nothing(self, tmp_path, caplog):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        header, frames = recorded_trace(path=recording_path)
        frames[0][SCENE_START_FIELD]['scene_class'] = 'NoSuchScene'
        with running_scene(CountingScene) as manager:
            assert not start_playback(
                manager=manager, header=header, frames=frames, then=manager.active_scene
            )
        assert 'no scene class named NoSuchScene' in caplog.text

    def test_an_unreadable_recording_starts_nothing(self, tmp_path, caplog):
        not_a_recording = tmp_path / 'not-a-recording.jsonl.gz'
        not_a_recording.write_text('not gzip')
        with running_scene(CountingScene) as manager:
            assert not start_playback_from_recording(
                manager=manager, path=tmp_path / 'missing.jsonl.gz', then=manager.active_scene
            )
            assert not start_playback_from_recording(
                manager=manager, path=not_a_recording, then=manager.active_scene
            )
        assert 'cannot be read' in caplog.text

    def test_a_header_without_a_seed_starts_nothing(self, tmp_path, caplog):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        header, frames = recorded_trace(path=recording_path)
        del header['random_seed']
        with running_scene(CountingScene) as manager:
            assert not start_playback(
                manager=manager, header=header, frames=frames, then=manager.active_scene
            )
        assert 'cannot be replayed' in caplog.text

    def test_scopes_do_not_nest(self, tmp_path, caplog):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            assert start_playback_from_recording(
                manager=manager, path=recording_path, then=live_scene
            )
            assert not start_playback_from_recording(
                manager=manager, path=recording_path, then=live_scene
            )
            step(manager)
            assert not start_playback_from_recording(
                manager=manager, path=recording_path, then=live_scene
            )
        assert 'already starting or playing' in caplog.text

    def test_scene_classes_are_found_by_unique_name(self):
        assert find_scene_class(name='CountingScene') is CountingScene
        assert find_scene_class(name='NoSuchScene') is None


class TestPlaybackSourcesServeTheRecording:
    """Saves are sandboxed and the playback scene's own posts are matched by the replay."""

    def test_real_saves_untouched_by_a_playback(self, tmp_path):
        recording_path = record_counting_scene(
            tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES, scene_class=SavingCountingScene
        )
        with running_scene(CountingScene) as manager:
            live_store = open_saves(app_name=COUNTING_SAVE_NAMESPACE)
            live_store.save(COUNTING_SAVE_SLOT, {'value': LIVE_SAVE_VALUE})
            slot_path = live_store.find_slot_path(COUNTING_SAVE_SLOT)
            bytes_before = slot_path.read_bytes()
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            step(manager, frames=SAVING_TICK)
            # The playback scene wrote its slot into the sandbox
            sandbox = active_sources().saves(namespace=COUNTING_SAVE_NAMESPACE)
            assert sandbox is not live_store
            assert sandbox.load(COUNTING_SAVE_SLOT) == {'value': 2}
            step(manager, frames=SHORT_RECORDED_FRAMES)
            assert manager.playback_session is None
            assert open_saves(app_name=COUNTING_SAVE_NAMESPACE) is live_store
            assert live_store.load(COUNTING_SAVE_SLOT) == {'value': LIVE_SAVE_VALUE}
            assert slot_path.read_bytes() == bytes_before
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None

    def test_playback_scene_posts_reach_the_replay_merge(self, tmp_path):
        """The playback scene's posts are matched with the recording's (no missing event)."""
        recording_path = record_counting_scene(
            tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES, scene_class=PostingCountingScene
        )
        with running_scene(CountingScene) as manager:
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            step(manager, frames=SHORT_RECORDED_FRAMES)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None
            assert result.frames_replayed == SHORT_RECORDED_FRAMES

    def test_live_posts_queued_before_the_scope_are_dropped(self, tmp_path):
        """The live game's post still queued when the scope begins is not the recording's."""
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            post_event(pygame.event.Event(pygame.USEREVENT, {'live': True}))
            step(manager, frames=SHORT_RECORDED_FRAMES)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None


class TestRecordingDuringAPlayback:
    """A session recorded through a playback holds what the live session did, and replays."""

    def test_the_session_recording_holds_the_scope_and_replays(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        session_path = tmp_path / 'session.jsonl.gz'
        with running_scene(CountingScene) as manager:
            engine = manager.game_engine
            assert engine is not None
            engine.start_trace_recording(path=session_path)
            self._play_in_the_session(manager=manager, recording_path=recording_path)
            engine.stop_trace_recording()
        _header, session_frames = recorded_trace(path=session_path)
        scope_frames = session_frames[2 : 2 + SHORT_RECORDED_FRAMES]
        assert scope_frames[0]['control_events'] == [
            {'kind': PLAYBACK_KIND, 'source': 'demo', 'frames': SHORT_RECORDED_FRAMES}
        ]
        # The player's press (only the exit check saw it), with no scene start or saves
        assert [record['type'] for record in scope_frames[1]['event_batches'][0]] == [
            pygame.KEYDOWN
        ]
        for frame in scope_frames:
            assert SCENE_START_FIELD not in frame
            assert 'saves_opened' not in frame
        with running_scene(
            CountingScene, extra_arguments=['--replay-trace', str(session_path), '--headless']
        ) as manager:
            engine = manager.game_engine
            assert engine is not None
            replay_sources = engine.replay_sources
            assert replay_sources is not None
            self._play_in_the_session(manager=manager, recording_path=recording_path)
            replay_sources.finish_run()
            assert replay_sources.result.divergence is None
            assert replay_sources.result.frames_replayed == len(session_frames)

    @staticmethod
    def _play_in_the_session(*, manager: Any, recording_path: Path) -> None:
        """Run two live frames, a playback with a key press in it, then two live frames."""
        step(manager, frames=2)
        start_playback_from_recording(
            manager=manager, path=recording_path, then=active_counting_scene(manager)
        )
        step(manager)
        step(manager, press(pygame.K_SPACE))
        step(manager, release(pygame.K_SPACE))
        step(manager, frames=SHORT_RECORDED_FRAMES - 3 + LIVE_FRAMES_AFTER)
        assert manager.playback_session is None
        result = manager.last_playback_result
        assert result is not None
        assert result.divergence is None


class TestQuitDuringAPlayback:
    """Only the player's real QUIT quits the game; the recording's ends the scope."""

    def test_the_playback_scenes_own_quit_ends_the_scope_not_the_game(self, tmp_path):
        recording_path = record_counting_scene(
            tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES, scene_class=QuittingCountingScene
        )
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            start_playback_from_recording(manager=manager, path=recording_path, then=live_scene)
            step(manager, frames=SHORT_RECORDED_FRAMES)
            assert manager.quit_requested is False
            assert manager.playback_session is None
            assert manager.active_scene is live_scene
            assert outcome_reason(manager) == 'recording_quit'

    def test_a_recorded_window_quit_ends_the_scope_not_the_game(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        header, frames = recorded_trace(path=recording_path)
        frames[2]['event_batches'][0].append({
            'type': pygame.QUIT,
            'name': 'Quit',
            'origin': 'external',
            'attributes': {},
        })
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            start_playback(manager=manager, header=header, frames=frames, then=live_scene)
            step(manager, frames=3)
            assert manager.quit_requested is False
            assert manager.playback_session is None
            assert manager.active_scene is live_scene
            assert outcome_reason(manager) == 'recording_quit'

    def test_a_real_quit_during_a_scope_tears_the_live_game_down(
        self, tmp_path, mocker: MockerFixture
    ):
        """The player's QUIT quits; the run's end ends the scope first.

        So the live scene is the one cleaned up, and the doors, streams and clock come back.
        """
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            expected_state = random_stream(COUNTING_STREAM_NAME).getstate()
            live_cleanup = mocker.spy(live_scene, 'cleanup')
            start_playback_from_recording(manager=manager, path=recording_path, then=live_scene)
            step(manager)
            playback_cleanup = mocker.spy(active_counting_scene(manager), 'cleanup')
            step(manager, pygame.event.Event(pygame.QUIT, {}))
            assert manager.quit_requested is True
            manager.terminate()
            assert manager.playback_session is None
            assert manager.active_scene is None
            assert not has_scoped_sources()
            assert random_stream(COUNTING_STREAM_NAME).getstate() == expected_state
            playback_cleanup.assert_called_once()
            live_cleanup.assert_called_once()
            assert outcome_reason(manager) == 'quit'

    def test_the_runs_end_drops_a_requested_playback(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            manager.terminate()
            assert manager._requested_playback is None
            assert manager.playback_session is None


class TestPolledInputInAPlayback:
    """The playback scene polls the recording's input; the live scene gets its own back."""

    def test_polled_input_does_not_leak_either_way(self, tmp_path, mocker: MockerFixture):
        recording_path = record_counting_scene(
            tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES, scene_class=InputReadingScene
        )
        with running_scene(InputReadingScene) as manager:
            live_input = dataclasses.replace(IDLE_INPUT, mouse_position=SCRIPTED_MOUSE_POSITION)
            mocker.patch.object(active_sources(), 'input_snapshot', return_value=live_input)
            live_scene = manager.active_scene
            assert isinstance(live_scene, InputReadingScene)
            step(manager, frames=2)
            assert live_scene.mouse_positions[-1] == SCRIPTED_MOUSE_POSITION
            start_playback_from_recording(manager=manager, path=recording_path, then=live_scene)
            step(manager)
            playback_scene = manager.active_scene
            assert isinstance(playback_scene, InputReadingScene)
            # Its first tick reads the input before the recording's first frame: idle
            assert playback_scene.mouse_positions == [IDLE_INPUT.mouse_position]
            step(manager, frames=SHORT_RECORDED_FRAMES - 1)
            assert manager.active_scene is live_scene
            assert current_input() == live_input
            step(manager)
            assert live_scene.mouse_positions[-1] == SCRIPTED_MOUSE_POSITION


class TestLiveEventsKeptThroughAPlayback:
    """The live game's events that arrive during a scope reach it after the scope."""

    @pytest.mark.parametrize(
        'held_event',
        [
            pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE, mod=0, unicode='', scancode=0),
            pygame.event.Event(pygame.AUDIODEVICEADDED, which=0, iscapture=0),
            pygame.event.Event(pygame.WINDOWRESIZED, x=640, y=480),
        ],
        ids=['release', 'device', 'window'],
    )
    def test_held_external_events_are_delivered_after_the_scope(
        self, tmp_path, mocker: MockerFixture, held_event
    ):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            engine = manager.game_engine
            assert engine is not None
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            step(manager)
            step(manager, held_event)
            step(manager, frames=SHORT_RECORDED_FRAMES - 2)
            assert manager.playback_session is None
            pump = mocker.spy(engine, '_pump_events')
            step(manager)
            assert [event.type for event in pump.spy_return] == [held_event.type]
            assert pump.spy_return[0].dict == held_event.dict

    def test_live_posts_queued_before_the_scope_are_posted_again_after_it(
        self, tmp_path, mocker: MockerFixture
    ):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            engine = manager.game_engine
            assert engine is not None
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            post_event(pygame.event.Event(pygame.USEREVENT, {'live': True}))
            step(manager, frames=SHORT_RECORDED_FRAMES)
            assert manager.playback_session is None
            pump = mocker.spy(engine, '_pump_events')
            step(manager)
            assert [(event.type, event.dict) for event in pump.spy_return] == [
                (pygame.USEREVENT, {'live': True})
            ]


class TestOnlyScopedErrorsAreContained:
    """An error of the installed doors under a scope propagates as it would outside one."""

    def test_a_session_recorder_error_propagates(self, tmp_path, mocker: MockerFixture):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            installed_sources = active_sources()
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            step(manager)
            mocker.patch.object(installed_sources, 'end_frame', side_effect=OSError('disk full'))
            with pytest.raises(OSError, match='disk full'):
                step(manager)


class TestUnusableRequests:
    """Malformed recordings and requests that cannot be honoured start nothing."""

    @pytest.mark.parametrize('damage', ['bad_id', 'missing_id'])
    def test_a_malformed_recording_starts_nothing(self, tmp_path, caplog, damage):
        header, frames = record_later_scene(tmp_path=tmp_path)
        sprite = frames[1]['sprites'][0]
        if damage == 'bad_id':
            sprite['id'] = 'Broken'
        else:
            del sprite['id']
        with running_scene(CountingScene) as manager:
            assert not start_playback(
                manager=manager,
                header=header,
                frames=frames,
                then=manager.active_scene,
                options=PlaybackOptions(start_frame=LATER_SCENE_FRAME),
            )
        assert 'cannot be replayed' in caplog.text

    def test_a_request_in_the_frame_of_a_scene_switch_is_dropped(
        self, tmp_path, mocker: MockerFixture, caplog
    ):
        """The live scene left in the frame that asked: there is no live scene to return to."""
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            next_scene = CountingScene(options=live_scene.options)

            def request_and_leave(dt: float) -> None:
                del dt
                assert start_playback_from_recording(
                    manager=manager, path=recording_path, then=live_scene
                )
                live_scene.next_scene = next_scene

            mocker.patch.object(live_scene, 'dt_tick', side_effect=request_and_leave)
            step(manager)
            assert manager.active_scene is next_scene
            step(manager)
            assert manager.playback_session is None
            assert manager.active_scene is next_scene
        assert 'the scene that asked for it has gone' in caplog.text


def record_switching_session(
    *,
    tmp_path: Path,
    scene_class: type[CountingScene],
    frames: int,
    option_overrides: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Record a scene that leaves for a new CountingScene mid-run.

    Args:
        tmp_path: Where the recording goes.
        scene_class: The leaving scene (switching or transitioning).
        frames: How many frames to record.
        option_overrides: Engine options to change for the run; given, frames run as start()
            runs them (frame clock, FPS events: ``step_finishing``).

    Returns:
        The recording's header fields and frames.

    """
    recording_path = tmp_path / f'{scene_class.__name__}-session.jsonl.gz'
    with running_scene(CameraFreeScene) as manager, contextlib.ExitStack() as restorations:
        engine = manager.game_engine
        assert engine is not None
        if option_overrides is not None:
            options_before = dict(manager.OPTIONS)
            manager.OPTIONS.update(option_overrides)
            restorations.callback(manager.OPTIONS.update, options_before)
        manager.dt = FRAME_SECONDS
        engine.start_trace_recording(path=recording_path)
        manager.switch_to_scene(scene_class(options=engine.OPTIONS))
        if option_overrides is not None:
            step_finishing(manager, frames=frames)
        else:
            step(manager, frames=frames)
        engine.stop_trace_recording()
    return recorded_trace(path=recording_path)


def arriving_scene_start_frame(*, frames: list[dict[str, Any]]) -> int:
    """Return the frame holding the arriving CountingScene's start.

    Returns:
        The frame index.

    """
    (start_frame,) = [
        index
        for index, frame in enumerate(frames)
        if frame.get(SCENE_START_FIELD, {}).get('scene_class') == 'CountingScene'
    ]
    return start_frame


class TestScenesThatBeganMidRun:
    """A playback starts at the scene's first logic frame, in the state it began that frame."""

    def test_a_scene_switched_to_at_a_frames_end_plays_from_its_first_logic_frame(self, tmp_path):
        header, frames = record_switching_session(
            tmp_path=tmp_path,
            scene_class=SwitchingCountingScene,
            frames=RECORDED_FRAMES,
        )
        start_frame = arriving_scene_start_frame(frames=frames)
        # Set up at the end of frame SWITCHING_TICK - 1; its first dt_tick is the next frame's
        assert start_frame == SWITCHING_TICK
        with running_scene(CountingScene) as manager:
            assert start_playback(
                manager=manager,
                header=header,
                frames=frames,
                then=active_counting_scene(manager),
                options=PlaybackOptions(start_frame=start_frame),
            )
            step(manager, frames=RECORDED_FRAMES - start_frame)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None
            assert outcome_reason(manager) == 'end_of_recording'

    def test_a_scene_that_arrived_by_a_transition_plays_from_its_first_logic_frame(self, tmp_path):
        transition_frames = round(TEST_FADE_SECONDS / FRAME_SECONDS)
        recorded_frames = SWITCHING_TICK + transition_frames + RECORDED_FRAMES
        header, frames = record_switching_session(
            tmp_path=tmp_path,
            scene_class=TransitioningCountingScene,
            frames=recorded_frames,
        )
        start_frame = arriving_scene_start_frame(frames=frames)
        # After the ride: the transition frames ran no logic on it
        assert start_frame > SWITCHING_TICK + 1
        with running_scene(CountingScene) as manager:
            assert start_playback(
                manager=manager,
                header=header,
                frames=frames,
                then=active_counting_scene(manager),
                options=PlaybackOptions(start_frame=start_frame),
            )
            step(manager, frames=recorded_frames - start_frame)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None
            assert outcome_reason(manager) == 'end_of_recording'

    @pytest.mark.parametrize('switch_tick', [SWITCHING_TICK, SWITCHING_TICK + 1])
    def test_fps_events_of_a_scene_that_began_mid_run_play_again_exactly(
        self, tmp_path, mocker: MockerFixture, switch_tick
    ):
        """The FPS event timer and an FPS event posted before the scene began are its start's.

        FPS events every other frame (an interval of FPS_EVENT_INTERVAL_MILLISECONDS): one
        switch tick leaves an FPS event queued for the scene's first logic frame, the other
        none; both need the recorded FPS timer.
        """
        mocker.patch.object(LiveSources, 'frame_seconds', return_value=FRAME_SECONDS)
        mocker.patch.object(SwitchingCountingScene, 'SWITCH_TICK', switch_tick)
        header, frames = record_switching_session(
            tmp_path=tmp_path,
            scene_class=SwitchingCountingScene,
            frames=RECORDED_FRAMES,
            option_overrides={'fps_log_interval_ms': FPS_EVENT_INTERVAL_MILLISECONDS},
        )
        assert any(
            record['type'] == FPSEVENT
            for frame in frames
            for batch in frame['event_batches']
            for record in batch
        )
        start_frame = arriving_scene_start_frame(frames=frames)
        with running_scene(CountingScene) as manager:
            mocker.patch.dict(
                manager.OPTIONS, {'fps_log_interval_ms': FPS_EVENT_INTERVAL_MILLISECONDS}
            )
            assert start_playback(
                manager=manager,
                header=header,
                frames=frames,
                then=active_counting_scene(manager),
                options=PlaybackOptions(start_frame=start_frame),
            )
            step_finishing(manager, frames=RECORDED_FRAMES - start_frame)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None
            assert outcome_reason(manager) == 'end_of_recording'

    def test_a_start_without_its_first_logic_frame_is_refused(self, tmp_path, caplog):
        """A start the playback cannot align (no first logic frame recorded) starts nothing."""
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        header, frames = recorded_trace(path=recording_path)
        del frames[0][SCENE_START_FIELD]['first_logic_frame']
        with running_scene(CountingScene) as manager:
            assert not start_playback(
                manager=manager, header=header, frames=frames, then=manager.active_scene
            )
        assert 'cannot be aligned' in caplog.text


KEY_RELEASE = pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE, mod=0, unicode='', scancode=0)


class TestPlaybacksBackToBack:
    """Attract-mode loops: a scope that ends into a scene starting the next one."""

    def test_a_release_held_by_a_demo_reaches_the_title_never_the_next_demo(
        self, tmp_path, mocker: MockerFixture
    ):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        key_up = mocker.spy(CountingScene, 'on_key_up_event')
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            title = DemoLoopScene(options=live_scene.options)
            title.demo_path = recording_path
            title.demos_left = 1
            assert start_playback_from_recording(manager=manager, path=recording_path, then=title)
            step(manager)
            step(manager, KEY_RELEASE)
            step(manager, frames=SHORT_RECORDED_FRAMES - 2)
            # The first demo ended into the title, whose setup asked for the second
            assert manager.active_scene is title
            step(manager)
            assert manager.playback_session is not None
            step(manager, frames=SHORT_RECORDED_FRAMES)
            assert manager.playback_session is None
            assert manager.active_scene is title
            step(manager)
            # The release reached the title once, and never a playback scene
            assert [call.args[0] for call in key_up.call_args_list] == [title]
            assert manager._playback_requesting_scene is None

    def test_a_scene_starting_right_after_a_scope_plays_back_exactly(self, tmp_path):
        """The events redelivered in its first logic frame are recorded, so it replays."""
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        session_path = tmp_path / 'session.jsonl.gz'
        with running_scene(CountingScene) as manager:
            engine = manager.game_engine
            assert engine is not None
            engine.start_trace_recording(path=session_path)
            # Built while recording: it captures its start
            title = KeyReleaseCountingScene(options=engine.OPTIONS)
            start_playback_from_recording(manager=manager, path=recording_path, then=title)
            step(manager)
            step(manager, KEY_RELEASE)
            step(manager, frames=SHORT_RECORDED_FRAMES - 2)
            assert manager.active_scene is title
            step(manager, frames=LIVE_FRAMES_AFTER)
            engine.stop_trace_recording()
        header, frames = recorded_trace(path=session_path)
        (title_start_frame,) = [
            index
            for index, frame in enumerate(frames)
            if frame.get(SCENE_START_FIELD, {}).get('scene_class') == 'KeyReleaseCountingScene'
        ]
        assert [record['type'] for record in frames[title_start_frame]['redelivered_events']] == [
            pygame.KEYUP
        ]
        with running_scene(CountingScene) as manager:
            assert start_playback(
                manager=manager,
                header=header,
                frames=frames,
                then=active_counting_scene(manager),
                options=PlaybackOptions(start_frame=title_start_frame),
            )
            step(manager, frames=len(frames) - title_start_frame)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None
            assert outcome_reason(manager) == 'end_of_recording'


class TestScopeHousekeeping:
    """The requesting scene is forgotten, teardown drops held posts, events keep their order."""

    def test_the_requesting_scene_is_forgotten(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            start_playback_from_recording(manager=manager, path=recording_path, then=live_scene)
            step(manager)
            assert manager.playback_session is not None
            assert manager._playback_requesting_scene is None
            step(manager, frames=SHORT_RECORDED_FRAMES)
            # Dropped: the asking scene has gone by the next frame
            start_playback_from_recording(manager=manager, path=recording_path, then=live_scene)
            manager.switch_to_scene(CountingScene(options=live_scene.options))
            step(manager)
            assert manager.playback_session is None
            assert manager._playback_requesting_scene is None
            # Terminated with a request pending
            start_playback_from_recording(
                manager=manager, path=recording_path, then=manager.active_scene
            )
            manager.terminate()
            assert manager._playback_requesting_scene is None

    def test_teardown_drops_the_held_live_posts(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            post_event(pygame.event.Event(pygame.USEREVENT, {'live': True}))
            step(manager)
            manager.terminate()
            assert not [event for event in pygame.event.get() if event.type == pygame.USEREVENT]
            assert take_redelivered_events() == []

    def test_held_events_come_back_in_their_original_order(self, tmp_path, mocker: MockerFixture):
        """A live post held on the first pump comes back before a release held later."""
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            engine = manager.game_engine
            assert engine is not None
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            post_event(pygame.event.Event(pygame.USEREVENT, {'live': True}))
            step(manager)
            step(manager, KEY_RELEASE)
            step(manager, frames=SHORT_RECORDED_FRAMES - 2)
            assert manager.playback_session is None
            pump = mocker.spy(engine, '_pump_events')
            step(manager)
            assert [event.type for event in pump.spy_return] == [pygame.USEREVENT, pygame.KEYUP]

    def test_a_cut_off_recording_ends_as_truncated(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        cut_off_after_frame(recording_path=recording_path, frame_number=SHORT_RECORDED_FRAMES - 1)
        with running_scene(CountingScene) as manager:
            start_playback_from_recording(
                manager=manager, path=recording_path, then=active_counting_scene(manager)
            )
            step(manager, frames=SHORT_RECORDED_FRAMES)
            assert manager.playback_session is None
            assert outcome_reason(manager) == 'truncated'


class TestPlayRecordingDemos:
    """SceneManager.play_recording: an attract-mode demo that returns to a scene."""

    def test_a_demo_runs_and_returns(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            title_scene = manager.active_scene
            manager.play_recording(path=recording_path, then=title_scene)
            step(manager)
            assert manager.playback_session is not None
            step(manager, frames=SHORT_RECORDED_FRAMES + 1)
            assert manager.active_scene is title_scene
            assert manager.playback_session is None
            assert outcome_reason(manager) == 'end_of_recording'

    def test_any_key_ends_the_demo(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            title_scene = manager.active_scene
            manager.play_recording(path=recording_path, then=title_scene)
            step(manager, frames=2)
            assert manager.playback_session is not None
            step(manager, press(pygame.K_SPACE))
            assert manager.playback_session is None
            assert manager.active_scene is title_scene
            assert outcome_reason(manager) == 'exit_input'

    def test_an_unusable_demo_is_logged_and_nothing_starts(self, tmp_path, caplog):
        broken_path = tmp_path / 'broken.jsonl.gz'
        broken_path.write_bytes(b'not a trace')
        with running_scene(CountingScene) as manager:
            manager.play_recording(path=broken_path, then=manager.active_scene)
            manager.play_recording(path=tmp_path / 'missing.jsonl.gz', then=manager.active_scene)
            step(manager)
            assert manager.playback_session is None
            assert manager.last_playback_outcome is None
        assert 'demo' in caplog.text
        assert 'cannot be read' in caplog.text
        assert {record.levelname for record in caplog.records if 'demo' in record.message} == {
            'WARNING'
        }

    def test_a_recording_of_another_game_is_logged_and_nothing_starts(self, tmp_path, caplog):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=SHORT_RECORDED_FRAMES)
        header, frames = recorded_trace(path=recording_path)
        frames[0][SCENE_START_FIELD]['scene_class'] = 'NoSuchScene'
        with running_scene(CountingScene) as manager:
            assert not start_playback(
                manager=manager,
                header=header,
                frames=frames,
                then=manager.active_scene,
            )
            step(manager)
            assert manager.playback_session is None
        assert 'No demo: no scene class named NoSuchScene' in caplog.text

    def test_a_diverging_demo_ends_early_and_says_so(self, tmp_path, caplog):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=20)
        tamper_sprite_in_frame(recording_path=recording_path, frame_number=TAMPERED_FRAME + 1)
        with running_scene(CountingScene) as manager:
            title_scene = manager.active_scene
            manager.play_recording(path=recording_path, then=title_scene)
            step(manager, frames=TAMPERED_FRAME + 4)
            assert manager.active_scene is title_scene
            assert manager.playback_session is None
            assert outcome_reason(manager) == 'diverged'
        assert 'demo diverged: frame' in caplog.text
        assert any(
            record.levelname == 'WARNING' and 'demo diverged' in record.message
            for record in caplog.records
        )

    def test_a_cut_off_demo_plays_to_its_cut_off_and_logs_at_info(self, tmp_path, caplog):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        cut_off_after_frame(recording_path=recording_path, frame_number=SHORT_RECORDED_FRAMES - 1)
        with caplog.at_level(logging.INFO), running_scene(CountingScene) as manager:
            manager.play_recording(path=recording_path, then=manager.active_scene)
            step(manager, frames=SHORT_RECORDED_FRAMES + 1)
            assert outcome_reason(manager) == 'truncated'
        assert 'truncated' in caplog.text
        assert not [
            record
            for record in caplog.records
            if record.levelname == 'WARNING'
            and record.name.startswith(('game.replay', 'game.scenes'))
        ]

    def test_a_demo_asked_for_during_a_demo_is_refused(self, tmp_path, caplog):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=RECORDED_FRAMES)
        with running_scene(CountingScene) as manager:
            manager.play_recording(path=recording_path, then=manager.active_scene)
            manager.play_recording(path=recording_path, then=manager.active_scene)
            step(manager)
            assert manager.playback_session is not None
        assert 'already starting or playing' in caplog.text
