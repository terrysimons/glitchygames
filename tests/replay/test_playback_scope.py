"""The playback scope (glitchygames/replay/playback.py).

A rebuilt scene plays a recording on scoped sources while the live game waits untouched.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

import pygame
from scripts.record_golden_traces import FRAME_SECONDS, press, release

from glitchygames.randomness import random_stream
from glitchygames.recording import SCENE_START_FIELD, post_event
from glitchygames.replay.playback import (
    PlaybackOptions,
    PlaybackSources,
    find_scene_class,
    start_playback,
    start_playback_from_recording,
)
from glitchygames.sources import active_sources, has_scoped_sources
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
    CountingScene,
    PostingCountingScene,
    SavingCountingScene,
    active_counting_scene,
    record_counting_scene,
)
from tests.world.test_frame_integration import (
    TEST_FADE_SECONDS,
    CameraFreeScene,
    running_scene,
    step,
)

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


def recorded_trace(*, path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return a recording's header fields and frames.

    Returns:
        The header (without the frames) and the decoded frames.

    """
    trace = read_trace_result(path=path).trace
    return {name: value for name, value in trace.items() if name != 'frames'}, trace['frames']


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
        recording_path = tmp_path / 'later.jsonl.gz'
        with running_scene(CountingScene) as manager:
            engine = manager.game_engine
            assert engine is not None
            engine.start_trace_recording(path=recording_path)
            # Built while recording: it captures its start, which the frame it begins holds
            first_scene = CountingScene(options=engine.OPTIONS)
            manager.switch_to_scene(first_scene)
            step(manager, frames=4)
            # Switched to between frames: frame 4 is the second scene's first whole frame
            manager.switch_to_scene(CountingScene(options=engine.OPTIONS))
            step(manager, frames=SHORT_RECORDED_FRAMES)
            engine.stop_trace_recording()
        header, frames = recorded_trace(path=recording_path)
        assert SCENE_START_FIELD in frames[4]
        with running_scene(CountingScene) as manager:
            assert start_playback(
                manager=manager,
                header=header,
                frames=frames,
                then=active_counting_scene(manager),
                options=PlaybackOptions(start_frame=4),
            )
            step(manager, frames=SHORT_RECORDED_FRAMES)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None
            assert result.end_reason == 'end_of_recording'
            assert result.frames_replayed == 4 + SHORT_RECORDED_FRAMES

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
