"""The instant-replay journal (glitchygames/instant_replay.py).

A scene that sets ``INSTANT_REPLAY_SECONDS`` keeps, in memory, the recording of every frame
since its first logic frame; played back through the playback scope it matches exactly.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame
import pytest
from scripts.record_golden_traces import (
    FRAME_SECONDS,
    GAME_SCENES,
    press,
    record_trace,
    release,
)

from glitchygames.events import FPSEVENT
from glitchygames.input.state import IDLE_INPUT
from glitchygames.instant_replay import (
    JOURNAL_BYTES_PER_MINUTE_LIMIT,
    JOURNAL_START_FRAME,
    InstantReplayJournal,
    JournalRecording,
)
from glitchygames.live_sources import LiveSources
from glitchygames.recording import (
    INTERNAL_ORIGIN,
    SAVES_OPENED_FIELD,
    SCENE_START_FIELD,
    post_event,
)
from glitchygames.replay.playback import INSTANT_PLAYBACK, PlaybackOptions, start_playback
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.sources import active_sources
from tests.replay.playback_fixtures import (
    COUNTING_SAVE_NAMESPACE,
    CountingScene,
    InputReadingScene,
    KeyReleaseCountingScene,
    PostingCountingScene,
    SavingCountingScene,
    active_counting_scene,
    step_finishing,
)
from tests.world.test_frame_integration import CameraFreeScene, running_scene, step

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pytest_mock import MockerFixture

    from glitchygames.events.base import HashableEvent
    from glitchygames.replay.playback import PlaybackOutcome

INSTANT_REPLAY_TEST_SECONDS = 10.0
# Spec 5.4: 60 s of scene time by default
DEFAULT_FAST_FORWARD_BUDGET_SECONDS = 60.0
JOURNALED_FRAMES = 5
BUDGET_FRAMES = 10
# PaddleSlap's golden script pauses at frame 450 and resumes at 510: both are journaled
PADDLESLAP_JOURNALED_FRAMES = 600
FRAMES_PER_MINUTE = 3600
# FPS events every other frame at 60 FPS (posted each half interval: 25 ms)
FPS_EVENT_INTERVAL_MILLISECONDS = 50
# The frame of the live run a scene is switched to (so its first logic frame is mid-run)
SWITCH_FRAME = 3
SCRIPTED_MOUSE_POSITION = (123, 45)
# Posts an SDL-type event every this many ticks (InstantExposingScene)
EXPOSE_EVERY_TICKS = 2


class InstantCountingScene(CountingScene):
    """A counting scene that offers instant replay; P pauses it (Space resumes it)."""

    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = INSTANT_REPLAY_TEST_SECONDS

    @override
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Pause on P, as a game's pause key does."""
        if event.key == pygame.K_p:
            self.pause()
            return
        super().on_key_down_event(event)


class SwitchingToInstantScene(CountingScene):
    """Switches to an InstantCountingScene with next_scene on a tick (at the frame's end)."""

    SWITCH_TICK: ClassVar[int] = SWITCH_FRAME

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Request the instant-replay scene on SWITCH_TICK."""
        super().dt_tick(dt)
        if self.frames_ticked == self.SWITCH_TICK:
            self.next_scene = InstantCountingScene(options=self.options)


class InstantKeyReleaseScene(KeyReleaseCountingScene):
    """Moves its marker for every key release (lost or extra input diverges)."""

    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = INSTANT_REPLAY_TEST_SECONDS


class InstantPostingScene(PostingCountingScene):
    """Posts a custom event every tick."""

    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = INSTANT_REPLAY_TEST_SECONDS


class InstantExposingScene(CountingScene):
    """Posts an SDL-type event (a window expose) every other tick: internal only when tracked."""

    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = INSTANT_REPLAY_TEST_SECONDS

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Post the expose event on every other tick."""
        super().dt_tick(dt)
        if self.frames_ticked % EXPOSE_EVERY_TICKS == 0:
            post_event(pygame.event.Event(pygame.VIDEOEXPOSE, {}))

    @override
    def on_video_expose_event(self: Self, event: HashableEvent) -> None:
        """Move the marker down a pixel per expose (a lost or extra one diverges)."""
        super().on_video_expose_event(event)
        self.marker.rect.y += 1


class InstantSavingScene(SavingCountingScene):
    """Writes its save slot on its third tick, opening the store then."""

    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = INSTANT_REPLAY_TEST_SECONDS


class InstantInputReadingScene(InputReadingScene):
    """Keeps the polled mouse position each tick saw."""

    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = INSTANT_REPLAY_TEST_SECONDS


def journal_of(manager: SceneManager) -> InstantReplayJournal:
    """Return the scene manager's journal, checked to exist.

    Returns:
        The journal.

    """
    journal = manager.instant_replay_journal
    assert journal is not None
    return journal


def play_journal(*, manager: SceneManager, recording: JournalRecording, then: Scene) -> None:
    """Play a journal's recording in a playback scope until it ends, and check it matched.

    Args:
        manager: The running scene manager (stepped by the golden harness).
        recording: The journal's recording.
        then: The scene to return to.

    """
    assert start_playback(
        manager=manager,
        header=recording.header,
        frames=recording.frames,
        then=then,
        options=PlaybackOptions(kind=INSTANT_PLAYBACK, start_frame=recording.start_frame),
    )
    step(manager, frames=len(recording.frames) - recording.start_frame)
    assert manager.playback_session is None
    result = manager.last_playback_result
    assert result is not None
    assert result.divergence is None, result.report()
    assert result.end_reason == 'end_of_recording'
    assert manager.active_scene is then


def event_records(*, frames: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return every event record of every batch, in order.

    Returns:
        The records.

    """
    return [record for frame in frames for batch in frame['event_batches'] for record in batch]


class TestTheJournal:
    """What an opted-in scene keeps, and for how long."""

    def test_journal_records_every_frame_of_an_opted_in_scene(self):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=JOURNALED_FRAMES)
            journal = journal_of(manager)
            assert journal.frame_count == JOURNALED_FRAMES
            assert journal.game_seconds == pytest.approx(JOURNALED_FRAMES * FRAME_SECONDS)
            recording = journal.as_recording()
            assert recording.start_frame == JOURNAL_START_FRAME
            assert len(recording.frames) == JOURNAL_START_FRAME + JOURNALED_FRAMES
            # The scene's start is on its first logic frame, the journal's first
            start = manager.active_scene_start
            assert start is not None
            assert recording.frames[recording.start_frame][SCENE_START_FIELD] == start.to_json()

    def test_scenes_without_the_attribute_keep_no_journal(self):
        with running_scene(CountingScene) as manager:
            step(manager, frames=JOURNALED_FRAMES)
            assert manager.instant_replay_journal is None

    def test_budget(self):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=BUDGET_FRAMES)
            journal = journal_of(manager)
            assert journal.within_budget(maximum_seconds=1.0)
            assert not journal.within_budget(maximum_seconds=JOURNALED_FRAMES * FRAME_SECONDS)

    def test_the_scene_defaults(self):
        assert Scene.INSTANT_REPLAY_SECONDS is None
        assert Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS == DEFAULT_FAST_FORWARD_BUDGET_SECONDS

    def test_journal_memory_per_minute_stays_bounded(self):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=FRAMES_PER_MINUTE)
            journal = journal_of(manager)
            assert journal.frame_count == FRAMES_PER_MINUTE
            assert journal.memory_bytes() < JOURNAL_BYTES_PER_MINUTE_LIMIT

    def test_the_journal_ends_past_its_fast_forward_budget(self, mocker: MockerFixture):
        """No instant replay can be shown once game time passes the budget: nothing is kept."""
        mocker.patch.object(
            InstantCountingScene,
            'MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS',
            (JOURNALED_FRAMES + 0.5) * FRAME_SECONDS,
        )
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=JOURNALED_FRAMES)
            assert manager.instant_replay_journal is not None
            step(manager)
            assert manager.instant_replay_journal is None

    def test_leaving_the_scene_drops_its_journal(self):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=2)
            assert manager.instant_replay_journal is not None
            manager.switch_to_scene(CameraFreeScene(options=manager.OPTIONS))
            step(manager)
            assert manager.instant_replay_journal is None

    def test_a_scene_switched_to_mid_run_journals_from_its_first_logic_frame(self):
        with running_scene(CameraFreeScene) as manager:
            step(manager, frames=SWITCH_FRAME)
            manager.switch_to_scene(InstantCountingScene(options=manager.OPTIONS))
            # Set up, but no logic frame has run on it yet
            assert manager.instant_replay_journal is None
            step(manager, frames=JOURNALED_FRAMES)
            assert journal_of(manager).frame_count == JOURNALED_FRAMES

    def test_posts_are_tracked_in_plain_live_play(self):
        """An SDL-type event the scene posts is recorded as internal, as a recording would."""
        with running_scene(InstantExposingScene) as manager:
            step(manager, frames=JOURNALED_FRAMES)
            recording = journal_of(manager).as_recording()
        exposes = [
            record
            for record in event_records(frames=recording.frames)
            if record['type'] == pygame.VIDEOEXPOSE
        ]
        assert exposes
        assert {record['origin'] for record in exposes} == {INTERNAL_ORIGIN}


class TestPlayingTheJournalBack:
    """A journal's recording plays back through the playback scope with no divergence."""

    def test_the_journal_plays_back_exactly(self):
        with running_scene(InstantKeyReleaseScene) as manager:
            step(manager, frames=2)
            step(manager, press(pygame.K_SPACE))
            step(manager, release(pygame.K_SPACE), frames=3)
            live_scene = active_counting_scene(manager)
            play_journal(
                manager=manager, recording=journal_of(manager).as_recording(), then=live_scene
            )

    def test_the_journals_posts_play_back_exactly(self):
        with running_scene(InstantExposingScene) as manager:
            step(manager, frames=JOURNALED_FRAMES)
            live_scene = active_counting_scene(manager)
            play_journal(
                manager=manager, recording=journal_of(manager).as_recording(), then=live_scene
            )

    def test_a_save_store_first_opened_in_the_scene_plays_back(self):
        with running_scene(InstantSavingScene) as manager:
            step(manager, frames=JOURNALED_FRAMES)
            recording = journal_of(manager).as_recording()
            assert any(
                COUNTING_SAVE_NAMESPACE in frame.get(SAVES_OPENED_FIELD, {})
                for frame in recording.frames
            )
            play_journal(manager=manager, recording=recording, then=active_counting_scene(manager))

    def test_the_input_held_as_the_scene_began_plays_back(self, mocker: MockerFixture):
        """The first logic frame's dt_tick polls the input from before it, not idle input."""
        with running_scene(CameraFreeScene) as manager:
            live_input = dataclasses.replace(IDLE_INPUT, mouse_position=SCRIPTED_MOUSE_POSITION)
            mocker.patch.object(active_sources(), 'input_snapshot', return_value=live_input)
            step(manager, frames=SWITCH_FRAME)
            manager.switch_to_scene(InstantInputReadingScene(options=manager.OPTIONS))
            step(manager, frames=JOURNALED_FRAMES)
            live_scene = manager.active_scene
            assert isinstance(live_scene, InstantInputReadingScene)
            assert live_scene.mouse_positions[0] == SCRIPTED_MOUSE_POSITION
            recording = journal_of(manager).as_recording()
            play_journal(manager=manager, recording=recording, then=live_scene)

    @pytest.mark.parametrize(
        ('switch_tick', 'earlier_event_count'), [(SWITCH_FRAME, 0), (SWITCH_FRAME + 1, 1)]
    )
    def test_fps_events_posted_before_the_scene_began_play_back(
        self, mocker: MockerFixture, switch_tick, earlier_event_count
    ):
        """An FPS event queued for the scene's first logic frame is its start's, not its logic's.

        FPS events every other frame: one switch tick leaves one queued for the scene's first
        logic frame, the other none. Posts are tracked from the scene's setup (the end of the
        switching frame, before its FPS event), so the count is exact in plain live play.
        """
        mocker.patch.object(LiveSources, 'frame_seconds', return_value=FRAME_SECONDS)
        mocker.patch.object(SwitchingToInstantScene, 'SWITCH_TICK', switch_tick)
        with running_scene(SwitchingToInstantScene) as manager:
            mocker.patch.dict(
                manager.OPTIONS, {'fps_log_interval_ms': FPS_EVENT_INTERVAL_MILLISECONDS}
            )
            step_finishing(manager, frames=switch_tick + JOURNALED_FRAMES)
            live_scene = active_counting_scene(manager)
            assert isinstance(live_scene, InstantCountingScene)
            recording = journal_of(manager).as_recording()
            assert any(
                record['type'] == FPSEVENT for record in event_records(frames=recording.frames)
            )
            start = live_scene.scene_start
            assert start is not None
            assert start.first_logic_frame is not None
            assert start.first_logic_frame.earlier_internal_event_count == earlier_event_count
            assert start_playback(
                manager=manager,
                header=recording.header,
                frames=recording.frames,
                then=live_scene,
                options=PlaybackOptions(kind=INSTANT_PLAYBACK, start_frame=recording.start_frame),
            )
            step_finishing(manager, frames=len(recording.frames) - recording.start_frame)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None, result.report()
            assert result.end_reason == 'end_of_recording'


class TestAnExampleGame:
    """PaddleSlap's golden script, paused and resumed, plays back from its journal exactly."""

    def test_paddleslaps_journal_plays_back_exactly(self, mocker: MockerFixture):
        scene_class = GAME_SCENES['paddleslap']
        mocker.patch.object(scene_class, 'INSTANT_REPLAY_SECONDS', INSTANT_REPLAY_TEST_SECONDS)
        outcomes: list[PlaybackOutcome] = []

        def start_and_watch(*, frame_number: int, scene: Scene, sprite_ids: object) -> None:
            """Start playing the journal after its last frame; keep how the playback ends."""
            del sprite_ids
            # The harness installs its own scene manager singleton for the run
            manager = SceneManager()
            if frame_number == PADDLESLAP_JOURNALED_FRAMES - 1:
                recording = journal_of(manager).as_recording()
                assert len(recording.frames) == JOURNAL_START_FRAME + PADDLESLAP_JOURNALED_FRAMES
                assert start_playback(
                    manager=manager,
                    header=recording.header,
                    frames=recording.frames,
                    then=scene,
                    options=PlaybackOptions(
                        kind=INSTANT_PLAYBACK, start_frame=recording.start_frame
                    ),
                )
            outcome = manager.last_playback_outcome
            if outcome is not None and not outcomes:
                outcomes.append(outcome)
                result = manager.last_playback_result
                assert result is not None
                assert result.divergence is None, result.report()

        record_trace(
            'paddleslap',
            frame_count=2 * PADDLESLAP_JOURNALED_FRAMES + 1,
            frame_observer=start_and_watch,
        )
        assert [outcome.reason for outcome in outcomes] == ['end_of_recording']
        assert outcomes[0].frames_played == PADDLESLAP_JOURNALED_FRAMES


class TestThePauseScreen:
    """A paused stretch is kept: the pause screen's frames, recorded as its own."""

    def test_pause_and_resume_keep_the_journal(self):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=JOURNALED_FRAMES)
            journal = journal_of(manager)
            game_seconds_before_pause = journal.game_seconds
            step(manager, press(pygame.K_p))
            step(manager, release(pygame.K_p))
            assert isinstance(manager.active_scene, PauseScene)
            assert manager.instant_replay_journal is journal
            step(manager, press(pygame.K_SPACE))
            step(manager, release(pygame.K_SPACE))
            assert isinstance(manager.active_scene, InstantCountingScene)
            assert manager.instant_replay_journal is journal
            # Frames of the pause screen are recorded as its own and add no scene time
            recording = journal.as_recording()
            scene_names = [frame['scene'] for frame in recording.frames[recording.start_frame :]]
            assert 'PauseScene' in scene_names
            assert scene_names[-1] == 'InstantCountingScene'
            assert journal.game_seconds == pytest.approx(game_seconds_before_pause + FRAME_SECONDS)

    def test_a_journal_with_a_paused_stretch_plays_back_exactly(self):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=2)
            step(manager, press(pygame.K_p))
            step(manager, release(pygame.K_p), frames=2)
            step(manager, press(pygame.K_SPACE))
            step(manager, release(pygame.K_SPACE), frames=2)
            live_scene = active_counting_scene(manager)
            play_journal(
                manager=manager, recording=journal_of(manager).as_recording(), then=live_scene
            )


class TestPlaybackScopesAndTheJournal:
    """A playback scope during the scene ends its journal; the scope's scene keeps none."""

    def test_a_playback_scope_ends_the_live_scenes_journal(self):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=2)
            assert manager.instant_replay_journal is not None
            live_scene = active_counting_scene(manager)
            recording = journal_of(manager).as_recording()
            assert start_playback(
                manager=manager,
                header=recording.header,
                frames=recording.frames,
                then=live_scene,
                options=PlaybackOptions(kind=INSTANT_PLAYBACK, start_frame=recording.start_frame),
            )
            step(manager)
            # The rebuilt scene opts in too, but a scope's scene keeps no journal
            assert manager.playback_session is not None
            assert manager.instant_replay_journal is None
            step(manager, frames=len(recording.frames))
            assert manager.active_scene is live_scene
            assert manager.instant_replay_journal is None


class TestReplayingTheSession:
    """Replaying a recorded session builds the same journal as the live session did."""

    def test_the_replayed_journal_is_the_live_one(self, tmp_path):
        session_path = tmp_path / 'session.jsonl.gz'
        with running_scene(InstantPostingScene) as manager:
            engine = manager.game_engine
            assert engine is not None
            engine.start_trace_recording(path=session_path)
            self._play(manager=manager)
            live_recording = journal_of(manager).as_recording()
            engine.stop_trace_recording()
        with running_scene(
            InstantPostingScene, extra_arguments=['--replay-trace', str(session_path), '--headless']
        ) as manager:
            engine = manager.game_engine
            assert engine is not None
            replay_sources = engine.replay_sources
            assert replay_sources is not None
            self._play(manager=manager)
            replayed_recording = journal_of(manager).as_recording()
            replay_sources.finish_run()
            assert replay_sources.result.divergence is None
        assert replayed_recording.frames == live_recording.frames

    @staticmethod
    def _play(*, manager: SceneManager) -> None:
        """Run frames with a key pressed and released among them."""
        step(manager, frames=2)
        step(manager, press(pygame.K_SPACE))
        step(manager, release(pygame.K_SPACE), frames=JOURNALED_FRAMES)
